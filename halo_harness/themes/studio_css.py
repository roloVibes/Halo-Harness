"""halo_harness.themes.studio_css -- the CSS variables Studio draws a palette in (Halo 3.3.12.0; R1's rule, moved
here in R2 so the server can run it).

    studio_vars(tokens, posture)  [(variable, value)] -- every colour variable of styles/tokens.css, in one order
    accent_vars(tokens, posture)  the ones that follow the accent and status pair (a -daltonized rule restates these)
    as_dict(name)                 {variable: value} for a theme name of the registry (its modifier applied), {} if unknown

`scripts/themes_css.py` writes the ten palettes' `[data-theme]` blocks of `styles/tokens.css` with these at build
time; a pack's palette (unknown at build time) gets the same variables at run time: `GET settings/themes` sends them
and `studio/theme_boot.py` inlines them for the first paint, so a pack palette is derived exactly like the ten.
The glass, the lines, the glows, the soft fills and the scrim come from the tokens by the posture's rule below.
"""

from __future__ import annotations

# The posture's rule for every variable Studio derives: (alpha of each soft fill, the glass, lines, glows, scrim).
SOFT = {"dark": {"accent": "0.14", "warn": "0.16", "bad": "0.16", "ok": "0.14"},
        "light": {"accent": "0.10", "warn": "0.14", "bad": "0.10", "ok": "0.12"}}
SCRIM_DARK = "rgba(2, 5, 12, 0.62)"


def rgba(hexstr: str, alpha: str) -> str:
    from halo_harness.themes.registry import rgb
    r, g, b = rgb(hexstr)
    return f"rgba({r}, {g}, {b}, {alpha})"


def accent_vars(t: dict, posture: str) -> list:
    """The variables that follow the accent and status pair (all a -daltonized rule needs to restate)."""
    a, soft = t["accent"], SOFT[posture]
    if posture == "dark":
        glow = f"0 0 0 1px {rgba(a, '0.10')}, 0 8px 32px rgba(0, 0, 0, 0.45), 0 0 24px {rgba(a, '0.06')}"
        strong = f"0 0 0 1px {rgba(a, '0.35')}, 0 0 28px {rgba(a, '0.22')}"
    else:
        glow = f"0 1px 0 {rgba(t['text'], '0.04')}, 0 8px 24px {rgba(t['text'], '0.12')}"
        strong = f"0 0 0 1px {rgba(a, '0.45')}, 0 6px 20px {rgba(a, '0.16')}"
    return [("--glow", glow), ("--glow-strong", strong), ("--accent", a), ("--accent-2", t["accent2"]),
            ("--accent-ink", t["accent_ink"]), ("--accent-soft", rgba(a, soft["accent"])), ("--ok", t["ok"]),
            ("--ok-soft", rgba(t["ok"], soft["ok"])), ("--warn", t["warn"]), ("--warn-soft", rgba(t["warn"], soft["warn"])),
            ("--bad", t["bad"]), ("--bad-soft", rgba(t["bad"], soft["bad"]))]


def studio_vars(t: dict, posture: str) -> list:
    """Every colour variable of styles/tokens.css for a palette's tokens, in one order."""
    dark = posture == "dark"
    out = [("color-scheme", posture), ("--bg", t["bg"]), ("--bg-2", t["bg2"]), ("--surface", t["surface"]),
           ("--surface-2", t["surface2"]), ("--surface-glass", rgba(t["surface"], "0.72" if dark else "0.82")),
           ("--line", rgba(t["line"], "0.16") if dark else t["line"]),
           ("--line-strong", rgba(t["line"], "0.34") if dark else t["faint"]),
           ("--grid-line", rgba(t["line"], "0.045") if dark else rgba(t["text"], "0.06"))]
    out += accent_vars(t, posture)
    out += [("--text", t["text"]), ("--muted", t["muted"]), ("--faint", t["faint"]),
            ("--scrim", SCRIM_DARK if dark else rgba(t["text"], "0.30")), ("--bracket-alpha", "0.55" if dark else "0")]
    return out


def as_dict(name) -> dict:
    """{variable: value} Studio draws theme `name` in. `-ansi` draws the palette itself (a browser always draws full
    colour, as the generated blocks do); `-daltonized` its daltonized tokens."""
    from halo_harness.themes import registry
    base, mod = registry.split(name)
    if not base:
        return {}
    t = registry.tokens(base if mod == "ansi" else name) or {}
    return dict(studio_vars(t, registry.posture(base))) if t else {}
