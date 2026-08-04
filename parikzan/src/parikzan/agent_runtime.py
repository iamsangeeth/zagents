"""Pydantic AI runtime used behind n8n HTTP orchestration."""

from __future__ import annotations

import json
from collections.abc import Mapping
from math import ceil
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from .clients import OllamaClient, PostgresClient, QdrantClient
from .config import settings
from .contracts import (
    BlogDraft,
    BlogDraftMetadata,
    BlogJobInput,
    BlogOutline,
    BlogRuntimeContext,
    BlogSectionDraft,
    BlogValidationReport,
    SEOData,
    SourceReference,
    ValidationIssue,
    count_blog_words,
    minimum_blog_word_count,
)
from .observability import MetricsRecorder
from .publishing import MarkdownPublisher, QdrantContentIndexer


class PromptStore:
    """Load versioned prompt files from configured prompt directory."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.app.prompts_dir / "blogging" / "v1"

    def load(self, name: str) -> str:
        path = self.root / f"{name}.md"
        if not path.is_file():
            raise FileNotFoundError(f"prompt not found: {path}")
        return path.read_text(encoding="utf-8")


class KnowledgeStore:
    """Read approved local knowledge and expose stable source references."""

    FILES = ("PRODUCT.md", "PRICING_FAQ.md", "API.md", "CONTENT_GUIDELINES.md")

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.app.knowledge_dir

    def sources(self) -> list[SourceReference]:
        references: list[SourceReference] = []
        for name in self.FILES:
            path = self.root / name
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8")
            source_id = uuid5(NAMESPACE_URL, f"parikzan:knowledge:{name}")
            references.append(
                SourceReference(
                    source_id=source_id,
                    source_type="product_knowledge",
                    title=name,
                    excerpt=content[:5000],
                    source_ref=str(path),
                    relevance_score=1.0,
                )
            )
        return references


class BlogAgentRuntime:
    """Typed stage agents and persistence tools for n8n."""

    def __init__(
        self,
        *,
        database: PostgresClient | None = None,
        ollama: OllamaClient | None = None,
        qdrant: QdrantClient | None = None,
        prompts: PromptStore | None = None,
        knowledge: KnowledgeStore | None = None,
        metrics: MetricsRecorder | None = None,
        publisher: MarkdownPublisher | None = None,
        indexer: QdrantContentIndexer | None = None,
    ) -> None:
        self.database = database or PostgresClient()
        self.ollama = ollama or OllamaClient()
        self.qdrant = qdrant or QdrantClient()
        self.prompts = prompts or PromptStore()
        self.knowledge = knowledge or KnowledgeStore()
        self.metrics = metrics or MetricsRecorder(self.database)
        self.publisher = publisher or MarkdownPublisher()
        self.indexer = indexer or QdrantContentIndexer(self.ollama, self.qdrant)

    def create_job(self, request: BlogJobInput) -> BlogRuntimeContext:
        job_id = self.database.create_job(
            request.model_dump(mode="json"),
            model_name=settings.ollama.model,
            prompt_version="blogging/v1",
        )
        sources = self.knowledge.sources()
        context = BlogRuntimeContext(
            job_id=job_id,
            input=request,
            model_name=settings.ollama.model,
            sources=sources,
            status="retrieving",
        )
        self.database.update_job_status(job_id, "retrieving", current_step="context")
        self.database.save_job_output(job_id, context.model_dump(mode="json"))
        self.metrics.event(
            job_id=job_id,
            event_type="job_created",
            step="intake",
            payload={"source_count": len(sources), "prompt_version": "blogging/v1"},
        )
        return context

    def _prompt(self, stage: str) -> str:
        if stage == "validate":
            return self.prompts.load(stage)
        return f"{self.prompts.load('system')}\n\n{self.prompts.load(stage)}"

    def _user_context(
        self,
        context: BlogRuntimeContext,
        stage: str,
        extra_context: str | None = None,
    ) -> str:
        if stage == "validate":
            context_data = {
                "job_id": str(context.job_id),
                "input": context.input.model_dump(mode="json"),
                "draft": {
                    "title": context.draft.title if context.draft else None,
                    "excerpt": context.draft.excerpt if context.draft else None,
                    "body_markdown": context.draft.body_markdown[:3000] if context.draft else None,
                    "seo": context.draft.seo.model_dump(mode="json") if context.draft else None,
                },
                "sources": [
                    {
                        "source_id": str(source.source_id),
                        "title": source.title,
                        "excerpt": source.excerpt[:300],
                    }
                    for source in context.sources
                ],
            }
            return (
                "VALIDATION INPUT JSON:\n"
                + json.dumps(context_data, indent=2)
                + (f"\n\n{extra_context}" if extra_context else "")
            )

        context_data = context.model_dump(mode="json")
        context_data["sources"] = [
            {"source_id": str(source.source_id), "title": source.title}
            for source in context.sources
        ]
        if context_data.get("draft"):
            context_data["draft"]["body_markdown"] = context.draft.body_markdown[:3500]
        source_text = "\n\n".join(
            f"SOURCE_ID: {source.source_id}\nSOURCE_TITLE: {source.title}\n"
            f"{source.excerpt[:800]}"
            for source in context.sources
        )
        return (
            f"STAGE: {stage}\nJOB CONTEXT JSON:\n"
            + json.dumps(context_data, indent=2)
            + "\n\nAPPROVED SOURCE CONTEXT (truncated):\n"
            + source_text
            + (f"\n\n{extra_context}" if extra_context else "")
        )

    def _run_agent(
        self,
        context: BlogRuntimeContext,
        stage: str,
        output_type: type[Any],
        extra_context: str | None = None,
    ) -> Any:
        stage_max_tokens = {
            "outline": 800,
            "section": 1600,
            "metadata": 800,
            "draft": 4000,
            "seo": 400,
            "validate": 700,
            "revise": 4000,
        }
        stage_retries = {"section": 3, "metadata": 3, "draft": 4, "revise": 4}
        max_tokens = stage_max_tokens.get(stage, 800)
        with self.metrics.observe_step(
            job_id=context.job_id,
            step=stage,
            attempt=max(1, context.revision_attempt + 1),
            payload={
                "model": context.model_name,
                "prompt_version": context.prompt_version,
                "max_tokens": max_tokens,
            },
        ):
            agent = self.ollama.agent(
                output_type,
                name=f"blog-{stage}-v1",
                system_prompt=self._prompt(stage),
                retries=stage_retries.get(stage, 2),
                max_tokens=max_tokens,
            )
            return agent.run_sync(
                self._user_context(context, stage, extra_context)
            ).output

    def _save(self, context: BlogRuntimeContext) -> BlogRuntimeContext:
        self.database.save_job_output(context.job_id, context.model_dump(mode="json"))
        return context

    def outline(self, context: BlogRuntimeContext) -> BlogRuntimeContext:
        outline = self._run_agent(context, "outline", BlogOutline)
        updated = context.model_copy(update={"outline": outline, "status": "outlining"})
        self.database.update_job_status(context.job_id, "outlining", current_step="outline")
        return self._save(updated)

    def _compose_draft(self, context: BlogRuntimeContext) -> BlogDraft:
        if context.outline is None:
            raise ValueError("outline required before drafting")

        minimum_words = minimum_blog_word_count(context.input.target_word_count)
        section_target = max(160, ceil(minimum_words / len(context.outline.sections)))
        revision_context = ""
        if context.validation is not None:
            revision_context = "VALIDATION ISSUES TO FIX:\n" + json.dumps(
                [issue.model_dump(mode="json") for issue in context.validation.issues],
                indent=2,
            )

        metadata = self._run_agent(
            context,
            "metadata",
            BlogDraftMetadata,
            extra_context=revision_context or None,
        )
        generated_sections: list[BlogSectionDraft] = []

        for index, outline_section in enumerate(context.outline.sections, start=1):
            best: BlogSectionDraft | None = None
            for attempt in range(1, 4):
                section_context = {
                    "section_number": index,
                    "section_count": len(context.outline.sections),
                    "section_target_words": section_target,
                    "outline_section": outline_section.model_dump(mode="json"),
                    "previous_section": best.body_markdown if best else None,
                    "revision_feedback": revision_context or None,
                }
                candidate = self._run_agent(
                    context,
                    "section",
                    BlogSectionDraft,
                    extra_context="SECTION GENERATION INPUT:\n"
                    + json.dumps(section_context, indent=2),
                )
                if best is None or count_blog_words(candidate.body_markdown) > count_blog_words(best.body_markdown):
                    best = candidate
                if count_blog_words(candidate.body_markdown) >= section_target:
                    break
            if best is not None:
                generated_sections.append(best)

        body_parts = [f"# {metadata.title}"]
        body_parts.extend(
            f"## {section.heading}\n\n{section.body_markdown.strip()}"
            for section in generated_sections
        )

        expansion_attempt = 0
        while count_blog_words("\n\n".join(body_parts)) < minimum_words and expansion_attempt < 3:
            expansion_attempt += 1
            current_body = "\n\n".join(body_parts)
            remaining_words = minimum_words - count_blog_words(current_body)
            expansion_context = {
                "section_number": len(generated_sections) + 1,
                "section_count": len(generated_sections) + 1,
                "section_target_words": max(200, ceil(remaining_words * 1.25)),
                "outline_section": {
                    "heading": "Practical Application and Next Steps",
                    "purpose": "Add substantive guidance needed to complete the article.",
                    "key_points": ["practical examples", "common mistakes", "next steps"],
                },
                "current_body": current_body,
                "remaining_words": remaining_words,
            }
            expansion = self._run_agent(
                context,
                "section",
                BlogSectionDraft,
                extra_context="ARTICLE EXPANSION INPUT:\n"
                + json.dumps(expansion_context, indent=2),
            )
            body_parts.append(f"## {expansion.heading}\n\n{expansion.body_markdown.strip()}")

        body_markdown = "\n\n".join(body_parts).strip()
        return BlogDraft(
            title=metadata.title,
            slug=metadata.slug,
            excerpt=metadata.excerpt,
            body_markdown=body_markdown,
            seo=metadata.seo,
            citations=metadata.citations,
            quiz_cta=metadata.quiz_cta,
            word_count=count_blog_words(body_markdown),
        )

    def draft(self, context: BlogRuntimeContext) -> BlogRuntimeContext:
        draft = self._compose_draft(context)
        updated = context.model_copy(update={"draft": draft, "status": "drafting"})
        self.database.update_job_status(context.job_id, "drafting", current_step="draft")
        return self._save(updated)

    def seo(self, context: BlogRuntimeContext) -> BlogRuntimeContext:
        if context.draft is None:
            raise ValueError("draft required before SEO")
        seo = self._run_agent(context, "seo", SEOData)
        draft = context.draft.model_copy(update={"seo": seo})
        updated = context.model_copy(update={"draft": draft, "seo": seo, "status": "drafting"})
        self.database.update_job_status(context.job_id, "drafting", current_step="seo")
        return self._save(updated)

    def validate(self, context: BlogRuntimeContext) -> BlogRuntimeContext:
        if context.draft is None:
            raise ValueError("draft required before validation")
        report = self._run_agent(context, "validate", BlogValidationReport)
        actual_word_count = count_blog_words(context.draft.body_markdown)
        minimum_word_count = minimum_blog_word_count(context.input.target_word_count)
        checks = {**report.checks, "minimum_word_count": actual_word_count >= minimum_word_count}
        issues = list(report.issues)
        if actual_word_count < minimum_word_count:
            if not any(issue.code == "minimum_word_count" for issue in issues):
                issues.append(
                    ValidationIssue(
                        code="minimum_word_count",
                        severity="error",
                        message=(
                            f"Draft has {actual_word_count} words; minimum is "
                            f"{minimum_word_count} for target {context.input.target_word_count}."
                        ),
                        path="draft.body_markdown",
                    )
                )
            report = report.model_copy(
                update={"passed": False, "issues": issues, "checks": checks}
            )
        elif checks != report.checks:
            report = report.model_copy(update={"checks": checks})
        status = "awaiting_approval" if report.passed else "needs_revision"
        event_type = "validation_passed" if report.passed else "validation_failed"
        updated = context.model_copy(update={"validation": report, "status": status})
        self.database.update_job_status(context.job_id, status, current_step="validate")
        self.metrics.event(
            job_id=context.job_id,
            event_type=event_type,
            step="validate",
            payload={"score": report.score, "issue_count": len(report.issues)},
        )
        return self._save(updated)

    def revise(self, context: BlogRuntimeContext) -> BlogRuntimeContext:
        if context.draft is None or context.validation is None:
            raise ValueError("draft and validation required before revision")
        draft = self._compose_draft(context)
        updated = context.model_copy(
            update={
                "draft": draft,
                "revision_attempt": context.revision_attempt + 1,
                "status": "drafting",
            }
        )
        self.database.update_job_status(context.job_id, "drafting", current_step="revise")
        self.metrics.event(
            job_id=context.job_id,
            event_type="revision",
            step="revise",
            attempt=updated.revision_attempt,
        )
        return self._save(updated)

    def request_approval(self, context: BlogRuntimeContext) -> dict[str, Any]:
        if context.validation is None:
            raise ValueError("approval requires validation report")
        if not context.validation.passed and not context.manual_approval:
            raise ValueError("failed validation requires explicit manual_approval=true")
        if context.draft is None:
            raise ValueError("approval requires draft")
        actual_word_count = count_blog_words(context.draft.body_markdown)
        minimum_word_count = minimum_blog_word_count(context.input.target_word_count)
        if actual_word_count < minimum_word_count:
            raise ValueError(
                f"draft body must contain at least {minimum_word_count} words; "
                f"got {actual_word_count}"
            )
        artifact_id = self.database.create_artifact(
            job_id=context.job_id,
            title=context.draft.title,
            slug=context.draft.slug,
            content_markdown=context.draft.body_markdown,
            metadata={"draft": context.draft.model_dump(mode="json")},
            validation=context.validation.model_dump(mode="json"),
        )
        approval_id = self.database.create_approval(
            job_id=context.job_id,
            artifact_id=artifact_id,
        )
        self.database.update_job_status(
            context.job_id,
            "awaiting_approval",
            current_step="approval",
        )
        return {
            **context.model_dump(mode="json"),
            "approval_id": str(approval_id),
            "approval_status": "pending",
            "status": "awaiting_approval",
        }

    def decide_approval(
        self,
        *,
        job_id: UUID,
        decision: str,
        reviewer: str,
        feedback: str | None = None,
    ) -> dict[str, Any]:
        row = self.database.decide_approval(
            job_id=job_id,
            decision=decision,
            reviewer=reviewer,
            feedback=feedback,
        )
        if row is None:
            raise ValueError("no pending approval found for job")
        artifact = self.database.fetch_one(
            "SELECT metadata_json FROM content_artifacts WHERE id = %s",
            (row["artifact_id"],),
        )
        draft = (artifact or {}).get("metadata_json", {}).get("draft")
        return {
            "job_id": str(job_id),
            "status": row["status"],
            "approval_status": row["status"],
            "approval_id": str(row["id"]),
            "reviewer": reviewer,
            "feedback": feedback,
            "draft": draft,
        }

    def publish(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        approval_status = str(payload.get("approval_status", payload.get("status", "")))
        draft = BlogDraft.model_validate(payload.get("draft"))
        job_id = UUID(str(payload["job_id"]))
        path = self.publisher.publish(
            draft,
            job_id=job_id,
            approval_status=approval_status,
        )
        self.database.update_job_status(job_id, "published", current_step="publish")
        self.database.mark_artifact_published(job_id=job_id, slug=draft.slug)
        self.metrics.event(job_id=job_id, event_type="published", step="publish")
        return {
            **dict(payload),
            "job_id": str(job_id),
            "status": "published",
            "artifact_path": str(path),
            "draft": draft.model_dump(mode="json"),
        }

    def index(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        approval_status = str(payload.get("approval_status", payload.get("status", "")))
        draft = BlogDraft.model_validate(payload.get("draft"))
        job_id = UUID(str(payload["job_id"]))
        try:
            point_id = self.indexer.index(
                draft,
                job_id=job_id,
                approval_status=approval_status,
            )
        except Exception as error:  # noqa: BLE001 - expose degraded index state
            self.metrics.event(
                job_id=job_id,
                event_type="error",
                step="index",
                payload={"error_type": type(error).__name__},
            )
            return {
                **dict(payload),
                "job_id": str(job_id),
                "indexed": False,
                "index_error": f"{type(error).__name__}: {error}",
                "draft": draft.model_dump(mode="json"),
            }
        return {
            **dict(payload),
            "job_id": str(job_id),
            "indexed": True,
            "qdrant_point_id": point_id,
            "draft": draft.model_dump(mode="json"),
        }
