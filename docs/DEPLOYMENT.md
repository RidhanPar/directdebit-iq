# DirectDebit IQ Deployment Guide

This guide follows the same deployment flow used for the PayGuard Streamlit project: prepare the repository, validate locally, push to GitHub, and deploy through Streamlit Cloud.

---

## 1. Local Validation

From the project root, install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows PowerShell

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Generate the dataset and SQLite database:

```bash
python data/generate_data.py
```

Run SQL analytics:

```bash
python src/sql_runner.py
```

Train the model:

```bash
python src/train.py
```

Run tests:

```bash
pytest -q
```

Launch the dashboard locally:

```bash
streamlit run streamlit_app.py
```

---

## 2. Required Files for Streamlit Cloud

Streamlit Cloud should point to the root-level entry file:

```text
streamlit_app.py
```

Required deployment files:

```text
requirements.txt
streamlit_app.py
.streamlit/config.toml
app/dashboard.py
data/generate_data.py
src/
sql/
```

The entry point imports and runs the dashboard:

```python
from app.dashboard import main

if __name__ == "__main__":
    main()
```

---

## 3. GitHub Push

```bash
git add .
git commit -m "Finalize DirectDebit IQ deployment files"
git push origin main
```

After pushing, GitHub Actions will run:

```text
Run Unit Tests
Run Code Quality Checks
Validate Build and App Startup
```

---

## 4. Streamlit Cloud Deployment

1. Open Streamlit Cloud.
2. Choose **New app**.
3. Select your GitHub repository.
4. Choose the `main` branch.
5. Set the main file path to:

```text
streamlit_app.py
```

6. Click **Deploy**.

---

## 5. Environment Variables

This project can run without secrets because it uses synthetic data.

Optional future variables can be stored in Streamlit Cloud settings:

```text
DATABASE_URL=
MODEL_REGISTRY_PATH=
API_BASE_URL=
```

Never commit real API keys or payment data into GitHub.

---

## 6. Production Notes

For a real production version, replace synthetic files with secure data access:

- Store raw payment data in a warehouse or secure object storage.
- Use a managed database instead of local SQLite.
- Schedule model retraining.
- Monitor prediction drift and payment success drift.
- Add authentication if the dashboard contains sensitive business data.
- Add a real-time scoring API before connecting to operational payment systems.

---

## 7. Troubleshooting

### App cannot find `payments.csv`

Run:

```bash
python data/generate_data.py
```

### App cannot find model file

Run:

```bash
python src/train.py
```

The dashboard still works with fallback rules, but the trained model is recommended for full functionality.

### SQL page is empty

Run:

```bash
python src/sql_runner.py
```

### Dependency install fails

Upgrade pip and reinstall:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```
