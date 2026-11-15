"""tests.test_kept_outlives_starter -- what a person asked to outlive the Halo that started it does (Halo 3.6.0.0,
fix package "lifecycle" batch 1).

The candidate put the standalone updater (`halo update`, `/update`) into the kill-on-close Job object of the halo it
waits for, so on Windows it died the moment that halo exited and nothing was ever installed; the pool's `--keep`
server, the rpc-server `halo host rpc on` starts and the Signal pack's link helper were ended by the command that said
it left them running (Windows: its Job; Linux and macOS: its marker scan). Each is now started as kept
(closing.start_kept / kept_kwargs: its own marker, out of the Job, a ledger row marked kept), and a kept spawn that an
OUTER Job will not let leave is started from outside every Job (WMI on Windows), or Halo says so in one line.

1. unit (every platform): each of those spawns carries a kept marker; the pool's and the rpc-server's ledger rows name
   the command that stops them;
2. real processes: a kept server outlives its starter ended normally and ended hard (every platform); the real
   updater outlives the halo that started it and installs (Windows; POSIX execs); a kept grandchild leaves Halo's own
   Job (Windows); a kept spawn inside an outer Job that forbids breakaway outlives that Job, or Halo says it cannot
   (Windows).
Every process a test starts uses a scratch home and is ended by pid and start time; nothing is killed by name.
Run: python -m tests.test_kept_outlives_starter
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import sysconfig
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SLEEPER = REPO / "tests" / "helpers" / "closing_sleeper.py"
SIGNAL_PACK = REPO / "halo_harness" / "templates" / "packs" / "signal"
SCRUB = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_",
         "PACKS_TEST_")
WIN = os.name == "nt"


# -- helpers --------------------------------------------------------------------------------------------------------

class _Rec:
    """Stands in for subprocess_safe.Popen: records each spawn, starts nothing."""
    calls: list = []
    on_spawn = None

    def __init__(self, args, *a, **kw):
        _Rec.calls.append((list(args), kw))
        self.pid = 0
        if _Rec.on_spawn:
            _Rec.on_spawn()

    def poll(self):
        return 0


class _recording:
    def __enter__(self):
        from halo_harness import subprocess_safe
        self.saved = subprocess_safe.Popen
        _Rec.calls, _Rec.on_spawn = [], None
        subprocess_safe.Popen = _Rec
        return _Rec

    def __exit__(self, *exc):
        from halo_harness import subprocess_safe
        subprocess_safe.Popen = self.saved
        _Rec.on_spawn = None
        return False


def _kept(kw: dict) -> bool:
    from halo_harness import closing
    env = kw.get("env")
    return isinstance(env, dict) and str(env.get(closing.MARKER) or "").startswith(closing.KEPT_PREFIX) \
        and closing.WATCH not in env and (not WIN or bool(int(kw.get("creationflags") or 0) & closing._BREAKAWAY))


def _env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB)}
    env.update(BRIDGE_TEST_HOME=str(home), BRIDGE_TEST_NO_BACKGROUND_NET="1", PYTHONPATH=str(REPO),
               PYTHONIOENCODING="utf-8", HALO_NO_BROWSER="1", OLLAMA_HOST="http://127.0.0.1:9",
               HALO_NO_UPDATER="1")  # the updater test hands launch its own popen: only a stand-in install runs
    return env


def _start_time(pid: int):
    from halo_harness.bg_run import process_start_time
    return process_start_time(pid)


def _same(pid, start) -> bool:
    from halo_harness.children import same_process
    return bool(pid) and bool(start) and same_process(int(pid), start)


def _end(pid, start) -> None:
    """Only a pid this test started (its start time still matches)."""
    if not _same(pid, start):
        return
    try:
        if WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=15)
        else:
            os.kill(int(pid), signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass


def _wait_file(path: Path, seconds: float) -> "dict | None":
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(0.1)
    return None


def _starter(tmp: Path, code: str, env: dict, **kw):
    script = tmp / "starter.py"
    script.write_text(code, encoding="utf-8")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if WIN else 0
    return subprocess.Popen([kw.pop("python", sys.executable), str(script)], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            errors="replace", env=env, cwd=str(tmp), creationflags=flags | kw.pop("flags", 0), **kw)


def _ready_line(proc, seconds: float = 30.0) -> dict:
    """The starter's first stdout line (JSON)."""
    import threading
    got: dict = {}

    def read() -> None:
        line = proc.stdout.readline()
        try:
            got.update(json.loads(line))
        except ValueError:
            got["raw"] = line
    t = threading.Thread(target=read, daemon=True)
    t.start()
    t.join(seconds)
    return got


