"""tests.test_pid_alive -- Halo 3.4.1.1 (the 3.4.1.0 R6 open item): "is this pid alive" never reads a slow answer as
dead. bg_run.pid_alive (and children.pid_running, which goes through it) asks Windows for the process's own exit code
first (halo_harness/process_alive.py, no process spawned); `tasklist` is the fallback only when that cannot tell, and
one slower than its timeout is unknown, so alive -- a loaded runner once pruned a live session that way.
Run: python -m tests.test_pid_alive
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


@test
def test_the_exit_code_says_alive_and_gone(ctx: Ctx):
    from halo_harness import bg_run, children
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=30)
    ctx.check("this process is alive", bg_run.pid_alive(os.getpid()) and children.pid_running(os.getpid()))
    ctx.check(f"a child that exited is not (pid {child.pid})", not bg_run.pid_alive(child.pid) and not children.pid_running(child.pid))
    if os.name == "nt":
        from halo_harness.process_alive import win_alive
        ctx.check("Windows answers from the exit code, no tasklist", win_alive(os.getpid()) is True and win_alive(child.pid) is False)


@test
def test_a_tasklist_that_times_out_is_not_a_dead_pid(ctx: Ctx):
    if os.name != "nt":
        raise SkipTest("Windows only: POSIX asks with a signal, nothing that can time out")
    from halo_harness import bg_run, process_alive
    saved_win, saved_run = process_alive.win_alive, subprocess.run

    def slow(*_a, **_k):
        raise subprocess.TimeoutExpired("tasklist", 5)
    try:
        process_alive.win_alive = lambda pid: None  # the API could not tell: the fallback runs
        subprocess.run = slow
        ctx.check("a tasklist slower than its timeout: unknown, so alive", bg_run.pid_alive(4242) is True)
    finally:
        process_alive.win_alive, subprocess.run = saved_win, saved_run


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
