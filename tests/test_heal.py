import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from heal import MAX_ARGUMENT_BYTES, MAX_COMMAND_BYTES, find_stuck


NOW = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)


def worker(worker_id="w1", state="running", heartbeat="2026-11-23T11:59Z"):
    return {"id": worker_id, "state": state, "last_heartbeat": heartbeat}


class DetectionTests(unittest.TestCase):
    def test_healthy(self):
        self.assertEqual(find_stuck([worker()], NOW), [])

    def test_stale(self):
        rows = [worker(heartbeat="2026-11-23T11:49:59.999999Z")]
        self.assertEqual(find_stuck(rows, NOW), ["w1"])

    def test_crashed_with_fresh_heartbeat(self):
        self.assertEqual(find_stuck([worker(state="crashed")], NOW), ["w1"])

    def test_crashed_without_heartbeat(self):
        self.assertEqual(find_stuck([{"id": "w1", "state": "crashed"}], NOW), ["w1"])

    def test_exactly_ten_minutes_with_offset(self):
        for offset in ("+03:00", "+0300", "+03"):
            with self.subTest(offset=offset):
                rows = [worker(heartbeat=f"2026-11-23T14:50:00{offset}")]
                self.assertEqual(find_stuck(rows, NOW), [])

    def test_one_microsecond_past_ten_minutes_with_offset(self):
        rows = [worker(heartbeat="2026-11-23T14:49:59.999999+03:00")]
        self.assertEqual(find_stuck(rows, NOW), ["w1"])


