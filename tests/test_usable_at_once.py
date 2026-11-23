"""tests.test_usable_at_once -- Halo 3.6.0.15 UN: an agent saved while a session runs is usable in that session at
once. U3: after a 200 of Studio's POST, PUT or DELETE crew/agent/<name>, the save reaches each live top session whose
folder sees its scope (studio/crew_push.py over the control socket's agent_put / agent_gone), skips a row marked
`unreachable_since`, and the answer gains `live`; a refused save asks nobody.

Real Sessions on the default map with real control sockets and a real Studio server (tests/helpers/crew_rig.py), a mock
upstream: nothing calls a model. Every session, socket and patch is closed or put back in a finally.
Run: python -m tests.test_usable_at_once
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MODEL = "or:mock/usable-at-once"


def _agent(name: str, does: str = "Sorts the files it is given by kind.") -> dict:
    return {"format": "agent/1", "name": name, "does": does, "uses": ["read"], "careful": "ask-changes", "model": "auto"}


def _trust(folder: Path) -> None:
    from halo_harness.config.paths import claude_json_path
    cj = claude_json_path()
    cj.parent.mkdir(parents=True, exist_ok=True)
    key = str(folder.absolute()).replace("\\", "/")
    cj.write_text(json.dumps({"projects": {key: {"hasTrustDialogAccepted": True}}}), encoding="utf-8")


def _session(rig, cwd: Path):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.crew.map_session import prepare
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.registry import ToolRegistry, default_tools
    return Session(cwd=cwd, model_ref=parse_model_ref(MODEL), model_profile=ModelProfile(),
                   creds=ProviderCreds(base_url=rig.mock.base_url, api_key="k"),
                   state_dir=Path(tempfile.mkdtemp(prefix="sess-", dir=str(rig.root))), model_label=MODEL,
                   crew_map=prepare(None, cwd)[0], openrouter_base_url=rig.mock.base_url, max_turns=4,
                   session_context=SessionContext(cwd=cwd, model_label=MODEL, tool_registry=ToolRegistry(default_tools())),
                   permission_engine=PermissionEngine(mode="default", cwd=cwd))


def _asked(session) -> list:
    """(cmd, name) of every agent_put / agent_gone this session's socket ran (main's transcript records each)."""
    return [(n["control"]["cmd"], n["control"].get("name")) for n in session.log.nodes()
            if n.get("type") == "meta" and isinstance(n.get("control"), dict)
            and n["control"].get("cmd") in ("agent_put", "agent_gone")]


@test
def test_a_save_reaches_the_sessions_that_see_it_two_projects_one_reached(ctx: Ctx):
    from halo_harness.agent.helpers_words import on_auto
    from halo_harness.controller import Controller
    from halo_harness.remote import agent_control, registry, runtime
    from halo_harness.remote.base import HandleError
    from tests.helpers.crew_rig import CrewRig
    from tests.helpers.fake_remote_session import FakeRegistry
    controllers: list = []
    real_run, real_live = agent_control.run, registry.list_live
    with CrewRig() as rig:
        try:
            other = rig.root / "other"
            other.mkdir()
            _trust(rig.proj)
            proj_agent = rig.proj / ".halo" / "crew" / "agents" / "sorter.yaml"
            proj_agent.parent.mkdir(parents=True, exist_ok=True)
            from halo_harness.crew import store
            store.write_text(proj_agent, store.dump(_agent("sorter")))
            names = ("a", "b", "old", "far")
            sessions = {k: _session(rig, rig.proj if k != "b" else other) for k in names}
            ctx.check("every session is on Auto", all(on_auto(s) for s in sessions.values()))
            ids = {}
            for k, s in sessions.items():
                c = Controller(session=s, cwd=s.cwd, registry=FakeRegistry()).start()
                controllers.append(c)
                act = runtime.start_for_controller(c)
                ctx.check(f"session {k}: its socket opened", act is not None)
                ids[k] = act.session_id if act is not None else None
            old_session = sessions["old"]

            def older(handle, req, conn=None):  # a session of a release before agent_put: its socket refuses
                if handle.session is old_session and req.get("cmd") in ("agent_put", "agent_gone"):
                    raise HandleError(f"unknown agent cmd {req.get('cmd')!r}")
                return real_run(handle, req, conn)

            def live():  # the row of `far` is marked as a failing probe marks it
                rows = real_live()
                return [dict(r, unreachable_since=1.0) if r.get("session_id") == ids["far"] else r for r in rows]
            agent_control.run, registry.list_live = older, live
            rig.studio()

            def by_sid(items) -> dict:
                return {next(k for k, v in ids.items() if v == it["session_id"]): {x: y for x, y in it.items()
                                                                                   if x != "session_id"}
                        for it in items}

            status, got = rig.api("PUT", "crew/agent/sorter", {"agent": _agent("sorter", "Sorts by kind and size.")})
            ctx.check(f"PUT of the project's sorter: 200 and only this project's sessions, got {status} {got.get('live')}",
                      status == 200 and by_sid(got.get("live") or []) == {
                          "a": {"took": True, "why": ""}, "old": {"took": False, "why": "unreached"}})
            status, got = rig.api("POST", "crew/agent/tidy", {"agent": _agent("tidy", "Tidies a folder.")})
            ctx.check(f"POST of yours: every reachable top session, got {status} {got.get('live')}",
                      status == 200 and by_sid(got.get("live") or []) == {
                          "a": {"took": True, "why": ""}, "b": {"took": True, "why": ""},
                          "old": {"took": False, "why": "unreached"}})
            before = {k: len(_asked(s)) for k, s in sessions.items()}
            status, got = rig.api("POST", "crew/agent/tidy", {"agent": _agent("tidy")})
            ctx.check(f"a 409 has no `live`, got {status} {sorted(got)}", status == 409 and "live" not in got)
            status, got = rig.api("PUT", "crew/agent/bad", {"agent": {"name": "bad", "does": "x"}})
            ctx.check(f"a 422 has no `live`, got {status} {sorted(got)}", status == 422 and "live" not in got)
            ctx.check("a refused save asks no session", {k: len(_asked(s)) for k, s in sessions.items()} == before)
            status, got = rig.api("DELETE", "crew/agent/tidy")
            ctx.check(f"DELETE of yours: queued in each, got {status} {got.get('live')}",
                      status == 200 and by_sid(got.get("live") or []) == {
                          "a": {"queued": True}, "b": {"queued": True}, "old": {"queued": False}})
            ctx.check(f"session a ran each command once, got {_asked(sessions['a'])}", _asked(sessions["a"]) == [
                ("agent_put", "sorter"), ("agent_put", "tidy"), ("agent_gone", "tidy")])
            ctx.check(f"session b was never asked about the project's sorter, got {_asked(sessions['b'])}",
                      _asked(sessions["b"]) == [("agent_put", "tidy"), ("agent_gone", "tidy")])
            ctx.check(f"the unreachable row's socket saw no request, got {_asked(sessions['far'])}",
                      _asked(sessions["far"]) == [])
        finally:
            agent_control.run, registry.list_live = real_run, real_live
            runtime.stop()
            for c in controllers:
                try:
                    c.quit()
                except Exception:
                    pass
            runtime._private_flag = None
            runtime._reopeners[:] = []


# -- U6: end to end (the design's S9): saved while a session runs, told (N1), started, shown, taken back (N2) ------------

N1 = "[Halo] A new helper you can start now: {name} ({words})."
N2 = "[Halo] Taken back: {name} can no longer be started in this session."
JOB = "SORT-JOB: sort what is in the folder."


def _main_script(steps: list, child: list, extra: "dict | None" = None):
    """main's replies in request order (`steps`); a request whose first user message holds JOB is the child's, answered
    `Sorted.` and kept in `child`. Every main request body is kept in `.seen`."""
    from tests.helpers.mock_openai import _finish

    def first_user(body) -> str:
        for m in (body or {}).get("messages") or []:
            if isinstance(m, dict) and m.get("role") == "user":
                return json.dumps(m.get("content"))
        return ""

    def scenario(handler, body):
        if "SORT-JOB" in first_user(body):
            child.append(body)
            from tests.helpers.session_rig import text_step
            _finish(handler, text_step("Sorted."))
            return
        scenario.seen.append(body)
        _finish(handler, steps[min(len(scenario.seen), len(steps)) - 1])
    scenario.seen = []
    return scenario


JUDGE_ROW = {"agent_id": "j1", "parent": "main", "name": "Judge", "state": "done", "model": MODEL, "task": "judge it",
             "spawn": {"step": "main#1", "description": "judge", "lead": "", "source": "built-in"}}
MADE_NOW = "Made judge, an agent of yours on {model}: main can start it now, unless it names a model itself."


def _save(ctx: Ctx, rig, sid: str, name: str, agent: "dict | None", child_model: "str | None"):
    """The save leg: the Agents form's POST, or (agent None, OP2 O2-3) Studio's pick at the session's Judge box, whose
    row the real session's own row gains (the drawing's helper; nothing else of the row is stood in). -> (words, undo)"""
    if agent is not None:
        status, got = rig.api("POST", f"crew/agent/{name}", {"agent": agent})
        ctx.check(f"{name}: POST 200, the running session took it, got {status} {got.get('live')}",
                  status == 200 and [(x.get("took"), x.get("why")) for x in got.get("live") or []] == [(True, "")])
        return None, None
    from halo_harness.crew import store
    from halo_harness.crew.kinds_note import n1
    from halo_harness.crew.spec import agent_spec
    from halo_harness.peers import local_view
    real = local_view.sessions
    local_view.sessions = lambda list_live=None: [
        dict(r, agents=list(r.get("agents") or []) + [JUDGE_ROW]) if r.get("session_id") == sid else r
        for r in real(list_live)]
    try:
        status, got = rig.api("POST", "crew/agent-model", {"session": sid, "agent": "j1", "model": child_model})
    finally:
        local_view.sessions = real
    ctx.check(f"judge: the pick made judge and the session took it, got {status} {got.get('line')!r}",
              status == 200 and got.get("line") == MADE_NOW.format(model=child_model))
    made = store.load("agent", "judge", scope="yours")
    ctx.check("judge: his file is on the pick", (made or {}).get("model") == child_model)
    return n1("judge", agent_spec(store.clean(made or {}))), got.get("undo")


def _run_live(ctx: Ctx, name: str, agent: "dict | None", words: str, child_model: "str | None",
              undo_leg: bool = True) -> None:
    """A real session on Auto, its socket registered, Studio's real server: turn 1; POST crew/agent/<name> (or the pick:
    `agent` None); turn 2 (main starts it); DELETE (or the pick's Undo); turn 3. `child_model`: the model the agent
    names, whose scenario must get the child's request."""
    from halo_harness.controller import Controller
    from halo_harness.crew import map_facts
    from halo_harness.peers.local_view import session_row
    from halo_harness.remote import runtime
    from tests.helpers.crew_rig import CrewRig
    from tests.helpers.fake_remote_session import FakeRegistry
    from tests.helpers.mock_openai import SCENARIOS
    from tests.helpers.session_rig import text_step, tool_step
    child: list = []
    on_model: list = []
    steps = [text_step("ok."), tool_step(("Agent", {"description": "sort", "prompt": JOB, "subagent_type": name}, "call_a")),
             text_step("Done."), text_step("ok.")]
    controllers: list = []
    with CrewRig() as rig:
        main = _main_script(steps, child)
        SCENARIOS["usable-at-once"] = main
        if child_model:
            other = _main_script([text_step("Sorted.")], on_model)
            SCENARIOS[child_model.split("/", 1)[1]] = other
        try:
            s = _session(rig, rig.proj)
            c = Controller(session=s, cwd=s.cwd, registry=FakeRegistry()).start()
            controllers.append(c)
            act = runtime.start_for_controller(c)
            ctx.check(f"{name}: the session's socket opened", act is not None)
            rig.studio()
            list(s.turn("first"))
            before = map_facts.row(s)
            told, token = _save(ctx, rig, act.session_id if act is not None else "", name, agent, child_model)
            list(s.turn("use it"))
            n1 = told or N1.format(name=name, words=words)
            texts = [json.dumps(b.get("messages") or []) for b in main.seen]
            ctx.check(f"{name}: three main requests so far, got {len(texts)}", len(texts) == 3)
            q = json.dumps(n1)[1:-1]
            ctx.check(f"{name}: N1 rides main's next request once, got {[t.count(q) for t in texts]}",
                      len(texts) >= 3 and texts[0].count(q) == 0 and texts[1].count(q) == 1 and texts[2].count(q) == 1)
            results = [str(n.get("content")) for n in s.log.nodes() if n.get("type") == "tool_result"]
            ctx.check(f"{name}: main started it and the child ran, got {results[-1:]!r}",
                      results and "Sorted." in results[-1] and "Unknown subagent_type" not in results[-1])
            if child_model:
                ctx.check(f"{name}: the child's request went to {child_model}, got {len(on_model)} there, "
                          f"{len(child)} on main's model", len(on_model) == 1 and not child)
            else:
                ctx.check(f"{name}: the child ran once, got {len(child)}", len(child) == 1)
            row = session_row({"session_id": "s-e2e", "cwd": str(rig.proj)}, map_facts.row(s), [])
            ctx.check(f"{name}: the row says use_now and kinds_added, got {row.get('use_now')} {row.get('kinds_added')}",
                      row.get("use_now") is True and row.get("kinds_added") == [name])
            ctx.check(f"{name}: map_agents and kinds_told are what main started with",
                      row.get("map_agents") == before.get("map_agents") and name not in (row.get("map_agents") or [])
                      and row.get("kinds_told") == before.get("kinds_told"))
            if not undo_leg:
                return
            if agent is None:
                status, got = rig.api("POST", "crew/agent-model/undo", {"undo": token})
                ctx.check(f"{name}: Undo of the pick: Taken back, got {status} {got}",
                          status == 200 and got.get("line") == "Taken back: judge is gone.")
            else:
                status, got = rig.api("DELETE", f"crew/agent/{name}")
                ctx.check(f"{name}: DELETE 200, queued, got {status} {got.get('live')}",
                          status == 200 and [x.get("queued") for x in got.get("live") or []] == [True])
            list(s.turn("third"))
            last = json.dumps(main.seen[-1].get("messages") or []) if main.seen else ""
            q2 = json.dumps(N2.format(name=name))[1:-1]
            ctx.check(f"{name}: the next request carries N2 once, got {last.count(q2)}", last.count(q2) == 1)
            ctx.check(f"{name}: taken back: not startable, no kinds_added",
                      name not in s.agent_runtime.agents and "kinds_added" not in map_facts.row(s))
        finally:
            runtime.stop()
            for c in controllers:
                try:
                    c.quit()
                except Exception:
                    pass
            runtime._private_flag = None
            runtime._reopeners[:] = []
            SCENARIOS.pop("usable-at-once", None)
            if child_model:
                SCENARIOS.pop(child_model.split("/", 1)[1], None)


@test
def test_a_save_while_a_session_runs_is_started_at_once(ctx: Ctx):
    _run_live(ctx, "sorter", _agent("sorter"), "Sorts the files it is given by kind", None)


@test
def test_an_agent_saved_on_a_model_starts_on_that_model(ctx: Ctx):
    """The stand-in for OP2's Judge pick (ruled: UN saves `judge` on a model through the Agents form's POST and takes
    it back with DELETE; OP2 adds the pick and Undo legs)."""
    from halo_harness.crew.kinds import BUILTIN_WORDS
    does = BUILTIN_WORDS["Judge"][:1].upper() + BUILTIN_WORDS["Judge"][1:] + "."
    body = dict(_agent("judge", does), model="or:mock/auto-cheap")
    _run_live(ctx, "judge", body, does.rstrip("."), "or:mock/auto-cheap")


# -- OP2 O2-3: the pick and Undo legs UN's ruling 6 left to OP2, on the same real session ---------------------------------

@test
def test_a_judge_pick_makes_judge_started_in_this_session(ctx: Ctx):
    """Studio's POST crew/agent-model at the session's Judge box on a model: `judge` made through the form's POST, the
    running session took it (the line's now form), N1 once, main starts `judge` and its request goes to that model."""
    _run_live(ctx, "judge", None, "", "or:mock/auto-cheap", undo_leg=False)


@test
def test_undo_of_the_pick_takes_judge_back(ctx: Ctx):
    """POST crew/agent-model/undo: "Taken back: judge is gone.", and main's next request carries N2 once."""
    _run_live(ctx, "judge", None, "", "or:mock/auto-cheap")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
