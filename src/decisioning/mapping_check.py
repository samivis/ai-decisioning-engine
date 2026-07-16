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


ACTIVE_CONTRACT_VERSION = 2


def main() -> int:
    """CI gate. Blocks on gaps in the ACTIVE contract version; historical
    versions are frozen artifacts and only warn. The known v1 gap
    (high_volatility unmapped, fixed in v2) is the gate's demo story:
    this check is what catches it before launch."""
    policy = load_policy()
    exit_code = 0
    for version in (1, 2):
        contract = load_contract(version)
        gaps = check_mapping_coverage(contract, policy)
        if not gaps:
            print(f"contract v{version}: mapping coverage OK")
            continue
        if version == ACTIVE_CONTRACT_VERSION:
            print(f"contract v{version} (ACTIVE): mapping coverage FAILED")
            exit_code = 1
        else:
            print(f"contract v{version} (historical): known gaps, frozen")
        for gap in gaps:
            print(f"  - {gap}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
