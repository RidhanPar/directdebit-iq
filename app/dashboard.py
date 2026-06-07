"""DirectDebit IQ — Streamlit payment intelligence dashboard.

Run from the project root:
    streamlit run app/dashboard.py

The dashboard is intentionally portfolio-ready: it combines executive payment
KPIs, predictive scoring for upcoming payments, retry scheduling, explainability,
and SQL analytics in one clean product-style app.
"""

from __future__ import annotations

import io
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -----------------------------------------------------------------------------
# Project imports
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src import config  # noqa: E402
from src.feature_store import FeatureStore  # noqa: E402
from src.sql_runner import SQLAnalytics  # noqa: E402

# -----------------------------------------------------------------------------
# Page config and constants
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="DirectDebit IQ",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

MODEL_PATH = PROJECT_ROOT / "models" / "failure_predictor.pkl"
LEGACY_MODEL_PATH = PROJECT_ROOT / "models" / "fraud_model.pkl"
JOBLIB_MODEL_PATH = PROJECT_ROOT / "models" / "payment_failure_model.joblib"
RAW_PAYMENTS_PATH = PROJECT_ROOT / "data" / "raw" / "payments.csv"
DB_PATH = PROJECT_ROOT / "data" / "payments.db"
SQL_DIR = PROJECT_ROOT / "sql"
BUSINESS_THRESHOLD = 0.30
HIGH_RISK_THRESHOLD = 0.50
CRITICAL_RISK_THRESHOLD = 0.70
RECOVERY_RATE_ESTIMATE = 0.62
COST_RECOVERY_MULTIPLIER = 3.0
DEMO_ROW_COUNT = 5000
GITHUB_REPO_URL = "https://github.com/RidhanPar/directdebit-iq"
LIVE_DEMO_URL = "https://directdebit-iq.streamlit.app/"
LINKEDIN_URL = "https://www.linkedin.com/in/ridhanparvendhan/"
AUTHOR_NAME = "Ridhan Parvendhan"

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
RISK_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
RISK_COLORS = {
    "LOW": "#16a34a",
    "MEDIUM": "#ca8a04",
    "HIGH": "#ea580c",
    "CRITICAL": "#dc2626",
}
BRAND_BLUE = "#0b5fff"
BRAND_GREEN = "#00a878"
BRAND_NAVY = "#0f172a"

