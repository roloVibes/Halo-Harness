"""tests.test_map_run_tags -- Halo 3.6.0.2 "Session map" R13 and R48: the rows and frames a run on a map says.

1. (R13) every child's `crew` row says `{map, box, line?, agent, saved, workflow?, step?}`; `made_up` only for a
   `general-purpose` call or a name no spec knows: a Workflow-tool step's child (SessionBackend._child) is tagged with
   its workflow and step under its caller's box; a saved agent main names with no line on the default map is that saved
   agent, not a made-up helper;
2. (R48) the Workflow tool's door sends one hand-off from the REAL caller's box to `workflow:{W}` and keys its steps'
   frames to that workflow; a made-up child, or a saved agent with no line on the default map, hands off to
   `made-up:{aid}`; `off` is True only off the default map with no line followed;
3. (R48) a hand-off that raises, fails or is stopped still sends its `end` (error), on the calling thread; once the
   session is closed no frame reaches its feed or its log.
Fakes only, no model call, no thread, no clock. Run: python -m tests.test_map_run_tags
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.workflow_fakes import FakeChild, FakeRuntime, run_tool  # noqa: E402
from tests.test_map_chains import call, flow, runtime as map_runtime, spawning  # noqa: E402

test, TESTS = new_registry()
REVIEW = {"format": "workflow/1", "name": "review", "for": "Code a change, then review it.",
          "steps": [{"name": "Code", "agents": ["coder"]}, {"name": "Review", "agents": ["reviewer"]}]}


def default_rt(h):
    """A runtime on the default map (the starter, as crew/map_session.py builds it), with the saved workflow `review`."""
    from halo_harness.crew import store
    from halo_harness.crew.compile import compile_map
    from halo_harness.crew.map_control import control_for
    p = store.path_for("workflow", "review")
    p.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(p, store.dump(REVIEW))
    c = compile_map("starter", cwd=h.repo)
    c.source = "default"
    rt = FakeRuntime(h.repo)
    rt.team_control = control_for(c, cwd=h.repo, session=rt.parent)
    return rt


def row(rt, aid: str) -> dict:
    from halo_harness.agent.agent_registry import tree_for
    return tree_for(rt.parent).row(aid) or {}


def hops(rt) -> list:
    return [d for k, _a, d in rt.frames if k == "map_hop"]


def steps(rt) -> list:
    return [d for k, _a, d in rt.frames if k == "map_step"]


def raising(calls: list, rt, after_child: bool = True):
    """A spawn that makes its child (row + on_child) and then raises, as a dying provider would."""
    inner = spawning(calls, rt)

    def boom(*, runtime, tool_id, tool_input, tool_name, on_event=None, on_child=None):
        if after_child:
            inner(runtime=runtime, tool_id=tool_id, tool_input=tool_input, tool_name=tool_name, on_child=on_child)
        raise RuntimeError("the provider went away")
    return boom


def raising_for(calls: list, rt, who: str):
    """A spawn that runs every agent as `spawning` does, except `who`: its child is made and then the call raises."""
    inner, boom = spawning(calls, rt), raising(calls, rt)

    def pick(*, runtime, tool_id, tool_input, tool_name, on_event=None, on_child=None):
        f = boom if tool_input.get("subagent_type") == who else inner
        return f(runtime=runtime, tool_id=tool_id, tool_input=tool_input, tool_name=tool_name, on_child=on_child)
    return pick


def stopping(calls: list, rt):
    """A spawn whose child is stopped (Esc / Stop): the session's abort is set and the call returns an error."""
    from halo_harness.tools.base import ToolResult
    inner = spawning(calls, rt)

    def stop(*, runtime, tool_id, tool_input, tool_name, on_event=None, on_child=None):
        inner(runtime=runtime, tool_id=tool_id, tool_input=tool_input, tool_name=tool_name, on_child=on_child)
        rt.parent.abort.set()
        return [], ToolResult("stopped by you", is_error=True)
    return stop


