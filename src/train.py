"""Train the DirectDebit IQ failure prediction model.

This script mirrors a production-style ML workflow:
1. Load and clean generated payment data
2. Build features through FeatureStore
3. Train/test split with stratification
4. Train an XGBoost classifier with class imbalance handling
5. Evaluate both ML and business metrics
6. Save a reusable artifact to models/failure_predictor.pkl
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from src import config
from src.data_pipeline import clean_payments
from src.feature_store import FeatureStore
from src.utils import ensure_project_directories, load_payments_csv, save_json

warnings.filterwarnings("ignore", category=UserWarning)

FAILURE_PREDICTOR_PATH = PROJECT_ROOT / "models" / "failure_predictor.pkl"
FAILURE_METRICS_PATH = PROJECT_ROOT / "models" / "failure_predictor_metrics.json"
FAILURE_IMPORTANCE_PATH = PROJECT_ROOT / "models" / "failure_predictor_feature_importance.csv"
BUSINESS_THRESHOLD = 0.30
RECOVERY_COST_MULTIPLIER = 3.0


def revenue_at_risk_caught_per_1000(
    y_true: pd.Series,
    probabilities: np.ndarray,
    payment_amounts: pd.Series,
    threshold: float = BUSINESS_THRESHOLD,
) -> float:
    """Calculate failed-payment value caught per 1,000 predictions.

    A caught item is a true failed payment whose predicted probability is above
    the decision threshold. The payment value is multiplied by the recovery cost
    estimate used in the project narrative.
    """
    predicted_failure = probabilities >= threshold
    true_failure = y_true.to_numpy() == 1
    caught_value = float(payment_amounts.to_numpy()[predicted_failure & true_failure].sum())
    if len(y_true) == 0:
        return 0.0
    return caught_value * RECOVERY_COST_MULTIPLIER / len(y_true) * 1000


def build_training_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, FeatureStore]:
    """Return model features, target, and fitted FeatureStore instance."""
    store = FeatureStore()
    model_df = store.build_feature_matrix(df)
    X = model_df.drop(columns=[config.TARGET_BINARY_COLUMN])
    y = model_df[config.TARGET_BINARY_COLUMN].astype(int)
    return X, y, store


def train_model() -> dict[str, Any]:
    """Train and save the final XGBoost payment failure classifier."""
    ensure_project_directories()
    raw = load_payments_csv()
    df = clean_payments(raw)
    X, y, store = build_training_data(df)

    # Keep payment amounts aligned with X/y for the business metric.
    payment_amounts = df.sort_values(["customer_id", "payment_date", "payment_id"]).reset_index(drop=True)[
        "payment_amount"
    ]

    X_train, X_test, y_train, y_test, amount_train, amount_test = train_test_split(
        X,
        y,
        payment_amounts,
        test_size=config.TEST_SIZE,
        random_state=config.RANDOM_SEED,
        stratify=y,
    )

    negative_count = int((y_train == 0).sum())
    positive_count = int((y_train == 1).sum())
    scale_pos_weight = negative_count / max(positive_count, 1)

    model = XGBClassifier(
        n_estimators=180,
        max_depth=3,
        learning_rate=0.06,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=3,
        reg_lambda=1.0,
        eval_metric="logloss",
        random_state=config.RANDOM_SEED,
        n_jobs=2,
        tree_method="hist",
        verbosity=0,
        scale_pos_weight=scale_pos_weight,
    )
    model.fit(X_train, y_train)

    probabilities = model.predict_proba(X_test)[:, 1]
    predictions_030 = (probabilities >= BUSINESS_THRESHOLD).astype(int)
    predictions_050 = (probabilities >= 0.50).astype(int)

    metrics: dict[str, Any] = {
        "rows": int(len(df)),
        "features": int(X.shape[1]),
        "test_rows": int(len(y_test)),
        "failure_rate": float(y.mean()),
        "threshold": BUSINESS_THRESHOLD,
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "average_precision": float(average_precision_score(y_test, probabilities)),
        "precision_at_0_30": float(precision_score(y_test, predictions_030, zero_division=0)),
        "recall_at_0_30": float(recall_score(y_test, predictions_030, zero_division=0)),
        "f1_at_0_30": float(f1_score(y_test, predictions_030, zero_division=0)),
        "f1_at_0_50": float(f1_score(y_test, predictions_050, zero_division=0)),
        "revenue_at_risk_caught_per_1000": float(
            revenue_at_risk_caught_per_1000(y_test, probabilities, amount_test, BUSINESS_THRESHOLD)
        ),
        "confusion_matrix_at_0_30": confusion_matrix(y_test, predictions_030).tolist(),
        "classification_report_at_0_30": classification_report(
            y_test, predictions_030, output_dict=True, zero_division=0
        ),
    }

    artifact = {
        "model": model,
        "feature_columns": list(X.columns),
        "feature_store_class": "src.feature_store.FeatureStore",
        "threshold": BUSINESS_THRESHOLD,
        "target_column": config.TARGET_BINARY_COLUMN,
        "model_type": "XGBClassifier",
        "metrics": metrics,
    }
    joblib.dump(artifact, FAILURE_PREDICTOR_PATH)

    # Also keep the original project path populated for backward compatibility.
    joblib.dump(artifact, config.MODEL_PATH)

    save_json(metrics, FAILURE_METRICS_PATH)
    save_json(metrics, config.METRICS_PATH)

    importance = pd.DataFrame(
        {
            "feature": X.columns,
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)
    importance.to_csv(FAILURE_IMPORTANCE_PATH, index=False)
    importance.to_csv(config.FEATURE_IMPORTANCE_PATH, index=False)

    return metrics


def predict_failure_risk(new_payments: pd.DataFrame, model_path: Path = FAILURE_PREDICTOR_PATH) -> pd.DataFrame:
    """Score new payment rows with the saved model artifact."""
    artifact = joblib.load(model_path)
    store = FeatureStore()
    model_df = store.build_feature_matrix(new_payments)
    X = model_df.drop(columns=[config.TARGET_BINARY_COLUMN], errors="ignore")
    X = X.reindex(columns=artifact["feature_columns"], fill_value=0)
    probabilities = artifact["model"].predict_proba(X)[:, 1]

    scored = new_payments.copy()
    scored["failure_probability"] = probabilities
    scored["predicted_high_risk"] = probabilities >= artifact.get("threshold", BUSINESS_THRESHOLD)
    return scored


if __name__ == "__main__":
    output = train_model()
    print("Failure predictor training complete")
    print(json.dumps({k: v for k, v in output.items() if k != "classification_report_at_0_30"}, indent=2))
