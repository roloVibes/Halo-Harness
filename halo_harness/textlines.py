"""halo_harness.textlines -- split a JSONL file's text into records the way
the writers made them (vibes/review.md finding 89).

`str.splitlines()` also breaks on U+2028, U+2029, U+0085, form feed and the
vertical tab. `json.dumps(..., ensure_ascii=False)` (what every log writer
here uses) leaves those characters raw inside a string value, so a record
holding one was cut in half by `splitlines()` and both halves failed to
parse: the record vanished. A JSONL record ends at a newline and nowhere
else.
"""
from __future__ import annotations


def split_lines(text: str, keepends: bool = False) -> "list[str]":
    """`text` cut at "\\n" only (read it with `read_text`, which already
    turns "\\r\\n" and a lone "\\r" into "\\n"). Same shape as
    `str.splitlines`: no empty last piece when the text ends with a
    newline."""
    if not text:
        return []
    parts = text.split("\n")
    tail = parts.pop()
    out = [p + "\n" for p in parts] if keepends else parts
    if tail:
        out.append(tail)
    return out
