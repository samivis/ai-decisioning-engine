#!/usr/bin/env python
"""Train the population scorecards and write the model registry.

Trains two logistic-regression scorecards on standardized features
(StandardScaler + LogisticRegression pipeline), one per population in
``schemas.MODEL_FEATURES``:

    full_file  : 5 features
    thin_file  : 3 features

For each population it produces a v1 artifact (full data) and a v2 variant
(retrained after dropping a random 30 percent of rows with a different
seed) so v1 and v2 decisions can genuinely differ, which the dispute-replay
demo needs. Artifacts land in ``models/{population}_{version}.joblib`` and
``models/registry.json`` maps "{population}:{version}" to path, sha256,
feature schema version, feature list, training timestamp, and data
provenance.

Real LendingClub data: pass ``--data path/to/accepted.csv``. Column mapping
and target construction (default = Charged Off or Late 120+, Current
excluded) are documented in ``scripts/make_synthetic_training_data.py``.

Usage::

    .venv/bin/python scripts/train_model.py [--data CSV] [--version v1]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from decisioning.schemas import FEATURE_SCHEMA_VERSION, MODEL_FEATURES  # noqa: E402

from make_synthetic_training_data import OUTPUT_PATH as SYNTHETIC_CSV  # noqa: E402
from make_synthetic_training_data import generate  # noqa: E402

MODELS_DIR = REPO_ROOT / "models"
V2_DROP_FRACTION = 0.30
V2_SEED = 4242


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_training_data(data_path: Path | None = None) -> tuple[pd.DataFrame, str]:
    """Load the training CSV, generating the synthetic stand-in if missing.

    Returns (frame, provenance) where provenance is "synthetic-standin" or
    "lendingclub".
    """
    path = data_path or SYNTHETIC_CSV
    if path == SYNTHETIC_CSV:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            generate().to_csv(path, index=False)
            print(f"Synthetic training data not found; generated {path}")
        return pd.read_csv(path), "synthetic-standin"
    return _load_lendingclub(path), "lendingclub"


def _load_lendingclub(path: Path) -> pd.DataFrame:
    """Map the real Kaggle accepted-loans CSV onto the model feature space."""
    usecols = ["annual_inc", "dti", "delinq_2yrs", "emp_length", "open_acc", "loan_status"]
    frame = pd.read_csv(path, usecols=usecols, low_memory=False)

    default_statuses = {"Charged Off", "Late (31-120 days)"}
    paid_statuses = {"Fully Paid"}
    # Exclude Current and other in-progress loans: unknown outcomes.
    frame = frame[frame["loan_status"].isin(default_statuses | paid_statuses)].copy()
    frame["default"] = frame["loan_status"].isin(default_statuses).astype(int)

    def parse_emp_length(raw: object) -> float:
        text = str(raw)
        if "10+" in text:
            return 10.0
        if "< 1" in text:
            return 0.5
        digits = "".join(ch for ch in text if ch.isdigit())
        return float(digits) if digits else 0.0

    out = pd.DataFrame(
        {
            "annual_income_estimate": frame["annual_inc"].fillna(0.0),
            "dti_proxy": (frame["dti"].fillna(0.0) / 100.0).clip(lower=0.0),
            "delinquency_proxy": frame["delinq_2yrs"].fillna(0.0),
            "employment_length_years": frame["emp_length"].map(parse_emp_length),
            "open_accounts": frame["open_acc"].fillna(0).astype(int),
            "default": frame["default"],
        }
    )
    return out.dropna()


def train_population(
    frame: pd.DataFrame, population: str, seed: int = 0
) -> tuple[Pipeline, float]:
    """Fit one scorecard pipeline; return (pipeline, holdout AUC)."""
    features = MODEL_FEATURES[population]
    X = frame[features]
    y = frame["default"]
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )
    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("logreg", LogisticRegression(max_iter=1000, random_state=seed)),
        ]
    )
    pipeline.fit(X_tr, y_tr)
    auc = roc_auc_score(y_te, pipeline.predict_proba(X_te)[:, 1])
    return pipeline, auc


def train_all(
    data_path: Path | None = None,
    models_dir: Path = MODELS_DIR,
    base_version: str = "v1",
) -> dict[str, dict]:
    """Train v1 and v2 scorecards for every population; write registry.json.

    Returns the registry dict.
    """
    frame, provenance = load_training_data(data_path)
    models_dir.mkdir(parents=True, exist_ok=True)

    registry_path = models_dir / "registry.json"
    registry: dict[str, dict] = (
        json.loads(registry_path.read_text()) if registry_path.exists() else {}
    )

    # v2 trains on a different sample: drop a random 30 percent of rows.
    frame_v2 = frame.sample(frac=1.0 - V2_DROP_FRACTION, random_state=V2_SEED)
    variants = [(base_version, frame, 0), ("v2", frame_v2, V2_SEED)]

    for population in MODEL_FEATURES:
        for version, data, seed in variants:
            pipeline, auc = train_population(data, population, seed=seed)
            artifact = models_dir / f"{population}_{version}.joblib"
            joblib.dump(pipeline, artifact)
            key = f"{population}:{version}"
            registry[key] = {
                "path": artifact.name,
                "sha256": _sha256(artifact),
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "features": MODEL_FEATURES[population],
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "data_provenance": provenance,
            }
            print(f"{key}: AUC={auc:.4f}  n={len(data):,}  -> {artifact.name}")

    registry_path.write_text(json.dumps(registry, indent=2) + "\n")
    print(f"Registry written to {registry_path}")
    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Train population scorecards.")
    parser.add_argument("--data", type=Path, default=None, help="Training CSV path")
    parser.add_argument("--version", default="v1", help="Base version label")
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR)
    args = parser.parse_args()
    train_all(args.data, args.models_dir, args.version)


if __name__ == "__main__":
    main()
