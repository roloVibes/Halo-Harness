"""halo_harness.orchestra.lanes -- `<run>/lanes/<n>.json`, one per worker lane.

    {"lane": 2, "job": "job-2", "title": "...", "claims": ["basket.py#remove_item"],
     "state": "merged", "holder": "<session>/main", "branch": "orchestra/<run>-worker-2",
     "worktree": "<run>/wt/worker-2", "head": "<sha>", "cost_usd": 0.0031,
     "started": 1760300000.1, "ended": 1760300042.7, "pieces_returned": 0,
     "session_ids": ["..."], "written": {"basket.py#remove_item": "def remove_item(...):\\n..."},
     "error": "", "reply": "...",
     "history": [{"state": "joined", "ts": ..., "elapsed_s": ..., "text": "..."}, ...],
     "handoff": {"gives": [...], "needs": [...]}, "after": ["job-1"], "base": "<sha>",
     "gave": [{"name": "summary", "kind": "summary", "path": "lanes/2/summary.md", "bytes": 812}, ...]}

3.0.9.0 (orchestra/handoff.py): `handoff` is the job's declaration, `after`
every job it starts after (its `after` plus each `needs.from`), `base` the
commit its worktree started from, `gave` what it produced when written (the
summary = its final reply, one `files` row per written key, an artifact =
a file it saved under `<run>/lanes/<n>/artifacts/`; paths are relative to
the run folder, a files row's path is the key).
3.0.9.0 R3 (the coach, orchestra/coach.py): `bio` and `model` the lane ran
with (the job's, else the model the worker's result names), `denied` the
tool calls the worker's permission engine denied `[{tool_name, reason}]`.

Every change is a read-modify-write under the file's lock, so the runner and
a worker's own OrchestraRelease (which stores a `written` snapshot) never
lose each other's fields. 3.1.2.0 R1: the file's shape and every read and
write of it live in work/adapters/lane.py (a lane is a unit of work,
docs/WORK.md); `Lane` is the engine's handle on it.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import jsonl
from halo_harness.work.adapters import lane as adapter
from halo_harness.work.adapters.lane import LANE_STATES  # noqa: F401  (joined .. failed, the lane's words)


def lanes_dir(run_dir) -> Path:
    return Path(run_dir) / "lanes"


def lane_path(run_dir, n: int) -> Path:
    return adapter.lane_path(run_dir, n)


class Lane:
    """A handle on one lane's file. Attributes that never change (n, job,
    branch, worktree) live on the object; everything else is read fresh."""

    def __init__(self, run_dir, n: int, job, branch: str, worktree):
        self.run_dir = Path(run_dir)
        self.n = int(n)
        self.job = job
        self.branch = branch
        self.worktree = Path(worktree)
        self.prompt = ""
        self.retry_text = ""
        self.handoff_text = ""  # 3.0.9.0: the prompt's "Hand-offs" section (orchestra/handoff.py)
        self.gives_text = ""

    @property
    def path(self) -> Path:
        return lane_path(self.run_dir, self.n)

    @classmethod
    def create(cls, run_dir, job, *, branch: str, worktree, started: float) -> "Lane":
        lane = cls(run_dir, job.worker, job, branch, worktree)
        adapter.write_record(lane.path, adapter.new_record(job, n=lane.n, branch=branch, worktree=lane.worktree,
                                                           started=started))
        return lane

    def data(self) -> dict:
        return adapter.read(self.path)

    def update(self, **fields) -> dict:
        return adapter.update(self.path, **fields)

    def store_written(self, key: str, text: str) -> None:
        adapter.store_written(self.path, key, text)

    def set_state(self, state: str, text: str = "", *, clock: Callable = time.time) -> None:
        adapter.set_state(self.run_dir, self.n, state, text, clock=clock)

    def unit(self):
        """This lane as a unit of work (work/unit.py)."""
        return adapter.to_unit(self.data(), self.run_dir.name)

    # ---- read-only views ---------------------------------------------------
    @property
    def state(self) -> str:
        return str(self.data().get("state") or "")

    @property
    def holder(self) -> str:
        return str(self.data().get("holder") or "")

    @property
    def written(self) -> dict:
        return dict(self.data().get("written") or {})

    @property
    def pieces_returned(self) -> int:
        return int(self.data().get("pieces_returned") or 0)

    @property
    def cost_usd(self) -> float:
        return float(self.data().get("cost_usd") or 0.0)

    def __repr__(self) -> str:
        return f"Lane({self.n}, {self.job.id}, {self.state or 'new'})"


def load_lane(run_dir, n) -> Optional[Lane]:
    from halo_harness.orchestra.split import Job
    data = jsonl.read_json(lane_path(run_dir, n), None)
    if not isinstance(data, dict):
        return None
    job = Job(id=str(data.get("job") or f"job-{n}"), title=str(data.get("title") or ""),
              claims=list(data.get("claims") or []), worker=int(n), order=int(data.get("order") or n),
              handoff=dict(data.get("handoff") or {}) if isinstance(data.get("handoff"), dict) else {},
              after=[str(a) for a in data.get("after") or []] if isinstance(data.get("after"), list) else [])
    return Lane(run_dir, int(n), job, str(data.get("branch") or ""), data.get("worktree") or "")


def list_lanes(run_dir) -> list:
    """Every lane of the run, by lane number."""
    out = []
    try:
        names = [p.stem for p in lanes_dir(run_dir).glob("*.json")]
    except OSError:
        return []
    for n in sorted(int(name) for name in names if name.isdigit()):
        lane = load_lane(run_dir, n)
        if lane is not None:
            out.append(lane)
    return out


def lane_rows(run_dir) -> list:
    """Every lane's file as a dict (what `halo orchestra lanes` and the TUI show)."""
    return [lane.data() for lane in list_lanes(run_dir)]


def lane_by_holder(run_dir, holder: str) -> Optional[Lane]:
    for lane in list_lanes(run_dir):
        if lane.holder == holder:
            return lane
    return None


def unit_text(content: str, rel: str, key: str) -> Optional[str]:
    """The lines of unit `key` in `content` (the file `rel`), or None when
    the file has no such unit any more."""
    from halo_harness.orchestra.index import index_text
    for unit in index_text(content, rel):
        if unit.key == key:
            lines = content.splitlines()
            return "\n".join(line.rstrip() for line in lines[unit.start_line - 1:unit.end_line]).rstrip()
    return None
