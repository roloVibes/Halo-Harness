"""halo_harness.start.screen -- `halo start` in a terminal (Halo 3.1.1.0 R1).

`Screen()` is the engine's `emit`: a step's first frame draws its screen
(a rule, "Step N of 7: <title>", the one sentence of why, the command it
runs), later frames print the lines not shown yet, and the last one its
outcome. The run step's lanes table is drawn again in place on a terminal
(the rows that changed are printed otherwise). `ask(prompt)` reads one line.
"""

from __future__ import annotations

import sys
from typing import Optional

RULE = "-" * 72
MARK = {"done": "[done]", "failed": "[failed]", "stopped": "[stopped]"}


class Screen:
    def __init__(self, stream=None, *, live: Optional[bool] = None):
        self.stream = stream or sys.stdout
        try:
            tty = self.stream.isatty()
        except Exception:
            tty = False
        self.live = tty if live is None else live
        self._drawn: "set[str]" = set()
        self._shown: "dict[str, int]" = {}
        self._table: "list[str]" = []

    def out(self, text: str = "") -> None:
        try:
            self.stream.write(text + "\n")
            self.stream.flush()
        except UnicodeEncodeError:
            self.stream.write(text.encode("ascii", "replace").decode("ascii") + "\n")

    def header(self, frame: dict) -> None:
        self.out()
        self.out(RULE)
        self.out(f"Step {frame['step']} of {frame['total']}: {frame['title']}")
        self.out(f"  {frame['why']}")
        if frame.get("command"):
            self.out(f"  $ {frame['command']}")
        self.out()

    def __call__(self, frame: dict) -> None:
        key, state, lines = frame["key"], frame["state"], list(frame.get("lines") or [])
        if key not in self._drawn:
            self._drawn.add(key)
            self.header(frame)
        if key == "run" and state == "running":
            self._lanes(lines)
            return
        start = self._shown.get(key, 0)
        if key == "run":  # done or stopped: the table is already on screen
            start = max(start, len(self._table))
        for line in lines[start:]:
            self.out(f"  {line}" if line else "")
        self._shown[key] = len(lines)
        if state in MARK:
            self.out(MARK[state])

    def _lanes(self, rows: "list[str]") -> None:
        old = self._table
        if self.live and old and len(old) == len(rows):
            self.stream.write(f"\x1b[{len(old)}F")
            for line in rows:
                self.stream.write("\x1b[2K  " + line + "\n")
            self.stream.flush()
        else:
            for i, line in enumerate(rows):
                if i >= len(old) or old[i] != line:
                    self.out(f"  {line}")
        self._table = list(rows)
        self._shown["run"] = len(rows)


def ask(prompt: str) -> str:
    """One line from stdin; EOF is q (nothing more to read means stop, never a silent go-ahead)."""
    sys.stdout.write("  " + prompt)
    sys.stdout.flush()
    line = sys.stdin.readline()
    if not line:
        sys.stdout.write("\n")
        return "q"
    return line.strip()
