"""halo_harness.studio.init_waiting -- "a `halo init` terminal is waiting for Setup's Done" (Halo 3.3.15.0 R6).

`halo init` on a terminal opens Setup in Studio and waits there for Done (halo_harness/init_wait.py); while it waits it
keeps one small record in the state dir, so Studio's Done knows whether a terminal will start halo:

    <state dir>/setup-wait.json   {"pid": <the init process>, "since": <iso utc>, "cwd": <where init ran>, "home": <hash>}

    mark(state_dir, cwd)   write the record (init, as the wait begins)
    clear(state_dir)       remove it when it is this process's (init, as the wait ends: Done, Ctrl+C, Studio gone)
    waiting(state_dir)     the record while its process is alive, else None (a stale one from a killed init is removed)

`POST setup/done` (studio/setup_done.py) reads `waiting`: a live record answers "halo is starting in your terminal";
none, and Studio opens a terminal running halo itself (studio/halo_terminal.py) or says it cannot. Nothing secret is in
the record.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

RECORD = "setup-wait.json"


def _path(state_dir=None) -> Path:
    from halo_harness.studio.setup_done import _dir
    return _dir(state_dir) / RECORD


_SEEN: dict = {}  # pid -> (monotonic time, alive): `GET setup/state` is read once a second while init waits
SEEN_S = 3.0


def alive(pid) -> bool:
    """Whether `pid` runs (bg_run.pid_alive: on Windows its exit code; kept SEEN_S seconds); this process at once."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    now = time.monotonic()
    hit = _SEEN.get(pid)
    if hit and now - hit[0] < SEEN_S:
        return hit[1]
    from halo_harness.bg_run import pid_alive
    _SEEN.clear()
    _SEEN[pid] = (now, pid_alive(pid))
    return _SEEN[pid][1]


def mark(state_dir=None, cwd=None) -> Path:
    from halo_harness.studio.setup_done import now_iso
    from halo_harness.studio.setup_state import home_id
    path = _path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(RECORD + ".tmp")
    tmp.write_text(json.dumps({"pid": os.getpid(), "since": now_iso(), "cwd": str(cwd or Path.cwd()),
                               "home": home_id(path.parent)}) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _read(state_dir=None) -> Optional[dict]:
    try:
        data = json.loads(_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def clear(state_dir=None) -> bool:
    """Remove the record when it is this process's (another init's record stays); True when one went."""
    data = _read(state_dir)
    if not data or data.get("pid") != os.getpid():
        return False
    try:
        _path(state_dir).unlink()
        return True
    except OSError:
        return False


def waiting(state_dir=None) -> Optional[dict]:
    """The record while its `halo init` still runs; a record whose process is gone is removed and reads as None."""
    data = _read(state_dir)
    if not data:
        return None
    if alive(data.get("pid")):
        return data
    try:
        _path(state_dir).unlink()
    except OSError:
        pass
    return None
