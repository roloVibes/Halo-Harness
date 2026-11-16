"""tests.test_lifecycle_fx2_batch01 -- a shell command the Bash tool started ends with Halo (Halo 3.6.0.0, fix package
"lifecycle", pass 2 batch 1).

1. Windows: Git Bash's children (sleep.exe, make, git ...) left Halo's kill-on-close Job object: an MSYS program
   starts its own children with CREATE_BREAKAWAY_FROM_JOB whenever its Job allows breakaway, and Halo's one Job
   allowed it (for a kept spawn of a Halo child). So after Ctrl+C or a hard kill of a halo whose Bash tool was mid-run,
   or whose session had a background Bash job, the command's programs lived on. An ordinary child now joins a Job
   that forbids breakaway; only Halo's own Python children join the one that allows it.
2. macOS (and every POSIX): `ps -E` hides an Apple platform binary's environment (bash, sleep, make, git), so the
   HALO_OWNER marker scan of close() and the reaper never found a shell command. The shell the Bash tool starts (a
   foreground call, a background job, a call moved to the background) is in the ledger while it runs, as `shell`;
   close(), the reaper, `halo ps` and `halo stop` reach it there and end its whole process group.
3. Windows: Halo itself was still running more than 5 s after Ctrl+C with a background Bash job. Each way out is
   checked for the owner's own exit within 5 s as well as for its children.
Every process a test starts uses a scratch home and is ended by pid and start time; nothing is killed by name.
Run: python -m tests.test_lifecycle_fx2_batch01
"""
from __future__ import annotations

import json
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
from tests.test_closing import BOUND_S, WAYS, WIN, _end, _end_tree_we_started, _owner, _same  # noqa: E402

test, TESTS = new_registry()


def _ways(ctx: Ctx, kind: str) -> None:
    for way in WAYS:
        tmp = Path(tempfile.mkdtemp(prefix=f"halo-fx2-{kind}-{way}-"))
        kids: list = []
        try:
            proc, out, ready = _owner(kind, tmp)
            kids = ready["kids"]
            t_end = time.monotonic()
            _end(proc, out, way)
            try:
                _o, err = proc.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                _o, err = proc.communicate(timeout=10)
            took = time.monotonic() - t_end
            t0 = time.monotonic()
            while time.monotonic() - t0 < BOUND_S and any(_same(k["pid"], k["start"]) for k in kids):
                time.sleep(0.05)
            alive = [(k["what"], k["pid"]) for k in kids if _same(k["pid"], k["start"])]
            if alive:  # a pid caught mid-exit reads alive once (bg_run.pid_alive): look again
                time.sleep(0.3)
                alive = [(k["what"], k["pid"]) for k in kids if _same(k["pid"], k["start"])]
            ctx.check(f"{kind}/{way}: nothing the shell started is alive {BOUND_S:.0f} s after Halo went "
                      f"(alive: {alive}; stderr: {err[-300:]!r})", not alive)
            ctx.check(f"{kind}/{way}: Halo itself ended within {BOUND_S:.0f} s, took {took:.1f} s "
                      f"(stderr: {err[-300:]!r})", took < BOUND_S)
            ctx.check(f"{kind}/{way}: the shell is in the ledger as `shell` while it runs, got {ready['ledger']}",
                      len(ready["ledger"]) == 1 and ready["ledger"][0].get("start_time"))
        finally:
            for k in kids:
                _end_tree_we_started(k["pid"], k["start"])
            shutil.rmtree(tmp, ignore_errors=True)


@test
def test_a_foreground_bash_command_ends_with_halo_every_way_out(ctx: Ctx):
    _ways(ctx, "bashfg")


@test
def test_a_background_bash_job_ends_with_halo_every_way_out(ctx: Ctx):
    _ways(ctx, "bashjob")