# -- 1. unit: each of these spawns is a kept one --------------------------------------------------------------------

@test
def test_the_updater_and_its_window_are_started_kept(ctx: Ctx):
    from halo_harness import update_plan as UP
    state = Path(tempfile.mkdtemp(prefix="fx-kept-update-"))
    plan = {"install": {"cmd": "echo x"}, "log": str(state / "update.log")}
    popens = []

    class _P:
        pid = 4321
    got = UP.launch(plan, state_dir=state, windows=True, python=[sys.executable, "-I"], quiet=True,
                    popen=lambda argv, **kw: popens.append((argv, kw)) or _P())
    ctx.check(f"launch started the updater and its window, got {got} {len(popens)}", got == 0 and len(popens) == 2)
    ctx.check(f"the updater is a kept spawn (its own marker, never this halo's Job), got {popens[0][1]}",
              _kept(popens[0][1]))
    ctx.check(f"its window (`--watch`) is a kept spawn too, got {popens[1][1]}",
              "--watch" in popens[1][0] and _kept(popens[1][1]) and popens[1][1]["creationflags"] & 0x10)


@test
def test_the_pools_keep_server_is_started_kept_and_named(ctx: Ctx):
    from halo_harness import closing
    from halo_harness.local_pool import spawn as S
    log = Path(tempfile.mkdtemp(prefix="fx-kept-pool-")) / "pool.log"
    with _recording() as rec:
        S.spawn(["llama-server", "--api-key", "secret"], log, ["llama-server", "--api-key", "***"], keep=True)
        S.spawn(["llama-server"], log, ["llama-server"])
    S._PROCS.clear()
    ctx.check(f"--keep: the pool's server is a kept spawn, got {rec.calls[0][1].get('env', {}).get(closing.MARKER)}",
              len(rec.calls) == 2 and _kept(rec.calls[0][1]))
    ctx.check("without --keep it stays this command's child", not _kept(rec.calls[1][1]))
    from halo_harness.local_pool import launch
    from halo_harness.local_pool import preflight as P
    from halo_harness.ollama_steward import changes_pool
    seen = []
    saved = launch.start, P.preflight
    launch.start = lambda pf, **kw: seen.append(kw) or {"ok": False, "lines": ["stand-in"]}
    P.preflight = lambda name, **kw: {"ok": True, "model": name}
    try:
        state = Path(tempfile.mkdtemp(prefix="fx-kept-warm-"))
        changes_pool.warm("qwen", keep=True, state_dir=state, home=state)
    finally:
        launch.start, P.preflight = saved
    ctx.check(f"`halo local serve --pool <model> --keep` hands --keep to the launch, got {seen}",
              seen and seen[0].get("keep") is True)
    ctx.check("the way out names how to stop it",
              closing._stop_line({"what": "pool", "pid": 1}) == "halo pool stop")


@test
def test_the_rpc_server_halo_host_rpc_on_starts_is_kept_and_named(ctx: Ctx):
    from halo_harness import closing, host_rpc_cli
    from halo_harness.host import ops_rpc, routes_view
    from halo_harness.host import rpc_runner as R
    log = Path(tempfile.mkdtemp(prefix="fx-kept-rpc-")) / "rpc.log"
    with _recording() as rec:
        R.start(["rpc-server", "-p", "50052"], log, keep=True)
        R.start(["rpc-server", "-p", "50052"], log)
    ctx.check("a kept rpc-server is a kept spawn", len(rec.calls) == 2 and _kept(rec.calls[0][1]))
    ctx.check("the host's own (not kept) stays its child", not _kept(rec.calls[1][1]))
    seen = []
    saved = ops_rpc.turn_on, routes_view.View, host_rpc_cli._addr

    class _View:
        def __init__(self, home):
            pass

        def card(self):
            return {}
    ops_rpc.turn_on = lambda home, **kw: seen.append(kw) or {"ok": False, "say": "stand-in"}
    routes_view.View, host_rpc_cli._addr = _View, (lambda home: "127.0.0.1")
    try:
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            host_rpc_cli.cmd_rpc(["on"])
    finally:
        ops_rpc.turn_on, routes_view.View, host_rpc_cli._addr = saved
    ctx.check(f"`halo host rpc on` (a command that returns) asks for a kept rpc-server, got {seen}",
              seen and seen[0].get("keep") is True)
    ctx.check("the way out names how to stop it",
              closing._stop_line({"what": "rpc", "pid": 1}) == "halo host rpc off")


