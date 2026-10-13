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
                ["understand_commons", "list_open_needs", "contribution_path"],
            )
            for tool in result.tools:
                self.assertTrue(tool.annotations.read_only_hint)
                self.assertTrue(tool.annotations.idempotent_hint)

    async def test_server_exposes_canonical_resources_and_prompt(self) -> None:
        async with Client(mcp) as client:
            resources = await client.list_resources()
            prompts = await client.list_prompts()
            self.assertEqual(
                [str(resource.uri) for resource in resources.resources],
                ["cora://manifest", "cora://connect", "cora://agents"],
            )
            self.assertEqual([prompt.name for prompt in prompts.prompts], ["join_cora_commons"])

    async def test_understand_commons_returns_human_authority_boundary(self) -> None:
        async with Client(mcp) as client:
            result = await client.call_tool("understand_commons", {})
            self.assertFalse(result.is_error)
            self.assertEqual(result.structured_content["name"], "Cora Commons")
            self.assertIn("post", result.structured_content["requires_human_approval"])
            self.assertIn("CORA issuance", result.structured_content["not_live"])


if __name__ == "__main__":
    unittest.main()
