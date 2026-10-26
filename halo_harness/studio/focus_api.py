"""halo_harness.studio.focus_api -- `POST /api/focus`, how a second `halo studio
--edit` reaches the Studio that already runs (Halo 3.1.1.0 R3).

    POST focus {edit: "bio:<name>"|"lineup:<name>"|"team"}
         200 {edit, mode, pages}   a `focus` frame went out on the live feed;
                                   `pages`: how many Studio pages are open to take it
         422 {error, problems}     not an edit target (studio/edit_target.py)
    POST focus {mode: <section>, session?: <sid>}       (3.1.4.0 R2, studio/session_open.py)
         200 {edit: "", mode, session, pages}   the pages switch to that section; Session
                                   chooses that session (`/studio`, `halo studio --session`)
         422 {error, problems}     not a section, or not a session id
    POST focus {mode: "setup", block?: <block>, first?: bool}    (3.3.0.0 R4, studio/setup_door.py)
         200 {edit: "", mode, session, block, first, pages}   the pages open Setup on that block

Every open page (ui/src/shell/edit.ts) answers the frame the way it answers
`?edit=` (or `?mode=session&session=`) in its URL: it switches to the section
and opens the bio form, the lineup's inspector, the Team section, or the
Session dashboard on that session.
"""

from __future__ import annotations

import time


def _publish(req, data: dict) -> int:
    """Put a `focus` frame on the live feed; the pages open to take it."""
    if req.server is None:
        return 0
    from halo_harness.studio.events import bridge_for
    bridge = bridge_for(req.server)
    pages = bridge.listeners()
    bridge.publish_local({"session_id": "studio", "event": "focus", "ts": time.time(), "data": data})
    return pages


def _post_section(req, body: dict):
    from halo_harness.studio.server import STUDIO_MODES
    from halo_harness.studio.session_open import valid_session_id
    mode, sid = str(body.get("mode") or ""), str(body.get("session") or "")
    if mode not in STUDIO_MODES:
        why = f"{mode!r} is not a Studio section: use one of {', '.join(STUDIO_MODES)}"
        return 422, {"error": why, "problems": [why]}
    if sid and (mode != "session" or not valid_session_id(sid)):
        why = f"{sid!r} is not a session id for Session"
        return 422, {"error": why, "problems": [why]}
    data = {"edit": "", "mode": mode, "session": sid}
    if mode == "setup":  # 3.3.0.0 R4 (studio/setup_door.py): the block to bring into view, the first run's help
        from halo_harness.studio.setup_door import block_word
        block, why = block_word(str(body.get("block") or ""))
        if block is None:
            return 422, {"error": why, "problems": [why]}
        data.update(block=block, first=bool(body.get("first")))
    return 200, {**data, "pages": _publish(req, data)}


def post_focus(req):
    from halo_harness.studio.edit_target import parse
    body = req.body if isinstance(req.body, dict) else {}
    if not body.get("edit") and body.get("mode"):
        return _post_section(req, body)
    target, why = parse(str(body.get("edit") or ""))
    if target is None:
        return 422, {"error": why, "problems": [why]}
    data = target.focus() if hasattr(target, "focus") else {"edit": target.text, "mode": target.mode}  # a Setup target
    pages = _publish(req, data)
    return 200, {"edit": target.text, "mode": target.mode, "pages": pages}


def dispatch_focus(req):
    if req.path != "focus":
        return 404, {"error": f"no route for {req.method} /api/{req.path}"}
    if req.method != "POST":
        return 405, {"error": "/api/focus answers POST"}
    return post_focus(req)
