EXPERIMENT_NAME = "DirectDebit IQ - Payment Failure Prediction"

# MLflow 3.x recommended local backend
# This creates a local mlflow.db file in your project root
TRACKING_URI = "sqlite:///mlflow.db"

RUN_TAGS = {
    "project": "DirectDebit IQ",
    "version": "1.0.0",
    "author": "Ridhan Parvendhan",
}