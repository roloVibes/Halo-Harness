"""halo_harness.remote.handle -- `SessionHandle`, the one surface the control
socket (and the Signal bridge behind it) drives a live session through.

Two implementations: `ControllerHandle` (the TUI: wraps `Controller`, every
method per the verified table in docs/harness/SIGNAL-RESEARCH.md 9.1) and
`remote.print_handle.PrintModeHandle` (`halo -p`: no Controller, so it wraps
the bare `Session` plus the stream-json input queue). Both share
`_BaseHandle` for the parts that only touch the Session or the event hub
(interrupt, answers, tail, subscribe, the "session"/"always" permission
scopes exactly as `tui/app.py::resolve_permission_decision` does them).

The handle never pushes raw `events.Command`s: it calls Controller / Session
methods (9.2). Every method is safe to call from the socket's own thread.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from halo_harness import events
from halo_harness.remote.base import HandleError, _BaseHandle, _short  # HandleError is re-exported here
from halo_harness.remote.feed import EventHub, Subscription


@runtime_checkable
class SessionHandle(Protocol):
    kind: str
    hub: EventHub

    @property
    def session_id(self) -> str: ...
    def status(self) -> dict: ...
    def submit(self, text: str, *, images: Optional[list] = None) -> dict: ...
    def interrupt(self) -> dict: ...
    def set_mode(self, mode: str) -> dict: ...
    def set_model(self, ref: str) -> dict: ...
    def set_effort(self, level: str) -> dict: ...
    def answer_permission(self, request_id: str, action: str, *, scope: str = "once",
                           message: str = "", rule: Optional[str] = None) -> bool: ...
    def answer_question(self, request_id: str, answer) -> bool: ...
    def answer_plan(self, approved: bool, *, feedback: str = "", mode_after: Optional[str] = None) -> bool: ...
    def answer_approval(self, request_id: str, action: str, *, instruction: str = "") -> bool: ...
    def run_slash(self, name: str, args: str = "") -> str: ...
    def tail(self, n: int = 20) -> str: ...
    def subscribe(self, *, kinds=None, maxsize: int = 256) -> Subscription: ...
    def unsubscribe(self, sub: Subscription) -> None: ...
    def attach(self) -> None: ...
    def detach(self) -> None: ...


class ControllerHandle(_BaseHandle):
    """The TUI's handle: every call is a `Controller` method (table 9.1)."""
    kind = "tui"

    def __init__(self, controller) -> None:
        super().__init__(controller.session, controller.cwd)
        self.controller = controller

    def attach(self) -> None:
        super().attach()
        self.controller.add_event_tap(self.hub.publish)

    def detach(self) -> None:
        self.controller.remove_event_tap(self.hub.publish)
        super().detach()

    def _note(self, text: str) -> None:
        try:
            self.controller.events.put(events.system_note(f"(remote) {text}"))
        except Exception:
            pass

    def _add_rule(self, rule: str, scope: str):
        return self.controller.add_permission_rule(rule, scope)

    def _remote_changed(self, count: int, peers: list, peer: str, attached: bool) -> None:
        try:
            self.controller.events.put(events.remote_attached(count, peers, peer=peer, attached=attached))
        except Exception:
            pass
        self._note(f"phone {peer} {'attached' if attached else 'detached'}")

    def _resolve_permission(self, request_id: str, reply: dict) -> bool:
        return self.controller.answer_permission(request_id, reply)

    def _close_after_shutdown(self, text: str) -> None:
        """The TUI sets `controller.on_fleet_shutdown` (it shows the line and
        exits through its own quit path); without one the Controller quits."""
        hook = getattr(self.controller, "on_fleet_shutdown", None)
        try:
            hook(text) if callable(hook) else self.controller.quit()
        except Exception:
            pass

    def title(self) -> str:
        return self.controller.get_title()

    def submit(self, text: str, *, images: Optional[list] = None) -> dict:
        text = (text or "").strip()
        if not text:
            raise HandleError("empty prompt")
        steered = bool(self.session.busy)
        self._note(("steer: " if steered else "prompt: ") + _short(text))
        self.controller.submit(text, images=images)
        return {"steered": steered}

    def set_mode(self, mode: str) -> dict:
        self._check_mode(mode)
        self._note(f"mode {mode}")
        self.controller.set_permission_mode(mode)
        return {"mode": mode}

    def set_model(self, ref: str) -> dict:
        if not ref:
            raise HandleError("model ref required")
        err = self.controller.set_model(ref)
        if err:
            raise HandleError(err)
        self._note(f"model {ref}")
        return {"model": ref, "queued": True}

    def set_effort(self, level: str) -> dict:
        self._check_effort(level)
        text = self.controller.run_slash("effort", level)
        self._note(f"effort {level}")
        return {"effort": getattr(self.session, "effort", level), "message": text}

    def run_slash(self, name: str, args: str = "") -> str:
        name = (name or "").lstrip("/").strip()
        if not name:
            raise HandleError("slash command name required")
        self._note(f"/{name} {_short(args)}".strip())
        return self.controller.run_slash(name, args or "")
