"""tests.test_studio_agents_live -- Halo 3.6.0.2 R52: Agents -> 4 · Live, in headless Chrome as a first-time user (driver
tests/helpers/studio_agents_live.py over the session rig and the live rig; skipped without Chrome; the Linux VM and CI
only). The pure half of the doors (urlDoor, viewOf, a replay on the Map, the live panels' doors) is
tests/test_agents_door.py, run in node everywhere.

1. the old door `?mode=agents&view=live` opens 4 · Live, its tab pressed; the switch reads
   `1 · Agents | 2 · Workflows | 3 · Map | 4 · Live`; the Live part holds its shell (the session's T-state line from
   truth.ts, its status line, the frame reserved for the drawing) in its own workspace `agents-live`; the dot sits on
   4 · Live while a session runs, never on 3 · Map; C -> Map, L -> Live, 3 -> Map, 4 -> Live; Live is remembered as the
   tab used last; the palette lists `Agents: 4 · Live` with its key 4 and Enter lands on Live;
2. R56 (decision 4): while a session he has talked to is open (here: between turns), Alt+2 opens Agents on 4 · Live
   whatever the tab used last, and Agents' help says so; a Studio-started session with no message yet (T10) does not
   count: Agents opens on the tab used last (2 · Workflows); this is decision 4's rewrite of
   tests/test_studio_session.py's `test_alt_keys_and_agents_opens_on_the_map` (there now `..._opens_on_live`);
3. R56: once Agents has drawn its opening tab it never moves by itself: busy, idle, busy frames leave it on Live.
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
OPENS = "Agents opens on Live while a session is open, else on the tab used last."  # R56's words in its help


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



@test
def test_alt_keys_and_agents_opens_on_live(ctx: Ctx):
    d = _got(ctx)
    ctx.check(f"R56: a session between turns open, the tab used last 1 · Agents: Alt+2 opens Agents on Live, got {d.get('alt2')!r} {d.get('opens')!r}",
              str(d.get("alt2")).startswith("Agents") and d.get("opens") == "live")
    ctx.check(f"Agents' help says the opening rule, got {d.get('help')!r}", OPENS in str(d.get("help")) and "Agents opens on the Map" not in str(d.get("help")))
    ctx.check(f"Alt+1 comes back to Session, got {d.get('alt1')!r}", str(d.get("alt1")).startswith("Session"))
    ctx.check(f"T10 (Studio-started, no message yet) does not count: the tab used last (2 · Workflows), got {d.get('t10')!r}",
              d.get("t10") == "workflows")
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))


@test
def test_opening_tab_never_flips_once_drawn(ctx: Ctx):
    d = _got(ctx)
    ctx.check(f"the three frames each read by the page, got {d.get('flip_reads')!r}", (d.get("flip_reads") or 0) >= 3)
    ctx.check(f"R56: busy, idle, busy never move the opening tab: one value, Live, got {d.get('flips')!r}", d.get("flips") == ["live"])
    ctx.check(f"the driver ran every step, got {d.get('failed')!r}", not d.get("failed"))

if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
