"""tests.test_auto_groups -- Halo 3.6.0.5 "Auto's own groups" (package b).

Batch 1 (B23, F1, decisions 4 and round 3 J2 M4, F10): main is asked to name the piece of work each helper belongs to
(`task`, 2 to 6 words) on the Agent and the Task tool alike (one schema, one check). `task` is in `required` as main sees
it; `agent/repair.py check_schema` is the ONE place that hands back, for Agent and Task only, a copy without it, so a call
that leaves `task` out still runs exactly as on 3.6.0.4: through the loop's resolver (`Session._resolve_tool_call`) and
through a local model's repair round (`_attempt_tool_repair_once`). The recorded plain-session requests (R38) were
recorded once more for `task`, and `test_r38_fixture_differs_only_by_task` proves that is the only difference from
3.6.0.4's (kept as tests/fixtures/map_facts_plain_requests_3604.json, never edited).

Batch 2 (B2, B3, B6, B28, B29): every helper's row says its piece of work (`spawn.task`) and its group
(`spawn.group {key, n, by}`, crew/groups.py), in every session: the same task words join one group across replies, a
call without `task` is keyed by its reply, a helper started by a helper is in its parent's group, each run of a saved
workflow is its own group from its first step, numbers 1, 2, 3 in start order never change and group frames leave in
the order of their numbers. The Builder's refusal to change a shipped agent says "ships with Halo".

Mock upstreams (OpenRouter-shaped and Ollama-shaped, loopback), a scratch home, no real model.
Run: python -m tests.test_auto_groups
"""
from __future__ import annotations

import inspect
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_default_provider_credentials()
test, TESTS = new_registry()

TASK_WORDS = ("Required: the piece of work this agent is part of, in 2 to 6 words, at most 60 characters (\"fix the "
              "login bug\"). Agents that work on the same piece of work get the same words, also in later replies; a "
              "new piece of work gets new words. Studio draws each piece of work as one named group.")
LEAN_TASK = "2-6 words naming the piece of work; the same words join one group"
CALL = {"description": "read report A", "prompt": "read it"}  # no `task`: as every caller of 3.6.0.4 sends it
CHILD_SAID = "REPORT A SAYS HELLO"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
_ENV = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST", "HALO_NO_UPDATER", "BRIDGE_TEST_NO_BACKGROUND_NET")


class _Env:
    """A scratch home for one test; OLLAMA_HOST on a dead port unless a test points it at its own loopback mock."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _ENV}
        root = Path(tempfile.mkdtemp(prefix="auto-groups-"))
        self.home, self.state_dir, self.cwd = root / "home", root / "home" / ".halo", root / "project"
        self.cwd.mkdir(parents=True)
        self.state_dir.mkdir(parents=True)
        os.environ.update({"BRIDGE_TEST_HOME": str(self.home), "BRIDGE_STATE_DIR": str(self.state_dir),
                           "OLLAMA_HOST": "http://127.0.0.1:9", "HALO_NO_UPDATER": "1",
                           "BRIDGE_TEST_NO_BACKGROUND_NET": "1"})
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _tool_names(body) -> set:
    out = set()
    for t in (body or {}).get("tools") or []:
        f = (t.get("function") or t) if isinstance(t, dict) else {}
        if isinstance(f, dict) and f.get("name"):
            out.add(f["name"])
    return out


def _is_child(body) -> bool:
    """The child's spec takes Agent and Task away (as tests/test_subagent_e2e.py's does): main always has them."""
    return not ({"Agent", "Task"} & _tool_names(body))


def _gp_spec():
    from halo_harness.config.agents_md import AgentSpec
    return AgentSpec(name="general-purpose", description="general purpose sub-agent", tools=None,
                     disallowed_tools=["Agent", "Task"], body="You are a helpful sub-agent.")


def _session(e: _Env, *, model: str, base_url: str, api_key: str = "k"):
    """A real Session over a loopback mock (the shape of tests/test_subagent_e2e.py `_new_session`)."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    return Session(cwd=e.cwd, model_ref=parse_model_ref(model), model_profile=ModelProfile(),
                   creds=ProviderCreds(base_url=base_url, api_key=api_key), state_dir=e.state_dir, model_label=model,
                   session_context=SessionContext(cwd=e.cwd, model_label=model, bare=True),
                   openrouter_base_url=base_url, max_turns=10,
                   permission_engine=PermissionEngine(mode="auto", cwd=e.cwd),
                   agents={"general-purpose": _gp_spec()}, routes={})


