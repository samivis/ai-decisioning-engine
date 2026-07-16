# Explainable Credit Decisioning with FCRA-Grade Reason Codes

A working credit-decisioning engine that shows how AI-driven underwriting can stay legally defensible: every decline maps to a governed, compliance-approved reason vocabulary, and every decision can be re-explained identically under dispute, even after the model changes.

**[Live demo](#)** | **[Demo GIF](#)** | Built by Samidha Visai

## The problem

<!-- 2-3 paragraphs. AI decisioning platforms generate plain-language explanations, but an accurate explanation is not a permissible adverse-action reason. FCRA and ECOA Reg B require specific, ranked, defensible reasons. Continuous-learning models make this worse: the logic that made the decision may not exist by the time a dispute arrives. -->

## Who this is for

<!-- Lenders and decisioning-platform teams shipping AI underwriting to regulated markets; secondarily, anyone evaluating "LLM explains the decision" designs. -->

## The core insight

Free-form model explanation and adverse-action compliance are different problems. This project separates them with a **reason-code contract layer**: the model proposes signals; a versioned, human-approved mapping translates them into ranked reasons from a controlled vocabulary, per applicant population. The LLM drafts the notice from those codes only, and its output is validated against the approved set before anything reaches an applicant.

## How it works

<!-- Architecture diagram (mermaid): Plaid Sandbox -> feature layer -> scorecard model -> rules/policy layer -> reason contract layer -> governed notice generation, with decision snapshot store underneath everything. -->

1. **Ingest**: applicant cash-flow data from Plaid Sandbox (or bundled fixtures)
2. **Score**: interpretable scorecard trained on public LendingClub data; per-feature contributions are exact, not approximated
3. **Decide**: policy rules on top of the score, with separate handling for thin-file applicants
4. **Explain**: contributions map to a ranked set of approved reason codes (`config/reason_codes.yaml`)
5. **Notify**: an LLM drafts the adverse-action notice from the approved codes; a validator rejects anything outside the vocabulary
6. **Snapshot**: every decision persists model version, inputs, and reason derivation, so a dispute replays the original decision exactly

## Naive vs governed explanation

<!-- Side-by-side example: what a raw "LLM, explain this decision" produces vs the governed notice. The naive one can be true and still non-compliant. -->

## Key design decisions and tradeoffs

<!-- Logistic scorecard over gradient boosting (exact contributions beat accuracy for this job). Cash-flow features mapped into bureau-style model features, and why that mirrors real thin-file underwriting. Reason vocabulary as config, not code. Template fallback when LLM validation fails. -->

## Why this matters (regulation, briefly)

<!-- FCRA 615(a) and ECOA Reg B require specific principal reasons for adverse action. SR 11-7 expects model decisions to be reproducible and governed. No overclaiming: this is a demonstration of the design pattern, not legal advice. -->

## What I would measure in production

<!-- Reason-code coverage (declines with no mappable code = launch blocker), notice validation failure rate, dispute replay fidelity, time-to-approve a new population's reason set, fair-lending monitoring hooks. -->

## Running it locally

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

That is the whole setup: model artifacts, persona fixtures, a seeded demo database, and cached LLM notice outputs are checked in, so the demo runs with zero API keys. `cp .env.example .env` with Plaid sandbox and OpenAI keys only if you want live mode; `python scripts/train_model.py` only to retrain (needs the Kaggle LendingClub dataset).

<!-- Plaid sandbox setup steps, Kaggle dataset download note. -->

## What this is not

Sandbox data and my own test accounts only; no real PII, no proprietary anything. The model is deliberately simple; the point is governed, explainable, reproducible decisioning, not accuracy.
