"""tests.test_studio_session_cost_map -- Session's Cost graphics and its map
as one picture, in a real browser (Halo 3.1.5.0 R3; headless Chrome through
the driver base, tests/helpers/studio_session_cost_map.py `costmap`; skipped
without one).

Over this harness's real session plus three extra agents and scripted
session figures (tests/helpers/studio_live_rig.py):

1. the context-fill bar: 50 % ok (cyan), 85 % amber, 97 % red;
2. the spend sparkline gains a point each time the spend rises; cost per
   turn is the spend over the turns; the share bar has a segment per agent
   that spent, sized by what it spent; the agent rows carry their tokens;
3.-6. (3.6.0.0 R5: the tree's nodes, their tool clock, their state colours and the GET-versus-frame node went
   with the agent tree; the Session's map is the lit map now, tests/test_studio_map_live.py)
7. (3.1.8.0 R6) with main mid-turn on its gated sub-agents, the session's own
   `message_end` moves the spend, the tokens and the turns within 1.5 s (no
   cache clear, no sessions frame); a GET from before it (lower figures)
   never pulls them back; a `status` frame with None totals leaves them; a
   sub-agent's frames never move them; a finished child is counted once in
   the share bar (main's share is the session total less its finished
   children's) and TURNS is the session's user turns, an agent's own count
   its "calls";
8. (3.3.5.0 R4) the last prompt's parts as one stacked bar in token colours, and the Live
   composer's preflight: the line, Compact / Bigger window / Send anyway posting the answer.
Run: python -m tests.test_studio_session_cost_map
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
_RUNS: dict = {}


def _driver(*argv: str) -> "tuple[subprocess.CompletedProcess, dict]":
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (Session's Cost and map need headless Chrome)")
    if argv not in _RUNS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_session_cost_map", *argv], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUNS[argv] = (r, info)
    r, info = _RUNS[argv]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    return r, info


def _ran(ctx: Ctx, r, got) -> None:
    ctx.check(f"the driver ran, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in got)


def _rgb(hexv: str) -> str:
    h = hexv.lstrip("#")
    return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})" if len(h) == 6 else hexv


@test
def test_the_context_bar_turns_amber_past_80_and_red_past_95(ctx: Ctx):
    r, got = _driver("costmap")
    _ran(ctx, r, got)
    lv = [x[0] for x in got.get("ctx") or []]
    ctx.check(f"50 % ok, 85 % warn, 97 % bad, got {lv}", lv == ["ok", "warn", "bad"])
    colors = [x[1] for x in (got.get("ctx") or [])[1:]]
    ctx.check(f"in amber, then red (instrument's warn and bad, 3.3.15.0), got {colors}", colors == ["rgb(245, 165, 36)", "rgb(255, 92, 106)"])


@test
def test_the_sparkline_rises_and_per_turn_and_the_share_bar_read(ctx: Ctx):
    r, got = _driver("costmap")
    _ran(ctx, r, got)
    p0, p1, segs = (got.get("spark") or [0, 0, 0])
    ctx.check(f"the sparkline gains a point per rise, got {p0} -> {p1} ({segs} segments)", p1 >= p0 + 3 and segs >= 3)
    ctx.check(f"cost per turn: $0.060 over 2 turns, got {got.get('per_turn')!r}", got.get("per_turn") == "$0.0300")
    share = dict(got.get("share") or [])
    ctx.check(f"a segment per agent that spent, sized by it, got {share}", share.get("t7e5s1t0") == 0.012 and share.get("d0c5w1r1") == 0.004)
    toks = got.get("agent_tokens") or []
    ctx.check(f"the agent rows carry their own tokens (the real agents' from their transcripts), got {toks}",
              any("/" in t and t != "-" for t in toks))


FIGS = ["$0.2468", "54.3k", "4.3k", "3", "$0.0823", "60.0"]  # spend, in, out, turns, per turn, context %


@test
def test_the_figures_move_on_the_sessions_own_frames(ctx: Ctx):
    r, got = _driver("costmap")
    _ran(ctx, r, got)
    moved, took = (got.get("fig_moved") or [None, 99])
    ctx.check(f"from {got.get('fig_before')}: message_end moved the spend, tokens and turns, got {moved!r} in {took}s",
              moved == "moved" and took <= 1.5)


@test
def test_a_get_from_before_the_frame_never_pulls_the_figures_back(ctx: Ctx):
    r, got = _driver("costmap")
    _ran(ctx, r, got)
    ctx.check(f"the lower GET answer landed, got {got.get('fig_get_landed')!r}", got.get("fig_get_landed") == "landed")
    ctx.check(f"the figures kept the frame's, got {got.get('fig_after_get')}", got.get("fig_after_get") == FIGS)


@test
def test_a_status_frame_without_totals_and_a_sub_agents_frames_leave_the_figures(ctx: Ctx):
    r, got = _driver("costmap")
    _ran(ctx, r, got)
    ctx.check(f"the status frame landed (its model shows), got {got.get('fig_status_landed')!r}", got.get("fig_status_landed") == "landed")
    ctx.check(f"None totals leave every figure, got {got.get('fig_after_status')}", got.get("fig_after_status") == FIGS)
    ctx.check(f"a sub-agent's message_end and status move nothing, got {got.get('fig_after_child')}", got.get("fig_after_child") == FIGS + ["r6-status"])


@test
def test_a_finished_child_is_counted_once_and_turns_are_one_unit(ctx: Ctx):
    r, got = _driver("costmap")
    _ran(ctx, r, got)
    share = dict(got.get("fig_share") or [])
    ctx.check(f"main's share is the total less the finished tester's: 0.2468 - 0.012, got {share}",
              share.get("main") == 0.2348 and share.get("t7e5s1t0") == 0.012 and share.get("d0c5w1r1") == 0.004)
    ctx.check(f"the bar adds up to the total plus the live docs agent's, never the finished child twice, got {round(sum(share.values()), 6)}",
              round(sum(share.values()), 6) == 0.2508)
    ctx.check(f"main's line: its own spend and its model calls as calls (TURNS says 3), got {got.get('fig_main_line')}",
              got.get("fig_main_line") == ["$0.2348", "1 call"])


@test
def test_v3331_an_unpriced_main_shows_a_plus_and_no_price(ctx: Ctx):
    r, got = _driver("costmap")
    _ran(ctx, r, got)
    model = got.get("partial_model") or ""
    ctx.check(f"the spend is the priced part with a +, got {got.get('partial')!r}", got.get("partial") == "$3.63+")
    ctx.check(f"its title names main's model, got {got.get('partial_title')!r}",
              got.get("partial_title") == f"main's model {model} reports no price: this is what the priced agents spent")
    ctx.check(f"PER TURN carries the + too, got {got.get('partial_per_turn')!r}", str(got.get("partial_per_turn") or "").endswith("+"))
    ctx.check(f"3.3.17.0: a Copilot part says its reason, got {got.get('copilot_line')!r}", got.get("copilot_line") == "+ Copilot: billed by your tenant (credits or licence)")
    ctx.check(f"main's line says no price, never $0.0000, got {got.get('noprice')!r}", got.get("noprice") == "no price")
    ctx.check(f"a complete total drops both, got {got.get('complete_again')!r}", got.get("complete_again") == "gone")


@test
def test_v3350_r4_the_composition_bar_and_the_preflight_buttons(ctx: Ctx):
    from tests.helpers.studio_cost_composition import COMP, LINE
    r, got = _driver("costmap")
    _ran(ctx, r, got)
    ctx.check(f"the bar shows the last prompt's total, got {got.get('comp_total')!r}", got.get("comp_total") == str(COMP["total"]))
    segs = got.get("comp_segs") or []
    parts = ["system", "memory", "topic_index", "tools_schema", "history", "user"]
    ctx.check(f"a segment per part in order, got {[s[0] for s in segs]}", [s[0] for s in segs] == parts)
    want = {p: round(COMP[p] / COMP["total"], 3) for p in parts}
    ctx.check(f"each sized by its tokens, got {segs}", all(abs(s[1] - want[s[0]]) <= 0.002 for s in segs))
    colours = [s[2] for s in segs]
    ctx.check(f"each part its own token colour, got {colours}", len(set(colours)) == len(parts) and all(c.startswith("rgb") for c in colours))
    keys = {k[0]: k[1] for k in got.get("comp_keys") or []}
    ctx.check(f"a key per part with its count, got {keys}", keys == {p: COMP[p] for p in parts})
    ctx.check(f"the title is the /cost line, got {got.get('comp_title')!r}",
              str(got.get("comp_title") or "").startswith("prompt 30,756: system 3,587 · memory 9,900 · topics 6,400"))
    ctx.check(f"a status frame's composition moves it, got {got.get('comp_after_frame')!r}", got.get("comp_after_frame") == "31587")
    ctx.check(f"the preflight line above the steer box, got {got.get('pf_line')!r}", got.get("pf_line") == LINE)
    ctx.check(f"three buttons, the switch naming the model, got {got.get('pf_buttons')}", got.get("pf_buttons") == [
        ["compact", "Compact", False], ["switch", "Bigger window: ol:wide:14b@lan", False], ["send", "Send anyway", False]])
    posted = got.get("pf_posted") or ["", ""]
    ctx.check(f"send posts the answer to the session's command route, got {posted}", posted[0].endswith("/command")
              and '"kind":"approval"' in posted[1] and '"action":"send"' in posted[1] and '"request_id":"preflight-r4test"' in posted[1])
    ctx.check(f"no bigger-window model: the switch is disabled, got {got.get('pf_no_switch')!r}", got.get("pf_no_switch") == "disabled")
    ctx.check(f"answered (no card waiting): the bar goes, got {got.get('pf_gone')!r}", got.get("pf_gone") == "gone")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