def _record_resolves(session) -> list:
    """Wrap the session's own resolver: every item it returns is recorded. `_unwrap` restores it."""
    got: list = []
    orig = session._resolve_tool_call

    def wrapped(tu, outcome, flags):
        item = orig(tu, outcome, flags)
        got.append(item)
        return item

    session._resolve_tool_call = wrapped
    return got


def _unwrap(session) -> None:
    session.__dict__.pop("_resolve_tool_call", None)


def _children(session) -> list:
    from halo_harness.agent.agent_registry import tree_for
    return [r for r in tree_for(session).public_rows() if r.get("kind") != "job" and r.get("agent_id") != "main"]


def _check_the_turn(ctx: Ctx, label: str, session, events: list, resolved: list, seen: dict, name: str) -> None:
    mine = [i for i in resolved if i.get("name") == name]
    ctx.check(f"{label}: the resolver returned one item for the {name} call, ready, got {mine!r}",
              len(mine) == 1 and mine[0].get("ready") is True)
    results = [str((ev.data or {}).get("content", "")) for ev in events if ev.kind == "tool_result"]
    ctx.check(f"{label}: no tool result begins 'Invalid arguments', got {[r[:120] for r in results]}",
              results and not any(r.startswith("Invalid arguments") for r in results))
    rows = _children(session)
    ctx.check(f"{label}: the child ran and its row ends done, got {[(r.get('agent_id'), r.get('state')) for r in rows]}",
              len(rows) == 1 and rows[0].get("state") == "done")
    group = ((rows[0].get("spawn") if rows else None) or {}).get("group") or {}
    ctx.check(f"{label}: a call without task runs and is keyed by its reply (B23), got {group!r}",
              group.get("by") == "reply" and str(group.get("key") or "").startswith("reply:"))
    follow = seen.get("followup") or []
    ctx.check(f"{label}: main's next request carries the child's text as the call's tool result, got {follow!r}"[:600],
              len(follow) == 1 and CHILD_SAID in json.dumps(follow[0].get("content")))


def _run_openrouter_turn(ctx: Ctx, name: str) -> None:
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
    seen: dict = {}

    def scenario(h, body):  # records only; every check runs on the test's own thread
        msgs = [m for m in body.get("messages") or [] if isinstance(m, dict)]
        if _is_child(body):
            _finish(h, _text(CHILD_SAID))
        elif any(m.get("role") == "tool" for m in msgs):
            seen["followup"] = [m for m in msgs if m.get("role") == "tool"]
            _finish(h, _text("Main is done."))
        else:
            _finish(h, _call(name, CALL))

    scn = f"auto-groups-{name.lower()}"
    SCENARIOS[scn] = scenario
    mock = MockUpstream().start()
    try:
        with _Env() as e:
            session = _session(e, model=f"or:mock/{scn}", base_url=mock.base_url)
            resolved = _record_resolves(session)
            try:
                events = list(session.turn("read report A with a sub-agent"))
            finally:
                _unwrap(session)
            _check_the_turn(ctx, name, session, events, resolved, seen, name)
    finally:
        mock.stop()
        SCENARIOS.pop(scn, None)


def _text(text: str) -> list:
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"content": text}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}]


def _call(name: str, args: dict) -> list:
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                                                                "function": {"name": name, "arguments": json.dumps(args)}}]}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]}]


def _schema_asserts(ctx: Ctx, tool, label: str) -> None:
    from halo_harness.tools.agent import INPUT_SCHEMA
    schema = tool.input_schema
    ctx.check(f"{label}: `task` and `description` are required, got {schema.get('required')!r}",
              "task" in schema.get("required", []) and "description" in schema.get("required", []))
    prop = INPUT_SCHEMA["properties"].get("task") or {}
    ctx.check(f"{label}: the task property's words are section 3's, letter for letter, got {prop.get('description')!r}",
              prop.get("description") == TASK_WORDS and prop.get("type") == "string")
    ctx.check(f"{label}: the property carries no maxLength (the engine cuts a longer one), got {prop!r}",
              "maxLength" not in prop)


@test
def test_agent_tool_requires_task_and_still_runs_without_it(ctx: Ctx):
    """The Agent schema asks for `task`; one real turn whose Agent call leaves it out goes through the loop's own
    resolver (ready), runs the child (done) and hands its text back as the call's result."""
    from halo_harness.tools.agent import AgentTool
    _schema_asserts(ctx, AgentTool(), "Agent")
    _run_openrouter_turn(ctx, "Agent")


@test
def test_task_tool_without_task_runs(ctx: Ctx):
    """The Task tool is treated exactly as Agent: the same schema, the same check, the same real turn."""
    from halo_harness.tools.agent import TaskTool
    _schema_asserts(ctx, TaskTool(), "Task")
    _run_openrouter_turn(ctx, "Task")


