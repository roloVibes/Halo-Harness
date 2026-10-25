"""halo_harness.children -- the processes a halo session or its tools start
to outlive a turn (Halo 3.2.2.0 R3), so a quit and `halo update` can find
and stop them.

    <state>/run/children.json  {"version": 1, "children": [entry, ...]}  0600
    entry: {pid, start_time, what, cmd, owner_pid, owner_start, since, ...}

`what` is studio | bg | schedule | supervisor (a local model server keeps
its own registry, `run/local-servers.json` in providers/local_runtime.py;
`local_servers()` reads it in the same shape and never copies it). Writers:
studio/launch.launch_detached, bg_run.start_background_run and
agents_schedule's plain-Popen fire. Writes are atomic
(privateio.write_private_atomic) under filelock.file_lock. A pid the OS
later gave to another program is told apart by `start_time`
(bg_run.process_start_time). Stopping lives in children_stop.py.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

FILENAME = "children.json"
LABELS = {"studio": ("Studio", "Studios"), "bg": ("background run", "background runs"),
          "schedule": ("schedule fire", "schedule fires"), "supervisor": ("supervisor", "supervisors"),
          "mlx": ("local model server", "local model servers"), "llama": ("local model server", "local model servers"),
          "halo": ("halo", "halo processes")}


def _state(state_dir=None) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def registry_path(state_dir=None) -> Path:
    return _state(state_dir) / "run" / FILENAME


def label(what: str, count: int = 1) -> str:
    one, many = LABELS.get(what, (what, what))
    return one if count == 1 else many


def _load(path: Path) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = data.get("children") if isinstance(data, dict) else None
    return [r for r in rows if isinstance(r, dict) and isinstance(r.get("pid"), int)] if isinstance(rows, list) else []


def _write(path: Path, rows: list) -> None:
    from halo_harness.privateio import write_private_atomic
    write_private_atomic(path, json.dumps({"version": 1, "children": rows}, indent=2, sort_keys=True))


def start_time(pid) -> Optional[str]:
    from halo_harness.bg_run import process_start_time
    return process_start_time(pid) if isinstance(pid, int) else None


def pid_running(pid) -> bool:
    """The pid names a process that has not exited (Windows: GetExitCodeProcess
    is still STILL_ACTIVE, so a handle someone keeps open on an exited process
    does not count; POSIX: bg_run.pid_alive, which also rules out a zombie)."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name != "nt":
        from halo_harness.bg_run import pid_alive
        return pid_alive(pid)
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            k32.CloseHandle(handle)
    except Exception:
        from halo_harness.bg_run import pid_alive
        return pid_alive(pid)


def same_process(pid, recorded: Optional[str]) -> bool:
    """`pid` still runs and is the process recorded (an unknown start time on
    either side cannot disprove it)."""
    if not pid_running(pid):
        return False
    if not recorded:
        return True
    current = start_time(pid)
    return current is None or current == recorded


def alive(entry: dict) -> bool:
    return same_process(entry.get("pid"), entry.get("start_time"))


def owner_alive(entry: dict) -> bool:
    owner = entry.get("owner_pid")
    return isinstance(owner, int) and same_process(owner, entry.get("owner_start"))


def spawned(proc) -> bool:
    """`proc` is a real `subprocess.Popen` (a test's stand-in never joins the registry)."""
    return type(proc).__module__ == "subprocess" and isinstance(getattr(proc, "pid", None), int)


def _short_cmd(cmd) -> list:
    if isinstance(cmd, (list, tuple)):
        return [str(c) for c in cmd]
    return str(cmd or "").split()


OWNER_ENV = "HALO_OWNER_PID"  # set by the Bash/PowerShell tools: the session a command runs under


def launcher_owner() -> Optional[int]:
    """The owner of what a short-lived launcher (`halo --bg`, `halo agents
    schedule run`) starts: the halo session whose tool ran it
    (`HALO_OWNER_PID`), else None -- a run someone started from a plain
    shell belongs to no session, so a quit leaves it (`halo update` and
    `halo bg stop` still end it)."""
    raw = os.environ.get(OWNER_ENV, "")
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


def register(pid, what: str, cmd, *, owner_pid: Optional[int] = None, launched: bool = False, state_dir=None,
             **extra) -> Optional[dict]:
    """Add (or replace) the entry for `pid`. The owner is this process, or
    `owner_pid`; `launched=True` (a short-lived launcher) takes
    `launcher_owner()`. Never raises: a registry problem never stops a spawn."""
    if not isinstance(pid, int) or pid <= 0:
        return None
    owner = launcher_owner() if launched else (os.getpid() if owner_pid is None else owner_pid)
    entry = {"pid": pid, "start_time": start_time(pid), "what": str(what), "cmd": _short_cmd(cmd),
             "owner_pid": owner, "owner_start": start_time(owner) if owner else None, "since": round(time.time(), 3)}
    entry.update({k: v for k, v in extra.items() if v is not None})
    try:
        from halo_harness.filelock import file_lock
        path = registry_path(state_dir)
        with file_lock(path):
            rows = [r for r in _load(path) if r.get("pid") != pid]
            rows.append(entry)
            _write(path, rows)
    except Exception:
        return None
    return entry


def unregister(pids, *, state_dir=None) -> None:
    gone = {pids} if isinstance(pids, int) else set(pids or ())
    if not gone:
        return
    try:
        from halo_harness.filelock import file_lock
        path = registry_path(state_dir)
        if not path.exists():
            return
        with file_lock(path):
            rows = _load(path)
            kept = [r for r in rows if r.get("pid") not in gone]
            if len(kept) != len(rows):
                _write(path, kept)
    except Exception:
        pass


def load(state_dir=None) -> list:
    return _load(registry_path(state_dir))


def prune(state_dir=None) -> list:
    """Drop every entry whose process is gone (or whose pid now belongs to
    another program, told by its start time); return the live ones."""
    path = registry_path(state_dir)
    if not path.exists():
        return []
    try:
        from halo_harness.filelock import file_lock
        with file_lock(path):
            rows = _load(path)
            live = [r for r in rows if alive(r)]
            if len(live) != len(rows):
                _write(path, live)
        return live
    except Exception:
        return [r for r in load(state_dir) if alive(r)]


def _under(path: str, root: str) -> bool:
    try:
        p = os.path.normcase(os.path.abspath(path))
        r = os.path.normcase(os.path.abspath(root))
    except (TypeError, ValueError):
        return False
    return p == r or p.startswith(r.rstrip("\\/") + os.sep)


def local_servers(state_dir=None, *, venv_only: bool = False) -> list:
    """The managed local model servers (providers/local_runtime's own
    registry, read only) as entries of this module's shape. `venv_only`:
    just the ones whose program is this install's own interpreter (they hold
    the venv an update replaces)."""
    try:
        from halo_harness.providers.local_runtime import load_registry
        rows = load_registry(_state(state_dir))
    except Exception:
        return []
    out = []
    for r in rows:
        if not isinstance(r, dict) or not isinstance(r.get("pid"), int):
            continue
        cmd = _short_cmd(r.get("cmdline") or [])
        in_venv = bool(cmd) and _under(cmd[0], sys.prefix)
        if venv_only and not in_venv:
            continue
        what = "mlx" if (r.get("runtime") or "").startswith("mlx") else "llama"
        out.append({"pid": r["pid"], "start_time": r.get("proc_start"), "what": what, "cmd": cmd,
                    "owner_pid": r.get("owner_pid"), "owner_start": r.get("owner_start"), "model": r.get("model"),
                    "keep": bool(r.get("keep")), "source": "local-servers"})
    return out
