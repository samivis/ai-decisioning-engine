"""Decision engine: orchestrates the full pipeline for one applicant.

    fixture -> features -> scorecard -> rules/policy -> reasons
            -> notice -> SNAPSHOT (committed first) -> rendered decision

The snapshot commit happens before the record is returned to any caller;
an unsnapshotted decision must never be shown (reproducibility guarantee).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from decisioning.contract import decision_config_version, load_contract, load_policy
from decisioning.features import extract_features
from decisioning.ingest import load_fixture
from decisioning.model import Scorecard
from decisioning.notice import generate_notice
from decisioning.reasons import derive_reasons
from decisioning.rules import apply_policy, evaluate_rules
from decisioning.schemas import DecisionRecord
from decisioning.snapshot import SnapshotStore, verify_replay

REPO_ROOT = Path(__file__).resolve().parents[2]


def decide(
    persona: str,
    store: SnapshotStore,
    model_version: str = "v1",
    contract_version: int = 1,
    decision_id: str | None = None,
    seeded: bool = False,
) -> DecisionRecord:
    """Run one applicant end to end and snapshot the result."""
    fixture = load_fixture(persona)
    fv = extract_features(fixture)

    scorecard = Scorecard.load(fv.population, model_version)
    score = scorecard.score(fv)

    policy = load_policy()
    trace = evaluate_rules(fv, policy)
    outcome = apply_policy(fv, score.probability_of_default, policy, trace)

    contract = load_contract(contract_version)
    codes = derive_reasons(fv, score, trace, outcome, contract)

    record = DecisionRecord(
        decision_id=decision_id or f"D-{uuid.uuid4().hex[:10]}",
        persona=persona,
        population=fv.population,
        feature_vector=fv,
        score=score,
        rule_trace=trace,
        decision=outcome,
        reason_codes=codes,
        decision_config_version=decision_config_version(contract_version),
        contract_version=contract_version,
        seeded=seeded,
    )
    text, mode = generate_notice(record)
    record.notice_text = text
    record.notice_mode = mode

    store.save(record)  # committed BEFORE the caller can render it
    return record


def verify(decision_id: str, store: SnapshotStore) -> DecisionRecord:
    """Verify mode: re-derive with the PINNED model + contract versions
    stored in the snapshot, and assert the derivation matches. Returns
    the recomputed record on success; raises VerificationFailure on any
    mismatch."""
    stored = store.replay(decision_id)
    model_version = stored.score.model_version.split(":")[-1]

    fixture = load_fixture(stored.persona)
    fv = extract_features(fixture)
    scorecard = Scorecard.load(fv.population, model_version)
    score = scorecard.score(fv)
    policy = load_policy()
    trace = evaluate_rules(fv, policy)
    outcome = apply_policy(fv, score.probability_of_default, policy, trace)
    contract = load_contract(stored.contract_version)
    codes = derive_reasons(fv, score, trace, outcome, contract)

    recomputed = stored.model_copy(
        update={
            "feature_vector": fv,
            "score": score,
            "rule_trace": trace,
            "decision": outcome,
            "reason_codes": codes,
        }
    )
    verify_replay(stored, recomputed)
    return recomputed
