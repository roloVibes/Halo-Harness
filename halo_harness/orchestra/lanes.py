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
lose each other's fields.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import jsonl

LANE_STATES = ("joined", "writing", "written", "in_review", "waiting", "merged", "failed")


def lanes_dir(run_dir) -> Path:
    return Path(run_dir) / "lanes"


def lane_path(run_dir, n: int) -> Path:
    return lanes_dir(run_dir) / f"{int(n)}.json"


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
        jsonl.write_json(lane.path, {
            "lane": lane.n, "job": job.id, "title": job.title, "claims": list(job.claims), "order": job.order,
            "state": "", "holder": "", "branch": branch, "worktree": str(lane.worktree), "head": "",
            "cost_usd": 0.0, "started": started, "ended": None, "pieces_returned": 0, "session_ids": [],
            "written": {}, "error": "", "reply": "", "history": [],
            "handoff": dict(getattr(job, "handoff", None) or {}), "after": list(getattr(job, "upstreams", []) or []),
            "base": "", "gave": [], "bio": str(getattr(job, "bio", "") or ""), "model": str(getattr(job, "model", "") or ""),
            "denied": []})
        return lane

    def data(self) -> dict:
        data = jsonl.read_json(self.path, {})
        return data if isinstance(data, dict) else {}

    def update(self, **fields) -> dict:
        with jsonl.locked(self.path):
            data = self.data()
            data.update(fields)
            jsonl.write_json(self.path, data)
        return data

    def store_written(self, key: str, text: str) -> None:
        with jsonl.locked(self.path):
            data = self.data()
            written = dict(data.get("written") or {})
            written[key] = text
            data["written"] = written
            jsonl.write_json(self.path, data)

    def set_state(self, state: str, text: str = "", *, clock: Callable = time.time) -> None:
        if state not in LANE_STATES:
            raise ValueError(f"lane state must be one of {', '.join(LANE_STATES)}, got {state!r}")
        ts = clock()
        with jsonl.locked(self.path):
            data = self.data()
            history = list(data.get("history") or [])
            history.append({"state": state, "ts": round(ts, 3), "elapsed_s": jsonl.elapsed(self.run_dir, ts),
                            "text": text})
            data.update(state=state, history=history)
            jsonl.write_json(self.path, data)
        run_events.log(self.run_dir, "state", f"lane {self.n} {state}" + (f": {text}" if text else ""),
                       lane=self.n, step=f"worker-{self.n}", lane_state=state)

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
