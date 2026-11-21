"""tests.test_session_start -- 3.6.0.10 MW rule M1 (a): what a new top session's start sets (the Agent, Task and Workflow
tools' `lineup` and `map_control`, the session's control, the runtime's `team_control`) comes from ONE place,
crew/session_start.py, which the measure (agent/prompt_measure.new_session) and a real Session both use, so the two
cannot differ. In-process, a scratch home and folder of its own (restored after each test); never a model or a server.
Run: python -m tests.test_session_start
"""
from __future__ import annotations

import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
TOOLS = ("Agent", "Task", "Workflow")


@contextmanager
def _scratch():
    """A scratch home and project folder; the home variable as it was afterwards."""
    root = Path(tempfile.mkdtemp(prefix="session-start-"))
    (root / "home").mkdir()
    (root / "proj").mkdir()
    before = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = str(root / "home")
    try:
        yield root
    finally:
        if before is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = before


def _real_session(root: Path):
    """A top Session as headless.build_session starts one on Auto: the map it prepares, the agents it finds."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.config.agents_md import discover_agents
    from halo_harness.crew import map_session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.registry import ToolRegistry, default_tools
    proj = root / "proj"
    compiled = map_session.prepare(None, proj)[0]
    agents, _targets = map_session.agents(discover_agents(proj, settings=None), compiled)
    ctx = SessionContext(cwd=proj, model_label="ol:tiny:3b", tool_registry=ToolRegistry(default_tools()))
    return Session(cwd=proj, model_ref=parse_model_ref("ol:tiny:3b"), model_profile=ModelProfile(),
                   creds=ProviderCreds(base_url="http://127.0.0.1:9", api_key="k"), state_dir=root / "state",
                   model_label="ol:tiny:3b", session_context=ctx, agents=agents, crew_map=compiled)


def _state(s) -> dict:
    control = getattr(s, "team_control", None)
    return {"tools": {n: (getattr(s.tool_registry.get(n), "lineup", "-"), getattr(s.tool_registry.get(n), "map_control", "-"))
                      for n in TOOLS},
            "control": (type(control).__name__, getattr(control, "name", None)),
            "runtime_control": s.agent_runtime.team_control is control,
            "agents": sorted(s.agent_runtime.agents), "depth": s.agent_runtime.depth,
            "restriction": getattr(s, "agent_type_restriction", None)}


@test
def test_a_session_and_the_measure_get_the_same_state(ctx: Ctx):
    from halo_harness.agent.prompt_measure import new_session
    with _scratch() as root:
        real = _state(_real_session(root))
        stub = _state(new_session("ol:tiny:3b", window=16384, cwd=root / "proj"))
    ctx.check(f"the same state, got session {real} and measure {stub}", real == stub)
    ctx.check(f"Auto: every tool's lineup is auto and holds no map, got {real['tools']}",
              all(v == ("auto", None) for v in real["tools"].values()))
    ctx.check(f"Auto: the control answers to auto, got {real['control']}", real["control"][1] == "auto"
              and real["runtime_control"])
    ctx.check(f"a clean home: 15 names, got {real['agents']}", len(real["agents"]) == 15)


@test
def test_the_session_start_calls_tool_state(ctx: Ctx):
    from halo_harness.crew import session_start
    calls = []
    saved = session_start.tool_state

    def spy(session, control):
        calls.append((session, control))
        return saved(session, control)
    session_start.tool_state = spy
    try:
        with _scratch() as root:
            s = _real_session(root)
    finally:
        session_start.tool_state = saved
    ctx.check(f"the start calls tool_state once with its own control, got {len(calls)} call(s)",
              len(calls) == 1 and calls[0][0] is s and calls[0][1] is s.team_control)


@test
def test_tool_state_on_a_map_of_his_and_with_roles_off(ctx: Ctx):
    from halo_harness.crew.session_start import tool_state
    from halo_harness.tools.registry import ToolRegistry, default_tools

    def stub():
        return SimpleNamespace(tool_registry=ToolRegistry(default_tools()), agent_runtime=SimpleNamespace(team_control=None))
    mine = SimpleNamespace(is_map=True, map=SimpleNamespace(source="config"), name="map:mine")
    s = stub()
    tool_state(s, mine)
    ctx.check("his map: the lineup is its name and the tools hold it",
              all(s.tool_registry.get(n).lineup == "map:mine" and s.tool_registry.get(n).map_control is mine for n in TOOLS)
              and s.agent_runtime.team_control is mine)
    drawn = SimpleNamespace(is_map=True, map=SimpleNamespace(source="default"), name="auto")
    s = stub()
    tool_state(s, drawn)
    ctx.check("the default map: lineup auto, no map held",
              all(s.tool_registry.get(n).lineup == "auto" and s.tool_registry.get(n).map_control is None for n in TOOLS))
    s = stub()
    tool_state(s, None)
    ctx.check("roles off: no lineup, no map, no control",
              all(s.tool_registry.get(n).lineup is None and s.tool_registry.get(n).map_control is None for n in TOOLS)
              and s.agent_runtime.team_control is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
