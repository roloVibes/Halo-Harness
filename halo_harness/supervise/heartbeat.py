"""halo_harness.supervise.heartbeat -- an Orchestra run's runner, seen from any
process (Halo 3.1.8.0 R1).

    <run>/runner.json   {pid, pstart, beat, by}   rewritten every BEAT_S seconds while a runner drives the run

Every runner writes it: `halo orchestra run` (orchestra_cli_run.py), Studio
(studio/orchestra_live.py) and the supervisor (team/adapters.orchestra_run).
`live(run_dir)` is the row while the beat is fresh (2 * BEAT_S, the team
board's rule) AND its process is alive and is the one that wrote it
(proc_ident's start token against a reused pid). Studio reads it: a run with
a live runner elsewhere is `running`, not `interrupted`, and Studio does not
start a second runner on it (409). The supervisor reads it to resume its own
goals whose run has no live runner and no report.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import jsonl

BEAT_S = 15.0
FILE = "runner.json"


def path(run_dir) -> Path:
    return Path(run_dir) / FILE


def write(run_dir, by: str = "", pstart: Optional[str] = None) -> dict:
    row = {"pid": os.getpid(), "pstart": pstart, "beat": round(time.time(), 3), "by": by}
    try:
        jsonl.write_json(path(run_dir), row)
    except OSError:
        pass
    return row


def clear(run_dir) -> None:
    """Drop runner.json when this process wrote it (a newer runner's beat stays)."""
    row = read(run_dir)
    if row is not None and row.get("pid") == os.getpid():
        try:
            path(run_dir).unlink()
        except OSError:
            pass


def read(run_dir) -> Optional[dict]:
    data = jsonl.read_json(path(run_dir), None)
    return data if isinstance(data, dict) else None


def live(run_dir, now: Optional[float] = None) -> Optional[dict]:
    """The runner's row while one beats for this run, else None."""
    row = read(run_dir)
    if row is None:
        return None
    if (time.time() if now is None else now) - float(row.get("beat") or 0) >= 2 * BEAT_S:
        return None
    if row.get("pid") == os.getpid():
        return row
    from halo_harness.remote.bridge_state import alive
    return row if alive({"pid": row.get("pid"), "pstart": row.get("pstart"), "started": row.get("beat")}) else None


def other_live(run_dir) -> Optional[dict]:
    """The row when ANOTHER process runs this run right now."""
    row = live(run_dir)
    return row if row is not None and row.get("pid") != os.getpid() else None


def other_live_in(repo) -> Optional[dict]:
    """The first run of `repo` another process runs right now, as `{run_id, pid, by}`."""
    from halo_harness.orchestra.goal import list_runs
    for run_dir in reversed(list_runs(repo)):
        if path(run_dir).is_file():
            row = other_live(run_dir)
            if row is not None:
                return {"run_id": Path(run_dir).name, "pid": row.get("pid"), "by": row.get("by") or ""}
    return None


class Beat:
    """`with Beat(run_dir, by="cli"):` writes runner.json now and every `every` seconds, clears it at the end."""

    def __init__(self, run_dir, by: str = "", every: float = BEAT_S):
        self.run_dir, self.by, self.every = Path(run_dir), by, every
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        from halo_harness.remote import proc_ident
        self.pstart = proc_ident.start_token(os.getpid())

    def __enter__(self) -> "Beat":
        write(self.run_dir, self.by, self.pstart)
        self._thread = threading.Thread(target=self._run, name=f"halo-runner-beat-{self.run_dir.name}", daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        while not self._stop.wait(self.every):
            write(self.run_dir, self.by, self.pstart)

    def __exit__(self, *exc) -> bool:
        self._stop.set()
        clear(self.run_dir)
        return False
