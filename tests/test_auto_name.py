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
    """A22: M1's {names} are `hand_to` on GET crew/map/auto only: the agents a NEW session on Auto gets now, the seven
    that ship with Halo first."""
    with CrewRig() as rig:
        rig.studio()
        _agent(rig, "extra")
        st, m = rig.api("GET", "crew/map/auto")
        got = m.get("hand_to")
        ctx.check(f"GET crew/map/auto: hand_to, the seven first, then extra, got {st} {got}",
                  st == 200 and isinstance(got, list) and set(got[:7]) == set(SEVEN) and "extra" in got)
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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
