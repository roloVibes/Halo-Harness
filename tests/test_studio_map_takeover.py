"""tests.test_studio_map_takeover -- Halo 3.6.0.0 R4b "the lit Map takes over what the old Live view still does": the
gaps R4's hand-back listed, closed on the Map, in headless Chrome over the lit Map's rigs (tests/helpers/
studio_map_takeover.py: this harness's real session, extra agent rows, the map `shop`, Studio's command routes recorded).
Skipped without Chrome. No model is called.

1  the clicked box's facts (model and why, may use, tokens, cost, how long) and Pause / Resume / Dismiss
2  the seconds on what a box does now; the box the session waits on outlined; the sentence's wait opens it
3  agents talking: a dashed pulse box to box, its label, no line added; reduced motion: the boxes marked
4  a helper's own helpers: "+N under it", not drawn; the drawer lists who started whom
5  the todo plan: "plan: 1 of 3 done", its rows in the drawer
6  Run a goal from the Map's bar opens the goal form in the drawer
7  a replay's rows in the drawer, up to the scrubber's moment
9  J / K between working boxes; with nothing running, "Replay the last session"
10 a hover summary card, by a move only, never over the box's controls
11 an ask's answer pressed in the drawer reaches the session (a real waiter, its Attention row); two sessions: the picker
Run: python -m tests.test_studio_map_takeover
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
CLOCK = re.compile(r" · \d+ (s|min \d\d s)$")


def got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_map_takeover", why="the lit Map is driven in headless Chrome", cache=_RUN,
                      timeout=600, tail=800, what="the lit Map's R4b driver",
                      env={k: os.environ[k] for k in ("HALO_STUDIO_SLOW_MS",) if k in os.environ})  # the driver drops HALO_ unless passed on


@test
def test_1_the_clicked_box_facts_and_controls(ctx: Ctx):
    g = got(ctx)
    head = g.get("head") or []
    ctx.check(f"a row per fact: who, the model, why, may use, tokens, cost, how long, got {head}", len(head) == 7 and head[0].startswith("reviewer")
              and "runs on or:mock/kimi-k3-research" in head[1] and head[2].startswith("why this model: Auto") and head[3].startswith("may use:")
              and head[4] == "tokens: 1.2k in · 56 out" and head[5] == "cost: $0.0123" and head[6].startswith("running for 1 min"))
    ctx.check(f"Pause reaches the route Live's node menu calls, got {g.get('pause')}", g.get("pause", [None])[0] == "pause" and g["pause"][2] == 200)
    ctx.check(f"a paused agent offers Resume, got {g.get('resume_btn')!r}", g.get("resume_btn") == "Resume researcher")
    ctx.check(f"Resume reaches the route, got {g.get('resume')}", g.get("resume", [None])[0] == "resume" and g["resume"][2] == 200)
    ctx.check(f"a failed agent's Dismiss, then gone, got {g.get('dismissed')!r}", g.get("dismissed") == "gone")


@test
def test_2_clocks_and_the_wait(ctx: Ctx):
    g = got(ctx)
    ctx.check(f"a tool's seconds on its box, got {g.get('tool')!r}", bool(CLOCK.search(g.get("tool") or "")) and g["tool"].startswith("Bash pytest -q"))
    ctx.check(f"an ask's seconds, got {g.get('waiting')!r}", bool(CLOCK.search(g.get("waiting") or "")) and g["waiting"].startswith("waiting on you"))
    ctx.check(f"the box the session waits on is outlined, got {g.get('outlined')!r}", g.get("outlined") == "check")
    ctx.check(f"the sentence's wait is a link, got {g.get('link')!r}", (g.get("link") or "").startswith("waiting on you: reviewer"))
    ctx.check(f"the link opens that box in the drawer and focuses it, in view, got {g.get('opened')} {g.get('in_view')}", g.get("opened") == "check" and g.get("in_view") is True)


@test
def test_3_agents_talking(ctx: Ctx):
    g = got(ctx)
    p = g.get("pulse") or []
    ctx.check(f"a dashed pulse box to box with its first words, both boxes marked, got {p}",
              p[:2] == [True, "inline"] and (p[2] or "").startswith("Please look at the tax order") and p[3:] == ["true", "true"])
    ctx.check(f"no line added to the map, got {g.get('lines_before')} then {g.get('lines')}", g.get("lines") == g.get("lines_before") and g.get("lines"))
    ctx.check(f"it goes after a few seconds, got {g.get('gone')!r}", g.get("gone") == "gone")
    ctx.check(f"reduced motion: nothing travels, the boxes marked, got {g.get('reduced')}", g.get("reduced") == ["none", "true", "true"])


@test
def test_4_depth_and_5_the_plan(ctx: Ctx):
    g = got(ctx)
    ctx.check(f"a helper's helper: '+1 under it', not drawn, got {g.get('under')!r} drawn={g.get('drawn')}", g.get("under") == "+1 under it" and g.get("drawn") is False)
    ctx.check(f"the drawer lists who started whom, got {g.get('listed')!r}", "file-counter started by general-purpose" in (g.get("listed") or ""))
    ctx.check(f"a row filters the drawer to it, got {g.get('filtered')!r}", g.get("filtered") == "agent:n3st3d01")
    ctx.check(f"the top line's plan, got {g.get('plan_line')!r}", g.get("plan_line") == "plan: 1 of 3 done")
    rows = g.get("plan_rows") or []
    ctx.check(f"the plan's rows in the drawer, got {rows}", [r[0] for r in rows] == ["completed", "in_progress", "pending"]
              and "Fixing the discount order" in rows[1][1])


@test
def test_6_7_9_goal_replay_keys(ctx: Ctx):
    g = got(ctx)
    ctx.check(f"Run a goal from the Map's bar: the goal form in the drawer, and back, got {g.get('form')} {g.get('back')}", g.get("form") == "goal" and g.get("back") == "back")
    ctx.check(f"History under the map opens Live's whole History (goal runs, saved files, Compare) in the drawer, got {g.get('history')}",
              isinstance(g.get("history"), int) and g["history"] >= 1)
    ctx.check(f"J / K step between working boxes, got {g.get('focus')} of {g.get('working')}",
              len(g.get("focus") or []) == 3 and g["focus"][0] != g["focus"][1] and g["focus"][2] == g["focus"][0] and all(f in (g.get("working") or []) for f in g["focus"]))
    ctx.check(f"nothing running: Replay the last session, got {g.get('offer')!r} -> {g.get('replaying')!r}", g.get("offer") == "Replay the last session" and g.get("replaying") == "replay")
    ctx.check(f"a replay's rows in the drawer up to the scrubber, got {g.get('rows')}", g.get("drawer") == "rows" and len(g.get("rows") or []) >= 1)


@test
def test_10_hover_and_11_checked(ctx: Ctx):
    g = got(ctx)
    ctx.check(f"no card opens by itself, got {g.get('by_itself')}", g.get("by_itself") is False)
    card = g.get("card") or ["", []]
    ctx.check(f"a summary card: what it is, now, model, cost, got {card}", "researcher" in card[0] and card[1] == ["now", "model", "cost"])
    ctx.check(f"it covers none of the box's controls, got {g.get('covers')}", g.get("covers") == 0)
    ctx.check(f"the ask's Attention row is read, got {g.get('row')!r}", "Attention row" in (g.get("row") or ""))
    s = g.get("sent") or []
    ctx.check(f"the answer pressed in the drawer reaches the session and resolves its waiter, got {s}",
              s[:4] == ["answer", "perm-r4b", "allow", 200] and "'resolved': True" in (s[4] if len(s) > 4 else ""))
    ctx.check(f"two sessions: the picker lists both and switches which is lit, got {g.get('options')} {g.get('second')} {g.get('first_is_rig')}",
              len(g.get("options") or []) == 2 and g.get("second") == "5eed0000two000000000000000000002" and g.get("first_is_rig") is True)
    ctx.check(f"the driver ran every step, got failed={g.get('failed')!r}", not g.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
