"""tests.test_tool_label -- Halo 3.6.0.5: what a tool call is called while it runs (`agent_transcript.tool_label`, the
`current` of an agent's row: main's box in Session's drawing, a card in Agents -> Live).

A Workflow call was said by its raw input, `Workflow: {"name": "review", "task": "..."}`: about 85 characters, five
lines in main's box on Auto, which holds the room of a usual line (two lines; the UI's sample is `Agent read the
report`). So the moment a workflow started, main's box grew and every group under it moved. The real-use check's step
auto-ready-lines saw it on Windows, on the hosted runner and on the PC; on the Linux VM an earlier long line had
already grown the box, so the same check passed there. A Workflow call is now said by the workflow's name, else by its
task; every other tool keeps its label.

Run: python -m tests.test_tool_label
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from halo_harness.agent.agent_transcript import tool_label  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

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
    sys.exit(print_results(results, passed, failed, skipped, label="tool label"))
