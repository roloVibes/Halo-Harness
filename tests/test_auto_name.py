"""tests.test_auto_name -- Halo 3.6.0.5 (a): the name Auto. `auto`, `starter` and no map set are ONE map, the default,
read through one Python test (crew/store.py `is_auto`, `find`'s alias) and named "Auto (the default)" everywhere a
person reads it; a file of his named auto or starter never runs, and no new map is saved under either name.
Run: python -m tests.test_auto_name
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.crew_rig import CrewRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

SEVEN = ["planner", "researcher", "coder", "reviewer", "writer", "media-reader", "ops"]
W1 = "Map: Auto (the default: main picks who works on each task, and a model for each one)"
W5 = "New sessions run on Auto (the default); no map of yours is set."


def _config(rig, **crew) -> None:
    cfg = rig.state / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    if crew:
        data["crew"] = crew
    else:
        data.pop("crew", None)
    cfg.write_text(json.dumps(data), encoding="utf-8")


def _his_map(rig, name: str, box: str = "x") -> Path:
    from halo_harness.crew import store
    p = rig.state / "crew" / "maps" / f"{name}.yaml"
    store.write_text(p, store.dump({"format": "map/1", "name": name, "main": {"agent": "main"},
                                    "boxes": [{"id": box, "agent": "coder"}], "lines": []}))
    return p


# --- entry 1: one default, `auto`, read for every name of it ------------------------------------------------------

@test
def test_default_is_auto_with_source_default(ctx: Ctx):
    with CrewRig() as rig:
        from halo_harness.crew import compile as C
        got = C.in_use(None, rig.proj)
        ctx.check(f"none set: ('auto', 'default'), got {got}", got == ("auto", "default"))
        c, lines = C.for_session(None, cwd=rig.proj)
        ctx.check(f"the session's map is auto, source default, the shipped auto.yaml, got {c and (c.name, c.source, c.path)} {lines}",
                  c is not None and c.name == "auto" and c.source == "default"
                  and Path(c.path).as_posix().endswith("templates/crew/maps/auto.yaml"))
        ctx.check(f"its seven agent targets, got {c and c.agent_targets()}", c is not None and sorted(c.agent_targets()) == sorted(SEVEN))


@test
def test_starter_or_auto_in_flag_config_goal_or_use_runs_as_auto(ctx: Ctx):
    with CrewRig() as rig:
        from halo_harness.crew import compile as C
        from halo_harness.crew import in_use as U
        from halo_harness.crew.map_control import PlainMap, control_for
        for f in ("starter", "Starter", "AUTO", " auto "):
            ctx.check(f"--map {f!r} is the default, got {C.in_use(f, rig.proj)}", C.in_use(f, rig.proj) == ("auto", "default"))
        _config(rig, map="starter")
        ctx.check(f"config crew.map starter is the default, got {C.in_use(None, rig.proj)}", C.in_use(None, rig.proj) == ("auto", "default"))
        _config(rig)
        ctl = control_for(C.for_session("starter", cwd=rig.proj)[0])
        ctx.check(f"--map starter runs a PlainMap named auto, got {type(ctl).__name__}",
                  isinstance(ctl, PlainMap) and ctl.map.name == "auto")
        ctx.check("halo local reads `starter` as the default: lanes('starter') == lanes(None)",
                  U.lanes("starter", cwd=rig.proj) == U.lanes(None, cwd=rig.proj))


@test
def test_alias_only_without_scope(ctx: Ctx):
    with CrewRig() as rig:
        from halo_harness.crew import compile as C
        from halo_harness.crew import store
        mine = _his_map(rig, "starter")
        got = store.find("map", "starter", state_dir=rig.state)
        ctx.check(f"no scope: the shipped auto.yaml, scope starter, got {got}",
                  got is not None and got[0] == store.SHIPPED / "maps" / "auto.yaml" and got[1] == "starter")
        got = store.find("map", "starter", state_dir=rig.state, scope="yours")
        ctx.check(f"scope yours: his own old file, got {got}", got is not None and got[0] == mine)
        ctx.check("scope yours has no auto.yaml", store.find("map", "auto", state_dir=rig.state, scope="yours") is None)
        c = C.compile_map("starter", cwd=rig.proj)
        ctx.check(f"compile_map('starter') runs the seven, not his box x, got {c.agent_targets()}", sorted(c.agent_targets()) == sorted(SEVEN))
        for flag in (None, "starter"):
            c = C.for_session(flag, cwd=rig.proj)[0]
            ctx.check(f"a session (flag {flag!r}) runs the seven, never his file, got {c and c.agent_targets()}",
                      c is not None and sorted(c.agent_targets()) == sorted(SEVEN) and c.path != str(mine))


@test
def test_use_starter_takes_the_key_out(ctx: Ctx):
    with CrewRig() as rig:
        from halo_harness.crew import changes_map
        for v in ("starter", "auto", None):
            _config(rig, map="ship-it")
            text = changes_map.config_text(v)
            crew = json.loads(text).get("crew") or {}
            ctx.check(f"use {v!r}: no crew.map left, got {crew}", "map" not in crew)


@test
def test_get_map_starter_without_scope_is_auto(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        st, m = rig.api("GET", "crew/map/starter")
        ctx.check(f"GET crew/map/starter: the auto map, in use, got {st} {(m.get('map') or {}).get('name')} {m.get('scope')} {m.get('in_use')}",
                  st == 200 and m["map"]["name"] == "auto" and m.get("scope") == "starter" and m.get("in_use") is True)
        _his_map(rig, "starter")
        st, m = rig.api("GET", "crew/map/starter")
        ctx.check(f"his old starter.yaml present: the unscoped read is still Auto, got {st} {sorted(m.get('boxes') or {})}",
                  st == 200 and m["map"]["name"] == "auto" and "x" not in (m.get("boxes") or {}))
        st, r = rig.api("GET", "crew/maps")
        rows = {(x["name"], x["scope"]): x["in_use"] for x in r.get("maps") or []}
        ctx.check(f"Studio's list: Auto (shipped) in use, his old starter.yaml listed beside it, never in use, got {rows}",
                  rows.get(("auto", "starter")) is True and rows.get(("starter", "yours")) is False)
        st, m = rig.api("GET", "crew/map/starter?scope=yours")
        ctx.check(f"?scope=yours: his file (box x), got {st} {sorted(m.get('boxes') or {})}",
                  st == 200 and sorted(m.get("boxes") or {}) == ["x"])


# --- entry 2: the terminal says Auto -------------------------------------------------------------------------------

class _Tc:
    is_map = True

    def __init__(self, c):
        self.map, self.map_name = c, c.name


class _Session:
    def __init__(self, c):
        self.team_control = _Tc(c)


def _out(fn, *a) -> "tuple":
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(*a)
    return rc, buf.getvalue()


@test
def test_words_status(ctx: Ctx):
    with CrewRig() as rig:
        from halo_harness.commands.builtins import _map_line
        from halo_harness.crew import compile as C
        ctx.check(f"/status with none set: W1, got {_map_line(None)!r}", _map_line(None) == W1)
        s = _Session(C.for_session(None, cwd=rig.proj)[0])
        ctx.check(f"/status in a session on the default: W1, got {_map_line(s)!r}", _map_line(s) == W1)


@test
def test_words_doctor(ctx: Ctx):
    with CrewRig():
        from halo_harness import doctor
        got = doctor._check_lineup()
        ctx.check(f"doctor: W2, got {got!r}", got.endswith(" Map: Auto (the default: main picks who works on each task); "
                                                            "halo maps use <name> changes it, halo maps list shows them"))


@test
def test_words_setup(ctx: Ctx):
    with CrewRig():
        from halo_harness import setup_cli
        _rc, out = _out(setup_cli._print_map_in_use)
        ctx.check(f"halo setup: W3, got {out!r}", out.strip() == "map: Auto (the default)")


@test
def test_words_maps_list(ctx: Ctx):
    with CrewRig() as rig:
        from halo_harness.maps_cli import cmd_maps
        _rc, out = _out(cmd_maps, ["list"])
        rows = out.rstrip().splitlines()
        ctx.check(f"first row auto, default, what it does; last line Auto, got {rows}",
                  rows[0].split() == ["*", "auto", "default", "main", "picks", "who", "works", "on", "each", "task"]
                  and rows[-1] == "in use: Auto (the default)")  # the scope column's words are batch04's
        _config(rig, map="ship-it")
        _rc, out = _out(cmd_maps, ["list"])
        rows = out.rstrip().splitlines()
        ctx.check(f"crew.map ship-it: its line as today, got {rows[-1]!r}",
                  rows[-1] == "in use: ship-it (config)" and rows[0].startswith("  auto "))
        _config(rig)
        _his_map(rig, "auto")
        _his_map(rig, "starter")
        _rc, out = _out(cmd_maps, ["list"])
        rows = out.rstrip().splitlines()
        marked = [r for r in rows if r.startswith("*")]
        mine = [r.split()[:2] for r in rows if " yours " in r]
        ctx.check(f"his old auto and starter files listed unmarked under their names, only the default marked, got {rows}",
                  len(marked) == 1 and marked[0] == rows[0] and sorted(mine) == [["auto", "yours"], ["starter", "yours"]])


@test
def test_words_use_off(ctx: Ctx):
    with CrewRig() as rig:
        from halo_harness.maps_cli import cmd_maps
        for argv in (["use", "--off"], ["use", "starter"], ["use", "auto"]):
            _config(rig, map="ship-it")
            _rc, out = _out(cmd_maps, argv)
            crew = json.loads((rig.state / "config.json").read_text(encoding="utf-8")).get("crew") or {}
            ctx.check(f"{argv}: W5 and no crew.map, got {out!r} {crew}", out.startswith(W5[:-1]) and "map" not in crew
                      and "starter" not in out)
        _rc, out = _out(cmd_maps, ["use", "--help"])
        ctx.check("--off's help: goes back to Auto (the default)", "goes back to Auto (the default)" in " ".join(out.split()))


@test
def test_words_problem_head(ctx: Ctx):
    with CrewRig() as rig:
        from halo_harness.crew import compile as C
        from halo_harness.crew import store
        store.write_text(rig.state / "crew" / "maps" / "gap.yaml", store.dump(
            {"format": "map/1", "name": "gap", "main": {"agent": "main"}, "boxes": [{"id": "a", "agent": "nobody"}],
             "lines": [{"from": "main", "to": "a"}]}))
        c, lines = C.for_session("gap", cwd=rig.proj)
        ctx.check(f"W6 with the map's name, got {lines[:1]}",
                  lines and lines[0] == "halo: the map gap has a problem, so this session runs on Auto (the default):"
                  and c is not None and c.name == "auto")


@test
def test_words_preflight(ctx: Ctx):
    with CrewRig() as rig:
        from halo_harness.crew import preflight
        got = preflight.run_problems("nosuch", cwd=rig.proj)
        ctx.check(f"the fix names auto for the default, got {[g['fix'] for g in got]}",
                  any(g["fix"] == "name one that exists (halo maps list), or auto for the default" for g in got))


@test
def test_words_old_team(ctx: Ctx):
    with CrewRig() as rig:
        from halo_harness.crew import old_files
        cfg = rig.state / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        cfg.write_text(json.dumps({**data, "team": "auto"}), encoding="utf-8")
        ctx.check(f"team: auto: W8, got {old_files.team_line()!r}", old_files.team_line() == (
            "Your config sets team: auto, which no session reads any more: lineups are gone; Auto is the default, so "
            "team: auto needs nothing. Clear the old key with halo config set team null."))
        cfg.write_text(json.dumps({**data, "team": "tiers"}), encoding="utf-8")
        ctx.check(f"team: tiers keeps today's line, got {old_files.team_line()!r}",
                  old_files.team_line().startswith("Your config sets team: tiers, which no session reads any more (lineups are gone): "))


@test
def test_words_team_preview(ctx: Ctx):
    from halo_harness.tui.dialogs import team_preview
    ctx.check(f"W9, got {team_preview.HEADER_TEXT[:70]!r}",
              team_preview.HEADER_TEXT.startswith("Halo runs Auto (the default) unless you pick a map of your own: main hands each "))


@test
def test_words_map_facts(ctx: Ctx):
    with CrewRig() as rig:
        from halo_harness.crew import map_facts as F
        for a in (("starter", False), ("auto", True), (None,)):
            ctx.check(f"words_of{a} is Auto (the default), got {F.words_of(*a)!r}", F.words_of(*a) == "Auto (the default)")
        ctx.check(f"name_the_map(None), got {F.name_the_map(None)!r}", F.name_the_map(None) == (
            "Name the map: this session runs on Auto (the default), where main chooses who works. Pass a new name in "
            "args.map to make a map that routes."))
        _config(rig, map="starter")
        ctx.check(f"config crew.map starter: next_map() names none, got {F.next_map()}", F.next_map()[0] is None)


@test
def test_words_studio_show(ctx: Ctx):
    with CrewRig() as rig:
        from halo_harness.crew.tools_show import studio_show
        got = studio_show({"what": "map", "name": "auto"}, {"cwd": rig.proj, "state_dir": None})["text"]
        ctx.check(f"MAP Auto (the default) -- new sessions use it:, got {got.splitlines()[0]!r}",
                  got.splitlines()[0] == "MAP Auto (the default) -- new sessions use it:")


@test
def test_words_setup_team(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        for name in ("auto", "starter"):
            _config(rig, map="ship-it")
            st, r = rig.api("POST", "setup/team", {"map": name})
            crew = json.loads((rig.state / "config.json").read_text(encoding="utf-8")).get("crew") or {}
            ctx.check(f"{name}: the Auto receipt, no crew.map, got {st} {r.get('lines')} {crew}",
                      st == 200 and r.get("lines") == ["crew.map unset: new sessions run on Auto (the default)"] and "map" not in crew)
        st, r = rig.api("POST", "setup/team", {"map": "ship-it"})
        ctx.check(f"ship-it: today's receipt, got {st} {r.get('lines')}",
                  st == 200 and r.get("lines") == ["crew.map = ship-it: new sessions run on the map ship-it"])


# --- entry 3: never a map of his under a default's name ------------------------------------------------------------

def _w16(name: str) -> str:
    return f"{name} is a name of the default (Auto); give your map another name."


@test
def test_new_map_named_auto_or_starter_refused(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        from halo_harness.crew import store, tools_map
        maps = rig.state / "crew" / "maps"
        for name in ("starter", "auto"):
            st, r = rig.api("PUT", f"crew/map/{name}", {"map": {"main": {"agent": "main"}, "boxes": [], "lines": []}})
            ctx.check(f"PUT {name}: 422 W16, got {st} {r.get('error')}", st == 422 and r.get("error") == _w16(name))
        ctx.check("no file written", not maps.is_dir() or not list(maps.iterdir()))
        try:
            store.own_copy("map", "ship-it", as_name="Starter", state_dir=rig.state)
            said = ""
        except ValueError as e:
            said = str(e)
        ctx.check(f"own_copy --as Starter: W16, got {said!r}", said == _w16("Starter"))
        got = tools_map.TOOLS["map_box_add"][0]({"map": "starter", "kind": "agent", "ref": "coder"},
                                                  {"cwd": rig.proj, "state_dir": rig.state})
        ctx.check(f"the Builder naming starter: W16, no row, got {got}", got == {"text": _w16("starter"), "rows": []})
        ctx.check("no file written by any of them", not maps.is_dir() or not list(maps.iterdir()))
        for t in (_w16("starter").replace("starter", "", 1), _w16("auto").replace("auto", "", 1)):
            ctx.check(f"the words hold no starter and auto only in (Auto): {t!r}",
                      "starter" not in t and t.lower().count("auto") == t.count("(Auto)"))


# --- batch 2: Auto's Map tab (M1), the switch's off receipt, one in_use per row, the status row's map_agents ---------

def _agent(rig, name: str) -> None:
    from halo_harness.crew import store
    store.write_text(store.path_for("agent", name, state_dir=rig.state), store.dump(
        {"format": "agent/1", "name": name, "does": "Helps.", "model": "auto", "uses": ["read"], "careful": "ask-changes"}))


@test
def test_m1_hand_to_is_what_a_new_session_gets(ctx: Ctx):
    """A22, 3.6.0.10 M9: M1's {names} are `hand_to` on GET crew/map/auto only: the kinds a NEW session on Auto would
    tell main it can start (crew/kinds.py `names`), his own first, then the seven that ship with Halo, then the
    built-ins not already covered; every name (main may read " and {n} more" where the tab lists them all)."""
    with CrewRig() as rig:
        rig.studio()
        _agent(rig, "extra")
        st, m = rig.api("GET", "crew/map/auto")
        got = m.get("hand_to")
        want = ["extra"] + SEVEN + ["Judge", "Tester"]
        ctx.check(f"GET crew/map/auto: hand_to is main's kinds, his extra first, got {st} {got}",
                  st == 200 and got == want)
        st, m = rig.api("GET", "crew/map/ship-it")
        ctx.check(f"GET crew/map/ship-it: no hand_to, got {st} {sorted(m)}", st == 200 and "hand_to" not in m)


@test
def test_words_switch_off(ctx: Ctx):
    """A21 / W18: turning his map's "New sessions run on this" off reads Auto, from the server and in the page's fallback."""
    off = "New sessions run on Auto (the default); a running session keeps its own"
    with CrewRig() as rig:
        rig.studio()
        rig.api("POST", "crew/map/ship-it/use", {"on": True})
        st, r = rig.api("POST", "crew/map/ship-it/use", {"on": False})
        crew = json.loads((rig.state / "config.json").read_text(encoding="utf-8")).get("crew") or {}
        ctx.check(f"ship-it off: Auto's words, no crew.map, got {st} {r.get('said')!r} {crew}",
                  st == 200 and r.get("said") == off + "." and "map" not in crew)
        from halo_harness.crew import store
        boss = "mine-boss"
        store.write_text(store.path_for("agent", boss, state_dir=rig.state), store.dump(
            {"format": "agent/1", "name": boss, "does": "Runs the session.", "model": "auto", "uses": ["read"], "careful": "own"}))
        store.write_text(store.path_for("map", "mine", state_dir=rig.state), store.dump(
            {"format": "map/1", "name": "mine", "boxes": [], "lines": [], "main": {"agent": boss}}))
        rig.api("POST", "crew/map/mine/use", {"on": True})
        st, r = rig.api("POST", "crew/map/mine/use", {"on": False})
        said = str(r.get("said"))
        ctx.check(f"mine off: Auto's words, then the moved clause, then the full stop, got {said!r}",
                  st == 200 and said.startswith(off + "; ") and "start in default mode" in said and said.endswith(".")
                  and not said.endswith(".."))
    src = (Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "crew" / "map"
           / "mapSwitch.ts").read_text(encoding="utf-8")
    ctx.check("mapSwitch.ts setUse's fallback says Auto, never 'as before maps'",
              f'r.said || "{off}."' in src and "as before maps" not in src)


@test
def test_get_map_in_use_equals_its_row(ctx: Ctx):
    """The checker of batch 1: one row has ONE answer in GET crew/map/<name> and GET crew/maps -- his old auto.yaml and
    starter.yaml are never in use (the alias makes them unsettable); the shipped Auto is, with none set."""
    with CrewRig() as rig:
        rig.studio()
        _his_map(rig, "auto")
        _his_map(rig, "starter")
        st, r = rig.api("GET", "crew/maps")
        rows = {(x["name"], x["scope"]): x["in_use"] for x in r.get("maps") or []}
        for path, key, want in (("crew/map/auto?scope=yours", ("auto", "yours"), False),
                                ("crew/map/starter?scope=yours", ("starter", "yours"), False),
                                ("crew/map/auto", ("auto", "starter"), True)):
            st, m = rig.api("GET", path)
            ctx.check(f"GET {path}: in_use {want} and equal to its row {key} in crew/maps, got {st} {m.get('in_use')} / {rows.get(key)}",
                      st == 200 and m.get("in_use") is want and rows.get(key) is want)


@test
def test_status_row_map_agents_on_auto_only(ctx: Ctx):
    """A22: a session on Auto carries in its status row the agents it had when it started (`map_agents`), never one
    saved later; a session on another map, or on none, has no key."""
    from types import SimpleNamespace
    with CrewRig() as rig:
        from halo_harness.config.agents_md import discover_agents
        from halo_harness.crew import map_facts
        from halo_harness.crew.map_control import control_for
        from halo_harness.crew.map_session import agents, prepare

        def session(flag):
            c = prepare(flag, rig.proj)[0]
            return SimpleNamespace(team_control=control_for(c, cwd=rig.proj) if c is not None else None,
                                   agent_runtime=SimpleNamespace(agents=agents(discover_agents(rig.proj), c)[0]))
        s = session(None)
        _agent(rig, "late")
        row = map_facts.row(s)
        ctx.check(f"Auto: map_agents is the session's own dict, without the agent saved after the start, got {row.get('map_agents')}",
                  row.get("map_agents") == list(s.agent_runtime.agents) and "late" not in row["map_agents"]
                  and set(SEVEN) <= set(row["map_agents"]))
        row = map_facts.row(session({"map": "ship-it"}))
        ctx.check(f"ship-it: no map_agents, got {sorted(row)}", row and "map_agents" not in row)
        row = map_facts.row(SimpleNamespace(team_control=None, agent_runtime=SimpleNamespace(agents={"x": 1})))
        ctx.check(f"no map: no map_agents, got {sorted(row)}", "map_agents" not in row)
        bare = SimpleNamespace(team_control=s.team_control)
        row = map_facts.row(bare)
        ctx.check(f"Auto with no runtime: no key, never raises, got {sorted(row)}", row and "map_agents" not in row)


# --- batch 3: Setup's Map step (A8, W10, W11, A13), his old file listed by its scope (A5) ---------------------------

W11 = "Main picks who works on each task; each one's model is picked for its task, and the reason is shown."


class _Trusted:
    """The rig's project folder trusted for the test's length (crew/store.py folders asks project_gate.trusted)."""

    def __enter__(self):
        from halo_harness import project_gate
        self.real, project_gate.trusted = project_gate.trusted, (lambda cwd=None: True)
        return self

    def __exit__(self, *exc) -> bool:
        from halo_harness import project_gate
        project_gate.trusted = self.real
        return False


def _proj_map(rig, name: str) -> None:
    from halo_harness.crew import store
    store.write_text(rig.proj / ".halo" / "crew" / "maps" / f"{name}.yaml", store.dump(
        {"format": "map/1", "name": name, "main": {"agent": "main"}, "boxes": [{"id": "p", "agent": "coder"}], "lines": []}))


@test
def test_setup_and_switcher_rows_auto_first_one_model_last(ctx: Ctx):
    """A8, W11, A13: Setup's Map step lists Auto (the default) first, his maps, this project's, the shipped ones
    "(ships with Halo)", One model for everything last; no label holds starter."""
    with CrewRig() as rig, _Trusted():
        from halo_harness.studio.setup_state import map_rows
        _his_map(rig, "shop")
        _proj_map(rig, "proj")
        rows = map_rows(rig.proj, rig.state)
        names = [r["name"] for r in rows]
        ctx.check(f"order: auto, shop, proj, ..., ship-it, one-model last, got {names}",
                  names[:3] == ["auto", "shop", "proj"] and "ship-it" in names[3:-1] and names[-1] == "one-model")
        a = rows[0]
        ctx.check(f"the Auto row, got {a}", a.get("label") == "Auto (the default)" and a.get("scope") == "starter"
                  and a.get("description") == W11 and a.get("default") is True and a.get("active") is True)
        by = {r["name"]: r for r in rows}
        ctx.check(f"shop and proj by name, got {by.get('shop', {}).get('label')} {by.get('proj', {}).get('label')}",
                  by.get("shop", {}).get("label") == "shop" and by.get("proj", {}).get("label") == "proj")
        ctx.check(f"ship-it (ships with Halo), got {by.get('ship-it', {}).get('label')}",
                  by.get("ship-it", {}).get("label") == "ship-it (ships with Halo)")
        ctx.check(f"One model for everything, last, got {rows[-1].get('label')}", rows[-1].get("label") == "One model for everything")
        ctx.check("no label holds starter", not any("starter" in str(r.get("label")).lower() for r in rows))


@test
def test_his_starter_file_listed_by_scope_never_run(ctx: Ctx):
    """A5: his own old starter.yaml / auto.yaml is listed among his maps as "{name} · your copy from before" (Setup) and
    beside the shipped Auto (GET crew/maps), never in use; it opens by its scope; no session runs it; the copy holds his
    boxes and lines, and his file is byte for byte unchanged."""
    with CrewRig() as rig:
        rig.studio()
        from halo_harness.crew import compile as C
        from halo_harness.studio.setup_state import map_rows
        his = _his_map(rig, "starter", "x")
        _his_map(rig, "auto", "y")
        before = his.read_bytes()
        st, r = rig.api("GET", "crew/maps")
        rows = {(x["name"], x["scope"]): x["in_use"] for x in r.get("maps") or []}
        ctx.check(f"GET crew/maps: the shipped auto (in use) and his starter and auto (never), got {rows}",
                  rows.get(("auto", "starter")) is True and rows.get(("starter", "yours")) is False
                  and rows.get(("auto", "yours")) is False)
        srows = map_rows(rig.proj, rig.state)
        old = [x for x in srows if x.get("old")]
        ctx.check(f"Setup: his two old rows, labelled, never active or default, got {old}",
                  sorted(x["label"] for x in old) == ["auto · your copy from before", "starter · your copy from before"]
                  and all(x["active"] is False and x["default"] is False and x["scope"] == "yours" for x in old))
        ctx.check(f"Setup: the shipped Auto row first, the old rows among his maps (before One model), got {[x['name'] for x in srows]}",
                  srows[0]["name"] == "auto" and srows[0].get("scope") == "starter" and not srows[0].get("old")
                  and srows[1].get("old") and srows[2].get("old") and srows[-1]["name"] == "one-model")
        st, m = rig.api("GET", "crew/map/starter?scope=yours")
        ctx.check(f"GET crew/map/starter?scope=yours is his file (box x), got {st} {(m.get('map') or {}).get('boxes')}",
                  st == 200 and [b.get("id") for b in (m.get("map") or {}).get("boxes") or []] == ["x"])
        for flag in (None, "starter"):
            c = C.for_session(flag, cwd=rig.proj)[0]
            ctx.check(f"a session with {flag!r} runs the shipped seven, got {c and c.path}",
                      c is not None and Path(c.path).as_posix().endswith("templates/crew/maps/auto.yaml")
                      and sorted(c.agent_targets()) == sorted(SEVEN))
        # the client's copy path (oldCopy.ts copyOld): GET ?scope=yours, then PUT crew/map/my-map with the map renamed
        st, put = rig.api("PUT", "crew/map/my-map", {"map": {**(m.get("map") or {}), "name": "my-map"}})
        from halo_harness.crew import store
        mine = store.read(rig.state / "crew" / "maps" / "my-map.yaml") or {}
        ctx.check(f"the copy my-map holds his boxes and lines, got {st} {mine.get('boxes')} {mine.get('lines')}",
                  st == 200 and mine.get("boxes") == (m.get("map") or {}).get("boxes")
                  and mine.get("lines") == (m.get("map") or {}).get("lines") and mine.get("name") == "my-map")
        ctx.check("his starter.yaml is byte for byte unchanged", his.read_bytes() == before)


@test
def test_setup_marks_only_the_shipped_row_default(ctx: Ctx):
    """The checker of batch 1, ruled into batch 3 entry 2: with his auto.yaml written and no map set, Setup's state
    marks exactly one row default (and active), the shipped one."""
    with CrewRig() as rig:
        from halo_harness.studio.setup_state import map_rows
        _his_map(rig, "auto")
        rows = map_rows(rig.proj, rig.state)
        default = [(r["name"], r["scope"]) for r in rows if r.get("default")]
        active = [(r["name"], r["scope"]) for r in rows if r.get("active")]
        ctx.check(f"exactly one default row, the shipped one, got {default}", default == [("auto", "starter")])
        ctx.check(f"exactly one active row, the shipped one, got {active}", active == [("auto", "starter")])


# --- batch 4: "ships with Halo" in every list, refusal and help text ------------------------------------------------

SHIPS = "ships with Halo"
UI_SRC = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes"


def _edit_out(kind: str, name: str, cwd) -> str:
    """crew_cli_parts.edit on a shipped item, with Studio's opener stubbed (nothing is started)."""
    import halo_harness.studio_edit_cli as E
    from halo_harness import crew_cli_parts as P
    saved = E.open_in_studio
    E.open_in_studio = lambda *a, **kw: 0
    try:
        return _out(P.edit, kind, name, cwd)[1]
    finally:
        E.open_in_studio = saved


