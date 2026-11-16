"""halo_harness.bg_run -- W4a/W5 CLI flags: `--bg`/`--background` (spawn
this same invocation detached, print an id + log path, state under
`<state>/bg/<id>/{output.log,meta.json}`) and `--tmux` (re-exec inside a
new tmux window when tmux exists; no iTerm2-native-pane backend). W5
(carried from W4a) adds the read/manage side over those SAME run
directories -- `list_runs`/`pid_alive`/`kill_pid` below, driven by
`bg_cli.cmd_bg`'s own `halo bg list|logs|stop|rm` (kept in a separate
module, same split as `mcp_setup.py`/`mcp_cli.py`: this file stays
argparse-free and directly unit-testable).

Kept as its own module (not inline in cli.py) so both are unit-testable
without going through argparse/subprocess-spawning-a-real-python at all --
`start_background_run`'s own argv-to-Popen-args translation and `run_in_tmux`'s
tmux-missing fallback are the parts worth pinning directly.
"""

from __future__ import annotations

from halo_harness.selfexec import python_argv  # 3.6.0.0 R10: never the working folder's copy
import calendar
import json
import os
from halo_harness import subprocess_safe as subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional


def _bg_root() -> Path:
    from halo_harness.config.paths import bridge_home
    return bridge_home() / "bg"


def start_background_run(argv: list, *, popen=subprocess.Popen, stdin_data: Optional[bytes] = None,
                         env: Optional[dict] = None, cwd: Optional[str] = None, launched: bool = False) -> dict:
    """Spawns `[sys.executable, -m halo_harness] + argv` (forcing `-p` when
    neither `-p` nor `--print` is already present -- a detached child has no
    terminal a TUI could ever render into), stdout+stderr merged into
    `<state>/bg/<id>/output.log`, stdin closed. Returns `{"id", "log_path",
    "pid", "meta_path"}` immediately -- never waits for the child. `popen`
    is a seam: a test substitutes a fake to avoid actually launching a real
    Python process for every invocation shape it wants to check.

    finding 15 (W6a): the REAL command is launched through `_bg_wrapper`
    (this process's own pid, recorded in `meta.json`, is the WRAPPER's --
    killing its group takes the real command with it, unchanged from
    before) so it can write `status.json` once the real command actually
    exits; `meta.json` also records `start_time` (`process_start_time`),
    so a PID the OS later reuses for something unrelated is never
    mistaken for this run still being alive. 3.1.8.0 R1: `cwd` (default
    this process's folder) is the folder the run starts in (a supervised
    job goal's repo). 3.2.2.0 R3: the run joins children.json; `launched`
    (the `halo --bg` launcher, which exits at
    once) records the halo session whose tool ran them as its owner, or
    none for a plain shell (children.launcher_owner)."""
    run_id = uuid.uuid4().hex[:8]
    run_dir = _bg_root() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "output.log"
    meta_path = run_dir / "meta.json"
    status_path = run_dir / "status.json"

    forced_argv = list(argv)
    if "-p" not in forced_argv and "--print" not in forced_argv:
        forced_argv = forced_argv + ["-p"]
    real_command = [*python_argv(), *forced_argv]
    command = [*python_argv("halo_harness._bg_wrapper"), str(status_path), *real_command]

    log_fh = open(log_path, "ab")
    # review finding 91: piped input (`echo task | halo --bg -p`) is spooled
    # to a file in the run directory and handed to the child as its stdin;
    # the child used to get the null device and saw an empty prompt.
    stdin_fh = None
    if stdin_data is not None:
        (run_dir / "stdin.bin").write_bytes(stdin_data)
        stdin_fh = open(run_dir / "stdin.bin", "rb")
    from halo_harness.closing import kept_kwargs  # 3.6.0.0 R10: a `--bg` run was asked to outlive its starter
    kept = kept_kwargs({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}, env=env)
    try:
        proc = popen(
            command, cwd=str(cwd or Path.cwd()), stdout=log_fh, stderr=subprocess.STDOUT,
            stdin=stdin_fh if stdin_fh is not None else subprocess.DEVNULL,
            env=kept["env"],
            # review finding 37: CREATE_NEW_PROCESS_GROUP alone still
            # leaves this child attached to the launching console --
            # Windows sends CTRL_CLOSE_EVENT to every process attached to
            # a closing console, killing it the moment that terminal
            # window closes, unlike the POSIX path's `start_new_session`
            # (a real new session, survives the launching terminal
            # closing by construction). A console of its own detaches it
            # from the launching one, same intent as `start_new_session` on
            # POSIX: closing.kept_kwargs gives CREATE_NO_WINDOW (3.6.0.0 fx:
            # DETACHED_PROCESS made a venv launcher's interpreter open a
            # visible terminal window) + CREATE_BREAKAWAY_FROM_JOB.
            creationflags=kept.get("creationflags", 0) if os.name == "nt" else 0,
            start_new_session=(os.name != "nt"),
        )
    finally:
        log_fh.close()  # the CHILD inherited its own duplicate fd; this process's copy is done with it
        if stdin_fh is not None:
            stdin_fh.close()

    from halo_harness import children
    meta = {"id": run_id, "pid": proc.pid, "command": real_command, "cwd": str(cwd or Path.cwd()),
            "started": time.time(), "log_path": str(log_path), "status_path": str(status_path),
            "start_time": children.read_start(proc.pid)}
    try:
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except OSError:
        pass
    if children.spawned(proc):  # 3.2.2.0 R3: a quit / `halo update` finds it (children.py)
        children.register(proc.pid, "bg", real_command, launched=launched, bg_id=run_id, keep=True,
                          start=meta["start_time"])
    return {"id": run_id, "log_path": str(log_path), "pid": proc.pid, "meta_path": str(meta_path)}


