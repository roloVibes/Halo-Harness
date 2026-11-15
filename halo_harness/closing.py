"""halo_harness.closing -- when Halo closes, everything it started closes (Halo 3.6.0.0 R10).

The rule: no process Halo started is alive five seconds after the Halo that started it is gone, however it went
(a normal exit, Ctrl+C, SIGTERM, a closed terminal, a hard kill), unless a person asked in so many words for that
thing to keep running and Halo said so on the way out. docs/PROCESSES.md is the page for people.

    install()            the real process's first call (cli.main with no argv): the marker, the owner watch, the
                         closing procedure on every way out, the sweep at start
    close()              THE closing procedure: every ledger child this process owns, children before parents,
                         politely (its own shutdown), then by signal to its group / tree, then hard, inside
                         POLITE_S + HARD_S; then every process that still carries this tree's marker (POSIX);
                         silent when all is well, one line per thing left running on purpose
    sweep()              at a launch: every ledger entry whose owner is gone and was not asked to stay is stopped
    kept_kwargs(kw)      what a spawn that a person asked to keep passes to Popen (its own marker, no owner watch,
                         out of the Job object on Windows)
    owner_env()          the environment entries that make a Halo child watch this process

How the children notice a dead owner on their own (a hard kill runs no Python at all):

* every child carries `HALO_OWNER=<id of the Halo that started it>` in its environment (subprocess_safe.Popen adds it
  when a caller built its own environment), so a scan finds strays the ledger lost (`halo ps`, the reaper, close());
  each Halo process marks what it starts with its OWN id, so a `halo` run from a session's shell tool, or a sub-agent,
  ends only its own and never its parent's (two sessions of one home never touch each other's either);
* Windows: every child subprocess_safe.Popen starts goes into this process's Job object with KILL_ON_JOB_CLOSE, so
  the kernel ends them when the last handle (this process) goes; a kept spawn breaks away;
* a Halo child (`python -m halo_harness ...`: the Studio server first of all) gets `HALO_OWNER_WATCH=<pid>:<start>`
  and its install() watches that process (the parent pid on POSIX, a process handle on Windows) and closes within
  two seconds of it going;
* POSIX: the first long-lived spawn starts the reaper (closing_reaper.py), a tiny Halo-owned process that waits for
  this one and, when it is gone, stops its ledger children and every process with its marker -- someone else's
  binary (an MCP server, a model server) that cannot watch anything is covered by it.

Never a pid Halo did not start: a ledger entry is checked by pid AND start time before every signal; a marker
match is a process that inherited this tree's own id (and is checked again by its start time before the kill).
"""

from __future__ import annotations

import atexit
import hashlib
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

MARKER = "HALO_OWNER"            # the id of the Halo that started this process (a Halo child sets its own for its own)
WATCH = "HALO_OWNER_WATCH"       # "<pid>:<start>" of the Halo that started this process (a Halo child watches it)
KEPT_PREFIX = "kept-"            # a marker that starts so: asked to outlive its starter, never stopped by a close
POLITE_S, HARD_S = 3.0, 2.0
WATCH_POLL_S = 0.25
KEPT_KINDS = ("bg", "supervisor", "host", "update", "terminal")
_BREAKAWAY = 0x01000000          # CREATE_BREAKAWAY_FROM_JOB
_STATE: dict = {"installed": False, "closed": False, "spawned": False, "reaper": None, "job": None,
                "callbacks": [], "owner_gone": False}
_LOCK = threading.RLock()


# -- who this process is -------------------------------------------------------------------------------------------

def _start(pid: int) -> Optional[str]:
    try:
        from halo_harness.bg_run import process_start_time
        return process_start_time(pid)
    except Exception:
        return None


def me() -> "tuple[int, Optional[str]]":
    pid = os.getpid()
    if _STATE.get("me_pid") != pid:
        _STATE["me_pid"], _STATE["me_start"] = pid, _start(pid)
    return pid, _STATE["me_start"]


def ident(pid: int, start: Optional[str]) -> str:
    """The marker id of a process: `<pid>-<10 hex of its start time>` (no spaces: a `ps -E` line splits on them)."""
    digest = hashlib.sha1(str(start or "").encode("utf-8")).hexdigest()[:10]
    return f"{int(pid)}-{digest}"


def my_ident() -> str:
    return ident(*me())


def marker() -> str:
    """The marker this process gives its children: its own id once installed."""
    return os.environ.get(MARKER) or my_ident()


