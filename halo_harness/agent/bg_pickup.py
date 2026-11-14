"""halo_harness.agent.bg_pickup -- background work that finishes while the session is idle (Halo 3.4.1.3).

The owner (2026-11-13): replies said "while you were away these tasks happened", but only once he sent a prompt.
A background sub-agent (agent/subagent.py `_bg_run`) or Bash job (agent/jobs.py `_push_notice`) queues its
completion notice on the session, and before this only the NEXT turn read it: his next message. Now, when one
finishes while the session is IDLE (no turn running) and the session runs under the worker pump (`Session.run`:
the TUI, Studio's session without a terminal):

1. At once, with no model call: a `turn_marker` of state `background` (the TUI draws it as a transcript line and
   on the status bar; Studio's Session feed shows it), a fresh `status` frame, and `session._bg_done`, which the
   control socket's `status` carries (remote/base.py) and Attention lists as a `background_done` row: Agents ->
   Live's attention chip, the glance and the browser alert (`studio.alerts`) see it.
2. With `background.when_done: continue` (the default) the main agent then takes a turn BY ITSELF: completions
   that land within WINDOW_S are one turn; never while the TUI's input holds text (`set_typing`) or an ask is
   open (it waits until the text is sent or cleared); the turn carries no message of the person's, only the
   finished work under FRAME_HEAD (the status-notice frame: not a message from the human); `background.self_turns`
   (default 3) turns in a row with no message from the person, or the session's spend cap, stop it with one line.

`tell` does 1 without 2; `wait` is the behaviour before 3.4.1.3 (the next message reads them). A finish DURING a
turn, `-p` and a bare Session (no pump, nothing attached) are unchanged.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from halo_harness import events

WINDOW_S = 3.0  # completions this close together are one self-started turn
ASK_RETRY_S = 2.0  # an ask is open: look again after this long
SETTING = "background.when_done"
MODES = ("continue", "tell", "wait")
CAP_KEY = "background.self_turns"
DEFAULT_CAP = 3
TURN_LABEL = "(background work finished)"  # the agent tree's task line for a self-started turn

FRAME_HEAD = (
    "<status-notices source=\"harness\">\n"
    "Automated harness status: background work finished while the session was idle.\n"
    "This block is NOT a message from the human: they have sent nothing since your last reply. The harness started\n"
    "this turn so you can read the results below. Tell the human in a few lines what they mean, or carry on with\n"
    "the task they gave you when the results let you; do not invent a new request.\n"
)


class _State:
    def __init__(self, commands) -> None:
        self.commands = commands
        self.lock = threading.Lock()
        self.timer: Optional[threading.Timer] = None
        self.typing = False  # the TUI's input holds text
        self.held = False  # a pickup waits on that text being sent or cleared
        self.self_turns = 0  # self-started turns since the person's last message
        self.stop_said = False  # the cap / spend line was said for this run of turns
        self.pumps = 0  # `bg_pickup` commands handled (what a test waits on)


def _config(key: str, default):
    try:
        from halo_harness.theme import get_config_value
        return get_config_value(key, default=default)
    except Exception:
        return default


def mode() -> str:
    """`background.when_done`: continue (default) | tell | wait."""
    v = _config(SETTING, "continue")
    return v if v in MODES else "continue"


def cap() -> int:
    try:
        return max(0, int(_config(CAP_KEY, DEFAULT_CAP)))
    except (TypeError, ValueError):
        return DEFAULT_CAP


def attach(session, commands) -> None:
    """`Session.run` calls this once: a self-started turn is queued on the pump's own command queue."""
    session._bg_pickup = _State(commands)
    session._bg_done = None
    session._bg_turn = False


def pending(session) -> int:
    return len(getattr(session, "_pending_agent_notices", None) or []) + len(
        getattr(session, "_pending_job_notices", None) or [])


def ask_open(session) -> bool:
    return any(getattr(session, n, None) for n in ("_permission_waiters", "_question_waiters", "_plan_waiters",
                                                  "_approval_waiters"))


def _line_for(line: str, count: int, how: str) -> str:
    what = line if count == 1 else f"{count} background tasks, the last: {line}"
    then = {"continue": "Halo picks it up in a few seconds, no message needed",
            "tell": "Halo reads it with your next message"}[how]
    return f"◼ background work finished: {what} -- {then}"


