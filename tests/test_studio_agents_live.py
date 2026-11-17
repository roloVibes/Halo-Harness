"""tests.test_studio_agents_live -- Halo 3.6.0.2 R52: Agents -> 4 · Live, in headless Chrome as a first-time user (driver
tests/helpers/studio_agents_live.py over the session rig and the live rig; skipped without Chrome; the Linux VM and CI
only). The pure half of the doors (urlDoor, viewOf, a replay on the Map, the live panels' doors) is
tests/test_agents_door.py, run in node everywhere.

1. the old door `?mode=agents&view=live` opens 4 · Live, its tab pressed; the switch reads
   `1 · Agents | 2 · Workflows | 3 · Map | 4 · Live`; the Live part holds its shell (the session's T-state line from
   truth.ts, its status line, the frame reserved for the drawing) in its own workspace `agents-live`; the dot sits on
   4 · Live while a session runs, never on 3 · Map; C -> Map, L -> Live, 3 -> Map, 4 -> Live; Live is remembered as the
   tab used last; the palette lists `Agents: 4 · Live` with its key 4 and Enter lands on Live.
Run: python -m tests.test_studio_agents_live
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}
FOUR = ["1 · Agents", "2 · Workflows", "3 · Map", "4 · Live"]


def _got(ctx: Ctx) -> dict:
    slow = {"HALO_STUDIO_SLOW_MS": os.environ["HALO_STUDIO_SLOW_MS"]} if os.environ.get("HALO_STUDIO_SLOW_MS") else None
    return driver_got(ctx, "tests.helpers.studio_agents_live", why="Agents -> Live is driven in headless Chrome", cache=_RUN, timeout=600,
                      env=slow)


@test
def test_old_live_door_and_l_key_open_live(ctx: Ctx):
    d = _got(ctx)
    ctx.check(f"?mode=agents&view=live opens Live, got {d.get('door')!r}", d.get("door") == "live")
    ctx.check(f"its tab pressed, got {d.get('pressed')!r}", d.get("pressed") == "true")
    ctx.check(f"four tabs, got {d.get('switch')}", d.get("switch") == FOUR)
    ctx.check(f"the Live part shown with its shell, in its own workspace, got {d.get('shown')} {d.get('workspace')!r}",
              d.get("shown") is True and d.get("workspace") == "agents-live")
    truth = d.get("truth") or ["", ""]
    ctx.check(f"the session's T-state line (T1), got {truth}", truth[0] == "T1" and str(truth[1]).startswith("This session runs on shop, as it started at "))
    ctx.check(f"the status line and the reserved frame, got {d.get('status')} {d.get('frame')}", d.get("status") is True and d.get("frame") is True)
    ctx.check(f"the dot on 4 · Live while a session runs, not on 3 · Map, got {d.get('dot')} {d.get('map_dot')!r}",
              d.get("dot") == ["1", "4 · Live"] and d.get("map_dot") == "")
    ctx.check(f"the keys: C -> Map, L -> Live, 3 -> Map, 4 -> Live, got {d}",
              d.get("key_c") == "map" and d.get("key_l") == "live" and d.get("key_3") == "map" and d.get("key_4") == "live")
    ctx.check(f"Live remembered as the tab used last, got {d.get('remembered')!r}", d.get("remembered") == "live")
    ctx.check(f"the palette's line with its key, got {d.get('palette')} (first {d.get('palette_first')!r})",
              d.get("palette") == [["Agents: 4 · Live", "4"]])
    ctx.check(f"Enter lands on Live, got {d.get('palette_to')!r}", d.get("palette_to") == "live")
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
