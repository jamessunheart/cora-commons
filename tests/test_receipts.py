from __future__ import annotations

import copy
import json
import math
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

    def test_rejects_boolean_and_non_finite_numbers(self) -> None:
        for field, value in (
            ("human_hours", True),
            ("human_hours", math.nan),
            ("human_hours", math.inf),
            ("cash_amount", False),
            ("cash_amount", math.nan),
            ("cash_amount", math.inf),
            ("cora_calculated", True),
            ("cora_funded", math.nan),
            ("cora_available", math.inf),
        ):
            receipt = copy.deepcopy(EXAMPLE)
            if field == "human_hours":
                receipt["delivery"]["capital_consumed"]["human_hours"] = value
                message = "delivery.capital_consumed.human_hours must be non-negative or null"
            elif field == "cash_amount":
                receipt["delivery"]["capital_consumed"]["cash"]["amount"] = value
                message = "delivery.capital_consumed.cash.amount must be non-negative or null"
            else:
                receipt["reward"][field] = value
                message = f"reward.{field} must be non-negative or null"
            self.assertIn(message, validate_receipt(receipt))

    def test_accepts_arbitrarily_large_integer_amounts(self) -> None:
        receipt = copy.deepcopy(EXAMPLE)
        huge_integer = 10**10_000
        receipt["delivery"]["capital_consumed"]["human_hours"] = huge_integer
        receipt["delivery"]["capital_consumed"]["cash"]["amount"] = huge_integer
        receipt["reward"]["cora_calculated"] = huge_integer
        receipt["reward"]["cora_funded"] = huge_integer
        receipt["reward"]["cora_available"] = huge_integer
        receipt["reward"]["status"] = "FUNDED"
        self.assertEqual(validate_receipt(receipt), [])

    def test_malformed_enum_values_report_errors_instead_of_crashing(self) -> None:
        cases = (
            ("contributors", 0, "kind", []),
            ("delivery", "capital_consumed", "cash", {"amount": 0, "currency": "USD", "status": {}}),
            ("review", None, "evidence_level", {}),
            ("reward", None, "status", []),
        )
        for section, nested, field, value in cases:
            receipt = copy.deepcopy(EXAMPLE)
            target = receipt[section]
            if nested == 0:
                target = target[nested]
            elif nested is not None:
                target = target[nested]
            target[field] = value
            errors = validate_receipt(receipt)
            self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
