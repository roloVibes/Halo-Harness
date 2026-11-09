"""halo_harness.themes.registry -- the palette registry (Halo 3.3.12.0 R1): eleven palettes (3.3.15.0: + instrument), two modifiers, one `theme`;
R2: live -- the enabled packs' palettes (`<pack-id>/<id>`) are read at call time (themes/packs.py), never at import.

    ids()                  the eleven palette ids, in their order (palettes.PALETTES)
    pack_ids()             the enabled packs' palette names (`<pack-id>/<id>`), packs in run order
    all_ids()              ids() then pack_ids()
    names()                every valid `theme` value: each of all_ids(), then `<id>-daltonized`, `<id>-ansi`
    register(pack, pals)   add palettes under a pack id by hand (a test, an embedding); unregister(pack) takes them out
    split(name)            (palette id, modifier) -- ("", "") for a name the registry does not know
    palette(pid)           {id, label, posture, tokens} or None
    tokens(name)           the token dict a renderer draws `name` in (modifier applied), None when unknown
    posture(name)          "dark" | "light" ("" when unknown)
    follow(system)         what "follow the system" picks: instrument on a dark system, paper on a light one
    DEFAULT, FOLLOW        3.3.15.0 R4: "instrument" (what an unset `theme` draws everywhere), "auto" (follow the system)
    values()               every value the `theme` key takes: "auto", then names()
    contrast(a, b)         the WCAG 2 contrast ratio of two #rrggbb colours
    contrast_rows(name)    every pinned pair of `name`: (fg, bg, ratio, floor)
    as_json()              the palettes for Studio's `GET settings/themes`

`-daltonized` swaps the accent pair and the status pair for blue and orange (never red against green), each moved
in lightness until it reads on that palette's backgrounds; `-ansi` is the 16-colour set of the palette's posture.
Pure data and arithmetic: no Textual, no file read.
"""

from __future__ import annotations

import colorsys
from collections.abc import Sequence
from typing import Optional

from halo_harness.themes.palettes import (ANSI, DALTONIZED_HUES, DEFAULT, FOLLOW, FOLLOW_DARK, FOLLOW_LIGHT, MODIFIERS,
                                          PALETTES, TOKEN_NAMES, TOKENS)

_BY_ID = {p["id"]: p for p in PALETTES}
_REGISTERED: dict = {}  # pack id -> [palette]: register() / unregister(); the enabled packs' own come from themes/packs.py
SEP = "/"  # a pack palette's name is <pack-id>/<id>: never a core id, visibly a pack's

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


def register(pack_id: str, palettes) -> "list[str]":
    """Add `palettes` (one or a list of {id, label, posture, tokens}; `id` without the pack) under `pack_id`; the names."""
    rows = [palettes] if isinstance(palettes, dict) else list(palettes or [])
    _REGISTERED[pack_id] = [{**p, "id": f"{pack_id}{SEP}{p.get('local_id') or p['id'].split(SEP)[-1]}",
                             "local_id": p.get("local_id") or p["id"].split(SEP)[-1], "pack": pack_id} for p in rows]
    return [p["id"] for p in _REGISTERED[pack_id]]


def unregister(pack_id: str) -> bool:
    return _REGISTERED.pop(pack_id, None) is not None


def packs() -> dict:
    """{name: palette} of every pack palette now: the enabled packs' (themes/packs.py, cached on the packs
    registry's signature) and the registered ones."""
    from halo_harness.themes.packs import live
    out = dict(live())
    for rows in _REGISTERED.values():
        out.update({p["id"]: p for p in rows})
    return out


def _get(pid) -> Optional[dict]:
    if pid in _BY_ID:
        return _BY_ID[pid]
    return packs().get(pid) if isinstance(pid, str) and SEP in pid else None


def ids() -> tuple:
    return tuple(_BY_ID)


def pack_ids() -> tuple:
    return tuple(packs())


def all_ids() -> tuple:
    return ids() + pack_ids()


def names() -> tuple:
    return tuple(f"{pid}{suffix}" for pid in all_ids() for suffix in ("",) + tuple(f"-{m}" for m in MODIFIERS))


def values() -> tuple:
    """3.3.15.0 R4: what the `theme` key takes: "auto" (follow the system, a saved choice) and every palette name."""
    return (FOLLOW,) + names()


class LiveNames(Sequence):
    """`names()` read at every use: `theme.VALID_THEMES` is this, never a frozen copy, so a pack palette is valid
    exactly while its pack is enabled. `in` asks `is_name`; iteration, `len` and indexing read `names()` now.
    3.3.15.0 R4: `LIVE_VALUES` (the Settings row's choices) leads with "auto" (`values()`)."""

    def __init__(self, lead: tuple = ()):
        self.lead = tuple(lead)

    def _all(self) -> tuple:
        return self.lead + names()

    def __contains__(self, name) -> bool:
        return name in self.lead or is_name(name)

    def __getitem__(self, i):
        return self._all()[i]

    def __len__(self) -> int:
        return len(self._all())

    def __repr__(self) -> str:
        return f"LiveNames({len(self)} names)"


LIVE_NAMES = LiveNames()
LIVE_VALUES = LiveNames((FOLLOW,))


def split(name) -> "tuple[str, str]":
    if not isinstance(name, str):
        return "", ""
    if _get(name) is not None:
        return name, ""
    for mod in MODIFIERS:
        base = name[:-len(mod) - 1] if name.endswith(f"-{mod}") else ""
        if base and _get(base) is not None:
            return base, mod
    return "", ""


def is_name(name) -> bool:
    return bool(split(name)[0])


def palette(pid: str) -> Optional[dict]:
    return _get(pid)


def posture(name) -> str:
    base, _mod = split(name)
    return _get(base)["posture"] if base else ""


def label(name) -> str:
    base, mod = split(name)
    if not base:
        return ""
    words = {"daltonized": " (blue and orange for red-green colour blindness)",
             "ansi": " (16 colours, for a terminal without truecolor)"}
    return _get(base)["label"] + words.get(mod, "")


def follow(system_posture: str) -> str:
    return FOLLOW_LIGHT if system_posture == "light" else FOLLOW_DARK


def tokens(name) -> Optional[dict]:
    base, mod = split(name)
    if not base:
        return None
    p = _get(base)
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
    modifiers, what "follow the system" picks and (3.3.15.0 R4) the default an unset `theme` draws. R2: then the pack palettes, each with `pack` and the CSS
    variables Studio draws it in (themes/packs.py rows)."""
    from halo_harness.themes.packs import json_rows
    return {"palettes": [{"id": p["id"], "label": p["label"], "posture": p["posture"], "tokens": dict(p["tokens"]),
                          "daltonized": daltonize(p["tokens"], p["posture"])} for p in PALETTES] + json_rows(),
            "tokens": [{"name": n, "about": about} for n, about in TOKENS], "modifiers": list(MODIFIERS),
            "follow": {"dark": FOLLOW_DARK, "light": FOLLOW_LIGHT}, "default": DEFAULT}


__all__ = ["LIVE_NAMES", "LIVE_VALUES", "DEFAULT", "FOLLOW", "values", "ids", "pack_ids", "all_ids", "register", "unregister", "packs", "names", "split", "is_name", "palette", "posture", "label", "follow", "tokens", "contrast",
           "contrast_rows", "daltonize", "as_json", "PAIRS", "TOKEN_NAMES"]
