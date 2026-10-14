"""halo_harness.fleet.table_live -- `halo fleet` with no arguments: the fleet
table, redrawn every REFRESH_S seconds, for anyone in a terminal (Halo
3.0.5.0 "Fleet" round R2, plan item D9).

Keys: Up/Down select a row, `s` steer that agent (type the note, Enter),
`k` stop it (asks y/N first), `p` pause it or resume it, `r` refresh now,
`q` (or Esc) quits. Without a terminal (a pipe, a file) it prints the
table once, like `halo fleet --once`.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Optional

REFRESH_S = 2.0


class _Keys:
    """Single keys without Enter: msvcrt on Windows, cbreak mode elsewhere."""

    def __enter__(self) -> "_Keys":
        self._old = None
        if os.name != "nt":
            import termios
            import tty
            self._fd = sys.stdin.fileno()
            self._old = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        else:
            _enable_vt()
        return self

    def __exit__(self, *exc) -> None:
        if self._old is not None:
            import termios
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)

    def get(self, timeout: float) -> Optional[str]:
        if os.name == "nt":
            import msvcrt
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\x00", "\xe0"):
                        return {"H": "up", "P": "down"}.get(msvcrt.getwch())
                    return ch
                time.sleep(0.02)
            return None
        import select
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if not ready:
            return None
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            more, _, _ = select.select([sys.stdin], [], [], 0.05)
            if more and sys.stdin.read(1) == "[":
                return {"A": "up", "B": "down"}.get(sys.stdin.read(1))
        return ch

    def line(self, prompt: str) -> str:
        if self._old is not None:
            import termios
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)
        try:
            return input(prompt)
        except (EOFError, KeyboardInterrupt):
            return ""
        finally:
            if self._old is not None:
                import tty
                tty.setcbreak(self._fd)


def _enable_vt() -> None:
    """Let a Windows console draw the ANSI clear-screen codes."""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if k32.GetConsoleMode(handle, ctypes.byref(mode)):
            k32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def _draw(table: list, sel: int, source: str, note: str) -> None:
    from halo_harness.fleet.table import render
    where = {"studio": "Studio's fleet view", "hub": "this machine's hub", "local": "this harness only"}[source]
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.write(f"Halo fleet ({where}, every {REFRESH_S:g} s)   Up/Down select  s steer  k stop  "
                     "p pause/resume  r refresh  q quit\n\n")
    sys.stdout.write(render(table, sel) + "\n\n" + (note or "") + "\n")
    sys.stdout.flush()


def live() -> int:
    from halo_harness.fleet.table import render, rows, send, snapshot
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        view, _source = snapshot()
        print(render(rows(view)))
        return 0
    sel, note, last, table, source = 0, "", 0.0, [], "local"
    with _Keys() as keys:
        while True:
            if time.monotonic() - last >= REFRESH_S:
                view, source = snapshot()
                table, last = rows(view), time.monotonic()
                sel = min(sel, max(0, len(table) - 1))
                _draw(table, sel, source, note)
            key = keys.get(0.2)
            if key is None:
                continue
            row = table[sel] if table else {}
            if key in ("q", "Q", "\x1b", "\x03"):
                break
            if key in ("up", "down"):
                sel = max(0, min(len(table) - 1, sel + (1 if key == "down" else -1)))
            elif key == "s" and row:
                text = keys.line(f"steer {row.get('agent')}: ").strip()
                note = send(row, "steer", source, text=text)[1] if text else "steer: nothing sent"
                last = 0.0
            elif key == "k" and row:
                sure = keys.line(f"stop {row.get('agent')} on {row.get('harness_name')}? [y/N] ").strip().lower()
                note = send(row, "stop", source, reason="stopped from halo fleet")[1] if sure.startswith("y") else "stop: cancelled"
                last = 0.0
            elif key == "p" and row:
                note = send(row, "resume" if row.get("state") == "paused" else "pause", source)[1]
                last = 0.0
            elif key == "r":
                last = 0.0
            _draw(table, sel, source, note)
    sys.stdout.write("\n")
    return 0