@test
def test_workflow_tool_step_children_are_tagged(ctx: Ctx):
    with PacksHome() as h:
        rt, calls = default_rt(h), []
        res = run_tool(rt, {"name": "review", "task": "fix the retry"}, spawn=spawning(calls, rt))
        ctx.check(f"the crew workflow ran on the step runner, got {str(res.content)[:120]!r}",
                  not res.is_error and "crew workflow review · ran on the step runner · done" in str(res.content))
        ctx.check(f"two steps, coder then reviewer, got {[c['who'] for c in calls]}", [c["who"] for c in calls] == ["coder", "reviewer"])
        for i, c in enumerate(calls, 1):
            crew = row(rt, c["aid"]).get("crew")
            ctx.check(f"step {i}'s child is the workflow's step under main, a saved agent, got {crew}",
                      crew == {"map": "starter", "box": "main", "workflow": "review", "step": i, "agent": c["who"], "saved": True})
        ctx.check("the step rows keep their workflow receipt mark (square)",
                  all((row(rt, c["aid"]).get("square") or {}).get("name") == "review" for c in calls))


@test
def test_saved_agent_by_name_is_not_made_up(ctx: Ctx):
    from halo_harness.crew.map_run import agent_call
    from halo_harness.crew.spec import agent_spec
    with PacksHome() as h:
        rt, calls = default_rt(h), []
        rt.agents = {"implementer": agent_spec({"name": "implementer", "does": "builds it"}, source="crew:yours")}
        inner = spawning(calls, rt)
        _ev, tr = agent_call(inner, runtime=rt, tool_id="toolu_9",
                             tool_input={"subagent_type": "implementer", "description": "do it", "prompt": "do it"}, tool_name="Agent")
        crew = row(rt, calls[-1]["aid"]).get("crew")
        ctx.check(f"implementer is the saved agent working for main, not made up, got {crew}",
                  crew == {"map": "starter", "box": "main", "agent": "implementer", "saved": True})
        ctx.check(f"the call ran as a plain session's (its result untouched), got {tr.content!r}",
                  tr.content == "<task_result>implementer did its part</task_result>" and not tr.is_error)


@test
def test_general_purpose_child_is_made_up(ctx: Ctx):
    from halo_harness.crew.map_run import agent_call
    with PacksHome() as h:
        rt, calls = default_rt(h), []
        rt.agents = {}
        for name in ("general-purpose", "nobody-knows"):
            agent_call(spawning(calls, rt), runtime=rt, tool_id="toolu_9",
                       tool_input={"subagent_type": name, "description": "look", "prompt": "look"}, tool_name="Agent")
            crew = row(rt, calls[-1]["aid"]).get("crew")
            ctx.check(f"{name} on the default map: made up, not saved, got {crew}",
                      crew == {"map": "starter", "box": "main", "agent": name, "saved": False, "made_up": True})
        mrt, mcalls = map_runtime(h), []
        call(mrt, spawning(mcalls, mrt), description="look around", prompt="list what the repo holds")
        crew = row(mrt, mcalls[-1]["aid"]).get("crew")
        ctx.check(f"on a map of his, a call no When claims: a general-purpose helper, made up, got {crew}",
                  crew == {"map": "chain", "box": "main", "agent": "general-purpose", "saved": False, "made_up": True})
        mcalls.clear()
        flow(mrt, spawning(mcalls, mrt), "fix the retry in client.py")
        coder = next(c for c in mcalls if c["who"] == "coder")
        crew = row(mrt, coder["aid"]).get("crew")
        ctx.check(f"a lined coder: its box and line, a saved agent, got {crew}",
                  crew == {"map": "chain", "box": "code", "line": "plan -> code", "agent": "coder", "saved": True})


@test
def test_workflow_tool_run_sends_hop_and_steps(ctx: Ctx):
    with PacksHome() as h:
        rt, calls = default_rt(h), []
        run_tool(rt, {"name": "review", "task": "fix the retry"}, spawn=spawning(calls, rt))
        hs = hops(rt)
        ctx.check(f"one start and one end, got {[d.get('state') for d in hs]}", [d.get("state") for d in hs] == ["start", "end"])
        ctx.check(f"each from main to workflow:review, the workflow named, on the default map (not off), no line, got {hs}",
                  all(d.get("from") == "main" and d.get("to") == "workflow:review" and d.get("workflow") == "review"
                      and d.get("off") is False and "line" not in d and d.get("map") == "starter" for d in hs))
        ss = steps(rt)
        ctx.check(f"the runner's step frames, start to end, keyed to the workflow, got {[d.get('kind') for d in ss]}",
                  len(ss) >= 2 and ss[0].get("kind") == "start" and ss[-1].get("kind") == "end"
                  and all(d.get("box") == "workflow:review" and d.get("workflow") == "review" for d in ss))
        logged = [n["event"] for n in rt.parent.log.receipts() if n.get("kind") == "map"]
        ctx.check(f"the log holds the same frames (a replay), got {len(logged)} of {len(hs) + len(ss)}", len(logged) == len(hs) + len(ss))