def finished(session, line: str) -> None:
    """A producer queued a completion notice (call it AFTER the append), from any thread."""
    st = getattr(session, "_bg_pickup", None)
    if st is None or bool(getattr(session, "busy", False)):
        return  # no pump (-p, a bare Session), or a running turn: its next turn reads it, as before
    how = mode()
    if how == "wait":
        return
    now = time.time()
    with st.lock:
        prev = getattr(session, "_bg_done", None) or {}
        count = int(prev.get("count") or 0) + 1
        session._bg_done = {"since": prev.get("since") or now, "at": now, "count": count, "line": line, "mode": how}
    sink = getattr(session, "_event_sink", None)
    if sink is not None:
        try:
            sink(events.turn_marker("background", _line_for(line, count, how), turn=session.turn_count,
                                    line=line, count=count, mode=how))
            sink(session.status_event(phase="idle"))
        except Exception:
            pass
    if how == "continue":
        _arm(st)


def _arm(st: _State, delay: Optional[float] = None) -> None:
    with st.lock:
        if st.timer is not None:
            return  # the window is open: this one rides in the same turn
        t = threading.Timer(WINDOW_S if delay is None else delay, _fire, args=(st,))
        t.daemon = True
        st.timer = t
    t.start()


def _fire(st: _State) -> None:
    with st.lock:
        st.timer = None
    st.commands.put(events.Command("bg_pickup", {}))


def set_typing(session, typing: bool) -> None:
    """The TUI's input changed: a pickup held while it held text goes once it is cleared (a send reads it anyway)."""
    st = getattr(session, "_bg_pickup", None)
    if st is None:
        return
    was, st.typing = st.typing, bool(typing)
    if was and not st.typing and st.held:
        st.held = False
        _arm(st)


def human_turn(session) -> None:
    """The person sent a message: it reads whatever is queued, and the count of turns by itself starts over."""
    st = getattr(session, "_bg_pickup", None)
    if st is not None:
        st.self_turns, st.stop_said, st.held = 0, False, False
    session._bg_done = None


def _stop_reason(session, st: _State) -> Optional[str]:
    n = cap()
    if st.self_turns >= n:
        return (f"{st.self_turns} turn{'' if st.self_turns == 1 else 's'} in a row started by background work with no "
                f"message from you (background.self_turns is {n})")
    team = getattr(session, "team_control", None)
    if team is not None:
        try:
            line = team.budget_refusal()
        except Exception:
            line = None
        if line:
            return f"the spend cap is reached ({line})"
    try:
        from halo_harness.agent.agent_inbox import _ctx
        tree, aid = _ctx(session)
        if tree is not None and tree.controls.pause_record(aid) is not None:
            return "this session is paused (a spend cap, or from Studio)"
    except Exception:
        pass
    return None


def pump(session, out) -> None:
    """The `bg_pickup` command, on the worker thread between turns: take the turn, or say in one line why not."""
    st = getattr(session, "_bg_pickup", None)
    if st is None:
        return
    try:
        _pump(session, st, out)
    finally:
        st.pumps += 1


def _pump(session, st: _State, out) -> None:
    if not pending(session) or mode() != "continue":
        return
    if st.typing:
        st.held = True
        return
    if ask_open(session):
        _arm(st, ASK_RETRY_S)
        return
    why = _stop_reason(session, st)
    if why:
        if not st.stop_said:
            st.stop_said = True
            out(events.turn_marker("background", f"◼ not picked up by itself: {why}; your next message reads it",
                                   turn=session.turn_count, stopped=True))
        return
    st.self_turns += 1
    session._bg_turn = True
    try:
        session._pump_turn(TURN_LABEL, None, out)
    finally:
        session._bg_turn = False


def is_bg_turn(session) -> bool:
    return bool(getattr(session, "_bg_turn", False))


def _drain(session, lock_name: str, list_name: str) -> list:
    with getattr(session, lock_name):
        got = list(getattr(session, list_name, None) or [])
        setattr(session, list_name, [])
    return got


def open_turn(session, turn_no: int):
    """The start of a self-started turn (`Session._turn_inner`, in place of the person's message): logged as one
    (a `bg_turn` meta node, never a user node), drawn as one (a `background` marker), then the queued notices under
    FRAME_HEAD as the turn's one `status_notice` snapshot."""
    from halo_harness.agent.loop import _compact_notices_text
    agent = _drain(session, "_agent_notices_lock", "_pending_agent_notices")
    jobs = _drain(session, "_job_notices_lock", "_pending_job_notices")
    parts = [got[0] if len(got) == 1 else _compact_notices_text(got, noun=noun)
             for got, noun in ((agent, "sub-agent"), (jobs, "job")) if got]
    text = "\n\n".join(parts) or "(the finished work was already read)"
    session.log.append_meta(bg_turn={"turn": turn_no, "notices": len(agent) + len(jobs), "at": time.time()})
    yield events.turn_marker("background", "↻ Halo picks up the finished background work (no message from you)",
                             turn=turn_no, started=True)
    framed = FRAME_HEAD + "\n" + text + "\n</status-notices>"
    session.log.append_snapshot([{"type": "text", "text": framed}], kind="status_notice")
    yield events.status_notice(text, framed=framed, turn=turn_no)
