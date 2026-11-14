"""tests.test_studio_agents -- Halo 3.3.16.0 R1 "Agents: one section" (the owner, 2026-11-09: "roles and orchestration
are almost the same ... all rolled into the new agents"): Team, Roles and Orchestra are one Studio section, Agents
(Alt+2), with its views -- Cast, Live, Workflows (3.4.0.0 D: Runs went) -- in headless Chrome through tests/helpers/studio_agents.py (skipped
without one), over a scratch home and a temp repo holding a live Orchestra run whose workers wait on a gate; no
model call:

1. Alt+2 opens Agents on Live (3.3.18.0: what runs now) with nothing else open (no inspector, no dialog, no help); six section tabs,
   Session Alt+1, Agents Alt+2, Local Alt+3 ... Settings Alt+6;
2. the doors land on their views: ?mode=roles -> Cast, roles&view=live -> Live, orchestra -> Live (3.4.0.0 D),
   agents&view=runs|live -> Live, agents -> Live (3.3.18.0); ?mode=team lands on Live with Team's one line, and not again;
3. C, L, W switch the views, R lands on Live (3.4.0.0 D; `?mode=agents&view=workflows` the board's door);
4. Live: every lane box says what it owns (the claim ledger's keys), a lane's Claims page lists its claims;
5. Live: the run's lead and its five lanes in the run's block, each with its number in its lane colour and its worktree;
6. Test this lineup: disabled on Auto with the Auto line; with a lineup of your own enabled, its card first;
3.3.16.0 R2 (tests/helpers/studio_agents_live.py, this harness alone):
7. the Attention chip on every view, its panel closed on load, opened by the chip, closed and opened by A;
8. Live's inspector: this halo at a glance with nothing picked.
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
SIX = ["session:Alt+1", "agents:Alt+2", "local:Alt+3", "packs:Alt+4", "setup:Alt+5", "settings:Alt+6"]


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_agents", why="Agents needs headless Chrome", cache=_RUN,
                      args=("agents",), timeout=420)


def _live(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_agents_live", why="Agents needs headless Chrome", cache=_RUN, key="live",
                      args=("live",), timeout=300)


@test
def test_alt2_opens_agents_on_the_agents_tab_with_nothing_else_open(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Alt+2 lands on Agents, on 1 · Agents (3.6.0.0 R1: the new tab is first and the default), got {got.get('alt2')!r}",
              got.get("alt2") == "crew")
    ctx.check(f"six section tabs with their keys, got {got.get('tab_ids')}", got.get("tab_ids") == SIX)
    q = got.get("quiet") or {}
    ctx.check(f"no inspector, no dialog, no help; 1 · Agents pressed, got {q}",
              q == {"inspector": "closed", "dialogs": 0, "help": False, "live_on": "true"})
    ctx.check(f"the Agents tab is drawn in its own room, got {got.get('cast_body')!r}", got.get("cast_body") == "crew")


@test
def test_the_doors_land_on_their_views(ctx: Ctx):
    got = _got(ctx)
    want = {"mode=roles": "cast", "mode=roles&view=live": "live", "mode=orchestra": "live",  # 3.4.0.0 D: Runs went
            "mode=agents&view=runs": "live", "mode=agents&view=live": "live", "mode=agents": "live",
            "mode=agents&view=workflows": "workflows", "mode=agents&view=crew": "crew"}  # 3.3.16.0 R3; 3.6.0.0 R1: the Agents tab
    seen = {k: got.get(k) for k in want}
    ctx.check(f"each door's view, got {seen}", seen == want)
    first = got.get("first") or ["", ""]
    ctx.check(f"?mode=team: Live with Team's line, got {first}",
              first[0] == "live" and first[1].startswith("Team's board is gone; a run on Live shows who owns what"))
    ctx.check(f"the second time: Live, no line, got {got.get('again')}", got.get("again") == ["live", False])


@test
def test_c_r_l_switch_the_views(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"R Live (3.4.0.0 D), W Workflows, L Live, C Cast, got {[got.get(k) for k in 'rwlc']}",
              [got.get(k) for k in "rwlc"] == ["live", "workflows", "live", "cast"])  # 3.3.16.0 R3: W the board
    ctx.check(f"1: the Agents tab (3.6.0.0 R1), got {got.get('1')!r}", got.get("1") == "crew")


@test
def test_a_lane_says_what_it_owns_and_its_claims(ctx: Ctx):
    got = _got(ctx)
    owns = got.get("owns") or []
    ctx.check(f"five owns lines, each the lane's claim key, got {owns}",
              len(owns) == 5 and all(o.startswith("OWNS") and "basket.py#" in o for o in owns))  # 3.4.0.0 D: a row of each lane box
    claims = got.get("claims") or []
    ctx.check(f"lane 1's Claims page: its claim, held by lane:1, claimed, got {claims}",
              len(claims) == 1 and claims[0][0] == "lane:1" and claims[0][1] == "claimed" and "basket.py#add_item" in claims[0][2])


@test
def test_live_draws_the_run_s_lanes_under_its_lead(ctx: Ctx):
    got = _got(ctx)
    lanes = got.get("lanes") or []
    ctx.check(f"five lane nodes, numbered, in their lane colours, each with its worktree, got {lanes}",
              [l[0] for l in lanes] == [1, 2, 3, 4, 5] and [l[1] for l in lanes] == ["0", "1", "2", "3", "4"]
              and all(str(l[2]).endswith(f"worker-{l[0]}") for l in lanes))
    ctx.check(f"the lead is the run, got {got.get('lead')!r} for {got.get('run')!r}", bool(got.get("run")) and got.get("lead") == got.get("run"))
    block = got.get("block") or ["", 0]
    ctx.check(f"the lanes are in the run's block under the lead (3.4.0.0 D), got {block}", str(block[0]) == f"run:{got.get('run')}:block" and block[1] == 5)


@test
def test_the_old_words_are_doors_and_team_left_nothing_behind(ctx: Ctx):
    """No Chrome: the page's doors (lib/agentsDoor.ts), STUDIO_MODES (the six, then the four words), the terminal's
    line for each word, and no Team route, panel or capture left (3.0.8.0 R2's Team section went with its board); 3.5.0.0:
    `fleet` is no door (Fleet left)."""
    from halo_harness.studio import server as S
    from halo_harness.studio.modes import check, door_line
    ui = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"
    door = (ui / "lib" / "agentsDoor.ts").read_text(encoding="utf-8")
    ctx.check("roles lands on Cast, orchestra and team on Live (3.4.0.0 D); Team's and Runs' lines",
              'AGENTS_DOORS: Record<string, AgentsView> = { roles: "cast", orchestra: "live", team: "live" }' in door
              and "Team's board is gone; a run on Live shows who owns what" in door
              and "Runs is gone: a goal runs on Live (Run a goal on its bar); a finished run is in History" in door
              and "fleet" not in door.lower())
    ctx.check("STUDIO_MODES: the six, then the three old words as doors",
              S.STUDIO_SECTIONS == ("session", "agents", "local", "packs", "setup", "settings")
              and S.STUDIO_MODES == S.STUDIO_SECTIONS + ("roles", "orchestra", "team"))
    ctx.check("each word is still a mode", all(check(w) == (w, "") for w in ("roles", "orchestra", "team", "agents")))
    lines = {w: door_line(w) for w in ("roles", "orchestra", "team", "agents", "fleet", "local")}
    ctx.check(f"each old word's line names the new door; agents and local print none, got {lines}",
              lines["roles"].startswith("Roles is Agents -> Cast now (Alt+2 in Studio; halo studio --mode agents)")
              and lines["orchestra"].startswith("Orchestra is Agents -> Live now") and "Runs is gone" in lines["orchestra"]
              and lines["team"].startswith("Team is Agents -> Live now")
              and "Team's board is gone" in lines["team"] and lines["fleet"] == lines["agents"] == lines["local"] == "")
    repo = ui.parents[3]
    ctx.check("routes/team/, its help, its capture and its picture are gone",
              not (ui / "routes" / "team").exists() and not (ui / "routes" / "help-team.ts").exists()
              and not (repo / "tools" / "capture_team.py").exists() and not (repo / "docs" / "media" / "studio-team.png").exists())
    live = ui / "routes" / "fleet"
    gone = [n for n in ("Mission.tsx", "Pair.tsx", "People.tsx", "Capabilities.tsx", "Digest.tsx", "Health.tsx", "mstore.ts",
                        "caps.ts") if (live / n).exists()]
    gone += [n for n in ("FleetGlance.tsx", "MachineNode.tsx", "MachineSummary.tsx", "PartCard.tsx", "MissionParts.tsx")
             if (ui / "routes" / "agents" / "live" / n).exists()]
    ctx.check(f"3.5.0.0: Fleet's pieces are gone, left: {gone}", not gone and not (ui / "routes" / "setup" / "Machines.tsx").exists())


@test
def test_the_attention_chip_is_on_every_view_and_opens_the_queue(ctx: Ctx):
    got = _live(ctx)
    views = [got.get(v) for v in ("cast", "live", "workflows")]
    ctx.check(f"the chip on Cast, Live and Workflows, nothing waiting (not amber), its panel closed on load, got {views}",
              views == [["0", "", False]] * 3)
    ctx.check(f"the chip opens the queue (the panel id it always had), its count the queue's, got {got.get('chip_opened')!r}",
              got.get("chip_opened") == "fleet-attention" and got.get("rows_match") is True)
    ctx.check("A closes it and opens it again", got.get("a_closes") == "closed" and got.get("a_opens") == "open")


@test
def test_live_inspector_with_nothing_picked_is_this_halo_at_a_glance(ctx: Ctx):
    got = _live(ctx)
    ctx.check(f"nothing picked: this halo at a glance, got {got.get('none')}", got.get("none") == ["working", "waits on you", "spent today"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio agents tests"))
