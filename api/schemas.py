"""Pydantic contracts for the operational action API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class PaymentInput(BaseModel):
    payment_id: str
    merchant_id: str = "M001"
    customer_id: str = "C0001"
    payment_amount: float = Field(gt=0)
    currency: str = "GBP"
    payment_date: date
    mandate_age_days: int = Field(default=90, ge=0)
    previous_failure_count: int = Field(default=0, ge=0)
    bank_country: str = "GB"
    bank_type: str = "high_street"
    estimated_balance_band: str = "medium"
    days_since_last_success: int = Field(default=30, ge=0)
    payment_type: str = "recurring"


class PredictionResponse(BaseModel):
    prediction_id: str
    payment_id: str
    risk_probability: float
    risk_level: str
    threshold: float
    prediction_version: str
    recommended_action: str
    approval_action_id: str | None = None
    trace_id: str


class RetryRecommendationRequest(BaseModel):
    prediction_id: str
    idempotency_key: str = Field(min_length=8, max_length=160)


class RetryRecommendationResponse(BaseModel):
    action_id: str
    payment_id: str
    status: str
    recommended_retry_date: date
    expected_success_probability: float
    expected_recovery_amount: float
    requires_human_approval: bool = True
    trace_id: str


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    reason: str = Field(min_length=3, max_length=500)


class ExecuteActionRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=160)


class ActionResponse(BaseModel):
    action_id: str
    status: str
    reviewer_decision: str | None
    action_outcome: str | None
    trace_id: str


class AgentPlanRequest(BaseModel):
    prediction_id: str


class AgentPlanStep(BaseModel):
    tool: str
    reason: str
    requires_approval: bool


class AgentPlanResponse(BaseModel):
    prediction_id: str
    summary: str
    steps: list[AgentPlanStep]
    source: str
    trace_id: str


class TraceResponse(BaseModel):
    trace_id: str
    spans: list[dict]


class AuditResponse(BaseModel):
    id: str
    actor: str
    event_type: str
    entity_type: str
    entity_id: str
    details: dict
    trace_id: str
    created_at: datetime
