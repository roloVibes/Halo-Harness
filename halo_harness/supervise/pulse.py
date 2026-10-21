"""halo_harness.supervise.pulse -- the supervisor's pulse file and stop file
(Halo 3.1.8.0 R1), so `halo supervise status`, Studio's Session landing and
a session arming its lineup's schedules can tell what a supervisor running in
another process does. The Signal bridge's pattern (remote/bridge_state.py).

    <state>/supervise/pulse.json  {pid, pstart, started, updated, state, goals: {queued, running, done, parked}}  0600
    <state>/supervise/stop        its existence asks the running supervisor to end (Windows has no signal for it)

`state` is starting, running, stopping or stopped. `read()` says
`running: true` only when the pid is alive AND is the process that wrote the
pulse (`pstart`, proc_ident.start_token: a pid reused after a crash or a
reboot does not count). One supervisor per state dir: a second one reads a
live pulse and says who runs.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from halo_harness.privateio import write_private_atomic
from halo_harness.remote import proc_ident

LIVE_STATES = ("starting", "running", "stopping")


def pulse_path(state_dir=None) -> Path:
    from halo_harness.supervise.queue import root
    return root(state_dir) / "pulse.json"


def stop_path(state_dir=None) -> Path:
    from halo_harness.supervise.queue import root
    return root(state_dir) / "stop"


class Pulse:
    """Written by the supervisor; every write is best-effort."""

    def __init__(self, state_dir, clock=time.time, pid: Optional[int] = None) -> None:
        self.path = pulse_path(state_dir)
        self.clock = clock
        self.pid = pid if pid is not None else os.getpid()
        self.started = round(self.clock(), 3)
        self.pstart = proc_ident.start_token(self.pid)
        self.state = "starting"

    def write(self, state: Optional[str] = None, goals: Optional[dict] = None) -> dict:
        if state is not None:
            self.state = state
        row = {"pid": self.pid, "pstart": self.pstart, "started": self.started, "updated": round(self.clock(), 3),
               "state": self.state, "goals": dict(goals or {"queued": 0, "running": 0, "done": 0, "parked": 0})}
        try:
            write_private_atomic(self.path, json.dumps(row, sort_keys=True))
        except OSError:
            pass
        return row


def read_row(state_dir=None) -> Optional[dict]:
    try:
        row = json.loads(pulse_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return row if isinstance(row, dict) else None


def read(state_dir=None) -> dict:
    """`{state, pid, started, updated, goals, running}`; `state` off when there is no pulse, stopped when its
    process is gone."""
    row = read_row(state_dir)
    if row is None:
        return {"state": "off", "pid": None, "started": None, "updated": None, "goals": {}, "running": False}
    from halo_harness.remote.bridge_state import alive
    state = str(row.get("state") or "stopped")
    running = state in LIVE_STATES and (row.get("pid") == os.getpid() or alive(row))
    return {"state": state if running else "stopped", "pid": row.get("pid"), "started": row.get("started"),
            "updated": row.get("updated"), "goals": row.get("goals") or {}, "running": running}


def live(state_dir=None) -> bool:
    """A supervisor runs for this state dir right now."""
    return read(state_dir)["running"]


def request_stop(state_dir=None) -> bool:
    """Create the stop file; True when a live supervisor was there to see it."""
    try:
        write_private_atomic(stop_path(state_dir), "stop\n")
    except OSError:
        return False
    return live(state_dir)


def clear_stop(state_dir=None) -> None:
    try:
        stop_path(state_dir).unlink()
    except OSError:
        pass


def stop_requested(state_dir=None) -> bool:
    return stop_path(state_dir).exists()
