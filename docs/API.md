# Action API

The FastAPI service converts a risk score into a governed operational workflow. Interactive OpenAPI documentation is available at `/docs` whenever the API is running.

## Local Run

```bash
uvicorn api.main:app --reload --port 8000
```

The local demo identities are:

| User | Role | Local-only password |
|---|---|---|
| `operator` | Create predictions and execute approved actions | `operator-demo` |
| `reviewer` | Approve/reject and inspect the audit ledger | `reviewer-demo` |
| `admin` | All operations | `admin-demo` |

Use environment-specific passwords and a strong `JWT_SECRET` outside local demonstrations.

## Endpoint Map

| Method and path | Required role | Purpose |
|---|---|---|
| `GET /health` | Public | Deployment health check |
| `POST /auth/token` | Public credentials | Issue a signed JWT |
| `POST /predictions` | Operator, reviewer, admin | Score and persist a payment |
| `GET /predictions/{id}` | Authenticated | Retrieve prediction evidence |
| `POST /retry-recommendations` | Operator, admin | Create an idempotent recommendation |
| `GET /actions` | Authenticated | Inspect the action queue |
| `POST /actions/{id}/decision` | Reviewer, admin | Record approval or rejection |
| `POST /actions/{id}/execute` | Operator, admin | Execute an approved retry |
| `POST /agent/plan` | Authenticated | Produce an approval-safe structured plan |
| `GET /traces/{trace_id}` | Authenticated | Inspect persisted spans |
| `GET /audit` | Reviewer, admin | Inspect governance events |

## Prediction Response

```json
{
  "prediction_id": "uuid",
  "payment_id": "PAY-1001",
  "risk_probability": 0.62,
  "risk_level": "high",
  "threshold": 0.3,
  "prediction_version": "directdebit-risk-v1",
  "recommended_action": "Send pre-collection reminder...",
  "approval_action_id": "uuid",
  "trace_id": "uuid"
}
```

An action starts as `pending`. Only `reviewer` or `admin` can change it to `approved` or `rejected`. Execution fails with HTTP `409` unless the action is approved and the caller supplies the action's idempotency key.
