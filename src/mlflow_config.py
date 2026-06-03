"""MLflow configuration for DirectDebit IQ experiment tracking."""

EXPERIMENT_NAME = "DirectDebit IQ - Payment Failure Prediction"

# Local SQLite backend works reliably across Windows, macOS, Linux, and Docker.
TRACKING_URI = "sqlite:///mlflow.db"

RUN_TAGS = {
    "project": "DirectDebit IQ",
    "version": "1.0.0",
    "author": "Ridhan Parvendhan",
}
