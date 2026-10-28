"""halo_harness.fleet.control_pulls -- Halo 3.3.5.0 R3: a member's pull jobs
reach the hub that asked for them with the member's ledger push (fleet/
ollama_share.py; the push runs every FLUSH_S, so the hub's progress bar moves
in those steps).

    read_pulls(home, now=None)       the member's side: its pull jobs (studio/local_pull_job.py's
                                     `<state>/ollama/pulls.json`) running, or ended in the last 5 minutes
    take_pulls(member, rows)         the hub's side: each onto the hub's job for it (local_pull_job.take_remote),
                                     which publishes the `pull` frame
"""

from __future__ import annotations

import time
from typing import Optional

RECENT_S = 300.0
MAX_ROWS = 20


def read_pulls(home, now: Optional[float] = None) -> list:
    from halo_harness.studio.local_pull_job import read_file
    now = time.time() if now is None else now
    keep = ("job", "host", "name", "status", "digest", "total", "completed", "percent", "speed", "eta", "done", "error",
            "ok", "cancelled", "say", "started")
    rows = [r for r in read_file(home) if isinstance(r, dict) and (not r.get("done")
                                                                   or now - float(r.get("started") or 0) < RECENT_S)]
    return [{k: r.get(k) for k in keep} for r in rows[:MAX_ROWS]]


def take_pulls(member: str, rows) -> int:
    from halo_harness.studio.local_pull_job import take_remote
    if not isinstance(rows, list) or not member:
        return 0
    return sum(1 for r in rows[:MAX_ROWS] if isinstance(r, dict) and take_remote(member, r))


__all__ = ["read_pulls", "take_pulls"]
