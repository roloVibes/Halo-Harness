"""tests.test_agents_door -- Halo 3.6.0.2 R52: Agents has four views, `1 · Agents | 2 · Workflows | 3 · Map | 4 · Live`,
and every old door lands on one of them. lib/agentsDoor.ts is pure (no React, no store), so it runs in node through
tests/helpers/node_ts.py on every platform; the browser half is tests/test_studio_agents_live.py.

1. the views are four, `live` the fourth; `?mode=agents&view=live` (an old link, a bookmark, a saved section) opens Live,
   no longer the Map; every other old door lands where it did (cast, roles, team, orchestra, runs -> map; flows ->
   workflows; ?mode=roles|orchestra|team|fleet -> map), and Fleet's note is unchanged;
2. an old replay link (`view=live&replay=<id>` of 3.6.0.1 and before, `view=map&replay=`) opens the Map as it is now
   (3.6.0.3 B, Z7; routes/agents/store.ts drops the parameter: tests/test_studio_agents_live.py);
3. the live panels' old doors (`showFleetPanel`: fleet-activity, fleet-costs, ...) land on Agents -> Live, where a run is
   now watched; the Attention panel, an agent's rows and Local -> Hosts keep their homes;
4. R56 (decision 4): the opening tab (`openingView`): a door's tab, else 4 · Live while a session he has talked to is open
   (a turn or a message asked, busy or between turns; T10 never), else the tab used last.
Run: python -m tests.test_agents_door
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
DOOR = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "lib" / "agentsDoor.ts"


def door(body: str):
    from tests.helpers import node_ts
    js = f"const D = await import({json.dumps(DOOR.resolve().as_uri())});\nconst out = {{}};\n{body}\nconsole.log(JSON.stringify(out));"
    return node_ts.run(js)


@test
def test_four_views_and_the_old_live_door_opens_live(ctx: Ctx):
    got = door("""
out.views = D.AGENTS_VIEWS;
out.live = D.urlDoor('?mode=agents&view=live');
out.viewOf = ['live', 'cast', 'flows', 'runs', 'map', 'nope'].map((w) => D.viewOf(w));
out.old = Object.fromEntries(['cast', 'roles', 'team', 'orchestra', 'runs', 'flows'].map((v) => [v, D.urlDoor('?mode=agents&view=' + v).view]));
out.modes = Object.fromEntries(['roles', 'orchestra', 'team', 'fleet'].map((m) => [m, D.urlDoor('?mode=' + m)]));
out.note = D.FLEET_NOTE;
out.run = D.urlRun('?mode=agents&run=r-1');
""")
    ctx.check(f"four views, Live the fourth, got {got.get('views')}", got.get("views") == ["crew", "workflows", "map", "live"])
    ctx.check(f"?mode=agents&view=live opens Live, got {got.get('live')}", got.get("live") == {"view": "live", "word": "agents"})
    ctx.check(f"a view word of any age, got {got.get('viewOf')}", got.get("viewOf") == ["live", "map", "workflows", "map", "map", ""])
    ctx.check(f"every other old view as before, got {got.get('old')}",
              got.get("old") == {"cast": "map", "roles": "map", "team": "map", "orchestra": "map", "runs": "map", "flows": "workflows"})
    ctx.check(f"the old sections' words on the Map, got {got.get('modes')}",
              got.get("modes") == {w: {"view": "map", "word": w} for w in ("roles", "orchestra", "team", "fleet")})
    ctx.check(f"Fleet's note unchanged, got {got.get('note')!r}", got.get("note") == "Fleet left Halo in 3.5: this machine's sessions run on the Map")
    ctx.check(f"&run=<id> unchanged, got {got.get('run')!r}", got.get("run") == "r-1")


@test
def test_a_replay_link_stays_on_the_map(ctx: Ctx):
    got = door("""
out.old = D.urlDoor('?mode=agents&view=live&replay=elsewhere-1&at=22');
out.map = D.urlDoor('?mode=agents&view=map&replay=elsewhere-1');
out.bare = D.urlDoor('?mode=agents&replay=elsewhere-1');
""")
    ctx.check(f"halo replay open's old address lands on the Map, got {got.get('old')}", got.get("old") == {"view": "map", "word": "agents"})
    ctx.check(f"view=map&replay as before, got {got.get('map')}", got.get("map") == {"view": "map", "word": "agents"})
    ctx.check(f"a bare replay link on the Map, got {got.get('bare')}", got.get("bare") == {"view": "map", "word": "agents"})


@test
def test_the_live_panels_old_doors_land_on_live(ctx: Ctx):
    got = door("""
