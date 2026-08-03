"""Small PostgreSQL client for job and artifact persistence."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ..config import PostgresSettings, settings


class PostgresClient:
    """Short-lived connection client for transactional agent operations."""

    def __init__(self, config: PostgresSettings | None = None) -> None:
        self.config = config or settings.postgres

    @property
    def dsn(self) -> str:
        """Return psycopg-compatible DSN from config URL."""
        return self.config.url.replace("postgresql+psycopg://", "postgresql://", 1)

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection[Any]]:
        """Open one transaction and commit it when context exits cleanly."""
        with psycopg.connect(
            self.dsn,
            connect_timeout=self.config.timeout_seconds,
            row_factory=dict_row,
        ) as connection:
            yield connection

    def execute(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> int:
        """Execute one parameterized statement and return affected row count."""
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.rowcount

    def fetch_one(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Execute query and return one row as a dictionary."""
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                row = cursor.fetchone()
                return dict(row) if row is not None else None

    def fetch_all(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute query and return all rows as dictionaries."""
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

    def create_job(
        self,
        input_json: Mapping[str, Any],
        *,
        job_type: str = "blog",
        model_name: str | None = None,
        prompt_version: str | None = None,
    ) -> UUID:
        """Create queued job and return its database identifier."""
        row = self.fetch_one(
            """
            INSERT INTO content_jobs
                (job_type, input_json, model_name, prompt_version)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (job_type, Jsonb(dict(input_json)), model_name, prompt_version),
        )
        if row is None:
            raise RuntimeError("PostgreSQL did not return created job id")
        return row["id"]

    def update_job_status(
        self,
        job_id: UUID,
        status: str,
        *,
        current_step: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> bool:
        """Update job state; return false when job does not exist."""
        row_count = self.execute(
            """
            UPDATE content_jobs
            SET status = %s,
                current_step = %s,
                error_code = %s,
                error_message = %s,
                completed_at = CASE
                    WHEN %s IN ('published', 'failed', 'dead_letter') THEN now()
                    ELSE completed_at
                END
            WHERE id = %s
            """,
            (
                status,
                current_step,
                error_code,
                error_message,
                status,
                job_id,
            ),
        )
        return row_count == 1

    def save_job_output(self, job_id: UUID, output: Mapping[str, Any]) -> bool:
        """Persist accumulated runtime context for job inspection."""
        return self.execute(
            """
            UPDATE content_jobs
            SET output_json = %s
            WHERE id = %s
            """,
            (Jsonb(dict(output)), job_id),
        ) == 1

    def record_event(
        self,
        *,
        job_id: UUID | None,
        event_type: str,
        step: str | None = None,
        attempt: int = 1,
        duration_ms: int | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> UUID:
        """Persist one agent execution event and return its identifier."""
        if attempt <= 0:
            raise ValueError("attempt must be greater than zero")
        if duration_ms is not None and duration_ms < 0:
            raise ValueError("duration_ms cannot be negative")
        row = self.fetch_one(
            """
            INSERT INTO agent_events
                (job_id, event_type, step, attempt, duration_ms, payload_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                job_id,
                event_type,
                step,
                attempt,
                duration_ms,
                Jsonb(dict(payload or {})),
            ),
        )
        if row is None:
            raise RuntimeError("PostgreSQL did not return created event id")
        return row["id"]

    def job_metrics(self, job_id: UUID) -> dict[str, Any]:
        """Return aggregate execution metrics for one job."""
        row = self.fetch_one(
            """
            SELECT
                COUNT(*)::int AS event_count,
                COALESCE(SUM(duration_ms), 0)::bigint AS total_duration_ms,
                COALESCE(AVG(duration_ms), 0)::numeric(12, 2) AS average_duration_ms,
                COUNT(*) FILTER (WHERE event_type = 'validation_failed')::int
                    AS validation_failures,
                COUNT(*) FILTER (WHERE event_type = 'revision')::int
                    AS revisions,
                COUNT(*) FILTER (WHERE event_type = 'published')::int
                    AS publish_events,
                COUNT(*) FILTER (WHERE event_type = 'error')::int
                    AS errors
            FROM agent_events
            WHERE job_id = %s
            """,
            (job_id,),
        )
        return row or {
            "event_count": 0,
            "total_duration_ms": 0,
            "average_duration_ms": 0,
            "validation_failures": 0,
            "revisions": 0,
            "publish_events": 0,
            "errors": 0,
        }

    def mark_artifact_published(self, *, job_id: UUID, slug: str) -> bool:
        """Mark matching artifact published after Markdown write succeeds."""
        return self.execute(
            """
            UPDATE content_artifacts
            SET approval_status = 'published', published_at = now()
            WHERE job_id = %s AND slug = %s
            """,
            (job_id, slug),
        ) == 1

    def create_artifact(
        self,
        *,
        job_id: UUID,
        title: str,
        slug: str,
        content_markdown: str,
        metadata: Mapping[str, Any] | None = None,
        validation: Mapping[str, Any] | None = None,
    ) -> UUID:
        """Persist one draft artifact and return its identifier."""
        row = self.fetch_one(
            """
            INSERT INTO content_artifacts
                (job_id, title, slug, content_markdown, metadata_json, validation_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                job_id,
                title,
                slug,
                content_markdown,
                Jsonb(dict(metadata or {})),
                Jsonb(dict(validation or {})),
            ),
        )
        if row is None:
            raise RuntimeError("PostgreSQL did not return created artifact id")
        return row["id"]

    def create_approval(self, *, job_id: UUID, artifact_id: UUID) -> UUID:
        """Create pending approval and mark artifact pending."""
        row = self.fetch_one(
            """
            INSERT INTO approvals (job_id, artifact_id)
            VALUES (%s, %s)
            RETURNING id
            """,
            (job_id, artifact_id),
        )
        self.execute(
            """
            UPDATE content_artifacts
            SET approval_status = 'pending'
            WHERE id = %s
            """,
            (artifact_id,),
        )
        if row is None:
            raise RuntimeError("PostgreSQL did not return created approval id")
        return row["id"]

    def decide_approval(
        self,
        *,
        job_id: UUID,
        decision: str,
        reviewer: str,
        feedback: str | None = None,
    ) -> dict[str, Any] | None:
        """Decide pending approval and synchronize artifact/job status."""
        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")
        status = "approved" if decision == "approve" else "rejected"
        row = self.fetch_one(
            """
            UPDATE approvals
            SET status = %s, reviewer = %s, feedback = %s, decided_at = now()
            WHERE id = (
                SELECT id FROM approvals
                WHERE job_id = %s AND status = 'pending'
                ORDER BY requested_at DESC
                LIMIT 1
            )
            RETURNING id, job_id, artifact_id, status, reviewer, feedback
            """,
            (status, reviewer, feedback, job_id),
        )
        if row is None:
            return None
        self.execute(
            """
            UPDATE content_artifacts
            SET approval_status = %s
            WHERE id = %s
            """,
            (status, row["artifact_id"]),
        )
        self.update_job_status(
            job_id,
            "approved" if decision == "approve" else "needs_revision",
            current_step="approval",
        )
        return row
