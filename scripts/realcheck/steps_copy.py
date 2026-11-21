"""scripts/realcheck/steps_copy.py -- copy-drag (3.6.0.6 package C; the owner, 2026-11-20: "Copying from the session
barely works!"). A real `halo` in a terminal gives two answers; the step drags over known words of the FIRST answer with
the terminal's own mouse sequences (press, move, release, in the SGR form the app asked for) and reads what reached the
clipboard: exactly those words, on release, and again on a second drag over them. Ctrl+C then copies the same words again; after a click clears the
selection, Ctrl+C copies the last answer. The unit tests passed while every such drag copied the last answer, because
they never dragged inside a reply.

The clipboard is never the person's: a small program of the step's own, named as the system's clipboard program is
(wl-copy, xclip and xsel on Linux, pbcopy on macOS, clip.exe on Windows: halo_harness/tui/clipboard.py), stands first
on the PATH of the halo it starts and writes what it is given to a file in the scratch home. Windows looks for a bare
`clip.exe` in the folder the program runs in before its own system folder and only then on PATH, so there the program
also stands in the project folder halo runs in."""
from __future__ import annotations

import io
import re
import sys
import time
import unicodedata
import zipfile
from pathlib import Path

from realcheck import fakes, screen
from realcheck.core import Fail, excerpt
from realcheck.steps_a import _no_leftovers

COLS, ROWS = 120, 40
DRAGGED = "COPYDRAG-ALPHA with some words"  # the words of the first answer the step drags over
SHIM = """import os, sys, time
data = sys.stdin.buffer.read()
out = {out!r}
os.makedirs(out, exist_ok=True)
name = os.path.join(out, "%020d.bin" % time.time_ns())
with open(name + ".part", "wb") as f:
    f.write(data)
os.replace(name + ".part", name)
"""
_CSI = re.compile(r"\x1b\[([?<>=]?)([0-9;:]*)[ -/]*([@-~])")
_OTHER = re.compile(r"\x1b(\][^\x07\x1b]*(\x07|\x1b\\)|[PX^_][^\x1b]*\x1b\\|[()*+].|.)", re.S)


def cells(raw: bytes, cols: int = COLS, rows: int = ROWS) -> list:
    """The screen a terminal of cols x rows shows after `raw`: enough of a terminal for Textual's frames and for what
    Windows' pseudoconsole draws again (cursor moves, erases, text; colours and modes are ignored). A list of rows, each
    a list of cells; the cell after a wide character is ""."""
    g = [[" "] * cols for _ in range(rows)]
    r = c = 0
    text = raw.decode("utf-8", "replace")
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\x1b":
            m = _CSI.match(text, i)
            if m is None:
                m2 = _OTHER.match(text, i)
                i = m2.end() if m2 else i + 1
                continue
            i = m.end()
            if m.group(1):
                continue
            nums = [int(p) if p.isdigit() else 0 for p in m.group(2).replace(":", ";").split(";")] if m.group(2) else []
            a, b, f = (nums[0] if nums else 0), (nums[1] if len(nums) > 1 else 0), m.group(3)
            k = max(a, 1)
            if f in "Hf":
                r, c = max(a, 1) - 1, max(b, 1) - 1
            elif f in "AF":
                r, c = r - k, (0 if f == "F" else c)
            elif f in "BE":
                r, c = r + k, (0 if f == "E" else c)
            elif f == "C":
                c += k
            elif f == "D":
                c -= k
            elif f == "G":
                c = k - 1
            elif f == "d":
                r = k - 1
            elif f == "J":
                spans = {0: [(r, c, cols)] + [(y, 0, cols) for y in range(r + 1, rows)],
                         1: [(y, 0, cols) for y in range(r)] + [(r, 0, c + 1)]}.get(a, [(y, 0, cols) for y in range(rows)])
                for y, x0, x1 in spans:
                    g[y][x0:x1] = [" "] * (x1 - x0)
            elif f == "K":
                x0, x1 = {0: (c, cols), 1: (0, c + 1)}.get(a, (0, cols))
                g[r][x0:x1] = [" "] * (x1 - x0)
            elif f == "X":
                g[r][c:min(cols, c + k)] = [" "] * (min(cols, c + k) - c)
            r, c = min(max(r, 0), rows - 1), min(max(c, 0), cols - 1)
            continue
        i += 1
        if ch == "\r":
            c = 0
        elif ch == "\n":
            r = min(r + 1, rows - 1)
        elif ch == "\b":
            c = max(c - 1, 0)
        elif ch >= " " and c < cols:
            wide = unicodedata.east_asian_width(ch) in "WF"
            g[r][c] = ch
            if wide and c + 1 < cols:
                g[r][c + 1] = ""
            c = min(c + (2 if wide else 1), cols)
    return g


