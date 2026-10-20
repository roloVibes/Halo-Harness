"""halo_harness.orchestra.probe_runs -- the coach's probe runs (Halo 3.1.6.0
R2): one Orchestra run per candidate overlay, kept under the reference run
so no run list ever shows one (`goal.list_runs` reads `<repo>/.halo/orchestra`
only):

    <run>/probes/<cand-id>/       goal.new_run(repo, goal, parent=<run>): run.json (repo_root, parent),
                                  goal.json (the reference's goal, `plan: review`, `budget_usd` = the cap),
                                  split.json (the reference's: the same base commit, the lead not asked
                                  again), plan.json (approved: the reference's jobs with the overlay's
                                  per-job bio / model / after, taken on the plan wait's first poll),
                                  lanes/, events.jsonl, report.json, deliverable.patch (base..finished)
    <run>/probes/reference.patch  the reference's own base..finished (orchestra/coach_compare.py)

A lane's worker gets the overlay through adapters.spawn_worker's `team=`
and `cwd_overlay=` (orchestra/probe_overlay.py); the lead's model and effort
reach the lead and the merge judge through `model_calls` / `judge`.

The budget: each probe run may spend `cap` (the reference's cost_usd x
`coach.probe.budget_factor`). Before a lane's worker starts, what the probe
spent + the forecasts of its lanes still running + this lane's forecast
(what the reference's lane cost: the same job from the same base; else its
forecast.json line) is checked against the cap; over it the worker does not
start, the run is asked to stop (`stop.json`) and the outcome's
`stop_reason` is `budget`.

`cleanup(probe_dir)` (after the compare) removes the probe's worktrees and
deletes its branches (`orchestra/<cand-id>`, `-worker-<n>`, `-base-<n>`); the
folder keeps its reports and its patch. `ADAPTERS(probe_dir, goal, cand,
facts, seen)` replaces `real_adapters` (tests, Studio's Chrome rig).
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import gitops, jsonl
from halo_harness.orchestra.coach_probe_schema import for_bio

ADAPTERS: Optional[Callable] = None
PATCH, REF_PATCH = "deliverable.patch", "reference.patch"
_JOB_KEYS = ("id", "title", "claims", "handoff", "after", "bio", "model", "est_tokens")


def probes_dir(run_dir) -> Path:
    return Path(run_dir) / "probes"


def plan_jobs(cand: dict, f: dict) -> list:
    """The reference's jobs with the overlay's per-job bio (the lane's), model and `after`."""
    overlay = cand.get("overlay") or {}
    edits = {r["job"]: list(r["after"]) for r in overlay.get("plan") or []}
    by_lane = {l["n"]: l for l in f.get("lanes") or []}
    out = []
    for j in f.get("jobs") or []:
        job = {k: v for k, v in j.items() if k in _JOB_KEYS}
        bio = str(j.get("bio") or (by_lane.get(int(j.get("worker") or 0)) or {}).get("bio") or "")
        if bio:
            job["bio"] = bio
        model = for_bio(overlay, bio).get("model")
        if model:
            job["model"] = model
        if str(j.get("id")) in edits:
            job["after"] = edits[str(j.get("id"))]
        out.append(job)
    return out


def checked(probe_dir, jobs: list, f: dict) -> "tuple[list, list, list]":
    """(jobs, notes, problems left): a bio or model the plan check names is dropped from its job, any other
    problem puts its jobs back as the reference ran them."""
    from halo_harness.orchestra import plan as P
    ref = {str(j.get("id")): j for j in f.get("jobs") or []}
    notes = []
    for p in P.check(probe_dir, jobs):
        for jid in p.get("jobs") or []:
            job = next((j for j in jobs if str(j.get("id")) == jid), None)
            if job is None:
                continue
            if p.get("field") in ("bio", "model") and p["field"] in job:
                job.pop(p["field"])
            elif jid in ref:
                job.clear()
                job.update({k: v for k, v in ref[jid].items() if k in _JOB_KEYS})
            notes.append(f"{jid}: {p['text']} (left as the run had it)")
    return jobs, notes, [p["text"] for p in P.check(probe_dir, jobs)]


def create(run_dir, cand: dict, f: dict, cap: Optional[float]) -> "tuple[Path, list]":
    """The probe's folder with its goal, the reference's split and the approved plan. ValueError: no plan fits."""
    from halo_harness.orchestra import plan as P
    from halo_harness.orchestra.goal import Goal, new_run
    run_dir = Path(run_dir)
    g = Goal.from_dict(f["goal"].to_dict())
    g.plan, g.budget_usd = "review", (round(cap, 6) if cap is not None else None)
    probe = new_run(f["repo"], g, parent=run_dir, name=cand["id"])
    split = dict(jsonl.read_json(run_dir / "split.json", {}) or {})
    split.pop("plan", None)
    split.update(lead_cost_usd=0.0, lead_sessions=[], probe_of=run_dir.name)
    jsonl.write_json(probe / "split.json", split)
    jobs, notes, problems = checked(probe, plan_jobs(cand, f), f)
    if problems or P.approve(probe, jobs, by="coach-probe"):
        raise ValueError("the probe's plan does not pass the check: " + "; ".join(problems or ["see plan.bad.json"]))
    return probe, notes


class Budget:
    """The probe's cap, checked before each lane's worker starts (team/budget.py's hold_if_over, per lane)."""

    def __init__(self, probe_dir, cap: Optional[float], ref_lanes: dict):
        self.dir, self.cap, self.ref = Path(probe_dir), cap, dict(ref_lanes)
        self.lock, self.running, self.hit = threading.Lock(), {}, ""

    def spent(self) -> float:
        lanes = sum(float((jsonl.read_json(p, {}) or {}).get("cost_usd") or 0.0) for p in (self.dir / "lanes").glob("*.json"))
        merge = jsonl.read_json(self.dir / "merge.json", {}) or {}
        return lanes + sum(float(c.get("cost_usd") or 0.0) for c in merge.get("conflicts") or [])

    def forecast(self, n: int) -> float:
        """What lane n is expected to cost: what the reference's lane n cost (the same job from the same base),
        else its forecast.json line."""
        if float(self.ref.get(n) or 0.0) > 0:
            return float(self.ref[n])
        from halo_harness.orchestra import forecast
        line = next((l for l in (forecast.read(self.dir) or {}).get("lanes") or [] if l.get("lane") == n), {})
        return float(line.get("usd") or 0.0)

    def guard(self, spawn: Callable) -> Callable:
        from halo_harness.orchestra.run import request_stop

        def guarded(lane):
            with self.lock:
                if self.cap is not None:
                    spent, ahead, own = self.spent(), sum(self.running.values()), self.forecast(lane.n)
                    if self.hit or spent + ahead + own > self.cap + 1e-12:
                        self.hit = self.hit or (f"lane {lane.n} not started: spent ${spent:.4f} + running ${ahead:.4f} + "
                                                f"its forecast ${own:.4f} is over the probe's cap ${self.cap:.4f}")
                        request_stop(self.dir, f"budget: {self.hit}")
                        return {"ok": True, "text": f"STOP: budget: {self.hit}", "cost_usd": 0.0}
                    self.running[lane.n] = own
            try:
                return spawn(lane)
            finally:
                with self.lock:
                    self.running.pop(lane.n, None)
        return guarded


def real_adapters(probe_dir, goal, cand: dict, f: dict, seen: dict, runner: Callable = subprocess.run) -> dict:
    """run()'s callables for one probe: the workers through spawn_worker with the overlay, the lead's model."""
    from halo_harness.orchestra import adapters as A
    from halo_harness.orchestra.probe_overlay import writer
    lead = (cand.get("overlay") or {}).get("lead") or {}
    spawn = A.spawn_worker(None, goal.worker, run_dir=probe_dir, runner=runner, team=f.get("lineup") or None,
                           cwd_overlay=writer(cand.get("overlay") or {}, f, seen))
    return {"model_calls": A.model_call(lead.get("model"), goal.lead, cwd=probe_dir, effort=lead.get("effort")),
            "spawn": spawn, "judge": A.fresh_judge(lead.get("model"), goal.lead, cwd=probe_dir, effort=lead.get("effort"))}


def run_one(run_dir, cand: dict, f: dict, cap: Optional[float], on_step: Optional[Callable] = None) -> dict:
    """One candidate's probe run to its report and deliverable; never raises."""
    from halo_harness.orchestra.coach_compare import deliverable
    from halo_harness.orchestra.goal import load_goal
    from halo_harness.orchestra.run import run
    say = on_step or (lambda text, **data: None)
    out = {"id": cand["id"], "kind": cand["kind"], "pair": cand.get("pair", 1), "cap_usd": cap}
    if cand.get("skipped"):
        return dict(out, status="skipped", stop_reason="", error=cand["skipped"])
    try:
        probe, notes = create(run_dir, cand, f, cap)
    except (ValueError, gitops.GitError, OSError) as e:
        return dict(out, status="failed", stop_reason="plan", error=str(e))
    say(f"{cand['id']}: running {len(f.get('jobs') or [])} lane(s) under the run's base", cand=cand["id"])
    seen: dict = {}
    out.update(dir=f"probes/{probe.name}", notes=notes)
    budget = Budget(probe, cap, {l["n"]: l["cost_usd"] for l in f.get("lanes") or []})
    try:
        made = (ADAPTERS or real_adapters)(probe, load_goal(probe / "goal.json"), cand, f, seen)
        report = run(probe, model_calls=made["model_calls"], spawn=budget.guard(made["spawn"]), judge=made["judge"],
                     plan_poll_s=0.05, on_event=lambda e: say(f"{cand['id']}: {e.get('text')}", cand=cand["id"])
                     if e.get("kind") in ("gate", "report") else None)
    except Exception as e:  # anything run() did not turn into a stopped report
        report = {"status": "stopped", "stop_reason": f"{type(e).__name__}: {e}"}
    try:
        got = deliverable(probe, patch_path=probe / PATCH)
    except Exception as e:  # a repo git cannot read: the probe delivered nothing it can show
        got, report = {}, dict(report, stop_reason=f"{report.get('stop_reason') or ''} (no deliverable: {e})".strip())
    say(f"{cand['id']}: {report.get('status')}" + (", stopped at the budget" if budget.hit else ""), cand=cand["id"])
    return dict(out, status=report.get("status"), stop_reason="budget" if budget.hit else str(report.get("stop_reason") or ""),
                stop_text=str(report.get("stop_reason") or ""), budget_hit=budget.hit,
                delivered={str(n): v for n, v in sorted(seen.items(), key=lambda kv: str(kv[0]))}, deliverable=got)


def run_all(run_dir, cands: list, f: dict, cap: Optional[float], on_step: Optional[Callable] = None) -> dict:
    """{cand id: outcome}: the pairs on threads (in parallel when there are several), each pair's two in turn."""
    pairs: dict = {}
    for c in cands:
        pairs.setdefault(c.get("pair", 1), []).append(c)

    def one_pair(group: list) -> list:
        return [run_one(run_dir, c, f, cap, on_step) for c in group]
    groups = [pairs[k] for k in sorted(pairs)]
    if len(groups) <= 1:
        rows = [o for g in groups for o in one_pair(g)]
    else:
        with ThreadPoolExecutor(max_workers=len(groups), thread_name_prefix="coach-probe") as pool:
            rows = [o for fut in [pool.submit(one_pair, g) for g in groups] for o in fut.result()]
    return {o["id"]: o for o in rows}


def branches_of(repo, name: str) -> list:
    out = gitops.git(["for-each-ref", "--format=%(refname:short)", f"refs/heads/orchestra/{name}",
                      f"refs/heads/orchestra/{name}-*"], repo).stdout
    return [b.strip() for b in out.splitlines() if b.strip()]


def cleanup(probe_dir) -> dict:
    """The probe's worktrees removed and its branches deleted; `{worktrees, branches}` it removed."""
    from halo_harness.orchestra.goal import repo_root_of
    probe_dir = Path(probe_dir)
    repo, removed = repo_root_of(probe_dir), []
    for wt in sorted((probe_dir / "wt").glob("*")) if (probe_dir / "wt").is_dir() else []:
        if wt.is_dir():
            gitops.worktree_remove(repo, wt)
            removed.append(wt.name)
    shutil.rmtree(probe_dir / "wt", ignore_errors=True)
    gitops.git(["worktree", "prune"], repo)
    gone = [b for b in branches_of(repo, probe_dir.name) if gitops.git(["branch", "-D", b], repo).returncode == 0]
    return {"worktrees": removed, "branches": gone, "ts": round(time.time(), 3)}
