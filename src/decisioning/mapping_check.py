"""Mapping coverage gate: every signal that can cause a decline must map
to at least one approved reason code for every population it applies to.

Run as `python -m decisioning.mapping_check` in CI: loads policy plus BOTH
contract versions and exits 1 printing gaps if any exist.
"""

from __future__ import annotations

import sys

from decisioning.contract import Policy, ReasonContract, load_contract, load_policy
from decisioning.schemas import MODEL_FEATURES, Population

_POPULATIONS: list[Population] = ["full_file", "thin_file"]


def _rule_populations(when: str) -> list[Population]:
    """Conservative parse of a rule's population gating from its when-string."""
    if "population == 'thin_file'" in when:
        return ["thin_file"]
    if "population == 'full_file'" in when:
        return ["full_file"]
    return list(_POPULATIONS)


def check_mapping_coverage(contract: ReasonContract, policy: Policy) -> list[str]:
    gaps: list[str] = []

    for population in _POPULATIONS:
        codes = [code for code in contract.codes if population in code.populations]
        mapped_features = {f for code in codes for f in code.maps_to.features}
        mapped_rules = {r for code in codes for r in code.maps_to.rules}

        for feature in MODEL_FEATURES[population]:
            if feature not in mapped_features:
                gaps.append(
                    f"population '{population}': model feature '{feature}' is not mapped "
                    f"by any reason code (contract v{contract.version})"
                )

        for rule in policy.rules:
            if rule.effect != "decline":
                continue
            if population not in _rule_populations(rule.when):
                continue
            if rule.id not in mapped_rules:
                gaps.append(
                    f"population '{population}': decline rule '{rule.id}' is not mapped "
                    f"by any reason code (contract v{contract.version})"
                )

    return gaps


def main() -> int:
    policy = load_policy()
    all_gaps: list[str] = []
    for version in (1, 2):
        contract = load_contract(version)
        all_gaps.extend(check_mapping_coverage(contract, policy))
    if all_gaps:
        print("mapping coverage FAILED:")
        for gap in all_gaps:
            print(f"  - {gap}")
        return 1
    print("mapping coverage OK: all model features and decline rules are mapped (v1, v2)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
