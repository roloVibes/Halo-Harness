"""tests.test_agents_live_tree -- Halo 3.3.11.0 R2: the TUI's `/agents live` prints the tree Studio's Roles Live
draws (agent/agent_hooks.py `format_tree`, `pick_line`): each agent indented under its parent, an `auto` pick's
reason on the line under it in the same words as the Live node (routes/roles/liveModel.ts `pickLine`), and an
agent whose parent is not in the tree under one "unknown parent" line, never dropped. Pure; no session.
Run: python -m tests.test_agents_live_tree
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

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
    src = (REPO / "halo_harness" / "studio" / "ui" / "src" / "routes" / "roles" / "liveModel.ts").read_text(encoding="utf-8")
    ctx.check("liveModel.ts pickLine builds 'picked at spawn: <role> on <model> -- <reason>'",
              "`picked at spawn: ${a.role || a.name}${a.model ? ` on ${a.model}` : \"\"} -- ${a.reason}`" in src)
    ctx.check("Live names the orphans' node 'unknown parent'", 'name: "unknown parent"' in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
