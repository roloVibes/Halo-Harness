"""tests.test_studio_hold_still -- the Studio views a person clicks right after they open hold still while their data
lands (3.6.0.0 R5c), in headless Chrome through tests/helpers/studio_hold_still.py (skipped without Chrome); every /api/
answer is held, the controls measured at first paint, the answers let go one at a time (tests/helpers/hold_still.py):

1. Agents -> Map as it opens, and in the drivers' arrangement: the rail, the view bar, the Map bar (Run a goal, the
   switcher, My sessions use this, Lock) hold still; History's "Goal runs, files, Compare" is not drawn until the map
   above it and the past runs have landed (drawn at once it moved down and right under a click);
2. "Goal runs, files, Compare" clicked as soon as it shows: the History drawer's controls hold still;
3. Run a goal clicked before anything landed: the form is drawn whole once its help lines and the model catalog have
   landed, and then nothing in it moves (Review the plan first moved 41 px, then 34 px; Back was squeezed);
4. Session as it opens (its Start view: New session, Open the workspace anyway) and its workspace opened with every
   panel open: the rail and the section hold still.
Each failure names the control, how it moved and the answer that moved it.
Run: python -m tests.test_studio_hold_still
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
    return driver_got(ctx, "tests.helpers.studio_hold_still", why="the hold-still checks need headless Chrome", cache=_RUN, timeout=400)


def _view(ctx: Ctx, name: str, must: tuple = ()) -> None:
    v = _got(ctx).get(name) or {}
    ctx.check(f"{name}: the view was read, got {v.get('error') or sorted(v)}", "first" in v and not v.get("error"))
    measured = " ".join(v.get("first") or {})
    for testid in must:
        ctx.check(f"{name}: {testid} was on the page at first paint and measured", f'"{testid}"' in measured)
    ctx.check(f"{name}: nothing moved, went away or was covered while the answers landed, got {v.get('moved')}", v.get("moved") == [])


@test
def test_the_map_holds_still_as_it_opens(ctx: Ctx):
    _view(ctx, "map", ("map-run-goal", "map-switcher", "map-uses", "map-lock", "agents-view-map", "viewbar-btn"))
    _view(ctx, "map_all", ("map-run-goal", "map-switcher", "map-lock"))
    got = _got(ctx)
    ctx.check("History's Compare door is not drawn before what sits above it has landed",
              not any("map-history-all" in k for k in (got.get("map") or {}).get("first", {})))


@test
def test_the_history_drawer_holds_still(ctx: Ctx):
    _view(ctx, "history", ("map-feed-back", "live-history-close"))


@test
def test_the_goal_form_is_drawn_whole_and_holds_still(ctx: Ctx):
    _view(ctx, "goal", ("map-feed-back", "run-goal-close", "model-select", "orchestra-review", "orchestra-run"))


@test
def test_the_session_view_holds_still(ctx: Ctx):
    _view(ctx, "session", ("section-tab", "session-open-workspace"))
    _view(ctx, "session_all", ("viewbar-btn",))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
