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


def _run_openrouter_turn(ctx: Ctx, name: str, call: "dict | None" = None, label: str = "") -> None:
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
    seen: dict = {}
    call = CALL if call is None else call

    def scenario(h, body):  # records only; every check runs on the test's own thread
        msgs = [m for m in body.get("messages") or [] if isinstance(m, dict)]
        if _is_child(body):
            _finish(h, _text(CHILD_SAID))
        elif any(m.get("role") == "tool" for m in msgs):
            seen["followup"] = [m for m in msgs if m.get("role") == "tool"]
            _finish(h, _text("Main is done."))
        else:
            _finish(h, _call(name, call))

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
            _check_the_turn(ctx, label or name, session, events, resolved, seen, name)
            if label:  # r/batch05 entry 4: a task that is not a non-empty text is no task: no task words on the row
                rows = _children(session)
                spawn = (rows[0].get("spawn") if rows else None) or {}
                ctx.check(f"{label}: the helper's row has no task words, got {spawn.get('task')!r}", not spawn.get("task"))
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


NOT_TEXT = (("null", None), ("an empty string", ""), ("a number", 5), ("a list", ["fix the login"]))


@test
def test_task_that_is_not_text_never_refuses_a_call(ctx: Ctx):
    """r/batch05 entry 4: an Agent or a Task call whose `task` is null, an empty string, a number or a list RUNS, as on
    3.6.0.4 (which ignored the key): the repair check passes it, one real turn runs the helper and groups it by its
    reply with no task words, and the loop's repair round hands the reply back with no error."""
    from halo_harness.agent.repair import repair_tool_use_block
    from halo_harness.tools.agent import AgentTool, TaskTool
    from halo_harness.tools.registry import ToolRegistry
    reg = ToolRegistry([AgentTool(), TaskTool()])
    for name in ("Agent", "Task"):
        for label, value in NOT_TEXT:
            got = repair_tool_use_block({"name": name, "input": {**CALL, "task": value}}, reg)
            ctx.check(f"{name}, task {label}: the check passes it, got {got.ok} {got.error_text!r}",
                      got.ok and got.error_kind is None)
            _run_openrouter_turn(ctx, name, {**CALL, "task": value}, f"{name}, task {label}")
    _repair_round_takes(ctx, [{**CALL, "task": v} for _l, v in NOT_TEXT])


def _repair_round_takes(ctx: Ctx, replies: list) -> None:
    """The loop's repair round on a local model (Ollama route): each reply in `replies` comes back from
    `_attempt_tool_repair_once` as it is, with no repair error."""
    from tests.helpers.mock_ollama import MockUpstream, _finish_chat
    from halo_harness.tools.agent import AgentTool
    todo = list(replies)

    def scenario(h, body):
        _finish_chat(h, [{"message": {"role": "assistant", "content": json.dumps(todo[0] if todo else {})}, "done": True,
                          "done_reason": "stop", "eval_count": 5}])

    mock = MockUpstream().start()
    mock.scenarios["auto-groups-task-values"] = scenario
    try:
        with _Env() as e:
            os.environ["OLLAMA_HOST"] = mock.base_url  # this test's own loopback mock
            session = _session(e, model="ol:auto-groups-task-values", base_url=mock.base_url, api_key="")
            while todo:
                want = todo[0]
                session._repair_error = None
                got = session._attempt_tool_repair_once(tool_name="Agent", schema=AgentTool().input_schema,
                                                        error_message="arguments were not valid JSON", raw_input="{")
                ctx.check(f"the repair round hands back task {want.get('task')!r}, got {got!r} "
                          f"(error {session._repair_error!r})", got == want and not session._repair_error)
                todo.pop(0)
    finally:
        mock.stop()


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


def _strip_browser(body: dict) -> dict:
    """3.6.0.8: the built-in Browser tool out of a recorded body: its definition among the tools, and its one line in
    the system text ("- **Browser**: ...")."""
    body["tools"] = [t for t in body.get("tools") or [] if (t.get("function") or t).get("name") != "Browser"]
    for m in body.get("messages") or []:
        if m.get("role") == "system" and isinstance(m.get("content"), str):
            m["content"] = "\n".join(line for line in m["content"].split("\n") if not line.startswith("- **Browser**: "))
    return body


