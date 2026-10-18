"""halo_harness.studio.orchestra_plan_api -- the reviewed plan's Studio
routes (Halo 3.0.9.0 round R2; orchestra/plan.py), beside
studio/orchestra_api.py's:

    GET  orchestra/<run>/plan      {run_id, state, planned, mode, source, jobs, lead_jobs, problems,
                                    preflight, units, decision}
    PUT  orchestra/<run>/plan {jobs}     validate, keep the draft (plan.draft.json) -> {ok, problems}; never approves
    POST orchestra/<run>/approve {jobs?} validate (the body's jobs, else the draft, else the split) and write
                                         plan.json approved -> {ok, run_id, jobs}; 422 {error, problems}
    POST orchestra/<run>/reject {reason} plan.json rejected -> {ok, reason}; 422 without a reason

`problems` rows are `{jobs, field, text}` (plan_check.py); `preflight` is
the run's lineup findings (lineup_preflight.py). Approve and reject answer
409 once the plan is decided or when the run is not waiting for review.
When no runner waits for the run (Studio restarted while it waited: no live
thread and a stale `plan.wait.json`), they start one (orchestra_api.RUNNER,
the seam tests set) so the run takes the decision and goes on (or stops).
"""

from __future__ import annotations

from halo_harness.orchestra import plan as P
from halo_harness.studio import orchestra_live as live
from halo_harness.studio import orchestra_model as OM


def _run(req):
    run_dir = OM.find_run(OM.repo_of(req.cwd), req.params["run"])
    return (run_dir, None) if run_dir else (None, (404, {"error": f"no Orchestra run {req.params['run']!r} in this repo"}))


def _lineup_findings(run_dir, state_dir) -> list:
    from halo_harness.lineup_preflight import lineup_problems
    lineup = str(OM.goal_of(run_dir).get("lineup") or "") or None
    try:
        return lineup_problems(lineup, cwd=OM.repo_of(run_dir), state_dir=state_dir) if lineup else []
    except Exception:
        return []


def get_plan(req):
    run_dir, err = _run(req)
    if err:
        return err
    from halo_harness.orchestra.report import load_report
    jobs, report = P.current_jobs(run_dir), load_report(run_dir)
    return 200, {"run_id": run_dir.name, "state": OM.run_state(run_dir, live.live_id() == run_dir.name, report),
                 "planned": P.is_planned(run_dir), "mode": OM.goal_of(run_dir).get("plan") or "auto",
                 "source": "draft" if P.read_draft(run_dir) is not None else "split", "jobs": jobs,
                 "lead_jobs": P.lead_jobs(run_dir), "problems": P.check(run_dir, jobs, state_dir=req.state_dir) if jobs else [],
                 "preflight": _lineup_findings(run_dir, req.state_dir), "units": P.unit_keys(run_dir) or [],
                 "decision": P.read_decision(run_dir)}


def _jobs_of(req):
    jobs = req.body.get("jobs") if isinstance(req.body, dict) else None
    if not isinstance(jobs, list) or not all(isinstance(j, dict) for j in jobs):
        return None, (422, {"error": 'send the plan as {"jobs": [{id, title, claims, ...}, ...]}',
                            "problems": [{"jobs": [], "field": "", "text": "the body has no jobs list"}]})
    return jobs, None


def put_plan(req):
    run_dir, err = _run(req)
    if err:
        return err
    jobs, err = _jobs_of(req)
    if err:
        return err
    if P.read_decision(run_dir) is not None:
        return 409, {"error": "the plan is already decided", "decision": P.read_decision(run_dir)}
    P.write_draft(run_dir, jobs)
    problems = P.check(run_dir, jobs, state_dir=req.state_dir)
    return 200, {"ok": not problems, "problems": problems, "jobs": jobs}


def _decidable(run_dir):
    decision = P.read_decision(run_dir)
    if decision is not None:
        return 409, {"error": f"the plan is already {'approved' if decision.get('approved') else 'rejected'}",
                     "decision": decision}
    if (OM.goal_of(run_dir).get("plan") or "auto") != "review":
        return 409, {"error": "this run does not review its plan (its goal has plan: auto)"}
    if not P.split_jobs(run_dir):
        return 409, {"error": "there is no plan yet: the lead has not split the goal"}
    if not P.is_planned(run_dir) and live.live_id() == run_dir.name:
        return 409, {"error": "this run is not waiting for review"}
    return None


def _resume(req, run_dir) -> bool:
    """Start the runner when none is live for this run, so it takes the decision now."""
    if live.live_id() is not None or P.waiting_alive(run_dir):
        return False
    from halo_harness.orchestra.goal import load_goal
    from halo_harness.studio import orchestra_api
    return live.start(run_dir, load_goal(run_dir / "goal.json"), runner=orchestra_api.RUNNER,
                      publish=orchestra_api._publisher(req))


def post_approve(req):
    run_dir, err = _run(req)
    if err:
        return err
    busy = _decidable(run_dir)
    if busy:
        return busy
    if isinstance(req.body, dict) and "jobs" in req.body:
        jobs, err = _jobs_of(req)
        if err:
            return err
    else:
        jobs = P.current_jobs(run_dir)
    problems = P.approve(run_dir, jobs, by="studio", state_dir=req.state_dir)
    if problems:
        return 422, {"error": f"the plan has {len(problems)} problem(s): " + problems[0]["text"], "problems": problems}
    resumed = _resume(req, run_dir)
    return 200, {"ok": True, "run_id": run_dir.name, "jobs": P.read_decision(run_dir)["jobs"], "resumed": resumed}


def post_reject(req):
    run_dir, err = _run(req)
    if err:
        return err
    busy = _decidable(run_dir)
    if busy:
        return busy
    reason = str((req.body or {}).get("reason") or "").strip()
    if not reason:
        return 422, {"error": "say why the plan is rejected: {\"reason\": \"...\"}", "problems": []}
    P.reject(run_dir, reason, by="studio")
    return 200, {"ok": True, "reason": reason, "resumed": _resume(req, run_dir)}


_RUN = r"(?P<run>[A-Za-z0-9_-]+)"
ROUTES = [
    ("GET", rf"^orchestra/{_RUN}/plan$", get_plan), ("PUT", rf"^orchestra/{_RUN}/plan$", put_plan),
    ("POST", rf"^orchestra/{_RUN}/approve$", post_approve), ("POST", rf"^orchestra/{_RUN}/reject$", post_reject),
]
