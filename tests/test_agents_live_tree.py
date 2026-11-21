"""tests.test_agents_live_tree -- Halo 3.3.11.0 R2: the TUI's `/agents live` prints the tree Studio's Roles Live
draws (agent/agent_hooks.py `format_tree`, `pick_line`): each agent indented under its parent, an `auto` pick's
reason on the line under it in the same words as the Live node (routes/crew/live/liveModel.ts `pickLine`, moved from routes/roles/ in 3.6.0.0 R4b), and an
agent whose parent is not in the tree under one "unknown parent" line, never dropped. Pure; no session.

3.6.0.5: what a tool call is called while it runs (`agent_transcript.tool_label`, the `current` of an agent's row: main's
box in Session's drawing, a card in Agents -> Live, a line of this tree). A Workflow call was said by its raw input,
`Workflow: {"name": "review", "task": "..."}`: main's row took five lines in a box that holds the room of a usual line
(the UI's sample is `Agent read the report`), so the box grew and every group under it moved the moment a workflow
started (seen on Windows, on the release gate and on the PC; on the Linux VM an earlier long line had already grown
the box). A Workflow call is said by the workflow's name, else by its task; every other tool keeps its label. (These
tests live here and not in a module of their own: the suite's shards are the sorted list mod 4, so a new module moves
every later one to another shard.)
Run: python -m tests.test_agents_live_tree
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from halo_harness.agent.agent_transcript import tool_label  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
WHY = "the bio asks for tools, the best tools model within 3x the cheapest"


def _rows() -> list:
    return [
        {"agent_id": "main", "parent": None, "name": "main", "state": "running", "cost_usd": 0.01, "model": "or:mock/main", "task": "ship it"},
        {"agent_id": "c0d3", "parent": "main", "name": "implementer", "role": "coder", "state": "running", "cost_usd": 0.0,
         "model": "or:mock/cheap-coder", "model_reason": WHY, "current": "Bash: npm test"},
        {"agent_id": "r3v1", "parent": "c0d3", "name": "checker", "role": "reviewer", "state": "done", "cost_usd": 0.002, "model": "or:mock/rev"},
        {"agent_id": "j0b1", "parent": "gone99", "name": "bg job", "state": "running", "model": "-", "task": "a job that never announced"},
    ]


@test
def test_the_tree_with_the_reason_and_the_unknown_parent(ctx: Ctx):
    from halo_harness.agent.agent_hooks import format_tree, pick_line
    lines = format_tree(_rows())
    ctx.check(f"main at the top, got {lines[0]!r}", lines[0].startswith("main "))
    ctx.check(f"the coder one level in, got {lines[1]!r}", lines[1].startswith("  c0d3 ") and "npm test" in lines[1])
    ctx.check(f"its pick's reason under it, got {lines[2]!r}",
              lines[2] == f"    picked at spawn: coder on or:mock/cheap-coder -- {WHY}")
    ctx.check(f"the reviewer under the coder, got {lines[3]!r}", lines[3].startswith("    r3v1 "))
    ctx.check(f"the orphan under one unknown parent line, got {lines[4:]}",
              lines[4] == "unknown parent (not in this session's tree)" and lines[5].startswith("  j0b1 "))
    ctx.check("nothing dropped: every agent has its line", all(any(l.strip().startswith(r["agent_id"]) for l in lines) for r in _rows()))
    ctx.check("no pick, no line", pick_line({"agent_id": "x", "model": "m"}) == "")


@test
def test_the_live_node_says_the_same_words(ctx: Ctx):
    src = (REPO / "halo_harness" / "studio" / "ui" / "src" / "routes" / "crew" / "live" / "liveModel.ts").read_text(encoding="utf-8")
    ctx.check("liveModel.ts pickLine builds 'picked at spawn: <role> on <model> -- <reason>'",
              "`picked at spawn: ${a.role || a.name}${a.model ? ` on ${a.model}` : \"\"} -- ${a.reason}`" in src)
    ctx.check("Live names the orphans' node 'unknown parent'", 'name: "unknown parent"' in src)


HELD = "Agent: read the report"  # the usual line main's box holds room for (ui: routes/crew/map/groupWords.ts MAIN_HOLD)
LONG_TASK = "RC-SUBHANG: fix the login bug and then check every page of the site for the same fault, one by one"


@test
def test_a_workflow_is_called_by_its_name(ctx):
    label = tool_label("Workflow", {"name": "review", "task": LONG_TASK})
    ctx.check(f"a named workflow's label is its name, got {label!r}", label == "Workflow: review")
    ctx.check("no raw input in the label", "{" not in label and '"' not in label)
    ctx.check(f"the label is no longer than the usual line the box holds room for ({len(label)} <= {len(HELD)})",
              len(label) <= len(HELD))


@test
def test_a_workflow_without_a_name_is_called_by_its_task(ctx):
    ctx.check("the task, when there is no name",
              tool_label("Workflow", {"task": "fix the login bug"}) == "Workflow: fix the login bug")
    ctx.check("an empty name does not win", tool_label("Workflow", {"name": "  ", "task": "fix it"}) == "Workflow: fix it")
    ctx.check("a name that is not text does not win",
              tool_label("Workflow", {"name": 3, "task": "fix it"}) == "Workflow: fix it")
    long = tool_label("Workflow", {"task": LONG_TASK + ", and then once more", "files": ["a.py"], "need": "review"})
    ctx.check(f"a task of more than 100 characters is cut at 100 with its mark, got {len(long)}",
              long.startswith("Workflow: RC-SUBHANG: fix the login bug") and long.endswith("...")
              and len(long) == len("Workflow: ") + 100)
    ctx.check("neither a name nor a task: the input as before",
              tool_label("Workflow", {"files": ["a.py"]}) == 'Workflow: {"files": ["a.py"]}')
    ctx.check("no input at all: the tool's name", tool_label("Workflow", {}) == "Workflow" and tool_label("Workflow", None) == "Workflow")


@test
def test_every_other_tool_keeps_its_label(ctx):
    ctx.check("Bash by its command", tool_label("Bash", {"command": "npm test", "description": "run the tests"}) == "Bash: npm test")
    ctx.check("Agent by its description",
              tool_label("Agent", {"description": "read the report", "prompt": "Read it all", "name": "x"}) == HELD)
    ctx.check("Read by its file", tool_label("Read", {"file_path": "a/b.py"}) == "Read: a/b.py")
    ctx.check("a tool with a name and no known argument: its input as before (only Workflow reads `name`)",
              tool_label("Skill", {"name": "review", "task": "x"}) == 'Skill: {"name": "review", "task": "x"}')


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
