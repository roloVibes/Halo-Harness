"""tests.test_codex_subprocess_timeout -- pass-B finding 14 (major):
`run_bounded_codex_subprocess`'s own timeout watchdog (halo_harness.agent.
codex_process) must kill the WHOLE process tree on a timeout -- not just
the one process handle a bare `subprocess.run(..., timeout=...)` would
reach. Reproduces the exact shape the finding verified live (a parent
process that spawns and waits on its own child, the same relationship an
npm `.cmd` shim launching `node`, which in turn launches the native codex
binary, has): a 2-second timeout against a parent whose child sleeps 120
seconds must return close to 2 seconds, not 120, and leave neither process
behind.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

# A parent that spawns ONE child and blocks on it (`child.wait()`) before
# ever exiting itself -- mirrors an npm `.cmd` shim (parent) running `node`
# (child) running the real codex binary (this script only needs one more
# level than that to prove a tree-kill reaches past the immediate handle).
# The child's own pid is written to `marker` right after Popen returns
# (near-instant), well before the parent's 2-second timeout below fires, so
# the test can confirm it genuinely started before checking it is gone.
_PARENT_SCRIPT = (
    "import subprocess, sys\n"
    "marker = sys.argv[1]\n"
    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
    "with open(marker, 'w') as f:\n"
    "    f.write(str(child.pid))\n"
    "child.wait()\n"
)


def _pid_alive(pid: int) -> bool:
    """Cross-platform, stdlib-only liveness check (no psutil). Windows has
    no `os.kill(pid, 0)` no-op probe, so `tasklist` (a standard OS command,
    the same family `taskkill` already belongs to) stands in for it."""
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                  capture_output=True, text=True, timeout=10).stdout
        except Exception:
            return False
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True  # exists but not ours to signal -- treat conservatively as alive
    return True


@test
def test_timeout_kills_the_whole_tree_not_just_the_top_process(ctx: Ctx):
    from halo_harness.agent.codex_process import run_bounded_codex_subprocess

    scratch = Path(tempfile.mkdtemp(prefix="cx-tree-kill-"))
    parent_script = scratch / "parent.py"
    parent_script.write_text(_PARENT_SCRIPT, encoding="utf-8")
    marker = scratch / "child-pid.txt"

    argv = [sys.executable, str(parent_script), str(marker)]
    start = time.monotonic()
    try:
        run_bounded_codex_subprocess(argv, timeout=2)
        ctx.check("must raise TimeoutExpired", False)
    except subprocess.TimeoutExpired:
        pass
    elapsed = time.monotonic() - start
    ctx.check(f"returned close to the 2s timeout, not the child's 120s sleep, got {elapsed:.1f}s", elapsed < 20)

    # The marker is written near-instantly (well before any real timeout
    # could fire) -- if this is missing, the test proved nothing.
    ctx.check(f"the child's own pid marker was written (it really did start), got exists={marker.exists()}",
              marker.exists())
    child_pid = int(marker.read_text(encoding="utf-8").strip())

    # poll returns non-None: the TOP-level process is fully reaped, no
    # zombie -- `run_bounded_codex_subprocess` itself already proved this
    # by returning/raising at all (a zombie top process would still have
    # let `communicate()`'s own internal `wait()` complete once killed);
    # this is the second half the brief's own phrasing asks for: the
    # GRANDCHILD -- never directly held by `run_bounded_codex_subprocess`
    # at all -- is ALSO gone, not merely orphaned and still running.
    deadline = time.monotonic() + 10
    alive = _pid_alive(child_pid)
    while time.monotonic() < deadline and alive:
        time.sleep(0.2)
        alive = _pid_alive(child_pid)
    ctx.check(f"no child left behind: grandchild pid {child_pid} is gone", not alive)


@test
def test_a_quick_process_is_unaffected(ctx: Ctx):
    """Sanity check: the watchdog path is a timeout-only branch -- an
    ordinary quick command still returns normally with its real output."""
    from halo_harness.agent.codex_process import run_bounded_codex_subprocess
    proc = run_bounded_codex_subprocess([sys.executable, "-c", "print('hi')"], timeout=10)
    ctx.check(f"exit 0, got {proc.returncode}", proc.returncode == 0)
    ctx.check(f"real stdout captured, got {proc.stdout!r}", "hi" in proc.stdout)


@test
def test_missing_binary_raises_oserror_not_timeout(ctx: Ctx):
    from halo_harness.agent.codex_process import run_bounded_codex_subprocess
    try:
        run_bounded_codex_subprocess(["this-binary-does-not-exist-anywhere-12345"], timeout=5)
        ctx.check("must raise OSError", False)
    except OSError:
        pass


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
