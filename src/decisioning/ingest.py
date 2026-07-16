"""Fixture ingestion: the only entry point for applicant transaction data.

Demo milestones load checked-in synthetic fixtures. Live Plaid ingestion
is a stretch milestone (M6) and is stubbed here so the seam already
exists in the call graph.

Fails loudly: a missing or malformed fixture raises FixtureError; this
module never returns a partial payload for downstream layers to trip on.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures"

# Keys a fixture must carry, and the type each must be.
_REQUIRED_KEYS: dict[str, type] = {
    "persona": str,
    "generated_by": str,
    "provenance": str,
    "accounts": list,
    "transactions": list,
}
_REQUIRED_TXN_KEYS = ("transaction_id", "account_id", "date", "amount", "name", "personal_finance_category")
_REQUIRED_ACCOUNT_KEYS = ("account_id", "type", "subtype", "balances")


class FixtureError(Exception):
    """A fixture file is missing, unreadable, or structurally invalid."""


def list_personas(fixtures_dir: Path | str = DEFAULT_FIXTURES_DIR) -> list[str]:
    """Names of every persona fixture present in fixtures_dir, sorted."""
    fixtures_dir = Path(fixtures_dir)
    if not fixtures_dir.is_dir():
        raise FixtureError(f"fixtures directory not found: {fixtures_dir}")
    return sorted(p.stem for p in fixtures_dir.glob("*.json"))


def load_fixture(persona_name: str, fixtures_dir: Path | str = DEFAULT_FIXTURES_DIR) -> dict:
    """Load and validate one persona fixture, returning the parsed dict.

    Raises FixtureError on a missing file, invalid JSON, missing keys, or
    wrongly typed sections. Never returns a partial fixture.
    """
    path = Path(fixtures_dir) / f"{persona_name}.json"
    if not path.is_file():
        raise FixtureError(f"fixture not found: {path} (run scripts/make_fixtures.py)")
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise FixtureError(f"fixture unreadable or not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise FixtureError(f"fixture root must be an object: {path}")
    for key, expected in _REQUIRED_KEYS.items():
        if key not in data:
            raise FixtureError(f"fixture missing required key {key!r}: {path}")
        if not isinstance(data[key], expected):
            raise FixtureError(f"fixture key {key!r} must be {expected.__name__}: {path}")
    for account in data["accounts"]:
        if not isinstance(account, dict) or any(k not in account for k in _REQUIRED_ACCOUNT_KEYS):
            raise FixtureError(f"malformed account entry in fixture: {path}")
    for txn in data["transactions"]:
        if not isinstance(txn, dict) or any(k not in txn for k in _REQUIRED_TXN_KEYS):
            raise FixtureError(f"malformed transaction entry in fixture: {path}")
    return data


def fetch_plaid_transactions(access_token: str, cursor: str | None = None) -> dict:
    """Live Plaid /transactions/sync ingestion. Not implemented.

    Stretch milestone M6. Fixtures are the only supported source until
    then; this stub exists so the ingest seam is already in place.
    """
    raise NotImplementedError(
        "Live Plaid ingestion is stretch milestone M6; use load_fixture() with checked-in synthetic fixtures."
    )
