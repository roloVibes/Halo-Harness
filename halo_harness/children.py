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
          "host": ("LAN host", "LAN hosts"), "steward": ("duty steward", "duty stewards"),
          "update": ("updater", "updaters"), "terminal": ("terminal window", "terminal windows"),
          "schedule": ("schedule fire", "schedule fires"), "supervisor": ("supervisor", "supervisors"),
          "mlx": ("local model server", "local model servers"), "llama": ("local model server", "local model servers"),
          "halo": ("halo", "halo processes"), "pool": ("pool server", "pool servers"),
          "rpc": ("rpc-server", "rpc-servers"), "pack": ("pack helper", "pack helpers"),
          "shell": ("shell command", "shell commands"),
          "browser": ("browser", "browsers"), "guest": ("Claude Code bridge", "Claude Code bridges")}


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
    from halo_harness.bg_run import pid_alive  # 3.4.1.1: Windows asks process_alive.win_alive first, there too
    return pid_alive(pid)


def same_process(pid, recorded: Optional[str]) -> bool:
    """`pid` still runs and is the process recorded (an unknown start time on
    either side cannot disprove it)."""
    if not pid_running(pid):
        return False
    if not recorded:
        return True
    current = start_time(pid)
    from halo_harness.bg_run import start_matches
    return current is None or start_matches(pid, recorded, current)


def provably_same(pid, recorded: Optional[str], *, tries: int = 1) -> bool:
    """3.6.0.0 R10: the proof a signal needs -- `pid` runs AND its start time is read now AND equals the one recorded.
    An unreadable start time on either side is not a match: Halo never signals on a pid alone. Where `ps` is read
    (macOS) the read is a fresh one, never the look kept for the watchers. `tries`: read again (0.3 s apart) while
    the pid runs and its start time is unreadable (a `ps` past its time limit while a large model loads)."""
    if not recorded:
        return False
    import time
    from halo_harness.bg_run import ps_forget, start_matches
    for attempt in range(max(1, tries)):
        if attempt:
            time.sleep(0.3)
        ps_forget(pid)
        if not pid_running(pid):
            return False
        current = start_time(pid)
        if current is not None:
            return start_matches(pid, recorded, current)
    return False


def read_start(pid, tries: int = 3) -> Optional[str]:
    """3.6.0.1: `start_time(pid)`, read again (0.3 s apart) while the pid runs and the read is None (a `ps` past its
    time limit while a large model loads). None at once for a pid that is not running."""
    for attempt in range(max(1, tries)):
        if attempt:
            time.sleep(0.3)
        got = start_time(pid)
        if got is not None or not pid_running(pid):
            return got
    return None


def boot_clock() -> Optional[float]:
    """Seconds since boot, suspend included, on the clock Linux's /proc starttime counts in (CLOCK_BOOTTIME, also
    inside a time namespace); None where start times are not /proc ticks (Windows, macOS, HALO_TEST_NO_PROC)."""
    from halo_harness.bg_run import no_proc
    if os.name == "nt" or no_proc() or not hasattr(time, "CLOCK_BOOTTIME"):
        return None
    try:
        return round(time.clock_gettime(time.CLOCK_BOOTTIME), 3)
    except OSError:
        return None


NEWER_MARGIN_S = 2.0


