from __future__ import annotations

import ast
import copy
import json
import re
import unittest
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from cora_mcp.inbox_eval import score_triage


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "cora_mcp" / "inbox_eval.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "inbox_eval"

# Hard-coded from the reviewed design; the integrity test checks labels.json agrees.
HIGH = [f"ev-{n:03d}" for n in range(1, 13)]
MEDIUM = [f"ev-{n:03d}" for n in range(13, 33)] + ["ev-053"]
LOW = [f"ev-{n:03d}" for n in range(33, 53)]
NOISE = [f"ev-{n:03d}" for n in range(54, 81)]
ALL_IDS = [f"ev-{n:03d}" for n in range(1, 81)]
NOISE_REASON_COUNTS = {
    "empty_body": 4, "reaction": 3, "edit": 3, "delete": 3,
    "status_broadcast": 3, "system": 4, "duplicate": 3, "from_me": 4,
}
FIELDS = ["id", "channel", "chat_id", "chat_type", "sender_id", "sender_name", "from_me", "kind", "body", "ts"]
FORBIDDEN_IMPORTS = {
    "socket", "requests", "urllib", "http", "httpx", "aiohttp", "ssl", "anthropic", "openai", "random", "subprocess",
}

# Section 4.2: small hand-made example.
SMALL_LABELS = {
    "n1": {"noise": True, "noise_reason": "empty_body", "priority": None},
    "n2": {"noise": True, "noise_reason": "reaction", "priority": None},
    "n3": {"noise": True, "noise_reason": "system", "priority": None},
    "n4": {"noise": True, "noise_reason": "from_me", "priority": None},
    "k1": {"noise": False, "noise_reason": None, "priority": "high"},
    "k2": {"noise": False, "noise_reason": None, "priority": "high"},
    "k3": {"noise": False, "noise_reason": None, "priority": "medium"},
    "k4": {"noise": False, "noise_reason": None, "priority": "low"},
    "k5": {"noise": False, "noise_reason": None, "priority": "high"},
    "k6": {"noise": False, "noise_reason": None, "priority": "low"},
}
SMALL_ORDER = ["k1", "k3", "n4", "k2", "k4", "k6"]


