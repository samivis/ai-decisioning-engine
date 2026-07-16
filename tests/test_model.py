"""Model lane tests: registry integrity, exact contributions, stability.

Run with: .venv/bin/pytest tests/test_model.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from decisioning.model import ModelIntegrityError, Scorecard
from decisioning.schemas import MODEL_FEATURES, FeatureVector, ScoreResult

from make_synthetic_training_data import generate
from train_model import train_all, train_population


@pytest.fixture(scope="module")
def training_frame():
    return generate(rows=20_000)


@pytest.fixture(scope="module")
def models_dir(tmp_path_factory, training_frame):
    """Train v1 + v2 into a temp models dir; tests never depend on repo artifacts."""
    out = tmp_path_factory.mktemp("models")
    csv = tmp_path_factory.mktemp("data") / "train.csv"
    training_frame.to_csv(csv, index=False)
    # train_all treats explicit --data paths as real LendingClub CSVs, so
    # point the module's synthetic default at our temp csv instead.
    import train_model

    original = train_model.SYNTHETIC_CSV
    train_model.SYNTHETIC_CSV = csv
    try:
        train_all(None, models_dir=out)
    finally:
        train_model.SYNTHETIC_CSV = original
    return out


def make_fv(population="full_file", **overrides) -> FeatureVector:
    base = dict(
        population=population,
        annual_income_estimate=60_000.0,
        dti_proxy=0.35,
        delinquency_proxy=1.0,
        employment_length_years=5.0,
        open_accounts=8,
        nsf_count_90d=0,
        months_of_history=24,
        balance_volatility=0.2,
    )
    base.update(overrides)
    return FeatureVector(**base)


@pytest.mark.parametrize("population", ["full_file", "thin_file"])
@pytest.mark.parametrize("version", ["v1", "v2"])
def test_load_and_score_valid_result(models_dir, population, version):
    card = Scorecard.load(population, version, models_dir=models_dir)
    result = card.score(make_fv(population))
    assert isinstance(result, ScoreResult)
    assert result.model_version == f"{population}:{version}"
    assert 0.0 <= result.probability_of_default <= 1.0
    assert len(result.model_sha256) == 64
    # Contributions cover exactly the population's features.
    assert {c.feature for c in result.contributions} == set(MODEL_FEATURES[population])
    # Ranked by absolute contribution, descending.
    mags = [abs(c.contribution) for c in result.contributions]
    assert mags == sorted(mags, reverse=True)


def test_sha256_tamper_raises_integrity_error(models_dir):
    artifact = models_dir / "full_file_v1.joblib"
    original = artifact.read_bytes()
    try:
        artifact.write_bytes(original + b"tampered")
        with pytest.raises(ModelIntegrityError):
            Scorecard.load("full_file", "v1", models_dir=models_dir)
    finally:
        artifact.write_bytes(original)


def test_unknown_population_or_version_raises_key_error(models_dir):
    with pytest.raises(KeyError, match="thin_file:v99"):
        Scorecard.load("thin_file", "v99", models_dir=models_dir)
    with pytest.raises(KeyError):
        Scorecard.load("no_such_population", "v1", models_dir=models_dir)


def test_contribution_exactness(models_dir):
    """sum(contributions) + intercept == logit(probability), exactly."""
    card = Scorecard.load("full_file", "v1", models_dir=models_dir)
    result = card.score(make_fv())
    total = sum(c.contribution for c in result.contributions) + card.intercept
    p = result.probability_of_default
    logit = np.log(p / (1.0 - p))
    assert np.allclose(total, logit, atol=1e-9)


def test_bootstrap_coefficient_sign_stability(training_frame):
    """Signs of each coefficient stable in >= 90 percent of bootstrap refits."""
    rng = np.random.default_rng(7)
    sub = training_frame.sample(n=5_000, random_state=7)
    features = MODEL_FEATURES["full_file"]
    signs = []
    for _ in range(20):
        resampled = sub.sample(frac=1.0, replace=True, random_state=int(rng.integers(1 << 30)))
        pipeline, _ = train_population(resampled, "full_file", seed=0)
        signs.append(np.sign(pipeline.named_steps["logreg"].coef_[0]))
    signs = np.array(signs)
    modal_sign = np.sign(signs.sum(axis=0))
    stability = (signs == modal_sign).mean(axis=0)
    for name, stab in zip(features, stability):
        assert stab >= 0.9, f"coefficient sign for {name} unstable: {stab:.2f}"


def test_monotonic_sanity(models_dir):
    """Higher dti raises PD; higher income lowers it."""
    card = Scorecard.load("full_file", "v1", models_dir=models_dir)
    base = card.score(make_fv()).probability_of_default
    high_dti = card.score(make_fv(dti_proxy=0.80)).probability_of_default
    high_income = card.score(make_fv(annual_income_estimate=200_000.0)).probability_of_default
    assert high_dti > base
    assert high_income < base