class HealerCLITests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.workdir = Path(directory.name)
        self.workers = self.workdir / "workers.json"
        self.config = self.workdir / "config.json"
        self.report = self.workdir / "heal.json"
        self.marker = self.workdir / "ran.txt"
        self.command = [
            sys.executable, "-c",
            "from pathlib import Path; import sys; Path('ran.txt').write_text(sys.argv[1])",
            "configured $HOME && literal",
        ]
        self.write_json(self.config, {"w1": self.command})
        self.write_json(self.workers, [worker(state="crashed")])

    def write_json(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def run_cli(self, *options):
        return subprocess.run(
            [sys.executable, str(ROOT / "heal.py"), "--workers", str(self.workers),
             "--config", str(self.config), *options],
            cwd=self.workdir, capture_output=True, text=True,
        )

    def test_default_dry_run_prints_stuck_and_writes_plan(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Dry-run | Stuck workers (1): ["w1"]', result.stdout)
        report = json.loads(self.report.read_text())
        self.assertEqual(set(report), {"checked_at", "stuck", "actions"})
        self.assertEqual(datetime.fromisoformat(report["checked_at"]).utcoffset(), timedelta(0))
        self.assertEqual(report["stuck"], ["w1"])
        self.assertEqual(report["actions"], [{"id": "w1", "command": self.command}])
        self.assertFalse(self.marker.exists())

    def test_apply_uses_only_trusted_command(self):
        row = worker(state="crashed")
        row["command"] = [sys.executable, "-c", "open('untrusted.txt', 'w').close()"]
        self.write_json(self.workers, [row])
        result = self.run_cli("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.marker.read_text(), self.command[-1])
        self.assertFalse((self.workdir / "untrusted.txt").exists())

    def test_apply_abbreviations_are_usage_errors(self):
        for option in ("--a", "--ap", "--app", "--appl"):
            with self.subTest(option=option):
                result = self.run_cli(option)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("usage:", result.stderr)
                self.assertFalse(self.marker.exists())
                self.assertFalse(self.report.exists())

    def test_empty_snapshot(self):
        self.write_json(self.workers, [])
        result = self.run_cli("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(self.report.read_text())
        self.assertEqual(report["stuck"], [])
        self.assertEqual(report["actions"], [])
        self.assertFalse(self.marker.exists())

    def assert_rejected_before_apply(self, message):
        self.report.write_text("previous report")
        result = self.run_cli("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.report.read_text(), "previous report")
        self.assertFalse(self.marker.exists())

    def assert_collision_rejected(self, option):
        original = self.report.read_bytes()
        result = self.run_cli("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"{option} input and output heal.json refer to the same file", result.stderr)
        self.assertEqual(self.report.read_bytes(), original)
        self.assertFalse(self.marker.exists())

    def test_workers_path_collides_with_report(self):
        self.workers = self.workers.rename(self.report)
        self.assert_collision_rejected("--workers")

    def test_config_path_collides_with_report(self):
        self.config = self.config.rename(self.report)
        self.assert_collision_rejected("--config")

    def test_workers_symlink_to_report(self):
        self.workers.rename(self.report)
        self.workers.symlink_to(self.report)
        self.assert_collision_rejected("--workers")

    def test_report_symlink_to_config(self):
        self.report.symlink_to(self.config)
        self.assert_collision_rejected("--config")
        self.assertTrue(self.report.is_symlink())

    def test_report_hard_link_to_workers(self):
        self.report.hardlink_to(self.workers)
        self.assert_collision_rejected("--workers")

    def test_validates_every_required_command_before_apply(self):
        self.write_json(self.workers, [worker(state="crashed"), worker("w2", "crashed")])
        for extra in ({}, {"w2": "echo wrong"}, {"w2": []}, {"w2": [42]},
                      {"w2": [sys.executable, "bad\x00argument"]},
                      {"w2": [sys.executable, "\ud800"]},
                      {"w2": ["missing-synthetic-governor-executable"]}):
            with self.subTest(extra=extra):
                self.write_json(self.config, {"w1": self.command, **extra})
                self.assert_rejected_before_apply("w2")

    def test_invalid_unused_command_prevents_apply(self):
        self.write_json(self.config, {"w1": self.command, "idle": [sys.executable, None]})
        self.assert_rejected_before_apply("idle")

    def test_second_command_exceeds_argument_limit(self):
        self.write_json(self.workers, [worker(state="crashed"), worker("w2", "crashed")])
        # The character count fits, but the UTF-8 byte count exceeds the limit.
        oversized = "é" * (MAX_ARGUMENT_BYTES // 2 + 1)
        command = [sys.executable, "-c", "pass", oversized]
        self.write_json(self.config, {"w1": self.command, "w2": command})
        self.assert_rejected_before_apply(f"w2: restart argument exceeds {MAX_ARGUMENT_BYTES} bytes")

    def test_second_command_exceeds_total_limit(self):
        self.write_json(self.workers, [worker(state="crashed"), worker("w2", "crashed")])
        # Each argument fits individually. The executable and terminators also count.
        chunks = ["x" * MAX_ARGUMENT_BYTES] * (MAX_COMMAND_BYTES // MAX_ARGUMENT_BYTES)
        command = [sys.executable, "-c", "pass", *chunks]
        self.write_json(self.config, {"w1": self.command, "w2": command})
        self.assert_rejected_before_apply(f"w2: restart command exceeds {MAX_COMMAND_BYTES} bytes")

    def test_invalid_timezone_offsets_prevent_apply(self):
        for offset in ("+00:60", "-02:90", "+24:00", "+1:30"):
            with self.subTest(offset=offset):
                self.write_json(self.workers, [
                    worker(state="crashed"),
                    worker("w2", heartbeat=f"2026-11-23T11:49:00{offset}"),
                ])
                self.assert_rejected_before_apply("last_heartbeat")

    def test_nonstandard_json_constants_prevent_apply(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            for path in (self.workers, self.config):
                with self.subTest(constant=constant, file=path.name):
                    # Put the constant outside the required data to test the decoder.
                    row = worker(state="crashed")
                    commands = {"w1": self.command}
                    if path == self.workers:
                        row["extra"] = float(constant)
                    else:
                        commands["idle"] = float(constant)
                    self.write_json(self.workers, [row])
                    self.write_json(self.config, commands)
                    self.assert_rejected_before_apply(f"{path}: invalid JSON constant {constant}")

    def test_missing_or_malformed_config(self):
        self.config.unlink()
        self.assert_rejected_before_apply("config.json")
        self.config.write_text("{oops")
        self.assert_rejected_before_apply("config.json")

    def test_invalid_worker_input(self):
        self.workers.write_text("[")
        self.assert_rejected_before_apply("workers.json")
        for rows, message in [
            ({}, "array"),
            ([1], "object"),
            ([worker(), worker()], "duplicate"),
            ([{"id": "w2", "state": "running"}], "last_heartbeat"),
            ([worker(heartbeat="yesterday")], "last_heartbeat"),
            ([worker(heartbeat="2026-11-23T11:59")], "UTC offset"),
        ]:
            with self.subTest(rows=rows):
                self.write_json(self.workers, rows)
                self.assert_rejected_before_apply(message)

    def test_failed_restart_stops_later_commands(self):
        self.write_json(self.workers, [worker("failed", "crashed"), worker(state="crashed")])
        self.write_json(self.config, {
            "failed": [sys.executable, "-c", "raise SystemExit(3)"],
            "w1": self.command,
        })
        result = self.run_cli("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed: restart failed", result.stderr)
        self.assertFalse(self.marker.exists())
        self.assertEqual(json.loads(self.report.read_text())["stuck"], ["failed", "w1"])

    def test_shipped_sample_uses_default_config_from_another_directory(self):
        now = datetime.now(timezone.utc)
        rows = json.loads((ROOT / "sample.json").read_text(encoding="utf-8"))
        for row in rows:
            heartbeat = now if row["state"] == "crashed" else now - timedelta(hours=1)
            row["last_heartbeat"] = heartbeat.isoformat()
        rows.insert(0, worker("healthy", heartbeat=now.isoformat()))
        self.write_json(self.workers, rows)
        result = subprocess.run(
            [sys.executable, str(ROOT / "heal.py"), "--workers", str(self.workers)],
            cwd=self.workdir, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(self.report.read_text())
        self.assertEqual(report["stuck"], ["w1", "w2"])
        self.assertEqual(report["actions"], [
            {"id": "w1", "command": ["echo", "Synthetic restart of w1"]},
            {"id": "w2", "command": ["echo", "Synthetic restart of w2"]},
        ])


if __name__ == "__main__":
    unittest.main()