M8_KINDS = " Helpers you can start (`subagent_type`): "  # agent/helpers_words.py KINDS_HEAD
M8_ROLES = ("With custom roles ON (the default) the model table (`roles.*`) picks a sub-agent's model (`role:`); with "
            "roles OFF it runs the session model unless the call passes `model:`.")
ROLES_3609 = ("With custom roles OFF (the default) every sub-agent runs the session model unless the call passes "
              "`model:`; with roles ON the model table (`roles.*`) picks it (`role:`).")


def _strip_m8(body: dict) -> dict:
    """3.6.0.10 M8: the kinds tail out of the Agent and Task tools' words (from its head to the end), and the cloud
    text's roles sentence back to 3.6.0.9's."""
    for t in body.get("tools") or []:
        f = t.get("function") or t
        if f.get("name") in ("Agent", "Task") and M8_KINDS in f.get("description", ""):
            f["description"] = f["description"][:f["description"].index(M8_KINDS)]
    for m in body.get("messages") or []:
        if m.get("role") == "system" and isinstance(m.get("content"), str):
            m["content"] = m["content"].replace(M8_ROLES, ROLES_3609)
    return body


@test
def test_m8_fixture_differs_from_3609_only_by_the_kinds_and_the_roles_sentence(ctx: Ctx):
    """3.6.0.10 M8: R38's recording was made once more, for the Agent and Task tools' kinds (a top Auto session) and the
    cloud text's true roles sentence. 3.6.0.9's recording is kept as tests/fixtures/map_facts_plain_requests_3609.json
    (never edited): take the kinds tail out of the Agent and Task tools of each new body and put the old roles sentence
    back, and the body is 3.6.0.9's letter for letter."""
    new = json.loads((FIXTURES / "map_facts_plain_requests.json").read_text(encoding="utf-8"))
    old_path = FIXTURES / "map_facts_plain_requests_3609.json"
    ctx.check("3.6.0.9's recording is kept", old_path.is_file())
    if not old_path.is_file():
        return
    old = json.loads(old_path.read_text(encoding="utf-8"))
    ctx.check(f"three request bodies in each, got {len(new)} and {len(old)}", len(new) == len(old) == 3)
    ctx.check("the recording happened: the new bodies are not 3.6.0.9's as they stand", all(n != o for n, o in zip(new, old)))
    for i, (n, o) in enumerate(zip(new, old)):
        body = json.loads(n)
        words = {(t.get("function") or t)["name"]: (t.get("function") or t).get("description", "") for t in body["tools"]}
        ctx.check(f"request {i}: the Agent and Task tools end with the kinds, planner first, once each",
                  all(words.get(k, "").count(M8_KINDS) == 1 and words[k].split(M8_KINDS)[1].startswith("planner (")
                      and words[k].endswith(". With no `subagent_type` Halo picks a kind from your words.")
                      for k in ("Agent", "Task")))
        system = "".join(str(m.get("content")) for m in body["messages"] if m.get("role") == "system")
        ctx.check(f"request {i}: the roles sentence is the true one", M8_ROLES in system and ROLES_3609 not in system)
        ctx.check(f"request {i}: without them it is 3.6.0.9's letter for letter",
                  json.dumps(_strip_m8(body), ensure_ascii=False) == o)


