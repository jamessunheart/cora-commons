from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ROOT_SCRIPT = ROOT / "verify.py"
BASIC = Path(__file__).resolve().parent / "fixtures" / "publisher" / "basic"
BASIC_REL = "tests/fixtures/publisher/basic"
USER_AGENT = "cora-commons-verify/1"

V1_STDOUT = (
    b'PASS about: 200 "About Cora & Friends"\n'
    b'PASS guide: 200 "Guide: Getting started"\n'
    b"2 passed, 0 failed\n"
)


def publish_module() -> ModuleType:
    """Import at call time so a missing module fails each test on its own."""
    return importlib.import_module("cora_mcp.publish")


def verify_module() -> ModuleType:
    """Import at call time so a missing module fails each test on its own."""
    return importlib.import_module("cora_mcp.verify")


def build_basic(dist: Path) -> None:
    publish = publish_module()
    publish.write_site(dist, BASIC, publish.build_site(publish.load_sources(BASIC)))


def run_module(*args: str, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    return subprocess.run(
        [sys.executable, "-m", "cora_mcp.verify", *args],
        cwd=cwd, capture_output=True, env=env, check=False, timeout=60,
    )


def run_root_script(*args: str, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    env = {key: value for key, value in os.environ.items() if key.upper() != "PYTHONPATH"}
    return subprocess.run(
        [sys.executable, str(ROOT_SCRIPT), *args], cwd=cwd, capture_output=True, env=env, check=False, timeout=60
    )


def stderr_text(result: subprocess.CompletedProcess[bytes]) -> str:
    return result.stderr.decode("utf-8", errors="replace")


class RecordingHandler(SimpleHTTPRequestHandler):
    """The handler `python -m http.server` uses, plus a log of each request and an optional first Set-Cookie."""

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        headers = {name.lower(): value for name, value in self.headers.items()}
        self.server.recorded.append((self.path, headers))
        super().do_GET()

    def end_headers(self) -> None:
        if self.server.set_cookie_once and not self.server.cookie_sent:
            self.server.cookie_sent = True
            self.send_header("Set-Cookie", "session=signed-in; Path=/")
        super().end_headers()


class VerifyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.dist = self.temp / "dist"
        build_basic(self.dist)
        handler = partial(RecordingHandler, directory=str(self.dist))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.server.recorded = []
        self.server.set_cookie_once = False
        self.server.cookie_sent = False
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def assert_entry_point_found(self, result: subprocess.CompletedProcess[bytes]) -> None:
        error = stderr_text(result)
        self.assertNotIn("No module named", error, "cora_mcp.verify is not importable")
        self.assertNotIn("can't open file", error, "root verify.py does not exist")

    def assert_exit(self, result: subprocess.CompletedProcess[bytes], code: int) -> None:
        self.assert_entry_point_found(result)
        self.assertEqual(result.returncode, code, stderr_text(result))

    def verify(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
        return run_module(*args, cwd=cwd or self.temp)

    def recorded_paths(self) -> list[str]:
        return [path for path, _headers in self.server.recorded]


class PassTests(VerifyTestCase):
    def test_published_pages_pass_against_http_server(self) -> None:
        # V1 [MUST, Done-when 2]
        result = self.verify("--base", self.base, "--slugs", "about", "guide", "--src", str(BASIC))
        self.assert_exit(result, 0)
        self.assertEqual(result.stdout, V1_STDOUT)

    def test_base_with_trailing_slash_gives_same_result(self) -> None:
        # V2 [EXTENDED]
        result = self.verify("--base", self.base + "/", "--slugs", "about", "guide", "--src", str(BASIC))
        self.assert_exit(result, 0)
        self.assertEqual(result.stdout, V1_STDOUT)

    def test_title_whitespace_is_normalized(self) -> None:
        # V8 [EXTENDED]
        page = "<!DOCTYPE html>\n<html>\n<head>\n<title>\n  About   Cora &amp;\tFriends \n</title>\n</head>\n<body></body>\n</html>\n"
        (self.dist / "about" / "index.html").write_bytes(page.encode("utf-8"))
        result = self.verify("--base", self.base, "--slugs", "about", "--src", str(BASIC))
        self.assert_exit(result, 0)
        self.assertEqual(result.stdout, b'PASS about: 200 "About Cora & Friends"\n1 passed, 0 failed\n')

    def test_same_host_redirect_to_trailing_slash_is_followed(self) -> None:
        # V9 [EXTENDED] http.server answers /about with 301 Location: /about/
        verify = verify_module()
        result = verify.check_page(verify.build_opener(), self.base + "/about", "about", "About Cora & Friends", 10.0)
        self.assertTrue(result.ok, result)
        self.assertEqual(result.status, 200)
        self.assertEqual(self.recorded_paths(), ["/about", "/about/"])


class FailureTests(VerifyTestCase):
    def test_title_mismatch_fails(self) -> None:
        # V3 [EXTENDED]
        (self.dist / "about" / "index.html").write_bytes(b"<title>Other</title>")
        result = self.verify("--base", self.base, "--slugs", "about", "--src", str(BASIC))
        self.assert_exit(result, 1)
        self.assertEqual(result.stdout, b'FAIL about: expected title "About Cora & Friends", got "Other"\n0 passed, 1 failed\n')

    def test_missing_page_reports_http_404(self) -> None:
        # V4 [EXTENDED]
        shutil.rmtree(self.dist / "guide")
        result = self.verify("--base", self.base, "--slugs", "about", "guide", "--src", str(BASIC))
        self.assert_exit(result, 1)
        self.assertEqual(
            result.stdout, b'PASS about: 200 "About Cora & Friends"\nFAIL guide: HTTP 404\n1 passed, 1 failed\n'
        )

    def test_unpublished_slug_fails_without_any_request(self) -> None:
        # V5 [EXTENDED]
        result = self.verify("--base", self.base, "--slugs", "secret-plan", "--src", BASIC_REL, cwd=ROOT)
        self.assert_exit(result, 1)
        self.assertEqual(
            result.stdout,
            b"FAIL secret-plan: not a published page in tests/fixtures/publisher/basic\n0 passed, 1 failed\n",
        )
        self.assertNotIn(b"not a published page in content", result.stdout)
        result = self.verify("--base", self.base, "--slugs", "roadmap", "--src", "content", cwd=ROOT)
        self.assert_exit(result, 1)
        self.assertEqual(result.stdout, b"FAIL roadmap: not a published page in content\n0 passed, 1 failed\n")
        self.assertEqual(self.server.recorded, [])

    def test_page_without_title_fails(self) -> None:
        # V12 [EXTENDED]
        (self.dist / "about" / "index.html").write_bytes(b"<!DOCTYPE html>\n<html>\n<body>\n<p>No title.</p>\n</body>\n</html>\n")
        result = self.verify("--base", self.base, "--slugs", "about", "--src", str(BASIC))
        self.assert_exit(result, 1)
        self.assertEqual(result.stdout, b"FAIL about: page has no <title>\n0 passed, 1 failed\n")

    def test_content_error_exits_1_without_any_request(self) -> None:
        # V17 [EXTENDED]
        result = self.verify(
            "--base", self.base, "--slugs", "ok", "--src", "tests/fixtures/publisher/missing_title", cwd=ROOT
        )
        self.assert_exit(result, 1)
        self.assertIn(
            "error: tests/fixtures/publisher/missing_title/missing.md: published page has no title", stderr_text(result)
        )
        self.assertNotIn(b"PASS", result.stdout)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(self.server.recorded, [])


class ProxyTests(VerifyTestCase):
    def test_proxy_environment_is_ignored(self) -> None:
        # V16 [EXTENDED] every proxy variable points at a closed port; NO_PROXY is removed
        dead_proxy = "http://127.0.0.1:9"
        env = {
            key: value
            for key, value in os.environ.items()
            if key.upper() not in {"NO_PROXY", "HTTP_PROXY", "HTTPS_PROXY"}
        }
        env.update({"PYTHONPATH": str(SRC), "HTTP_PROXY": dead_proxy, "http_proxy": dead_proxy,
                    "HTTPS_PROXY": dead_proxy, "https_proxy": dead_proxy})
        result = subprocess.run(
            [sys.executable, "-m", "cora_mcp.verify", "--base", self.base, "--slugs", "about", "guide", "--src", str(BASIC)],
            cwd=self.temp, capture_output=True, env=env, check=False, timeout=60,
        )
        self.assert_exit(result, 0)
        self.assertEqual(result.stdout, V1_STDOUT)
        self.assertEqual(self.recorded_paths(), ["/about/", "/guide/"])


class SignedOutTests(VerifyTestCase):
    def test_requests_carry_no_cookie_or_credentials(self) -> None:
        # V6 [MUST, goal "signed-out visitor"] the server sets a cookie on the first response
        self.server.set_cookie_once = True
        result = self.verify("--base", self.base, "--slugs", "about", "guide", "--src", str(BASIC))
        self.assert_exit(result, 0)
        self.assertTrue(self.server.cookie_sent, "the server never sent Set-Cookie")
        self.assertEqual(self.recorded_paths(), ["/about/", "/guide/"])
        for path, headers in self.server.recorded:
            with self.subTest(path=path):
                self.assertNotIn("cookie", headers)
                self.assertNotIn("authorization", headers)
                self.assertEqual(headers.get("user-agent"), USER_AGENT)
                self.assertEqual(headers.get("accept"), "text/html")


class UsageErrorTests(VerifyTestCase):
    def test_bad_arguments_exit_2_without_any_request(self) -> None:
        # V7 [EXTENDED]
        cases = {
            "ftp scheme": ("--base", "ftp://x", "--slugs", "about"),
            "credentials in base": ("--base", "http://user:pw@127.0.0.1", "--slugs", "about"),
            "no scheme": ("--base", "127.0.0.1:8000", "--slugs", "about"),
            "missing --base": ("--slugs", "about"),
            "invalid slug": ("--base", self.base, "--slugs", "Foo"),
            "zero timeout": ("--base", self.base, "--slugs", "about", "--timeout", "0"),
        }
        for name, args in cases.items():
            with self.subTest(case=name):
                result = self.verify(*args, "--src", str(BASIC))
                self.assert_exit(result, 2)
        self.assertEqual(self.server.recorded, [])


class EntryPointTests(VerifyTestCase):
    def test_module_and_root_script_give_v1_output(self) -> None:
        # V13 [MUST, Done-when 2: root verify.py] -m with PYTHONPATH=src; root script with no PYTHONPATH, cwd = temp
        args = ("--base", self.base, "--slugs", "about", "guide", "--src", str(BASIC))
        for name, runner in {"module": run_module, "root script": run_root_script}.items():
            with self.subTest(entry_point=name):
                result = runner(*args, cwd=self.temp)
                self.assert_exit(result, 0)
                self.assertEqual(result.stdout, V1_STDOUT)


if __name__ == "__main__":
    unittest.main()
