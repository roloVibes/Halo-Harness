"""halo_harness.agent.turn_marker -- Halo 3.2.2.0 R4: the line a turn ends
with, and the nudge for a reply that promised work and stopped.

Every finished turn gets ONE `turn_marker` event, yielded right before its
`turn_done` (agent/loop.py's `Session.turn` wraps `_turn_inner` with
`with_markers`):

    ◼ done · 42 s · 3 tools · $0.012       the model ended the turn
    ◼ waiting on you: <what>               the turn ends on a question / the plan
    ◼ stopped: <why>                       max_tokens, max turns, an error, a hook, Esc

A card the turn waits on (a permission ask, a question, the plan review, an
approval) also gets a `waiting` marker the moment the card is shown, with
`mid_turn: True` (the TUI already has its `⏸ ... see below` line for it;
Studio's Session feed shows the marker).

The nudge (`should_nudge`): a reply with no tool call whose last sentence
promises action ("Now I'll edit X.") gets one user-role notice, NUDGE_TEXT,
and one more model call -- once per turn, never when the turn waits on the
user, off with `turn.nudge_promises: false`.
"""

from __future__ import annotations

import re
import time
from typing import Iterator, Optional

from halo_harness import events

NUDGE_TEXT = "You ended your turn while saying you would do more. Continue."
NUDGED_LINE = "↳ nudged: the reply promised work and stopped"
_ASK_KINDS = {"permission_request": "permission", "question": "question", "plan_review": "plan",
              "approval_request": "approval"}

# The opening of a last sentence that promises more work. "Let me know" and
# "I'll wait" end a reply that is waiting on the user, so they never count.
_PROMISE_RE = re.compile(
    r"^(?:(?:ok|okay|alright|great|good|sure|now|next|then|first)[,!.]?\s+)?"
    r"(?:i'll|i’ll|i will|let me|now i|next,?\s+i|going to|i'm going to|i’m going to|i am going to)\b",
    re.IGNORECASE)
_NOT_A_PROMISE_RE = re.compile(r"^(?:let me know|i'll wait|i’ll wait|i will wait)\b", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _last_sentence(text: str) -> str:
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text or "") if p and p.strip()]
    return parts[-1] if parts else ""


def promises_work(text: str) -> bool:
    """True when the reply's LAST sentence opens with a promise of action
    ("I'll", "I will", "Let me", "Now I", "Next, I", "Going to")."""
    last = _last_sentence(text).lstrip("*_-> ").strip()
    if not last or last.endswith("?"):
        return False
    if _NOT_A_PROMISE_RE.match(last):
        return False
    return bool(_PROMISE_RE.match(last))


def asks_the_user(text: str) -> Optional[str]:
    """The reply's last line when it is a question to the user, else None."""
    lines = [ln.strip() for ln in (text or "").strip().splitlines() if ln.strip()]
    if lines and lines[-1].rstrip("*_ ").endswith("?"):
        return lines[-1].strip("*_ ")
    return None


def nudge_enabled() -> bool:
    from halo_harness.theme import get_config_value
    return bool(get_config_value("turn.nudge_promises", default=True))


def should_nudge(session, final_text: str) -> bool:
    """Once per turn, on, the turn not waiting on the user, and the reply promising work."""
    if getattr(session, "_turn_nudged", False) or getattr(session, "_turn_waiting_on", None):
        return False
    if asks_the_user(final_text) is not None or not promises_work(final_text):
        return False
    return nudge_enabled()


def _clip(text: str, n: int = 100) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 3] + "..."