@test
def test_r38_fixture_differs_only_by_task(ctx: Ctx):
    """R38's recorded plain-session requests (tests/fixtures/map_facts_plain_requests.json, asserted byte for byte by
    tests/test_map_facts.py) were re-recorded in 3.6.0.5, for the Agent and the Task tools' `task`, in 3.6.0.8, for
    the built-in Browser tool (one more tool, one more line of the system text), and in 3.6.0.10 for M8 (proved by
    the test above). 3.6.0.4's recording is kept as tests/fixtures/map_facts_plain_requests_3604.json (never edited);
    this test proves those are the only differences: take M8's kinds and roles sentence out, the property `task` and
    "task" in `required` out of the Agent and Task tools of each new body, take the Browser tool and its line out, and
    the body is 3.6.0.4's letter for letter; 3.6.0.9's kept recording, with `task` and the Browser out, is too."""
    new = json.loads((FIXTURES / "map_facts_plain_requests.json").read_text(encoding="utf-8"))
    kept = json.loads((FIXTURES / "map_facts_plain_requests_3609.json").read_text(encoding="utf-8"))
    old_path = FIXTURES / "map_facts_plain_requests_3604.json"
    ctx.check("3.6.0.4's recording is kept", old_path.is_file())
    if not old_path.is_file():
        return
    old = json.loads(old_path.read_text(encoding="utf-8"))
    ctx.check(f"three request bodies in each, got {len(new)} and {len(old)}", len(new) == len(old) == 3)
    ctx.check("the recording happened: the new bodies are not 3.6.0.4's as they stand",
              all(n != o for n, o in zip(new, old)))
    for i, (n, o) in enumerate(zip(new, old)):
        body = json.loads(n)
        ctx.check(f"request {i}: the Browser tool is among the tools, with its one line in the system text",
                  sum((t.get("function") or t).get("name") == "Browser" for t in body["tools"]) == 1
                  and sum(line.startswith("- **Browser**: ") for m in body["messages"] if m.get("role") == "system"
                          for line in str(m.get("content")).split("\n")) == 1)
        stripped = json.dumps(_strip_browser(_strip_task(_strip_m8(body))), ensure_ascii=False)
        ctx.check(f"request {i}: without M8, task and the Browser tool it is 3.6.0.4's letter for letter", stripped == o)
        ctx.check(f"request {i}: 3.6.0.9's kept recording without task and the Browser tool is 3.6.0.4's",
                  json.dumps(_strip_browser(_strip_task(json.loads(kept[i]))), ensure_ascii=False) == o)
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