def find(grid: list, word: str) -> "tuple[int, int] | None":
    """(column, row), 0-based, of the first cell of `word` on the screen (top first), or None."""
    for y, row in enumerate(grid):
        line, at = "", []
        for x, ch in enumerate(row):
            if ch:
                line += ch
                at.append(x)
        k = line.find(word)
        if k >= 0:
            return at[k], y
    return None


def drag_bytes(start: "tuple[int, int]", end: "tuple[int, int]") -> list:
    """The terminal's own mouse sequences (SGR, 1-based) of a left-button drag: press, two moves, release."""
    (x0, y0), (x1, y1) = start, end
    mid = ((x0 + x1) // 2, y0)
    return [f"\x1b[<0;{x0 + 1};{y0 + 1}M".encode(), f"\x1b[<32;{mid[0] + 1};{mid[1] + 1}M".encode(),
            f"\x1b[<32;{x1 + 1};{y1 + 1}M".encode(), f"\x1b[<0;{x1 + 1};{y1 + 1}m".encode()]


def read_copy(data: bytes) -> str:
    """What the clipboard program was given, as text: clip.exe's UTF-16LE with its BOM, or UTF-8 elsewhere."""
    if data.startswith(b"\xff\xfe"):
        return data[2:].decode("utf-16-le", "replace")
    return data.decode("utf-8", "replace")


def judge(copies: list, dragged: str, last: str) -> list:
    """What went wrong, in a person's words: copies[i] is what gesture i put on the clipboard (None: nothing) -- [0]
    letting go of the drag, [1] the same drag again, [2] Ctrl+C after it, [3] Ctrl+C with nothing selected. [] when
    all four are right."""
    bad = []
    for i, (when, want) in enumerate((("letting go of the drag", dragged), ("the same drag again", dragged),
                                      ("Ctrl+C after the drag", dragged), ("Ctrl+C with nothing selected", last))):
        got = copies[i] if i < len(copies) else None
        if got is None:
            bad.append(f"{when} put nothing on the clipboard")
        elif got != want:
            what = "the LAST answer" if got == last else repr(excerpt(got, 80))
            bad.append(f"{when} copied {what}, not {want!r}")
    return bad


def _launcher(script: Path) -> bytes:
    """Windows: an .exe that runs `script` with this Python -- the console-script launcher pip itself writes (its
    stub, a `#!` line naming the interpreter, then a zip holding __main__.py)."""
    import platform
    from pip._vendor import distlib
    stub = Path(distlib.__file__).parent / ("t64-arm.exe" if platform.machine().lower() in ("arm64", "aarch64")
                                            else "t64.exe")
    exe = sys.executable
    shebang = ('#!"%s"\n' % exe if " " in exe else "#!%s\n" % exe).encode("utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("__main__.py", script.read_text(encoding="utf-8"))
    return stub.read_bytes() + shebang + buf.getvalue()


def _shim(h) -> "tuple[Path, Path]":
    """(the folder put first on PATH, the folder each copy lands in as its own file)."""
    bin_dir, out = h.dir / "clipbin", h.dir / "copies"
    bin_dir.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "clipshim.py"
    script.write_text(SHIM.format(out=str(out)), encoding="utf-8")
    if sys.platform == "win32":
        exe = _launcher(script)
        for d in (bin_dir, h.proj):
            (d / "clip.exe").write_bytes(exe)
    else:
        for name in ("pbcopy",) if sys.platform == "darwin" else ("wl-copy", "xclip", "xsel"):
            p = bin_dir / name
            p.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
            p.chmod(0o755)
    return bin_dir, out


def _copies(out: Path) -> list:
    return [read_copy(p.read_bytes()) for p in sorted(out.glob("*.bin"))]


def _next_copy(out: Path, have: int, timeout: float) -> list:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = _copies(out)
        if len(got) > have:
            return got
        time.sleep(0.1)
    return _copies(out)


def _asked(t, prompt: str, answer_word: str, ev: dict, tag: str) -> bool:
    from realcheck.steps_map import _say
    mark = _say(t, prompt)
    ok = t.wait_for(lambda s: answer_word in s[mark:], 60)
    ev[f"{tag}_answered"] = ok
    return ok


def copy_drag(ctx):
    h = ctx.home("copy-drag")
    bin_dir, out = _shim(h)
    env = ctx.env(h)
    env["PATH"] = str(bin_dir) + (";" if sys.platform == "win32" else ":") + env.get("PATH", "")
    t = ctx.terminal(h, env=env, cols=COLS, rows=ROWS)
    ev: dict = {}
    bad: list = []
    try:
        ev["session_up_s"] = round(screen.tui_ready(t, 60), 1)
        if not ev["session_up_s"]:
            raise Fail("the terminal session never showed its status line in 60 s: " + excerpt(t.plain(), 300), ev)
        if not (_asked(t, "RC-COPYONE: the first answer, please", "COPYDRAG-OMEGA", ev, "first")
                and _asked(t, "RC-COPYTWO: and the second", fakes.COPY_TWO.split()[0], ev, "second")):
            raise Fail("the session did not show both answers in 60 s each: " + excerpt(t.plain()[-600:], 300), ev)
        time.sleep(0.8)  # the last frame drawn
        raw = t.raw()
        ev["sgr_mouse_asked"] = b"\x1b[?1006h" in raw
        grid = cells(raw)
        start = find(grid, DRAGGED)
        if start is None:
            ev["screen"] = [("".join(row)).rstrip() for row in grid if "".join(row).strip()][-20:]
            raise Fail("the first answer's words are not on the screen", ev)
        end = (start[0] + len(DRAGGED) - 1, start[1])
        ev["drag_from_to"] = [start, end]
        click = drag_bytes(start, start)[:1] + drag_bytes(start, start)[3:]  # a click: the selection goes
        gestures = [drag_bytes(start, end), drag_bytes(start, end), [b"\x03"], click + [b"\x03"]]
        seen: list = []
        have = 0
        for keys in gestures:
            for seq in keys:
                t.write(seq)
                time.sleep(0.2)
            got = _next_copy(out, have, 15)
            seen.append(got[have] if len(got) > have else None)
            have = len(got)
        ev["copies"] = [None if x is None else excerpt(x, 120) for x in seen]
        bad.extend(judge(seen, DRAGGED, fakes.COPY_TWO))
        time.sleep(3.2)  # out of the Ctrl+C window the last copy opened: the quit below is a person's double press
        ev["quit_keys"] = screen.quit_with_ctrl_c(t)
        ev["exit"] = t.poll()
        if ev["exit"] is None:
            bad.append(f"the session did not end on {ev['quit_keys']}")
    finally:
        if t.poll() is None:
            t.hard_kill()
        t.cleanup()
    _no_leftovers(ctx, h, "the session")
    if bad:
        raise Fail("; ".join(bad), ev)
    return f"a drag over the first answer copied {DRAGGED!r} on release, twice, and on Ctrl+C; Ctrl+C then the last answer", ev
