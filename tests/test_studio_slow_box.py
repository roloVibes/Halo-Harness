"""tests.test_studio_slow_box -- the Studio on a slow box (Halo 3.3.0.0 R7).
Two Studio behaviours differed on GitHub's runners from every box here, both
timing; `HALO_STUDIO_SLOW_MS` (studio/server.py: every API answer and every
live-feed frame that many ms late; docs/DEVELOPMENT.md "A slow box") shows
the runner's order of events on any box, and these run the same steps with
it set (headless Chrome; skipped without one):

1. the Roles canvas makes room (tests/helpers/studio_roles_room.py, the steps
   of tests/test_studio_roles_tiers.py) with every answer 800 ms late: at
   800 ms the base of this round showed the Windows runner's numbers to the
   pixel (run 40285708108: the held card at [870, 419, 109, 54] against the
   leads box [701, 204, 126, 207]) and the spots after a removal moved; a
   cross-tier drop is one ordered write now, so the held card sits in its box
   and every card keeps its spot;
2. the Fleet map with every answer and frame 400 ms late
   (tests/helpers/studio_slow_fleet.py): a stopped agent whose end frame and
   every re-reading frame are lost while the feed stays alive ends on the map
   within the poll floor (fleet/sync.ts FLOOR_MS) + 1 s, and a late `running`
   frame after its end is corrected as fast (the base kept both `running`
   for the whole 30 s wait: the Linux runner's 60 s).
Run: python -m tests.test_studio_slow_box
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
ROOM_MS = 800  # the reproduction's latency: the runner's failure showed here at 800, not at 400
FLEET_MS = 400
_RUN: dict = {}


def _floor_s() -> float:
    src = (REPO / "halo_harness" / "studio" / "ui" / "src" / "routes" / "fleet" / "sync.ts").read_text(encoding="utf-8")
    m = re.search(r"export const FLOOR_MS = (\d+);", src)
    return int(m.group(1)) / 1000 if m else 0.0


def _got(ctx: Ctx, helper: str, args: list, slow_ms: int) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the slow-box checks need headless Chrome)")
    if helper not in _RUN:
        env = driver_env(REPO)
        env["HALO_STUDIO_SLOW_MS"] = str(slow_ms)  # driver_env scrubs HALO_*: the one flag these runs need, put back
        r = subprocess.run([sys.executable, "-m", helper, *args], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=600, env=env, cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN[helper] = (r, info)
    r, info = _RUN[helper]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in info)
    return info


def _room(ctx: Ctx) -> dict:
    return _got(ctx, "tests.helpers.studio_roles_room", ["room"], ROOM_MS)


def _fleet(ctx: Ctx) -> dict:
    return _got(ctx, "tests.helpers.studio_slow_fleet", [], FLEET_MS)


@test
def test_a_cross_tier_drop_lands_in_its_box_on_a_slow_box(ctx: Ctx):
    got = _room(ctx)
    ctx.check(f"the tier move is saved, the card inside its new box, nothing overlapping, got {got.get('moved_tiers')} {got.get('other_in_leads')!r}",
              (got.get("moved_tiers") or {}).get("leads") == ["worker", "research", "release"] and got.get("other_in_leads") == "in"
              and got.get("other_overlaps") == [])


@test
def test_the_held_drop_joins_the_tier_inside_its_box_on_a_slow_box(ctx: Ctx):
    got = _room(ctx)
    ctx.check("held over the collapsed strip, the tier opens", got.get("held_opened") is True)
    ctx.check(f"the drop joins it, drawn, nothing overlapping, got {got.get('held_joined')} {got.get('held_overlaps')}",
              "watchdog" in (got.get("held_joined") or {}).get("leads", []) and got.get("held_shown") is True and got.get("held_overlaps") == [])
    ctx.check(f"and the joined card sits inside the leads box, got card / box {got.get('held_rects')}", got.get("held_in_box") is True)


@test
def test_removing_a_card_keeps_the_others_spots_on_a_slow_box(ctx: Ctx):
    got = _room(ctx)
    ctx.check(f"every other card keeps its id and its spot in the layout file, got {got.get('kept')} of {got.get('others')}",
              len(got.get("others") or []) == 7 and got.get("kept") == got.get("others")
              and got.get("removed_id") not in (got.get("layout_after") or {"scout#0": 1}))
    ctx.check(f"and nothing overlaps, got {got.get('after_overlaps')}", got.get("after_overlaps") == [])


@test
def test_a_stopped_agent_ends_on_the_map_within_the_floor(ctx: Ctx):
    got = _fleet(ctx)
    floor = _floor_s()
    limit = floor + 1 + FLEET_MS / 1000  # the floor, a second, and the view's own answer that much late
    ctx.check(f"the poll floor is 5 s (fleet/sync.ts FLOOR_MS), got {floor}", floor == 5.0)
    ctx.check(f"the end frame and every re-reading frame were lost, the view said running when the model call was let go, got "
              f"{got.get('lost')} {got.get('before_release')!r}",
              (got.get("lost") or {}).get("agent_state", 0) >= 1 and got.get("before_release") == "running" and got.get("stopped") == "stopped")
    ctx.check(f"the node ends within {limit:g} s of the tree, got {got.get('floor')!r} after {got.get('floor_s')} s",
              got.get("floor") == "stopped" and (got.get("floor_s") or 99) <= limit)


@test
def test_a_late_running_frame_after_the_end_is_corrected(ctx: Ctx):
    got = _fleet(ctx)
    limit = _floor_s() + 1 + FLEET_MS / 1000
    ctx.check(f"the late frame drew the node running, then it ends again within {limit:g} s, got {got.get('late_running')!r} "
              f"{got.get('late')!r} after {got.get('late_s')} s", got.get("late") == "stopped" and (got.get("late_s") or 99) <= limit)
    ctx.check(f"one feed listener all along, got {got.get('listeners')}", got.get("listeners") == 1)


if __name__ == "__main__":
    results, passed, failed, skipped = run_all(TESTS, Ctx())
    sys.exit(print_results(results, passed, failed, skipped))
