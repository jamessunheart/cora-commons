from __future__ import annotations

import ast
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ROOT_SCRIPT = ROOT / "publish.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "publisher"
BASIC = FIXTURES / "basic"
MISSING_TITLE_REL = "tests/fixtures/publisher/missing_title"

BASIC_FILES = {".cora-publish", "index.html", "about/index.html", "guide/index.html"}

ABOUT_HTML = (
    b'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    b"<title>About Cora &amp; Friends</title>\n</head>\n<body>\n<main>\n"
    b"<h1>Hello</h1>\n<p>Cora is a <em>commons</em> for <strong>people</strong>.</p>\n"
    b"</main>\n</body>\n</html>\n"
)
GUIDE_HTML = (
    b'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    b"<title>Guide: Getting started</title>\n</head>\n<body>\n<main>\n"
    b'<p>Read <a href="https://example.org/docs?a=1&amp;b=2">the docs</a> first.</p>\n'
    b"<ul>\n<li>one</li>\n<li>two <code>x &lt; y</code></li>\n</ul>\n"
    b"<pre><code>&lt;b&gt;raw&lt;/b&gt;\n</code></pre>\n"
    b"</main>\n</body>\n</html>\n"
)
INDEX_HTML = (
    b'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    b"<title>Index</title>\n</head>\n<body>\n<main>\n<h1>Index</h1>\n<ul>\n"
    b'<li><a href="about/">About Cora &amp; Friends</a></li>\n'
    b'<li><a href="guide/">Guide: Getting started</a></li>\n'
    b"</ul>\n</main>\n</body>\n</html>\n"
)
CRLF_BOM_SOURCE = b"\xef\xbb\xbf---\r\ntitle: T\r\nslug: t\r\npublished: true\r\n---\r\n# H\r\n\r\nx\r\n"
CRLF_BOM_HTML = (
    b'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    b"<title>T</title>\n</head>\n<body>\n<main>\n<h1>H</h1>\n<p>x</p>\n"
    b"</main>\n</body>\n</html>\n"
)
SLUG_HINT = "use lowercase letters, digits and single hyphens, at most 64 characters"

# Design section 8, P17 (section 4 as amended). Each input is one paragraph line.
LINK_CASES = [
    ("[x](https://example.org)", '<p><a href="https://example.org">x</a></p>\n'),
    ("[x](HTTPS://Example.org)", '<p><a href="HTTPS://Example.org">x</a></p>\n'),
    ("[x](../guide/)", '<p><a href="../guide/">x</a></p>\n'),
    ("[x](#top)", '<p><a href="#top">x</a></p>\n'),
    ("[x](javascript:alert)", "<p>[x](javascript:alert)</p>\n"),
    ("[x](JaVaScRiPt:alert)", "<p>[x](JaVaScRiPt:alert)</p>\n"),
    ("[x](javascript:alert(1))", "<p>[x](javascript:alert(1))</p>\n"),
    ("[x](data:text/html,hi)", "<p>[x](data:text/html,hi)</p>\n"),
    ("[x](//evil.example)", "<p>[x](//evil.example)</p>\n"),
    (r"[x](/\evil.example)", r"<p>[x](/\evil.example)</p>" + "\n"),
    ("[x]( javascript:x)", "<p>[x]( javascript:x)</p>\n"),
    ("[x](&#106;avascript:x)", "<p>[x](&amp;#106;avascript:x)</p>\n"),
    ("[x](javascript&#58;x)", '<p><a href="javascript&amp;#58;x">x</a></p>\n'),
    ('[x](https://a.org/"onmouseover=)', '<p><a href="https://a.org/&quot;onmouseover=">x</a></p>\n'),
    ("[x](mailto:a@b.org)", "<p>[x](mailto:a@b.org)</p>\n"),
    ("[x](?q=a:b)", "<p>[x](?q=a:b)</p>\n"),
    ("[x](docs/p?t=10:30)", '<p><a href="docs/p?t=10:30">x</a></p>\n'),
]


def publish_module() -> ModuleType:
    """Import at call time so a missing module fails each test on its own."""
    return importlib.import_module("cora_mcp.publish")


def page(front_matter: str, body: str = "") -> str:
    return f"---\n{front_matter}---\n{body}"


def error_messages(test: unittest.TestCase, action) -> list[str]:
    module = publish_module()
    with test.assertRaises(module.PublishError) as caught:
        action(module)
    return list(caught.exception.messages)


