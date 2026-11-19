"""tests.test_group_colours -- the four group colours of Auto's groups (Halo 3.6.0.5 B7, B21; decisions J3 M1, F11).

The four live in a table of their own, `GROUP_COLOURS` in halo_harness/themes/palettes.py (not among the palette
tokens), a plain four and a daltonized four for each of the eleven palettes; `studio_css.studio_vars` appends
`--group-1..4`, scripts/themes_css.py writes them into every `[data-theme]` rule and every `-daltonized` override,
and a pack's palette takes the default palette's four. For every rule the generated block draws:

1. `--group-1..4` are there; CIEDE2000 >= 15 between any two of the four, and from `--accent`, `--warn`, `--ok`,
   `--bad`, `--off-map` (the 55 % sRGB mix of `--bad` and `--user`, as tokens.css computes it) and `--user`: a group's
   colour is never read as a state;
2. each, as a 2 px border, reads at 3:1 or more on `--surface` (WCAG relative luminance);
3. in a `-daltonized` rule (its override applied over its palette) also CIEDE2000 >= 10 between the four after
   deuteranopia and after protanopia (Machado 2009, severity 1.0, applied in linear RGB).
Pure Python, runs anywhere. Run: python -m tests.test_group_colours
"""
from __future__ import annotations

import importlib.util
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
GROUPS = ("--group-1", "--group-2", "--group-3", "--group-4")
STATES = ("--accent", "--warn", "--ok", "--bad", "--off-map", "--user")
APART, FROM_STATE, BORDER, CVD_APART = 15.0, 15.0, 3.0, 10.0
TOKEN_NAMES_3604 = ("bg", "bg2", "surface", "surface2", "border", "line", "text", "muted", "faint", "accent", "accent2",
                    "accent_ink", "ok", "warn", "bad", "user", "tool")
# Machado, Oliveira and Fernandes 2009, severity 1.0 (linear RGB)
MACHADO = {
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
}


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _enc(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _rgb(hexstr: str) -> tuple:
    h = hexstr.strip().lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def lab(hexstr: str) -> tuple:
    """CIE L*a*b* (D65) of an sRGB #rrggbb."""
    r, g, b = (_lin(c) for c in _rgb(hexstr))
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883
    f = [t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29 for t in (x, y, z)]
    return 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])


def de2000(c1: str, c2: str) -> float:
    """CIEDE2000 between two #rrggbb."""
    return de2000_lab(lab(c1), lab(c2))


