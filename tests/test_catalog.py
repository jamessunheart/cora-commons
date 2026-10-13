from __future__ import annotations

import unittest

from cora_mcp.catalog import manifest, needs, overview, read_text


class CatalogTests(unittest.TestCase):
    def test_manifest_names_current_boundary(self) -> None:
        data = manifest()
        self.assertEqual(data["name"], "Cora Commons")
        self.assertIn("hosted public MCP endpoint", data["not_live"])
        self.assertIn("read", data["default_agent_authority"])

    def test_open_needs_are_structured(self) -> None:
        records = needs()
        self.assertTrue(records)
        self.assertEqual(records[0]["id"], "0001-agent-onboarding")
        self.assertTrue(records[0]["url"].startswith("https://github.com/"))

    def test_overview_preserves_human_approval(self) -> None:
        data = overview()
        self.assertIn("post", data["requires_human_approval"])
        self.assertIn("wait for human approval", data["next_step"].lower())

    def test_reader_rejects_path_escape(self) -> None:
        with self.assertRaises(ValueError):
            read_text("../private.txt")


if __name__ == "__main__":
    unittest.main()
