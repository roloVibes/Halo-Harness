"""halo_harness.studio.crew_flow_api -- the Workflows tab's routes (Halo 3.6.0.0 R2; docs/STUDIO-workflows.md "Routes").

    GET    crew/workflows                {workflows: [row], starters: [row], rows: [every row]}  a row: name, for, steps,
                                         own_copy, max_usd, scope, new, problems, maps (the maps it is on)
    GET    crew/workflow/<name>          {workflow, scope, path, problems, maps, writable, cost, writes, missing}
    POST   crew/workflow/<name> {workflow}   a new workflow of yours (409 when you have one by that name; 422 the lines)
    PUT    crew/workflow/<name> {workflow}   save it (a starter: 409, Copy makes yours)
    DELETE crew/workflow/<name>          delete yours (409 while a map has a box for it, saying which)
    POST   crew/workflow-cost {workflow} {cost, writes, problems, missing}: the band for the form as it stands, unsaved
    POST   crew/try {kind: workflow, body, request}   Try it on the step runner (crew/trial_flow.py)
    POST   crew/run {name, task, cwd?, model?}  3.6.0.6 P: Run it -- 202 {session_id, workflow, cwd, ...}: a new session
                                         runs that workflow by name on the task (crew/flow_run.py); 404 no such workflow

`cost` = {low, high, unknown: [agent], cap, line} (crew/flow_cost.py); `writes` the lines on what Save and a run write;
`missing` the agents a step names that are not agents of yours. Every write is owner-only (studio/owner_proof.py).
"""

from __future__ import annotations

from halo_harness.crew import flow_cost, runner, store
from halo_harness.crew.formats import workflow_problems
from halo_harness.studio.owner_proof import owner_only

ROW_KEYS = ("name", "for", "steps", "own_copy", "max_usd")


def _resolve(req):
    def one(name: str):
        got = store.load("agent", name, cwd=req.cwd, state_dir=req.state_dir)
        return store.clean(got) if got else None
    return one


def _row(r: dict, req) -> dict:
    out = {k: r.get(k) for k in ROW_KEYS if k in r}
    out.update(name=r["name"], scope=r["_scope"], new=bool(r.get("_new")), problems=r["_problems"])
    out["maps"] = store.maps_with(r["name"], cwd=req.cwd, state_dir=req.state_dir) if r["_scope"] != "starter" else []
    return out


def get_workflows(req):
    rows = store.rows("workflow", cwd=req.cwd, state_dir=req.state_dir)
    every = [_row(r, req) for r in rows]
    return 200, {"workflows": [r for r in every if r["scope"] != "starter"], "starters": [r for r in every if r["scope"] == "starter"],
                 "rows": every}


def facts(wf: dict, req) -> dict:
    resolve = _resolve(req)
    missing = []
    for s in wf.get("steps") or []:
        for a in (s.get("agents") or []) if isinstance(s, dict) else []:
            if a not in missing and resolve(a) is None:
                missing.append(a)
    return {"cost": flow_cost.band(wf, resolve, req.state_dir), "writes": flow_cost.writes(wf, resolve, req.state_dir), "missing": missing}


def get_workflow(req):
    name, scope = req.params["name"], str((req.query or {}).get("scope") or "")
    got = store.load("workflow", name, cwd=req.cwd, state_dir=req.state_dir, scope=scope)
    if got is None:
        return 404, {"error": f"no workflow named {name!r}"}
    body = store.clean(got)
    return 200, {"workflow": body, "scope": got["_scope"], "path": got["_path"], "problems": workflow_problems(body, name=name),
                 "maps": store.maps_with(name, cwd=req.cwd, state_dir=req.state_dir), "writable": got["_scope"] not in ("starter", "pack"),
                 **facts(body, req)}


def _body(req, name: str):
    raw = (req.body or {}).get("workflow")
    if not isinstance(raw, dict):
        return None, (400, {"error": "the body needs a 'workflow' mapping"})
    raw = store.clean({**raw, "name": name, "format": raw.get("format") or "workflow/1"})
    probs = workflow_problems(raw, name=name)
    if probs:
        return None, (422, {"error": probs[0], "problems": probs})
    return raw, None


def _pack_refusal(req, name: str):
    """3.6.0.6 P: an enabled pack's workflow is the pack's: no write, no delete, the one sentence (crew/store.py)."""
    said = store.pack_read_only("workflow", name, cwd=req.cwd, state_dir=req.state_dir)
    return (409, {"error": said, "problems": []}) if said else None


def post_workflow(req):
    name = req.params["name"]
    if refused := _pack_refusal(req, name):
        return refused
    raw, err = _body(req, name)
    if err:
        return err
    if store.find("workflow", name, cwd=req.cwd, state_dir=req.state_dir, scope="yours"):
        return 409, {"error": f"you have a workflow named {name} already: pick another name", "problems": []}
    path = store.path_for("workflow", name, state_dir=req.state_dir)
    store.write_text(path, store.dump(raw))
    return 200, {"ok": True, "path": str(path), "workflow": raw}


