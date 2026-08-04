"""Blogging Agent input, output, and validation contracts."""

from __future__ import annotations

import re
from math import ceil
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MIN_BLOG_WORD_COUNT = 1000
MIN_TARGET_WORD_RATIO = 0.75


def count_blog_words(body_markdown: str) -> int:
    """Count human-readable words while ignoring Markdown punctuation."""
    return len(re.findall(r"\b[\w'-]+\b", body_markdown))


def minimum_blog_word_count(target_word_count: int) -> int:
    """Return minimum acceptable length for requested target."""
    return max(MIN_BLOG_WORD_COUNT, ceil(target_word_count * MIN_TARGET_WORD_RATIO))


JobStatus = Literal[
    "queued",
    "retrieving",
    "outlining",
    "drafting",
    "validating",
    "needs_revision",
    "awaiting_approval",
    "approved",
    "published",
    "failed",
    "retryable_failed",
    "dead_letter",
]

BlogCategory = Literal[
    "learning",
    "self_study",
    "competitive_exam",
    "self_evaluation",
    "teachers",
]


class ContractModel(BaseModel):
    """Base model rejecting undeclared fields at integration boundaries."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BlogJobInput(ContractModel):
    """Request sent from n8n to start blog generation."""

    topic: str = Field(min_length=3, max_length=300)
    category: BlogCategory | None = None
    quiz_id: str | None = Field(default=None, min_length=1, max_length=100)
    audience: str = Field(default="general learners", min_length=2, max_length=200)
    primary_keyword: str | None = Field(default=None, min_length=2, max_length=100)
    secondary_keywords: list[str] = Field(default_factory=list, max_length=20)
    tone: str = Field(default="educational", min_length=2, max_length=60)
    cta: str | None = Field(default=None, max_length=300)
    locale: str = Field(default="en", pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    output_format: Literal["markdown"] = "markdown"
    target_word_count: int = Field(default=1000, ge=300, le=5000)

    @field_validator("secondary_keywords")
    @classmethod
    def normalize_keywords(cls, keywords: list[str]) -> list[str]:
        normalized = [keyword.strip() for keyword in keywords if keyword.strip()]
        return list(dict.fromkeys(normalized))


class SourceReference(ContractModel):
    """Approved context returned by PostgreSQL/Qdrant retrieval."""

    source_id: UUID
    source_type: str = Field(min_length=1, max_length=60)
    title: str | None = Field(default=None, max_length=300)
    excerpt: str = Field(min_length=1, max_length=5000)
    source_ref: str | None = Field(default=None, max_length=500)
    relevance_score: float = Field(ge=0, le=1)


class OutlineSection(ContractModel):
    """One planned article section."""

    heading: str = Field(min_length=2, max_length=200)
    purpose: str = Field(min_length=2, max_length=500)
    key_points: list[str] = Field(min_length=1, max_length=10)


class BlogOutline(ContractModel):
    """Structured outline generated before drafting."""

    title: str = Field(min_length=5, max_length=160)
    angle: str = Field(min_length=5, max_length=500)
    sections: list[OutlineSection] = Field(min_length=1, max_length=20)
    faq_questions: list[str] = Field(default_factory=list, max_length=10)
    internal_link_targets: list[str] = Field(default_factory=list, max_length=20)


class SEOData(ContractModel):
    """Search metadata attached to an article draft."""

    meta_title: str = Field(min_length=10, max_length=60)
    meta_description: str = Field(min_length=50, max_length=160)
    slug: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    primary_keyword: str | None = Field(default=None, max_length=100)
    secondary_keywords: list[str] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("secondary_keywords", "tags")
    @classmethod
    def normalize_list_values(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values if value.strip()]
        return list(dict.fromkeys(normalized))


class Citation(ContractModel):
    """Traceability reference for claim support."""

    source_id: UUID
    claim: str = Field(min_length=5, max_length=1000)
    locator: str | None = Field(default=None, max_length=500)


class BlogSectionDraft(ContractModel):
    """One article section generated as standalone Markdown."""

    heading: str = Field(min_length=2, max_length=200)
    body_markdown: str = Field(min_length=100)
    word_count: int = Field(ge=0)


class BlogDraftMetadata(ContractModel):
    """Article metadata generated separately from long-form body text."""

    title: str = Field(min_length=5, max_length=160)
    slug: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    excerpt: str = Field(min_length=20, max_length=500)
    seo: SEOData
    citations: list[Citation] = Field(default_factory=list, max_length=50)
    quiz_cta: str | None = Field(default=None, max_length=500)


class BlogDraft(ContractModel):
    """Complete article artifact produced by Pydantic AI."""

    title: str = Field(min_length=5, max_length=160)
    slug: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    excerpt: str = Field(min_length=20, max_length=500)
    body_markdown: str = Field(min_length=100)
    seo: SEOData
    citations: list[Citation] = Field(default_factory=list, max_length=50)
    quiz_cta: str | None = Field(default=None, max_length=500)
    word_count: int = Field(ge=0)


class ValidationIssue(ContractModel):
    """Single deterministic or model-generated quality issue."""

    code: str = Field(min_length=2, max_length=80)
    severity: Literal["error", "warning", "info"]
    message: str = Field(min_length=2, max_length=1000)
    path: str | None = Field(default=None, max_length=200)


class BlogValidationReport(ContractModel):
    """Quality gate result consumed by n8n routing."""

    passed: bool
    score: float = Field(ge=0, le=100)
    issues: list[ValidationIssue] = Field(default_factory=list, max_length=100)
    checks: dict[str, bool] = Field(default_factory=dict, max_length=50)

    @model_validator(mode="after")
    def reject_errors_marked_passed(self) -> "BlogValidationReport":
        has_error = any(issue.severity == "error" for issue in self.issues)
        if self.passed and has_error:
            raise ValueError("passed cannot be true when validation has error issues")
        return self


class BlogJobEnvelope(ContractModel):
    """Execution envelope passed between n8n and Pydantic AI."""

    job_id: UUID
    input: BlogJobInput
    attempt: int = Field(default=1, ge=1, le=10)
    model_name: str = Field(min_length=1, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=100)


class BlogRuntimeContext(ContractModel):
    """Accumulated context passed between n8n and Pydantic AI stages."""

    job_id: UUID
    input: BlogJobInput
    model_name: str = Field(min_length=1, max_length=100)
    prompt_version: str = Field(default="blogging/v1", min_length=1, max_length=100)
    sources: list[SourceReference] = Field(default_factory=list, max_length=100)
    outline: BlogOutline | None = None
    draft: BlogDraft | None = None
    seo: SEOData | None = None
    validation: BlogValidationReport | None = None
    revision_attempt: int = Field(default=0, ge=0, le=10)
    approval_id: UUID | None = None
    approval_status: Literal["pending", "approved", "rejected"] | None = None
    manual_approval: bool = False
    status: JobStatus = "queued"
    error_code: str | None = Field(default=None, max_length=80)
    error_message: str | None = Field(default=None, max_length=1000)


class BlogAgentResult(ContractModel):
    """Final typed result returned to n8n."""

    job_id: UUID
    status: JobStatus
    outline: BlogOutline | None = None
    draft: BlogDraft | None = None
    validation: BlogValidationReport | None = None
    sources: list[SourceReference] = Field(default_factory=list, max_length=100)
    error_code: str | None = Field(default=None, max_length=80)
    error_message: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_output_for_success(self) -> "BlogAgentResult":
        if self.status in {"approved", "published"} and self.draft is None:
            raise ValueError("successful result requires draft")
        return self
