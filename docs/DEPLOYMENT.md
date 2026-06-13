# Deployment Guide

## Live Dashboard

The Streamlit dashboard is deployed at:

<https://directdebit-iq.streamlit.app/>

Main file: `streamlit_app.py`.

## Action API on Render

The root [`render.yaml`](../render.yaml) Blueprint creates:

- `directdebit-iq-action-api`: Dockerized FastAPI web service
- `directdebit-iq-actions-db`: managed PostgreSQL database

In Render:

1. Create a new Blueprint from `RidhanPar/directdebit-iq`.
2. Select branch `main` and Blueprint path `render.yaml`.
3. Set `OPENAI_API_KEY` only if the optional structured planner should call OpenAI.
4. Deploy and verify `/health` and `/docs`.

Render generates `JWT_SECRET` and injects the managed database connection. Configure non-demo identity before real operational use.

## Local Full Stack

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Streamlit dashboard | `http://localhost:8501` |
| Action API docs | `http://localhost:8000/docs` |
| MLflow | `http://localhost:5000` |
| n8n | `http://localhost:5678` |

Import `automation/n8n_retry_approval_workflow.json` into n8n and configure its documented environment variables.

## Release Gate

GitHub Actions runs unit/integration tests, lint, the seven-control governance evaluation, Streamlit/API startup checks, and an API container build. Render auto-deployment is configured to follow passing checks.