@test
def test_hop_from_is_the_callers_box(ctx: Ctx):
    from halo_harness.agent.agent_registry import tree_for
    with PacksHome() as h:
        cases = []
        for case in ("own", "parent", "none"):
            rt, calls = default_rt(h), []
            rt.depth = 1
            rt.parent.agent_id = "a7"
            tree = tree_for(rt.parent)
            tree.add("p1", parent="main", name="planner", state="running", kind="subagent",
                     crew={"map": "starter", "box": "planner", "agent": "planner", "saved": True} if case == "parent" else None)
            tree.add("a7", parent="p1", name="coder", state="running", kind="subagent",
                     crew={"map": "starter", "box": "coder", "line": "main -> coder", "agent": "coder", "saved": True}
                     if case == "own" else None)
            run_tool(rt, {"name": "review", "task": "fix the retry"}, spawn=spawning(calls, rt))
            cases.append((case, [d.get("from") for d in hops(rt)]))
        ctx.check(f"from = its own row's box, else its parent row's, else main, got {cases}",
                  cases == [("own", ["coder", "coder"]), ("parent", ["planner", "planner"]), ("none", ["main", "main"])])


@test
def test_made_up_child_hops_to_its_aid(ctx: Ctx):
    with PacksHome() as h:
        rt, calls = map_runtime(h), []
        call(rt, spawning(calls, rt), description="look around", prompt="list it")
        hs = hops(rt)
        aid = calls[-1]["aid"]
        ctx.check(f"a start and an end, got {[d.get('state') for d in hs]}", [d.get("state") for d in hs] == ["start", "end"])
        ctx.check(f"from main to made-up:{aid}, its aid, off the lines on a map of his, no line, got {hs}",
                  all(d.get("to") == "made-up:" + aid and d.get("aid") == aid and d.get("from") == "main" and d.get("off") is True
                      and "line" not in d for d in hs))


@test
def test_unlined_drawn_child_sends_a_hop(ctx: Ctx):
    from halo_harness.crew.map_run import agent_call
    from halo_harness.crew.spec import agent_spec
    with PacksHome() as h:
        rt, calls = default_rt(h), []
        rt.agents = {"implementer": agent_spec({"name": "implementer", "does": "builds it"}, source="crew:yours")}
        seen: dict = {}
        inner = spawning(calls, rt)

        def kept(**kw):
            ev, tr = inner(**kw)
            seen["content"], seen["is_error"] = tr.content, tr.is_error
            return ev, tr
        _ev, tr = agent_call(kept, runtime=rt, tool_id="toolu_9",
                             tool_input={"subagent_type": "implementer", "description": "do it", "prompt": "do it"}, tool_name="Agent")
        hs, aid = hops(rt), calls[-1]["aid"]
        ctx.check(f"a start and an end to made-up:{aid}, on the default map (not off), got {hs}",
                  [d.get("state") for d in hs] == ["start", "end"]
                  and all(d.get("to") == "made-up:" + aid and d.get("off") is False and d.get("from") == "main" for d in hs))
        ctx.check("send only: the tool result is what inner returned", tr.content == seen["content"] and tr.is_error == seen["is_error"])


