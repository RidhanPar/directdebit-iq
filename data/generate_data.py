"""Generate realistic synthetic direct-debit payment data.

Creates 50,000 rows by default and saves them to:
- data/raw/payments.csv
- data/payments.db, table: payments

Run from the project root:
    python data/generate_data.py
"""

from __future__ import annotations

import sqlite3
import sys
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

# Allow running this file directly without installing the package.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src import config  # noqa: E402


def _ensure_directories() -> None:
    """Create output directories when they do not already exist."""
    config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)


def _format_merchant_ids(rng: np.random.Generator, n_rows: int) -> np.ndarray:
    ids = rng.integers(config.MERCHANT_MIN_ID, config.MERCHANT_MAX_ID + 1, n_rows)
    return np.array([f"{config.MERCHANT_PREFIX}{i:03d}" for i in ids])


def _format_customer_ids(rng: np.random.Generator, n_rows: int) -> np.ndarray:
    ids = rng.integers(config.CUSTOMER_MIN_ID, config.CUSTOMER_MAX_ID + 1, n_rows)
    return np.array([f"{config.CUSTOMER_PREFIX}{i:04d}" for i in ids])


def _sample_payment_amounts(rng: np.random.Generator, n_rows: int) -> np.ndarray:
    """Generate mostly £10-£500 amounts with a small number of outliers."""
    typical_amounts = rng.lognormal(mean=3.75, sigma=0.75, size=n_rows)
    typical_amounts = np.clip(
        typical_amounts,
        config.AMOUNT_TYPICAL_MIN,
        config.AMOUNT_TYPICAL_MAX,
    )

    outlier_mask = rng.random(n_rows) < config.AMOUNT_OUTLIER_RATE
    outliers = rng.uniform(config.AMOUNT_OUTLIER_MIN, config.AMOUNT_OUTLIER_MAX, n_rows)
    amounts = np.where(outlier_mask, outliers, typical_amounts)
    return np.round(amounts, 2)


def _sample_payment_dates(rng: np.random.Generator, n_rows: int) -> pd.Series:
    """Generate dates from the last two years, with day 1-28 for recurring safety."""
    today = pd.Timestamp.today().normalize()
    random_days_back = rng.integers(0, config.HISTORY_DAYS + 1, n_rows)
    raw_dates = today - pd.to_timedelta(random_days_back, unit="D")

    # Direct Debit collections often use safe recurring calendar days.
    safe_days = rng.integers(config.PAYMENT_DAY_MIN, config.PAYMENT_DAY_MAX + 1, n_rows)
    safe_dates = [date.replace(day=int(day)) for date, day in zip(raw_dates, safe_days)]
    return pd.Series(pd.to_datetime(safe_dates))


def _sample_mandate_age_days(rng: np.random.Generator, n_rows: int) -> np.ndarray:
    """Skewed distribution: most mandates are newer, some are long-standing."""
    ages = rng.exponential(scale=380, size=n_rows).astype(int)
    return np.clip(ages, 0, config.MANDATE_MAX_AGE_DAYS)


def _calculate_failure_probability(df: pd.DataFrame) -> np.ndarray:
    """Calculate row-level failure probability with realistic risk patterns."""
    probability = np.full(len(df), 0.040)

    # Prior failed attempts are one of the strongest risk signals.
    probability += df["previous_failure_count"].to_numpy() * 0.045
    probability += np.where(df["previous_failure_count"].to_numpy() > 2, 0.165, 0.00)

    # New mandates are less proven and fail more often.
    mandate_age = df["mandate_age_days"].to_numpy()
    probability += np.where(mandate_age < 30, 0.135, 0.00)
    probability += np.where((mandate_age >= 30) & (mandate_age < 90), 0.055, 0.00)

    # Monday is often operationally heavier after weekend activity.
    day = df["day_of_week"].to_numpy()
    probability += np.where(day == "Monday", 0.070, 0.00)
    probability += np.where(day == "Tuesday", 0.020, 0.00)
    probability += np.where(day == "Friday", 0.010, 0.00)

    # Balance band is a clear synthetic proxy for insufficient funds risk.
    balance = df["estimated_balance_band"].to_numpy()
    probability += np.where(balance == "low", 0.180, 0.00)
    probability += np.where(balance == "medium", 0.030, 0.00)
    probability -= np.where(balance == "high", 0.020, 0.00)

    # Bank and payment type effects add operational realism.
    bank_type = df["bank_type"].to_numpy()
    probability += np.where(bank_type == "challenger", 0.025, 0.00)
    probability += np.where(bank_type == "credit_union", 0.012, 0.00)

    payment_type = df["payment_type"].to_numpy()
    probability += np.where(payment_type == "one_off", 0.020, 0.00)

    # Very high amounts carry greater risk; tiny amounts can be test/debit retries.
    amount = df["payment_amount"].to_numpy()
    probability += np.where(amount > 500, 0.070, 0.00)
    probability += np.where(amount < 15, 0.012, 0.00)

    # Days since last success captures customer inactivity risk.
    days_since_success = df["days_since_last_success"].to_numpy()
    probability += np.where(days_since_success > 60, 0.050, 0.00)
    probability += np.where((days_since_success > 30) & (days_since_success <= 60), 0.015, 0.00)

    # Country-level small differences for realism.
    country = df["bank_country"].to_numpy()
    probability += np.where(np.isin(country, ["US", "AU"]), 0.015, 0.00)
    probability -= np.where(country == "GB", 0.010, 0.00)

    # Calibrate the generated sample close to the requested 15% failure rate.
    probability = probability * (config.TARGET_FAILURE_RATE / probability.mean())
    return np.clip(probability, 0.015, 0.70)