def process_start_time(pid: int) -> Optional[str]:
    """finding 15 (W6a): an opaque, re-readable "when did THIS pid start"
    fingerprint -- never a real timestamp a caller should interpret, just
    a value that stays the same for the SAME still-running process and
    differs once the OS reuses that pid for something else entirely.
    `/proc/<pid>/stat` field 22 (starttime) on Linux; the creation
    `FILETIME` from `GetProcessTimes` on Windows. `None` when it can't be
    determined at all (an unsupported platform, or the process is already
    gone) -- callers treat that as "can't tell, don't refuse on it
    alone", same as a pre-upgrade `meta.json` with no `start_time` key."""
    if not isinstance(pid, int) or pid <= 0:
        return None
    if os.name == "nt":
        return _windows_process_start_time(pid)
    if no_proc():
        return _ps_process_start_time(pid)  # macOS and the BSDs have no /proc
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        # `comm` (field 2, in parens) can itself contain spaces/parens --
        # same `rsplit(")", 1)` trick `pid_alive` above already uses for
        # the state field. Fields from "state" (3) onward are then
        # `after[0]`, `after[1]`, ...; starttime is field 22, so index 19.
        after = content.rsplit(")", 1)[-1].split()
        return after[19]
    except (OSError, IndexError, ValueError):
        return None


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def start_epoch(text, *, windows: Optional[bool] = None) -> Optional[float]:
    """3.6.0.1: the wall-clock second a start time of `process_start_time` names, where the text carries one: the
    creation FILETIME on Windows (100 ns since 1601), a `ps:` lstart read in UTC. None for anything else (Linux's
    /proc ticks count from boot: children.py compares those with CLOCK_BOOTTIME instead) or a text it cannot read."""
    if not text:
        return None
    text = str(text)
    if text.startswith("ps:"):
        parts = text[3:].split()  # "Mon Oct  5 10:00:00 2026" (C locale, read with TZ=UTC0)
        try:
            h, m, s = (int(x) for x in parts[3].split(":"))
            return float(calendar.timegm((int(parts[4]), _MONTHS.index(parts[1][:3]) + 1, int(parts[2]), h, m, s)))
        except (IndexError, ValueError):
            return None
    if (os.name == "nt" if windows is None else windows) and text.isdigit():
        return int(text) / 1e7 - 11644473600
    return None


def no_proc() -> bool:
    """POSIX with no /proc (macOS, the BSDs): process identity and liveness are read from `ps`. HALO_TEST_NO_PROC=1
    (tests only, read here alone) makes a Linux box take the same path, so the macOS closing procedure runs there."""
    return os.name != "nt" and (os.environ.get("HALO_TEST_NO_PROC") == "1" or not os.path.exists("/proc/self/stat"))


PS_TTL_S = 1.5  # how long one `ps` look at a pid answers for it (macOS, the BSDs)
_PS_SEEN: dict = {}  # pid -> (monotonic time, stat, lstart text)