def load_messages() -> list[dict[str, Any]]:
    lines = (FIXTURES / "messages.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def load_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


MESSAGES = load_messages()
BY_ID = {message["id"]: message for message in MESSAGES}
LABELS = load_json("labels.json")


def make_output(ids: list[str]) -> dict[str, Any]:
    return {
        "messages": [{**BY_ID[i], "score": float(len(ids) - n), "reasons": []} for n, i in enumerate(ids)],
        "dropped_by_reason": {},
    }


def bare_output(ids: list[str], scores: list[float] | None = None) -> dict[str, Any]:
    scores = scores or [float(len(ids) - n) for n in range(len(ids))]
    return {"messages": [{"id": i, "score": s, "reasons": []} for i, s in zip(ids, scores)]}


def expected(precision: float | None, recall: float | None, p5: float, p10: float,
             tp: int, fp: int, fn: int, top5: int, top10: int) -> dict[str, Any]:
    return {
        "noise_precision": precision,
        "noise_recall": recall,
        "precision_at_5": p5,
        "precision_at_10": p10,
        "counts": {
            "true_positives": tp, "false_positives": fp, "false_negatives": fn,
            "high_in_top_5": top5, "high_in_top_10": top10,
        },
    }


class ScoreAssertions(unittest.TestCase):
    def assertScores(self, result: dict[str, Any], want: dict[str, Any]) -> None:
        self.assertEqual(set(result), set(want))
        self.assertEqual(result["counts"], want["counts"])
        for key in ("noise_precision", "noise_recall", "precision_at_5", "precision_at_10"):
            with self.subTest(metric=key):
                if want[key] is None:
                    self.assertIsNone(result[key])
                else:
                    self.assertIsInstance(result[key], float)
                    self.assertAlmostEqual(result[key], want[key])


class RealLabelTests(ScoreAssertions):
    """Section 4.1: hand-worked cases on the real labels."""

    def test_perfect_output_scores_the_maximum(self) -> None:
        result = score_triage(make_output(HIGH + MEDIUM + LOW), LABELS)
        self.assertScores(result, expected(1.0, 1.0, 1.0, 1.0, 27, 0, 0, 5, 10))

    def test_inverted_filter_keeps_only_noise(self) -> None:
        result = score_triage(make_output(NOISE), LABELS)
        self.assertScores(result, expected(0.0, 0.0, 0.0, 0.0, 0, 53, 27, 0, 0))

    def test_perfect_filter_with_high_ranked_last(self) -> None:
        result = score_triage(make_output(LOW + MEDIUM + HIGH), LABELS)
        self.assertScores(result, expected(1.0, 1.0, 0.0, 0.0, 27, 0, 0, 0, 0))

    def test_dropping_nothing_gives_undefined_noise_precision(self) -> None:
        result = score_triage(make_output(ALL_IDS), LABELS)
        self.assertScores(result, expected(None, 0.0, 1.0, 1.0, 0, 0, 27, 5, 10))

    def test_dropping_everything(self) -> None:
        result = score_triage(make_output([]), LABELS)
        self.assertScores(result, expected(0.3375, 1.0, 0.0, 0.0, 27, 53, 0, 0, 0))

    def test_high_messages_in_slots_four_to_eight(self) -> None:
        head = ["ev-033", "ev-034", "ev-035", "ev-001", "ev-002", "ev-003", "ev-004", "ev-005", "ev-036", "ev-037"]
        rest = [i for i in sorted(HIGH + MEDIUM + LOW) if i not in head]
        result = score_triage(make_output(head + rest), LABELS)
        self.assertScores(result, expected(1.0, 1.0, 0.4, 0.5, 27, 0, 0, 2, 5))


class SmallExampleTests(ScoreAssertions):
    """Section 4.2 and edge cases E2, E3, E8, E9."""

    def test_partial_example(self) -> None:
        result = score_triage(bare_output(SMALL_ORDER), SMALL_LABELS)
        self.assertScores(result, expected(0.75, 0.75, 0.4, 0.2, 3, 1, 1, 2, 2))

    def test_fewer_than_k_kept_still_divides_by_k(self) -> None:
        result = score_triage(bare_output(SMALL_ORDER), SMALL_LABELS)
        self.assertAlmostEqual(result["precision_at_10"], 0.2)
        self.assertNotAlmostEqual(result["precision_at_10"], 2 / 6)

    def test_order_given_wins_over_scores(self) -> None:
        # k4 gets the largest score and k1 the smallest; the list order is unchanged.
        output = bare_output(SMALL_ORDER, scores=[0.1, 0.5, 0.4, 0.3, 9.0, 0.2])
        self.assertScores(score_triage(output, SMALL_LABELS), expected(0.75, 0.75, 0.4, 0.2, 3, 1, 1, 2, 2))

    def test_labels_without_noise_give_undefined_noise_metrics(self) -> None:
        labels = {
            "a": {"noise": False, "noise_reason": None, "priority": "high"},
            "b": {"noise": False, "noise_reason": None, "priority": "low"},
        }
        result = score_triage(bare_output(["a", "b"]), labels)
        self.assertScores(result, expected(None, None, 0.2, 0.1, 0, 0, 0, 1, 1))

    def test_noise_label_with_high_priority_is_accepted_but_never_counts_as_high(self) -> None:
        labels = {
            "n1": {"noise": True, "noise_reason": "system", "priority": "high"},
            "k1": {"noise": False, "noise_reason": None, "priority": "high"},
        }
        result = score_triage(bare_output(["n1", "k1"]), labels)
        self.assertScores(result, expected(None, 0.0, 0.2, 0.1, 0, 0, 1, 1, 1))

    def test_empty_labels_and_output(self) -> None:
        result = score_triage({"messages": []}, {})
        self.assertScores(result, expected(None, None, 0.0, 0.0, 0, 0, 0, 0, 0))


class ValidationTests(unittest.TestCase):
    """Edge cases E4-E7 and E10."""

    def test_unknown_output_id_raises(self) -> None:
        output = make_output(HIGH + MEDIUM + LOW)
        output["messages"].append({"id": "ev-999", "score": 0.0, "reasons": []})
        with self.assertRaisesRegex(ValueError, "unknown id in output: ev-999"):
            score_triage(output, LABELS)

    def test_duplicate_output_id_raises(self) -> None:
        output = make_output(HIGH + MEDIUM + LOW + ["ev-001"])
        with self.assertRaisesRegex(ValueError, "duplicate id in output: ev-001"):
            score_triage(output, LABELS)

    def test_bad_labels_raise(self) -> None:
        cases = {
            "not a dict": [],
            "entry not a dict": {"a": "high"},
            "noise missing": {"a": {"noise_reason": None, "priority": "high"}},
            "noise is text": {"a": {"noise": "yes", "noise_reason": None, "priority": "high"}},
            "noise is int": {"a": {"noise": 1, "noise_reason": "system", "priority": None}},
            "unknown priority": {"a": {"noise": False, "noise_reason": None, "priority": "urgent"}},
            "kept without priority": {"a": {"noise": False, "noise_reason": None, "priority": None}},
            "noise with unknown priority": {"a": {"noise": True, "noise_reason": "system", "priority": "urgent"}},
        }
        for name, labels in cases.items():
            with self.subTest(name):
                with self.assertRaises(ValueError):
                    score_triage({"messages": []}, labels)

    def test_bad_output_raises(self) -> None:
        cases = {
            "none": (None, "output must be a dict"),
            "list": ([], "output must be a dict"),
            "no messages key": ({}, "output must have a 'messages' list"),
            "messages not a list": ({"messages": "x"}, "output must have a 'messages' list"),
            "message not a dict": ({"messages": ["ev-001"]}, "message at index 0 has no text id"),
            "message without id": ({"messages": [{"score": 1.0}]}, "message at index 0 has no text id"),
            "non-text id": ({"messages": [{"id": 7}]}, "message at index 0 has no text id"),
            "empty id": ({"messages": [{"id": ""}]}, "message at index 0 has no text id"),
        }
        for name, (output, message) in cases.items():
            with self.subTest(name):
                with self.assertRaisesRegex(ValueError, message):
                    score_triage(output, LABELS)

    def test_labels_are_checked_before_output(self) -> None:
        with self.assertRaisesRegex(ValueError, "labels must be a dict"):
            score_triage(None, [])

    def test_ids_are_checked_in_list_order(self) -> None:
        output = bare_output(["ev-001", "ev-999", "ev-001"])
        with self.assertRaisesRegex(ValueError, "unknown id in output: ev-999"):
            score_triage(output, LABELS)


class BehaviourTests(ScoreAssertions):
    def test_dropped_by_reason_and_extra_keys_are_ignored(self) -> None:
        want = expected(1.0, 1.0, 1.0, 1.0, 27, 0, 0, 5, 10)
        without = make_output(HIGH + MEDIUM + LOW)
        del without["dropped_by_reason"]
        extra = make_output(HIGH + MEDIUM + LOW)
        extra["dropped_by_reason"] = {"empty_body": 999}
        extra["debug"] = {"anything": True}
        for name, output in (("without", without), ("extra", extra)):
            with self.subTest(name):
                self.assertScores(score_triage(output, LABELS), want)

    def test_inputs_are_not_mutated(self) -> None:
        output = make_output(HIGH + NOISE[:3] + LOW)
        labels = copy.deepcopy(LABELS)
        output_before, labels_before = copy.deepcopy(output), copy.deepcopy(labels)
        score_triage(output, labels)
        self.assertEqual(output, output_before)
        self.assertEqual(labels, labels_before)

    def test_same_input_gives_the_same_result(self) -> None:
        output = make_output(LOW[:4] + HIGH + MEDIUM)
        self.assertEqual(score_triage(output, LABELS), score_triage(output, LABELS))


class PurityTests(unittest.TestCase):
    def test_module_imports_no_network_llm_random_or_subprocess(self) -> None:
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported & FORBIDDEN_IMPORTS, set())

    def test_scoring_runs_with_sockets_disabled(self) -> None:
        with patch("socket.socket", side_effect=AssertionError("network access attempted")):
            result = score_triage(make_output(HIGH + MEDIUM + LOW), LABELS)
        self.assertEqual(result["counts"]["true_positives"], 27)


