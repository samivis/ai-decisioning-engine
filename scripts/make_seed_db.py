"""Build the checked-in seed database (data/seed.db).

The seed contains one deterministic "decision from last week" made under
model v1 and contract v1, so the dispute-replay demo works on a cold
start with zero setup: the world has since moved to v2, and the seeded
decision still replays with its original v1 reasons.

Run after any change to fixtures, policy, contract v1, or the v1 models:
    python scripts/make_seed_db.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from decisioning.engine import decide
from decisioning.snapshot import SEED_DB, SnapshotStore

SEED_DECISION_ID = "D-SEED-LASTWEEK"


def main() -> int:
    SEED_DB.unlink(missing_ok=True)
    store = SnapshotStore(SEED_DB)
    record = decide(
        "distressed_full_file",
        store,
        model_version="v1",
        contract_version=1,
        decision_id=SEED_DECISION_ID,
        seeded=True,
    )
    # Backdate so the demo reads honestly as "a decision from last week".
    stored = store.replay(SEED_DECISION_ID)
    stored = stored.model_copy(update={"created_at": datetime.now(timezone.utc) - timedelta(days=7)})
    store.save(stored)
    print(f"seeded {SEED_DECISION_ID}: {record.decision} with codes "
          f"{[c.code_id for c in record.reason_codes]} -> {SEED_DB}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