@test
def test_scope_words_is_the_one_function(ctx: Ctx):
    from halo_harness.crew import store
    ctx.check("starter reads 'ships with Halo', short 'shipped'",
              store.scope_words("starter") == SHIPS and store.scope_words("starter", short=True) == "shipped")
    ctx.check("every other scope unchanged", [store.scope_words(s) for s in ("yours", "project", "pack")]
              == ["yours", "project", "pack"] and store.scope_words("yours", short=True) == "yours")
    with CrewRig() as rig:
        from halo_harness.crew import builder, tools_map
        from halo_harness.crew.tools_show import studio_show
        cx = {"cwd": rig.proj, "state_dir": None}
        lists = studio_show({"what": "lists"}, cx)["text"]
        ctx.check("studio_show lists: 'agent coder (ships with Halo): '", "agent coder (ships with Halo): " in lists
                  and "(starter)" not in lists)
        head = studio_show({"what": "map", "name": "ship-it"}, cx)["text"].splitlines()[0]
        ctx.check(f"studio_show map ship-it: its head, got {head!r}", head == "MAP ship-it (ships with Halo):")
        text = builder.context(rig.proj, None, {}, "", [])
        ctx.check("the Builder's rows: '- coder (ships with Halo): ' and '- ship-it (ships with Halo)'",
                  "- coder (ships with Halo): " in text and "- ship-it (ships with Halo)" in text and "(starter)" not in text)
        _rc, out = _out(__import__("halo_harness.crew_cli_parts", fromlist=["show"]).show, "agent", "coder", rig.proj)
        first = out.splitlines()[0]
        ctx.check(f"halo agents show coder: '# <path> (ships with Halo)', got {first!r}",
                  first.startswith("# ") and first.endswith(" (ships with Halo)"))
        _body, first_rows = tools_map._view("ship-it", cx)
        ctx.check(f"the copy row, got {[r['summary'] for r in first_rows]}",
                  [r["summary"] for r in first_rows] == ["Copy the map ship-it (ships with Halo) as yours (the changes below go into your copy)"])


