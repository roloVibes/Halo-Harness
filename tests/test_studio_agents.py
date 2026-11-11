"""tests.test_studio_agents -- Halo 3.3.16.0 R1 "Agents: one section" (the owner, 2026-11-09: "roles and orchestration
are almost the same ... all rolled into the new agents"): Team, Roles and Orchestra are one Studio section, Agents
(Alt+2), with its views -- Cast, Live, Workflows (3.4.0.0 D: Runs went) -- in headless Chrome through tests/helpers/studio_agents.py (skipped
without one), over a scratch home and a temp repo holding a live Orchestra run whose workers wait on a gate; no
model call:

1. Alt+2 opens Agents on Live (3.3.18.0: what runs now) with nothing else open (no inspector, no dialog, no help); six section tabs,
   Session Alt+1, Agents Alt+2, Local Alt+3 ... Settings Alt+6 (3.3.16.0 R2: Fleet folded in);
2. the doors land on their views: ?mode=roles -> Cast, roles&view=live -> Live, orchestra -> Live (3.4.0.0 D),
   agents&view=runs|live -> Live, agents -> Live (3.3.18.0); ?mode=team lands on Live with Team's one line, and not again;
3. C, L, W switch the views, R lands on Live (3.4.0.0 D; `?mode=agents&view=workflows` the board's door);
4. Live: every lane box says what it owns (the claim ledger's keys), a lane's Claims page lists its claims;
5. Live: the run's lead and its five lanes in the run's block, each with its number in its lane colour and its worktree;
6. Test this lineup: disabled on Auto with the Auto line; with a lineup of your own enabled, its card first;
3.3.16.0 R2 "the Fleet fold" (tests/helpers/studio_agents_fleet.py, this harness alone and one drafted mission):
7. ?mode=fleet lands on Live with the fleet scope on (this machine's node in its box) and Fleet's line once; the scope
   switch and F on the canvas;
8. the Attention chip on every view, its panel closed on load, opened by the chip, closed and opened by A;
9. Live's inspector: the fleet at a glance with nothing picked, a machine's summary (its People row, Edit rows) on a
   click, its Specs one page, Back;
10. the mission is a row of Runs' list and opens Runs' Mission panel; ?mode=fleet&mission=<id> lands on it.
Run: python -m tests.test_studio_agents
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.helpers import fleet_pack as _fleet_pack  # noqa: E402  (the fleet pack on: these drive its Studio doors)
_fleet_pack.on()

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


def _fleet(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_agents_fleet", why="Agents needs headless Chrome", cache=_RUN, key="fleet",
                      args=("fleet",), timeout=300)


@test
def test_alt2_opens_agents_on_live_with_nothing_else_open(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Alt+2 lands on Agents, on Live (3.3.18.0), got {got.get('alt2')!r}", got.get("alt2") == "live")
    ctx.check(f"six section tabs with their keys, got {got.get('tab_ids')}", got.get("tab_ids") == SIX)
    q = got.get("quiet") or {}
    ctx.check(f"no inspector, no dialog, no help; Live pressed, got {q}",
              q == {"inspector": "closed", "dialogs": 0, "help": False, "live_on": "true"})
    ctx.check(f"Live is drawn in Roles' room, got {got.get('cast_body')!r}", got.get("cast_body") == "roles")


@test
def test_the_doors_land_on_their_views(ctx: Ctx):
    got = _got(ctx)
    want = {"mode=roles": "cast", "mode=roles&view=live": "live", "mode=orchestra": "live",  # 3.4.0.0 D: Runs went
            "mode=agents&view=runs": "live", "mode=agents&view=live": "live", "mode=agents": "live",
            "mode=agents&view=workflows": "workflows"}  # 3.3.16.0 R3: the fourth view
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
    line for each word, and no Team route, panel or capture left (3.0.8.0 R2's Team section went with its board); 3.3.16.0
    R2: nor the Fleet section's view, map, tree or Ollama panel."""
    from halo_harness.studio import server as S
    from halo_harness.studio.modes import check, door_line
    ui = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"
    door = (ui / "lib" / "agentsDoor.ts").read_text(encoding="utf-8")
    ctx.check("roles lands on Cast, orchestra, team and fleet on Live (3.4.0.0 D); Team's, Runs' and Fleet's lines",
              'AGENTS_DOORS: Record<string, AgentsView> = { roles: "cast", orchestra: "live", team: "live", fleet: "live" }' in door
              and "Team's board is gone; a run on Live shows who owns what" in door
              and "Runs is gone: a goal runs on Live (Run a goal on its bar); a finished run is in History" in door
              and "Fleet is Agents -> Live now: machines in Setup -> Machines, models in Local" in door)
    ctx.check("STUDIO_MODES: the six, then the four old words as doors",
              S.STUDIO_SECTIONS == ("session", "agents", "local", "packs", "setup", "settings")
              and S.STUDIO_MODES == S.STUDIO_SECTIONS + ("roles", "orchestra", "team", "fleet"))
    ctx.check("each word is still a mode", all(check(w) == (w, "") for w in ("roles", "orchestra", "team", "agents", "fleet")))
    lines = {w: door_line(w) for w in ("roles", "orchestra", "team", "agents", "fleet", "local")}
    ctx.check(f"each old word's line names the new door; agents and local print none, got {lines}",
              lines["roles"].startswith("Roles is Agents -> Cast now (Alt+2 in Studio; halo studio --mode agents)")
              and lines["orchestra"].startswith("Orchestra is Agents -> Live now") and "Runs is gone" in lines["orchestra"]
              and lines["team"].startswith("Team is Agents -> Live now")
              and "Team's board is gone" in lines["team"] and lines["fleet"].startswith("Fleet is Agents -> Live now, the fleet scope on")
              and "Setup -> Machines" in lines["fleet"] and lines["agents"] == lines["local"] == "")
    repo = ui.parents[3]
    ctx.check("routes/team/, its help, its capture and its picture are gone",
              not (ui / "routes" / "team").exists() and not (ui / "routes" / "help-team.ts").exists()
              and not (repo / "tools" / "capture_team.py").exists() and not (repo / "docs" / "media" / "studio-team.png").exists())
    fleet = ui / "routes" / "fleet"
    gone = [n for n in ("Fleet.tsx", "Start.tsx", "Map.tsx", "MapNode.tsx", "MapChips.tsx", "MapMission.tsx", "MapSteer.tsx",
                        "MapTreeNode.tsx", "FleetTree.tsx", "layout.ts", "Ollama.tsx", "OllamaModels.tsx", "OllamaPlan.tsx",
                        "OllamaSteward.tsx", "ostore.ts") if (fleet / n).exists()]
    ctx.check(f"3.3.16.0 R2: the Fleet section's view, map, tree and Ollama panel are gone, left: {gone}", not gone)


