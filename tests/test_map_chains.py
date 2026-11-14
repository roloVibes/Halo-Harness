"""tests.test_map_chains -- Halo 3.6.0.0 R3: main's hand-offs on a map and the chains the runtime follows
(halo_harness/crew/map_run.py; docs/CREW-sessions.md "Chains").

1. main -> plan -> code -> reviewer: main hands the task to the plan workflow (its steps on the step runner); the
   runtime follows plan -> code -> reviewer by itself, each target getting the task and what came before; one receipt
   line per hand-off names the line that fired; no call decides a chain (a fake model: each agent's reply scripted);
2. a `needs: [pdf]` line is taken only for a task with a PDF (and says why when it is not);
3. the Agent tool on a map: exactly main's agents (another name is one line), an `ask` line runs only when the person
   named it, a call with no target follows the first line whose When fires; the session's cap stops hand-offs.
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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
