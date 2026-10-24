"""halo_harness.studio.orchestra_api -- `/api/orchestra/...`, the Studio
Orchestra view's backend (Halo 3.0.3.0 round R4). Same loopback / origin /
token guard as every Studio route; the runs are those of the git repo that
holds Studio's folder (`req.cwd`).

    GET  orchestra/runs                    [{run_id, created, state, workers, goal_what, cost_usd}]
    POST orchestra/run                     {what, done_when, stop_when, workers, ..., model?, dry_run?, force?} -> 201 {run_id}
                                           (422 {error, problems, preflight: true} when the lineup preflight blocks)
    GET  orchestra/<run>                   {run, goal, workflow, split, lanes, claims, merge, report, events_count, live}
    GET  orchestra/<run>/events?since=N    {events, next}
    GET  orchestra/<run>/file?path=<rel>   {path, base, regions}
    POST orchestra/<run>/stop              {ok}
    POST orchestra/<run>/release {key}     the live claim on key lets go
    POST orchestra/<run>/steal {key}       the run's lead takes key
    GET|PUT orchestra/<run>/plan, POST orchestra/<run>/approve|reject   the reviewed plan (orchestra_plan_api.py)

3.0.9.0 R2: `POST run` takes `review: true` (the goal's `plan: review`: the
run pauses after the split until the plan is approved). 3.2.0.0 R6: `POST
run {workflow: <pack>/<name>, inputs: {k: v}, model?}` compiles a pack's
workflow to its goal first (`halo workflow run`'s compile; its lines on a 422).
3.2.1.0 R1: a goal (not a workflow) takes its lineup's acceptance first
(`packs.lineup_run.goal_defaults`: an empty test, `plan: review`); the 201
then carries `taken` (the lines saying what it took), `test` and `plan` (a
test you typed wins).

`POST run` starts the runner on a daemon thread (orchestra_live.py) and
answers at once; a second POST while a run is live is a 409 naming it.
`RUNNER(run_dir, goal, model)` returns run()'s `model_calls` / `spawn` /
`judge` (None = the real adapters); tests set it to the fakes.
"""

from __future__ import annotations

import re

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra.goal import Goal, new_run, norm_file, validate_goal
from halo_harness.studio import orchestra_live as live
from halo_harness.studio import orchestra_model as OM
from halo_harness.studio.orchestra_plan_api import ROUTES as PLAN_ROUTES

RUNNER = None
RUN_FIELDS = tuple(Goal.__dataclass_fields__)


def _bad(lines, status: int = 422):
    lines = [lines] if isinstance(lines, str) else list(lines)
    return status, {"error": lines[0] if lines else "invalid", "problems": lines}


def _repo(req):
    return OM.repo_of(req.cwd)


def _run(req):
    run_dir = OM.find_run(_repo(req), req.params["run"])
    return (run_dir, None) if run_dir else (None, (404, {"error": f"no Orchestra run {req.params['run']!r} in this repo"}))


def list_runs(req):
    return 200, OM.run_rows(_repo(req), live.live_id())


def post_run(req):
    body = req.body
    compiled = None
    if body.get("workflow"):  # 3.2.0.0 R6: a pack's workflow, compiled first (studio/workflow_api.py compiled_goal)
        from halo_harness.studio.workflow_api import compiled_goal
        compiled, err = compiled_goal(body, _repo(req))
        if err is not None:
            return err
    data = compiled.to_dict() if compiled is not None else {k: body[k] for k in RUN_FIELDS if k in body}
    if body.get("review"):
        data["plan"] = "review"
    if isinstance(data.get("files"), str):
        data["files"] = [f.strip() for f in data["files"].split(",") if f.strip()]
    problems = validate_goal(data)
    if problems:
        return _bad(problems)
    repo = _repo(req)
    from halo_harness.worktree import repo_root
    if repo_root(repo) is None:
        return _bad(f"Studio's folder ({req.cwd}) is not in a git repo: start halo studio in the repo the run works on")
    missing = [f for f in data.get("files") or [] if not (repo / norm_file(f)).is_file()]
    if missing:
        return _bad([f"{f} is not a file in {repo}" for f in missing])
    taken: list = []
    if compiled is None:  # 3.2.1.0 R1: the lineup's acceptance (test, review), as `halo orchestra new` takes it
        from halo_harness.packs.lineup_run import goal_defaults
        g = Goal.from_dict(data)
        taken = goal_defaults(g, cwd=repo, state_dir=req.state_dir, explicit_test=bool(str(data.get("test") or "").strip()))
        data = g.to_dict()
    if not body.get("force"):  # 3.0.7.0 R1: the run-start preflight (lineup_preflight.py)
        from halo_harness.lineup_preflight import blocking, lineup_problems, refusal_body
        problems = lineup_problems(str(data.get("lineup") or "") or None, cwd=repo, state_dir=req.state_dir)
        if blocking(problems):
            return 422, refusal_body(problems, what="the Orchestra run")
    busy = live.live_id()
    if busy:
        return 409, {"error": f"run {busy} is still running: stop it or wait for its report", "run_id": busy}
    from halo_harness.supervise.heartbeat import other_live_in
    other = other_live_in(repo)
    if other is not None:  # 3.1.8.0 R1: the supervisor (or a `halo orchestra run`) already drives a run here
        return 409, {"error": f"run {other['run_id']} is running elsewhere ({other['by'] or 'another process'})",
                     "run_id": other["run_id"]}
    goal = compiled or Goal.from_dict(data)
    run_dir = new_run(repo, goal)
    model = str(body.get("model") or "") or None
    started = live.start(run_dir, goal, model=model, dry_run=bool(body.get("dry_run")), runner=RUNNER,
                         publish=_publisher(req))
    if not started:
        return 409, {"error": f"run {live.live_id()} is still running", "run_id": live.live_id()}
    took = {"taken": taken, "test": goal.test, "plan": goal.plan} if taken else {}
    return 201, {"run_id": run_dir.name, "dry_run": bool(body.get("dry_run")), **took}