# -----------------------------------------------------------------------------
# CSS styling
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
        .main .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2rem;
            max-width: 1400px;
        }
        .app-title {
            font-size: 2.15rem;
            font-weight: 800;
            color: #0f172a;
            letter-spacing: -0.03em;
            margin-bottom: 0.1rem;
        }
        .app-subtitle {
            color: #64748b;
            font-size: 1rem;
            margin-bottom: 1.25rem;
        }
        .hero-panel {
            background: linear-gradient(135deg, #071a3d 0%, #0b5fff 58%, #00a878 130%);
            border-radius: 24px; padding: 28px 30px; color: white;
            box-shadow: 0 20px 48px rgba(11, 95, 255, 0.20); margin-bottom: 1.35rem;
        }
        .hero-kicker { font-size: 0.78rem; font-weight: 800; letter-spacing: 0.14em; opacity: 0.78; }
        .hero-title { font-size: 2.35rem; font-weight: 850; letter-spacing: -0.04em; margin: 0.35rem 0; }
        .hero-copy { font-size: 1rem; opacity: 0.9; max-width: 820px; line-height: 1.55; }
        .trust-strip { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 1rem; }
        .trust-chip {
            border: 1px solid rgba(255,255,255,0.28); background: rgba(255,255,255,0.12);
            border-radius: 999px; padding: 6px 11px; font-size: 0.78rem; font-weight: 750;
        }
        .metric-card {
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
            border: 1px solid #e2e8f0;
            border-radius: 18px;
            padding: 18px 18px 16px 18px;
            box-shadow: 0 10px 26px rgba(15, 23, 42, 0.06);
            min-height: 118px;
        }
        .metric-label {
            color: #64748b;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        .metric-value {
            color: #0f172a;
            font-size: 1.8rem;
            font-weight: 850;
            letter-spacing: -0.03em;
            line-height: 1.1;
        }
        .metric-help {
            color: #64748b;
            font-size: 0.8rem;
            margin-top: 0.55rem;
        }
        .insight-card {
            border-radius: 16px;
            border: 1px solid #e2e8f0;
            background: #ffffff;
            padding: 16px 18px;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.05);
            margin-bottom: 12px;
        }
        .insight-title {
            color: #0f172a;
            font-weight: 800;
            font-size: 1rem;
            margin-bottom: 0.25rem;
        }
        .insight-body {
            color: #475569;
            font-size: 0.92rem;
            line-height: 1.45;
        }
        .action-box {
            background: linear-gradient(90deg, rgba(11,95,255,0.10), rgba(0,168,120,0.12));
            border: 1px solid rgba(11,95,255,0.22);
            border-radius: 18px;
            padding: 18px;
            color: #0f172a;
            margin-top: 10px;
        }
        .risk-pill {
            display: inline-block;
            color: white;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 0.78rem;
            font-weight: 800;
        }
        div[data-testid="stSidebar"] {
            background: #f8fafc;
            border-right: 1px solid #e2e8f0;
        }
        .calendar-cell {
            min-height: 74px;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 8px;
            background: #ffffff;
            font-size: 0.82rem;
        }
        .calendar-day {
            color: #0f172a;
            font-weight: 800;
        }
        .calendar-event {
            color: #0b5fff;
            font-weight: 700;
            margin-top: 4px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Data loading and transformation helpers
# -----------------------------------------------------------------------------

def generate_demo_payments(n: int = DEMO_ROW_COUNT, seed: int = 42) -> pd.DataFrame:
    """Generate built-in demo payments for Streamlit Cloud when data files are absent.

    Streamlit Cloud deployments often start from a clean Git repository where
    large generated CSV/SQLite/model files are intentionally excluded. This
    deterministic sample keeps the live demo fully functional for recruiters
    without requiring any upload or setup step.
    """
    rng = np.random.default_rng(seed)
    today = pd.Timestamp.today().normalize()
    start_date = today - pd.Timedelta(days=730)

    merchants = np.array([f"M{i:03d}" for i in range(1, 201)])
    customers = np.array([f"C{i:04d}" for i in range(1, 5001)])
    dates = start_date + pd.to_timedelta(rng.integers(0, 731, size=n), unit="D")

    amounts = rng.lognormal(mean=np.log(85), sigma=0.75, size=n).clip(10, 500)
    outlier_mask = rng.random(n) < 0.025
    amounts[outlier_mask] = rng.uniform(500, 2500, size=outlier_mask.sum())

    mandate_age = rng.gamma(shape=2.2, scale=170, size=n).astype(int).clip(0, 1825)
    prev_failures = rng.choice([0, 1, 2, 3, 4, 5], size=n, p=[0.68, 0.17, 0.08, 0.04, 0.02, 0.01])
    balance_band = rng.choice(["low", "medium", "high"], size=n, p=[0.22, 0.55, 0.23])
    day_names = pd.Series(dates).dt.day_name().to_numpy()

    failure_probability = (
        0.075
        + 0.055 * prev_failures
        + 0.085 * (mandate_age < 30)
        + 0.045 * (day_names == "Monday")
        + 0.095 * (balance_band == "low")
        + 0.025 * (amounts > 500)
    ).clip(0.03, 0.78)
    failed = rng.random(n) < failure_probability

    df = pd.DataFrame(
        {
            "payment_id": [f"DEMO-{i + 1:06d}" for i in range(n)],
            "merchant_id": rng.choice(merchants, size=n),
            "customer_id": rng.choice(customers, size=n),
            "payment_amount": amounts.round(2),
            "currency": rng.choice(["GBP", "EUR", "USD"], size=n, p=[0.70, 0.20, 0.10]),
            "payment_date": dates,
            "payment_day_of_month": pd.Series(dates).dt.day.clip(upper=28),
            "day_of_week": day_names,
            "mandate_age_days": mandate_age,
            "previous_failure_count": prev_failures,
            "bank_country": rng.choice(["GB", "FR", "DE", "IE", "AU", "US"], size=n, p=[0.50, 0.14, 0.13, 0.09, 0.07, 0.07]),
            "bank_type": rng.choice(["high_street", "challenger", "credit_union"], size=n, p=[0.62, 0.28, 0.10]),
            "estimated_balance_band": balance_band,
            "days_since_last_success": rng.integers(0, 91, size=n),
            "payment_type": rng.choice(["recurring", "one_off"], size=n, p=[0.82, 0.18]),
            "payment_status": np.where(failed, "failed", "success"),
        }
    )
    df["is_failed"] = df["payment_status"].eq("failed").astype(int)
    df["is_success"] = df["payment_status"].eq("success").astype(int)
    df["failed_amount"] = np.where(df["is_failed"].eq(1), df["payment_amount"], 0.0)
    df["year_month"] = pd.to_datetime(df["payment_date"]).dt.to_period("M").astype(str)
    df.attrs["source"] = "demo"
    return df

@st.cache_data(show_spinner=False)
def load_payments() -> pd.DataFrame:
    """Load generated payments, or use built-in demo data if files are absent."""
    if RAW_PAYMENTS_PATH.exists():
        try:
            df = pd.read_csv(RAW_PAYMENTS_PATH)
            source = "file"
        except Exception:
            df = generate_demo_payments()
            source = "demo"
    else:
        df = generate_demo_payments()
        source = "demo"

    df["payment_date"] = pd.to_datetime(df["payment_date"], errors="coerce")
    df["payment_amount"] = pd.to_numeric(df["payment_amount"], errors="coerce").fillna(0)
    df["payment_status"] = df["payment_status"].fillna("success").astype(str).str.lower()
    df["is_failed"] = df["payment_status"].eq("failed").astype(int)
    df["is_success"] = df["payment_status"].eq("success").astype(int)
    df["failed_amount"] = np.where(df["is_failed"].eq(1), df["payment_amount"], 0.0)
    df["year_month"] = df["payment_date"].dt.to_period("M").astype(str)
    df.attrs["source"] = source
    return df


@st.cache_resource(show_spinner=False)
def load_model_artifact() -> Dict[str, Any] | None:
    """Load a trained model artifact if available; otherwise use safe fallback scoring.

    The GitHub repository intentionally ignores heavy generated model files.
    On Streamlit Cloud, the app therefore uses the transparent heuristic scorer
    until a model artifact is generated locally and committed through a release
    or loaded from external storage.
    """
    for candidate_path in [MODEL_PATH, LEGACY_MODEL_PATH, JOBLIB_MODEL_PATH]:
        if candidate_path.exists():
            try:
                artifact = joblib.load(candidate_path)
                if isinstance(artifact, dict) and "model" in artifact:
                    return artifact
            except Exception:
                continue
    return None


@st.cache_data(show_spinner=False)
def run_sql_analyses() -> Dict[str, pd.DataFrame]:
    """Run SQLite analyses when the database exists.

    If Streamlit Cloud is running without generated data/payments.db, callers
    fall back to pandas-based demo analyses instead of crashing.
    """
    if not DB_PATH.exists() or not SQL_DIR.exists():
        return {}
    try:
        analytics = SQLAnalytics(db_path=DB_PATH, sql_dir=SQL_DIR)
        try:
            return analytics.run_all_analyses()
        finally:
            analytics.close()
    except Exception:
        return {}


def build_sql_fallback_analyses(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Build SQL-equivalent analytics from the active dataframe for demo mode."""
    working = df.copy()
    working["mandate_age_band"] = pd.cut(
        working["mandate_age_days"],
        bins=[-1, 30, 90, 365, np.inf],
        labels=["0-30 days", "31-90", "91-365", "365+"],
    ).astype(str)

    monthly = (
        working.groupby("year_month")
        .agg(
            total_payments=("payment_id", "count"),
            successful_payments=("is_success", "sum"),
            failed_payments=("is_failed", "sum"),
        )
        .reset_index()
        .sort_values("year_month")
    )
    monthly["success_rate_pct"] = (100 * monthly["successful_payments"] / monthly["total_payments"]).round(2)
    monthly["vs_previous_month_change"] = monthly["success_rate_pct"].diff().fillna(0).round(2)

    cohort = (
        working.groupby(["merchant_id", "mandate_age_band"], observed=False)
        .agg(payment_count=("payment_id", "count"), success_rate=("is_success", lambda x: round(x.mean() * 100, 2)))
        .reset_index()
    )

    customers = (
        working.groupby("customer_id")
        .agg(
            total_payments=("payment_id", "count"),
            failure_count=("is_failed", "sum"),
            total_amount_failed=("failed_amount", "sum"),
        )
        .query("total_payments >= 3")
        .reset_index()
    )
    customers["failure_rate"] = customers["failure_count"] / customers["total_payments"]
    customers["risk_score"] = customers["failure_rate"] * np.log1p(customers["failure_count"])
    customers["risk_category"] = pd.cut(
        customers["risk_score"],
        bins=[-0.01, 0.10, 0.25, 0.50, np.inf],
        labels=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    ).astype(str)
    customers = customers.sort_values("risk_score", ascending=False)

    bank_base = (
        working.groupby(["bank_country", "bank_type"])
        .agg(
            total_payments=("payment_id", "count"),
            success_rate=("is_success", lambda x: round(x.mean() * 100, 2)),
            avg_payment_amount=("payment_amount", "mean"),
        )
        .reset_index()
    )
    failure_days = (
        working[working["is_failed"].eq(1)]
        .groupby(["bank_country", "bank_type", "day_of_week"])
        .size()
        .reset_index(name="failure_count")
        .sort_values(["bank_country", "bank_type", "failure_count"], ascending=[True, True, False])
    )
    failure_days["rank"] = failure_days.groupby(["bank_country", "bank_type"])["failure_count"].rank(method="first", ascending=False)
    top_days = failure_days[failure_days["rank"].eq(1)][["bank_country", "bank_type", "day_of_week"]].rename(
        columns={"day_of_week": "most_common_failure_day"}
    )
    bank = bank_base.merge(top_days, on=["bank_country", "bank_type"], how="left")
    bank["most_common_failure_day"] = bank["most_common_failure_day"].fillna("No failures")

    return {
        "monthly_success_rates": monthly,
        "merchant_cohort_analysis": cohort,
        "high_risk_customers": customers,
        "bank_country_analysis": bank,
    }


def get_sql_results(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Return SQL outputs from SQLite or dataframe fallback.

    First try the SQLite-backed SQL runner. If the database is missing
    or SQL execution fails, use pandas fallback analyses so Streamlit Cloud
    demo mode still works for recruiters.
    """
    results = run_sql_analyses()
    if results:
        return results
    return build_sql_fallback_analyses(df)


def pct(series: pd.Series) -> float:
    """Return mean percentage for a 0/1 series."""
    if len(series) == 0:
        return 0.0
    return float(series.mean() * 100)


def format_currency(value: float, prefix: str = "£") -> str:
    """Human-friendly currency display."""
    return f"{prefix}{value:,.0f}"


def render_header(subtitle: str | None = None) -> None:
    """Render the product-style dashboard header."""
    st.markdown(
        '<div class="app-title">DirectDebit IQ — Payment Intelligence Platform</div>',
        unsafe_allow_html=True,
    )


def render_product_hero() -> None:
    """Render the executive-facing product introduction."""
    st.markdown(
        """
        <div class="hero-panel">
            <div class="hero-kicker">PAYMENT OPERATIONS DECISIONING</div>
            <div class="hero-title">Catch likely failures before collection day.</div>
            <div class="hero-copy">
                DirectDebit IQ combines payment-success analytics, explainable risk scoring,
                and prioritised retry recommendations in one review-ready workflow.
            </div>
            <div class="trust-strip">
                <span class="trust-chip">Synthetic-data prototype</span>
                <span class="trust-chip">Out-of-time model validation</span>
                <span class="trust-chip">Leakage-aware historical features</span>
                <span class="trust-chip">Human review before action</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="app-subtitle">{subtitle or "Predict failures, prioritise retries, and explain payment risk."}</div>',
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, help_text: str = "") -> str:
    """Return HTML for a custom KPI card."""
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-help">{help_text}</div>
    </div>
    """


def risk_category(score: float) -> str:
    """Map a 0-100 risk score into business risk categories."""
    if score >= 70:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"


def risk_style(value: str) -> str:
    """Pandas Styler helper for risk category cells."""
    color = RISK_COLORS.get(str(value), "#64748b")
    return f"background-color: {color}; color: white; font-weight: 800; text-align: center;"


def ensure_scoring_columns(upcoming: pd.DataFrame) -> pd.DataFrame:
    """Fill missing columns so uploaded scheduled payments can be scored safely."""
    df = upcoming.copy()
    n = len(df)
    today = pd.Timestamp.today().normalize()

    defaults: Dict[str, Any] = {
        "payment_id": [f"UPCOMING-{i + 1:05d}" for i in range(n)],
        "merchant_id": "M001",
        "customer_id": [f"NEW-C{i + 1:04d}" for i in range(n)],
        "payment_amount": 100.0,
        "currency": "GBP",
        "payment_date": today,
        "mandate_age_days": 90,
        "previous_failure_count": 0,
        "bank_country": "GB",
        "bank_type": "high_street",
        "estimated_balance_band": "medium",
        "days_since_last_success": 30,
        "payment_type": "recurring",
        "payment_status": "success",
    }

    for column, default in defaults.items():
        if column not in df.columns:
            df[column] = default

    df["payment_date"] = pd.to_datetime(df["payment_date"], errors="coerce").fillna(today)
    df["payment_amount"] = pd.to_numeric(df["payment_amount"], errors="coerce").fillna(100.0)
    df["mandate_age_days"] = pd.to_numeric(df["mandate_age_days"], errors="coerce").fillna(90).clip(lower=0)
    df["previous_failure_count"] = pd.to_numeric(
        df["previous_failure_count"], errors="coerce"
    ).fillna(0).clip(lower=0)
    df["days_since_last_success"] = pd.to_numeric(
        df["days_since_last_success"], errors="coerce"
    ).fillna(30).clip(lower=0)

    df["payment_day_of_month"] = df["payment_date"].dt.day.clip(upper=28)
    df["day_of_week"] = df["payment_date"].dt.day_name()
    df["payment_status"] = df["payment_status"].fillna("success")

    # Normalize categorical values to the project vocabulary where possible.
    replacements = {
        "currency": "GBP",
        "bank_country": "GB",
        "bank_type": "high_street",
        "estimated_balance_band": "medium",
        "payment_type": "recurring",
    }
    for column, default in replacements.items():
        df[column] = df[column].fillna(default).astype(str)

    return df


def build_model_features_with_history(
    scoring_rows: pd.DataFrame,
    history_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Build FeatureStore features for scoring rows using history as context.

    The model was trained on historical customer and merchant features. This
    helper temporarily appends uploaded scheduled payments to the historical
    dataset so features such as merchant_failure_rate and customer lifetime
    counts use realistic historical context. Only the uploaded rows are returned.
    """
    scoring = ensure_scoring_columns(scoring_rows)
    scoring["__is_scoring_row"] = 1

    history = history_df.copy()
    history["__is_scoring_row"] = 0

    required_columns = [
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
        "__is_scoring_row",
    ]

    combined = pd.concat(
        [history[required_columns], scoring[required_columns]],
        ignore_index=True,
    )

    store = FeatureStore()
    featured = store._prepare_base_frame(combined)  # Uses target only for historical feature context.
    featured = store.compute_rolling_failure_rate(featured, window=5)
    featured = store.compute_merchant_risk_score(featured)
    featured = store.compute_customer_lifetime_value(featured)
    featured = store._add_mandate_age_band(featured)
    featured = store._add_amount_zscore(featured)
    featured = store._add_days_since_failure(featured)
    featured = store._add_business_flags(featured)
    encoded = store.encode_categorical_features(featured)

    scoring_mask = featured["__is_scoring_row"].eq(1).to_numpy()
    return encoded.loc[scoring_mask].reset_index(drop=True), featured.loc[scoring_mask].reset_index(drop=True)


def heuristic_failure_probability(scoring_rows: pd.DataFrame, history_df: pd.DataFrame) -> np.ndarray:
    """Fallback scoring when no trained model is available."""
    df = ensure_scoring_columns(scoring_rows)
    merchant_rates = (
        history_df.groupby("merchant_id")["is_failed"].mean().rename("merchant_history_failure_rate")
    )
    df = df.merge(merchant_rates, on="merchant_id", how="left")
    df["merchant_history_failure_rate"] = df["merchant_history_failure_rate"].fillna(
        history_df["is_failed"].mean()
    )

    risk = (
        0.08
        + 0.06 * df["previous_failure_count"].clip(0, 5)
        + 0.10 * df["estimated_balance_band"].eq("low").astype(int)
        + 0.07 * df["mandate_age_days"].lt(30).astype(int)
        + 0.04 * df["day_of_week"].eq("Monday").astype(int)
        + 0.45 * df["merchant_history_failure_rate"]
        + 0.02 * df["payment_amount"].gt(500).astype(int)
    )
    return risk.clip(0.02, 0.92).to_numpy()


def score_payments(upcoming: pd.DataFrame, history_df: pd.DataFrame) -> pd.DataFrame:
    """Score upcoming payments with the trained model or fallback heuristic."""
    scoring = ensure_scoring_columns(upcoming)
    artifact = load_model_artifact()

    if artifact is not None:
        encoded, featured = build_model_features_with_history(scoring, history_df)
        X = encoded.drop(columns=[config.TARGET_BINARY_COLUMN], errors="ignore")
        X = X.reindex(columns=artifact["feature_columns"], fill_value=0)
        probabilities = artifact["model"].predict_proba(X)[:, 1]
        model_source = "XGBoost model"
        scoring["merchant_failure_rate"] = featured.get("merchant_failure_rate", pd.Series(0)).to_numpy()
        scoring["amount_zscore"] = featured.get("amount_zscore", pd.Series(0)).to_numpy()
        scoring["days_since_failure"] = featured.get("days_since_failure", pd.Series(999)).to_numpy()
    else:
        probabilities = heuristic_failure_probability(scoring, history_df)
        model_source = "business-rule fallback"
        scoring["merchant_failure_rate"] = scoring["merchant_id"].map(
            history_df.groupby("merchant_id")["is_failed"].mean()
        ).fillna(history_df["is_failed"].mean())
        scoring["amount_zscore"] = 0.0
        scoring["days_since_failure"] = 999

    scored = scoring.copy()
    scored["risk_probability"] = probabilities
    scored["risk_score"] = (probabilities * 100).round(1)
    scored["risk_level"] = scored["risk_score"].apply(risk_category)
    scored["expected_to_fail"] = np.where(scored["risk_probability"].ge(BUSINESS_THRESHOLD), "Yes", "No")
    scored["potential_revenue_at_risk"] = np.where(
        scored["expected_to_fail"].eq("Yes"), scored["payment_amount"], 0.0
    ).round(2)
    scored["model_source"] = model_source
    return scored


def make_template_csv() -> bytes:
    """Create a downloadable upcoming-payments CSV template."""
    template = pd.DataFrame(
        [
            {
                "payment_id": "UPCOMING-00001",
                "merchant_id": "M014",
                "customer_id": "C0042",
                "payment_amount": 129.99,
                "currency": "GBP",
                "payment_date": (pd.Timestamp.today().normalize() + pd.Timedelta(days=3)).date(),
                "mandate_age_days": 14,
                "previous_failure_count": 3,
                "bank_country": "GB",
                "bank_type": "challenger",
                "estimated_balance_band": "low",
                "days_since_last_success": 45,
                "payment_type": "recurring",
            },
            {
                "payment_id": "UPCOMING-00002",
                "merchant_id": "M087",
                "customer_id": "C3141",
                "payment_amount": 42.50,
                "currency": "GBP",
                "payment_date": (pd.Timestamp.today().normalize() + pd.Timedelta(days=5)).date(),
                "mandate_age_days": 420,
                "previous_failure_count": 0,
                "bank_country": "IE",
                "bank_type": "high_street",
                "estimated_balance_band": "medium",
                "days_since_last_success": 12,
                "payment_type": "recurring",
            },
        ]
    )
    return template.to_csv(index=False).encode("utf-8")


def build_retry_schedule(scored_df: pd.DataFrame) -> pd.DataFrame:
    """Create a retry recommendation table for high-risk payments."""
    if scored_df.empty:
        return pd.DataFrame()

    risk_df = scored_df[scored_df["risk_score"].ge(BUSINESS_THRESHOLD * 100)].copy()
    if risk_df.empty:
        return pd.DataFrame()

    # Prefer mid-week retries because Monday has the highest failure pattern in this dataset.
    preferred_days = {"Tuesday", "Wednesday", "Thursday"}

    retry_dates: List[pd.Timestamp] = []
    for raw_date in pd.to_datetime(risk_df["payment_date"], errors="coerce").fillna(pd.Timestamp.today()):
        candidate = raw_date + pd.Timedelta(days=2)
        attempts = 0
        while candidate.day_name() not in preferred_days and attempts < 7:
            candidate += pd.Timedelta(days=1)
            attempts += 1
        retry_dates.append(candidate.normalize())

    risk_df["recommended_retry_date"] = retry_dates
    risk_df["retry_day_of_week"] = risk_df["recommended_retry_date"].dt.day_name()
    risk_df["expected_success_probability"] = (
        0.96 - risk_df["risk_probability"] * 0.55
    ).clip(lower=0.35, upper=0.92)
    risk_df["priority_score"] = risk_df["payment_amount"] * risk_df["risk_probability"]
    risk_df = risk_df.sort_values("priority_score", ascending=False).reset_index(drop=True)
    risk_df["priority_rank"] = np.arange(1, len(risk_df) + 1)
    risk_df["expected_recovery_amount"] = (
        risk_df["payment_amount"] * risk_df["expected_success_probability"]
    ).round(2)
    return risk_df


def render_calendar_grid(schedule_df: pd.DataFrame) -> None:
    """Render a simple monthly retry calendar grid."""
    if schedule_df.empty:
        st.info("No retry dates to display yet.")
        return

    schedule = schedule_df.copy()
    schedule["recommended_retry_date"] = pd.to_datetime(schedule["recommended_retry_date"])
    first_retry_month = schedule["recommended_retry_date"].min().to_period("M").to_timestamp()
    month_start = first_retry_month.date()
    month_end = (first_retry_month + pd.offsets.MonthEnd(0)).date()
    st.caption(f"Calendar view for {month_start.strftime('%B %Y')}")

    daily = (
        schedule.groupby(schedule["recommended_retry_date"].dt.date)
        .agg(payments=("payment_id", "count"), amount=("payment_amount", "sum"))
        .reset_index()
    )
    events = {
        row["recommended_retry_date"]: (int(row["payments"]), float(row["amount"]))
        for _, row in daily.iterrows()
    }

    # Build a Monday-first calendar.
    start = month_start - timedelta(days=month_start.weekday())
    end = month_end + timedelta(days=(6 - month_end.weekday()))
    days = pd.date_range(start, end, freq="D").date

    for week_start in range(0, len(days), 7):
        cols = st.columns(7)
        for col, day_value in zip(cols, days[week_start : week_start + 7]):
            event = events.get(day_value)
            muted = "#94a3b8" if day_value.month != month_start.month else "#0f172a"
            event_html = ""
            if event:
                count, amount = event
                event_html = f'<div class="calendar-event">{count} retry · £{amount:,.0f}</div>'
            col.markdown(
                f"""
                <div class="calendar-cell">
                    <div class="calendar-day" style="color:{muted};">{day_value.day}</div>
                    {event_html}
                </div>
                """,
                unsafe_allow_html=True,
            )


def merchant_risk_table(df: pd.DataFrame) -> pd.DataFrame:
    """Return top merchant risk table for the executive page."""
    merchants = (
        df.groupby("merchant_id")
        .agg(
            total_payments=("payment_id", "count"),
            failed_payments=("is_failed", "sum"),
            failed_amount=("failed_amount", "sum"),
            avg_payment_amount=("payment_amount", "mean"),
        )
        .reset_index()
    )
    merchants["failure_rate_pct"] = 100 * merchants["failed_payments"] / merchants["total_payments"]
    merchants["risk_score"] = merchants["failure_rate_pct"] * np.log1p(merchants["failed_amount"])
    return merchants.sort_values("risk_score", ascending=False).head(5)


def build_failure_reasons(row: pd.Series) -> List[Tuple[str, str]]:
    """Create plain-English reason cards for a selected payment."""
    reasons: List[Tuple[str, str]] = []

    previous_failures = int(float(row.get("previous_failure_count", 0)))
    mandate_age = int(float(row.get("mandate_age_days", 0)))
    amount_z = float(row.get("amount_zscore", 0) or 0)
    balance_band = str(row.get("estimated_balance_band", "medium"))
    day_name = str(row.get("day_of_week", ""))
    merchant_rate = float(row.get("merchant_failure_rate", 0) or 0)

    if previous_failures >= 3:
        reasons.append(("⚠️ Repeated previous failures", f"Customer has failed {previous_failures} times before, so this payment should be monitored closely."))
    elif previous_failures > 0:
        reasons.append(("⚠️ Some failure history", f"Customer has {previous_failures} previous failed payment(s), increasing retry risk."))
    else:
        reasons.append(("✅ Clean payment history", "Customer has no previous failures in the available payment history."))

    if mandate_age < 30:
        reasons.append(("⚠️ New mandate", f"Mandate is only {mandate_age} days old — new mandates fail more often."))
    elif mandate_age < 90:
        reasons.append(("⚠️ Young mandate", f"Mandate is {mandate_age} days old, so it still has limited successful collection history."))
    else:
        reasons.append(("✅ Established mandate", f"Mandate is {mandate_age} days old, which lowers operational uncertainty."))

    if balance_band == "low":
        reasons.append(("⚠️ Low balance band", "Customer is in the low estimated balance band, which is one of the strongest business risk signals."))
    elif abs(amount_z) <= 1:
        reasons.append(("✅ Normal payment amount", "Payment amount is normal for this customer based on their historical amount pattern."))
    else:
        reasons.append(("⚠️ Unusual amount", f"Payment amount is unusual for this customer with an amount z-score of {amount_z:.1f}."))

    if day_name == "Monday":
        reasons.append(("⚠️ Monday collection", "Monday has the weakest payment success pattern in this dataset."))

    if merchant_rate >= 0.18:
        reasons.append(("⚠️ Merchant risk pattern", f"This merchant has a historical failure rate of {merchant_rate:.1%}."))

    return reasons[:3]


def recommended_action(row: pd.Series) -> str:
    """Return a recommended action for a scored payment."""
    score = float(row.get("risk_score", 0))
    if score >= 70:
        return "Prioritise customer outreach before collection, verify mandate details, and schedule a retry away from Monday."
    if score >= 50:
        return "Flag for proactive reminder and retry scheduling. Monitor this payment before the next collection run."
    if score >= 30:
        return "Keep in the watchlist and use automated reminder messaging before collection."
    return "Proceed normally. No manual intervention needed unless the customer profile changes."


def plot_shap_or_proxy(row: pd.Series, history_df: pd.DataFrame) -> go.Figure:
    """Create a SHAP-style waterfall chart for one selected payment.

    If SHAP is installed and the XGBoost model is available, this uses TreeSHAP.
    If not, it falls back to a transparent business-rule contribution chart.
    """
    artifact = load_model_artifact()
    one_row = pd.DataFrame([row.to_dict()])

    if artifact is not None:
        try:
            import shap  # type: ignore

            encoded, _ = build_model_features_with_history(one_row, history_df)
            X = encoded.drop(columns=[config.TARGET_BINARY_COLUMN], errors="ignore")
            X = X.reindex(columns=artifact["feature_columns"], fill_value=0)
            explainer = shap.TreeExplainer(artifact["model"])
            shap_values = explainer.shap_values(X)
            if isinstance(shap_values, list):
                values = np.asarray(shap_values[-1][0])
            else:
                values = np.asarray(shap_values[0])

            base_value = explainer.expected_value
            if isinstance(base_value, (list, np.ndarray)):
                base_value = float(np.asarray(base_value).ravel()[0])
            else:
                base_value = float(base_value)

            top_idx = np.argsort(np.abs(values))[-10:]
            top_features = X.columns[top_idx]
            top_values = values[top_idx]
            order = np.argsort(np.abs(top_values))[::-1]
            top_features = top_features[order]
            top_values = top_values[order]

            fig = go.Figure(
                go.Waterfall(
                    name="SHAP impact",
                    orientation="v",
                    measure=["relative"] * len(top_values) + ["total"],
                    x=list(top_features) + ["model output"],
                    y=list(top_values) + [base_value + float(values.sum())],
                    connector={"line": {"color": "#94a3b8"}},
                )
            )
            fig.update_layout(
                title="SHAP Waterfall — strongest model drivers",
                yaxis_title="Impact on model log-odds",
                xaxis_title="Feature",
                height=480,
                template="plotly_white",
                margin=dict(l=20, r=20, t=60, b=80),
            )
            return fig
        except Exception:
            pass

    # Transparent fallback if SHAP is unavailable.
    contributions = {
        "previous failures": 0.06 * float(row.get("previous_failure_count", 0)) * 100,
        "low balance": 10.0 if str(row.get("estimated_balance_band", "")) == "low" else -2.0,
        "new mandate": 7.0 if float(row.get("mandate_age_days", 999)) < 30 else -3.0,
        "Monday": 4.0 if str(row.get("day_of_week", "")) == "Monday" else -1.0,
        "merchant risk": 45.0 * float(row.get("merchant_failure_rate", 0)),
        "amount pattern": min(abs(float(row.get("amount_zscore", 0))) * 2.0, 8.0),
    }
    fig = go.Figure(
        go.Waterfall(
            name="Risk contribution",
            orientation="v",
            measure=["relative"] * len(contributions) + ["total"],
            x=list(contributions.keys()) + ["risk score"],
            y=list(contributions.values()) + [float(row.get("risk_score", 0))],
            connector={"line": {"color": "#94a3b8"}},
        )
    )
    fig.update_layout(
        title="SHAP-style Risk Waterfall — business-rule fallback",
        yaxis_title="Risk score contribution",
        height=480,
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=60),
    )
    return fig


def style_scored_table(df: pd.DataFrame):
    """Return styled dataframe for prediction results."""
    display = df.copy()
    display["Risk Score (0-100)"] = display["risk_score"].round(1)
    display["Risk Level"] = display["risk_level"]
    display["Potential revenue at risk"] = display["potential_revenue_at_risk"]
    cols = [
        "payment_id",
        "payment_amount",
        "customer_id",
        "Risk Score (0-100)",
        "Risk Level",
        "expected_to_fail",
        "Potential revenue at risk",
    ]
    styled = display[cols].rename(
        columns={
            "payment_id": "Payment ID",
            "payment_amount": "Amount",
            "customer_id": "Customer",
            "expected_to_fail": "Expected to fail",
        }
    )
    return styled.style.applymap(risk_style, subset=["Risk Level"]).format(
        {"Amount": "£{:,.2f}", "Potential revenue at risk": "£{:,.2f}"}
    )


# -----------------------------------------------------------------------------
# Page 1: Executive Dashboard
# -----------------------------------------------------------------------------
def page_executive_dashboard(df: pd.DataFrame) -> None:
    render_product_hero()
    render_header("Executive health view for payment success, failed value, and merchant risk.")

    total_payments = len(df)
    success_rate = pct(df["is_success"])
    failed_amount = float(df["failed_amount"].sum())
    recovered_amount = failed_amount * RECOVERY_RATE_ESTIMATE
    avg_retry_success_rate = RECOVERY_RATE_ESTIMATE * 100

    kpi_cols = st.columns(5)
    kpis = [
        ("Total Payments", f"{total_payments:,}", "Synthetic payments analysed"),
        ("Success Rate %", f"{success_rate:.1f}%", "Successful collections"),
        ("Failed Amount £", format_currency(failed_amount), "Gross payment value failed"),
        ("Recovered Amount £", format_currency(recovered_amount), "Estimated after retry actions"),
        ("Avg Retry Success Rate", f"{avg_retry_success_rate:.0f}%", "Portfolio planning assumption"),
    ]
    for col, (label, value, help_text) in zip(kpi_cols, kpis):
        col.markdown(metric_card(label, value, help_text), unsafe_allow_html=True)

    st.markdown("---")

    monthly = get_sql_results(df).get("monthly_success_rates", pd.DataFrame())
    if not monthly.empty:
        monthly_last12 = monthly.tail(12).copy()
    else:
        monthly_last12 = (
            df.groupby("year_month")
            .agg(success_rate_pct=("is_success", lambda x: x.mean() * 100), total_payments=("payment_id", "count"))
            .reset_index()
            .tail(12)
        )

    country_failures = (
        df[df["is_failed"].eq(1)]
        .groupby("bank_country")
        .agg(failed_payments=("payment_id", "count"), failed_amount=("payment_amount", "sum"))
        .reset_index()
        .sort_values("failed_payments", ascending=False)
    )

    left, right = st.columns(2)
    with left:
        fig = px.line(
            monthly_last12,
            x="year_month",
            y="success_rate_pct",
            markers=True,
            title="Monthly success rate trend — last 12 months",
        )
        fig.update_traces(line=dict(width=3, color=BRAND_BLUE), marker=dict(size=8))
        fig.update_layout(
            template="plotly_white",
            yaxis_title="Success rate %",
            xaxis_title="Month",
            yaxis=dict(range=[max(70, monthly_last12["success_rate_pct"].min() - 3), 100]),
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        fig = px.bar(
            country_failures,
            x="bank_country",
            y="failed_payments",
            text="failed_payments",
            title="Failure distribution by bank country",
        )
        fig.update_traces(marker_color=BRAND_GREEN, textposition="outside")
        fig.update_layout(template="plotly_white", xaxis_title="Bank country", yaxis_title="Failed payments")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 5 highest risk merchants")
    top_merchants = merchant_risk_table(df)
    st.dataframe(
        top_merchants[
            [
                "merchant_id",
                "total_payments",
                "failed_payments",
                "failure_rate_pct",
                "failed_amount",
                "risk_score",
            ]
        ]
        .rename(
            columns={
                "merchant_id": "Merchant",
                "total_payments": "Total Payments",
                "failed_payments": "Failed Payments",
                "failure_rate_pct": "Failure Rate %",
                "failed_amount": "Failed Amount",
                "risk_score": "Risk Score",
            }
        )
        .style.format({"Failure Rate %": "{:.1f}%", "Failed Amount": "£{:,.2f}", "Risk Score": "{:,.1f}"}),
        use_container_width=True,
    )


# -----------------------------------------------------------------------------
# Page 2: Predict Payment Failures
# -----------------------------------------------------------------------------
def page_predict_payment_failures(df: pd.DataFrame) -> None:
    render_header("Upload upcoming scheduled payments to identify failure risks.")

    st.markdown(
        "Upload a CSV with upcoming payments. Missing optional fields are filled with safe defaults, "
        "but the best results come from including customer history, merchant, bank, balance band, and mandate age."
    )

    template_col, upload_col = st.columns([1, 2])
    with template_col:
        st.download_button(
            "Download CSV template",
            data=make_template_csv(),
            file_name="directdebit_iq_upcoming_payments_template.csv",
            mime="text/csv",
            use_container_width=True,
        )
        use_sample = st.checkbox("Demo Mode: use 250 sample upcoming payments", value=st.session_state.get("demo_mode", True))

    with upload_col:
        uploaded_file = st.file_uploader("Upload upcoming payments CSV", type=["csv"])

    upcoming_df: pd.DataFrame | None = None
    if uploaded_file is not None:
        upcoming_df = pd.read_csv(uploaded_file)
        st.success(f"Uploaded {len(upcoming_df):,} upcoming payments.")
    elif use_sample:
        upcoming_df = (
            df.sort_values(["previous_failure_count", "failed_amount", "payment_amount"], ascending=False)
            .head(250)
            .copy()
        )
        upcoming_df["payment_id"] = [f"SAMPLE-UPCOMING-{i + 1:05d}" for i in range(len(upcoming_df))]
        upcoming_df["payment_date"] = pd.Timestamp.today().normalize() + pd.to_timedelta(
            np.arange(len(upcoming_df)) % 14 + 1, unit="D"
        )
        upcoming_df["payment_status"] = "success"
        st.info("Demo Mode is using 250 sample upcoming payments, so reviewers can see predictions without uploading a file.")

    analyse = st.button("Analyse Payments", type="primary", use_container_width=True)

    auto_demo_score = uploaded_file is None and use_sample and upcoming_df is not None

    if analyse or (auto_demo_score and st.session_state.get("scored_payments") is None):
        if upcoming_df is None or upcoming_df.empty:
            st.warning("Upload a CSV or select the sample option before analysing payments.")
            return

        with st.spinner("Scoring payments and calculating revenue at risk..."):
            scored = score_payments(upcoming_df, df)
            st.session_state["scored_payments"] = scored

    scored_df = st.session_state.get("scored_payments")
    if scored_df is None:
        st.info("No prediction results yet. Upload a CSV or keep Demo Mode enabled to auto-load sample payments.")
        return

    high_risk = scored_df[scored_df["risk_level"].isin(["HIGH", "CRITICAL"])]
    total_at_risk = float(high_risk["payment_amount"].sum())
    expected_fail = scored_df[scored_df["expected_to_fail"].eq("Yes")]

    summary_cols = st.columns(3)
    summary_cols[0].markdown(
        metric_card("High/Critical Risk", f"{len(high_risk):,}", "Payments requiring attention"),
        unsafe_allow_html=True,
    )
    summary_cols[1].markdown(
        metric_card("Total At Risk", format_currency(total_at_risk), "High + critical payment value"),
        unsafe_allow_html=True,
    )
    summary_cols[2].markdown(
        metric_card("Expected To Fail", f"{len(expected_fail):,}", "Using 0.30 business threshold"),
        unsafe_allow_html=True,
    )

    st.success(f"{len(high_risk):,} payments at HIGH risk | {format_currency(total_at_risk)} total at risk")
    st.subheader("Operations capacity planner")
    minimum_capacity = min(10, len(scored_df))
    review_capacity = st.slider(
        "Daily manual-review capacity",
        min_value=minimum_capacity,
        max_value=min(250, len(scored_df)),
        value=min(50, len(scored_df)),
        step=max(1, minimum_capacity),
        help="Prioritises the highest risk-value payments the team can review today.",
    )
    priority_queue = (
        scored_df.assign(priority_value=scored_df["risk_probability"] * scored_df["payment_amount"])
        .sort_values("priority_value", ascending=False)
        .head(review_capacity)
    )
    capacity_cols = st.columns(3)
    capacity_cols[0].markdown(
        metric_card("Reviews Today", f"{review_capacity:,}", "Highest risk-value payments"),
        unsafe_allow_html=True,
    )
    capacity_cols[1].markdown(
        metric_card("Value Reviewed", format_currency(float(priority_queue["payment_amount"].sum())), "Inside review capacity"),
        unsafe_allow_html=True,
    )
    capacity_cols[2].markdown(
        metric_card("Expected Failures Covered", f"{priority_queue['risk_probability'].sum():.1f}", "Probability-weighted estimate"),
        unsafe_allow_html=True,
    )
    st.dataframe(style_scored_table(scored_df), use_container_width=True, height=430)

    csv = scored_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download flagged payments CSV",
        data=csv,
        file_name="directdebit_iq_flagged_payments.csv",
        mime="text/csv",
        use_container_width=True,
    )


# -----------------------------------------------------------------------------
# Page 3: Retry Recommendations
# -----------------------------------------------------------------------------
def page_retry_recommendations(df: pd.DataFrame) -> None:
    render_header("Prioritise retry timing and estimate recoverable payment value.")

    source = st.radio(
        "Choose input source",
        ["Use Page 2 prediction results", "Upload scored payments CSV"],
        horizontal=True,
    )

    scored_df: pd.DataFrame | None = None
    if source == "Use Page 2 prediction results":
        scored_df = st.session_state.get("scored_payments")
        if scored_df is None:
            st.info("No Page 2 results yet. I’ll create retry recommendations from a high-risk sample so the page can be reviewed.")
            sample = (
                df.sort_values(["previous_failure_count", "failed_amount", "payment_amount"], ascending=False)
                .head(120)
                .copy()
            )
            sample["payment_id"] = [f"RETRY-SAMPLE-{i + 1:05d}" for i in range(len(sample))]
            sample["payment_date"] = pd.Timestamp.today().normalize() + pd.to_timedelta(
                np.arange(len(sample)) % 10 + 1, unit="D"
            )
            sample["payment_status"] = "success"
            scored_df = score_payments(sample, df)
    else:
        uploaded = st.file_uploader("Upload scored payments CSV", type=["csv"], key="retry_upload")
        if uploaded is not None:
            scored_df = pd.read_csv(uploaded)
            if "risk_probability" not in scored_df.columns and "risk_score" in scored_df.columns:
                scored_df["risk_probability"] = scored_df["risk_score"] / 100
            if "risk_score" not in scored_df.columns and "risk_probability" in scored_df.columns:
                scored_df["risk_score"] = scored_df["risk_probability"] * 100
            if "payment_date" not in scored_df.columns:
                scored_df["payment_date"] = pd.Timestamp.today().normalize()

    if scored_df is None or scored_df.empty:
        st.warning("No scored payments available yet.")
        return

    with st.spinner("Building retry schedule..."):
        retry_schedule = build_retry_schedule(scored_df)

    if retry_schedule.empty:
        st.success("No high-risk payments found. No retry schedule is required.")
        return

    total_expected_recovery = float(retry_schedule["expected_recovery_amount"].sum())
    at_risk_value = float(retry_schedule["payment_amount"].sum())

    top_cols = st.columns(3)
    top_cols[0].markdown(
        metric_card("Expected Recovery", format_currency(total_expected_recovery), "Probability-adjusted retry value"),
        unsafe_allow_html=True,
    )
    top_cols[1].markdown(
        metric_card("At-Risk Retry Value", format_currency(at_risk_value), "Payments in retry schedule"),
        unsafe_allow_html=True,
    )
    top_cols[2].markdown(
        metric_card("Retry Items", f"{len(retry_schedule):,}", "Prioritised by value × risk"),
        unsafe_allow_html=True,
    )

    display = retry_schedule[
        [
            "payment_id",
            "payment_amount",
            "recommended_retry_date",
            "retry_day_of_week",
            "expected_success_probability",
            "priority_rank",
        ]
    ].rename(
        columns={
            "payment_id": "Payment ID",
            "payment_amount": "Amount",
            "recommended_retry_date": "Recommended retry date",
            "retry_day_of_week": "Day of week",
            "expected_success_probability": "Expected success probability",
            "priority_rank": "Priority rank",
        }
    )
    st.dataframe(
        display.style.format(
            {
                "Amount": "£{:,.2f}",
                "Expected success probability": "{:.1%}",
                "Recommended retry date": lambda x: pd.to_datetime(x).strftime("%Y-%m-%d"),
            }
        ),
        use_container_width=True,
        height=360,
    )

    st.subheader("Calendar view")
    render_calendar_grid(retry_schedule)

    st.download_button(
        "Download retry schedule CSV",
        data=retry_schedule.to_csv(index=False).encode("utf-8"),
        file_name="directdebit_iq_retry_schedule.csv",
        mime="text/csv",
        use_container_width=True,
    )


# -----------------------------------------------------------------------------
# Page 4: Explainability
# -----------------------------------------------------------------------------
def page_explainability(df: pd.DataFrame) -> None:
    render_header("Explain individual payment risk in plain English.")

    scored_df = st.session_state.get("scored_payments")
    if scored_df is None or scored_df.empty:
        st.info("No Page 2 results found. Using a high-risk sample from the historical dataset for explainability.")
        sample = (
            df.sort_values(["previous_failure_count", "failed_amount", "payment_amount"], ascending=False)
            .head(80)
            .copy()
        )
        sample["payment_id"] = [f"EXPLAIN-SAMPLE-{i + 1:05d}" for i in range(len(sample))]
        sample["payment_date"] = pd.Timestamp.today().normalize() + pd.to_timedelta(
            np.arange(len(sample)) % 7 + 1, unit="D"
        )
        sample["payment_status"] = "success"
        scored_df = score_payments(sample, df)

    payment_ids = scored_df["payment_id"].astype(str).tolist()
    selected_id = st.selectbox("Select a payment ID", payment_ids)
    selected_row = scored_df[scored_df["payment_id"].astype(str).eq(selected_id)].iloc[0]

    top_cols = st.columns(4)
    top_cols[0].markdown(
        metric_card("Risk Score", f"{selected_row['risk_score']:.1f}/100", selected_row["risk_level"]),
        unsafe_allow_html=True,
    )
    top_cols[1].markdown(
        metric_card("Amount", format_currency(float(selected_row["payment_amount"])), "Scheduled payment value"),
        unsafe_allow_html=True,
    )
    top_cols[2].markdown(
        metric_card("Previous Failures", f"{int(selected_row.get('previous_failure_count', 0))}", "Customer history signal"),
        unsafe_allow_html=True,
    )
    top_cols[3].markdown(
        metric_card("Expected To Fail", str(selected_row["expected_to_fail"]), "0.30 business threshold"),
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.45, 1])
    with left:
        with st.spinner("Building SHAP explanation..."):
            fig = plot_shap_or_proxy(selected_row, df)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Top 3 failure reasons")
        for title, body in build_failure_reasons(selected_row):
            st.markdown(
                f"""
                <div class="insight-card">
                    <div class="insight-title">{title}</div>
                    <div class="insight-body">{body}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(
            f"""
            <div class="action-box">
                <strong>Recommended action</strong><br>
                {recommended_action(selected_row)}
            </div>
            """,
            unsafe_allow_html=True,
        )


# -----------------------------------------------------------------------------
# Page 5: SQL Analytics
# -----------------------------------------------------------------------------
def page_sql_analytics(df: pd.DataFrame) -> None:
    render_header("Run and visualise the four SQLite analysis queries.")

    with st.spinner("Running SQL analyses through SQLite..."):
        results = get_sql_results(df)

    # 1. Monthly success rates
    monthly = results["monthly_success_rates"]
    st.subheader("1. Monthly Success Rates")
    fig = px.line(
        monthly,
        x="year_month",
        y="success_rate_pct",
        markers=True,
        hover_data=["total_payments", "failed_payments", "vs_previous_month_change"],
        title="Success rate by month",
    )
    fig.update_traces(line=dict(width=3, color=BRAND_BLUE))
    fig.update_layout(template="plotly_white", yaxis_title="Success rate %", xaxis_title="Month")
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Raw data — monthly success rates"):
        st.dataframe(monthly, use_container_width=True)

    # 2. Merchant cohort analysis
    cohort = results["merchant_cohort_analysis"].copy()
    st.subheader("2. Merchant Cohort Analysis")
    worst_cohort = cohort.sort_values(["success_rate", "payment_count"], ascending=[True, False]).head(30)
    fig = px.bar(
        worst_cohort,
        x="merchant_id",
        y="success_rate",
        color="mandate_age_band",
        hover_data=["payment_count"],
        title="Lowest-performing merchant + mandate age cohorts",
    )
    fig.update_layout(template="plotly_white", yaxis_title="Success rate %", xaxis_title="Merchant")
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Raw data — merchant cohort analysis"):
        st.dataframe(cohort, use_container_width=True)

    # 3. High-risk customers
    customers = results["high_risk_customers"].copy()
    st.subheader("3. High-Risk Customers")
    category_counts = (
        customers.groupby("risk_category")
        .size()
        .reindex(RISK_ORDER, fill_value=0)
        .reset_index(name="customer_count")
    )
    fig = px.pie(
        category_counts,
        names="risk_category",
        values="customer_count",
        title="Customer risk category distribution",
        hole=0.45,
    )
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Raw data — high-risk customers"):
        st.dataframe(customers, use_container_width=True)

    # 4. Bank country analysis
    bank = results["bank_country_analysis"].copy()
    st.subheader("4. Bank Country & Bank Type Analysis")
    fig = px.bar(
        bank,
        x="bank_country",
        y="success_rate",
        color="bank_type",
        barmode="group",
        hover_data=["total_payments", "avg_payment_amount", "most_common_failure_day"],
        title="Success rate by bank country and bank type",
    )
    fig.update_layout(template="plotly_white", yaxis_title="Success rate %", xaxis_title="Bank country")
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Raw data — bank country analysis"):
        st.dataframe(bank, use_container_width=True)


# -----------------------------------------------------------------------------
# App router
# -----------------------------------------------------------------------------
def main() -> None:
    payments = load_payments()
    data_source = payments.attrs.get("source", "file")

    with st.sidebar:
        st.markdown("### 💳 DirectDebit IQ")
        st.caption("Payment Success Analytics & Failure Predictor")
        st.session_state["demo_mode"] = st.checkbox(
            "Demo Mode",
            value=True,
            help="Loads built-in sample data/results so recruiters can review the live app without uploading files.",
        )
        page = st.radio(
            "Navigation",
            [
                "📊 Executive Dashboard",
                "🔮 Predict Payment Failures",
                "🔄 Retry Recommendations",
                "🧠 Why Did It Fail?",
                "📈 SQL Analytics",
            ],
            label_visibility="collapsed",
        )
        st.markdown("---")
        model_status = "Loaded" if load_model_artifact() is not None else "Fallback rules"
        st.metric("Model", model_status)
        st.metric("Dataset", f"{len(payments):,} rows")
        st.caption("Built for stakeholder demos, analytics portfolios, and ML project review.")

        with st.expander("About This Project", expanded=True):
            st.markdown(
                f"""
                **What it demonstrates**  
                End-to-end payment analytics, ML failure prediction, retry recommendations, SQL analysis, explainability, and Streamlit deployment readiness.

                **Technical stack**  
                Python, pandas, scikit-learn, XGBoost, SQLite, SQL, Plotly, Streamlit, MLflow, pytest, Docker.

                **GitHub**  
                [DirectDebit IQ repository]({GITHUB_REPO_URL})

                **Live demo**
                [Open DirectDebit IQ]({LIVE_DEMO_URL})

                **Author**  
                {AUTHOR_NAME}  
                [LinkedIn]({LINKEDIN_URL})
                """
            )

    if data_source == "demo":
        st.info(
            "Demo Mode data is active because generated CSV/SQLite files were not found. "
            "The app remains fully usable for reviewers without any setup."
        )

    if page == "📊 Executive Dashboard":
        page_executive_dashboard(payments)
    elif page == "🔮 Predict Payment Failures":
        page_predict_payment_failures(payments)
    elif page == "🔄 Retry Recommendations":
        page_retry_recommendations(payments)
    elif page == "🧠 Why Did It Fail?":
        page_explainability(payments)
    elif page == "📈 SQL Analytics":
        page_sql_analytics(payments)


if __name__ == "__main__":
    main()
