"""tests.test_lifecycle_batch02 -- stop paths that signal, the ledger's own spawns, liveness checks that cost a
program, and the Studio a venv launcher starts (Halo 3.6.0.0, fix package "lifecycle" batch 2).

1. `halo host stop`, `halo host steward off`, the rpc-server's off and the pool's stop read a pid from a state file;
   they signal it only when its start time is recorded AND matches (children.provably_same). A record that names
   another program now (a reboot, a hard kill) is cleared, never signalled. (every platform)
2. what the marker scan ends on the way out is named in one line, and a tool command that starts something with a
   `kept-` marker keeps it (POSIX: the marker scan does not run on Windows, the Job object covers it).
3. a `halo --bg` run (started with subprocess_safe.Popen) is in the ledger, so `halo ps` / `halo stop` see it.
4. a liveness check of this process's own pid starts no program, and the Governor checks another pid at most once a
   second (macOS pays one `ps` per check).
5. closing a launch whose Studio a venv's python.exe launcher started asks that Studio to stop itself (Windows: the
   ledger holds the launcher's pid, studio.json the real one).
Every process a test starts is its own and is ended by pid and start time; nothing is killed by name.
Run: python -m tests.test_lifecycle_batch02
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
WIN = os.name == "nt"
SCRUB = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_",
         "GEMINI_", "GOOGLE_", "OLLAMA_")


def _start(pid):
    from halo_harness.children import start_time
    return start_time(pid)


def _sleeper():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 10
    start = _start(proc.pid)
    while start is None and time.time() < deadline:
        time.sleep(0.05)
        start = _start(proc.pid)
    return proc, start


def _end(proc) -> None:
    if proc.poll() is None:
        proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


class _Home:
    """A scratch state folder for this process (BRIDGE_STATE_DIR) and back."""

    def __enter__(self):
        self._snap = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        self.root = Path(tempfile.mkdtemp(prefix="lc-b2-"))
        self.state = self.root / "state"
        (self.state / "host").mkdir(parents=True)
        os.environ["BRIDGE_TEST_HOME"] = str(self.root)
        os.environ["BRIDGE_STATE_DIR"] = str(self.state)
        return self

    def __exit__(self, *exc):
        for k, v in self._snap.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.root, ignore_errors=True)


def _quiet(fn, *a, **kw):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = fn(*a, **kw)
    return code, out.getvalue()


# ---- 1. a pid read from a state file is signalled only with its start time ------------------------------------------

def _records(proc, start) -> list:
    return [("no start time", {}), ("another start time", {"start_time": "not-" + str(start)})]


@test
def test_halo_host_stop_never_signals_a_pid_its_record_cannot_prove(ctx: Ctx):
    from halo_harness import host_cli
    old = getattr(host_cli, "STOP_WAIT_S", None)
    host_cli.STOP_WAIT_S = 0.5
    try:
        for name, extra in _records(None, "x"):
            with _Home() as h:
                proc, start = _sleeper()
                try:
                    (h.state / "host" / "serve.json").write_text(json.dumps({"pid": proc.pid, "port": 9, **extra}))
                    code, out = _quiet(host_cli.cmd_stop, [])
                    time.sleep(0.3)
                    ctx.check(f"{name}: the other program is not signalled (exit {proc.poll()}), said {out!r}",
                              proc.poll() is None)
                    ctx.check(f"{name}: it does not claim it stopped a host, said {out!r}", "stopped (pid" not in out)
                    ctx.check(f"{name}: the stale record is cleared", not (h.state / "host" / "serve.json").exists())
                finally:
                    _end(proc)
        with _Home() as h:  # the control: a record that proves its process is still stopped
            proc, start = _sleeper()
            try:
                (h.state / "host" / "serve.json").write_text(json.dumps({"pid": proc.pid, "port": 9,
                                                                          "start_time": start}))
                code, out = _quiet(host_cli.cmd_stop, [])
                proc.wait(timeout=10)
                ctx.check(f"a proven host that ignores the stop file is ended, said {out!r}", proc.poll() is not None)
            finally:
                _end(proc)
    finally:
        host_cli.STOP_WAIT_S = old if old is not None else 10.0


@test
def test_serve_json_records_the_hosts_start_time(ctx: Ctx):
    from halo_harness.host import state as S
    with _Home() as h:
        S.write_info(h.state, {"pid": os.getpid(), "port": 9})
        got = json.loads((h.state / "host" / "serve.json").read_text())
        ctx.check(f"serve.json carries start_time, got {got}", got.get("start_time") == _start(os.getpid()))
        proc, start = _sleeper()
        try:
            (h.state / "host" / "serve.json").write_text(json.dumps({"pid": proc.pid, "port": 9, "start_time": "x"}))
            ctx.check("a record whose start time does not match reads as no host", S.read_info(h.state) is None)
            from halo_harness import closing_home_watch as W
            ctx.check("the home watch does not take it for a living halo",
                      not W.halos_alive(str(h.state), (2 ** 22 + 7, "")))
        finally:
            _end(proc)


@test
def test_halo_host_steward_off_never_signals_a_pid_its_record_cannot_prove(ctx: Ctx):
    from halo_harness import host_steward_cli
    from halo_harness.host import duty
    old = getattr(host_steward_cli, "STOP_WAIT_S", None)
    host_steward_cli.STOP_WAIT_S = 0.5
    try:
        for name, extra in _records(None, "x"):
            with _Home() as h:
                proc, start = _sleeper()
                try:
                    duty.write_state(h.state, {"pid": proc.pid, "model": "m", **extra})
                    if not extra:  # a record an older halo wrote: no start time at all
                        (h.state / "host" / duty.STATE_FILE).write_text(json.dumps({"pid": proc.pid, "model": "m"}))
                    code, out = _quiet(host_steward_cli.cmd_off, [])
                    time.sleep(0.3)
                    ctx.check(f"{name}: the other program is not signalled (exit {proc.poll()}), said {out!r}",
                              proc.poll() is None)
                finally:
                    _end(proc)
        with _Home() as h:
            duty.write_state(h.state, {"pid": os.getpid(), "model": "m"})
            got = duty.read_state(h.state)
            ctx.check(f"steward.json records the start time, got {got}", got.get("start_time") == _start(os.getpid()))
    finally:
        host_steward_cli.STOP_WAIT_S = old if old is not None else 10.0


@test
def test_rpc_server_off_never_signals_a_pid_its_record_cannot_prove(ctx: Ctx):
    from halo_harness.host import ops_rpc
    for name, extra in _records(None, "x"):
        with _Home() as h:
            proc, start = _sleeper()
            try:
                (h.state / "host" / ops_rpc.FILE).write_text(json.dumps({"pid": proc.pid, "port": 50052,
                                                                         "bind": "127.0.0.1", **extra}))
                got = ops_rpc.turn_off(h.state)
                time.sleep(0.3)
                ctx.check(f"{name}: the other program is not signalled (exit {proc.poll()}), said {got.get('say')!r}",
                          proc.poll() is None)
                ctx.check(f"{name}: the record no longer names that pid", ops_rpc.read(h.state).get("pid") is None)
            finally:
                _end(proc)
    with _Home() as h:
        proc, start = _sleeper()
        try:
            (h.state / "host" / ops_rpc.FILE).write_text(json.dumps({"pid": proc.pid, "port": 50052,
                                                                     "start_time": start}))
            got = ops_rpc.turn_off(h.state)
            proc.wait(timeout=10)
            ctx.check(f"a proven rpc-server is stopped, said {got.get('say')!r}", proc.poll() is not None)
        finally:
            _end(proc)


@test
def test_halt_and_terminate_signal_only_a_proven_pid(ctx: Ctx):
    from halo_harness import children_stop
    from halo_harness.local_pool import spawn
    from halo_harness.providers import local_server_cmd
    proc, start = _sleeper()
    try:
        how = local_server_cmd.halt(proc.pid, grace=1.0, start=None)
        time.sleep(0.3)
        ctx.check(f"halt with no start time signals nothing, said {how!r}", proc.poll() is None)
        how = local_server_cmd.halt(proc.pid, grace=1.0, start="not-" + str(start))
        time.sleep(0.3)
        ctx.check(f"halt with another start time signals nothing, said {how!r}", proc.poll() is None)
        how = spawn.halt(proc.pid)
        time.sleep(0.3)
        ctx.check(f"the pool's halt of a pid it did not spawn, with no start time, signals nothing: {how!r}",
                  proc.poll() is None)
        ok = children_stop.terminate(proc.pid, timeout=1.0, recorded=None)
        time.sleep(0.3)
        ctx.check(f"children_stop.terminate with no start time signals nothing (said {ok})", proc.poll() is None)
        how = local_server_cmd.halt(proc.pid, grace=2.0, start=start)
        proc.wait(timeout=10)
        ctx.check(f"halt with the matching start time ends it, said {how!r}", proc.poll() is not None)
    finally:
        _end(proc)


@test
def test_the_pools_run_record_carries_its_start_time(ctx: Ctx):
    from halo_harness.local_pool import launch
    for name, extra in _records(None, "x"):
        with _Home() as h:
            proc, start = _sleeper()
            try:
                launch._save({"model": "m", "pid": proc.pid, "port": 9, "placed": [], "rpc_started": [], **extra},
                             h.state)
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    got = launch.stop(state_dir=h.state, home=h.state)
                time.sleep(0.3)
                ctx.check(f"{name}: `halo pool stop` does not signal the other program, said {got.get('lines')}",
                          proc.poll() is None)
            finally:
                _end(proc)
    with _Home() as h:
        proc, start = _sleeper()
        try:
            launch._save({"model": "m", "pid": proc.pid, "port": 9, "placed": [], "rpc_started": [],
                          "start_time": start}, h.state)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                got = launch.stop(state_dir=h.state, home=h.state)
            proc.wait(timeout=15)
            ctx.check(f"a proven pool server is stopped, said {got.get('lines')}", proc.poll() is not None)
        finally:
            _end(proc)
    src = (REPO / "halo_harness" / "local_pool" / "launch.py").read_text(encoding="utf-8")
    ctx.check("the run record is written with the server's start time", "\"start_time\": start_time(pid)" in src)


# ---- 2. what the marker scan ends is named; a kept- marker keeps it (POSIX) ---------------------------------------

def _owner_run(kind: str, tmp: Path, started: list):
    """Start the owner; it goes into `started` at once, so the caller's finally ends it (and what it started) even
    when it never gets ready. HALO_TEST_NO_PROC is kept, as tests/test_closing.py keeps it: the owner and this test
    must read start times the same way (/proc or `ps`), or a live child reads as gone and is never ended."""
    out = tmp / "out"
    out.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB) or k == "HALO_TEST_NO_PROC"}
    env.update(BRIDGE_TEST_HOME=str(tmp / "home"), PYTHONPATH=str(REPO), PYTHONIOENCODING="utf-8",
               HALO_NO_BROWSER="1", OLLAMA_HOST="http://127.0.0.1:9", HALO_NO_UPDATER="1")
    proc = subprocess.Popen([sys.executable, str(REPO / "tests" / "helpers" / "closing_owner.py"), kind, str(out)],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            env=env, cwd=str(tmp))
    started.append(proc)
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            return proc, out, json.loads((out / "ready.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            if proc.poll() is not None:
                break
            time.sleep(0.1)
    raise AssertionError("the owner never got ready")


def _end_owner_run(started: list, mine: list, out: Path) -> None:
    """End what one owner run started: the owner (its Popen), each kid by pid and the start time THIS process read
    at ready time, and a child the owner started but never listed (it died before ready.json) by its pid when its
    command line names this run's own folder."""
    from halo_harness.children import provably_same
    from tests.helpers import leftovers
    for proc in started:
        if proc.poll() is None:
            proc.kill()
        with contextlib.suppress(Exception):
            proc.communicate(timeout=10)
    for pid, start in mine:
        if start is not None and provably_same(pid, start):
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGKILL)
    listed = {pid for pid, _s in mine}
    for f in out.glob("*.json") if out.is_dir() else ():
        try:
            pid = int(json.loads(f.read_text(encoding="utf-8")).get("pid") or 0)
        except (OSError, ValueError, AttributeError):
            continue
        if pid and pid not in listed:
            row = leftovers.scan(lambda p, _s: p == pid).get(pid)
            if row is not None and str(out) in row.cmd:
                leftovers.end_one(row)


