"""Authenticated DirectDebit IQ score-to-action API."""

from __future__ import annotations

import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from api.auth import Actor, get_actor, issue_token, require_roles
from api.database import Base, engine, get_db
from api.models import AuditEvent, PredictionAudit, RetryAction, TraceEvent
from api.observability import log_event, trace_id_context
from api.schemas import (
    ActionResponse,
    AgentPlanRequest,
    AgentPlanResponse,
    AuditResponse,
    DecisionRequest,
    ExecuteActionRequest,
    PaymentInput,
    PredictionResponse,
    RetryRecommendationRequest,
    RetryRecommendationResponse,
    TokenResponse,
    TraceResponse,
)
from api.service import (
    decide_action,
    execute_action,
    get_or_create_recommendation,
    plan_for_prediction,
    predict_and_audit,
)

Base.metadata.create_all(bind=engine)
app = FastAPI(
    title="DirectDebit IQ Action API",
    version="1.0.0",
    description="Auditable prediction-to-approval-to-retry workflow service.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://directdebit-iq.streamlit.app", "http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_requests(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    token = trace_id_context.set(trace_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        log_event(
            "http_request",
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return response
    finally:
        trace_id_context.reset(token)


@app.get("/health")
def health():
    return {"status": "ok", "service": "directdebit-iq-action-api"}


@app.post("/auth/token", response_model=TokenResponse)
def token(form: OAuth2PasswordRequestForm = Depends()):
    access_token, role = issue_token(form)
    return TokenResponse(access_token=access_token, role=role)


@app.post("/predictions", response_model=PredictionResponse)
def create_prediction(
    payment: PaymentInput,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_roles("operator", "reviewer", "admin")),
):
    prediction, action = predict_and_audit(db, payment, actor)
    return PredictionResponse(
        prediction_id=prediction.id,
        payment_id=prediction.payment_id,
        risk_probability=prediction.risk_probability,
        risk_level=prediction.risk_level,
        threshold=prediction.threshold,
        prediction_version=prediction.prediction_version,
        recommended_action=prediction.recommended_action,
        approval_action_id=action.id if action else None,
        trace_id=prediction.trace_id,
    )


@app.get("/predictions/{prediction_id}", response_model=PredictionResponse)
def get_prediction(
    prediction_id: str,
    db: Session = Depends(get_db),
    _: Actor = Depends(get_actor),
):
    prediction = db.get(PredictionAudit, prediction_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    action = (
        db.query(RetryAction).filter(RetryAction.prediction_id == prediction.id).first()
    )
    return PredictionResponse(
        prediction_id=prediction.id,
        payment_id=prediction.payment_id,
        risk_probability=prediction.risk_probability,
        risk_level=prediction.risk_level,
        threshold=prediction.threshold,
        prediction_version=prediction.prediction_version,
        recommended_action=prediction.recommended_action,
        approval_action_id=action.id if action else None,
        trace_id=prediction.trace_id,
    )


@app.post("/retry-recommendations", response_model=RetryRecommendationResponse)
def create_retry_recommendation(
    payload: RetryRecommendationRequest,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_roles("operator", "admin")),
):
    prediction = db.get(PredictionAudit, payload.prediction_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    action = get_or_create_recommendation(
        db, prediction, payload.idempotency_key, actor
    )
    return RetryRecommendationResponse(
        action_id=action.id,
        payment_id=action.payment_id,
        status=action.status,
        trace_id=action.trace_id,
        **action.recommendation,
    )


@app.get("/actions")
def list_actions(
    db: Session = Depends(get_db),
    _: Actor = Depends(get_actor),
):
    return (
        db.query(RetryAction).order_by(RetryAction.created_at.desc()).limit(100).all()
    )


@app.post("/actions/{action_id}/decision", response_model=ActionResponse)
def review_action(
    action_id: str,
    payload: DecisionRequest,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_roles("reviewer", "admin")),
):
    action = db.get(RetryAction, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    action = decide_action(db, action, payload.decision, payload.reason, actor)
    return ActionResponse(
        action_id=action.id,
        status=action.status,
        reviewer_decision=action.reviewer_decision,
        action_outcome=action.action_outcome,
        trace_id=action.trace_id,
    )


@app.post("/actions/{action_id}/execute", response_model=ActionResponse)
def run_action(
    action_id: str,
    payload: ExecuteActionRequest,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_roles("operator", "admin")),
):
    action = db.get(RetryAction, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    action = execute_action(db, action, payload.idempotency_key, actor)
    return ActionResponse(
        action_id=action.id,
        status=action.status,
        reviewer_decision=action.reviewer_decision,
        action_outcome=action.action_outcome,
        trace_id=action.trace_id,
    )


@app.post("/agent/plan", response_model=AgentPlanResponse)
def agent_plan(
    payload: AgentPlanRequest,
    db: Session = Depends(get_db),
    _: Actor = Depends(get_actor),
):
    prediction = db.get(PredictionAudit, payload.prediction_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    summary, steps, source = plan_for_prediction(prediction)
    return AgentPlanResponse(
        prediction_id=prediction.id,
        summary=summary,
        steps=steps,
        source=source,
        trace_id=prediction.trace_id,
    )


@app.get("/traces/{trace_id}", response_model=TraceResponse)
def get_trace(
    trace_id: str,
    db: Session = Depends(get_db),
    _: Actor = Depends(get_actor),
):
    spans = (
        db.query(TraceEvent)
        .filter(TraceEvent.trace_id == trace_id)
        .order_by(TraceEvent.created_at)
        .all()
    )
    return TraceResponse(
        trace_id=trace_id,
        spans=[
            {
                "span_name": span.span_name,
                "status": span.status,
                "latency_ms": span.latency_ms,
                "metadata": span.metadata_json,
            }
            for span in spans
        ],
    )


@app.get("/audit", response_model=list[AuditResponse])
def list_audit(
    db: Session = Depends(get_db),
    _: Actor = Depends(require_roles("reviewer", "admin")),
):
    return db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200).all()