@test
def test_shipped_reads_ships_with_halo(ctx: Ctx):
    with CrewRig():
        from halo_harness.agents_cli import cmd_agents
        from halo_harness.maps_cli import cmd_maps
        from halo_harness.workflows_cli import cmd_workflows
        for verb, fn, name in (("agents", cmd_agents, "coder"), ("workflows", cmd_workflows, "review"), ("maps", cmd_maps, "ship-it")):
            _rc, out = _out(fn, ["list"])
            row = [r.split() for r in out.splitlines() if r.strip().lstrip("*").split()[:1] == [name]]
            ctx.check(f"halo {verb} list: {name}'s scope column reads shipped, and no 'starter' in the list, got {row}",
                      len(row) == 1 and row[0][row[0].index(name) + 1] == "shipped" and "starter" not in out)


@test
def test_ships_with_halo_refusals_word_for_word(ctx: Ctx):
    with CrewRig() as rig:
        for kind, asked, own in (("agent", "coder", "coder"), ("map", "ship-it", "ship-it"), ("map", "starter", "auto")):
            out = _edit_out(kind, asked, rig.proj)
            want = f"{own} ships with Halo (read-only): halo {kind}s copy {own} makes yours (my-{own})"
            ctx.check(f"edit {kind} {asked}: {want!r}, got {out!r}", want in out and "a starter" not in out)
        rig.studio()
        agent = {"format": "agent/1", "name": "coder", "does": "Writes code.", "model": "auto", "uses": ["read"], "careful": "own"}
        st, r = rig.api("PUT", "crew/agent/coder", {"agent": agent})
        ctx.check(f"PUT a shipped agent: 409, its words, got {st} {r.get('error')!r}",
                  st == 409 and r.get("error") == "coder ships with Halo: Copy makes it yours")
        wf = {"format": "workflow/1", "name": "review", "for": "x", "steps": [{"name": "a", "agents": ["coder"]}]}
        st, r = rig.api("PUT", "crew/workflow/review", {"workflow": wf})
        ctx.check(f"PUT a shipped workflow: 409, its words, got {st} {r.get('error')!r}",
                  st == 409 and r.get("error") == "review ships with Halo: Copy makes it yours")
        st, r = rig.api("DELETE", "crew/map/ship-it")
        ctx.check(f"DELETE a shipped map: 409, its words, got {st} {r.get('error')!r}",
                  st == 409 and r.get("error") == "ship-it is not one of your maps (one that ships with Halo or this project's stays)")
        from halo_harness.crew import store
        from halo_harness.crew.compile import compile_map
        tail = "(yours, this project's or one that ships with Halo)"
        ctx.check("no such map: its one problem line",
                  compile_map("nosuch", cwd=rig.proj).problems == [f"no map named nosuch {tail}"])
        store.write_text(rig.state / "crew" / "maps" / "ghosts.yaml", store.dump(
            {"format": "map/1", "name": "ghosts", "main": {"agent": "nobody"}, "boxes": [{"id": "x", "agent": "ghost"}], "lines": []}))
        probs = compile_map("ghosts", cwd=rig.proj).problems
        ctx.check(f"a missing main agent and a missing box agent: the two lines, got {probs}",
                  f"main: no agent named nobody {tail}" in probs and f"box x: no agent named ghost {tail}" in probs)
        from halo_harness.crew import tools_flow
        cx = {"cwd": rig.proj, "state_dir": None}
        got = tools_flow.workflow_change({"name": "review"}, cx)["text"]
        ctx.check(f"the Builder changing a shipped workflow, got {got!r}", got == "review: ships with Halo: workflow_copy it first")
        from halo_harness.crew import builder
        text = builder.context(rig.proj, None, {}, "", [])
        ctx.check("the Builder's two headings",
                  "AGENTS (yours, this project's, and the ones that ship with Halo, which you can copy):" in text
                  and "WORKFLOWS (yours, this project's, and the ones that ship with Halo, which you can copy):" in text)
        from halo_harness.crew import flow_door
        last = flow_door.listing(rig.proj, state_dir=None)[-1]
        ctx.check(f"/workflows' last line, got {last!r}", last == "halo workflows list shows every workflow file, the ones "
                  "that ship with Halo too (Copy makes it yours); /workflows show <name>")
    from halo_harness import agents_cli, maps_cli, workflows_cli
    from halo_harness.agents_cli import cmd_agents
    from halo_harness.maps_cli import cmd_maps
    from halo_harness.workflows_cli import cmd_workflows

    def flat(s: str) -> str:
        return " ".join(s.split())

    copy = "your own copy of one (one that ships with Halo, a pack's, the project's), to edit"
    for verb, fn, mod in (("maps", cmd_maps, maps_cli), ("agents", cmd_agents, agents_cli), ("workflows", cmd_workflows, workflows_cli)):
        _rc, out = _out(fn, ["--help"])
        _rc, cp = _out(fn, ["copy", "--help"])
        ctx.check(f"halo {verb} --help and copy --help: the copy words, no 'starter'",
                  copy in flat(out) and "starter" not in out + cp and copy in flat(mod.__doc__))
        ctx.check(f"halo {verb}'s module help: no 'starter'", "starter" not in mod.__doc__)
    for fn, verb in ((cmd_agents, "agents"), (cmd_workflows, "workflows")):
        _rc, new = _out(fn, ["new", "--help"])
        ctx.check(f"halo {verb} new --from: its words", "copy this one (one that ships with Halo or another)" in flat(new))
    ctx.check("halo maps list's help line", "every map: yours, this project's (a trusted folder), then the ones that ship "
              "with Halo; the one in use marked" in flat(maps_cli.__doc__))
    ctx.check("halo maps use's help line", "new sessions run on it (config `crew.map`); `--off` goes back to Auto (the default: "
              "main picks who works on each task); `--none` is One model for everything (roles off, no map)" in flat(maps_cli.__doc__))
    for mod in (agents_cli, workflows_cli):
        ctx.check(f"{mod.__name__} list's help line",
                  "yours, this project's (a trusted folder), then the ones that ship with Halo" in flat(mod.__doc__))
    ctx.check("halo agents new's help line", "one of yours: a copy of one that ships with Halo or of another agent, else a blank one"
              in flat(agents_cli.__doc__))
    ctx.check("halo workflows new's help line", "one of yours: a copy of one that ships with Halo (code, plan, review, research, "
              "media)" in flat(workflows_cli.__doc__))
    from halo_harness.cli import GONE_VERBS
    from halo_harness.cli_commands import BY_NAME
    ctx.check(f"the blocks row, got {BY_NAME['blocks'].purpose!r}", BY_NAME["blocks"].purpose == "blocks are workflows now (halo workflows)")
    ctx.check(f"the blocks hint, got {GONE_VERBS['blocks']!r}",
              GONE_VERBS["blocks"] == "shipped workflows: halo workflows new <name> --from <a shipped one> (halo workflows list)")
    from halo_harness import crew_cli_parts as P
    from halo_harness.crew import store
    saved = store.rows
    store.rows = lambda *a, **kw: []
    try:
        _rc, out = _out(P.print_list, "agent", Path.cwd())
    finally:
        store.rows = saved
    ctx.check(f"no agents at all: its line, got {out!r}", out.strip() == "no agents (the ones that ship with Halo are missing: check the install)")


