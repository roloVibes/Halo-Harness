"""halo_harness.orchestra.workers -- one git worktree and one worker per job.

`start_workers(run_dir, goal, jobs, *, spawn)` gives every job a lane: a
worktree `<run>/wt/worker-<n>` on branch `orchestra/<run-id>-worker-<n>`
(from the split's base commit), then runs `spawn(lane)` for the lanes in
parallel. `spawn` is the worker: in the real runner a fresh halo session in
the worktree with HALO_ORCHESTRA_RUN / HALO_ORCHESTRA_LANE set
(orchestra/adapters.py); in tests a fake that edits files directly. It
returns None, a string (the worker's reply) or a dict with any of `text`,
`cost_usd`, `session_id`, `ok`. A reply line `STOP: <reason>` stops the run.

After `spawn` returns, code finishes the lane: every key the worker still
holds is snapshotted, marked written and released, and the worktree is
committed. Lane states, each logged with its time:

    joined -> writing -> written -> in_review -> merged
                            waiting (a piece sent back) -> writing ...
                            failed

`<run>/lanes/<n>.json` (lanes.py) holds the lane (state, holder, cost, the
`written` snapshots, history; 3.0.9.0: hand-offs, base, gave: handoff.py).
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import RUN_ENV, gitops
from halo_harness.orchestra import events as run_events
from halo_harness.orchestra.claims import ClaimLog
from halo_harness.orchestra.goal import run_meta
from halo_harness.orchestra.lanes import Lane, lane_by_holder, load_lane
from halo_harness.orchestra.split import placeholder
from halo_harness.orchestra.worker_result import record_denied, result_fields as _result_fields

LANE_ENV = "HALO_ORCHESTRA_LANE"
_COMMIT_LOCK = threading.Lock()


def worker_prompt(goal, lane: Lane, retry_text: str = "") -> str:
    keys = ", ".join(f"`{k}`" for k in lane.job.claims)
    text = (
        f"You are worker {lane.n} of an Orchestra run. Your working folder is a git worktree of the repo; "
        "other workers edit other parts of the same files at the same time.\n\n"
        f"WHAT YOU WANT: {goal.what}\nDONE WHEN: {goal.done_when}\nSTOP WHEN: {goal.stop_when}\n\n"
        f"Your job ({lane.job.id}): {lane.job.title}\nYour claim keys: {keys}\n\n"
        "The rule: OrchestraClaim each key -> edit only those units (Edit, not Write) -> OrchestraRelease each "
        "key (it marks the claim written) -> OrchestraNote one line saying what you changed. Leave every other "
        "unit as it is. Do not commit; the run commits your worktree when you finish.\n"
    )
    if goal.test:
        text += f"The run's test command is `{goal.test}` (other workers' units may still be unwritten).\n"
    text += "If STOP WHEN applies to your job, end your reply with one line: STOP: <the reason>.\n"
    extra = [t for t in (getattr(lane, "handoff_text", ""), getattr(lane, "gives_text", "")) if t]
    if extra:  # 3.0.9.0: only a lane that declares hand-offs (orchestra/handoff.py)
        text += "\n" + "\n\n".join(extra) + "\n"
    if retry_text:
        text += f"\nYour piece came back from the merge. Fix it:\n{retry_text}\n"
    return text


def stop_line(text: str) -> Optional[str]:
    for line in str(text or "").splitlines():
        if line.strip().upper().startswith("STOP:"):
            return line.strip()[5:].strip() or "the worker stopped"
    return None


def join_lane(run_dir, lane_n: int, holder: str) -> list:
    """The lane's worker joined: the `lane:<n>` placeholder claims -- and any
    claim the lane's previous worker session still holds (a worker run
    again after a failure) -- move to `holder`, by the lead (code acting on
    the lead's split). Returns the keys."""
    log = ClaimLog(run_dir)
    lead = log.lead_holder() or "orchestra/lead"
    lane = load_lane(run_dir, lane_n)
    previous = {placeholder(lane_n)} | ({lane.holder} if lane is not None and lane.holder else set())
    previous.discard(holder)
    moved = []
    for claim in log.active().values():
        if claim.holder in previous:
            if log.reassign(claim.key, holder, lead).ok:
                moved.append(claim.key)
    if lane is not None and (moved or lane.holder != holder):
        lane.update(holder=holder)
        run_events.log(run_dir, "state", f"lane {lane_n}: {holder} joined", lane=lane_n, holder=holder,
                       keys=moved)
    return moved


def record_written(run_dir, holder: str, key: str, cwd, lane_n: Optional[int] = None) -> bool:
    """Store the unit's text as it stands in the worker's folder when the
    claim is marked written. True when a lane took the snapshot."""
    lane = load_lane(run_dir, lane_n) if lane_n else lane_by_holder(run_dir, holder)
    if lane is None:
        return False
    text = unit_text_on_disk(Path(cwd), key)
    if text is None:
        return False
    lane.store_written(key, text)
    return True


def unit_text_on_disk(root: Path, key: str) -> Optional[str]:
    from halo_harness.orchestra.lanes import unit_text
    rel = key.split("#", 1)[0]
    try:
        content = (Path(root) / rel).read_text(encoding="utf-8")
    except OSError:
        return None
    return unit_text(content, rel, key)


def finish_lane(run_dir, lane: Lane) -> None:
    """Code closes the worker's claims (snapshot, written, released) and
    commits its worktree."""
    log = ClaimLog(run_dir)
    holder = lane.holder or placeholder(lane.n)
    for claim in list(log.active().values()):
        if claim.holder not in (holder, placeholder(lane.n)):
            continue
        text = unit_text_on_disk(lane.worktree, claim.key)  # the worker is done: disk is its last word
        if text is not None:
            lane.store_written(claim.key, text)
        if claim.state != "written":
            log.mark_written(claim.holder, claim.key, note="closed by the run when the worker finished")
        log.release(claim.holder, claim.key, note="worker finished")
    for key in lane.job.claims:
        if key not in lane.written:
            text = unit_text_on_disk(lane.worktree, key)
            if text is not None:
                lane.store_written(key, text)
    with _COMMIT_LOCK:
        sha = gitops.commit_all(lane.worktree, f"worker {lane.n}: {lane.job.title}")
    if sha:
        lane.update(head=sha)


def run_lane(run_dir, goal, lane: Lane, spawn: Callable, *, clock: Callable = time.time,
             retry_text: str = "") -> Lane:
    """One worker pass on one lane: writing -> spawn -> finish -> written
    (or failed, with the error or the worker's STOP reason)."""
    from halo_harness.orchestra import handoff  # 3.0.9.0: the lane's hand-offs in, its gives asked for
    lane.handoff_text = handoff.deliver(run_dir, lane)
    lane.gives_text = handoff.gives_text(run_dir, lane)
    lane.prompt = worker_prompt(goal, lane, retry_text)
    lane.retry_text = retry_text
    lane.set_state("writing", "worker writing" + (" (piece sent back)" if retry_text else ""), clock=clock)
    try:
        fields = _result_fields(spawn(lane))
    except Exception as e:  # a worker's own failure never takes the runner down
        fields = {"text": "", "cost_usd": 0.0, "session_id": None, "ok": False, "error": f"{type(e).__name__}: {e}"}
    data = lane.data()
    sessions = list(data.get("session_ids") or [])
    if fields["session_id"]:
        sessions.append(fields["session_id"])
    lane.update(cost_usd=round(float(data.get("cost_usd") or 0.0) + fields["cost_usd"], 6),
                session_ids=sessions, reply=fields["text"][-2000:], error="")
    record_denied(run_dir, lane, data, fields)  # 3.0.9.0 R3: the coach's evidence
    stop = stop_line(fields["text"])
    if not fields["ok"] or stop:
        reason = f"STOP: {stop}" if stop else (fields["error"] or "the worker did not finish")
        lane.update(error=reason, ended=clock())
        lane.set_state("failed", f"worker failed: {reason}", clock=clock)
        return lane
    try:
        finish_lane(run_dir, lane)
    except gitops.GitError as e:
        lane.update(error=str(e), ended=clock())
        lane.set_state("failed", f"could not commit the worker's piece: {e}", clock=clock)
        return lane
    handoff.record_gave(run_dir, lane, fields["text"])
    lane.update(ended=clock())
    lane.set_state("written", "worker finished; piece committed", clock=clock)
    return lane


def prepare_lane(run_dir, job, base: str, *, clock: Callable = time.time) -> Lane:
    """The lane's record and worktree (both reused when they exist)."""
    run_dir = Path(run_dir)
    run_id = run_meta(run_dir).get("run_id") or run_dir.name
    from halo_harness.orchestra.goal import repo_root_of
    lane = load_lane(run_dir, job.worker)
    if lane is None:
        lane = Lane.create(run_dir, job, branch=gitops.worker_branch(run_id, job.worker),
                           worktree=run_dir / "wt" / f"worker-{job.worker}", started=clock())
    gitops.worktree_add(repo_root_of(run_dir), lane.worktree, lane.branch, base)
    if not lane.data().get("base"):
        lane.update(base=base)
    if lane.state in ("", "pending"):
        lane.set_state("joined", f"worktree {lane.worktree.name} on {lane.branch}", clock=clock)
    return lane


def run_with_retry(run_dir, goal, lane: Lane, spawn: Callable, *, clock: Callable = time.time) -> None:
    """run_lane; a worker's own error (a dropped connection, a crash) gets
    one more run in the same worktree."""
    run_lane(run_dir, goal, lane, spawn, clock=clock)
    error = str(lane.data().get("error") or "")
    if lane.state == "failed" and not error.startswith("STOP:"):
        run_lane(run_dir, goal, lane, spawn, clock=clock,
                 retry_text=f"Your previous run in this worktree ended with an error: {error[:300]}\n"
                            "Check what is already written, then finish the job.")


def start_workers(run_dir, goal, jobs: list, *, spawn: Callable, base: str = "HEAD",
                  clock: Callable = time.time, on_lane: Optional[Callable] = None,
                  on_start: Optional[Callable] = None) -> list:
    """Every job's lane; the lanes not yet written run their worker, in parallel (written or merged
    ones are left as they are). 3.0.9.0: lanes with upstreams wait for them (handoff_run.py)."""
    from halo_harness.orchestra.goal import repo_root_of
    if base == "HEAD":
        base = gitops.head(repo_root_of(run_dir))
    if any(job.upstreams for job in jobs):
        from halo_harness.orchestra.handoff_run import start_layered
        return start_layered(run_dir, goal, jobs, spawn=spawn, base=base, clock=clock, on_lane=on_lane,
                             on_start=on_start)
    lanes = [prepare_lane(run_dir, job, base, clock=clock) for job in jobs]
    todo = [lane for lane in lanes if lane.state in ("joined", "writing", "waiting", "failed")]

    def _one(lane: Lane) -> None:
        run_with_retry(run_dir, goal, lane, spawn, clock=clock)
        if on_lane is not None:
            on_lane(lane)

    if len(todo) == 1:
        _one(todo[0])
    elif todo:
        with ThreadPoolExecutor(max_workers=len(todo), thread_name_prefix="orchestra-worker") as pool:
            for future in [pool.submit(_one, lane) for lane in todo]:
                future.result()
    return lanes


def child_env(run_dir, lane_n: int, base_env: dict) -> dict:
    """The worker's environment: the run and its lane on top of `base_env`."""
    env = dict(base_env)
    env[RUN_ENV] = str(Path(run_dir).resolve())
    env[LANE_ENV] = str(int(lane_n))
    return env
