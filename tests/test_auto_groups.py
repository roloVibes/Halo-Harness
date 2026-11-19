"""tests.test_auto_groups -- Halo 3.6.0.5 "Auto's own groups" (package b).

Batch 1 (B23, F1, decisions 4 and round 3 J2 M4, F10): main is asked to name the piece of work each helper belongs to
(`task`, 2 to 6 words) on the Agent and the Task tool alike (one schema, one check). `task` is in `required` as main sees
it; `agent/repair.py check_schema` is the ONE place that hands back, for Agent and Task only, a copy without it, so a call
that leaves `task` out still runs exactly as on 3.6.0.4: through the loop's resolver (`Session._resolve_tool_call`) and
through a local model's repair round (`_attempt_tool_repair_once`). The recorded plain-session requests (R38) were
recorded once more for `task`, and `test_r38_fixture_differs_only_by_task` proves that is the only difference from
3.6.0.4's (kept as tests/fixtures/map_facts_plain_requests_3604.json, never edited).

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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
