"""
DirectDebit IQ — SQLite SQL Analytics Runner

This module provides a reusable class for running the project's SQL analysis
files against the SQLite payments database.

Example:
    python src/sql_runner.py

Or from Python:
    from src.sql_runner import SQLAnalytics

    analytics = SQLAnalytics.connect("data/payments.db")
    results = analytics.run_all_analyses()
    analytics.export_results("data/processed/sql_outputs")
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, Optional, Union

import pandas as pd


PathLike = Union[str, Path]


class SQLAnalytics:
    """Run SQL analytics queries against the DirectDebit IQ SQLite database."""

    DEFAULT_ANALYSES = {
        "monthly_success_rates": "01_monthly_success_rates.sql",
        "merchant_cohort_analysis": "02_merchant_cohort_analysis.sql",
        "high_risk_customers": "03_high_risk_customers.sql",
        "bank_country_analysis": "04_bank_country_analysis.sql",
    }

    def __init__(
        self,
        db_path: Optional[PathLike] = None,
        sql_dir: Optional[PathLike] = None,
    ) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.db_path = Path(db_path) if db_path else self.project_root / "data" / "payments.db"
        self.sql_dir = Path(sql_dir) if sql_dir else self.project_root / "sql"
        self.connection: Optional[sqlite3.Connection] = None
        self.results: Dict[str, pd.DataFrame] = {}

    @classmethod
    def connect(cls, db_path: PathLike) -> "SQLAnalytics":
        """
        Create a SQLAnalytics instance and connect to SQLite.

        Args:
            db_path: Path to the SQLite database file.

        Returns:
            Connected SQLAnalytics instance.
        """
        analytics = cls(db_path=db_path)
        analytics._connect()
        return analytics

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection if one does not already exist."""
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"SQLite database not found at {self.db_path}. "
                "Run data/generate_data.py first to create data/payments.db."
            )

        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row

        return self.connection

    def run_query(self, sql_file: PathLike) -> pd.DataFrame:
        """
        Read and execute a SQL file, returning the result as a pandas DataFrame.

        Args:
            sql_file: SQL filename inside the sql/ folder, or a full path.

        Returns:
            Query result as a pandas DataFrame.
        """
        sql_path = Path(sql_file)
        if not sql_path.is_absolute():
            sql_path = self.sql_dir / sql_path

        if not sql_path.exists():
            raise FileNotFoundError(f"SQL file not found: {sql_path}")

        query = sql_path.read_text(encoding="utf-8")
        connection = self._connect()
        return pd.read_sql_query(query, connection)

    def run_all_analyses(self) -> Dict[str, pd.DataFrame]:
        """
        Run all DirectDebit IQ SQL analysis files.

        Returns:
            Dictionary where keys are analysis names and values are DataFrames.
        """
        self.results = {
            analysis_name: self.run_query(sql_filename)
            for analysis_name, sql_filename in self.DEFAULT_ANALYSES.items()
        }
        return self.results

    def export_results(self, output_dir: PathLike) -> Dict[str, Path]:
        """
        Run all analyses if needed and export each result as CSV.

        Args:
            output_dir: Directory where CSV files should be saved.

        Returns:
            Dictionary where keys are analysis names and values are CSV paths.
        """
        if not self.results:
            self.run_all_analyses()

        output_path = Path(output_dir)
        if not output_path.is_absolute():
            output_path = self.project_root / output_path
        output_path.mkdir(parents=True, exist_ok=True)

        exported_files: Dict[str, Path] = {}
        for analysis_name, dataframe in self.results.items():
            csv_path = output_path / f"{analysis_name}.csv"
            dataframe.to_csv(csv_path, index=False)
            exported_files[analysis_name] = csv_path

        return exported_files

    def close(self) -> None:
        """Close the SQLite connection."""
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def __enter__(self) -> "SQLAnalytics":
        self._connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


if __name__ == "__main__":
    analytics = SQLAnalytics()
    results = analytics.run_all_analyses()

    print("DirectDebit IQ SQL analyses completed successfully.\n")
    for name, dataframe in results.items():
        print(f"{name}: {len(dataframe):,} rows")

    exported = analytics.export_results("data/processed/sql_outputs")
    print("\nExported CSV files:")
    for name, path in exported.items():
        print(f"- {name}: {path}")

    analytics.close()