@test
def test_check_schema_is_the_one_place(ctx: Ctx):
    """`check_schema` drops `task` from `required` for Agent and Task only, on a copy; every other tool's schema comes
    back as it is; the repair check and the loop's repair round both call it, and loop.py calls it once."""
    import copy
    from halo_harness.agent import repair
    from halo_harness.agent.loop import Session
    from halo_harness.tools.agent import AgentTool
    from halo_harness.tools.registry import default_tools
    check_schema = getattr(repair, "check_schema", None)
    ctx.check("agent/repair.py has check_schema", callable(check_schema))
    if not callable(check_schema):
        return
    s = AgentTool().input_schema
    before = copy.deepcopy(s)
    for name in ("Agent", "Task"):
        got = check_schema(name, s)
        ctx.check(f"{name}: a copy without task in required, got {got.get('required')!r}",
                  got is not s and "task" not in got.get("required", []) and "description" in got.get("required", []))
    ctx.check("the schema itself is not mutated", s == before and "task" in s["required"])
    others = [t for t in default_tools(platform="linux") if t.name not in ("Agent", "Task")]
    bad = [t.name for t in others if check_schema(t.name, t.input_schema) != t.input_schema]
    ctx.check(f"every other tool's schema comes back equal, got {bad}", others and not bad)
    ctx.check("a tool not named Agent or Task keeps a required task", check_schema("Read", s) is s)
    src = inspect.getsource(repair.repair_tool_use_block)
    line = next((ln for ln in src.splitlines() if ln.strip().startswith("schema =")), "")
    ctx.check(f"repair_tool_use_block sets schema through check_schema, got {line.strip()!r}", "check_schema(" in line)
    once = inspect.getsource(Session._attempt_tool_repair_once)
    ctx.check("the loop's repair round validates through check_schema", "check_schema(" in once)
    import halo_harness.agent.loop as loop_mod
    n = Path(loop_mod.__file__).read_text(encoding="utf-8").count("check_schema(")
    ctx.check(f"loop.py calls check_schema exactly once, got {n}", n == 1)


@test
def test_lean_agent_params_name_task(ctx: Ctx):
    """The lean wire copy (a local model, a small window) carries `task` with its short words, and required."""
    from halo_harness.tools.agent import AgentTool, TaskTool
    from halo_harness.tools.lean_descriptions import lean_definition
    for tool in (AgentTool(), TaskTool()):
        lean = lean_definition(tool.definition())
        schema = lean.get("input_schema") or {}
        prop = (schema.get("properties") or {}).get("task") or {}
        ctx.check(f"{tool.name}: lean task words, got {prop!r}", prop.get("description") == LEAN_TASK)
        ctx.check(f"{tool.name}: task in the lean required, got {schema.get('required')!r}",
                  "task" in (schema.get("required") or []))


@test
def test_repaired_local_reply_without_task_runs(ctx: Ctx):
    """On a local model (Ollama route), a reply the repair round fixed that still leaves `task` out runs, as on
    3.6.0.4: `_attempt_tool_repair_once` hands the dict back, and a malformed Agent call whose repaired reply has no
    task goes through `_resolve_tool_call` ready and is dispatched."""
    from tests.helpers.mock_ollama import MockUpstream, _finish_chat
    from halo_harness.tools.agent import AgentTool
    seen: dict = {"repairs": 0}

    def done(h, msg):  # no prompt_eval_count: a small count would read as a prompt Ollama cut (ollama_prompt.py)
        _finish_chat(h, [{"message": {"role": "assistant", **msg}, "done": True, "done_reason": "stop",
                          "eval_count": 5}])

    def scenario(h, body):  # records only; every check runs on the test's own thread
        msgs = [m for m in body.get("messages") or [] if isinstance(m, dict)]
        if body.get("format"):
            seen["repairs"] += 1
            done(h, {"content": json.dumps(CALL)})
        elif _is_child(body):
            done(h, {"content": CHILD_SAID})
        elif any(m.get("role") == "tool" for m in msgs):
            seen["followup"] = [m for m in msgs if m.get("role") == "tool"]
            done(h, {"content": "Main is done."})
        else:
            done(h, {"content": "", "tool_calls": [{"function": {"name": "Agent", "arguments": "{not valid json"}}]})

    mock = MockUpstream().start()
    mock.scenarios["auto-groups-repair"] = scenario
    try:
        with _Env() as e:
            os.environ["OLLAMA_HOST"] = mock.base_url  # this test's own loopback mock
            session = _session(e, model="ol:auto-groups-repair", base_url=mock.base_url, api_key="")
            session._repair_error = None
            got = session._attempt_tool_repair_once(tool_name="Agent", schema=AgentTool().input_schema,
                                                    error_message="arguments were not valid JSON", raw_input="{")
            ctx.check(f"the repair round hands back the reply without task, got {got!r} "
                      f"(error {session._repair_error!r})", got == CALL)
            ctx.check(f"no repair error, got {session._repair_error!r}", not session._repair_error)
            seen["repairs"] = 0
            resolved = _record_resolves(session)
            try:
                events = list(session.turn("read report A with a sub-agent"))
            finally:
                _unwrap(session)
            ctx.check(f"the turn's malformed call went through one repair round, got {seen['repairs']}",
                      seen["repairs"] == 1)
            _check_the_turn(ctx, "repaired", session, events, resolved, seen, "Agent")
    finally:
        mock.stop()