@test
def test_hop_end_sent_on_error_and_stop(ctx: Ctx):
    from halo_harness.crew.map_run import agent_call
    with PacksHome() as h:
        out = []
        # a lined workflow box on a map of his whose spawn raises: the raise propagates (or is the step's failure)
        rt, calls = map_runtime(h), []
        try:
            flow(rt, raising(calls, rt), "fix the retry in client.py")
        except RuntimeError:
            pass
        out.append(("map box raises", [(d.get("line"), d.get("state"), d.get("error")) for d in hops(rt) if d.get("state") != "skipped"]))
        # a chain hop (plan -> code, run by _hop outside any step runner) whose spawn raises: the raise leaves _hop itself
        rt, calls = map_runtime(h), []
        raised = False
        try:
            flow(rt, raising_for(calls, rt, "coder"), "fix the retry in client.py")
        except RuntimeError:
            raised = True
        out.append(("chain hop raises", raised, [(d.get("state"), d.get("error")) for d in hops(rt) if d.get("line") == "plan -> code"]))
        # a named agent on a line whose spawn raises
        rt, calls = map_runtime(h), []
        rt.parent.messages = [{"role": "user", "content": "have the tester run the suite"}]
        raised = False
        try:
            call(rt, raising(calls, rt), subagent_type="tester", description="run the tests", prompt="run the tests")
        except RuntimeError:
            raised = True
        out.append(("named raises", raised, [(d.get("state"), d.get("error")) for d in hops(rt)]))
        # a stop (the session's abort set, an error result)
        rt, calls = map_runtime(h), []
        rt.parent.messages = [{"role": "user", "content": "have the tester run the suite"}]
        call(rt, stopping(calls, rt), subagent_type="tester", description="run the tests", prompt="run the tests")
        out.append(("named stopped", [(d.get("state"), d.get("error")) for d in hops(rt)]))
        # the door on the default map, its spawn raising
        rt, calls = default_rt(h), []
        try:
            run_tool(rt, {"name": "review", "task": "fix the retry"}, spawn=raising(calls, rt))
        except RuntimeError:
            pass
        out.append(("door", [(d.get("state"), d.get("error")) for d in hops(rt)]))
        # a made-up helper whose spawn raises after its child exists
        rt, calls = map_runtime(h), []
        try:
            call(rt, raising(calls, rt), description="look around", prompt="list it")
        except RuntimeError:
            pass
        out.append(("made up", [(d.get("state"), d.get("error")) for d in hops(rt)]))
        # the default map's unlined branch
        rt, calls = default_rt(h), []
        rt.agents = {}
        try:
            agent_call(raising(calls, rt), runtime=rt, tool_id="toolu_9",
                       tool_input={"subagent_type": "nobody-knows", "description": "x", "prompt": "x"}, tool_name="Agent")
        except RuntimeError:
            pass
        out.append(("drawn unlined", [(d.get("state"), d.get("error")) for d in hops(rt)]))
        ctx.check(f"every start has its end, with error, got {out}", out == [
            ("map box raises", [("main -> plan", "start", None), ("main -> plan", "end", True)]),
            ("chain hop raises", True, [("start", None), ("end", True)]),
            ("named raises", True, [("start", None), ("end", True)]),
            ("named stopped", [("start", None), ("end", True)]),
            ("door", [("start", None), ("end", True)]),
            ("made up", [("start", None), ("end", True)]),
            ("drawn unlined", [("start", None), ("end", True)])])


@test
def test_no_frame_after_the_session_closed(ctx: Ctx):
    from halo_harness.crew import map_events
    with PacksHome() as h:
        rt = FakeRuntime(h.repo)
        before = map_events.publish(rt.parent, "map_hop", {"state": "start", "t": 1})
        ctx.check("before the end: on the feed and in the log",
                  len([f for f in rt.frames if f[0] == "map_hop"]) == 1 and len(rt.parent.log.receipts()) == 1 and before["t"] == 1)
        map_events.close(rt.parent)  # what Session.close_runtimes calls
        got = map_events.publish(rt.parent, "map_hop", {"state": "end", "t": 2})
        ctx.check(f"after the end: nothing on the feed, nothing in the log, the data still returned, got {got}",
                  len([f for f in rt.frames if f[0] == "map_hop"]) == 1 and len(rt.parent.log.receipts()) == 1 and got == {"state": "end", "t": 2})


@test
def test_close_runtimes_marks_the_session_closed(ctx: Ctx):
    """The one line in agent/loop.py: Session.close_runtimes marks the session closed for map_events."""
    from halo_harness.agent.loop import Session
    from halo_harness.crew import map_events
    s = Session.__new__(Session)
    ctx.check("open before", not map_events.closed(s))
    Session.close_runtimes(s)
    ctx.check("closed after close_runtimes", map_events.closed(s))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
