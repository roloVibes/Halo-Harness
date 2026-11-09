"""halo_signal.relay -- the answer, as the model writes it (3.3.13.0 R3).

The session's text reaches the phone as the answer, in order, paragraph by paragraph: a paragraph (text up to a
blank line) or a whole code block is one message, sent the moment it is complete, never split mid-sentence on a
timer. After LIVE_MESSAGES messages of one turn the rest waits and goes out at the turn's end as one short message
plus the whole answer as reply.txt. While tools run the typing indicator shows, and after STATUS_S seconds with
nothing sent one status line says what it is doing ("still working: ran 3 commands, reading tests/"). The turn ends
with one short closing line only when it did real work (a tool ran): "Done: ran 3 commands, edited 2 files ($0.04)."

    Relay()                    one turn's state
      .feed(text) -> [para]    the paragraphs now complete
      .flush() -> [para]       the rest, at the turn's end
      .tool(name, input)       a tool call, for the status and closing lines
      .doing() -> str          "ran 3 commands, edited 2 files, reading tests/"
"""

from __future__ import annotations

import re
import time
from pathlib import PurePath

LIVE_MESSAGES = 4
STATUS_S = 20.0
_FENCE = re.compile(r"^\s*(```|~~~)")
READS = ("Read", "Grep", "Glob", "LS")
EDITS = ("Edit", "Write", "NotebookEdit", "MultiEdit")


class Relay:
    def __init__(self, clock=time.monotonic) -> None:
        self.clock = clock
        self.buf = ""
        self.in_code = False
        self.cur: list = []
        self.sent = 0
        self.held: list = []        # paragraphs past LIVE_MESSAGES, sent at the end with reply.txt
        self.all: list = []         # every paragraph of the answer (reply.txt)
        self.commands = 0
        self.edited: list = []
        self.reading = ""
        self.other: list = []
        self.started = self.clock()
        self.last_out = self.clock()

    # ---- text --------------------------------------------------------------------------
    def feed(self, text: str) -> list:
        self.buf += str(text or "")
        out = []
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            out += self._line(line)
        return self._take(out)

    def _line(self, line: str) -> list:
        if _FENCE.match(line):
            if self.in_code:
                self.cur.append(line)
                self.in_code = False
                return self._close()
            done = self._close()
            self.in_code = True
            self.cur.append(line)
            return done
        if self.in_code:
            self.cur.append(line)
            return []
        if not line.strip():
            return self._close()
        self.cur.append(line)
        return []

    def _close(self) -> list:
        text = "\n".join(self.cur).strip("\n")
        self.cur = []
        return [text] if text.strip() else []

    def flush(self) -> list:
        out = []
        if self.buf:
            out += self._line(self.buf)
            self.buf = ""
        if self.in_code:
            self.cur.append("```")
            self.in_code = False
        return self._take(out + self._close())

    def _take(self, paras: list) -> list:
        """The paragraphs to send now; past LIVE_MESSAGES they are held for the end."""
        now = []
        for p in paras:
            self.all.append(p)
            if self.sent < LIVE_MESSAGES and not self.held:
                now.append(p)
                self.sent += 1
            else:
                self.held.append(p)
        return now

    # ---- work -------------------------------------------------------------------------
    def tool(self, name: str, data) -> None:
        inp = data if isinstance(data, dict) else {}
        if name in ("Bash", "PowerShell"):
            self.commands += 1
        elif name in EDITS:
            path = str(inp.get("file_path") or inp.get("notebook_path") or "")
            if path and PurePath(path).name not in self.edited:
                self.edited.append(PurePath(path).name)
        elif name in READS:
            where = str(inp.get("file_path") or inp.get("path") or inp.get("pattern") or "")
            parts = [p for p in where.replace("\\", "/").split("/") if p]
            self.reading = ("/".join(parts[-2:-1]) + "/" if len(parts) > 1 else (parts[0] if parts else "files"))
        elif name and name not in self.other:
            self.other.append(name)

    @property
    def worked(self) -> bool:
        return bool(self.commands or self.edited or self.reading or self.other)

    def doing(self) -> str:
        bits = []
        if self.commands:
            bits.append(f"ran {self.commands} command{'s' if self.commands != 1 else ''}")
        if self.edited:
            n = len(self.edited)
            bits.append(f"edited {n} file{'s' if n != 1 else ''}" + (f" ({self.edited[-1]})" if n == 1 else ""))
        if self.reading:
            bits.append(f"reading {self.reading}")
        if self.other:
            bits.append("used " + ", ".join(self.other[-2:]))
        return ", ".join(bits) or "thinking"

    def status_due(self) -> bool:
        return self.clock() - self.last_out >= STATUS_S

    def touched(self) -> None:
        self.last_out = self.clock()


def closing_line(relay: "Relay", status: dict) -> str:
    cost = status.get("cost_usd") if isinstance(status, dict) else None
    tail = f" (${cost:.2f}{'+' if status.get('cost_complete') is False else ''})" if isinstance(cost, (int, float)) else ""
    return f"Done: {relay.doing()}{tail}."
