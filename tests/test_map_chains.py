"""tests.test_map_chains -- Halo 3.6.0.0 R3: main's hand-offs on a map and the chains the runtime follows
(halo_harness/crew/map_run.py; docs/CREW-sessions.md "Chains").

1. main -> plan -> code -> reviewer: main hands the task to the plan workflow (its steps on the step runner); the
   runtime follows plan -> code -> reviewer by itself, each target getting the task and what came before; one receipt
   line per hand-off names the line that fired; no call decides a chain (a fake model: each agent's reply scripted);
2. a `needs: [pdf]` line is taken only for a task with a PDF (and says why when it is not);
3. the Agent tool on a map: exactly main's agents (another name is one line), an `ask` line runs only when the person
   named it, a call with no target follows the first line whose When fires; the session's cap stops hand-offs;
4. (R4) every hand-off is a `map_hop` frame (start / end / skipped), a workflow box's steps `map_step` frames, the same
   in the log, each spawned row tagged with its box; a call no line claims runs as a helper main made up.
Fakes only, no model call. Run: python -m tests.test_map_chains
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.workflow_fakes import FakeRuntime  # noqa: E402

test, TESTS = new_registry()
MAP = """format: map/1
name: chain
boxes:
- {id: plan, workflow: plan}
- {id: code, agent: coder}
- {id: review, agent: reviewer}
- {id: pdfs, agent: media-reader}
- {id: sec, agent: tester}
lines:
- {from: main, to: plan, when: always}
- {from: plan, to: code, when: always}
- {from: code, to: review, when: always}
- {from: code, to: pdfs, when: {needs: [pdf]}}
- {from: main, to: sec, when: ask}
caps: {session_usd: 1.0}
"""


def fake(calls: list, cost: float = 0.0, rt=None):
    from halo_harness.tools.base import ToolResult

    def inner(*, runtime, tool_id, tool_input, tool_name, on_event=None, on_child=None):
        who = tool_input.get("subagent_type")
        calls.append({"who": who, "prompt": tool_input.get("prompt") or ""})
        if rt is not None and cost:
            rt.team_control.record_spend(cost)
        return [], ToolResult(f"<task_result>{who} did its part</task_result>")
    return inner


def runtime(h, text: str = MAP):
    from halo_harness.crew.compile import compile_map
    from halo_harness.crew.map_control import MapControl
    from halo_harness.crew import store
    p = store.path_for("map", "chain")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    rt = FakeRuntime(h.repo)
    c = compile_map("chain", cwd=h.repo)
    assert not c.problems, c.problems
    rt.team_control = MapControl(c, cwd=h.repo, session=rt.parent)
    return rt


def call(rt, inner, **tool_input):
    from halo_harness.crew.map_run import agent_call
    return agent_call(inner, runtime=rt, tool_id="toolu_9", tool_input=tool_input, tool_name="Agent")[1]


def flow(rt, inner, task: str, files=()):
    from halo_harness.crew import map_run
    from halo_harness.tools.base import ToolContext
    import halo_harness.agent.subagent as sub
    saved = sub.run_agent_call
    sub.run_agent_call = inner  # the workflow tool's own spawn: the fake model
    try:
        ctx = ToolContext(cwd=rt.parent.cwd, tool_use_id="toolu_1")
        return map_run.workflow_call(rt, {"task": task, "files": list(files)}, ctx)
    finally:
        sub.run_agent_call = saved


@test
def test_main_plan_code_reviewer_is_followed_with_receipts(ctx: Ctx):
    with PacksHome() as h:
        rt, calls = runtime(h), []
        res = flow(rt, fake(calls), "fix the retry in client.py")
        text = str(res.content)
        ctx.check(f"planner (the plan workflow's step), then coder, then reviewer, got {[c['who'] for c in calls]}",
                  [c["who"] for c in calls] == ["planner", "coder", "reviewer"])
        ctx.check("main's hand-off receipt names its line", "map chain · line main -> plan (always) · plan" in text)
        ctx.check("each chain hop's receipt names its line",
                  "map chain · line plan -> code (always) · coder" in text and "map chain · line code -> review (always) · reviewer" in text)
        ctx.check("the next target gets the task and what came before (as data)",
                  "fix the retry" in calls[1]["prompt"] and "planner did its part" in calls[1]["prompt"] and "coder did its part" in calls[2]["prompt"])
        ctx.check("the PDF line is not taken without a PDF, and says why", "line code -> pdfs not taken" in text and "media-reader" not in
                  [c["who"] for c in calls])
        ctx.check("every hand-off is recorded", [f["line"] for f in rt.team_control.fired] == ["main -> plan", "plan -> code", "code -> review"])


@test
def test_a_needs_pdf_line_is_taken_for_a_task_with_a_pdf(ctx: Ctx):
    with PacksHome() as h:
        rt, calls = runtime(h), []
        res = flow(rt, fake(calls), "fix the totals the spec in invoice.pdf describes", files=["invoice.pdf"])
        ctx.check(f"media-reader runs after coder, got {[c['who'] for c in calls]}",
                  [c["who"] for c in calls] == ["planner", "coder", "reviewer", "media-reader"])
        ctx.check("its receipt says the need", "line code -> pdfs (when the task needs a PDF: the task needs a PDF) · media-reader" in str(res.content))


@test
def test_the_agent_tool_offers_exactly_mains_agents(ctx: Ctx):
    with PacksHome() as h:
        rt, calls = runtime(h), []
        got = call(rt, fake(calls), subagent_type="coder", description="fix it", prompt="fix it")
        ctx.check(f"coder has no line from main: one line naming main's agents, got {got.content!r}",
                  got.is_error and "no line from main" in got.content and "tester" in got.content and calls == [])
        got = call(rt, fake(calls), subagent_type="tester", description="run the tests", prompt="run the tests")
        ctx.check(f"an ask line: the person did not name it, got {got.content!r}", got.is_error and "only when the person asks" in got.content)
        rt.parent.messages = [{"role": "user", "content": "have the tester run the suite"}]
        got = call(rt, fake(calls), subagent_type="tester", description="run the tests", prompt="run the tests")
        ctx.check(f"named by the person: it runs, its receipt says so, got {got.content!r}",
                  not got.is_error and "line main -> sec (only when I ask" in got.content and calls[-1]["who"] == "tester")


@test
def test_the_session_cap_stops_hand_offs(ctx: Ctx):
    with PacksHome() as h:
        rt, calls = runtime(h), []
        res = flow(rt, fake(calls, cost=0.6, rt=rt), "fix the retry in client.py")
        ctx.check(f"the cap ($1.00) stops the chain before reviewer, got {[c['who'] for c in calls]}",
                  [c["who"] for c in calls] == ["planner", "coder"] and "session cap ($1.00, caps.session_usd) is reached" in str(res.content))
        again = flow(rt, fake(calls), "another task")
        ctx.check("the next hand-off is one plain line", again.is_error and "no more hand-offs this session" in str(again.content))


def spawning(calls: list, rt):
    """A fake spawn that adds the child's row and hands the child to `on_child` (as run_agent_call does)."""
    from halo_harness.agent.agent_registry import tree_for
    from halo_harness.tools.base import ToolResult
    from tests.helpers.workflow_fakes import FakeChild

    def inner(*, runtime, tool_id, tool_input, tool_name, on_event=None, on_child=None):
        who = tool_input.get("subagent_type")
        child = FakeChild(f"a{len(calls)}")
        tree_for(rt.parent).add(child.agent_id, parent="main", name=who, state="running", kind="subagent")
        calls.append({"who": who, "aid": child.agent_id})
        if on_child is not None:
            on_child(child)
        return [], ToolResult(f"<task_result>{who} did its part</task_result>")
    return inner


