from __future__ import annotations

import ast
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

from cora_mcp.tripwires import DEFAULT_RULES, Action, _parse_timestamp, evaluate


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
MODULE = SRC / "cora_mcp" / "tripwires.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tripwires"
NOW_TEXT = "2026-11-21T10:00:00Z"
NOW = datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc)
PLUS_TWO = timezone(timedelta(hours=2))

RULE_ACTIONS = {
    "fuel": ("pause_non_foundation", None),
    "churn": ("park", "T-1"),
    "cluster": ("ensure_foundation", "db migration"),
    "stall": ("restart", "indexer"),
    "order": ("promote", "T-6"),
    "promise": ("flag_red", "C-1"),
}
FORBIDDEN_IMPORTS = {
    "socket", "requests", "urllib", "http", "httpx", "aiohttp", "ssl", "anthropic", "openai", "random", "subprocess",
}


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def pairs(actions: list[Action]) -> list[tuple[str, str | None]]:
    return [(action.kind, action.target) for action in actions]


def run_all(state: object, now: datetime = NOW) -> list[tuple[str, str | None]]:
    return pairs(evaluate(state, DEFAULT_RULES, now))


def run_cli(*args: str, hash_seed: str | None = None) -> subprocess.CompletedProcess[bytes]:
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    if hash_seed is not None:
        env["PYTHONHASHSEED"] = hash_seed
    return subprocess.run(
        [sys.executable, "-m", "cora_mcp.tripwires", *args],
        capture_output=True,
        env=env,
        check=False,
    )


class RuleThresholdTests(unittest.TestCase):
    def test_each_rule_fires_exactly_at_its_threshold(self) -> None:
        for rule, expected in RULE_ACTIONS.items():
            with self.subTest(rule=rule):
                actions = evaluate(load(f"{rule}_fires.json"), DEFAULT_RULES, NOW)
                self.assertEqual(pairs(actions), [expected])
                self.assertIsInstance(actions[0].reason, str)
                self.assertTrue(actions[0].reason.strip())

    def test_each_rule_is_quiet_just_under_its_threshold(self) -> None:
        for rule in RULE_ACTIONS:
            with self.subTest(rule=rule):
                self.assertEqual(evaluate(load(f"{rule}_quiet.json"), DEFAULT_RULES, NOW), [])

    def test_fuel_cutoff_is_18_00_utc(self) -> None:
        state = load("fuel_fires.json")
        self.assertEqual(run_all(state, datetime(2026, 11, 21, 17, 59, 59, tzinfo=timezone.utc)), [RULE_ACTIONS["fuel"]])
        self.assertEqual(run_all(state, datetime(2026, 11, 21, 18, 0, 0, tzinfo=timezone.utc)), [])

    def test_aware_now_in_another_offset_is_compared_in_utc(self) -> None:
        fuel = load("fuel_fires.json")
        self.assertEqual(run_all(fuel, datetime(2026, 11, 21, 19, 59, 59, tzinfo=PLUS_TWO)), [RULE_ACTIONS["fuel"]])
        self.assertEqual(run_all(fuel, datetime(2026, 11, 21, 20, 0, 0, tzinfo=PLUS_TWO)), [])
        promise = load("promise_quiet.json")
        self.assertEqual(run_all(promise, datetime(2026, 11, 21, 12, 0, 0, tzinfo=PLUS_TWO)), [])
        self.assertEqual(run_all(promise, datetime(2026, 11, 21, 12, 0, 1, tzinfo=PLUS_TWO)), [RULE_ACTIONS["promise"]])

    def test_naive_now_and_timestamps_are_treated_as_utc(self) -> None:
        self.assertEqual(run_all(load("fuel_fires.json"), datetime(2026, 11, 21, 17, 59, 59)), [RULE_ACTIONS["fuel"]])
        naive_now = datetime(2026, 11, 21, 10, 0, 0)
        for last_moved, expected in (("2026-11-19T09:59:59", [("flag_red", "C-1")]), ("2026-11-19T10:00:00", [])):
            with self.subTest(last_moved=last_moved):
                state = {"commitments": [{"id": "C-1", "opened": "2026-11-01T00:00:00", "last_moved": last_moved}]}
                self.assertEqual(run_all(state, naive_now), expected)

    def test_promise_falls_back_to_opened_when_last_moved_is_missing(self) -> None:
        for commitment in (
            {"id": "C-1", "opened": "2026-11-19T09:59:59Z"},
            {"id": "C-1", "opened": "2026-11-19T09:59:59Z", "last_moved": None},
        ):
            with self.subTest(commitment=commitment):
                self.assertEqual(run_all({"commitments": [commitment]}), [("flag_red", "C-1")])
        self.assertEqual(run_all({"commitments": [{"id": "C-1", "opened": "2026-11-19T10:00:00Z"}]}), [])

    def test_promise_falls_back_to_opened_when_last_moved_is_unusable(self) -> None:
        cases = {"absent": {}, "null": {"last_moved": None}, "empty": {"last_moved": ""}, "unreadable": {"last_moved": "n/a"}}
        for name, extra in cases.items():
            with self.subTest(last_moved=name):
                stale = {"id": "C-1", "opened": "2026-11-19T09:59:59Z", **extra}
                actions = evaluate({"commitments": [stale]}, DEFAULT_RULES, NOW)
                self.assertEqual(pairs(actions), [("flag_red", "C-1")])
                self.assertIn("since opened 2026-11-19T09:59:59Z", actions[0].reason)
                fresh = {"id": "C-1", "opened": "2026-11-19T10:00:00Z", **extra}
                self.assertEqual(run_all({"commitments": [fresh]}), [])

    def test_commitment_with_unreadable_last_moved_and_opened_is_skipped(self) -> None:
        self.assertEqual(run_all({"commitments": [{"id": "C-1", "opened": "bad", "last_moved": "n/a"}]}), [])

    def test_lowercase_z_suffix_is_utc(self) -> None:
        self.assertEqual(run_all({"commitments": [{"id": "C-1", "opened": "2026-11-19T09:59:59z"}]}), [("flag_red", "C-1")])
        self.assertEqual(run_all({"commitments": [{"id": "C-1", "opened": "2026-11-19T10:00:00z"}]}), [])
        self.assertEqual(_parse_timestamp("2026-11-21T17:59:59z"), datetime(2026, 11, 21, 17, 59, 59, tzinfo=timezone.utc))


