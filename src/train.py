"""Train the DirectDebit IQ failure prediction model with MLflow tracking.

This script mirrors a production-style ML workflow:
1. Load and clean generated payment data
2. Build leakage-safe features through FeatureStore
3. Train/test split with stratification
4. Train an XGBoost classifier with class imbalance handling
5. Evaluate ML and business metrics
6. Log parameters, metrics, model artifacts, and plots to MLflow
7. Save a reusable artifact to models/failure_predictor.pkl
"""

from __future__ import annotations

import json
import sys
import warnings
from contextlib import nullcontext
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from xgboost import XGBClassifier

from src import config
from src.data_pipeline import clean_payments
from src.feature_store import FeatureStore
from src.mlflow_config import EXPERIMENT_NAME, RUN_TAGS, TRACKING_URI
from src.utils import ensure_project_directories, load_payments_csv, save_json

warnings.filterwarnings("ignore", category=UserWarning)

try:  # Keep tests/imports working before dependencies are installed.
    import mlflow
    import mlflow.xgboost

    MLFLOW_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only in minimal local envs
    mlflow = None  # type: ignore[assignment]
    MLFLOW_AVAILABLE = False

FAILURE_PREDICTOR_PATH = PROJECT_ROOT / "models" / "failure_predictor.pkl"
FAILURE_METRICS_PATH = PROJECT_ROOT / "models" / "failure_predictor_metrics.json"
FAILURE_IMPORTANCE_PATH = PROJECT_ROOT / "models" / "failure_predictor_feature_importance.csv"
MLFLOW_ARTIFACT_DIR = PROJECT_ROOT / "models" / "mlflow_artifacts"
BUSINESS_THRESHOLD = 0.30
RECOVERY_COST_MULTIPLIER = 3.0
OUT_OF_TIME_TEST_SHARE = 0.20


def configure_mlflow() -> None:
    """Configure local MLflow tracking if MLflow is installed."""
    if not MLFLOW_AVAILABLE:
        print("MLflow is not installed. Install requirements.txt to enable experiment tracking.")
        return

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)


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


def out_of_time_split(
    X: pd.DataFrame,
    y: pd.Series,
    payment_amounts: pd.Series,
    payment_dates: pd.Series,
    test_share: float = OUT_OF_TIME_TEST_SHARE,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series, pd.Series, pd.Timestamp]:
    """Split model data chronologically so evaluation represents future payments."""
    if not 0 < test_share < 1:
        raise ValueError("test_share must be between 0 and 1.")

    split_frame = pd.DataFrame(
        {
            "row_position": np.arange(len(X)),
            "payment_date": pd.to_datetime(payment_dates, errors="raise").to_numpy(),
        }
    ).sort_values(["payment_date", "row_position"])
    split_index = max(1, min(len(split_frame) - 1, int(len(split_frame) * (1 - test_share))))
    train_positions = split_frame.iloc[:split_index]["row_position"].to_numpy()
    test_positions = split_frame.iloc[split_index:]["row_position"].to_numpy()
    cutoff_date = pd.Timestamp(split_frame.iloc[split_index]["payment_date"])

    return (
        X.iloc[train_positions],
        X.iloc[test_positions],
        y.iloc[train_positions],
        y.iloc[test_positions],
        payment_amounts.iloc[train_positions],
        payment_amounts.iloc[test_positions],
        cutoff_date,
    )


