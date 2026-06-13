"""Run deterministic score-to-action governance evaluations."""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["ACTION_DATABASE_URL"] = "sqlite:///./data/evaluation_actions.db"
os.environ["JWT_SECRET"] = "evaluation-only-secret"
os.environ.pop("OPENAI_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from api.database import Base, engine  # noqa: E402
from api.main import app  # noqa: E402

CASES_PATH = ROOT / "evaluations" / "action_workflow_cases.json"
RESULTS_PATH = ROOT / "evaluations" / "results" / "action_workflow_results.json"


def token(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/auth/token", data={"username": username, "password": f"{username}-demo"}
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def payment(payment_id: str, high_risk: bool) -> dict:
    return {
        "payment_id": payment_id,
        "merchant_id": "M014",
        "customer_id": "C0042",
        "payment_amount": 1000 if high_risk else 100,
        "currency": "GBP",
        "payment_date": date(2026, 6, 16).isoformat(),
        "mandate_age_days": 10 if high_risk else 300,
        "previous_failure_count": 5 if high_risk else 0,
        "bank_country": "GB",
        "bank_type": "challenger",
        "estimated_balance_band": "low" if high_risk else "high",
        "days_since_last_success": 75 if high_risk else 10,
        "payment_type": "recurring",
    }


def run() -> dict:
    cases = {
        case["id"]: case for case in json.loads(CASES_PATH.read_text(encoding="utf-8"))
    }
    results: list[dict] = []

    def record(case_id: str, passed: bool, evidence: str) -> None:
        results.append({**cases[case_id], "passed": passed, "evidence": evidence})

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    operator = token(client, "operator")
    reviewer = token(client, "reviewer")

    high = client.post(
        "/predictions", headers=operator, json=payment("EVAL-HIGH", True)
    ).json()
    low = client.post(
        "/predictions", headers=operator, json=payment("EVAL-LOW", False)
    ).json()
    action_id = high["approval_action_id"]
    key = f"prediction:{high['prediction_id']}"

    record(
        "high-risk-routes-to-approval",
        bool(action_id),
        "pending approval action created",
    )
    record(
        "low-risk-does-not-create-action",
        low["approval_action_id"] is None,
        "approval_action_id is null",
    )

    operator_review = client.post(
        f"/actions/{action_id}/decision",
        headers=operator,
        json={"decision": "approved", "reason": "Self approval must fail."},
    )
    record(
        "rbac-enforced",
        operator_review.status_code == 403,
        f"HTTP {operator_review.status_code}",
    )

    unapproved = client.post(
        f"/actions/{action_id}/execute", headers=operator, json={"idempotency_key": key}
    )
    record(
        "approval-gate-enforced",
        unapproved.status_code == 409,
        f"HTTP {unapproved.status_code}",
    )

    client.post(
        f"/actions/{action_id}/decision",
        headers=reviewer,
        json={"decision": "approved", "reason": "Evaluation reviewer approved retry."},
    ).raise_for_status()
    first = client.post(
        f"/actions/{action_id}/execute", headers=operator, json={"idempotency_key": key}
    )
    second = client.post(
        f"/actions/{action_id}/execute", headers=operator, json={"idempotency_key": key}
    )
    record(
        "execution-is-idempotent",
        first.status_code == 200 and first.json() == second.json(),
        first.json().get("action_outcome", "missing"),
    )

    audit = client.get("/audit", headers=reviewer).json()
    trace = client.get(f"/traces/{high['trace_id']}", headers=reviewer).json()
    event_types = {event["event_type"] for event in audit}
    evidence_complete = {
        "prediction.created",
        "retry.reviewed",
        "retry.executed",
    }.issubset(event_types) and bool(trace["spans"])
    record(
        "audit-and-trace-complete",
        evidence_complete,
        f"events={sorted(event_types)}; spans={len(trace['spans'])}",
    )

    plan = client.post(
        "/agent/plan", headers=operator, json={"prediction_id": high["prediction_id"]}
    ).json()
    tools = [step["tool"] for step in plan["steps"]]
    approval_safe = (
        "request_human_approval" in tools
        and "execute_retry" in tools
        and tools.index("request_human_approval") < tools.index("execute_retry")
    )
    record(
        "agent-plan-is-approval-safe",
        approval_safe,
        f"source={plan['source']}; tools={tools}",
    )

    passed = sum(result["passed"] for result in results)
    report = {
        "suite": "action-workflow-governance",
        "passed": passed,
        "total": len(results),
        "score_percent": round(passed / len(results) * 100, 1),
        "results": results,
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] == result["total"] else 1)
