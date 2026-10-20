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
3. a running tool's name and clock on its node ("Bash 2s · pytest -q");
4. the tree fans out: main's five children sit in rows under it, side by
   side, each naming main as its parent, and no two labels touch;
5. the state colours on node and edge: waiting amber, failed red (and it
   stays), done green that fades back after ten seconds;
6. (follow-up) a GET fleet answer never undoes a newer agent_state frame: a
   frame says stopped, GET still says running, the node stays stopped.
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
    ctx.check(f"in amber, then red, got {colors}", colors == ["rgb(255, 179, 71)", "rgb(255, 77, 141)"])


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


@test
def test_a_node_shows_its_tool_and_its_clock(ctx: Ctx):
    r, got = _driver("costmap")
    _ran(ctx, r, got)
    s0, s1, text = (got.get("node_secs") or ["", "", ""])
    ctx.check(f"the clock ticks on the node, got {s0} -> {s1}", str(s0).isdigit() and str(s1).isdigit() and int(s1) >= int(s0) + 2)
    ctx.check(f"with the tool and its target, got {text!r}", str(text).startswith("Bash ") and str(text).endswith("pytest -q"))


@test
def test_the_tree_fans_out_and_no_labels_overlap(ctx: Ctx):
    r, got = _driver("costmap")
    _ran(ctx, r, got)
    t = got.get("tree") or {}
    main, kids = t.get("main") or [0, 0], t.get("kids") or []
    ctx.check(f"five children placed, got {kids}", len(kids) == 5 and all(len(k) == 2 for k in kids))
    ctx.check(f"every child below main, got main {main} kids {kids}", all(k[1] > main[1] for k in kids))
    rows: dict = {}
    for k in kids:
        rows.setdefault(k[1], []).append(k[0])
    first = rows[min(rows)] if rows else []
    ctx.check(f"a fan: at least two children side by side on one row, got rows {rows}", len(first) >= 2 and len(set(first)) == len(first))
    ctx.check(f"each names main as its parent, got {t.get('parents')}", (t.get("parents") or []).count("main") >= 5)
    ctx.check(f"no two labels touch, got {got.get('overlaps')}", got.get("overlaps") == [])


@test
def test_state_colours_and_the_done_fade(ctx: Ctx):
    r, got = _driver("costmap")
    _ran(ctx, r, got)
    w = got.get("waiting") or ["", "", ""]
    ctx.check(f"waiting: the node and its edge amber, got {w}", w[0] == "waiting" and w[1] == _rgb(w[2]))
    f = got.get("red") or ["", "", ""]
    ctx.check(f"failed: red on its edge, got {f}", f[0] == "error" and f[1] == _rgb(f[2]))
    d = got.get("done") or ["", ""]
    ctx.check(f"done: green that fades (the fade animation runs), got {d}", d[0] == "done" and d[1] == "fm-done-fade")
    ctx.check(f"ten seconds on, done has settled and failed has stayed, got {got.get('done_later')} {got.get('red_later')}",
              got.get("done_later") == "idle" and got.get("red_later") == "error")


@test
def test_a_get_answer_never_undoes_a_newer_frame(ctx: Ctx):
    r, got = _driver("costmap")
    _ran(ctx, r, got)
    ctx.check(f"the frame said stopped, got {got.get('fresh_frame')!r}", got.get("fresh_frame") == "stopped")
    ctx.check(f"GET fleet still said running and its answer landed, got {got.get('fresh_api_says')!r} {got.get('fresh_get_landed')!r}",
              got.get("fresh_api_says") == "running" and got.get("fresh_get_landed") == "landed")
    ctx.check(f"the node kept the frame's newer state, got {got.get('fresh_after_get')!r}", got.get("fresh_after_get") == "stopped")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
