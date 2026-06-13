"""Thin Streamlit dashboard entrypoint.

Page implementations live in ``app.pages``. Shared operational logic belongs
in ``src`` or ``api`` modules so it can be reused by the dashboard, API, tests,
and automation workflows.
"""

from app.pages import main

__all__ = ["main"]
