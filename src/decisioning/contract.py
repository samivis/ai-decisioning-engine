"""Governed configuration contracts: the reason-code vocabulary and policy.

Both yaml files are load-validated with pydantic. A bad contract must fail
loudly at load time (ContractValidationError naming the offending field);
that is the governance claim. decision_config_version() hashes the exact
bytes of both files so any edit changes the version string.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from decisioning.schemas import Outcome, Population

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


class ContractValidationError(Exception):
    """Raised when a governed config file fails validation."""


class ChangelogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    date: object
    change: str
    approved_by: str

    @field_validator("approved_by")
    @classmethod
    def approved_by_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("approved_by must be non-empty")
        return v


class MapsTo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    features: list[str] = []
    rules: list[str] = []


class Code(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    populations: list[Population]
    priority: int
    consumer_text: str
    maps_to: MapsTo


class ReasonContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    changelog: list[ChangelogEntry]
    populations: list[Population]
    codes: list[Code]

    @model_validator(mode="after")
    def changelog_covers_version(self) -> "ReasonContract":
        if not self.changelog:
            raise ValueError("changelog must not be empty")
        max_version = max(entry.version for entry in self.changelog)
        if max_version != self.version:
            raise ValueError(
                f"changelog: max changelog version {max_version} != contract version {self.version}"
            )
        return self


class PopulationCutoffs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve_below: float
    review_below: float

    @model_validator(mode="after")
    def cutoffs_ordered(self) -> "PopulationCutoffs":
        if not self.approve_below < self.review_below:
            raise ValueError(
                f"approve_below ({self.approve_below}) must be < review_below ({self.review_below})"
            )
        return self


class Routing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thin_file_max_open_accounts: int


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    when: str
    effect: Outcome


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    populations: dict[Population, PopulationCutoffs]
    routing: Routing
    rules: list[PolicyRule]


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise ContractValidationError(f"config file not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ContractValidationError(f"{path.name}: top level must be a mapping")
    return data


def _format_validation_error(name: str, exc: ValidationError) -> str:
    lines = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"]) or "<root>"
        lines.append(f"{name}: field '{loc}': {err['msg']}")
    return "; ".join(lines)


def load_contract(version: int, config_dir: Path = DEFAULT_CONFIG_DIR) -> ReasonContract:
    path = Path(config_dir) / f"reason_codes_v{version}.yaml"
    data = _load_yaml(path)
    try:
        contract = ReasonContract(**data)
    except ValidationError as exc:
        raise ContractValidationError(_format_validation_error(path.name, exc)) from exc
    if contract.version != version:
        raise ContractValidationError(
            f"{path.name}: field 'version': declares {contract.version}, expected {version}"
        )
    return contract


def load_policy(config_dir: Path = DEFAULT_CONFIG_DIR) -> Policy:
    path = Path(config_dir) / "policy.yaml"
    data = _load_yaml(path)
    try:
        return Policy(**data)
    except ValidationError as exc:
        raise ContractValidationError(_format_validation_error(path.name, exc)) from exc


def decision_config_version(
    contract_version: int, config_dir: Path = DEFAULT_CONFIG_DIR
) -> str:
    """Hash manifest over the exact bytes of policy.yaml plus the active
    reason_codes yaml. Any byte change to either file changes the version."""
    config_dir = Path(config_dir)
    hasher = hashlib.sha256()
    hasher.update((config_dir / "policy.yaml").read_bytes())
    hasher.update((config_dir / f"reason_codes_v{contract_version}.yaml").read_bytes())
    return f"cfgv{contract_version}-{hasher.hexdigest()[:16]}"
