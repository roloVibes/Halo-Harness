"""tests.test_studio_live_think -- Session's Live column, 3.3.16.2 "thinking you can see" (the owner: "make watching a
model think much better"), in headless Chrome (tests/helpers/studio_session_think.py `think`; skipped without one):

1. a thought's `thinking_chunk` frames grow ONE THINK row (KIND THINK) with a caret while it grows;
2. it clamps at four lines with "show all", which grows the row; when it ends, the caret goes and a mono suffix says
   how long it thought and its tokens ("thought 4.2 s · 812 tokens");
3. its chip says what it led to ("then ran Edit basket.py"); `why?` on that Edit row opens that thought under it;
4. Thinking (beside Follow) narrows the feed to the thoughts and their acts (the researcher's untought rows go);
5. the implementer's timeline lane is drawn in phases (thinking, a tool, idle); hovering a thinking segment says its
   length; its click scrolls the column back to that THINK row;
6. no THINK row's text is pushed out of its box.
Run: python -m tests.test_studio_live_think
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
_RUNS: dict = {}


def _driver(*argv: str) -> "tuple[subprocess.CompletedProcess, dict]":
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Live column needs headless Chrome)")
    if argv not in _RUNS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_session_think", *argv], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUNS[argv] = (r, info)
    r, info = _RUNS[argv]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    return r, info


def _ran(ctx: Ctx, r, got) -> None:
    ctx.check(f"the driver ran, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in got)


@test
def test_a_thought_streams_as_one_think_row_and_clamps(ctx: Ctx):
    r, got = _driver("think")
    _ran(ctx, r, got)
    ctx.check(f"its KIND is THINK, got {got.get('kind_label')!r}", got.get("kind_label") == "THINK")
    ctx.check("a caret while it grows", got.get("streaming") is True)
    ctx.check(f"eight chunks are ONE row, got {got.get('one_row')}", got.get("one_row") == 1)
    ctx.check(f"clamped at four lines, got {got.get('clamped')}", got.get("clamped") == [True, 4])
    ctx.check(f"show all on the row, got {got.get('show_all')!r}", got.get("show_all") == "show all")
    ctx.check(f"show all shows it whole and the row grows, got {got.get('expanded')}", got.get("expanded") == [True, True])


@test
def test_the_end_says_how_long_and_the_chip_what_it_led_to(ctx: Ctx):
    r, got = _driver("think")
    _ran(ctx, r, got)
    ctx.check(f"how long and its tokens, got {got.get('took')!r}", got.get("took") == "thought 4.2 s · 812 tokens")
    ctx.check("no caret once it ended", got.get("caret_after") is False)
    ctx.check(f"what it led to, got {got.get('led')!r}", str(got.get("led") or "").startswith("then ran Edit basket.py"))


@test
def test_why_on_the_action_row_opens_the_thought_before_it(ctx: Ctx):
    r, got = _driver("think")
    _ran(ctx, r, got)
    ctx.check("the Edit row's why? is linked to the thought", got.get("why_linked") is True)
    said = str(got.get("why_opens") or "")
    ctx.check(f"it opens that thought under the row, got {said[:120]!r}", said.startswith("THE THOUGHT BEFORE IT") and "off by a cent" in said)


@test
def test_the_thinking_view_reads_one_mind_as_a_column(ctx: Ctx):
    r, got = _driver("think")
    _ran(ctx, r, got)
    ctx.check(f"off by default, got {got.get('view_off')!r}", got.get("view_off") == "false")
    rows = got.get("view_rows") or []
    ctx.check(f"thought, what it did, thought, what it did, got {rows}", rows == [["think", "impl"], ["tool", "impl"], ["think", "impl"], ["tool", "impl"]])
    ctx.check("the feed is narrower than every row", got.get("view_fewer") is True)


@test
def test_the_timeline_lane_shows_the_mix_and_a_thought_is_a_click_away(ctx: Ctx):
    r, got = _driver("think")
    _ran(ctx, r, got)
    ctx.check(f"phases on the lane, got {got.get('phases')}", {"thinking", "tool", "idle"} <= set(got.get("phases") or []))
    ctx.check(f"the hover names the phase and its length, got {got.get('tip')!r}", "thinking" in str(got.get("tip")) and " from " in str(got.get("tip")))
    ctx.check("the thought was out of view before the click", got.get("away") is True)
    ctx.check(f"the click hit the thinking segment, got {got.get('hit')!r}", got.get("hit") == "thinking")
    ctx.check("the click holds Follow and scrolls the column to the THINK row", got.get("paused") == "paused" and got.get("scrolled_to") is True)
    ctx.check(f"no THINK row overflows, got {got.get('overflow')}", got.get("overflow") == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
