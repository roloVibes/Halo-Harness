"""tests.test_child_mode_follows -- Halo 3.4.1.2 (ENGINE-5): a mode switch on the main session never reached running
sub-agents (agent/subagent.py built the child engine once with its clamped mode). Now the child's engine reads its
mode clamped to its parent engine's current one (halo_harness/perm_clamp.py, `PermissionEngine(parent=...)`):

- a child spawned in auto: the parent switches to plan -> the child's Write is denied; to default -> asked; back to
  auto -> the child's own auto again (never above the parent's);
- a child that set itself to plan stays in plan whatever the parent does;
- the real spawn path (`_build_child_session`) links the child to the parent.
Run: python -m tests.test_child_mode_follows
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.fake_home import build_fake_home  # noqa: E402
from tests.helpers.mock_openai import MockUpstream  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_review2_round8 import _restore_home, _session  # noqa: E402

test, TESTS = new_registry()


def _write(engine, proj: Path) -> str:
    return engine.decide("Write", {"file_path": str(proj / "f.txt"), "content": "x"}).action


@test
def test_engine5_a_parents_mode_change_clamps_a_live_child(ctx: Ctx):
    from halo_harness.permissions import PermissionEngine
    proj = Path(build_fake_home()["proj"])
    parent = PermissionEngine(mode="auto", cwd=proj)
    child = PermissionEngine(mode="auto", cwd=proj, parent=parent)
    ctx.check(f"both auto: the child writes, got {_write(child, proj)}", _write(child, proj) == "allow")
    parent.mode = "plan"
    ctx.check(f"the parent in plan: the child's Write is denied, got {child.mode} {_write(child, proj)}",
              child.mode == "plan" and _write(child, proj) == "deny")
    parent.mode = "default"
    ctx.check(f"the parent in default: the child asks, got {child.mode} {_write(child, proj)}",
              child.mode == "default" and _write(child, proj) == "ask")
    parent.mode = "auto"
    ctx.check("the parent back in auto: the child's own auto again", child.mode == "auto")
    child.mode = "plan"
    parent.mode = "bypassPermissions"
    ctx.check("a child that set itself to plan stays there", child.mode == "plan")
    grand = PermissionEngine(mode="acceptEdits", cwd=proj, parent=child)
    child.mode = "auto"
    parent.mode = "dontAsk"
    ctx.check(f"a grandchild follows the chain, got {grand.mode}", grand.mode == "dontAsk")


@test
def test_engine5_the_spawn_path_links_the_child(ctx: Ctx):
    from halo_harness.agent.subagent import _build_child_session
    from halo_harness.config.agents_md import AgentSpec
    from halo_harness.permissions import PermissionEngine
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        session = _session(fh, mock)
        session.permission_engine = PermissionEngine(mode="auto", cwd=fh["proj"])
        spec = AgentSpec(name="x", description="d", permission_mode=None, source="user")
        child, _ = _build_child_session(runtime=session.agent_runtime, spec=spec, agent_id="e5follow",
                                        model_override=None, parent_tool_use_id="t")
        ctx.check(f"spawned in auto, got {child.permission_engine.mode}", child.permission_engine.mode == "auto")
        session.permission_engine.mode = "plan"
        ctx.check(f"Shift+Tab to plan on the main session: the live child is in plan and cannot write, got "
                  f"{child.permission_engine.mode} {_write(child.permission_engine, Path(fh['proj']))}",
                  child.permission_engine.mode == "plan" and _write(child.permission_engine, Path(fh["proj"])) == "deny")
    finally:
        mock.stop()
        _restore_home()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
