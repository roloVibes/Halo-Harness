"""halo_harness.remote.base -- the part of a `SessionHandle` that only touches
the Session or the event hub (shared by `ControllerHandle` and
`PrintModeHandle`): interrupt, the answers (with the TUI's once / session /
always permission scopes), status, tail, subscribe. See remote/handle.py."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Optional

from halo_harness.remote.feed import EventHub, Subscription

MODES = ("default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions")
NOTE_CHARS = 120
SHUTDOWN_WAIT_S = 900.0  # a shutdown waits this long for the current tool call to end


class HandleError(Exception):
    """A bad request (unknown mode, unresolvable model, nothing to steer ...);
    the socket turns it into `{"ok": false, "error": ...}`."""


def render_tail(nodes: list, n: int) -> str:
    """The last `n` user/assistant messages of a node list as Markdown."""
    from halo_harness.controller import _messages_from_nodes
    msgs = _messages_from_nodes(nodes)[-max(1, int(n)):]
    parts = []
    for m in msgs:
        parts.append(f"## {'User' if m['role'] == 'user' else 'Assistant'}\n\n{m['text'].strip()}\n")
    return "\n".join(parts) if parts else "(no messages yet)\n"


def _short(text: str) -> str:
    one = " ".join((text or "").split())
    return one if len(one) <= NOTE_CHARS else one[:NOTE_CHARS - 3] + "..."


class _BaseHandle:
    kind = "base"

    def __init__(self, session, cwd) -> None:
        self.session = session
        self.cwd = Path(cwd)
        self.hub = EventHub()
        self._suggested: dict = {}
        self._remote_peers: set = set()
        self._remote_lock = threading.Lock()
        self.hub.add_observer(self._observe)

    # ---- subclass hooks --------------------------------------------------
    def attach(self) -> None:
        self.hub.start()

    def detach(self) -> None:
        self.hub.close()

    def _note(self, text: str) -> None:
        """A `(remote)`-tagged transcript line, where the surface has one."""

    def _add_rule(self, rule: str, scope: str):
        raise NotImplementedError

    def _remote_changed(self, count: int, peers: list, peer: str, attached: bool) -> None:
        """A phone attached or detached (see set_remote_peer)."""

    def _resolve_permission(self, request_id: str, reply: dict) -> bool:
        return self.session.resolve_permission(request_id, _decision(reply))

    def fleet_shutdown(self, text: str) -> None:
        """`shutdown` (3.0.5.0): every agent already ends at its next tool
        boundary (agent/agent_inbox.py); this closes the session once the
        turn is over. Subclasses say how (`_close_after_shutdown`)."""
        self._note(text)

        def _wait_then_close() -> None:
            end = time.monotonic() + SHUTDOWN_WAIT_S
            while getattr(self.session, "busy", False) and time.monotonic() < end:
                time.sleep(0.1)
            self._close_after_shutdown(text)
        threading.Thread(target=_wait_then_close, daemon=True, name="halo-fleet-shutdown").start()

    def _close_after_shutdown(self, text: str) -> None:
        """Nothing to close for a bare handle (a flow's org session ends with its run)."""

    # ---- feed ------------------------------------------------------------
    def _observe(self, ev) -> None:
        if ev.kind == "permission_request":
            rid = ev.data.get("id")
            if rid:
                self._suggested[rid] = ev.data.get("suggested_rule")
                while len(self._suggested) > 64:
                    self._suggested.pop(next(iter(self._suggested)))

    def subscribe(self, *, kinds=None, maxsize: int = 256) -> Subscription:
        return self.hub.subscribe(maxsize, kinds)

    def unsubscribe(self, sub: Subscription) -> None:
        self.hub.unsubscribe(sub)

    # ---- state -------------------------------------------------------------
    @property
    def session_id(self) -> str:
        return self.session.log.session_id

    def title(self) -> str:
        for node in reversed(self.session.log.nodes()):
            if node.get("type") == "meta" and isinstance(node.get("title"), str) and node["title"]:
                return node["title"]
        return ""

    def _pending(self) -> dict:
        s = self.session
        return {"permission": sorted(getattr(s, "_permission_waiters", {}) or {}),
                "question": sorted(getattr(s, "_question_waiters", {}) or {}),
                "plan": sorted(getattr(s, "_plan_waiters", {}) or {}),
                "approval": sorted(getattr(s, "_approval_waiters", {}) or {})}

    def set_remote_peer(self, peer: str, attached: bool) -> int:
        """Record that phone `peer` (an ACI prefix) attached or detached;
        returns how many are attached now."""
        with self._remote_lock:
            before = len(self._remote_peers)
            (self._remote_peers.add if attached else self._remote_peers.discard)(peer)
            peers = sorted(self._remote_peers)
            changed = len(peers) != before
        if changed:
            self._remote_changed(len(peers), peers, peer, attached)
        return len(peers)

    def status(self) -> dict:
        data = dict(self.session.status_event().data)
        data.update(session_id=self.session_id, cwd=str(self.cwd), title=self.title(), busy=bool(self.session.busy),
                    kind=self.kind, pid=os.getpid(), pending=self._pending(),
                    remote_attached=len(self._remote_peers), agents=_live_agents(self.session))
        return data

    def tail(self, n: int = 20) -> str:
        return render_tail(self.session.log.nodes(), n)

    # ---- direct controls ---------------------------------------------------
    def interrupt(self) -> dict:
        self._note("interrupt")
        self.session.abort.set()
        return {"interrupted": True}

    @staticmethod
    def _check_mode(mode: str) -> str:
        if mode not in MODES:
            raise HandleError(f"unknown mode {mode!r} (expected one of {', '.join(MODES)})")
        return mode

    @staticmethod
    def _check_effort(level: str) -> str:
        from halo_harness.providers.profiles import EFFORT_LEVELS
        if level not in EFFORT_LEVELS:
            raise HandleError(f"unknown effort {level!r} (expected one of {', '.join(EFFORT_LEVELS)})")
        return level

    # ---- answers -------------------------------------------------------------
    def answer_permission(self, request_id: str, action: str, *, scope: str = "once",
                           message: str = "", rule: Optional[str] = None) -> bool:
        """`scope` once|session|always; the rule to learn defaults to the
        `suggested_rule` the permission_request event carried (as the TUI)."""
        if action not in ("allow", "deny"):
            raise HandleError(f"permission action must be allow or deny, got {action!r}")
        if scope not in ("once", "session", "always"):
            raise HandleError(f"permission scope must be once, session or always, got {scope!r}")
        suggested = rule or self._suggested.get(request_id)
        # Only an allow learns rules (as the TUI, whose deny carries no scope):
        # a deny with session/always must never write allow rules anywhere.
        rules = ([r.strip() for r in suggested.split(", ") if r.strip()]
                 if (action == "allow" and scope in ("session", "always") and suggested) else [])
        reply = {"action": action, "reason": "", "rule": rules[0] if rules else None, "message": message or ""}
        if not self._resolve_permission(request_id, reply):
            return False
        self._suggested.pop(request_id, None)
        self._note(f"permission {action} ({scope})")
        for extra in rules[1:]:
            self._add_rule(extra, "session")
        if scope == "always":
            for r in rules:
                try:
                    self._add_rule(r, "local")
                except Exception:
                    pass
        return True

    def answer_question(self, request_id: str, answer) -> bool:
        ok = self.session.resolve_question(request_id, answer)
        if ok:
            self._note("question answered")
        return ok

    def answer_plan(self, approved: bool, *, feedback: str = "", mode_after: Optional[str] = None) -> bool:
        ok = self.session.resolve_plan({"approved": bool(approved), "feedback": feedback or "",
                                         "mode_after": mode_after})
        if ok:
            self._note("plan " + ("approved" if approved else "sent back"))
        return ok

    def answer_approval(self, request_id: str, action: str, *, instruction: str = "") -> bool:
        if action not in ("accept", "edit", "stop"):
            raise HandleError(f"approval action must be accept, edit or stop, got {action!r}")
        ok = self.session.resolve_approval(request_id, {"action": action, "instruction": instruction or None})
        if ok:
            self._note(f"approval {action}")
        return ok


def _live_agents(session) -> int:
    """Sub-agents queued, running, waiting or paused right now (3.0.5.0 Fleet)."""
    tree = getattr(session, "_fleet_tree", None)
    try:
        return tree.live_count() if tree is not None else 0
    except Exception:
        return 0


def _decision(reply: dict):
    from halo_harness.permissions import Decision
    return Decision(action=reply.get("action", "deny"), reason=reply.get("reason", ""),
                    rule=reply.get("rule"), message=reply.get("message", ""))
