"""tests.test_studio_advise -- Halo 3.3.7.0 R4, Local -> Models' Adviser and the guards' lines in headless Chrome
through tests/helpers/studio_advise.py (skipped without one), over R1's seeded home with a lineup whose coder and verify
are one family, two more models on box and an unexplained model in box's /api/ps; no provider request, no model call:

1. the Adviser lists its suggestions by kind (mismatch, overlap, freshness), each with one button and its CLI line;
2. the mismatch's Point button writes roles.verify and nothing else, and says so;
3. the box card's foreign line and refresh line; the traffic view's foreign line; Steward's refresh block.
Run: python -m tests.test_studio_advise
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.driver_got import got as driver_got  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    info = driver_got(ctx, "tests.helpers.studio_advise", why="the Adviser checks need headless Chrome", cache=_RUN,
                      timeout=480)
    return info


@test
def test_the_adviser_lists_its_kinds(ctx: Ctx):
    got = _got(ctx)
    kinds = {k for k, _v in got.get("rows") or []}
    ctx.check(f"mismatch, overlap and freshness rows, got {got.get('rows')}", {"mismatch", "overlap", "freshness"} <= kinds)
    ctx.check(f"the head line, got {got.get('head')!r}", str(got.get("head")).startswith("roster: "))
    ctx.check(f"each row has its CLI line, got {got.get('clis')}", len(got.get("clis") or []) == len(got.get("rows") or [])
              and any(x.startswith("halo roles point verify ") for x in got["clis"]))


@test
def test_point_writes_the_role_only(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the button names it, got {got.get('point_label')!r}", got.get("point_label") == "Point verify at gemma3:12b@box")
    ctx.check(f"roles.verify written and nothing else, got {got.get('written')}", got.get("written") == {"verify": "ol:gemma3:12b@box"})
    ctx.check(f"it says so, got {got.get('said')!r}", "roles.verify:" in str(got.get("said")) and "nothing pulled" in str(got.get("said")))


@test
def test_the_guards_lines(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"box's foreign line, got {got.get('foreign')!r}", str(got.get("foreign")).startswith("foreign: 1 model, 4.7 GB, since "))
    ctx.check(f"box's refresh line, got {got.get('refresh')!r}", str(got.get("refresh")).startswith("refresh: "))
    ctx.check(f"the traffic view's foreign line, got {got.get('traffic_foreign')!r}",
              str(got.get("traffic_foreign")).startswith("box: foreign: 1 model"))
    ctx.check(f"Steward's refresh block, got {got.get('steward')!r}", bool(got.get("steward")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
