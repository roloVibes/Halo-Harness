"""tests.test_run_all_leftovers -- Halo 3.6.0.1 (fix package "test-rig"): tests/run_all.py fails a module that leaves a
process running, names it, and ends it by pid so it cannot poison the rest of the run.

1. A module whose test starts a sleeper and returns: the run exits 1, a `[LEFTOVER]` line names the pid, and the
   sleeper is gone afterwards.
2. An orphan: the test's child starts a grandchild (without the run's marker, its command line naming a folder the
   test made with tempfile.mkdtemp) and exits; the grandchild is found and ended too.
3. What the check must not touch: a sleeper THIS test started before the nested run is still alive after it, and a
   zombie (POSIX: killed without wait) is not counted.
4. The check's cost on a module that leaves nothing (printed; the bound is generous for slow CI runners).
5. The macOS `ps -E` rows are read right (pid, parent, start time, the marker, a zombie left out).
Everything a test here starts is ended in its finally, by its Popen or by pid and a start time read at the time.
Run: python -m tests.test_run_all_leftovers
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import leftovers  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

_HEAD = '''
import os, subprocess, sys, tempfile, time
from tests.helpers.runner import new_registry
from tests.helpers import leftovers
test, TESTS = new_registry()
SEEN = {}
QUIET = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
'''

_LEAVES_A_SLEEPER = _HEAD + '''
@test
def test_leaves_a_sleeper(ctx):
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], **QUIET)
    SEEN.update(proc=proc, pid=proc.pid)
    ctx.check("started", True)
'''

_LEAVES_AN_ORPHAN = _HEAD + '''
_CHILD = (
    "import os, subprocess, sys\\n"
    "env = {k: v for k, v in os.environ.items() if k.upper() != 'RUNALL_MODULE'}\\n"
    "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)', sys.argv[1]], env=env,\\n"
    "                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\\n"
    "open(sys.argv[2], 'w').write(str(g.pid))\\n")

@test
def test_leaves_an_orphan(ctx):
    folder = tempfile.mkdtemp(prefix="leftover-orphan-")
    pidfile = os.path.join(folder, "grandchild.pid")
    child = subprocess.Popen([sys.executable, "-c", _CHILD, folder, pidfile], **QUIET)
    child.wait(timeout=60)
    pid = int(open(pidfile).read())
    SEEN.update(grandchild=leftovers.scan().get(pid), pid=pid)
    ctx.check("the grandchild runs", SEEN["grandchild"] is not None)
'''

_LEAVES_A_ZOMBIE = _HEAD + '''
@test
def test_leaves_only_a_zombie(ctx):
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], **QUIET)
    SEEN.update(proc=proc, pid=proc.pid)
    if os.name != "nt":
        os.kill(proc.pid, 9)  # no wait(): it stays a zombie of this process until the test reaps it
        time.sleep(0.5)
    else:
        proc.kill()
        proc.wait(timeout=30)
    ctx.check("killed", True)
'''


def _package(*sources: str) -> "list[str]":
    """A throwaway package on sys.path holding one module per source; returns the module names."""
    root = Path(tempfile.mkdtemp(prefix="run-all-left-"))
    pkg = f"_run_all_left_{uuid.uuid4().hex[:8]}"
    (root / pkg).mkdir()
    (root / pkg / "__init__.py").write_text("", encoding="utf-8")
    names = []
    for i, src in enumerate(sources):
        (root / pkg / f"test_left_{i}.py").write_text(src, encoding="utf-8")
        names.append(f"{pkg}.test_left_{i}")
    sys.path.insert(0, str(root))
    return names


def _run_main(names: list) -> "tuple[int, str]":
    import tests.run_all as R
    real_discover, real_sessions = R.discover_test_modules, R._real_sessions_snapshot
    R.discover_test_modules = lambda: list(names)
    R._real_sessions_snapshot = lambda: set()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = R.main([])
    finally:
        R.discover_test_modules, R._real_sessions_snapshot = real_discover, real_sessions
    return rc, buf.getvalue()


def _gone_within(proc_row, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not leftovers._alive(proc_row):
            return True
        time.sleep(0.1)
    return not leftovers._alive(proc_row)


def _end_popen(proc) -> None:
    if proc is not None and proc.poll() is None:
        proc.kill()
    with contextlib.suppress(Exception):
        proc.wait(timeout=10)


@test
def test_a_module_that_leaves_a_sleeper_fails_and_the_sleeper_is_ended(ctx: Ctx):
    names = _package(_LEAVES_A_SLEEPER)
    seen: dict = {}
    try:
        rc, out = _run_main(names)
        seen = sys.modules[names[0]].SEEN
        pid = seen.get("pid")
        ctx.check(f"the run is red (exit 1), got {rc}:\n{out[-1200:]}", rc == 1)
        line = next((ln for ln in out.splitlines() if ln.startswith("[LEFTOVER]") and f"pid {pid} " in ln), "")
        ctx.check(f"a [LEFTOVER] line names pid {pid} and its command line, got {line!r}",
                  bool(line) and "time.sleep(60)" in line and names[0] in line)
        proc = seen.get("proc")
        deadline = time.monotonic() + 5
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        ctx.check("the sleeper was ended by the run", proc.poll() is not None)
    finally:
        _end_popen(seen.get("proc"))


@test
def test_an_orphan_naming_the_modules_temp_folder_is_found_and_ended(ctx: Ctx):
    names = _package(_LEAVES_AN_ORPHAN)
    seen: dict = {}
    try:
        rc, out = _run_main(names)
        seen = sys.modules[names[0]].SEEN
        pid, row = seen.get("pid"), seen.get("grandchild")
        ctx.check(f"the module's own test ran, got:\n{out[-800:]}", row is not None)
        ctx.check(f"the run is red (exit 1), got {rc}", rc == 1)
        ctx.check(f"a [LEFTOVER] line names the grandchild's pid {pid}",
                  any(ln.startswith("[LEFTOVER]") and f"pid {pid} " in ln for ln in out.splitlines()))
        ctx.check("the grandchild is gone", row is not None and _gone_within(row, 5))
    finally:
        row = seen.get("grandchild")
        if row is not None and leftovers._alive(row):
            leftovers.end_one(row)


@test
def test_the_check_leaves_an_older_process_and_a_zombie_alone(ctx: Ctx):
    mine = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    names = _package(_LEAVES_A_ZOMBIE)
    seen: dict = {}
    try:
        rc, out = _run_main(names)
        seen = sys.modules[names[0]].SEEN
        ctx.check(f"a module that leaves only a zombie is green, got {rc}:\n{out[-1200:]}", rc == 0)
        ctx.check("no [LEFTOVER] line", "[LEFTOVER]" not in out)
        ctx.check("the sleeper this test started before the run still runs", mine.poll() is None)
    finally:
        _end_popen(seen.get("proc"))
        _end_popen(mine)


@test
def test_the_check_costs_little_when_nothing_is_left(ctx: Ctx):
    t0 = time.monotonic()
    token = leftovers.begin("cost-probe")
    took_begin = time.monotonic() - t0
    got = leftovers.end(token)
    print(f"    (the leftover check: begin {took_begin:.3f}s, end {got['seconds']:.3f}s, "
          f"{len(token['known'])} processes on this machine)")
    ctx.check(f"nothing is left, got {leftovers.report_lines('cost-probe', got)}", not got["left"])
    ctx.check(f"the check costs under 5 s on a module that leaves nothing, took {took_begin + got['seconds']:.2f}s",
              took_begin + got["seconds"] < 5)
    ctx.check("the marker is put back", os.environ.get(leftovers.MARK) == token["prev"])


@test
def test_macos_ps_rows_are_read_right(ctx: Ctx):
    text = ("  101     1 Ss   Mon Nov 16 09:05:01 2026     /usr/sbin/sshd -D PATH=/usr/bin\n"
            "  202   101 S    Mon Nov 16 11:28:53 2026     /usr/bin/python3 -c sleep ~/tmp/x RUNALL_MODULE=77-5/tests.t "
            "HOME=/x\n"
            "  303   202 Z    Mon Nov 16 11:28:54 2026     (python3)\n"
            "  404   202 R    Mon Nov  2 01:02:03 2026     ps -A -ww -E\n")
    rows = leftovers.parse_ps(text, skip_pid=404)
    ctx.check(f"two live rows, the zombie and the scan's own ps left out, got {sorted(rows)}", sorted(rows) == [101, 202])
    r = rows.get(202)
    ctx.check(f"parent, marker and command read, got {r}",
              r is not None and r.ppid == 101 and r.mark == "77-5/tests.t" and r.cmd.startswith("/usr/bin/python3"))
    ctx.check("the start time is UTC epoch seconds, later for the child",
              r is not None and rows[101].start < r.start and r.start % 60 == 53)
    one_digit = leftovers.parse_ps("  9 1 S Mon Nov  2 01:02:03 2026 x\n")
    ctx.check("a padded one-digit day is read", 9 in one_digit)


@test
def test_run_all_runs_the_check_around_every_module(ctx: Ctx):
    src = (Path(__file__).resolve().parent / "run_all.py").read_text(encoding="utf-8")
    ctx.check("run_all begins the check before a module and ends it in the module's finally",
              re.search(r"leftovers\.begin\(", src) is not None and re.search(r"leftovers\.end\(", src) is not None)


if __name__ == "__main__":
    from tests.helpers.runner import install_temp_dir_tracking
    install_temp_dir_tracking()
    results, passed, failed, skipped = run_all(TESTS, Ctx())
    sys.exit(print_results(results, passed, failed, skipped))
