"""tests.test_themes_css_drift -- Studio's palette blocks are generated from the registry (Halo 3.3.12.0 R1):

1. scripts/themes_css.py renders the block between tokens.css's two marker comments byte for byte (the way the dist
   gate holds the build), and a palette changed in memory makes `--check` fail;
2. one rule per palette naming its id, -daltonized and -ansi; one override rule per -daltonized name; the dark default
   (3.3.15.0 L1: instrument, holo before) is also `:root` and `auto`, paper is `auto` under a light system;
3. holo keeps its colours (every variable copied from a token as before 3.3.12.0); 3.3.15.0 L1: instrument's
   variables are PROPOSAL.md section 1 and 2 (every value pinned): solid surfaces, opaque hairlines from `border`,
   no resting glow, a 1 px accent ring, 6-8 % soft fills, one shadow level; the same rule for every dark palette;
4. a colour lives in one place: no `#rrggbb` / `rgb(` in the theme files of ui/src (the menu, the swatch, the page,
   lib/theme.ts, styles/themes.css), and tokens.css stays under the 250-line cap; 3.3.15.0 L1: its static block (the
   derived look, the scales) carries no colour literal either.
Run: python -m tests.test_themes_css_drift
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
HOLO_COLOURS = {  # holo's variables copied from its tokens, as before 3.3.12.0 (3.3.15.0 L1: the derived ones follow the look)
    "--bg": "#070b14", "--bg-2": "#0b1222", "--surface": "#0e1628", "--surface-2": "#142038",
    "--accent": "#39d7ff", "--accent-2": "#7c8cff", "--accent-ink": "#04121c", "--warn": "#ffb347", "--bad": "#ff4d8d",
    "--ok": "#4ef0a8", "--text": "#dbe7ff", "--muted": "#7d8fb3", "--faint": "#4a5878",
}
INSTRUMENT = {  # 3.3.15.0 L1: PROPOSAL.md section 1 (the tokens) and section 2 (what Studio derives from them)
    "--bg": "#07090c", "--bg-2": "#0b0e12", "--surface": "#0f1318", "--surface-2": "#151a21", "--surface-glass": "#0f1318",
    "--border": "#232a33", "--line": "#232a33", "--line-soft": "#1a2027", "--line-strong": "#3a414a", "--grid-line": "#20262e",
    "--text": "#e6edf3", "--muted": "#9aa6b2", "--faint": "#7d8995", "--accent": "#22d3ee", "--accent-2": "#f5a524",
    "--accent-ink": "#031317", "--ok": "#3dd68c", "--warn": "#f5a524", "--bad": "#ff5c6a", "--user": "#a78bfa", "--tool": "#67e8f9",
    "--glow": "0 0 0 0 transparent", "--glow-strong": "0 0 0 1px rgba(34, 211, 238, 0.55)",
    "--accent-soft": "rgba(34, 211, 238, 0.08)", "--warn-soft": "rgba(245, 165, 36, 0.06)", "--ok-soft": "rgba(61, 214, 140, 0.08)",
    "--bad-soft": "rgba(255, 92, 106, 0.08)", "--shadow-1": "0 16px 40px rgba(0, 0, 0, 0.7)", "--bracket-alpha": "1",
}


def _script():
    spec = importlib.util.spec_from_file_location("themes_css_drift", REPO / "scripts" / "themes_css.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rules(css: str) -> list:
    """(selectors, {var: value}) of every rule in the generated block."""
    out = []
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for sels, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        decls = dict((k.strip(), v.strip()) for k, _, v in (d.partition(":") for d in body.split(";")) if k.strip())
        out.append(([s.strip() for s in sels.split(",")], decls))
    return out


@test
def test_the_block_is_the_registry_rendered(ctx: Ctx):
    m = _script()
    css = m.TOKENS_CSS.read_text(encoding="utf-8")
    ctx.check("both markers, once each", css.count(m.BEGIN) == 1 and css.count(m.END) == 1)
    block = css[css.index(m.BEGIN):css.index(m.END) + len(m.END)]
    ctx.check("the block is what the script renders, byte for byte", block == m.render())
    ctx.check("--check exits 0", m.main(["--check"]) == 0)
    from halo_harness.themes import palettes
    saved = palettes.PALETTES[4]["tokens"]["accent"]
    try:
        palettes.PALETTES[4]["tokens"]["accent"] = "#123456"
        ctx.check("a palette changed in memory: --check exits 1", m.main(["--check"]) == 1)
    finally:
        palettes.PALETTES[4]["tokens"]["accent"] = saved
    ctx.check("and 0 again once it is back", m.main(["--check"]) == 0)


@test
def test_one_rule_per_palette_and_the_follow_rules(ctx: Ctx):
    from halo_harness.themes.registry import ids
    m = _script()
    rules = _rules(m.render().split("@media")[0])
    for pid in ids():
        base = [r for r in rules if f':root[data-theme="{pid}"]' in r[0]]
        dal = [r for r in rules if r[0] == [f':root[data-theme="{pid}-daltonized"]']]
        ctx.check(f"{pid}: one rule names it, -daltonized and -ansi", len(base) == 1 and f':root[data-theme="{pid}-ansi"]' in base[0][0]
                  and f':root[data-theme="{pid}-daltonized"]' in base[0][0])
        ctx.check(f"{pid}: one -daltonized override, the accent pair in it", len(dal) == 1 and {"--accent", "--accent-2", "--ok", "--bad"} <= set(dal[0][1]))
    default = next(r for r in rules if ':root[data-theme="instrument"]' in r[0])
    ctx.check("instrument (3.3.15.0 L1) is :root and auto too", ":root" in default[0] and ':root[data-theme="auto"]' in default[0])
    holo = next(r for r in rules if ':root[data-theme="holo"]' in r[0])
    ctx.check("holo is neither any more", ":root" not in holo[0] and ':root[data-theme="auto"]' not in holo[0])
    media = m.render().split("@media (prefers-color-scheme: light)")[1]
    ctx.check("paper under a light system", ':root[data-theme="auto"]' in media and "--bg: #f7f3ea;" in media)


@test
def test_holo_keeps_its_colours_and_instrument_is_the_proposal(ctx: Ctx):
    m = _script()
    rules = _rules(m.render())
    holo = next(d for s, d in rules if ':root[data-theme="holo"]' in s)
    off = {k: (v, holo.get(k)) for k, v in HOLO_COLOURS.items() if holo.get(k) != v}
    ctx.check(f"every holo colour as before 3.3.12.0, off: {off}", not off)
    inst = next(d for s, d in rules if ':root[data-theme="instrument"]' in s)
    off = {k: (v, inst.get(k)) for k, v in INSTRUMENT.items() if inst.get(k) != v}
    ctx.check(f"every instrument variable as PROPOSAL.md says, off: {off}", not off)
    for sels, d in rules:
        if "color-scheme" in d and d["color-scheme"] == "dark":
            ctx.check(f"{sels[0]}: solid, no resting glow, a 1 px ring", d["--surface-glass"] == d["--surface"]
                      and d["--glow"] == "0 0 0 0 transparent" and d["--glow-strong"].startswith("0 0 0 1px rgba("))


@test
def test_colours_live_in_one_place(ctx: Ctx):
    files = [UI / "shell" / "ThemeMenu.tsx", UI / "shell" / "Swatch.tsx", UI / "shell" / "themeCommands.ts", UI / "lib" / "theme.ts",
             UI / "routes" / "settings" / "Themes.tsx", UI / "routes" / "settings" / "themePage.ts", UI / "styles" / "themes.css"]
    raw = [f"{p.name}: {hit}" for p in files for hit in re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgba?\(", p.read_text(encoding="utf-8"))]
    ctx.check(f"no raw colour in the theme files, got {raw}", all(p.is_file() for p in files) and not raw)
    css = (UI / "styles" / "tokens.css").read_text(encoding="utf-8")
    n = len(css.splitlines())
    ctx.check(f"tokens.css under the 250-line cap, got {n}", n <= 250)
    static = re.sub(r"/\*.*?\*/", "", css.split("/* themes:begin")[0], flags=re.S)
    raw = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", static)
    ctx.check(f"3.3.15.0 L1: the static block (the derived look, the scales) has no colour literal, got {raw}", not raw
              and "--grid: radial-gradient(var(--grid-dot)" in static and "--soft-user: color-mix(in srgb, var(--user) 8%" in static)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
