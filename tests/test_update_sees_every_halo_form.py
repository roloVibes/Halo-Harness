"""tests.test_update_sees_every_halo_form -- 3.6.0.0 fix package update-install, pass 2: `halo update` sees every
process of this install that runs on its interpreter, in each form Halo starts or writes it.

`update.halo_what` read `-m halo_harness`, its bootstrap and a `halo` launcher only. So these were "not halo": the
LAN host from its installed unit (`persisted_argv("halo_harness.cli") host serve --foreground`, and 3.5's
`-m halo_harness.cli host serve --foreground`), any other `-m halo_harness.<module>` (the media server), and a
script of the package run by path (a model server's home watch, `python -I .../closing_home_watch.py`). The update
neither named nor stopped them: on Windows their python.exe holds the environment the reinstall replaces; on macOS and
Linux the host kept running the old code. The host is now its own kind ("host") and is stopped through its own stop
file, a clean exit its service unit does not restart, before the update falls back to ending it.

The shapes are fed as Windows' command line (`subprocess.list2cmdline`) and as a POSIX `ps -eo args` line."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from halo_harness import children as C
from halo_harness import selfexec
from halo_harness import update as upd
from halo_harness import update_stop as US

test, TESTS = new_registry()

PY = "/usr/lib/python3.10/bin/python3.10"
WPY = r"C:\Program Files\Python310\python.exe"
PKG = Path(upd.__file__).resolve().parent


def _shapes(argv: list) -> "list[tuple[str, str]]":
    head = [WPY] if argv[0] == PY else [r"C:\Users\u\.local\bin\halo.exe"]
    return [("windows", subprocess.list2cmdline(head + argv[1:])), ("ps", " ".join(argv))]


@test
def test_the_host_in_every_form_is_the_host(ctx: Ctx):
    cases = [
        selfexec.persisted_argv("halo_harness.cli", python=PY) + ["host", "serve", "--foreground"],  # 3.6 unit
        [PY, "-m", "halo_harness.cli", "host", "serve", "--foreground"],  # the unit 3.5.0.1 wrote
        [PY, "-P", "-m", "halo_harness", "host", "serve", "--foreground", "--port", "7311"],
        ["halo", "host", "serve", "--foreground"],
    ]
    for argv in cases:
        for label, line in _shapes(argv):
            got = upd.halo_what(line)
            ctx.check(f"{label}: {line[:90]!r} -> host, got {got}", got == "host")


@test
def test_other_modules_of_the_package_are_halo(ctx: Ctx):
    cases = [
        ([PY, "-m", "halo_harness.media.comfy_server", "--port", "0"], "halo"),
        ([PY, "-m", "halo_harness.cli", "studio"], "studio"),
        (selfexec.persisted_argv("halo_harness.cli", python=PY) + ["supervise"], "supervisor"),
        (selfexec.persisted_argv(python=PY) + ["supervise"], "supervisor"),  # the logon unit without halo on PATH
        ([PY, "-c", selfexec.BOOT.format(module="halo_harness.media.comfy_server")], "halo"),
    ]
    for argv, want in cases:
        for label, line in _shapes(argv):
            got = upd.halo_what(line)
            ctx.check(f"{label}: {line[:90]!r} -> {want}, got {got}", got == want)


@test
def test_a_script_of_this_package_run_by_path_is_halo(ctx: Ctx):
    watch = str(PKG / "closing_home_watch.py")
    argv = [PY, "-I", watch, "/home/u/.halo", "4242", "x", "4000", "y", str(PKG.parent)]
    for label, line in _shapes(argv):
        got = upd.halo_what(line)
        ctx.check(f"{label}: the home watch is halo, got {got}", got == "halo")
    for line in [f"{PY} -I /tmp/closing_home_watch.py a b", f"{PY} {PKG.parent / 'notes.py'}",
                 f"{PY} -m halo_harnessX studio", f"{PY} -m other.halo_harness studio"]:
        ctx.check(f"not halo: {line!r}, got {upd.halo_what(line)}", upd.halo_what(line) is None)


@test
def test_the_host_is_named_with_its_own_stop_command(ctx: Ctx):
    entry = {"pid": 4242, "what": "host", "cmd": ["python", "-m", "halo_harness.cli", "host", "serve"]}
    ctx.check(f"stop command, got {US.stop_command(entry)!r}", US.stop_command(entry) == "halo host stop")
    ctx.check(f"label, got {US.describe(entry)!r}", US.describe(entry).startswith("LAN host (pid 4242)"))


@test
def test_the_host_is_stopped_by_its_stop_file_a_clean_exit(ctx: Ctx):
    """A stand-in host that leaves with code 0 when `<home>/host/stop` appears. Ended by a signal or
    TerminateProcess instead, its unit (Restart=on-failure, KeepAlive SuccessfulExit=false, RestartOnFailure) starts
    it again in the middle of the install."""
    with tempfile.TemporaryDirectory() as home:
        stop = Path(home) / "host" / "stop"
        code = ("import os, sys, time\n"
                f"p = {str(stop)!r}\n"
                "end = time.time() + 30\n"
                "while time.time() < end:\n"
                "    if os.path.exists(p): sys.exit(0)\n"
                "    time.sleep(0.05)\n"
                "sys.exit(3)\n")
        proc = subprocess.Popen([sys.executable, "-I", "-c", code])
        try:
            time.sleep(0.3)
            entry = {"pid": proc.pid, "start_time": C.start_time(proc.pid), "what": "host",
                     "cmd": ["python", "-m", "halo_harness.cli", "host", "serve"], "source": "scan"}
            result = US._stop(entry, state_dir=home, timeout=10.0)
            rc = proc.wait(timeout=15)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
        ctx.check(f"reported stopped, got {result}", result.get("ok") is True and result.get("what") == "host")
        ctx.check(f"a clean exit through the stop file (code 0), got {rc}", rc == 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
