"""Turn a folder of Markdown pages with front matter into a static site folder."""

from __future__ import annotations

import argparse
import codecs
import html
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TextIO


SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SLUG_MAX = 64
SLUG_HINT = "use lowercase letters, digits and single hyphens, at most 64 characters"
KEY_LINE_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_-]*):(.*)")
FRONT_MATTER_FENCE = "---"

# Block rules: each is used with fullmatch on one raw line.
FENCE_OPEN_RE = re.compile(r"```[A-Za-z0-9_+-]*[ \t]*")
FENCE_CLOSE_RE = re.compile(r"```[ \t]*")
HEADING_RE = re.compile(r"(#{1,6})[ \t]+(\S.*)")
BULLET_ITEM_RE = re.compile(r"[ \t]*[-*+][ \t]+(\S.*)")
NUMBER_ITEM_RE = re.compile(r"[ \t]*\d{1,9}\.[ \t]+(\S.*)")

# Inline rules: each runs on text that is already HTML-escaped.
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
LINK_RE = re.compile(r"(?<!!)\[([^\]\n]+)\]\(([^()\s]+)\)")
STRONG_RE = re.compile(r"\*\*([^*\s](?:[^*\n]*[^*\s])?)\*\*")
EM_RE = re.compile(r"\*([^*\s](?:[^*\n]*[^*\s])?)\*")
SAFE_SCHEMES = ("http://", "https://")

MARKER_NAME = ".cora-publish"
MARKER_TEXT = "Built by cora_mcp.publish. This folder is deleted and rebuilt on every run.\n"
INDEX_TITLE = "Index"
INDEX_FILE = "index.html"
PAGE_TEMPLATE = (
    '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    "<title>{title}</title>\n</head>\n<body>\n<main>\n{body}</main>\n</body>\n</html>\n"
)


