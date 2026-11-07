"""halo_harness.themes.registry -- the palette registry (Halo 3.3.12.0 R1): ten palettes, two modifiers, one `theme`.

    ids()                  the ten palette ids, in their order (palettes.PALETTES)
    names()                every valid `theme` value: each id, then `<id>-daltonized`, `<id>-ansi`
    split(name)            (palette id, modifier) -- ("", "") for a name the registry does not know
    palette(pid)           {id, label, posture, tokens} or None
    tokens(name)           the token dict a renderer draws `name` in (modifier applied), None when unknown
    posture(name)          "dark" | "light" ("" when unknown)
    follow(system)         what "follow the system" picks: holo on a dark system, paper on a light one
    contrast(a, b)         the WCAG 2 contrast ratio of two #rrggbb colours
    contrast_rows(name)    every pinned pair of `name`: (fg, bg, ratio, floor)
    as_json()              the palettes for Studio's `GET settings/themes`

`-daltonized` swaps the accent pair and the status pair for blue and orange (never red against green), each moved
in lightness until it reads on that palette's backgrounds; `-ansi` is the 16-colour set of the palette's posture.
Pure data and arithmetic: no Textual, no file read.
"""

from __future__ import annotations

import colorsys
from typing import Optional

from halo_harness.themes.palettes import (ANSI, DALTONIZED_HUES, FOLLOW_DARK, FOLLOW_LIGHT, MODIFIERS, PALETTES,
                                          TOKEN_NAMES, TOKENS)

_BY_ID = {p["id"]: p for p in PALETTES}

# The contrast pins (WCAG AA): body text 4.5:1 on every face, a large or UI colour 3:1 on the three backgrounds a
# word in that colour sits on, and the label of a primary button 4.5:1 on the accent. `faint` is decoration (dim
# thinking text, a strong line on a light page) and is not pinned.
BODY, LARGE = 4.5, 3.0
_BODY_ON = ("bg", "bg2", "surface", "surface2")
_LARGE = ("muted", "accent", "accent2", "ok", "warn", "bad", "user", "tool")
_LARGE_ON = ("bg", "bg2", "surface")
PAIRS = (tuple(("text", b, BODY) for b in _BODY_ON) + (("accent_ink", "accent", BODY),)
         + tuple((f, b, LARGE) for f in _LARGE for b in _LARGE_ON))

# What -daltonized moves to which hue (the accent pair, the status pair, the terminal's user and tool lines).
_DALTON = {"accent": "blue", "accent2": "orange", "ok": "blue", "bad": "vermillion", "user": "blue", "tool": "orange"}


def ids() -> tuple:
    return tuple(_BY_ID)


def names() -> tuple:
    return tuple(f"{pid}{suffix}" for pid in _BY_ID for suffix in ("",) + tuple(f"-{m}" for m in MODIFIERS))


def split(name) -> "tuple[str, str]":
    if not isinstance(name, str):
        return "", ""
    if name in _BY_ID:
        return name, ""
    for mod in MODIFIERS:
        base = name[:-len(mod) - 1] if name.endswith(f"-{mod}") else ""
        if base in _BY_ID:
            return base, mod
    return "", ""


def is_name(name) -> bool:
    return bool(split(name)[0])


def palette(pid: str) -> Optional[dict]:
    return _BY_ID.get(pid)


def posture(name) -> str:
    base, _mod = split(name)
    return _BY_ID[base]["posture"] if base else ""


def label(name) -> str:
    base, mod = split(name)
    if not base:
        return ""
    words = {"daltonized": " (blue and orange for red-green colour blindness)",
             "ansi": " (16 colours, for a terminal without truecolor)"}
    return _BY_ID[base]["label"] + words.get(mod, "")


def follow(system_posture: str) -> str:
    return FOLLOW_LIGHT if system_posture == "light" else FOLLOW_DARK


def tokens(name) -> Optional[dict]:
    base, mod = split(name)
    if not base:
        return None
    p = _BY_ID[base]
    if mod == "ansi":
        return dict(ANSI[p["posture"]])
    if mod == "daltonized":
        return daltonize(p["tokens"], p["posture"])
    return dict(p["tokens"])


# -- colour arithmetic -------------------------------------------------------------------------------------------

def rgb(hexstr: str) -> "tuple[int, int, int]":
    h = hexstr.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex(r: float, g: float, b: float) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in (r, g, b))


def luminance(hexstr: str) -> float:
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (v / 255 for v in rgb(hexstr))]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def contrast_rows(name) -> list:
    t = tokens(name) or {}
    return [(fg, bg, round(contrast(t[fg], t[bg]), 2), floor) for fg, bg, floor in PAIRS if fg in t and bg in t]


def _reads_on(colour: str, t: dict, floor: float) -> bool:
    return all(contrast(colour, t[b]) >= floor for b in _LARGE_ON)


def _fit(hue_hex: str, t: dict, dark: bool, floor: float) -> str:
    """The hue moved in lightness (lighter on a dark palette, darker on a light one) until it reads at `floor`."""
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb(hue_hex)))
    step = 0.01 if dark else -0.01
    for _ in range(100):
        cand = _hex(*colorsys.hls_to_rgb(h, l, s))
        if _reads_on(cand, t, floor) or not 0.02 < l < 0.98:
            return cand
        l += step
    return _hex(*colorsys.hls_to_rgb(h, max(0.0, min(1.0, l)), s))


def daltonize(base: dict, posture_word: str) -> dict:
    """`base` with the accent pair, the status pair and the user / tool lines in blue and orange."""
    t = dict(base)
    dark = posture_word == "dark"
    fitted = {hue: _fit(hexstr, t, dark, BODY) for hue, hexstr in DALTONIZED_HUES.items()}
    for token, hue in _DALTON.items():
        t[token] = fitted[hue]
    for ink in (base["accent_ink"], base["bg"], "#000000", "#ffffff"):
        if contrast(ink, t["accent"]) >= BODY:
            t["accent_ink"] = ink
            break
    return t


def as_json() -> dict:
    """`GET settings/themes`'s palettes: each with its tokens and its -daltonized tokens, the vocabulary, the
    modifiers and what "follow the system" picks."""
    return {"palettes": [{"id": p["id"], "label": p["label"], "posture": p["posture"], "tokens": dict(p["tokens"]),
                          "daltonized": daltonize(p["tokens"], p["posture"])} for p in PALETTES],
            "tokens": [{"name": n, "about": about} for n, about in TOKENS], "modifiers": list(MODIFIERS),
            "follow": {"dark": FOLLOW_DARK, "light": FOLLOW_LIGHT}}


__all__ = ["ids", "names", "split", "is_name", "palette", "posture", "label", "follow", "tokens", "contrast",
           "contrast_rows", "daltonize", "as_json", "PAIRS", "TOKEN_NAMES"]
