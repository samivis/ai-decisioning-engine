"""Feature extraction: Plaid-shaped fixture dict -> FeatureVector.

Pipeline position:

    +---------+     +----------------+     +---------------+
    | fixture | --> | extract_       | --> | FeatureVector | --> model/rules
    | (dict)  |     | features()     |     | (schemas.py)  |
    +---------+     +----------------+     +---------------+

Plaid amount convention: positive = money OUT (debit), negative = money
IN (credit/deposit).

All thresholds that belong to policy (the thin-file routing cutoff) are
read from config/policy.yaml, never hardcoded here.
"""

from __future__ import annotations

import re
import statistics
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import yaml

from decisioning.schemas import FeatureVector, Population

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[2] / "config" / "policy.yaml"

# Word-bounded so e.g. "TRANSFER" never matches "NSF".
_NSF_PATTERN = re.compile(r"\bNSF\b|OVERDRAFT")
_DELINQUENCY_MARKERS = ("LATE FEE", "COLLECTION")
_OBLIGATION_MARKERS = ("LOAN", "CREDIT CARD")


def _thin_file_cutoff(policy_path: Path) -> int:
    policy = yaml.safe_load(policy_path.read_text())
    return int(policy["routing"]["thin_file_max_open_accounts"])


def _month_key(d: date) -> tuple[int, int]:
    return (d.year, d.month)