def ps_forget(pid) -> None:
    """The next look at `pid` runs `ps` again (the proof before a signal is always a fresh read)."""
    _PS_SEEN.pop(pid, None)


def _ps_look(pid: int, *, local: bool = False) -> "tuple[Optional[str], Optional[str]]":
    """(state, start time text) of `pid` from ONE `ps` where there is no /proc, kept for PS_TTL_S: the closing
    procedure's watchers look several times a second and every look started a `ps` (3.6.0.0 fx). The start time is
    read in UTC (`local`: in this process's own zone, how a 3.5 Halo recorded it): `lstart` is local-time text, so a
    zone that differs between two reads (a laptop that travels, TZ set in one shell) made a live process read as
    another. (None, None): unknown; ("", None): no such process."""
    now = time.monotonic()
    if not local and (hit := _PS_SEEN.get(pid)) and now - hit[0] < PS_TTL_S:
        return hit[1], hit[2]
    env = subprocess.Probe({**os.environ, "LC_ALL": "C", "LANG": "C"})  # Halo's own look: not a spawn (3.6.0.1)
    if not local:
        env["TZ"] = "UTC0"
    try:
        result = subprocess.run(["ps", "-o", "stat=", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True,
                                timeout=5, env=env)
    except (OSError, subprocess.SubprocessError):
        return None, None
    parts = (result.stdout or "").split()
    if result.returncode != 0 or not parts:
        _PS_SEEN.pop(pid, None)
        return "", None
    # `lstart` is always five fields ("Mon Oct  5 10:00:00 2026", the day padded on macOS); the state is what is before
    stat, start = " ".join(parts[:-5]), " ".join(parts[-5:])
    if not local:
        if len(_PS_SEEN) > 256:
            _PS_SEEN.clear()
        _PS_SEEN[pid] = (now, stat, start)
    return stat, start


def _ps_process_start_time(pid: int, *, local: bool = False) -> Optional[str]:
    """review finding 87: the start time from `ps -o lstart=` where there
    is no /proc (macOS). Without it `process_start_time` was always None
    there, so the PID-reuse guard in `is_our_process` could never refuse
    anything and `halo bg stop` could kill an unrelated process group."""
    text = _ps_look(pid, local=local)[1]
    return f"ps:{text}" if text else None


def start_matches(pid, recorded: Optional[str], current: Optional[str]) -> bool:
    """`current` (read now) is the start time `recorded`: equal, or -- a `ps:` text a 3.5 Halo recorded in its own
    time zone -- equal to this pid's start read in this process's zone."""
    if current == recorded:
        return True
    return (bool(recorded) and str(recorded).startswith("ps:") and current is not None and isinstance(pid, int)
            and _ps_process_start_time(pid, local=True) == recorded)


def _windows_process_start_time(pid: int) -> Optional[str]:
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            creation, exit_t, kernel_t, user_t = (wintypes.FILETIME(), wintypes.FILETIME(),
                                                     wintypes.FILETIME(), wintypes.FILETIME())
            ok = kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_t),
                                            ctypes.byref(kernel_t), ctypes.byref(user_t))
            if not ok:
                return None
            return str((creation.dwHighDateTime << 32) | creation.dwLowDateTime)
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None


def is_our_process(meta: dict) -> bool:
    """finding 15 (W6a): `pid_alive(meta["pid"])` alone answers "is SOME
    process using this pid right now" -- true even once the OS has
    reassigned it to something this run never spawned. Refuses that case
    whenever `meta["start_time"]` (recorded at spawn) and a FRESH
    `process_start_time` for the SAME pid disagree; a run recorded before
    this field existed, or a platform/moment where it can't be read at
    all, falls back to the pid-only check rather than a false refusal."""
    pid = meta.get("pid")
    if not pid_alive(pid):
        return False
    # The wrapper writes `status.json` when the real command exits, so its
    # presence means this run is over whatever now owns the pid (covers a
    # run recorded without a start time).
    status_path = meta.get("status_path")
    if status_path and os.path.exists(status_path):
        return False
    expected = meta.get("start_time")
    if not expected:
        return True
    current = process_start_time(pid)
    return current is None or start_matches(pid, expected, current)


