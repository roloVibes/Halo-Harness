"""tests.test_studio_session_links -- the links into the Session dashboard in a
real browser (Halo 3.1.4.0 R2; headless Chrome through the driver base,
tests/helpers/studio_session.py `links` -> studio_session_links.py; skipped
without one), over this harness's real session mid-work and a member harness:

1. the Fleet rail: a click on this harness's agent opens Session with that
   agent selected; a member's agent opens Fleet as before;
2. the map node's `...` menu: Open in Session on this harness's nodes (it
   opens Session on that agent), not on a member's;
3. the Roles canvas: a working card's Live tab header has Watch in Session,
   which opens Session on that agent;
4. a live Orchestra run led by this harness's session: its run line has Watch
   in Session, which opens Session with that session chosen.
Run: python -m tests.test_studio_session_links
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_studio_session import _driver, _ran  # noqa: E402  (one driver runner, its cache per module)

test, TESTS = new_registry()


@test
def test_the_rail_opens_this_harness_in_session_and_a_member_in_fleet(ctx: Ctx):
    r, got = _driver("links")
    _ran(ctx, r, got)
    ctx.check(f"this harness's agent: Session on it, got {got.get('rail_local_tab')!r} {got.get('rail_local_agent')}",
              str(got.get("rail_local_tab")).startswith("Session") and got.get("rail_local_agent") == "implementer")
    ctx.check(f"a member's agent: Fleet as before, got {got.get('rail_member_tab')!r} {got.get('rail_member_agent')}",
              str(got.get("rail_member_tab")).startswith("Fleet") and got.get("rail_member_agent") == "member")


@test
def test_the_map_menu_opens_in_session_on_this_harness_only(ctx: Ctx):
    r, got = _driver("links")
    _ran(ctx, r, got)
    ctx.check(f"this harness's node has Open in Session, got {got.get('menu_local')}", "session" in (got.get("menu_local") or []))
    ctx.check(f"it opens Session on that agent, got {got.get('menu_tab')!r} {got.get('menu_agent')}",
              str(got.get("menu_tab")).startswith("Session") and got.get("menu_agent") == "researcher")
    ctx.check(f"a member's node has no such entry, got {got.get('menu_member')}",
              got.get("menu_member") and "session" not in got.get("menu_member"))


@test
def test_roles_live_tab_watches_in_session(ctx: Ctx):
    r, got = _driver("links")
    _ran(ctx, r, got)
    ctx.check(f"the working card's Live tab has the button, got {got.get('watch_roles')!r}", got.get("watch_roles") == "Watch in Session")
    ctx.check(f"it opens Session on that agent, got {got.get('roles_tab')!r} {got.get('roles_agent')}",
              str(got.get("roles_tab")).startswith("Session") and got.get("roles_agent") == "implementer")


@test
def test_orchestra_run_line_watches_its_session(ctx: Ctx):
    r, got = _driver("links")
    _ran(ctx, r, got)
    ctx.check(f"a live run's line has the button, got {got.get('watch_orchestra')!r}", got.get("watch_orchestra") == "Watch in Session")
    ctx.check(f"it opens Session with the run's session chosen, got {got.get('orchestra_tab')!r} {got.get('orchestra_session')} {got.get('orchestra_agent')}",
              str(got.get("orchestra_tab")).startswith("Session") and got.get("orchestra_session") == got.get("sid") and got.get("orchestra_agent") is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