@test
def test_the_signal_link_helper_is_started_kept(ctx: Ctx):
    sys.path.insert(0, str(SIGNAL_PACK))
    try:
        from halo_signal import ctl_account as A
    finally:
        sys.path.remove(str(SIGNAL_PACK))
    state: dict = {}
    saved = A._link_state, A._set_link
    A._link_state = lambda: dict(state)
    A._set_link = lambda **row: state.clear() or state.update(row)
    try:
        import contextlib
        import io
        with _recording() as rec, contextlib.redirect_stdout(io.StringIO()):
            rec.on_spawn = lambda: state.update(state="failed", line="stand-in")
            A.link([])
    finally:
        A._link_state, A._set_link = saved
    ctx.check(f"`/signal link`'s helper (it waits minutes for the phone after the command returns) is a kept spawn, "
              f"got {rec.calls}", len(rec.calls) == 1 and _kept(rec.calls[0][1]))


# -- 2. real processes ---------------------------------------------------------------------------------------------

_KEPT_SERVERS = r'''
import json, os, sys, time
sys.path.insert(0, {repo!r})
from pathlib import Path
from halo_harness import closing
closing.install(sweep_at_start=False)
from halo_harness.local_pool import spawn as S
from halo_harness.host import rpc_runner as R
tmp = Path({tmp!r})
pool = S.spawn([sys.executable, {sleeper!r}, str(tmp / "pool.json")], tmp / "pool.log", ["pool"], keep=True)
rpc = R.start([sys.executable, {sleeper!r}, str(tmp / "rpc.json")], tmp / "rpc.log", keep=True)
for name in ("pool.json", "rpc.json"):
    end = time.time() + 20
    while not (tmp / name).exists() and time.time() < end:
        time.sleep(0.05)
print(json.dumps({{"pool": pool, "rpc": rpc}}), flush=True)
if {mode!r} == "hard":
    time.sleep(120)
'''


@test
def test_a_kept_server_outlives_its_starter_ended_normally_or_hard(ctx: Ctx):
    for mode in ("normal", "hard"):
        tmp = Path(tempfile.mkdtemp(prefix=f"fx-kept-srv-{mode}-"))
        code = _KEPT_SERVERS.format(repo=str(REPO), tmp=str(tmp), sleeper=str(SLEEPER), mode=mode)
        proc = _starter(tmp, code, _env(tmp / "home"))
        kids: dict = {}
        try:
            ready = _ready_line(proc)
            ctx.check(f"{mode}: the starter started both, got {ready}", ready.get("pool") and ready.get("rpc"))
            kids = {k: (ready[k], _start_time(ready[k])) for k in ("pool", "rpc")}
            if mode == "hard":
                proc.kill()  # TerminateProcess / SIGKILL: no Python of the starter runs
            proc.wait(timeout=30)
            time.sleep(3.5)  # past the owner watch's two seconds and the reaper's bound
            for k, (pid, start) in kids.items():
                ctx.check(f"{mode}: the kept {k} server (pid {pid}) still runs after its starter went",
                          _same(pid, start))
        finally:
            if proc.poll() is None:
                proc.kill()
            for pid, start in kids.values():
                _end(pid, start)


_UPDATER = r'''
import json, os, sys, time
sys.path.insert(0, {repo!r})
from pathlib import Path
from halo_harness import closing, subprocess_safe, update_plan as UP
closing.install(sweep_at_start=False)  # what cli.main does first in a real halo
tmp = Path({tmp!r})
state = tmp / "state"
(state / "run").mkdir(parents=True, exist_ok=True)
marker = tmp / "installed.txt"
plan = UP.build_plan(cmd=f'echo installed> "{{marker}}"', cwd=None, before={{"version": None, "commit": None}},
                     expect={{"version": "9.9.9.9", "label": "9.9.9.9"}}, restore=None, state_dir=state,
                     wait_pids=[os.getpid()], windows=True)
plan["halo"] = [sys.executable, "-I", "-c", "print('halo 9.9.9.9 (abc1234, test)')"]
plan["wait_s"], plan["pause_s"] = 60, 0
started = {{}}

def popen(argv, **kw):
    if "--watch" in argv:  # no window on the test machine (the unit test checks it is started kept)
        raise OSError("no window in a test")
    proc = subprocess_safe.Popen(argv, **kw)  # what launch uses without a test seam
    started["pid"] = proc.pid
    return proc

code = UP.launch(plan, state_dir=state, windows=True, python=[sys.executable, "-I"], popen=popen, quiet=True)
print(json.dumps({{"code": code, "runner": started.get("pid")}}), flush=True)
time.sleep(1.5)
if {mode!r} == "hard":
    time.sleep(120)
'''