def parse_watch(text: str) -> "tuple[Optional[int], Optional[str]]":
    pid, _sep, start = str(text or "").partition(":")
    try:
        return int(pid), (start or None)
    except ValueError:
        return None, None


def marker_owner_alive(mark: str) -> Optional[bool]:
    """Whether the root a marker names still runs (None: not a marker of that shape, a kept one)."""
    if not mark or mark.startswith(KEPT_PREFIX):
        return None
    pid, _sep, digest = mark.partition("-")
    if not pid.isdigit():
        return None
    from halo_harness import children as C
    if not C.pid_running(int(pid)):
        return False
    return ident(int(pid), _start(int(pid))) == mark or not digest


def owner() -> "tuple[Optional[int], Optional[str]]":
    """The Halo that started this process and that it watches: (pid, start), or (None, None) for a root."""
    if _STATE.get("owner"):
        return _STATE["owner"]
    pid, start = parse_watch(os.environ.get(WATCH, ""))
    return (pid, start) if pid and pid != os.getpid() else (None, None)


def owner_env() -> dict:
    """What a Halo child's environment carries so it watches this process and joins this tree."""
    pid, start = me()
    return {MARKER: marker(), WATCH: f"{pid}:{start or ''}"}


def kept_kwargs(kwargs: Optional[dict] = None, *, env: Optional[dict] = None) -> dict:
    """Popen keyword arguments for a spawn a person asked to keep (`halo --bg`, `halo host serve`, `halo supervise
    --daemon`, a model server with --keep, the updater): its own kept marker, no owner watch, out of the Job object."""
    import uuid
    kw = dict(kwargs or {})
    base = dict(env if env is not None else (kw.get("env") if isinstance(kw.get("env"), dict) else os.environ))
    base.pop(WATCH, None)
    base[MARKER] = KEPT_PREFIX + uuid.uuid4().hex[:12]
    kw["env"] = base
    if os.name == "nt":  # out of the Job object, and off this console (a closed window or Ctrl+Break never reaches it)
        flags = int(kw.get("creationflags") or 0) | _BREAKAWAY | 0x00000200  # | CREATE_NEW_PROCESS_GROUP
        kw["creationflags"] = flags if flags & 0x00000010 else flags | 0x00000008  # NEW_CONSOLE, else DETACHED_PROCESS
    else:
        kw["start_new_session"] = True  # off this terminal: its SIGHUP and Ctrl+C never reach it
    return kw


def keep_kw(keep: bool, env: dict) -> dict:
    """`env=` (and on Windows the breakaway flag) for a spawn that may or may not have been asked to stay."""
    return kept_kwargs(env=env) if keep else {"env": env}


def is_kept_env(env) -> bool:
    return isinstance(env, dict) and str(env.get(MARKER) or "").startswith(KEPT_PREFIX)


class without_marker:
    """`with without_marker():` -- what starts inside does not carry this tree's marker or owner (a browser the
    person keeps: webbrowser.open starts it when none runs). Process-wide for the moment it lasts."""

    def __enter__(self):
        self.saved = {k: os.environ.pop(k) for k in (MARKER, WATCH) if k in os.environ}
        return self

    def __exit__(self, *exc):
        os.environ.update(self.saved)
        return False


# -- the Popen hook (subprocess_safe.Popen calls these) -----------------------------------------------------------

def before_spawn(kw: dict) -> dict:
    """A caller that built its own environment still passes this tree's marker (and owner) on."""
    env = kw.get("env")
    if isinstance(env, dict) and MARKER not in env and os.environ.get(MARKER):
        env = dict(env)
        env[MARKER] = os.environ[MARKER]
        if os.environ.get(WATCH) and WATCH not in env:
            env[WATCH] = os.environ[WATCH]
        kw = dict(kw, env=env)
    return kw


def after_spawn(proc, kw: dict) -> None:
    """A child that was not asked to stay joins this process's Job object (Windows); the reaper starts (POSIX)."""
    if is_kept_env(kw.get("env")):
        return
    _STATE["spawned"] = True
    if os.name == "nt":
        adopt(proc)
    elif _STATE["installed"]:
        ensure_reaper()


def note_spawn() -> None:
    """A spawn that does not go through subprocess_safe (the MCP SDK's own) still counts."""
    _STATE["spawned"] = True
    if os.name != "nt" and _STATE["installed"]:
        ensure_reaper()


# -- Windows: the Job object ---------------------------------------------------------------------------------------

