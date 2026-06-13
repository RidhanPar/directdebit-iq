"""Request trace IDs, structured logs, and persisted spans."""

from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from contextlib import contextmanager

from sqlalchemy.orm import Session

from api.models import TraceEvent

trace_id_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)
logger = logging.getLogger("directdebit_iq.api")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def current_trace_id() -> str:
    return trace_id_context.get() or str(uuid.uuid4())


def log_event(event: str, **values) -> None:
    logger.info(json.dumps({"event": event, **values}, default=str, sort_keys=True))


@contextmanager
def traced(db: Session, span_name: str, metadata: dict | None = None):
    trace_id = current_trace_id()
    started = time.perf_counter()
    status = "success"
    try:
        yield trace_id
    except Exception:
        status = "error"
        raise
    finally:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        db.add(
            TraceEvent(
                id=str(uuid.uuid4()),
                trace_id=trace_id,
                span_name=span_name,
                status=status,
                latency_ms=latency_ms,
                metadata_json=metadata or {},
            )
        )
        log_event(
            "trace_span",
            trace_id=trace_id,
            span_name=span_name,
            status=status,
            latency_ms=latency_ms,
        )