@test
def test_fleet_lands_on_live_with_the_fleet_scope_and_its_switch(ctx: Ctx):
    got = _fleet(ctx)
    door = got.get("fleet_door") or ["", "", ""]
    ctx.check(f"?mode=fleet: Live, the fleet scope, Fleet's line, got {door}", door[0] == "live" and door[1] == "fleet"
              and str(door[2]).startswith("Fleet is Agents -> Live now: machines in Setup -> Machines, models in Local"))
    ctx.check(f"this machine is a node in its own box, got {got.get('machines_drawn')}", got.get("machines_drawn") == [["true", True]])
    ctx.check("the line the second time: none", got.get("again") is False)
    ctx.check(f"one harness: Live starts on this halo, got {got.get('default')!r}", got.get("default") == "here")
    ctx.check(f"the switch's fleet, then F on the canvas back to this halo, got {got.get('clicked')!r} {got.get('f_key')!r}",
              got.get("clicked") == "fleet" and got.get("f_key") == "here" and got.get("focus_off") == "off")


@test
def test_the_attention_chip_is_on_every_view_and_opens_the_queue(ctx: Ctx):
    got = _fleet(ctx)
    views = [got.get(v) for v in ("cast", "live", "workflows")]
    ctx.check(f"the chip on Cast, Live and Workflows, nothing waiting (not amber), its panel closed on load, got {views}",
              views == [["0", "", False]] * 3)
    ctx.check(f"the chip opens the queue (the panel id it always had), its count the queue's, got {got.get('chip_opened')!r}",
              got.get("chip_opened") == "fleet-attention" and got.get("rows_match") is True)
    ctx.check("A closes it and opens it again", got.get("a_closes") == "closed" and got.get("a_opens") == "open")


@test
def test_live_inspector_is_summary_first_by_what_is_picked(ctx: Ctx):
    got = _fleet(ctx)
    ctx.check(f"nothing picked: the fleet at a glance, got {got.get('none')}", got.get("none") == ["machines", "working", "waits on you", "spent today"])
    machine = got.get("machine") or [False, []]
    ctx.check(f"a machine: its People row and one Edit row per block, got {machine}",
              machine[0] is True and machine[1] == ["machine-block-specs", "machine-block-caps", "machine-block-sharing"])
    ctx.check("Specs is one page (the Who box, the card), Back returns, the canvas-level Back clears the pick",
              got.get("specs") == "page" and got.get("back") == "summary" and got.get("cleared") == "none")


@test
def test_a_mission_s_door_opens_its_panel_on_live(ctx: Ctx):
    """3.4.0.0 D: Runs' mission rows went with Runs; `?mode=fleet&mission=<id>` opens the Mission panel on Live, and M."""
    got = _fleet(ctx)
    ctx.check(f"?mode=fleet&mission=<id>: Live, the Mission panel on it, got {got.get('mission_door')!r}", got.get("mission_door") == "Chart the basket prices across the fleet")
    ctx.check(f"M opens the Mission panel on Live, got {got.get('m_key')!r}", got.get("m_key") == "mission")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio agents tests"))
