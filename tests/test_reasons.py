"""Tests for adverse-action reason derivation.

FeatureVectors and ScoreResults are constructed directly; model.py and
features.py belong to other lanes and are intentionally not imported.
"""

from __future__ import annotations

import pytest

from decisioning.contract import load_contract
from decisioning.reasons import UnmappedDeclineError, derive_reasons
from decisioning.schemas import Contribution, FeatureVector, RuleTraceEntry, ScoreResult


def make_fv(population="full_file", **overrides) -> FeatureVector:
    defaults = dict(
        population=population,
        annual_income_estimate=52000.0,
        dti_proxy=0.45,
        delinquency_proxy=2.0,
        employment_length_years=1.5,
        open_accounts=4,
        nsf_count_90d=0,
        months_of_history=18,
        balance_volatility=0.3,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


def make_score(contributions, population="full_file") -> ScoreResult:
    return ScoreResult(
        population=population,
        model_version="test-model",
        model_sha256="0" * 64,
        probability_of_default=0.5,
        contributions=[Contribution(**c) for c in contributions],
    )


def entry(rule_id, fired, effect=None) -> RuleTraceEntry:
    return RuleTraceEntry(rule_id=rule_id, fired=fired, effect=effect if fired else None)


V1 = load_contract(1)
V2 = load_contract(2)


class TestNonDecline:
    def test_approve_returns_empty(self):
        fv = make_fv()
        score = make_score([{"feature": "dti_proxy", "value": 0.45, "contribution": 0.2}])
        assert derive_reasons(fv, score, [], "approve", V1) == []

    def test_review_returns_empty(self):
        fv = make_fv()
        score = make_score([{"feature": "dti_proxy", "value": 0.45, "contribution": 0.2}])
        trace = [entry("income_unverifiable", True, "review")]
        assert derive_reasons(fv, score, trace, "review", V1) == []


class TestArbitration:
    def test_rule_sourced_outranks_contribution_sourced(self):
        fv = make_fv()
        # dti has a huge contribution but the fired decline rule still wins.
        score = make_score([{"feature": "dti_proxy", "value": 0.9, "contribution": 5.0}])
        trace = [entry("excessive_nsf", True, "decline")]
        reasons = derive_reasons(fv, score, trace, "decline", V1)
        assert reasons[0].code_id == "EXCESSIVE_NSF_ACTIVITY"
        assert reasons[0].source == "rule"
        assert reasons[0].rank == 1
        assert reasons[1].code_id == "EXCESSIVE_OBLIGATIONS"
        assert reasons[1].source == "contribution"

    def test_contribution_ordering_by_magnitude(self):
        fv = make_fv()
        score = make_score(
            [
                {"feature": "dti_proxy", "value": 0.9, "contribution": 0.3},
                {"feature": "annual_income_estimate", "value": 12000, "contribution": 0.8},
            ]
        )
        reasons = derive_reasons(fv, score, [], "decline", V1)
        assert [r.code_id for r in reasons] == ["INCOME_INSUFFICIENT", "EXCESSIVE_OBLIGATIONS"]

    def test_contribution_tie_broken_by_priority(self):
        fv = make_fv()
        # Equal magnitudes: EXCESSIVE_OBLIGATIONS (priority 20) beats
        # EMPLOYMENT_LENGTH (priority 40).
        score = make_score(
            [
                {"feature": "employment_length_years", "value": 0.5, "contribution": 0.4},
                {"feature": "dti_proxy", "value": 0.9, "contribution": 0.4},
            ]
        )
        reasons = derive_reasons(fv, score, [], "decline", V1)
        assert [r.code_id for r in reasons] == ["EXCESSIVE_OBLIGATIONS", "EMPLOYMENT_LENGTH"]

    def test_cap_at_four_with_ranks(self):
        fv = make_fv()
        score = make_score(
            [
                {"feature": "dti_proxy", "value": 0.9, "contribution": 0.9},
                {"feature": "annual_income_estimate", "value": 1, "contribution": 0.8},
                {"feature": "delinquency_proxy", "value": 5, "contribution": 0.7},
                {"feature": "employment_length_years", "value": 0.1, "contribution": 0.6},
            ]
        )
        trace = [entry("excessive_nsf", True, "decline")]
        reasons = derive_reasons(fv, score, trace, "decline", V1)
        assert len(reasons) == 4
        assert [r.rank for r in reasons] == [1, 2, 3, 4]
        assert reasons[0].code_id == "EXCESSIVE_NSF_ACTIVITY"

    def test_negative_contributions_never_produce_codes(self):
        fv = make_fv()
        score = make_score(
            [
                {"feature": "dti_proxy", "value": 0.9, "contribution": 0.5},
                {"feature": "delinquency_proxy", "value": 0, "contribution": -0.9},
            ]
        )
        reasons = derive_reasons(fv, score, [], "decline", V1)
        assert all(r.code_id != "DELINQUENT_OBLIGATIONS" for r in reasons)

    def test_dedupe_keeps_best_rank(self):
        fv = make_fv()
        score = make_score(
            [
                {"feature": "dti_proxy", "value": 0.9, "contribution": 0.5},
                {"feature": "dti_proxy", "value": 0.9, "contribution": 0.4},
            ]
        )
        reasons = derive_reasons(fv, score, [], "decline", V1)
        assert [r.code_id for r in reasons] == ["EXCESSIVE_OBLIGATIONS"]
        assert reasons[0].rank == 1


class TestPopulationFiltering:
    def test_thin_file_never_cites_full_file_only_codes(self):
        fv = make_fv(population="thin_file")
        # Contributions citing full_file-only features should be filtered.
        score = make_score(
            [
                {"feature": "delinquency_proxy", "value": 5, "contribution": 0.9},
                {"feature": "open_accounts", "value": 1, "contribution": 0.8},
                {"feature": "dti_proxy", "value": 0.9, "contribution": 0.3},
            ],
            population="thin_file",
        )
        reasons = derive_reasons(fv, score, [], "decline", V1)
        cited = {r.code_id for r in reasons}
        assert "DELINQUENT_OBLIGATIONS" not in cited
        assert "LIMITED_CREDIT_STRUCTURE" not in cited
        assert "EXCESSIVE_OBLIGATIONS" in cited


class TestUnmappedDecline:
    def test_raises_when_nothing_maps(self):
        fv = make_fv()
        score = make_score(
            [{"feature": "delinquency_proxy", "value": 0, "contribution": -0.2}]
        )
        with pytest.raises(UnmappedDeclineError):
            derive_reasons(fv, score, [], "decline", V1)

    def test_raises_for_unmapped_decline_rule_in_v1(self):
        # high_volatility has no v1 mapping; a thin_file decline driven only
        # by it must fail loudly under v1.
        fv = make_fv(population="thin_file", balance_volatility=0.9)
        score = make_score([], population="thin_file")
        trace = [entry("high_volatility", True, "decline")]
        with pytest.raises(UnmappedDeclineError):
            derive_reasons(fv, score, trace, "decline", V1)
        # ...and succeed under v2 via VARIABLE_INCOME_PATTERN.
        reasons = derive_reasons(fv, score, trace, "decline", V2)
        assert reasons[0].code_id == "VARIABLE_INCOME_PATTERN"


class TestContractVersionText:
    def test_v1_vs_v2_excessive_obligations_text(self):
        fv = make_fv()
        score = make_score([{"feature": "dti_proxy", "value": 0.9, "contribution": 0.5}])
        r1 = derive_reasons(fv, score, [], "decline", V1)
        r2 = derive_reasons(fv, score, [], "decline", V2)
        assert r1[0].code_id == r2[0].code_id == "EXCESSIVE_OBLIGATIONS"
        assert r1[0].consumer_text == "Excessive obligations in relation to income"
        assert r2[0].consumer_text == "Monthly obligations are too high relative to income"
        assert r1[0].consumer_text != r2[0].consumer_text
