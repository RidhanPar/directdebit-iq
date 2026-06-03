"""Tests for synthetic data generation."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from data.generate_data import generate_payments


def test_generate_payments_shape_and_columns():
    df = generate_payments(n_rows=1_000, seed=123)
    assert df.shape[0] == 1_000
    assert df.shape[1] == 16
    assert "payment_status" in df.columns
    assert set(df["payment_status"].unique()).issubset({"success", "failed"})


def test_generated_failure_rate_is_realistic():
    df = generate_payments(n_rows=5_000, seed=123)
    failure_rate = (df["payment_status"] == "failed").mean()
    assert 0.11 <= failure_rate <= 0.19


def test_risk_patterns_have_signal():
    df = generate_payments(n_rows=8_000, seed=123)
    high_previous_failure_rate = df.loc[df["previous_failure_count"] > 2, "payment_status"].eq("failed").mean()
    zero_previous_failure_rate = df.loc[df["previous_failure_count"] == 0, "payment_status"].eq("failed").mean()
    assert high_previous_failure_rate > zero_previous_failure_rate
