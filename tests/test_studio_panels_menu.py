"""tests.test_studio_panels_menu -- Halo 3.3.2.0 "Quiet Studio" round R2: panels and layout leave the rail.
Headless Chrome through tests/helpers/studio_panels_menu.py (skipped without one), over a seeded scratch home;
no provider request, no model call:

1. the "+" menu in the section header lists the section's panels with the word a press does ("focus" an open
   one, "bring back" a strip with its badge, "add" an optional one); it opens from the keyboard (ArrowDown on
   its button), the arrows and End move, Escape closes it and gives the button the focus, Enter on a strip's
   row opens the panel again; a change of the user's shows the "custom layout" badge;
2. the palette's Reset layout is drawn disabled with its words on a default layout; Arrange panels (the
   section in its hint) puts a moved panel back in its default box and says so;
3. the "..." menu's Reset layout clears the saved layout and the badge goes; its rows then say what they would
   do (Reset disabled, "already default"); "How panels move" opens the section help on Moving panels, which the
   ? reaches too;
4. Fleet's "+" adds the optional Tree panel (the tree the expanded rail used to carry), the strips read "bring
   back"; Orchestra's "+" carries its RUNS group with New run; the rail holds the section rows and the chevron
   only, in both widths (<= 200 px expanded); Setup and Local (paged) have no "+", no "..." and no badge.
Run: python -m tests.test_studio_panels_menu
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
_RUN: dict = {}
ROLES = [["roles-lineups", "Lineups"], ["roles-bios", "Bios"], ["roles-graph", "Canvas"], ["roles-inspector", "Inspector"],
         ["roles-problems", "Problems"], ["roles-models", "Models"]]
STRIPS = ("fleet-health", "fleet-mission", "fleet-capabilities", "fleet-agent")


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the panels menu checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_panels_menu"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=420, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_the_rail_source_holds_sections_only(ctx: Ctx):
    rail = (UI / "shell" / "Rail.tsx").read_text(encoding="utf-8")
    for gone in ("function Panels", "function Layout", "FleetRail", "layout-arrange", "def.rail"):
        ctx.check(f"Rail.tsx has no {gone}", gone not in rail)
    ctx.check("the Fleet tree's old file is gone", not (UI / "routes" / "fleet" / "FleetRail.tsx").exists())
    css = (UI / "styles" / "shell.css").read_text(encoding="utf-8")
    ctx.check("the expanded rail is 200 px", '.app[data-rail="open"] { grid-template-columns: 200px minmax(0, 1fr) 0; }' in css)
    ctx.check("no .rail-more and no .rail-foot rule left", ".rail-more" not in css and ".rail-foot" not in css)


@test
def test_the_plus_menu_lists_and_brings_back(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Roles: six rows, each open panel 'focus', no badge, one PANELS group, got {got.get('rows')} {got.get('groups')}",
              got.get("rows") == [[p, "focus", [], t] for p, t in ROLES] and got.get("groups") == ["PANELS"])
    ctx.check(f"ArrowDown opens it on the first row, ArrowDown / End move, Escape gives the button back, got "
              f"{got.get('kbd_open')} {got.get('kbd_down')} {got.get('kbd_end')} {got.get('kbd_esc')}",
              [got.get(k) for k in ("kbd_open", "kbd_down", "kbd_end", "kbd_esc")] == ["roles-lineups", "roles-bios", "roles-models", "panels-add"])
    strip = {r[0]: r for r in got.get("rows_strip") or []}
    ctx.check(f"a collapsed panel reads 'bring back' with the strip badge, got {strip.get('roles-problems')}",
              strip.get("roles-problems") == ["roles-problems", "bring back", ["strip"], "Problems"])
    ctx.check(f"Enter on its row opens it again, got {got.get('brought_back')}", got.get("brought_back") == "open")
    ctx.check(f"no badge on a default layout, 'custom layout' after the change, got {got.get('badge_fresh')} {got.get('badge_custom')!r}",
              got.get("badge_fresh") is False and got.get("badge_custom") == "custom layout")


@test
def test_the_palette_arranges(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Reset layout on a default layout: disabled, its words, got {got.get('pal_reset_fresh')}",
              got.get("pal_reset_fresh") == ["Reset layout", "Roles: nothing to reset, the layout is the default", "true"])
    moved, default = got.get("moved") or {}, got.get("default") or {}
    ctx.check(f"Alt+Left moved the Inspector and saved the layout, got {moved.get('roles-inspector')} vs {default.get('roles-inspector')}",
              moved.get("roles-inspector") != default.get("roles-inspector") and got.get("saved_moved") is True)
    ctx.check(f"Arrange panels: enabled, the section in its hint, got {got.get('pal_arrange')}",
              got.get("pal_arrange") == ["Arrange panels", "Roles: the open panels back in their default places and sizes", None])
    ctx.check(f"it ran: the toast, every panel in its default box, got {got.get('arrange_toast')} {got.get('arranged')}",
              got.get("arrange_toast") == "arranged" and got.get("arranged") == default)


@test
def test_the_overflow_menu_resets_and_explains(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Reset layout from the ... menu: the toast, the badge gone, the key gone, got {got.get('badge_before')!r} {got.get('reset_toast')} {got.get('after')}",
              got.get("badge_before") == "custom layout" and got.get("reset_ran") is True and got.get("reset_toast") == "reset" and got.get("after") == [False, None])
    ctx.check(f"the rows say what they would do, got {got.get('more_rows')}",
              got.get("more_rows") == [["layout-arrange", False, ""], ["layout-reset", True, "already default"], ["layout-help", False, ""]])
    on, text = (got.get("moving") or ["", ""])[:2]
    ctx.check(f"How panels move opens the help on Moving panels, got {on!r} {text[:80]!r}",
              got.get("help_ran") is True and on == "true" and "Drag a title bar to move a panel (the others make room)" in text and "grows the focused one" in text)
    ctx.check(f"the ? reaches the same part, got {got.get('moving_from_q')}", got.get("moving_from_q") == "plain")


@test
def test_fleet_tree_orchestra_runs_setup_and_the_rail(ctx: Ctx):
    got = _got(ctx)
    before = {r[0]: r[1:3] for r in got.get("fleet_rows") or []}
    after = {r[0]: r[1:3] for r in got.get("fleet_rows_after") or []}
    ctx.check(f"Fleet: the Tree is 'add', each strip 'bring back' with its badge, got {before}",
              before.get("fleet-tree") == ["add", []] and all(before.get(s) == ["bring back", ["strip"]] for s in STRIPS)
              and before.get("fleet-ollama") == ["add", []] and len(before) == 11)  # 3.3.4.0 R5: + the optional Ollama panel
    ctx.check(f"the + added the Tree panel with the tree, its row now 'focus', got {got.get('tree')} {after.get('fleet-tree')}",
              got.get("tree") is True and after.get("fleet-tree") == ["focus", []])
    ctx.check(f"Orchestra's + carries RUNS with New run, got {got.get('orch_groups')} {got.get('orch_new_run')}",
              (got.get("orch_groups") or [""])[0] == "PANELS" and str((got.get("orch_groups") or ["", ""])[-1]).startswith("RUNS") and got.get("orch_new_run") is True)
    only = ["rail-sections,rail-toggle", 0, 0]
    ctx.check(f"the rail: sections only, in both widths, <= 200 px expanded, got {got.get('rail_icons')} {got.get('rail_open')} {got.get('rail_open_w')}",
              got.get("rail_icons") == only and got.get("rail_open") == only and 64 < (got.get("rail_open_w") or 0) <= 200)
    ctx.check(f"Setup: no +, no ..., no badge, got {got.get('setup')}", got.get("setup") == [False, False, False])
    ctx.check(f"3.3.5.0 R1: Local (paged) the same, got {got.get('local')}", got.get("local") == [False, False, False])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