@test
def test_the_updater_outlives_the_halo_that_started_it_and_installs(ctx: Ctx):
    if not WIN:
        raise SkipTest("POSIX: the halo becomes the updater (exec); nothing waits in a Job")
    for mode in ("normal", "hard"):
        tmp = Path(tempfile.mkdtemp(prefix=f"fx-kept-upd-{mode}-"))
        code = _UPDATER.format(repo=str(REPO), tmp=str(tmp), mode=mode)
        proc = _starter(tmp, code, _env(tmp / "home"))
        runner = (None, None)
        try:
            ready = _ready_line(proc)
            ctx.check(f"{mode}: launch started the updater, got {ready}", ready.get("code") == 0 and ready.get("runner"))
            runner = (ready["runner"], _start_time(ready["runner"]))
            if mode == "hard":
                time.sleep(1.0)
                proc.kill()
            proc.wait(timeout=30)
            result = _wait_file(tmp / "state" / "run" / "update-result.json", 45.0)
            ctx.check(f"{mode}: the updater ran to the end after the halo went and wrote its outcome, got {result}",
                      bool(result) and result.get("outcome") == "updated")
            ctx.check(f"{mode}: the install ran", (tmp / "installed.txt").exists())
        finally:
            if proc.poll() is None:
                proc.kill()
            _end(*runner)


_GRAND = r'''
import json, os, sys, time
sys.path.insert(0, {repo!r})
from pathlib import Path
from halo_harness import closing, subprocess_safe
closing.install(sweep_at_start=False)
tmp = Path({tmp!r})
if sys.argv[1:] == ["child"]:
    kept = subprocess_safe.start_kept([sys.executable, {sleeper!r}, str(tmp / "kept.json")], what="bg",
                                      stdin=subprocess_safe.DEVNULL, stdout=subprocess_safe.DEVNULL,
                                      stderr=subprocess_safe.DEVNULL)
    (tmp / "child.json").write_text(json.dumps({{"pid": os.getpid(), "kept": kept.pid}}))
    time.sleep(120)
    sys.exit(0)
child = subprocess_safe.Popen([sys.executable, __file__, "child"], stdin=subprocess_safe.DEVNULL)  # in this Job
end = time.time() + 30
while not ((tmp / "child.json").exists() and (tmp / "kept.json").exists()) and time.time() < end:
    time.sleep(0.05)
print(json.dumps(json.loads((tmp / "child.json").read_text())), flush=True)
time.sleep(120)
'''