def _publisher(req):
    if req.server is None:
        return None
    from halo_harness.studio.events import bridge_for
    bridge = bridge_for(req.server)
    return bridge.publish_local


def get_run(req):
    run_dir, err = _run(req)
    return err or (200, OM.run_payload(run_dir, live.live_id() == run_dir.name))


def get_events(req):
    run_dir, err = _run(req)
    if err:
        return err
    try:
        since = max(0, int(req.query.get("since") or 0))
    except ValueError:
        return _bad("since is a whole number (the count of lines already seen)")
    entries = run_events.read(run_dir, since=since)
    return 200, {"events": entries, "next": since + len(entries)}


def get_file(req):
    run_dir, err = _run(req)
    if err:
        return err
    rel = norm_file(str(req.query.get("path") or ""))
    files = [norm_file(f) for f in OM.goal_of(run_dir).get("files") or []]
    if not rel and files:
        rel = files[0]
    if rel not in files:
        return _bad(f"{rel or '(none)'} is not one of the goal's files ({', '.join(files) or 'none'})")
    return 200, OM.file_view(run_dir, rel)


def post_stop(req):
    run_dir, err = _run(req)
    if err:
        return err
    from halo_harness.orchestra.run import request_stop
    reason = str(req.body.get("reason") or "stopped from Studio")
    request_stop(run_dir, reason)
    return 200, {"ok": True, "live": live.live_id() == run_dir.name, "reason": reason}


def _key(req, run_dir):
    key = str(req.body.get("key") or "").strip()
    if not key:
        return None, _bad("say which claim: {\"key\": \"file#unit\"}")
    files = [norm_file(f) for f in OM.goal_of(run_dir).get("files") or []]
    if key.partition("#")[0] not in files:
        return None, _bad(f"{key} is not a unit of the goal's files ({', '.join(files) or 'none'})")
    return key, None


def post_release(req):
    run_dir, err = _run(req)
    if err:
        return err
    key, err = _key(req, run_dir)
    if err:
        return err
    from halo_harness.orchestra.claims import ClaimLog
    log = ClaimLog(run_dir)
    claim = log.active().get(key)
    if claim is None:
        return _bad(f"nobody holds {key} right now")
    holder = str(req.body.get("holder") or "")
    if holder and holder != claim.holder:
        return 403, {"error": f"{key} is held by {claim.holder}, not {holder}", "holder": claim.holder}
    result = log.release(claim.holder, key, note=str(req.body.get("reason") or "released from Studio"))
    if not result.ok:
        return 403, {"error": str(result)}
    return 200, {"ok": True, "key": key, "holder": claim.holder, "claims": OM.active_claims(run_dir)}


def post_steal(req):
    run_dir, err = _run(req)
    if err:
        return err
    key, err = _key(req, run_dir)
    if err:
        return err
    from halo_harness.orchestra.claims import ClaimLog
    log = ClaimLog(run_dir)
    by = str(req.body.get("by") or log.lead_holder() or "studio/main")
    result = log.steal(key, by, str(req.body.get("reason") or "taken by the lead from Studio"))
    if not result.ok:
        return 403, {"error": str(result), "lead": log.lead_holder()}
    return 200, {"ok": True, "key": key, "holder": by, "claims": OM.active_claims(run_dir)}


def _run_artifact(req):
    from halo_harness.studio.workflow_api import run_artifact
    return run_artifact(req)


_RUN = r"(?P<run>[A-Za-z0-9_-]+)"
ROUTES = [
    ("GET", r"^orchestra/runs$", list_runs), ("POST", r"^orchestra/run$", post_run),
    ("GET", rf"^orchestra/{_RUN}$", get_run), ("GET", rf"^orchestra/{_RUN}/events$", get_events),
    ("GET", rf"^orchestra/{_RUN}/file$", get_file), ("POST", rf"^orchestra/{_RUN}/stop$", post_stop),
    ("POST", rf"^orchestra/{_RUN}/release$", post_release), ("POST", rf"^orchestra/{_RUN}/steal$", post_steal),
    ("GET", rf"^orchestra/{_RUN}/artifact/(?P<name>[A-Za-z0-9_-]+)$", _run_artifact),  # 3.2.0.0 R5: a workflow's output
] + PLAN_ROUTES


def dispatch_orchestra(req):
    for method, pattern, fn in ROUTES:
        m = re.match(pattern, req.path)
        if m and method == req.method:
            req.params = dict(m.groupdict())
            return fn(req)
    if any(re.match(p, req.path) for _, p, _ in ROUTES):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