@test
def test_init_summary_lineup_reads_auto(ctx: Ctx):
    """RULINGS 7: `halo init`'s summary names the default by its one name; a map of his keeps its own."""
    from halo_harness.init_wait import summary_lines

    def lineup(team) -> str:
        return [ln for ln in summary_lines({"team": team}) if ln.startswith("Lineup: ")][0]
    for name in ("auto", "starter"):
        got = lineup({"active": name, "source": "default"})
        ctx.check(f"the default named {name}: 'Lineup: Auto (the default)', got {got!r}", got == "Lineup: Auto (the default)")
    got = lineup({"active": "shop", "source": "config"})
    ctx.check(f"a map of his keeps its name, got {got!r}", got == "Lineup: shop")
    ctx.check("one model and not set stay", lineup({"active": "one-model"}) == "Lineup: one model for everything"
              and lineup({}) == "Lineup: not set")


@test
def test_studio_lists_say_ships_with_halo(ctx: Ctx):
    def flat(rel: str) -> str:
        return " ".join((UI_SRC / rel).read_text(encoding="utf-8").split())

    new = {
        "crew/Crew.tsx": ["Your agents and this project's, then the ones that ship with Halo (Copy makes it yours).",
                          "One that ships with Halo: a click copies it as yours (Save keeps it)."],
        "crew/flows/Flows.tsx": ["Your workflows and this project's (on the map or not), then the ones that ship with Halo (Copy makes it yours).",
                                 "One that ships with Halo: a click copies it as yours (Save keeps it)."],
        "crew/List.tsx": ["None yet: + New agent, or copy one that ships with Halo below.", ">Ships with Halo · Copy makes it yours<"],
        "crew/flows/FlowList.tsx": ["None yet: + New workflow, copy one that ships with Halo below, or describe one in the builder box.",
                                    ">Ships with Halo · Copy makes it yours<"],
        "crew/Form.tsx": ["Make one here, copy one that ships with Halo from the list, or describe it in the builder box below."],
        "crew/flows/FlowForm.tsx": ["Make one here, copy one that ships with Halo from the list, or describe it in the builder box below.",
                                    '<span className="cw-tag">{scopeTag(a.scope, a.name)}</span>'],
        # 3.6.0.6 P: the tag of every list comes from the one function (a pack's reads "pack {id}")
        "crew/scopeTag.ts": ['if (scope === "starter") return "ships with Halo";', 'if (scope === "project") return "this project\'s";',
                             'if (scope === "pack") return `pack ${packOf(name)}`;'],
        "crew/flows/StepRow.tsx": ['` (${scopeTag(a.scope, a.name)})`'],
        "crew/map/AddList.tsx": ['{scopeTag(it.scope, it.name)}'],
        "crew/map/MapBar.tsx": ['" (one that ships with Halo: your first change saves it as yours)"'],
        "sectionHelp.ts": ["Every session runs on a map (Auto, the default, until you pick one).",
                           "then the ones that ship with Halo to copy; the form on the right.",
                           '"Map: Auto (the default), a map of yours, or One model for everything, with its preview; Apply writes '
                           "what the wizard's Map step writes.\""],
        "help-setup.ts": ['"Auto (the default): each task goes to agents main picks, each on a model picked for it. One model for '
                          'everything: roles off, no map."'],
    }
    old = ["Starters to copy", "copy a starter", "then the starters to copy", "A starter's click", '<span className="cw-tag">starter</span>',
           '" (starter)"', ': "starter"}', "(a starter:", "the starter map until", "starter (the default)"]
    for rel, words in new.items():
        text = flat(rel)
        missing = [w for w in words if w not in text]
        stale = [w for w in old if w in text]
        ctx.check(f"{rel}: the new words, none of the old, missing {missing} stale {stale}", not missing and not stale)
    ids = flat("crew/List.tsx") + flat("crew/flows/FlowList.tsx")
    ctx.check("the test ids crew-starter and flow-starter stay (A19)", 'data-testid="crew-starter"' in ids and 'data-testid="flow-starter"' in ids)


