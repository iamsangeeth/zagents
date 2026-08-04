from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from parikzan.config import AppSettings
from parikzan.contracts import BlogDraft, SEOData
from parikzan.publishing import MarkdownPublisher, QdrantContentIndexer


def make_draft() -> BlogDraft:
    return BlogDraft(
        title="Python Quiz Preparation Guide",
        slug="python-quiz-preparation-guide",
        excerpt="A practical guide for preparing with Python quizzes and improving recall.",
        body_markdown="# Python Quiz Preparation\n\n" + ("Practice with short explanations. " * 260),
        seo=SEOData(
            meta_title="Python Quiz Preparation Guide",
            meta_description="A practical guide for preparing with Python quizzes and improving recall.",
            slug="python-quiz-preparation-guide",
            primary_keyword="python quiz",
        ),
        word_count=1043,
    )


class FakeOllama:
    def embed(self, texts: list[str]) -> list[list[float]]:
        assert texts
        return [[0.1, 0.2, 0.3]]


class FakeQdrant:
    def __init__(self) -> None:
        self.collection_args: tuple[str, int] | None = None
        self.points: list[dict] = []

    def ensure_collection(self, collection: str, *, vector_size: int) -> bool:
        self.collection_args = (collection, vector_size)
        return True

    def upsert_points(self, collection: str, points: list[dict]) -> dict:
        self.points.extend(points)
        return {"status": "ok"}


class PublishingTests(unittest.TestCase):
    def test_unapproved_draft_cannot_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = AppSettings(
                environment="test",
                debug=False,
                host="127.0.0.1",
                port=8000,
                log_level="INFO",
                output_dir=Path(directory),
                data_dir=Path(directory),
                knowledge_dir=Path(directory),
                prompts_dir=Path(directory),
                approval_required=True,
            )
            with self.assertRaises(PermissionError):
                MarkdownPublisher(config).publish(
                    make_draft(),
                    job_id=uuid4(),
                    approval_status="pending",
                )

    def test_short_approved_draft_cannot_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = AppSettings(
                environment="test",
                debug=False,
                host="127.0.0.1",
                port=8000,
                log_level="INFO",
                output_dir=Path(directory),
                data_dir=Path(directory),
                knowledge_dir=Path(directory),
                prompts_dir=Path(directory),
                approval_required=True,
            )
            short_draft = make_draft().model_copy(
                update={"body_markdown": "# Short\n\n" + ("word " * 40), "word_count": 40}
            )
            with self.assertRaises(ValueError):
                MarkdownPublisher(config).publish(
                    short_draft,
                    job_id=uuid4(),
                    approval_status="approved",
                )

    def test_approved_draft_writes_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            config = AppSettings(
                environment="test",
                debug=False,
                host="127.0.0.1",
                port=8000,
                log_level="INFO",
                output_dir=output_dir,
                data_dir=output_dir,
                knowledge_dir=output_dir,
                prompts_dir=output_dir,
                approval_required=True,
            )
            job_id = uuid4()
            path = MarkdownPublisher(config).publish(
                make_draft(),
                job_id=job_id,
                approval_status="approved",
            )
            content = path.read_text(encoding="utf-8")
            self.assertEqual(path, output_dir / "python-quiz-preparation-guide.md")
            self.assertIn('title: "Python Quiz Preparation Guide"', content)
            self.assertIn(f"job_id: {job_id}", content)
            self.assertIn("# Python Quiz Preparation", content)

    def test_indexer_requires_approval_and_uses_stable_point(self) -> None:
        ollama = FakeOllama()
        qdrant = FakeQdrant()
        indexer = QdrantContentIndexer(ollama=ollama, qdrant=qdrant)
        job_id = uuid4()
        with self.assertRaises(PermissionError):
            indexer.index(make_draft(), job_id=job_id, approval_status="pending")
        point_id = indexer.index(
            make_draft(),
            job_id=job_id,
            approval_status="approved",
        )
        same_point_id = indexer.index(
            make_draft(),
            job_id=job_id,
            approval_status="approved",
        )
        self.assertEqual(point_id, same_point_id)
        self.assertEqual(qdrant.collection_args[1], 3)
        self.assertEqual(len(qdrant.points), 2)
        self.assertTrue(qdrant.points[0]["payload"]["approved"])


if __name__ == "__main__":
    unittest.main()
