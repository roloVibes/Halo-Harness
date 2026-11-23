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
import json
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
ENV = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST", "BRIDGE_OPENROUTER_BASE_URL")
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


def _session(home: Path, *, agents=None, drop=(), mode: str = "default", base_url: str = DEAD):
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
                creds=ProviderCreds(base_url=base_url, api_key="k"), state_dir=home / "sess-state", model_label=MODEL,
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
        # 3.6.0.16 C1: main could start this name before the put and can after it: an edit, never "added"
        ctx.check(f"it is an edit, not added", changes(s) == [(name, "edited")] and name not in use_now.added(s))
        ctx.check("started_with gives the start back", use_now.started_with(s)[name] is start)
        use_now.gone(s, name, "yours")
        ctx.check(f"gone puts the starter back, an edit again (the name never left)",
                  changes(s) == [(name, "edited")] and s.agent_runtime.agents[name] is start)

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


# -- U5: the notes main reads (crew/kinds_note.py), letter for letter, once each, before main's next model call ----------

N1_SORTER = "[Halo] A new helper you can start now: sorter (Sorts the files it is given by kind)."
N2_SORTER = "[Halo] Taken back: sorter can no longer be started in this session."


def _notes(s) -> list:
    """Every text of every kinds_note snapshot in the session's log, in order."""
    return [b.get("text") for n in s.log.nodes() if n.get("type") == "snapshot" and n.get("kind") == "kinds_note"
            for b in n.get("content") or []]


@test
def test_n1_and_n2_letter_for_letter(ctx: Ctx):
    from halo_harness.agent.prompt_composition import tokens_of
    from halo_harness.crew import kinds_note, use_now

    def run(home):
        from halo_harness.crew.map_session import agents as start_agents, prepare
        start = start_agents({}, prepare(None, home / "proj")[0])[0]
        start["keeper"] = _spec(_body("keeper"), "crew:yours")
        s = _session(home, agents=start)
        use_now.put(s, _body(), "yours", SHA1)
        got = kinds_note.step(s)
        ctx.check(f"N1 letter for letter, got {got}", got == [N1_SORTER] and _notes(s) == [N1_SORTER])
        ctx.check(f"N1 is 24 tokens, got {tokens_of(N1_SORTER)}", tokens_of(N1_SORTER) == 24)
        snaps = [n for n in s.log.nodes() if n.get("type") == "snapshot" and n.get("kind") == "kinds_note"]
        ctx.check("one snapshot of kind kinds_note", len(snaps) == 1)
        use_now.gone(s, "sorter", "yours")
        ctx.check("N2 (gone) letter for letter", kinds_note.step(s) == [N2_SORTER])
        ctx.check(f"N2 is 20 tokens, got {tokens_of(N2_SORTER)}", tokens_of(N2_SORTER) == 20)
        # 3.6.0.16 C1: N2 (back) is told when an undo brings back a start name a delete took out
        use_now.gone(s, "keeper", "yours")
        kinds_note.step(s)
        use_now.back(s, "keeper")
        back = "[Halo] Taken back: keeper starts as it did when this session began."
        ctx.check(f"N2 (back) letter for letter, got {_notes(s)[-1:]}", kinds_note.step(s) == [back])
        ctx.check(f"N2 (back) is 20 tokens for the example", tokens_of(back.replace("keeper", "sorter")) == 20)
        use_now.put(s, _body("tidy", does="..."), "yours", SHA2)
        ctx.check(f"a kind with no words is told bare, got {_notes(s)[-1:]}",
                  kinds_note.step(s) == ["[Halo] A new helper you can start now: tidy."])
        ctx.check("nothing queued: nothing logged", kinds_note.step(s) is None and len(_notes(s)) == 5)
    _scoped(run)


@test
def test_each_name_is_told_once(ctx: Ctx):
    from halo_harness.crew import kinds_note, use_now

    def run(home):
        s = _session(home, agents={"keeper": _spec(_body("keeper"), "crew:yours")})
        use_now.put(s, _body(), "yours", SHA1)
        kinds_note.step(s)
        use_now.put(s, _body(does="Sorts by size."), "yours", SHA2)
        ctx.check("a second put of an added name with other words: no note", kinds_note.step(s) is None)
        use_now.gone(s, "sorter", "yours")
        use_now.put(s, _body(), "yours", SHA1)
        ctx.check("gone then put again before one step: N1 is not told twice", kinds_note.step(s) is None)
        use_now.gone(s, "sorter", "yours")
        kinds_note.step(s)
        use_now.put(s, _body(), "yours", SHA1)
        kinds_note.step(s)
        ctx.check(f"gone then put again: N1, N2, N1, got {_notes(s)}", _notes(s) == [N1_SORTER, N2_SORTER, N1_SORTER])
        use_now.put(s, _body("tidy"), "yours", SHA1, note=False)
        ctx.check("a put with note False (the Builder's): no N1", kinds_note.step(s) is None
                  and "tidy" in s.agent_runtime.agents)
        use_now.put(s, _body("keeper", does="Keeps the notes."), "yours", SHA2)
        ctx.check("an edit of an agent the session started with: no note", kinds_note.step(s) is None
                  and s.agent_runtime.agents["keeper"].description == "Keeps the notes.")
        ctx.check(f"three notes in all, got {_notes(s)}", len(_notes(s)) == 3)
    _scoped(run)


