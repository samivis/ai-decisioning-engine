"""Policy rule evaluation and outcome arbitration.

Decision flow:

    FeatureVector + score_probability
              |
              v
    +--------------------+
    | evaluate all rules |   every rule lands in the trace, fired or not
    +--------------------+
              |
              v
    any fired rule with effect decline? --yes--> DECLINE
              | no
              v
    any fired rule with effect review?  --yes--> REVIEW
              | no
              v
    probability < approve_below[pop]?   --yes--> APPROVE
              | no
              v
    probability < review_below[pop]?    --yes--> REVIEW
              | no
              v
           DECLINE

Rule `when` expressions are simple comparisons over FeatureVector fields
plus `population`. They are parsed with ast and evaluated with a strict
whitelist (no calls, no attributes, no subscripts), so the yaml can never
execute arbitrary code.
"""

from __future__ import annotations

import ast

from decisioning.contract import Policy
from decisioning.schemas import FeatureVector, Outcome, RuleTraceEntry

_ALLOWED_NODES = (
    ast.Expression,
    ast.Compare,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.Name,
    ast.Constant,
    ast.Load,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)


class RuleExpressionError(Exception):
    """Raised when a rule `when` expression is malformed or unsafe."""


def _eval_node(node: ast.AST, env: dict[str, object]) -> object:
    if not isinstance(node, _ALLOWED_NODES):
        raise RuleExpressionError(f"disallowed syntax: {type(node).__name__}")
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, env)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise RuleExpressionError(f"unknown name: {node.id}")
        return env[node.id]
    if isinstance(node, ast.BoolOp):
        results = [bool(_eval_node(v, env)) for v in node.values]
        return all(results) if isinstance(node.op, ast.And) else any(results)
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, env)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, env)
            ok = {
                ast.Eq: lambda a, b: a == b,
                ast.NotEq: lambda a, b: a != b,
                ast.Lt: lambda a, b: a < b,
                ast.LtE: lambda a, b: a <= b,
                ast.Gt: lambda a, b: a > b,
                ast.GtE: lambda a, b: a >= b,
            }[type(op)](left, right)
            if not ok:
                return False
            left = right
        return True
    raise RuleExpressionError(f"disallowed syntax: {type(node).__name__}")


def safe_eval(expression: str, env: dict[str, object]) -> bool:
    tree = ast.parse(expression, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise RuleExpressionError(
                f"disallowed syntax in rule expression: {type(node).__name__}"
            )
    return bool(_eval_node(tree, env))


def _rule_env(fv: FeatureVector) -> dict[str, object]:
    env: dict[str, object] = dict(fv.model_dump())
    env["population"] = fv.population
    return env


def evaluate_rules(fv: FeatureVector, policy: Policy) -> list[RuleTraceEntry]:
    """Evaluate every policy rule; every rule appears in the trace."""
    env = _rule_env(fv)
    trace: list[RuleTraceEntry] = []
    for rule in policy.rules:
        fired = safe_eval(rule.when, env)
        trace.append(
            RuleTraceEntry(
                rule_id=rule.id,
                fired=fired,
                effect=rule.effect if fired else None,
                detail=f"{rule.when} -> {fired} ({rule.description})",
            )
        )
    return trace


def apply_policy(
    fv: FeatureVector,
    score_probability: float,
    policy: Policy,
    rule_trace: list[RuleTraceEntry],
) -> Outcome:
    """Arbitrate: fired decline rules win, then fired review rules, then
    population score cutoffs."""
    fired_effects = {entry.effect for entry in rule_trace if entry.fired}
    if "decline" in fired_effects:
        return "decline"
    if "review" in fired_effects:
        return "review"
    cutoffs = policy.populations[fv.population]
    if score_probability < cutoffs.approve_below:
        return "approve"
    if score_probability < cutoffs.review_below:
        return "review"
    return "decline"
