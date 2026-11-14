"""tests.test_studio_map_live -- Halo 3.6.0.0 R4: Agents -> 3 · Map lit while a session runs, and History replayed on
it, in headless Chrome as a first-time user (driver tests/helpers/studio_map_live.py over the session rig and the live
rig: a real session with the row's `map`, extra agent rows and the map frames a session on a map sends; skipped
without Chrome). The overlay's own rules are tests/test_map_overlay.py's; the frames' source is tests/test_map_chains.py.

1. the top line: the session running on this map, when it started, the one sentence, when an edit takes effect; the
   tab's dot (its words stay "3 · Map");
2. each box's state, what it does, its cost, a row per fact, nothing cut; a stray agent in the strip, tagged;
3. a hand-off moves on the line its frame names (the label: the task, then its When again); a chain; reduced motion;
4. an opened workflow box: its steps lit, a step's agent, the repeat's rounds and checks;
5. a made-up helper beside main, dashed, tagged; Save as an agent opens the form with its body, nothing written;
6. the drawer: filtered by the clicked box, THINK / SAY / TALK rows, an ask's answers and its box waiting on you, the
   keyboard; Steer and Stop reach the session's command route;
8. another map shown: amber, Show the running map;  9. a session that did not start on a map;
10. History: the picker, Replay it on the map (quiet colours, a removed box), the scrubber, the report card;
the room at 1280 / 1500 / 1920 and a zoom step while frames arrive; 11. Session's Map panel lit, with its link.
Run: python -m tests.test_studio_map_live
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
    return driver_got(ctx, "tests.helpers.studio_map_live", why="the lit Map is driven in headless Chrome", cache=_RUN, timeout=900, env=slow)


@test
def test_the_top_line_and_the_tab_dot(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the top line, got {got.get('head')!r}", str(got.get("head")).startswith("A session is running on this map (started "))
    ctx.check(f"the one sentence: who works, the models, dollars, got {got.get('sentence')!r}",
              "agent" in str(got.get("sentence")) and "model" in str(got.get("sentence")) and "$" in str(got.get("sentence")))
    ctx.check(f"when an edit takes effect, got {got.get('when')!r}", "at the next hand-off" in str(got.get("when"))
              and "the next time that agent starts" in str(got.get("when")) and "with the next session" in str(got.get("when")))
    ctx.check(f"the tab's dot, its words unchanged, got {got.get('dot')}", got.get("dot") == ["1", "3 · Map"])


@test
def test_each_box_says_its_state_and_nothing_is_cut(ctx: Ctx):
    got = _got(ctx)
    s = got.get("states") or {}
    ctx.check(f"working / not used yet per box, got {s}", s.get("code") == "working" and s.get("check") == "working" and s.get("notes") == "idle"
              and s.get("main") == "working")
    ctx.check(f"a row per fact: state, what it does, its cost, got {got.get('check_rows')}",
              (got.get("check_rows") or [""])[0] == "working" and len(got.get("check_rows") or []) == 3 and "so far" in got["check_rows"][2])
    ctx.check(f"not used yet, got {got.get('notes_rows')}", got.get("notes_rows") == ["not used yet"])
    ctx.check(f"nothing cut, got {got.get('cut')}", got.get("cut") == 0)
    ctx.check(f"an agent no box claims: in the strip, tagged, got {got.get('stranger')}", got.get("stranger") == [["x0rph4n1", "not on this map"]])


@test
def test_a_hand_off_moves_along_the_line_it_named(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the label shows the task, got {got.get('pulse')!r}", got.get("pulse") == "apply the discount before tax")
    ctx.check(f"the line lit and a dot travels it, got {got.get('travel')}", got.get("travel") == [True, "1"])
    ctx.check(f"then its When again, got {got.get('back')!r}", got.get("back") == "always")
    ctx.check(f"a chain: the next line's label, got {got.get('chain')!r}", got.get("chain") == "check the basket diff")
    ctx.check("reduced motion: the line lit, no travel", got.get("reduced") is True)


@test
def test_an_opened_workflow_box_lights_its_steps(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"its steps, a step's agent, the repeat, got {got.get('steps')}",
              got.get("steps") == ["1 · Review: done (reviewer)", "2 · Test: running (tester) · repeat: round 2, 2 checks"])
    ctx.check(f"the click opened the drawer on it, got {got.get('open_drawer')!r}", got.get("open_drawer") == "check")


@test
def test_a_made_up_helper_and_save_as_an_agent(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"beside main, dashed, tagged, got {got.get('helper')}", got.get("helper") == ["made up for this task", "dashed", True])
    ctx.check(f"Save as an agent: the Agents form with its body, not saved, got {got.get('view')!r} {got.get('form')}",
              got.get("view") == "crew" and (got.get("form") or ["", False])[0] == "list-what-shop" and got["form"][1] is True)
    ctx.check(f"nothing written, got {got.get('written')}", got.get("written") == [])


@test
def test_the_drawer_steer_stop_and_an_ask(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"a click filters it to the box, got {got.get('filter')!r}", got.get("filter") == "code")
    ctx.check(f"THINK, SAY and TALK rows, got {got.get('kinds')}", {"think", "text", "talk"} <= set(got.get("kinds") or []))
    ctx.check(f"an ask: its box waits on you, its answers are buttons, got {got.get('waits')!r} {got.get('ask_keys')}",
              got.get("waits") == "waiting on you" and (got.get("ask_keys") or 0) >= 2)
    ctx.check(f"Enter on a box opens its words, got {got.get('keyboard')!r}", got.get("keyboard") == "research")
    ctx.check(f"Steer reaches the session, got {got.get('steer')}", got.get("steer") == ["agent_steer", 200])
    ctx.check(f"Stop (asked first) reaches it, got {got.get('stop')}", got.get("stop") == ["agent_stop", 200])


@test
def test_another_map_and_a_session_with_no_map(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"another map shown: amber, not lit, got {got.get('amber')} {got.get('unlit')}",
              (got.get("amber") or [False])[0] is True and got.get("unlit") == 0)
    ctx.check(f"Show the running map opens it, lit again, got {got.get('shown_running')!r}", got.get("shown_running") == "shop")
    ctx.check(f"no map: offered, then main and every agent as a made-up helper, no lines, got {got.get('boxes')} {got.get('labels')}",
              got.get("offer") is True and (got.get("boxes") or [0, []])[1] == ["main"] and got["boxes"][0] >= 4 and got.get("labels") == 0)
    ctx.check(f"the top line says it did not start on a map, got {got.get('nomap_head')!r}",
              str(got.get("nomap_head")).startswith("This session did not start on a map"))
    ctx.check(f"the map again, its lines, got {got.get('again')}", got.get("again") == 5)


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
        ctx.check(f"{w}: no sideways scroll, nothing under 12 px, controls >= 28 px, nothing cut, the drawer open, got {r}",
                  r == {"small": 0, "ctl": 0, "side": 0, "cut": 0, "feed": True})
    z = got.get("zoom") or ["", "x"]
    ctx.check(f"his zoom holds while a helper and a hand-off arrive, got {z}", z[0] and z[0] == z[1])


@test
def test_sessions_map_panel_is_the_lit_map(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"compact, read-only (no dot, no label card), its helper, got {got.get('panel')}", got.get("panel") == ["shop", True, 0])
    ctx.check(f"its link opens the Map tab on that map, got {got.get('to_tab')!r}", got.get("to_tab") == "shop")
    ctx.check(f"the driver ran every step, got {got.get('failed')!r}", not got.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