@test
def test_after_clear_the_added_names_are_told_again(ctx: Ctx):
    from halo_harness.crew import kinds_note, use_now

    def run(home):
        s = _session(home, agents={"keeper": _spec(_body("keeper"), "crew:yours")})
        s.clear()
        ctx.check("a clear with nothing added marks nothing", not getattr(s, "_kinds_retell", False))
        use_now.put(s, _body(), "yours", SHA1)
        use_now.put(s, _body("tidy", does="Tidies a folder."), "yours", SHA1, note=False)
        use_now.gone(s, "keeper", "yours")
        kinds_note.step(s)
        s.clear()
        got = kinds_note.step(s)
        ctx.check(f"after /clear: N1 for each added name and N2 for the start name taken out, once, got {got}",
                  got == [N1_SORTER, "[Halo] A new helper you can start now: tidy (Tidies a folder).",
                          "[Halo] Taken back: keeper can no longer be started in this session."])
        ctx.check("told once: the next step is quiet", kinds_note.step(s) is None)
        kinds_note.compacted(s)
        ctx.check("after a compaction they are told once more", len(kinds_note.step(s) or []) == 3)
    _scoped(run)


# -- 3.6.0.16 C1: main is told exactly when the set of names it can start changes -----------------------------------

N1_KEEPER = "[Halo] A new helper you can start now: keeper (Sorts the files it is given by kind)."
N2_KEEPER = "[Halo] Taken back: keeper can no longer be started in this session."
BACK_KEEPER = "[Halo] Taken back: keeper starts as it did when this session began."


def _auto_start(home, **extra):
    """A session that started with Auto's agents (crew:starter) plus `extra` -> (session, a starter's name)."""
    from halo_harness.crew.map_session import agents as start_agents, prepare
    start = start_agents({}, prepare(None, home / "proj")[0])[0]
    start.update(extra)
    s = _session(home, agents=start)
    return s, next(n for n, sp in s.agent_runtime.agents.items() if str(sp.source) == "crew:starter")


@test
def test_a_save_over_a_name_the_session_started_with_is_never_a_new_helper(ctx: Ctx):
    from halo_harness.crew import kinds_note, map_facts, use_now

    def run(home):
        s, name = _auto_start(home, keeper=_spec(_body("keeper"), "crew:yours"))
        use_now.put(s, _body("keeper", does="Keeps the notes."), "project", SHA1)  # a project's save over his agent
        use_now.put(s, _body(name), "yours", SHA2)  # a model pick on one of Auto's cards: his over the starter
        got = kinds_note.step(s)
        ctx.check(f"neither save is told, got {got}", got is None and _notes(s) == [])
        ctx.check(f"neither is added, got {use_now.added(s)}", use_now.added(s) == [])
        ctx.check("the session runs both new bodies", str(s.agent_runtime.agents["keeper"].source) == "crew:project"
                  and str(s.agent_runtime.agents[name].source) == "crew:yours")
        ctx.check("the row lists no kinds_added", "kinds_added" not in map_facts.row(s))
        s.clear()
        ctx.check("after /clear nothing is told again", kinds_note.step(s) is None)
    _scoped(run)


