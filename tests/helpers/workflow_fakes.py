"""tests.helpers.workflow_fakes -- a session, its log and its runtime, enough for the Workflow tool (Halo 3.3.16.0 R3,
tools/workflow.py) to run with a fake spawn: the receipts land in `FakeLog.nodes`, the usage in `FakeLog.usage`, the
agent tree is the real one (agent/agent_registry.py `tree_for`), so its frames are the ones Studio would get.

    rt = FakeRuntime(repo, model="or:vendor/text-only", team=None)
    result = run_tool(rt, {"task": ..., "files": [...]}, spawn=fake, takes=["text"], run_orchestra=None)
    frames(rt)   # [(kind, agent_id, row)] the tree published since the runtime was made
"""
from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace


class FakeLog:
    def __init__(self) -> None:
        self.nodes: list = []
        self.usage: list = []

    def _append(self, node: dict) -> dict:
        self.nodes.append(dict(node))
        return node

    def append_usage(self, usage, cost_usd=None, **kw) -> dict:
        self.usage.append({"cost_usd": cost_usd, **kw})
        return {}

    def receipts(self) -> list:
        return [n for n in self.nodes if n.get("type") == "receipt"]


class FakeSession:
    def __init__(self, cwd: Path, model: str) -> None:
        self.cwd = Path(cwd)
        self.log = FakeLog()
        self.model_ref = SimpleNamespace(raw=model)
        self.state_dir = None
        self.abort = threading.Event()


class FakeChild:
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.abort = threading.Event()


class FakeRuntime:
    def __init__(self, repo, model: str = "or:vendor/text-only", team=None) -> None:
        from halo_harness.agent.agent_registry import tree_for
        self.parent = FakeSession(repo, model)
        self.team_control = team
        self.frames: list = []
        tree_for(self.parent).add_listener(lambda kind, aid, row: self.frames.append((kind, aid, dict(row or {}))))


def child_row(rt, aid: str, **fields) -> FakeChild:
    """A child the spawn made: its row in the session's tree (as register_child adds it), and the child."""
    from halo_harness.agent.agent_registry import tree_for
    tree_for(rt.parent).add(aid, parent="main", name="general-purpose", state="running", kind="subagent", **fields)
    return FakeChild(aid)


def run_tool(rt, tool_input: dict, *, spawn=None, takes=None, run_orchestra=None):
    from halo_harness.tools import workflow as W
    from halo_harness.tools.base import ToolContext
    saved = (W.SPAWN, W.TAKES, W.RUN_ORCHESTRA)
    W.SPAWN, W.TAKES, W.RUN_ORCHESTRA = spawn, takes, run_orchestra
    try:
        ctx = ToolContext(cwd=rt.parent.cwd, tool_use_id="toolu_1")
        ctx.agent_runtime = rt
        ctx.model_ref = rt.parent.model_ref.raw
        return W.WorkflowTool().run(tool_input, ctx)
    finally:
        W.SPAWN, W.TAKES, W.RUN_ORCHESTRA = saved
