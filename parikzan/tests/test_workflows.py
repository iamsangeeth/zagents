from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def load_workflow(self, name: str) -> dict:
        return json.loads((ROOT / "workflows" / name).read_text(encoding="utf-8"))

    def test_main_workflow_has_bounded_revision_and_approval(self) -> None:
        workflow = self.load_workflow("blogging_agent_v1.json")
        nodes = {node["name"]: node for node in workflow["nodes"]}
        self.assertEqual(len(nodes), 19)
        self.assertIn("Normalize Validation Result", nodes)
        self.assertEqual(
            workflow["connections"]["Validate Blog"]["main"][0][0]["node"],
            "Normalize Validation Result",
        )
        self.assertEqual(
            workflow["connections"]["Normalize Validation Result"]["main"][0][0]["node"],
            "Validation Gate",
        )
        gate_condition = nodes["Validation Gate"]["parameters"]["conditions"]["conditions"][0]
        self.assertEqual(gate_condition["leftValue"], "={{ $json.validation?.passed }}")
        self.assertEqual(gate_condition["operator"]["type"], "boolean")
        self.assertEqual(gate_condition["operator"]["operation"], "true")
        self.assertEqual(
            workflow["connections"]["Validation Gate"]["main"][0][0]["node"],
            "Approval Payload Guard",
        )
        self.assertIn("manual approval was not requested", nodes["Approval Payload Guard"]["parameters"]["jsCode"])
        self.assertIn("Prepare Manual Review", nodes)
        self.assertEqual(
            workflow["connections"]["Revision Limit"]["main"][1][0]["node"],
            "Prepare Manual Review",
        )
        self.assertIn("manual_approval: true", nodes["Prepare Manual Review"]["parameters"]["jsCode"])
        self.assertEqual(
            workflow["connections"]["Prepare Manual Review"]["main"][0][0]["node"],
            "Request Human Approval",
        )
        self.assertEqual(
            workflow["connections"]["Approval Payload Guard"]["main"][0][0]["node"],
            "Request Human Approval",
        )
        self.assertIn("Select Random Blog Topic", nodes)
        topic_code = nodes["Select Random Blog Topic"]["parameters"]["jsCode"]
        for category in ("learning", "self_study", "competitive_exam", "self_evaluation", "teachers"):
            self.assertIn(f"category: '{category}'", topic_code)
        self.assertIn("Math.random()", topic_code)
        self.assertIn("https://www.parikzen.com", topic_code)
        self.assertEqual(
            workflow["connections"]["Schedule Daily Blog"]["main"][0][0]["node"],
            "Select Random Blog Topic",
        )
        self.assertEqual(
            workflow["connections"]["Select Random Blog Topic"]["main"][0][0]["node"],
            "Create Blog Job",
        )
        self.assertEqual(workflow["settings"]["timezone"], "Asia/Kolkata")
        self.assertEqual(
            nodes["Schedule Daily Blog"]["parameters"]["rule"]["interval"][0]["expression"],
            "0 8 * * *",
        )
        self.assertEqual(
            workflow["connections"]["Revise Draft"]["main"][0][0]["node"],
            "Validate Blog",
        )
        self.assertEqual(
            nodes["Revision Limit"]["parameters"]["conditions"]["conditions"][0]["rightValue"],
            2,
        )
        self.assertIn("/v1/blog/approval/request", nodes["Request Human Approval"]["parameters"]["url"])
        self.assertEqual(
            workflow["connections"]["Validation Gate"]["main"][0][0]["node"],
            "Approval Payload Guard",
        )

    def test_approval_workflow_publishes_only_approved_status(self) -> None:
        workflow = self.load_workflow("blogging_approval_v1.json")
        nodes = {node["name"]: node for node in workflow["nodes"]}
        self.assertEqual(len(nodes), 9)
        gate = nodes["Approved Gate"]["parameters"]["conditions"]["conditions"][0]
        self.assertEqual(gate["rightValue"], "approved")
        self.assertEqual(
            workflow["connections"]["Approved Gate"]["main"][0][0]["node"],
            "Publish Approved Markdown",
        )
        self.assertEqual(
            workflow["connections"]["Approved Gate"]["main"][1][0]["node"],
            "Return Approval Result",
        )
        self.assertEqual(
            workflow["connections"]["Publish Approved Markdown"]["main"][0][0]["node"],
            "Index Approved Content",
        )

    def test_prompt_versions_and_required_knowledge_files_exist(self) -> None:
        prompt_dir = ROOT / "prompts" / "blogging" / "v1"
        expected = {"system.md", "outline.md", "draft.md", "seo.md", "validate.md", "revise.md"}
        self.assertEqual({path.name for path in prompt_dir.glob("*.md")}, expected)
        for path in prompt_dir.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("version: `v1`", text)
        for name in ("PRODUCT.md", "PRICING_FAQ.md", "API.md", "CONTENT_GUIDELINES.md"):
            self.assertTrue((ROOT / "knowledge" / name).is_file())

    def test_workflows_contain_no_embedded_credentials(self) -> None:
        for name in ("blogging_agent_v1.json", "blogging_approval_v1.json"):
            text = (ROOT / "workflows" / name).read_text(encoding="utf-8").lower()
            self.assertNotIn("password", text)
            self.assertNotIn("api_key", text)
            self.assertNotIn("secret", text)


if __name__ == "__main__":
    unittest.main()
