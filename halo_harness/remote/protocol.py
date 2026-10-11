"""halo_harness.remote.protocol -- the control socket's wire commands.

One JSON object per line. Request `{"id", "cmd", ...fields}`; response
`{"id", "ok": true, "result": {...}}` or `{"id", "ok": false, "error": str}`.
Event frames (after `subscribe`) carry `"event"` instead of `"id"`:
`{"event": kind, "data": {...}, "turn", "agent_id", "ts"}` where `kind` is
an `events.EVENT_KINDS` name or `text_chunk` (coalesced `text_delta`s).

`CMDS` is the exact command set. Each maps onto one `SessionHandle` method
(remote/handle.py); nothing here touches a Controller or Session directly.
"""

from __future__ import annotations

from typing import Any

from halo_harness.remote.base import HandleError

CMDS = ("status", "submit", "steer", "interrupt", "answer", "model", "effort", "mode", "slash", "tail",
        "subscribe", "unsubscribe", "ping", "note")
ANSWER_KINDS = ("permission", "question", "plan", "approval")
TAIL_DEFAULT = 20
TAIL_MAX = 200


def _str(req: dict, key: str, *alts: str) -> str:
    for k in (key, *alts):
        v = req.get(k)
        if isinstance(v, str):
            return v
    return ""


def _answer(handle, req: dict) -> dict:
    kind = req.get("kind")
    if kind not in ANSWER_KINDS:
        raise HandleError(f"answer kind must be one of {', '.join(ANSWER_KINDS)}")
    # the card id is `request_id`; the brief's bare `id` of an answer is taken
    # as the card id too when no `request_id` is given (the correlation id
    # of the reply is then the same string).
    rid = _str(req, "request_id", "target", "id")
    if kind == "permission":
        ok = handle.answer_permission(rid, _str(req, "action", "decision"), scope=_str(req, "scope") or "once",
                                       message=_str(req, "message"), rule=_str(req, "rule") or None)
    elif kind == "question":
        ok = handle.answer_question(rid, req.get("answer"))
    elif kind == "plan":
        ok = handle.answer_plan(bool(req.get("approved")), feedback=_str(req, "feedback"),
                                 mode_after=_str(req, "mode_after") or None)
    else:
        ok = handle.answer_approval(rid, _str(req, "action"), instruction=_str(req, "instruction"))
    if not ok:
        raise HandleError(f"no pending {kind} request" + (f" {rid!r}" if rid else ""))
    return {"resolved": True}


def _note(handle, req: dict, conn) -> dict:
    """`{"cmd": "note", "name": "remote.attached", "peer": "<id prefix>",
    "attached": true|false}` -- the Signal bridge telling the session a
    phone attached or detached. A connection that closes takes its peers
    with it, so a crashed bridge never leaves the chip lit."""
    name = _str(req, "name")
    if name != "remote.attached":
        raise HandleError(f"unknown note {name!r} (expected remote.attached)")
    peer = _str(req, "peer").strip()[:16]
    if not peer:
        raise HandleError("note remote.attached needs a peer")
    attached = bool(req.get("attached"))
    noted = getattr(conn, "noted", None)
    if noted is not None:
        (noted.add if attached else noted.discard)(peer)
    return {"attached": handle.set_remote_peer(peer, attached)}


def run_cmd(handle, req: dict, conn) -> Any:
    """Execute one request; `conn` offers `start_feed(kinds)` / `stop_feed()`."""
    cmd = req.get("cmd")
    if cmd == "ping":
        return {"pong": True, "session_id": handle.session_id}
    if cmd == "status":
        return handle.status()
    if cmd in ("submit", "steer"):
        return handle.submit(_str(req, "text"))
    if cmd == "interrupt":
        return handle.interrupt()
    if cmd == "answer":
        return _answer(handle, req)
    if cmd == "model":
        return handle.set_model(_str(req, "ref", "model"))
    if cmd == "effort":
        return handle.set_effort(_str(req, "level", "effort"))
    if cmd == "mode":
        return handle.set_mode(_str(req, "mode"))
    if cmd == "slash":
        line = _str(req, "line").strip()
        name, args = _str(req, "name"), _str(req, "args")
        if line.startswith("/") and not name:
            name, _, args = line[1:].partition(" ")
        return {"output": handle.run_slash(name, args)}
    if cmd == "tail":
        n = req.get("n", TAIL_DEFAULT)
        n = n if isinstance(n, int) and not isinstance(n, bool) else TAIL_DEFAULT
        return {"markdown": handle.tail(max(1, min(n, TAIL_MAX)))}
    if cmd == "note":
        return _note(handle, req, conn)
    if cmd == "subscribe":
        kinds = req.get("kinds")
        conn.start_feed([k for k in kinds if isinstance(k, str)] if isinstance(kinds, list) else None)
        return {"subscribed": True}
    if cmd == "unsubscribe":
        conn.stop_feed()
        return {"subscribed": False}
    raise HandleError(f"unknown cmd {cmd!r} (expected one of {', '.join(CMDS)})")


def handle_request(handle, req: Any, conn) -> dict:
    rid = req.get("id") if isinstance(req, dict) else None
    if not isinstance(req, dict):
        return {"id": rid, "ok": False, "error": "request must be a JSON object"}
    try:
        return {"id": rid, "ok": True, "result": run_cmd(handle, req, conn)}
    except HandleError as e:
        return {"id": rid, "ok": False, "error": str(e)}
    except Exception as e:  # a bad request must never take the connection thread down
        return {"id": rid, "ok": False, "error": f"{type(e).__name__}: {e}"}
