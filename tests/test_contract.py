"""Tests for the governed config contracts and the mapping coverage gate."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from decisioning.contract import (
    DEFAULT_CONFIG_DIR,
    ContractValidationError,
    ReasonContract,
    decision_config_version,
    load_contract,
    load_policy,
)
from decisioning.mapping_check import check_mapping_coverage


def _copy_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    for name in ("policy.yaml", "reason_codes_v1.yaml", "reason_codes_v2.yaml"):
        shutil.copy(DEFAULT_CONFIG_DIR / name, config_dir / name)
    return config_dir


def _rewrite(path: Path, mutate) -> None:
    data = yaml.safe_load(path.read_text())
    mutate(data)
    path.write_text(yaml.safe_dump(data))


class TestLoading:
    def test_v1_loads(self):
        contract = load_contract(1)
        assert contract.version == 1
        assert any(code.id == "EXCESSIVE_OBLIGATIONS" for code in contract.codes)

    def test_v2_loads(self):
        contract = load_contract(2)
        assert contract.version == 2
        assert any(code.id == "VARIABLE_INCOME_PATTERN" for code in contract.codes)

    def test_policy_loads(self):
        policy = load_policy()
        assert policy.populations["full_file"].approve_below == 0.15
        assert len(policy.rules) == 4


class TestTamperedConfig:
    def test_missing_approved_by(self, tmp_path):
        config_dir = _copy_config(tmp_path)

        def mutate(data):
            del data["changelog"][0]["approved_by"]

        _rewrite(config_dir / "reason_codes_v1.yaml", mutate)
        with pytest.raises(ContractValidationError, match="approved_by"):
            load_contract(1, config_dir=config_dir)

    def test_empty_approved_by(self, tmp_path):
        config_dir = _copy_config(tmp_path)

        def mutate(data):
            data["changelog"][0]["approved_by"] = "  "

        _rewrite(config_dir / "reason_codes_v1.yaml", mutate)
        with pytest.raises(ContractValidationError, match="approved_by"):
            load_contract(1, config_dir=config_dir)

    def test_approve_below_not_less_than_review_below(self, tmp_path):
        config_dir = _copy_config(tmp_path)

        def mutate(data):
            data["populations"]["full_file"]["approve_below"] = 0.30

        _rewrite(config_dir / "policy.yaml", mutate)
        with pytest.raises(ContractValidationError, match="approve_below"):
            load_policy(config_dir=config_dir)

    def test_unknown_field_rejected(self, tmp_path):
        config_dir = _copy_config(tmp_path)

        def mutate(data):
            data["codes"][0]["surprise_field"] = True

        _rewrite(config_dir / "reason_codes_v1.yaml", mutate)
        with pytest.raises(ContractValidationError, match="surprise_field"):
            load_contract(1, config_dir=config_dir)

    def test_bad_field_type(self, tmp_path):
        config_dir = _copy_config(tmp_path)

        def mutate(data):
            data["codes"][0]["priority"] = "not-a-number"

        _rewrite(config_dir / "reason_codes_v1.yaml", mutate)
        with pytest.raises(ContractValidationError, match="priority"):
            load_contract(1, config_dir=config_dir)

    def test_bad_population_name(self, tmp_path):
        config_dir = _copy_config(tmp_path)

        def mutate(data):
            data["codes"][0]["populations"] = ["mystery_file"]

        _rewrite(config_dir / "reason_codes_v1.yaml", mutate)
        with pytest.raises(ContractValidationError, match="populations"):
            load_contract(1, config_dir=config_dir)

    def test_changelog_version_mismatch(self, tmp_path):
        config_dir = _copy_config(tmp_path)

        def mutate(data):
            data["version"] = 3
            # changelog still tops out at a lower version

        _rewrite(config_dir / "reason_codes_v2.yaml", mutate)
        (config_dir / "reason_codes_v3.yaml").write_text(
            (config_dir / "reason_codes_v2.yaml").read_text()
        )
        with pytest.raises(ContractValidationError, match="changelog"):
            load_contract(3, config_dir=config_dir)


class TestDecisionConfigVersion:
    def test_stable_when_bytes_unchanged(self, tmp_path):
        config_dir = _copy_config(tmp_path)
        assert decision_config_version(1, config_dir=config_dir) == decision_config_version(
            1, config_dir=config_dir
        )
        assert decision_config_version(1, config_dir=config_dir) == decision_config_version(
            1, config_dir=DEFAULT_CONFIG_DIR
        )

    def test_format(self):
        v = decision_config_version(1)
        assert v.startswith("cfgv1-")
        assert len(v.split("-")[1]) == 16

    def test_changes_when_policy_bytes_change(self, tmp_path):
        config_dir = _copy_config(tmp_path)
        before = decision_config_version(1, config_dir=config_dir)
        path = config_dir / "policy.yaml"
        path.write_text(path.read_text() + "\n# tweak\n")
        assert decision_config_version(1, config_dir=config_dir) != before

    def test_changes_when_reason_codes_bytes_change(self, tmp_path):
        config_dir = _copy_config(tmp_path)
        before = decision_config_version(1, config_dir=config_dir)
        path = config_dir / "reason_codes_v1.yaml"
        path.write_text(path.read_text() + "\n# tweak\n")
        assert decision_config_version(1, config_dir=config_dir) != before

    def test_contract_version_selects_file(self):
        assert decision_config_version(1) != decision_config_version(2)


class TestMappingCoverage:
    def test_real_config_v1_has_only_the_known_high_volatility_gap(self):
        # v1 predates VARIABLE_INCOME_PATTERN (added in v2 per its changelog),
        # so the high_volatility decline rule is unmapped for thin_file. That
        # is the one gap the checker must surface, and nothing else.
        gaps = check_mapping_coverage(load_contract(1), load_policy())
        assert len(gaps) == 1
        assert "high_volatility" in gaps[0]
        assert "thin_file" in gaps[0]

    def test_real_config_passes_v2(self):
        assert check_mapping_coverage(load_contract(2), load_policy()) == []

    def test_detects_gap_when_code_removed(self):
        contract = load_contract(1)
        policy = load_policy()
        data = contract.model_dump()
        data["codes"] = [c for c in data["codes"] if c["id"] != "EXCESSIVE_OBLIGATIONS"]
        modified = ReasonContract(**data)
        gaps = check_mapping_coverage(modified, policy)
        assert gaps
        assert any("dti_proxy" in gap for gap in gaps)

    def test_detects_unmapped_decline_rule(self):
        contract = load_contract(1)
        policy = load_policy()
        data = contract.model_dump()
        data["codes"] = [c for c in data["codes"] if c["id"] != "EXCESSIVE_NSF_ACTIVITY"]
        modified = ReasonContract(**data)
        gaps = check_mapping_coverage(modified, policy)
        assert any("excessive_nsf" in gap for gap in gaps)
