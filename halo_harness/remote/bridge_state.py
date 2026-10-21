"""halo_harness.remote.bridge_state -- the bridge's pulse file and stop file
(Halo 2.0.9 round 4), so `halo remote signal status`, the `/remote` dialog
and `halo doctor` can say what a bridge running in another process is doing.

    <remote>/bridge.json   {pid, pstart, started, state, until, updated}   0600
    <remote>/stop          its existence asks a running bridge to end

`state` is what the bridge last wrote: starting, connected, rate-limited
(until `until`, a unix time) or stopped. `read()` turns that into what a
viewer should show: off (no file), starting, connected, rate-limited or
stopped; a file whose process is gone reads as stopped. `pstart` is the
process's own start record (proc_ident.start_token): a PID the system handed
to another process after a crash or a reboot does not read as this bridge.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from halo_harness.privateio import write_private_atomic
from halo_harness.remote import proc_ident
from halo_harness.remote.signal_config import remote_dir

STATES = ("off", "starting", "connected", "rate-limited", "stopped")


def state_path() -> Path:
    return remote_dir() / "bridge.json"


def stop_path() -> Path:
    return remote_dir() / "stop"


class BridgeState:
    """Written by the bridge process; every write is best-effort."""

    def __init__(self, path: Optional[Path] = None, clock=time.time, pid: Optional[int] = None) -> None:
        self.path = Path(path) if path else state_path()
        self.clock = clock
        self.pid = pid if pid is not None else os.getpid()
        self.started = self.clock()
        self.pstart = proc_ident.start_token(self.pid)
        self.state, self.until = "starting", 0.0

    def write(self, state: Optional[str] = None, until: Optional[float] = None) -> None:
        if state is not None:
            self.state = state
        if until is not None:
            self.until = until
        row = {"pid": self.pid, "pstart": self.pstart, "started": self.started, "state": self.state, "until": self.until,
               "updated": self.clock()}
        try:
            write_private_atomic(self.path, json.dumps(row, sort_keys=True))
        except OSError:
            pass


BOOT_SLACK_S = 5.0


def _alive(row: dict) -> bool:
    """The pulse's process is running AND is the bridge that wrote it."""
    pid = row.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return False
    from halo_harness.remote.registry import pid_alive
    if not pid_alive(pid):
        return False
    want = row.get("pstart")
    if want:
        have = proc_ident.start_token(pid)
        if have is not None:
            return have == want
    started, boot = row.get("started"), proc_ident.boot_time()
    if isinstance(started, (int, float)) and boot is not None and started < boot - BOOT_SLACK_S:
        return False  # written before this boot: the PID now belongs to something else
    return True


alive = _alive  # 3.1.8.0 R1: the supervisor's pulse (supervise/pulse.py) is checked the same way


def read(path: Optional[Path] = None, now: Optional[float] = None) -> dict:
    """`{state, pid, started, until, running}`; `state` is one of STATES."""
    try:
        row = json.loads(Path(path or state_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        row = None
    if not isinstance(row, dict):
        return {"state": "off", "pid": None, "started": None, "until": 0.0, "running": False}
    pid, state = row.get("pid"), str(row.get("state") or "stopped")
    alive = state in ("starting", "connected", "rate-limited") and _alive(row)
    if state not in STATES or not alive:
        state = "stopped"
    until = float(row.get("until") or 0.0)
    if state == "rate-limited" and until <= (time.time() if now is None else now):
        state = "connected"
    return {"state": state, "pid": pid, "started": row.get("started"), "until": until, "running": alive}


def request_stop() -> bool:
    """Create the stop file; True when a live bridge was there to see it."""
    try:
        write_private_atomic(stop_path(), "stop\n")
    except OSError:
        return False
    return read()["running"]


def clear_stop() -> None:
    try:
        stop_path().unlink()
    except OSError:
        pass


def stop_requested() -> bool:
    return stop_path().exists()
