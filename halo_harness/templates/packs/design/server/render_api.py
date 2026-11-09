"""The design pack's server/render_api.py -- a ComfyUI workflow rendered into a design project (Halo 3.0.4.0 R5's
`POST media/render` and `GET media/renders/<id>`, the design pack's routes since 3.3.13.0 R2):

    POST render {workflow, set, project, artboard, source?}   -> 202 {prompt_id, project, artboard, workflow, source}
    GET  renders/<prompt id>                                   the render's last state (the `render` frames' data)

The workflow is a starter or a name saved on the ComfyUI Halo is pointed at (`halo media`); render.py follows it and
saves each output as an artboard.
"""

from __future__ import annotations

from halo_harness.ext import host

from . import render as R
from .request import _SLUG, _bad
from .store import Project


def post_render(req):
    body = req.body
    workflow, slug = str(body.get("workflow") or "").strip(), str(body.get("project") or "").strip()
    if not workflow or "/" in workflow or "\\" in workflow:
        return _bad("say which workflow: a starter or a saved name")
    sets = body.get("set") if isinstance(body.get("set"), dict) else {}
    project = Project.open(slug, state_dir=req.state_dir) if _SLUG.match(slug) else None  # 3.3.14.0 R1 (#38): `../x` 404
    if project is None:
        return 404, {"error": f"no design project {slug!r}: make it in Design first"}
    artboard = str(body.get("artboard") or "render").strip() or "render"
    try:
        comfy = host.comfy()
        q = comfy.queue(workflow, sets, str(body.get("source") or ""), cwd=req.cwd)
    except host.HostError as e:
        return (404 if e.status == 404 else 502), {"error": str(e)}
    publish = getattr(req, "publish", None)
    to_feed = (lambda frame: publish("render", frame.get("data"))) if publish is not None else None
    poll = float(body["poll_s"]) if isinstance(body.get("poll_s"), (int, float)) and body["poll_s"] else 1.0
    R.start(comfy, project, pid=q["prompt_id"], workflow=workflow, sets=sets, artboard=artboard, publish=to_feed, poll_s=poll)
    return 202, {"prompt_id": q["prompt_id"], "project": project.slug, "artboard": artboard, "workflow": workflow,
                 "source": q["source"]}


def get_render(req):
    row = R.render_state(req.params["pid"])
    return (200, row) if row else (404, {"error": f"no render {req.params['pid']!r} in this Studio"})
