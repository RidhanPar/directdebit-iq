# Streamlit Cloud Deployment Checklist

This checklist confirms DirectDebit IQ is ready for a recruiter-friendly Streamlit Cloud deployment.

## Deployment Status

| Check | Status | Notes |
|---|---:|---|
| Root entry point exists | ✅ Fixed | `streamlit_app.py` exists at project root and imports `main()` from `app/dashboard.py`. |
| Requirements are pinned | ✅ Fixed | `requirements.txt` uses exact package versions for reproducible Streamlit Cloud builds. |
| Paths are relative | ✅ Fixed | App paths are built from `Path(__file__).resolve().parents[1]`; no absolute local paths are required. |
| Missing model handled | ✅ Fixed | The app checks for `models/failure_predictor.pkl`, `models/fraud_model.pkl`, and `models/payment_failure_model.joblib`; if none exist, it uses transparent fallback scoring. |
| Missing data handled | ✅ Fixed | If `data/raw/payments.csv` or SQLite files are missing, the app loads deterministic built-in demo data instead of crashing. |
| No secrets in code | ✅ Checked | No API keys or hardcoded secrets are used. Use `st.secrets` for future private credentials. |
| Streamlit config valid | ✅ Checked | `.streamlit/config.toml` contains valid theme, server, and browser sections. |
| Demo mode available | ✅ Fixed | Sidebar Demo Mode is enabled by default, and the prediction page auto-loads sample upcoming payments. |
| About section available | ✅ Fixed | Sidebar includes project explanation, stack, GitHub link, author, and LinkedIn link. |

## Recommended Streamlit Cloud Settings

| Setting | Value |
|---|---|
| Repository | `RidhanPar/directdebit-iq` |
| Branch | `main` |
| Main file path | `streamlit_app.py` |
| Python version | 3.10 or 3.11 (`runtime.txt` pins Python 3.10) |
| Secrets | None required for demo mode |
| Runtime file | `runtime.txt` with `python-3.10` |

## Pre-Deployment Commands

Run these locally before pushing:

```bash
python -m pip install -r requirements.txt
python -m py_compile streamlit_app.py app/dashboard.py
pytest -q
streamlit run streamlit_app.py
```

## Streamlit Cloud Deployment Steps

1. Push the latest code to GitHub.
2. Open Streamlit Cloud.
3. Choose **New app**.
4. Select the GitHub repository.
5. Set the main file path to `streamlit_app.py`.
6. Deploy.
7. Open the deployed link and verify the Executive Dashboard loads immediately.
8. Go to **Predict Payment Failures** and confirm Demo Mode shows scored sample payments without uploading a file.

## Reviewer Experience

When a recruiter opens the live app, they should immediately see:

- Executive KPIs and charts without uploading data.
- Prediction results using Demo Mode.
- Retry recommendations using sample high-risk payments.
- Explainability with plain-English failure reasons.
- SQL analytics from SQLite or dataframe fallback.

## Future Production Notes

For real production deployment, replace Demo Mode with controlled production data access, secret-managed database credentials, model registry loading, and proper user authentication.
