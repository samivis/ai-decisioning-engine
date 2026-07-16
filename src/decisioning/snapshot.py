"""Decision snapshot store: persistence, replay, and verification.

The reproducibility guarantee lives here.

    decide() ---> DecisionRecord ---> [snapshot committed] ---> rendered to user
                                          |
              dispute, months later       v
    replay(decision_id)  <--- read mode: stored output, never recomputed
    verify(decision_id)  <--- recompute with pinned model + config, assert match

Rules encoded below:
  * A decision is never returned to a caller unless its snapshot committed
    first (engine.py enforces call order; save() is transactional).
  * Read-mode replay never recomputes. Unknown ids raise DecisionNotFound.
  * Verify mode asserts: decision, ranked code ids, rule trace fired-set
    match exactly; probability within EPSILON. numpy/scikit-learn are
    pinned in requirements.txt so float drift cannot flake the demo.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from sqlalchemy import Column, DateTime, String, Text, create_engine, Boolean
from sqlalchemy.orm import Session, declarative_base

from decisioning.schemas import DecisionRecord

EPSILON = 1e-9
SEED_DB = Path(__file__).resolve().parents[2] / "data" / "seed.db"

Base = declarative_base()


class SnapshotRow(Base):
    __tablename__ = "decision_snapshots"

    decision_id = Column(String, primary_key=True)
    created_at = Column(DateTime, nullable=False)
    persona = Column(String, nullable=False)
    population = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    model_sha256 = Column(String, nullable=False)
    decision_config_version = Column(String, nullable=False)
    seeded = Column(Boolean, nullable=False, default=False)
    record_json = Column(Text, nullable=False)  # full DecisionRecord, canonical


class DecisionNotFound(Exception):
    pass


class VerificationFailure(Exception):
    pass


class SnapshotStore:
    """SQLite-backed snapshot store.

    The demo ships a read-only seed database (data/seed.db) containing a
    "decision from last week". At startup the app copies it to a working
    path per session, which sidesteps ephemeral cloud filesystems and
    concurrent-session contention on a single SQLite file.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        Base.metadata.create_all(self.engine)

    @classmethod
    def from_seed(cls, working_path: Path, seed_path: Path = SEED_DB) -> "SnapshotStore":
        """Copy the checked-in seed db to a working path (if not present)."""
        working_path = Path(working_path)
        if not working_path.exists() and Path(seed_path).exists():
            working_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(seed_path, working_path)
        return cls(working_path)

    def save(self, record: DecisionRecord) -> None:
        """Persist transactionally. Callers must save BEFORE rendering."""
        with Session(self.engine) as session, session.begin():
            session.merge(
                SnapshotRow(
                    decision_id=record.decision_id,
                    created_at=record.created_at.replace(tzinfo=None),
                    persona=record.persona,
                    population=record.population,
                    decision=record.decision,
                    model_version=record.score.model_version,
                    model_sha256=record.score.model_sha256,
                    decision_config_version=record.decision_config_version,
                    seeded=record.seeded,
                    record_json=record.model_dump_json(),
                )
            )

    def replay(self, decision_id: str) -> DecisionRecord:
        """Read mode: return the stored record exactly. Never recomputes."""
        with Session(self.engine) as session:
            row = session.get(SnapshotRow, decision_id)
        if row is None:
            raise DecisionNotFound(f"No snapshot for decision id {decision_id!r}")
        return DecisionRecord.model_validate(json.loads(row.record_json))

    def list_decisions(self) -> list[dict]:
        with Session(self.engine) as session:
            rows = session.query(SnapshotRow).order_by(SnapshotRow.created_at).all()
            return [
                {
                    "decision_id": r.decision_id,
                    "created_at": r.created_at,
                    "persona": r.persona,
                    "population": r.population,
                    "decision": r.decision,
                    "model_version": r.model_version,
                    "config_version": r.decision_config_version,
                    "seeded": r.seeded,
                }
                for r in rows
            ]


def verify_replay(stored: DecisionRecord, recomputed: DecisionRecord) -> None:
    """Verify mode: assert the recomputed decision matches the snapshot.

    Raises VerificationFailure naming the first mismatch. Matching
    semantics per the eng review: exact on decision, ranked code ids,
    and rule-trace fired set; probability within EPSILON.
    """
    if recomputed.decision != stored.decision:
        raise VerificationFailure(
            f"decision mismatch: stored {stored.decision}, recomputed {recomputed.decision}"
        )
    stored_codes = [c.code_id for c in stored.reason_codes]
    new_codes = [c.code_id for c in recomputed.reason_codes]
    if stored_codes != new_codes:
        raise VerificationFailure(f"reason codes mismatch: stored {stored_codes}, recomputed {new_codes}")
    stored_fired = [(e.rule_id, e.fired) for e in stored.rule_trace]
    new_fired = [(e.rule_id, e.fired) for e in recomputed.rule_trace]
    if stored_fired != new_fired:
        raise VerificationFailure(f"rule trace mismatch: stored {stored_fired}, recomputed {new_fired}")
    delta = abs(recomputed.score.probability_of_default - stored.score.probability_of_default)
    if delta > EPSILON:
        raise VerificationFailure(f"probability drift {delta} exceeds epsilon {EPSILON}")