def de2000_lab(p1: tuple, p2: tuple) -> float:
    """CIEDE2000 between two L*a*b* (Sharma, Wu and Dalal 2005)."""
    (l1, a1, b1), (l2, a2, b2) = p1, p2
    cbar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(cbar ** 7 / (cbar ** 7 + 25 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if c1p else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if c2p else 0.0
    dl, dc = l2 - l1, c2p - c1p
    if c1p * c2p == 0:
        dh = 0.0
    else:
        dh = h2p - h1p
        dh = dh - 360 if dh > 180 else dh + 360 if dh < -180 else dh
    dhh = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh / 2))
    lbar, cbarp = (l1 + l2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        hbar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbar = (h1p + h2p) / 2
    else:
        hbar = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    t = (1 - 0.17 * math.cos(math.radians(hbar - 30)) + 0.24 * math.cos(math.radians(2 * hbar))
         + 0.32 * math.cos(math.radians(3 * hbar + 6)) - 0.20 * math.cos(math.radians(4 * hbar - 63)))
    sl = 1 + 0.015 * (lbar - 50) ** 2 / math.sqrt(20 + (lbar - 50) ** 2)
    sc, sh = 1 + 0.045 * cbarp, 1 + 0.015 * cbarp * t
    rt = (-2 * math.sqrt(cbarp ** 7 / (cbarp ** 7 + 25 ** 7))
          * math.sin(math.radians(60 * math.exp(-(((hbar - 275) / 25) ** 2)))))
    return math.sqrt((dl / sl) ** 2 + (dc / sc) ** 2 + (dhh / sh) ** 2 + rt * (dc / sc) * (dhh / sh))


def simulate(hexstr: str, kind: str) -> str:
    """`hexstr` as a person with `kind` sees it (Machado 2009, severity 1.0, linear RGB), as #rrggbb."""
    lin = [_lin(c) for c in _rgb(hexstr)]
    out = [sum(m * c for m, c in zip(row, lin)) for row in MACHADO[kind]]
    return "#" + "".join(f"{round(_enc(c) * 255):02x}" for c in out)


def contrast(a: str, b: str) -> float:
    from halo_harness.themes.registry import contrast as wcag
    return wcag(a, b)


def _script():
    spec = importlib.util.spec_from_file_location("themes_css_groups", REPO / "scripts" / "themes_css.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rules(css: str) -> list:
    out = []
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for sels, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        decls = dict((k.strip(), v.strip()) for k, _, v in (d.partition(":") for d in body.split(";")) if k.strip())
        out.append(([s.strip() for s in sels.split(",")], decls))
    return out


def drawn() -> list:
    """(label, {variable: value}, daltonized) of every set of variables a `[data-theme]` rule draws."""
    from halo_harness.themes.palettes import PALETTES
    head, _, media = _script().render().partition("@media (prefers-color-scheme: light)")
    rules = _rules(head)
    out = []
    for p in PALETTES:
        base = next(d for s, d in rules if f':root[data-theme="{p["id"]}"]' in s)
        over = next(d for s, d in rules if s == [f':root[data-theme="{p["id"]}-daltonized"]'])
        out.append((p["id"], dict(base), False))
        out.append((p["id"] + "-daltonized", {**base, **over}, True, over))
    light = _rules(media.strip()[1:])
    out.append(('auto (light system)', dict(light[0][1]), False))
    return out


def faults(label: str, v: dict, daltonized: bool) -> list:
    from halo_harness.themes.studio_css import mix
    bad = []
    four = [v.get(g, "") for g in GROUPS]
    if not all(re.fullmatch(r"#[0-9a-f]{6}", c) for c in four):
        return [f"{label}: --group-1..4 missing or not #rrggbb: {four}"]
    states = {s: v[s] for s in STATES if s != "--off-map"}
    states["--off-map"] = mix(v["--bad"], v["--user"], 0.55)
    for i in range(4):
        for j in range(i + 1, 4):
            d = de2000(four[i], four[j])
            if d < APART:
                bad.append(f"{label}: {GROUPS[i]} {four[i]} and {GROUPS[j]} {four[j]} only {d:.1f} apart")
        for s, c in states.items():
            d = de2000(four[i], c)
            if d < FROM_STATE:
                bad.append(f"{label}: {GROUPS[i]} {four[i]} only {d:.1f} from {s} {c}")
        k = contrast(four[i], v["--surface"])
        if k < BORDER:
            bad.append(f"{label}: {GROUPS[i]} {four[i]} reads {k:.2f}:1 on --surface {v['--surface']}")
    if daltonized:
        for kind in MACHADO:
            seen = [simulate(c, kind) for c in four]
            for i in range(4):
                for j in range(i + 1, 4):
                    d = de2000(seen[i], seen[j])
                    if d < CVD_APART:
                        bad.append(f"{label}: under {kind} {GROUPS[i]} and {GROUPS[j]} only {d:.1f} apart")
    return bad


@test
def test_the_colour_maths(ctx: Ctx):
    sharma = (((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425), ((50, 0, 0), (50, -1, 2), 2.3669),
              ((50, 2.5, 0), (73, 25, -18), 27.1492), ((2.0776, 0.0795, -1.135), (0.9033, -0.0636, -0.5514), 0.9082))
    got = [round(de2000_lab(a, b), 4) for a, b, _ in sharma]
    ctx.check(f"Sharma, Wu and Dalal 2005, table 1 (pairs 1, 7, 17, 34), got {got}", got == [w for _, _, w in sharma])
    ctx.check("white and black are about 100 apart", abs(de2000("#ffffff", "#000000") - 100) < 0.5)
    ctx.check("a colour is 0 from itself", de2000("#a78bfa", "#a78bfa") == 0)
    ctx.check("deuteranopia folds red and green together", de2000(simulate("#d55e00", "deuteranopia"),
                                                                  simulate("#3a9a3a", "deuteranopia")) < de2000("#d55e00", "#3a9a3a") / 2)
    ctx.check("grey is grey to everyone", simulate("#808080", "protanopia") == "#808080")


@test
def test_every_rule_draws_four_group_colours_that_are_not_states(ctx: Ctx):
    sets = drawn()
    ctx.check(f"eleven palettes, eleven -daltonized, the light auto: {len(sets)}", len(sets) == 23)
    for entry in sets:
        label, v, dal = entry[0], entry[1], entry[2]
        if dal:
            over = entry[3]
            ctx.check(f"{label}: its override rule restates --group-1..4", all(g in over for g in GROUPS))
        bad = faults(label, v, dal)
        ctx.check(f"{label}: {bad or 'four apart, from every state, 3:1 on the surface'}", not bad)


@test
def test_group_colours_are_not_tokens(ctx: Ctx):
    from halo_harness.themes import palettes
    ctx.check(f"TOKEN_NAMES as on 3.6.0.4, got {palettes.TOKEN_NAMES}", palettes.TOKEN_NAMES == TOKEN_NAMES_3604)
    ctx.check("no TOKENS row is a group colour", not [n for n, _ in palettes.TOKENS if "group" in n])
    ctx.check("MODIFIERS unchanged", palettes.MODIFIERS == ("daltonized", "ansi"))
    table = getattr(palettes, "GROUP_COLOURS", None)
    ids = [p["id"] for p in palettes.PALETTES]
    ctx.check("GROUP_COLOURS has the eleven palette ids", isinstance(table, dict) and sorted(table) == sorted(ids))
    for pid in ids if isinstance(table, dict) else []:
        row = table.get(pid, {})
        ok = sorted(row) == ["daltonized", "plain"] and all(
            len(row[k]) == 4 and all(re.fullmatch(r"#[0-9a-f]{6}", c) for c in row[k]) for k in row)
        ctx.check(f"{pid}: a plain four and a daltonized four, #rrggbb", ok)


@test
def test_studio_vars_end_with_the_palettes_four(ctx: Ctx):
    from halo_harness.themes import palettes, studio_css
    gv = getattr(studio_css, "group_vars", None)
    ctx.check("studio_css.group_vars exists", callable(gv))
    if not callable(gv):
        return
    table = palettes.GROUP_COLOURS
    ctx.check("group_vars() is the default palette's plain four",
              gv() == list(zip(GROUPS, table[palettes.DEFAULT]["plain"])))
    ctx.check("group_vars('dusk', daltonized=True) is dusk's daltonized four",
              gv("dusk", daltonized=True) == list(zip(GROUPS, table["dusk"]["daltonized"])))
    ctx.check("an unknown palette id takes the default's", gv("pack/x", daltonized=True) == gv(palettes.DEFAULT, daltonized=True))
    dusk = next(p for p in palettes.PALETTES if p["id"] == "dusk")
    got = studio_css.studio_vars(dusk["tokens"], "dark", palette="dusk")
    ctx.check("studio_vars ends with --group-1..4 of the palette it names", got[-4:] == gv("dusk"))
    d = studio_css.as_dict("dusk-daltonized")
    ctx.check("as_dict of a -daltonized name holds that palette's daltonized four",
              [d.get(g) for g in GROUPS] == list(table["dusk"]["daltonized"]))
    d = studio_css.as_dict("paper-ansi")
    ctx.check("as_dict of an -ansi name holds the palette's plain four", [d.get(g) for g in GROUPS] == list(table["paper"]["plain"]))


@test
def test_pack_palette_takes_default_group_colours(ctx: Ctx):
    from halo_harness.packs import manifest_themes as MT
    from halo_harness.packs.discover import read_pack
    from halo_harness.themes import packs, registry
    from halo_harness.themes.palettes import DEFAULT
    from tests.helpers.packs_home import fixture
    table = __import__("halo_harness.themes.palettes", fromlist=["x"]).__dict__.get("GROUP_COLOURS")
    ctx.check("GROUP_COLOURS exists", isinstance(table, dict))
    if not isinstance(table, dict):
        return
    pals = MT.palettes("pack-theme", read_pack(fixture("pack-theme"), "source").manifest)
    saved = registry.packs
    try:
        registry.packs = lambda: {p["id"]: {**p, "pack_name": "Pack themes"} for p in pals}
        rows = packs.json_rows()
    finally:
        registry.packs = saved
    ctx.check(f"two pack rows, a dark and a light one, got {[(r['id'], r['posture']) for r in rows]}",
              [r["posture"] for r in rows] == ["dark", "light"])
    for r in rows:
        ctx.check(f"{r['id']}: vars hold the default palette's plain four",
                  [r["vars"].get(g) for g in GROUPS] == list(table[DEFAULT]["plain"]))
        ctx.check(f"{r['id']}: daltonized_vars hold the default palette's daltonized four",
                  [r["daltonized_vars"].get(g) for g in GROUPS] == list(table[DEFAULT]["daltonized"]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
