"""halo_harness.supervise.replan_apply -- a checked replan written into the run
(Halo 3.1.8.0 R2, docs/SUPERVISE.md "Replanning"). The run is stopped on its
replan pause while this runs; it resumes from its checkpoint with the new plan.

* split.json takes the whole plan (split.lead.json keeps the lead's first split,
  once); a merged lane's job and lane file are never rewritten.
* A kept lane's file takes its new model, bio and hand-offs. A lane whose worker
  runs again is re-queued (`waiting`, or `joined` from `failed`) and its job
  carries `replan_note` {revision, text}, which its hand-off section shows
  (orchestra/handoff.py): the contrast for a retry, the specialist for a lane
  that is assisted.
* A split lane is replaced: its file keeps its history and its spend and gains
  `replaced` {revision, by, ts}, its claims are released, and each part takes
  placeholder claims (`lane:<n>`) on its keys, as the lead's split does.
* A specialist's lane file is made at once with `assist` (the gate never blames
  it, orchestra/gate.py) and takes no claim; the lane it assists holds
  placeholders on its keys, so the specialist reads them and cannot edit them.
* workflow.json is redesigned for the lanes (a replaced lane's step skipped,
  the steps that run again pending); merge.json's order is dropped when lanes
  came or went (merge.py recomputes it; a merged lane is skipped anyway).
* plan.json gains a revision {n, at, why, from, to, by, moves}; forecast.json is
  recomputed; events.jsonl gets `replan_applied` with the numbers.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from halo_harness.orchestra import jsonl


def apply(run_dir, checked, *, n: int, why: list, by: str, clock: Callable = time.time) -> dict:
    """Write `checked` (replan_plan.Checked) into the run; the plan.json revision."""
    from halo_harness.orchestra import events as run_events
    from halo_harness.orchestra import forecast
    from halo_harness.orchestra.claims import ClaimLog
    from halo_harness.orchestra.split import PLACEHOLDER_TTL_S, placeholder
    from halo_harness.supervise.replan_moves import diff_lines
    run_dir, now = Path(run_dir), clock()
    split = jsonl.read_json(run_dir / "split.json", {}) or {}
    if not (run_dir / "split.lead.json").exists():
        jsonl.write_json(run_dir / "split.lead.json", split)
    jobs = [dict(j) for j in checked.jobs]
    by_n = {int(j["worker"]): j for j in jobs}
    for ln, text in checked.notes.items():
        if ln in by_n and text:
            by_n[ln]["replan_note"] = {"revision": n, "text": str(text)[-2000:]}
    jsonl.write_json(run_dir / "split.json", dict(split, jobs=jobs))
    log = ClaimLog(run_dir)
    parts_of = {m["lane"]: [p["job"] for p in m.get("into") or []] for m in checked.moves if m["kind"] == "split"}
    for ln in checked.retired:
        _retire(run_dir, log, ln, n, parts_of.get(ln, []), clock)
    for ln, job in by_n.items():
        if ln not in checked.added:
            _kept(run_dir, ln, job)
    for ln in checked.requeue:
        _requeue(run_dir, ln, n, clock)
    for ln in checked.added:
        job = by_n[ln]
        if job.get("assist"):
            _specialist(run_dir, job, clock)
            continue
        for key in job.get("claims") or []:
            log.claim(placeholder(ln), key, ttl_s=PLACEHOLDER_TTL_S, note=f"{job['id']}: {job.get('title') or ''}")
    for target in checked.assists.values():
        _hold(log, next(j for j in jobs if j["id"] == target), PLACEHOLDER_TTL_S)
    _workflow(run_dir, jobs, checked)
    if checked.added or checked.retired:
        merge = jsonl.read_json(run_dir / "merge.json", None)
        if isinstance(merge, dict) and merge.pop("order", None) is not None:
            jsonl.write_json(run_dir / "merge.json", merge)
    diff = diff_lines(checked.moves)
    changed = sorted({m["lane"] for m in checked.moves if m["kind"] in ("model", "bio", "retry")}
                     | set(checked.added) | {int(by_n_id(jobs, t)) for t in checked.assists.values()})
    rev = {"n": n, "at": round(now, 3), "why": list(why), "from": list(checked.before),
           "to": [by_n[x] for x in changed if x in by_n], "by": by, "moves": diff}
    _plan_json(run_dir, jobs, rev, by, now)
    fc = forecast.write_quietly(run_dir, jobs) or {}
    run_events.log(run_dir, "state", f"replan_applied: #{n} by {by}: " + ("; ".join(diff) or "no change"),
                   step="replan", replan="applied", n=n, by=by, moves=checked.moves, lanes=len(jobs),
                   added=checked.added, retired=checked.retired, requeued=checked.requeue,
                   forecast_usd=(fc.get("total") or {}).get("usd"))
    return rev


def by_n_id(jobs: list, jid: str) -> int:
    return int(next(j["worker"] for j in jobs if j["id"] == jid))


def _kept(run_dir, ln: int, job: dict) -> None:
    """A kept lane's file takes its job's model, bio, title and hand-offs (a merged lane: never)."""
    from halo_harness.orchestra.lanes import load_lane
    from halo_harness.orchestra.split import Job
    lane = load_lane(run_dir, ln)
    if lane is None or lane.state == "merged":
        return
    j, data, fields = Job.from_dict(job), lane.data(), {}
    for k in ("model", "bio", "title"):
        if getattr(j, k) and getattr(j, k) != data.get(k):
            fields[k] = getattr(j, k)
    if dict(j.handoff) != (data.get("handoff") or {}):
        fields["handoff"] = dict(j.handoff)
    if list(j.upstreams) != list(data.get("after") or []):
        fields["after"] = list(j.upstreams)
    if fields:
        lane.update(**fields)


def _retire(run_dir, log, ln: int, n: int, into: list, clock: Callable) -> None:
    from halo_harness.orchestra.lanes import load_lane
    from halo_harness.orchestra.split import placeholder
    lane = load_lane(run_dir, ln)
    holders = {placeholder(ln)} | ({lane.holder} if lane is not None and lane.holder else set())
    for c in list(log.active().values()):
        if c.holder in holders:
            log.release(c.holder, c.key, note=f"lane {ln} replaced by the replan (revision {n})")
    if lane is None:
        return
    lane.update(replaced={"revision": n, "by": list(into), "ts": round(clock(), 3)})
    if lane.state:
        lane.set_state(lane.state, f"replaced by the replan (revision {n}): {', '.join(into)}", clock=clock)


def _requeue(run_dir, ln: int, n: int, clock: Callable) -> None:
    from halo_harness.orchestra.lanes import load_lane
    lane = load_lane(run_dir, ln)
    if lane is None or lane.state in ("", "merged"):
        return
    lane.set_state("joined" if lane.state == "failed" else "waiting", f"re-queued by the replan (revision {n})",
                   clock=clock)


def _specialist(run_dir, job: dict, clock: Callable) -> None:
    from halo_harness.orchestra import gitops
    from halo_harness.orchestra.goal import run_meta
    from halo_harness.orchestra.lanes import Lane, load_lane
    from halo_harness.orchestra.split import Job
    ln = int(job["worker"])
    if load_lane(run_dir, ln) is not None:
        return
    run_id = run_meta(run_dir).get("run_id") or Path(run_dir).name
    lane = Lane.create(run_dir, Job.from_dict(job), branch=gitops.worker_branch(run_id, ln),
                       worktree=Path(run_dir) / "wt" / f"worker-{ln}", started=clock())
    lane.update(assist=job["assist"])


def _hold(log, target: dict, ttl_s: int) -> None:
    """The lane assisted keeps its keys (a placeholder on each key nobody holds)."""
    from halo_harness.orchestra.index import overlaps
    from halo_harness.orchestra.split import placeholder
    held = [c.key for c in log.active().values()]
    for key in target.get("claims") or []:
        if not any(overlaps(key, h) for h in held):
            log.claim(placeholder(int(target["worker"])), key, ttl_s=ttl_s, note=f"{target['id']}: held while assisted")


def _workflow(run_dir, jobs: list, checked) -> None:
    from halo_harness.orchestra import workflow as wf
    from halo_harness.orchestra.handoff_spec import edge_label
    from halo_harness.orchestra.split import Job
    path = Path(run_dir) / "workflow.json"
    graph = jsonl.read_json(path, {}) or {}
    js = [Job.from_dict(j) for j in jobs]
    lane_of = {j.id: j.worker for j in js}
    after = {j.worker: [lane_of[u] for u in j.upstreams if u in lane_of] for j in js}
    labels = {(lane_of[u], j.worker): edge_label(j.handoff, u) for j in js for u in j.upstreams if u in lane_of}
    width = max([int(graph.get("workers") or 1)] + list(lane_of.values()) + list(checked.retired))
    new = wf.designed_graph(width, {k: v for k, v in after.items() if v} or None, labels)
    states = {s.get("id"): s.get("state") for s in graph.get("steps") or []}
    used, fresh = set(lane_of.values()), set(checked.requeue) | set(checked.added)
    for s in new["steps"]:
        s["state"] = states.get(s["id"]) or s["state"]
        if s["kind"] == "worker" and s["lane"] not in used:
            s["state"] = "skipped"
        elif (s["kind"] == "worker" and s["lane"] in fresh) or s["kind"] in ("merge", "test", "gate", "done"):
            s["state"] = "pending"
    jsonl.write_json(path, new)


def _plan_json(run_dir, jobs: list, rev: dict, by: str, now: float) -> None:
    from halo_harness.orchestra import plan as P
    data = P.read_decision(run_dir) or {}
    data.update(approved=True, jobs=jobs, ts=round(now, 3), by=data.get("by") or f"replan ({by})")
    data["revisions"] = list(data.get("revisions") or []) + [rev]
    jsonl.write_json(Path(run_dir) / P.PLAN, data)


def revisions(run_dir) -> list:
    """plan.json's revisions (every replan applied to this run), oldest first."""
    from halo_harness.orchestra import plan as P
    return list((P.read_decision(run_dir) or {}).get("revisions") or [])
