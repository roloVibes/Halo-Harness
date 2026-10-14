"""halo_harness.flows.post_text -- the text of each platform's post, out of
the Copywriter's answer.

`split_posts(text, platforms) -> {platform: {text, title?}}`:

1. a fenced JSON block (or a bare object) `{"youtube": {"title", "text"},
   "instagram": {"text"}, "x": "...", ...}` -- keys may be `twitter`, `ig`,
   `tik tok`; a value is a string or a mapping with `text` (`caption`,
   `description`, `content`, `body`) and an optional `title`;
2. else the block headed by the platform's name (a `X:` / `## Instagram`
   line per platform), else the whole text.

A `text` that is already a mapping is used as it is.
"""

from __future__ import annotations

import json
import re

_PLATFORM_NAMES = {"x": ("x", "twitter", "x (twitter)", "x/twitter"), "youtube": ("youtube", "youtube shorts"),
                   "instagram": ("instagram", "ig"), "tiktok": ("tiktok", "tik tok")}
_CANON = {n: p for p, names in _PLATFORM_NAMES.items() for n in names}
_TEXT_KEYS = ("text", "caption", "description", "content", "body")


def _header_of(line: str, platforms: list) -> "str | None":
    s = re.sub(r"^[#>*\-\s]+|[*:\s]+$", "", line.strip()).strip().lower()
    s = re.sub(r"\*+", "", s).strip()
    if not s or len(s) > 40:
        return None
    for p in platforms:
        names = _PLATFORM_NAMES.get(str(p).lower(), (str(p).lower(),))
        if s in names or any(s.startswith(n + " ") or s.startswith(n + "(") for n in names if len(n) > 1):
            return p
    return None


def platform_text(text: str, platform: str, platforms: list) -> str:
    """The block of `text` headed by `platform`; the whole text when there are no such headings."""
    lines = str(text or "").splitlines()
    heads = [(i, _header_of(l, platforms)) for i, l in enumerate(lines)]
    heads = [(i, p) for i, p in heads if p is not None]
    for k, (i, p) in enumerate(heads):
        if p == platform:
            end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
            block = "\n".join(lines[i + 1:end]).strip().strip("-").strip()
            if block:
                return block
    return str(text or "").strip()


def _entry(value) -> dict:
    if isinstance(value, str):
        return {"text": value.strip()} if value.strip() else {}
    if isinstance(value, dict):
        body = next((str(value[k]).strip() for k in _TEXT_KEYS if isinstance(value.get(k), str) and value[k].strip()), "")
        if body:
            return dict({"text": body}, **({"title": str(value["title"]).strip()} if value.get("title") else {}))
    return {}


def _canonical(obj) -> dict:
    out: dict = {}
    for key, value in (obj.items() if isinstance(obj, dict) else []):
        platform, entry = _CANON.get(str(key).strip().lower()), _entry(value)
        if platform and entry:
            out.setdefault(platform, entry)
    return out


def platform_json(text) -> dict:
    """{canonical platform: {text, title?}} from the first JSON object in `text` that has any."""
    s, dec = str(text or ""), json.JSONDecoder()
    fenced = [m.group(1) for m in re.finditer(r"```[A-Za-z]*[ \t]*\r?\n(.*?)```", s, re.S)]
    for chunk in fenced + [s]:
        for m in re.finditer(r"\{", chunk):
            try:
                found = _canonical(dec.raw_decode(chunk, m.start())[0])
            except ValueError:
                continue
            if found:
                return found
    return {}


def split_posts(text, platforms: list) -> dict:
    if isinstance(text, dict):
        raw = _canonical(text)
        return {p: raw.get(_CANON.get(str(p).lower(), str(p).lower())) or _entry(text.get(p)) for p in platforms}
    found = platform_json(text)
    out = {}
    for p in platforms:
        entry = found.get(_CANON.get(str(p).lower(), str(p).lower()))
        out[p] = entry or {"text": platform_text(str(text or ""), p, platforms)}
    return out
