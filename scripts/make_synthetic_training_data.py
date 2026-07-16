#!/usr/bin/env python
"""Generate SYNTHETIC training data for the credit scorecards.

============================================================================
LOUD DISCLAIMER: THIS IS A SYNTHETIC STAND-IN, NOT REAL LENDING DATA.
No Kaggle credentials were available in this environment, so this script
fabricates ~50k rows shaped like the LendingClub-derived feature set the
scorecards expect. Distributions and correlations are plausible but made up
from a known true coefficient structure. Do NOT quote AUC numbers from
models trained on this data as if they measured real-world performance.
============================================================================

Real-data path (what to do when you have Kaggle access):

1. Download the Kaggle dataset ``wordsforthewise/lending-club`` and take the
   accepted-loans CSV (``accepted_2007_to_2018Q4.csv``), e.g.::

       kaggle datasets download -d wordsforthewise/lending-club
       unzip lending-club.zip -d data/lendingclub/

2. Run ``scripts/train_model.py --data <path to accepted csv>``. It maps the
   real columns onto the model feature space:

       annual_inc   -> annual_income_estimate
       dti          -> dti_proxy (LendingClub dti is a percentage; divide
                       by 100 to get a ratio comparable to this synthetic
                       expense/income proxy)
       delinq_2yrs  -> delinquency_proxy
       emp_length   -> employment_length_years (parse "10+ years" -> 10.0,
                       "< 1 year" -> 0.5, "n/a" -> 0.0)
       open_acc     -> open_accounts

   Target: ``default = 1`` when ``loan_status`` is "Charged Off" or
   "Late (31-120 days)" / "Late (16-30 days)" 120+ bucket ("Late (31-120
   days)" is the closest LendingClub bucket to 120+ late); ``default = 0``
   for "Fully Paid". EXCLUDE "Current" and other in-progress statuses
   entirely: still-open loans have unknown outcomes and keeping them as
   non-defaults would leak optimism into the label.

   Survivorship bias caveat: the accepted-loans file only contains loans
   LendingClub chose to fund. Applicants rejected at origination are absent,
   so the trained model sees a truncated risk distribution and its
   probabilities are not calibrated for the full applicant population.

Usage::

    .venv/bin/python scripts/make_synthetic_training_data.py [--rows 50000]

Writes ``data/lendingclub/synthetic_training.csv`` (data/lendingclub/ is
gitignored, matching where the real Kaggle CSV would land).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260715
DEFAULT_ROWS = 50_000
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "lendingclub" / "synthetic_training.csv"

# True coefficient structure on standardized features (log-odds scale).
# Signs are the point: higher dti and delinquency push toward default,
# higher income and employment length push away from it.
TRUE_COEFFICIENTS: dict[str, float] = {
    "annual_income_estimate": -0.55,
    "dti_proxy": 0.90,
    "delinquency_proxy": 0.70,
    "employment_length_years": -0.30,
    "open_accounts": 0.15,
}
TRUE_INTERCEPT = -1.7  # base default rate around 15 percent


def generate(rows: int = DEFAULT_ROWS, seed: int = SEED) -> pd.DataFrame:
    """Generate a synthetic training frame with a known coefficient structure."""
    rng = np.random.default_rng(seed)

    # Latent correlated normals: income correlates negatively with dti and
    # delinquency, mildly positively with employment length and open accounts.
    corr = np.array(
        [
            #  inc    dti    delinq emp    open
            [1.00, -0.35, -0.20, 0.30, 0.15],  # income
            [-0.35, 1.00, 0.25, -0.10, 0.20],  # dti
            [-0.20, 0.25, 1.00, -0.05, 0.10],  # delinquency
            [0.30, -0.10, -0.05, 1.00, 0.10],  # employment length
            [0.15, 0.20, 0.10, 0.10, 1.00],  # open accounts
        ]
    )
    latent = rng.multivariate_normal(np.zeros(5), corr, size=rows)

    # Map latents to realistic marginals.
    income = np.exp(11.0 + 0.55 * latent[:, 0])  # lognormal, median ~60k
    dti = np.clip(0.32 + 0.13 * latent[:, 1], 0.0, 1.2)  # expense/income ratio
    delinq = rng.poisson(np.exp(-1.1 + 0.9 * latent[:, 2]))  # mostly 0-2 events
    emp_years = np.clip(5.5 + 3.5 * latent[:, 3], 0.0, 40.0)
    open_acc = np.clip(np.round(11 + 5 * latent[:, 4]), 0, 60).astype(int)

    frame = pd.DataFrame(
        {
            "annual_income_estimate": income.round(2),
            "dti_proxy": dti.round(4),
            "delinquency_proxy": delinq.astype(float),
            "employment_length_years": emp_years.round(2),
            "open_accounts": open_acc,
        }
    )

    # Default probability from the true coefficients on standardized features.
    logit = np.full(rows, TRUE_INTERCEPT)
    for name, coef in TRUE_COEFFICIENTS.items():
        col = frame[name].to_numpy(dtype=float)
        logit += coef * (col - col.mean()) / col.std()
    prob = 1.0 / (1.0 + np.exp(-logit))
    frame["default"] = (rng.uniform(size=rows) < prob).astype(int)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS)
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    frame = generate(args.rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.out, index=False)
    print(
        f"Wrote {len(frame):,} synthetic rows to {args.out} "
        f"(default rate {frame['default'].mean():.3f}) [SYNTHETIC STAND-IN]"
    )


if __name__ == "__main__":
    main()
