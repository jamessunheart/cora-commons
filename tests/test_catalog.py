from __future__ import annotations

import unittest

from cora_mcp.catalog import (
    capital_build_path,
    contribution_receipts,
    manifest,
    match_needs,
    needs,
    overview,
    pulse,
    read_text,
    recognition_board,
    search,
)


class CatalogTests(unittest.TestCase):
    def test_manifest_names_current_boundary(self) -> None:
        data = manifest()
        self.assertEqual(data["name"], "Cora Commons")
        self.assertEqual(data["hosted_mcp"], "https://fullpotential.com/mcp")
        self.assertIn("hosted read-only MCP endpoint", data["current_interfaces"])
        self.assertNotIn("hosted public MCP endpoint", data["not_live"])
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

    def test_search_is_bounded_to_public_records(self) -> None:
        results = search("verification reward", limit=3)
        self.assertTrue(results)
        self.assertLessEqual(len(results), 3)
        self.assertTrue(all(".." not in result["path"] for result in results))

    def test_match_explains_its_basis(self) -> None:
        matches = match_needs("agent onboarding testing")
        self.assertEqual(matches[0]["id"], "0001-agent-onboarding")
        self.assertGreater(matches[0]["match_score"], 0)
        self.assertIn("Matched on", matches[0]["reason"])

    def test_pulse_does_not_invent_cora(self) -> None:
        data = pulse()
        self.assertIsNone(data["cora_calculated"])
        self.assertIsNone(data["cora_available"])
        self.assertEqual(data["leaderboard"], [])
        self.assertEqual(data["recognition_board"], [])

    def test_recognition_uses_only_canonical_receipts(self) -> None:
        self.assertEqual(contribution_receipts(), [])
        self.assertEqual(recognition_board(), [])

    def test_capital_path_starts_with_evidence_not_currency(self) -> None:
        data = capital_build_path()
        self.assertEqual(data["priority_needs"][0]["id"], "0002-contribution-receipts")
        self.assertEqual(data["ordered_phases"][0], "evidence foundation")
        self.assertIn("Do not issue CORA", data["boundary"])


if __name__ == "__main__":
    unittest.main()