@test
def test_every_hand_off_and_step_is_a_frame_and_in_the_log(ctx: Ctx):
    """R4: the lit Map reads `map_hop` (start / end / skipped) and `map_step` frames; the log holds the same."""
    with PacksHome() as h:
        rt, calls = runtime(h), []
        flow(rt, spawning(calls, rt), "fix the retry in client.py")
        hops = [(d["line"], d["state"]) for k, _a, d in rt.frames if k == "map_hop"]
        ctx.check(f"each line's start and end, the PDF line skipped, got {hops}",
                  hops == [("main -> plan", "start"), ("main -> plan", "end"), ("plan -> code", "start"), ("plan -> code", "end"),
                           ("code -> review", "start"), ("code -> review", "end"), ("code -> pdfs", "skipped")])
        end = next(d for k, _a, d in rt.frames if k == "map_hop" and d["line"] == "plan -> code" and d["state"] == "end")
        ctx.check(f"a hop names its box, its When, the task's first words and the child it spawned, got {end}",
                  end["to"] == "code" and end["when"] == "always" and end["task"].startswith("fix the retry") and end["agent_id"] == calls[1]["aid"])
        steps = [d["kind"] for k, _a, d in rt.frames if k == "map_step"]
        ctx.check(f"the plan box's steps as the runner emits them, got {steps}", steps[0] == "start" and "step" in steps and "agent" in steps
                  and steps[-1] == "end" and all(d["box"] == "plan" for k, _a, d in rt.frames if k == "map_step"))
        from halo_harness.agent.agent_registry import tree_for
        crew = tree_for(rt.parent).row(calls[1]["aid"]).get("crew")
        ctx.check(f"coder's row says its box and line, got {crew}", crew == {"map": "chain", "box": "code", "line": "plan -> code"})
        logged = [n["event"] for n in rt.parent.log.receipts() if n.get("kind") == "map"]
        ctx.check(f"the log holds the same events (a replay reads them), got {len(logged)} of {len(hops) + len(steps)}",
                  len(logged) == len(hops) + len(steps))


@test
def test_a_call_no_line_claims_is_a_made_up_helper(ctx: Ctx):
    """R4: a call naming no agent that no When claims runs as a helper main made up; a named stranger is still one line."""
    with PacksHome() as h:
        rt, calls = runtime(h), []
        got = call(rt, spawning(calls, rt), description="look around", prompt="list what the repo holds")
        ctx.check(f"it ran as general-purpose, the receipt says made up, got {got.content!r}",
                  not got.is_error and calls[-1]["who"] == "general-purpose" and "a helper main made up for this task" in got.content)
        from halo_harness.agent.agent_registry import tree_for
        crew = tree_for(rt.parent).row(calls[-1]["aid"]).get("crew")
        ctx.check(f"its row hangs off main, made up, got {crew}", crew == {"map": "chain", "box": "main", "made_up": True})
        got = call(rt, spawning(calls, rt), subagent_type="general-purpose", description="look around", prompt="again")
        ctx.check("general-purpose named is the same as naming none", not got.is_error and "made up" in got.content)
        got = call(rt, spawning(calls, rt), subagent_type="coder", description="fix it", prompt="fix it")
        ctx.check("a named agent with no line from main stays one line", got.is_error and "no line from main" in got.content)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