out.doors = Object.fromEntries(['fleet-activity', 'fleet-costs', 'fleet-map', 'fleet-runs', 'fleet-attention', 'fleet-agent',
  'fleet-ollama', 'ollama'].map((p) => [p, D.panelDoor(p)]));
""")
    ctx.check(f"each live panel's door, got {got.get('doors')}", got.get("doors") == {
        "fleet-activity": "live", "fleet-costs": "live", "fleet-map": "live", "fleet-runs": "live",
        "fleet-attention": "attention", "fleet-agent": "agent", "fleet-ollama": "local", "ollama": "local"})


@test
def test_agents_opens_on_live_while_a_session_he_talked_to_is_open(ctx: Ctx):
    got = door("""
const T10 = { parent: 'studio:1', turns: 0 }, between = { turns: 2, busy: false }, asked = { parent: 'studio:1', turns: 0, asked: true };
out.between = D.openingView('', [between], 'crew');
out.busy = D.openingView('', [{ turns: 1, busy: true }], 'workflows');
out.asked = D.openingView('', [asked], 'map');
out.t10 = D.openingView('', [T10], 'workflows');
out.terminal_no_turn = D.openingView('', [{ parent: 'main', turns: 0 }], 'map');
out.none = D.openingView('', [], 'crew');
out.door = D.openingView('workflows', [between], 'crew');
""")
    ctx.check(f"R56: a session between turns or busy opens Live, got {got.get('between')!r} {got.get('busy')!r}",
              got.get("between") == "live" and got.get("busy") == "live")
    ctx.check(f"a Studio-started session asked once (a /clear keeps it) counts, got {got.get('asked')!r}", got.get("asked") == "live")
    ctx.check(f"T10 (Studio-started, no message yet) and a session with no turn do not count: the tab used last, got "
              f"{got.get('t10')!r} {got.get('terminal_no_turn')!r}", got.get("t10") == "workflows" and got.get("terminal_no_turn") == "map")
    ctx.check(f"none open: the tab used last, got {got.get('none')!r}", got.get("none") == "crew")
    ctx.check(f"a door's tab wins, got {got.get('door')!r}", got.get("door") == "workflows")


@test
def test_a_page_load_on_agents_waits_for_the_session_list(ctx: Ctx):
    """The coordinator's ruling on R56 for a page that boots on Agents (no `view=`): the tab bar and ONE quiet line, no
    view, until the session list has been read once; then Live while a session he has talked to is open, else the tab
    used last; no answer after 1.5 s: the tab used last. A door's tab is drawn at once."""
    got = door("""
const talked = { turns: 1, busy: false };
out.unread = D.bootView('', false, [], 'crew', false);
out.unread_rows = D.bootView('', false, [talked], 'crew', false);
out.talked = D.bootView('', true, [talked], 'crew', false);
out.empty = D.bootView('', true, [], 'workflows', false);
out.timeout = D.bootView('', false, [], 'map', true);
out.door = D.bootView('crew', false, [], 'map', false);
out.line = D.READING_SESSIONS;
out.ms = D.OPEN_WAIT_MS;
out.last = [null, 'live', 'map', 'workflows', 'flows', 'crew', 'cast', ''].map((v) => D.lastViewOf(v));
""")
    ctx.check(f"no list read yet: no view (''), got {got.get('unread')!r} {got.get('unread_rows')!r}",
              got.get("unread") == "" and got.get("unread_rows") == "")
    ctx.check(f"the list read with a session he talked to: Live, got {got.get('talked')!r}", got.get("talked") == "live")
    ctx.check(f"the list read, nothing open: the tab used last, got {got.get('empty')!r}", got.get("empty") == "workflows")
    ctx.check(f"no answer within the wait: the tab used last, got {got.get('timeout')!r}", got.get("timeout") == "map")
    ctx.check(f"a door's tab at once, got {got.get('door')!r}", got.get("door") == "crew")
    ctx.check(f"the one quiet line, got {got.get('line')!r}", got.get("line") == "Reading the sessions.")
    ctx.check(f"the wait is 1.5 s, got {got.get('ms')!r}", got.get("ms") == 1500)
    ctx.check(f"lastViewOf (store.ts lastView) reads every tab back, Live too, got {got.get('last')!r}",
              got.get("last") == ["crew", "live", "map", "workflows", "workflows", "crew", "crew", "crew"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
