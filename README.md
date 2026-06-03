# DirectDebit IQ — Payment Success Analytics & Failure Predictor

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-ff4b4b)
![XGBoost](https://img.shields.io/badge/XGBoost-ML-green)
![SQLite](https://img.shields.io/badge/SQLite-Analytics-lightgrey)
![Plotly](https://img.shields.io/badge/Plotly-Interactive%20Charts-3f4f75)
![Pytest](https://img.shields.io/badge/Pytest-Tested-brightgreen)

**DirectDebit IQ predicts payment failures before they happen, saving businesses the cost of failed payments and recovery overhead.**

This project is a professional, portfolio-ready data science product focused on payment success analytics, direct debit failure prediction, customer risk segmentation, merchant performance monitoring, SQL analytics, and retry recommendations.

---

## Business Context

Failed direct debit payments create avoidable cost, operational workload, customer friction, and cash-flow risk. In many payment operations, a single failed direct debit can cost around **£5–£25 per failure** when bank fees, support handling, customer communication, retry processing, and recovery overhead are included.

DirectDebit IQ helps payment teams answer practical questions:

- Which payments are most likely to fail before collection?
- Which merchants, customers, banks, and mandate ages create the highest risk?
- How much revenue is currently at risk?
- Which payments should be retried first?
- What retry date is likely to improve recovery?

---

## Architecture

```text
+---------------------------+
| Synthetic Payment Dataset |
| data/generate_data.py     |
+-------------+-------------+
              |
              v
+---------------------------+        +--------------------------+
| Raw Data Layer            |        | SQLite Analytics DB      |
| data/raw/payments.csv     +------->| data/payments.db         |
+-------------+-------------+        +------------+-------------+
              |                                   |
              v                                   v
+---------------------------+        +--------------------------+
| Feature Store             |        | SQL Analysis Layer       |
| src/feature_store.py      |        | sql/*.sql                |
+-------------+-------------+        +------------+-------------+
              |                                   |
              v                                   |
+---------------------------+                     |
| ML Training Pipeline      |                     |
| src/train.py              |                     |
| XGBoost failure model     |                     |
+-------------+-------------+                     |
              |                                   |
              v                                   v
+----------------------------------------------------------+
| Streamlit Product Dashboard                              |
| app/dashboard.py                                         |
| Executive KPIs | Prediction | Retry | Explainability | SQL|
+----------------------------------------------------------+
```

---

## Key Results

| Metric | Result | Why it matters |
|---|---:|---|
| Dataset size | 50,000 payments | Large enough for realistic analytics and modelling |
| Generated success rate | ~85% | Matches the target payment success profile |
| Failure rate | ~15% | Creates realistic class imbalance |
| ROC AUC | ~0.690 | Measures ranking quality for failure risk |
| Average Precision | ~0.296 | Useful for imbalanced failure prediction |
| F1 at threshold 0.30 | ~0.281 | Lower threshold catches more risky payments |
| Recall at threshold 0.30 | ~0.945 | Captures most failed payments for proactive action |
| Revenue at risk caught per 1,000 predictions | ~£59,092 | Business-focused model value metric |

> Note: this is a synthetic portfolio project. The metrics are generated from realistic simulated payment patterns, not from private production data.

---

## Tech Stack

| Area | Tools |
|---|---|
| Data generation | Python, Faker, NumPy, pandas |
| Storage | CSV, SQLite, SQLAlchemy |
| Analytics | SQL, pandas, Plotly |
| Machine learning | scikit-learn, XGBoost, imbalanced-learn |
| Explainability | SHAP, feature importance |
| Dashboard | Streamlit, Plotly |
| Testing | pytest |
| CI/CD | GitHub Actions |

---

## Project Structure

```text
directdebit-iq/
├── app/
│   └── dashboard.py
├── data/
│   ├── generate_data.py
│   ├── payments.db
│   ├── raw/payments.csv
│   └── processed/
├── dbt_models/
│   ├── staging/
│   └── marts/
├── docs/
│   └── DEPLOYMENT.md
├── models/
│   ├── failure_predictor.pkl
│   ├── failure_predictor_metrics.json
│   └── failure_predictor_feature_importance.csv
├── notebooks/
│   ├── 01_eda.ipynb
│   └── 02_failure_prediction.ipynb
├── sql/
│   ├── 01_monthly_success_rates.sql
│   ├── 02_merchant_cohort_analysis.sql
│   ├── 03_high_risk_customers.sql
│   └── 04_bank_country_analysis.sql
├── src/
│   ├── config.py
│   ├── data_pipeline.py
│   ├── feature_store.py
│   ├── recommend.py
│   ├── sql_runner.py
│   ├── train.py
│   └── utils.py
├── tests/
│   └── test_pipeline.py
├── .github/workflows/ci.yml
├── .streamlit/config.toml
├── requirements.txt
├── streamlit_app.py
└── README.md
```

---

## Quick Start Guide

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/directdebit-iq.git
cd directdebit-iq
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows PowerShell
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Generate synthetic payment data

```bash
python data/generate_data.py
```

This creates:

```text
data/raw/payments.csv
data/payments.db
```

### 5. Run SQL analytics

```bash
python src/sql_runner.py
```

This exports CSV analysis outputs to:

```text
data/processed/sql_outputs/
```

### 6. Train the ML model

```bash
python src/train.py
```

This creates:

```text
models/failure_predictor.pkl
models/failure_predictor_metrics.json
models/failure_predictor_feature_importance.csv
```

### 7. Launch the Streamlit dashboard

```bash
streamlit run streamlit_app.py
```

---

## SQL Analyses

| SQL file | Purpose |
|---|---|
| `01_monthly_success_rates.sql` | Tracks monthly total payments, success rate, failures, and month-over-month change |
| `02_merchant_cohort_analysis.sql` | Finds merchant and mandate-age combinations with weak payment performance |
| `03_high_risk_customers.sql` | Scores customers by failure count, failure rate, and failed amount |
| `04_bank_country_analysis.sql` | Compares success rate by bank country and bank type, including common failure days |

Run all SQL analyses with:

```bash
python src/sql_runner.py
```

Or use the **📈 SQL Analytics** page inside the Streamlit dashboard.

---

## Dashboard Pages

### 📊 Executive Dashboard
Portfolio-level KPIs, monthly success trends, failure distribution by bank country, and highest-risk merchants.

### 🔮 Predict Payment Failures
Upload upcoming scheduled payments and identify high-risk payments before collection.

### 🔄 Retry Recommendations
Prioritise high-risk or failed payments, recommend future retry dates, and estimate recoverable value.

### 🧠 Why Did It Fail?
Explainability page with SHAP-style reasoning and plain-English failure drivers.

### 📈 SQL Analytics
Interactive charts and raw SQL result tables for stakeholder analysis.

---

## Screenshots

> Add screenshots after deploying the dashboard.

| Page | Screenshot |
|---|---|
| Executive Dashboard | `docs/screenshots/01_executive_dashboard.png` |
| Predict Payment Failures | `docs/screenshots/02_prediction_page.png` |
| Retry Recommendations | `docs/screenshots/03_retry_recommendations.png` |
| Explainability | `docs/screenshots/04_explainability.png` |
| SQL Analytics | `docs/screenshots/05_sql_analytics.png` |

---

## Live Demo

Live demo link: **Coming soon**  
Streamlit Cloud placeholder: `https://your-directdebit-iq-demo.streamlit.app/`

---

## Testing

Run the full test suite:

```bash
pytest -q
```

Current tests validate:

- Data generation columns and row count
- Realistic success rate
- Rolling feature creation
- Leakage-safe historical features
- Model training and prediction
- Retry recommendation output
- SQL query execution
- Future-dated recommendation dates

---

## Future Improvements

- Real-time scoring API with FastAPI
- Kafka integration for streaming payment events
- A/B testing framework for retry strategies
- Monitoring dashboard for model drift and payment success drift
- More advanced SHAP explanations for operational users
- dbt production model documentation and lineage
- Automated data quality checks before model training

---

## Portfolio Positioning

DirectDebit IQ is designed to show end-to-end capability across data analytics, machine learning, SQL, product thinking, business problem framing, dashboarding, and deployment readiness.

It is especially relevant for roles such as:

- Data Analyst
- BI Analyst
- Product Analyst
- Junior Data Scientist
- Payments Analyst
- Risk Analytics Analyst
- AI Automation / Operations Analytics Specialist
