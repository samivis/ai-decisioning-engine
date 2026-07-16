"""Tests for the ingest lane: fixtures, ingest.py, features.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from decisioning.features import extract_features
from decisioning.ingest import DEFAULT_FIXTURES_DIR, FixtureError, list_personas, load_fixture
from decisioning.schemas import FeatureVector

REPO_ROOT = Path(__file__).resolve().parents[1]
PERSONAS = ["healthy_full_file", "distressed_full_file", "thin_file"]


@pytest.fixture(scope="module")
def vectors() -> dict[str, FeatureVector]:
    return {name: extract_features(load_fixture(name)) for name in PERSONAS}


def test_list_personas_finds_all_fixtures() -> None:
    assert set(PERSONAS) <= set(list_personas(DEFAULT_FIXTURES_DIR))


@pytest.mark.parametrize("persona", PERSONAS)
def test_each_persona_loads_and_extracts(persona: str, vectors: dict[str, FeatureVector]) -> None:
    fixture = load_fixture(persona)
    assert fixture["persona"] == persona
    assert fixture["provenance"] == "synthetic, never captured from live API"
    assert isinstance(vectors[persona], FeatureVector)


def test_routing(vectors: dict[str, FeatureVector]) -> None:
    assert vectors["healthy_full_file"].population == "full_file"
    assert vectors["distressed_full_file"].population == "full_file"
    assert vectors["thin_file"].population == "thin_file"
    assert vectors["thin_file"].open_accounts <= 2
    assert vectors["healthy_full_file"].open_accounts >= 3


def test_directional_signals(vectors: dict[str, FeatureVector]) -> None:
    healthy = vectors["healthy_full_file"]
    distressed = vectors["distressed_full_file"]
    thin = vectors["thin_file"]

    assert distressed.nsf_count_90d >= 4
    assert healthy.nsf_count_90d == 0
    assert thin.nsf_count_90d == 0
    assert distressed.dti_proxy > healthy.dti_proxy
    assert distressed.delinquency_proxy > healthy.delinquency_proxy
    assert abs(healthy.annual_income_estimate - 85000) <= 0.20 * 85000
    assert thin.months_of_history < 6
    assert healthy.months_of_history >= 6


def test_empty_transactions_yield_zeros() -> None:
    fixture = {
        "persona": "empty",
        "generated_by": "test",
        "provenance": "synthetic, never captured from live API",
        "accounts": [],
        "transactions": [],
    }
    fv = extract_features(fixture)
    assert fv.annual_income_estimate == 0.0
    assert fv.dti_proxy == 0.0
    assert fv.delinquency_proxy == 0.0
    assert fv.employment_length_years == 0.0
    assert fv.open_accounts == 0
    assert fv.nsf_count_90d == 0
    assert fv.months_of_history == 0
    assert fv.balance_volatility == 0.0


def test_missing_fixture_raises(tmp_path: Path) -> None:
    with pytest.raises(FixtureError):
        load_fixture("no_such_persona", fixtures_dir=tmp_path)


def test_malformed_fixture_raises(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text('{"persona": "broken", "accounts": []}')
    with pytest.raises(FixtureError):
        load_fixture("broken", fixtures_dir=tmp_path)
    (tmp_path / "notjson.json").write_text("{nope")
    with pytest.raises(FixtureError):
        load_fixture("notjson", fixtures_dir=tmp_path)


def test_fixture_generation_is_deterministic(tmp_path: Path) -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import make_fixtures
    finally:
        sys.path.pop(0)

    run_a = tmp_path / "a"
    run_b = tmp_path / "b"
    make_fixtures.main(run_a)
    make_fixtures.main(run_b)
    for persona in PERSONAS:
        assert (run_a / f"{persona}.json").read_bytes() == (run_b / f"{persona}.json").read_bytes()
        # Checked-in fixtures match a fresh run too.
        assert (run_a / f"{persona}.json").read_bytes() == (DEFAULT_FIXTURES_DIR / f"{persona}.json").read_bytes()


def test_checked_in_fixtures_are_valid_json() -> None:
    for persona in PERSONAS:
        data = json.loads((DEFAULT_FIXTURES_DIR / f"{persona}.json").read_text())
        assert data["generated_by"] == "scripts/make_fixtures.py"
