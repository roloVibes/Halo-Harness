"""tests.test_update_halo_what_bootstrap -- 3.6.0.0 fix package update-install: `halo update` recognises Halo's own
children started in the one-line bootstrap shape. R10 starts them with `selfexec.python_argv`, which on Python 3.10
(no `-P`) is `python [-u] -c <bootstrap> <args>`, and `selfexec.persisted_argv` (a unit or task written to a file)
is that shape on every Python. `update.halo_what` read only `-m halo_harness` or a `halo` launcher, so on 3.10 a
Studio, the supervisor, a Studio-started session and a background run were "not halo": the update neither named nor
stopped them, and a Studio that opened this halo was no longer its opener.

The shapes are fed as Windows' command line (`subprocess.list2cmdline`, the bootstrap one quoted token) and as a
POSIX `ps -eo args` line (the argv joined by spaces, the bootstrap split into words), on every platform."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from halo_harness import selfexec
from halo_harness import update as upd

test, TESTS = new_registry()

PY = "/usr/lib/python3.10/bin/python3.10"
WPY = r"C:\Program Files\Python310\python.exe"


def _boot(module: str = "halo_harness") -> str:
    return selfexec.BOOT.format(module=module)


def _shapes(argv: list) -> "list[tuple[str, str]]":
    """(label, command line) as Windows and as `ps` show `argv`."""
    win = [WPY] + argv[1:]
    return [("windows", subprocess.list2cmdline(win)), ("ps", " ".join(argv))]


@test
def test_the_bootstrap_shape_is_read_as_halo(ctx: Ctx):
    cases = [
        ([PY, "-u", "-c", _boot(), "studio", "--port", "0"], "studio"),
        ([PY, "-c", _boot(), "supervise"], "supervisor"),
        ([PY, "-u", "-c", _boot(), "--headless", "--session-for", "studio"], "halo"),
        ([PY, "-c", _boot()], "halo"),
        ([PY, "-u", "-c", _boot("halo_harness._bg_wrapper"), "abc123"], "bg"),
    ]
    for argv, want in cases:
        for label, line in _shapes(argv):
            got = upd.halo_what(line)
            ctx.check(f"{label}: {argv[2:4]!r}.. {argv[4:5]} -> {want}, got {got}", got == want)


@test
def test_python_argv_on_every_version_is_halo(ctx: Ctx):
    """What R10's own helpers produce, on this Python and as 3.10 makes it (`persisted_argv` is the 3.10 shape)."""
    for argv in (selfexec.python_argv(unbuffered=True, python=PY) + ["studio"],
                 selfexec.persisted_argv(python=PY) + ["studio"]):
        for label, line in _shapes(argv):
            ctx.check(f"{label}: {argv[1:3]} studio is studio, got {upd.halo_what(line)}", upd.halo_what(line) == "studio")


@test
def test_other_code_after_c_is_not_halo(ctx: Ctx):
    for line in [f"{PY} -c print('halo')",
                 f"{PY} -c import runpy; runpy.run_module('other_pkg', run_name='__main__') studio",
                 f"{PY} -c import halo_harness studio",
                 f"{PY} -c",
                 f"{PY} notes.py -c run_module('halo_harness')"]:
        ctx.check(f"not halo: {line[len(PY):]!r}, got {upd.halo_what(line)}", upd.halo_what(line) is None)


@test
def test_a_studio_in_the_bootstrap_shape_is_this_halos_opener(ctx: Ctx):
    me = os.getpid()
    studio_line = subprocess.list2cmdline([WPY, "-u", "-c", _boot(), "studio"])
    rows = [(4000, 1, studio_line), (me, 4000, subprocess.list2cmdline([WPY, "-c", _boot(), "-p", "hi"]))]

    class _R:
        stdout = ""

    def fake_run(cmd, **kw):
        import json
        r = _R()
        r.stdout = json.dumps([{"ProcessId": p, "ParentProcessId": pp, "CommandLine": c} for p, pp, c in rows])
        return r

    old = upd.list_processes
    try:
        upd.list_processes = lambda run_fn=None, windows=None: old(run_fn=fake_run, windows=True)
        chain, openers = upd.launch_lineage()
    finally:
        upd.list_processes = old
    ctx.check(f"no launcher chain, got {chain}", chain == [])
    ctx.check(f"the Studio is the opener, got {openers}", [o["pid"] for o in openers] == [4000]
              and openers[0]["what"] == "studio")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