@test
def test_a_started_agent_deleted_then_saved_again_is_told_it_can_start(ctx: Ctx):
    from halo_harness.crew import kinds_note, use_now

    def run(home):
        s = _session(home, agents={"keeper": _spec(_body("keeper"), "crew:yours")})
        use_now.gone(s, "keeper", "yours")
        ctx.check(f"the delete is told N2, got {_notes(s)}", kinds_note.step(s) == [N2_KEEPER])
        use_now.put(s, _body("keeper"), "yours", SHA2)
        got = kinds_note.step(s)
        ctx.check(f"saved again: N1 once, got {got}", got == [N1_KEEPER] and "keeper" in s.agent_runtime.agents)
        ctx.check("not 'Added in this session': main could start it when the session began", use_now.added(s) == [])
        ctx.check("told once: the next step is quiet", kinds_note.step(s) is None)
        s.clear()
        ctx.check("after /clear nothing to retell (its start block names it)",
                  kinds_note.step(s) is None and "keeper" in use_now.started_with(s))
        use_now.gone(s, "keeper", "yours")
        kinds_note.step(s)
        kinds_note.compacted(s)
        ctx.check(f"deleted again, then a compaction: N2 told once more, got {_notes(s)[-2:]}",
                  kinds_note.step(s) == [N2_KEEPER] and _notes(s)[-2:] == [N2_KEEPER, N2_KEEPER])
        use_now.put(s, _body("keeper"), "yours", SHA1, note=False)
        ctx.check("a put with note False (the Builder's) tells nothing", kinds_note.step(s) is None
                  and "keeper" in s.agent_runtime.agents and use_now.added(s) == [])
    _scoped(run)


@test
def test_the_undo_of_a_change_main_never_read_is_not_told(ctx: Ctx):
    from halo_harness.crew import kinds_note, use_now

    def run(home):
        start = _spec(_body("keeper"), "crew:yours")
        s, name = _auto_start(home, keeper=start)
        use_now.put(s, _body("keeper", does="Keeps the notes."), "yours", SHA2)
        kinds_note.step(s)
        ctx.check("an undo of an edit queues", use_now.back(s, "keeper") is True)
        got = kinds_note.step(s)
        ctx.check(f"the undo of an edit is not told, got {got}", got is None
                  and s.agent_runtime.agents["keeper"] is start)
        held = s.agent_runtime.agents[name]
        use_now.put(s, _body(name), "yours", SHA1)
        kinds_note.step(s)
        ctx.check("the delete of the replacing file queues", use_now.gone(s, name, "yours") is True)
        got = kinds_note.step(s)
        ctx.check(f"the starter is back and nothing is told, got {got}", got is None
                  and s.agent_runtime.agents[name] is held)
        ctx.check(f"nothing was ever told, got {_notes(s)}", _notes(s) == [])
    _scoped(run)


@test
def test_the_undo_of_a_delete_is_told(ctx: Ctx):
    from halo_harness.crew import kinds_note, use_now

    def run(home):
        start = _spec(_body("keeper"), "crew:yours")
        s = _session(home, agents={"keeper": start})
        use_now.gone(s, "keeper", "yours")
        ctx.check("the delete: N2", kinds_note.step(s) == [N2_KEEPER] and "keeper" not in s.agent_runtime.agents)
        ctx.check("the undo queues", use_now.back(s, "keeper") is True)
        ctx.check(f"the undo: N2 (back) once, got {_notes(s)}", kinds_note.step(s) == [BACK_KEEPER]
                  and s.agent_runtime.agents["keeper"] is start)
        ctx.check("told once: the next step is quiet", kinds_note.step(s) is None)
        s.clear()
        ctx.check("after /clear nothing to retell", kinds_note.step(s) is None)
    _scoped(run)


def _turns(home, prompts, between=None, *, stand_in: bool = False) -> dict:
    """REAL turns of a session on Auto against the mock upstream (every reply `ok.`); `between(s, i)` runs after turn
    i. `stand_in`: 3.6.0.14 -- kinds_note.step a no-op and use_now.started_with the session's agents."""
    from halo_harness.crew import kinds_note, use_now
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, ScriptedTurns
    from tests.helpers.session_rig import text_step
    mock = MockUpstream().start()
    real_step, real_started = kinds_note.step, use_now.started_with
    os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
    SCENARIOS["use-now"] = ScriptedTurns([text_step("ok.")])
    out: dict = {"errors": []}
    try:
        if stand_in:
            kinds_note.step = lambda session: None
            use_now.started_with = lambda session: session.agent_runtime.agents
        s = _session(home, base_url=mock.base_url)
        s._map_started_at = 1000.0
        for i, p in enumerate(prompts):
            try:
                list(s.turn(p))
            except Exception as e:
                out["errors"].append(e)
            if between:
                between(s, i)
        out["session"] = s
        out["requests"] = [r.get("body") or {} for r in mock.requests if r.get("method") == "POST"
                           and str(r.get("path", "")).endswith("/chat/completions")]
        return out
    finally:
        kinds_note.step, use_now.started_with = real_step, real_started
        mock.stop()
        SCENARIOS.pop("use-now", None)


def _dumped(body: dict) -> str:
    import re
    return re.sub(r"Today's date: [^\\\"]*", "Today's date: D", json.dumps(body, sort_keys=True))