class RobustnessTests(unittest.TestCase):
    def test_negative_minutes_or_grace_are_skipped(self) -> None:
        workers = [
            {"name": "w1", "minutes_since_write": 0, "grace_minutes": -5},
            {"name": "w2", "minutes_since_write": -1, "grace_minutes": -1},
            {"name": "w3", "minutes_since_write": -100, "grace_minutes": 0},
        ]
        self.assertEqual(run_all({"workers": workers}), [])

    def test_bools_nan_infinity_and_numeric_strings_are_not_numbers(self) -> None:
        for bad in (True, math.nan, math.inf, "85", None):
            with self.subTest(value=bad):
                self.assertEqual(run_all({"fuel_pct": bad}), [])
                self.assertEqual(run_all({"workers": [{"name": "w", "minutes_since_write": bad, "grace_minutes": 0}]}), [])
                self.assertEqual(run_all({"workers": [{"name": "w", "minutes_since_write": 99, "grace_minutes": bad}]}), [])

    def test_tasks_without_a_numeric_sort_order_are_not_ranked(self) -> None:
        state = load("order_quiet.json")
        state["tasks"].insert(0, {"id": "T-0", "tags": [], "sort_order": "0", "blocked_reasons": []})
        state["tasks"].insert(0, {"id": "T-00", "tags": [], "sort_order": True, "blocked_reasons": []})
        self.assertEqual(run_all(state), [])

    def test_out_of_range_or_invalid_timestamps_are_skipped(self) -> None:
        for timestamp in ("0001-01-01T00:00:00+01:00", "9999-12-31T23:00:00-02:00", "not-a-date", "", 1700000000):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(run_all({"commitments": [{"id": "C-1", "opened": timestamp}]}), [])

    def test_wrong_type_tags_and_blocked_reasons_are_ignored(self) -> None:
        order = load("order_fires.json")
        order["tasks"][-1]["tags"] = "foundation"
        self.assertEqual(run_all(order), [])
        for reasons in ("waiting on review", None, {"a": "a"}, [1, 1, None, None, ["a"], ["a"]]):
            with self.subTest(blocked_reasons=reasons):
                tasks = [{"id": f"T-{index}", "blocked_reasons": reasons} for index in range(3)]
                self.assertEqual(run_all({"tasks": tasks}), [])

    def test_whitespace_only_blocked_reasons_are_ignored(self) -> None:
        for blank in (" ", "   ", "\t", " \n "):
            with self.subTest(reason=blank):
                tasks = [{"id": f"T-{index}", "blocked_reasons": [blank, blank]} for index in range(3)]
                self.assertEqual(run_all({"tasks": tasks}), [])

    def test_integer_task_ids_give_the_same_actions_as_text_ids(self) -> None:
        def state(make_id: Any) -> dict[str, Any]:
            return {"tasks": [
                {"id": make_id(n), "tags": ["foundation"] if n == 6 else [], "sort_order": n, "blocked_reasons": ["x", "x"]}
                for n in range(1, 7)
            ]}
        expected = [("park", str(n)) for n in range(1, 7)] + [("ensure_foundation", "x"), ("promote", "6")]
        self.assertEqual(run_all(state(str)), expected)
        self.assertEqual(run_all(state(int)), expected)
        self.assertEqual(evaluate(state(int), DEFAULT_RULES, NOW), evaluate(state(str), DEFAULT_RULES, NOW))

    def test_bool_and_other_non_text_task_ids_are_refused(self) -> None:
        for bad in (True, False, 1.0, None, "", "  ", ["T-1"]):
            with self.subTest(task_id=bad):
                tasks = [{"id": bad, "tags": ["foundation"], "sort_order": 9, "blocked_reasons": ["x", "x"]}] * 3
                self.assertEqual(run_all({"tasks": tasks}), [])

    def test_duplicate_task_ids_count_once_for_cluster(self) -> None:
        state = load("cluster_fires.json")
        for task in state["tasks"]:
            task["id"] = "T-1"
        self.assertEqual(run_all(state), [])

    def test_empty_or_wrongly_shaped_state_gives_no_actions(self) -> None:
        for state in (
            {},
            {"fuel_pct": 0, "tasks": [], "workers": [], "commitments": []},
            {"tasks": "abc", "workers": None, "commitments": {}},
            {"tasks": [1, "x", None], "workers": [[]], "commitments": ["C-1"]},
        ):
            with self.subTest(state=state):
                self.assertEqual(run_all(state), [])


