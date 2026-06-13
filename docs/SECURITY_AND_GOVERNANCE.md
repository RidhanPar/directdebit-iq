# Security and Governance

## Implemented Controls

| Risk | Implemented control | Evidence |
|---|---|---|
| Unauthorized access | Signed JWTs and role checks | `api/auth.py` |
| Self-approval or approval bypass | Separate reviewer role and execution gate | `api/main.py`, `api/service.py` |
| Duplicate retry execution | Unique idempotency key and stable repeated response | `api/models.py`, `tests/test_action_api.py` |
| Unexplained decision | Prediction version, threshold, recommendation, and inputs persisted | `api/models.py` |
| Missing accountability | Reviewer, reason, decision, and action outcome persisted | `api/models.py` |
| Weak incident evidence | Request trace IDs, JSON logs, and persisted spans | `api/observability.py` |
| Unsafe LLM plan | Pydantic structured output, fixed tool catalog, approval validation, safe fallback | `src/operations_agent.py` |
| Control regression | Seven-case governance evaluation in CI | `evaluations/run_action_evaluation.py` |

## Data and Model Boundary

- All repository data is synthetic.
- No real payment credentials or personal customer data should be committed.
- The action API demonstrates a retry scheduling outcome; it does not connect to a bank or payment processor.
- Model results and financial benefits require validation on approved historical data before operational use.

## Production Requirements

Before a real deployment, replace local demo authentication with an enterprise identity provider and short-lived scoped tokens. Add rate limiting, database migrations, encrypted backups, secret rotation, vulnerability scanning, retention policies, privacy review, fairness monitoring, alerting, and a documented rollback process.

Start in shadow mode. Require operations, risk, compliance, and security approval before enabling customer-impacting actions.