class PublishError(Exception):
    """One or more content or output problems, each 'error: <name>: <message>'. Exit code 1."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__("\n".join(messages))
        self.messages = messages


@dataclass(frozen=True)
class Page:
    source: str
    slug: str | None
    title: str
    published: bool
    body: str


def _error(name: str, message: str) -> str:
    return f"error: {name}: {message}"


def _fail(name: str, message: str) -> PublishError:
    return PublishError([_error(name, message)])


def decode_source(source: str, data: bytes) -> str:
    """Strip one UTF-8 BOM, decode strictly, and turn CRLF and lone CR into LF."""
    offset = 0
    if data.startswith(codecs.BOM_UTF8):
        data, offset = data[len(codecs.BOM_UTF8):], len(codecs.BOM_UTF8)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        byte = data[exc.start]
        raise _fail(source, f"not valid UTF-8 (byte 0x{byte:02x} at offset {exc.start + offset})") from None
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _closing_line(lines: list[str]) -> int | None:
    for number in range(1, len(lines)):
        if lines[number].rstrip(" \t") == FRONT_MATTER_FENCE:
            return number
    return None


def parse_front_matter(source: str, text: str) -> tuple[dict[str, str], str]:
    """Return (raw field values, body). Values are stripped but still carry their quotes."""
    lines = text.split("\n")
    if lines[0].rstrip(" \t") != FRONT_MATTER_FENCE:
        raise _fail(source, "missing front matter (first line must be ---)")
    closing = _closing_line(lines)
    if closing is None:
        raise _fail(source, "front matter is not closed (no line with ---)")
    fields: dict[str, str] = {}
    for number in range(1, closing):
        line = lines[number].rstrip(" \t")
        if not line or line.startswith("#"):
            continue
        match = KEY_LINE_RE.fullmatch(line)
        if match is None:
            raise _fail(source, f'front matter line {number + 1}: expected "key: value"')
        key = match.group(1)
        if key in fields:
            raise _fail(source, f'front matter line {number + 1}: duplicate key "{key}"')
        fields[key] = match.group(2).strip(" \t")
    return fields, "\n".join(lines[closing + 1:])


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _published(source: str, fields: dict[str, str]) -> bool:
    if "published" not in fields:
        raise _fail(source, 'missing "published" (must be true or false)')
    raw = fields["published"]
    if raw not in ("true", "false"):
        raise _fail(source, f'"published" must be true or false, got {raw!r}')
    return raw == "true"


def _slug_errors(source: str, slug: str) -> list[str]:
    if not slug:
        return [_error(source, "published page has no slug")]
    if len(slug) > SLUG_MAX or SLUG_RE.fullmatch(slug) is None:
        return [_error(source, f'invalid slug "{slug}": {SLUG_HINT}')]
    return []


def parse_page(source: str, text: str) -> Page:
    """Parse one page. Drafts only need valid front matter and a valid published value."""
    fields, body = parse_front_matter(source, text)
    published = _published(source, fields)
    title = _unquote(fields.get("title", ""))
    slug = _unquote(fields["slug"]) if "slug" in fields else None
    if not published:
        return Page(source, slug, title, False, body)
    errors = [] if title.strip() else [_error(source, "published page has no title")]
    errors += _slug_errors(source, slug or "")
    if errors:
        raise PublishError(errors)
    return Page(source, slug, title, True, body)


def is_safe_href(raw: str) -> bool:
    """Allow http(s) URLs and relative links; reject every other scheme (design section 4)."""
    if not raw:
        return False
    if any(char.isspace() or ord(char) < 0x20 or ord(char) == 0x7F or char == "\\" for char in raw):
        return False
    if raw.startswith("//"):
        return False
    lowered = raw.lower()
    if any(lowered.startswith(scheme) and len(raw) > len(scheme) for scheme in SAFE_SCHEMES):
        return True
    slash = raw.find("/")
    head = raw if slash < 0 else raw[:slash]
    return ":" not in head


def _split_tokens(text: str, pattern: re.Pattern[str], plain: Callable[[str], str], matched: Callable[[re.Match[str]], str]) -> str:
    """Render the matches of pattern with matched() and the text between them with plain()."""
    parts: list[str] = []
    position = 0
    for match in pattern.finditer(text):
        parts.append(plain(text[position:match.start()]))
        parts.append(matched(match))
        position = match.end()
    parts.append(plain(text[position:]))
    return "".join(parts)


def _render_em(text: str) -> str:
    return EM_RE.sub(lambda match: f"<em>{match.group(1)}</em>", text)


def _render_emphasis(text: str) -> str:
    return _split_tokens(text, STRONG_RE, _render_em, lambda match: f"<strong>{match.group(1)}</strong>")


def _render_link(match: re.Match[str]) -> str:
    url = match.group(2)
    if not is_safe_href(html.unescape(url)):
        return match.group(0)
    return f'<a href="{url}">{_render_emphasis(match.group(1))}</a>'


def _render_links(text: str) -> str:
    return _split_tokens(text, LINK_RE, _render_emphasis, _render_link)


def render_inline(escaped: str) -> str:
    """Apply code spans, then links, then emphasis to text that is already HTML-escaped."""
    return _split_tokens(escaped, CODE_SPAN_RE, _render_links, lambda match: f"<code>{match.group(1)}</code>")


def _inline(lines: list[str]) -> str:
    return render_inline(html.escape("\n".join(lines)))


class _BlockWriter:
    """Collects the open paragraph or list and turns finished blocks into HTML."""

    def __init__(self) -> None:
        self.output: list[str] = []
        self.paragraph: list[str] = []
        self.list_tag: str | None = None
        self.items: list[list[str]] = []

    def close(self) -> None:
        if self.paragraph:
            self.output.append(f"<p>{_inline(self.paragraph)}</p>\n")
            self.paragraph = []
        if self.list_tag is not None:
            items = "".join(f"<li>{_inline(item)}</li>\n" for item in self.items)
            self.output.append(f"<{self.list_tag}>\n{items}</{self.list_tag}>\n")
            self.list_tag, self.items = None, []

    def heading(self, level: int, text: str) -> None:
        self.close()
        self.output.append(f"<h{level}>{_inline([text])}</h{level}>\n")

    def code(self, lines: list[str]) -> None:
        self.close()
        content = "".join(html.escape(line) + "\n" for line in lines)
        self.output.append(f"<pre><code>{content}</code></pre>\n")

    def item(self, tag: str, text: str) -> None:
        if self.list_tag != tag:
            self.close()
            self.list_tag = tag
        self.items.append([text])

    def text(self, line: str) -> None:
        if self.list_tag is not None:
            self.items[-1].append(line)
        else:
            self.paragraph.append(line)


def _list_item(line: str) -> tuple[str, str] | None:
    for tag, pattern in (("ul", BULLET_ITEM_RE), ("ol", NUMBER_ITEM_RE)):
        match = pattern.fullmatch(line)
        if match:
            return tag, match.group(1).rstrip(" \t")
    return None


def render_markdown(markdown: str) -> str:
    """Render the supported Markdown subset (design section 3). Everything else is escaped text."""
    lines = markdown.split("\n")
    if lines[-1] == "":
        lines.pop()
    writer = _BlockWriter()
    fence: list[str] | None = None
    for line in lines:
        if fence is not None:
            if FENCE_CLOSE_RE.fullmatch(line):
                writer.code(fence)
                fence = None
            else:
                fence.append(line)
            continue
        heading = HEADING_RE.fullmatch(line)
        item = _list_item(line)
        if FENCE_OPEN_RE.fullmatch(line):
            writer.close()
            fence = []
        elif not line.strip(" \t"):
            writer.close()
        elif heading:
            writer.heading(len(heading.group(1)), heading.group(2).rstrip(" \t"))
        elif item:
            writer.item(*item)
        else:
            writer.text(line.strip(" \t"))
    if fence is not None:
        writer.code(fence)
    writer.close()
    return "".join(writer.output)


def _document(title: str, body: str) -> str:
    return PAGE_TEMPLATE.format(title=html.escape(title), body=body)


def render_page(page: Page) -> str:
    return _document(page.title, render_markdown(page.body))


def render_index(pages: list[Page]) -> str:
    """List published pages sorted by slug, with relative links so a path prefix works."""
    ordered = sorted(pages, key=lambda page: page.slug or "")
    if not ordered:
        return _document(INDEX_TITLE, f"<h1>{INDEX_TITLE}</h1>\n<p>No published pages.</p>\n")
    items = "".join(f'<li><a href="{page.slug}/">{html.escape(page.title)}</a></li>\n' for page in ordered)
    return _document(INDEX_TITLE, f"<h1>{INDEX_TITLE}</h1>\n<ul>\n{items}</ul>\n")


def _parse_all(sources: list[tuple[str, bytes]]) -> list[Page]:
    """Parse every source in name order; collect every error, including duplicate published slugs."""
    pages: list[Page] = []
    errors: list[str] = []
    first_use: dict[str, str] = {}
    for source, data in sorted(sources, key=lambda item: item[0]):
        try:
            page = parse_page(source, decode_source(source, data))
        except PublishError as exc:
            errors.extend(exc.messages)
            continue
        if page.published and page.slug in first_use:
            errors.append(_error(source, f'slug "{page.slug}" is already used by {first_use[page.slug]}'))
            continue
        if page.published:
            first_use[page.slug] = source
        pages.append(page)
    if errors:
        raise PublishError(errors)
    return pages


def published_pages(sources: list[tuple[str, bytes]]) -> list[Page]:
    """Return the published pages sorted by slug, or raise PublishError listing every content error."""
    return sorted((page for page in _parse_all(sources) if page.published), key=lambda page: page.slug or "")


def build_site(sources: list[tuple[str, bytes]]) -> dict[str, str]:
    """Map relative POSIX paths to HTML: the index plus one page per published source. No marker."""
    pages = published_pages(sources)
    files = {INDEX_FILE: render_index(pages)}
    for page in pages:
        files[f"{page.slug}/{INDEX_FILE}"] = render_page(page)
    return files


def _display(path: Path) -> str:
    return path.as_posix()


def load_sources(src: Path) -> list[tuple[str, bytes]]:
    """Read every regular *.md file directly inside src (not dotfiles), sorted by name."""
    if not src.is_dir():
        raise _fail(_display(src), "not a directory")
    names = sorted(
        entry.name
        for entry in src.iterdir()
        if entry.name.endswith(".md") and not entry.name.startswith(".") and entry.is_file()
    )
    if not names:
        raise _fail(_display(src), "no .md files found")
    sources: list[tuple[str, bytes]] = []
    for name in names:
        source = f"{_display(src)}/{name}"
        try:
            sources.append((source, (src / name).read_bytes()))
        except OSError as exc:
            raise _fail(source, f"cannot read: {exc.strerror or exc}") from None
    return sources


def _inside(child: Path, parent: Path) -> bool:
    return parent in child.parents


def _check_out(out: Path, src: Path) -> None:
    """Refuse an --out that could hold someone's files (design section 6). Deletes nothing."""
    name = _display(out)
    out_r, src_r, cwd_r = out.resolve(), src.resolve(), Path.cwd().resolve()
    if out_r in (src_r, cwd_r) or _inside(src_r, out_r) or _inside(out_r, src_r) or _inside(cwd_r, out_r):
        raise _fail(name, "output folder overlaps the source folder or the current directory")
    if out.is_symlink() or (out.exists() and not out.is_dir()):
        raise _fail(name, "exists and is not a directory")
    marker = out / MARKER_NAME
    marked = marker.is_file() and not marker.is_symlink()
    if out.exists() and any(out.iterdir()) and not marked:
        raise _fail(name, f"refusing to replace a folder that is not empty and has no {MARKER_NAME} file")


