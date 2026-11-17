"""tests.test_studio_map_live -- a session's run drawn while it works (3.6.0.0 R4; 3.6.0.2 R34: in Agents -> 4 · Live, the
Map is the plan), and History replayed on 3 · Map, in headless Chrome as a first-time user (driver
tests/helpers/studio_map_live.py over the session rig and the live rig: a real session with the row's `map`, extra agent
rows and the map frames a session on a map sends; skipped without Chrome). The overlay's own rules are
tests/test_map_overlay.py's; the frames' source is tests/test_map_chains.py.

1. 4 · Live's head: the session's T-state (it runs on shop) and its status line (who works, dollars); the tab dot on 4 · Live;
2. each box's state, its face ("{kind} · {state}"), nothing cut; a stray agent no box started: no row of any box,
   counted among those working in the status line, never a hand-off outside the map;
3. a hand-off lights the line its frame names (the label: the task, then its When again); a chain; reduced motion;
4. a workflow box is its block: the head and a row per step, its agent; a click on the head opens the step-in card;
5. a made-up child is a row "made up: {task} · {state}" in main's box with Save as an agent, a saved row has none; Save
   opens the form with its body, nothing written;
6. the Map's drawer (P4 batch 4 moves the Feed to Live): filtered by the clicked box, THINK / SAY / TALK rows, an ask's
   answers and its box waiting on you, the keyboard; Steer and Stop reach the session's command route;
8. another map open on 3 · Map: 4 · Live still draws shop, lit, nothing amber;  9. a session with no map: T4 in Live;
10. History (on the Map, R55): the picker, Replay it on the map (quiet colours, a removed box), the scrubber, the card;
the room in Live at 1280 / 1500 / 1920 and a zoom step while frames arrive; 11. Session's Live drawer, its link to Live.
Run: python -m tests.test_studio_map_live
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}
# R14: the block of the workflow review in the box check, its head then a row per step (EVERY step)
STEPS = ["workflow review · step 2 of 2", "1 Review · reviewer · done", "2 Test · tester · working"]  # no model: the frames name none


def _got(ctx: Ctx) -> dict:
    slow = {"HALO_STUDIO_SLOW_MS": os.environ["HALO_STUDIO_SLOW_MS"]} if os.environ.get("HALO_STUDIO_SLOW_MS") else None
    return driver_got(ctx, "tests.helpers.studio_map_live", why="the lit Map is driven in headless Chrome", cache=_RUN, timeout=900, env=slow)


@test
def test_the_top_line_and_the_tab_dot(ctx: Ctx):
    got = _got(ctx)
    head = got.get("head") or ["", ""]  # 3.6.0.2 R34: Live's head is the T-state (shop is not the map new sessions use: T2)
    ctx.check(f"Live's T-state line: it runs on shop, got {head}", head[0] in ("T1", "T2") and "on shop, as it started" in str(head[1]))
    ctx.check(f"the status line: who works, dollars, got {got.get('sentence')!r}",
              "agents working" in str(got.get("sentence")) and "$" in str(got.get("sentence")))
    ctx.check(f"the tab's dot on 4 · Live (3.6.0.2 R52: a run is Live's), none on 3 · Map, got {got.get('dot')}",
              got.get("dot") == ["1", "4 · Live", ""])


@test
def test_each_box_says_its_state_and_nothing_is_cut(ctx: Ctx):
    got = _got(ctx)
    s = got.get("states") or {}
    ctx.check(f"working / not used yet per box, got {s}", s.get("code") == "working" and s.get("check") == "working" and s.get("notes") == "idle"
              and s.get("main") == "working")
    ctx.check(f"code's face: agent, working, got {got.get('code_face')!r}", str(got.get("code_face")).startswith("agent · working"))
    ctx.check(f"not used yet, got {got.get('notes_face')}", got.get("notes_face") == ["agent · not used yet"])
    ctx.check(f"nothing cut, got {got.get('cut')}", got.get("cut") == 0)
    # rewritten to the truth on 4 · Live (was: "an agent no box claims: in the strip, tagged 'not on this map'", the Map's
    # strip, which the run's drawing does not have): R15 R17 R23, see tests/helpers/studio_map_live_steps.py `stray`
    sg = got.get("stranger") or {}
    ctx.check(f"an agent no box claims: no row of any box in Live, got {sg.get('rows')!r}", sg.get("rows") == 0)
    n = re.match(r"(\d+) agents working", str(sg.get("working")))
    left = str(sg.get("done"))
    ctx.check(f"... counted among those working: one fewer once it is done, as many again when it works, got {sg}",
              bool(n) and (left.startswith(f"{int(n.group(1)) - 1} agents working") if int(n.group(1)) > 2 else not left.startswith(f"{n.group(1)} agents"))
              and sg.get("again") == sg.get("working"))
    off = re.compile(r" · \d+ hand-offs? outside the map$")
    ctx.check(f"... and never a hand-off outside the map (no box started it): the count is the same either way, got {sg}",
              (off.search(str(sg.get("working"))) or [""])[0] == (off.search(left) or [""])[0])


@test
def test_a_hand_off_moves_along_the_line_it_named(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the label shows the task, got {got.get('pulse')!r}", got.get("pulse") == "apply the discount before tax")
    ctx.check(f"the line lit, its trace counts one hand-off, got {got.get('travel')}",
              (got.get("travel") or [""])[0] in ("live", "trace") and got["travel"][1] == "1")
    ctx.check(f"then its When again, got {got.get('back')!r}", got.get("back") == "always")
    ctx.check(f"a chain: the next line's label, got {got.get('chain')!r}", got.get("chain") == "check the basket diff")
    ctx.check("reduced motion: the line lit, nothing travels", got.get("reduced") is True)


@test
def test_an_opened_workflow_box_lights_its_steps(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"R14: its block, the head and a row per step with its agent, got {got.get('steps')}", got.get("steps") == STEPS)
    ctx.check(f"a click on the head opens the step-in card for it, got {got.get('open_drawer')!r}", got.get("open_drawer") == "head:review")


@test
def test_a_made_up_helper_and_save_as_an_agent(ctx: Ctx):
    got = _got(ctx)
    h = got.get("helper") or ["", False, "", False]  # 3.6.0.2 R15: a made-up row in main's box with Save; saved rows have none
    ctx.check(f"a made-up row in main's box with Save as an agent; a saved row has none, got {h}",
              h[0] == "made up: List what the shop repo holds for the re · working" and h[1] is True and h[2] == "main" and h[3] is True)
    ctx.check(f"Save as an agent: the Agents form with its body, not saved, got {got.get('view')!r} {got.get('form')}",
              got.get("view") == "crew" and (got.get("form") or ["", False])[0] == "list-what-shop" and got["form"][1] is True)
    ctx.check(f"nothing written, got {got.get('written')}", got.get("written") == [])


@test
def test_the_drawer_steer_stop_and_an_ask(ctx: Ctx):
    """3.6.0.2 R57: the drawer is 4 · Live's Feed (it was the Map's): opened from its button, set by a click on Live's box."""
    got = _got(ctx)
    ctx.check(f"a click on Live's box filters the Feed to it, got {got.get('filter')!r}", got.get("filter") == "code")
    ctx.check(f"THINK, SAY and TALK rows, got {got.get('kinds')}", {"think", "text", "talk"} <= set(got.get("kinds") or []))
    ctx.check(f"an ask: its box waits on you, its answers are buttons, got {got.get('waits')!r} {got.get('ask_keys')}",
              got.get("waits") == "waiting" and (got.get("ask_keys") or 0) >= 2)  # R57: Live's block box is marked waiting (its rows are its steps)
    ctx.check(f"Enter on a box of Live sets the Feed to its words, got {got.get('keyboard')!r}", got.get("keyboard") == "research")
    ctx.check(f"Steer reaches the session, got {got.get('steer')}", got.get("steer") == ["agent_steer", 200])
    ctx.check(f"Stop (asked first) reaches it, got {got.get('stop')}", got.get("stop") == ["agent_stop", 200])