# --- batch 5 entry 1 (A15, W-B): on Auto a workflow is made with no map ----------------------------------------------

W_B = "In a session on Auto, make the workflow and the agents it needs, with no map, unless the person asks for a map."
R37 = "A workflow the person wants run is a saved workflow in a box on a map, made and named in the same card."


class _Sess:
    """The parts of a session the Builder reads (as tests/test_builder_map.py `_S`): on Auto, or on his map `mp`."""

    def __init__(self, rig, mp=None) -> None:
        from types import SimpleNamespace
        from halo_harness.crew.compile import compile_map
        from halo_harness.crew.map_control import control_for
        c = compile_map(mp or "auto", cwd=rig.proj, state_dir=rig.state)
        c.source = "flag" if mp else "default"
        self.cwd = rig.proj
        self.team_control = control_for(c, cwd=rig.proj, state_dir=rig.state)
        self.permission_engine = SimpleNamespace(mode="default")
        self.interactive = True
        self.agent_depth = 0


REVIEW_CARD = [{"tool": "agent_make", "args": {"name": "checker", "does": "Checks the code."}},
               {"tool": "workflow_make", "args": {"name": "review", "for": "code then check",
                                                  "steps": [{"name": "code", "agents": ["coder"]},
                                                            {"name": "check", "agents": ["checker"]}]}}]


