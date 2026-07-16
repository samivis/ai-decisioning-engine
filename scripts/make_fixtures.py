"""Deterministic synthetic persona fixture generator.

Emits three Plaid-shaped /transactions/sync response subsets into
data/fixtures/. Fixed seed, fixed anchor date: byte-identical output on
every run (tested). Provenance is stamped into every file; nothing here
was ever captured from a live API.

Plaid amount convention: positive = money OUT (debit), negative = money
IN (credit/deposit).

Personas:
    healthy_full_file    steady payroll (~$85k/yr), 3 recurring debt
                         obligations, zero NSF, stable balances, 8 months
    distressed_full_file payroll ~$52k/yr, 5 NSF fees in last 90 days,
                         late fees + collection payments, high
                         expense-to-income, declining balance, 3 obligations
    thin_file            gig income (~$38k/yr annualized), 4 months of
                         history, 1 recurring obligation, zero NSF
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20260716
ANCHOR = date(2026, 6, 30)  # fixed window end so output never drifts
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures"


def _txn(rng: random.Random, account_id: str, day: date, amount: float, name: str, category: str) -> dict:
    return {
        "transaction_id": f"txn-{rng.getrandbits(48):012x}",
        "account_id": account_id,
        "date": day.isoformat(),
        "amount": round(amount, 2),
        "name": name,
        "personal_finance_category": {"primary": category},
    }


def _monthly_days(start: date, end: date, day_of_month: int) -> list[date]:
    """Every occurrence of day_of_month between start and end inclusive."""
    days = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        d = date(y, m, min(day_of_month, 28))
        if start <= d <= end:
            days.append(d)
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return days


def _biweekly_days(end: date, count: int) -> list[date]:
    return sorted(end - timedelta(days=14 * i) for i in range(count))


def make_healthy(rng: random.Random) -> dict:
    acct = "acct-healthy-checking"
    start = ANCHOR - timedelta(days=239)  # ~8 months
    txns: list[dict] = []
    # Payroll: same employer, biweekly, ~85k/yr (26 * 3269.23).
    for d in _biweekly_days(ANCHOR - timedelta(days=3), 17):
        txns.append(_txn(rng, acct, d, -3269.23, "ACME CORP PAYROLL", "INCOME"))
    for d in _monthly_days(start, ANCHOR, 1):
        txns.append(_txn(rng, acct, d, 1600.00, "OAKWOOD APTS RENT", "RENT_AND_UTILITIES"))
    for d in _monthly_days(start, ANCHOR, 5):
        txns.append(_txn(rng, acct, d, 145.00 + rng.uniform(-10, 10), "CITY POWER AND WATER", "RENT_AND_UTILITIES"))
    # Debt obligations: 2 loans + 1 credit card => open_accounts >= 3.
    for d in _monthly_days(start, ANCHOR, 10):
        txns.append(_txn(rng, acct, d, 352.00, "LAKESIDE AUTO LOAN PAYMENT", "LOAN_PAYMENTS"))
    for d in _monthly_days(start, ANCHOR, 12):
        txns.append(_txn(rng, acct, d, 218.00, "NAVIENT STUDENT LOAN PAYMENT", "LOAN_PAYMENTS"))
    for d in _monthly_days(start, ANCHOR, 20):
        txns.append(_txn(rng, acct, d, 400.00, "CHASE CREDIT CARD PAYMENT", "LOAN_PAYMENTS"))
    # Groceries, weekly-ish.
    d = start + timedelta(days=2)
    while d <= ANCHOR:
        txns.append(_txn(rng, acct, d, rng.uniform(90, 140), "WHOLE HARVEST GROCERY", "FOOD_AND_DRINK"))
        d += timedelta(days=7)
    # Surplus swept to savings monthly: keeps the checking balance stable.
    for d in _monthly_days(start, ANCHOR, 27):
        txns.append(_txn(rng, acct, d, 3900.00, "TRANSFER TO SAVINGS", "TRANSFER_OUT"))
    return {
        "accounts": [
            {"account_id": acct, "type": "depository", "subtype": "checking", "balances": {"current": 11250.44}},
        ],
        "transactions": sorted(txns, key=lambda t: (t["date"], t["transaction_id"])),
    }


def make_distressed(rng: random.Random) -> dict:
    acct = "acct-distressed-checking"
    start = ANCHOR - timedelta(days=239)
    txns: list[dict] = []
    # Payroll ~52k/yr (26 * 2000).
    for d in _biweekly_days(ANCHOR - timedelta(days=5), 17):
        txns.append(_txn(rng, acct, d, -2000.00, "RIVERTON LOGISTICS PAYROLL", "INCOME"))
    for d in _monthly_days(start, ANCHOR, 1):
        txns.append(_txn(rng, acct, d, 1400.00, "PINE COURT RENT", "RENT_AND_UTILITIES"))
    for d in _monthly_days(start, ANCHOR, 6):
        txns.append(_txn(rng, acct, d, 130.00 + rng.uniform(-8, 8), "CITY POWER AND WATER", "RENT_AND_UTILITIES"))
    # 3 recurring debt obligations => full_file.
    for d in _monthly_days(start, ANCHOR, 9):
        txns.append(_txn(rng, acct, d, 318.00, "DRIVETIME AUTO LOAN PAYMENT", "LOAN_PAYMENTS"))
    for d in _monthly_days(start, ANCHOR, 14):
        txns.append(_txn(rng, acct, d, 245.00, "ONEMAIN PERSONAL LOAN PAYMENT", "LOAN_PAYMENTS"))
    for d in _monthly_days(start, ANCHOR, 22):
        txns.append(_txn(rng, acct, d, 290.00, "CAPITAL ONE CREDIT CARD PAYMENT", "LOAN_PAYMENTS"))
    # Delinquency signal: late fees and collection payments.
    for d in _monthly_days(start, ANCHOR, 24):
        txns.append(_txn(rng, acct, d, 35.00, "LATE FEE", "BANK_FEES"))
    for d in _monthly_days(start + timedelta(days=60), ANCHOR, 26):
        txns.append(_txn(rng, acct, d, 150.00, "MIDLAND COLLECTION AGENCY PAYMENT", "LOAN_PAYMENTS"))
    # 5 NSF fees inside the last 90 days.
    for offset in (8, 21, 40, 62, 80):
        txns.append(_txn(rng, acct, ANCHOR - timedelta(days=offset), 34.00, "NSF FEE", "BANK_FEES"))
    # Heavy discretionary spend: expense-to-income high, balance declining.
    d = start + timedelta(days=1)
    while d <= ANCHOR:
        txns.append(_txn(rng, acct, d, rng.uniform(180, 240), "QUICKMART PURCHASE", "GENERAL_MERCHANDISE"))
        d += timedelta(days=3)
    return {
        "accounts": [
            {"account_id": acct, "type": "depository", "subtype": "checking", "balances": {"current": 412.18}},
        ],
        "transactions": sorted(txns, key=lambda t: (t["date"], t["transaction_id"])),
    }


def make_thin(rng: random.Random) -> dict:
    acct = "acct-thin-checking"
    start = ANCHOR - timedelta(days=118)  # 4 months
    txns: list[dict] = []
    # Gig income, irregular payers and amounts, ~38k/yr annualized
    # (~3167/mo, ~731/wk).
    payers = ["DOORDASH DIRECT DEP", "UBER EARNINGS", "INSTACART SHOPPER PAY"]
    d = start + timedelta(days=1)
    while d <= ANCHOR:
        for _ in range(rng.randint(2, 3)):
            txns.append(_txn(rng, acct, d + timedelta(days=rng.randint(0, 4)), -rng.uniform(240, 345), rng.choice(payers), "INCOME"))
        d += timedelta(days=7)
    for d in _monthly_days(start, ANCHOR, 3):
        txns.append(_txn(rng, acct, d, 1100.00, "MAPLE ST RENT", "RENT_AND_UTILITIES"))
    # Exactly 1 recurring obligation => open_accounts <= 2 => thin_file.
    for d in _monthly_days(start, ANCHOR, 18):
        txns.append(_txn(rng, acct, d, 120.00, "DISCOVER CREDIT CARD PAYMENT", "LOAN_PAYMENTS"))
    d = start + timedelta(days=4)
    while d <= ANCHOR:
        txns.append(_txn(rng, acct, d, rng.uniform(60, 110), "CORNER GROCERY", "FOOD_AND_DRINK"))
        d += timedelta(days=6)
    for d in _monthly_days(start, ANCHOR, 25):
        txns.append(_txn(rng, acct, d, 1500.00, "TRANSFER TO SAVINGS", "TRANSFER_OUT"))
    return {
        "accounts": [
            {"account_id": acct, "type": "depository", "subtype": "checking", "balances": {"current": 2140.77}},
        ],
        "transactions": sorted(txns, key=lambda t: (t["date"], t["transaction_id"])),
    }


PERSONAS = {
    "healthy_full_file": make_healthy,
    "distressed_full_file": make_distressed,
    "thin_file": make_thin,
}


def main(out_dir: Path = FIXTURES_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, builder in PERSONAS.items():
        rng = random.Random(f"{SEED}:{name}")
        body = builder(rng)
        fixture = {
            "persona": name,
            "generated_by": "scripts/make_fixtures.py",
            "provenance": "synthetic, never captured from live API",
            "accounts": body["accounts"],
            "transactions": body["transactions"],
        }
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
        print(f"wrote {path} ({len(body['transactions'])} transactions)")


if __name__ == "__main__":
    main()
