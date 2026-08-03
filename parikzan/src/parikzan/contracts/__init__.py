"""Typed contracts shared by n8n, Pydantic AI, and persistence code."""

from .blogging import (
    BlogAgentResult,
    BlogCategory,
    BlogDraft,
    BlogJobEnvelope,
    BlogJobInput,
    BlogOutline,
    BlogRuntimeContext,
    Citation,
    OutlineSection,
    SEOData,
    SourceReference,
    ValidationIssue,
    BlogValidationReport,
)

__all__ = [
    "BlogAgentResult",
    "BlogCategory",
    "BlogDraft",
    "BlogJobEnvelope",
    "BlogJobInput",
    "BlogOutline",
    "BlogRuntimeContext",
    "BlogValidationReport",
    "Citation",
    "OutlineSection",
    "SEOData",
    "SourceReference",
    "ValidationIssue",
]