def _strip_task(body: dict) -> dict:
    for t in body.get("tools") or []:
        f = t.get("function") or t
        if f.get("name") in ("Agent", "Task"):
            params = f.get("parameters") or f.get("input_schema") or {}
            (params.get("properties") or {}).pop("task", None)
            params["required"] = [r for r in params.get("required") or [] if r != "task"]
    return body


@test
def test_r38_fixture_differs_only_by_task(ctx: Ctx):
    """R38's recorded plain-session requests (tests/fixtures/map_facts_plain_requests.json, asserted byte for byte by
    tests/test_map_facts.py) were re-recorded ONCE in 3.6.0.5, for the Agent and the Task tools' `task`. 3.6.0.4's
    recording is kept as tests/fixtures/map_facts_plain_requests_3604.json (never edited); this test proves `task` is
    the only difference: take the property `task` and "task" in `required` out of the Agent and Task tools of each new
    body, and the body is 3.6.0.4's letter for letter."""
    new = json.loads((FIXTURES / "map_facts_plain_requests.json").read_text(encoding="utf-8"))
    old_path = FIXTURES / "map_facts_plain_requests_3604.json"
    ctx.check("3.6.0.4's recording is kept", old_path.is_file())
    if not old_path.is_file():
        return
    old = json.loads(old_path.read_text(encoding="utf-8"))
    ctx.check(f"three request bodies in each, got {len(new)} and {len(old)}", len(new) == len(old) == 3)
    ctx.check("the recording happened: the new bodies are not 3.6.0.4's as they stand",
              all(n != o for n, o in zip(new, old)))
    for i, (n, o) in enumerate(zip(new, old)):
        stripped = json.dumps(_strip_task(json.loads(n)), ensure_ascii=False)
        ctx.check(f"request {i}: without task it is 3.6.0.4's letter for letter", stripped == o)
        ctx.check(f"request {i}: the Agent tool asks for task",
                  any((t.get("function") or {}).get("name") == "Agent"
                      and "task" in t["function"]["parameters"].get("required", []) for t in json.loads(n)["tools"]))


# ---- batch 2: every helper's row says its piece of work and its group (B2, B3, B6, B28, B29) ----------------------------

def _tree():
    """A real AgentTree under a fake main session (no agent_id: main) and a recorder of its agent_state frames."""
    from types import SimpleNamespace
    from halo_harness.agent.agent_registry import tree_for
    main = SimpleNamespace(log=None, opt_ins=None)
    tree = tree_for(main)
    frames: list = []
    tree.add_listener(lambda kind, aid, data: frames.append((kind, aid, data)) if kind == "agent_state" else None)
    return main, tree, frames


def _kid(main, aid: str, *, task: str = "", workflow=None, reply: int = 0, parent=None):
    """`register_child` as agent/subagent.py calls it, on reply `reply` of main; returns the child's fake session."""
    from types import SimpleNamespace
    from halo_harness.agent import agent_hooks
    from halo_harness.agent.agent_registry import tree_for
    tree = tree_for(main)
    with tree.lock:
        tree.rows["main"]["turns"] = reply
    child = SimpleNamespace(agent_id=aid, log=None, opt_ins=None)
    agent_hooks.register_child(parent or main, child, agent_id=aid, spec=SimpleNamespace(name="general-purpose"),
                               model=None, role=None, task_text=f"{aid}\ndo it", group_task=task,
                               group_workflow=workflow)
    return child


def _group(tree, aid: str) -> dict:
    return ((tree.row(aid) or {}).get("spawn") or {}).get("group") or {}


