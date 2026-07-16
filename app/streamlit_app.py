"""Demo UI: run a decision, read the governed reasons, dispute it later.

Layout: two white cards on a tinted canvas. Left card is the live
decision instrument (applicant, model, contract, result, notices).
Right card is the governance record (snapshot timeline, dispute replay,
verified re-derivation). Serif display headings carry the status.

Decisions run inside a form so inputs and the click submit atomically:
a rapid double-click cannot fire two decisions or read stale state.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "app"))

import streamlit as st

from decisioning.engine import decide, verify
from decisioning.ingest import list_personas
from decisioning.notice import naive_llm_notice
from decisioning.snapshot import DecisionNotFound, SnapshotStore, VerificationFailure
import importlib

import style as _style

importlib.reload(_style)  # style.py edits hot-reload with the page
CSS, display_row, humanize, reason_list, timeline = (
    _style.CSS, _style.display_row, _style.humanize, _style.reason_list, _style.timeline
)
contributions_table, rule_trace_table = _style.contributions_table, _style.rule_trace_table
prose_block = _style.prose_block

st.set_page_config(page_title="Explainable Credit Decisioning", page_icon="🏦", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource
def get_store() -> SnapshotStore:
    working = Path(tempfile.mkdtemp()) / "decisions.db"
    return SnapshotStore.from_seed(working)


store = get_store()

# Friendly faces for the synthetic personas; raw keys stay the engine's truth
PERSONAS = {
    "healthy_full_file": "Avery (steady payroll, clean accounts)",
    "distressed_full_file": "Jordan (overdrafts, late payments)",
    "thin_file": "Sam (gig income, 4 months of history)",
}


def persona_label(key: str) -> str:
    return PERSONAS.get(key, key)

# masthead
st.title("Credit Decisioning Engine")
st.caption(
    "Governed adverse-action reason codes with dispute-grade replay. "
    "Synthetic, calibrated demo personas, stated on purpose."
)
st.write("")

left, right = st.columns([7, 5], gap="large")

# ----------------------------------------------------------------- left card
with left:
    st.markdown('<div class="micro">Decision instrument</div>', unsafe_allow_html=True)

    with st.form("decide_form", border=False):
        persona = st.selectbox(
            "Applicant",
            list_personas(),
            format_func=persona_label,
            help="Three synthetic applicants, each built to exercise different "
                 "decline reasons. No real people, no real bank data.",
        )
        col_a, col_b, col_c = st.columns([1, 1, 1.2])
        model_version = col_a.radio(
            "Scorecard version", ["v1", "v2"], horizontal=True, index=1,
            help="The risk model. v2 is a retrain of v1; the point of the demo "
                 "is that old decisions stay explainable after upgrades.",
        )
        contract_version = col_b.radio(
            "Reason vocabulary", [1, 2], horizontal=True, index=1,
            help="The approved list of decline-reason phrasings, versioned like "
                 "code. v2 revised one phrasing and added one reason, each with "
                 "compliance sign-off recorded in the file.",
        )
        with col_c:
            st.write("")
            submitted = st.form_submit_button("Run decision", type="primary")

    if submitted:
        with st.spinner("Scoring, applying policy, deriving reasons, snapshotting..."):
            st.session_state["last_decision"] = decide(
                persona, store, model_version=model_version, contract_version=contract_version
            )

    record = st.session_state.get("last_decision")
    if record is None:
        st.markdown(display_row("Adverse Action Codes", aux="AWAITING DECISION"), unsafe_allow_html=True)
        st.markdown(
            '<div class="logic-card"><div class="micro">How to read this panel</div>'
            "<p>Pick an applicant and run a decision. A decline lists up to four "
            "reasons, each drawn word-for-word from an approved, versioned phrasebook "
            "(<code>config/reason_codes_v2.yaml</code>). The percentage next to a reason "
            "is how much of the model's risk signal it carried; RULE means a hard "
            "policy rule drove it outright. Every decision is sealed to a permanent "
            "record before it is shown.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        status_class = {"approve": "status-approve", "decline": "status-decline", "review": "status-review"}[record.decision]
        status_text = {"approve": "APPROVED", "decline": "DECLINED", "review": "REVIEW"}[record.decision]
        st.markdown(display_row("Adverse Action Codes", status_text=status_text, status_class=status_class), unsafe_allow_html=True)
        st.markdown(
            f'<div class="micro">{persona_label(record.persona)} &nbsp;|&nbsp; {record.population.replace("_", " ")} &nbsp;|&nbsp; '
            f"decision <code>{record.decision_id}</code> &nbsp;|&nbsp; model <code>{record.score.model_version}</code> "
            f"&nbsp;|&nbsp; config <code>{record.decision_config_version}</code></div>",
            unsafe_allow_html=True,
        )

        if record.decision == "decline":
            # compute each contribution code's share of positive contribution mass
            positive = [c for c in record.score.contributions if c.contribution > 0]
            total = sum(c.contribution for c in positive) or 1.0
            feature_share = {c.feature: c.contribution / total for c in positive}
            # attach share labels by walking the contract mapping through rank order
            from decisioning.contract import load_contract

            contract = load_contract(record.contract_version)
            code_features = {c.id: (c.maps_to.features or []) for c in contract.codes}
            for rc in record.reason_codes:
                if rc.source == "contribution":
                    rc._share = sum(feature_share.get(f, 0.0) for f in code_features.get(rc.code_id, []))
            st.markdown(reason_list(record.reason_codes), unsafe_allow_html=True)

            tab_gov, tab_naive = st.tabs(["Governed notice", "Naive LLM (the anti-pattern)"])
            with tab_gov:
                st.text(record.notice_text)
                st.caption(
                    f"Generation mode: {record.notice_mode}. Validation is exact slot match "
                    "against the contract; any failure falls back to pure templates."
                )
            with tab_naive:
                st.markdown(prose_block(naive_llm_notice(record)), unsafe_allow_html=True)
                st.caption(
                    "Deliberately non-compliant: raw features in, fluent prose out. "
                    "True, unapproved, unranked, different every run."
                )
        elif record.decision == "review":
            st.markdown(
                '<div class="logic-card"><div class="micro">Routed to manual review</div>'
                "<p>No adverse-action notice is generated for review outcomes in this demo; "
                "review is routing, not adverse action.</p></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="logic-card"><div class="micro">Approved</div>'
                "<p>No reason codes and no notice: adverse-action obligations attach to "
                "declines. Open the internals below to see the exact contributions that "
                "cleared the cutoffs.</p></div>",
                unsafe_allow_html=True,
            )

        with st.expander("Model internals"):
            st.markdown(
                f"Probability of default `{record.score.probability_of_default:.4f}` | "
                f"artifact sha `{record.score.model_sha256[:12]}`"
            )
            st.markdown('<div class="micro">Exact contributions (coefficient times standardized value)</div>', unsafe_allow_html=True)
            st.markdown(contributions_table(record.score.contributions), unsafe_allow_html=True)
            st.markdown('<div class="micro">Rule trace</div>', unsafe_allow_html=True)
            from decisioning.contract import load_policy

            rule_effects = {r.id: r.effect for r in load_policy().rules}
            st.markdown(rule_trace_table(record.rule_trace, rule_effects), unsafe_allow_html=True)

# ---------------------------------------------------------------- right card
with right:
    st.markdown('<div class="micro">Governance record</div>', unsafe_allow_html=True)
    st.markdown(display_row("Snapshot"), unsafe_allow_html=True)

    decisions = store.list_decisions()
    decision_ids = [d["decision_id"] for d in decisions]
    chosen = st.selectbox(
        "Decision under dispute", decision_ids,
        help="Every decision run in this session appears here, plus one seeded "
             "decision from last week. Pick one to pull its sealed record.",
    )
    chosen_meta = next(d for d in decisions if d["decision_id"] == chosen)

    st.markdown(
        timeline([
            ("Scorecard retrained", "full_file:v2 | vocabulary v2 active", False),
            ("Reason vocabulary revised", "reason_codes v2 | signed off", False),
            (
                "Original decision",
                f"{chosen} | model {chosen_meta['model_version'].split(':')[-1]} | "
                f"{chosen_meta['created_at']:%d %b %Y}".upper(),
                True,
            ),
        ]),
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="logic-card"><div class="micro">Decision logic</div>'
        "<p>The snapshot stores the model hash, config hash, full input vector, rule "
        "trace, ranked reasons, and notice text, written before the decision was ever "
        "shown. Replay reads that record; it never recomputes.</p></div>",
        unsafe_allow_html=True,
    )

    if st.button("Replay decision"):
        try:
            st.session_state["replayed"] = store.replay(chosen)
        except DecisionNotFound as e:
            st.error(str(e))

    replayed = st.session_state.get("replayed")
    if replayed and replayed.decision_id == chosen:
        st.markdown(
            display_row("Governed Replay", aux=f"{replayed.decision.upper()} | AS DECIDED"),
            unsafe_allow_html=True,
        )
        st.markdown(reason_list(replayed.reason_codes), unsafe_allow_html=True)
        st.markdown(
            f'<p class="replay-note">Stored under model <code>{replayed.score.model_version}</code> '
            f"and config <code>{replayed.decision_config_version}</code>. The original wording "
            f"survives even though the active contract has moved on.</p>",
            unsafe_allow_html=True,
        )

        if st.button("Verify re-derivation (SR 11-7 mode)"):
            try:
                verify(chosen, store)
                st.session_state["verified"] = chosen
            except VerificationFailure as e:
                st.session_state["verified"] = None
                st.error(f"Verification FAILED: {e}")

        if st.session_state.get("verified") == chosen:
            st.markdown(display_row("Verified", aux="MATCH 100%"), unsafe_allow_html=True)
            st.markdown(
                f'<p class="replay-note">The pinned artifacts for <code>{replayed.score.model_version}</code> '
                f"were loaded and the decision re-derived from scratch. Decision, ranked reason "
                f"codes, and rule trace match the snapshot exactly; probability agrees within "
                f"1e-9. Even with v2 active in production, this record re-explains identically.</p>",
                unsafe_allow_html=True,
            )