# 3.6.0.14 K3: every line the two docs quote of the drawing on Auto and of the box opened in place, in the docs' own form
# (placeholders in braces), with the made-up values that turn it into the product's output for the inputs below. A row:
# (the doc, the fragments the doc quotes, the values, the key of the product's line the fragments joined must equal).
_GROUPS, _LIVE = "docs/STUDIO-groups.md", "docs/STUDIO-live.md"
_NAMES = [f"kind{i}" for i in range(1, 15)]
_DOC_LINES = [
    (_GROUPS, ["waiting for you · {s}"], {"s": "12 s"}, "now_wait"),
    (_GROUPS, ["paused"], {}, "now_paused"),
    (_GROUPS, ["queued · {s}"], {"s": "12 s"}, "now_queued"),
    (_GROUPS, ["stopped after {span}"], {"span": "42 s"}, "now_stopped"),
    (_GROUPS, ["done in {span}"], {"span": "42 s"}, "now_done"),
    (_GROUPS, ["failed after {span}"], {"span": "42 s"}, "now_failed"),
    (_GROUPS, ["{tool} · {s}"], {"tool": "Grep", "s": "12 s"}, "now_tool"),
    (_GROUPS, ["thinking · {s}"], {"s": "12 s"}, "now_think"),
    (_GROUPS, ["writing · {s}"], {"s": "12 s"}, "now_write"),
    (_GROUPS, ["waiting for a model reply · {s}"], {"s": "12 s"}, "now_model"),
    (_GROUPS, ["a tool · {s}"], {"s": "12 s"}, "now_held"),
    (_LIVE, ["a tool · {s}"], {"s": "12 s"}, "now_held"),
    (_GROUPS, ["{who}: {description}"], {"who": "reader", "description": "read the pdf"}, "member_line"),
    (_GROUPS, ["{model} · {state}"], {"model": "kimi-x", "state": "queued"}, "member_state"),
    (_GROUPS, ["Now: {whole words}"], {"whole words": "Grep · 12 s"}, "hover_now"),
    (_GROUPS, ["Now: queued · {s}: it starts when a running helper ends."], {"s": "12 s"}, "hover_queued"),
    (_GROUPS, ["This turn: started {h} helpers · used {t} tools itself"], {"h": "3", "t": "5"}, "turn_both"),
    (_GROUPS, ["This turn: started {h} helpers"], {"h": "3"}, "turn_helpers"),
    (_GROUPS, ["This turn: used {t} tools itself"], {"t": "5"}, "turn_tools"),
    (_GROUPS, ["This turn: started ", "1 helper", " · used ", "1 tool", " itself"], {}, "turn_ones"),
    (_GROUPS, ["main · {model}"], {"model": "qwen-x"}, "main_head"),
    (_GROUPS, ["This session: started {H} helpers · used {T} tools itself"], {"H": "4", "T": "9"}, "main_session"),
    (_GROUPS, ["Told it can start: {names}", " and {n} more"], {"names": ", ".join(_NAMES[:12]), "n": "2"}, "main_told"),
    (_GROUPS, ["Can hand work to: {names}"], {"names": ", ".join(_NAMES[:3])}, "main_before"),
    (_GROUPS, ["{n} agents · {w} working · {q} queued · {v} waiting on you · {d} done · {k} stopped · {f} failed · ${cost}"],
     {"n": "7", "w": "2", "q": "1", "v": "1", "d": "1", "k": "1", "f": "1", "cost": "0.07"}, "head_all"),
    (_GROUPS, ["{n} agents · all done · ${cost} · {time}"], {"n": "2", "cost": "0.03", "time": "42 s"}, "head_done"),
    (_GROUPS, ["1 agent · 1 stopped"], {}, "head_stopped"),
    (_GROUPS, ["2 agents · 1 done · 1 stopped"], {}, "head_done_stopped"),
    (_GROUPS, ["↓ {name} · waits on you"], {"name": "review"}, "slot_down"),
    (_GROUPS, ["↑ {name} · waits on you"], {"name": "review"}, "slot_up"),
    (_GROUPS, ["{name} · waits on you · under the open box"], {"name": "review"}, "slot_under"),
    (_GROUPS, ["↓ {name} · working"], {"name": "review"}, "slot_working"),
    (_GROUPS, ["↓ {name} · working", " · and {n} more groups below"], {"name": "review", "n": "3"}, "slot_more3"),
    (_GROUPS, ["↓ {name} · working", " · and 1 more group below"], {"name": "review"}, "slot_more1"),
    (_LIVE, ["Last said at {hh:mm:ss}: {text}"], {"text": "All four files read."}, "said_at"),
    (_LIVE, ["Last thought at {hh:mm:ss}: {text}"], {"text": "Which file first?"}, "thought_at"),
    (_LIVE, ["Last said: {text}"], {"text": "All four files read."}, "said"),
    (_LIVE, ["Last thought: {text}"], {"text": "Which file first?"}, "thought"),
    (_LIVE, ["Nothing said yet."], {}, "said_none"),
    (_LIVE, ["Reading what it said..."], {}, "said_reading"),
    (_LIVE, ["Could not read what it said: {error}"], {"error": "timed out"}, "said_error"),
    (_LIVE, ["The rest is in the session export: Export on Session's Feed, or halo session export {sid}."], {"sid": "s-k3"},
     "said_rest"),
    (_LIVE, ["Told it can start: {names}", " and {n} more"], {"names": "kind1, kind2", "n": "3"}, "sheet_told"),
    (_LIVE, ["Open in Agents -> Live"], {}, "open_agents"),
    (_GROUPS, ["Open in Agents -> Live"], {}, "open_agents"),
]
# The forms the docs held before 3.6.0.13 and OP1, gone.
_DOC_GONE = [(_GROUPS, "· {v} waiting ·"), (_GROUPS, "working and {n} more below"), (_GROUPS, "A box's card"),
             (_GROUPS, "the helper's card open"), (_LIVE, "its card open (the ask's choices")]


def _fill(line: str, values: dict) -> str:
    import re
    return re.sub(r"\{([^{}]+)\}", lambda m: values.get(m.group(1), m.group(0)), line)


