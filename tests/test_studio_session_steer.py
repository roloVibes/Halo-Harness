"""tests.test_studio_session_steer -- Session's Live column, Halo 3.1.7.0 R1
"Session has what Fleet has, and the steer is always at hand" (the owner,
2026-10-20: "I want what fleet has with tool running too within the session
tab. More of insight and ability to jump in and steer"), in a real browser
(headless Chrome through the driver base, tests/helpers/studio_session_steer.py
`steer`; skipped without one). Over this harness's real session (a lead, an
implementer and a researcher mid-work behind the real Controller) plus three
extra agents and scripted feed frames (tests/helpers/studio_live_rig.py), with
Studio's command route to the session recorded:

1. with nothing pinned the Steer box sits at the column's foot addressed to
   main ("STEER main"), Pause and Stop beside it; a steer typed there lands as
   a YOU line at once and reaches main's command route (delivered);
2. a line's tag shows "steer" on hover and a map node shows its chip: the
   click pins that agent, the box talks to it and has the keyboard; the agent
   pick follows the pin, its "every agent" goes back to main;
3. the timeline strip: one lane per live agent of this session, 5 / 15 / 60
   min; a lane click pins it (the lane lit, the pick and the box follow);
4. the kind pick "tools" hides the text rows (your steer stays); every kind
   brings them back;
5. a finished agent's box is disabled with one line, Pause and Stop with it;
6. Stop asks first (the confirm names main; Cancel sends nothing); Pause
   reaches main's route;
7. in Fleet the node's chip opens the Agent panel's Steer box, focused.
Run: python -m tests.test_studio_session_steer
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}


def _driver() -> "tuple[subprocess.CompletedProcess, dict]":
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Live column needs headless Chrome)")
    if not _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_session_steer", "steer"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"], _RUN["info"] = r, info
    r, info = _RUN["r"], _RUN["info"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    return r, info


def _ran(ctx: Ctx, r, got) -> None:
    ctx.check(f"the driver ran, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in got)


@test
def test_the_steer_box_is_there_with_nothing_pinned_and_talks_to_main(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    b = got.get("box_main") or {}
    ctx.check(f"nothing pinned: the box at the foot, addressed to main, it takes text, got {b}",
              b.get("key") == got.get("main_key") and b.get("main") is True and str(b.get("head")).lower() == "steer main" and b.get("enabled") is True and b.get("pinned") == "")
    ctx.check(f"Pause and Stop beside it, for main, got {b.get('pause')} {b.get('stop')}", b.get("pause") == ["Pause", True] and b.get("stop") == ["Stop", True])


@test
def test_a_steer_sent_from_the_column_echoes_as_you_and_reaches_main(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    ctx.check(f"a YOU line for main at once, got {got.get('you_line')} in {got.get('you_s')} s",
              got.get("you_line") == [got.get("main_key"), "YOU"] and float(got.get("you_s", 9)) < 2)
    s = got.get("steer_route") or {}
    ctx.check(f"it reached main's command route on this session and was delivered, got {s}",
              s.get("sid") == got.get("sid") and s.get("agent_id") == "main" and s.get("mode") == "nudge" and s.get("status") == 200 and s.get("delivered") in ("steer", "turn"))
    ctx.check("acknowledged and the box cleared", got.get("steer_ack") == "steered" and got.get("steer_cleared") is True)


@test
def test_steer_on_a_tags_hover_pins_it_and_focuses_the_box(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    ctx.check(f"hidden until the line is hovered, then shown, got {got.get('tag_hidden')!r} -> {got.get('tag_shown')!r}", got.get("tag_hidden") == "0" and got.get("tag_shown") == "1")
    t = got.get("tag_steer") or {}
    ctx.check(f"the click: the researcher pinned, the box to it, the keyboard in it, got {t}",
              t.get("pinned") == got.get("res_key") and t.get("key") == got.get("res_key") and str(t.get("head")).lower() == "steer researcher" and t.get("focused") is True)
    ctx.check(f"the agent pick follows the pin; every agent goes back to main, got {got.get('pick_after_tag')} {got.get('pick_cleared')}",
              got.get("pick_after_tag") == got.get("res_key") and got.get("pick_cleared") == "main")


@test
def test_steer_on_a_map_nodes_hover_pins_it_in_live(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    ctx.check(f"the node's chip shows on hover, got {got.get('node_hidden')!r} -> {got.get('node_shown')!r}", got.get("node_hidden") == "0" and got.get("node_shown") == "1")
    n = got.get("node_steer") or {}
    ctx.check(f"the click: the implementer pinned in Live, the box to it and focused, the pick on it, got {n} {got.get('pick_after_node')}",
              n.get("pinned") == got.get("impl_key") and n.get("key") == got.get("impl_key") and n.get("focused") is True and got.get("pick_after_node") == got.get("impl_key"))


@test
def test_the_strip_has_a_lane_per_live_agent_and_a_lane_click_pins(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    lanes = got.get("lanes") or []
    ctx.check(f"one lane per live agent of this session, got {len(lanes)} for {len(got.get('live_nodes') or [])}",
              len(lanes) >= 6 and lanes == got.get("live_nodes") and got.get("spans") == ["5 min", "15 min", "60 min"])
    ctx.check(f"a lane click pins the tester: the lane lit, the pick and the box follow, got {got.get('lane_pinned')} {got.get('lane_lit')} {got.get('pick_after_lane')}",
              got.get("lane_pinned") == got.get("tester_key") and got.get("lane_lit") is True and got.get("pick_after_lane") == got.get("tester_key")
              and got.get("box_after_lane") == got.get("tester_key"))
    rows = got.get("pick_rows") or []
    ctx.check(f"the agent pick: every agent, then each agent of the session, main first, got {len(rows)}", rows[:2] == ["", got.get("main_key")] and len(rows) == len(lanes) + 1)


@test
def test_the_kind_pick_hides_the_text_rows(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    before, tools, after = (got.get(k) or {} for k in ("kinds_before", "kinds_tools", "kinds_after"))
    ctx.check(f"text rows were there, got {before}", (before.get("text") or 0) >= 1 and (before.get("tool") or 0) >= 1)
    ctx.check(f"tools: only tool rows and your steer, got {tools}", set(tools) <= {"tool", "you"} and tools.get("tool") == before.get("tool"))
    ctx.check(f"every kind brings them back, got {after}", after == before)


@test
def test_a_finished_agents_box_is_disabled_with_one_line(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    d = got.get("done_box") or {}
    ctx.check(f"the docs agent finished: its box disabled, one line saying so, Pause and Stop too, got {d}",
              d.get("enabled") is False and got.get("done_disabled") is True and "has finished" in str(d.get("placeholder")) and "\n" not in str(d.get("placeholder"))
              and d.get("pause") == ["Pause", False] and d.get("stop") == ["Stop", False])
    ctx.check(f"every agent again: main, enabled, got {got.get('back_to_main')}", (got.get("back_to_main") or {}).get("enabled") is True)


@test
def test_stop_asks_first_and_pause_reaches_mains_route(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    ctx.check(f"Stop opens the confirm naming main, got {got.get('stop_dialog')!r}", "Stop main?" in str(got.get("stop_dialog")))
    ctx.check(f"Cancel closes it and sends nothing, got {got.get('stop_cancelled')} {got.get('stop_sent')}", got.get("stop_cancelled") == "closed" and got.get("stop_sent") == [])
    p = got.get("pause_route") or {}
    ctx.check(f"Pause reached main's command route, got {p} {got.get('pause_ack')!r}",
              p.get("sid") == got.get("sid") and p.get("agent_id") == "main" and p.get("status") == 200 and got.get("pause_ack") == "paused")


@test
def test_in_fleet_the_node_chip_opens_the_agent_panels_steer(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    ctx.check(f"Fleet's map: the chip opens Agent on that agent, the keyboard in its Steer box, got {got.get('fleet_chip')!r}", got.get("fleet_chip") == "focused")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