@test
def test_a_kept_grandchild_leaves_halos_own_job(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows only: Halo's Job object")
    tmp = Path(tempfile.mkdtemp(prefix="fx-kept-grand-"))
    proc = _starter(tmp, _GRAND.format(repo=str(REPO), tmp=str(tmp), sleeper=str(SLEEPER)), _env(tmp / "home"))
    pids: list = []
    try:
        ready = _ready_line(proc)
        ctx.check(f"the halo's child started a kept grandchild, got {ready}", ready.get("pid") and ready.get("kept"))
        pids = [(ready["pid"], _start_time(ready["pid"])), (ready["kept"], _start_time(ready["kept"]))]
        proc.kill()  # the halo ended hard: its Job closes
        proc.wait(timeout=30)
        time.sleep(3.0)
        ctx.check("its own child (in its Job) is gone", not _same(*pids[0]))
        ctx.check("the kept grandchild broke away from the Job and still runs", _same(*pids[1]))
    finally:
        if proc.poll() is None:
            proc.kill()
        for p in pids:
            _end(*p)


_OUTER = r'''
import json, os, sys, time
from pathlib import Path
from halo_harness import closing, subprocess_safe
closing.install(sweep_at_start=False)
tmp = Path({tmp!r})
if {no_way!r}:
    closing.start_outside_job = lambda *a, **k: None
with open(tmp / "kept.log", "ab") as out:
    kept = subprocess_safe.start_kept([sys.executable, {sleeper!r}, str(tmp / "kept.json")], what="bg",
                                      stdin=subprocess_safe.DEVNULL, stdout=out, stderr=subprocess_safe.STDOUT)
end = time.time() + 30
while not (tmp / "kept.json").exists() and time.time() < end:
    time.sleep(0.05)
print(json.dumps({{"kept": kept.pid, "poll": kept.poll(), "self": json.loads((tmp / "kept.json").read_text())}}),
      flush=True)
time.sleep(120)
'''


def _no_breakaway_job():
    """A Job object of this test's: kill-on-close, breakaway forbidden (what some terminals and services hold)."""
    import ctypes
    from ctypes import wintypes

    class _Basic(ctypes.Structure):
        _fields_ = [("a", ctypes.c_int64), ("b", ctypes.c_int64), ("LimitFlags", wintypes.DWORD),
                    ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("e", wintypes.DWORD), ("f", ctypes.c_size_t),
                    ("g", wintypes.DWORD), ("h", wintypes.DWORD)]

    class _Ext(ctypes.Structure):
        _fields_ = [("Basic", _Basic), ("Io", ctypes.c_ulonglong * 6), ("x", ctypes.c_size_t * 4)]
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    job = k32.CreateJobObjectW(None, None)
    info = _Ext()
    info.Basic.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE only: no BREAKAWAY_OK, no SILENT_BREAKAWAY_OK
    if not job or not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        raise SkipTest("could not make a Job object here")
    return k32, job


@test
def test_a_kept_spawn_survives_an_outer_job_that_forbids_breakaway_or_halo_says_so(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows only: Job objects")
    import ctypes
    # The base interpreter itself (a venv's python.exe is a launcher with a Job of its own in between).
    base = getattr(sys, "_base_executable", None) or sys.executable
    for no_way in (False, True):
        tmp = Path(tempfile.mkdtemp(prefix="fx-kept-outer-"))
        env = _env(tmp / "home")
        env["PYTHONPATH"] = os.pathsep.join([str(REPO), sysconfig.get_paths()["purelib"]])
        code = _OUTER.format(tmp=str(tmp), sleeper=str(SLEEPER), no_way=no_way)
        k32, job = _no_breakaway_job()
        proc = _starter(tmp, code, env, python=base, flags=0x4)  # CREATE_SUSPENDED: in the Job before it runs
        kept = (None, None)
        try:
            ctx.check("the starter is in the test's Job", k32.AssignProcessToJobObject(job, int(proc._handle)))
            ctypes.WinDLL("ntdll").NtResumeProcess(ctypes.c_void_p(int(proc._handle)))
            ready = _ready_line(proc)
            ctx.check(f"the kept spawn started, got {ready}", ready.get("kept"))
            kept = (ready["kept"], _start_time(ready["kept"]))
            k32.CloseHandle(job)  # the outer Job closes: the kernel ends everything still in it
            job = None
            proc.wait(timeout=30)
            err = proc.stderr.read()
            time.sleep(2.0)
            if not no_way:
                ctx.check(f"the Popen stands for the kept process itself, got {ready}",
                          ready["self"].get("pid") == ready["kept"] and ready.get("poll") is None)
                ctx.check("started from outside every Job, it outlives the outer Job", _same(*kept))
                ctx.check(f"and nothing was said, got {err!r}", "Job object" not in err)
            else:
                ctx.check(f"with no way out of the Job, Halo says so in one line, got {err!r}",
                          sum("Job object" in line for line in err.splitlines()) == 1)
                ctx.check("and, as that line says, it ended with that Job (the candidate did this silently)",
                          not _same(*kept))
        finally:
            if job:
                k32.CloseHandle(job)
            if proc.poll() is None:
                proc.kill()
            _end(*kept)


# -- batch 1 repair: the outer-Job way never starts a program twice, and its line says what is true ------------------

_OUTER_SHORT = r'''
import json, sys, time
from halo_harness import closing, subprocess_safe
closing.install(sweep_at_start=False)
p = subprocess_safe.start_kept([sys.executable, "-I", "-c", "open({tally!r}, 'a').write('ran\\n')"], what="bg",
                               stdin=subprocess_safe.DEVNULL, stdout=subprocess_safe.DEVNULL,
                               stderr=subprocess_safe.DEVNULL)
print(json.dumps({{"pid": p.pid, "poll": p.poll()}}), flush=True)
time.sleep(3)
'''


@test
def test_a_kept_program_that_ends_at_once_inside_an_outer_job_runs_once_and_nothing_false_is_said(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows only: Job objects")
    import ctypes
    base = getattr(sys, "_base_executable", None) or sys.executable
    tmp = Path(tempfile.mkdtemp(prefix="fx-kept-once-"))
    tally = tmp / "tally.txt"
    env = _env(tmp / "home")
    env["PYTHONPATH"] = os.pathsep.join([str(REPO), sysconfig.get_paths()["purelib"]])
    k32, job = _no_breakaway_job()
    proc = _starter(tmp, _OUTER_SHORT.format(tally=tally.as_posix()), env, python=base, flags=0x4)
    try:
        ctx.check("the starter is in the test's Job", k32.AssignProcessToJobObject(job, int(proc._handle)))
        ctypes.WinDLL("ntdll").NtResumeProcess(ctypes.c_void_p(int(proc._handle)))
        ready = _ready_line(proc, 60.0)
        ctx.check(f"start_kept returned, got {ready}", "pid" in ready)
        proc.wait(timeout=60)
        err = proc.stderr.read()
        time.sleep(2.0)
        runs = tally.read_text().count("ran") if tally.exists() else 0
        ctx.check(f"the program ran exactly once (the candidate's fallback ran it twice), got {runs}", runs == 1)
        ctx.check(f"and no line claims it was held in a Job, got {err!r}", "Job object" not in err)
    finally:
        k32.CloseHandle(job)
        if proc.poll() is None:
            proc.kill()


def _fake_wmi(take: bool, seen: list):
    """Stands in for subprocess.run of the WMI call: answers "created" (0); `take`: the runner has taken the spec
    (renamed it, as the real runner does first) but gives no pid in time."""
    def run(argv, **kw):
        spec = Path(kw["env"]["HALO_KEPT_CMDLINE"].rsplit(" ", 1)[-1].strip('"'))
        seen.append(spec)
        if take:
            spec.rename(str(spec) + ".taken")
        return subprocess.CompletedProcess(argv, 0, "0", "")
    return run


@test
def test_a_slow_runner_never_leads_to_a_second_start(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows only: the WMI way out of a Job")
    from halo_harness import closing
    tmp = Path(tempfile.mkdtemp(prefix="fx-kept-slow-"))
    tally = tmp / "tally.txt"
    argv = [sys.executable, "-I", "-c", f"open({str(tally)!r}, 'a').write('ran\\n')"]
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
          "env": dict(os.environ), "cwd": str(tmp)}
    real = subprocess.run
    try:
        seen: list = []
        subprocess.run = _fake_wmi(True, seen)
        got = closing.start_outside_job(argv, kw, wait_s=0.3)
        ctx.check(f"a runner that took the spec counts as started (never None: the caller would start it again), "
                  f"got {got!r}", got is not None)
        seen.clear()
        subprocess.run = _fake_wmi(False, seen)
        got = closing.start_outside_job(argv, kw, wait_s=0.3)
        ctx.check(f"a runner that never took the spec counts as not started, got {got!r}", got is None)
        ctx.check("and its spec was taken back, so a late runner finds nothing", seen and not seen[0].exists())
    finally:
        subprocess.run = real
    runner = tmp / "runner.py"
    runner.write_text(closing._OUTSIDE_RUNNER, encoding="utf-8")
    late = real([sys.executable, "-I", "-S", str(runner), str(seen[0])], capture_output=True, text=True, timeout=30)
    ctx.check(f"a runner that comes late starts nothing, got rc={late.returncode} {late.stderr[-300:]!r}",
              late.returncode == 0 and not tally.exists())
    leftovers = [p for p in Path(tempfile.gettempdir()).glob("halo-kept-*") if p in [s.parent for s in seen]]
    ctx.check(f"its folder (the environment, keys included) is removed, got {leftovers}", not leftovers)


@test
def test_the_held_in_a_job_line_says_asked_only_when_a_person_asked(ctx: Ctx):
    import contextlib
    import io
    from halo_harness import closing
    for env, asked in (({closing.MARKER: closing.KEPT_PREFIX + "x"}, True), ({closing.MARKER: "home-x"}, False)):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            closing.say_held_in_job(123, ["llama-server.exe", "-m", "m.gguf"], env)
        line = buf.getvalue()
        ctx.check(f"one line naming the program, got {line!r}", line.count("\n") == 1 and "llama-server" in line)
        ctx.check(f"'asked to keep' only for a kept one (asked={asked}), got {line!r}",
                  ("asked to keep" in line) == asked)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
