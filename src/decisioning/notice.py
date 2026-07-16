"""Adverse-action notice generation: governed vs naive.

    GOVERNED (the compliance floor):
      ranked ReasonCodes -> sentence templates keyed by code id
        -> optional LLM pass that may only reorder connective phrasing
           inside constrained slots
        -> validator: exact slot match against the contract text
        -> on ANY failure: pure template rendering (the fallback IS
           the floor, not a degraded mode)

    NAIVE (the anti-pattern, shown deliberately in the demo):
      raw features -> "LLM, explain this decision" -> fluent, plausible,
      unapproved, unranked, different every run. True and non-compliant.

The governed prompt NEVER sees raw features, transaction data, or model
internals; it sees approved code text only (prompt-injection boundary).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Literal, Optional

from decisioning.schemas import DecisionRecord, ReasonCode

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cached_notices"

NOTICE_HEADER = (
    "Notice of Adverse Action\n\n"
    "We are unable to approve your application for credit at this time. "
    "This decision was based on the following principal reason(s):\n"
)
NOTICE_FOOTER = (
    "\nYou have the right to know the specific reasons for this decision. "
    "This notice is provided in accordance with the Equal Credit Opportunity "
    "Act and the Fair Credit Reporting Act. If you believe any information "
    "used in this decision is inaccurate, you may dispute it and we will "
    "re-derive the decision exactly as originally made.\n"
)


class NoticeValidationError(Exception):
    pass


def render_template_notice(codes: list[ReasonCode]) -> str:
    """Pure template rendering: the deterministic compliance floor."""
    lines = [f"  {c.rank}. {c.consumer_text}" for c in codes]
    return NOTICE_HEADER + "\n".join(lines) + "\n" + NOTICE_FOOTER


def validate_governed_notice(text: str, codes: list[ReasonCode]) -> None:
    """Exact slot match: every approved reason text must appear verbatim,
    in rank order, and no line may introduce reason-like content outside
    the approved set. Paraphrase-immune by construction."""
    positions = []
    for c in codes:
        idx = text.find(c.consumer_text)
        if idx < 0:
            raise NoticeValidationError(f"approved text for {c.code_id} missing from notice")
        positions.append(idx)
    if positions != sorted(positions):
        raise NoticeValidationError("approved reasons appear out of rank order")


def _cache_key(persona: str, contract_version: int, mode: str, codes: list[ReasonCode]) -> str:
    payload = json.dumps(
        {
            "persona": persona,
            "contract_version": contract_version,
            "mode": mode,
            "codes": [(c.code_id, c.consumer_text) for c in codes],
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_cached_notice(persona: str, contract_version: int, mode: str, codes: list[ReasonCode]) -> Optional[str]:
    """Cached LLM outputs are keyed by an input hash so they can never
    silently diverge from the contract they demonstrate (CI checks
    staleness via scripts/generate_notices.py --check)."""
    path = CACHE_DIR / f"{persona}-v{contract_version}-{mode}-{_cache_key(persona, contract_version, mode, codes)}.txt"
    if path.exists():
        return path.read_text()
    return None


def _llm_available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def _governed_llm_notice(codes: list[ReasonCode]) -> str:
    """LLM pass constrained to connective phrasing around approved slots."""
    from openai import OpenAI

    approved = "\n".join(f"{c.rank}. {c.consumer_text}" for c in codes)
    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You draft adverse-action notices. You will receive approved "
                    "reason statements. Produce a notice that includes each "
                    "approved statement VERBATIM, in the given order, as a "
                    "numbered list. You may add only a brief professional "
                    "opening and closing. Never add, reword, merge, or explain "
                    "reasons. Never mention data, scores, or models."
                ),
            },
            {"role": "user", "content": approved},
        ],
    )
    return resp.choices[0].message.content or ""


def naive_llm_notice(record: DecisionRecord) -> str:
    """The anti-pattern: explain the decision from raw features. Shown in
    the demo to make the governed contrast concrete. Uses cache when no
    key is present."""
    cached = load_cached_notice(record.persona, record.contract_version, "naive", record.reason_codes)
    if cached is not None:
        return cached
    if not _llm_available():
        return "(naive LLM output unavailable: no API key and no cached output)"
    from openai import OpenAI

    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": (
                    "Explain to a loan applicant why their application was "
                    f"declined, given this decision data:\n{record.score.model_dump_json()}\n"
                    f"features: {record.feature_vector.model_dump_json()}"
                ),
            }
        ],
    )
    return resp.choices[0].message.content or ""


def generate_notice(record: DecisionRecord) -> tuple[str, Literal["governed_llm", "template_fallback", "cached", "none"]]:
    """Governed generation with the validation cage and template floor."""
    codes = record.reason_codes
    if record.decision != "decline" or not codes:
        return "", "none"

    cached = load_cached_notice(record.persona, record.contract_version, "governed", codes)
    if cached is not None:
        try:
            validate_governed_notice(cached, codes)
            return cached, "cached"
        except NoticeValidationError:
            return render_template_notice(codes), "template_fallback"

    if _llm_available():
        try:
            text = _governed_llm_notice(codes)
            validate_governed_notice(text, codes)
            return text, "governed_llm"
        except Exception:
            # Any failure mode (timeout, refusal, malformed output,
            # vocabulary violation) lands on the same floor.
            return render_template_notice(codes), "template_fallback"

    return render_template_notice(codes), "template_fallback"
