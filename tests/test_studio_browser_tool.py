"""tests.test_studio_browser_tool -- 3.6.0.6 W batch 2 entry 2 (the owner: "We need a different solution that allows
agents in the harness to FULLY CONTROL A BROWSER AND SEE IT"), in headless Chrome through tests/helpers/
studio_browser_tool.py (skipped without one), over an in-process Studio whose launcher spawns a real
`halo --headless --session-for studio` child on the fake upstream (no model call):
1. a session started FROM STUDIO, with nothing set up for a browser, drives Halo's own browser: open a page this test
   serves on 127.0.0.1, click, screenshot; the reply names the page's text after the click;
2. Session's Live column has one row per Browser call in the tool's words ("Browser open <address>", "Browser click
   Press me", "Browser screenshot");
3. a click on the click step's row opens its detail on the page's picture: a PNG whose size is not zero, at the
   detail's width;
4. End session: no process carries the session's browser profile.
Run: python -m tests.test_studio_browser_tool
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
    return driver_got(ctx, "tests.helpers.studio_browser_tool", why="a Studio session's browser needs headless Chrome",
                      cache=_RUN, args=("browser",), timeout=400)


@test
def test_a_studio_session_drives_the_browser_with_nothing_set_up(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"a session from Studio, got {got.get('sid')!r}", len(str(got.get("sid") or "")) == 32)
    ctx.check(f"the reply names the page's text after the click, got {str(got.get('reply'))[-200:]!r}",
              "browser done:" in str(got.get("reply")) and "after the press" in str(got.get("reply")))
    ctx.check(f"its browser ran under Halo's own profile while the session lived, got {got.get('profile_pids_running')}",
              int(got.get("profile_pids_running") or 0) > 0)


@test
def test_live_shows_each_step_in_the_tools_words(ctx: Ctx):
    got = _got(ctx)
    rows = [r for r in got.get("rows") or [] if "Browser" in r]
    ctx.check(f"three Browser rows, got {rows}", len(rows) == 3)
    if len(rows) == 3:
        ctx.check(f"open <address>, got {rows[0]!r}", "Browser open http://127.0.0.1:" in rows[0])
        ctx.check(f"click <target>, got {rows[1]!r}", "Browser click Press me" in rows[1])
        ctx.check(f"screenshot, got {rows[2]!r}", "Browser screenshot" in rows[2])


@test
def test_a_steps_detail_shows_the_pages_picture(ctx: Ctx):
    got = _got(ctx)
    shot = got.get("shot") or []
    ctx.check(f"the picture: a PNG, its size not zero, got {shot}",
              len(shot) == 6 and shot[0] == "image/png" and shot[1] > 0 and shot[2] > 0 and shot[3] > 0)
    ctx.check(f"its bytes are a PNG, got {got.get('magic')}", got.get("magic") == [137, 80, 78, 71, 13, 10, 26, 10])
    if len(shot) == 6:
        ctx.check(f"it fits the detail's width and keeps its shape, got {shot[4]:.0f} of {shot[5]:.0f}",
                  0 < shot[4] <= shot[5])


@test
def test_end_session_leaves_no_browser(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the session ended, got {got.get('ended')}", got.get("ended") == "gone")
    ctx.check(f"no process carries its browser's profile, got {got.get('browser_left')}", got.get("browser_left") == [])
    ctx.check(f"no child survives, got {got.get('survivors')}", got.get("survivors") == [])
    ctx.check(f"no step failed, got {got.get('failed')}", not got.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
