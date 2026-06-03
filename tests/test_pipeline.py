"""End-to-end quality tests for DirectDebit IQ.

These tests validate the portfolio project's core promise: generate realistic
payment data, build leakage-safe features, train a failure model, run SQL
analytics, and create future retry recommendations.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from data.generate_data import generate_payments
from src import config
from src.feature_store import FeatureStore
from src.recommend import build_retry_recommendations
from src.sql_runner import SQLAnalytics

EXPECTED_PAYMENT_COLUMNS = {
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
}


@pytest.fixture(scope="session")
def generated_payments() -> pd.DataFrame:
    """Generate one full synthetic dataset for row count and rate tests."""
    return generate_payments(n_rows=config.N_ROWS, seed=config.RANDOM_SEED)


def _controlled_payments(include_future: bool = False) -> pd.DataFrame:
    """Small deterministic dataset for feature leakage tests."""
    rows = [
        {
            "payment_id": "P001",
            "merchant_id": "M001",
            "customer_id": "C0001",
            "payment_amount": 100.0,
            "currency": "GBP",
            "payment_date": "2026-01-01",
            "payment_day_of_month": 1,
            "day_of_week": "Thursday",
            "mandate_age_days": 10,
            "previous_failure_count": 0,
            "bank_country": "GB",
            "bank_type": "high_street",
            "estimated_balance_band": "medium",
            "days_since_last_success": 5,
            "payment_type": "recurring",
            "payment_status": "success",
        },
        {
            "payment_id": "P002",
            "merchant_id": "M001",
            "customer_id": "C0001",
            "payment_amount": 120.0,
            "currency": "GBP",
            "payment_date": "2026-01-10",
            "payment_day_of_month": 10,
            "day_of_week": "Saturday",
            "mandate_age_days": 19,
            "previous_failure_count": 0,
            "bank_country": "GB",
            "bank_type": "high_street",
            "estimated_balance_band": "medium",
            "days_since_last_success": 14,
            "payment_type": "recurring",
            "payment_status": "failed",
        },
        {
            "payment_id": "P003",
            "merchant_id": "M001",
            "customer_id": "C0001",
            "payment_amount": 140.0,
            "currency": "GBP",
            "payment_date": "2026-01-20",
            "payment_day_of_month": 20,
            "day_of_week": "Tuesday",
            "mandate_age_days": 29,
            "previous_failure_count": 1,
            "bank_country": "GB",
            "bank_type": "high_street",
            "estimated_balance_band": "low",
            "days_since_last_success": 24,
            "payment_type": "recurring",
            "payment_status": "success",
        },
    ]
    if include_future:
        rows.append(
            {
                "payment_id": "P004",
                "merchant_id": "M001",
                "customer_id": "C0001",
                "payment_amount": 10_000.0,
                "currency": "GBP",
                "payment_date": "2026-12-31",
                "payment_day_of_month": 28,
                "day_of_week": "Thursday",
                "mandate_age_days": 365,
                "previous_failure_count": 5,
                "bank_country": "GB",
                "bank_type": "high_street",
                "estimated_balance_band": "low",
                "days_since_last_success": 90,
                "payment_type": "recurring",
                "payment_status": "failed",
            }
        )
    return pd.DataFrame(rows)


def _feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Build the leakage-sensitive intermediate feature frame."""
    store = FeatureStore()
    featured = store._prepare_base_frame(df)  # noqa: SLF001 - intentional pipeline validation
    featured = store.compute_rolling_failure_rate(featured, window=2)
    featured = store.compute_merchant_risk_score(featured)
    featured = store.compute_customer_lifetime_value(featured)
    featured = store._add_amount_zscore(featured)  # noqa: SLF001
    featured = store._add_days_since_failure(featured)  # noqa: SLF001
    return featured.sort_values("payment_id").reset_index(drop=True)


def test_data_generator_creates_correct_columns(generated_payments: pd.DataFrame) -> None:
    assert set(generated_payments.columns) == EXPECTED_PAYMENT_COLUMNS


def test_data_generator_creates_correct_row_count(generated_payments: pd.DataFrame) -> None:
    assert len(generated_payments) == 50_000