def _marker_scan_case(ctx: Ctx, kind: str, mine: list) -> None:
    """One owner run of `kind` ("tool" or "keptmark"); `mine` gets (pid, start time read by this process) per kid."""
    from halo_harness.children import same_process
    tmp = Path(tempfile.mkdtemp(prefix=f"lc-b2-{kind}-"))
    started: list = []
    try:
        proc, out, ready = _owner_run(kind, tmp, started)
        kids = ready["kids"]
        mine.extend((k["pid"], _start(k["pid"])) for k in kids)
        (out / "quit").write_text("", encoding="utf-8")
        _o, err = proc.communicate(timeout=20)
        time.sleep(1.0)
        kid = kids[0]
        alive = same_process(kid["pid"], kid["start"])
        if kind == "tool":
            ctx.check(f"tool: the leftover is ended (alive {alive})", not alive)
            ctx.check(f"tool: the way out names what it ended, got {err[-400:]!r}",
                      "halo: ended" in err and str(kid["pid"]) in err)
        else:
            ctx.check(f"kept marker: the child started with HALO_OWNER=kept-... survives (alive {alive})", alive)
            ctx.check(f"kept marker: its marker is a kept one, got {kid.get('marker')!r}",
                      str(kid.get("marker") or "").startswith("kept-"))
    finally:
        _end_owner_run(started, mine, tmp / "out")
        shutil.rmtree(tmp, ignore_errors=True)


