"""halo_harness.themes.studio_css -- the CSS variables Studio draws a palette in (Halo 3.3.12.0; R1's rule, moved
here in R2 so the server can run it; 3.3.15.0 L1: the Instrument look's rule).

    studio_vars(tokens, posture, palette=DEFAULT, daltonized=False)  [(variable, value)] -- every colour variable of
                                  styles/tokens.css, in one order, the palette's four group colours last
    group_vars(palette, daltonized)  `--group-1..4` (3.6.0.5 B21; a pack's palette takes the default palette's four)
    accent_vars(tokens, posture)  the ones that follow the accent and status pair (a -daltonized rule restates these)
    as_dict(name)                 {variable: value} for a theme name of the registry (its modifier applied), {} if unknown

`scripts/themes_css.py` writes the eleven palettes' `[data-theme]` blocks of `styles/tokens.css` with these at build
time; a pack's palette (unknown at build time) gets the same variables at run time: `GET settings/themes` sends them
and `studio/theme_boot.py` inlines them for the first paint, so a pack palette is derived exactly like the eleven.

3.3.15.0 L1 (docs/design/studio-instrument/PROPOSAL.md section 2), the same rule for every palette of a posture:
surfaces are solid (`--surface-glass` is the surface itself), the resting `--glow` is no shadow at all and
`--glow-strong` is a 1 px ring in the accent, the hairlines come from the opaque `border` token (`--line`, `--border`;
a light palette's `line` is its `border`, so a light page draws as before), `--line-soft` (row separators, the HUD
cell rules) sits between the border and the surface, `--line-strong` is the border lifted toward the text (the hover
edge), `--grid-line` is the map canvas's dot, one shadow level (`--shadow-1`, menus and floating cards only), and the
soft fills are 6-8 % on a dark page. `--user` and `--tool` (YOU and TOOL in Live) are the tokens as they are.
"""

from __future__ import annotations

from halo_harness.themes.palettes import DEFAULT, GROUP_COLOURS

# The posture's rule for every variable Studio derives: the alpha of each soft fill, the scrim (the ring, the shadow and
# the lines are inline below, as the glows were before).
SOFT = {"dark": {"accent": "0.08", "warn": "0.06", "bad": "0.08", "ok": "0.08"},
        "light": {"accent": "0.10", "warn": "0.14", "bad": "0.10", "ok": "0.12"}}
SCRIM_DARK = "rgba(2, 5, 12, 0.62)"


def rgba(hexstr: str, alpha: str) -> str:
    from halo_harness.themes.registry import rgb
    r, g, b = rgb(hexstr)
    return f"rgba({r}, {g}, {b}, {alpha})"


def mix(a: str, b: str, wa: float) -> str:
    """`a` at weight `wa` over `b` (sRGB), as #rrggbb: the opaque derived lines."""
    from halo_harness.themes.registry import rgb
    return "#" + "".join(f"{round(x * wa + y * (1 - wa)):02x}" for x, y in zip(rgb(a), rgb(b)))


def accent_vars(t: dict, posture: str) -> list:
    """The variables that follow the accent and status pair (all a -daltonized rule needs to restate)."""
    a, soft = t["accent"], SOFT[posture]
    ring = rgba(a, "0.55" if posture == "dark" else "0.45")
    # --glow: no shadow at rest; `0 0 0 0 transparent` is a valid item of a box-shadow list where `none` is not
    return [("--glow", "0 0 0 0 transparent"), ("--glow-strong", f"0 0 0 1px {ring}"), ("--accent", a),
            ("--accent-2", t["accent2"]), ("--accent-ink", t["accent_ink"]), ("--accent-soft", rgba(a, soft["accent"])),
            ("--ok", t["ok"]), ("--ok-soft", rgba(t["ok"], soft["ok"])), ("--warn", t["warn"]),
            ("--warn-soft", rgba(t["warn"], soft["warn"])), ("--bad", t["bad"]), ("--bad-soft", rgba(t["bad"], soft["bad"])),
            ("--user", t["user"]), ("--tool", t["tool"])]


def group_vars(palette: str = DEFAULT, daltonized: bool = False) -> list:
    """3.6.0.5 B21: `--group-1..4` of a palette (plain or daltonized) from palettes.GROUP_COLOURS; a palette id it does
    not hold (a pack's) takes the default palette's four."""
    row = GROUP_COLOURS.get(palette) or GROUP_COLOURS[DEFAULT]
    return [(f"--group-{i}", c) for i, c in enumerate(row["daltonized" if daltonized else "plain"], 1)]


def studio_vars(t: dict, posture: str, palette: str = DEFAULT, daltonized: bool = False) -> list:
    """Every colour variable of styles/tokens.css for a palette's tokens, in one order (the group four last: `palette`
    names the row of GROUP_COLOURS, the default palette's when unknown)."""
    dark = posture == "dark"
    out = [("color-scheme", posture), ("--bg", t["bg"]), ("--bg-2", t["bg2"]), ("--surface", t["surface"]),
           ("--surface-2", t["surface2"]), ("--surface-glass", t["surface"]), ("--border", t["border"]),
           ("--line", t["border"]), ("--line-soft", mix(t["border"], t["surface"], 0.55)),
           ("--line-strong", mix(t["border"], t["text"], 0.88) if dark else t["faint"]),
           ("--grid-line", mix(t["border"], t["bg"], 0.88))]
    out += accent_vars(t, posture)
    out += [("--text", t["text"]), ("--muted", t["muted"]), ("--faint", t["faint"]),
            ("--shadow-1", "0 16px 40px rgba(0, 0, 0, 0.7)" if dark else f"0 16px 40px {rgba(t['text'], '0.18')}"),
            ("--scrim", SCRIM_DARK if dark else rgba(t["text"], "0.30")), ("--bracket-alpha", "1")]
    return out + group_vars(palette, daltonized)


def as_dict(name) -> dict:
    """{variable: value} Studio draws theme `name` in. `-ansi` draws the palette itself (a browser always draws full
    colour, as the generated blocks do); `-daltonized` its daltonized tokens."""
    from halo_harness.themes import registry
    base, mod = registry.split(name)
    if not base:
        return {}
    t = registry.tokens(base if mod == "ansi" else name) or {}
    return dict(studio_vars(t, registry.posture(base), base, mod == "daltonized")) if t else {}
