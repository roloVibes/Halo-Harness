"""halo_harness.remote.prompt_queue -- what a `submit` does while a turn runs (Halo 3.3.11.0 R1, Studio's Prompt
panel), and the one user turn a session may hold for later.

`submit` (remote/protocol.py) takes two more fields:

    origin     {via: "studio", by}   where the turn came from: the TUI's transcript line says "(from Studio)",
                                     the turn's `user_message` carries `via` / `by` (remote/receipt_seams.stamp)
    when_busy  steer (the default: today's behaviour, the Signal remote's unchanged) | refuse | queue

* `refuse`: a busy session answers `{busy: true, line}` and takes nothing; the panel then offers Queue it / Steer.
* `queue`: the session holds ONE user turn (`PromptQueue.hold`) and submits it when the running turn ends: on the
  main session's `turn_done` (the handle's hub observer, `on_event`) the held turn goes straight onto the
  Controller's command queue as a `user_input` Command with its meta (never through `Controller.submit`, which
  would read the still-busy session and make it a steer), so the worker runs it as the next turn. A second
  `queue` while one is held answers `{busy: true, held: true, line}` (Studio: 409). The TUI's prompt hint says
  "1 queued from Studio" while it waits (`hint`); a session that quits with one held drops it with one line.

A held turn whose session finished its turn between the busy read and the hold (the `turn_done` already seen
for the current turn) is handed over at once, so it never waits for a turn that is not coming.
"""

from __future__ import annotations

import threading
from typing import Optional

WHEN_BUSY = ("steer", "refuse", "queue")
BUSY_LINE = "A turn is running: queue this one (it starts when the running turn ends) or steer the running turn with it."
HELD_LINE = "One turn is already queued from Studio: it starts when the running turn ends (send this one after it)."
HINT = "1 queued from Studio: it starts when this turn ends"


def submit_kw(req: dict) -> dict:
    """The socket request's `origin`, `when_busy` and `receipt`, only those it names (a request without them is
    the call it always was)."""
    kw: dict = {}
    origin = req.get("origin")
    if isinstance(origin, dict) and origin.get("via"):
        kw["origin"] = {"via": str(origin["via"])[:32], "by": " ".join(str(origin.get("by") or "").split())[:64]}
    wb = req.get("when_busy")
    if isinstance(wb, str) and wb:
        if wb not in WHEN_BUSY:
            from halo_harness.remote.base import HandleError
            raise HandleError(f"when_busy is one of {', '.join(WHEN_BUSY)}, got {wb!r}")
        kw["when_busy"] = wb
    rid = req.get("receipt")
    if isinstance(rid, str) and rid:
        kw["receipt"] = rid[:64]
    return kw


def meta_of(origin: Optional[dict], receipt: str = "") -> dict:
    """The `user_input` Command's meta: `{via, by, receipt}`, only the parts there are."""
    meta: dict = {}
    if isinstance(origin, dict) and origin.get("via"):
        meta["via"] = origin["via"]
        if origin.get("by"):
            meta["by"] = origin["by"]
    if receipt:
        meta["receipt"] = receipt
    return meta


def origin_word(origin: Optional[dict]) -> str:
    """How a transcript line names the sender: "from Studio" (a Studio send), else "remote" (the phone, a CLI)."""
    via = str((origin or {}).get("via") or "").lower() if isinstance(origin, dict) else ""
    return "from Studio" if via == "studio" else (f"from {via}" if via else "remote")


class PromptQueue:
    """One held user turn for a Controller-driven session."""

    def __init__(self, controller) -> None:
        self.controller = controller
        self._lock = threading.Lock()
        self.held: Optional[dict] = None
        self._done_turn = 0

    @property
    def session(self):
        return self.controller.session

    def hint(self) -> str:
        return HINT if self.held is not None else ""

    def hold(self, text: str, images, meta: dict) -> bool:
        """Hold the turn; False when one is held already. Handed over at once when the current turn already ended."""
        with self._lock:
            if self.held is not None:
                return False
            self.held = {"text": text, "images": images, "meta": dict(meta or {})}
            ended = not self.session.busy or self._done_turn >= int(getattr(self.session, "turn_count", 0) or 0)
            if ended:
                self._handover_locked()
        self._note(f"queued: {_short(text)}" if not ended else "")
        return True

    def on_event(self, ev) -> None:
        """The hub observer: the main session's `turn_done` hands the held turn over."""
        if getattr(ev, "kind", "") != "turn_done" or getattr(ev, "agent_id", None):
            return
        with self._lock:
            self._done_turn = max(self._done_turn, int(getattr(ev, "turn", 0) or 0))
            if self.held is not None:
                self._handover_locked()

    def _handover_locked(self) -> None:
        from halo_harness import events
        held, self.held = self.held, None
        if held is None:
            return
        self.controller.commands.put(events.Command("user_input", {"text": held["text"], "images": held["images"],
                                                                     "pasted": None, "meta": held["meta"]}))
        self._note(f"the queued turn starts: {_short(held['text'])}")

    def drop(self) -> Optional[dict]:
        """The session ends: the held turn (if any) is dropped with one line; returns it."""
        with self._lock:
            held, self.held = self.held, None
        if held is not None:
            self._note(f"the queued turn was dropped (the session is ending): {_short(held['text'])}")
        return held

    def _note(self, text: str) -> None:
        if not text:
            return
        try:
            from halo_harness import events
            self.controller.events.put(events.system_note(f"(from Studio) {text}"))
        except Exception:
            pass


def _short(text: str) -> str:
    from halo_harness.remote.base import _short as short
    return short(text)


def hint_for(controller) -> str:
    """The TUI's prompt hint while a Studio turn waits ("" otherwise)."""
    q = getattr(controller, "prompt_queue", None)
    try:
        return q.hint() if q is not None else ""
    except Exception:
        return ""
