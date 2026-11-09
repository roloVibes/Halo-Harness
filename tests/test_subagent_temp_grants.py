"""tests.test_subagent_temp_grants -- a sub-agent never keeps a Skill's temporary grant (Halo 3.3.14.0 R2, REVIEW #36
PERMS-15; agent/subagent.py `_build_child_session_inner`): a child spawned while a skill's `allowed-tools` grant is
live gets the parent's permanent allow rules only; the parent still drops its grant at the next message, and the child
never had it. No model is called (the child is built, not run).
Run: python -m tests.test_subagent_temp_grants"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.policy_session import Upstream, fenced_home, session_in  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.turn_session import text_step  # noqa: E402

test, TESTS = new_registry()


@test
def test_a_child_spawned_during_a_skill_run_does_not_hold_the_grant(ctx: Ctx):
    from halo_harness.agent.subagent import AgentRuntime, _build_child_session
    from halo_harness.config.agents_md import AgentSpec
    with fenced_home(armed=False, install=False) as h:
        with Upstream("sub-temp", [text_step("ok")]) as up:
            parent = session_in(h, up, mode="default")
            eng = parent.permission_engine
            ctx.check("the person's own session grant", eng.add_session_allow_rule("Bash(ls:*)"))
            ctx.check("a skill's temporary grant", eng.add_session_allow_rule("Bash(rm:*)", temporary=True))
            runtime = parent.agent_runtime or AgentRuntime(parent=parent)
            spec = AgentSpec(name="worker", description="w", tools=None, body="You work.")
            child, _m = _build_child_session(runtime=runtime, spec=spec, agent_id="w-1", model_override=None,
                                             parent_tool_use_id="t1")
            kept = [r.raw for r in child.permission_engine.allow_rules]
            ctx.check(f"the child keeps the permanent rule, got {kept}", "Bash(ls:*)" in kept)
            ctx.check(f"and not the skill's grant, got {kept}", "Bash(rm:*)" not in kept)
            d = child.permission_engine.decide("Bash", {"command": "rm -rf build"}, None)
            ctx.check(f"the child asks for what the grant allowed the parent, got {d.action}", d.action != "allow")
            eng.clear_temporary_allow_rules()
            ctx.check("the parent's grant ends at the next message", "Bash(rm:*)" not in [r.raw for r in eng.allow_rules]
                      and "Bash(ls:*)" in [r.raw for r in eng.allow_rules])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
