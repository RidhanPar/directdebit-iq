"""Small service client used by the Streamlit automation evidence page."""

from __future__ import annotations

import os

import httpx


def action_api_url() -> str:
    return os.getenv(
        "DDIQ_ACTION_API_URL", os.getenv("DDIQ_API_URL", "http://localhost:8000")
    ).rstrip("/")


def action_api_health() -> tuple[str, str]:
    """Return a reviewer-friendly status and the configured API URL."""
    api_url = action_api_url()
    try:
        response = httpx.get(f"{api_url}/health", timeout=3)
        status = (
            "Healthy" if response.status_code == 200 else f"HTTP {response.status_code}"
        )
    except httpx.HTTPError:
        status = "Not connected in this Streamlit environment"
    return status, api_url
