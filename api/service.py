"""Prediction, recommendation, approval, and action-execution services."""

from __future__ import annotations

import os
import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.auth import Actor
from api.models import AuditEvent, PredictionAudit, RetryAction, utc_now
from api.observability import current_trace_id, traced
from api.schemas import PaymentInput
from src.operations_agent import build_agent_plan
from src.recommend import recommend_action

BUSINESS_THRESHOLD = float(os.getenv("BUSINESS_THRESHOLD", "0.30"))
PREDICTION_VERSION = os.getenv("PREDICTION_VERSION", "directdebit-risk-v1")


def _audit(
    db: Session,
    actor: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    details: dict,
) -> None:
    db.add(
        AuditEvent(
            id=str(uuid.uuid4()),
            actor=actor,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            trace_id=current_trace_id(),
        )
    )


def risk_probability(payment: PaymentInput) -> float:
    """Transparent production fallback aligned with the dashboard heuristic."""
    risk = (
        0.08
        + 0.06 * min(payment.previous_failure_count, 5)
        + 0.10 * int(payment.estimated_balance_band == "low")
        + 0.07 * int(payment.mandate_age_days < 30)
        + 0.04 * int(payment.payment_date.strftime("%A") == "Monday")
        + 0.02 * int(payment.payment_amount > 500)
        + 0.03 * int(payment.days_since_last_success > 60)
    )
    return round(min(max(risk, 0.02), 0.92), 4)


def risk_level(probability: float) -> str:
    if probability >= 0.70:
        return "critical"
    if probability >= 0.50:
        return "high"
    if probability >= BUSINESS_THRESHOLD:
        return "medium"
    return "low"


def predict_and_audit(
    db: Session, payment: PaymentInput, actor: Actor
) -> tuple[PredictionAudit, RetryAction | None]:
    with traced(db, "predict_payment", {"payment_id": payment.payment_id}):
        probability = risk_probability(payment)
        recommendation = recommend_action(payment.model_dump())
        prediction = PredictionAudit(
            id=str(uuid.uuid4()),
            payment_id=payment.payment_id,
            risk_probability=probability,
            risk_level=risk_level(probability),
            threshold=BUSINESS_THRESHOLD,
            prediction_version=PREDICTION_VERSION,
            recommended_action=recommendation,
            input_payload=payment.model_dump(mode="json"),
            trace_id=current_trace_id(),
        )
        db.add(prediction)
        action = None
        if probability >= BUSINESS_THRESHOLD:
            retry = build_retry(payment, probability)
            action = RetryAction(
                id=str(uuid.uuid4()),
                prediction_id=prediction.id,
                payment_id=payment.payment_id,
                recommendation=retry,
                requested_by=actor.username,
                idempotency_key=f"prediction:{prediction.id}",
                trace_id=current_trace_id(),
            )
            db.add(action)
        _audit(
            db,
            actor.username,
            "prediction.created",
            "prediction",
            prediction.id,
            {
                "payment_id": payment.payment_id,
                "prediction_version": PREDICTION_VERSION,
                "threshold": BUSINESS_THRESHOLD,
                "risk_probability": probability,
                "approval_action_id": action.id if action else None,
            },
        )
    db.commit()
    return prediction, action


def build_retry(payment: PaymentInput, probability: float) -> dict:
    candidate = payment.payment_date + timedelta(days=2)
    while candidate.strftime("%A") in {"Monday", "Saturday", "Sunday"}:
        candidate += timedelta(days=1)
    success_probability = round(min(max(0.96 - probability * 0.55, 0.35), 0.92), 4)
    return {
        "recommended_retry_date": candidate.isoformat(),
        "expected_success_probability": success_probability,
        "expected_recovery_amount": round(
            payment.payment_amount * success_probability, 2
        ),
    }


def get_or_create_recommendation(
    db: Session, prediction: PredictionAudit, idempotency_key: str, actor: Actor
) -> RetryAction:
    existing = (
        db.query(RetryAction)
        .filter(RetryAction.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        return existing
    payment = PaymentInput(**prediction.input_payload)
    action = RetryAction(
        id=str(uuid.uuid4()),
        prediction_id=prediction.id,
        payment_id=prediction.payment_id,
        recommendation=build_retry(payment, prediction.risk_probability),
        requested_by=actor.username,
        idempotency_key=idempotency_key,
        trace_id=current_trace_id(),
    )
    db.add(action)
    _audit(
        db,
        actor.username,
        "retry.requested",
        "retry_action",
        action.id,
        action.recommendation,
    )
    db.commit()
    return action


def decide_action(
    db: Session, action: RetryAction, decision: str, reason: str, actor: Actor
) -> RetryAction:
    if action.status == "executed":
        raise HTTPException(
            status_code=409, detail="Executed actions cannot be reviewed again"
        )
    action.status = decision
    action.reviewer = actor.username
    action.reviewer_decision = decision
    action.review_reason = reason
    action.reviewed_at = utc_now()
    _audit(
        db,
        actor.username,
        "retry.reviewed",
        "retry_action",
        action.id,
        {"reviewer_decision": decision, "reason": reason},
    )
    db.commit()
    return action


def execute_action(
    db: Session, action: RetryAction, idempotency_key: str, actor: Actor
) -> RetryAction:
    if action.status == "executed":
        return action
    if action.status != "approved":
        raise HTTPException(
            status_code=409,
            detail="Retry action requires reviewer approval before execution",
        )
    if idempotency_key != action.idempotency_key:
        raise HTTPException(
            status_code=409, detail="Idempotency key does not match the approved action"
        )
    with traced(
        db, "execute_retry", {"action_id": action.id, "payment_id": action.payment_id}
    ):
        retry_date = action.recommendation["recommended_retry_date"]
        action.status = "executed"
        action.action_outcome = f"retry_scheduled:{retry_date}"
        action.executed_at = utc_now()
        _audit(
            db,
            actor.username,
            "retry.executed",
            "retry_action",
            action.id,
            {"action_outcome": action.action_outcome},
        )
    db.commit()
    return action


def plan_for_prediction(prediction: PredictionAudit) -> tuple[str, list[dict], str]:
    return build_agent_plan(
        payment_id=prediction.payment_id,
        probability=prediction.risk_probability,
        risk_level=prediction.risk_level,
        recommendation=prediction.recommended_action,
    )