class FixtureIntegrityTests(unittest.TestCase):
    """Section 4.4."""

    def test_messages_and_labels_share_the_same_80_ids(self) -> None:
        ids = [message["id"] for message in MESSAGES]
        self.assertEqual(len(ids), 80)
        self.assertEqual(sorted(ids), ALL_IDS)
        self.assertEqual(list(LABELS), ALL_IDS)

    def test_messages_have_the_issue_41_fields_and_values(self) -> None:
        for message in MESSAGES:
            with self.subTest(message["id"]):
                self.assertEqual(list(message), FIELDS)
                self.assertIn(message["channel"], {"whatsapp", "telegram", "email"})
                self.assertIn(message["chat_type"], {"direct", "group", "broadcast"})
                self.assertIn(message["kind"], {"text", "reaction", "edit", "delete", "system", "media"})
                self.assertIsInstance(message["from_me"], bool)
                self.assertIsInstance(message["body"], str)
                ts = message["ts"]
                ts = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
                self.assertIsNotNone(datetime.fromisoformat(ts).tzinfo)

    def test_synthetic_only(self) -> None:
        patterns = [re.compile(p) for p in (r"https?://", r"[\w.]+@[\w-]+\.\w+", r"\d{7,}")]
        for message in MESSAGES:
            for field in ("body", "sender_name"):
                for pattern in patterns:
                    with self.subTest(id=message["id"], field=field, pattern=pattern.pattern):
                        self.assertIsNone(pattern.search(message[field]))

    def test_labels_are_consistent(self) -> None:
        for label_id, label in LABELS.items():
            with self.subTest(label_id):
                self.assertEqual(set(label), {"noise", "noise_reason", "priority"})
                if label["noise"] is True:
                    self.assertIn(label["noise_reason"], NOISE_REASON_COUNTS)
                    self.assertIsNone(label["priority"])
                else:
                    self.assertIs(label["noise"], False)
                    self.assertIsNone(label["noise_reason"])
                    self.assertIn(label["priority"], {"high", "medium", "low"})

    def test_every_noise_rule_appears_at_least_three_times(self) -> None:
        counts = Counter(label["noise_reason"] for label in LABELS.values() if label["noise"])
        self.assertEqual(dict(counts), NOISE_REASON_COUNTS)
        self.assertTrue(all(count >= 3 for count in counts.values()))

    def test_priority_groups_match_the_design(self) -> None:
        by_priority = {p: sorted(i for i, label in LABELS.items() if label["priority"] == p) for p in ("high", "medium", "low")}
        self.assertEqual(by_priority, {"high": HIGH, "medium": sorted(MEDIUM), "low": LOW})
        self.assertEqual(sorted(i for i, label in LABELS.items() if label["noise"]), NOISE)
        self.assertEqual((len(HIGH), len(MEDIUM), len(LOW)), (12, 21, 20))

    def test_profile_matches_the_messages(self) -> None:
        profile = load_json("profile.json")
        self.assertEqual(profile["owner_aliases"], ["Tova"])
        senders = {message["sender_id"] for message in MESSAGES}
        self.assertLessEqual(set(profile["vip"]), senders)
        self.assertEqual(len(profile["vip"]), 3)
        kept_bodies = [message["body"] for message in MESSAGES if LABELS[message["id"]]["noise"] is False]
        for topic in profile["pressing_topics"]:
            with self.subTest(topic):
                pattern = re.compile(r"(?<!\w)" + re.escape(topic) + r"(?!\w)", re.IGNORECASE)
                self.assertTrue(any(pattern.search(body) for body in kept_bodies))


if __name__ == "__main__":
    unittest.main()