def _build_xgboost_model(scale_pos_weight: float) -> XGBClassifier:
    """Create the final XGBoost model with project hyperparameters."""
    return XGBClassifier(
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


def _xgboost_hyperparameters(model: XGBClassifier) -> dict[str, Any]:
    """Return all relevant model hyperparameters in MLflow-friendly format."""
    params = model.get_params()
    wanted = [
        "n_estimators",
        "max_depth",
        "learning_rate",
        "subsample",
        "colsample_bytree",
        "min_child_weight",
        "reg_lambda",
        "eval_metric",
        "random_state",
        "n_jobs",
        "tree_method",
        "verbosity",
        "scale_pos_weight",
    ]
    return {key: params.get(key) for key in wanted}


def _save_feature_importance_plot(importance: pd.DataFrame) -> Path:
    """Save a Plotly feature importance chart as an MLflow artifact."""
    MLFLOW_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    top_features = importance.head(20).sort_values("importance", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=top_features["importance"],
            y=top_features["feature"],
            orientation="h",
            hovertemplate="%{y}<br>Importance: %{x:.4f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Top 20 Feature Importances — DirectDebit IQ",
        xaxis_title="Importance",
        yaxis_title="Feature",
        template="plotly_white",
        height=720,
        margin=dict(l=220, r=40, t=80, b=60),
    )
    output_path = MLFLOW_ARTIFACT_DIR / "feature_importance_plot.html"
    fig.write_html(output_path, include_plotlyjs="cdn")
    return output_path


def _save_confusion_matrix_plot(matrix: np.ndarray) -> Path:
    """Save a Plotly confusion matrix heatmap as an MLflow artifact."""
    MLFLOW_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    labels = ["Predicted Success", "Predicted Failure"]
    actual_labels = ["Actual Success", "Actual Failure"]
    fig = go.Figure(
        data=go.Heatmap(
            z=matrix,
            x=labels,
            y=actual_labels,
            text=matrix,
            texttemplate="%{text}",
            colorscale="Blues",
            hovertemplate="%{y}<br>%{x}<br>Count: %{z}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"Confusion Matrix at Threshold {BUSINESS_THRESHOLD:.2f}",
        template="plotly_white",
        height=520,
        margin=dict(l=100, r=40, t=80, b=60),
    )
    output_path = MLFLOW_ARTIFACT_DIR / "confusion_matrix.html"
    fig.write_html(output_path, include_plotlyjs="cdn")
    return output_path


def _log_mlflow_run(
    model: XGBClassifier,
    hyperparameters: dict[str, Any],
    metrics: dict[str, Any],
    importance_path: Path,
    feature_importance_plot_path: Path,
    confusion_matrix_plot_path: Path,
    model_path: Path,
    metrics_path: Path,
) -> None:
    """Log all experiment data to MLflow."""
    if not MLFLOW_AVAILABLE:
        return

    scalar_metrics = {
        "auc_roc": metrics["roc_auc"],
        "average_precision": metrics["average_precision"],
        "precision_at_0_30": metrics["precision_at_0_30"],
        "recall_at_0_30": metrics["recall_at_0_30"],
        "f1_at_0_30": metrics["f1_at_0_30"],
        "f1_at_0_50": metrics["f1_at_0_50"],
        "revenue_at_risk_caught_per_1000": metrics["revenue_at_risk_caught_per_1000"],
        "failure_rate": metrics["failure_rate"],
    }

    mlflow.set_tags(RUN_TAGS)
    mlflow.log_params(hyperparameters)
    mlflow.log_params(
        {
            "test_size": OUT_OF_TIME_TEST_SHARE,
            "validation_method": "out_of_time_holdout",
            "business_threshold": BUSINESS_THRESHOLD,
            "recovery_cost_multiplier": RECOVERY_COST_MULTIPLIER,
            "feature_count": metrics["features"],
            "training_rows": metrics["rows"],
        }
    )
    mlflow.log_metrics(scalar_metrics)

    mlflow.log_artifact(str(model_path), artifact_path="model_artifacts")
    mlflow.log_artifact(str(metrics_path), artifact_path="model_artifacts")
    mlflow.log_artifact(str(importance_path), artifact_path="model_artifacts")
    mlflow.log_artifact(str(feature_importance_plot_path), artifact_path="plots")
    mlflow.log_artifact(str(confusion_matrix_plot_path), artifact_path="plots")

    try:
        mlflow.xgboost.log_model(model, artifact_path="xgboost_failure_predictor")
    except Exception as exc:  # pragma: no cover - MLflow version/platform dependent
        print(f"MLflow model logging skipped, but local model artifact was logged: {exc}")


def train_model() -> dict[str, Any]:
    """Train, evaluate, save, and MLflow-log the final payment failure classifier."""
    ensure_project_directories()
    configure_mlflow()

    raw = load_payments_csv()
    df = clean_payments(raw)
    X, y, _store = build_training_data(df)

    # Keep payment amounts aligned with X/y for the business metric.
    aligned_payments = df.sort_values(["customer_id", "payment_date", "payment_id"]).reset_index(drop=True)
    payment_amounts = aligned_payments["payment_amount"]
    payment_dates = aligned_payments["payment_date"]

    X_train, X_test, y_train, y_test, amount_train, amount_test, cutoff_date = out_of_time_split(
        X,
        y,
        payment_amounts,
        payment_dates,
    )

    negative_count = int((y_train == 0).sum())
    positive_count = int((y_train == 1).sum())
    scale_pos_weight = negative_count / max(positive_count, 1)

    model = _build_xgboost_model(scale_pos_weight=scale_pos_weight)
    hyperparameters = _xgboost_hyperparameters(model)

    run_context = mlflow.start_run(run_name="XGBoost_v1") if MLFLOW_AVAILABLE else nullcontext()
    with run_context:
        model.fit(X_train, y_train)

        probabilities = model.predict_proba(X_test)[:, 1]
        predictions_030 = (probabilities >= BUSINESS_THRESHOLD).astype(int)
        predictions_050 = (probabilities >= 0.50).astype(int)
        cm_030 = confusion_matrix(y_test, predictions_030)

        metrics: dict[str, Any] = {
            "rows": int(len(df)),
            "features": int(X.shape[1]),
            "test_rows": int(len(y_test)),
            "failure_rate": float(y.mean()),
            "validation_method": "out_of_time_holdout",
            "validation_cutoff_date": cutoff_date.strftime("%Y-%m-%d"),
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
            "confusion_matrix_at_0_30": cm_030.tolist(),
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

        feature_importance_plot_path = _save_feature_importance_plot(importance)
        confusion_matrix_plot_path = _save_confusion_matrix_plot(cm_030)

        _log_mlflow_run(
            model=model,
            hyperparameters=hyperparameters,
            metrics=metrics,
            importance_path=FAILURE_IMPORTANCE_PATH,
            feature_importance_plot_path=feature_importance_plot_path,
            confusion_matrix_plot_path=confusion_matrix_plot_path,
            model_path=FAILURE_PREDICTOR_PATH,
            metrics_path=FAILURE_METRICS_PATH,
        )

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
