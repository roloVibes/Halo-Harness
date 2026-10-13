"""tests.test_review3_s3 -- pins for the 3.0.1.0 review fix pass, round
S-subagents-teams (part 3): review items 52 and 53.

  * 52  /roles off then /roles on keeps the session's merged team roles
  * 53  OrgBudgetTracker.record_spend never loses per-position spend
"""
from __future__ import annotations

import sys
import threading
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


# ---- 53: OrgBudgetTracker.record_spend under one lock ------------------------


@test
def test_53_record_spend_updates_every_counter_under_the_lock(ctx: Ctx):
    from halo_harness.orgs import OrgBudgetTracker
    tracker = OrgBudgetTracker(org_name="o", org_budget_usd=1000.0, position_budgets={"Worker": 50.0})
    unlocked = []

    class _Guarded(dict):
        def __setitem__(self, k, v):
            if not tracker._lock.locked():
                unlocked.append(k)
            super().__setitem__(k, v)

    tracker.spent_by_position = _Guarded()
    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        def work():
            for _ in range(5000):
                tracker.record_spend("Worker", 0.001, 0.0)
        threads = [threading.Thread(target=work) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(old_interval)
    ctx.check(f"per-position spend is written only under the lock, unlocked writes: {len(unlocked)}", not unlocked)
    ctx.check(f"no spend is lost, got {tracker.spent_by_position['Worker']:.6f} vs {tracker.org_spent_usd:.6f}",
              abs(tracker.spent_by_position["Worker"] - 20.0) < 1e-6 and abs(tracker.org_spent_usd - 20.0) < 1e-6)
    note = tracker.record_spend("Worker", 30.0, 0.0)
    ctx.check(f"the position stop still trips, got {note!r}",
              "Worker" in tracker.stopped_positions and note and "reached" in note)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
