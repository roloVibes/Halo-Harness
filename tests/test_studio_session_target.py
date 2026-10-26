"""tests.test_studio_session_target -- Session's Live column, Halo 3.3.0.0 R6
"the steer knows its target, and the timeline exports a trace" (the owner,
2026-10-26: "if you choose to steer via studio, you can't really tell which
call you are steering. Highlight what you are interacting with because that
scroller in the session tab can lose where you were steering in real time";
"also in the timeline, have an export button that saves it as an .md file"),
in a real browser (headless Chrome through tests/helpers/studio_session_target.py
`target`; skipped without one), over this harness's real session plus three
extra agents and scripted feed frames:

1. the target line names the agent and its call ("Steering: main · Bash
   (pytest -q), 3 s"), ticking; main's row is outlined;
2. a click on the researcher's row makes it the target: the line says so
   (and what it was), the row and its map node are outlined, the node's
   steer chip lit, its lane lit; the row stays the held row, in view, while
   rows arrive;
3. with the field focused, twenty new rows do not move the view and the pill
   counts them ("20 new rows · follow");
4. a steer lands right under its target ("↳ steer to ..."), the agent's next
   row is marked "after your steer", the turn-end marker shows in the list;
5. Tab cycles the target among the live agents (the field keeps the keyboard
   and its text), Shift+Tab back; Escape follows again; `s` on a focused row
   makes it the target with the field focused;
6. Export: the header's and the timeline's buttons; the download is
   halo-trace-<sid>-<yyyy-mm-dd-hhmm>.md and its text, read back through the
   page, is the route's trace.
Run: python -m tests.test_studio_session_target
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
_RUN: dict = {}


def _driver() -> "tuple[subprocess.CompletedProcess, dict]":
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Live column needs headless Chrome)")
    if not _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_session_target", "target"], capture_output=True, encoding="utf-8",
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
def test_the_target_line_names_the_agent_and_its_call(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    m = got.get("line_main") or {}
    ctx.check(f"main and its call, the box to main, got {m}",
              m.get("key") == got.get("main_key") and m.get("name") == "main" and m.get("box") == got.get("main_key")
              and re.fullmatch(r"Bash \(pytest -q\), \d+ s", str(m.get("call"))) is not None and str(m.get("text")).startswith("Steering:"))
    ctx.check(f"the time ticks, got {m.get('call')!r} -> {got.get('line_ticks')!r}", got.get("line_ticks") != m.get("call"))
    ctx.check("main's row is the outlined one", got.get("main_row_outlined") is True)


@test
def test_a_row_click_makes_it_the_target_and_it_stays_highlighted(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    ch = got.get("chosen") or {}
    ctx.check(f"the researcher is the target, the line says so and what it was, got {ch}",
              ch.get("key") == got.get("res_key") and ch.get("box") == got.get("res_key") and ch.get("col") == got.get("res_key")
              and ch.get("was") == "(was main)" and bool(ch.get("call")))
    ctx.check(f"the clicked row is the held one, outlined, got {got.get('held_n')} {got.get('row_n')} {got.get('outline')}",
              got.get("held_n") and got.get("held_n") == got.get("row_n") and got.get("outline") == "solid")
    ctx.check(f"its map node is outlined with its steer chip lit, its lane lit, got {got.get('node_target')} {got.get('node_chip')} {got.get('lane_lit')}",
              got.get("node_target") is True and got.get("node_chip") == "1" and got.get("lane_lit") is True)
    ctx.check(f"ten rows later it is still the held row and in view, got {got.get('held_after')} {got.get('held_in_view')}",
              got.get("held_after") == got.get("row_n") and got.get("held_in_view") is True)


@test
def test_while_composing_new_rows_do_not_move_the_view(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    ctx.check(f"twenty rows, the view did not move, got {got.get('top_moved')}", got.get("top_moved") is not None and got.get("top_moved") <= 1)
    ctx.check(f"the pill counts them, got {got.get('pill')!r}", str(got.get("pill")).strip() == "20 new rows · follow")
    ctx.check("the field kept the keyboard", got.get("still_focused") is True)


@test
def test_a_steer_lands_under_its_target_and_the_next_row_is_marked(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    ctx.check(f"↳ steer to the researcher, right under the target row, got {got.get('steer_text')!r} {got.get('steer_under')}",
              str(got.get("steer_text")).startswith("↳ steer to ") and "STEER-T keep the tax rule" in str(got.get("steer_text")) and got.get("steer_under") is True)
    ctx.check(f"the researcher's next row says after your steer, got {got.get('after_mark')}", got.get("after_mark") == ["true", "after your steer"])
    ctx.check(f"the turn-end marker is a row of the same list, got {got.get('marker_row')}", (got.get("marker_row") or 0) >= 1)


@test
def test_tab_cycles_the_target_and_escape_follows_again(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    ctx.check(f"Tab: the next live agent, got {got.get('tab_after')} for {got.get('tab_expected')} among {len(got.get('tab_live') or [])}",
              got.get("tab_after") == got.get("tab_expected") and got.get("tab_line") == got.get("tab_after") and len(got.get("tab_live") or []) >= 3)
    ctx.check(f"the field keeps the keyboard and its text, got {got.get('tab_kept')}", got.get("tab_kept") == [True, "KEEP"])
    ctx.check(f"Shift+Tab goes back, got {got.get('shift_tab')}", got.get("shift_tab") == got.get("tab_before"))
    ctx.check(f"Escape out of the field follows again, got {got.get('esc_paused')} -> {got.get('esc_follows')!r}",
              got.get("esc_paused") is True and got.get("esc_follows") == "follows")
    ctx.check(f"s on a focused row makes its agent the target, the field focused, got {got.get('row_focused')} {got.get('s_key')}",
              got.get("row_focused") is True and got.get("s_key") == got.get("impl_key"))


@test
def test_export_downloads_the_sessions_trace(ctx: Ctx):
    r, got = _driver()
    _ran(ctx, r, got)
    where = {b[0]: b for b in got.get("buttons") or []}
    ctx.check(f"Export on the header and on the timeline, got {got.get('buttons')}",
              set(where) == {"head", "timeline"} and all(b[1] == "Export" and b[2] is True for b in where.values()))
    sid = got.get("sid")
    ctx.check(f"the name, got {got.get('name')!r}", re.fullmatch(rf"halo-trace-{re.escape(str(sid))}-\d{{4}}-\d\d-\d\d-\d{{4}}\.md", str(got.get("name"))) is not None)
    ctx.check(f"its text is the session's trace, the route's bytes, got {got.get('head')!r} {got.get('log_found')!r}",
              got.get("head") == f"# Halo trace: session {sid}" and got.get("has_totals") is True and got.get("same_as_route") is True)
    ctx.check(f"a toast says it saved, got {got.get('toast')!r}", got.get("toast") == "saved")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
