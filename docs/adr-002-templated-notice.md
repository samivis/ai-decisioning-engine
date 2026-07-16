# ADR-002: The adverse-action notice is templated, not generative

## Status

Accepted.

## Decision

The applicant-facing adverse-action notice is rendered from sentence
templates keyed to approved reason-code ids. An LLM may participate only
inside a cage: it receives the approved reason text verbatim, may add
connective opening and closing phrasing, and its output is validated by
exact substring match, in rank order, against the contract text. Any
validation failure, timeout, refusal, or malformed output falls back to
pure template rendering. The naive alternative, handing the LLM raw
features and asking it to explain the decline, is implemented too, but
only as a labeled anti-pattern exhibit in the demo.

## Why

1. An adverse-action notice is a legal document with a controlled
   vocabulary. Generative variance is a liability with no offsetting
   benefit: the applicant needs the specific approved reasons, not fluent
   prose about them.
2. Validation by paraphrase detection is a losing game. An LLM can restate
   a non-approved reason in synonyms that pass any denylist. Exact slot
   matching flips the burden: the only way to pass validation is to carry
   the approved text unchanged.
3. The fallback is the floor, not a degraded mode. If the cage ever
   rejects an output, the applicant still receives a fully compliant
   templated notice. Production behavior under failure is identical to
   production behavior under success, minus polish.

## Tradeoffs accepted

- Notices read as formal boilerplate rather than warm prose. For this
  document class, that is correct.
- The LLM adds little here by design. The point of including it at all is
  to show precisely where generative AI fits in a regulated decisioning
  flow: at the edges, caged, with a deterministic floor.

## When generative would be right

Explanatory surfaces that are not legal notices: internal analyst
summaries, applicant help content, dispute-intake triage. Anywhere the
vocabulary is not contractual and a wrong word is a quality bug rather
than a compliance event.
