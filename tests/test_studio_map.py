"""tests.test_studio_map -- Halo 3.6.0.0 R3: Agents -> 3 · Map in headless Chrome, as a first-time user (driver
tests/helpers/studio_map.py over tests/helpers/crew_rig.py; skipped without Chrome). The room rules over this tab at
1280 / 1500 / 1920 are tests/test_studio_room.py's (the `map` view).

1. the 3 key opens 3 · Map: the switch reads 1 · Agents | 2 · Workflows | 3 · Map; the starter map,
   main at the left, a label per line in the lane, never over a box; no dialog, no conversation, the list closed;
2. a row dragged with the pointer: the drop places light up and say what a drop does; dropped on main, the When card at
   the line; "when the task says test" saved: the label, the receipt, the file;
3. a chain: coder's dot dragged onto reviewer (a column to the right), Always; a line back is refused in one sentence;
   the receipt's Undo takes the last change back;
4. the keyboard: Enter on a workflow row adds it under Not connected yet (tagged new); Enter on its dot lists targets;
   main, only when I ask; the workflow box opens to its steps and the link; hover lifts a box's lines and dims the rest;
   a label's card takes the line out (the box waits under Not connected yet again);
5. + New map (main only); New sessions run on this writes config crew.map (a fresh home tags no map); Lock: no dot, no Add;
6. a hand zoom survives the list drawer; Fit never under 75 %;
7. the builder on ship-it: ghost box and dashed line with its When; Apply draws them for real; Undo takes them away.
Run: python -m tests.test_studio_map
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    slow = {"HALO_STUDIO_SLOW_MS": os.environ["HALO_STUDIO_SLOW_MS"]} if os.environ.get("HALO_STUDIO_SLOW_MS") else None
    return driver_got(ctx, "tests.helpers.studio_map", why="the Map tab is driven in headless Chrome", cache=_RUN, timeout=600, env=slow)


@test
def test_the_3_key_opens_the_starter_map(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"3 lands on 3 · Map, got {got.get('view')!r}", got.get("view") == "map")
    ctx.check(f"the switch, got {got.get('switch')}", got.get("switch") == ["1 · Agents", "2 · Workflows", "3 · Map", "4 · Live"])  # 3.6.0.2 R52
    f = got.get("first") or {}
    ctx.check(f"the starter map, no dialog, no conversation, the list closed, got {f}",
              f.get("map") == "starter" and f.get("dialogs") == 0 and f.get("conversation") is False and f.get("drawer") is False)
    ctx.check(f"seven lines from main, their When in words, got {f.get('labels')}", f.get("labels") == ["main decides per task"] * 7)
    g = got.get("geom") or {}
    ctx.check(f"main at the left, no label over a box or another label, got {g}", g.get("main") is True and g.get("over") == 0 and g.get("boxes") == 8)
    ctx.check(f"the builder's hint on this tab, got {f.get('hint')!r}", f.get("hint") == "Say how things should connect, or ask why something happened")


@test
def test_a_drag_lights_the_drop_places_and_the_when_card(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"while dragging: the box and the strip say what a drop does, the one under the pointer marked, got {got.get('lit')}",
              got.get("lit") == ["drop: main hands work to it", "drop: add, connect later", True])
    ctx.check(f"dropped on main: the When card at the line, got {got.get('card')!r}", got.get("card") == "When does main hand work to tester?")
    ctx.check(f"the label and the receipt, got {got.get('label')!r} {got.get('receipt')!r}",
              got.get("label") == "says test" and got.get("receipt") == "main hands work to tester: says test.")
    ctx.check(f"the file, got {got.get('file')}", got.get("file") == [{"from": "main", "to": "tester", "when": {"says": ["test"]}}])


@test
def test_a_chain_a_circle_refused_and_undo(ctx: Ctx):
    got = _got(ctx)
    ctx.check("coder -> reviewer, Always, reviewer one column right", got.get("chain") is True and got.get("cols") == [True])
    ctx.check(f"a line back: one sentence naming the circle, got {got.get('circle')!r}",
              "circle (coder -> reviewer -> coder)" in str(got.get("circle")))
    ctx.check(f"the receipt's Undo puts the last change back, got {got.get('undone')!r}", got.get("undone") == "main decides per task")


@test
def test_the_keyboard_the_strip_a_workflow_box_and_hover(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Enter on a workflow row: under Not connected yet, tagged new, got {got.get('strip')}", got.get("strip") is True)
    ctx.check(f"Enter on its dot: a list of who may hand it work, main first, got {got.get('pick')}", (got.get("pick") or [""])[0] == "main")
    ctx.check(f"its box opened: its steps and the link to Workflows, got {got.get('steps')}",
              got.get("steps") == ["1 · Review (reviewer)", "2 · Test (tester)", "To change the steps: open it in Workflows"])
    ctx.check("hover lifts its lines and dims the rest", got.get("hover") is True)
    ctx.check("a label's card takes the line out: the box waits under Not connected yet", got.get("back") is True)


@test
def test_more_than_one_map_uses_and_lock(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"+ New map: main only, got {got.get('new')}", got.get("new") == 1)
    # 3.6.0.2 R24 (rewritten to the truth): the switch says "New sessions run on this"; a fresh home tags no map
    ctx.check(f"a fresh home: no map tagged; new sessions run on starter, the default: no switch there (P4 batch 12, rewritten to the truth: it could change nothing), the plain sentence, got {got.get('fresh_tags')} {got.get('uses_off')}",
              not any(" · new sessions" in o or " · running in " in o or "my sessions use this" in o for o in got.get("fresh_tags") or ["?"])
              and got.get("uses_off") == [False, "New sessions run on starter (the default)."])
    ctx.check(f"New sessions run on this (ship-it): config crew.map, got {got.get('in_use')!r}", got.get("in_use") == "ship-it")
    ctx.check(f"... and ship-it is tagged new sessions, got {got.get('tagged')!r}", str(got.get("tagged")).endswith(" · new sessions"))
    ctx.check("Lock: no dot, no Add", got.get("locked") is True)


@test
def test_a_hand_zoom_survives_the_drawer_and_fit(ctx: Ctx):
    got = _got(ctx)
    hand = got.get("hand") or ["", ""]
    ctx.check(f"a zoom by hand survives the drawer closing, got {hand}", hand[0] and hand[0] == hand[1])
    ctx.check(f"Fit: never under 75 %, got {got.get('fit')}", (got.get("fit") or 0) >= 0.75)


@test
def test_the_builder_draws_ghosts_apply_undo(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the preview's line on the map: a ghost box, a dashed line, its When, got {got.get('ghost')!r}", got.get("ghost") == "says auth")
    lines = got.get("lines") or []
    ctx.check(f"one preview: the copy, the box, the line with its When, got {lines}",
              len(lines) == 3 and "code hands work to my-reviewer, when the task says auth" in lines[2])
    ctx.check("Apply draws it for real; Undo takes it away", got.get("applied") is True and got.get("b_undone") is True)
    ctx.check(f"the driver ran every step, got {got.get('failed')!r}", not got.get("failed"))


@test
def test_the_old_doors_land_on_the_four_tabs(ctx: Ctx):
    """3.6.0.0 R5: Cast and the board went; their addresses and keys land on the Map (the board's on Workflows). 3.6.0.2 R52:
    Live is a tab again, so its address and L land on it."""
    d = _got(ctx)
    want = {"&view=cast": "map", "&view=live": "live", "&view=orchestra": "map", "&view=flows": "workflows", "&mode=roles": "map",
            "&mode=team": "map", "&mode=fleet": "map"}
    ctx.check(f"each old address on its tab, got {d}", all(d.get(k) == v for k, v in want.items()))
    ctx.check(f"mode=fleet says Fleet left once, got {d.get('fleet_note')!r}", "Fleet left Halo in 3.5" in str(d.get("fleet_note")))
    ctx.check(f"the keys: W -> Workflows, C -> Map, L and 4 -> Live, got {d}", d.get("key_w") == "workflows" and d.get("key_c") == "map"
              and d.get("key_l") == "live" and d.get("key_4") == "live")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
