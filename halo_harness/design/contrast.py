"""halo_harness.design.contrast -- WCAG 2.x contrast for a design artboard
(Halo 3.0.1.0 round D5). Pure Python, no model: colour tokens come from the
`:root { --x: <value>; }` block of an artboard's index.html (hex 3/4/6/8,
`rgb()`/`rgba()`), with system.json's colour tokens as the fallback. Every
token whose name reads as text / foreground / accent is paired with every token
whose name reads as a background / surface, and each pair gets its ratio and
the AA / AAA / AA-large verdicts. A translucent colour is composited over the
other side of the pair (a translucent background over white).
"""

from __future__ import annotations

import re
from typing import Optional

# name heuristics: one small table (whole words between - or _)
FG_WORDS = ("text", "fg", "foreground", "ink", "accent", "primary", "link", "muted", "heading", "title", "on")
BG_WORDS = ("bg", "background", "surface", "canvas", "panel", "card", "page")
MAX_PAIRS = 60

_ROOT = re.compile(r":root\s*\{([^}]*)\}", re.I)
_DECL = re.compile(r"--([\w-]+)\s*:\s*([^;]+)")
_RGB = re.compile(r"^rgba?\(\s*([\d.]+%?)[\s,]+([\d.]+%?)[\s,]+([\d.]+%?)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$", re.I)


def parse_color(value) -> Optional[tuple]:
    """(r, g, b, a) with r/g/b 0-255 and a 0-1, or None when `value` is no colour."""
    if isinstance(value, (tuple, list)):
        return tuple(value) if len(value) == 4 else (*value, 1.0)
    v = str(value).strip().rstrip(";").strip()
    if v.startswith("#"):
        h = v[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) in (6, 8) and re.fullmatch(r"[0-9a-fA-F]+", h):
            a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)
        return None
    m = _RGB.match(v)
    if not m:
        return None

    def chan(s: str, scale: float) -> float:
        return float(s[:-1]) / 100 * scale if s.endswith("%") else float(s)
    r, g, b = (max(0.0, min(255.0, chan(m.group(i), 255))) for i in (1, 2, 3))
    a = max(0.0, min(1.0, chan(m.group(4), 1))) if m.group(4) else 1.0
    return (r, g, b, a)


def _over(top: tuple, under: tuple) -> tuple:
    a = top[3]
    return tuple(top[i] * a + under[i] * (1 - a) for i in range(3)) + (1.0,)


def luminance(rgb: tuple) -> float:
    def lin(c: float) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2])


def ratio(a, b) -> float:
    """The WCAG contrast ratio of two colours (strings or tuples), 1.0 to 21.0, two decimals."""
    ca, cb = parse_color(a), parse_color(b)
    if ca is None or cb is None:
        raise ValueError(f"not a colour: {a if ca is None else b!r}")
    cb = _over(cb, (255, 255, 255, 1.0))
    ca = _over(ca, cb)
    hi, lo = sorted((luminance(ca), luminance(cb)), reverse=True)
    return round((hi + 0.05) / (lo + 0.05), 2)


def role(name: str) -> str:
    """'fg', 'bg' or '' for a token name, from the heuristics table."""
    parts = [p for p in re.split(r"[-_]+", name.lower()) if p]
    if "on" in parts:
        return "fg"
    if any(p in BG_WORDS for p in parts):
        return "bg"
    return "fg" if any(p in FG_WORDS for p in parts) else ""


def root_colors(html: str) -> dict:
    """{name: value} of the colour custom properties declared on :root."""
    out = {}
    for block in _ROOT.findall(html or ""):
        for name, value in _DECL.findall(block):
            if parse_color(value) is not None:
                out["--" + name] = value.strip()
    return out


def system_colors(system: dict) -> dict:
    out = {}
    for group, vals in ((system or {}).get("tokens") or {}).items():
        if isinstance(vals, dict) and "colo" in str(group).lower():
            for name, value in vals.items():
                if parse_color(value) is not None:
                    out[name if str(name).startswith("--") else "--" + str(name)] = str(value).strip()
    return out


def pairs_for(tokens: dict) -> list:
    fgs = {n: v for n, v in tokens.items() if role(n) == "fg"}
    bgs = {n: v for n, v in tokens.items() if role(n) == "bg"}
    rows = []
    for fn, fv in fgs.items():
        for bn, bv in bgs.items():
            r = ratio(fv, bv)
            rows.append({"fg": fn, "bg": bn, "fg_value": fv, "bg_value": bv, "ratio": r, "aa": r >= 4.5, "aaa": r >= 7.0, "aa_large": r >= 3.0})
    rows.sort(key=lambda x: (x["aa"], x["ratio"]))  # failing pairs first, the weakest at the top
    return rows[:MAX_PAIRS]


def check_artboard(project, aid: str) -> dict:
    """{pairs, note} for one artboard of a design project."""
    page = project.artboard_dir(aid) / "index.html"
    html = page.read_text(encoding="utf-8", errors="replace") if page.is_file() else ""
    tokens = root_colors(html)
    source = "the page's :root"
    if not (any(role(n) == "fg" for n in tokens) and any(role(n) == "bg" for n in tokens)):
        tokens = {**system_colors(project.system()), **tokens}
        source = "the page's :root and the design system"
    pairs = pairs_for(tokens)
    if not pairs:
        return {"pairs": [], "note": "No text and background colour tokens found: declare them as --text and --bg on :root so they can be checked."}
    bad = sum(1 for p in pairs if not p["aa"])
    return {"pairs": pairs, "note": f"{len(pairs)} pair(s) from {source}; {bad} below AA for normal text."}
