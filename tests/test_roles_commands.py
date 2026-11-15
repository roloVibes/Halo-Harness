"""tests.test_roles_commands -- Halo 2.0.2 (W7 round 1, brief A.4/A.5):
`/role <name> <model> [effort]` and `/roles set|templates|save|load|new|
show` (`commands/builtins.py`). Split out of tests/test_roles_resolve.py to
keep each file under the house "<= 250 lines per Write" rule.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _fake_facade_with_session(*, roles=None, cli_roles=None, state_dir=None):
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.commands.builtins import HeadlessFacade

    roles = roles if roles is not None else {}
    runtime = SimpleNamespace(role_table=roles, cli_role_overrides=(cli_roles or {}), routes={})
    session = SimpleNamespace(model_ref=parse_model_ref("or:vendor/parent"), model_profile=ModelProfile(),
                               state_dir=state_dir or Path(tempfile.mkdtemp(prefix="roles-cmd-")),
                               agent_runtime=runtime, roles=roles)
    return HeadlessFacade(cwd=Path(tempfile.mkdtemp(prefix="roles-cmd-cwd-")), session=session), session


@test
def test_role_command_sets_a_known_role_live(ctx: Ctx):
    """2.0.2 review finding 23: `/role` must land in `cli_role_overrides`
    (the rung `resolve_agent_model` treats as winning even over an agent
    file's own `model:`), never the plain `role_table` -- so this checks
    `agent_runtime.cli_role_overrides`, not `session.roles`."""
    from halo_harness.commands.builtins import _cmd_role
    facade, session = _fake_facade_with_session(roles={})
    out = _cmd_role("coder or:vendor/newcoder high", facade)
    ctx.check(f"confirms the set, got {out!r}", "coder" in out and "newcoder" in out)
    overrides = session.agent_runtime.cli_role_overrides
    ctx.check(f"landed in cli_role_overrides, got {overrides}",
              overrides.get("coder") == {"model": "or:vendor/newcoder", "effort": "high"})
    ctx.check(f"the plain role_table was left alone, got {session.roles}", session.roles == {})


@test
def test_role_command_no_effort_sets_a_bare_string(ctx: Ctx):
    from halo_harness.commands.builtins import _cmd_role
    facade, session = _fake_facade_with_session(roles={})
    _cmd_role("researcher or:vendor/newresearcher", facade)
    overrides = session.agent_runtime.cli_role_overrides
    ctx.check(f"bare model, no effort, got {overrides}", overrides.get("researcher") == "or:vendor/newresearcher")


@test
def test_role_command_unknown_name_lists_known_names(ctx: Ctx):
    from halo_harness.commands.builtins import _cmd_role
    facade, _session = _fake_facade_with_session(roles={})
    out = _cmd_role("not_a_role or:vendor/x", facade)
    ctx.check(f"names the bad role and lists known ones, got {out!r}", "not_a_role" in out and "coder" in out)


@test
def test_role_command_no_session_is_a_clean_message(ctx: Ctx):
    from halo_harness.commands.builtins import HeadlessFacade, _cmd_role
    facade = HeadlessFacade(cwd=Path(tempfile.mkdtemp()))
    out = _cmd_role("coder or:vendor/x", facade)
    ctx.check(f"no traceback, a plain message, got {out!r}", "session" in out.lower())


@test
def test_role_command_rejects_bad_model_and_bad_effort(ctx: Ctx):
    """2.0.2 review finding 23: the model/effort strings were never
    validated at all before this -- a typo silently became "this role's
    live override" with no error until the next sub-agent spawn failed."""
    from halo_harness.commands.builtins import _cmd_role
    facade, session = _fake_facade_with_session(roles={})
    out = _cmd_role("coder not-a-real-model-ref", facade)
    ctx.check(f"bad model is rejected, got {out!r}", "not-a-real-model-ref" in out)
    ctx.check("nothing was written", not session.agent_runtime.cli_role_overrides)

    out2 = _cmd_role("coder or:vendor/x ultra-high", facade)
    ctx.check(f"bad effort is rejected, got {out2!r}", "ultra-high" in out2 and "high" in out2)
    ctx.check("nothing was written", not session.agent_runtime.cli_role_overrides)


@test
def test_role_command_override_wins_over_frontmatter_model(ctx: Ctx):
    """2.0.2 review finding 23 pin: `/role` used to write into the plain
    `role_table` rung, which `resolve_agent_model` ranks BELOW an agent
    file's own `model:` -- so `/role coder X` reported success but a
    coder-role agent with its own `model:` set kept using ITS model, not
    X. `cli_role_overrides` is the rung that chain says wins regardless."""
    from halo_harness.commands.builtins import _cmd_role
    from halo_harness.config.agents_md import resolve_agent_model
    facade, session = _fake_facade_with_session(roles={})
    out = _cmd_role("coder or:vendor/overridden", facade)
    ctx.check(f"confirms the set, got {out!r}", "overridden" in out)
    runtime = session.agent_runtime
    ref, _profile = resolve_agent_model(
        frontmatter_model="or:vendor/agent-files-own-model", role_name="coder",
        role_table=runtime.role_table, cli_role_overrides=runtime.cli_role_overrides,
        parent_ref=session.model_ref, parent_profile=session.model_profile, state_dir=session.state_dir,
        routes=runtime.routes,
    )
    ctx.check(f"the live /role override wins over the agent file's own model:, got {ref.raw}",
              ref.raw == "or:vendor/overridden")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
