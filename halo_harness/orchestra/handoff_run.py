"""halo_harness.orchestra.handoff_run -- the workers when some lanes start
after others (Halo 3.0.9.0 round R1; workers.start_workers hands over here
when any job has upstreams).

Every lane gets its record at once; a lane without upstreams gets its
worktree from the split's base and runs at once, in parallel, as before. A
lane with upstreams is `waiting` ("waits for job-1 (hand-off)") until every
upstream lane is done; then, if they were all written, its worktree is made
from their head (handoff.start_base: one head, or the merge of two or more)
and it runs; if one was not written, or the heads do not merge, it stays
`waiting` with the reason and the run stops on it (run.py).
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import gitops, handoff
from halo_harness.orchestra.goal import repo_root_of, run_meta
from halo_harness.orchestra.lanes import Lane, load_lane


def lane_record(run_dir, job, *, clock: Callable = time.time) -> Lane:
    """The lane's file, without a worktree yet (it waits for its upstreams)."""
    run_dir = Path(run_dir)
    lane = load_lane(run_dir, job.worker)
    if lane is None:
        run_id = run_meta(run_dir).get("run_id") or run_dir.name
        lane = Lane.create(run_dir, job, branch=gitops.worker_branch(run_id, job.worker),
                           worktree=run_dir / "wt" / f"worker-{job.worker}", started=clock())
    if lane.state in ("", "pending"):
        lane.set_state("waiting", "waits for " + ", ".join(job.upstreams) + " (hand-off)", clock=clock)
    return lane


def open_lane(run_dir, lane: Lane, split_base: str, ups: list, *, clock: Callable = time.time) -> Optional[str]:
    """Make the waiting lane's worktree from its upstreams' head; the reason
    it does not start, or None."""
    why = handoff.unfinished(ups)
    if why:
        return why
    if (lane.worktree / ".git").exists():
        return None  # a resumed lane keeps its worktree and its base
    start, err = handoff.start_base(run_dir, lane, split_base)
    if start is None:
        return err
    gitops.worktree_add(repo_root_of(run_dir), lane.worktree, lane.branch, start)
    lane.update(base=start)
    lane.set_state("joined", f"worktree {lane.worktree.name} on {lane.branch} from {start[:12]} "
                   f"(the head of {', '.join(f'lane {u.n}' for u in ups)})", clock=clock)
    return None


def start_layered(run_dir, goal, jobs: list, *, spawn: Callable, base: str, clock: Callable = time.time,
                  on_lane: Optional[Callable] = None, on_start: Optional[Callable] = None) -> list:
    from halo_harness.orchestra.workers import prepare_lane, run_with_retry
    lanes = [lane_record(run_dir, job, clock=clock) if job.upstreams else prepare_lane(run_dir, job, base, clock=clock)
             for job in jobs]
    by_job = {lane.job.id: lane for lane in lanes}
    done = {lane.job.id: threading.Event() for lane in lanes}
    todo = [lane for lane in lanes if lane.state in ("joined", "writing", "waiting", "failed")]
    for lane in lanes:
        if lane not in todo:
            done[lane.job.id].set()

    def _one(lane: Lane) -> None:
        try:
            if lane.job.upstreams:
                for jid in lane.job.upstreams:
                    if jid in done:
                        done[jid].wait()
                why = open_lane(run_dir, lane, base, [by_job[j] for j in lane.job.upstreams if j in by_job], clock=clock)
                if why:
                    lane.set_state("waiting", f"not started: {why}", clock=clock)
                    return
            if on_start is not None:
                on_start(lane)
            run_with_retry(run_dir, goal, lane, spawn, clock=clock)
            if on_lane is not None:
                on_lane(lane)
        finally:
            done[lane.job.id].set()

    if todo:
        with ThreadPoolExecutor(max_workers=len(todo), thread_name_prefix="orchestra-worker") as pool:
            for future in [pool.submit(_one, lane) for lane in todo]:
                future.result()
    return lanes


def stuck(lanes: list) -> list:
    """Lanes that never got to run (`waiting`), with the reason they show."""
    out = []
    for lane in lanes:
        if lane.state == "waiting":
            history = lane.data().get("history") or [{}]
            out.append((lane, str(history[-1].get("text") or "it waits for its upstreams")))
    return out
