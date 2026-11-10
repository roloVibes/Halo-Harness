"""tests.test_studio_density -- Halo 3.3.16.0 R1b, the density pass (the owner, 2026-11-09: "small blocks that make it
hard to use ... needs a review to make studio cleaner and clearer"; ROADMAP: no control bar under 36 px, no strip under
40 px, 12 px minimum padding, one thing per section). Unit pins over the source, then headless Chrome through
tests/helpers/studio_density.py (skipped without one); no provider request, no model call:

1. the primitives mark themselves: a panel's title bar, Tabs, the header, Agents' bar, Setup's step rail, an inspector
   page's head and a form's button row are `data-density="bar"`; a collapsed panel, an inspector Edit row and a page
   rail's item are `"row"`; a panel's body is `"body"`; the sizes are tokens (--ctl-h 36, --row-h 40) and no section
   sheet sets a panel body's padding to 0 (the 12 px is the primitive's, never exempted);
2. Chrome, every core section on load (Session, Agents on Cast / Runs / Live, Fleet, Packs, Setup, Settings, Local) and
   the inspector's summary and one page: every bar >= 36 px, every row >= 40 px, every body inset >= 12 px, each
   workspace panel opened in turn (its bar and its body the same), 12 px between the panels, one panel open on load;
   the first offender fails with its section, its testid and its height.
Run: python -m tests.test_studio_density
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
_RUN: dict = {}
SECTIONS = ("session", "agents-cast", "agents-runs", "agents-live", "fleet", "packs", "setup", "settings", "local")
BAR, ROW, PAD, GAP = 36, 40, 12, 12


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_density", why="the density pass measures the page in headless Chrome",
                      cache=_RUN, timeout=480, tail=600, what="the density driver")


def _src(rel: str) -> str:
    return (UI / rel).read_text(encoding="utf-8")


def offenders(got: dict) -> list:
    """Every 'section: testid NN px (rule)' in the order the sections were opened."""
    out = []
    for name in (*SECTIONS, "inspector-summary", "inspector-page"):
        m = got.get(name) or {}
        out += [f"{name}: bar {t} {h} px (< {BAR})" for t, h in m.get("bars") or [] if h < BAR]
        out += [f"{name}: row {t} {h} px (< {ROW})" for t, h in m.get("rows") or [] if h < ROW]
        out += [f"{name}: body {t} inset {h} px (< {PAD})" for t, h in m.get("bodies") or [] if h < PAD]
        for p in m.get("panels") or []:
            if p and p[1] < BAR:
                out.append(f"{name}: panel {p[0]} bar {p[1]} px (< {BAR})")
            if p and p[2] < PAD:
                out.append(f"{name}: panel {p[0]} body inset {p[2]} px (< {PAD})")
        if m.get("gap") is not None and m["gap"] < GAP:
            out.append(f"{name}: {m['gap']} px between two panels (< {GAP})")
    return out


@test
def test_the_primitives_mark_themselves(ctx: Ctx):
    panel = _src("lib/workspace/Panel.tsx")
    ctx.check("a panel's title bar, its body and its strip are marked", 'className="panel-bar" data-density="bar"' in panel
              and panel.count('data-density="body"') == 3 and 'data-density={p.collapsed ? "row" : undefined}' in panel)
    for rel, mark in (("lib/ui/Tabs.tsx", 'data-density="bar"'), ("shell/Header.tsx", 'className="topbar" data-density="bar"'),
                      ("routes/agents/ViewSwitch.tsx", 'data-density="bar"'), ("routes/setup/SetupRail.tsx", 'data-density="bar"'),
                      ("routes/local/LocalRail.tsx", 'data-density="row"'), ("routes/settings/SettingsRail.tsx", 'data-density="row"'),
                      ("routes/roles/LineupSummary.tsx", 'data-density="row"'), ("routes/roles/LineupPage.tsx", 'data-density="bar"')):
        ctx.check(f"{rel} carries {mark}", mark in _src(rel))


@test
def test_the_sizes_are_tokens_and_nothing_is_exempted(ctx: Ctx):
    tokens = _src("styles/tokens.css")
    ctx.check("--ctl-h 36 and --row-h 40 in the comfortable set", "--ctl-h: 36px; --row-h: 40px;" in tokens)
    for rel in ("styles/local.css", "styles/settings.css", "styles/roles-inspector.css"):
        ctx.check(f"{rel} sizes its rows with --row-h", "min-height: var(--row-h)" in _src(rel))
    zero = [p.name for p in (UI / "styles").glob("*.css")
            if re.search(r"\.panel-body[^{]*\{[^}]*\bpadding:\s*0\s*[;}]", p.read_text(encoding="utf-8"))]
    ctx.check(f"no sheet sets a panel body's padding to 0, got {zero}", zero == [])


@test
def test_every_section_was_measured(ctx: Ctx):
    got = _got(ctx)
    for name in SECTIONS:
        m = got.get(name) or {}
        ctx.check(f"{name}: drawn and measured, got {len(m.get('bars') or [])} bars", len(m.get("bars") or []) >= 1)
    for name in ("session", "fleet", "agents-cast", "agents-live", "packs"):
        m = got.get(name) or {}
        ctx.check(f"{name}: its workspace's panels each opened and measured, got {len(m.get('panels') or [])} of {m.get('cells')}",
                  m.get("cells", 0) >= 4 and len(m.get("panels") or []) == m.get("cells"))
    for name, rows in (("settings", 15), ("local", 8)):
        ctx.check(f"{name}: its page rail's rows measured", len((got.get(name) or {}).get("rows") or []) >= rows)


@test
def test_no_bar_under_36_no_row_under_40_no_body_under_12(ctx: Ctx):
    bad = offenders(_got(ctx))
    ctx.check(f"the first offender: {bad[0] if bad else 'none'} ({len(bad)} in all)", not bad)


@test
def test_one_thing_per_section_on_load(ctx: Ctx):
    got = _got(ctx)
    for name in SECTIONS:
        opened = (got.get(name) or {}).get("open") or []
        ctx.check(f"{name}: at most one panel open on load, got {opened}", len(opened) <= 1)
    ctx.check("an edit target opens the canvas and the inspector, nothing else",
              sorted((got.get("inspector-summary") or {}).get("open") or []) == ["roles-graph", "roles-inspector"])


@test
def test_the_inspector_rows_are_targets(ctx: Ctx):
    got = _got(ctx)
    rows = [r for r in (got.get("inspector-summary") or {}).get("rows") or [] if r[0].startswith("roles-block-")]
    ctx.check(f"the summary's twelve Edit rows, each >= 40 px, got {rows}", len(rows) == 12 and min(h for _t, h in rows) >= ROW)
    bars = [b for b in (got.get("inspector-page") or {}).get("bars") or [] if b[0] == "roles-page-budget"]
    ctx.check(f"a page's head is a bar >= 36 px, got {bars}", len(bars) == 1 and bars[0][1] >= BAR)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