def _k32():
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    k32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    k32.WaitForSingleObject.restype = wintypes.DWORD
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    return k32


def _job():
    """This process's Job object: KILL_ON_JOB_CLOSE (the kernel ends every member when this process's handle goes,
    a hard kill included) and BREAKAWAY_OK (a kept spawn leaves it). Never inherited: no child holds it open."""
    if _STATE["job"] is not None:
        return _STATE["job"] or None
    with _LOCK:
        if _STATE["job"] is not None:
            return _STATE["job"] or None
        try:
            import ctypes
            from ctypes import wintypes

            class _Basic(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                            ("SchedulingClass", wintypes.DWORD)]

            class _Io(ctypes.Structure):
                _fields_ = [(n, ctypes.c_ulonglong) for n in ("Read", "Write", "Other", "ReadB", "WriteB", "OtherB")]

            class _Extended(ctypes.Structure):
                _fields_ = [("Basic", _Basic), ("Io", _Io), ("ProcessMemoryLimit", ctypes.c_size_t),
                            ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                            ("PeakJobMemoryUsed", ctypes.c_size_t)]

            k32 = _k32()
            job = k32.CreateJobObjectW(None, None)
            info = _Extended()
            info.Basic.LimitFlags = 0x2000 | 0x800  # KILL_ON_JOB_CLOSE | BREAKAWAY_OK
            if not job or not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
                _STATE["job"] = 0
                return None
            _STATE["job"] = job
            return job
        except Exception:
            _STATE["job"] = 0
            return None


def adopt(proc) -> bool:
    """Put a just-started child into this process's Job object (Windows). False when it could not be."""
    if os.name != "nt":
        return False
    handle = getattr(proc, "_handle", None)
    job = _job()
    if not job or handle is None:
        return False
    try:
        return bool(_k32().AssignProcessToJobObject(job, int(handle)))
    except Exception:
        return False


# -- the ledger (children.json, children.py) -----------------------------------------------------------------------

def _mine(entry: dict) -> bool:
    pid, start = me()
    if entry.get("owner_pid") != pid:
        return False
    recorded = entry.get("owner_start")
    return not recorded or not start or recorded == start


def kept(entry: dict) -> bool:
    return bool(entry.get("keep")) or (entry.get("what") or "") in KEPT_KINDS


def _entries(state_dir=None) -> list:
    from halo_harness import children as C
    try:
        rows = C.prune(state_dir)
    except Exception:
        rows = []
    return rows + [r for r in C.local_servers(state_dir) if C.alive(r)]


def _stop_line(entry: dict) -> str:
    what = entry.get("what") or "halo"
    if entry.get("source") == "local-servers":
        return f"halo local stop {entry.get('model') or entry.get('pid')}"
    try:
        from halo_harness.update_stop import stop_command
        cmd = stop_command(entry)
        if cmd:
            return cmd
    except Exception:
        pass
    return {"supervisor": "halo supervise stop", "host": "halo host stop"}.get(what, f"halo stop {entry.get('pid')}")


# -- stopping, bounded ---------------------------------------------------------------------------------------------

def _signal_tree(pid: int, hard: bool) -> None:
    """Its process group when it leads one (POSIX), else the pid; Windows: the tree (taskkill /T, /F when hard)."""
    if os.name == "nt":
        try:
            from halo_harness import subprocess_safe as sp
            sp.run(["taskkill", "/PID", str(pid), "/T"] + (["/F"] if hard else []), capture_output=True, timeout=5)
        except Exception:
            pass
        return
    sig = signal.SIGKILL if hard else signal.SIGTERM
    try:
        if os.getpgid(pid) == pid and pid != os.getpgid(0):
            os.killpg(pid, sig)
            return
    except OSError:
        pass
    try:
        os.kill(pid, sig)
    except OSError:
        pass


def _polite(entry: dict, state_dir) -> None:
    """The child's own shutdown first: Studio's stop route, a model server's stop; else SIGTERM to its group."""
    what = entry.get("what")
    try:
        if what == "studio":
            from halo_harness.studio import launch
            info = launch.read_info(Path(state_dir) if state_dir else _home())
            if info and info.get("pid") == entry.get("pid"):
                threading.Thread(target=launch._ask_shutdown, args=(info,), daemon=True).start()
                return
        elif entry.get("source") == "local-servers" and entry.get("model"):
            from halo_harness.providers.local_runtime import stop_managed_server
            threading.Thread(target=stop_managed_server, args=(entry["model"],),
                             kwargs={"state_dir": state_dir}, daemon=True).start()
            return
    except Exception:
        pass
    _signal_tree(entry["pid"], hard=False)