def run_module(*args: str, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    return subprocess.run(
        [sys.executable, "-m", "cora_mcp.publish", *args], cwd=cwd, capture_output=True, env=env, check=False
    )


def run_root_script(*args: str, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    env = {key: value for key, value in os.environ.items() if key.upper() != "PYTHONPATH"}
    return subprocess.run(
        [sys.executable, str(ROOT_SCRIPT), *args], cwd=cwd, capture_output=True, env=env, check=False
    )


def stderr_text(result: subprocess.CompletedProcess[bytes]) -> str:
    return result.stderr.decode("utf-8", errors="replace")


def written_files(out: Path) -> set[str]:
    files: set[str] = set()
    for folder, _dirs, names in os.walk(out):
        for name in names:
            files.add((Path(folder) / name).relative_to(out).as_posix())
    return files


class PublishTestCase(unittest.TestCase):
    def assert_entry_point_found(self, result: subprocess.CompletedProcess[bytes]) -> None:
        error = stderr_text(result)
        self.assertNotIn("No module named", error, "cora_mcp.publish is not importable")
        self.assertNotIn("can't open file", error, "root publish.py does not exist")

    def assert_exit(self, result: subprocess.CompletedProcess[bytes], code: int) -> None:
        self.assert_entry_point_found(result)
        self.assertEqual(result.returncode, code, stderr_text(result))

    def build_basic(self, temp: Path) -> Path:
        out = temp / "dist"
        self.assert_exit(run_module("--src", str(BASIC), "--out", str(out), cwd=temp), 0)
        return out


class PublishedVersusDraftTests(PublishTestCase):
    def test_only_published_pages_and_index_are_written(self) -> None:
        # P1 [MUST, Done-when 1]
        with tempfile.TemporaryDirectory() as temp:
            out = self.build_basic(Path(temp))
            self.assertEqual(written_files(out), BASIC_FILES)
            self.assertFalse((out / "secret-plan").exists())

    def test_published_page_with_ampersand_title_is_exact(self) -> None:
        # P2 [EXTENDED]
        with tempfile.TemporaryDirectory() as temp:
            out = self.build_basic(Path(temp))
            self.assertEqual((out / "about" / "index.html").read_bytes(), ABOUT_HTML)

    def test_published_page_with_colon_title_link_list_and_code_is_exact(self) -> None:
        # P3 [EXTENDED]
        with tempfile.TemporaryDirectory() as temp:
            out = self.build_basic(Path(temp))
            self.assertEqual((out / "guide" / "index.html").read_bytes(), GUIDE_HTML)

    def test_index_lists_published_pages_sorted_by_slug(self) -> None:
        # P4 [EXTENDED]
        with tempfile.TemporaryDirectory() as temp:
            out = self.build_basic(Path(temp))
            self.assertEqual((out / "index.html").read_bytes(), INDEX_HTML)


class MissingTitleTests(PublishTestCase):
    def test_published_page_without_title_fails_and_writes_nothing(self) -> None:
        # P6 [MUST, Done-when 1]
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "dist"
            result = run_module("--src", MISSING_TITLE_REL, "--out", str(out), cwd=ROOT)
            self.assert_exit(result, 1)
            self.assertIn(f"error: {MISSING_TITLE_REL}/missing.md: published page has no title", stderr_text(result))
            self.assertFalse(out.exists())


class SlugTests(PublishTestCase):
    def test_invalid_slugs_are_rejected(self) -> None:
        # P10 [EXTENDED]
        for slug in ("Foo", "-a", "a-", "a--b", "a_b", "a/b", "../x", "a b", "a" * 65):
            with self.subTest(slug=slug):
                text = page(f"title: T\nslug: {slug}\npublished: true\n")
                messages = error_messages(self, lambda module: module.parse_page("x.md", text))
                self.assertIn(f'error: x.md: invalid slug "{slug}": {SLUG_HINT}', messages)

    def test_published_page_without_slug_is_rejected(self) -> None:
        # P10 [EXTENDED]
        text = page("title: T\npublished: true\n")
        messages = error_messages(self, lambda module: module.parse_page("x.md", text))
        self.assertIn("error: x.md: published page has no slug", messages)

    def test_duplicate_published_slug_is_reported_once_on_the_later_file(self) -> None:
        # P10 [EXTENDED]
        source = page("title: T\nslug: about\npublished: true\n").encode("utf-8")
        sources = [("content/a.md", source), ("content/b.md", source)]
        messages = error_messages(self, lambda module: module.build_site(sources))
        self.assertEqual(messages, ['error: content/b.md: slug "about" is already used by content/a.md'])

    def test_draft_may_share_a_slug_with_a_published_page(self) -> None:
        # P10 [EXTENDED]
        published = page("title: T\nslug: about\npublished: true\n").encode("utf-8")
        draft = page("slug: about\npublished: false\n").encode("utf-8")
        files = publish_module().build_site([("content/a.md", published), ("content/b.md", draft)])
        self.assertEqual(set(files), {"index.html", "about/index.html"})


class LineEndingTests(PublishTestCase):
    def test_crlf_and_bom_source_renders_lf_output(self) -> None:
        # P12 [EXTENDED]
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "src"
            src.mkdir()
            (src / "t.md").write_bytes(CRLF_BOM_SOURCE)
            out = Path(temp) / "dist"
            self.assert_exit(run_module("--src", str(src), "--out", str(out), cwd=Path(temp)), 0)
            self.assertEqual((out / "t" / "index.html").read_bytes(), CRLF_BOM_HTML)
            for name in written_files(out):
                with self.subTest(file=name):
                    self.assertNotIn(b"\r", (out / name).read_bytes())


class LinkPolicyTests(PublishTestCase):
    def test_link_policy_table(self) -> None:
        # P17 [EXTENDED]
        module = publish_module()
        for markdown, expected in LINK_CASES:
            with self.subTest(markdown=markdown):
                self.assertEqual(module.render_markdown(markdown), expected)


class EntryPointTests(PublishTestCase):
    def test_module_entry_point_builds_basic(self) -> None:
        # P20 [MUST, Done-when 2] python -m cora_mcp.publish with PYTHONPATH=src
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "dist"
            self.assert_exit(run_module("--src", str(BASIC), "--out", str(out), cwd=Path(temp)), 0)
            self.assertEqual(written_files(out), BASIC_FILES)

    def test_root_script_builds_basic_without_pythonpath(self) -> None:
        # P20 [MUST, Done-when 2] python <ROOT>/publish.py, no PYTHONPATH, cwd = temp folder
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "dist"
            self.assert_exit(run_root_script("--src", str(BASIC), "--out", str(out), cwd=Path(temp)), 0)
            self.assertEqual(written_files(out), BASIC_FILES)

    def test_missing_out_is_a_usage_error(self) -> None:
        # P20 [EXTENDED] missing --out exits 2 on both entry points
        runners = {"module": run_module, "root script": run_root_script}
        for name, runner in runners.items():
            with self.subTest(entry_point=name), tempfile.TemporaryDirectory() as temp:
                result = runner("--src", str(BASIC), cwd=Path(temp))
                self.assert_exit(result, 2)
                self.assertIn("--out", stderr_text(result))
                self.assertFalse((Path(temp) / "dist").exists())


# ---------------------------------------------------------------------------
# Second batch: P5, P7, P8, P9, P11, P13, P14, P15, P16, P18, P19, P21, P22, P23
# ---------------------------------------------------------------------------

MODULE_FILE = SRC / "cora_mcp" / "publish.py"
CONTENT = ROOT / "content"
FORBIDDEN_PUBLISH_IMPORTS = {"socket", "urllib", "http", "ssl", "requests", "markdown"}

ONLY_DRAFTS_INDEX = (
    '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    "<title>Index</title>\n</head>\n<body>\n<main>\n"
    "<h1>Index</h1>\n<p>No published pages.</p>\n"
    "</main>\n</body>\n</html>\n"
)

# Design section 8, P16. One row per table line, copied as literals.
RENDER_CASES = [
    ("# Hello", "<h1>Hello</h1>\n"),
    ("###### six", "<h6>six</h6>\n"),
    ("####### seven", "<p>####### seven</p>\n"),
    ("#NoSpace", "<p>#NoSpace</p>\n"),
    ("### Title ###", "<h3>Title ###</h3>\n"),
    ("Tom & Jerry <3", "<p>Tom &amp; Jerry &lt;3</p>\n"),
    ("It's", "<p>It&#x27;s</p>\n"),
    ("line one\nline two", "<p>line one\nline two</p>\n"),
    ("para\n# Head", "<p>para</p>\n<h1>Head</h1>\n"),
    ("- a\n- b", "<ul>\n<li>a</li>\n<li>b</li>\n</ul>\n"),
    ("* a\n+ b", "<ul>\n<li>a</li>\n<li>b</li>\n</ul>\n"),
    ("1. a\n7. b", "<ol>\n<li>a</li>\n<li>b</li>\n</ol>\n"),
    ("- a\n  - b", "<ul>\n<li>a</li>\n<li>b</li>\n</ul>\n"),
    ("- a\nlazy", "<ul>\n<li>a\nlazy</li>\n</ul>\n"),
    ("- a\n\npara", "<ul>\n<li>a</li>\n</ul>\n<p>para</p>\n"),
    ("- a\n1. b", "<ul>\n<li>a</li>\n</ul>\n<ol>\n<li>b</li>\n</ol>\n"),
    ("```\n<b>x</b>\n```", "<pre><code>&lt;b&gt;x&lt;/b&gt;\n</code></pre>\n"),
    ("```python\nx = 1\n```", "<pre><code>x = 1\n</code></pre>\n"),
    ("```\n```", "<pre><code></code></pre>\n"),
    ("```\n*a*\n", "<pre><code>*a*\n</code></pre>\n"),
    ("use `a<b`", "<p>use <code>a&lt;b</code></p>\n"),
    ("`*x*`", "<p><code>*x*</code></p>\n"),
    ("Hello *world*", "<p>Hello <em>world</em></p>\n"),
    ("a **b** c", "<p>a <strong>b</strong> c</p>\n"),
    ("2 * 3 * 4", "<p>2 * 3 * 4</p>\n"),
    ("**unclosed", "<p>**unclosed</p>\n"),
    ("> quote", "<p>&gt; quote</p>\n"),
    ("---", "<p>---</p>\n"),
    ("<script>alert(1)</script>", "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>\n"),
    ("![img](a.png)", "<p>![img](a.png)</p>\n"),
    ("[*a*](x/)", '<p><a href="x/"><em>a</em></a></p>\n'),
    ("", ""),
]


def build_errors(test: unittest.TestCase, data: bytes, source: str = "x.md") -> list[str]:
    return error_messages(test, lambda module: module.build_site([(source, data)]))


def snapshot(folder: Path) -> dict[str, bytes]:
    return {name: (folder / name).read_bytes() for name in written_files(folder)}


def copy_fixture(fixture: Path, target: Path) -> Path:
    target.mkdir(parents=True)
    for item in sorted(fixture.iterdir()):
        shutil.copyfile(item, target / item.name)
    return target


class FrontMatterTests(PublishTestCase):
    def test_unquoted_colon_title_is_kept_whole(self) -> None:
        # P5 [EXTENDED]
        page_ = publish_module().parse_page("x.md", "---\ntitle: Guide: Part 2\nslug: g\npublished: true\n---\n")
        self.assertEqual(page_.title, "Guide: Part 2")

    def test_empty_title_variants_count_as_missing(self) -> None:
        # P7 [EXTENDED]
        for line in ('title: ""', "title: ''", "title:    "):
            with self.subTest(line=line):
                text = f"---\n{line}\nslug: s\npublished: true\n---\n"
                messages = error_messages(self, lambda module, text=text: module.parse_page("x.md", text))
                self.assertIn("error: x.md: published page has no title", messages)

    def test_draft_without_title_or_slug_is_fine(self) -> None:
        # P8 [EXTENDED]
        page_ = publish_module().parse_page("d.md", "---\npublished: false\n---\n")
        self.assertIs(page_.published, False)
        self.assertEqual(page_.title, "")
        self.assertIsNone(page_.slug)

    def test_published_value_must_be_lowercase_true_or_false(self) -> None:
        # P9 [EXTENDED]
        cases = {
            "published: yes": "error: x.md: \"published\" must be true or false, got 'yes'",
            "published: True": "error: x.md: \"published\" must be true or false, got 'True'",
            'published: "true"': "error: x.md: \"published\" must be true or false, got '\"true\"'",
        }
        for line, expected in cases.items():
            with self.subTest(line=line):
                text = f"---\ntitle: T\nslug: s\n{line}\n---\n"
                messages = error_messages(self, lambda module, text=text: module.parse_page("x.md", text))
                self.assertIn(expected, messages)
        with self.subTest(line="(missing)"):
            text = "---\ntitle: T\nslug: s\n---\n"
            messages = error_messages(self, lambda module: module.parse_page("x.md", text))
            self.assertIn('error: x.md: missing "published" (must be true or false)', messages)

    def test_front_matter_structure_errors(self) -> None:
        # P11 [EXTENDED]
        cases = [
            (b"", "error: x.md: missing front matter (first line must be ---)"),
            (b"hello", "error: x.md: missing front matter (first line must be ---)"),
            (b"---\ntitle: x\n", "error: x.md: front matter is not closed (no line with ---)"),
            (b"---\n  title: x\n---\n", 'error: x.md: front matter line 2: expected "key: value"'),
            (
                b"---\ntitle: a\ntitle: b\nslug: s\npublished: true\n---\n",
                'error: x.md: front matter line 3: duplicate key "title"',
            ),
        ]
        for data, expected in cases:
            with self.subTest(data=data):
                self.assertIn(expected, build_errors(self, data))

    def test_trailing_spaces_and_tabs_are_ignored(self) -> None:
        # P13 [EXTENDED]
        module = publish_module()
        data = b"--- \ntitle: T  \nslug: t\t\npublished: true \n---  \n"
        page_ = module.parse_page("x.md", module.decode_source("x.md", data))
        self.assertEqual((page_.title, page_.slug, page_.published), ("T", "t", True))

    def test_non_utf8_source_names_byte_and_offset(self) -> None:
        # P14 [EXTENDED]
        data = b"---\ntitle: caf\xe9\nslug: c\npublished: true\n---\n"
        self.assertIn("error: x.md: not valid UTF-8 (byte 0xe9 at offset 14)", build_errors(self, data))


class EscapingTests(PublishTestCase):
    def test_title_and_body_are_escaped(self) -> None:
        # P15 [EXTENDED]
        cases = [
            ("title: <script>alert(1)</script>", "<title>&lt;script&gt;alert(1)&lt;/script&gt;</title>"),
            ("title: It's \"fine\"", "<title>It&#x27;s &quot;fine&quot;</title>"),
        ]
        for line, expected in cases:
            with self.subTest(line=line):
                data = f"---\n{line}\nslug: s\npublished: true\n---\n<b>hi</b>\n".encode("utf-8")
                html = publish_module().build_site([("x.md", data)])["s/index.html"]
                self.assertIn(expected, html)
                self.assertIn("<main>\n<p>&lt;b&gt;hi&lt;/b&gt;</p>\n</main>", html)


class RenderMarkdownTests(PublishTestCase):
    def test_render_markdown_table(self) -> None:
        # P16 [EXTENDED]
        module = publish_module()
        for markdown, expected in RENDER_CASES:
            with self.subTest(markdown=markdown):
                self.assertEqual(module.render_markdown(markdown), expected)


class OutDirProtocolTests(PublishTestCase):
    """P18. Runs with cwd = temp folder, --src src and --out dist, so messages name 'dist' and 'src'."""

    def run_in(self, temp: Path, src: str = "src", out: str = "dist") -> subprocess.CompletedProcess[bytes]:
        return run_module("--src", src, "--out", out, cwd=temp)

    def test_a_absent_out_is_created(self) -> None:
        # P18a [EXTENDED]
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            copy_fixture(BASIC, temp / "src")
            self.assert_exit(self.run_in(temp), 0)
            self.assertEqual(written_files(temp / "dist"), BASIC_FILES)

    def test_b_empty_out_is_accepted(self) -> None:
        # P18b [EXTENDED]
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            copy_fixture(BASIC, temp / "src")
            (temp / "dist").mkdir()
            self.assert_exit(self.run_in(temp), 0)
            self.assertEqual(written_files(temp / "dist"), BASIC_FILES)

    def test_c_marked_out_is_rebuilt_and_stale_pages_removed(self) -> None:
        # P18c [EXTENDED]
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            copy_fixture(BASIC, temp / "src")
            (temp / "dist" / "stale").mkdir(parents=True)
            (temp / "dist" / ".cora-publish").write_bytes(b"old marker\n")
            (temp / "dist" / "stale" / "index.html").write_bytes(b"stale\n")
            self.assert_exit(self.run_in(temp), 0)
            self.assertFalse((temp / "dist" / "stale").exists())
            self.assertEqual(written_files(temp / "dist"), BASIC_FILES)

    def test_d_unmarked_non_empty_out_is_refused(self) -> None:
        # P18d [EXTENDED]
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            copy_fixture(BASIC, temp / "src")
            (temp / "dist").mkdir()
            keep = b"do not delete me\n"
            (temp / "dist" / "keep.txt").write_bytes(keep)
            result = self.run_in(temp)
            self.assert_exit(result, 1)
            self.assertIn(
                "error: dist: refusing to replace a folder that is not empty and has no .cora-publish file",
                stderr_text(result),
            )
            self.assertEqual(snapshot(temp / "dist"), {"keep.txt": keep})

    def test_e_out_that_is_a_file_is_refused(self) -> None:
        # P18e [EXTENDED]
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            copy_fixture(BASIC, temp / "src")
            (temp / "dist").write_bytes(b"a file\n")
            result = self.run_in(temp)
            self.assert_exit(result, 1)
            self.assertIn("error: dist: exists and is not a directory", stderr_text(result))
            self.assertEqual((temp / "dist").read_bytes(), b"a file\n")

    def test_f_out_equal_to_src_is_refused(self) -> None:
        # P18f [EXTENDED]
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            src = copy_fixture(BASIC, temp / "src")
            before = snapshot(src)
            result = self.run_in(temp, src="src", out="src")
            self.assert_exit(result, 1)
            self.assertIn("error: src: output folder overlaps the source folder or the current directory", stderr_text(result))
            self.assertEqual(snapshot(src), before)

    def test_g_content_error_keeps_previous_build(self) -> None:
        # P18g [EXTENDED]
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            copy_fixture(BASIC, temp / "src")
            self.assert_exit(self.run_in(temp), 0)
            before = snapshot(temp / "dist")
            copy_fixture(FIXTURES / "missing_title", temp / "broken")
            result = self.run_in(temp, src="broken")
            self.assert_exit(result, 1)
            self.assertIn("error: broken/missing.md: published page has no title", stderr_text(result))
            self.assertEqual(snapshot(temp / "dist"), before)


class DeterminismTests(PublishTestCase):
    def test_builds_are_byte_identical_across_hash_seeds(self) -> None:
        # P19 [EXTENDED]
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            builds = []
            for seed in ("0", "1"):
                out = temp / f"dist-{seed}"
                env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONHASHSEED": seed}
                result = subprocess.run(
                    [sys.executable, "-m", "cora_mcp.publish", "--src", str(BASIC), "--out", str(out)],
                    cwd=temp, capture_output=True, env=env, check=False,
                )
                self.assert_exit(result, 0)
                builds.append(snapshot(out))
            self.assertEqual(builds[0], builds[1])
            self.assertEqual(set(builds[0]), BASIC_FILES)
            for file_name, data in builds[0].items():
                with self.subTest(file=file_name):
                    self.assertNotIn(b"\r", data)


class SampleContentTests(PublishTestCase):
    def test_sample_content_builds_published_pages_only(self) -> None:
        # P21 [EXTENDED]
        self.assertTrue(CONTENT.is_dir(), "content/ does not exist yet")
        with tempfile.TemporaryDirectory() as name:
            out = Path(name) / "dist"
            self.assert_exit(run_root_script("--src", "content", "--out", str(out), cwd=ROOT), 0)
            self.assertTrue((out / "welcome" / "index.html").is_file())
            self.assertTrue((out / "how-to-contribute" / "index.html").is_file())
            self.assertFalse((out / "roadmap").exists())


class ImportPolicyTests(unittest.TestCase):
    def test_publish_module_has_no_network_or_markdown_imports(self) -> None:
        # P22 [EXTENDED]
        self.assertTrue(MODULE_FILE.is_file(), f"{MODULE_FILE} does not exist")
        tree = ast.parse(MODULE_FILE.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported & FORBIDDEN_PUBLISH_IMPORTS, set())


class EmptySiteTests(PublishTestCase):
    def test_only_drafts_gives_index_with_no_published_pages(self) -> None:
        # P23 [EXTENDED]
        draft = b"---\nslug: d\npublished: false\n---\nLater.\n"
        files = publish_module().build_site([("d.md", draft)])
        self.assertEqual(files, {"index.html": ONLY_DRAFTS_INDEX})


if __name__ == "__main__":
    unittest.main()
