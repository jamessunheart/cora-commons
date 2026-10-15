from __future__ import annotations

import unittest

from cora_mcp.steward import markdown_summary, review_event


def michael_style_event() -> dict[str, object]:
    return {
        "event_name": "issue_comment", "action": "created",
        "issue": {"number": 1, "title": "Founding onboarding test", "body": "Test the connection path.", "html_url": "https://github.com/jamessunheart/cora-commons/issues/1", "user": {"login": "jamessunheart"}, "labels": []},
        "comment": {"body": "I delivered an onboarding report. Deliverable: a report of the agent path. Acceptance evidence: the path was reproduced. Limitations: one participant. Cost: 20 human minutes and 10 agent minutes.", "html_url": "https://github.com/jamessunheart/cora-commons/issues/1#issuecomment-1", "user": {"login": "humaniterrian"}},
    }


class StewardTests(unittest.TestCase):
    def test_delivered_event_is_ready_for_independent_review(self) -> None:
        packet = review_event(michael_style_event())
        self.assertEqual(packet["status"], "READY_FOR_REVIEW")
        self.assertEqual(packet["event"]["issue_number"], 1)
        self.assertFalse(packet["receipt"]["created"])

    def test_missing_evidence_stays_needs_info(self) -> None:
        event = michael_style_event()
        event["comment"]["body"] = "I built something useful."
        packet = review_event(event)
        self.assertEqual(packet["status"], "NEEDS_INFO")
        self.assertIn("acceptance evidence", packet["evidence"]["missing_fields"])
        self.assertIn("cost disclosure", packet["evidence"]["missing_fields"])

    def test_steward_does_not_infer_agent_or_reward(self) -> None:
        packet = review_event(michael_style_event())
        self.assertTrue(packet["participants"]["human_and_agent_to_confirm"])
        self.assertEqual(packet["receipt"]["status"], "DRAFT_ONLY")
        self.assertIn("issue CORA", packet["authority_boundary"])

    def test_summary_is_explicitly_non_acceptance(self) -> None:
        summary = markdown_summary(review_event(michael_style_event()))
        self.assertIn("Cora Steward review packet", summary)
        self.assertIn("not acceptance", summary)


if __name__ == "__main__":
    unittest.main()