def _home() -> Path:
    from halo_harness.children import _state
    return _state(None)


def stop_entries(entries: list, *, state_dir=None, polite_s: float = POLITE_S, hard_s: float = HARD_S) -> list:
    """Stop these ledger entries, newest (a child's child) first: politely, then hard once `polite_s` passed, all
    inside `polite_s + hard_s`. Each is checked by pid and start time before every signal. Returns the ones gone."""
    from halo_harness import children as C
    live = [e for e in sorted(entries, key=lambda e: -(e.get("since") or 0)) if C.alive(e) and e.get("pid") != os.getpid()]
    for e in live:
        _polite(e, state_dir)
    _wait(live, polite_s)
    left = [e for e in live if C.alive(e)]
    for e in left:
        if C.alive(e):
            _signal_tree(e["pid"], hard=True)
    _wait(left, hard_s)
    gone = [e for e in live if not C.alive(e)]
    try:
        C.unregister([e["pid"] for e in gone if e.get("source") != "local-servers"], state_dir=state_dir)
    except Exception:
        pass
    return gone


def _wait(entries: list, seconds: float) -> None:
    from halo_harness import children as C
    deadline = time.monotonic() + max(0.0, seconds)
    while entries and time.monotonic() < deadline:
        if os.name != "nt":
            for e in entries:
                try:
                    os.waitpid(e["pid"], os.WNOHANG)
                except (ChildProcessError, OSError):
                    pass
        if not any(C.alive(e) for e in entries):
            return
        time.sleep(0.05)


# -- the marker scan -----------------------------------------------------------------------------------------------

def marker_pids(mark: Optional[str] = None, *, prefix: bool = False) -> "dict[int, str]":
    """{pid: marker} of the processes whose environment carries `HALO_OWNER=<mark>` (any marker with `mark` None;
    `prefix`: markers starting with it). Linux reads /proc/<pid>/environ, macOS `ps -E`; Windows has no cheap way to
    read another process's environment, so it answers {} (the Job object covers Windows)."""
    out: dict = {}
    me_pid = os.getpid()

    def take(pid: int, value: str) -> None:
        if pid == me_pid:
            return
        if mark is None or value == mark or (prefix and value.startswith(mark)):
            out[pid] = value

    if os.path.isdir("/proc") and os.path.exists("/proc/self/environ"):
        key = (MARKER + "=").encode()
        for name in os.listdir("/proc"):
            if not name.isdigit():
                continue
            try:
                with open(f"/proc/{name}/environ", "rb") as fh:
                    data = fh.read()
            except OSError:
                continue
            for item in data.split(b"\0"):
                if item.startswith(key):
                    take(int(name), item[len(key):].decode("utf-8", "replace"))
                    break
        return out
    if sys.platform == "darwin":
        try:
            import subprocess as _sp
            r = _sp.run(["/bin/ps", "-E", "-ww", "-A", "-o", "pid=,command="], capture_output=True, text=True,
                        timeout=10, env={**os.environ, "LC_ALL": "C"})
        except Exception:
            return out
        key = f" {MARKER}="
        for line in (r.stdout or "").splitlines():
            head, _sp2, rest = line.strip().partition(" ")
            if not head.isdigit() or key not in " " + rest:
                continue
            value = (" " + rest).split(key, 1)[1].split(" ", 1)[0]
            take(int(head), value)
    return out


def kill_marked(mark: str, *, exclude=(), bound_s: float = 2.0) -> list:
    """SIGTERM, then SIGKILL after half the bound, every process that carries this tree's marker (POSIX)."""
    if os.name == "nt" or not mark or mark.startswith(KEPT_PREFIX):
        return []
    found = {p: _start(p) for p in marker_pids(mark) if p not in set(exclude)}
    if not found:
        return []
    from halo_harness import children as C
    for pid in found:
        if C.same_process(pid, found[pid]):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
    deadline = time.monotonic() + bound_s / 2
    while time.monotonic() < deadline and any(C.same_process(p, s) for p, s in found.items()):
        for p in found:
            try:
                os.waitpid(p, os.WNOHANG)
            except (ChildProcessError, OSError):
                pass
        time.sleep(0.05)
    for pid, start in found.items():
        if C.same_process(pid, start):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    return list(found)


# -- the reaper (POSIX) --------------------------------------------------------------------------------------------

