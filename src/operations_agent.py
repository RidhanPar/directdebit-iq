"""Optional LLM planning agent with a deterministic, approval-safe fallback."""

from __future__ import annotations

import logging
import os

from pydantic import BaseModel

logger = logging.getLogger("directdebit_iq.agent")
ALLOWED_TOOLS = {
    "score_payment",
    "create_retry_recommendation",
    "request_human_approval",
    "execute_retry",
}


class PlanStep(BaseModel):
    tool: str
    reason: str
    requires_approval: bool


class OperationsPlan(BaseModel):
    summary: str
    steps: list[PlanStep]


def validate_plan(plan: OperationsPlan) -> OperationsPlan:
    """Reject plans that bypass the approved tool catalog or approval gate."""
    tools = [step.tool for step in plan.steps]
    if not tools or any(tool not in ALLOWED_TOOLS for tool in tools):
        raise ValueError("Plan contains an unknown or empty tool sequence")
    if "execute_retry" in tools:
        approval_index = (
            tools.index("request_human_approval")
            if "request_human_approval" in tools
            else -1
        )
        execute_index = tools.index("execute_retry")
        if approval_index < 0 or approval_index > execute_index:
            raise ValueError("Retry execution must follow human approval")
        if not plan.steps[execute_index].requires_approval:
            raise ValueError("Retry execution must be marked as approval-required")
    return plan


def _fallback_plan(
    payment_id: str, probability: float, risk_level: str, recommendation: str
) -> OperationsPlan:
    steps = [
        PlanStep(
            tool="score_payment",
            reason="Persist the model score and decision threshold.",
            requires_approval=False,
        )
    ]
    if probability >= 0.30:
        steps.extend(
            [
                PlanStep(
                    tool="create_retry_recommendation",
                    reason="Convert risk into a value-ranked retry recommendation.",
                    requires_approval=False,
                ),
                PlanStep(
                    tool="request_human_approval",
                    reason="A reviewer must approve customer-impacting retry actions.",
                    requires_approval=True,
                ),
                PlanStep(
                    tool="execute_retry",
                    reason="Schedule the approved retry using an idempotency key.",
                    requires_approval=True,
                ),
            ]
        )
    return OperationsPlan(
        summary=f"{payment_id} is {risk_level} risk at {probability:.1%}. {recommendation}",
        steps=steps,
    )


def build_agent_plan(
    payment_id: str, probability: float, risk_level: str, recommendation: str
) -> tuple[str, list[dict], str]:
    """Return an OpenAI structured plan when configured, otherwise a deterministic plan."""
    fallback = _fallback_plan(payment_id, probability, risk_level, recommendation)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return (
            fallback.summary,
            [step.model_dump() for step in fallback.steps],
            "deterministic_fallback",
        )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=20, max_retries=2)
        response = client.responses.parse(
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            input=[
                {
                    "role": "system",
                    "content": (
                        "Plan direct-debit operations using only score_payment, create_retry_recommendation, "
                        "request_human_approval, and execute_retry. Never execute a retry without approval."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Payment {payment_id}: probability={probability}, risk={risk_level}, "
                        f"recommendation={recommendation}"
                    ),
                },
            ],
            text_format=OperationsPlan,
        )
        plan = response.output_parsed
        if plan is None:
            raise ValueError("Model returned no structured plan")
        validate_plan(plan)
        return (
            plan.summary,
            [step.model_dump() for step in plan.steps],
            "openai_structured_plan",
        )
    except Exception as exc:
        logger.warning(
            "Agent provider/validation failure; using safe fallback: %s",
            type(exc).__name__,
        )
        return (
            fallback.summary,
            [step.model_dump() for step in fallback.steps],
            "fallback_after_provider_failure",
        )