@test
def test_what_the_marker_scan_ends_is_named_and_a_kept_marker_keeps_it(ctx: Ctx):
    if WIN:
        raise SkipTest("POSIX: the marker scan does not run on Windows (the Job object ends a tool's daemon)")
    for kind in ("tool", "keptmark"):
        _marker_scan_case(ctx, kind, [])


@test
def test_the_kept_marker_case_ends_its_kept_child_on_the_macos_identity_path(ctx: Ctx):
    """3.6.0.1: with HALO_TEST_NO_PROC=1 (Linux reading start times from `ps`, as macOS does) the case above went red
    AND left its kept sleeper running forever: the owner (its env scrubbed of the variable) recorded a /proc start
    time, this process compared it with a `ps` one, so the kept child read as gone and the finally skipped it."""
    if WIN:
        raise SkipTest("POSIX: the marker scan does not run on Windows (the Job object ends a tool's daemon)")
    from unittest import mock
    from halo_harness.children import provably_same
    mine: list = []
    with mock.patch.dict(os.environ, {"HALO_TEST_NO_PROC": "1"}):
        inner, failed = Ctx(), ""
        try:
            try:
                _marker_scan_case(inner, "keptmark", mine)
            except AssertionError as e:
                failed = str(e)
            ctx.check(f"the kept-marker case passes on the macOS identity path, failed with {failed!r}", not failed)
            ctx.check(f"the case named its kept child, got {mine}", bool(mine) and all(s for _p, s in mine))
            time.sleep(3.0)
            alive = [pid for pid, start in mine if start is not None and provably_same(pid, start)]
            ctx.check(f"nothing the case started still runs 3 s after it, alive {alive}", not alive)
        finally:
            for pid, start in mine:
                if start is not None and provably_same(pid, start):
                    with contextlib.suppress(OSError):
                        os.kill(pid, signal.SIGKILL)