def test_success_rate_is_realistic(generated_payments: pd.DataFrame) -> None:
    success_rate = generated_payments["payment_status"].eq("success").mean()
    assert 0.80 <= success_rate <= 0.90


def test_feature_store_creates_rolling_features() -> None:
    store = FeatureStore()
    featured = store.compute_rolling_failure_rate(_controlled_payments(), window=2)
    c1 = featured.sort_values("payment_date")

    assert "rolling_failure_rate" in c1.columns
    assert c1["rolling_failure_rate"].round(3).tolist() == [0.0, 0.0, 0.5]


def test_no_data_leakage_in_features() -> None:
    base = _feature_frame(_controlled_payments(include_future=False))
    with_future = _feature_frame(_controlled_payments(include_future=True))

    compare_columns = [
        "payment_id",
        "rolling_failure_rate",
        "merchant_failure_rate",
        "customer_lifetime_payments",
        "customer_lifetime_value",
        "amount_zscore",
        "days_since_failure",
    ]
    base_first_three = base[compare_columns]
    future_first_three = with_future.loc[with_future["payment_id"].isin(["P001", "P002", "P003"]), compare_columns]
    future_first_three = future_first_three.sort_values("payment_id").reset_index(drop=True)

    pd.testing.assert_frame_equal(base_first_three, future_first_three, check_dtype=False, atol=1e-9, rtol=1e-9)


def test_model_trains_and_predicts() -> None:
    df = generate_payments(n_rows=2_000, seed=7)
    store = FeatureStore()
    model_df = store.build_feature_matrix(df)
    X = model_df.drop(columns=[config.TARGET_BINARY_COLUMN])
    y = model_df[config.TARGET_BINARY_COLUMN].astype(int)

    X_train, X_test, y_train, _ = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=config.RANDOM_SEED,
        stratify=y,
    )

    model = XGBClassifier(
        n_estimators=20,
        max_depth=2,
        learning_rate=0.10,
        eval_metric="logloss",
        random_state=config.RANDOM_SEED,
        n_jobs=1,
        tree_method="hist",
        verbosity=0,
    )
    model.fit(X_train, y_train)
    probabilities = model.predict_proba(X_test)[:, 1]

    assert len(probabilities) == len(X_test)
    assert np.all((probabilities >= 0) & (probabilities <= 1))


def test_retry_recommender_returns_required_fields() -> None:
    scored = pd.DataFrame(
        {
            "payment_id": ["P100", "P200"],
            "payment_amount": [250.0, 80.0],
            "failure_probability": [0.72, 0.48],
        }
    )
    recommendations = build_retry_recommendations(scored, start_date=pd.Timestamp("2026-06-03"))

    required_fields = {
        "payment_id",
        "payment_amount",
        "recommended_retry_date",
        "recommended_retry_day_of_week",
        "expected_success_probability",
        "priority_rank",
        "expected_recovery_amount",
    }
    assert required_fields.issubset(recommendations.columns)
    assert len(recommendations) == 2


def test_sql_queries_return_dataframes(tmp_path: Path) -> None:
    df = generate_payments(n_rows=5_000, seed=99)
    db_path = tmp_path / "payments.db"
    with sqlite3.connect(db_path) as conn:
        df.to_sql(config.SQLITE_TABLE_NAME, conn, index=False, if_exists="replace")

    analytics = SQLAnalytics(db_path=db_path, sql_dir=PROJECT_ROOT / "sql")
    results = analytics.run_all_analyses()
    analytics.close()

    assert set(results) == set(SQLAnalytics.DEFAULT_ANALYSES)
    for dataframe in results.values():
        assert isinstance(dataframe, pd.DataFrame)
        assert not dataframe.empty


def test_recommendation_dates_are_in_future() -> None:
    scored = pd.DataFrame(
        {
            "payment_id": ["P100", "P200", "P300"],
            "payment_amount": [250.0, 80.0, 500.0],
            "failure_probability": [0.72, 0.48, 0.91],
        }
    )
    anchor = pd.Timestamp("2026-06-03")
    recommendations = build_retry_recommendations(scored, start_date=anchor)

    retry_dates = pd.to_datetime(recommendations["recommended_retry_date"])
    assert (retry_dates > anchor).all()
