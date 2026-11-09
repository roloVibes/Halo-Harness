"""halo_harness.supervise.single -- one supervisor per state folder (Halo 3.3.13.1, plans/REVIEW-2026-11.md #16,
CORE-2). "One supervisor" was a read of pulse.json then a write: two starts inside that window (a logon unit and
`halo update`'s `supervise --daemon`, or two quick starts by hand) both ran, each starting every pack service and
the same queued goal.

`take(state_dir)` takes an exclusive OS lock on `<state>/supervise/supervisor.lock` (msvcrt on Windows, flock
elsewhere, halo_harness/filelock.py) and holds it until `release` or the process ends; the holder's pid goes into
`supervisor.pid` beside it. A second start gets None and the holder's pid for its one line.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _dir(state_dir) -> Path:
    from halo_harness.supervise.queue import root
    return root(state_dir)


def holder(state_dir) -> Optional[int]:
    try:
        return int((_dir(state_dir) / "supervisor.pid").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def take(state_dir):
    """The open lock file while this process holds the lock, else None."""
    from halo_harness.filelock import _try_lock
    d = _dir(state_dir)
    try:
        d.mkdir(parents=True, exist_ok=True)
        fh = open(d / "supervisor.lock", "a+b")
    except OSError:
        return None
    if not _try_lock(fh):
        fh.close()
        return None
    try:
        (d / "supervisor.pid").write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass
    return fh


def release(state_dir, fh) -> None:
    from halo_harness.filelock import _unlock
    if fh is None:
        return
    try:
        if holder(state_dir) == os.getpid():
            (_dir(state_dir) / "supervisor.pid").unlink()
    except OSError:
        pass
    _unlock(fh)
    try:
        fh.close()
    except OSError:
        pass


def held_line(state_dir) -> str:
    pid = holder(state_dir)
    return (f"a supervisor is already running (pid {pid}). `halo supervise stop` ends it." if pid else
            "a supervisor is already running (it holds supervise/supervisor.lock). `halo supervise stop` ends it.")