@test
def test_one_reply_is_one_group(ctx: Ctx):
    main, tree, _f = _tree()
    for aid in ("a1", "a2", "a3"):
        _kid(main, aid, reply=2)
    got = [_group(tree, a) for a in ("a1", "a2", "a3")]
    ctx.check(f"three children of one reply, no task: one group keyed by the reply, n 1, got {got}",
              all(g == {"key": "reply:main#2", "n": 1, "by": "reply"} for g in got))


@test
def test_same_task_words_join_across_replies(ctx: Ctx):
    main, tree, _f = _tree()
    _kid(main, "a1", task="fix the login bug", reply=1)
    _kid(main, "b1", reply=2)
    _kid(main, "a2", task="fix the login bug", reply=3)
    ga, gb, ga2 = _group(tree, "a1"), _group(tree, "b1"), _group(tree, "a2")
    ctx.check(f"the same words in reply 1 and reply 3 are one group, n kept, got {ga} {ga2}",
              ga == ga2 == {"key": "task:fix the login bug", "n": 1, "by": "task"})
    ctx.check(f"the reply between is a group of its own, got {gb}", gb.get("n") == 2 and gb.get("by") == "reply")


@test
def test_task_words_meet_case_blind_spaces_end_punct(ctx: Ctx):
    from halo_harness.crew import groups
    main, tree, _f = _tree()
    _kid(main, "a1", task="Fix the  login bug.", reply=1)
    _kid(main, "a2", task=" fix the login bug", reply=2)
    ctx.check(f"both meet on the key task:fix the login bug, got {_group(tree, 'a1')} {_group(tree, 'a2')}",
              _group(tree, "a1") == _group(tree, "a2") and _group(tree, "a1").get("key") == "task:fix the login bug")
    ctx.check("norm: lower case, runs of whitespace one space, spaces and . , ; : ! ? dropped at both ends",
              groups.norm("  Fix\tthe \n login BUG!?.;, ") == "fix the login bug" and groups.norm(" .,;:!? ") == "")
    ctx.check("a key longer than 120 characters is cut to 120",
              len(groups.key_of("main#1", "w " * 100)[0]) == 120)


@test
def test_fanout_children_share_one_group(ctx: Ctx):
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, ScriptedTurns
    scn = "auto-groups-fan-child"
    SCENARIOS[scn] = ScriptedTurns([_text("fan child done")])
    mock = MockUpstream().start()
    try:
        with _Env() as e:
            session = _session(e, model="or:mock/auto-groups-fan-parent", base_url=mock.base_url)
            tu = {"type": "tool_use", "id": "call_fan", "name": "Agent",
                  "input": {"description": "fan", "prompt": "go", "subagent_type": "general-purpose", "count": 3,
                            "task": "Check the docs", "model": f"or:mock/{scn}"}}
            list(session._dispatch_tools(1, [tu]))
            rows = _children(session)
            spawns = [r.get("spawn") or {} for r in rows]
            ctx.check(f"three rows, got {len(rows)}", len(rows) == 3)
            ctx.check(f"one key for the three: task:check the docs, got {[s.get('group') for s in spawns]}",
                      len({json.dumps(s.get("group"), sort_keys=True) for s in spawns}) == 1
                      and spawns[0].get("group", {}).get("key") == "task:check the docs")
            ctx.check(f"spawn.task on each, got {[s.get('task') for s in spawns]}",
                      all(s.get("task") == "Check the docs" for s in spawns))
    finally:
        mock.stop()
        SCENARIOS.pop(scn, None)


@test
def test_child_of_child_joins_its_parents_group(ctx: Ctx):
    main, tree, _f = _tree()
    _kid(main, "x0", reply=1)
    parent = _kid(main, "p1", task="fix the login bug", reply=1)
    _kid(main, "g1", task="something else entirely", parent=parent)
    ctx.check(f"the grandchild's group is its parent's (key, n and by), got {_group(tree, 'g1')}",
              _group(tree, "g1") == _group(tree, "p1") == {"key": "task:fix the login bug", "n": 2, "by": "task"})
    ctx.check("its own task words are still its spawn.task",
              (tree.row("g1") or {}).get("spawn", {}).get("task") == "something else entirely")


@test
def test_workflow_step_started_by_a_helper_stays_in_the_helpers_group(ctx: Ctx):
    main, tree, _f = _tree()
    parent = _kid(main, "p1", task="fix the login bug", reply=1)
    _kid(main, "s1", task="a step", workflow=("review", "tu9"), parent=parent)
    ctx.check(f"a workflow step started by a helper is in the helper's group, got {_group(tree, 's1')}",
              _group(tree, "s1") == _group(tree, "p1") and _group(tree, "s1").get("by") == "task")
    ctx.check("no workflow group was numbered for it", "workflow:review#tu9" not in getattr(tree, "group_n", {}))


