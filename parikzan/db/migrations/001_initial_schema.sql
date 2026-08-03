-- Parikzan Blogging Agent MVP
-- Migration: 001_initial_schema
-- PostgreSQL source of truth for agent jobs, artifacts, approvals, and telemetry.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS content_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type TEXT NOT NULL DEFAULT 'blog',
    status TEXT NOT NULL DEFAULT 'queued',
    current_step TEXT,
    input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_json JSONB,
    model_name TEXT,
    prompt_version TEXT,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT content_jobs_status_check CHECK (
        status IN (
            'queued',
            'retrieving',
            'outlining',
            'drafting',
            'validating',
            'needs_revision',
            'awaiting_approval',
            'approved',
            'published',
            'failed',
            'retryable_failed',
            'dead_letter'
        )
    )
);

CREATE INDEX IF NOT EXISTS content_jobs_status_created_idx
    ON content_jobs (status, created_at);

CREATE INDEX IF NOT EXISTS content_jobs_type_created_idx
    ON content_jobs (job_type, created_at);

CREATE TABLE IF NOT EXISTS content_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES content_jobs(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL DEFAULT 'blog_post',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    title TEXT,
    slug TEXT,
    content_markdown TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_json JSONB,
    approval_status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    CONSTRAINT content_artifacts_approval_status_check CHECK (
        approval_status IN ('draft', 'pending', 'approved', 'rejected', 'published')
    ),
    CONSTRAINT content_artifacts_job_type_version_unique
        UNIQUE (job_id, artifact_type, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS content_artifacts_published_slug_idx
    ON content_artifacts (slug)
    WHERE approval_status = 'published' AND slug IS NOT NULL;

CREATE INDEX IF NOT EXISTS content_artifacts_job_idx
    ON content_artifacts (job_id, created_at DESC);

CREATE INDEX IF NOT EXISTS content_artifacts_status_idx
    ON content_artifacts (approval_status, updated_at);

CREATE TABLE IF NOT EXISTS content_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,
    source_ref TEXT,
    title TEXT,
    content TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    checksum TEXT,
    qdrant_collection TEXT,
    qdrant_point_id TEXT,
    approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT content_sources_checksum_unique UNIQUE (source_type, source_ref, checksum)
);

CREATE INDEX IF NOT EXISTS content_sources_type_approved_idx
    ON content_sources (source_type, approved);

CREATE TABLE IF NOT EXISTS content_job_sources (
    job_id UUID NOT NULL REFERENCES content_jobs(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES content_sources(id) ON DELETE CASCADE,
    relevance_score NUMERIC(6, 5) CHECK (
        relevance_score IS NULL OR (relevance_score >= 0 AND relevance_score <= 1)
    ),
    excerpt TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (job_id, source_id)
);

CREATE INDEX IF NOT EXISTS content_job_sources_source_idx
    ON content_job_sources (source_id);

CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES content_jobs(id) ON DELETE CASCADE,
    artifact_id UUID NOT NULL REFERENCES content_artifacts(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    reviewer TEXT,
    feedback TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at TIMESTAMPTZ,
    CONSTRAINT approvals_status_check CHECK (
        status IN ('pending', 'approved', 'rejected', 'cancelled')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS approvals_one_pending_per_artifact_idx
    ON approvals (artifact_id)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS approvals_status_requested_idx
    ON approvals (status, requested_at);

CREATE TABLE IF NOT EXISTS agent_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES content_jobs(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    step TEXT,
    attempt INTEGER NOT NULL DEFAULT 1 CHECK (attempt > 0),
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_events_job_created_idx
    ON agent_events (job_id, created_at);

CREATE INDEX IF NOT EXISTS agent_events_type_created_idx
    ON agent_events (event_type, created_at);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS content_jobs_set_updated_at ON content_jobs;
CREATE TRIGGER content_jobs_set_updated_at
    BEFORE UPDATE ON content_jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS content_artifacts_set_updated_at ON content_artifacts;
CREATE TRIGGER content_artifacts_set_updated_at
    BEFORE UPDATE ON content_artifacts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS content_sources_set_updated_at ON content_sources;
CREATE TRIGGER content_sources_set_updated_at
    BEFORE UPDATE ON content_sources
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
