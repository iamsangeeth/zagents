from __future__ import annotations

import unittest
from uuid import uuid4

from pydantic import ValidationError

from parikzan.contracts import (
    BlogAgentResult,
    BlogDraft,
    BlogJobInput,
    BlogValidationReport,
    Citation,
    SEOData,
    ValidationIssue,
)


class BloggingContractTests(unittest.TestCase):
    def test_job_input_normalizes_duplicate_keywords(self) -> None:
        request = BlogJobInput(
            topic="Python quiz preparation",
            category="self_evaluation",
            secondary_keywords=["python quiz", " python quiz ", "learning"],
        )
        self.assertEqual(request.category, "self_evaluation")
        self.assertEqual(request.secondary_keywords, ["python quiz", "learning"])
        self.assertEqual(request.output_format, "markdown")

    def test_invalid_slug_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SEOData(
                meta_title="Python Quiz Preparation Guide",
                meta_description="A practical guide for preparing with Python quizzes and improving recall.",
                slug="Invalid Slug",
            )

    def test_validation_report_rejects_passed_errors(self) -> None:
        with self.assertRaises(ValidationError):
            BlogValidationReport(
                passed=True,
                score=90,
                issues=[
                    ValidationIssue(
                        code="missing_source",
                        severity="error",
                        message="Claim has no source.",
                    )
                ],
            )

    def test_published_result_requires_draft(self) -> None:
        with self.assertRaises(ValidationError):
            BlogAgentResult(job_id=uuid4(), status="published")

    def test_draft_serializes_for_n8n(self) -> None:
        source_id = uuid4()
        draft = BlogDraft(
            title="Python Quiz Preparation Guide",
            slug="python-quiz-preparation-guide",
            excerpt="A practical guide for preparing with Python quizzes and improving recall.",
            body_markdown="# Python Quiz Preparation\n\n" + ("Practice with short explanations. " * 10),
            seo=SEOData(
                meta_title="Python Quiz Preparation Guide",
                meta_description="A practical guide for preparing with Python quizzes and improving recall.",
                slug="python-quiz-preparation-guide",
                primary_keyword="python quiz",
            ),
            citations=[
                Citation(
                    source_id=source_id,
                    claim="Practice improves recall.",
                )
            ],
            word_count=55,
        )
        payload = draft.model_dump(mode="json")
        self.assertEqual(payload["slug"], "python-quiz-preparation-guide")
        self.assertEqual(payload["citations"][0]["source_id"], str(source_id))


if __name__ == "__main__":
    unittest.main()
