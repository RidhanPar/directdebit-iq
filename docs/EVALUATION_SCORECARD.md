# Evaluation Scorecard

## Scope

This scorecard maps the implemented platform capabilities to concrete repository evidence. Predictive-model quality and workflow-control behavior are evaluated separately.

| Capability | Evidence |
|---|---|
| Authenticated action API | `api/main.py`, OpenAPI `/docs` |
| Authentication and RBAC | `api/auth.py`, API integration tests |
| Human approval and retry scheduling | `api/service.py`, n8n workflow |
| Audit records | Prediction, decision, and outcome models |
| Optional LLM planning | Structured approval-safe planner |
| Tracing and structured logs | Trace middleware and persisted spans |
| Cloud deployment configuration | Render Blueprint and managed PostgreSQL |
| Dashboard module boundary | Thin entrypoint, pages, automation page, API client |
| Automated governance evaluation | Seven executable control cases |
| Synthetic scenario disclosure | README, model card, business-impact memo |

## Executable Control Result

Run:

```bash
python evaluations/run_action_evaluation.py
```

The latest checked-in result is [`evaluations/results/action_workflow_results.json`](../evaluations/results/action_workflow_results.json). CI regenerates the report and fails if any declared control does not pass.

## Operational Boundary

The action service persists a simulated retry-scheduling outcome; it does not call a bank or payment processor. A real deployment still requires governed data, enterprise identity, provider integration, privacy/compliance approval, operational monitoring, and measured rollout.
