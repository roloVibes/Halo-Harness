"""tests.test_studio_type_scale -- Halo 3.6.0.0 R0a, rule R6 (the owner, 2026-11-12: "the panel is cramped ... fix that
for all of studio parts"): one type scale, 12 (data, captions), 13 (body), 15 (titles), 18 (a page title), nothing under
12 px. A lint over the source, no browser:

1. no sheet of the shell (ui/src/styles) or of a shipped pack's page (templates/packs/*/studio) sets a font size under
   12 px: a `font-size`, the size inside a `font:` shorthand, or a `--t-*` / `--fs*` token;
2. tokens.css names the scale (--ts-data 12, --ts-body 13, --ts-title 15, --ts-page 18) and the spacing scale
   (4 / 8 / 12 / 16 / 24), and the compact density set stays at 12 px or more;
3. no component sets a font size inline (`fontSize` in a .tsx): sizes live in the sheets, where this lint reads them.
The computed sizes of the drawn page are measured by the room test (tests/test_studio_room.py).
Run: python -m tests.test_studio_type_scale
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
PACKS = REPO / "halo_harness" / "templates" / "packs"
DECL = re.compile(r"(?<![\w-])(font-size|font|--t-[\w-]+|--fs[\w-]*)\s*:([^;{}]*)")
PX = re.compile(r"(?<![\w.-])(\d+(?:\.\d+)?)px")


def sheets() -> list:
    return sorted(UI.rglob("*.css")) + sorted(PACKS.glob("*/studio/**/*.css"))


def small_sizes(css: str) -> list:
    """Every (declaration, size) whose font size is under 12 px."""
    out = []
    for m in DECL.finditer(css):
        prop, val = m.group(1), m.group(2)
        size = PX.search(val)
        if not size:
            continue
        if float(size.group(1)) < 12:
            out.append((f"{prop}:{val.strip()}", float(size.group(1))))
    return out


@test
def test_the_lint_finds_a_small_size(ctx: Ctx):
    ctx.check("a 10.5 px font-size is found", small_sizes(".a { font-size: 10.5px; }") == [("font-size:10.5px", 10.5)])
    ctx.check("the size of a font shorthand is found", [s for _, s in small_sizes(".a { font: 600 11px/16px var(--mono); }")] == [11.0])
    ctx.check("a token is found", [s for _, s in small_sizes(":root { --t-caption: 500 10px/16px var(--mono); }")] == [10.0])
    ctx.check("a line height or a letter spacing is not a size", small_sizes(".a { font: 12px/9px var(--mono); letter-spacing: 1px; }") == [])
    ctx.check("--font-data is not a font declaration", small_sizes(":root { --font-data: var(--mono); }") == [])


@test
def test_no_sheet_sets_text_under_12_px(ctx: Ctx):
    found = sheets()
    ctx.check(f"the sheets are there ({len(found)})", len(found) > 40)
    bad = []
    for f in found:
        for decl, _ in small_sizes(f.read_text(encoding="utf-8")):
            bad.append(f"{f.relative_to(REPO).as_posix()}: {decl}")
    ctx.check(f"no font size under 12 px, got {bad[:8]}{' ...' if len(bad) > 8 else ''}", not bad)


@test
def test_the_scale_is_tokens(ctx: Ctx):
    css = (UI / "styles" / "tokens.css").read_text(encoding="utf-8")
    for name, px in (("--ts-data", 12), ("--ts-body", 13), ("--ts-title", 15), ("--ts-page", 18)):
        ctx.check(f"{name}: {px}px", f"{name}: {px}px;" in css)
    for name, px in (("--s-1", 4), ("--s-2", 8), ("--s-3", 12), ("--s-4", 16), ("--s-5", 24)):
        ctx.check(f"spacing {name}: {px}px", f"{name}: {px}px;" in css)
    m = re.search(r':root\[data-density="compact"\] \{(.*?)\}', css, re.S)
    ctx.check("the compact set keeps 12 px text", bool(m) and not small_sizes(m.group(1)) and "--fs: 12px;" in m.group(1))


@test
def test_no_inline_font_size(ctx: Ctx):
    bad = [p.relative_to(UI).as_posix() for p in UI.rglob("*.tsx") if re.search(r"\bfontSize\s*:", p.read_text(encoding="utf-8"))]
    bad += [p.relative_to(REPO).as_posix() for p in PACKS.glob("*/studio/**/*.tsx") if re.search(r"\bfontSize\s*:", p.read_text(encoding="utf-8"))]
    ctx.check(f"no inline fontSize in a component, got {bad}", not bad)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
