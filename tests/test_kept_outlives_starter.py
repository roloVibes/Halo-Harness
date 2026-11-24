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
from tests.helpers.spawn_shown import kw_shown  # noqa: E402

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
    ctx.check(f"the updater is a kept spawn (its own marker, never this halo's Job), got {kw_shown(popens[0][1])}",
              _kept(popens[0][1]))
    ctx.check(f"its window (`--watch`) is a kept spawn too, got {kw_shown(popens[1][1])}",
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
    ctx.check(f"--keep: the pool's server is a kept spawn, got {[kw_shown(kw) for _a, kw in rec.calls[:1]]}",
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
    ctx.check(f"`halo local serve --pool <model> --keep` hands --keep to the launch, got {[kw_shown(kw) for kw in seen]}",
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
    ctx.check(f"`halo host rpc on` (a command that returns) asks for a kept rpc-server, got {[kw_shown(kw) for kw in seen]}",
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


def _base_starter_code(code: str) -> str:
    """The outer-Job starters run the BASE interpreter. Inside a venv its site-packages is added AFTER the standard
    library (site.addsitedir appends): on PYTHONPATH it would rank first, and an old backport there (Anaconda's
    `pathlib`) shadows the standard library. Outside a venv the base interpreter already has its own."""
    if sys.prefix == sys.base_prefix:
        return code
    return f"import site; site.addsitedir({sysconfig.get_paths()['purelib']!r})\n" + code


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
        env = _env(tmp / "home")  # PYTHONPATH = the repo only
        code = _base_starter_code(_OUTER.format(tmp=str(tmp), sleeper=str(SLEEPER), no_way=no_way))
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
    env = _env(tmp / "home")  # PYTHONPATH = the repo only
    k32, job = _no_breakaway_job()
    proc = _starter(tmp, _base_starter_code(_OUTER_SHORT.format(tally=tally.as_posix())), env, python=base, flags=0x4)
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


@test
def test_the_outer_job_starters_never_put_a_site_packages_folder_ahead_of_the_standard_library(ctx: Ctx):
    """A site-packages folder holding an old backport (Anaconda's `pathlib`) must not shadow the standard library in
    the outer-Job starters: they put it on PYTHONPATH, which ranks it first, and the starter died at its first import
    on such a PC. Here purelib is a folder whose `pathlib.py` fails (a .pth in it still leads to the real one)."""
    if not WIN:
        raise SkipTest("Windows only: the two outer-Job tests are")
    from unittest import mock
    shadow = Path(tempfile.mkdtemp(prefix="fx-kept-shadow-"))
    (shadow / "pathlib.py").write_text("raise ImportError('shadowed')\n", encoding="utf-8")
    real = sysconfig.get_paths()
    (shadow / "real.pth").write_text(real["purelib"] + "\n", encoding="utf-8")
    shadowed = dict(real, purelib=str(shadow))
    for fn in (test_a_kept_spawn_survives_an_outer_job_that_forbids_breakaway_or_halo_says_so,
               test_a_kept_program_that_ends_at_once_inside_an_outer_job_runs_once_and_nothing_false_is_said):
        err = ""
        with mock.patch.object(sysconfig, "get_paths", lambda *a, **k: dict(shadowed)):
            try:
                fn(Ctx())
            except AssertionError as e:
                err = str(e)
        ctx.check(f"{fn.__name__} passes with a shadowing site-packages, got {err!r}", not err)


def _fake_wmi(take: bool, seen: list):
    """Stands in for closing._run_wmi (the WMI call's PowerShell): answers "created" (0); `take`: the runner has taken
    the spec (renamed it, as the real runner does first) but gives no pid in time."""
    def run(cmdline, cwd, wait_s, stop):
        spec = Path(cmdline.rsplit(" ", 1)[-1].strip('"'))
        seen.append(spec)
        if take:
            spec.rename(str(spec) + ".taken")
        return "0"
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
    real = closing._run_wmi
    try:
        seen: list = []
        closing._run_wmi = _fake_wmi(True, seen)
        got = closing.start_outside_job(argv, kw, wait_s=0.3)
        ctx.check(f"a runner that took the spec counts as started (never None: the caller would start it again), "
                  f"got {got!r}", got is not None)
        took = seen[0].parent
        ctx.check(f"and only its stop mark stays for that runner (no spec, no keys), got "
                  f"{sorted(p.name for p in took.iterdir()) if took.exists() else None}",
                  took.exists() and [p.name for p in took.iterdir()] == ["stop"])
        import shutil
        shutil.rmtree(took, ignore_errors=True)
        seen.clear()
        closing._run_wmi = _fake_wmi(False, seen)
        got = closing.start_outside_job(argv, kw, wait_s=0.3)
        ctx.check(f"a runner that never took the spec counts as not started, got {got!r}", got is None)
        ctx.check("and its spec was taken back, so a late runner finds nothing", seen and not seen[0].exists())
    finally:
        closing._run_wmi = real
    runner = tmp / "runner.py"
    runner.write_text(closing._OUTSIDE_RUNNER, encoding="utf-8")
    late = subprocess.run([sys.executable, "-I", "-S", str(runner), str(seen[0])], capture_output=True, text=True,
                          timeout=30)
    ctx.check(f"a runner that comes late starts nothing, got rc={late.returncode} {late.stderr[-300:]!r}",
              late.returncode == 0 and not tally.exists())
    leftovers = [p for p in Path(tempfile.gettempdir()).glob("halo-kept-*") if p in [s.parent for s in seen]]
    ctx.check(f"its folder (the environment, keys included) is removed, got {leftovers}", not leftovers)


@test
def test_a_kept_outside_start_that_begins_once_close_ran_is_taken_back_with_no_create(ctx: Ctx):
    """3.6.0.18 L (batch 2, entry 5a): close() sets "closed" and then marks the outside starts in flight; a start that
    BEGINS after that (a worker's kept start) is marked from the start: taken back at once, the WMI create never runs,
    the caller gets what a taken-back start gives (StartCancelled), and no folder (the environment) stays."""
    if not WIN:
        raise SkipTest("Windows only: the WMI way out of a Job")
    from halo_harness import closing
    tmp = Path(tempfile.mkdtemp(prefix="fx-kept-after-close-"))
    argv = [sys.executable, "-I", "-c", "pass"]
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
          "env": dict(os.environ), "cwd": str(tmp)}
    real, saved_closed = closing._run_wmi, closing._STATE.get("closed")
    before = set(Path(tempfile.gettempdir()).glob("halo-kept-*"))
    seen: list = []
    got: object = None
    try:
        closing._run_wmi = _fake_wmi(False, seen)
        closing._STATE["closed"] = True
        try:
            got = closing.start_outside_job(argv, kw, wait_s=0.3)
        except closing.StartCancelled as e:
            got = e
    finally:
        closing._run_wmi = real
        closing._STATE["closed"] = saved_closed
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    ctx.check(f"the create ran 0 times, got {len(seen)}", seen == [])
    ctx.check(f"the caller gets a taken-back start (StartCancelled), got {got!r}",
              isinstance(got, closing.StartCancelled))
    left = set(Path(tempfile.gettempdir()).glob("halo-kept-*")) - before
    ctx.check(f"no folder stays, got {sorted(left)}", not left)


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


# -- 3.6.0.18 S: a quit while a kept start is in flight -------------------------------------------------------------
# At a quit, a start that has not happened does not happen; one that did is named (kept) or is the person's (the
# browser). The WMI create's PowerShell is held in Halo's strict Job; the runner starts only for a starter that still
# runs (its pid AND creation time) and a folder with no stop mark; every way out marks the starts in flight first.

def _runner_ns() -> "dict | None":
    """The outside runner's functions, loaded without running it (None when it has no decision to test)."""
    from halo_harness import closing
    if "def may_start" not in closing._OUTSIDE_RUNNER:
        return None
    ns: dict = {"__name__": "halo_kept_runner_under_test"}
    exec(compile(closing._OUTSIDE_RUNNER, "<halo-kept runner>", "exec"), ns)
    return ns


@test
def test_the_kept_runner_starts_only_for_its_running_starter_and_no_stop_mark(ctx: Ctx):
    ns = _runner_ns()
    ctx.check("the runner decides from state right before the start (may_start)", ns is not None)
    if ns is None:
        return
    import shutil
    tmp = Path(tempfile.mkdtemp(prefix="fx-kept-decide-"))
    try:
        taken = tmp / "spec.json.taken"
        taken.write_text("{}", encoding="utf-8")
        may = ns["may_start"]
        ctx.check("the starter runs with the creation time the orders carry: it starts", may(str(taken), "77", "77"))
        ctx.check("the starter is gone: nothing starts", not may(str(taken), "77", None))
        ctx.check("the pid is another process now (another creation time): nothing starts",
                  not may(str(taken), "77", "78"))
        ctx.check("orders with no identity: nothing starts", not may(str(taken), None, "77"))
        (tmp / "stop").write_text("x", encoding="utf-8")
        ctx.check("a stop mark is there: nothing starts", not may(str(taken), "77", "77"))
        (tmp / "stop").unlink()
        taken.unlink()
        ctx.check("its orders were removed (the folder taken back): nothing starts", not may(str(taken), "77", "77"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if WIN:  # the identity the runner reads is the one closing.me() gives
        from halo_harness import closing
        ctx.check("a running starter reads as its own creation time", ns["starter_start"](os.getpid()) == closing.me()[1])
        done = subprocess.Popen([sys.executable, "-c", "pass"])
        done.wait(timeout=60)  # its handle stays open here: the pid is not reused, the process has ended
        ctx.check("an ended starter reads as gone", ns["starter_start"](done.pid) is None)


@test
def test_a_second_ctrl_c_in_the_browser_wait_prints_nothing_and_loses_no_start(ctx: Ctx):
    import contextlib
    import io
    import threading
    from halo_harness import closing
    release = threading.Event()

    class _Held(threading.Thread):
        interrupted = False

        def join(self, timeout=None):
            if not self.interrupted:
                self.interrupted = True
                raise KeyboardInterrupt  # the second Ctrl+C, inside the wait
            return super().join(timeout)

    th = _Held(target=release.wait, name="halo-browser-start", daemon=True)
    th.halo_in_command = True
    saved_browsers, saved_deadline = list(closing._BROWSERS), closing._STATE.get("deadline")
    th.start()
    buf, raised = io.StringIO(), None
    try:
        closing._BROWSERS[:] = [th]
        with contextlib.redirect_stderr(buf):
            try:
                closing._browsers_at_exit()
            except KeyboardInterrupt as e:
                raised = e
        ctx.check("the wait ends without a KeyboardInterrupt (no traceback at exit)", raised is None)
        ctx.check(f"and prints nothing, got {buf.getvalue()!r}", buf.getvalue() == "")
        ctx.check("the start is still in the list, so a later close() sees it", th in closing._BROWSERS)
    finally:
        release.set()
        th.interrupted = True
        th.join(30)
        closing._BROWSERS[:] = saved_browsers
        closing._STATE["deadline"] = saved_deadline


@test
def test_a_kept_start_registered_during_closes_wait_is_named(ctx: Ctx):
    import shutil
    import threading
    from halo_harness import children, closing
    sd = Path(tempfile.mkdtemp(prefix="fx-kept-named-"))
    go = threading.Event()

    def start() -> None:  # a start in flight at the quit; its program had started before the mark
        if go.wait(60):
            children.register(os.getpid(), "pool", [sys.executable, "-m", "gpu-box-server"], keep=True, state_dir=sd)

    th = threading.Thread(target=start, name="halo-browser-start", daemon=True)
    th.halo_in_command = True
    saved, saved_browsers = dict(closing._STATE), list(closing._BROWSERS)
    try:
        closing._STATE.update(closed=False, callbacks=[go.set], spawned=False, reaper=None, deadline=None,
                              hard_exit=None, owner_gone=False)
        closing._BROWSERS[:] = [th]
        th.start()
        lines = closing.close(state_dir=sd, say=lambda _l: None)
        ctx.check(f"close() names the kept program registered inside its wait, got {lines}",
                  any(f"(pid {os.getpid()})" in line and "halo pool stop" in line for line in lines))
    finally:
        go.set()
        th.join(30)
        closing._STATE.clear()
        closing._STATE.update(saved)
        closing._BROWSERS[:] = saved_browsers
        shutil.rmtree(sd, ignore_errors=True)


@test
def test_a_ctrl_c_in_a_kept_outside_start_takes_it_back_or_names_what_did_start(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows only: the WMI way out of a Job")
    from halo_harness import children, closing
    real_wmi, real_reg, real_mark = closing._run_wmi, children.register, closing._mark_outside
    had_frees, saved_frees = "frees" in closing._STATE, closing._STATE.get("frees")
    for started in (False, True):
        folders: list = []
        named: list = []
        stops: list = []

        def wmi(cmdline, cwd, wait_s, stop):
            spec = Path(cmdline.rsplit(" ", 1)[-1].strip('"'))
            folders.append(spec.parent)
            if started:  # the runner took the spec and started the program, then the Ctrl+C came
                spec.rename(str(spec) + ".taken")
                (spec.parent / "result.json").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
            raise KeyboardInterrupt

        def mark(folder):
            real_mark(folder)
            stops.append((folder / "stop").exists() or (folder / "spec.void").exists())

        raised = False
        try:
            closing._run_wmi, closing._mark_outside = wmi, mark
            children.register = lambda pid, what, cmd, **kw: named.append((pid, what, kw.get("keep")))
            closing._STATE["frees"] = False  # an outer Job that forbids breakaway
            try:
                closing.start_kept([sys.executable, "-c", "pass"], what="pool", stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except KeyboardInterrupt:
                raised = True
        finally:
            closing._run_wmi, closing._mark_outside, children.register = real_wmi, real_mark, real_reg
            if had_frees:
                closing._STATE["frees"] = saved_frees
            else:
                closing._STATE.pop("frees", None)
        ctx.check(f"started={started}: the Ctrl+C goes on", raised)
        ctx.check(f"started={started}: the start was marked (a void spec or a stop file), got {stops}",
                  stops and all(stops))
        want = [(os.getpid(), "pool", True)] if started else []
        ctx.check(f"started={started}: a program that did start is in the ledger as kept, else nothing, got {named}",
                  named == want)
        ctx.check(f"started={started}: its folder is gone", folders and not folders[0].exists())


_QUIT_MID_START = r'''
import json, os, sys, time
from halo_harness import closing
closing.install(sweep_at_start=False)
{hold}
ok = closing.open_url("http://127.0.0.1:9/quit-mid-start")
print(json.dumps({{"ok": ok, "unsure": closing.open_unsure()}}), flush=True)
while not os.path.exists({held!r}):
    time.sleep(0.05)
if {way!r} == "close":
    closing.close()
    os._exit(0)
if {way!r} == "hard_exit":
    closing.hard_exit(0, 0)
time.sleep(600)
'''


def _held_pid(path: Path, seconds: float) -> "int | None":
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            return int(path.read_text(encoding="utf-8", errors="replace").strip().lstrip("﻿"))
        except (OSError, ValueError):
            time.sleep(0.1)
    return None


def _gone(pairs: list, seconds: float) -> bool:
    """Every (pid, start) here has ended, waited for within `seconds`."""
    end = time.monotonic() + seconds
    while any(_same(*p) for p in pairs):
        if time.monotonic() >= end:
            return False
        time.sleep(0.1)
    return True


def _kept_folders(temp: Path) -> list:
    return sorted(temp.glob("halo-kept-*"))


def _settle(temp: Path, opened: Path, seconds: float) -> None:
    """A runner that took a spec has answered, and the browser it started has written its line."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        busy = [f for f in _kept_folders(temp) if (f / "spec.json").exists() or (f / "spec.json.taken").exists()]
        started = [f for f in _kept_folders(temp) if "pid" in ((_wait_file(f / "result.json", 0.1) or {}))]
        if not busy and (not started or (opened.exists() and opened.read_text(encoding="utf-8").strip())):
            return
        time.sleep(0.1)


def _quit_mid_start(ctx: Ctx, held_part: str, way: str) -> None:
    """A starter (in a Job that forbids breakaway) opens the stand-in browser; its outside start is held at
    `held_part` ("powershell": before the WMI create; "runner": the create done, the runner before its spec); the
    starter leaves `way` ("close": close() then os._exit; "hard_exit": hard_exit(0, 0); "kill": a hard kill)."""
    import ctypes
    import shutil
    sys.path.insert(0, str(REPO / "scripts"))
    from realcheck import fakes
    base = getattr(sys, "_base_executable", None) or sys.executable
    tmp = Path(tempfile.mkdtemp(prefix="fx-kept-quit-"))
    temp = tmp / "t"
    temp.mkdir()
    held, go = tmp / "held", tmp / "go"
    browser, opened = fakes.browser_command(tmp)
    if held_part == "powershell":
        ps = (f"Set-Content -LiteralPath '{held}' -Value $PID; "
              f"while (-not (Test-Path -LiteralPath '{go}')) {{ Start-Sleep -Milliseconds 100 }}; ")
        hold = f"closing._WMI_CREATE = {ps!r} + closing._WMI_CREATE"
    else:
        py = (f"import os as _o, time as _t\nopen({str(held) + '.tmp'!r}, 'w').write(str(_o.getpid()))\n"
              f"_o.replace({str(held) + '.tmp'!r}, {str(held)!r})\n"
              f"while not _o.path.exists({str(go)!r}):\n    _t.sleep(0.05)\n")
        hold = f"closing._OUTSIDE_RUNNER = {py!r} + closing._OUTSIDE_RUNNER"
    env = _env(tmp / "home")
    env.pop("HALO_NO_BROWSER", None)
    env.update(BROWSER=browser, TEMP=str(temp), TMP=str(temp))
    code = _base_starter_code(_QUIT_MID_START.format(hold=hold, held=str(held), way=way))
    k32, job = _no_breakaway_job()
    proc = _starter(tmp, code, env, python=base, flags=0x4)  # CREATE_SUSPENDED: in the Job before it runs
    helper: tuple = (None, None)
    kids: list = []
    what = f"{held_part} held, {way}"
    try:
        ctx.check(f"{what}: the starter is in the test's Job", k32.AssignProcessToJobObject(job, int(proc._handle)))
        ctypes.WinDLL("ntdll").NtResumeProcess(ctypes.c_void_p(int(proc._handle)))
        ready = _ready_line(proc, 120.0)
        ctx.check(f"{what}: the browser start was handed on, got {ready}", ready.get("ok") and ready.get("unsure"))
        pid = _held_pid(held, 120.0)
        ctx.check(f"{what}: the outside start reached its hold", pid)
        helper = (pid, _start_time(pid))
        if held_part == "powershell":
            from halo_harness import closing
            kids = [(k, _start_time(k)) for k, parent in closing._parent_map_windows().items() if parent == pid]
        if way == "kill":
            proc.kill()
        proc.wait(timeout=120)
        alive_at_go = False
        if held_part == "powershell":
            ctx.check(f"{what}: the helper PowerShell (and its console host) ended with Halo, before it could create "
                      f"anything", _gone([helper] + kids, 60.0))
            alive_at_go = _same(*helper)
        go.write_text("go", encoding="utf-8")
        if held_part == "runner" or alive_at_go:
            ctx.check(f"{what}: the held helper has finished", _gone([helper], 120.0))
            _settle(temp, opened, 60.0)
        lines = opened.read_text(encoding="utf-8").strip() if opened.exists() else ""
        ctx.check(f"{what}: no browser started after Halo had gone, got {lines!r}", not lines)
        left = [(f.name, sorted(p.name for p in f.iterdir())) for f in _kept_folders(temp)]
        if held_part == "powershell" and way == "kill":  # a hard kill runs no code: its spec stays, never taken
            ctx.check(f"{what}: no runner took its spec, got {left}",
                      all("spec.json" in names and "result.json" not in names for _n, names in left))
        else:
            ctx.check(f"{what}: no halo-kept folder is left, got {left}", not left)
    finally:
        try:
            go.write_text("go", encoding="utf-8")
        except OSError:
            pass
        if proc.poll() is None:
            proc.kill()
        if job:
            k32.CloseHandle(job)
        for pair in [helper] + kids:
            _end(*pair)
        _gone([helper], 60.0)
        shutil.rmtree(tmp, ignore_errors=True)


@test
def test_a_quit_while_the_helper_powershell_is_held_starts_nothing_and_leaves_nothing(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows only: the outside-the-Job start runs only inside a Job that forbids breakaway")
    for way in ("close", "hard_exit", "kill"):
        _quit_mid_start(ctx, "powershell", way)


@test
def test_a_quit_while_the_runner_is_held_starts_no_browser_and_leaves_nothing(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows only: the outside-the-Job start runs only inside a Job that forbids breakaway")
    for way in ("close", "hard_exit", "kill"):
        _quit_mid_start(ctx, "runner", way)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
