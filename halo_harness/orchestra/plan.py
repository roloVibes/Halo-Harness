"""halo_harness.orchestra.plan -- the reviewed plan between the split and the
workers (Halo 3.0.9.0 round R2).

A goal with `plan: review` (`halo orchestra run --review`, Studio's "Review
the plan before it runs") runs the lead's split as always, then holds the
workflow's split step `planned` and waits for the run folder's decision:

    <run>/plan.json        {"approved": true, "jobs": [...], "ts", "by"}    the plan to run
                           {"approved": false, "reason": "...", "ts", "by"}  the run stops with that reason
    <run>/plan.draft.json  {"jobs": [...], "ts"}    Studio's edit in progress (it never approves)
    <run>/split.lead.json  the lead's own split.json, kept once an approved plan replaces its jobs

The jobs are split.json's shape plus the hand-off fields (`handoff`,
`after`) and the worker's `bio` / `model`. Approving validates them first
(`plan_check.plan_problems`: ids, titles, claims, references, cycles,
takes, overlapping claims without an `after`, the bio/model preflight); a
plan with problems is not written. On approval code renumbers the jobs
`job-1..N` in their order (rewriting `after` / `needs.from`), rewrites
split.json's jobs (`"plan": "approved"`), moves the placeholder claims to
the new lanes (in layer order: of two sequenced jobs on one key the earlier
holds it) and widens workflow.json when the plan has more lanes than the
goal's workers. A plan.json written by hand that fails the check is moved
to plan.bad.json with its problems and the run keeps waiting. While it
waits the runner touches `<run>/plan.wait.json` ({pid, ts}) every BEAT_S
seconds, so Studio knows whether a runner (here or in a terminal) will take
the decision or it has to start one.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import jsonl

PLAN, DRAFT, LEAD, BAD, WAIT = "plan.json", "plan.draft.json", "split.lead.json", "plan.bad.json", "plan.wait.json"
POLL_S = 0.5
BEAT_S = 2.0  # the waiting runner touches plan.wait.json this often; Studio starts a runner only when it is stale


def waiting_alive(run_dir, within: float = 3 * BEAT_S) -> bool:
    """A runner (this process or a `halo orchestra run --review` elsewhere) waits for this plan right now."""
    data = jsonl.read_json(Path(run_dir) / WAIT, None)
    return isinstance(data, dict) and time.time() - float(data.get("ts") or 0) < within


def read_decision(run_dir) -> Optional[dict]:
    data = jsonl.read_json(Path(run_dir) / PLAN, None)
    return data if isinstance(data, dict) else None


def read_draft(run_dir) -> Optional[list]:
    data = jsonl.read_json(Path(run_dir) / DRAFT, None)
    return data["jobs"] if isinstance(data, dict) and isinstance(data.get("jobs"), list) else None


def write_draft(run_dir, jobs: list) -> None:
    jsonl.write_json(Path(run_dir) / DRAFT, {"jobs": jobs, "ts": round(time.time(), 3)})


def split_jobs(run_dir) -> list:
    data = jsonl.read_json(Path(run_dir) / "split.json", {}) or {}
    return list(data.get("jobs") or []) if isinstance(data, dict) else []


def lead_jobs(run_dir) -> list:
    """The jobs as the lead split them (before any approved edit)."""
    data = jsonl.read_json(Path(run_dir) / LEAD, None)
    return list(data.get("jobs") or []) if isinstance(data, dict) else split_jobs(run_dir)


def current_jobs(run_dir) -> list:
    """What the editor opens: the draft, else split.json's jobs."""
    draft = read_draft(run_dir)
    return draft if draft is not None else split_jobs(run_dir)


def is_planned(run_dir) -> bool:
    graph = jsonl.read_json(Path(run_dir) / "workflow.json", {}) or {}
    return any(s.get("id") == "split" and s.get("state") == "planned" for s in graph.get("steps") or [])


def unit_keys(run_dir) -> Optional[list]:
    """Every claimable key of the goal's files (None when a file cannot be read)."""
    from halo_harness.orchestra.goal import load_goal, repo_root_of
    from halo_harness.orchestra.index import index_file
    run_dir = Path(run_dir)
    try:
        goal, repo = load_goal(run_dir / "goal.json"), repo_root_of(run_dir)
        return [u.key for rel in goal.files for u in index_file(repo / rel, root=repo)]
    except (OSError, ValueError):
        return None


def check(run_dir, jobs, *, state_dir=None) -> list:
    """`plan_check.plan_problems` against this run's files (the bios looked up from its repo)."""
    from halo_harness.orchestra.goal import repo_root_of
    from halo_harness.orchestra.plan_check import plan_problems
    return plan_problems(jobs, unit_keys=unit_keys(run_dir), cwd=repo_root_of(run_dir), state_dir=state_dir)


def normalize(jobs: list) -> list:
    """The jobs renumbered `job-1..N` in their order, worker/order = N, refs rewritten."""
    ids = {str(j.get("id")): f"job-{i}" for i, j in enumerate(jobs, 1)}
    out = []
    for i, raw in enumerate(jobs, 1):
        job = {k: v for k, v in raw.items() if k in ("title", "claims", "handoff", "after", "bio", "model")}
        job.update(id=f"job-{i}", worker=i, order=i, title=str(job.get("title") or "").strip(),
                   claims=[str(c) for c in job.get("claims") or []])
        job["after"] = [ids.get(str(a), str(a)) for a in job.get("after") or []]
        h = dict(job.get("handoff") or {})
        if h.get("needs"):
            h["needs"] = [dict(n, **{"from": ids.get(str(n.get("from")), str(n.get("from")))}) for n in h["needs"]]
        job["handoff"] = {k: v for k, v in h.items() if k in ("gives", "needs") and v}
        out.append({k: v for k, v in job.items() if v not in ("", [], {}, None) or k in ("claims", "title")})
    return out