@test
def test_auto_build_makes_no_map_or_use_row(ctx: Ctx):
    """A15: on Auto, "a coder then a checker" is ONE card (the agent not saved yet, the workflow), no map row, no use
    row, headed by FIRST_WORKFLOW_AUTO; on his map the same card keeps 3.6.0.2's (no such line)."""
    from halo_harness.crew import session_tool
    from halo_harness.crew.map_facts import FIRST_WORKFLOW_AUTO
    want = "Your review workflow: the workflow review (coder, then checker)."
    ctx.check("FIRST_WORKFLOW_AUTO's words", FIRST_WORKFLOW_AUTO.format(words="review", W="review", steps="coder, then checker") == want)
    with CrewRig() as rig:
        pv = session_tool.preview(_Sess(rig), {"changes": REVIEW_CARD})
        targets = [str(r.get("target")) for r in pv["rows"]]
        ctx.check(f"agent + workflow rows, none for a map or a use, got {targets}",
                  "agent:checker" in targets and "workflow:review" in targets
                  and not any(t.startswith(("map:", "use:")) for t in targets))
        q = pv["card"]["questions"][0]["question"].splitlines()
        ctx.check(f"the card's first line and the text's line 1, got {q[:2]} / {pv['text'].splitlines()[:1]}",
                  len(q) > 1 and q[1] == want and pv["text"].splitlines()[0] == want)
    with CrewRig() as rig:
        _his_map(rig, "shop")
        pv = session_tool.preview(_Sess(rig, "shop"), {"changes": REVIEW_CARD})
        targets = [str(r.get("target")) for r in pv["rows"]]
        ctx.check(f"on his map: no FIRST_WORKFLOW_AUTO, no map or use row, got {pv['text'].splitlines()[:1]} / {targets}",
                  want not in pv["text"] and "Your review workflow" not in pv["text"]
                  and not any(t.startswith(("map:", "use:")) for t in targets))


@test
def test_card_and_builder_words_never_promise_this_session(ctx: Ctx):
    """Decision 2: no line of (a) promises "usable in this session"; W-B replaces R37's sentence before the tool list."""
    from halo_harness.crew.map_facts import FIRST_WORKFLOW_AUTO
    from halo_harness.tools.builder_tool import BuilderTool
    for name, text in (("FIRST_WORKFLOW_AUTO", FIRST_WORKFLOW_AUTO), ("W-B", W_B)):
        low = text.lower()
        bad = [w for w in ("usable", "this session") if w in low] + (["now"] if "now" in low.replace(",", " ").replace(".", " ").split() else [])
        ctx.check(f"{name} promises nothing for now, got {bad}", not bad)
    d = BuilderTool().description
    ctx.check("W-B before 'The tools:'", 0 <= d.find(W_B) < d.find("The tools:"))
    ctx.check("R37's sentence is gone", R37 not in d)


# --- batch 5 entry 3 (A18, A23): the docs and the shipped comments say Auto and "ships with Halo" ---------------------

# Where "starter" means something else, by file: None keeps the whole file (ComfyUI's starter workflows); else the
# phrases that keep it (each must still be there, so a stale skip shows). CHANGELOG.md and data/changelog.md are not
# read: past release notes keep the word.
DOCS_KEEP = {
    "docs/COMFYUI.md": None,
    "docs/STUDIO-local-media.md": None,
    "docs/LOCAL-MODELS.md": ["whose starter has"],  # the process that started a server
    "docs/REMOTE.md": ["the starter's `HALO_SESSION_PARENT`"],  # the process that started a session
    "docs/review-findings-m4-6.md": ["BridgeStartError"],  # line 81: a class name
    # `halo media`: ComfyUI's starter workflows, as `halo media`'s own help and output say them (media/*, kept)
    "docs/COMMANDS-studio.md": ["saved workflows, the starters, the entry", "and the Halo starters",
                                "starter workflows into ComfyUI's workflow browser", "asking once when a starter",
                                "the text-to-image starter"],
    # the JSON keys of the two list routes (code identifiers, unchanged)
    "docs/STUDIO-builder.md": ["`{agents, starters}`"],
    "docs/STUDIO-workflows.md": ["`{workflows, starters}`"],
}


@test
def test_starter_absent_from_docs_and_shipped_comments(ctx: Ctx):
    """A18 A23: every docs/*.md and README.md, the first line of every file under templates/crew/, the doc-review
    pack's README and its map's first line hold no "starter" (any case) outside DOCS_KEEP."""
    root = Path(__file__).resolve().parent.parent
    left, stale = [], []
    for p in sorted([*(root / "docs").glob("*.md"), root / "README.md"]):
        rel = p.relative_to(root).as_posix()
        keep = DOCS_KEEP.get(rel, [])
        if keep is None:
            continue
        text = p.read_text(encoding="utf-8")
        for phrase in keep:
            if phrase not in text:
                stale.append(f"{rel}: {phrase}")
            text = text.replace(phrase, "")
        left += [f"{rel}:{i}" for i, line in enumerate(text.splitlines(), 1) if "starter" in line.lower()]
    tpl = root / "halo_harness" / "templates"
    for p in sorted((tpl / "crew").rglob("*")):
        if p.is_file():
            first = (p.read_text(encoding="utf-8").splitlines() or [""])[0]
            if "starter" in first.lower():
                left.append(f"{p.relative_to(root).as_posix()}:1")
    pack = tpl / "packs" / "doc-review"
    left += [f"doc-review/README.md:{i}" for i, line in enumerate((pack / "README.md").read_text(encoding="utf-8").splitlines(), 1)
             if "starter" in line.lower()]
    if "starter" in (pack / "crew" / "maps" / "review.yaml").read_text(encoding="utf-8").splitlines()[0].lower():
        left.append("doc-review/crew/maps/review.yaml:1")
    ctx.check(f"no starter left, got {left}", not left)
    ctx.check(f"every kept phrase is still there, stale {stale}", not stale)
    first = (tpl / "crew" / "workflows" / "code.yaml").read_text(encoding="utf-8").splitlines()[0]
    ctx.check(f"a shipped file's first line, got {first!r}", first == "# Ships with Halo (3.6.0.0): read-only; Copy makes yours.")


