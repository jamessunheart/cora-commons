"""Check that published pages load for a signed-out visitor and carry the expected title."""

from __future__ import annotations

import argparse
import http.client
import math
import sys
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import TextIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from cora_mcp.publish import SLUG_MAX, SLUG_RE, PublishError, load_sources, published_pages


SAFE_SCHEMES = ("http", "https")
USER_AGENT = "cora-commons-verify/1"
ACCEPT = "text/html"
DEFAULT_TIMEOUT = 10.0
MAX_TIMEOUT = 120.0


@dataclass(frozen=True)
class CheckResult:
    slug: str
    ok: bool
    status: int | None
    detail: str


def validate_base(base: str) -> str:
    """Return the base URL without a trailing slash, or raise ValueError saying what is wrong."""
    parts = urlsplit(base)
    if parts.scheme.lower() not in SAFE_SCHEMES:
        raise ValueError("must start with http:// or https://")
    if "@" in parts.netloc:
        raise ValueError("must not contain a user name or password")
    if not parts.hostname:
        raise ValueError("must name a host")
    if parts.query or parts.fragment:
        raise ValueError("must not contain a query or fragment")
    return base.rstrip("/")


def page_url(base: str, slug: str) -> str:
    return f"{base.rstrip('/')}/{slug}/"


def normalize_title(text: str) -> str:
    """Trim and collapse every run of whitespace (including NBSP) to one space."""
    return " ".join(text.split())


class _TitleParser(HTMLParser):
    """Keeps the text of the first <title> element, once its end tag has been seen."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.inside = False
        self.parts: list[str] = []
        self.title: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title" and self.title is None:
            self.inside, self.parts = True, []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self.inside:
            self.inside, self.title = False, "".join(self.parts)

    def handle_data(self, data: str) -> None:
        if self.inside:
            self.parts.append(data)


def extract_title(html_text: str) -> str | None:
    """Return the decoded text of the first closed <title>, or None."""
    parser = _TitleParser()
    parser.feed(html_text)
    parser.close()
    return parser.title


def build_opener() -> urllib.request.OpenerDirector:
    """An opener with no cookie jar, no auth handler and no proxies from the environment."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    opener.addheaders = []
    return opener


def _fail(slug: str, detail: str, status: int | None = None) -> CheckResult:
    return CheckResult(slug, False, status, detail)


def _fetch(opener: urllib.request.OpenerDirector, url: str, timeout: float) -> tuple[int, str]:
    """GET url as a signed-out visitor; return (final status, decoded body)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": ACCEPT})
    with opener.open(request, timeout=timeout) as response:
        body = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        status = response.status
    try:
        return status, body.decode(charset, errors="replace")
    except LookupError:
        return status, body.decode("utf-8", errors="replace")


def _compare(slug: str, status: int, html_text: str, expected: str) -> CheckResult:
    found = extract_title(html_text)
    if found is None:
        return _fail(slug, "page has no <title>", status)
    found, wanted = normalize_title(found), normalize_title(expected)
    if found != wanted:
        return _fail(slug, f'expected title "{wanted}", got "{found}"', status)
    return CheckResult(slug, True, status, found)


def check_page(
    opener: urllib.request.OpenerDirector, url: str, slug: str, expected: str, timeout: float
) -> CheckResult:
    """Fetch one page and check that it answers 200 with the expected title."""
    try:
        status, html_text = _fetch(opener, url, timeout)
    except HTTPError as exc:
        return _fail(slug, f"HTTP {exc.code}", exc.code)
    except TimeoutError:
        return _fail(slug, f"timed out after {timeout:g}s")
    except URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            return _fail(slug, f"timed out after {timeout:g}s")
        return _fail(slug, f"cannot connect: {exc.reason}")
    except (OSError, http.client.HTTPException) as exc:
        return _fail(slug, f"cannot connect: {exc}")
    if status != 200:
        return _fail(slug, f"HTTP {status}", status)
    return _compare(slug, status, html_text, expected)


def _emit(stream: TextIO, lines: list[str]) -> None:
    stream.flush()
    stream.buffer.write("".join(line + "\n" for line in lines).encode("utf-8"))
    stream.buffer.flush()


def _result_line(result: CheckResult) -> str:
    if result.ok:
        return f'PASS {result.slug}: {result.status} "{result.detail}"'
    return f"FAIL {result.slug}: {result.detail}"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse and validate arguments; any problem exits 2 through parser.error."""
    parser = argparse.ArgumentParser(description="Check that published pages load signed-out with the right title")
    parser.add_argument("--base", required=True, help="site URL, http or https, for example http://127.0.0.1:8000")
    parser.add_argument("--slugs", nargs="+", required=True, help="slugs of the pages to check")
    parser.add_argument("--src", type=Path, default=Path("content"), help="folder of .md pages (default: content)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="seconds per request (default: 10)")
    args = parser.parse_args(argv)
    try:
        args.base = validate_base(args.base)
    except ValueError as exc:
        parser.error(f"--base {exc}")
    for slug in args.slugs:
        if len(slug) > SLUG_MAX or SLUG_RE.fullmatch(slug) is None:
            parser.error(f'--slugs: invalid slug "{slug}"')
    if not (math.isfinite(args.timeout) and 0 < args.timeout <= MAX_TIMEOUT):
        parser.error(f"--timeout must be more than 0 and at most {MAX_TIMEOUT:g} seconds")
    args.slugs = list(dict.fromkeys(args.slugs))
    return args


def _check_all(args: argparse.Namespace, expected: dict[str, str]) -> list[CheckResult]:
    opener = build_opener()
    results: list[CheckResult] = []
    for slug in args.slugs:
        if slug not in expected:
            results.append(_fail(slug, f"not a published page in {args.src.as_posix()}"))
        else:
            results.append(check_page(opener, page_url(args.base, slug), slug, expected[slug], args.timeout))
    return results


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        pages = published_pages(load_sources(args.src))
    except PublishError as exc:
        _emit(sys.stderr, exc.messages)
        return 1
    results = _check_all(args, {page.slug: page.title for page in pages})
    passed = sum(result.ok for result in results)
    lines = [_result_line(result) for result in results]
    lines.append(f"{passed} passed, {len(results) - passed} failed")
    _emit(sys.stdout, lines)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
