"""tests.test_studio_doors -- Halo 3.6.0.2 P4 batch 9, "a door never leads nowhere", in headless Chrome as a person uses
it (driver tests/helpers/studio_doors.py over the session rig and the live rig; skipped without Chrome; the Linux VM and
CI only). The pure half (the kept ask, where the asking agent is drawn, the requests' time limit) is
tests/test_studio_door_kept.py and tests/test_api_limit.py, run in node everywhere.

1. the owner's own case (2026-11-17, "attention open in map doesn't do anything"): a COLD page on Agents -> 3 · Map, the
   helper agent asks; the Attention row's O pressed ONCE lands within 5 s on Agents -> 4 · Live for that session, the
   asking agent's box selected and waiting, its card open with the ask's choices (the queue's panel closed: the card
   carries the ask); from Session's Attention drawer the same O lands on Session's Live drawer the same way;
2. a goal run's Open on the Map's top line is one DOM node before and after the Map settles, and opens the Map's drawer
   on the run at once while the run's file read never answers (Studio's requests have a time limit: lib/apiLimit.ts);
3. the builder box shows what Apply LEFT OUT, each line in the server's words, under its result.
Run: python -m tests.test_studio_doors
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_doors", why="Studio's doors are driven in headless Chrome", cache=_RUN, timeout=480)


@test
def test_attention_open_on_the_map_lands_on_the_asking_box(ctx: Ctx):
    d = _got(ctx)
    ctx.check(f"the row offers O, got {d.get('ask_map_keys')}", "o" in (d.get("ask_map_keys") or []))
    got = d.get("ask_map")
    ctx.check(f"from a cold 3 · Map, one O: 4 · Live, the box selected and waiting, its card open with the ask's choices, got {got!r}",
              isinstance(got, list) and got[1] >= 1 and got[2] == "reviewer")
    ctx.check(f"the box carries the waiting mark, got {d.get('ask_map_state')!r}", d.get("ask_map_state") == "waiting")
    ctx.check(f"the queue's panel closed over the card, got {d.get('ask_map_attention_closed')!r}", d.get("ask_map_attention_closed") is True)


@test
def test_attention_open_in_session_lands_on_the_live_drawer(ctx: Ctx):
    d = _got(ctx)
    got = d.get("ask_session")
    ctx.check(f"Session's Attention O: the Live drawer, the box selected and waiting, its card with the ask, got {got!r}",
              isinstance(got, list) and got[1] >= 1 and got[2] == "reviewer")
    ctx.check(f"the box carries the waiting mark, got {d.get('ask_session_state')!r}", d.get("ask_session_state") == "waiting")
    ctx.check(f"Session's Live drawer is open, got {d.get('ask_session_live_btn')!r}", d.get("ask_session_live_btn") == "true")


@test
def test_an_ask_from_an_agent_on_no_box_opens_the_feed_and_says_so(ctx: Ctx):
    """P4 batch 12 (the owner's point 24, the coordinator's ruling): a door never leads nowhere -- an agent the drawing puts
    on no box asks; its O opens the Feed on that agent with the ask's choices in view, and one line says so."""
    d = _got(ctx)
    line = d.get("stranger_line") or ""
    for where in ("agents", "session"):
        got = d.get(f"stranger_{where}") or ["", ""]
        ctx.check(f"from {where}: the Feed shows the ask's choices and the line {line!r}, got {got!r}",
                  got[0] == "feed" and line in (got[1] or ""))
    ctx.check(f"Agents: it stays on 4 · Live, got {d.get('stranger_agents_view')!r}", d.get("stranger_agents_view") == "live")
    ctx.check(f"Session: nothing else closes (the Attention drawer is open), got {d.get('stranger_session_attention')!r}",
              d.get("stranger_session_attention") is True)


@test
def test_a_goal_runs_open_holds_still_and_opens_at_once(ctx: Ctx):
    d = _got(ctx)
    ctx.check(f"Open is the same node before and after the Map settled, got {d.get('run_same_node')!r}", d.get("run_same_node") is True)
    ctx.check(f"one press opens the drawer on the run while its file read never answers, got {d.get('run_open')!r} "
              f"in {d.get('run_open_s')} s", d.get("run_open") == d.get("run_id"))


@test
def test_the_builder_box_says_what_apply_left_out(ctx: Ctx):
    d = _got(ctx)
    ctx.check(f"the left line under the result, in the server's words, got {d.get('builder_left')!r} (sent {d.get('left_sent')!r})",
              d.get("builder_left") == [d.get("left_sent")])
    ctx.check(f"the result's own line does not say new sessions switched, got {d.get('builder_result')!r}",
              "new sessions" not in str(d.get("builder_result")).lower())
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
