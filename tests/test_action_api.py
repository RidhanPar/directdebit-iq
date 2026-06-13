"""Integration tests for the auditable score-to-action API."""

from __future__ import annotations

import os
from datetime import date

os.environ["ACTION_DATABASE_URL"] = "sqlite:///./data/test_actions.db"
os.environ["JWT_SECRET"] = "not-a-production-secret"
os.environ.pop("OPENAI_API_KEY", None)

import pytest
from fastapi.testclient import TestClient

from api.database import Base, SessionLocal, engine
from api.main import app
from api.models import AuditEvent, RetryAction


@pytest.fixture(scope="session", autouse=True)
def action_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    return TestClient(app)


def _headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/auth/token",
        data={"username": username, "password": f"{username}-{'demo'}"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _high_risk_payment() -> dict:
    return {
        "payment_id": "LIVE-TEST-001",
        "merchant_id": "M014",
        "customer_id": "C0042",
        "payment_amount": 1000,
        "currency": "GBP",
        "payment_date": date(2026, 6, 15).isoformat(),
        "mandate_age_days": 10,
        "previous_failure_count": 5,
        "bank_country": "GB",
        "bank_type": "challenger",
        "estimated_balance_band": "low",
        "days_since_last_success": 75,
        "payment_type": "recurring",
    }


def test_prediction_requires_authentication(client):
    response = client.post("/predictions", json=_high_risk_payment())
    assert response.status_code == 401


def test_high_risk_prediction_creates_auditable_approval_action(client):
    response = client.post(
        "/predictions", headers=_headers(client, "operator"), json=_high_risk_payment()
    )
    assert response.status_code == 200
    result = response.json()
    assert result["risk_probability"] >= result["threshold"]
    assert result["approval_action_id"]
    assert result["prediction_version"]
    assert result["trace_id"]


def test_reviewer_approval_and_idempotent_execution(client):
    prediction = client.post(
        "/predictions", headers=_headers(client, "operator"), json=_high_risk_payment()
    ).json()
    action_id = prediction["approval_action_id"]
    idempotency_key = f"prediction:{prediction['prediction_id']}"

    review = client.post(
        f"/actions/{action_id}/decision",
        headers=_headers(client, "reviewer"),
        json={
            "decision": "approved",
            "reason": "Validated retry timing and customer impact.",
        },
    )
    assert review.status_code == 200
    assert review.json()["reviewer_decision"] == "approved"

    first = client.post(
        f"/actions/{action_id}/execute",
        headers=_headers(client, "operator"),
        json={"idempotency_key": idempotency_key},
    )
    second = client.post(
        f"/actions/{action_id}/execute",
        headers=_headers(client, "operator"),
        json={"idempotency_key": idempotency_key},
    )
    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["status"] == "executed"
    assert first.json()["action_outcome"].startswith("retry_scheduled:")


def test_unapproved_action_cannot_execute(client):
    prediction = client.post(
        "/predictions", headers=_headers(client, "operator"), json=_high_risk_payment()
    ).json()
    response = client.post(
        f"/actions/{prediction['approval_action_id']}/execute",
        headers=_headers(client, "operator"),
        json={"idempotency_key": f"prediction:{prediction['prediction_id']}"},
    )
    assert response.status_code == 409


def test_agent_plan_uses_approval_safe_tools(client):
    prediction = client.post(
        "/predictions", headers=_headers(client, "operator"), json=_high_risk_payment()
    ).json()
    response = client.post(
        "/agent/plan",
        headers=_headers(client, "operator"),
        json={"prediction_id": prediction["prediction_id"]},
    )
    assert response.status_code == 200
    result = response.json()
    tools = {step["tool"] for step in result["steps"]}
    assert {"score_payment", "request_human_approval", "execute_retry"}.issubset(tools)
    assert result["source"] == "deterministic_fallback"


def test_audit_ledger_records_prediction_review_and_execution(client):
    operator = _headers(client, "operator")
    reviewer = _headers(client, "reviewer")
    prediction = client.post(
        "/predictions", headers=operator, json=_high_risk_payment()
    ).json()
    action_id = prediction["approval_action_id"]
    client.post(
        f"/actions/{action_id}/decision",
        headers=reviewer,
        json={"decision": "approved", "reason": "Operational review complete."},
    )
    client.post(
        f"/actions/{action_id}/execute",
        headers=operator,
        json={"idempotency_key": f"prediction:{prediction['prediction_id']}"},
    )

    response = client.get("/audit", headers=reviewer)
    event_types = {event["event_type"] for event in response.json()}
    assert {"prediction.created", "retry.reviewed", "retry.executed"}.issubset(
        event_types
    )

    db = SessionLocal()
    action = db.get(RetryAction, action_id)
    assert action.reviewer_decision == "approved"
    assert action.action_outcome.startswith("retry_scheduled:")
    assert db.query(AuditEvent).count() >= 3
    db.close()
