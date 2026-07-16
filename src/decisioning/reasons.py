"""Adverse-action reason derivation.

Arbitration spec (encoded exactly, tested in tests/test_reasons.py):

- approve or review: no adverse action reasons; review is a routing
  outcome, not adverse action in this demo. Returns [].
- decline: candidates come from two sources:
    (a) each FIRED rule with effect decline maps to the code(s) whose
        maps_to.rules include that rule id and whose populations include
        the applicant's population (source "rule");
    (b) each model contribution with contribution > 0 (pushes toward
        default) maps to the code(s) whose maps_to.features include that
        feature, population-matched (source "contribution").
- Ranking: ALL rule-sourced codes outrank ALL contribution-sourced codes.
  Within rule-sourced: contract priority ascending. Within
  contribution-sourced: |contribution| descending, ties broken by
  priority ascending. Dedupe by code_id keeping the best rank. Cap at 4,
  assign rank 1..n.
- A decline with zero candidates raises UnmappedDeclineError: an
  unexplainable decline is a launch blocker, never a silent empty list.
"""

from __future__ import annotations

from decisioning.contract import Code, ReasonContract
from decisioning.schemas import (
    FeatureVector,
    Outcome,
    ReasonCode,
    RuleTraceEntry,
    ScoreResult,
)


class UnmappedDeclineError(Exception):
    """Raised when a decline produces no mappable reason codes."""


def _codes_for_population(contract: ReasonContract, population: str) -> list[Code]:
    return [code for code in contract.codes if population in code.populations]


def derive_reasons(
    fv: FeatureVector,
    score: ScoreResult,
    rule_trace: list[RuleTraceEntry],
    decision: Outcome,
    contract: ReasonContract,
) -> list[ReasonCode]:
    if decision in ("approve", "review"):
        return []

    codes = _codes_for_population(contract, fv.population)

    # Sort key: (source_tier, primary, priority). Rule-sourced codes are
    # tier 0 and always outrank contribution-sourced (tier 1).
    candidates: list[tuple[tuple[int, float, int], Code, str]] = []

    fired_decline_rules = [
        entry.rule_id for entry in rule_trace if entry.fired and entry.effect == "decline"
    ]
    for rule_id in fired_decline_rules:
        for code in codes:
            if rule_id in code.maps_to.rules:
                candidates.append(((0, 0.0, code.priority), code, "rule"))

    for contribution in score.contributions:
        if contribution.contribution <= 0:
            continue
        for code in codes:
            if contribution.feature in code.maps_to.features:
                candidates.append(
                    ((1, -abs(contribution.contribution), code.priority), code, "contribution")
                )

    candidates.sort(key=lambda item: item[0])

    seen: set[str] = set()
    reasons: list[ReasonCode] = []
    for _key, code, source in candidates:
        if code.id in seen:
            continue
        seen.add(code.id)
        reasons.append(
            ReasonCode(
                code_id=code.id,
                consumer_text=code.consumer_text,
                source=source,
                rank=len(reasons) + 1,
            )
        )
        if len(reasons) == 4:
            break

    if not reasons:
        raise UnmappedDeclineError(
            f"decline for population '{fv.population}' produced no mappable reason codes "
            f"(fired decline rules: {fired_decline_rules or 'none'})"
        )
    return reasons