# --- batch 6 entry 2 (A9, A10, A16): the scans that keep "starter" away from him -------------------------------------

LINEUP = "The lineup is auto: a sub-agent's model is picked for its task; say `model:` to choose yourself."
PLAIN_FIXTURE_SHA = "289547bec4e6b518aec8c25b8bf21d0e8ad82ad4fcb27ea99588c9971d854d2c"  # map_facts_plain_requests_3604.json


def _said(fn, *a) -> str:
    """What `fn(*a)` prints on stdout and stderr; argparse's exit (a --help) ends it."""
    from contextlib import redirect_stderr
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            fn(*a)
        except SystemExit:
            pass
    return buf.getvalue()


def _with_starter(said: dict) -> list:
    return [f"{k}: {v!r}" for k, v in said.items() if "starter" in str(v).lower()]


def _api_words(v, key: str = "") -> list:
    """Every string value of an API answer, except the `scope` VALUE (a code word); JSON field names are not read."""
    if isinstance(v, dict):
        return [w for k, x in v.items() if k != "scope" for w in _api_words(x, k)]
    if isinstance(v, list):
        return [w for x in v for w in _api_words(x, key)]
    return [v] if isinstance(v, str) else []


@test
def test_starter_absent_from_terminal_output(ctx: Ctx):
    """A9: nothing the terminal prints, no `halo` command's output or help, no tool result and nothing the Builder's model
    is given says "starter"; it reaches him only as his own old file's name (A5)."""
    import os
    with CrewRig() as rig:
        from halo_harness import crew_cli_parts as P
        from halo_harness import doctor, setup_cli
        from halo_harness.agents_cli import cmd_agents
        from halo_harness.cli import GONE_VERBS
        from halo_harness.cli_commands import BY_NAME
        from halo_harness.commands.builtins import _map_line
        from halo_harness.crew import builder, flow_door, map_facts, old_files, preflight, store, tools_map
        from halo_harness.crew import compile as C
        from halo_harness.crew.tools_show import studio_show
        from halo_harness.maps_cli import cmd_maps
        from halo_harness.tui.dialogs import team_preview
        from halo_harness.workflows_cli import cmd_workflows
        cx = {"cwd": rig.proj, "state_dir": None}
        auto = _Session(C.for_session(None, cwd=rig.proj)[0])
        said = {"/status, no session": _map_line(None), "/status, a session on Auto": _map_line(auto),
                "doctor": doctor._check_lineup(), "halo setup": _said(setup_cli._print_map_in_use),
                "[Halo] note, none set": map_facts.note_text(auto), "studio_show's line, none set": map_facts.show_line(auto),
                "name_the_map": map_facts.name_the_map(auto), "name_the_map, no session": map_facts.name_the_map(None)}
        for verb, fn, subs in (("maps", cmd_maps, ("list", "show", "copy", "use", "edit")),
                               ("agents", cmd_agents, ("list", "show", "new", "copy", "edit", "try")),
                               ("workflows", cmd_workflows, ("list", "show", "new", "copy", "edit"))):
            said[f"halo {verb} list"] = _said(fn, ["list"])
            said[f"halo {verb} --help"] = _said(fn, ["--help"])
            for sub in subs:
                said[f"halo {verb} {sub} --help"] = _said(fn, [sub, "--help"])
        said["halo maps use --off"] = _said(cmd_maps, ["use", "--off"])
        said["halo agents show coder"] = _said(P.show, "agent", "coder", rig.proj)
        saved_env = {k: os.environ.pop(k, None) for k in ("VISUAL", "EDITOR")}
        try:
            said["halo agents edit coder"] = _edit_out("agent", "coder", rig.proj)
            said["halo workflows edit review"] = _edit_out("workflow", "review", rig.proj)
        finally:
            os.environ.update({k: v for k, v in saved_env.items() if v is not None})
        said["halo blocks (the row)"] = BY_NAME["blocks"].purpose
        said["halo blocks (the hint)"] = GONE_VERBS["blocks"]
        empty = rig.state / "empty-shipped"
        empty.mkdir()
        real, store.SHIPPED = store.SHIPPED, empty
        try:
            for kind in ("agent", "workflow"):
                said[f"no {kind}s at all"] = _said(P.print_list, kind, rig.proj)
        finally:
            store.SHIPPED = real
        said["/workflows"] = "\n".join(flow_door.listing(rig.proj, state_dir=None))
        said["studio_show lists"] = studio_show({"what": "lists"}, cx)["text"]
        for name in ("ship-it", "auto"):
            said[f"studio_show map {name}"] = studio_show({"what": "map", "name": name}, cx)["text"]
        said["the Builder's context"] = builder.context(rig.proj, None, {}, "", [])
        said["the Builder's copy row"] = json.dumps(tools_map._view("ship-it", cx)[1])
        cfg = rig.state / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        cfg.write_text(json.dumps({**data, "team": "auto"}), encoding="utf-8")
        said["team: auto"] = old_files.team_line()
        cfg.write_text(json.dumps(data), encoding="utf-8")
        said["team preview"] = team_preview.HEADER_TEXT
        said["preflight, a missing map"] = json.dumps(preflight.run_problems("nosuch", cwd=rig.proj))
        store.write_text(rig.state / "crew" / "maps" / "gap.yaml", store.dump(
            {"format": "map/1", "name": "gap", "main": {"agent": "main"}, "boxes": [{"id": "a", "agent": "nobody"}],
             "lines": [{"from": "main", "to": "a"}]}))
        said["--map gap (a box with no agent)"] = "\n".join(C.for_session("gap", cwd=rig.proj)[1])
        _config(rig, map="ship-it")
        said["[Halo] note, ship-it set"] = map_facts.note_text(auto)
        said["studio_show's line, ship-it set"] = map_facts.show_line(auto)
        _config(rig)
        ctx.check(f"the scan read every surface ({len(said)}), none empty: "
                  f"{[k for k, v in said.items() if not str(v).strip()]}", all(str(v).strip() for v in said.values()))
        bad = _with_starter(said)
        ctx.check(f"no line he reads says starter: {len(bad)} found:\n  " + "\n  ".join(bad), not bad)
        _his_map(rig, "starter")
        rows = _said(cmd_maps, ["list"]).splitlines()
        named = [r for r in rows if "starter" in r.lower()]
        ctx.check(f"halo maps list with his old starter.yaml: the word only as that row's own name, got {named}",
                  len(named) == 1 and named[0].lstrip("* ").split()[0] == "starter"
                  and "starter" not in named[0].lstrip("* ").split(None, 1)[1].lower())


