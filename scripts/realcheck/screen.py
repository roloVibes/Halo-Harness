"""scripts/realcheck/screen.py -- reading what a terminal showed: a beep, a traceback, the palette of the first frame,
and quitting the full-screen session the way a person does."""
from __future__ import annotations

import re
import time
from collections import Counter

OSC_BEL = re.compile(rb"\x1b\][^\x07\x1b]*\x07")
TRACEBACK = "Traceback (most recent call last)"
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


SGR = re.compile(rb"\x1b\[([0-9;]*)m")


def colours_of(raw: bytes) -> "tuple[Counter, Counter, Counter, Counter]":
    """(24-bit backgrounds, 24-bit foregrounds, 256/16-colour backgrounds, 256/16-colour foregrounds) a frame set,
    each a Counter. A 256-colour one is its number ("16"); a 16-colour one (40-47, 100-107, 48;5;0-15) is "a<n>"."""
    tbg, tfg, xbg, xfg = Counter(), Counter(), Counter(), Counter()
    for m in SGR.finditer(raw):
        parts = m.group(1).split(b";")
        i = 0
        while i < len(parts):
            p = parts[i]
            if p in (b"38", b"48") and i + 1 < len(parts) and parts[i + 1] == b"2" and i + 4 < len(parts):
                (tbg if p == b"48" else tfg)[hex_of(parts[i + 2:i + 5])] += 1
                i += 5
                continue
            if p in (b"38", b"48") and i + 2 < len(parts) and parts[i + 1] == b"5" and parts[i + 2].isdigit():
                n = int(parts[i + 2])
                (xbg if p == b"48" else xfg)[f"a{n}" if n < 16 else str(n)] += 1
                i += 3
                continue
            n = int(p) if p.isdigit() else -1
            if 40 <= n <= 47 or 100 <= n <= 107:
                xbg[f"a{n - 40 if n < 100 else n - 92}"] += 1
            elif 30 <= n <= 37 or 90 <= n <= 97:
                xfg[f"a{n - 30 if n < 90 else n - 82}"] += 1
            i += 1
    return tbg, tfg, xbg, xfg


def _best(bg: list, fg: list, palettes: dict, together: bool = False) -> list:
    """The palette names whose colours hold the most of the backgrounds `bg`, then of the text colours `fg` (all of
    them on a tie); none when no background is a palette's. `together`: count both as one (256 colours, where many
    palettes' dark greys fall on the same few numbers, so the backgrounds alone do not decide)."""
    def score(cols):
        b, f = sum(1 for c in bg if c in cols), sum(1 for c in fg if c in cols)
        return (b + f, b) if together else (b, f)
    scores = {name: score(cols) for name, cols in palettes.items()}
    has_bg = {name for name, cols in palettes.items() if any(c in cols for c in bg)}
    top = max((s for n, s in scores.items() if n in has_bg), default=None)
    return [n for n, s in scores.items() if s == top and n in has_bg] if top else []


def palette_of(raw: bytes, palettes: "dict | None" = None) -> dict:
    """What the frame drew. {"truecolor": it set 24-bit colours, "top_bg": its most-used backgrounds, "theme": the
    palette they name (or ""), "themes": every palette that names them as well (the `-ansi` siblings of one posture
    are the same 16 colours)}. A terminal without truecolor gets each palette's colours as the 256-colour numbers
    Halo's renderer (rich) downgrades them to, read from backgrounds AND text, because a palette and its `-ansi`
    sibling share their darkest background (instrument and instrument-ansi both paint 16)."""
    palettes = palettes or _palettes()
    tbg, tfg, xbg, xfg = colours_of(raw)
    truecolor = bool(tbg) or bool(tfg)
    if truecolor:
        top = [c for c, _ in tbg.most_common(4)]
        names = _best(top, [c for c, _ in tfg.most_common(10)], palettes)
    else:
        top = [c for c, _ in xbg.most_common(6)]
        names = _best(top, [c for c, _ in xfg.most_common(10)], _downgraded(palettes), together=True)
    return {"truecolor": truecolor, "top_bg": top, "theme": names[0] if names else "", "themes": names}


def _downgraded(palettes: dict) -> dict:
    """Each palette's colours as a 256-colour terminal gets them: the number rich downgrades a 24-bit colour to (the
    renderer Halo's terminal draws through), and its 16-colour one ("a<n>")."""
    from rich.color import Color, ColorSystem
    out = {}
    for name, cols in palettes.items():
        got = set()
        for c in cols:
            col = Color.parse(c)
            got.add(str(col.downgrade(ColorSystem.EIGHT_BIT).number))
            got.add(f"a{col.downgrade(ColorSystem.STANDARD).number}")
        out[name] = got
    return out


def _palettes() -> dict:
    """Every built-in palette and its `-ansi` sibling (the 16 colours of its posture, what a terminal without
    truecolor draws when nothing was picked), by the data the terminal and Studio both draw from."""
    from halo_harness.theme import DEFAULT_THEME
    from halo_harness.themes.palettes import ANSI, PALETTES
    ps = sorted(PALETTES, key=lambda p: p["id"] != DEFAULT_THEME)  # on a tie of -ansi siblings, name the default's
    out = {p["id"]: {v.lower() for v in p["tokens"].values()} for p in ps}
    out.update({f"{p['id']}-ansi": {v.lower() for v in ANSI[p["posture"]].values()} for p in ps})
    return out


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
