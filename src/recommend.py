"""Business recommendations for reducing payment failures."""

from __future__ import annotations

import pandas as pd

from src import config


def risk_label(probability: float) -> str:
    """Convert failure probability into a business-friendly risk label."""
    if probability >= config.HIGH_RISK_THRESHOLD:
        return config.RISK_LABELS["critical"]
    if probability >= config.MEDIUM_RISK_THRESHOLD:
        return config.RISK_LABELS["high"]
    if probability >= config.LOW_RISK_THRESHOLD:
        return config.RISK_LABELS["medium"]
    return config.RISK_LABELS["low"]


def recommend_action(row: pd.Series | dict) -> str:
    """Return a practical collection-success recommendation for one payment."""
    value = dict(row)

    if value.get("previous_failure_count", 0) > config.HIGH_FAILURE_COUNT_THRESHOLD:
        return "Pause automatic retries, trigger customer outreach, and verify payment details."

    if value.get("estimated_balance_band") == config.LOW_BALANCE_BAND:
        return "Send pre-collection reminder and retry after balance improvement window."

    if value.get("mandate_age_days", 9999) < config.NEW_MANDATE_DAYS_THRESHOLD:
        return "Verify mandate setup and send first-payment confirmation before collection."

    if value.get("day_of_week") == config.MONDAY:
        return "Consider shifting retry to Tuesday or Wednesday to reduce Monday failure pressure."

    if value.get("days_since_last_success", 0) > 60:
        return "Run customer re-engagement check before the next debit attempt."

    return "Proceed with normal collection monitoring."


def add_recommendations(df: pd.DataFrame, probability_column: str = "failure_probability") -> pd.DataFrame:
    """Attach risk labels and recommended actions to a dataframe."""
    output = df.copy()
    if probability_column in output.columns:
        output["risk_label"] = output[probability_column].apply(risk_label)
    output["recommended_action"] = output.apply(recommend_action, axis=1)
    return output


def build_retry_recommendations(
    df: pd.DataFrame,
    probability_column: str = "failure_probability",
    threshold: float = 0.30,
    start_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Create a future-dated retry schedule for failed or high-risk payments.

    Parameters
    ----------
    df:
        Payment-level data. It can include ``failure_probability`` from the ML
        model or ``risk_score`` on a 0-100 scale from the dashboard.
    probability_column:
        Column containing predicted failure probability. If it is missing and a
        ``risk_score`` column exists, risk score is converted from 0-100 to 0-1.
    threshold:
        Minimum failure probability that should enter the retry schedule.
    start_date:
        Optional anchor date for testing. Defaults to today.

    Returns
    -------
    pandas.DataFrame
        Prioritised retry recommendations with future retry dates.
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "payment_id",
                "payment_amount",
                "recommended_retry_date",
                "recommended_retry_day_of_week",
                "expected_success_probability",
                "priority_rank",
                "expected_recovery_amount",
            ]
        )

    output = df.copy()
    if probability_column not in output.columns:
        if "risk_score" in output.columns:
            output[probability_column] = output["risk_score"].astype(float) / 100.0
        else:
            output[probability_column] = output.apply(
                lambda row: 0.65 if risk_label(float(row.get("previous_failure_count", 0)) / 5.0) in {"High risk", "Critical risk"} else 0.30,
                axis=1,
            )

    output[probability_column] = output[probability_column].astype(float).clip(0, 1)
    output = output.loc[output[probability_column] >= threshold].copy()
    if output.empty:
        return pd.DataFrame(
            columns=[
                "payment_id",
                "payment_amount",
                "recommended_retry_date",
                "recommended_retry_day_of_week",
                "expected_success_probability",
                "priority_rank",
                "expected_recovery_amount",
            ]
        )

    anchor = pd.Timestamp(start_date).normalize() if start_date is not None else pd.Timestamp.today().normalize()
    retry_dates: list[pd.Timestamp] = []
    for idx, row in output.reset_index(drop=True).iterrows():
        # Stagger recommendations over the next few days and avoid Monday, where
        # this project data intentionally has the highest failure risk.
        candidate = anchor + pd.Timedelta(days=1 + (idx % 5))
        while candidate.day_name() in {"Monday", "Saturday", "Sunday"}:
            candidate += pd.Timedelta(days=1)
        retry_dates.append(candidate)

    output = output.reset_index(drop=True)
    output["recommended_retry_date"] = retry_dates
    output["recommended_retry_day_of_week"] = output["recommended_retry_date"].dt.day_name()
    output["expected_success_probability"] = (1 - output[probability_column]).clip(0.05, 0.95)
    output["expected_recovery_amount"] = output["payment_amount"].astype(float) * output["expected_success_probability"]
    output["priority_score"] = output["payment_amount"].astype(float) * output[probability_column]
    output = output.sort_values("priority_score", ascending=False).reset_index(drop=True)
    output["priority_rank"] = range(1, len(output) + 1)

    return output[
        [
            "payment_id",
            "payment_amount",
            "recommended_retry_date",
            "recommended_retry_day_of_week",
            "expected_success_probability",
            "priority_rank",
            "expected_recovery_amount",
        ]
    ]
