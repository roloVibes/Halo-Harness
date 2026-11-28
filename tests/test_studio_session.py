"""tests.test_studio_session -- the Session dashboard in a real browser (Halo
3.1.4.0 R2 "The session dashboard"; headless Chrome through the driver base,
tests/helpers/studio_session.py `dash`; skipped without one).

Over this harness's real session (a lead, an implementer and a researcher
mid-work) and a second session of this harness:

1. landing: with nothing saved for the browser and a session live here the
   page lands on Session (the served page carries `data-live-session`); with
   nothing live it lands on Roles as before;
2. `?mode=session` mounts the seven panels (session-map, -activity,
   -attention, -agent, -cost, 3.1.5.0 R3, -live and, 3.3.11.0 R1, -prompt: Agent, Activity, Attention and Prompt
   as strips; the arrangement itself is tests/test_studio_session_live.py's), each with its about line;
3. the map draws this harness only (no harness box since 3.5.0.0): one card per session, its
   agent tree, the working nodes lit, the newest working agent selected (lit)
   and its session the chosen card; Cost speaks of that session (its model,
   its agents); Activity draws one lane per live agent of it and logs only
   this harness; Attention holds no rows; J / K stay on
   this harness;
4. `&session=<id>` chooses that session: the agent panel and Cost follow;
5. Alt+2 shows Agents on Live with this machine's session and no harness box,
   Alt+1 (3.1.6.0 R6: Session is the first tab) comes back to Session;
6. `/studio`'s opener on the running Studio focuses the open page: on Agents,
   it switches to Session on that session, and no tab opens.
The links into it are tests/test_studio_session_links.py; `/studio` and
`halo studio --session` are tests/test_slash_studio.py and
tests/test_studio_cli_session.py.
Run: python -m tests.test_studio_session
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
        raise SkipTest("no Chrome found (the Session dashboard needs headless Chrome)")
    if argv not in _RUNS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_session", *argv], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=400, env=driver_env(REPO), cwd=str(REPO))
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
    ctx.check(f"the driver ran, got {r.returncode} {got.get('failed')!r} {r.stderr[-500:]!r}", r.returncode == 0 and "failed" not in got)


@test
def test_landing_follows_a_live_session_here(ctx: Ctx):
    r, got = _driver("dash")
    _ran(ctx, r, got)
    ctx.check(f"nothing saved, a session live here: Session, got {got.get('landing_live')!r} (mark {got.get('boot_live')!r})",
              str(got.get("landing_live")).startswith("Session") and bool(got.get("boot_live")))
    ctx.check(f"nothing saved, nothing live: Agents (Roles before 3.3.16.0), got {got.get('landing_none')!r} (mark {got.get('boot_none')!r})",
              str(got.get("landing_none")).startswith("Agents") and got.get("boot_none") == "")


@test
def test_mode_session_mounts_the_seven_panels(ctx: Ctx):
    r, got = _driver("dash")
    _ran(ctx, r, got)
    ctx.check(f"the seven panels once each (3.3.11.0 R1: Prompt), got {got.get('panels')}", got.get("panels") == [1] * 7)
    ctx.check(f"each with its about line, got {got.get('abouts')}", got.get("abouts") == 7)
    t = got.get("titles") or {}
    m, f = t.get("session-map") or {}, t.get("session-live") or {}
    ctx.check(f"3.6.0.2 R35: the left drawer (session-map) is titled Live, its hover says (was Map), got {m}",
              m.get("text") == "Live" and "(was Map)" in m.get("title", "") and (not m.get("bar") or m.get("bar") == "Live")
              and (not m.get("barTitle") or "(was Map)" in m.get("barTitle", "")))
    ctx.check(f"3.6.0.2 R35: the main panel (session-live) is titled Feed, its hover says (was Live), got {f}",
              f.get("text") == "Feed" and "(was Live)" in f.get("title", "") and (not f.get("bar") or f.get("bar") == "Feed"))


@test
def test_the_map_is_this_harness_with_the_working_agent_lit(ctx: Ctx):
    r, got = _driver("dash")
    _ran(ctx, r, got)
    ctx.check(f"no harness box (3.5.0.0: one machine), got {got.get('boxes')}", got.get("boxes") == 0)
    ctx.check(f"R2 R15: an open session between turns is drawn (>= 3 boxes and rows, none working), got {got.get('idle_nodes')}, "
              f"{got.get('idle_working')} working", (got.get("idle_nodes") or 0) >= 3 and got.get("idle_working") == 0)
    ctx.check(f"3.6.0.0 R5, 3.6.0.2 R15: the session running here drawn as its map: main, its children rows in it, got {got.get('nodes')}",
              (got.get("nodes") or 0) >= 3)
    ctx.check(f"the working boxes and rows lit, got {got.get('working')}", (got.get("working") or 0) >= 2)


@test
def test_cost_activity_and_attention_are_this_session(ctx: Ctx):
    r, got = _driver("dash")
    _ran(ctx, r, got)
    ctx.check(f"Cost speaks of the chosen session, got {got.get('cost_session')} {got.get('cost_model')!r} {got.get('cost_agents')!r} {got.get('cost_usd')!r}",
              got.get("cost_session") == got.get("sid") and got.get("cost_model") == "qwen3-lead"
              and str(got.get("cost_agents")).endswith("of 3") and str(got.get("cost_usd")).startswith("$"))
    ctx.check(f"one lane per live agent of it, got {got.get('lanes')} for {got.get('want_lanes')}",
              got.get("lanes") == got.get("want_lanes") and (got.get("want_lanes") or 0) >= 2 and got.get("lane_keys_here") is True)
    ctx.check(f"the log is this harness's only, got {got.get('log_who')}", got.get("log_who") == ["you@studio"])
    ctx.check(f"no attention rows, got {got.get('attn_here')} (empty {got.get('attn_empty')})",
              got.get("attn_here") == 0 and got.get("attn_empty") == 1)


@test
def test_session_param_chooses_that_session(ctx: Ctx):
    from tests.helpers.studio_session import FAKE_SID
    r, got = _driver("dash")
    _ran(ctx, r, got)
    ctx.check(f"and Cost, got {got.get('deep_cost')}", got.get("deep_cost") == FAKE_SID)


@test
def test_alt_keys_and_agents_opens_on_live(ctx: Ctx):
    # 3.6.0.2 decision 4 (R56): rewritten from test_alt_keys_and_agents_opens_on_the_map (3.6.0.0 R5: "on the Map while a
    # session runs"); the opening tab is the first one Agents draws, so the driver reads it, not a wait for one value
    r, got = _driver("dash")
    _ran(ctx, r, got)
    ctx.check(f"Alt+2 shows Agents, got {got.get('alt4')!r}", str(got.get("alt4")).startswith("Agents"))
    ctx.check(f"it opens on Live while a session he talked to is open (3.6.0.2 R56), no harness box, got {got.get('agents_view')} {got.get('agents_boxes')}",
              got.get("agents_view") == "live" and got.get("agents_boxes") == 0)
    ctx.check(f"Alt+1 comes back to Session, its map still lit, got {got.get('alt1')!r} {got.get('back_map')}",
              str(got.get("alt1")).startswith("Session") and got.get("back_map") == "lit")


@test
def test_studio_focuses_the_page_already_open(ctx: Ctx):
    from tests.helpers.studio_session import FAKE_SID
    r, got = _driver("dash")
    _ran(ctx, r, got)
    ctx.check(f"/studio's opener on a running Studio: focused, one line, got {got.get('focus_how')} {got.get('focus_line')!r}",
              got.get("focus_how") == "focused" and str(got.get("focus_line")).startswith("Opened this session in the Studio page"))
    ctx.check(f"the open page (on Agents) switches to Session on that session, no new tab, got {got.get('focus_tab')!r} {got.get('focus_agent')} {got.get('focus_tabs_opened')}",
              str(got.get("focus_tab")).startswith("Session") and f"|{FAKE_SID}|" in str(got.get("focus_agent")) and got.get("focus_tabs_opened") == 0)



@test
def test_a_claude_code_session_is_drawn_as_a_session_watch_only(ctx: Ctx):
    """3.6.0.25 G (tests/helpers/studio_guest.py): a guest row is a session named "Claude Code", "watch only" beside
    it; no Prompt box (one line instead), Steer and Screenshot disabled, no Steer box; the bridge's end takes its row
    out of the list (the Cost panel's "not known" is read in tests/test_studio_prompt_words.py)."""
    from tests.helpers.driver_got import got as driver_got
    got = driver_got(ctx, "tests.helpers.studio_guest", why="a Claude Code session in Session needs headless Chrome",
                     cache=_RUNS, key="guest", args=("guest",), timeout=300)
    ctx.check(f"the driver ran: {got.get('failed')!r}", "failed" not in got)
    head = str(got.get("head") or "")
    ctx.check(f"the header names Claude Code, watch only: {head!r}", "Claude Code" in head and "watch only" in head)
    ctx.check(f"no Prompt box, the watch-only line: {got.get('watch_line')!r}",
              got.get("prompt_input") is False and str(got.get("watch_line") or "").startswith("Claude Code · watch only"))
    ctx.check("Steer and Screenshot are disabled, no Steer box",
              got.get("steer_disabled") is True and got.get("shot_disabled") is True and got.get("steer_box") is False)
    row = got.get("row") or {}
    ctx.check(f"the registry row: kind guest, its parent Claude Code's: {row}",
              row.get("kind") == "guest" and str(row.get("parent") or "").startswith("claude-code:"))
    ctx.check("its end: the row and the spool gone", got.get("row_gone") == "gone" and got.get("spool_gone") is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
