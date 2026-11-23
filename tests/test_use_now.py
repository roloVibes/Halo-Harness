"""tests.test_use_now -- Halo 3.6.0.15 UN, rule U1: an agent saved while a session on Auto runs is put into that
session's agents (crew/use_now.py) and taken at main's next model call, in the very dict every helper shares; a running
helper keeps its spec; each refusal names its code; gone and back put the start back or remove the name; a session
nothing is put to is untouched.

Real, never-turned Sessions on the default map (as tests/test_ready_lines.py builds one), a dead upstream: nothing calls
a model. Every test sets BRIDGE_TEST_HOME to a fresh scratch folder and puts os.environ back in a finally.
Run: python -m tests.test_use_now
"""
from __future__ import annotations

import dataclasses
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MODEL = "or:mock/use-now"
DEAD = "http://127.0.0.1:9"
ENV = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST")
SHA1 = "a" * 64
SHA2 = "b" * 64


def _body(name: str = "sorter", **kw) -> dict:
    b = {"format": "agent/1", "name": name, "does": "Sorts the files it is given by kind.", "uses": ["read"],
         "careful": "ask-changes", "model": "auto"}
    b.update(kw)
    return b


def _scoped(fn):
    saved = {k: os.environ.get(k) for k in ENV}
    home = Path(tempfile.mkdtemp(prefix="use-now-"))
    os.environ.pop("BRIDGE_STATE_DIR", None)
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ["OLLAMA_HOST"] = DEAD
    (home / "proj").mkdir()
    try:
        return fn(home)
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        shutil.rmtree(home, ignore_errors=True)