def _scratch_home():
    home = Path(tempfile.mkdtemp(prefix="halo-fx2-home-"))
    return home, mock.patch.dict(os.environ, {"BRIDGE_TEST_HOME": str(home)})


@test
def test_a_shell_command_is_in_the_ledger_while_it_runs_and_leaves_it_after(ctx: Ctx):
    from halo_harness import children
    from halo_harness.config.paths import git_bash, to_posix
    from halo_harness.tools._proc import run_streamed
    shell = git_bash()
    if shell is None:
        raise SkipTest("no bash here")
    home, env = _scratch_home()
    try:
        with env:
            ledger = to_posix(str(children.registry_path()))
            # fx jb7: the row is written just after the spawn (its start time is one `ps` call on macOS and under
            # HALO_TEST_NO_PROC=1), so a shell whose first act is to read the ledger can be faster than the row:
            # it waits for the row (bounded), as `halo ps` run by a person a moment later finds it
            wait = (f"for i in $(seq 1 100); do grep -q '\"shell\"' '{ledger}' 2>/dev/null && break; sleep 0.1; "
                    f"done; cat '{ledger}'")
            out, code, _t, _a = run_streamed([str(shell), "-lc", wait], cwd=home, env=dict(os.environ),
                                             timeout_s=60)
            rows = json.loads(out[out.index("{"):]).get("children") if "{" in out else []
            mine = [r for r in rows or [] if r.get("what") == "shell"]
            ctx.check(f"the running shell reads itself in the ledger as `shell` with a start time and this owner: {rows}",
                      code == 0 and len(mine) == 1 and mine[0].get("start_time") and mine[0].get("owner_pid") == os.getpid()
                      and mine[0].get("cmd", [""])[0] == str(shell))
            left = [r for r in children.load() if r.get("what") == "shell"]
            ctx.check(f"the ledger has no shell left once the command ended: {left}", not left)
            from halo_harness.agent.jobs import JobRegistry
            reg = JobRegistry(None)
            rec, err = reg.start_background("sleep 30", description="s", cwd=home, env=dict(os.environ),
                                            shell_path=str(shell))
            ctx.check(f"a background job started: {err}", rec is not None)
            got = [r for r in children.load() if r.get("what") == "shell"]
            ctx.check(f"a background job's shell is in the ledger: {got}", [r["pid"] for r in got] == [rec.proc.pid])
            reg.kill_all()
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and [r for r in children.load() if r.get("what") == "shell"]:
                time.sleep(0.1)
            ctx.check("a killed background job leaves the ledger",
                      not [r for r in children.load() if r.get("what") == "shell"])
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _sleeping_job(home: Path, shell) -> tuple:
    """A background job whose shell waits on `sleep 300`: (record, sleep pid, sleep start)."""
    from halo_harness import children
    from halo_harness.agent.jobs import JobRegistry
    from halo_harness.config.paths import to_posix
    pidfile = home / f"sleep-{time.monotonic_ns()}.pid"
    cmd = (f"sleep 300 & p=$!; {{ cat /proc/$p/winpid 2>/dev/null || echo $p; }} > "
           f"'{to_posix(str(pidfile))}'; wait $p")
    reg = JobRegistry(None)
    rec, _err = reg.start_background(cmd, description="s", cwd=home, env=dict(os.environ), shell_path=str(shell))
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            spid = int(pidfile.read_text(encoding="utf-8").split()[0])
            return reg, rec, spid, children.start_time(spid)
        except (OSError, ValueError, IndexError):
            time.sleep(0.05)
    raise AssertionError("the shell never wrote its sleep's pid")