@test
def test_the_docs_say_what_the_drawing_and_the_sheet_say(ctx: Ctx):
    """3.6.0.14 K3: docs/STUDIO-groups.md and docs/STUDIO-live.md quote the drawing on Auto (NOW, the member hover, TURN,
    main's hover, the head's counts, the slot) and the box opened in place (Last said) letter for letter: each quoted
    line is in its doc, and with its placeholders filled it is the product's output (nowLine.ts, nowRoom.ts,
    groupWords.ts, turnWords.ts, truthBits.ts in node) for the same made-up inputs. Reads only; changes nothing."""
    import re
    from tests.helpers import node_ts
    from halo_harness.agent import agent_transcript
    repo = Path(__file__).resolve().parent.parent
    ui = repo / "halo_harness" / "studio" / "ui" / "src" / "routes" / "crew" / "map"
    url = lambda f: json.dumps((ui / f).resolve().as_uri())  # noqa: E731
    js = """const N = await import(%s), R = await import(%s), G = await import(%s), T = await import(%s), B = await import(%s);
const now = 100000, at = 88000, names = %s, nw = (x) => N.nowWords(N.nowOf(x, now));
const m = (raw, state, o = {}) => ({ aid: raw, who: "reader", description: "read the pdf", model: "kimi-x", reason: "",
  state, raw, cost: 0.01, started: 100, ended: 0, ...o });
const counts = (ms) => G.countsLine({ members: ms });
const held = R.nowFit({ text: "mcp__a_rather_long_server_name__slow_tool_with_a_long_name · ", secs: "12 s" }, 160, { rows: 2, grown: false }, true);
const ts = 1700000000, said = (ev) => B.saidLines({ events: ev }, "s-k3");
console.log(JSON.stringify({
  now_wait: nw({ raw: "waiting", started: 1, ended: 0, wait: { kind: "you", since: at } }),
  now_paused: nw({ raw: "paused", started: 1, ended: 0 }),
  now_queued: nw({ raw: "queued", started: 88, ended: 0 }),
  now_stopped: nw({ raw: "stopped", started: 100, ended: 142 }),
  now_done: nw({ raw: "done", started: 100, ended: 142 }),
  now_failed: nw({ raw: "failed", started: 100, ended: 142 }),
  now_tool: nw({ raw: "running", started: 1, ended: 0, tool: { tool: "Grep", t0: at } }),
  now_think: nw({ raw: "running", started: 1, ended: 0, last: { kind: "thinking", t0: at } }),
  now_write: nw({ raw: "running", started: 1, ended: 0, last: { kind: "text", t0: at }, wait: { kind: "nothing", since: at } }),
  now_model: nw({ raw: "running", started: 1, ended: 0, wait: { kind: "model", since: at } }),
  now_held: held.text + held.secs,
  member_line: G.memberLine(m("queued", "idle")), member_state: G.memberState(m("queued", "idle")),
  words: ["running", "waiting", "queued", "done", "stopped", "failed"].map((r) =>
    G.memberWord(m(r, { running: "working", waiting: "waiting", queued: "idle", done: "done", stopped: "idle", failed: "failed" }[r]))),
  hover_now: G.g4Lines(m("running", "working"), 130, "Grep · 12 s").slice(-1)[0],
  hover_queued: G.g4Lines(m("queued", "idle"), 130, "queued · 12 s").slice(-1)[0],
  turn_both: T.turnLine({ helpers: 3, tools: 5 }), turn_helpers: T.turnLine({ helpers: 3 }), turn_tools: T.turnLine({ tools: 5 }),
  turn_ones: T.turnLine({ helpers: 1, tools: 1 }), turn_blank: T.turnLine(null),
  main_hover: T.mainHover("qwen-x", [], { names, more: 0 }, { helpers: 4, tools: 9 }),
  main_before: T.mainHover("qwen-x", names.slice(0, 3), null, null),
  head_all: counts([m("running", "working", { cost: 0.01 }), m("paused", "working"), m("queued", "idle"), m("waiting", "waiting"),
    m("done", "done"), m("stopped", "idle"), m("failed", "failed")]),
  head_done: counts([m("done", "done", { ended: 130, cost: 0.02 }), m("done", "done", { ended: 142 })]),
  head_stopped: counts([m("stopped", "idle", { cost: 0 })]),
  head_done_stopped: counts([m("done", "done", { cost: 0, ended: 120 }), m("stopped", "idle", { cost: 0 })]),
  slot_down: G.slotWords("review", "down", 0), slot_up: G.slotWords("review", "up", 0),
  slot_under: G.slotWords("review", "under", 0), slot_working: G.slotWords("review", "working", 0),
  slot_more3: G.slotWords("review", "working", 3), slot_more1: G.slotWords("review", "working", 1),
  clock: B.secsClock(ts),
  said_at: said([{ kind: "text", text: "All four files read.", ts }])[0],
  thought_at: said([{ kind: "thinking", text: "Which file first?", ts }])[0],
  said: said([{ kind: "text", text: "All four files read." }])[0],
  thought: said([{ kind: "thinking", text: "Which file first?" }])[0],
  said_none: said([])[0], said_reading: B.saidLines("reading", "s-k3")[0],
  said_error: B.saidLines({ error: "timed out" }, "s-k3")[0],
  said_cut: said([{ kind: "text", text: "abc... (120 more characters)" }]),
  sheet_told: T.toldEvery({ names: ["kind1", "kind2"], more: 3 }),
  open_agents: B.openInAgents().label,
}));""" % (url("nowLine.ts"), url("nowRoom.ts"), url("groupWords.ts"), url("turnWords.ts"), url("truthBits.ts"),
           json.dumps(_NAMES))
    got = node_ts.run(js)
    hover = got.get("main_hover") or []
    got.update(main_head=hover[0] if hover else None, main_session=hover[1] if len(hover) > 1 else None,
               main_told=hover[2] if len(hover) > 2 else None)
    got["main_before"] = (got.get("main_before") or [None, None])[-1]
    got["said_rest"] = (got.get("said_cut") or [None, None])[-1]
    docs = {d: re.sub(r"\s+", " ", (repo / d).read_text(encoding="utf-8")) for d in (_GROUPS, _LIVE)}
    clock = got.get("clock") or ""
    for doc, parts, values, key in _DOC_LINES:
        values = {"hh:mm:ss": clock, **values}
        missing = [p for p in parts if p not in docs[doc]]
        whole = _fill("".join(parts), values)
        ctx.check(f"{doc} quotes {parts!r} and, filled, it is the product's {key}: missing {missing}, "
                  f"filled {whole!r}, product {got.get(key)!r}", not missing and whole == got.get(key))
    ctx.check(f"main's hover before the first request is main · {{model}} over Can hand work to, got {got.get('main_before')!r}",
              got.get("main_before") == "Can hand work to: kind1, kind2, kind3")
    ctx.check(f"TURN is blank before the first turn, got {got.get('turn_blank')!r}", got.get("turn_blank") == "")
    words = got.get("words") or []
    ctx.check(f"each helper's state word is quoted in {_GROUPS}, got {words}",
              words == ["working", "waiting on you", "queued", "done", "stopped", "failed"]
              and all(f'"{w}"' in docs[_GROUPS] for w in words))
    cut = agent_transcript._cap("x" * (agent_transcript.TEXT_CAP + 120))
    tail = _fill("... ({n} more characters)", {"n": "120"})
    ctx.check(f"{_LIVE} quotes the reader's cut '... ({{n}} more characters)' as the server writes it, got {cut[-30:]!r}",
              "... ({n} more characters)" in docs[_LIVE] and cut.endswith(tail))
    ctx.check("STUDIO-live.md links the docs' new anchor from STUDIO-groups.md",
              "STUDIO-live.md#the-box-opens-in-place" in docs[_GROUPS] and "## The box opens in place" in docs[_LIVE])
    for doc, gone in _DOC_GONE:
        ctx.check(f"{doc} no longer says {gone!r}", gone not in docs[doc])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
