"""tests.test_studio_roles_live_map -- Roles Live (Halo 3.3.11.0 R2; rolo 2026-11-02: "if the roles tab kept up with
what's happening during sessions for better map views that would be huge"), in headless Chrome through
tests/helpers/studio_roles_live_map.py (skipped without one), over the Studio fleet rig's real session plus three
agents an Auto-mode main spawned whose lineup is `auto` and whose roles no card of the open lineup has; no model call:

1. Alt+3 then L opens Live on this harness's session; the Plan canvas glowed none of the three;
2. every agent is a node (main, the rig's two, the three spawned), each spawned one with an edge from main and its
   pick's reason ("picked at spawn: <role> on <model> -- <why>"), none of them in a lineup group; the main card's
   faint (dashed) group sits behind main;
3. the first draw fits the wider-than-the-page tree; + zooms in, Fit brings it back;
4. a click selects the agent: the Inspector's Live tab shows it with its reason;
5. L goes back to Plan, `?mode=roles&view=live` opens on Live, and the Session Map thumbnail's "Open in Roles Live"
   lands on the same tree.
Run: python -m tests.test_studio_roles_live_map
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.helpers import fleet_pack as _fleet_pack  # noqa: E402  (the fleet pack on: these drive its Studio doors)
_fleet_pack.on()

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}
SPAWNED = ("w1r4n6l0", "t2r1a6e0", "s3c2r1b0")


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_roles_live_map", why="Roles Live needs headless Chrome", cache=_RUN,
                      args=("livemap",), timeout=420)


@test
def test_alt3_then_l_opens_live_on_the_session(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Live draws this harness's session, got {got.get('sid')!r} for {got.get('rig_sid')!r}",
              bool(got.get("sid")) and got.get("sid") == got.get("rig_sid"))
    glows = str(got.get("plan_glows") or "")
    ctx.check(f"the Plan canvas glows none of the spawned three, got {glows!r}",
              not any(n in glows for n in ("wrangler", "triage", "scribe")))


@test
def test_every_agent_is_a_node_with_its_edge_and_reason(ctx: Ctx):
    got = _got(ctx)
    nodes = got.get("nodes") or []
    ctx.check(f"all six agents are nodes, got {nodes}", len(nodes) == 6 and "main" in nodes and all(a in nodes for a in SPAWNED))
    ctx.check(f"each spawned one hangs under main, got {got.get('edges')}", all((got.get("edges") or {}).get(a) == ["main"] for a in SPAWNED))
    picks = got.get("picks") or {}
    ctx.check(f"each carries its pick's reason, got {picks}",
              all(str(picks.get(a, "")).startswith("picked at spawn: ") and " -- " in str(picks.get(a, "")) for a in SPAWNED))
    ctx.check(f"none of the three sits in a lineup group, got {got.get('spawned_cards')}", got.get("spawned_cards") == ["", "", ""])
    g = got.get("main_group") or {}
    ctx.check(f"the main card's faint group is behind main, got {got.get('main_card')!r} {g}",
              bool(got.get("main_card")) and g.get("behind") is True and g.get("first") is True and g.get("faint") == "dashed")


@test
def test_zoom_and_fit(ctx: Ctx):
    got = _got(ctx)
    z = got.get("zoom") or [0, 0, 0]
    ctx.check(f"the first draw fits the tree, got {got.get('first_fit')}", isinstance(got.get("first_fit"), (int, float)) and got["first_fit"] < 1)
    ctx.check(f"+ zooms in, Fit brings it back, got {z} fits={got.get('fits')}", z[1] > z[0] and z[2] < z[1] and got.get("fits") is True)


@test
def test_a_click_puts_the_agent_in_the_inspector(ctx: Ctx):
    got = _got(ctx)
    insp = got.get("inspector") or ["", "", ""]
    ctx.check(f"the Inspector's Live tab shows it, got {insp}", str(insp[0]).endswith("|t2r1a6e0") and insp[1] == got.get("want_name"))
    ctx.check(f"with its reason, got {insp[2]!r}", str(insp[2]).startswith("auto: or:mock/cheap-fast -- "))
    ctx.check(f"the node is selected, got {got.get('selected')!r}", got.get("selected") == "true")


@test
def test_plan_again_the_url_and_the_session_map_expand(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"L goes back to Plan, got {got.get('l_back')!r}", got.get("l_back") == "plan")
    ctx.check(f"?view=live opens on Live, got {got.get('by_url')!r}", got.get("by_url") == "live")
    ex = got.get("expanded") or ["", 0, ""]
    ctx.check(f"the Session Map thumbnail's expand lands on Roles Live, the same tree, got {ex} from {got.get('thumb_nodes')}",
              ex[0] == got.get("rig_sid") and ex[1] == got.get("thumb_nodes") == 6 and ex[2] == "true")
    ctx.check(f"no step failed, got {got.get('failed')}", not got.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