def extract_features(fixture: dict, policy_path: Path | str = DEFAULT_POLICY_PATH) -> FeatureVector:
    """Derive the FeatureVector from a validated fixture dict.

    Derivations:
        annual_income_estimate: sum of INCOME-category deposits (negative
            amounts) over the window, annualized by window length in days
            (* 365 / window_days). Zero when no income transactions exist,
            so the income_unverifiable policy rule routes to review.
        dti_proxy: monthly outflows (positive amounts: recurring
            obligations plus expenses, excluding TRANSFER_* categories
            since own-account transfers are neither, averaged per month)
            divided by monthly income (annual estimate / 12). Capped at
            2.0. If income is zero, set 0 and let income_unverifiable fire.
        delinquency_proxy: count of late-fee/collection-type transactions
            (name contains LATE FEE or COLLECTION) in the window, scaled
            to 12 months (count / months_of_history * 12).
        employment_length_years: payroll-consistency heuristic. For the
            INCOME payer name observed in the most distinct months, tenure
            is extrapolated as months_observed * coverage * 0.5 where
            coverage = months_observed / months_of_history, capped at
            10.0. A single employer paying across the whole window scores
            high; irregular gig payers split coverage and score low.
        open_accounts: distinct recurring debt-obligation payees: outflow
            names in LOAN_PAYMENTS category or containing LOAN / CREDIT
            CARD, seen in at least 2 distinct months.
        nsf_count_90d: NSF/overdraft fee transactions (name contains NSF
            or OVERDRAFT) dated within the last 90 days of the window.
        months_of_history: distinct (year, month) values among
            transaction dates.
        balance_volatility: daily total balance series reconstructed
            backwards from the accounts' current balances; stdev/mean,
            clamped via min(1.0, value). 1.0 when the mean is <= 0.
        population: thin_file when open_accounts <= the policy routing
            cutoff (config/policy.yaml routing.thin_file_max_open_accounts),
            else full_file.

    An empty transaction list yields an all-zeros vector (income 0 makes
    the review rule fire downstream).
    """
    cutoff = _thin_file_cutoff(Path(policy_path))
    txns = fixture.get("transactions", [])
    if not txns:
        population: Population = "thin_file"  # 0 open_accounts <= cutoff
        return FeatureVector(
            population=population,
            annual_income_estimate=0.0,
            dti_proxy=0.0,
            delinquency_proxy=0.0,
            employment_length_years=0.0,
            open_accounts=0,
            nsf_count_90d=0,
            months_of_history=0,
            balance_volatility=0.0,
        )

    parsed = [
        {
            "date": date.fromisoformat(t["date"]),
            "amount": float(t["amount"]),
            "name": str(t["name"]).upper(),
            "category": str(t.get("personal_finance_category", {}).get("primary", "")).upper(),
        }
        for t in txns
    ]
    start = min(t["date"] for t in parsed)
    end = max(t["date"] for t in parsed)
    window_days = (end - start).days + 1
    months_of_history = len({_month_key(t["date"]) for t in parsed})

    # Income (deposits are negative under the Plaid convention).
    income_txns = [t for t in parsed if t["category"] == "INCOME" and t["amount"] < 0]
    income_total = -sum(t["amount"] for t in income_txns)
    annual_income_estimate = income_total * 365.0 / window_days if income_total > 0 else 0.0

    monthly_income = annual_income_estimate / 12.0
    # Transfers move cash between the applicant's own accounts; they are
    # neither an obligation nor an expense, so dti excludes them (they
    # still count in the balance series below, being real cash movement).
    monthly_outflow = sum(
        t["amount"] for t in parsed if t["amount"] > 0 and not t["category"].startswith("TRANSFER")
    ) / max(months_of_history, 1)
    dti_proxy = min(2.0, monthly_outflow / monthly_income) if monthly_income > 0 else 0.0

    delinquency_count = sum(
        1 for t in parsed if t["amount"] > 0 and any(m in t["name"] for m in _DELINQUENCY_MARKERS)
    )
    delinquency_proxy = delinquency_count / max(months_of_history, 1) * 12.0

    # Employment length from payroll payer consistency.
    payer_months: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for t in income_txns:
        payer_months[t["name"]].add(_month_key(t["date"]))
    employment_length_years = 0.0
    if payer_months:
        best_months = max(len(m) for m in payer_months.values())
        coverage = best_months / max(months_of_history, 1)
        employment_length_years = min(10.0, best_months * coverage * 0.5)

    # Open accounts: recurring debt-obligation payees.
    obligation_months: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for t in parsed:
        if t["amount"] <= 0:
            continue
        is_obligation = t["category"] == "LOAN_PAYMENTS" or any(m in t["name"] for m in _OBLIGATION_MARKERS)
        if is_obligation and not any(m in t["name"] for m in _DELINQUENCY_MARKERS):
            obligation_months[t["name"]].add(_month_key(t["date"]))
    open_accounts = sum(1 for months in obligation_months.values() if len(months) >= 2)

    nsf_floor = end - timedelta(days=90)
    nsf_count_90d = sum(
        1
        for t in parsed
        if t["amount"] > 0 and t["date"] >= nsf_floor and _NSF_PATTERN.search(t["name"])
    )

    # Daily balance series, reconstructed backwards from current balances.
    current_total = sum(float(a.get("balances", {}).get("current", 0.0)) for a in fixture.get("accounts", []))
    net_out_by_day: dict[date, float] = defaultdict(float)
    for t in parsed:
        net_out_by_day[t["date"]] += t["amount"]
    balances: list[float] = []
    running = current_total
    day = end
    while day >= start:
        balances.append(running)
        running += net_out_by_day.get(day, 0.0)  # undo the day going backwards
        day -= timedelta(days=1)
    mean = statistics.fmean(balances)
    if mean <= 0:
        balance_volatility = 1.0
    elif len(balances) < 2:
        balance_volatility = 0.0
    else:
        balance_volatility = min(1.0, statistics.stdev(balances) / mean)

    population = "thin_file" if open_accounts <= cutoff else "full_file"
    return FeatureVector(
        population=population,
        annual_income_estimate=round(annual_income_estimate, 2),
        dti_proxy=round(dti_proxy, 4),
        delinquency_proxy=round(delinquency_proxy, 4),
        employment_length_years=round(employment_length_years, 2),
        open_accounts=open_accounts,
        nsf_count_90d=nsf_count_90d,
        months_of_history=months_of_history,
        balance_volatility=round(balance_volatility, 4),
    )
