# Contributing

## Development Workflow

1. Create a focused branch from `main`.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run `pytest -q`.
4. Run `python -m py_compile streamlit_app.py app/dashboard.py src/*.py`.
5. Launch `streamlit run streamlit_app.py` and review the affected workflow.
6. Open a pull request describing the user impact, validation, and limitations.

Keep generated data, model artifacts, secrets, and local MLflow databases out of commits.

## Analytical Changes

Document the data grain, available-at-scoring-time features, leakage controls, validation method, operating threshold, and business assumptions. New decision logic should remain explainable and reviewable.
