"""tests.test_studio_live_plan -- Agents -> Live, parts 2-4 of Halo 3.3.18.0 "The living canvas" (the owner: "what does it
need to make this a break through orchestration visualization?"), in headless Chrome through
tests/helpers/studio_live_plan.py (skipped without one), over the fleet rig's real session under halo-dev-cycle with two
tiers and one square, a square's agent and its helper, and a scribe no card matches; no model call:

1. the plan under it, on by default: main's block, the two tiers by their purpose, the square, the unused tier dim, "not
   in the plan" with why; each agent inside its block; main's lines with their when, the dash only into blocks at work;
   nothing overlaps, no bar spills; the toggle draws the tree and the blocks again;
2. what each agent waits on (an agent, a model reply, a tool, nothing, you); the waiting path and the one sentence for a
   tool wait and for an ask (the ask first); the sentence steady while the tool's seconds tick; a click centres the agent;
3. a task labels its line, then the line goes back to its when; the line's hover card; a click opens Conversations;
4. far / mid / near by the switch (far: blocks only; near: the thought); the wheel keeps the thing under the pointer;
   Fit with thirty more agents lands on far, every block readable, inside the view, nothing overlapping.
Run: python -m tests.test_studio_live_plan
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
    return driver_got(ctx, "tests.helpers.studio_live_plan", why="Live's plan needs headless Chrome", cache=_RUN, args=("plan",), timeout=480)


def _block(got: dict, bid: str) -> dict:
    return next((b for b in got.get("blocks") or [] if b.get("id") == bid), {})


@test
def test_the_plan_under_it_draws_each_agent_in_its_block(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"on by default, got {got.get('plan_on')!r}", got.get("plan_on") == "true")
    want = {"main": ["main"], "square:media": ["sqm1", "sqh1"], "none": ["scr1"]}
    for bid, ids in want.items():
        b = _block(got, bid)
        ctx.check(f"{bid} holds {ids}, got {b.get('inside')}", sorted(b.get("inside") or []) == sorted(ids))
    for bid, title in (("tier:build", "the builders"), ("tier:read", "the readers")):
        b = _block(got, bid)
        ctx.check(f"{bid}: titled by its purpose, one agent at work, got {b.get('title')!r} {b.get('counts')!r}",
                  b.get("title") == title and str(b.get("counts", "")).startswith("1 agent · 1 working") and len(b.get("inside") or []) == 1)
    rest = _block(got, "tier:rest")
    ctx.check(f"an unused block is dim, its name and purpose readable, got {rest}", rest.get("used") is False and rest.get("title") == "tier rest"
              and rest.get("purpose") == "review, release, watchdog" and rest.get("color") != _block(got, "main").get("color"))
    none = _block(got, "none")
    ctx.check(f"not in the plan, with why, got {none.get('title')!r} {none.get('purpose')!r}", none.get("title") == "not in the plan"
              and none.get("purpose") == "no card of halo-dev-cycle matches its role (scribe) or its bio (scribe)")


@test
def test_mains_lines_their_when_and_the_one_motion(ctx: Ctx):
    got = _got(ctx)
    lines = dict((a, b) for a, b in got.get("lines") or [])
    ctx.check(f"a line into each tier and the square, the dash only where agents work, got {lines}",
              lines == {"tier:build": True, "tier:read": True, "tier:rest": False, "square:media": True} and got.get("flows") == 3)
    whens = dict((a, b) for a, b in got.get("whens") or [])
    ctx.check(f"each line's when, got {whens}", whens.get("tier:read") == "says research" and str(whens.get("square:media", "")).startswith("needs pdf"))
    bad = [b.get("id") for b in got.get("blocks") or [] if b.get("spill") or b.get("cut")]
    ctx.check(f"nothing overlaps, no bar spills, got {got.get('overlap')} {bad}", got.get("overlap") == [] and not bad)
    hs = got.get("bar_heights") or []
    ctx.check(f"the density rule: each block's bar and the one sentence >= 36 px, got {hs}", len(hs) == 7 and min(hs) >= 36)
    ctx.check(f"the toggle: the tree, then the blocks again, got {got.get('off')} {got.get('on_again')}",
              isinstance(got.get("off"), int) and got.get("off") >= 3 and got.get("on_again") == 6)


@test
def test_what_each_agent_waits_on(ctx: Ctx):
    got = _got(ctx)
    for k, want in (("main_waits", "WAITSan agent"), ("model_waits", "WAITSa model reply"), ("tool_waits", "WAITSa tool · Bash pytest -q"),
                    ("nothing_waits", "WAITSnothing · working: writing"), ("you_waits", "WAITSyou · listener asks to run: git push origin feature/basket")):
        ctx.check(f"{k}, got {got.get(k)!r}", str(got.get(k, "")).startswith(want))


@test
def test_the_waiting_path_and_the_one_sentence(ctx: Ctx):
    got = _got(ctx)
    t = str(got.get("tool_sentence", ""))
    ctx.check(f"a tool wait: the agents by block, then what it waits on, the models, the spend, got {t!r}",
              "in square media" in t and "waiting on: scribe -> Bash pytest -q · on 4 models · $" in t and len(t) <= 140)
    ctx.check(f"the path main -> scribe, got {got.get('path')}", got.get("path") == ["main", "scr1"])
    ctx.check(f"steady while the seconds tick, got {got.get('secs_a')!r} -> {got.get('secs_b')!r}",
              got.get("tool_sentence_later") == t and got.get("secs_a") != got.get("secs_b"))
    a = str(got.get("ask_sentence", ""))
    ctx.check(f"an ask comes first, got {a!r}", a.startswith("waiting on you: listener asks to run: git push") and len(a) <= 140)
    ctx.check(f"its path and leaf, got {got.get('ask_path')} {got.get('ask_leaf')!r}", got.get("ask_path") == ["main", "sqh1", "sqm1"] and got.get("ask_leaf") == "sqh1")
    ctx.check(f"a click centres it, got {got.get('seen_before')} -> {got.get('centred')!r}", got.get("seen_before") is False and got.get("centred") == "in view")


@test
def test_a_hand_off_labels_its_line_then_fades(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the task on the line, got {got.get('handoff')!r}", str(got.get("handoff", "")).startswith("task: Check what the pricing notes"))
    s = got.get("handoff_s")
    ctx.check(f"back to the when after its moments, got {got.get('back_to_when')!r} after {s} s",
              got.get("back_to_when") == "says research" and isinstance(s, (int, float)) and 7 <= s <= 16)
    ctx.check(f"the line's hover card, got {got.get('hover_rows')} rows", got.get("hover_rows") == 1)
    ctx.check(f"a click opens Conversations on the pair, got {got.get('conv')!r}", str(got.get("conv", "")).startswith("main ↔ researcher"))


@test
def test_three_levels_the_anchor_and_fit_with_thirty(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"far: blocks only, got {got.get('far')}", (got.get("far") or [0])[0] < 0.6 and got["far"][1] == 0 and got["far"][2] == 6)
    ctx.check(f"near: every agent's thought row, got {got.get('near')} {got.get('thought')!r}", (got.get("near") or [0])[0] >= 1.3
              and got["near"][1] == got["near"][3] == 6 and "Weighing whether the discount" in str(got.get("thought")))
    ctx.check(f"mid: the boxes, got {got.get('mid')}", got.get("mid") == [1, 6, 6, 0])
    ctx.check(f"the wheel moves the level, the thing under the pointer stays, got {got.get('wheel_level')!r} {got.get('anchor_before')!r} {got.get('anchor_after')!r}",
              got.get("wheel_level") == "near" and got.get("anchor_before") and got.get("anchor_before") == got.get("anchor_after"))
    fit, sizes = got.get("fit") or [9, 9], got.get("readable") or []
    ctx.check(f"Fit with thirty more lands on far, got {fit}", fit[0] < 0.6 and fit[1] == 0)
    ctx.check(f"every block readable (11 px or more on screen), inside the view, nothing overlapping, got {sizes} {got.get('inside')} {got.get('far_overlap')}",
              sizes and min(sizes) >= 11 and got.get("inside") is True and got.get("far_overlap") == [] and got.get("none_block") == "31")
    ctx.check(f"no step failed, got {got.get('failed')}", not got.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
