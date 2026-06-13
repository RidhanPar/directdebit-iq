"""SQLAlchemy database configuration for the operational action ledger."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = f"sqlite:///{(PROJECT_ROOT / 'data' / 'actions.db').as_posix()}"


def normalize_database_url(value: str) -> str:
    """Make Render-style PostgreSQL URLs explicit for SQLAlchemy."""
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg2://", 1)
    return value


DATABASE_URL = normalize_database_url(
    os.getenv("ACTION_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or DEFAULT_DATABASE_URL
)
CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=CONNECT_ARGS, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
