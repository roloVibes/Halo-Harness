"""halo_harness.studio.crew_api -- the Agents tab's routes (Halo 3.6.0.0 R1; docs/STUDIO-builder.md "Routes").

    GET    crew/agents                 {agents: [row], starters: [row]}  a row: name, does, model, uses, careful, scope
                                       (yours | project | starter), new, used [workflow x | map y], problems
    GET    crew/agent/<name>           {agent, scope, path, problems, used, writable}  (?scope= picks one)
    POST   crew/agent/<name> {agent}   a new agent of yours (409 when you have one by that name)
    PUT    crew/agent/<name> {agent}   save it (422 with the problem lines; a starter answers 409: Copy makes yours)
    DELETE crew/agent/<name>           delete yours (409 while a workflow or a map names it, saying which)
    GET    crew/workflows | crew/maps  the rows of those kinds (read-only in R1)
    GET    crew/estimate?model=<ref>   {usd, line}: one typical task on that model, said before a Try it
    POST   crew/try {kind: agent, body, request}   {try}: the run's record, running (progress on /api/events, `crew`)
    GET    crew/try/<id>               {try}
    POST   crew/try/<id>/stop | crew/try/<id>/seen

Every write is owner-only (studio/owner_proof.py).
"""

from __future__ import annotations

import re

from halo_harness.crew import store, trial
from halo_harness.crew.formats import agent_problems
from halo_harness.studio.owner_proof import owner_only

ROW_KEYS = ("name", "does", "model", "needs", "uses", "careful", "instructions", "more")


def _row(r: dict, cwd, state_dir) -> dict:
    out = {k: r.get(k) for k in ROW_KEYS if k in r}
    out.update(name=r["name"], scope=r["_scope"], new=bool(r.get("_new")), problems=r["_problems"])
    out["used"] = store.used_by(r["name"], cwd=cwd, state_dir=state_dir) if r["_scope"] != "starter" else []
    return out


def get_agents(req):
    rows = store.rows("agent", cwd=req.cwd, state_dir=req.state_dir)
    mine = [_row(r, req.cwd, req.state_dir) for r in rows if r["_scope"] != "starter"]
    starters = [_row(r, req.cwd, req.state_dir) for r in rows if r["_scope"] == "starter"]
    return 200, {"agents": mine, "starters": starters}


def get_agent(req):
    name, scope = req.params["name"], str((req.query or {}).get("scope") or "")
    got = store.load("agent", name, cwd=req.cwd, state_dir=req.state_dir, scope=scope)
    if got is None:
        return 404, {"error": f"no agent named {name!r}"}
    body = store.clean(got)
    return 200, {"agent": body, "scope": got["_scope"], "path": got["_path"], "problems": agent_problems(body, name=name),
                 "used": store.used_by(name, cwd=req.cwd, state_dir=req.state_dir), "writable": got["_scope"] != "starter"}


def _body(req, name: str):
    raw = (req.body or {}).get("agent")
    if not isinstance(raw, dict):
        return None, (400, {"error": "the body needs an 'agent' mapping"})
    raw = store.clean({**raw, "name": name, "format": raw.get("format") or "agent/1"})
    probs = agent_problems(raw, name=name)
    if probs:
        return None, (422, {"error": probs[0], "problems": probs})
    return raw, None


def post_agent(req):
    name = req.params["name"]
    raw, err = _body(req, name)
    if err:
        return err
    if store.find("agent", name, cwd=req.cwd, state_dir=req.state_dir, scope="yours"):
        return 409, {"error": f"you have an agent named {name} already: pick another name", "problems": []}
    path = store.path_for("agent", name, state_dir=req.state_dir)
    store.write_text(path, store.dump(raw))
    return 200, {"ok": True, "path": str(path), "agent": raw}


def put_agent(req):
    name = req.params["name"]
    raw, err = _body(req, name)
    if err:
        return err
    found = store.find("agent", name, cwd=req.cwd, state_dir=req.state_dir)
    if found and found[1] == "starter":
        return 409, {"error": f"{name} is a starter: Copy makes it yours", "problems": []}
    project = bool(found and found[1] == "project")
    path = store.path_for("agent", name, cwd=req.cwd, state_dir=req.state_dir, project=project)
    store.write_text(path, store.dump(raw))
    return 200, {"ok": True, "path": str(path), "agent": raw}


