"""tests.test_live_groups -- Halo 3.3.16.3 "Live in groups": what an agent row carries so Studio's Live can box the
agents of one task (agent/agent_hooks.py `spawn_of`, agent/agent_observe.py's per-reply `_said`): `spawn: {step,
description, lead}` -- every Agent call of one reply shares the step (the parent's id and its reply count), a call in
the next reply has another, a count job queued then built keeps the step it was queued with, `lead` is the last line
the parent wrote in that reply; a square's agent row carries the square's DOES line (workflows/receipts.py). The
grouping itself is Studio's (routes/agents/live/groups.ts): its rule is pinned in the source here. Pure; no model.
Run: python -m tests.test_live_groups
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _ev(kind: str, **data):
    return NS(kind=kind, data=data)


def _reply(tree, aid: str, text: str) -> None:
    """One model reply of `aid`: its text, then its end (the tool calls run after it)."""
    tree.observe(aid, _ev("message_start"))
    for chunk in (text[: len(text) // 2], text[len(text) // 2:]):
        tree.observe(aid, _ev("text_delta", text=chunk))
    tree.observe(aid, _ev("message_end"))


def _tree():
    from halo_harness.agent.agent_registry import AgentTree
    from halo_harness.agent.agent_registry import tree_for
    root = NS(agent_id=None, model_ref=None, log=None)
    return root, tree_for(root)


def _spawn(root, aid: str, desc: str, prompt: str = "do it") -> None:
    from halo_harness.agent.agent_hooks import register_child
    child = NS(log=None, opt_ins=None)
    register_child(root, child, agent_id=aid, spec=NS(name="general-purpose"), model="or:mock/m", role="reader",
                   task_text=f"{desc}\n{prompt}")


@test
def test_one_reply_shares_a_step_the_next_has_another(ctx: Ctx):
    root, tree = _tree()
    tree.started("main", root, "read the three PDFs and review")
    _reply(tree, "main", "Let me look.\nI'll read the three PDFs side by side.")
    for i in range(3):
        _spawn(root, f"r{i}", f"Read PDF {i + 1}")
    _reply(tree, "main", "")
    _spawn(root, "v1", "Review the notes")
    rows = {r["agent_id"]: r for r in tree.public_rows()}
    steps = [rows[f"r{i}"]["spawn"]["step"] for i in range(3)]
    ctx.check(f"the three of one reply share a step, got {steps}", len(set(steps)) == 1 and steps[0] == "main#1")
    ctx.check(f"each keeps its own description, got {[rows[f'r{i}']['spawn']['description'] for i in range(3)]}",
              [rows[f"r{i}"]["spawn"]["description"] for i in range(3)] == ["Read PDF 1", "Read PDF 2", "Read PDF 3"])
    ctx.check(f"the lead is the parent's last line in that reply, got {rows['r0']['spawn']['lead']!r}",
              rows["r0"]["spawn"]["lead"] == "I'll read the three PDFs side by side.")
    v = rows["v1"]["spawn"]
    ctx.check(f"a spawn of the next reply is a step of its own with no lead, got {v}", v["step"] == "main#2" and v["lead"] == "")


@test
def test_a_queued_job_keeps_its_step_and_a_prompt_without_a_description(ctx: Ctx):
    from halo_harness.agent.agent_hooks import register_queued
    root, tree = _tree()
    tree.started("main", root, "go")
    _reply(tree, "main", "Fanning out.")
    register_queued(root, "q1", name="general-purpose", task="Summarise chapter one", description="Summarise (1/2)")
    _reply(tree, "main", "later words")
    _spawn(root, "q1", "Summarise (1/2)")  # the job starts after main moved on: the step it was queued with stays
    _spawn(root, "p1", "", "Check the links in README.md\nthen say which are dead")
    rows = {r["agent_id"]: r for r in tree.public_rows()}
    ctx.check(f"the queued job's step is its queue time's, got {rows['q1']['spawn']}", rows["q1"]["spawn"]["step"] == "main#1"
              and rows["q1"]["spawn"]["description"] == "Summarise (1/2)" and rows["q1"]["spawn"]["lead"] == "Fanning out.")
    ctx.check(f"no description: the prompt's first line, got {rows['p1']['spawn']}",
              rows["p1"]["spawn"]["description"] == "Check the links in README.md")


@test
def test_a_square_agent_carries_its_does_line(ctx: Ctx):
    from halo_harness.workflows import receipts
    root, tree = _tree()
    _spawn(root, "c1", "square media")
    receipts.mark_child(root, NS(agent_id="c1"), "media", "session", does="Reads PDFs for a model that cannot.")
    key = receipts.node(root, "code", "orchestra", state="running", does="Makes a code change.")
    rows = {r["agent_id"]: r for r in tree.public_rows()}
    ctx.check(f"the session square's agent, got {rows['c1'].get('square')}",
              rows["c1"]["square"] == {"name": "media", "engine": "session", "does": "Reads PDFs for a model that cannot."})
    ctx.check(f"the orchestra square's node, got {rows[key].get('square')}", rows[key]["square"]["does"] == "Makes a code change.")


@test
def test_studio_groups_by_these_fields(ctx: Ctx):
    """The rule Studio draws by (routes/agents/live/groups.ts): siblings of one step, two or more, are a task group; a
    square's agent and the agents under it are its group; the rest of a lineup tier's agents are grouped by the tier."""
    src = (REPO / "halo_harness" / "studio" / "ui" / "src" / "routes" / "agents" / "live" / "groups.ts").read_text(encoding="utf-8")
    for needle in ("spawn?.step", "square", "tier", "MIN_TASK = 2"):
        ctx.check(f"groups.ts reads {needle!r}", needle in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
