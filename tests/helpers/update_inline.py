"""tests.helpers.update_inline -- Halo 3.6.0.0 R13: `halo update` hands the install to a standalone updater
(halo_harness/update_runner.py, started outside the tool environment by update_plan.launch). A test never starts
that process: it sets `update_cli.launch` (or `update_detached.launch`) to `inline`, which runs the same plan in this
process with `halo_harness.update.run` -- the seam every update test already fakes -- as the runner's command
runner, no pid alive, no real sleep.

    inline(plan) -> exit code       plans(): the plans it was given
"""
from __future__ import annotations

PLANS: list = []


def inline(plan: dict, **_kw) -> int:
    from halo_harness import update as upd
    from halo_harness.update_runner import run_plan
    PLANS.append(plan)
    code, _result = run_plan(plan, run_fn=lambda cmd, **kw: upd.run(cmd, **kw), alive_fn=lambda pid: False,
                             kill_fn=lambda pid: None, sleep_fn=lambda s: None)
    return code


def plans() -> list:
    return PLANS