def delete_agent(req):
    name = req.params["name"]
    found = store.find("agent", name, cwd=req.cwd, state_dir=req.state_dir, scope="yours")
    if not found:
        return 404, {"error": f"no agent of yours named {name!r}"}
    used = store.used_by(name, cwd=req.cwd, state_dir=req.state_dir)
    if used:
        return 409, {"error": f"{name} is used by {', '.join(used)}: take it out there first", "problems": used}
    store.write_text(found[0], None)
    return 200, {"ok": True}


def get_kind(kind: str):
    def handler(req):
        rows = store.rows(kind, cwd=req.cwd, state_dir=req.state_dir)
        return 200, {"rows": [{**{k: v for k, v in r.items() if not k.startswith("_")}, "scope": r["_scope"],
                                "problems": r["_problems"]} for r in rows]}
    return handler


def get_estimate(req):
    return 200, trial.estimate({"model": str((req.query or {}).get("model") or "auto")}, req.state_dir)


def _publisher(req):
    if req.server is None:
        return None
    from halo_harness.studio.events import bridge_for
    bridge = bridge_for(req.server)
    return bridge.publish_local


def post_try(req):
    body = req.body or {}
    if body.get("kind", "agent") != "agent":
        return 422, {"error": "Try it runs an agent in this version (a workflow's comes with the Workflows tab)"}
    raw = body.get("body")
    request = str(body.get("request") or "").strip()
    if not isinstance(raw, dict) or not request:
        return 400, {"error": "the body needs the agent ('body') and a test request ('request')"}
    name = str(raw.get("name") or "")
    raw = store.clean({**raw, "format": "agent/1"})
    probs = agent_problems(raw, name=name)
    if probs:
        return 422, {"error": probs[0], "problems": probs}
    rec = trial.start(raw, request, cwd=req.cwd, state_dir=req.state_dir, publish=_publisher(req))
    return 200, {"try": rec}


def get_try(req):
    rec = trial.get(req.params["tid"], req.state_dir)
    return (200, {"try": rec}) if rec else (404, {"error": "no such run"})


def post_try_stop(req):
    got = trial.stop(req.params["tid"], req.state_dir)
    return (200, got) if got.get("ok") else (409, got)


def post_try_seen(req):
    got = trial.seen(req.params["tid"], req.state_dir)
    return (200, got) if got.get("ok") else (404, got)


_NAME = r"(?P<name>[a-z][a-z0-9-]{0,47})"
_TID = r"(?P<tid>t[0-9a-f]{10})"
ROUTES: list = [
    ("GET", r"^crew/agents$", get_agents),
    ("GET", rf"^crew/agent/{_NAME}$", get_agent),
    ("POST", rf"^crew/agent/{_NAME}$", owner_only(post_agent)),
    ("PUT", rf"^crew/agent/{_NAME}$", owner_only(put_agent)),
    ("DELETE", rf"^crew/agent/{_NAME}$", owner_only(delete_agent)),
    ("GET", r"^crew/workflows$", get_kind("workflow")),
    ("GET", r"^crew/maps$", get_kind("map")),
    ("GET", r"^crew/estimate$", get_estimate),
    ("POST", r"^crew/try$", owner_only(post_try)),
    ("GET", rf"^crew/try/{_TID}$", get_try),
    ("POST", rf"^crew/try/{_TID}/stop$", owner_only(post_try_stop)),
    ("POST", rf"^crew/try/{_TID}/seen$", owner_only(post_try_seen)),
]


def dispatch_table(req, routes: list):
    for method, pattern, fn in routes:
        m = re.match(pattern, req.path)
        if m and method == req.method:
            req.params = dict(m.groupdict())
            return fn(req)
    if any(re.match(p, req.path) for _m, p, _f in routes):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}


def dispatch_crew(req):
    return dispatch_table(req, ROUTES)
