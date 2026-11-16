"""tests.test_studio_session_links -- the links into the Session dashboard in a
real browser (Halo 3.1.4.0 R2; headless Chrome through the driver base,
tests/helpers/studio_session.py `links` -> studio_session_links.py; skipped
without one), over this harness's real session mid-work:

a live Orchestra run led by this harness's session: its pages (the Map's line, Open) have Watch in Session, which
opens Session with that session chosen. 3.6.0.0 R5: Live's Watch in Session, its node menu's Open in Session and Roles'
Live tab went with those views.
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
def test_orchestra_run_line_watches_its_session(ctx: Ctx):
    r, got = _driver("links")
    _ran(ctx, r, got)
    if (got.get("open_clicks") or 1) > 1 or got.get("settled") is False:  # said on a green run too (the driver's note)
        print(f"    (the Map's Open took {got.get('open_clicks')} click(s) before its drawer showed the run; "
              f"the Map had settled first: {got.get('settled')})")
    ctx.check(f"a live run's line has the button, got {got.get('watch_orchestra')!r}", got.get("watch_orchestra") == "Watch in Session")
    ctx.check(f"it opens Session with the run's session chosen, got {got.get('orchestra_tab')!r} {got.get('orchestra_session')}",
              str(got.get("orchestra_tab")).startswith("Session") and got.get("orchestra_session") == got.get("sid"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