@test
def test_stopping_a_shell_entry_ends_everything_it_started_without_the_marker_scan(ctx: Ctx):
    """What close() does with a `shell` entry (and, on POSIX, the reaper or `halo stop` from another process) where
    the marker cannot be read (macOS): the shell goes with every program it started, at once."""
    from halo_harness import children, closing
    from halo_harness.config.paths import git_bash
    from halo_harness.tools import _proc
    shell = git_bash()
    if shell is None:
        raise SkipTest("no bash here")
    home, env = _scratch_home()
    procs = []
    try:
        with env, mock.patch.object(closing, "marker_pids", lambda *a, **k: {}):
            ways = [("this process's close()", False)] + ([] if WIN else [("another process's stop", True)])
            for label, elsewhere in ways:
                _reg, rec, spid, sstart = _sleeping_job(home, shell)
                procs += [(rec.proc.pid, children.start_time(rec.proc.pid)), (spid, sstart)]
                rows = [r for r in children.load() if r.get("what") == "shell" and r["pid"] == rec.proc.pid]
                t0 = time.monotonic()
                with mock.patch.dict(_proc._SHELLS, {}, clear=True) if elsewhere else mock.patch.dict({}):
                    closing.stop_entries(rows)
                took = time.monotonic() - t0
                gone_deadline = time.monotonic() + BOUND_S
                while time.monotonic() < gone_deadline and _same(spid, sstart):
                    time.sleep(0.05)
                ctx.check(f"{label}: the shell's own child (pid {spid}) ended with its shell", not _same(spid, sstart))
                ctx.check(f"{label}: a shell has no polite stop to wait out: stop took {took:.1f} s", took < 2.5)
    finally:
        for pid, start in procs:
            _end_tree_we_started(pid, start)
        shutil.rmtree(home, ignore_errors=True)


@test
def test_task_stop_ends_a_background_job_with_everything_it_started(ctx: Ctx):
    """TaskStop (JobRegistry.kill): Windows used to end bash.exe alone (taskkill /T never reaches a Git Bash
    program's own children) and the job's `sleep` ran on, holding its output pipe, until Halo exited."""
    from halo_harness.config.paths import git_bash
    shell = git_bash()
    if shell is None:
        raise SkipTest("no bash here")
    home, env = _scratch_home()
    procs = []
    try:
        with env:
            reg, rec, spid, sstart = _sleeping_job(home, shell)
            procs = [(spid, sstart)]
            t0 = time.monotonic()
            ok, _msg = reg.kill(rec.job_id)
            took = time.monotonic() - t0
            gone_deadline = time.monotonic() + BOUND_S
            while time.monotonic() < gone_deadline and _same(spid, sstart):
                time.sleep(0.05)
            ctx.check(f"TaskStop ended the job's sleep (pid {spid})", ok and not _same(spid, sstart))
            ctx.check(f"TaskStop took {took:.1f} s", took < 2.5)
    finally:
        for pid, start in procs:
            _end_tree_we_started(pid, start)
        shutil.rmtree(home, ignore_errors=True)


@test
def test_halo_ps_names_a_shell_command(ctx: Ctx):
    from halo_harness import children
    ctx.check(f"`halo ps` says shell command, got {children.label('shell')!r}", children.label("shell") == "shell command")


@test
def test_windows_only_halos_own_python_children_join_the_job_that_allows_breakaway(ctx: Ctx):
    from halo_harness import closing
    from halo_harness.selfexec import python_argv
    ctx.check("Halo's own Python child may leave (it may start a kept thing)",
              closing.may_break_away([*python_argv(), "studio"]))
    ctx.check("Halo's console script child may leave", closing.may_break_away([r"C:\x\Scripts\halo.exe", "update"]))
    for argv in (["bash", "-lc", "sleep 1"], [r"C:\Program Files\Git\bin\bash.exe", "-lc", "make"],
                 [sys.executable, "server.py"], ["npx", "-y", "some-mcp"], "bash -lc x", None):
        ctx.check(f"an ordinary child stays in the Job that forbids breakaway: {argv!r}", not closing.may_break_away(argv))
    if not WIN:
        return
    ctx.check("two different Jobs", closing._job() and closing._job(strict=True) and closing._job() != closing._job(strict=True))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
