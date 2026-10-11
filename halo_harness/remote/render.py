"""halo_harness.remote.render -- text going out to the phone (Halo 2.0.9
round 3): Markdown flattened to plain text, split into messages that fit a
Signal bubble, or turned into one message plus a text attachment.

* headings become upper-case lines, lists use `-`, emphasis markers and
  inline-code backticks are dropped, links become `text (url)`;
* code fences are dropped and their lines kept verbatim; each run of code
  lines is reported as a MONOSPACE `textStyle` range (`start:length:MONOSPACE`
  in UTF-16 code units, which is what signal-cli counts);
* a message holds at most `CHUNK_BYTES` (1800) UTF-8 bytes (Signal's hard
  line is 2000), split on whitespace where there is any;
* more than `MAX_CHUNKS` (4) messages -> a short first message and the whole
  text as a `data:text/plain;filename=reply.txt;base64,...` attachment (the
  bridge writes nothing to disk).
"""

from __future__ import annotations

import base64
import re
from typing import NamedTuple, Optional

CHUNK_BYTES = 1800
MAX_CHUNKS = 4
HEAD_BYTES = 900
FILENAME = "reply.txt"
_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+")
_RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)[^)]*\)")
_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_ITAL_STAR = re.compile(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])")
_ITAL_UNDER = re.compile(r"(?<!\w)_(?!\s)([^_\n]+?)(?<!\s)_(?!\w)")
_CODE = re.compile(r"`([^`\n]+)`")


class Msg(NamedTuple):
    text: str
    styles: list  # ["start:length:MONOSPACE", ...]


class Rendered(NamedTuple):
    messages: list            # [Msg]
    attachment: Optional[str]  # a data: URI, set only for the overflow form


def _nbytes(s: str) -> int:
    return len(s.encode("utf-8"))


def _utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def _inline(line: str) -> str:
    line = _IMAGE.sub(lambda m: f"{m.group(1)} ({m.group(2)})".strip(), line)
    line = _LINK.sub(lambda m: f"{m.group(1)} ({m.group(2)})", line)
    line = _CODE.sub(r"\1", line)
    line = _BOLD.sub(r"\2", line)
    line = _ITAL_STAR.sub(r"\1", line)
    return _ITAL_UNDER.sub(r"\1", line)


def flatten_markdown(md: str, state: Optional[dict] = None) -> list:
    """Markdown -> `[(line, is_code)]`. Pass the same `state` dict for the
    successive pieces of one streamed reply so a fence that spans two pieces
    keeps its meaning."""
    out: list = []
    in_code = bool(state and state.get("in_code"))
    for raw in (md or "").replace("\r\n", "\n").split("\n"):
        if _FENCE.match(raw):
            in_code = not in_code
            continue
        if in_code:
            out.append((raw, True))
            continue
        if _RULE.match(raw):
            out.append(("", False))
            continue
        h = _HEADING.match(raw)
        if h:
            out.append((_inline(h.group(1)).upper(), False))
            continue
        line = re.sub(r"^\s{0,3}>\s?", "", raw)
        line = _BULLET.sub(lambda m: m.group(1) + "- ", line)
        out.append((_inline(line).rstrip(), False))
    if state is not None:
        state["in_code"] = in_code
    return _squeeze(out)


def plain_lines(text: str) -> list:
    return [(ln, False) for ln in (text or "").replace("\r\n", "\n").split("\n")]


def _squeeze(lines: list) -> list:
    out, blanks = [], 0
    for ln, code in lines:
        if not code and not ln.strip():
            blanks += 1
            if blanks > 1:
                continue
            ln = ""
        else:
            blanks = 0
        out.append((ln, code))
    while out and not out[0][1] and not out[0][0]:
        out.pop(0)
    while out and not out[-1][1] and not out[-1][0]:
        out.pop()
    return out


def _split_long(line: str, limit: int) -> list:
    """Pieces of `line` of at most `limit` bytes, on whitespace where possible."""
    pieces: list = []
    while _nbytes(line) > limit:
        cut = len(line)
        while cut > 0 and _nbytes(line[:cut]) > limit:
            cut -= max(1, (_nbytes(line[:cut]) - limit) // 4)
        ws = max(line.rfind(" ", 0, cut + 1), line.rfind("\t", 0, cut + 1))
        if ws > 0:
            cut = ws
        if cut <= 0:
            cut = 1
        pieces.append(line[:cut].rstrip() if ws > 0 else line[:cut])
        line = line[cut:].lstrip() if ws > 0 else line[cut:]
    pieces.append(line)
    return pieces


def chunk_lines(lines: list, limit: int = CHUNK_BYTES) -> list:
    """Group `[(line, is_code)]` into chunks of at most `limit` bytes."""
    expanded: list = []
    for ln, code in lines:
        for piece in (_split_long(ln, limit) if _nbytes(ln) > limit else [ln]):
            expanded.append((piece, code))
    chunks: list = []
    cur: list = []
    size = 0
    for ln, code in expanded:
        add = _nbytes(ln) + (1 if cur else 0)
        if cur and size + add > limit:
            chunks.append(cur)
            cur, size, add = [], 0, _nbytes(ln)
        cur.append((ln, code))
        size += add
    if cur:
        chunks.append(cur)
    return chunks


def _msg(chunk: list) -> Msg:
    text = "\n".join(ln for ln, _ in chunk)
    runs, pos, start, end = [], 0, None, 0
    for ln, code in chunk:
        n = _utf16_len(ln)
        if code:
            if start is None:
                start = pos
            end = pos + n
        elif start is not None:
            runs.append((start, end))
            start = None
        pos += n + 1
    if start is not None:
        runs.append((start, end))
    return Msg(text, [f"{a}:{b - a}:MONOSPACE" for a, b in runs if b > a])


def data_uri(text: str, filename: str = FILENAME) -> str:
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"data:text/plain;filename={filename};base64,{b64}"


def render_lines(lines: list, *, limit: int = CHUNK_BYTES, max_chunks: int = MAX_CHUNKS) -> Rendered:
    chunks = chunk_lines(lines, limit)
    if len(chunks) > max_chunks:
        full = "\n".join(ln for ln, _ in lines)
        head = _split_long(full, HEAD_BYTES)[0].rstrip()
        note = f"{head}\n\n[{len(chunks)} messages long; the full text is attached as {FILENAME}]"
        return Rendered([Msg(note, [])], data_uri(full))
    return Rendered([_msg(c) for c in chunks], None)


def render_markdown(md: str, state: Optional[dict] = None, **kw) -> Rendered:
    return render_lines(flatten_markdown(md, state), **kw)


def render_plain(text: str, **kw) -> Rendered:
    return render_lines(_squeeze(plain_lines(text)), **kw)