def newer_than_row(entry: dict) -> bool:
    """3.6.0.1: a row with no recorded start time whose pid now runs a process that provably started AFTER the row
    was written -- another program the OS gave that pid to. `since` is written only once the process exists, so the
    recorded process started at or before it; a live start more than NEWER_MARGIN_S later cannot be it. Windows (the
    creation FILETIME) and macOS (`ps` lstart in UTC) keep the start as wall time; Linux compares /proc ticks with
    the row's CLOCK_BOOTTIME `since_boot` (a wall-clock step moves /proc/stat's btime), and a Linux row without it
    is not provable. Anything unreadable is not provable (False): the row stays (`halo ps --forget` clears it)."""
    if entry.get("start_time"):
        return False
    pid = entry.get("pid")
    live = start_time(pid)
    if not live:
        return False
    from halo_harness.bg_run import no_proc, start_epoch
    if os.name != "nt" and not no_proc() and not live.startswith("ps:"):  # Linux /proc: ticks since boot
        mark = entry.get("since_boot")
        if not isinstance(mark, (int, float)) or isinstance(mark, bool) or not live.isdigit():
            return False
        try:
            return int(live) / os.sysconf("SC_CLK_TCK") > mark + NEWER_MARGIN_S
        except (ValueError, OSError, ZeroDivisionError):
            return False
    since, epoch = entry.get("since"), start_epoch(live)
    return (epoch is not None and isinstance(since, (int, float)) and not isinstance(since, bool)
            and epoch > since + NEWER_MARGIN_S)


def alive(entry: dict) -> bool:
    """The row's process still runs: its pid, its recorded start time; a row with none is dropped once the pid
    provably runs another program (`newer_than_row`)."""
    return same_process(entry.get("pid"), entry.get("start_time")) and not newer_than_row(entry)


def owner_alive(entry: dict) -> bool:
    owner = entry.get("owner_pid")
    return isinstance(owner, int) and same_process(owner, entry.get("owner_start"))


def spawned(proc) -> bool:
    """`proc` is a real `subprocess.Popen`, the standard one or subprocess_safe's subclass of it (a test's stand-in
    never joins the registry). 3.6.0.0 fx: the subclass is what Halo's own spawns use (`halo --bg` was never listed)."""
    from halo_harness.subprocess_safe import STDLIB_POPEN
    return (isinstance(proc, STDLIB_POPEN) and type(proc).__module__ in ("subprocess", "halo_harness.subprocess_safe")
            and isinstance(getattr(proc, "pid", None), int))


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


def in_session() -> bool:
    """3.4.1.1 (48): this process is a halo session (a TUI or headless row of run/sessions.json), so what it starts
    is its own; a shell command's (`halo init`) is not."""
    try:
        from halo_harness.remote import registry
        rows = registry._load(registry.registry_path())
    except Exception:
        return False
    return any(r.get("pid") == os.getpid() and (r.get("kind") or "tui") in ("tui", "headless") for r in rows)


def register(pid, what: str, cmd, *, owner_pid: Optional[int] = None, launched: bool = False, state_dir=None,
             start: Optional[str] = None, owner_start: Optional[str] = None, **extra) -> Optional[dict]:
    """Add (or replace) the entry for `pid`. The owner is this process, or
    `owner_pid`; `launched=True` (a short-lived launcher) takes
    `launcher_owner()`. Never raises: a registry problem never stops a spawn.
    3.6.0.1: `start` / `owner_start`: a start time the caller already holds (studio.json's `pstart`); otherwise it
    is read, again while unreadable (`read_start`). A pid that no longer runs is not written (None): its row is the
    one that comes back to life once the OS gives the pid to another program."""
    if not isinstance(pid, int) or pid <= 0:
        return None
    if not start:
        start = read_start(pid)
        if start is None and not pid_running(pid):
            return None
    owner = launcher_owner() if launched else (os.getpid() if owner_pid is None else owner_pid)
    if owner and not owner_start:
        owner_start = read_start(owner)
    entry = {"pid": pid, "start_time": start, "what": str(what), "cmd": _short_cmd(cmd),
             "owner_pid": owner, "owner_start": owner_start if owner else None, "since": round(time.time(), 3)}
    boot = boot_clock()
    if boot is not None:
        entry["since_boot"] = boot
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
                    "keep": bool(r.get("keep")), "source": "local-servers", "since": _epoch(r.get("started"))})
    return out


def _epoch(iso) -> Optional[float]:
    """A local-servers row's `started` (ISO text, written once the server process exists) as `since`."""
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(iso)).timestamp() if iso else None
    except (TypeError, ValueError, OverflowError, OSError):
        return None
