# Docker Deployment Guide — DirectDebit IQ

This guide shows how to run **DirectDebit IQ — Payment Intelligence Platform** in Docker.

The Docker image starts the Streamlit dashboard on port `8501`. The Docker Compose stack also starts an optional MLflow tracking server on port `5000`.

---

## Prerequisites

Install Docker Desktop and make sure Docker is running.

Check Docker from the terminal:

```bash
docker --version
docker compose version
```

---

## Option 1: Build and run the Streamlit app only

From the project root:

```bash
docker build -t payguard .
```

Run the container:

```bash
docker run -p 8501:8501 payguard
```

Open the dashboard:

```text
http://localhost:8501
```

> Note: the image name `payguard` is kept here for consistency with the deployment command style used in the related PayGuard project. You can also use `directdebit-iq` as the image name if preferred.

Example:

```bash
docker build -t directdebit-iq .
docker run -p 8501:8501 directdebit-iq
```

---

## Option 2: Run full stack with Docker Compose

This starts:

- Streamlit dashboard: `http://localhost:8501`
- MLflow tracking server: `http://localhost:5000`

Run:

```bash
docker-compose up
```

Or with modern Docker Compose:

```bash
docker compose up
```

To rebuild after code changes:

```bash
docker compose up --build
```

To stop the stack:

```bash
docker compose down
```

---

## Makefile shortcuts

```bash
make docker-build
make docker-run
make docker-compose
```

---

## Useful URLs

| Service | URL |
|---|---|
| Streamlit dashboard | `http://localhost:8501` |
| MLflow UI | `http://localhost:5000` |

---

## Notes for reviewers

- `data/raw/` and `models/` are excluded from Docker context to keep the image clean.
- The Docker image generates the synthetic payment dataset during build using `python data/generate_data.py`.
- If the trained model artifact is not present, the dashboard can still run using the business-rule fallback scoring logic.
- MLflow runtime outputs are stored locally under `./mlflow/` when using Docker Compose.
