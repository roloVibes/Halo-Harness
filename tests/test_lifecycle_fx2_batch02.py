"""tests.test_lifecycle_fx2_batch02 -- macOS liveness looks without a `ps` process, and the quit path's stop of a pid
whose start time is unknown (Halo 3.6.0.0, fix package "lifecycle", pass 2 batch 2).

1. macOS (no /proc): a liveness look (is this pid a zombie?) reads the kernel's own record of the pid (sysctl
   KERN_PROC_PID) and starts no `ps`. Studio's session rows, the closing home watch, the local servers and the
   registry poll it several times a second; each look started a `ps` (up to 5 s) before. A record this reader does not
   understand, or no record at all, still asks `ps`.
2. The quit path (children_stop.stop_entry, used by Ctrl+Q, the controller's quit, headless and Studio sessions) never
   signals a pid whose start time it cannot prove: a `bg` entry and an ordinary one, both with no start time.
Every process a test starts is its own and is ended by its own handle; nothing is killed by name.
Run: python -m tests.test_lifecycle_fx2_batch02
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MAC = sys.platform == "darwin"


def _record(pid: int, stat: int) -> bytes:
    """A struct kinfo_proc as macOS's sysctl returns it (648 bytes): kp_proc.p_stat at 36, kp_proc.p_pid at 40."""
    raw = bytearray(648)
    raw[36] = stat
    raw[40:44] = int(pid).to_bytes(4, sys.byteorder, signed=True)
    return bytes(raw)


class _Ps:
    def __init__(self):
        self.runs = 0

    def __call__(self, argv, **kw):
        self.runs += 1
        return subprocess.CompletedProcess(argv, 0, "S Sun Nov 15 10:00:00 2026\n", "")


@test
def test_macos_a_liveness_look_reads_the_kernel_record_and_starts_no_ps(ctx: Ctx):
    from halo_harness import bg_run
    pid = 4545
    for label, raw, zombie, runs in (("a sleeping process", _record(pid, 3), False, 0),
                                     ("a zombie", _record(pid, 5), True, 0),
                                     ("no such process", b"", False, 0),
                                     ("a record for another pid (a layout this reader does not know)",
                                      _record(pid + 1, 5), False, 1),
                                     ("no record readable here", None, False, 1)):
        ps = _Ps()
        getattr(bg_run, "_PS_SEEN", {}).clear()
        with mock.patch.object(bg_run, "_KINFO_READ", lambda p, raw=raw: raw, create=True), \
                mock.patch.object(bg_run.subprocess, "run", ps):
            got = [bg_run._ps_zombie(pid) for _ in range(10)]
        getattr(bg_run, "_PS_SEEN", {}).clear()
        ctx.check(f"{label}: zombie={zombie} on every look, got {set(got)}", set(got) == {zombie})
        ctx.check(f"{label}: {runs} `ps` for ten looks, got {ps.runs}", ps.runs == runs)
    reader = getattr(bg_run, "_KINFO_READ", "missing")
    ctx.check(f"the kernel reader is on for macOS only, got {reader!r}",
              (reader is getattr(bg_run, "_darwin_kinfo", None)) if MAC else reader is None)


@test
def test_macos_the_kernel_record_tells_a_live_process_from_a_zombie(ctx: Ctx):
    """The real sysctl on a Mac: the record's layout (p_pid, p_stat) is the one the reader expects."""
    if not MAC:
        raise SkipTest("macOS only (not run on the PC)")
    from halo_harness import bg_run
    live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], stdin=subprocess.DEVNULL)
    dead = subprocess.Popen([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL)
    try:
        deadline = time.time() + 10
        while time.time() < deadline and bg_run._kinfo_zombie(dead.pid) is not True:
            time.sleep(0.1)  # not reaped: Popen waits only when asked
        raw = bg_run._darwin_kinfo(live.pid)
        ctx.check(f"a record of {len(raw or b'')} bytes names the live pid",
                  bool(raw) and int.from_bytes(raw[40:44], sys.byteorder, signed=True) == live.pid)
        ctx.check("the live process is no zombie", bg_run._kinfo_zombie(live.pid) is False)
        ctx.check("the exited, unreaped one is a zombie", bg_run._kinfo_zombie(dead.pid) is True)
        ps = subprocess.run(["ps", "-o", "stat=", "-p", str(dead.pid)], capture_output=True, text=True, timeout=10)
        ctx.check(f"and ps agrees, got {ps.stdout!r}", ps.stdout.strip().upper().startswith("Z"))
        dead.wait(10)
        ctx.check("a reaped pid has no record", bg_run._darwin_kinfo(dead.pid) == b"")
        ctx.check("pid_alive: the live one runs, the reaped one does not",
                  bg_run.pid_alive(live.pid) and not bg_run.pid_alive(dead.pid))
    finally:
        live.kill()
        live.wait(10)
        if dead.poll() is None:
            dead.kill()
        dead.wait(10)


@test
def test_the_quit_path_never_stops_a_pid_whose_start_time_is_unknown(ctx: Ctx):
    from halo_harness import children_stop
    state = Path(tempfile.mkdtemp(prefix="lc-fx2-b2-"))
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for what in ("bg", "halo"):
            res = children_stop.stop_entry({"pid": proc.pid, "what": what, "cmd": ["sleeper"]}, state_dir=state,
                                           timeout=1.0)
            time.sleep(0.3)
            ctx.check(f"a `{what}` entry with no start time: nothing signalled (said {res['ok']})",
                      proc.poll() is None)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(10)
        shutil.rmtree(state, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
