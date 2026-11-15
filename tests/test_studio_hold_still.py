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
5. the other views (3.6.0.0 R5c, second pass): Agents' Agents tab with a form open, its Workflows tab, the model
   picker, Local, Setup, Settings;
6. a choice made early survives (hold_still.survives): made as soon as it can be, still in effect at the end.
7. the same over a FRESH home (3.6.0.0 R5e): nothing seeded, a provider set up, no catalog yet.
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


@test
def test_the_other_views_hold_still(ctx: Ctx):
    """3.6.0.0 R5c, the sweep's second pass: every MODEL field kept one line's room while the catalog is read (the
    agent's form moved 22 px, then 45 px, under it); the picker's not-here line sits under the last row; Setup draws
    Back and Next once it is read; the builder's model line has its own line."""
    _view(ctx, "crew", ("crew-save", "crew-effort", "crew-max-turns"))  # under the form's MODEL fields
    _view(ctx, "workflows", ("builder-input", "builder-send"))
    _view(ctx, "picker", ("model-search", "model-sort-best", "model-not-listed"))
    _view(ctx, "local", ("section-tab",))
    _view(ctx, "setup", ("section-tab",))
    _view(ctx, "settings", ("settings-search",))


@test
def test_a_choice_made_early_survives(ctx: Ctx):
    """Pressed, picked or typed as soon as it can be, and still in effect once every answer has landed, whichever order
    they land in: Best in the model picker while its catalog is read, the Library's search and source, Settings' search."""
    got = _got(ctx)
    for name in ("picker_best", "library_search", "library_source", "settings_search"):
        for order in ("oldest", "newest"):
            v = got.get(f"{name}/{order}") or {}
            ctx.check(f"{name} ({order} first): made, got {v}", v.get("made") is True and not v.get("error"))
            ctx.check(f"{name} ({order} first): still in effect at the end, lost after {v.get('lost')!r}", v.get("lost") == "")


_FRESH: dict = {}


def _fresh(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_hold_still", why="the hold-still checks need headless Chrome", cache=_FRESH, key="fresh",
                      args=("--fresh",), timeout=400)


@test
def test_a_fresh_home_holds_still(ctx: Ctx):
    """3.6.0.0 R5e: the views above over a FRESH home (nothing seeded, a provider set up, no catalog yet), the home a
    person starts with. Seeded, the checks above missed: every control under the agent's MODEL fields and Settings' Save
    moved 38-77 px when the empty catalog's line landed; Session's Setup gave way to Refresh once the providers' status
    was read; Local's traffic host moved."""
    got = _fresh(ctx)
    for name in ("session", "crew", "workflows", "map", "local", "setup", "settings"):
        v = got.get(name) or {}
        ctx.check(f"fresh {name}: the view was read, got {v.get('error') or sorted(v)}", "first" in v and not v.get("error"))
        ctx.check(f"fresh {name}: nothing moved, went away or was covered while the answers landed, got {v.get('moved')}", v.get("moved") == [])
    for name in ("settings_search", "library_search"):
        for order in ("oldest", "newest"):
            v = got.get(f"{name}/{order}") or {}
            ctx.check(f"fresh {name} ({order} first): made and still in effect, got {v}", v.get("made") is True and v.get("lost") == "" and not v.get("error"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
