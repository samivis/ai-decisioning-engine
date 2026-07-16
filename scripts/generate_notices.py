"""Pre-generate cached LLM notice outputs for the demo personas.

Why this exists: the public demo cannot ship an API key, so both the
governed and naive LLM outputs are generated once, here, and cached in
data/cached_notices/ keyed by a hash of (persona, contract version, mode,
approved codes). The cache can therefore never silently diverge from the
contract it demonstrates: if the contract or a persona's reasons change,
the key changes, --check fails CI, and this script must be re-run.

Usage:
    python scripts/generate_notices.py            # needs OPENAI_API_KEY
    python scripts/generate_notices.py --check    # CI staleness gate, no key needed
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from decisioning import notice as notice_mod
from decisioning.engine import decide
from decisioning.ingest import list_personas
from decisioning.notice import (
    CACHE_DIR,
    _cache_key,
    _governed_llm_notice,
    _llm_available,
    naive_llm_notice,
    validate_governed_notice,
)
from decisioning.snapshot import SnapshotStore


def expected_paths() -> dict[Path, object]:
    """Compute the cache paths the current configs and personas demand."""
    out: dict[Path, object] = {}
    with tempfile.TemporaryDirectory() as tmp:
        store = SnapshotStore(Path(tmp) / "scratch.db")
        for persona in list_personas():
            for contract_version in (1, 2):
                record = decide(persona, store, contract_version=contract_version)
                if record.decision != "decline" or not record.reason_codes:
                    continue
                for mode in ("governed", "naive"):
                    key = _cache_key(persona, contract_version, mode, record.reason_codes)
                    path = CACHE_DIR / f"{persona}-v{contract_version}-{mode}-{key}.txt"
                    out[path] = record
    return out


def check() -> int:
    """CI gate: every existing cache file must correspond to a currently
    valid key. Missing cache is allowed (demo falls back to templates);
    STALE cache, a file whose key no longer matches any expected path,
    fails the build, because a stale cached notice silently diverging
    from the contract is the exact failure this project exists to prevent."""
    expected = {p.name for p in expected_paths()}
    existing = {p.name for p in CACHE_DIR.glob("*.txt")}
    stale = existing - expected
    if stale:
        print("STALE cached notices (contract or personas changed; re-run scripts/generate_notices.py):")
        for name in sorted(stale):
            print(f"  {name}")
        return 1
    missing = expected - existing
    if missing:
        print(f"note: {len(missing)} cache entries not generated (demo uses template fallback); run with an API key to populate")
    print("cached notices: fresh")
    return 0


def generate() -> int:
    if not _llm_available():
        print("OPENAI_API_KEY not set; cannot generate cached LLM outputs.")
        return 1
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for path, record in expected_paths().items():
        mode = "governed" if "-governed-" in path.name else "naive"
        if mode == "governed":
            text = _governed_llm_notice(record.reason_codes)
            validate_governed_notice(text, record.reason_codes)
        else:
            # Bypass cache lookup to force a real generation
            saved, notice_mod.CACHE_DIR = notice_mod.CACHE_DIR, Path(tempfile.mkdtemp())
            try:
                text = naive_llm_notice(record)
            finally:
                notice_mod.CACHE_DIR = saved
        path.write_text(text)
        print(f"wrote {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(check() if "--check" in sys.argv else generate())
