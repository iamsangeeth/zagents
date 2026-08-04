"""Approved blog publishing and Qdrant indexing services."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, NAMESPACE_URL, uuid5

from .clients import OllamaClient, QdrantClient
from .config import AppSettings, QdrantSettings, settings
from .contracts import BlogDraft, MIN_BLOG_WORD_COUNT, count_blog_words


ApprovedStatus = Literal["approved", "published"]


@dataclass(frozen=True, slots=True)
class PublicationResult:
    """Result of Markdown publication and optional indexing."""

    job_id: UUID
    slug: str
    path: Path
    indexed: bool
    qdrant_point_id: str | None = None
    index_error: str | None = None


class MarkdownPublisher:
    """Write approved blog drafts as safe, deterministic Markdown files."""

    def __init__(self, config: AppSettings | None = None) -> None:
        self.config = config or settings.app

    def publish(
        self,
        draft: BlogDraft,
        *,
        job_id: UUID,
        approval_status: str,
    ) -> Path:
        """Publish draft only when approval status is approved or published."""
        if approval_status not in {"approved", "published"}:
            raise PermissionError(
                "blog draft must have approved status before publishing"
            )
        actual_word_count = count_blog_words(draft.body_markdown)
        if actual_word_count < MIN_BLOG_WORD_COUNT:
            raise ValueError(
                f"blog draft must contain at least {MIN_BLOG_WORD_COUNT} words; "
                f"got {actual_word_count}"
            )

        output_dir = self.config.output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = (output_dir / f"{draft.slug}.md").resolve()
        if destination.parent != output_dir:
            raise ValueError("draft slug escaped output directory")

        published_at = datetime.now(UTC)
        front_matter_lines = [
            "---",
            f"title: {json.dumps(draft.title)}",
            f"description: {json.dumps(draft.excerpt)}",
            f"date: {published_at.date().isoformat()}",
            f"slug: {draft.slug}",
            "author: Parikzen Team",
            f"job_id: {job_id}",
            f"published_at: {published_at.isoformat()}",
        ]
        if draft.seo.tags:
            front_matter_lines.append("tags:")
            front_matter_lines.extend(f"  - {json.dumps(tag)}" for tag in draft.seo.tags)
        front_matter_lines.extend(["---", ""])
        content = "\n".join(front_matter_lines) + draft.body_markdown.rstrip() + "\n"
        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(destination)
        return destination


class QdrantContentIndexer:
    """Embed approved blog content and upsert it into Qdrant."""

    def __init__(
        self,
        ollama: OllamaClient | None = None,
        qdrant: QdrantClient | None = None,
        config: QdrantSettings | None = None,
    ) -> None:
        self.ollama = ollama or OllamaClient()
        self.qdrant = qdrant or QdrantClient(config)
        self.config = config or settings.qdrant

    def index(
        self,
        draft: BlogDraft,
        *,
        job_id: UUID,
        approval_status: str,
    ) -> str:
        """Index approved draft and return deterministic Qdrant point ID."""
        if approval_status not in {"approved", "published"}:
            raise PermissionError(
                "blog draft must have approved status before indexing"
            )
        actual_word_count = count_blog_words(draft.body_markdown)
        if actual_word_count < MIN_BLOG_WORD_COUNT:
            raise ValueError(
                f"blog draft must contain at least {MIN_BLOG_WORD_COUNT} words; "
                f"got {actual_word_count}"
            )

        vector = self.ollama.embed([draft.body_markdown])[0]
        self.qdrant.ensure_collection(
            self.config.content_collection,
            vector_size=len(vector),
        )
        point_id = str(uuid5(NAMESPACE_URL, f"parikzan:blog:{job_id}:{draft.slug}"))
        self.qdrant.upsert_points(
            self.config.content_collection,
            [
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": {
                        "source_type": "blog",
                        "source_id": str(job_id),
                        "title": draft.title,
                        "slug": draft.slug,
                        "content": draft.body_markdown,
                        "approved": True,
                    },
                }
            ],
        )
        return point_id


class BlogPublicationService:
    """Publish Markdown and attempt Qdrant indexing as one application action."""

    def __init__(
        self,
        publisher: MarkdownPublisher | None = None,
        indexer: QdrantContentIndexer | None = None,
    ) -> None:
        self.publisher = publisher or MarkdownPublisher()
        self.indexer = indexer or QdrantContentIndexer()

    def publish_and_index(
        self,
        draft: BlogDraft,
        *,
        job_id: UUID,
        approval_status: str,
    ) -> PublicationResult:
        """Write approved Markdown, then report Qdrant indexing outcome."""
        path = self.publisher.publish(
            draft,
            job_id=job_id,
            approval_status=approval_status,
        )
        try:
            point_id = self.indexer.index(
                draft,
                job_id=job_id,
                approval_status=approval_status,
            )
        except Exception as error:
            return PublicationResult(
                job_id=job_id,
                slug=draft.slug,
                path=path,
                indexed=False,
                index_error=f"{type(error).__name__}: {error}",
            )
        return PublicationResult(
            job_id=job_id,
            slug=draft.slug,
            path=path,
            indexed=True,
            qdrant_point_id=point_id,
        )


__all__ = [
    "BlogPublicationService",
    "MarkdownPublisher",
    "PublicationResult",
    "QdrantContentIndexer",
]