def approve(run_dir, jobs, *, by: str = "cli", state_dir=None) -> list:
    """Validate and write plan.json approved; the problems ([] = written)."""
    problems = check(run_dir, jobs, state_dir=state_dir)
    if not problems:
        jsonl.write_json(Path(run_dir) / PLAN, {"approved": True, "jobs": normalize(jobs), "ts": round(time.time(), 3),
                                                "by": by})
        run_events.log(run_dir, "state", f"plan approved by {by}: {len(jobs)} job(s)", step="split", plan="approved")
    return problems


def reject(run_dir, reason: str, *, by: str = "cli") -> None:
    jsonl.write_json(Path(run_dir) / PLAN, {"approved": False, "reason": reason, "ts": round(time.time(), 3), "by": by})
    run_events.log(run_dir, "state", f"plan rejected by {by}: {reason}", step="split", plan="rejected")


def apply(run_dir, jobs: list, flow=None) -> list:
    """split.json takes the approved jobs; the placeholder claims follow them; the
    workflow gets a step per lane. Returns the Jobs."""
    from halo_harness.orchestra import workflow as wf
    from halo_harness.orchestra.claims import ClaimLog
    from halo_harness.orchestra.handoff_spec import layers
    from halo_harness.orchestra.split import PLACEHOLDER_TTL_S, Job, placeholder
    run_dir = Path(run_dir)
    split = jsonl.read_json(run_dir / "split.json", {}) or {}
    if not (run_dir / LEAD).exists():
        jsonl.write_json(run_dir / LEAD, split)
    new = [Job.from_dict(j) for j in jobs]
    jsonl.write_json(run_dir / "split.json", dict(split, jobs=[j.to_dict() for j in new], plan="approved"))
    log = ClaimLog(run_dir)
    for c in list(log.active().values()):
        if c.holder.startswith("lane:"):
            log.release(c.holder, c.key, note="the reviewed plan replaces the split")
    depth = layers({j.id: j.upstreams for j in new})
    for job in sorted(new, key=lambda j: (depth.get(j.id, 0), j.worker)):
        for key in job.claims:
            log.claim(placeholder(job.worker), key, ttl_s=PLACEHOLDER_TTL_S, note=f"{job.id}: {job.title}")
    lock = flow.lock if flow is not None else None
    if lock is not None:
        lock.acquire()
    try:
        graph = jsonl.read_json(run_dir / "workflow.json", {}) or {}
        if int(graph.get("workers") or 0) < len(new):
            wide = wf.designed_graph(len(new))
            states = {s.get("id"): s.get("state") for s in graph.get("steps") or []}
            for s in wide["steps"]:
                s["state"] = states.get(s["id"]) or s["state"]
            jsonl.write_json(run_dir / "workflow.json", wide)
    finally:
        if lock is not None:
            lock.release()
    return new


def await_plan(run_dir, flow, jobs: list, *, check_stop: Callable, poll_s: float = POLL_S) -> list:
    """Hold the split `planned` until plan.json says; the approved Jobs, or StopRun."""
    run_dir = Path(run_dir)
    split = jsonl.read_json(run_dir / "split.json", {}) or {}
    decision = read_decision(run_dir)
    if split.get("plan") == "approved" and decision and decision.get("approved"):
        return jobs  # a resumed run: the approved plan is already split.json's
    announced, beat = False, 0.0
    try:
        return _wait(run_dir, flow, jobs, check_stop, poll_s, announced, beat)
    finally:
        try:
            (run_dir / WAIT).unlink()
        except OSError:
            pass


def _wait(run_dir: Path, flow, jobs: list, check_stop: Callable, poll_s: float, announced: bool, beat: float) -> list:
    import os
    from halo_harness.orchestra.split import StopRun
    while True:
        if time.time() - beat >= BEAT_S:
            beat = time.time()
            jsonl.write_json(run_dir / WAIT, {"pid": os.getpid(), "ts": round(beat, 3)})
        decision = read_decision(run_dir)
        if decision is not None and not decision.get("approved"):
            reason = str(decision.get("reason") or "no reason given")
            flow.set("split", "failed", f"the plan was rejected: {reason}")
            raise StopRun(f"the plan was rejected: {reason}")
        if decision is not None:
            problems = check(run_dir, decision.get("jobs"))
            if not problems:
                approved = apply(run_dir, normalize(decision["jobs"]), flow)
                run_events.log(run_dir, "state", f"the run takes the reviewed plan: {len(approved)} job(s)", step="split")
                return approved
            (run_dir / PLAN).replace(run_dir / BAD)
            jsonl.write_json(run_dir / BAD, dict(decision, problems=[p["text"] for p in problems]))
            run_events.log(run_dir, "state", "plan.json fails the check, so the plan still waits: "
                           + "; ".join(p["text"] for p in problems), step="split", problems=[p["text"] for p in problems])
        if not announced:
            announced = True
            flow.set("split", "planned", f"{len(jobs)} job(s) wait for review: halo orchestra plan {run_dir.name}, "
                     f"then approve or reject (or Studio's plan canvas)")
        try:
            check_stop()
        except StopRun:
            flow.set("split", "failed", "stopped while the plan waited for review")
            raise
        time.sleep(poll_s)