def list_runs() -> "list[dict]":
    """Every `<state>/bg/<id>/meta.json`, oldest first, each with its own
    directory under `run_dir` -- a run directory with no readable
    `meta.json` (never written, or corrupted) is silently skipped, same
    degrade-gracefully contract every small-JSON-file loader in this
    codebase already has."""
    root = _bg_root()
    if not root.is_dir():
        return []
    out: "list[dict]" = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        try:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(meta, dict):
            continue
        meta = dict(meta)
        meta["run_dir"] = str(d)
        out.append(meta)
    return out


def load_run(run_id: str) -> Optional[dict]:
    """One run's own meta dict (plus `run_dir`), or `None` for an unknown
    id -- never raises."""
    try:
        meta = json.loads((_bg_root() / run_id / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict):
        return None
    meta = dict(meta)
    meta["run_dir"] = str(_bg_root() / run_id)
    return meta


def pid_alive(pid: int) -> bool:
    """Liveness of a PID this process never spawned: Windows, its own exit code (process_alive, 3.4.1.1), else `tasklist`
    (one slower than its timeout is unknown, never dead); POSIX, a signal-0 probe."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():  # 3.6.0.0 fx: this process is alive; macOS paid a `ps` to learn it
        return True
    if os.name == "nt":
        from halo_harness.process_alive import win_alive
        if (got := win_alive(pid)) is not None:
            return got
        try:
            result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError) as e:
            return isinstance(e, subprocess.TimeoutExpired)
        return str(pid) in (result.stdout or "")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        _PS_SEEN.pop(pid, None)  # gone: a later process given this pid is looked at afresh
        return False
    except PermissionError:
        return True  # exists, just owned by someone else -- still alive
    except OSError:
        return False
    # A zombie (exited, not yet reaped) still answers kill(pid, 0); Linux
    # exposes its state in /proc, and a zombie is not alive for our purposes.
    if no_proc():
        return not _ps_zombie(pid)  # 3.6.0.0 R12: macOS has no /proc
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8", errors="replace") as fh:
            state = fh.read().rsplit(")", 1)[-1].split()[0]
        return state != "Z"
    except (OSError, IndexError, ValueError):
        if os.path.isdir("/proc/self"):  # 3.6.0.0 R10: /proc has it no more -- it was reaped between the two looks
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            except OSError:
                pass
        return True
    except OSError:
        return False


def _ps_zombie(pid: int) -> bool:
    """3.6.0.0 R12: on a POSIX system without /proc (macOS, the BSDs) `ps` says whether `pid` is a zombie -- a
    session that ended but whose parent has not reaped it read as alive there, so Studio waited on it for ever.
    Unknown (no ps, a timeout) is not a zombie. One `ps` look answers for PS_TTL_S (it also holds the start time).
    3.6.0.0 fx: macOS reads the kernel's record first (no `ps` started); `ps` only when that cannot be read."""
    if (zombie := _kinfo_zombie(pid)) is not None:
        return zombie
    return (_ps_look(pid)[0] or "").upper().startswith("Z")


_LIBC = None


def _darwin_kinfo(pid: int) -> Optional[bytes]:
    """macOS: the kernel's record of `pid` (sysctl CTL_KERN.KERN_PROC.KERN_PROC_PID, a struct kinfo_proc) with no
    process started. b"": no such process; None: not readable."""
    global _LIBC
    try:
        import ctypes
        import ctypes.util
        if _LIBC is None:
            lib = ctypes.CDLL(ctypes.util.find_library("c") or "libc.dylib", use_errno=True)
            lib.sysctl.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_uint, ctypes.c_void_p,
                                   ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t]
            lib.sysctl.restype = ctypes.c_int
            _LIBC = lib
        mib = (ctypes.c_int * 4)(1, 14, 1, int(pid))
        buf = ctypes.create_string_buffer(2048)
        size = ctypes.c_size_t(len(buf))
        if _LIBC.sysctl(mib, 4, buf, ctypes.byref(size), None, 0) != 0:
            return None
        return buf.raw[:size.value]
    except Exception:
        return None


_KINFO_READ = _darwin_kinfo if sys.platform == "darwin" else None


def _kinfo_zombie(pid: int) -> Optional[bool]:
    """Whether `pid` is a zombie by the kernel's record (kp_proc.p_stat at 36 == SZOMB 5, checked by kp_proc.p_pid at
    40); None when there is no reader or the record is not one this reader knows (then `ps` answers)."""
    read = _KINFO_READ
    raw = read(pid) if read is not None else None
    if raw is None:
        return None
    if not raw:
        return False  # gone since kill(pid, 0): no zombie either
    if len(raw) < 44 or int.from_bytes(raw[40:44], sys.byteorder, signed=True) != pid:
        return None
    return raw[36] == 5


