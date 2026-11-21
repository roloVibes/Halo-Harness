"""tests.test_turn_counts -- 3.6.0.10 MW rule M10: main's box can say, per turn, what it handed out. ONE meaning of
"itself" (agent/handout_kind.py `kind`): an Agent or Task call or a Workflow run is a hand-out, the task board's tools
(TaskCreate, TaskUpdate, TaskList, TodoWrite) are neither, every other tool call is main's own. Main's row in the live
tree (agent/agent_registry.py) carries `turn {n, helpers, tools, ended}` and `turn_total {helpers, tools}`: n counts
main's turns, helpers the helpers main started that turn (each counted once, at its first start), tools main's own
calls. Nothing draws them yet and nothing of them is sent to a model.

A real top Session on Auto talks to a scripted loopback provider: one reply with 2 Agent calls (one `count: 3`), an
Agent call naming an unknown type, a Workflow run that starts none, 4 Reads and 1 TaskCreate, then "done". A scratch
home (tests/helpers/packs_home.py restores every variable), the mock ended in a `finally`; no real model, no network.
Run: python -m tests.test_turn_counts
"""
from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MAIN = "turn-counts-main"
CHILD = "turn-counts-child"
_RUN: dict = {}  # the running test's project folder (the Reads' absolute paths); emptied when the test ends


def _calls() -> list:
    child = f"or:mock/{CHILD}"
    agent = {"description": "check it", "prompt": "say done", "task": "check the notes", "model": child}
    calls = [("Agent", dict(agent, subagent_type="coder")),
             ("Agent", dict(agent, count=3)),
             ("Agent", dict(agent, subagent_type="no-such-helper")),
             ("Workflow", {"task": "review the notes", "name": "no-such-workflow"})]
    calls += [("Read", {"file_path": str(_RUN["repo"] / f"note{i}.txt")}) for i in range(4)]
    calls += [("TaskCreate", {"title": "tidy the notes"})]
    return calls


def _text(hd, words: str):
    from tests.helpers.mock_openai import _finish
    _finish(hd, [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
                 {"choices": [{"index": 0, "delta": {"content": words}}]},
                 {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}])


def _main(hd, body):
    """Turn 1's first request: the nine calls; after their results, or on any later turn: a short reply."""
    from tests.helpers.mock_openai import _finish
    msgs = body.get("messages") or []
    users = [m for m in msgs if m.get("role") == "user"]
    if any(m.get("role") == "tool" for m in msgs) or len(users) > 1:
        return _text(hd, "done")
    chunks = [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]}]
    for i, (name, args) in enumerate(_calls()):
        chunks.append({"choices": [{"index": 0, "delta": {"tool_calls": [{"index": i, "id": f"call_{i}", "type": "function",
                                                                          "function": {"name": name,
                                                                                       "arguments": json.dumps(args)}}]}}]})
    chunks.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]})
    _finish(hd, chunks)


@contextmanager
def _home():
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream
    saved = os.environ.get("OLLAMA_HOST")
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"
    mock = None
    try:
        with PacksHome() as h:
            os.environ["OPENROUTER_API_KEY"] = "sk-or-test-default"
            os.environ["HALO_NO_UPDATER"] = "1"
            SCENARIOS[MAIN] = _main
            SCENARIOS[CHILD] = lambda hd, _b: _text(hd, "child done")
            mock = MockUpstream().start()
            h.mock = mock
            h.repo.mkdir(parents=True, exist_ok=True)
            _RUN["repo"] = h.repo
            yield h
    finally:
        _RUN.clear()
        if mock is not None:
            mock.stop()
        SCENARIOS.pop(MAIN, None)
        SCENARIOS.pop(CHILD, None)
        if saved is None:
            os.environ.pop("OLLAMA_HOST", None)
        else:
            os.environ["OLLAMA_HOST"] = saved


def _session(h):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.crew import map_session
    from halo_harness.crew.session_start import start_agents
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.registry import ToolRegistry, default_tools
    compiled = map_session.prepare(None, h.repo)[0]
    ref = f"or:mock/{MAIN}"
    ctx = SessionContext(cwd=h.repo, model_label=ref, tool_registry=ToolRegistry(default_tools()))
    s = Session(cwd=h.repo, model_ref=parse_model_ref(ref), model_profile=ModelProfile(),
                creds=ProviderCreds(base_url=h.mock.base_url, api_key="k"), state_dir=h.state, model_label=ref,
                session_context=ctx, openrouter_base_url=h.mock.base_url, max_turns=6,
                permission_engine=PermissionEngine(mode="bypassPermissions", cwd=h.repo),
                agents=start_agents(h.repo, compiled), crew_map=compiled)
    s.interactive = True
    return s


