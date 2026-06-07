# Streamlit Cloud Deployment Fix

## Issue

Streamlit Cloud deployment failed during dependency installation because the app was built with Python 3.14.5:

```text
Using Python 3.14.5 environment
Collecting pandas==2.2.2
Installing build dependencies...
Error during processing dependencies
```

This happens because the project dependencies were developed and tested on Python 3.10/3.11, while Streamlit Cloud selected Python 3.14. Some packages, especially pandas/scikit-learn/xgboost/shap, may not have compatible prebuilt wheels for the selected Python version and can fail while building from source.

## Required Fix

Use Python 3.11 for Streamlit Cloud.

This repository includes:

```text
runtime.txt        -> python-3.11
.python-version    -> 3.11.9
```

## Streamlit Cloud Settings

When deploying or redeploying:

1. Open the app in Streamlit Cloud.
2. Go to **Manage app**.
3. Open **Settings**.
4. Under **Python version**, select **3.11**.
5. Save and reboot the app.

If the app still uses Python 3.14, delete the Streamlit Cloud app and create a fresh deployment with Python 3.11 selected in **Advanced settings**.

## Main file path

Use:

```text
streamlit_app.py
```

## Install dependencies locally before pushing

```powershell
python --version
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

## After committing the fix

```powershell
git add runtime.txt .python-version requirements.txt docs/STREAMLIT_DEPLOYMENT_FIX.md
git commit -m "Fix Streamlit Cloud Python version"
git push
```

Then reboot the Streamlit Cloud app.
