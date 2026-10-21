"""halo_harness.orchestra.run -- the run pipeline, end to end.

    goal -> lead (split) -> workers (one worktree each, in parallel)
         -> merge one at a time (a fresh judge on a conflict, checked by tests)
         -> test -> gate (a failed piece loops back to its worker, up to
            return_cap times) -> done: the finished branch and report.json

`run(run_dir, *, model_calls, spawn, judge, clock)`: the lead's one-shot call (split), a worker
and the fresh judge (the real ones: adapters.py; tests pass fakes). Every transition advances
`workflow.json` and logs a `state` line; `on_event(entry)` sees each new events.jsonl line.
`plan: review` holds the split `planned` for the reviewed plan (plan.py).

Resumable: a re-run reads split.json, lanes/*.json and merge.json and picks up at the first
unfinished step (a written lane is not run again, a merged lane is not merged again). STOP WHEN
goes to the lead (`{"stop": reason}`) and every worker (`STOP: reason`); the gate stops at the
return cap; `halo orchestra stop` writes `<run>/stop.json`, honoured between steps; a stopped run
still writes its report. 3.1.2.0 R2: the plan's forecast goes beside split.json (forecast.py); a
lane that started from a piece the gate sent back is re-based before the merge (stale.py).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import forecast, gitops, jsonl
from halo_harness.orchestra import workflow as wf
from halo_harness.orchestra.gate import quality_gate, send_back
from halo_harness.orchestra.handoff_run import stuck
from halo_harness.orchestra.goal import load_goal, repo_root_of, run_meta, set_lead_holder
from halo_harness.orchestra.index import index_file
from halo_harness.orchestra.lanes import load_lane
from halo_harness.orchestra.merge import merge_lanes
from halo_harness.orchestra.plan import await_plan
from halo_harness.orchestra.report import load_report, write_report
from halo_harness.orchestra.split import Job, StopRun, load_split, split_goal
from halo_harness.orchestra.stale import StaleLanes
from halo_harness.orchestra.workers import run_lane, start_workers

LEAD_HOLDER = "orchestra/lead"


def stop_path(run_dir) -> Path:
    return Path(run_dir) / "stop.json"


def request_stop(run_dir, reason: str = "stopped by the user") -> None:
    jsonl.write_json(stop_path(run_dir), {"reason": reason, "ts": time.time()})
    run_events.log(run_dir, "state", f"stop requested: {reason}", step="stop")


def stop_requested(run_dir) -> Optional[str]:
    data = jsonl.read_json(stop_path(run_dir), None)
    return str(data.get("reason") or "stopped by the user") if isinstance(data, dict) else None


class Flow:
    """workflow.json plus the event pump."""

    def __init__(self, run_dir: Path, on_event: Optional[Callable]):
        self.run_dir = run_dir
        self.path = run_dir / "workflow.json"
        self.on_event = on_event
        self.seen = len(run_events.read(run_dir))
        self.lock = threading.RLock()

    def graph(self) -> dict:
        return jsonl.read_json(self.path, {}) or {}

    def set(self, step_id: str, state: str, text: str = "") -> None:
        with self.lock:
            graph = self.graph()
            if wf.step(graph, step_id).get("state") != state:
                jsonl.write_json(self.path, wf.advance(graph, step_id, state))
                lane = wf.step(graph, step_id).get("lane")
                run_events.log(self.run_dir, "state", f"{step_id} {state}" + (f": {text}" if text else ""),
                               lane=lane, step=step_id, state=state)
            self.pump()

    def loop_back(self, lane: int) -> None:
        with self.lock:
            jsonl.write_json(self.path, wf.loop_back(self.graph(), lane))
            run_events.log(self.run_dir, "gate", f"lane {lane} sent back to its worker", lane=lane,
                           step=wf.worker_id(lane), state="pending")
            self.pump()

    def layer(self, jobs: list) -> None:
        """3.0.9.0: lanes with upstreams hang off them (workflow.designed_graph's `after`); once."""
        from halo_harness.orchestra.handoff_spec import edge_label
        lane_of = {job.id: job.worker for job in jobs}
        after = {job.worker: [lane_of[u] for u in job.upstreams if u in lane_of] for job in jobs if job.upstreams}
        with self.lock:
            graph = self.graph()
            if not after or any(e.get("kind") == "after" for e in graph.get("edges") or []):
                return
            labels = {(lane_of[u], job.worker): edge_label(job.handoff, u) for job in jobs for u in job.upstreams
                      if u in lane_of}
            jsonl.write_json(self.path, wf.with_layers(graph, after, labels))
            run_events.log(self.run_dir, "state", "lanes in layers: " + "; ".join(
                f"lane {n} after {', '.join(f'lane {u}' for u in ups)}" for n, ups in sorted(after.items())),
                step="split", layers=wf.designed_graph(int(graph.get("workers") or 1), after).get("layers"))
            self.pump()

    def running(self) -> list:
        return [s["id"] for s in self.graph().get("steps") or [] if s.get("state") == "running"]

    def first_unfinished(self) -> Optional[str]:
        for s in self.graph().get("steps") or []:
            if s.get("state") not in ("done", "skipped"):
                return s["id"]
        return None

    def pump(self) -> None:
        if self.on_event is None:
            return
        with self.lock:
            new = run_events.read(self.run_dir, since=self.seen)
            self.seen += len(new)
        for entry in new:
            self.on_event(entry)


def goal_units(repo: Path, goal) -> list:
    units = []
    for rel in goal.files:
        path = repo / rel
        if not path.is_file():
            raise StopRun(f"the goal's file {rel} is not in the repo")
        units += index_file(path, root=repo)
    return units


def _check_stop(run_dir) -> None:
    reason = stop_requested(run_dir)
    if reason:
        raise StopRun(reason)


def run(run_dir, *, model_calls: Callable, spawn: Callable, judge: Callable,
        clock: Callable = time.time, on_event: Optional[Callable] = None, plan_poll_s: float = 0.5) -> dict:
    run_dir = Path(run_dir)
    goal = load_goal(run_dir / "goal.json")
    done = load_report(run_dir)
    if done and done.get("status") == "finished":
        return done
    if stop_path(run_dir).exists():
        stop_path(run_dir).unlink()
    lead = run_meta(run_dir).get("lead_holder")
    if not lead:
        lead = LEAD_HOLDER
        set_lead_holder(run_dir, lead)
    flow = Flow(run_dir, on_event)
    resume_at = flow.first_unfinished()
    if resume_at and resume_at != "goal":
        run_events.log(run_dir, "state", f"resume: picking up at {resume_at}", step=resume_at)
    repo = repo_root_of(run_dir)
    lanes, gate = [], None
    stale = StaleLanes(run_dir, goal, lambda: lanes, flow, clock)

    def respawn(lane, text: str) -> None:
        flow.set(wf.worker_id(lane.n), "running", "piece sent back")
        lane.update(returned_text=text[-2000:])  # 3.1.8.0 R2: what came back, for a replan's contrast
        run_lane(run_dir, goal, lane, spawn, clock=clock, retry_text=text)
        flow.set(wf.worker_id(lane.n), "failed" if lane.state == "failed" else "done")
        stale.rewritten(lane, respawn)

    def respawn_in_merge(lane, text: str) -> None:
        respawn(lane, text)
        flow.set("merge", "running", f"merging lane {lane.n} again")

    try:
        flow.set("goal", "done")
        flow.set("lead", "running")
        split = load_split(run_dir)
        if split is None:
            base = gitops.head(repo)
            flow.set("split", "running")
            split_goal(run_dir, goal, goal_units(repo, goal), call_model=model_calls, base=base,
                       lead_holder=lead)
            split = load_split(run_dir)
        jobs = [Job.from_dict(j) for j in split["jobs"]]
        base = split.get("base") or gitops.head(repo)
        flow.set("lead", "done")
        if goal.plan == "review":  # 3.0.9.0 R2: the split waits for the reviewed plan (orchestra/plan.py)
            jobs = await_plan(run_dir, flow, jobs, check_stop=lambda: _check_stop(run_dir), poll_s=plan_poll_s)
        flow.set("split", "done", f"{len(jobs)} job(s)")
        forecast.write_quietly(run_dir, [job.to_dict() for job in jobs])
        for s in [s for s in wf.steps_of_kind(flow.graph(), "worker") if s["lane"] not in {j.worker for j in jobs}]:
            flow.set(s["id"], "skipped")  # 3.1.8.0 R2: a replan's lanes need not be 1..N (supervise/replan_apply.py)
        _check_stop(run_dir)
        flow.layer(jobs)
        for job in jobs:
            lane = load_lane(run_dir, job.worker)
            if (lane is None or lane.state not in ("written", "in_review", "merged")) and not job.upstreams:
                flow.set(wf.worker_id(job.worker), "running")
        lanes = start_workers(run_dir, goal, jobs, spawn=spawn, base=base, clock=clock,
                              on_lane=lambda lane: flow.set(wf.worker_id(lane.n),
                                                            "failed" if lane.state == "failed" else "done"),
                              on_start=lambda lane: flow.set(wf.worker_id(lane.n), "running"))
        waiting = stuck(lanes)
        for lane in lanes:
            if lane.state != "waiting":
                flow.set(wf.worker_id(lane.n), "failed" if lane.state == "failed" else "done")
        failed = [lane for lane in lanes if lane.state == "failed"]
        if failed or waiting:
            raise StopRun("; ".join([f"lane {l.n}: {l.data().get('error') or 'failed'}" for l in failed]
                                    + [f"lane {l.n} waits: {why}" for l, why in waiting]))
        while True:
            _check_stop(run_dir)
            flow.set("merge", "running")
            result = merge_lanes(run_dir, goal, lanes, judge=judge, base=base, respawn=respawn_in_merge,
                                 on_return=lambda lane: (flow.loop_back(lane.n), stale.sent_back(lane)),
                                 on_merged=lambda lane: flow.pump(), clock=clock)
            flow.set("merge", "done", f"{len(result.merged)} branch(es) merged")
            _check_stop(run_dir)
            flow.set("test", "running")
            gate = quality_gate(run_dir, goal, lanes, run_dir / "wt" / "merge", ref=result.branch)
            run_events.log(run_dir, "gate", f"tests {'pass' if gate.tests.ok else 'fail'} on {result.branch}",
                           tests_ok=gate.tests.ok, returncode=gate.tests.returncode, record_ok=gate.record_ok,
                           back=gate.back)
            flow.set("test", "done" if gate.tests.ok else "failed")
            flow.set("gate", "running")
            if gate.ok:
                flow.set("gate", "done")
                break
            if gate.stop_reason:
                raise StopRun(gate.stop_reason)
            for n in gate.back:
                lane = next(l for l in lanes if l.n == n)
                send_back(lane, lambda k: f"the gate sent the piece back ({k}/{goal.return_cap})", clock=clock)
                flow.loop_back(n)
                stale.sent_back(lane)
                respawn(lane, f"The tests fail on the finished branch {result.branch}:\n{gate.tests.tail}")
                if lane.state == "failed":
                    raise StopRun(f"lane {n}'s worker failed after the gate sent its piece back")
        report = write_report(run_dir, goal=goal, lanes=lanes, gate=gate, status="finished", clock=clock)
        flow.set("done", "done", f"{result.branch} at {str(report.get('finished') or '')[:12]}")
    except (StopRun, gitops.GitError) as e:
        for step_id in flow.running():
            flow.set(step_id, "failed")
        report = write_report(run_dir, goal=goal, lanes=lanes, gate=gate, status="stopped", stop_reason=str(e),
                              clock=clock)
    run_events.log(run_dir, "report", f"run {report['status']}"
                   + (f": {report['stop_reason']}" if report.get("stop_reason") else ""),
                   status=report["status"], checks={c["id"]: c["ok"] for c in report["checks"]})
    flow.pump()
    return report
