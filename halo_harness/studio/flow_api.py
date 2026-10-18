"""halo_harness.studio.flow_api -- `/api/flow/...`, Studio's Flow backend
(Halo 3.0.4.0 round R5). Same loopback / origin / token guard as every
Studio route; the runs are `<state>/flows/runs/` (docs/FLOWS.md).

    GET  flow/templates                  [{name, source: template|user|project, steps: [{id, kind, uses, deps, layer, gate}], form, budget_usd}]
    PUT  flow/templates/<name> {yaml} | {order}       the flow file, validated (flow_api_edit.py, 3.0.9.0 R2)
    GET  flow/runs                       [{run, name, status, created, cost_usd, project, live, waiting_step?}]
    POST flow/runs {template|name, intake, model?, set?, yes?, start?, force?}  -> 201 {run, started}
                                         (422 {error, problems, preflight: true} when the lineup preflight blocks)
    GET  flow/runs/<id>                  {flow, steps, gate, report, posts, metrics_tail, artboards, events, live, project}
    GET  flow/runs/<id>/events?since=N   {events, next}
    POST flow/runs/<id>/assets {name, data_base64}   -> 201 {name, size, kind, path, rel, project, intake}
    POST flow/runs/<id>/stop {reason?}   {ok, live}
    POST flow/runs/<id>/resume {model?, yes?}        {run, started}
    POST flow/runs/<id>/answer {step, action, instruction?, round?}  {ok, message, gate}
    GET  flow/runs/<id>/report | posts?all=1 | metrics?limit=N

`RUNNER` is the adapters factory (the `flows.adapters.Adapters` keywords;
None = the real adapters); tests set it to the fakes.
"""

from __future__ import annotations

import re

from halo_harness.flows import gates, spec as fspec, state
from halo_harness.orchestra import jsonl
from halo_harness.studio import flow_model as FM
from halo_harness.studio import flow_runs as live
from halo_harness.studio.flow_api_edit import ROUTES as EDIT_ROUTES
from halo_harness.studio.flow_assets_api import post_assets as _post_assets
from halo_harness.studio.flow_request import bad as _bad, intake_of, overrides_of

RUNNER = None


def _run(req):
    run_dir = FM.run_dir_of(req.state_dir, req.params["run"])
    return (run_dir, None) if run_dir else (None, (404, {"error": f"no flow run {req.params['run']!r}"}))


def _publisher(req):
    if req.server is None:
        return None
    from halo_harness.studio.events import bridge_for
    return bridge_for(req.server).publish_local


def _start(req, run_dir):
    return live.start(run_dir, factory=RUNNER, model=str(req.body.get("model") or "") or None,
                      auto_accept=bool(req.body.get("yes")), state_dir=req.state_dir, cwd=req.cwd,
                      publish=_publisher(req))


def _busy():
    busy = live.live_id()
    return (409, {"error": f"flow run {busy} is still running: stop it or wait for its report", "run": busy}) if busy else None


def list_templates(req):
    return 200, FM.template_rows(req.cwd, req.state_dir)


def list_runs(req):
    return 200, FM.run_rows(req.state_dir, live.live_id())


def post_run(req):
    body = req.body
    name = str(body.get("template") or body.get("name") or "").strip()
    if not name:
        return _bad("say which flow: {\"template\": \"social-post\"}")
    path = FM.find_flow_file(name, req.cwd, req.state_dir)
    if path is None:
        return 404, {"error": f"no flow {name!r} (templates: {', '.join(fspec.template_names())})"}
    try:
        spec = fspec.load_flow(path)
    except ValueError as e:
        return _bad(str(e))
    intake, err = intake_of(body)
    if err:
        return err
    overrides, err = overrides_of(body.get("set"))
    if err:
        return err
    lines = fspec.validate_flow(spec, cwd=req.cwd, state_dir=req.state_dir)
    if fspec.errors(lines):
        return _bad(lines)
    if not body.get("force"):  # 3.0.7.0 R1: the run-start preflight over the flow's lineups
        from halo_harness.lineup_preflight import blocking, flow_problems, refusal_body
        problems = flow_problems(spec, cwd=req.cwd, state_dir=req.state_dir)
        if blocking(problems):
            return 422, refusal_body(problems, what=f"flow {spec.get('name') or name}")
    start = body.get("start", True) is not False
    if start and _busy():
        return _busy()
    run_dir = state.new_run(spec, intake, source=str(path), state_dir=req.state_dir, overrides=overrides)
    if start and not _start(req, run_dir):
        return _busy() or (409, {"error": "another flow run is live"})
    return 201, {"run": run_dir.name, "started": start, "warnings": [l for l in lines if l.startswith("warning: ")]}


