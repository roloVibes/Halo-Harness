"""halo_harness.voice.aggregate -- the sentence aggregator (Halo 3.3.9.0 R2; docs/VOICE.md "The loop"): the reply's
text as it streams, cut into the sentences the speech server says one at a time, so the first sentence speaks while the
model still writes the second.

    Aggregator().feed(text) -> [sentence]     the sentences this delta completed (none while one is still open)
    Aggregator().flush() -> [sentence]        the rest, at the reply's end
    speakable(line) -> the line as said: markdown marks, `[...]` markup and inline code ticks out, a link's text kept

A sentence ends at `.`, `?` or `!` before a space (or at the end on flush), at a newline, or at MAX_CHARS (the last
space before it). Skipped, never said: a fenced code block (said once as "a code block"), a tool-call line (`<tool_call>`,
`<function`, a `{"name": ...}` call, `⏺ Tool(...)`), and `[...]` markup ([1], [^2], a checkbox; a link keeps its text).
"""

from __future__ import annotations

import re

MAX_CHARS = 200
CODE_SAID = "a code block"
FENCE = ("```", "~~~")
TOOL_LINE = re.compile(r'^\s*(</?(tool_call|tool|function)\b|⏺|\{\s*"(name|tool|function)"\s*:)')
MARKERS = ("<tool_call", "</tool_call", "<tool", "</tool", "<function", "</function", "⏺", '{"name"', '{"tool"',
           '{"function"') + FENCE
_LINK = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")
_BRACKET = re.compile(r"\[[^\]\n]*\]")
_LEAD = re.compile(r"^\s*(#{1,6}\s+|>\s*|[-*+]\s+|\d{1,3}[.)]\s+)")
_MARKS = re.compile(r"(\*\*|__|\*|`|~~)")
_END = re.compile(r"[.!?]+[\"')\]]*(?=\s)")


def speakable(line: str, *, line_start: bool = True) -> str:
    s = _LEAD.sub("", line) if line_start else line
    s = _LINK.sub(r"\1", s)
    s = _BRACKET.sub("", s)
    s = _MARKS.sub("", s)
    return re.sub(r"[ \t]+", " ", s)


def _held(tail: str) -> bool:
    """A partial line that may still turn into a fence or a tool-call line waits for its newline."""
    t = tail.lstrip()
    return bool(t) and any(m.startswith(t) or t.startswith(m) for m in MARKERS)


class Aggregator:
    def __init__(self) -> None:
        self.raw = ""
        self.speech = ""
        self.in_fence = False
        self.mid_line = False

    def feed(self, text: str) -> list:
        self.raw += str(text or "")
        out: list = []
        while "\n" in self.raw:
            line, self.raw = self.raw.split("\n", 1)
            out += self._line(line)
        return out + self._tail()

    def flush(self) -> list:
        out = self._line(self.raw) if self.raw else []
        self.raw = ""
        out += self._cut(final=True)
        self.in_fence = False
        return out

    def _line(self, line: str) -> list:
        started, self.mid_line = self.mid_line, False
        s = line.strip()
        if not started and s.startswith(FENCE):
            out = self._cut(final=True)
            self.in_fence = not self.in_fence
            return out + ([CODE_SAID] if self.in_fence else [])
        if self.in_fence or (not started and TOOL_LINE.match(line)):
            return []
        self.speech += speakable(line, line_start=not started)
        return self._cut(final=True)

    def _tail(self) -> list:
        t = self.raw
        if not t or self.in_fence or (not self.mid_line and _held(t)):
            return []
        cut = len(t)
        opened = t.rfind("[")
        if opened >= 0 and "]" not in t[opened:]:
            cut = opened  # an open [ waits for its ] (markup or a link's text)
        if t[:cut].count("`") % 2:
            cut = t.rfind("`", 0, cut)
        safe, self.raw = t[:cut], t[cut:]
        if safe:
            self.speech += speakable(safe, line_start=not self.mid_line)
            self.mid_line = True
        return self._cut(final=False)

    def _cut(self, *, final: bool) -> list:
        out: list = []
        while True:
            m = _END.search(self.speech)
            if m:
                head, self.speech = self.speech[: m.end()], self.speech[m.end():]
            elif len(self.speech) >= MAX_CHARS:
                at = self.speech.rfind(" ", 0, MAX_CHARS)
                at = at if at > 0 else MAX_CHARS
                head, self.speech = self.speech[:at], self.speech[at:]
            else:
                break
            if head.strip():
                out.append(head.strip())
        if final:
            if self.speech.strip():
                out.append(self.speech.strip())
            self.speech = ""
        return out