def generate_payments(n_rows: int = config.N_ROWS, seed: int = config.RANDOM_SEED) -> pd.DataFrame:
    """Return a synthetic payment-level dataset."""
    rng = np.random.default_rng(seed)
    payment_dates = _sample_payment_dates(rng, n_rows)

    df = pd.DataFrame(
        {
            "payment_id": [str(uuid.uuid4()) for _ in range(n_rows)],
            "merchant_id": _format_merchant_ids(rng, n_rows),
            "customer_id": _format_customer_ids(rng, n_rows),
            "payment_amount": _sample_payment_amounts(rng, n_rows),
            "currency": rng.choice(config.CURRENCIES, n_rows, p=config.CURRENCY_WEIGHTS),
            "payment_date": payment_dates.dt.date.astype(str),
            "payment_day_of_month": payment_dates.dt.day.astype(int),
            "day_of_week": payment_dates.dt.day_name(),
            "mandate_age_days": _sample_mandate_age_days(rng, n_rows),
            "previous_failure_count": rng.choice(
                config.PREVIOUS_FAILURE_VALUES,
                n_rows,
                p=config.PREVIOUS_FAILURE_WEIGHTS,
            ),
            "bank_country": rng.choice(
                config.BANK_COUNTRIES,
                n_rows,
                p=config.BANK_COUNTRY_WEIGHTS,
            ),
            "bank_type": rng.choice(config.BANK_TYPES, n_rows, p=config.BANK_TYPE_WEIGHTS),
            "estimated_balance_band": rng.choice(
                config.BALANCE_BANDS,
                n_rows,
                p=config.BALANCE_BAND_WEIGHTS,
            ),
            "days_since_last_success": rng.integers(
                0,
                config.DAYS_SINCE_LAST_SUCCESS_MAX + 1,
                n_rows,
            ),
            "payment_type": rng.choice(
                config.PAYMENT_TYPES,
                n_rows,
                p=config.PAYMENT_TYPE_WEIGHTS,
            ),
        }
    )

    failure_probability = _calculate_failure_probability(df)
    is_failed = rng.random(n_rows) < failure_probability
    df["payment_status"] = np.where(is_failed, "failed", "success")

    # Stable professional column ordering.
    return df[
        [
            "payment_id",
            "merchant_id",
            "customer_id",
            "payment_amount",
            "currency",
            "payment_date",
            "payment_day_of_month",
            "day_of_week",
            "mandate_age_days",
            "previous_failure_count",
            "bank_country",
            "bank_type",
            "estimated_balance_band",
            "days_since_last_success",
            "payment_type",
            "payment_status",
        ]
    ]


def save_outputs(df: pd.DataFrame) -> None:
    """Save generated payments to CSV and SQLite."""
    _ensure_directories()
    df.to_csv(config.RAW_PAYMENTS_CSV, index=False)

    with sqlite3.connect(config.SQLITE_DB_PATH) as conn:
        df.to_sql(config.SQLITE_TABLE_NAME, conn, if_exists="replace", index=False)


def main() -> None:
    df = generate_payments()
    save_outputs(df)

    failure_rate = (df["payment_status"] == "failed").mean()
    print(f"Generated {len(df):,} payments")
    print(f"Saved CSV: {config.RAW_PAYMENTS_CSV}")
    print(f"Saved SQLite DB: {config.SQLITE_DB_PATH}")
    print(f"Observed success rate: {1 - failure_rate:.2%}")
    print(f"Observed failure rate: {failure_rate:.2%}")


if __name__ == "__main__":
    main()