@test
def test_queued_child_keeps_its_group(ctx: Ctx):
    from halo_harness.agent import agent_hooks
    main, tree, _f = _tree()
    agent_hooks.register_queued(main, "q1", name="general-purpose", task="go", description="fan", group_task="alpha")
    queued = _group(tree, "q1")
    _kid(main, "b1", task="beta", reply=1)
    _kid(main, "q1", task="gamma", reply=4)
    ctx.check(f"queued: task:alpha n 1, got {queued}", queued == {"key": "task:alpha", "n": 1, "by": "task"})
    ctx.check(f"built later, the queued group stands, n unchanged, got {_group(tree, 'q1')}", _group(tree, "q1") == queued)
    ctx.check("the queued row's own task field is still its first line",
              (tree.row("q1") or {}).get("task") == "go")


@test
def test_n_in_start_order_never_changes(ctx: Ctx):
    main, tree, _f = _tree()
    for aid, task in (("k1", "A"), ("k2", "B"), ("k3", "A"), ("k4", "C")):
        _kid(main, aid, task=task, reply=1)
    ns = [_group(tree, a).get("n") for a in ("k1", "k2", "k3", "k4")]
    ctx.check(f"keys A, B, A, C: n 1, 2, 1, 3, got {ns}", ns == [1, 2, 1, 3])
    before = _group(tree, "k2")
    tree.update("k2", state="running", current="Read x")
    tree.update("k2", state="done", turns=3)
    ctx.check(f"later updates never change a row's group, got {_group(tree, 'k2')}", _group(tree, "k2") == before)


