"""Scorecard loading and scoring with exact per-feature contributions.

Scoring pipeline (linear scorecard, so contributions are exact):

    FeatureVector
        |
        v
    +---------------------+     +------------------------+
    | select population   | --> | StandardScaler         |
    | features (schemas.  |     | z_i = (x_i - mu_i)/s_i |
    | MODEL_FEATURES)     |     +------------------------+
    +---------------------+                 |
                                            v
                              +---------------------------+
                              | LogisticRegression        |
                              | logit = b0 + sum(w_i*z_i) |
                              +---------------------------+
                                            |
                    contribution_i = w_i * z_i (signed, exact)
                                            |
                                            v
                              +---------------------------+
                              | ScoreResult               |
                              | pd = sigmoid(logit)       |
                              | contributions ranked by   |
                              | |contribution| descending |
                              +---------------------------+

Artifacts are loaded only through models/registry.json and verified by
sha256 before deserialization; a mismatch raises ModelIntegrityError.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from .schemas import Contribution, FeatureVector, Population, ScoreResult

DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[2] / "models"


class ModelIntegrityError(Exception):
    """Raised when an artifact's sha256 does not match its registry entry."""


class Scorecard:
    """A registry-backed logistic-regression scorecard for one population.

    Load through :meth:`load`; never deserialize artifacts directly, so the
    sha256 check in the registry cannot be bypassed.
    """

    def __init__(
        self,
        population: Population,
        version: str,
        pipeline: Pipeline,
        sha256: str,
        features: list[str],
    ) -> None:
        self.population = population
        self.version = version
        self.pipeline = pipeline
        self.sha256 = sha256
        self.features = features

    @property
    def model_version(self) -> str:
        return f"{self.population}:{self.version}"

    @classmethod
    def load(
        cls,
        population: Population,
        version: str,
        models_dir: Path | str = DEFAULT_MODELS_DIR,
    ) -> "Scorecard":
        """Load a scorecard via the registry, verifying artifact integrity.

        Raises:
            KeyError: unknown population:version in the registry.
            ModelIntegrityError: artifact sha256 mismatch.
            FileNotFoundError: registry or artifact file missing.
        """
        models_dir = Path(models_dir)
        registry_path = models_dir / "registry.json"
        registry: dict[str, dict] = json.loads(registry_path.read_text())

        key = f"{population}:{version}"
        if key not in registry:
            raise KeyError(
                f"Unknown model {key!r}; registry has: {sorted(registry)}"
            )
        entry = registry[key]

        artifact = models_dir / entry["path"]
        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            raise ModelIntegrityError(
                f"sha256 mismatch for {key}: registry={entry['sha256']} "
                f"actual={actual}; refusing to load {artifact}"
            )

        pipeline = joblib.load(artifact)
        return cls(population, version, pipeline, entry["sha256"], entry["features"])

    def score(self, fv: FeatureVector) -> ScoreResult:
        """Score a feature vector; contributions are exact for this model.

        contribution_i = coefficient_i * standardized_value_i (signed;
        positive pushes toward default). Ranked by absolute value desc.
        """
        if fv.population != self.population:
            raise ValueError(
                f"FeatureVector population {fv.population!r} does not match "
                f"scorecard population {self.population!r}"
            )
        inputs = fv.model_inputs()
        x = pd.DataFrame([[inputs[name] for name in self.features]], columns=self.features)

        scaler = self.pipeline.named_steps["scaler"]
        logreg = self.pipeline.named_steps["logreg"]
        z = scaler.transform(x)[0]
        coefs = logreg.coef_[0]

        contributions = sorted(
            (
                Contribution(
                    feature=name,
                    value=inputs[name],
                    contribution=float(coef * z_val),
                )
                for name, coef, z_val in zip(self.features, coefs, z)
            ),
            key=lambda c: abs(c.contribution),
            reverse=True,
        )
        probability = float(self.pipeline.predict_proba(x)[0, 1])
        return ScoreResult(
            population=self.population,
            model_version=self.model_version,
            model_sha256=self.sha256,
            probability_of_default=probability,
            contributions=contributions,
        )

    @property
    def intercept(self) -> float:
        """Model intercept on the logit scale (for contribution audits)."""
        return float(self.pipeline.named_steps["logreg"].intercept_[0])