def ensure_reaper() -> None:
    """Start, once, the tiny process that outlives a hard kill of this one long enough to end what it started."""
    if os.name == "nt" or _STATE["reaper"] is not None or _STATE["closed"]:
        return
    with _LOCK:
        if _STATE["reaper"] is not None:
            return
        _STATE["reaper"] = 0
        pid, start = me()
        import subprocess as _sp
        argv = [sys.executable, "-I", "-S", str(Path(__file__).with_name("closing_reaper.py")), str(pid), start or "",
                marker(), str(_home()), str(Path(__file__).resolve().parent.parent)]
        env = {k: v for k, v in os.environ.items() if k != WATCH}
        try:
            proc = _sp.Popen(argv, stdin=_sp.DEVNULL, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, env=env,
                             start_new_session=True, close_fds=True)
            _STATE["reaper"] = proc
        except OSError:
            _STATE["reaper"] = 0


def _stop_reaper() -> None:
    proc = _STATE.get("reaper")
    if proc:
        try:
            proc.kill()
            proc.wait(timeout=2)
        except Exception:
            pass
    _STATE["reaper"] = 0 if proc is not None else None


# -- the closing procedure -----------------------------------------------------------------------------------------

def on_close(fn: Callable[[], None]) -> None:
    """Run `fn` first when this process closes (an MCP manager's close, a job registry's kill)."""
    _STATE["callbacks"].append(fn)


def close(*, polite_s: float = POLITE_S, hard_s: float = HARD_S, say: Optional[Callable[[str], None]] = None,
          state_dir=None) -> list:
    """THE closing procedure, idempotent; every way out runs it. Returns the lines it printed (one per thing left
    running on purpose, with the command that stops it); nothing when all is well."""
    with _LOCK:
        if _STATE["closed"]:
            return []
        _STATE["closed"] = True
    t0 = time.monotonic()
    for fn in reversed(_STATE["callbacks"]):
        try:
            fn()
        except BaseException:
            pass
    lines: list = []
    try:
        rows = [e for e in _entries(state_dir) if _mine(e)]
        stop_entries([e for e in rows if not kept(e)], state_dir=state_dir, polite_s=polite_s, hard_s=hard_s)
        lines = [f"halo: left running on purpose: {_label(e)} (pid {e['pid']}); `{_stop_line(e)}` stops it"
                 for e in rows if kept(e)]
    except Exception:
        pass
    if os.name != "nt" and _STATE["spawned"] and os.environ.get(MARKER) == my_ident():
        left = max(0.5, polite_s + hard_s - (time.monotonic() - t0))
        reaper = _STATE.get("reaper")
        kill_marked(marker(), exclude=(reaper.pid,) if reaper else (), bound_s=min(left, 2.0))
    _stop_reaper()
    out = say if say is not None else _say
    for line in lines:
        try:
            out(line)
        except Exception:
            pass
    return lines


def _label(entry: dict) -> str:
    from halo_harness import children as C
    return C.label(entry.get("what") or "halo")


def _say(line: str) -> None:
    try:
        print(line, file=sys.stderr, flush=True)
    except Exception:
        pass


def is_root() -> bool:
    """Nothing Halo runs is watching this process (it was started by a person, or to be kept)."""
    return owner() == (None, None)


# -- the sweep at start --------------------------------------------------------------------------------------------

def orphans(state_dir=None) -> list:
    """Ledger entries whose owner is gone and that nobody asked to keep. A Studio with no owner at all (what an
    older `halo init` left) counts too: there is no detached Studio."""
    from halo_harness import children as C
    out = []
    for e in _entries(state_dir):
        if e.get("pid") == os.getpid() or kept(e):
            continue
        owner = e.get("owner_pid")
        if owner is None:
            if e.get("what") == "studio":
                out.append(e)
            continue
        if not C.owner_alive(e):
            out.append(e)
    return out


def _when(entry: dict) -> str:
    since = entry.get("since")
    if not isinstance(since, (int, float)):
        return "an earlier run"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(since)))
    except (OverflowError, OSError, ValueError):
        return "an earlier run"


def sweep(state_dir=None, say: Optional[Callable[[str], None]] = None) -> list:
    """Stop every orphan (above), one line each: "halo: stopped a Studio server left from 2026-11-14 22:10"."""
    found = orphans(state_dir)
    if not found:
        return []
    gone = {e["pid"] for e in stop_entries(found, state_dir=state_dir)}
    lines = []
    for e in found:
        name = "a Studio server" if e.get("what") == "studio" else f"a {_label(e)}"
        lines.append(f"halo: {'stopped' if e['pid'] in gone else 'could not stop'} {name} left from {_when(e)}"
                     f" (pid {e['pid']})")
    out = say if say is not None else _say
    for line in lines:
        out(line)
    return lines


