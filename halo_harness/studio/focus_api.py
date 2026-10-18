"""halo_harness.studio.focus_api -- `POST /api/focus`, how a second `halo studio
--edit` reaches the Studio that already runs (Halo 3.1.1.0 R3).

    POST focus {edit: "bio:<name>"|"lineup:<name>"|"team"}
         200 {edit, mode, pages}   a `focus` frame went out on the live feed;
                                   `pages`: how many Studio pages are open to take it
         422 {error, problems}     not an edit target (studio/edit_target.py)

Every open page (ui/src/lib/edit.ts) answers the frame the way it answers
`?edit=` in its URL: it switches to the section and opens the bio form, the
lineup's inspector or the Team section.
"""

from __future__ import annotations

import time


def post_focus(req):
    from halo_harness.studio.edit_target import parse
    target, why = parse(str(req.body.get("edit") or ""))
    if target is None:
        return 422, {"error": why, "problems": [why]}
    pages = 0
    if req.server is not None:
        from halo_harness.studio.events import bridge_for
        bridge = bridge_for(req.server)
        pages = bridge.listeners()
        bridge.publish_local({"session_id": "studio", "event": "focus", "ts": time.time(),
                              "data": {"edit": target.text, "mode": target.mode}})
    return 200, {"edit": target.text, "mode": target.mode, "pages": pages}


def dispatch_focus(req):
    if req.path != "focus":
        return 404, {"error": f"no route for {req.method} /api/{req.path}"}
    if req.method != "POST":
        return 405, {"error": "/api/focus answers POST"}
    return post_focus(req)
