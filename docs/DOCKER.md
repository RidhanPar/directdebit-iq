# Docker Guide

Docker Compose starts the complete portfolio stack:

| Service | URL |
|---|---|
| Streamlit dashboard | `http://localhost:8501` |
| FastAPI action service | `http://localhost:8000/docs` |
| MLflow tracking server | `http://localhost:5000` |
| n8n workflow automation | `http://localhost:5678` |

## Run

```bash
docker compose up --build
```

Import `automation/n8n_retry_approval_workflow.json` into n8n after the stack starts.

## Dashboard Only

```bash
docker build -t directdebit-iq .
docker run --rm -p 8501:8501 directdebit-iq
```

## Action API Only

```bash
docker build -f Dockerfile.api -t directdebit-iq-action-api .
docker run --rm -p 8000:8000 directdebit-iq-action-api
```

The local API uses SQLite by default. The Render Blueprint injects managed PostgreSQL through `ACTION_DATABASE_URL`.
