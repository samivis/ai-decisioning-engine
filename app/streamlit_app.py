"""Demo UI: run a decision, read the governed reasons, dispute it later.

Information hierarchy (deliberate): decision banner first, reason codes
second, the notice third, model internals last behind an expander. A
hiring manager should understand the decision before seeing a logit.

Decisions run inside a form so inputs and the click submit atomically:
a rapid double-click cannot fire two decisions or execute against stale
widget state (QA finding F1).
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
from style import CSS, reason_row

st.set_page_config(page_title="Explainable Credit Decisioning", page_icon="🏦", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource
def get_store() -> SnapshotStore:
    # Copy the checked-in read-only seed db to a per-process working file:
    # survives cloud ephemeral filesystems and concurrent sessions.
    working = Path(tempfile.mkdtemp()) / "decisions.db"
    return SnapshotStore.from_seed(working)


store = get_store()

st.title("Explainable credit decisioning.")
st.caption(
    "Governed adverse-action reason codes with dispute-grade reproducibility. "
    "Demo personas are synthetic and calibrated to exercise specific reason codes; "
    "that is stated here on purpose."
)
st.write("")

left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader("Decide")

    # Form = atomic submit: persona/model/contract values are read at
    # click time, and reruns cannot re-trigger the decision.
    with st.form("decide_form", border=True):
        persona = st.selectbox("Applicant persona", list_personas())
        col_a, col_b = st.columns(2)
        model_version = col_a.radio("Model", ["v1", "v2"], horizontal=True, index=1)
        contract_version = col_b.radio("Reason contract", [1, 2], horizontal=True, index=1)
        submitted = st.form_submit_button("Run decision", type="primary")

    if submitted:
        with st.spinner("Scoring, applying policy, deriving reasons, snapshotting..."):
            st.session_state["last_decision"] = decide(
                persona, store, model_version=model_version, contract_version=contract_version
            )

    record = st.session_state.get("last_decision")
    if record:
        banner = {"approve": st.success, "decline": st.error, "review": st.warning}[record.decision]
        banner(
            f"**{record.decision.upper()}**: {record.persona} "
            f"(population: {record.population}, decision id: `{record.decision_id}`)"
        )

        if record.decision == "decline":
            st.markdown("**Adverse-action reason codes, ranked, from the approved contract:**")
            st.markdown(
                "".join(
                    reason_row(c.rank, c.code_id, c.consumer_text, c.source)
                    for c in record.reason_codes
                ),
                unsafe_allow_html=True,
            )

            tab_gov, tab_naive = st.tabs(["Governed notice", "Naive LLM (the anti-pattern)"])
            with tab_gov:
                st.text(record.notice_text)
                st.caption(f"Generation mode: {record.notice_mode}. Validation: exact slot match "
                           "against the contract; any failure falls back to pure templates.")
            with tab_naive:
                st.text(naive_llm_notice(record))
                st.caption(
                    "Deliberately non-compliant: raw features in, fluent prose out. "
                    "True, unapproved, unranked, and different every run. This is why "
                    "explanation is not defensibility."
                )
        elif record.decision == "review":
            st.info("Routed to manual review. No adverse-action notice is generated for "
                    "review outcomes in this demo; review is routing, not adverse action.")

        with st.expander("Model internals (last on purpose)"):
            st.markdown(f"Probability of default: `{record.score.probability_of_default:.4f}` "
                        f"| model `{record.score.model_version}` | artifact sha `{record.score.model_sha256[:12]}...` "
                        f"| config `{record.decision_config_version}`")
            st.markdown("**Exact contributions (coefficient times standardized value):**")
            st.table([
                {"feature": c.feature, "value": round(c.value, 3), "contribution": round(c.contribution, 4)}
                for c in record.score.contributions
            ])
            st.markdown("**Rule trace:**")
            st.table([
                {"rule": t.rule_id, "fired": t.fired, "effect": t.effect or "", "detail": t.detail}
                for t in record.rule_trace
            ])

with right:
    st.subheader("Dispute")
    st.caption(
        "A decision from last week is already in the store (`D-SEED-LASTWEEK`, "
        "made under model v1 and contract v1). The world has since moved to v2. "
        "Replay it anyway."
    )
    decision_ids = [d["decision_id"] for d in store.list_decisions()]
    chosen = st.selectbox("Decision to dispute", decision_ids)

    if st.button("Replay original decision"):
        try:
            st.session_state["replayed"] = store.replay(chosen)
        except DecisionNotFound as e:
            st.error(str(e))

    replayed = st.session_state.get("replayed")
    if replayed and replayed.decision_id == chosen:
        st.markdown(
            f"**Stored decision** `{replayed.decision_id}`"
            f"{' (seeded demo decision)' if replayed.seeded else ''}: "
            f"**{replayed.decision.upper()}** under model `{replayed.score.model_version}`, "
            f"config `{replayed.decision_config_version}`, decided {replayed.created_at:%Y-%m-%d}."
        )
        st.markdown(
            "".join(
                reason_row(c.rank, c.code_id, c.consumer_text, c.source)
                for c in replayed.reason_codes
            ),
            unsafe_allow_html=True,
        )
        st.caption("Read mode: stored output, never recomputed. The original v1 wording "
                   "survives even though the active contract is v2.")

        if st.button("Verify re-derivation (SR 11-7 mode)"):
            try:
                verify(chosen, store)
                st.success(
                    "Verified: re-deriving with the pinned model artifact and contract "
                    "version reproduces the decision, the ranked reason codes, and the "
                    "rule trace exactly (probability within 1e-9)."
                )
            except VerificationFailure as e:
                st.error(f"Verification FAILED: {e}")
