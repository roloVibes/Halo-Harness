"""scripts/realcheck/screen.py -- reading what a terminal showed: a beep, a traceback, the palette of the first frame,
and quitting the full-screen session the way a person does."""
from __future__ import annotations

import re
import time
from collections import Counter

OSC_BEL = re.compile(rb"\x1b\][^\x07\x1b]*\x07")
TRACEBACK = "Traceback (most recent call last)"
BG = re.compile(rb"\x1b\[[0-9;]*?48;2;(\d+);(\d+);(\d+)")
FG = re.compile(rb"\x1b\[[0-9;]*?38;2;(\d+);(\d+);(\d+)")
READY = re.compile(r"ctx \d|\$0\.0|Quit Halo\?")  # the status line of the full-screen session is up


def beeps(raw: bytes) -> dict:
    """{"bare": BEL bytes that ring (not the end of an OSC), "osc": the OSC sequences that end in BEL (name only)}."""
    osc = [m.group(0) for m in OSC_BEL.finditer(raw)]
    bare = raw.count(b"\x07") - len(osc)
    where = []
    rest = OSC_BEL.sub(b"", raw)
    for i, b in enumerate(rest):
        if b == 7 and len(where) < 3:
            where.append(rest[max(0, i - 30):i + 1].decode("utf-8", "replace"))
    return {"bare": bare, "osc": sorted({o[2:].split(b";", 1)[0].decode("ascii", "replace") for o in osc}),
            "bare_context": where}


def hex_of(rgb) -> str:
    return "#" + "".join(f"{int(x):02x}" for x in rgb)


def palette_of(raw: bytes, palettes: "dict | None" = None) -> dict:
    """{"truecolor": bool, "top_bg": [hex], "theme": the palette whose tokens the most-used backgrounds are, or ""}."""
    bgs = Counter(hex_of(m.groups()) for m in BG.finditer(raw))
    truecolor = bool(bgs) or bool(FG.search(raw))
    top = [c for c, _ in bgs.most_common(4)]
    best, score = "", 0
    for name, tokens in (palettes or _palettes()).items():
        s = sum(1 for c in top if c in tokens)
        if s > score:
            best, score = name, s
    return {"truecolor": truecolor, "top_bg": top, "theme": best}


def _palettes() -> dict:
    from halo_harness.themes.palettes import PALETTES  # the data the terminal and Studio both draw from
    return {p["id"]: {v.lower() for v in p["tokens"].values()} for p in PALETTES}


def page_theme(html: bytes) -> str:
    m = re.search(rb'<html\b[^>]*\bdata-theme="([^"]*)"', html or b"", re.I)
    return m.group(1).decode("utf-8", "replace") if m else ""


def tui_ready(t, timeout: float) -> float:
    """Seconds until the full-screen session's status line showed (0 when it did not)."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if READY.search(t.plain()):
            return time.monotonic() - t.started_at
        if t.poll() is not None:
            return 0.0
        time.sleep(0.05)
    return 0.0


def quit_with_ctrl_c(t, wait: float = 5.0) -> str:
    """What a person does to leave with Ctrl+C: press it twice (the session asks on the second within 3 s); when Halo
    asks "Quit Halo?", press Enter; once more if it is still up. A program that ends on the first Ctrl+C ends there.
    Returns the keys pressed."""
    from realcheck.term import strip_ansi
    keys = []
    for _ in range(2):  # the session asks on a second Ctrl+C within 3 s ("quit_on_double_ctrl_c"): a double tap
        if t.poll() is not None:
            break
        mark = len(t.raw())
        t.ctrl_c()
        keys.append("Ctrl+C")
        if t.wait(0.4) is None:
            t.ctrl_c()
            keys.append("Ctrl+C")
        end = time.monotonic() + 4.0
        asked = False
        while time.monotonic() < end and t.poll() is None:
            fresh = re.sub(r"\s+", "", strip_ansi(t.raw()[mark:].decode("utf-8", "replace")))
            if "QuitHalo?" in fresh:  # a terminal may draw the space as a cursor move
                asked = True
                break
            time.sleep(0.05)
        if asked:
            time.sleep(0.3)
            t.write(b"\r")
            keys.append("Enter")
            t.wait(wait)
            break
        t.wait(1.0)
    return " ".join(keys)