def _session(home: Path, *, agents=None, drop=(), mode: str = "default"):
    """A real Session on the default map; `drop` names tools taken out of its registry before it is made."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.crew.map_session import prepare
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.builder_tool import BuilderTool
    from halo_harness.tools.registry import ToolRegistry, default_tools
    cwd = home / "proj"
    reg = ToolRegistry([t for t in default_tools() + [BuilderTool()] if t.name not in drop])
    s = Session(cwd=cwd, model_ref=parse_model_ref(MODEL), model_profile=ModelProfile(),
                creds=ProviderCreds(base_url=DEAD, api_key="k"), state_dir=home / "sess-state", model_label=MODEL,
                crew_map=prepare(None, cwd)[0],
                session_context=SessionContext(cwd=cwd, model_label=MODEL, tool_registry=reg), max_turns=6,
                permission_engine=PermissionEngine(mode=mode, cwd=cwd), agents=agents)
    s.interactive = True
    return s


def _spec(body: dict, source: str):
    from halo_harness.crew import store
    from halo_harness.crew.spec import agent_spec
    return agent_spec(store.clean(body), source=source)


@test
def test_put_waits_for_the_take_then_the_agent_is_startable(ctx: Ctx):
    from halo_harness.crew import use_now

    def run(home):
        s = _session(home)
        ctx.check("the session is on Auto", use_now.can_take(s))
        agents = s.agent_runtime.agents
        got = use_now.put(s, _body(), "yours", SHA1)
        ctx.check(f"put took, got {got}", got == (True, ""))
        ctx.check("nothing in the agents before the take", "sorter" not in agents)
        took = use_now.take(s)
        ctx.check(f"take added sorter, got {[(t['name'], t['change']) for t in took]}",
                  [(t["name"], t["change"]) for t in took] == [("sorter", "added")] and took[0]["note"] is True)
        ctx.check("the very dict a helper shares", s.agent_runtime.agents is agents)
        sp = agents.get("sorter")
        ctx.check(f"an AgentSpec from crew:yours, got {sp!r}",
                  sp is not None and sp.source == "crew:yours" and sp.description == _body()["does"])
        ctx.check(f"added lists it, got {use_now.added(s)}", use_now.added(s) == ["sorter"])
        ctx.check("a second take has nothing", use_now.take(s) == [])
    _scoped(run)


@test
def test_each_why(ctx: Ctx):
    from halo_harness.crew import use_now

    def one(label, body, want, **kw):
        def run(home):
            s = _session(home, **{k: v for k, v in kw.items() if k in ("agents", "drop", "mode")})
            if kw.get("prep"):
                kw["prep"](s, home)
            got = use_now.put(s, body, kw.get("scope", "yours"), SHA1)
            ctx.check(f"{label}: want {want}, got {got}", got == want)
            if not got[0]:
                ctx.check(f"{label}: nothing queued", not getattr(s, "_kinds_pending", None))
        _scoped(run)

    one("a built-in's name", _body("general-purpose"), (False, "built-in"))
    one("web with neither web tool", _body(uses=["web"]), (False, "tool:WebFetch"), drop=("WebFetch", "WebSearch"))
    one("web with one web tool", _body(uses=["web"]), (True, ""), drop=("WebSearch",))
    one("bash where PowerShell is not registered", _body(uses=["bash"]), (True, ""), drop=("PowerShell",))
    one("bash with no shell at all", _body(uses=["read", "bash"]), (False, "tool:Bash"),
        drop=("Bash", "PowerShell", "BashOutput", "TaskStop"))
    one("an mcp server the session lacks", _body(uses=["mcp:notes"]), (False, "tool:mcp__notes__*"))
    one("own on a default-mode session", _body(careful="own"), (False, "mode"))
    one("ask-commands on an acceptEdits session", _body(careful="ask-commands"), (True, ""), mode="acceptEdits")
    one("own on a plan session (a plan child, no refusal)", _body(careful="own"), (True, ""), mode="plan")
    one("a body with a format problem", _body(format="agent/9"), (False, "problems"))

    def his_map(s, home):
        from halo_harness.crew import store
        from halo_harness.crew.compile import compile_map
        from halo_harness.crew.map_control import control_for
        from halo_harness.providers.config import default_state_dir
        state = Path(default_state_dir())
        raw = store.read(store.SHIPPED / "maps" / "auto.yaml")
        mine = state / "crew" / "maps" / "shop.yaml"
        mine.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(mine, store.dump({"format": raw["format"], "name": "shop", "main": raw.get("main") or
                                           {"agent": "main"}, "boxes": raw["boxes"], "lines": raw["lines"]}))
        s.team_control = control_for(compile_map("shop", cwd=home / "proj", state_dir=state), cwd=home / "proj",
                                     state_dir=state)

    one("a session on a map of his", _body(), (False, "map"), prep=his_map)
    one("roles off", _body(), (False, "off"), prep=lambda s, h: setattr(s, "team_control", None))

    def outranked(home):
        s = _session(home, agents={"sorter": _spec(_body(), f"project:{home / 'proj'}")})
        got = use_now.put(s, _body(does="Other words."), "yours", SHA1)
        ctx.check(f"a project .claude/agents sorter: outranked, got {got}", got == (False, "outranked"))
        s2 = _session(home, agents={"sorter": _spec(_body(), "crew:project")})
        ctx.check("this project's crew sorter outranks a save of yours",
                  use_now.put(s2, _body(), "yours", SHA1) == (False, "outranked"))
        ctx.check("a save of the project's own takes",
                  use_now.put(s2, _body(does="New words."), "project", SHA1) == (True, ""))
    _scoped(outranked)


@test
def test_a_running_helper_keeps_its_spec(ctx: Ctx):
    from halo_harness.crew import use_now

    def run(home):
        old = _spec(_body(), "crew:yours")
        s = _session(home, agents={"sorter": old})
        held = s.agent_runtime.agents["sorter"]  # what a running helper was started from
        use_now.put(s, _body(does="Sorts by size."), "yours", SHA2)
        use_now.take(s)
        ctx.check("the helper's spec object is unchanged", held is old and held.description == _body()["does"])
        ctx.check("the session's dict holds the new one", s.agent_runtime.agents["sorter"].description == "Sorts by size.")
    _scoped(run)


@test
def test_gone_and_back(ctx: Ctx):
    from halo_harness.crew import use_now

    def changes(s):
        return [(t["name"], t["change"]) for t in use_now.take(s)]

    def run(home):
        from halo_harness.crew.map_session import agents as start_agents, prepare
        s = _session(home, agents=start_agents({}, prepare(None, home / "proj")[0])[0])  # Auto's starters, as a start
        use_now.put(s, _body(), "yours", SHA1)
        use_now.take(s)
        ctx.check("gone queues", use_now.gone(s, "sorter", "yours") is True)
        ctx.check("gone takes it out", changes(s) == [("sorter", "gone")] and "sorter" not in s.agent_runtime.agents)
        ctx.check("added is empty again", use_now.added(s) == [])

        starters = [n for n, sp in s.agent_runtime.agents.items() if not str(sp.source).startswith(("crew:yours",))
                    and n not in ("general-purpose",)]
        ctx.check(f"the session started with a starter to replace, got {starters[:3]}", bool(starters))
        name = starters[0]
        start = s.agent_runtime.agents[name]
        ctx.check(f"a put over {name} took", use_now.put(s, _body(name), "yours", SHA1) == (True, ""))
        ctx.check(f"it is told as added", changes(s) == [(name, "added")])
        ctx.check("started_with gives the start back", use_now.started_with(s)[name] is start)
        use_now.gone(s, name, "yours")
        ctx.check(f"gone puts the starter back", changes(s) == [(name, "back")] and s.agent_runtime.agents[name] is start)

        use_now.put(s, _body("tidy"), "yours", SHA1)
        use_now.take(s)
        ctx.check("back after a put queues", use_now.back(s, "tidy") is True)
        ctx.check("back removes a name the start had not", changes(s) == [("tidy", "gone")]
                  and "tidy" not in s.agent_runtime.agents)
        ctx.check("back with nothing changed is False", use_now.back(s, "tidy") is False)
        use_now.put(s, _body("tidy"), "yours", SHA2)
        use_now.gone(s, "tidy", "yours")
        ctx.check("a put and a gone before one take leave nothing", changes(s) == [] and "tidy" not in
                  s.agent_runtime.agents)
    _scoped(run)

    def project_one(home):
        s = _session(home, agents={"sorter": _spec(_body(), "crew:project")})
        ctx.check("gone of yours while the session runs the project's: False",
                  use_now.gone(s, "sorter", "yours") is False and not getattr(s, "_kinds_pending", None))
    _scoped(project_one)

    def his_start(home):
        start = _spec(_body(), "crew:yours")
        s = _session(home, agents={"sorter": start})
        use_now.put(s, _body(does="Sorts by date."), "yours", SHA2)
        got = use_now.take(s)
        ctx.check(f"an edit of his start agent is 'edited', got {got}",
                  [(t["name"], t["change"]) for t in got] == [("sorter", "edited")])
        ctx.check("the dict holds the new spec", s.agent_runtime.agents["sorter"].description == "Sorts by date.")
        ctx.check("added stays empty (no N1)", use_now.added(s) == [])
        ctx.check("gone of it queues", use_now.gone(s, "sorter", "yours") is True)
        ctx.check("gone of an edited start agent is 'gone'", changes(s) == [("sorter", "gone")]
                  and "sorter" not in s.agent_runtime.agents)
        ctx.check("started_with still has it", use_now.started_with(s).get("sorter") is start)
    _scoped(his_start)


@test
def test_the_same_body_twice_is_no_change(ctx: Ctx):
    from halo_harness.crew import use_now

    def run(home):
        s = _session(home)
        ctx.check("first put", use_now.put(s, _body(), "yours", SHA1) == (True, ""))
        ctx.check("one take entry", len(use_now.take(s)) == 1)
        ctx.check("the same body again is 'same'", use_now.put(s, _body(), "yours", SHA1) == (True, "same"))
        ctx.check("nothing to take", use_now.take(s) == [])
    _scoped(run)


@test
def test_nothing_put_changes_nothing(ctx: Ctx):
    from halo_harness.crew import use_now

    def run(home):
        s = _session(home)
        before = set(vars(s))
        ctx.check("take on a fresh session is []", use_now.take(s) == [])
        ctx.check("a refused put", use_now.put(s, _body("general-purpose"), "yours", SHA1) == (False, "built-in"))
        ctx.check("gone of nothing", use_now.gone(s, "sorter", "yours") is False)
        ctx.check("back of nothing", use_now.back(s, "sorter") is False)
        ctx.check(f"no attribute added, got {set(vars(s)) - before}", set(vars(s)) == before)
        ctx.check("started_with is the very dict", use_now.started_with(s) is s.agent_runtime.agents)
        ctx.check("added is []", use_now.added(s) == [])
    _scoped(run)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
