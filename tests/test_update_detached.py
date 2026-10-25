"""tests.test_update_detached -- Halo 3.2.2.0 R3: `/update` installs from a
detached updater after halo has exited (halo_harness/update_detached.py).
The script text is checked as text for both platforms; `spawn()` runs a
real script whose "reinstall" is an `echo`, whose `halo` is this test's own
interpreter (`--version` only) and whose waited-for parent is a short-lived
child of this test; the pid it stops is another fake sleeping child. The
log lands in a scoped state dir; nothing real is installed or stopped.
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from halo_harness import update_detached as UD

test, TESTS = new_registry()


def _kw(**over):
    kw = {"wait_pids": [111, 112], "stop_pids": [222], "reinstall_cmd": "uv tool install --reinstall git+https://x/y@v1 && echo 50%",
          "log": "/home/u/.halo/update.log", "cwd": None, "supervisor_stop_file": None, "restart_supervisor": False,
          "halo": "halo"}
    kw.update(over)
    return kw


@test
def test_the_windows_script_waits_stops_reinstalls_and_logs(ctx: Ctx):
    text = UD.windows_script(**_kw(log=r"C:\Users\u\.halo\update.log", cwd=r"C:\src\halo"))
    ctx.check("cmd.exe line endings", "\r\n" in text and text.startswith("@echo off"))
    ctx.check("waits for each pid with tasklist, in a loop", 'tasklist /FI "PID eq 111"' in text and
              'tasklist /FI "PID eq 112"' in text and "goto wait_111" in text and "ping -n 2 127.0.0.1" in text)
    ctx.check("stops the listed pid by pid", 'taskkill /PID 222 /T /F >> "%LOG%" 2>&1' in text)
    ctx.check("never by image name", "/IM" not in text)
    ctx.check("runs the reinstall (a % doubled for cmd.exe) from the checkout",
              "uv tool install --reinstall git+https://x/y@v1 && echo 50%%" in text and r'cd /d "C:\src\halo"' in text)
    ctx.check("logs everything to update.log", r'set "LOG=C:\Users\u\.halo\update.log"' in text
              and 'call :reinstall >> "%LOG%" 2>&1' in text)
    ctx.check("ends with halo --version into the log", '"halo" --version >> "%LOG%" 2>&1' in text)
    ctx.check("the steps come in order", text.index("wait_111") < text.index("taskkill") < text.index("call :reinstall")
              < text.index("--version"))
    ctx.check("no supervisor step when none ran", "supervise" not in text)
    sup = UD.windows_script(**_kw(supervisor_stop_file=r"C:\h\supervise\stop", restart_supervisor=True))
    ctx.check("a supervisor that ran: its stop file first, `supervise --daemon` after the install",
              r'echo stop> "C:\h\supervise\stop"' in sup and sup.index("supervise\\stop") < sup.index("taskkill")
              and sup.index("call :reinstall") < sup.index('"halo" supervise --daemon'))


@test
def test_the_posix_script_waits_stops_reinstalls_and_logs(ctx: Ctx):
    text = UD.posix_script(**_kw(cwd="/src/halo dir"))
    ctx.check("a POSIX sh script", text.startswith("#!/bin/sh"))
    ctx.check("everything goes to the log", "exec >>/home/u/.halo/update.log 2>&1" in text)
    ctx.check("polls kill -0 for each pid", "while kill -0 111 2>/dev/null" in text and "while kill -0 112" in text)
    ctx.check("stops the listed pid, then hard after 2 s", "kill 222 2>/dev/null" in text and "kill -9 222" in text)
    ctx.check("runs the reinstall from the checkout", "( cd '/src/halo dir' && uv tool install --reinstall" in text)
    ctx.check("then halo --version", "halo --version" in text and text.index("kill 222") < text.index("--version"))
    ctx.check("never the tool venv's python", sys.executable not in text)
    sup = UD.posix_script(**_kw(supervisor_stop_file="/h/supervise/stop", restart_supervisor=True))
    ctx.check("a supervisor that ran is asked to stop, then started again",
              "echo stop > /h/supervise/stop" in sup and "halo supervise --daemon" in sup)


def _wait_for(path: Path, needle: str, within: float = 60.0) -> str:
    deadline = time.time() + within
    text = ""
    while time.time() < deadline:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if needle in text:
            return text
        time.sleep(0.25)
    return text


@test
def test_spawn_waits_for_a_short_lived_parent_and_writes_the_log(ctx: Ctx):
    windows = os.name == "nt"
    if not (shutil.which("cmd.exe") if windows else shutil.which("sh")):
        raise SkipTest("no cmd.exe / sh here")
    state = Path(tempfile.mkdtemp(prefix="r3-detached-"))
    parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.5)"])
    victim = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log = UD.log_path(state)
    try:
        make = UD.windows_script if windows else UD.posix_script
        text = make(wait_pids=[parent.pid], stop_pids=[victim.pid], reinstall_cmd="echo reinstalled-ok",
                    log=str(log), halo=sys.executable)
        path = UD.write_script(text, UD.script_path(state, windows=windows))
        pid = UD.spawn(path, windows=windows, cwd=state)
        ctx.check(f"spawn returns the updater's pid, got {pid}", isinstance(pid, int) and pid > 0)
        parent.wait(timeout=30)
        got = _wait_for(log, "=== done")
        ctx.check(f"the log says the parent exited, then the reinstall ran, got {got!r}",
                  f"(pid {parent.pid}) has exited" in got and "reinstalled-ok" in got
                  and got.index("has exited") < got.index("reinstalled-ok"))
        ctx.check(f"and the version line closes it, got {got!r}", "Python " in got and got.rstrip().endswith("=== done"))
        try:
            victim.wait(timeout=15)
        except subprocess.TimeoutExpired:
            pass
        ctx.check("the listed pid was stopped", victim.poll() is not None)
    finally:
        for p in (parent, victim):
            if p.poll() is None:
                p.kill()
            p.wait(timeout=10)


@test
def test_run_after_exit_writes_the_script_starts_it_and_names_the_log(ctx: Ctx):
    from halo_harness import update as upd
    from halo_harness import update_stop
    state = Path(tempfile.mkdtemp(prefix="r3-after-exit-"))
    started = []
    saved = (UD.reinstall_cmd, UD.spawn, upd.halo_ancestors, update_stop.lingering)
    UD.reinstall_cmd = lambda to=None: ("echo reinstall", {"kind": "uv_tool", "spec": "git+https://x"})
    UD.spawn = lambda path, **kw: started.append(Path(path)) or 4321
    upd.halo_ancestors = lambda **kw: [77]
    update_stop.lingering = lambda state_dir=None: [{"pid": 4242, "what": "studio", "cmd": ["halo", "studio"]}]
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            code = UD.run_after_exit(state_dir=state, resume_hint="halo --continue")
    finally:
        UD.reinstall_cmd, UD.spawn, upd.halo_ancestors, update_stop.lingering = saved
    text = out.getvalue()
    ctx.check(f"exit 0 and one updater started, got {code} {started}", code == 0 and len(started) == 1)
    script = started[0].read_text(encoding="utf-8")
    ctx.check("the script waits for this process and its launcher, and stops the lingering Studio",
              str(os.getpid()) in script and "77" in script and "4242" in script and "echo reinstall" in script)
    ctx.check(f"the TUI's last lines name what it stops and where the log is, got {text!r}",
              "the updater stops Studio (pid 4242): halo studio" in text
              and f"its log: {state / 'update.log'}" in text and "`halo --version` then" in text
              and "`halo --continue` picks the session up again" in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
