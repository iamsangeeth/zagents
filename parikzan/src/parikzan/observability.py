"""Execution telemetry for Blogging Agent jobs."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from time import perf_counter
from typing import Any
from uuid import UUID

from .clients import PostgresClient


_SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
}
_MAX_VALUE_LENGTH = 1000


def _safe_payload(value: Any, *, key: str | None = None) -> Any:
    """Redact credentials and bound telemetry payload size."""
    if key and any(part in key.lower() for part in _SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(name): _safe_payload(item, key=str(name)) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_payload(item) for item in value[:50]]
    if isinstance(value, str):
        return value if len(value) <= _MAX_VALUE_LENGTH else value[:_MAX_VALUE_LENGTH] + "…"
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)[:_MAX_VALUE_LENGTH]


class MetricsRecorder:
    """Record bounded, non-secret agent execution telemetry."""

    def __init__(self, database: PostgresClient | None = None) -> None:
        self.database = database or PostgresClient()

    def event(
        self,
        *,
        job_id: UUID | None,
        event_type: str,
        step: str | None = None,
        attempt: int = 1,
        duration_ms: int | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> UUID:
        """Record one sanitized event."""
        return self.database.record_event(
            job_id=job_id,
            event_type=event_type,
            step=step,
            attempt=attempt,
            duration_ms=duration_ms,
            payload=_safe_payload(payload or {}),
        )

    @contextmanager
    def observe_step(
        self,
        *,
        job_id: UUID,
        step: str,
        attempt: int = 1,
        payload: Mapping[str, Any] | None = None,
    ) -> Iterator[None]:
        """Record successful or failed step with elapsed milliseconds."""
        started = perf_counter()
        try:
            yield
        except Exception as error:
            self.event(
                job_id=job_id,
                event_type="error",
                step=step,
                attempt=attempt,
                duration_ms=_elapsed_ms(started),
                payload={**(payload or {}), "error_type": type(error).__name__},
            )
            raise
        else:
            self.event(
                job_id=job_id,
                event_type="step_completed",
                step=step,
                attempt=attempt,
                duration_ms=_elapsed_ms(started),
                payload=payload,
            )

    def job_metrics(self, job_id: UUID) -> dict[str, Any]:
        """Return aggregate metrics from PostgreSQL."""
        return self.database.job_metrics(job_id)


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


__all__ = ["MetricsRecorder"]
