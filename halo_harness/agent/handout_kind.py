"""halo_harness.agent.handout_kind -- ONE meaning of "itself" (3.6.0.10 MW, rule M10; the decisions' B8): what a tool
call of main's is, for main's per-turn counts (agent/agent_registry.py `turn`) and for the gym alike.

    kind(tool) -> "handout" | "board" | "own"

An Agent or Task call or a Workflow run hands work out; the task board's tools are neither; every other tool call is
main's own step.
"""

from __future__ import annotations

HANDOUT = frozenset({"Agent", "Task", "Workflow"})
BOARD = frozenset({"TaskCreate", "TaskUpdate", "TaskList", "TodoWrite"})


def kind(tool) -> str:
    name = str(tool or "")
    if name in HANDOUT:
        return "handout"
    if name in BOARD:
        return "board"
    return "own"