@test
def test_another_map_open_on_map_live_unchanged_and_a_session_with_no_map(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"3 · Map on starter: 4 · Live still draws shop, nothing amber, got {got.get('amber')}", got.get("amber") == ["shop", 0])
    ctx.check(f"and lit, got {got.get('unlit')}", (got.get("unlit") or 0) >= 1)
    head = str(got.get("nomap_head"))
    ctx.check(f"no map: T4 in section 4's words, got {head!r}",
              head.startswith("This session runs with no map, as it started at ") and head.endswith(": main does the work and starts its own agents."))
    ctx.check(f"no drawing and no Show it, got {got.get('boxes')}", got.get("boxes") == [0, False])
    ctx.check(f"the map again, its lines' labels, got {got.get('again')}", got.get("again") == 5)


@test
def test_history_replays_a_run_on_its_map(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the picker lists the finished run, got {got.get('rows')}", len(got.get("rows") or []) >= 1)
    ctx.check(f"replayed on this map in quiet colours, its box done, its line fired, got {got.get('replay')!r} {got.get('quiet')!r} {got.get('fired_end')!r}",
              got.get("replay") == "replay" and got.get("quiet") == "done" and got.get("fired_end") == "1")
    ctx.check(f"a box the run used that the map lost: removed since, got {got.get('removed')}", got.get("removed") == ["pdfs"])
    ctx.check(f"the scrubber at the start: not used yet, got {got.get('at_start')!r}", got.get("at_start") == "idle")
    ctx.check(f"the report card from the picker row, got {got.get('card')!r}", str(got.get("card")).startswith("session:"))
    ctx.check(f"back to now, got {got.get('now')!r}", got.get("now") == "live")


@test
def test_the_room_and_a_zoom_while_frames_arrive(ctx: Ctx):
    got = _got(ctx)
    for w in (1280, 1500, 1920):
        r = got.get(f"room_{w}") or {}
        ctx.check(f"{w}: in Live no sideways scroll, nothing under 12 px, controls >= 28 px, nothing cut, got {r}",
                  r == {"small": 0, "ctl": 0, "side": 0, "cut": 0})
    z = got.get("zoom") or ["", "x"]
    ctx.check(f"his zoom holds while a helper and a hand-off arrive, got {z}", z[0] and z[0] == z[1])


@test
def test_sessions_map_panel_is_the_lit_map(ctx: Ctx):
    got = _got(ctx)
    p = got.get("panel") or ["", 0, False, 9, 1, False]  # 3.6.0.2 R7 R15: drawn down, children as named rows
    ctx.check(f"Session's Live drawer: shop, >= 6 boxes, every box under main, <= 2 a row, no dot or label, a named row, got {p}",
              p[0] == "shop" and p[1] >= 6 and p[2] is True and p[3] <= 2 and p[4] == 0 and p[5] is True)
    ctx.check(f"its link opens Agents -> 4 · Live on this session, got {got.get('to_tab')!r}", got.get("to_tab") == "shop")
    ctx.check(f"the driver ran every step, got {got.get('failed')!r}", not got.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
