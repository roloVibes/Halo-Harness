"""tests.test_review3_s3 -- pins for the 3.0.1.0 review fix pass, round
S-subagents-teams (part 3): review item 52 (item 53, the org budget
tracker's lock, went with Org in 3.1.4.0).

  * 52  /roles off then /roles on keeps the session's merged team roles
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_review3_s import patched

test, TESTS = new_registry()


# ---- 52: /roles off then on keeps the session's merged team roles -------------


@test
def test_52_roles_off_then_on_restores_the_team_roles(ctx: Ctx):
    from halo_harness import roles as roles_mod
    from halo_harness.agent.loop import Session
    enabled = [True]
    persisted = {"coder": "or:vendor/coder"}
    table = {"coder": "or:vendor/coder", "reviewer": "or:team/reviewer", "release": "or:team/release"}
    fake = SimpleNamespace(agent_runtime=SimpleNamespace(role_table=table), tool_env={}, settings=None,
                           model_ref=SimpleNamespace(provider="openrouter"), _role_table_base=dict(persisted))
    with patched(roles_mod, roles_mode_enabled=lambda: enabled[0],
                 resolve_role_table=lambda provider=None, subagent_model=None: dict(persisted) if enabled[0] else {}):
        enabled[0] = False
        Session.refresh_role_table(fake)
        ctx.check(f"roles off empties the live table, got {table}", table == {})
        enabled[0] = True
        Session.refresh_role_table(fake)
        ctx.check(f"roles on brings the team's roles back, got {table}",
                  table == {"coder": "or:vendor/coder", "reviewer": "or:team/reviewer", "release": "or:team/release"})
        persisted["coder"] = "or:vendor/coder-2"
        Session.refresh_role_table(fake)
        ctx.check(f"a changed persisted layer still flows through, got {table.get('coder')}",
                  table.get("coder") == "or:vendor/coder-2" and table.get("reviewer") == "or:team/reviewer")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
