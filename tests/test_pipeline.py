"""Integration tier: golden persona outcomes, end-to-end pipeline,
snapshot semantics, and the dispute-replay guarantee (the 2am test)."""

from __future__ import annotations

import pytest

from decisioning.engine import decide, verify
from decisioning.notice import (
    NoticeValidationError,
    render_template_notice,
    validate_governed_notice,
)
from decisioning.schemas import ReasonCode
from decisioning.snapshot import DecisionNotFound, SnapshotStore

# Golden outcomes: the calibrated demo narrative. If these change, the
# demo story changed; that must be a deliberate decision, not drift.
GOLDENS = {
    "healthy_full_file": ("full_file", "approve", []),
    "distressed_full_file": (
        "full_file",
        "decline",
        [
            "EXCESSIVE_NSF_ACTIVITY",
            "DELINQUENT_OBLIGATIONS",
            "EXCESSIVE_OBLIGATIONS",
            "INCOME_INSUFFICIENT",
        ],
    ),
    "thin_file": (
        "thin_file",
        "decline",
        [
            "INSUFFICIENT_CASHFLOW_HISTORY",
            "EXCESSIVE_OBLIGATIONS",
            "INCOME_INSUFFICIENT",
            "EMPLOYMENT_LENGTH",
        ],
    ),
}


@pytest.fixture()
def store(tmp_path):
    return SnapshotStore(tmp_path / "test.db")


@pytest.mark.parametrize("persona", list(GOLDENS))
def test_golden_outcomes(store, persona):
    population, decision, codes = GOLDENS[persona]
    record = decide(persona, store)
    assert record.population == population
    assert record.decision == decision
    assert [c.code_id for c in record.reason_codes] == codes
    assert [c.rank for c in record.reason_codes] == list(range(1, len(codes) + 1))


def test_decline_notice_is_present_and_validates(store):
    record = decide("distressed_full_file", store)
    assert record.notice_mode in ("template_fallback", "cached", "governed_llm")
    validate_governed_notice(record.notice_text, record.reason_codes)


def test_approve_has_no_notice(store):
    record = decide("healthy_full_file", store)
    assert record.notice_text == ""
    assert record.notice_mode == "none"
    assert record.reason_codes == []


def test_snapshot_committed_before_render(store):
    record = decide("thin_file", store)
    # The record we hold must already be replayable: save happened first.
    stored = store.replay(record.decision_id)
    assert stored.model_dump() == record.model_dump()


def test_replay_unknown_id(store):
    with pytest.raises(DecisionNotFound):
        store.replay("D-DOES-NOT-EXIST")


def test_the_2am_test_replay_survives_model_and_contract_bump(store):
    """Decide under model v1 + contract v1. Then 'retrain' (v2) and bump
    the contract (v2). The original decision must replay byte-identically
    and verify against its pinned versions, while new decisions differ."""
    original = decide("distressed_full_file", store, model_version="v1", contract_version=1)
    original_codes = [(c.code_id, c.consumer_text) for c in original.reason_codes]

    # The world moves on: new decisions use v2 model and v2 contract.
    new = decide("distressed_full_file", store, model_version="v2", contract_version=2)
    assert new.score.model_version.endswith("v2")
    assert new.contract_version == 2
    # v2 revised the EXCESSIVE_OBLIGATIONS consumer text; new notices use it.
    new_texts = {c.code_id: c.consumer_text for c in new.reason_codes}
    if "EXCESSIVE_OBLIGATIONS" in new_texts:
        assert new_texts["EXCESSIVE_OBLIGATIONS"] == "Monthly obligations are too high relative to income"

    # Read-mode replay: stored output exactly, v1 text preserved.
    replayed = store.replay(original.decision_id)
    assert [(c.code_id, c.consumer_text) for c in replayed.reason_codes] == original_codes
    assert replayed.score.model_version.endswith("v1")
    assert replayed.notice_text == original.notice_text

    # Verify mode: re-derivation with pinned versions still matches.
    verify(original.decision_id, store)


def test_notice_validator_rejects_paraphrase():
    codes = [
        ReasonCode(code_id="INCOME_INSUFFICIENT", consumer_text="Income insufficient for amount of credit requested", source="contribution", rank=1),
    ]
    good = render_template_notice(codes)
    validate_governed_notice(good, codes)
    paraphrased = good.replace(
        "Income insufficient for amount of credit requested",
        "Your earnings were too low for this loan",
    )
    with pytest.raises(NoticeValidationError):
        validate_governed_notice(paraphrased, codes)


def test_notice_validator_rejects_reordering():
    codes = [
        ReasonCode(code_id="A", consumer_text="First approved reason text", source="rule", rank=1),
        ReasonCode(code_id="B", consumer_text="Second approved reason text", source="contribution", rank=2),
    ]
    out_of_order = render_template_notice(list(reversed(codes)))
    with pytest.raises(NoticeValidationError):
        validate_governed_notice(out_of_order, codes)