def format_elapsed(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    if s < 60:
        return f"{s} s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m} m {s:02d} s"
    h, m = divmod(m, 60)
    return f"{h} h {m:02d} m"


def done_line(*, elapsed_s: float, tools: int, cost_usd: Optional[float]) -> str:
    parts = ["◼ done", format_elapsed(elapsed_s)]
    if tools:
        parts.append(f"{tools} tool" + ("" if tools == 1 else "s"))
    if cost_usd is not None:
        parts.append(f"${cost_usd:.3f}")
    return " · ".join(parts)


def _ask_what(kind: str, data: dict) -> str:
    if kind == "permission_request":
        return f"permission for {data.get('name') or 'a tool'}"
    if kind == "question":
        inp = data.get("input") if isinstance(data.get("input"), dict) else {}
        qs = inp.get("questions") if isinstance(inp.get("questions"), list) else []
        q = (qs[0].get("question") if qs and isinstance(qs[0], dict) else None) or inp.get("question")
        return f"the question \"{_clip(q, 80)}\"" if q else "the question"
    if kind == "plan_review":
        return "the plan (1 approve, 2 approve manual, 3 keep planning)"
    return f"approval for {data.get('position') or 'a result'}"


class TurnTracker:
    """What one turn did, read off its own events (never a child's)."""

    def __init__(self, session) -> None:
        self.session = session
        self.t0 = time.monotonic()
        meter = getattr(session, "cost_meter", None)
        self.cost0 = meter.total_usd if meter is not None and meter.has_cost_data else 0.0
        self.tools = 0
        self.last_error: Optional[str] = None
        self.last_text = ""
        self._cur: list = []

    def see(self, ev) -> None:
        if ev.agent_id is not None:
            return
        kind = ev.kind
        if kind == "tool_use_ready":
            self.tools += 1
        elif kind == "error":
            self.last_error = str(ev.data.get("message") or "") or self.last_error
        elif kind == "message_start":
            self._cur = []
        elif kind == "text_delta":
            self._cur.append(str(ev.data.get("text") or ""))
        elif kind == "message_end":
            self.last_text = "".join(self._cur)

    def _cost(self) -> Optional[float]:
        meter = getattr(self.session, "cost_meter", None)
        if meter is None or not meter.has_cost_data:
            return None
        return max(0.0, (meter.total_usd or 0.0) - (self.cost0 or 0.0))

    def end_marker(self, reason: str, *, turn: int) -> events.Event:
        s = self.session
        stop_why = getattr(s, "_turn_stop_why", None)
        waiting = getattr(s, "_turn_waiting_on", None)
        elapsed = time.monotonic() - self.t0
        if reason == "interrupted":
            return events.turn_marker("stopped", "◼ stopped: interrupted (Esc)", turn=turn, reason=reason)
        if reason == "max_tokens":
            return events.turn_marker("stopped", "◼ stopped: the reply hit its output limit (max_tokens)",
                                      turn=turn, reason=reason)
        if reason == "max_turns":
            n = getattr(s, "max_turns", None)
            return events.turn_marker("stopped", f"◼ stopped: the turn used its {n} model calls (--max-turns)",
                                      turn=turn, reason=reason)
        if reason == "error":
            why = _clip((self.last_error or "the model call failed").splitlines()[0], 140)
            return events.turn_marker("stopped", f"◼ stopped: {why}", turn=turn, reason=reason)
        if reason == "blocked":
            why = _clip(stop_why or "a UserPromptSubmit hook", 140)
            return events.turn_marker("stopped", f"◼ stopped: blocked by {why}", turn=turn, reason=reason)
        if stop_why:
            return events.turn_marker("stopped", f"◼ stopped: {_clip(stop_why, 140)}", turn=turn, reason=reason)
        question = asks_the_user(self.last_text)
        if waiting or question:
            what = waiting or f"the question \"{_clip(question, 80)}\""
            return events.turn_marker("waiting", f"◼ waiting on you: {what}", turn=turn, reason=reason)
        return events.turn_marker("done", done_line(elapsed_s=elapsed, tools=self.tools, cost_usd=self._cost()),
                                  turn=turn, reason=reason, elapsed_s=round(elapsed, 1), tools=self.tools)

    def waiting_marker(self, ev) -> events.Event:
        what = _ask_what(ev.kind, ev.data if isinstance(ev.data, dict) else {})
        return events.turn_marker("waiting", f"◼ waiting on you: {what}", turn=ev.turn,
                                  ask=_ASK_KINDS.get(ev.kind), mid_turn=True)


def reset_turn_state(session) -> None:
    """Per-turn flags the loop sets: the nudge's once, a stop reason, what the turn waits on."""
    session._turn_nudged = False
    session._turn_stop_why = None
    session._turn_waiting_on = None


def with_markers(session, gen, turn_no: int) -> Iterator[events.Event]:
    """`gen`'s events, plus a `turn_marker` right before the main session's
    `turn_done` and right after each card the turn waits on."""
    tracker = TurnTracker(session)
    try:
        for ev in gen:
            tracker.see(ev)
            if ev.kind == "turn_done" and ev.agent_id is None:
                yield tracker.end_marker(str(ev.data.get("reason") or "end_turn"), turn=ev.turn or turn_no)
            yield ev
            if ev.kind in _ASK_KINDS and ev.agent_id is None:
                yield tracker.waiting_marker(ev)
    finally:
        close = getattr(gen, "close", None)
        if callable(close):
            close()