@test
def test_one_meaning_of_itself(ctx: Ctx):
    from halo_harness.agent.handout_kind import kind
    got = {n: kind(n) for n in ("Agent", "Task", "Workflow", "TaskCreate", "TaskUpdate", "TaskList", "TodoWrite", "Read",
                                "Bash", "TaskStop", "Builder", "mcp__x__y", "", None)}
    ctx.check(f"Agent, Task, Workflow hand out; the board is neither; every other call is main's own, got {got}",
              got == {"Agent": "handout", "Task": "handout", "Workflow": "handout", "TaskCreate": "board",
                      "TaskUpdate": "board", "TaskList": "board", "TodoWrite": "board", "Read": "own", "Bash": "own",
                      "TaskStop": "own", "Builder": "own", "mcp__x__y": "own", "": "own", None: "own"})


@test
def test_a_turn_counts_its_helpers_and_main_s_own_calls(ctx: Ctx):
    from halo_harness.agent.agent_registry import FIELDS, tree_for
    with _home() as h:
        for i in range(4):
            (h.repo / f"note{i}.txt").write_text(f"note {i}\n", encoding="utf-8")
        s = _session(h)
        try:
            tree = tree_for(s)
            ctx.check(f"blank before the first turn, got {tree.row('main').get('turn')!r}",
                      "turn" in FIELDS and "turn_total" in FIELDS and tree.row("main").get("turn") is None
                      and tree.row("main").get("turn_total") is None)
            events = list(s.turn("Tidy the notes with helpers."))
            row = tree.row("main")
            results = {e.data.get("id"): e.data for e in events if e.kind == "tool_result" and not e.agent_id}
            failed = sorted(i for i, r in results.items() if r.get("ok") is not True)
            children = [r for r in tree.public_rows() if r.get("parent") == "main" and r.get("kind") != "job"]
            ctx.check(f"the run: nine calls answered, only the unknown type refused, the workflow started none, four "
                      f"helpers ran, got {len(results)} results, failed {failed}, {len(children)} children",
                      len(results) == 9 and failed == ["call_2"] and "did not start" in str(results["call_3"].get("summary"))
                      and len(children) == 4)
            ctx.check(f"turn 1: 4 helpers, 4 tools of its own, ended, got {row.get('turn')}",
                      row.get("turn") == {"n": 1, "helpers": 4, "tools": 4, "ended": True})
            ctx.check(f"the session so far, got {row.get('turn_total')}", row.get("turn_total") == {"helpers": 4, "tools": 4})
            list(s.turn("Now say hi, a second time."))
            row = tree.row("main")
            ctx.check(f"turn 2 starts from zero, got {row.get('turn')}",
                      row.get("turn") == {"n": 2, "helpers": 0, "tools": 0, "ended": True})
            ctx.check(f"the session keeps its total, got {row.get('turn_total')}",
                      row.get("turn_total") == {"helpers": 4, "tools": 4})
            kids = [r for r in tree.public_rows() if r.get("parent") == "main" and r.get("kind") != "job"]
            ctx.check(f"a helper's row carries no turn counts, got {[k.get('turn') for k in kids]}",
                      kids and all(k.get("turn") is None and k.get("turn_total") is None for k in kids))
        finally:
            s.close_runtimes()


@test
def test_counts_come_only_from_main_s_turn(ctx: Ctx):
    """A child's own turn and own tool calls never count as main's: its turn_started is a helper's start (once), its
    tool calls are its own; a child that starts again (a resumed task) is not counted twice."""
    from types import SimpleNamespace
    from halo_harness.agent import agent_hooks
    from halo_harness.agent.agent_registry import tree_for
    main = SimpleNamespace(agent_id=None, model_ref=None, log=None)
    tree = tree_for(main)
    agent_hooks.turn_started(main, "go")
    child = SimpleNamespace(agent_id="a1", model_ref=None, log=None, _agent_tree=tree)
    tree.add("a1", session=child, parent="main", name="coder", kind="subagent", state="queued")
    grand = SimpleNamespace(agent_id="a2", model_ref=None, log=None, _agent_tree=tree)
    tree.add("a2", session=grand, parent="a1", name="coder", kind="subagent", state="queued")
    for who in (child, grand, child):
        agent_hooks.turn_started(who, "work")
    agent_hooks.tools_called(child, ["Read", "Bash"])
    agent_hooks.tools_called(main, ["Read", "Agent", "TodoWrite", "Bash"])
    agent_hooks.turn_ended(child)
    ctx.check(f"main's turn: one helper (its own child, once), two own calls, still running, got {tree.row('main')['turn']}",
              tree.row("main")["turn"] == {"n": 1, "helpers": 1, "tools": 2, "ended": False})
    agent_hooks.turn_ended(main)
    ctx.check(f"main's turn ends, got {tree.row('main')['turn']}", tree.row("main")["turn"]["ended"] is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
