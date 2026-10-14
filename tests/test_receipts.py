from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from cora_mcp.receipts import validate_receipt


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((ROOT / "CONTRIBUTIONS" / "examples" / "CR-EXAMPLE-0001.json").read_text())


class ReceiptValidationTests(unittest.TestCase):
    def test_example_receipt_is_valid(self) -> None:
        self.assertEqual(validate_receipt(EXAMPLE, "CR-EXAMPLE-0001.json"), [])

    def test_rejects_self_approval(self) -> None:
        receipt = copy.deepcopy(EXAMPLE)
        receipt["review"]["reviewer_id"] = "human-example"
        self.assertIn("reviewer_id must not be a contributor id", validate_receipt(receipt))

    def test_requires_independence_statement(self) -> None:
        receipt = copy.deepcopy(EXAMPLE)
        del receipt["review"]["independence_statement"]
        self.assertIn("review.independence_statement must be a non-empty string", validate_receipt(receipt))

    def test_rejects_recognition_only_cora_amount(self) -> None:
        receipt = copy.deepcopy(EXAMPLE)
        receipt["reward"]["cora_calculated"] = 10
        self.assertIn(
            "recognition-only receipts cannot report calculated, funded or available CORA",
            validate_receipt(receipt),
        )

    def test_rejects_available_without_backing(self) -> None:
        receipt = copy.deepcopy(EXAMPLE)
        receipt["reward"]["status"] = "AVAILABLE"
        receipt["reward"]["cora_available"] = 10
        self.assertIn("CORA cannot be available without funded or service-backed capacity", validate_receipt(receipt))

    def test_rejects_backward_state_history(self) -> None:
        receipt = copy.deepcopy(EXAMPLE)
        receipt["status"] = "ACCEPTED"
        receipt["events"].append(
            {"event_id": "event-bad", "type": "RECORDED", "at": "2026-10-13T15:00:00Z", "actor": "reviewer-example"}
        )
        self.assertIn("receipt state events cannot move backwards", validate_receipt(receipt))

    def test_rejects_wrong_filename(self) -> None:
        self.assertIn(
            "filename must be CR-EXAMPLE-0001.json",
            validate_receipt(EXAMPLE, "wrong.json"),
        )


if __name__ == "__main__":
    unittest.main()