def put_workflow(req):
    name = req.params["name"]
    if refused := _pack_refusal(req, name):
        return refused
    raw, err = _body(req, name)
    if err:
        return err
    found = store.find("workflow", name, cwd=req.cwd, state_dir=req.state_dir)
    if found and found[1] == "starter":
        return 409, {"error": f"{name} ships with Halo: Copy makes it yours", "problems": []}
    project = bool(found and found[1] == "project")
    path = store.path_for("workflow", name, cwd=req.cwd, state_dir=req.state_dir, project=project)
    store.write_text(path, store.dump(raw))
    return 200, {"ok": True, "path": str(path), "workflow": raw}


def delete_workflow(req):
    name = req.params["name"]
    found = store.find("workflow", name, cwd=req.cwd, state_dir=req.state_dir, scope="yours")
    if not found:
        return _pack_refusal(req, name) or (404, {"error": f"no workflow of yours named {name!r}"})
    maps = store.maps_with(name, cwd=req.cwd, state_dir=req.state_dir)
    if maps:
        return 409, {"error": f"{name} is on the map {', '.join(maps)}: take it off there first", "problems": maps}
    store.write_text(found[0], None)
    return 200, {"ok": True}


def post_cost(req):
    raw = (req.body or {}).get("workflow")
    if not isinstance(raw, dict):
        return 400, {"error": "the body needs a 'workflow' mapping"}
    raw = store.clean({**raw, "format": "workflow/1"})
    return 200, {**facts(raw, req), "problems": workflow_problems(raw, name=str(raw.get("name") or ""))}


def post_try_flow(req, publish):
    from halo_harness.crew import trial_flow
    body = req.body or {}
    raw, request = body.get("body"), str(body.get("request") or "").strip()
    if not isinstance(raw, dict) or not request:
        return 400, {"error": "the body needs the workflow ('body') and a test request ('request')"}
    wf = store.clean({**raw, "format": "workflow/1"})
    probs = workflow_problems(wf, name=str(wf.get("name") or ""))
    problems, agents = runner.preflight(wf, _resolve(req))
    probs = probs or problems
    if probs:
        return 422, {"error": probs[0], "problems": probs}
    rec = trial_flow.start_flow(wf, agents, request, cwd=req.cwd, state_dir=req.state_dir, publish=publish)
    return 200, {"try": rec}


TASK_MAX = 8000  # the task rides on the session's argv (Windows' command line holds 32k characters)


def post_run(req):
    """3.6.0.6 P: Run it -- a real run of a crew workflow (an enabled pack's, yours, this project's) on a task. A new
    session, started as POST sessions/new starts one (Studio's child; it ends with Studio), runs it by name on its own
    command pump (crew/flow_run.py: the Workflow tool's code, no model asked); 202 says the session, workflow, folder."""
    from halo_harness.crew import flow_door
    from halo_harness.studio import sessions_new_api as N
    body = req.body if isinstance(req.body, dict) else {}
    name, task = str(body.get("name") or "").strip(), str(body.get("task") or "").strip()
    cwd, why = N._cwd_of(req, body.get("cwd"))  # noqa: SLF001  the same folder rules as a new session
    if cwd is None:
        return 422, {"error": why, "problems": [why]}
    wf = flow_door.named(name, cwd, req.state_dir) if name else None
    if wf is None:
        return 404, {"error": f"no workflow named {name!r} that a session runs (yours, this project's or an enabled pack's)"}
    if not task:
        return 422, {"error": "say what the workflow should work on: the task is empty", "problems": ["task"]}
    if len(task) > TASK_MAX:
        return 422, {"error": f"the task is {len(task)} characters; a run takes at most {TASK_MAX}", "problems": ["task"]}
    clean = store.clean(wf)
    probs = workflow_problems(clean, name=str(clean.get("name") or "")) or runner.preflight(clean, _resolve(req))[0]
    if probs:
        return 422, {"error": probs[0], "problems": probs}
    full = str(wf.get("name") or name)
    status, out = N.start(req, cwd, body.get("model"), ("--run-workflow", full, "--workflow-task", task))
    return status, ({**out, "workflow": full} if status == 202 else out)


_NAME = r"(?P<name>[a-z][a-z0-9-]{0,47})"
ROUTES: list = [
    ("GET", r"^crew/workflows$", get_workflows),
    ("GET", rf"^crew/workflow/{_NAME}$", get_workflow),
    ("POST", rf"^crew/workflow/{_NAME}$", owner_only(post_workflow)),
    ("PUT", rf"^crew/workflow/{_NAME}$", owner_only(put_workflow)),
    ("DELETE", rf"^crew/workflow/{_NAME}$", owner_only(delete_workflow)),
    ("POST", r"^crew/workflow-cost$", owner_only(post_cost)),
    ("POST", r"^crew/run$", owner_only(post_run)),  # 3.6.0.6 P: Run it
]
