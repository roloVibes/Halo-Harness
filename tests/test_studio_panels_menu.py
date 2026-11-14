"""tests.test_studio_panels_menu -- Halo 3.3.2.0 "Quiet Studio" round R2: panels and layout leave the rail; 3.6.0.0 R0a:
the header's "+" became the view bar. Headless Chrome through tests/helpers/studio_panels_menu.py (skipped without
one), over a seeded scratch home; no provider request, no model call:

1. Agents' view bar on Cast names every panel of the view: the left drawers (Lineups, Bios), the Canvas with its tabs
   (Activity and the plan review to add), the right drawers (Inspector, Problems, Models), every drawer closed on
   load; a focused button and Enter open its drawer beside the canvas (the button pressed), the panel's close puts it
   away; opening a drawer is never a "custom layout";
2. the palette's Reset layout is drawn disabled with its words on a default layout; "Show panel: Inspector" opens its
   drawer; Alt+Left on it widens it by 40 px and the width is kept (the v3 record); Reset layout is enabled then;
3. the "..." menu's Reset layout (the toast) closes every drawer and clears the saved key; its rows then say so
   (Reset disabled, "already default"); "How panels open" opens the section help on Moving panels, which the ?
   reaches too;
4. Agents -> Live's bar adds the optional Activity tab (it takes the canvas's place); the rail holds the section rows
   and the chevron only, in both widths (<= 200 px expanded; 176 since 3.3.15.0); Setup and Local (paged) have no view
   bar, no "..." and no badge.
Run: python -m tests.test_studio_panels_menu
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.driver_got import got as driver_got  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
_RUN: dict = {}
ROWS = [["roles-lineups", "closed", "drawer", "Lineups"], ["roles-bios", "closed", "drawer", "Bios"],
        ["roles-graph", "open", "main", "Canvas"], ["fleet-activity", "add", "tab", "Activity"], ["orchestra-plan", "add", "tab", "Plan"],
        ["roles-inspector", "closed", "drawer", "Inspector"], ["roles-problems", "closed", "drawer", "Problems"],
        ["roles-models", "closed", "drawer", "Models"]]


def _got(ctx: Ctx) -> dict:
    info = driver_got(ctx, "tests.helpers.studio_panels_menu", why="the panels menu checks need headless Chrome",
                      cache=_RUN, timeout=420, tail=600)
    return info


@test
def test_the_rail_source_holds_sections_only(ctx: Ctx):
    rail = (UI / "shell" / "Rail.tsx").read_text(encoding="utf-8")
    for gone in ("function Panels", "function Layout", "FleetRail", "layout-arrange", "def.rail"):
        ctx.check(f"Rail.tsx has no {gone}", gone not in rail)
    ctx.check("the Fleet tree's old file is gone", not (UI / "routes" / "fleet" / "FleetRail.tsx").exists())
    css = (UI / "styles" / "shell.css").read_text(encoding="utf-8")
    ctx.check("the expanded rail is 176 px (3.3.15.0 L1; 200 before)", '.app[data-rail="open"] { grid-template-columns: 176px minmax(0, 1fr) 0; }' in css)
    ctx.check("no .rail-more and no .rail-foot rule left", ".rail-more" not in css and ".rail-foot" not in css)


@test
def test_the_view_bar_names_and_opens(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Agents' bar on Cast: the left drawers, the Canvas and its tabs, the right drawers, every drawer closed, got {got.get('rows')}",
              got.get("rows") == ROWS)
    ctx.check(f"no drawer drawn on load, no badge, got {got.get('drawers_fresh')} {got.get('badge_fresh')}",
              got.get("drawers_fresh") == [] and got.get("badge_fresh") is False)
    ctx.check(f"the button takes the focus, got {got.get('focus')!r}", got.get("focus") == "roles-problems")
    opened = got.get("opened") or [[], "", True]
    ctx.check(f"Enter opens Problems as a right drawer at its content's width, pressed, no custom layout, got {opened}",
              opened[0] == [["roles-problems", "right", 360]] and opened[1] == "true" and opened[2] is False)
    ctx.check(f"its close puts it away, got {got.get('closed')}", got.get("closed") == [[], "false"])


@test
def test_the_palette_shows_and_widens(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Reset layout on a default layout: disabled, its words, got {got.get('pal_reset_fresh')}",
              got.get("pal_reset_fresh") == ["Reset layout", "Agents: nothing to reset, every drawer is closed", "true"])
    ctx.check(f"Show panel: Inspector is a palette line, got {got.get('pal_show')}", (got.get("pal_show") or [""])[0] == "Show panel: Inspector")
    before, after, saved = (got.get("widened") or [[], [], {}])[:3]
    ctx.check(f"Alt+Left widens the Inspector drawer by 40 px, kept in the v3 record, got {before} {after} {saved}",
              before == [["roles-inspector", "right", 400]] and after == [["roles-inspector", "right", 440]]
              and (saved or {}).get("v") == 3 and (saved or {}).get("widths") == {"roles-inspector": 440} and (saved or {}).get("open") == ["roles-inspector"])
    ctx.check(f"Reset layout is enabled now, the section in its hint, got {got.get('pal_reset_now')}",
              got.get("pal_reset_now") == ["Reset layout", "Agents: every drawer closed, the main thing back", None])


@test
def test_the_overflow_menu_resets_and_explains(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Reset layout from the ... menu: the toast, the drawers closed, the key gone, got {got.get('reset_toast')} {got.get('after')}",
              got.get("reset_ran") is True and got.get("reset_toast") == "reset" and got.get("after") == [[], None])
    ctx.check(f"the rows say what they would do, got {got.get('more_rows')}",
              got.get("more_rows") == [["layout-reset", True, "already default"], ["layout-help", False, ""]])
    on, text = (got.get("moving") or ["", ""])[:2]
    ctx.check(f"How panels open opens the help on Moving panels, got {on!r} {text[:80]!r}",
              got.get("help_ran") is True and on == "true" and "Every other panel is a button in the bar above it" in text and "resets the layout" in text)
    ctx.check(f"the ? reaches the same part, got {got.get('moving_from_q')}", got.get("moving_from_q") == "plain")


@test
def test_live_activity_setup_local_and_the_rail(ctx: Ctx):
    got = _got(ctx)
    before = {r[0]: r[1] for r in got.get("fleet_rows") or []}
    after = {r[0]: r[1] for r in got.get("fleet_rows_after") or []}
    ctx.check(f"Live: Activity is 'add', the drawers closed, got {before}",
              before.get("fleet-activity") == "add" and before.get("roles-inspector") == "closed" and len(before) == 8)
    ctx.check(f"the bar added Activity with its log in the canvas's place, its button shown, the canvas's not, got {got.get('tree')} {after}",
              got.get("tree") is True and after.get("fleet-activity") == "open" and after.get("roles-graph") == "closed")
    only = ["rail-sections,rail-toggle", 0, 0]
    ctx.check(f"the rail: sections only, in both widths, <= 200 px expanded, got {got.get('rail_icons')} {got.get('rail_open')} {got.get('rail_open_w')}",
              got.get("rail_icons") == only and got.get("rail_open") == only and 64 < (got.get("rail_open_w") or 0) <= 200)
    ctx.check(f"Setup: no view bar, no ..., no badge, got {got.get('setup')}", got.get("setup") == [False, False, False])
    ctx.check(f"Local (paged; its Media drawers come from the palette): no view bar, no ..., no badge, got {got.get('local')}",
              got.get("local") == [False, False, False])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