@test
def test_parallel_first_members_share_one_n(ctx: Ctx):
    import threading
    main, tree, _f = _tree()
    gate = threading.Barrier(8)

    def go(i: int) -> None:
        from types import SimpleNamespace
        from halo_harness.agent import agent_hooks
        gate.wait(10)
        agent_hooks.register_child(main, SimpleNamespace(agent_id=f"t{i}", log=None, opt_ins=None), agent_id=f"t{i}",
                                   spec=SimpleNamespace(name="general-purpose"), model=None, role=None,
                                   group_task="one piece of work")

    threads = [threading.Thread(target=go, args=(i,), daemon=True) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    got = {json.dumps(_group(tree, f"t{i}"), sort_keys=True) for i in range(8)}
    ctx.check(f"8 first members at once: one group, n 1, got {got}",
              got == {json.dumps({"by": "task", "key": "task:one piece of work", "n": 1}, sort_keys=True)})
    ctx.check(f"the table holds one key, got {getattr(tree, 'group_n', None)}", getattr(tree, "group_n", {}) == {"task:one piece of work": 1})


@test
def test_group_frames_leave_in_n_order(ctx: Ctx):
    import threading
    from types import SimpleNamespace
    from halo_harness.agent import agent_hooks
    bad, stuck, unlocked, blind = [], [], [], []
    for rnd in range(200):
        main, tree, frames = _tree()
        gate = threading.Barrier(2)
        # the rule this pins (decisions round 3, J2 M5): `tree.add` stays inside groups.py's `with tree.lock:`, so a
        # group's first frame leaves while the publishing thread holds the tree's lock (an RLock: `_is_owned`)
        owned = getattr(tree.lock, "_is_owned", None)
        if owned is None:
            ctx.check(f"the tree's lock can say who holds it (an RLock), got {type(tree.lock)!r}", False)
            return
        seen: set = set()

        def held(kind, aid, data, rnd=rnd, seen=seen, owned=owned) -> None:
            key = ((data or {}).get("spawn") or {}).get("group", {}) if kind == "agent_state" else None
            key = (key or {}).get("key") if isinstance(key, dict) else None
            if key and key not in seen:
                seen.add(key)
                if not owned():
                    unlocked.append((rnd, aid))

        tree.add_listener(held)

        def go(key: str) -> None:
            gate.wait(10)
            agent_hooks.register_child(main, SimpleNamespace(agent_id=key, log=None, opt_ins=None), agent_id=key,
                                       spec=SimpleNamespace(name="general-purpose"), model=None, role=None,
                                       group_task=key)

        threads = [threading.Thread(target=go, args=(k,), daemon=True) for k in ("key A", "key B")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        if any(t.is_alive() for t in threads):
            stuck.append(rnd)
            break
        if len(seen) != 2:  # b/batch07: the listener checked both groups' first frames, or this round proves nothing
            blind.append((rnd, sorted(seen)))
        ns = [((d.get("spawn") or {}).get("group") or {}).get("n") for _k, _a, d in frames]
        ns = [n for n in ns if n is not None]
        if not (1 in ns and 2 in ns and ns.index(1) < ns.index(2)):
            bad.append((rnd, ns))
    ctx.check(f"all threads joined within 10 s in every round (no deadlock), stuck in rounds {stuck}", not stuck)
    ctx.check(f"in every round the lock listener saw exactly the two groups' keys, not so in {blind[:5]}", not blind)
    ctx.check(f"in every round of 200 the first frame with n=1 left before the first with n=2, bad {bad[:5]}", not bad)
    ctx.check(f"every group's first frame left while its thread held the tree's lock, not so in {unlocked[:5]}",
              not unlocked)


@test
def test_engine_writes_group_without_a_name(ctx: Ctx):
    from halo_harness.crew import groups
    main, tree, _f = _tree()
    long = "update the parser so that every nested block keeps its own indent level oks"
    _kid(main, "a1", task=long, reply=1)
    spawn = (tree.row("a1") or {}).get("spawn") or {}
    ctx.check(f"spawn.group has exactly key, n, by, got {sorted(spawn.get('group') or {})}",
              sorted(spawn.get("group") or {}) == ["by", "key", "n"])
    kept = spawn.get("task") or ""
    ctx.check(f"a {len(long)}-character task is kept to its first 60 characters cut at a word, got {kept!r}",
              len(long) == 75 and 0 < len(kept) <= 60 and long.startswith(kept) and long[len(kept)] == " ")
    ctx.check("spawn.step, description and lead are still there", {"step", "description", "lead"} <= set(spawn))
    ctx.check("cut: as is when it fits; a hard cut at 60 with no space",
              groups.cut("short words") == "short words" and groups.cut("x" * 70) == "x" * 60)


@test
def test_two_runs_of_one_workflow_are_two_groups(ctx: Ctx):
    from types import SimpleNamespace
    from halo_harness.crew import flow_door, groups
    from halo_harness.tools.workflow import WorkflowTool
    seen: list = []
    orig = flow_door.run
    flow_door.run = lambda runtime, name, task, **kw: (seen.append(runtime), ("ran", False))[1]
    try:
        rt = SimpleNamespace(parent=SimpleNamespace(), team_control=None)
        for tid in ("tu1", "tu2", "", ""):
            WorkflowTool().run({"task": "t", "name": "review"}, SimpleNamespace(
                agent_runtime=rt, tool_use_id=tid, cwd=Path("."), model_ref=None, permission_engine=None))
    finally:
        flow_door.run = orig
    got = [getattr(r, "group_workflow", None) for r in seen]
    ctx.check(f"the runtimes carry (review, tu1), (review, tu2), (review, run-1), (review, run-2), got {got}",
              got == [("review", "tu1"), ("review", "tu2"), ("review", "run-1"), ("review", "run-2")])
    ctx.check("two runs, two keys", groups.key_of("s", "", got[0])[0] == "workflow:review#tu1"
              and groups.key_of("s", "", got[1])[0] == "workflow:review#tu2")
    ctx.check("the original runtime carries no group_workflow and every handed one is a copy",
              not hasattr(rt, "group_workflow") and all(r is not rt for r in seen))


@test
def test_workflow_step_child_first_row_already_in_its_run_group(ctx: Ctx):
    main, tree, frames = _tree()
    _kid(main, "w1", task="read the step", workflow=("review", "tu1"), reply=1)
    first = next((d for _k, aid, d in frames if aid == "w1"), {})
    ctx.check(f"the step child's FIRST agent_state frame is already in the run's group, got {first.get('spawn')}",
              (first.get("spawn") or {}).get("group") == {"key": "workflow:review#tu1", "n": 1, "by": "workflow"})


@test
def test_square_session_run_gets_the_run_group(ctx: Ctx):
    from types import SimpleNamespace
    from halo_harness.tools.workflow import WorkflowTool
    from halo_harness.workflows import receipts, registry, router, square_run
    seen: list = []
    wf = SimpleNamespace(ref="sq-review", contract=SimpleNamespace(run_engine=lambda: "session", does="x"))
    fake = {(router, "route"): lambda *a, **k: SimpleNamespace(refused=False, role=None, square=wf, gaps=[], cap_usd=None,
                                                             hops=None),
            (registry, "enabled_squares"): lambda *a, **k: [],
            (square_run, "lead_model"): lambda *a, **k: ("m", None),
            (square_run, "run_session"): lambda wf, task, files, runtime=None, **k: (
                seen.append(runtime), SimpleNamespace(status="done", text="ok", cost_usd=0.0))[1],
            (receipts, "make"): lambda *a, **k: {}, (receipts, "write"): lambda *a, **k: None,
            (receipts, "line"): lambda rec: "line"}
    saved = {k: getattr(*k) for k in fake}
    for (mod, name), fn in fake.items():
        setattr(mod, name, fn)
    try:
        rt = SimpleNamespace(parent=SimpleNamespace(), team_control=None)
        for tid in ("tu7", ""):
            WorkflowTool().run({"task": "t"}, SimpleNamespace(agent_runtime=rt, tool_use_id=tid, cwd=Path("."),
                                                              model_ref="m", permission_engine=None))
    finally:
        for (mod, name), fn in saved.items():
            setattr(mod, name, fn)
    got = [getattr(r, "group_workflow", None) for r in seen]
    ctx.check(f"the square session engine's runtime carries (wf.ref, run id), got {got}",
              got == [("sq-review", "tu7"), ("sq-review", "run-1")])
    ctx.check("the original runtime is unchanged", not hasattr(rt, "group_workflow"))


@test
def test_agent_copy_refusal_says_ships_with_halo(ctx: Ctx):
    from halo_harness.crew.tools import agent_change
    with _Env() as e:
        got = agent_change({"name": "coder", "fields": {"does": "x"}}, {"cwd": e.cwd, "state_dir": e.state_dir})
    ctx.check(f"the refusal reads word for word, got {got.get('text')!r}",
              got.get("text") == "coder: ships with Halo: agent_copy it first, then change the copy"
              and "starter" not in got.get("text", "") and got.get("rows") == [])


@test
def test_g5_lists_the_start_agents_m1_lists_the_new_ones(ctx: Ctx):
    """Round 3 J1 M3 (b/batch05 entry 4): main's hover on Auto (G5) lists the agents this session had at its START (the
    status row's `map_agents`); the Map tab's line (M1, `hand_to` of GET crew/map/auto) lists the agents a NEW session on
    Auto gets now. One sentence each, one test: an agent saved mid-session is in M1, never in G5."""
    from types import SimpleNamespace
    from tests.helpers import node_ts
    from tests.helpers.crew_rig import CrewRig
    ui = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "crew" / "map"
    with CrewRig() as rig:
        rig.studio()
        from halo_harness.config.agents_md import discover_agents
        from halo_harness.crew import map_facts, store
        from halo_harness.crew.map_control import control_for
        from halo_harness.crew.map_session import agents, prepare
        c = prepare(None, rig.proj)[0]
        session = SimpleNamespace(team_control=control_for(c, cwd=rig.proj) if c is not None else None,
                                  agent_runtime=SimpleNamespace(agents=agents(discover_agents(rig.proj), c)[0]))
        store.write_text(store.path_for("agent", "checker", state_dir=rig.state), store.dump(
            {"format": "agent/1", "name": "checker", "does": "Checks.", "model": "auto", "uses": ["read"], "careful": "ask-changes"}))
        st, m = rig.api("GET", "crew/map/auto")
        hand_to = m.get("hand_to") or []
        start = map_facts.row(session).get("map_agents") or []
    ctx.check(f"M1's hand_to holds checker (a new session gets it), got {st} {hand_to}", st == 200 and "checker" in hand_to)
    ctx.check(f"the row's map_agents is the session's start, without checker, got {start}", start and "checker" not in start)
    js = """const g = await import(%s), a = await import(%s);
console.log(JSON.stringify({g5: g.g5Lines("m", %s), m1: a.m1Head(%s)}));""" % (
        json.dumps((ui / "groupWords.ts").resolve().as_uri()), json.dumps((ui / "autoWords.ts").resolve().as_uri()),
        json.dumps(start), json.dumps(hand_to))
    got = node_ts.run(js)
    g5 = got.get("g5") or []
    ctx.check(f"G5 lists the start agents, never checker, got {g5}",
              g5[:1] == ["main · m"] and len(g5) == 2 and g5[1].startswith("Can hand work to: ") and "checker" not in g5[1])
    m1, at = str(got.get("m1")), hand_to.index("checker") if "checker" in hand_to else -1
    # M1 names twelve, then "and {n} more" (autoWords.ts SHOWN): checker is named, or counted in that tail
    ctx.check(f"M1 holds checker (named, or counted in its 'and {{n}} more'), got {m1!r}",
              at >= 0 and ("checker" in m1 if at < 12 else m1.endswith(f" and {len(hand_to) - 12} more.")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
