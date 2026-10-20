"""tests.test_studio_session -- the Session dashboard in a real browser (Halo
3.1.4.0 R2 "The session dashboard"; headless Chrome through the driver base,
tests/helpers/studio_session.py `dash`; skipped without one).

Over this harness's real session (a lead, an implementer and a researcher
mid-work), a second session of this harness and a member harness `kali@lab`:

1. landing: with nothing saved for the browser and a session live here the
   page lands on Session (the served page carries `data-live-session`); with
   nothing live it lands on Roles as before;
2. `?mode=session` mounts the six panels (session-map, -activity,
   -attention, -agent, -cost and, 3.1.5.0 R3, -live: Agent, Activity and
   Attention as strips; the arrangement itself is
   tests/test_studio_session_live.py's), each with its about line;
3. the map draws only this harness's box: one card per session on it, its
   agent tree, the working nodes lit, the newest working agent selected (lit)
   and its session the chosen card; Cost speaks of that session (its model,
   its agents); Activity draws one lane per live agent of it and logs only
   this harness; Attention holds none of the member's rows; J / K stay on
   this harness;
4. `&session=<id>` chooses that session: the agent panel and Cost follow;
5. Alt+4 shows Fleet with both harnesses and the member's attention rows (no
   regression), Alt+1 (3.1.6.0 R6: Session is the first tab) comes back to Session;
6. `/studio`'s opener on the running Studio focuses the open page: on Fleet,
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
    ctx.check(f"nothing saved, nothing live: Roles as before, got {got.get('landing_none')!r} (mark {got.get('boot_none')!r})",
              str(got.get("landing_none")).startswith("Roles") and got.get("boot_none") == "")


@test
def test_mode_session_mounts_the_six_panels(ctx: Ctx):
    r, got = _driver("dash")
    _ran(ctx, r, got)
    ctx.check(f"the six panels once each, got {got.get('panels')}", got.get("panels") == [1, 1, 1, 1, 1, 1])
    ctx.check(f"each with its about line, got {got.get('abouts')}", got.get("abouts") == 6)


@test
def test_the_map_is_this_harness_with_the_working_agent_lit(ctx: Ctx):
    r, got = _driver("dash")
    _ran(ctx, r, got)
    ctx.check(f"one box, this harness's, got {got.get('boxes')}", got.get("boxes") == ["rolo@studio"])
    ctx.check(f"a card per session here and every agent of them, nothing else, got {got.get('cards')} cards, "
              f"{got.get('nodes')} of {got.get('want_nodes')} nodes, {got.get('foreign')} foreign",
              got.get("cards") == 2 and got.get("nodes") == got.get("want_nodes") and (got.get("nodes") or 0) >= 4 and got.get("foreign") == 0)
    ctx.check(f"the working nodes lit, got {got.get('working')}", (got.get("working") or 0) >= 2)
    sel = str(got.get("selected") or "")
    ctx.check(f"the newest working agent selected on enter, lit, got {sel} {got.get('selected_state')} {got.get('selected_lit')}",
              sel.startswith(f"{got.get('hid')}|{got.get('sid')}|") and got.get("selected_state") == "running" and got.get("selected_lit") == "working")
    ctx.check(f"its session is the chosen card, got {got.get('chosen_card')}", got.get("chosen_card") == got.get("sid"))


@test
def test_cost_activity_and_attention_are_this_session(ctx: Ctx):
    r, got = _driver("dash")
    _ran(ctx, r, got)
    ctx.check(f"Cost speaks of the chosen session, got {got.get('cost_session')} {got.get('cost_model')!r} {got.get('cost_agents')!r} {got.get('cost_usd')!r}",
              got.get("cost_session") == got.get("sid") and got.get("cost_model") == "qwen3-lead"
              and str(got.get("cost_agents")).endswith("of 3") and str(got.get("cost_usd")).startswith("$"))
    ctx.check(f"one lane per live agent of it, got {got.get('lanes')} for {got.get('want_lanes')}",
              got.get("lanes") == got.get("want_lanes") and (got.get("want_lanes") or 0) >= 2 and got.get("lane_keys_here") is True)
    ctx.check(f"the log is this harness's only, got {got.get('log_who')}", got.get("log_who") == ["rolo@studio"])
    ctx.check(f"none of the member's attention rows, got {got.get('attn_here')} (empty {got.get('attn_empty')})",
              got.get("attn_here") == 0 and got.get("attn_empty") == 1)
    ctx.check("J / K hop between this harness's agents only", got.get("hops_here") is True)


@test
def test_session_param_chooses_that_session(ctx: Ctx):
    from tests.helpers.studio_session import FAKE_SID
    r, got = _driver("dash")
    _ran(ctx, r, got)
    ctx.check(f"&session=<id>: the agent panel follows, got {got.get('deep_agent')}",
              str(got.get("deep_agent") or "").endswith(f"|{FAKE_SID}|main"))
    ctx.check(f"and Cost and the chosen card, got {got.get('deep_cost')} {got.get('deep_card')}",
              got.get("deep_cost") == FAKE_SID and got.get("deep_card") == FAKE_SID)


@test
def test_alt_keys_and_fleet_keeps_everything(ctx: Ctx):
    r, got = _driver("dash")
    _ran(ctx, r, got)
    ctx.check(f"Alt+4 shows Fleet, got {got.get('alt4')!r}", str(got.get("alt4")).startswith("Fleet"))
    ctx.check(f"Fleet still draws every harness, got {got.get('fleet_boxes')}", got.get("fleet_boxes") == ["rolo@studio", "kali@lab"])
    ctx.check(f"and the member's attention rows, got {got.get('fleet_attn')}", (got.get("fleet_attn") or 0) >= 2)
    ctx.check(f"Alt+1 comes back to Session, its map still one box, got {got.get('alt1')!r} {got.get('back_boxes')}",
              str(got.get("alt1")).startswith("Session") and got.get("back_boxes") == 1)


@test
def test_studio_focuses_the_page_already_open(ctx: Ctx):
    from tests.helpers.studio_session import FAKE_SID
    r, got = _driver("dash")
    _ran(ctx, r, got)
    ctx.check(f"/studio's opener on a running Studio: focused, one line, got {got.get('focus_how')} {got.get('focus_line')!r}",
              got.get("focus_how") == "focused" and str(got.get("focus_line")).startswith("Opened this session in the Studio page"))
    ctx.check(f"the open page (on Fleet) switches to Session on that session, no new tab, got {got.get('focus_tab')!r} {got.get('focus_agent')} {got.get('focus_tabs_opened')}",
              str(got.get("focus_tab")).startswith("Session") and f"|{FAKE_SID}|" in str(got.get("focus_agent")) and got.get("focus_tabs_opened") == 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