@test
def test_starter_absent_from_api_answers(ctx: Ctx):
    """A9: no Studio API answer he reads says "starter" (field names and the `scope` value are not words he reads);
    the one allowed echo is W16 repeating the name he typed."""
    with CrewRig() as rig:
        rig.studio()
        agent = {"format": "agent/1", "name": "coder", "does": "Writes code.", "model": "auto", "uses": ["read"], "careful": "own"}
        wf = {"format": "workflow/1", "name": "review", "for": "x", "steps": [{"name": "a", "agents": ["coder"]}]}
        answers = {}
        for label, method, path, body, want in (
                ("PUT crew/agent/coder", "PUT", "crew/agent/coder", {"agent": agent}, 409),
                ("PUT crew/workflow/review", "PUT", "crew/workflow/review", {"workflow": wf}, 409),
                ("DELETE crew/map/ship-it", "DELETE", "crew/map/ship-it", None, 409),
                ("ship-it on", "POST", "crew/map/ship-it/use", {"on": True}, 200),
                ("ship-it off", "POST", "crew/map/ship-it/use", {"on": False}, 200),
                ("setup/team starter", "POST", "setup/team", {"map": "starter"}, 200),
                ("setup/team auto", "POST", "setup/team", {"map": "auto"}, 200)):
            st, r = rig.api(method, path, body) if body is not None else rig.api(method, path)
            ctx.check(f"{label}: {want}, got {st}", st == want)
            answers[label] = _api_words(r)
        st, r = rig.api("GET", "setup/state")
        rows = ((r.get("team") or {}).get("maps")) or []
        ctx.check(f"GET setup/state: the team's map rows, got {st} {len(rows)}", st == 200 and len(rows) > 2)
        answers["setup/state team rows"] = [str(x.get(k)) for x in rows for k in ("label", "description") if x.get(k)]
        ctx.check("setup/team's receipts and the off receipt are read", answers["setup/team starter"] and answers["ship-it off"])
        bad = _with_starter(answers)
        ctx.check(f"no API answer he reads says starter: {bad}", not bad)
        st, r = rig.api("PUT", "crew/map/starter", {"map": {"main": {"agent": "main"}, "boxes": [], "lines": []}})
        ctx.check(f"PUT crew/map/starter: 422, W16 echoing the name he typed and nothing else holds it, got {st} {r}",
                  st == 422 and r.get("error") == _w16("starter")
                  and not _with_starter({"rest": [w for w in _api_words(r) if w != _w16("starter")]}))


@test
def test_start_words_say_auto_never_starter(ctx: Ctx):
    """A16, A10: what main is told at the start of a session on Auto (system text, tool descriptions, messages) holds
    the Agent tool's "The lineup is auto: ..." letter for letter and no "starter"; 3.6.0.4's recorded plain-session
    requests are kept byte for byte (map_facts_plain_requests_3604.json: the main fixture was re-recorded once in
    3.6.0.5 for `task`, and tests/test_auto_groups.py::test_r38_fixture_differs_only_by_task proves that is the only
    difference)."""
    import hashlib
    from tests import test_map_facts as MF
    got, facts = MF.plain_requests()
    ctx.check(f"a session on Auto, got {facts.get('map')!r} and {len(got)} requests", facts.get("map") == "auto" and got)
    ctx.check("the first request holds the lineup sentence letter for letter", LINEUP in got[0])
    bad = [i for i, b in enumerate(got) if "starter" in b.lower()]
    ctx.check(f"no request main sent says starter, got requests {bad}", not bad)
    kept = MF.FIXTURE.with_name("map_facts_plain_requests_3604.json").read_bytes()
    ctx.check("3.6.0.4's plain-request recording is kept byte for byte",
              hashlib.sha256(kept).hexdigest() == PLAIN_FIXTURE_SHA)
    raw = MF.FIXTURE.read_bytes()
    ctx.check("the fixture holds the lineup sentence and no starter",
              LINEUP in raw.decode("utf-8") and b"starter" not in raw.lower())


@test
def test_the_map_switch_is_quoted_by_its_new_name(ctx: Ctx):
    """b/batch06 entry 4 (the coordinator's ruling): no file under docs/, README.md or halo_harness/ (but the two
    changelogs and the built studio/static/dist) quotes the Map switch by its old name, and the `crew.map` row's help
    says what unset means on Auto's terms."""
    from halo_harness.settings_catalog_rows_a import ROWS
    root = Path(__file__).resolve().parent.parent
    old = "My sessions use " + "this"
    files = [*(root / "docs").rglob("*.md"), root / "README.md", *(root / "halo_harness").rglob("*")]
    skip = ("halo_harness/data/changelog.md", "halo_harness/studio/static/dist/", "halo_harness/studio/ui/node_modules/")
    left = []
    for p in files:
        rel = p.relative_to(root).as_posix()
        if not p.is_file() or p.suffix not in (".md", ".py", ".ts", ".tsx", ".css", ".json", ".yaml", ".txt", ".html") \
                or rel.startswith(skip) or "__pycache__" in rel:
            continue
        if old in p.read_text(encoding="utf-8", errors="replace"):
            left.append(rel)
    ctx.check(f"no file quotes the switch's old name, got {left}", left == [])
    row = next((r for r in ROWS if r.key == "crew.map"), None)
    ctx.check(f"the crew.map row's help, word for word, got {getattr(row, 'help', None)!r}",
              row is not None and row.help == "The map new sessions run on (Agents -> 3 · Map, New sessions run on this); "
                                              "unset, new sessions run on Auto (the default).")


# --- r/batch05 (the judge of the joined candidate, engine M1 and M2) ------------------------------------------------

@test
def test_builder_maps_text_marks_one_row_in_use(ctx: Ctx):
    """r/batch05 entry 1 (RULINGS 7): his own old auto.yaml and starter.yaml, no map set: the MAPS block of the
    Builder's context marks exactly ONE row IN USE, the one that ships with Halo; the one rule lives in the crew store
    and Studio's routes call it (no second copy)."""
    from halo_harness.crew import builder, store
    from halo_harness.studio import crew_map_api
    with CrewRig() as rig:
        _his_map(rig, "auto")
        _his_map(rig, "starter")
        _config(rig)
        text = builder._maps_text(rig.proj, rig.state)
        marked = [ln for ln in text.splitlines() if " IN USE" in ln]
        ctx.check(f"one row IN USE, the shipped auto, got {marked}",
                  len(marked) == 1 and marked[0].startswith("- auto (ships with Halo) IN USE:"))
        ctx.check(f"his two old files are listed, never in use, got {text.splitlines()}",
                  "- auto (yours): 1 boxes | lines: none" in text.splitlines()
                  and "- starter (yours): 1 boxes | lines: none" in text.splitlines())
    ctx.check("the one rule is the crew store's row_in_use", callable(getattr(store, "row_in_use", None)))
    ctx.check("Studio's routes keep no copy of their own", not hasattr(crew_map_api, "_row_in_use"))


AUTO_ALREADY = "New sessions run on Auto (the default) already."
AUTO_BACK = "New sessions run on Auto (the default); a running session keeps its own"


@test
def test_map_use_on_a_default_name_says_the_truth(ctx: Ctx):
    """r/batch05 entry 2: `map_use` with a name of the default, his own old starter.yaml present. With Auto in use: the
    answer says new sessions run on Auto already, no row. With his ship-it set: ONE row in the release's own words for
    going back to the default, its value the default; applied, crew.map is unset. No line holds the word starter."""
    from halo_harness.crew import changes_map, tools_map
    from halo_harness.crew.compile import DEFAULT_MAP
    with CrewRig() as rig:
        _his_map(rig, "starter")
        _his_map(rig, "ship-it")
        ctx_ = {"cwd": rig.proj, "state_dir": rig.state}
        _config(rig)
        for name in ("starter", "Auto", "auto"):
            got = tools_map.map_use({"map": name}, ctx_)
            ctx.check(f"none set, map_use {name!r}: already, no row, got {got}",
                      got == {"text": AUTO_ALREADY, "rows": []})
        _config(rig, map="ship-it")
        for name in ("starter", "Auto"):
            got = tools_map.map_use({"map": name}, ctx_)
            rows = got.get("rows") or []
            said = str(rows[0].get("summary")) if rows else ""
            ctx.check(f"ship-it set, map_use {name!r}: one row in the release's words, got {got.get('text')!r} {said!r}",
                      len(rows) == 1 and (said == AUTO_BACK + "." or (said.startswith(AUTO_BACK + " -- ")
                                                                       and said.endswith("."))))
            op = rows[0]["op"] if rows else {}
            ctx.check(f"its value is the default, got {op.get('op')!r} {op.get('value')!r}",
                      op.get("op") == "use" and op.get("value") == DEFAULT_MAP)
            crew = json.loads(changes_map.config_text(op.get("value"))).get("crew") or {}
            ctx.check(f"applied, crew.map is unset, got {crew}", "map" not in crew)
            ctx.check(f"no line of the result holds the word starter, got {got.get('text')!r} {said!r}",
                      "starter" not in (str(got.get("text")) + "\n" + said).lower())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
