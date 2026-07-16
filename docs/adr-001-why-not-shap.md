# ADR-001: Linear scorecard with exact coefficient contributions, not gradient boosting plus SHAP

Status: accepted

## Context

The reason-code layer must cite, per applicant, which features drove the
decision. Those citations become adverse-action reasons, so they need to be
mathematically honest and reproducible on replay. Two candidate designs:

1. Logistic regression on standardized features. Per-feature contribution
   is `coefficient_i * standardized_value_i`, and the contributions plus the
   intercept sum exactly to the logit of the returned probability.
2. Gradient boosting (XGBoost or LightGBM) with SHAP values for attribution.

## Decision

Logistic regression scorecards, one per population, with exact coefficient
contributions. No SHAP.

## Rationale

- Exactness. SHAP values for tree ensembles are exact for the Shapley game
  they define, but the game itself (feature coalitions, background
  distribution choices) is a modeling decision that changes attributions.
  A linear model has one attribution and it is an identity, not an
  approximation. A replay test can assert it to 1e-9.
- Auditability. A regulator or model validator can verify a scorecard with
  a calculator. Explaining TreeSHAP's interventional versus conditional
  expectation choices to an audit is a real cost.
- Per-population clarity. Two small scorecards with separate cutoffs are
  easier to reason about than one ensemble with a population feature and
  interaction effects that blur which population drove a decision.
- This mirrors production practice. Real credit scorecards are largely
  linear on binned features for exactly these reasons.

## Tradeoffs accepted

- Accuracy ceiling. Gradient boosting would likely add a few points of AUC
  by capturing nonlinearities and interactions. We accept that ceiling;
  model accuracy is explicitly not the point of this system.
- Feature engineering burden shifts to us. The linear model only sees what
  we hand it, so nonlinear signal has to be encoded manually (binning,
  ratios) if it matters.

## Honest caveat: correlated features

Coefficient attributions are exact for the fitted model but not necessarily
stable across refits. When features are correlated (income and employment
length are, here), two nearly equivalent models can distribute weight
differently between the correlated pair, flipping which one ranks first in
an applicant's contributions. The attribution is still exact; the model it
is exact about is what moved.

We bound this risk with a bootstrap stability test
(`tests/test_model.py::test_bootstrap_coefficient_sign_stability`): refit on
20 bootstrap resamples and require each coefficient's sign to be stable in
at least 90 percent of fits. Sign stability is the floor that matters for
reason codes, because a sign flip would reverse the direction of a cited
reason. Rank stability between close contributions is weaker and the reason
contract handles it with explicit tie-break priorities rather than
pretending the ranking is more precise than it is.

## When SHAP would be the right call

- The accuracy gap materially changes outcomes (pricing, loss forecasting)
  and interpretability is advisory rather than contractual.
- The model is already nonlinear for reasons we cannot avoid, and some
  attribution is better than none.
- Attributions feed internal model monitoring, not consumer-facing
  adverse-action notices with legal weight.

If any of those become true, revisit this ADR rather than bolting SHAP onto
the scorecard.
