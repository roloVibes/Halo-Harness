"""tests.test_run_all_leftovers -- Halo 3.6.0.1 (fix package "test-rig"): tests/run_all.py fails a module that leaves a
process running, names it, and ends it by pid so it cannot poison the rest of the run.

1. A module whose test starts a sleeper and returns: the run exits 1, a `[LEFTOVER]` line names the pid, and the
   sleeper is gone afterwards.
2. An orphan: the test's child starts a grandchild (without the run's marker, its command line naming a folder the
   test made with tempfile.mkdtemp) and exits; the grandchild is found and named, the run is red, but the check does
   not end it (jf-rig: found by a folder name alone is not proof the run started it; Windows under WmiPrvSE excepted).
3. What the check must not touch: a sleeper THIS test started before the nested run is still alive after it, and a
   zombie (POSIX: killed without wait) is not counted.
4. The check's cost on a module that leaves nothing (printed; the bound is generous for slow CI runners).
5. The macOS `ps -E` rows are read right (pid, parent, start time, the marker, a zombie left out).
6. (jf-rig) What may be ended (a child or a marker of the run; a folder match only on Windows under WmiPrvSE), that a
   [LEFTOVER] line shows argv only (never an environment, cut to 200 characters), and the grace: Halo's way-out budget
   plus a margin, waited only while something is still there (injected clock).
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
def test_an_orphan_naming_the_modules_temp_folder_is_found_and_named_not_ended(ctx: Ctx):
    # 3.6.0.1 jf-rig: an orphan found only because its command line names a run folder is not proven to be the run's
    # (a developer's `tail -f` from another terminal looks the same): it is named and the module is red, but the
    # check never ends it. This test started it, so this test ends it, in the finally.
    names = _package(_LEAVES_AN_ORPHAN)
    seen: dict = {}
    try:
        rc, out = _run_main(names)
        seen = sys.modules[names[0]].SEEN
        pid, row = seen.get("pid"), seen.get("grandchild")
        ctx.check(f"the module's own test ran, got:\n{out[-800:]}", row is not None)
        ctx.check(f"the run is red (exit 1), got {rc}", rc == 1)
        line = next((ln for ln in out.splitlines() if ln.startswith("[LEFTOVER]") and f"pid {pid} " in ln), "")
        ctx.check(f"a [LEFTOVER] line names the grandchild's pid {pid} and says it was not ended, got {line!r}",
                  "NOT ENDED" in line)
        ctx.check("the check left the grandchild running", row is not None and leftovers._alive(row))
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


# ---- 3.6.0.1 (jf-rig): what may be ended, what a line shows, how long the check waits -------------------------------

_ORPHAN_CHILD = (
    "import os, subprocess, sys\n"
    "env = {k: v for k, v in os.environ.items() if k.upper() != 'RUNALL_MODULE'}\n"
    "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)', sys.argv[1]], env=env,\n"
    "                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
    "open(sys.argv[2], 'w').write(str(g.pid))\n")


class _Clock:
    """An injected clock for leftovers.end: sleep() moves it on, nothing really waits."""

    def __init__(self):
        self.now, self.sleeps = 1000.0, 0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        self.now += seconds


@contextlib.contextmanager
def _patched(**attrs):
    old = {k: getattr(leftovers, k) for k in attrs}
    try:
        for k, v in attrs.items():
            setattr(leftovers, k, v)
        yield
    finally:
        for k, v in old.items():
            setattr(leftovers, k, v)


def _token(folders=()) -> dict:
    return {"module": "m", "known": set(), "prev": os.environ.get(leftovers.MARK),
            "value": f"{leftovers.run_id()}/m", "folders": [str(f) for f in folders],
            "tracked_from": len(leftovers._tracked())}


def _row(pid, ppid, start, cmd="", mark="", **extra):
    p = leftovers.Proc(pid, ppid, start, cmd, mark)
    for k, v in extra.items():
        setattr(p, k, v)
    return p


@test
def test_only_the_helpers_of_the_rigs_own_browser_are_left_out(ctx: Ctx):
    """The first CI run with the check on, macOS legs: two browser modules were counted red for the crash handler of
    the rig's own driver Chrome and for the machine's Google updater (`GoogleUpdater --wake-all`, started by any
    Chrome), and the check ended them. Left out now, with what they start: but ONLY under the marker the rig's driver
    gives its browser (rig_browser_env). The reviewers' case: a crash handler left by the Chrome HALO starts (replay
    clips) carries the plain marker and is still counted and ended. A name alone leaves nothing out."""
    me = os.getpid()
    token = _token()  # before the scan is patched: run_id() reads this process once
    plain, rig = token["value"], token["value"] + leftovers.RIG_BROWSER
    app = "/Applications/Google Chrome.app/Contents/Frameworks/Google Chrome Framework.framework/Versions/1/Helpers"
    updater = "/Library/Application Support/Google/GoogleUpdater/1.0/GoogleUpdater.app/Contents/MacOS/GoogleUpdater"
    procs = {
        me: _row(me, 1, 10),
        701: _row(701, 1, 20, f"{app}/chrome_crashpad_handler --monitor-self-annotation=ptype=crashpad-handler", rig),
        702: _row(702, 1, 20, f"{updater} --wake-all", rig),
        703: _row(703, me, 20, "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --headless=new --x", rig),
        704: _row(704, 1, 20, "/opt/google/chrome/chrome_crashpad_handler --monitor-self --database=/tmp/x", rig),
        705: _row(705, me, 20, "python sleeper.py --note GoogleUpdater", plain),  # an ordinary child that names one
        706: _row(706, 1, 20, f"{app}/chrome_crashpad_handler --monitor-self-annotation=ptype=crashpad-handler", plain),
        707: _row(707, 702, 21, "/bin/sh /tmp/ksinstall-step.sh", rig),          # what the rig browser's updater starts
        708: _row(708, 1, 20, "sleep 600 /tmp/googleupdater", plain),            # a helper's name as an argument
        709: _row(709, 1, 20, "/opt/x/chrome_crashpad_handler_more --monitor-self", rig),  # not the name itself
        710: _row(710, 1, 20, "C:/Program Files/X/crashpad_handler.exe --database=C:/t", rig),
    }
    with _patched(scan=lambda want=None: dict(procs)):
        found = {p.pid: p for p in leftovers.find(token)}
    ctx.check(f"left out: the rig browser's crash handlers (701, 704, 710), its updater (702) and what that starts "
              f"(707); counted: everything else, got {sorted(found)}", sorted(found) == [703, 705, 706, 708, 709])
    ctx.check(f"the crash handler of the Chrome Halo started is found by the marker and may be ended, got "
              f"{getattr(found.get(706), 'why', None)!r}",
              706 in found and found[706].why == "marker" and leftovers._may_end(found[706]))
    saved = os.environ.get(leftovers.MARK)
    try:
        os.environ[leftovers.MARK] = plain
        env = leftovers.rig_browser_env()
        again = leftovers.rig_browser_env()
        ctx.check(f"the rig's browser gets the marker with its ending, once, and this process keeps its own, got "
                  f"{env.get(leftovers.MARK)!r}", env[leftovers.MARK] == rig and again[leftovers.MARK] == rig
                  and os.environ[leftovers.MARK] == plain)
        del os.environ[leftovers.MARK]
        ctx.check("with no check on, the browser's environment gets no marker", leftovers.MARK not in leftovers.rig_browser_env())
    finally:
        if saved is None:
            os.environ.pop(leftovers.MARK, None)
        else:
            os.environ[leftovers.MARK] = saved


@test
def test_a_process_found_only_by_a_folder_name_is_named_but_never_ended(ctx: Ctx):
    folder = os.path.join(tempfile.gettempdir(), "run-folder-probe")
    me = os.getpid()
    token = _token([folder])
    procs = {
        me: _row(me, 1, 10),
        501: _row(501, me, 20, "python child.py"),                                   # a child of this run
        502: _row(502, 1, 20, "python marked.py", token["value"]),                   # carries this run's marker
        503: _row(503, 1, 20, f"tail -f {folder}{os.sep}x.log", parent_exe="explorer.exe"),  # another terminal
        504: _row(504, 1, 20, f"python {folder}{os.sep}kept.py", parent_exe="WmiPrvSE.exe"),  # Windows: a WMI start
    }
    ended: list = []
    clock = _Clock()

    def fake_end(p, wait_s=5.0):
        ended.append(p.pid)
        return True

    # _fill_args is stubbed: on macOS it reads each found pid's argv again with a real `ps`, and these pids are made up
    with _patched(scan=lambda want=None: dict(procs), end_one=fake_end, time=clock, _fill_args=lambda found: None):
        got = leftovers.end(token)
    left = {p.pid: ok for p, ok in got["left"]}
    want_ended = [501, 502] + ([504] if leftovers.WIN else [])
    ctx.check(f"all four are named, got {sorted(left)}", sorted(left) == [501, 502, 503, 504])
    ctx.check(f"only the run's own are ended ({want_ended}), got {sorted(ended)}", sorted(ended) == want_ended)
    line = next((ln for ln in leftovers.report_lines("m", got) if "pid 503 " in ln), "")
    ctx.check(f"the line of the one found by its folder alone says it was not ended, got {line!r}",
              "NOT ENDED" in line and "ended by pid" not in line)


@test
def test_a_folder_match_is_ended_only_on_windows_under_the_wmi_host(ctx: Ctx):
    wmi = _row(9, 8, 2, "x", why="folder", parent_exe="WmiPrvSE.exe")
    other = _row(9, 8, 2, "x", why="folder", parent_exe="cmd.exe")
    ctx.check("Windows, parent WmiPrvSE: ended", leftovers._may_end(wmi, win=True) is True)
    ctx.check("Windows, any other parent: not ended", leftovers._may_end(other, win=True) is False)
    ctx.check("macOS / Linux: never by a folder alone", leftovers._may_end(wmi, win=False) is False)
    for why in ("child", "marker"):
        ctx.check(f"a {why} of the run is ended everywhere",
                  leftovers._may_end(_row(9, 8, 2, why=why), win=False) is True
                  and leftovers._may_end(_row(9, 8, 2, why=why), win=True) is True)


@test
def test_a_real_process_naming_a_run_folder_is_left_running(ctx: Ctx):
    folder = tempfile.mkdtemp(prefix="leftover-folder-")
    pidfile = os.path.join(folder, "orphan.pid")
    row = None
    token = leftovers.begin("folder-probe", [folder])
    try:
        env = {k: v for k, v in os.environ.items() if k.upper() != leftovers.MARK}
        child = subprocess.Popen([sys.executable, "-c", _ORPHAN_CHILD, folder, pidfile], env=env,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        child.wait(timeout=60)
        pid = int(open(pidfile).read())
        row = leftovers.scan(lambda p, _s: p == pid).get(pid)
        ctx.check("the orphan runs", row is not None)
        got = leftovers.end(token, grace_s=0.5)
        token = None
        mine = [(p, ok) for p, ok in got["left"] if row is not None and p.pid == row.pid]
        ctx.check(f"it is named (the module is red), got {leftovers.report_lines('folder-probe', got)}", bool(mine))
        ctx.check("it was not ended", bool(mine) and not mine[0][1])
        ctx.check("it still runs after the check", row is not None and leftovers._alive(row))
    finally:
        if token is not None:
            leftovers.end(token, grace_s=0)
        if row is not None and leftovers._alive(row):
            leftovers.end_one(row)


@test
def test_a_leftover_line_never_shows_an_environment(ctx: Ctx):
    text = ("  202   101 S    Mon Nov 16 11:28:53 2026     /usr/bin/python3 -c import time;time.sleep(60) TERM=xterm "
            "SHELL=/bin/zsh ANTHROPIC_API_KEY=not-a-real-key-123 HOME=/h/someone RUNALL_MODULE=77-5/tests.t\n")
    row = leftovers.parse_ps(text).get(202)
    ctx.check("the macOS row is read, its marker too", row is not None and row.mark == "77-5/tests.t")
    line = leftovers.report_lines("tests.t", {"left": [(row, True)]})[0] if row else ""
    ctx.check(f"no environment in the line, got {line!r}",
              bool(line) and not any(w in line for w in ("ANTHROPIC_API_KEY", "not-a-real-key", "HOME=", "TERM=")))
    long = _row(7, 1, 1, "x" * 500, args="x" * 500)
    line = leftovers.report_lines("m", {"left": [(long, True)]})[0]
    ctx.check(f"the command line is cut to 200 characters, got {line.count('x')}", line.count("x") == 200)


@test
def test_macos_argv_is_read_again_without_the_environment(ctx: Ctx):
    plain = leftovers.parse_ps("  202 101 S Mon Nov 16 11:28:53 2026 /usr/bin/python3 -c pass\n", with_env=False)
    ctx.check("a row read without -E: its command is its argv", plain[202].args == "/usr/bin/python3 -c pass")
    envd = leftovers.parse_ps("  202 101 S Mon Nov 16 11:28:53 2026 /usr/bin/python3 -c pass HOME=/h\n")
    ctx.check("a row read with -E: its argv is not known from it", envd[202].args == "")
    same, reused = envd[202], _row(203, 101, 5, "y HOME=/h")
    now = {202: _row(202, 101, same.start, "/usr/bin/python3 -c pass", args="/usr/bin/python3 -c pass"),
           203: _row(203, 101, 99, "z", args="z")}
    with _patched(WIN=False, HAVE_PROC=False, _row_now=lambda pid: now.get(pid)):
        leftovers._fill_args([same, reused])
    ctx.check(f"argv read again for the same process, got {same.args!r}", same.args == "/usr/bin/python3 -c pass")
    ctx.check(f"nothing taken from a pid now naming another process, got {reused.args!r}", reused.args == "")


@test
def test_a_process_that_ends_inside_halos_way_out_budget_is_not_a_leftover(ctx: Ctx):
    from halo_harness.closing import QUIT_BUDGET_S
    clock = _Clock()
    gone_at = clock.now + QUIT_BUDGET_S + 0.5
    p = _row(601, os.getpid(), 20, "halo", why="child")
    ended: list = []
    with _patched(find=lambda token: [p] if clock.now < gone_at else [], time=clock, _fill_args=lambda found: None,
                  end_one=lambda q, wait_s=5.0: ended.append(q.pid) or True):
        got = leftovers.end(_token())
    ctx.check(f"a process gone {QUIT_BUDGET_S + 0.5}s after the module is no leftover, got {got['left']}",
              not got["left"] and not ended)


@test
def test_a_process_alive_after_the_whole_grace_is_a_leftover(ctx: Ctx):
    from halo_harness.closing import QUIT_BUDGET_S
    clock = _Clock()
    t0 = clock.now
    p = _row(602, os.getpid(), 20, "sleeper", why="child")
    ended: list = []
    with _patched(find=lambda token: [p], time=clock, _fill_args=lambda found: None,
                  end_one=lambda q, wait_s=5.0: ended.append(q.pid) or True):
        got = leftovers.end(_token())
    waited = clock.now - t0
    ctx.check(f"the grace is Halo's way-out budget plus a margin, at least 8 s, got {waited:.2f}s",
              waited >= max(8.0, QUIT_BUDGET_S + 1.0))
    ctx.check("then it is a leftover, ended by pid", [q.pid for q, _ok in got["left"]] == [602] and ended == [602])
    clean = _Clock()
    with _patched(find=lambda token: [], time=clean):
        leftovers.end(_token())
    ctx.check(f"a module that leaves nothing never waits, slept {clean.sleeps} times", clean.sleeps == 0)


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
