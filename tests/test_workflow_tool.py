"""tests.test_workflow_tool -- the Workflow tool's hand-off through a fake agent call (Halo 3.3.16.0 R3,
tools/workflow.py, workflows/square_run.py, workflows/receipts.py): a session square's receipt line in the
answer and one `receipt` node in the transcript (the files' names, never their content); the Live node
frame (the child's agent row carries `square: {name, engine}`); the cost rolls up as the child's (an
orchestra square's run cost is one usage node); a `gives` miss is one line; a refused hand-off is a receipt
too and never an error; the cap stops a child that spends past it; an orchestra run lists the squares it
used, in order. Fakes only, no model call.

Run: python -m tests.test_workflow_tool
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.workflow_fakes import FakeRuntime, child_row, run_tool  # noqa: E402

test, TESTS = new_registry()


def spawner(rt, text: str, cost: float = 0.02, after=None):
    from halo_harness.agent.agent_registry import tree_for
    from halo_harness.tools.base import ToolResult

    def spawn(*, runtime, tool_id, tool_input, tool_name, on_child=None):
        child = child_row(rt, "c1", cost_usd=cost)
        if on_child:
            on_child(child)
        if after:
            after(child, tree_for(rt.parent))
        return [], ToolResult(text)
    return spawn


@test
def test_a_session_square_the_receipt_the_live_node_and_the_cost(ctx: Ctx):
    with PacksHome() as h:
        rt = FakeRuntime(h.repo)
        got = run_tool(rt, {"task": "summarize the report", "files": ["docs/report.pdf"]}, spawn=spawner(rt, "page 1: revenue up"),
                       takes=["text"])
        first = got.content.splitlines()[0]
        ctx.check(f"the receipt line, got {first!r}", first == "square media · in pdf (report.pdf) · back text · $0.0200 -- "
                  "handing the PDF to media: your model takes text only")
        ctx.check("then what came back", got.content.endswith("page 1: revenue up") and not got.is_error)
        recs = rt.parent.log.receipts()
        ctx.check(f"one receipt node, got {len(recs)}", len(recs) == 1)
        r = recs[0]
        ctx.check(f"the files' names, never the path or content, got {r.get('files')}", r.get("files") == ["report.pdf"])
        ctx.check(f"which square, the engine, the cost, got {r}", r["square"] == "media" and r["engine"] == "session"
                  and r["cost_usd"] == 0.02 and r["status"] == "done" and r["back"] == "text" and r["line"] == first)
        sq = [row.get("square") for kind, aid, row in rt.frames if aid == "c1" and row.get("square")]
        ctx.check(f"the Live node frame carries the square, got {sq[-1:] }", sq and sq[-1] == {"name": "media", "engine": "session"})
        ctx.check("no usage node of its own: the child rolls up as every sub-agent does", rt.parent.log.usage == [])


@test
def test_a_gives_miss_is_one_line(ctx: Ctx):
    with PacksHome() as h:
        rt = FakeRuntime(h.repo)
        got = run_tool(rt, {"task": "read shot.png"}, spawn=spawner(rt, "   "), takes=["text"])
        first = got.content.splitlines()[0]
        ctx.check(f"named on the receipt, got {first!r}", first.endswith("(gives missed: text (the reply is empty))"))
        ctx.check("and on the node", rt.parent.log.receipts()[0]["gives_miss"] == "gives missed: text (the reply is empty)")


@test
def test_a_refused_hand_off_is_a_receipt_and_never_an_error(ctx: Ctx):
    with PacksHome() as h:
        rt = FakeRuntime(h.repo)
        called = []
        got = run_tool(rt, {"task": "plan the move", "name": "plan"}, spawn=lambda **k: called.append(k), takes=["text"])
        ctx.check(f"one line, no spawn, got {got.content!r}", not called and not got.is_error
                  and got.content == "square - did not start -- plan is not enabled for this lineup: halo workflows enable plan "
                  "(or Studio: Agents -> Workflows)")
        ctx.check("the receipt says not-started", rt.parent.log.receipts()[0]["status"] == "not-started")
        rt.parent._square_hops = 0
        got = run_tool(rt, {"task": "read a.pdf"}, spawn=lambda **k: called.append(k), takes=["text"])
        ctx.check(f"inside a depth-1 square: refused, got {got.content!r}", not called and "allows no further square" in got.content)


@test
def test_the_cap_stops_a_child_that_spends_past_it(ctx: Ctx):
    from halo_harness.workflows import square_run
    with PacksHome() as h:
        rt = FakeRuntime(h.repo)
        saved, square_run.WATCH_S = square_run.WATCH_S, 0.01

        def overspend(child, tree):
            tree.update("c1", cost_usd=3.0)
            deadline = time.time() + 5
            while not child.abort.is_set() and time.time() < deadline:
                time.sleep(0.01)
        try:
            got = run_tool(rt, {"task": "read a.pdf"}, spawn=spawner(rt, "partial", after=overspend), takes=["text"])
        finally:
            square_run.WATCH_S = saved
        r = rt.parent.log.receipts()[0]
        ctx.check(f"stopped at the cap ($1.00), got {r.get('status')} {r.get('stop')!r}",
                  r["status"] == "stopped" and r["stop"] == "its cost passed the cap $1.00")
        ctx.check("the line says so", "stopped: its cost passed the cap $1.00" in got.content.splitlines()[0])


@test
def test_an_orchestra_square_its_node_its_cost_and_the_run_report(ctx: Ctx):
    with PacksHome() as h:
        rt = FakeRuntime(h.repo)
        from halo_harness.workflows.registry import enable
        enable("code", cwd=h.repo)

        def runner(run_dir):
            (Path(run_dir) / "report.json").write_text(json.dumps({"status": "finished", "cost_usd": 0.5, "finished": True}), encoding="utf-8")
        got = run_tool(rt, {"task": "fix the failing test", "name": "code"}, run_orchestra=runner, takes=["text"])
        ctx.check(f"done, got {got.content.splitlines()[0]!r}", got.content.startswith("square code · in ") and "$0.5000" in got.content)
        ctx.check(f"one usage node, square:code $0.50, got {rt.parent.log.usage}",
                  rt.parent.log.usage == [{"cost_usd": 0.5, "agent_id": "square:code"}])
        nodes = [row for kind, aid, row in rt.frames if aid.startswith("sq-")]
        ctx.check(f"a node under main, then its state, got {nodes[-1:]}", nodes and nodes[0].get("parent") == "main"
                  and nodes[-1].get("square") == {"name": "code", "engine": "orchestra"} and nodes[-1].get("state") == "done")
        from halo_harness.workflows import receipts
        run = h.repo / "run-dir"
        run.mkdir()
        os.environ["HALO_ORCHESTRA_RUN"] = str(run)
        try:
            for name in ("media", "plan"):
                receipts.write(rt.parent, {"square": name, "need": "x", "status": "done", "cost_usd": 0.1})
        finally:
            os.environ.pop("HALO_ORCHESTRA_RUN", None)
        part = receipts.report_part(run)
        ctx.check(f"the run's squares in order, got {part}", [r["square"] for r in part.get("squares", [])] == ["media", "plan"])
        ctx.check("the report's line", receipts.report_lines(part) == ["  squares: media (done, $0.1000) -> plan (done, $0.1000)"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
