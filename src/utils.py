"""Shared utility functions for DirectDebit IQ."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from src import config


def ensure_project_directories() -> None:
    """Create standard project output directories."""
    for path in [config.RAW_DATA_DIR, config.PROCESSED_DATA_DIR, config.MODELS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def load_payments_csv(path: Path = config.RAW_PAYMENTS_CSV) -> pd.DataFrame:
    """Load raw payment data from CSV."""
    if not path.exists():
        raise FileNotFoundError(
            f"Payment CSV not found at {path}. Run `python data/generate_data.py` first."
        )
    return pd.read_csv(path)


def load_payments_sqlite(
    db_path: Path = config.SQLITE_DB_PATH,
    table_name: str = config.SQLITE_TABLE_NAME,
) -> pd.DataFrame:
    """Load payment data from the SQLite database."""
    if not db_path.exists():
        raise FileNotFoundError(
            f"SQLite database not found at {db_path}. Run `python data/generate_data.py` first."
        )
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)


def save_json(data: dict[str, Any], path: Path) -> None:
    """Save a dictionary as formatted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))
