"""Feature engineering layer for DirectDebit IQ.

This module centralises the project features used by the failure prediction
notebook, training script, Streamlit dashboard, and tests.  The main interface is
``FeatureStore``; small wrapper functions are kept for backward compatibility
with the original project tests and earlier notebooks.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import config


class FeatureStore:
    """Build model-ready features for Direct Debit payment failure prediction.

    The class intentionally creates business-readable features so the project is
    easy to explain in interviews: customer history, merchant risk, mandate age,
    payment timing, and amount abnormality.
    """

    def __init__(self) -> None:
        self.feature_names_: list[str] = []
        self.categorical_columns_: list[str] = [
            "currency",
            "day_of_week",
            "bank_country",
            "bank_type",
            "estimated_balance_band",
            "payment_type",
            "mandate_age_band",
        ]
        self.base_numeric_features_: list[str] = [
            "payment_amount",
            "log_payment_amount",
            "payment_day_of_month",
            "mandate_age_days",
            "previous_failure_count",
            "days_since_last_success",
            "rolling_failure_rate",
            "is_monday",
            "amount_zscore",
            "days_since_failure",
            "merchant_failure_rate",
            "customer_lifetime_payments",
            "customer_lifetime_value",
            "is_new_mandate",
            "has_multiple_previous_failures",
            "is_low_balance",
        ]

    @staticmethod
    def _prepare_base_frame(df: pd.DataFrame) -> pd.DataFrame:
        """Return a sorted copy with parsed dates and a binary target."""
        required = {
            "payment_id",
            "merchant_id",
            "customer_id",
            "payment_amount",
            "payment_date",
            "day_of_week",
            "mandate_age_days",
            "previous_failure_count",
            "estimated_balance_band",
            "payment_status",
        }
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        prepared = df.copy()
        prepared["payment_date"] = pd.to_datetime(prepared["payment_date"], errors="coerce")
        prepared = prepared.sort_values(["customer_id", "payment_date", "payment_id"]).reset_index(drop=True)
        prepared[config.TARGET_BINARY_COLUMN] = (
            prepared[config.TARGET_COLUMN].astype(str).str.lower().eq("failed").astype(int)
        )
        prepared["log_payment_amount"] = np.log1p(prepared["payment_amount"].clip(lower=0))
        return prepared

    def compute_rolling_failure_rate(
        self,
        df: pd.DataFrame,
        customer_id: str = "customer_id",
        window: int = 5,
    ) -> pd.DataFrame:
        """Add customer's previous ``window`` payment failure rate.

        The current payment is shifted out before rolling, which avoids target
        leakage. Customers with no previous payments receive 0.
        """
        featured = self._prepare_base_frame(df) if config.TARGET_BINARY_COLUMN not in df.columns else df.copy()
        featured = featured.sort_values([customer_id, "payment_date", "payment_id"]).reset_index(drop=True)

        shifted_failures = featured.groupby(customer_id)[config.TARGET_BINARY_COLUMN].shift(1)
        featured["rolling_failure_rate"] = (
            shifted_failures.groupby(featured[customer_id])
            .rolling(window=window, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
            .fillna(0)
        )
        return featured

    def compute_merchant_risk_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add historical merchant failure rate prior to each payment.

        Uses expanding historical outcomes per merchant with a global fallback
        for the first observed payment of each merchant.
        """
        featured = self._prepare_base_frame(df) if config.TARGET_BINARY_COLUMN not in df.columns else df.copy()
        featured = featured.sort_values(["merchant_id", "payment_date", "payment_id"]).reset_index(drop=True)

        merchant_history_sum = featured.groupby("merchant_id")[config.TARGET_BINARY_COLUMN].cumsum() - featured[config.TARGET_BINARY_COLUMN]
        merchant_history_count = featured.groupby("merchant_id").cumcount()
        featured["merchant_failure_rate"] = (
            merchant_history_sum / merchant_history_count.replace(0, np.nan)
        ).fillna(0.0)
        featured["merchant_risk_score"] = featured["merchant_failure_rate"] * np.log1p(
            featured.groupby("merchant_id").cumcount() + 1
        )
        return featured

    def compute_customer_lifetime_value(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add historical customer lifetime count and value features.

        These values are calculated only from payments that occurred before the
        current row for the same customer. This makes the features safe for
        production scoring and avoids future-data leakage during model training.
        """
        featured = self._prepare_base_frame(df) if config.TARGET_BINARY_COLUMN not in df.columns else df.copy()
        featured = featured.sort_values(["customer_id", "payment_date", "payment_id"]).reset_index(drop=True)
        featured["customer_lifetime_payments"] = featured.groupby("customer_id").cumcount()
        featured["customer_lifetime_value"] = (
            featured.groupby("customer_id")["payment_amount"].cumsum() - featured["payment_amount"]
        ).fillna(0)
        return featured

    @staticmethod
    def _add_amount_zscore(df: pd.DataFrame) -> pd.DataFrame:
        """Add historical customer-level amount z-score.

        The z-score compares the current payment amount with the same customer's
        previous payments only. First or second customer payments are assigned 0
        because there is not enough prior history to estimate a stable standard
        deviation.
        """
        featured = df.copy().sort_values(["customer_id", "payment_date", "payment_id"]).reset_index(drop=True)
        amounts = featured["payment_amount"].astype(float)
        prior_count = featured.groupby("customer_id").cumcount()
        prior_sum = featured.groupby("customer_id")["payment_amount"].cumsum() - amounts
        prior_sq_sum = featured.groupby("customer_id")["payment_amount"].transform(lambda s: (s.astype(float) ** 2).cumsum()) - (amounts ** 2)

        prior_mean = prior_sum / prior_count.replace(0, np.nan)
        prior_variance = (prior_sq_sum / prior_count.replace(0, np.nan)) - (prior_mean ** 2)
        prior_std = np.sqrt(prior_variance.clip(lower=0))

        featured["amount_zscore"] = ((amounts - prior_mean) / prior_std.replace(0, np.nan)).replace(
            [np.inf, -np.inf], 0
        ).fillna(0)
        return featured

    @staticmethod
    def _add_days_since_failure(df: pd.DataFrame) -> pd.DataFrame:
        """Add days since each customer's previous failed payment."""
        featured = df.copy().sort_values(["customer_id", "payment_date", "payment_id"]).reset_index(drop=True)

        previous_failed_date = featured["payment_date"].where(featured[config.TARGET_BINARY_COLUMN].eq(1))
        featured["previous_failed_date"] = previous_failed_date.groupby(featured["customer_id"]).ffill().groupby(
            featured["customer_id"]
        ).shift(1)
        featured["days_since_failure"] = (
            featured["payment_date"] - featured["previous_failed_date"]
        ).dt.days.fillna(999).clip(lower=0)
        featured = featured.drop(columns=["previous_failed_date"])
        return featured

    @staticmethod
    def _add_mandate_age_band(df: pd.DataFrame) -> pd.DataFrame:
        """Add categorical mandate age band: new, young, mature, established."""
        featured = df.copy()
        featured["mandate_age_band"] = pd.cut(
            featured["mandate_age_days"],
            bins=[-1, 30, 90, 365, np.inf],
            labels=["new", "young", "mature", "established"],
        ).astype("object")
        return featured

    def _add_business_flags(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add simple binary business indicators."""
        featured = df.copy()
        featured["is_monday"] = featured["day_of_week"].eq("Monday").astype(int)
        featured["is_new_mandate"] = featured["mandate_age_days"].lt(30).astype(int)
        featured["has_multiple_previous_failures"] = featured["previous_failure_count"].gt(2).astype(int)
        featured["is_low_balance"] = featured["estimated_balance_band"].eq("low").astype(int)
        return featured

    def encode_categorical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """One-hot encode categorical features and keep numeric modelling columns."""
        featured = df.copy()
        available_categoricals = [col for col in self.categorical_columns_ if col in featured.columns]
        available_numerics = [col for col in self.base_numeric_features_ if col in featured.columns]

        encoded = pd.get_dummies(
            featured[available_numerics + available_categoricals + [config.TARGET_BINARY_COLUMN]],
            columns=available_categoricals,
            drop_first=False,
            dtype=int,
        )
        encoded = encoded.replace([np.inf, -np.inf], np.nan).fillna(0)
        self.feature_names_ = [col for col in encoded.columns if col != config.TARGET_BINARY_COLUMN]
        return encoded

    def build_feature_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run all feature engineering steps and return a model-ready DataFrame."""
        featured = self._prepare_base_frame(df)
        featured = self.compute_rolling_failure_rate(featured, window=5)
        featured = self.compute_merchant_risk_score(featured)
        featured = self.compute_customer_lifetime_value(featured)
        featured = self._add_mandate_age_band(featured)
        featured = self._add_amount_zscore(featured)
        featured = self._add_days_since_failure(featured)
        featured = self._add_business_flags(featured)
        encoded = self.encode_categorical_features(featured)
        return encoded

    def get_feature_names(self) -> list[str]:
        """Return final model feature names from the latest build."""
        return list(self.feature_names_)


# -----------------------------------------------------------------------------
# Backward-compatible helper functions used by earlier project files/tests
# -----------------------------------------------------------------------------

def add_business_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add interpretable business features before modelling."""
    store = FeatureStore()
    featured = store._prepare_base_frame(df)
    featured = store._add_mandate_age_band(featured)
    featured = store._add_amount_zscore(featured)
    featured = store._add_days_since_failure(featured)
    featured = store._add_business_flags(featured)
    featured["is_monday_collection"] = featured["is_monday"]
    featured["is_high_amount"] = featured["payment_amount"].gt(500).astype(int)
    featured["is_inactive_customer"] = featured["days_since_last_success"].gt(60).astype(int)
    featured["payment_month"] = featured["payment_date"].dt.month
    featured["payment_quarter"] = featured["payment_date"].dt.quarter
    return featured


def build_model_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Build a one-hot encoded model matrix and target vector."""
    store = FeatureStore()
    model_df = store.build_feature_matrix(df)
    X = model_df.drop(columns=[config.TARGET_BINARY_COLUMN])
    y = model_df[config.TARGET_BINARY_COLUMN].astype(int)
    return X, y


def merchant_performance_features(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate merchant-level payment performance for analytics."""
    featured = add_business_features(df)
    merchant_summary = (
        featured.groupby("merchant_id")
        .agg(
            total_payments=("payment_id", "count"),
            failed_payments=(config.TARGET_BINARY_COLUMN, "sum"),
            avg_payment_amount=("payment_amount", "mean"),
            avg_previous_failures=("previous_failure_count", "mean"),
            low_balance_share=("is_low_balance", "mean"),
        )
        .reset_index()
    )
    merchant_summary["failure_rate"] = merchant_summary["failed_payments"] / merchant_summary["total_payments"]
    return merchant_summary.sort_values("failure_rate", ascending=False)
