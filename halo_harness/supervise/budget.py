"""halo_harness.supervise.budget -- a goal's `budget_usd` and the queue's
`supervise.budget_usd` are caps, not forecasts (Halo 3.1.8.0 R1).

The probe guard's rule (orchestra/probe_runs.py `Budget`) over the real
spend (orchestra/report.py's line: the lead's split + every lane + the
judge's conflicts): before a lane's worker starts, what the run spent + what
the lanes running now are expected to cost + this lane's forecast must stay
under the goal's cap, and the other goals' spend + all of that under the
queue's. A lane that would pass a cap does not start: the run gets
request_stop("budget: ...") and stops between steps; the supervisor parks the
goal (`why: budget`, a `goal_budget` row). A `job` goal runs with
`--max-budget-usd` (the lower of its cap and what the queue has left), which
`halo -p` enforces itself.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import jsonl

EPS = 1e-12


def run_spent(run_dir) -> float:
    """What the run has spent: the lead's split, every lane, every conflict the judge resolved."""
    run_dir = Path(run_dir)
    split = jsonl.read_json(run_dir / "split.json", {}) or {}
    lanes = sum(float((jsonl.read_json(p, {}) or {}).get("cost_usd") or 0.0) for p in (run_dir / "lanes").glob("*.json"))
    merge = jsonl.read_json(run_dir / "merge.json", {}) or {}
    conflicts = sum(float(c.get("cost_usd") or 0.0) for c in merge.get("conflicts") or [])
    return round(float(split.get("lead_cost_usd") or 0.0) + lanes + conflicts, 6)


def others_spent(state_dir, gid: str) -> float:
    from halo_harness.supervise.queue import all_goals
    return round(sum(float(g.get("cost_usd") or 0.0) for g in all_goals(state_dir) if g["id"] != gid), 6)


def lane_forecast(run_dir, n: int) -> float:
    from halo_harness.orchestra import forecast
    line = next((l for l in (forecast.read(run_dir) or {}).get("lanes") or [] if l.get("lane") == n), {})
    return float(line.get("usd") or 0.0)


def queue_left(state_dir, gid: str, queue_cap: Optional[float]) -> Optional[float]:
    return None if queue_cap is None else round(max(0.0, float(queue_cap) - others_spent(state_dir, gid)), 6)


def job_cap(state_dir, goal: dict, queue_cap: Optional[float]) -> Optional[float]:
    """The `--max-budget-usd` a job goal runs with: the lower of its own cap and the queue's rest."""
    caps = [c for c in (goal.get("budget_usd"), queue_left(state_dir, goal["id"], queue_cap)) if c is not None]
    return round(min(float(c) for c in caps), 6) if caps else None


def over_at_start(state_dir, goal: dict, queue_cap: Optional[float]) -> str:
    """Why the goal may not start at all ('' = it may): its cap or the queue's is already spent."""
    own = goal.get("budget_usd")
    if own is not None and float(goal.get("cost_usd") or 0.0) + EPS >= float(own):
        return f"the goal has spent ${float(goal.get('cost_usd') or 0):.4f} of its ${float(own):.4f}"
    left = queue_left(state_dir, goal["id"], queue_cap)
    if left is not None and left <= EPS:
        return f"the queue has spent its ${float(queue_cap):.4f} (supervise.budget_usd)"
    return ""


class Guard:
    """Wraps a run's `spawn(lane)`: a lane that would pass a cap does not start (`hit` says why)."""

    def __init__(self, state_dir, goal: dict, run_dir, queue_cap: Optional[float]):
        self.state_dir, self.gid, self.dir = state_dir, goal["id"], Path(run_dir)
        self.cap = None if goal.get("budget_usd") is None else float(goal["budget_usd"])
        self.queue_cap = None if queue_cap is None else float(queue_cap)
        self.lock, self.running, self.hit = threading.Lock(), {}, ""

    def check(self, n: int) -> str:
        spent, ahead, own = run_spent(self.dir), sum(self.running.values()), lane_forecast(self.dir, n)
        if self.cap is not None and spent + ahead + own > self.cap + EPS:
            return (f"lane {n} not started: spent ${spent:.4f} + running ${ahead:.4f} + its forecast ${own:.4f} "
                    f"is over the goal's cap ${self.cap:.4f}")
        if self.queue_cap is not None:
            others = others_spent(self.state_dir, self.gid)
            if others + spent + ahead + own > self.queue_cap + EPS:
                return (f"lane {n} not started: the other goals' ${others:.4f} + this run's ${spent + ahead:.4f} "
                        f"+ its forecast ${own:.4f} is over the queue's cap ${self.queue_cap:.4f}")
        return ""

    def wrap(self, spawn: Callable) -> Callable:
        from halo_harness.orchestra.run import request_stop

        def guarded(lane):
            with self.lock:
                why = self.hit or self.check(lane.n)
                if why:
                    if not self.hit:
                        self.hit = why
                        request_stop(self.dir, f"budget: {why}")
                    return {"ok": True, "text": f"STOP: budget: {why}", "cost_usd": 0.0}
                self.running[lane.n] = lane_forecast(self.dir, lane.n)
            try:
                return spawn(lane)
            finally:
                with self.lock:
                    self.running.pop(lane.n, None)
        return guarded