def write_site(out: Path, src: Path, files: dict[str, str]) -> None:
    """Check --out, delete it, then write the marker first and every file as UTF-8 with LF."""
    _check_out(out, src)
    try:
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        (out / MARKER_NAME).write_bytes(MARKER_TEXT.encode("utf-8"))
        for relative, text in sorted(files.items()):
            target = out.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))
    except OSError as exc:
        raise _fail(_display(out), f"cannot write: {exc.strerror or exc}") from None


def _emit(stream: TextIO, lines: list[str]) -> None:
    stream.flush()
    stream.buffer.write("".join(line + "\n" for line in lines).encode("utf-8"))
    stream.buffer.flush()


def _count(number: int, word: str) -> str:
    return f"{number} {word}" if number == 1 else f"{number} {word}s"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a static site from Markdown pages with front matter")
    parser.add_argument("--src", type=Path, required=True, help="folder of .md pages (not recursive)")
    parser.add_argument("--out", type=Path, required=True, help="output folder, deleted and rebuilt")
    args = parser.parse_args(argv)
    try:
        sources = load_sources(args.src)
        files = build_site(sources)
        write_site(args.out, args.src, files)
    except PublishError as exc:
        _emit(sys.stderr, exc.messages)
        return 1
    published = len(files) - 1
    lines = [f"wrote {_display(args.out)}/{relative}" for relative in sorted(files)]
    lines.append(f"published {_count(published, 'page')}, skipped {_count(len(sources) - published, 'draft')}")
    _emit(sys.stdout, lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
