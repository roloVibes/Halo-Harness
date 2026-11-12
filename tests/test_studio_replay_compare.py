"""tests.test_studio_replay_compare -- History's Compare in headless Chrome (Halo 3.4.1.0 R2 "Time"), through
tests/helpers/studio_replay_compare.py (skipped without Chrome); no model call:

1. nothing opens by itself: no tick, no Compare bar, no page;
2. tick a session and a goal run -> Compare: the drawer wide, two columns of lanes over one axis, the rows with the
   better figure named by a word in its own cell (cost: "cheaper" on A; wall time: "faster" on B), three "what
   differed" lines; Back keeps the ticks;
3. a third tick lets the oldest go; one ticked -> "Compare before / after", split at its steer (+30 s), then at 0:20;
4. a goal run's replay saves as one file (what it holds said first) and Export a clip is on for it.
Run: python -m tests.test_studio_replay_compare
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
    return driver_got(ctx, "tests.helpers.studio_replay_compare", why="Compare needs headless Chrome", cache=_RUN, timeout=300)


@test
def test_nothing_opens_by_itself(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"no tick, no Compare bar, no page on load: {got.get('quiet')}", got.get("quiet") is True)
    ctx.check(f"one tick offers before / after: {got.get('one')!r}", got.get("one") == "Compare before / after")


@test
def test_compare_marks_the_better_figure_with_a_word(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the page compares the two ticked, the drawer wide: {got.get('refs')} {got.get('wide')}",
              got.get("wide") is True and str((got.get("refs") or [""])[0]).startswith("session:") and str((got.get("refs") or ["", ""])[1]).startswith("run:"))
    rows = {r["key"]: r for r in got.get("rows") or []}
    ctx.check(f"nine rows, got {list(rows)}", len(rows) == 9)
    cost, wall = rows.get("cost") or {}, rows.get("wall") or {}
    ctx.check(f"cost: the word 'cheaper' in A's cell, got {cost}", cost.get("word") == "cheaper" and cost.get("side") == "a" and cost.get("a") == "$0.0300")
    ctx.check(f"wall time: 'faster' in B's cell, got {wall}", wall.get("word") == "faster" and wall.get("side") == "b")
    ctx.check(f"failures the same, no word in a cell, got {rows.get('failures')}", (rows.get("failures") or {}).get("better") == "same" and not rows["failures"]["word"])
    ctx.check(f"tokens unknown on both: not marked, got {rows.get('tokens')}", not (rows.get("tokens") or {}).get("side"))
    lines = got.get("differed") or []
    ctx.check(f"three plain lines, got {lines}", len(lines) == 3 and any("cost 40 % less" in x for x in lines))
    lanes = got.get("lanes") or []
    ctx.check(f"each run's agents as lanes over one axis, got {lanes}",
              {"A:main", "A:scout1", "A:fixer1", "B:lead", "B:lane-1", "B:lane-2"} == set(lanes) and (got.get("segs") or 0) > 4)
    ctx.check(f"Back keeps the ticks, got {got.get('back')}", got.get("back") == 2)


@test
def test_one_run_before_and_after_its_steer(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"a third tick lets the oldest go, got {got.get('third')}", got.get("third") is True)
    ctx.check(f"split at the steer, got {got.get('split')} {got.get('titles')}",
              got.get("split") == "30" and "before 30 s" in str(got.get("titles")) and "from 30 s on" in str(got.get("titles")))
    rows = {r["key"]: r for r in got.get("self_rows") or []}
    ctx.check(f"a shorter stretch is not faster; the unpriced part is not compared, got {rows.get('wall')} {rows.get('cost')}",
              not (rows.get("wall") or {}).get("word") and not (rows.get("cost") or {}).get("side") and (rows.get("cost") or {}).get("a") == "$0.0120+")
    ctx.check(f"split at 0:20 when asked, got {got.get('moved')}", got.get("moved") == "20")


@test
def test_a_goal_run_saves_and_clips(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the goal run on the scrubber, Export a clip on, got {got.get('kind')} {got.get('clip_on')}", got.get("kind") == "run" and got.get("clip_on") is True)
    holds = got.get("holds") or []
    ctx.check(f"Save says what a goal run's file holds, got {holds}", len(holds) == 5 and any("goal run's record" in h for h in holds))
    says = got.get("says") or []
    ctx.check(f"DOES / COSTS / WRITES before it writes, got {says}", len(says) == 3 and says[1] == "nothing: no model call" and ".halo-replay" in says[2])
    ctx.check(f"it wrote one file, got {got.get('wrote')!r}", str(got.get("wrote")).endswith(".halo-replay"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio replay compare"))