class ErrorTests(unittest.TestCase):
    def test_unknown_or_missing_rule_type_raises(self) -> None:
        for rules in ([{"type": "weather"}], [{}], ["fuel"], [{"type": ["fuel"]}]):
            with self.subTest(rules=rules):
                with self.assertRaises(ValueError):
                    evaluate({}, rules, NOW)

    def test_state_that_is_not_a_dict_raises(self) -> None:
        for state in ([], None, "{}"):
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, "state must be a JSON object"):
                    evaluate(state, DEFAULT_RULES, NOW)

    def test_non_number_rule_parameter_raises(self) -> None:
        for rule in ({"type": "stall", "multiplier": "3"}, {"type": "fuel", "threshold": True}, {"type": "promise", "hours": None}):
            with self.subTest(rule=rule):
                with self.assertRaisesRegex(ValueError, "must be a number"):
                    evaluate({}, [rule], NOW)


class RulesArgumentTests(unittest.TestCase):
    def test_only_the_listed_rules_run(self) -> None:
        state = load("all_rules.json")
        self.assertEqual(pairs(evaluate(state, [{"type": "stall"}], NOW)), [("restart", "indexer")])
        self.assertEqual(
            pairs(evaluate(state, [{"type": "promise"}, {"type": "fuel"}], NOW)),
            [("flag_red", "C-1"), ("pause_non_foundation", None)],
        )

    def test_rule_parameters_override_the_defaults(self) -> None:
        state = load("all_rules.json")
        self.assertEqual(evaluate(state, [{"type": "fuel", "threshold": 90}], NOW), [])
        self.assertEqual(pairs(evaluate(state, [{"type": "stall", "multiplier": 2.9}], NOW)), [("restart", "indexer"), ("restart", "mailer")])

    def test_empty_rules_list_gives_no_actions(self) -> None:
        self.assertEqual(evaluate(load("all_rules.json"), [], NOW), [])


