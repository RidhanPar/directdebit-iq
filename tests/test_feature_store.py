"""Tests for feature engineering."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from data.generate_data import generate_payments
from src.feature_store import add_business_features, build_model_matrix


def test_add_business_features_creates_target():
    df = generate_payments(n_rows=100, seed=42)
    featured = add_business_features(df)
    assert "is_failed" in featured.columns
    assert "is_low_balance" in featured.columns
    assert set(featured["is_failed"].unique()).issubset({0, 1})


def test_build_model_matrix_returns_aligned_x_y():
    df = generate_payments(n_rows=100, seed=42)
    X, y = build_model_matrix(df)
    assert len(X) == len(y) == 100
    assert X.shape[1] > 10