@test
def test_the_note_rides_the_next_request(ctx: Ctx):
    from halo_harness.crew import use_now

    def run(home):
        def between(s, i):
            if i == 0:
                ctx.check("the put from outside took", use_now.put(s, _body(), "yours", SHA1) == (True, ""))
        out = _turns(home, ["first", "second", "third"], between)
        reqs = out["requests"]
        ctx.check(f"three turns, three requests, no error, got {len(reqs)} {out['errors']}",
                  len(reqs) == 3 and not out["errors"])
        texts = [json.dumps(r.get("messages") or []) for r in reqs]
        n1 = json.dumps(N1_SORTER)[1:-1]
        ctx.check("request 1 has no note", n1 not in texts[0])
        ctx.check(f"request 2 holds N1 once, after the user's text, got {texts[1].count(n1)}",
                  texts[1].count(n1) == 1 and texts[1].find(n1) > texts[1].find("second"))
        ctx.check(f"request 3 holds it once (from the log), got {texts[2].count(n1)}", texts[2].count(n1) == 1)
        ctx.check("main can start sorter", "sorter" in out["session"].agent_runtime.agents)
    _scoped(run)


@test
def test_a_session_with_no_agent_added_sends_byte_for_byte(ctx: Ctx):
    from halo_harness.crew import use_now

    def run(home):
        def put_and_gone(s, i):
            if i == 0:
                use_now.put(s, _body(), "yours", SHA1)
                use_now.gone(s, "sorter", "yours")
        for label, between in (("nothing put", None), ("a put then a gone before turn 2", put_and_gone)):
            _fresh_home(home)
            built = _turns(home, ["first", "second"], between)
            _fresh_home(home)
            old = _turns(home, ["first", "second"], between, stand_in=True)
            a, b = [_dumped(r) for r in built["requests"]], [_dumped(r) for r in old["requests"]]
            ctx.check(f"{label}: two requests each, no error, got {len(a)} {len(b)}",
                      len(a) == len(b) == 2 and not built["errors"] and not old["errors"])
            ctx.check(f"{label}: every request body (system, tools, messages) byte-equal", a == b)
    _scoped(run)


def _fresh_home(home: Path) -> None:
    """The same home path, empty again (a second run whose paths equal the first's)."""
    shutil.rmtree(home, ignore_errors=True)
    home.mkdir()
    (home / "proj").mkdir()


@test
def test_a_session_that_takes_nothing_loses_nothing(ctx: Ctx):
    """3.6.0.15 (the review's must): a session that is not on Auto (a map of his, roles off) takes no put, and a
    delete in Studio or a Builder undo takes nothing out of it either: its agent stays, nothing is queued and main
    is told nothing. A delete of yours does not cancel a project's save that waits for the take."""
    def run(home):
        from halo_harness.crew import kinds_note, store, use_now
        from halo_harness.crew.compile import compile_map
        from halo_harness.crew.map_control import control_for
        from halo_harness.providers.config import default_state_dir
        for label in ("a map of his", "roles off"):
            s = _session(home, agents={"sorter": _spec(_body(), "crew:yours")})
            if label == "roles off":
                s.team_control = None
            else:
                state = Path(default_state_dir())
                raw = store.read(store.SHIPPED / "maps" / "auto.yaml")
                mine = state / "crew" / "maps" / "shop.yaml"
                mine.parent.mkdir(parents=True, exist_ok=True)
                store.write_text(mine, store.dump({"format": raw["format"], "name": "shop",
                                                   "main": raw.get("main") or {"agent": "main"},
                                                   "boxes": raw["boxes"], "lines": raw["lines"]}))
                s.team_control = control_for(compile_map("shop", cwd=home / "proj", state_dir=state),
                                             cwd=home / "proj", state_dir=state)
            ctx.check(f"{label}: the session takes nothing", use_now.can_take(s) is False)
            ctx.check(f"{label}: a delete queues nothing, got {use_now.gone(s, 'sorter', 'yours')}",
                      use_now.gone(s, "sorter", "yours") is False)
            ctx.check(f"{label}: a Builder undo queues nothing", use_now.back(s, "sorter") is False)
            said = kinds_note.step(s)
            ctx.check(f"{label}: main is told nothing and the agent stays, got {said!r}",
                      not said and "sorter" in s.agent_runtime.agents and not getattr(s, "_kinds_pending", None))
        s = _session(home)
        took = use_now.put(s, _body(), "project", SHA1)
        ctx.check(f"on Auto a project's save waits for the take, got {took}", took == (True, ""))
        ctx.check("a delete of YOURS does not cancel it", use_now.gone(s, "sorter", "yours") is False)
        use_now.take(s)
        ctx.check("the project's agent is in the session after the take", "sorter" in s.agent_runtime.agents)
    _scoped(run)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