# -- the owner watch (a Halo child) --------------------------------------------------------------------------------

def _owner_gone_check(owner_pid: int, owner_start: Optional[str]) -> Callable[[], bool]:
    """A cheap test for "my owner is gone". POSIX direct child: the parent pid changed. Windows: a handle opened now
    (it pins the process, so a reused pid can never answer for it). Else the pid and its start time."""
    from halo_harness import children as C
    if owner_start and _start(owner_pid) not in (None, owner_start):
        return lambda: True
    if os.name != "nt" and os.getppid() == owner_pid:
        return lambda: os.getppid() != owner_pid
    if os.name == "nt":
        try:
            k32 = _k32()
            handle = k32.OpenProcess(0x00100000 | 0x1000, False, int(owner_pid))  # SYNCHRONIZE | QUERY_LIMITED
            if handle:
                if owner_start and _start(owner_pid) not in (None, owner_start):
                    return lambda: True
                return lambda: k32.WaitForSingleObject(handle, 0) == 0  # WAIT_OBJECT_0: it ended
        except Exception:
            pass
        return lambda: not C.pid_running(owner_pid)
    ticks = {"n": 0}

    def gone() -> bool:
        ticks["n"] += 1
        if not C.pid_running(owner_pid):
            return True
        if owner_start and ticks["n"] % 8 == 0:  # the start time costs a `ps` on macOS: every 2 s
            return not C.same_process(owner_pid, owner_start)
        return False
    return gone


def watch_owner(owner_pid: int, owner_start: Optional[str], *, on_gone: Optional[Callable[[], None]] = None) -> threading.Thread:
    gone = _owner_gone_check(owner_pid, owner_start)

    def loop() -> None:
        while not gone():
            time.sleep(WATCH_POLL_S)
        (on_gone or _owner_gone)()

    t = threading.Thread(target=loop, name="halo-owner-watch", daemon=True)
    t.start()
    return t


def _owner_gone() -> None:
    """The owner went: unwind the main thread (Ctrl+C's path: a Studio's serve loop ends, its `finally` runs), give
    it a second, then close from here and leave -- inside two seconds."""
    _STATE["owner_gone"] = True
    try:
        import _thread
        _thread.interrupt_main()
    except Exception:
        pass
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and not _STATE["closed"]:
        time.sleep(0.05)
    close(polite_s=0.6, hard_s=0.4, say=lambda _l: None)
    os._exit(0)


# -- install --------------------------------------------------------------------------------------------------------

_CTRL_HANDLER: list = []


def _windows_console_close() -> None:
    """A closed console window (CTRL_CLOSE_EVENT), a logoff or a shutdown: Windows gives the process a few seconds
    and runs no atexit; the closing procedure runs here (the Job object would end the children anyway)."""
    try:
        import ctypes
        from ctypes import wintypes
        handler_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

        def handler(event: int) -> bool:
            if event in (2, 5, 6):
                close(polite_s=1.5, hard_s=1.0, say=lambda _l: None)
            return False
        cb = handler_type(handler)
        _CTRL_HANDLER.append(cb)
        ctypes.WinDLL("kernel32").SetConsoleCtrlHandler(cb, True)
    except Exception:
        pass


def install(*, sweep_at_start: bool = True) -> None:
    """The real process's first call. Idempotent."""
    if _STATE["installed"]:
        return
    _STATE["installed"] = True
    watch = os.environ.get(WATCH, "")
    owner_pid, owner_start = parse_watch(watch)
    _STATE["owner"] = (owner_pid, owner_start) if owner_pid and owner_pid != os.getpid() else (None, None)
    os.environ[MARKER] = my_ident()  # what THIS process starts carries its id: a nested halo marks its own, never its parent's
    pid, start = me()
    os.environ[WATCH] = f"{pid}:{start or ''}"  # what this process starts watches it
    atexit.register(close)
    if os.name == "nt":
        _windows_console_close()
    if owner_pid and owner_pid != pid:
        watch_owner(owner_pid, owner_start)
    elif sweep_at_start:
        try:
            sweep()
        except Exception:
            pass


def reset_for_tests() -> None:
    _STATE.update(installed=False, closed=False, spawned=False, callbacks=[], owner_gone=False)
