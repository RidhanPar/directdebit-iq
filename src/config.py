"""Project-wide constants for DirectDebit IQ.

This file keeps paths, generation settings, modelling constants, and business
risk thresholds in one place so the project remains easy to maintain.
"""

from pathlib import Path

# -----------------------------------------------------------------------------
# Project metadata
# -----------------------------------------------------------------------------
PROJECT_NAME = "DirectDebit IQ — Payment Success Analytics & Failure Predictor"
PROJECT_SLUG = "directdebit-iq"
RANDOM_SEED = 42
N_ROWS = 50_000

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"
SQL_DIR = BASE_DIR / "sql"

RAW_PAYMENTS_CSV = RAW_DATA_DIR / "payments.csv"
PROCESSED_PAYMENTS_CSV = PROCESSED_DATA_DIR / "payments_features.csv"
SQLITE_DB_PATH = DATA_DIR / "payments.db"
SQLITE_TABLE_NAME = "payments"

MODEL_PATH = MODELS_DIR / "payment_failure_model.joblib"
METRICS_PATH = MODELS_DIR / "model_metrics.json"
FEATURE_IMPORTANCE_PATH = MODELS_DIR / "feature_importance.csv"

# -----------------------------------------------------------------------------
# Synthetic data constants
# -----------------------------------------------------------------------------
MERCHANT_PREFIX = "M"
MERCHANT_MIN_ID = 1
MERCHANT_MAX_ID = 200
CUSTOMER_PREFIX = "C"
CUSTOMER_MIN_ID = 1
CUSTOMER_MAX_ID = 5_000

CURRENCIES = ["GBP", "EUR", "USD"]
CURRENCY_WEIGHTS = [0.70, 0.20, 0.10]

BANK_COUNTRIES = ["GB", "FR", "DE", "IE", "AU", "US"]
BANK_COUNTRY_WEIGHTS = [0.48, 0.15, 0.13, 0.09, 0.08, 0.07]

BANK_TYPES = ["high_street", "challenger", "credit_union"]
BANK_TYPE_WEIGHTS = [0.66, 0.25, 0.09]

BALANCE_BANDS = ["low", "medium", "high"]
BALANCE_BAND_WEIGHTS = [0.28, 0.52, 0.20]

PAYMENT_TYPES = ["recurring", "one_off"]
PAYMENT_TYPE_WEIGHTS = [0.82, 0.18]

PAYMENT_STATUSES = ["success", "failed"]
TARGET_SUCCESS_RATE = 0.85
TARGET_FAILURE_RATE = 0.15

PREVIOUS_FAILURE_VALUES = [0, 1, 2, 3, 4, 5]
PREVIOUS_FAILURE_WEIGHTS = [0.74, 0.13, 0.06, 0.035, 0.02, 0.015]

MANDATE_MAX_AGE_DAYS = 1_825
DAYS_SINCE_LAST_SUCCESS_MAX = 90
PAYMENT_DAY_MIN = 1
PAYMENT_DAY_MAX = 28
HISTORY_DAYS = 730

# Amount distribution controls
AMOUNT_TYPICAL_MIN = 10
AMOUNT_TYPICAL_MAX = 500
AMOUNT_OUTLIER_MIN = 501
AMOUNT_OUTLIER_MAX = 5_000
AMOUNT_OUTLIER_RATE = 0.025

# -----------------------------------------------------------------------------
# Model constants
# -----------------------------------------------------------------------------
TARGET_COLUMN = "payment_status"
TARGET_BINARY_COLUMN = "is_failed"
ID_COLUMNS = ["payment_id", "merchant_id", "customer_id"]
DATE_COLUMNS = ["payment_date"]
NUMERIC_FEATURES = [
    "payment_amount",
    "payment_day_of_month",
    "mandate_age_days",
    "previous_failure_count",
    "days_since_last_success",
]
CATEGORICAL_FEATURES = [
    "currency",
    "day_of_week",
    "bank_country",
    "bank_type",
    "estimated_balance_band",
    "payment_type",
]

TEST_SIZE = 0.20
VALIDATION_SIZE = 0.20
CV_FOLDS = 5
CLASSIFICATION_THRESHOLD = 0.50

XGBOOST_PARAMS = {
    "n_estimators": 80,
    "max_depth": 3,
    "learning_rate": 0.08,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "eval_metric": "logloss",
    "random_state": RANDOM_SEED,
    "n_jobs": 2,
    "tree_method": "hist",
    "verbosity": 0,
}

# -----------------------------------------------------------------------------
# Business thresholds used by recommendations and dashboard
# -----------------------------------------------------------------------------
LOW_RISK_THRESHOLD = 0.20
MEDIUM_RISK_THRESHOLD = 0.45
HIGH_RISK_THRESHOLD = 0.65

RISK_LABELS = {
    "low": "Low risk",
    "medium": "Medium risk",
    "high": "High risk",
    "critical": "Critical risk",
}

RETRY_WINDOW_DAYS = 3
MAX_RETRY_ATTEMPTS = 2
HIGH_FAILURE_COUNT_THRESHOLD = 2
NEW_MANDATE_DAYS_THRESHOLD = 30
LOW_BALANCE_BAND = "low"
MONDAY = "Monday"
