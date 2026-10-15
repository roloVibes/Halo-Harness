"""halo_harness.studio.fleet_mission_api -- fleet missions (Halo 3.0.6.0
"Fleet Missions" round R7), appended to studio/fleet_hub_api.py's ROUTES;
the same loopback + token guard as every Studio route. Every route is one
function of fleet/mission_api.py, run with Studio's own hub, else through
the loopback `local/mission` route of a `halo fleet serve` on this machine,
else for this harness alone.

    GET  fleet/missions                        {missions: [summary], at, root_shared}
    POST fleet/missions {goal, constraints?, prefer?, budget_usd?, test?, repo?: false}
                                               drafts and plans: {mission, plan, summary, running}
    GET  fleet/missions/<id>                   {mission, plan, summary, running}
    POST fleet/missions/<id>/plan              plans again (the lead): the same shape
    POST fleet/missions/<id>/parts/<n> {harness?, drop?: true}   reassign or drop one part, checked in code
    POST fleet/missions/<id>/approve           planned -> approved (409 with the problems: an unassignable part)
    POST fleet/missions/<id>/run               approves when planned, then runs
    POST fleet/missions/<id>/stop {reason?}    stops every running part; the mission ends `stopped`
    GET  fleet/missions/<id>/report            {report, markdown, final}
    GET  fleet/missions/<id>/files[?path=]     the folder's files, or one text file {path, size, text, truncated}

Errors: 404 unknown mission or part, 409 a state that does not allow it, 422
a bad body or a plan the lead could not make (with `problems`), 400 a path
outside the mission folder. Every change is a `fleet` frame `{action:
"mission", id, state, part?, part_state?}` on the live feed.
"""

from __future__ import annotations


def _ctx(req):
    from halo_harness.fleet.identity import fleet_name
    from halo_harness.fleet.mission_api import Ctx
    from halo_harness.studio import fleet_watch_io as io
    hub = getattr(req.server, "fleet_hub", None)
    publish = None if hub is not None else (lambda f: io.publish(req.server, f))
    return Ctx(req.state_dir, hub, publish=publish, by=fleet_name(req.state_dir), cwd=req.cwd)


def _do(req, op: str, **fields):
    from halo_harness.fleet import mission_api as A
    if getattr(req.server, "fleet_hub", None) is None:
        from halo_harness.fleet.hub import running_call
        got = running_call(req.state_dir, "POST", "local/mission", {"op": op, "cwd": str(req.cwd), **fields},
                           timeout=180.0 if op in ("new", "plan") else 40.0)
        if got:
            return got
    ctx = _ctx(req)
    mid = str(fields.get("id") or "")
    if op == "list":
        return A.list_missions(ctx)
    if op == "new":
        return A.create(ctx, fields)
    if op == "edit":
        return A.edit_part(ctx, mid, str(fields.get("part") or ""), fields)
    if op == "stop":
        return A.stop(ctx, mid, str(fields.get("reason") or ""))
    if op == "files":
        return A.files(ctx, mid, str(fields.get("path") or ""))
    return {"get": A.get, "plan": A.replan, "approve": A.approve, "run": A.run, "report": A.report}[op](ctx, mid)


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def get_missions(req):
    return _do(req, "list")


def post_missions(req):
    b = _body(req)
    return _do(req, "new", **{k: b[k] for k in ("goal", "constraints", "prefer", "budget_usd", "test", "repo") if k in b})


def get_mission(req):
    return _do(req, "get", id=req.params["mid"])


def post_plan(req):
    return _do(req, "plan", id=req.params["mid"])


def post_part(req):
    b = _body(req)
    return _do(req, "edit", id=req.params["mid"], part=req.params["pid"],
               **{k: b[k] for k in ("harness", "drop") if k in b})


def post_approve(req):
    return _do(req, "approve", id=req.params["mid"])


def post_run(req):
    return _do(req, "run", id=req.params["mid"])


def post_stop(req):
    return _do(req, "stop", id=req.params["mid"], reason=str(_body(req).get("reason") or ""))


def get_report(req):
    return _do(req, "report", id=req.params["mid"])


def get_files(req):
    return _do(req, "files", id=req.params["mid"], path=str(req.query.get("path") or ""))


_M = r"(?P<mid>m-\d{8}-[0-9a-f]{4})"
ROUTES = [("GET", r"^fleet/missions$", get_missions),
          ("POST", r"^fleet/missions$", post_missions),
          ("GET", rf"^fleet/missions/{_M}$", get_mission),
          ("POST", rf"^fleet/missions/{_M}/plan$", post_plan),
          ("POST", rf"^fleet/missions/{_M}/parts/(?P<pid>\d{{1,3}})$", post_part),
          ("POST", rf"^fleet/missions/{_M}/approve$", post_approve),
          ("POST", rf"^fleet/missions/{_M}/run$", post_run),
          ("POST", rf"^fleet/missions/{_M}/stop$", post_stop),
          ("GET", rf"^fleet/missions/{_M}/report$", get_report),
          ("GET", rf"^fleet/missions/{_M}/files$", get_files)]