def get_run(req):
    run_dir, err = _run(req)
    return err or (200, FM.run_payload(run_dir, req.state_dir, live.live_id() == run_dir.name))


def get_events(req):
    run_dir, err = _run(req)
    if err:
        return err
    try:
        since = max(0, int(req.query.get("since") or 0))
    except ValueError:
        return _bad("since is a whole number (the count of lines already seen)")
    entries = state.read_events(run_dir, since=since)
    return 200, {"events": entries, "next": since + len(entries)}


def post_assets(req):
    run_dir, err = _run(req)
    return err or _post_assets(req, run_dir)


def post_stop(req):
    run_dir, err = _run(req)
    if err:
        return err
    reason = str(req.body.get("reason") or "stopped from Studio")
    state.request_stop(run_dir, reason)
    return 200, {"ok": True, "live": live.live_id() == run_dir.name, "reason": reason}


def post_resume(req):
    run_dir, err = _run(req)
    if err:
        return err
    report = jsonl.read_json(run_dir / "report.json", None)
    if isinstance(report, dict) and report.get("status") == "finished":
        return 409, {"error": f"flow run {run_dir.name} already finished", "run": run_dir.name}
    busy = _busy()
    if busy:
        return busy
    if not _start(req, run_dir):
        return _busy() or (409, {"error": "another flow run is live"})
    return 200, {"run": run_dir.name, "started": True}


def post_answer(req):
    run_dir, err = _run(req)
    if err:
        return err
    step = str(req.body.get("step") or "").strip()
    action = str(req.body.get("action") or "").strip()
    if not step or not action:
        return _bad("an answer is {\"step\": \"<step id>\", \"action\": \"accept|redo|stop\", \"instruction\": \"...\"}")
    ids = [s.get("id") for s in state.read_flow(run_dir).get("steps") or []]
    n = ids.index(step) + 1 if step in ids else (int(step) if step.isdigit() and 1 <= int(step) <= len(ids) else 0)
    gate = jsonl.read_json(gates.gate_path(run_dir, n), None) if n else None
    if not isinstance(gate, dict):
        return _bad(f"no gate is open at step {step} of run {run_dir.name}")
    rnd = req.body.get("round")
    if rnd not in (None, "") and str(rnd) != str(gate.get("round")):
        return _bad(f"the gate at {step} is at round {gate.get('round')}, not {rnd}: reload it")
    ok, message = gates.write_answer(run_dir, step, action, str(req.body.get("instruction") or ""))
    if not ok:
        return _bad(message)
    return 200, {"ok": True, "message": message, "gate": gate}


def get_report(req):
    run_dir, err = _run(req)
    if err:
        return err
    report = jsonl.read_json(run_dir / "report.json", None)
    return (200, report) if isinstance(report, dict) else (404, {"error": f"flow run {run_dir.name} has no report yet"})


def get_posts(req):
    run_dir, err = _run(req)
    if err:
        return err
    return 200, {"posts": FM.posts_of(run_dir, req.state_dir, everything=req.query.get("all") in ("1", "true"))}


def get_metrics(req):
    run_dir, err = _run(req)
    if err:
        return err
    try:
        limit = max(0, min(1000, int(req.query.get("limit") or FM.METRICS_TAIL)))
    except ValueError:
        return _bad("limit is a whole number")
    return 200, {"metrics": FM.metrics_of(run_dir, req.state_dir, limit)}


_RUN = r"^flow/runs/(?P<run>[A-Za-z0-9_-]+)"
ROUTES = [
    ("GET", r"^flow/templates$", list_templates), ("GET", r"^flow/runs$", list_runs), ("POST", r"^flow/runs$", post_run),
    ("GET", _RUN + "$", get_run), ("GET", _RUN + "/events$", get_events), ("POST", _RUN + "/assets$", post_assets),
    ("POST", _RUN + "/stop$", post_stop), ("POST", _RUN + "/resume$", post_resume),
    ("POST", _RUN + "/answer$", post_answer), ("GET", _RUN + "/report$", get_report),
    ("GET", _RUN + "/posts$", get_posts), ("GET", _RUN + "/metrics$", get_metrics),
] + EDIT_ROUTES  # 3.0.9.0 R2: PUT flow/templates/<name> (flow_api_edit.py)


def dispatch_flow(req):
    for method, pattern, fn in ROUTES:
        m = re.match(pattern, req.path)
        if m and method == req.method:
            req.params = dict(m.groupdict())
            return fn(req)
    if any(re.match(p, req.path) for _, p, _ in ROUTES):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