class DeterminismTests(unittest.TestCase):
    def test_input_order_never_changes_the_output(self) -> None:
        state = load("all_rules.json")
        baseline = evaluate(state, DEFAULT_RULES, NOW)
        for seed in range(50):
            rng = random.Random(seed)
            shuffled = {key: rng.sample(value, len(value)) if isinstance(value, list) else value for key, value in state.items()}
            with self.subTest(seed=seed):
                self.assertEqual(evaluate(shuffled, DEFAULT_RULES, NOW), baseline)

    def test_actions_are_sorted_by_target_and_reason_whatever_the_input_order(self) -> None:
        state = load("sorting.json")
        expected = [
            ("park", "T-1"), ("park", "T-2"),
            ("restart", "indexer"), ("restart", "mailer"),
            ("promote", "T-6"), ("promote", "T-7"),
            ("flag_red", "C-1"), ("flag_red", "C-2"),
        ]
        orders = {"direct": state, "reversed": {key: value[::-1] if isinstance(value, list) else value for key, value in state.items()}}
        for seed in range(20):
            rng = random.Random(seed)
            orders[f"shuffled {seed}"] = {key: rng.sample(value, len(value)) if isinstance(value, list) else value for key, value in state.items()}
        for name, ordered in orders.items():
            with self.subTest(order=name):
                actions = evaluate(ordered, DEFAULT_RULES, NOW)
                self.assertEqual(pairs(actions), expected)
                for kind in ("park", "restart", "promote", "flag_red"):
                    group = [action for action in actions if action.kind == kind]
                    self.assertEqual(len(group), 2)
                    self.assertEqual(group, sorted(group, key=lambda action: (action.target, action.reason)))

    def test_order_ties_on_sort_order_are_broken_by_id(self) -> None:
        ahead = [{"id": f"T-{n}", "tags": [], "sort_order": n, "blocked_reasons": []} for n in range(1, 5)]
        tied = [{"id": task_id, "tags": ["foundation"], "sort_order": 5, "blocked_reasons": []} for task_id in ("T-C", "T-A", "T-B")]
        # Ranked: T-1..T-4, then T-A (5th), T-B (6th), T-C (7th) -> only T-B and T-C are outside the top 5.
        expected = [("promote", "T-B"), ("promote", "T-C")]
        for name, tasks in {"tied first": tied + ahead, "tied reversed": ahead + tied[::-1]}.items():
            with self.subTest(order=name):
                actions = evaluate({"tasks": tasks}, [{"type": "order"}], NOW)
                self.assertEqual(pairs(actions), expected)
                self.assertEqual([action.reason.split(" ranked ")[1].split(" ")[0] for action in actions], ["6", "7"])

    def test_evaluate_twice_gives_equal_results(self) -> None:
        state = load("all_rules.json")
        self.assertEqual(evaluate(state, DEFAULT_RULES, NOW), evaluate(state, DEFAULT_RULES, NOW))


class CliTests(unittest.TestCase):
    def test_cli_output_matches_expected_fixture_byte_for_byte(self) -> None:
        result = run_cli("--state", str(FIXTURES / "all_rules.json"), "--now", NOW_TEXT)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = (FIXTURES / "all_rules.expected.jsonl").read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(result.stdout, expected)
        self.assertEqual(result.stderr, b"")

    def test_cli_writes_lf_only_json_lines(self) -> None:
        result = run_cli("--state", str(FIXTURES / "all_rules.json"), "--now", NOW_TEXT)
        self.assertNotIn(b"\r", result.stdout)
        self.assertTrue(result.stdout.endswith(b"\n"))
        for line in result.stdout.decode("utf-8").splitlines():
            self.assertEqual(set(json.loads(line)), {"kind", "target", "reason"})

    def test_cli_output_is_byte_identical_across_runs_and_hash_seeds(self) -> None:
        args = ("--state", str(FIXTURES / "all_rules.json"), "--now", NOW_TEXT)
        first, second = run_cli(*args), run_cli(*args)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(run_cli(*args, hash_seed="1").stdout, run_cli(*args, hash_seed="2").stdout)
        self.assertEqual(first.stdout, run_cli(*args, hash_seed="1").stdout)

    def test_ticket_form_without_now_prints_json_lines(self) -> None:
        result = run_cli("--state", str(FIXTURES / "all_rules.json"))
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.decode("utf-8").splitlines()
        self.assertGreaterEqual(len(lines), 1, "the CLI printed no actions")
        for line in lines:
            self.assertEqual(set(json.loads(line)), {"kind", "target", "reason"})

    def test_bad_input_exits_non_zero_with_one_error_line_and_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            malformed = Path(temporary_directory) / "malformed.json"
            malformed.write_text("{not json", encoding="utf-8")
            not_an_object = Path(temporary_directory) / "list.json"
            not_an_object.write_text("[]", encoding="utf-8")
            cases = {
                "missing file": ("--state", str(Path(temporary_directory) / "missing.json")),
                "malformed JSON": ("--state", str(malformed)),
                "not an object": ("--state", str(not_an_object)),
                "invalid --now": ("--state", str(FIXTURES / "all_rules.json"), "--now", "yesterday"),
            }
            for name, args in cases.items():
                with self.subTest(case=name):
                    result = run_cli(*args)
                    stderr = result.stderr.decode("utf-8", errors="replace")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b"")
                    self.assertNotIn("Traceback", stderr)
                    self.assertEqual(len([line for line in stderr.splitlines() if "error:" in line]), 1, stderr)


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

    def test_evaluate_runs_with_sockets_disabled(self) -> None:
        expected = [
            json.loads(line)
            for line in (FIXTURES / "all_rules.expected.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        with patch("socket.socket", side_effect=AssertionError("network access attempted")):
            actions = evaluate(load("all_rules.json"), DEFAULT_RULES, NOW)
        self.assertEqual([{"kind": a.kind, "target": a.target, "reason": a.reason} for a in actions], expected)


if __name__ == "__main__":
    unittest.main()
