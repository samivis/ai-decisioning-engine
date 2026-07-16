"""Shared data contracts for the decisioning pipeline.

Every layer emits these shapes from day one so snapshots serialize an
existing contract instead of retrofitting one (eng review finding E3/OV3).

    ingest -> features -> FeatureVector -> model -> rules -> reasons
                                            \\________________________
                                                                     v
                                                             DecisionRecord
                                                             (snapshotted)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Bump when FeatureVector fields change. Snapshots store this so replay
# can detect schema drift instead of silently mis-matching (finding 1.1).
FEATURE_SCHEMA_VERSION = 1

Population = Literal["full_file", "thin_file"]
Outcome = Literal["approve", "decline", "review"]

# Features the scorecards consume. Cash-flow-derivable ONLY, by design:
# a reason code must never cite an input the applicant never supplied.
MODEL_FEATURES: dict[Population, list[str]] = {
    "full_file": [
        "annual_income_estimate",
        "dti_proxy",
        "delinquency_proxy",
        "employment_length_years",
        "open_accounts",
    ],
    "thin_file": [
        "annual_income_estimate",
        "dti_proxy",
        "employment_length_years",
    ],
}


class FeatureVector(BaseModel):
    """Model-adjacent features derived from applicant transactions."""

    schema_version: int = FEATURE_SCHEMA_VERSION
    population: Population

    # Scorecard inputs
    annual_income_estimate: float = Field(ge=0)
    dti_proxy: float = Field(ge=0)  # monthly expenses / monthly income
    delinquency_proxy: float = Field(ge=0)  # late/collection payment events, 12m
    employment_length_years: float = Field(ge=0)
    open_accounts: int = Field(ge=0)

    # Rule-layer inputs (never scored, never cited as model contributions)
    nsf_count_90d: int = Field(ge=0)
    months_of_history: int = Field(ge=0)
    balance_volatility: float = Field(ge=0)

    def model_inputs(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in MODEL_FEATURES[self.population]}


class Contribution(BaseModel):
    feature: str
    value: float
    contribution: float  # signed; positive pushes toward default/decline


class ScoreResult(BaseModel):
    population: Population
    model_version: str
    model_sha256: str
    probability_of_default: float = Field(ge=0, le=1)
    contributions: list[Contribution]  # ranked by |contribution|, desc


class RuleTraceEntry(BaseModel):
    rule_id: str
    fired: bool
    effect: Optional[Outcome] = None  # only when fired
    detail: str = ""


class ReasonCode(BaseModel):
    code_id: str
    consumer_text: str
    source: Literal["rule", "contribution"]
    rank: int  # 1..4


class DecisionRecord(BaseModel):
    """The snapshot unit. Replay reads this; verify mode recomputes and
    asserts: decision, ranked code ids, and rule trace match exactly,
    probability within epsilon 1e-9."""

    decision_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    persona: str
    population: Population

    feature_vector: FeatureVector
    score: ScoreResult
    rule_trace: list[RuleTraceEntry]
    decision: Outcome
    reason_codes: list[ReasonCode]  # empty for approve; empty for review (no adverse action notice)

    decision_config_version: str  # hash manifest over (policy.yaml, reason_codes yaml)
    contract_version: int

    notice_text: str = ""
    notice_mode: Literal["governed_llm", "template_fallback", "cached", "none"] = "none"

    seeded: bool = False
