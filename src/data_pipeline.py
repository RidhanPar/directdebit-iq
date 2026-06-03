"""Data loading and cleaning pipeline for DirectDebit IQ."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import pandas as pd

from src import config
from src.utils import ensure_project_directories, load_payments_csv


REQUIRED_COLUMNS = [
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


def validate_schema(df: pd.DataFrame) -> None:
    """Raise an error if required payment columns are missing."""
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")


def clean_payments(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and type raw payment records."""
    validate_schema(df)
    cleaned = df.copy()

    cleaned["payment_date"] = pd.to_datetime(cleaned["payment_date"], errors="coerce")
    cleaned["payment_amount"] = pd.to_numeric(cleaned["payment_amount"], errors="coerce")
    cleaned["payment_day_of_month"] = pd.to_numeric(
        cleaned["payment_day_of_month"], errors="coerce"
    ).astype("Int64")
    cleaned["mandate_age_days"] = pd.to_numeric(
        cleaned["mandate_age_days"], errors="coerce"
    ).astype("Int64")
    cleaned["previous_failure_count"] = pd.to_numeric(
        cleaned["previous_failure_count"], errors="coerce"
    ).astype("Int64")
    cleaned["days_since_last_success"] = pd.to_numeric(
        cleaned["days_since_last_success"], errors="coerce"
    ).astype("Int64")

    cleaned = cleaned.dropna(subset=["payment_date", "payment_amount", "payment_status"])
    cleaned = cleaned[cleaned["payment_amount"] > 0]
    cleaned["payment_status"] = cleaned["payment_status"].str.lower().str.strip()
    cleaned = cleaned[cleaned["payment_status"].isin(config.PAYMENT_STATUSES)]

    string_columns = [
        "payment_id",
        "merchant_id",
        "customer_id",
        "currency",
        "day_of_week",
        "bank_country",
        "bank_type",
        "estimated_balance_band",
        "payment_type",
    ]
    for column in string_columns:
        cleaned[column] = cleaned[column].astype(str).str.strip()

    return cleaned.reset_index(drop=True)


def run_pipeline() -> pd.DataFrame:
    """Load raw CSV, clean it, and save the processed version."""
    ensure_project_directories()
    raw = load_payments_csv()
    processed = clean_payments(raw)
    processed.to_csv(config.PROCESSED_PAYMENTS_CSV, index=False)
    return processed


if __name__ == "__main__":
    df = run_pipeline()
    print(f"Processed {len(df):,} payment rows")
    print(f"Saved: {config.PROCESSED_PAYMENTS_CSV}")
