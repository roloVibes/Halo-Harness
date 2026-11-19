"""tests.test_studio_density -- Halo 3.3.16.0 R1b, the density pass (the owner, 2026-11-09: "small blocks that make it
hard to use ... needs a review to make studio cleaner and clearer"; ROADMAP: no control bar under 36 px, no strip under
40 px, 12 px minimum padding, one thing per section). Unit pins over the source, then headless Chrome through
tests/helpers/studio_density.py (skipped without one); no provider request, no model call:

1. the primitives mark themselves: a panel's title bar, Tabs, the header, Agents' bar, Setup's step rail, an inspector
   page's head, a form's button row and the view bar are `data-density="bar"`; an inspector Edit row and a page
   rail's item are `"row"`; a panel's body is `"body"`; the sizes are tokens (--ctl-h 36, --row-h 40) and no section
   sheet sets a panel body's padding to 0 (the 12 px is the primitive's, never exempted);
2. Chrome, every core section on load (Session, Agents on Cast / Live and on the fleet, Packs, Setup and its
   Machines page, Settings, Local), the inspector's summary and one page, and (3.3.16.0 R2) the glance (3.6.0.5 r: the
   Attention queue is Session's drawer, measured with Session's panels): every bar >= 36 px, every row >= 40 px, every body inset >= 12 px, each
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
SECTIONS = ("session", "agents-map", "agents-busy", "packs", "setup", "settings", "local")  # R5: three tabs
BAR, ROW, PAD, GAP = 36, 40, 12, 12


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_density", why="the density pass measures the page in headless Chrome",
                      cache=_RUN, timeout=480, tail=600, what="the density driver")


def _src(rel: str) -> str:
    return (UI / rel).read_text(encoding="utf-8")


DOCKS = ("map-builder", "crew-builder", "flow-builder")  # 3.6.0.0 R5: the builder box, docked on every tab


def offenders(got: dict) -> list:
    """Every 'section: testid NN px (rule)' in the order the sections were opened."""
    out = []
    for name in (*SECTIONS, "agents-map-strip"):
        m = got.get(name) or {}
        out += [f"{name}: bar {t} {h} px (< {BAR})" for t, h in m.get("bars") or [] if h < BAR]
        out += [f"{name}: row {t} {h} px (< {ROW})" for t, h in m.get("rows") or [] if h < ROW]
        out += [f"{name}: body {t} inset {h} px (< {PAD})" for t, h in m.get("bodies") or [] if h < PAD]
        for p in m.get("panels") or []:
            if p and p[0] in DOCKS:  # a dock (the builder box) is one line at the main thing's foot, no title bar
                continue
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
    ctx.check("a panel's title bar and its body are marked, and the view bar (3.6.0.0 R0a: the strips went)",
              'className="panel-bar" data-density="bar"' in panel and panel.count('data-density="body"') == 3
              and 'data-density="bar"' in _src("lib/workspace/ViewBar.tsx"))
    for rel, mark in (("lib/ui/Tabs.tsx", 'data-density="bar"'), ("shell/Header.tsx", 'className="topbar" data-density="bar"'),
                      ("routes/setup/SetupRail.tsx", 'data-density="bar"'),  # R5: the tab switch sits in each tab's view bar
                      ("routes/local/LocalRail.tsx", 'data-density="row"'), ("routes/settings/SettingsRail.tsx", 'data-density="row"')):
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
def test_the_hover_card_keeps_the_rules(ctx: Ctx):
    """3.3.16.1: the hover card (styles/hover-card.css) -- the 12 px inset, a row per fact at least 20 px tall, the labels
    in the inspector's small mono caps, the text wrapping inside its row; tests/test_studio_hover.py measures it drawn."""
    css = _src("styles/hover-card.css")
    card = re.search(r"\.hover-card\s*\{([^}]*)\}", css)
    ctx.check("the card's inset is the 12 px token", bool(card) and "padding: var(--s-3)" in card.group(1))
    row = re.search(r"\.hc-row\s*\{([^}]*)\}", css)
    ctx.check("a row is at least 20 px", bool(row) and "min-height: 20px" in row.group(1))
    dt = re.search(r"\.hc-row dt\s*\{([^}]*)\}", css)
    ctx.check("its label is mono caps", bool(dt) and "var(--font-data)" in dt.group(1) and "text-transform: uppercase" in dt.group(1))
    dd = re.search(r"\.hc-row dd\s*\{([^}]*)\}", css)
    ctx.check("its value wraps inside the row (never cut, never over)", bool(dd) and "overflow-wrap: anywhere" in dd.group(1) and "min-width: 0" in dd.group(1))
    ctx.check("tokens only: no raw colour", not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", css))


@test
def test_every_section_was_measured(ctx: Ctx):
    got = _got(ctx)
    for name in SECTIONS:
        m = got.get(name) or {}
        ctx.check(f"{name}: drawn and measured, got {len(m.get('bars') or [])} bars", len(m.get("bars") or []) >= 1)
    for name in ("session", "agents-busy", "agents-map", "packs"):
        m = got.get(name) or {}
        ctx.check(f"{name}: its workspace's panels each opened and measured, got {len(m.get('panels') or [])} of {m.get('cells')}",
                  m.get("cells", 0) >= 3 and len(m.get("panels") or []) == m.get("cells"))
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
        opened = [o for o in (got.get(name) or {}).get("open") or [] if o not in DOCKS]
        ctx.check(f"{name}: at most one panel open on load, got {opened}", len(opened) <= 1)


@test
def test_the_living_canvas_pieces_pass_the_rules(ctx: Ctx):
    """3.3.18.0; 3.6.0.0 R5: the Map over a home with nothing running (its panels too) and the strip under it (its rows
    targets) pass the rules (3.6.0.3 B: History, under the map before, left Studio)."""
    got = _got(ctx)
    m = got.get("agents-map") or {}
    ctx.check(f"the Map over a home with nothing running: its panels measured, got {len(m.get('panels') or [])} of {m.get('cells')}",
              m.get("cells", 0) >= 3 and len(m.get("panels") or []) == m.get("cells"))
    h = got.get("agents-map-strip") or {}
    ctx.check(f"the Map with its strip was measured, got {sorted(h)[:6]}", bool(h))
    rows = [r for r in h.get("rows") or [] if "strip" in str(r[0])]
    ctx.check(f"the strip's rows are targets >= 40 px (or none yet), got {rows}", all(v >= ROW for _, v in rows))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
