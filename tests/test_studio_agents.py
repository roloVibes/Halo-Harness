"""tests.test_studio_agents -- Halo 3.3.16.0 R1 "Agents: one section" (the owner, 2026-11-09: "roles and orchestration
are almost the same ... all rolled into the new agents"): Team, Roles and Orchestra are one Studio section, Agents
(Alt+2), with three views -- Cast, Runs, Live -- in headless Chrome through tests/helpers/studio_agents.py (skipped
without one), over a scratch home and a temp repo holding a live Orchestra run whose workers wait on a gate; no
model call:

1. Alt+2 opens Agents on Cast with nothing else open (no inspector, no dialog, no help); seven section tabs,
   Session Alt+1 ... Local Alt+7;
2. the doors land on their views: ?mode=roles -> Cast, roles&view=live -> Live, orchestra -> Runs,
   agents&view=runs|live, agents -> Cast; ?mode=team lands on Runs with Team's one line, and not again;
3. C, R, L switch the views;
4. Runs: every lane says what it owns (the claim ledger's keys), a focused lane lists its claims (holder, state);
5. Live: the run's lead and its five lanes under it, each with its number in its lane colour and its worktree;
6. Test this lineup: disabled on Auto with the Auto line; with a lineup of your own enabled, its card first.
Run: python -m tests.test_studio_agents
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()  # the non-Chrome test reads the mode words: never the real home

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}
SEVEN = ["session:Alt+1", "agents:Alt+2", "fleet:Alt+3", "packs:Alt+4", "setup:Alt+5", "settings:Alt+6", "local:Alt+7"]


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_agents", why="Agents needs headless Chrome", cache=_RUN,
                      args=("agents",), timeout=420)


@test
def test_alt2_opens_agents_on_cast_with_nothing_else_open(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Alt+2 lands on Agents, on Cast, got {got.get('alt2')!r}", got.get("alt2") == "cast")
    ctx.check(f"seven section tabs with their keys, got {got.get('tab_ids')}", got.get("tab_ids") == SEVEN)
    q = got.get("quiet") or {}
    ctx.check(f"no inspector, no dialog, no help; Cast pressed, got {q}",
              q == {"inspector": "closed", "dialogs": 0, "help": False, "cast_on": "true"})
    ctx.check(f"Cast is Roles' room (its Start view or its canvas), got {got.get('cast_body')!r}", got.get("cast_body") == "roles")


@test
def test_the_doors_land_on_their_views(ctx: Ctx):
    got = _got(ctx)
    want = {"mode=roles": "cast", "mode=roles&view=live": "live", "mode=orchestra": "runs",
            "mode=agents&view=runs": "runs", "mode=agents&view=live": "live", "mode=agents": "cast"}
    seen = {k: got.get(k) for k in want}
    ctx.check(f"each door's view, got {seen}", seen == want)
    first = got.get("first") or ["", ""]
    ctx.check(f"?mode=team: Runs with Team's line, got {first}",
              first[0] == "runs" and first[1].startswith("Team's board is gone; a run's plan shows who owns what"))
    ctx.check(f"the second time: Runs, no line, got {got.get('again')}", got.get("again") == ["runs", False])


@test
def test_c_r_l_switch_the_views(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"R Runs, L Live, C Cast, got {[got.get(k) for k in 'rlc']}", [got.get(k) for k in "rlc"] == ["runs", "live", "cast"])


@test
def test_a_lane_says_what_it_owns_and_its_claims(ctx: Ctx):
    got = _got(ctx)
    owns = got.get("owns") or []
    ctx.check(f"five owns lines, each the lane's claim key, got {owns}",
              len(owns) == 5 and all(o.startswith("OWNS") and "basket.py#" in o for o in owns))
    claims = got.get("claims") or []
    ctx.check(f"lane 1 focused: its claim, held by lane:1, claimed, got {claims}",
              len(claims) == 1 and claims[0][0] == "lane:1" and claims[0][1] == "claimed" and "basket.py#add_item" in claims[0][2])


@test
def test_live_draws_the_run_s_lanes_under_its_lead(ctx: Ctx):
    got = _got(ctx)
    lanes = got.get("lanes") or []
    ctx.check(f"five lane nodes, numbered, in their lane colours, each with its worktree, got {lanes}",
              [l[0] for l in lanes] == [1, 2, 3, 4, 5] and [l[1] for l in lanes] == ["0", "1", "2", "3", "4"]
              and all(str(l[2]).endswith(f"worker-{l[0]}") for l in lanes))
    ctx.check(f"the lead is the run, got {got.get('lead')!r} for {got.get('run')!r}", bool(got.get("run")) and got.get("lead") == got.get("run"))
    ctx.check(f"each lane hangs under the lead, got {got.get('edges')} {got.get('under_lead')}", got.get("edges") == 5 and got.get("under_lead") is True)


@test
def test_test_this_lineup_waits_on_auto_and_shows_its_card_first(ctx: Ctx):
    got = _got(ctx)
    auto = got.get("auto") or [None, ""]
    ctx.check(f"on Auto: disabled, the Auto line beside it, got {auto}",
              auto[0] is True and str(auto[1]).startswith("Your lineup is Auto: pick or build a lineup in Agents -> Cast first"))
    ctx.check("with a lineup of your own: enabled", got.get("enabled") == "enabled")
    card = str(got.get("card") or "")
    ctx.check(f"its card: the run, the lineup, the cost, what it writes, got {card[:120]!r}",
              card.startswith("The guided first run (halo start)") and "halo-dev-cycle" in card and "Estimated cost:" in card and "Writes:" in card)
    ctx.check("the card comes first, Run after it", got.get("card_first") is True)


@test
def test_the_old_words_are_doors_and_team_left_nothing_behind(ctx: Ctx):
    """No Chrome: the page's doors (lib/agentsDoor.ts), STUDIO_MODES (the seven, then the three words), the terminal's
    line for each word, and no Team route, panel or capture left (3.0.8.0 R2's Team section went with its board)."""
    from halo_harness.studio import server as S
    from halo_harness.studio.modes import check, door_line
    ui = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"
    door = (ui / "lib" / "agentsDoor.ts").read_text(encoding="utf-8")
    ctx.check("roles lands on Cast, orchestra and team on Runs; Team's line",
              'AGENTS_DOORS: Record<string, AgentsView> = { roles: "cast", orchestra: "runs", team: "runs" }' in door
              and "Team's board is gone; a run's plan shows who owns what" in door)
    ctx.check("STUDIO_MODES: the seven, then the three old words as doors",
              S.STUDIO_SECTIONS == ("session", "agents", "fleet", "packs", "setup", "settings", "local")
              and S.STUDIO_MODES == S.STUDIO_SECTIONS + ("roles", "orchestra", "team"))
    ctx.check("each word is still a mode", all(check(w) == (w, "") for w in ("roles", "orchestra", "team", "agents")))
    lines = {w: door_line(w) for w in ("roles", "orchestra", "team", "agents", "fleet")}
    ctx.check(f"each old word's line names the new door; agents and fleet print none, got {lines}",
              lines["roles"].startswith("Roles is Agents -> Cast now (Alt+2 in Studio; halo studio --mode agents)")
              and lines["orchestra"].startswith("Orchestra is Agents -> Runs now") and lines["team"].startswith("Team is Agents -> Runs now")
              and "Team's board is gone" in lines["team"] and lines["agents"] == lines["fleet"] == "")
    repo = ui.parents[3]
    ctx.check("routes/team/, its help, its capture and its picture are gone",
              not (ui / "routes" / "team").exists() and not (ui / "routes" / "help-team.ts").exists()
              and not (repo / "tools" / "capture_team.py").exists() and not (repo / "docs" / "media" / "studio-team.png").exists())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio agents tests"))