@test
def test_the_line_for_ended_leftovers_names_each_program(ctx: Ctx):
    from halo_harness import closing
    line = closing.ended_line({101: "tmux", 202: "sleep"})
    ctx.check(f"one line, both named with pids, got {line!r}",
              line.startswith("halo: ended") and "tmux (pid 101)" in line and "sleep (pid 202)" in line
              and "\n" not in line)
    ctx.check(f"it says how to keep one, got {line!r}", "HALO_OWNER=kept-" in line)
    ctx.check("nothing ended: no line", closing.ended_line({}) == "")


# ---- 3. a `halo --bg` run is in the ledger -------------------------------------------------------------------------

@test
def test_a_popen_of_subprocess_safe_counts_as_spawned(ctx: Ctx):
    from unittest import mock

    from halo_harness import children
    from halo_harness import subprocess_safe
    proc = subprocess_safe.Popen([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait(timeout=30)
    ctx.check("subprocess_safe.Popen is a real spawn", children.spawned(proc))
    ctx.check("a mock with the Popen spec is not", not children.spawned(mock.MagicMock(spec=subprocess.Popen)))


@test
def test_a_bg_run_is_in_the_ledger(ctx: Ctx):
    from halo_harness import children
    from halo_harness.bg_run import start_background_run
    with _Home() as h:
        snap = os.environ.get("HALO_NO_UPDATER"), os.environ.get("OLLAMA_HOST")
        os.environ.update(HALO_NO_UPDATER="1", OLLAMA_HOST="http://127.0.0.1:9")
        try:
            info = start_background_run(["--version"])
        finally:
            for k, v in zip(("HALO_NO_UPDATER", "OLLAMA_HOST"), snap):
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        rows = children._load(children.registry_path(h.state))
        ctx.check(f"children.json has the bg run (pid {info['pid']}), got {rows}",
                  any(r.get("pid") == info["pid"] and r.get("what") == "bg" for r in rows))
        deadline = time.time() + 60
        while time.time() < deadline and children.pid_running(info["pid"]):
            time.sleep(0.2)


# ---- 4. liveness checks that start a program ----------------------------------------------------------------------

@test
def test_this_processs_own_pid_is_alive_without_starting_a_program(ctx: Ctx):
    from unittest import mock

    from halo_harness import bg_run, process_alive

    def boom(*_a, **_k):
        raise AssertionError("a program was started (or the OS asked) for this process's own pid")
    with mock.patch.object(bg_run, "_ps_zombie", boom), mock.patch.object(process_alive, "win_alive", boom), \
            mock.patch.object(bg_run.subprocess, "run", boom):
        try:
            got = bg_run.pid_alive(os.getpid())
        except AssertionError as e:
            got = str(e)
    ctx.check(f"pid_alive(os.getpid()) is True at once, got {got!r}", got is True)


@test
def test_the_governor_checks_another_pid_at_most_once_a_second(ctx: Ctx):
    from unittest import mock

    from halo_harness.providers import governor
    seen: list = []

    def counting(pid):
        seen.append(pid)
        return True
    now = 1000.0
    st = {"inflight": {"a": {"pid": os.getpid(), "ts": now}, "b": {"pid": 4_000_001, "ts": now}},
          "waiters": {"w1": {"pid": 4_000_002, "ts": now, "hb": now}, "w2": {"pid": os.getpid(), "ts": now, "hb": now}}}
    governor._ALIVE_SEEN.clear() if hasattr(governor, "_ALIVE_SEEN") else None
    with mock.patch.object(governor, "pid_alive", counting):
        for i in range(25):  # 0.5 s of a waiter's passes, 20 ms apart
            governor._reap(st, now + i * 0.02)
            for e in list(st["inflight"].values()) + list(st["waiters"].values()):
                e["hb"] = now + i * 0.02
    ctx.check(f"this process's own pid is never checked, got {seen.count(os.getpid())}", os.getpid() not in seen)
    ctx.check(f"each other pid once in half a second, got {sorted(seen)}", sorted(seen) == [4_000_001, 4_000_002])
    ctx.check("nothing was reaped", len(st["inflight"]) == 2 and len(st["waiters"]) == 2)


# ---- 5. a Studio a venv launcher started is asked to stop itself ---------------------------------------------------

@test
def test_closing_asks_its_own_studio_to_stop_when_the_ledger_holds_the_launchers_pid(ctx: Ctx):
    from unittest import mock

    from halo_harness import closing
    from halo_harness.studio import launch
    with _Home() as h:
        me, mstart = closing.me()
        (h.state / "studio.json").write_text(json.dumps({"pid": 4_000_003, "port": 9, "owner_pid": me,
                                                          "owner_start": mstart}))
        asked: list = []
        signalled: list = []
        with mock.patch.object(launch, "_ask_shutdown", lambda info: asked.append(info["pid"]) or True), \
                mock.patch.object(closing, "_signal_tree", lambda pid, hard: signalled.append((pid, hard))):
            closing._polite({"pid": 4_000_004, "what": "studio"}, h.state)
            time.sleep(0.3)
        ctx.check(f"the Studio studio.json names (this halo's own) is asked to stop, got {asked}", asked == [4_000_003])
        ctx.check(f"the launcher is not signalled before that, got {signalled}", not signalled)


def _venv_python(tmp: Path) -> Path:
    subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", "--without-pip", str(tmp / "venv")],
                   check=True, capture_output=True, timeout=180)
    return tmp / "venv" / "Scripts" / "python.exe"


VENV_PROBE = r'''
import json, os, sys, time
from pathlib import Path
from halo_harness import children, closing
from halo_harness.studio import launch
closing.install()
state = Path(os.environ["BRIDGE_STATE_DIR"])
url = launch.launch_detached("setup", cwd=state.parent, state_dir=state, open_browser=False, timeout=120)
info = launch.read_info(state) or {}
rows = [r.get("pid") for r in children.load(state) if r.get("what") == "studio"]
t0 = time.monotonic()
closing.close(say=lambda line: None, state_dir=state)
print(json.dumps({"url": url, "studio_pid": info.get("pid"), "pstart": info.get("pstart"), "ledger": rows,
                  "close_s": round(time.monotonic() - t0, 2), "studio_json_left": (state / "studio.json").exists()}))
'''


@test
def test_windows_a_venv_launch_closes_its_studio_politely(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows: only there is a venv's python.exe a launcher with its own child")
    from halo_harness.children import same_process
    tmp = Path(tempfile.mkdtemp(prefix="lc-b2-venv-"))
    got: dict = {}
    try:
        py = _venv_python(tmp)
        (tmp / "probe.py").write_text(VENV_PROBE, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB)}
        env.update(BRIDGE_TEST_HOME=str(tmp / "home"), BRIDGE_STATE_DIR=str(tmp / "home" / ".halo"),
                   PYTHONPATH=str(REPO), PYTHONIOENCODING="utf-8", HALO_NO_BROWSER="1", HALO_NO_UPDATER="1",
                   OLLAMA_HOST="http://127.0.0.1:9", BRIDGE_TEST_NO_BACKGROUND_NET="1")
        (tmp / "home" / ".halo").mkdir(parents=True)
        r = subprocess.run([str(py), str(tmp / "probe.py")], capture_output=True, text=True, env=env,
                           cwd=str(tmp), timeout=240)
        try:
            got = json.loads((r.stdout or "").strip().splitlines()[-1])
        except (IndexError, ValueError):
            raise AssertionError(f"the probe gave no answer (exit {r.returncode}): {r.stderr[-800:]}")
        ctx.check(f"the Studio started, got {got}", bool(got.get("url")))
        ctx.check(f"the ledger holds the Studio's own pid, got {got}", got.get("studio_pid") in (got.get("ledger") or []))
        ctx.check(f"the close took well under the polite wait, got {got.get('close_s')} s", got.get("close_s", 9) < 2.5)
        ctx.check(f"the Studio ran its own shutdown (studio.json removed), got {got}", not got.get("studio_json_left"))
    finally:
        if got.get("studio_pid") and got.get("pstart") and same_process(got["studio_pid"], got["pstart"]):
            subprocess.run(["taskkill", "/PID", str(got["studio_pid"]), "/T", "/F"], capture_output=True, timeout=15)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
