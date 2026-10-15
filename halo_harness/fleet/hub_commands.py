"""halo_harness.fleet.hub_commands -- the commands a hub sends to a member
and what came back (Halo 3.0.5.0 "Fleet" round R2).

`send` queues a `command` doc for the link that announced the session on
that link's SSE stream (which signs it) and waits up to `wait_s` for the member's
reply: `done` (200 with the result), `refused` (403 with the member's
reason: control off, the owner said deny, a print-mode session under `ask`,
a share level too low), `error` (502), `asked` (202: the owner's card is
open; the outcome arrives later) or nothing yet (504). Every final outcome
is also published as a `fleet` frame `{action: command, command_id, cmd,
state, error?}` and kept for PENDING_KEEP_S (`get`, Studio's
`GET /api/fleet/commands/<id>`). `open()` lists the ones still `asked`
(3.0.5.0 R4: the attention queue's `control_ask` rows).
"""

from __future__ import annotations

import secrets
import threading
import time

from halo_harness.fleet import protocol

PENDING_KEEP_S = 600.0
FINAL = ("done", "refused", "error")


class Pending:
    def __init__(self, cid: str, hid: str, sid: str, cmd: str) -> None:
        self.cid, self.hid, self.sid, self.cmd = cid, hid, sid, cmd
        self.state, self.result, self.error = "sent", None, None
        self.created = time.time()
        self.cond = threading.Condition()

    def public(self) -> dict:
        return {"command_id": self.cid, "harness": self.hid, "session_id": self.sid, "cmd": self.cmd,
                "state": self.state, "result": self.result, "error": self.error, "created": self.created}


class Commands:
    def __init__(self, state) -> None:
        self.state = state
        self._pending: "dict[str, Pending]" = {}
        self._lock = threading.Lock()

    def _prune(self) -> None:
        cut = time.time() - PENDING_KEEP_S
        self._pending = {k: p for k, p in self._pending.items() if p.created > cut}

    def send(self, hid: str, sid: str, cmd: str, fields: dict, *, by: str, wait_s: float = 5.0):
        if cmd not in protocol.FLEET_CMDS:
            return 422, {"error": f"cmd is one of {', '.join(protocol.FLEET_CMDS)}, got {cmd!r}"}
        member = self.state.members.get(hid)
        if member is None:
            return 404, {"error": f"no member {hid!r} on this hub"}
        link = member.link_for(sid)
        if link is None:
            return 404, {"error": f"{member.name} has no live session {sid!r}"}
        if not link.streams or member.key is None:
            return 409, {"error": f"{member.name} is not connected right now"}
        cid = secrets.token_hex(8)
        doc = {"type": "command", "cid": cid, "session_id": sid, "cmd": cmd, "fields": dict(fields or {}),
               "by": by, "hub": self.state.name}  # signed and numbered by the stream that sends it (hub_http.py)
        p = Pending(cid, hid, sid, cmd)
        with self._lock:
            self._prune()
            self._pending[cid] = p
        if not link.push(doc):
            p.state, p.error = "error", f"{member.name}'s command queue is full"
            return self._result(p, member.name)
        with p.cond:  # the outcome when it comes within wait_s; `asked` (202) when the owner's card is still open
            p.cond.wait_for(lambda: p.state in FINAL, timeout=max(0.0, min(float(wait_s), 120.0)))
        return self._result(p, member.name)

    @staticmethod
    def _result(p: Pending, name: str):
        base = {"command_id": p.cid}
        if p.state == "done":
            return 200, {"ok": True, "result": p.result, **base}
        if p.state == "refused":
            return 403, {"error": p.error or f"{name} refused the command", "refused": True, **base}
        if p.state == "error":
            return 502, {"error": p.error or f"{name} could not run the command", **base}
        if p.state == "asked":
            return 202, {"ok": True, "asked": True, "text": f"waiting for {name}'s owner to allow or deny it", **base}
        return 504, {"error": f"no answer from {name} yet", **base}

    def reply(self, hid: str, body: dict) -> bool:
        cid = str(body.get("cid") or "")
        state = str(body.get("state") or "")
        with self._lock:
            p = self._pending.get(cid)
        if p is None or p.hid != hid or state not in ("asked",) + FINAL:
            return False
        with p.cond:
            if p.state in FINAL:
                return False
            p.state = state
            p.result = body.get("result") if state == "done" else None
            p.error = str(body.get("error") or "")[:500] or None
            p.cond.notify_all()
        if state in FINAL or state == "asked":
            self.state.publish({"session_id": p.sid, "harness": hid, "event": "fleet", "turn": None, "agent_id": None,
                                "ts": time.time(), "data": {"action": "command", "command_id": cid, "cmd": p.cmd,
                                                            "state": state, "error": p.error}})
        return True

    def get(self, cid: str):
        with self._lock:
            p = self._pending.get(cid)
        return p.public() if p is not None else None

    def open(self) -> list:
        """The commands in state `asked` (a member's owner has the card open): the Fleet
        attention queue's `control_ask` rows (3.0.5.0 R4)."""
        with self._lock:
            self._prune()
            return [p.public() for p in self._pending.values() if p.state == "asked"]
