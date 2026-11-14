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
    def submit(self, text: str, *, images: Optional[list] = None, origin: Optional[dict] = None,
               when_busy: str = "steer", receipt: str = "") -> dict: ...
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
        from halo_harness.remote.prompt_queue import PromptQueue  # 3.3.11.0 R1: the one held Studio turn
        self.queue = controller.prompt_queue = PromptQueue(controller)
        self.hub.add_observer(self._prompt_observe)

    def attach(self) -> None:
        super().attach()
        self.controller.add_event_tap(self.hub.publish)

    def detach(self) -> None:
        self.controller.remove_event_tap(self.hub.publish)
        self.queue.drop()  # 3.3.11.0 R1: a held turn ends with the session; its unread receipts go back to sent
        from halo_harness.remote import receipt_seams
        receipt_seams.requeue(self.session, self.cwd)
        super().detach()

    def _prompt_observe(self, ev) -> None:
        """3.3.11.0 R1: the main session's `turn_done` hands a held turn over and marks what it read replied."""
        self.queue.on_event(ev)
        if ev.kind == "turn_done" and not getattr(ev, "agent_id", None):
            from halo_harness.remote import receipt_seams
            receipt_seams.replied(self.session, int(ev.turn or 0), self.cwd)

    def _note(self, text: str, word: str = "remote") -> None:
        try:
            self.controller.events.put(events.system_note(f"({word}) {text}"))
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
        """The TUI sets `controller.on_control_shutdown` (it shows the line and
        exits through its own quit path); without one the Controller quits."""
        hook = getattr(self.controller, "on_control_shutdown", None)
        try:
            hook(text) if callable(hook) else self.controller.quit()
        except Exception:
            pass

    def title(self) -> str:
        return self.controller.get_title()

    def submit(self, text: str, *, images: Optional[list] = None, origin: Optional[dict] = None,
               when_busy: str = "steer", receipt: str = "") -> dict:
        """A new turn, or a steer while busy (`when_busy` steer, the default); 3.3.11.0 R1: `refuse` answers
        `{busy: true, line}`, `queue` holds one turn for when the running one ends (remote/prompt_queue.py);
        `origin` names the sender in the transcript, `receipt` is marked delivered once the text is taken."""
        from halo_harness.remote import prompt_queue as PQ, receipt_seams
        text = (text or "").strip()
        if not text:
            raise HandleError("empty prompt")
        meta = PQ.meta_of(origin, receipt)
        steered = bool(self.session.busy)
        if steered and when_busy == "refuse":
            return {"busy": True, "steered": False, "queued": False, "line": PQ.BUSY_LINE}
        if steered and when_busy == "queue":
            if self.queue.held is not None:
                return {"busy": True, "held": True, "steered": False, "queued": False, "line": PQ.HELD_LINE}
            receipt_seams.delivered(self.session, receipt, self.cwd)  # taken: before the hold, which may hand it on
            if not self.queue.hold(text, images, meta):
                receipt_seams.failed(self.session, receipt, "held", self.cwd)
                return {"busy": True, "held": True, "steered": False, "queued": False, "line": PQ.HELD_LINE}
            return {"busy": True, "steered": False, "queued": True}
        self._note(("steer: " if steered else "prompt: ") + _short(text), PQ.origin_word(origin))
        receipt_seams.delivered(self.session, receipt, self.cwd)  # taken: before the worker can read it
        if meta:
            self.controller.submit(text, images=images, meta=meta)
        else:
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