def kill_pid(pid: int) -> bool:
    """Best-effort kill of a background run's own process TREE by bare PID
    (`halo bg stop`/`rm --force`) -- reuses `tools/_proc.py`'s own Windows
    orphan-grandchild-aware tree kill (the SAME one `agent.jobs.JobRegistry.
    kill` already uses for a live Bash job, just driven by a bare pid here
    instead of a live `Popen` handle, since this process never spawned the
    one it's stopping). Never raises; returns whether the process looks
    gone afterward."""
    if not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
        return False  # never ourselves
    if os.name == "nt":
        try:
            from halo_harness.tools._proc import _kill_process_tree_windows
            _kill_process_tree_windows(pid)
        except Exception:
            pass
    else:
        import signal
        # A real `--bg` run lives in its own session (start_new_session), so
        # killing its process group is the right tree kill. A pid that is NOT
        # in its own group -- one that shares THIS process's group -- must be
        # killed alone: killpg there would take down the caller too (seen on
        # Linux: a test's plain child in the suite runner's own group ended
        # the whole runner, its wrapper shell and the SSH session).
        try:
            target_pgid = os.getpgid(pid)
        except (ProcessLookupError, OSError):
            target_pgid = None
        own_pgid = os.getpgid(0)
        try:
            if target_pgid is not None and target_pgid != own_pgid and target_pgid == pid:
                os.killpg(target_pgid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        # Reap it when it is our own child so it does not linger as a zombie
        # (a pid we never spawned is not ours to wait for).
        try:
            os.waitpid(pid, 0)
        except (ChildProcessError, OSError):
            pass
    return not pid_alive(pid)


def run_in_tmux(argv: list, *, which=None, call=subprocess.call) -> Optional[int]:
    """`None` when `tmux` isn't on PATH (the caller falls back to an
    ordinary in-process launch and prints its own notice) -- otherwise
    blocks for the whole tmux session's life and returns its exit code,
    exactly like the in-process launch it replaces would have."""
    import shutil
    which = which or shutil.which
    tmux_path = which("tmux")
    if not tmux_path:
        return None
    # 3.6.0.0 R10 (judge item 4): a tmux server this starts keeps the environment it was given for every later pane;
    # Halo's owner variables must not be in it (a later `halo` in a pane would watch a halo that is long gone).
    from halo_harness.closing import scrubbed_env
    import tempfile
    env = scrubbed_env()
    # 3.6.0.0 fx: a tmux server already running starts the session with ITS environment, not this shell's (keys and
    # HALO_* switches exported here were not seen). The session takes this shell's from a private file (never a value
    # in argv), deleted as it is read (take_tmux_env); the pane's own TMUX / TERM stay tmux's.
    fd, path = tempfile.mkstemp(prefix="halo-tmux-env-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({k: v for k, v in env.items() if k not in _PANE_KEYS}, fh)
        command = [tmux_path, "new-session", "env", f"{TMUX_ENV}={path}", *python_argv(), *argv]
        return call(command, env=env)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


TMUX_ENV = "HALO_TMUX_ENV"
_PANE_KEYS = ("TMUX", "TMUX_PANE", "TERM", "TERM_PROGRAM", "TERM_PROGRAM_VERSION", "COLORTERM")


def take_tmux_env() -> bool:
    """In a session `halo --tmux` started: this process's environment becomes the one of the shell that ran it (the
    file run_in_tmux wrote, deleted here), keeping the pane's own TMUX / TERM. True when it did."""
    path = os.environ.pop(TMUX_ENV, None)
    if not path or "TMUX" not in os.environ:
        return False
    try:
        st = os.lstat(path)
        if os.name != "nt" and (st.st_uid != os.getuid() or st.st_mode & 0o077):
            return False  # only this user's own private file
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return False
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if not isinstance(data, dict):
        return False
    pane = {k: os.environ[k] for k in _PANE_KEYS if k in os.environ}
    os.environ.clear()
    os.environ.update({str(k): str(v) for k, v in data.items()})
    os.environ.update(pane)
    return True
