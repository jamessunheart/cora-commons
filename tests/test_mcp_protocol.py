from __future__ import annotations

import unittest

from mcp import Client

from cora_mcp.server import mcp


class MCPProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_exposes_only_read_only_tools(self) -> None:
        async with Client(mcp) as client:
            result = await client.list_tools()
            self.assertEqual(
                [tool.name for tool in result.tools],
                [
                    "understand_commons",
                    "list_open_needs",
                    "get_need",
                    "list_accepted_bricks",
                    "search_commons",
                    "match_contribution",
                    "draft_contribution_proposal",
                    "validate_contribution_proposal",
                    "commons_pulse",
                    "contribution_path",
                    "capital_commons_build_path",
                    "list_contribution_receipts",
                    "get_contribution_receipt",
                    "commons_recognition",
                    "recognition_path",
                ],
            )
            for tool in result.tools:
                self.assertTrue(tool.annotations.read_only_hint)
                self.assertTrue(tool.annotations.idempotent_hint)

    async def test_server_exposes_canonical_resources_and_prompt(self) -> None:
        async with Client(mcp) as client:
            resources = await client.list_resources()
            templates = await client.list_resource_templates()
            prompts = await client.list_prompts()
            self.assertEqual(
                [str(resource.uri) for resource in resources.resources],
                ["cora://manifest", "cora://connect", "cora://agents", "cora://capital"],
            )
            self.assertEqual(
                [str(template.uri_template) for template in templates.resource_templates],
                ["cora://needs/{need_id}", "cora://bricks/{brick_id}", "cora://receipts/{receipt_id}"],
            )
            self.assertEqual([prompt.name for prompt in prompts.prompts], ["join_cora_commons"])

    async def test_understand_commons_returns_human_authority_boundary(self) -> None:
        async with Client(mcp) as client:
            result = await client.call_tool("understand_commons", {})
            self.assertFalse(result.is_error)
            self.assertEqual(result.structured_content["name"], "Cora Commons")
            self.assertIn("post", result.structured_content["requires_human_approval"])
            self.assertIn("CORA issuance", result.structured_content["not_live"])

    async def test_matching_drafting_validation_and_pulse(self) -> None:
        async with Client(mcp) as client:
            matched = await client.call_tool(
                "match_contribution",
                {"capabilities": "agent onboarding testing", "time_budget_hours": 2},
            )
            self.assertEqual(matched.structured_content["matches"][0]["id"], "0001-agent-onboarding")

            draft = await client.call_tool(
                "draft_contribution_proposal",
                {
                    "need_id": "0001-agent-onboarding",
                    "human": "Example Human",
                    "agent": "Example Agent",
                    "deliverable": "Test the connection guide",
                    "acceptance_evidence": "A newcomer completes it without coaching",
                    "expected_cost": "Two human hours; AI cost unknown",
                    "limitations": "One client and one participant",
                },
            )
            self.assertEqual(draft.structured_content["status"], "draft_only")
            self.assertTrue(draft.structured_content["requires_human_approval_before_posting"])

            validation = await client.call_tool(
                "validate_contribution_proposal",
                {
                    "need_id": "0001-agent-onboarding",
                    "human": "Example Human",
                    "agent": "Example Agent",
                    "deliverable": "Test the connection guide",
                    "acceptance_evidence": "A newcomer completes it without coaching",
                    "expected_cost": "Two human hours; AI cost unknown",
                    "limitations": "One client and one participant",
                },
            )
            self.assertTrue(validation.structured_content["complete"])

            current = await client.call_tool("commons_pulse", {})
            self.assertIsNone(current.structured_content["cora_calculated"])
            self.assertEqual(current.structured_content["leaderboard"], [])

            recognition = await client.call_tool("commons_recognition", {})
            self.assertEqual(recognition.structured_content["contributors"], [])
            self.assertIn("not CORA issuance", recognition.structured_content["boundary"])

            path = await client.call_tool("recognition_path", {})
            self.assertIn("recognition.yml", path.structured_content["submit"])
            self.assertIn("commits", path.structured_content["boundary"])


if __name__ == "__main__":
    unittest.main()
