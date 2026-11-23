"""halo_harness.agent.agent_inbox -- what Studio (or `halo remote`) asks of
one agent, and the two places the loop honours it (Halo 3.0.5.0 "Fleet" R1).

One `Controls` per agent tree (`agent_registry.AgentTree.controls`):

* the steer inbox: notes for one agent, drained by THAT agent's loop right
  before its next model call and applied through the path a typed steer
  takes (`Session._apply_pending_steers_events`: UserPromptSubmit hooks
  run, the note is logged as a user-role steer). A `redirect` also leaves
  the rest of the agent's current tool round unrun ("not run: redirected
  ..."), so its next model call starts from the new task.
* stop: the agent and its subtree end at their next tool boundary (checked
  before every tool call and before every model call); the parent's tool
  result is "stopped from <via>: <reason>" and the parent goes on (3.6.0.2
  P3: no line names a user or host, only the request's via).
* pause / resume: an agent and its subtree, or the whole session, hold at
  the next tool boundary until resumed (state `paused` meanwhile).
* shutdown: every agent ends at its next boundary; the session then closes.

Code decides: the loop reads these flags, nothing here is ever put to a
model. A note is a user-role message like any steer: it never changes a
permission, answers a card, moves an Orchestra claim or skips a gate.
"""

from __future__ import annotations

import time
from typing import Optional

POLL_S = 0.25
ALL = "*"
_NO_TEXT = "(the sub-agent finished without producing a final text answer)"
PARTIAL_CAP = 1500


def who(rec: dict) -> str:
    """Where a stop or pause came from: its via only (3.6.0.2 P3)."""
    return f"from {rec.get('via') or 'Studio'}"


class Controls:
    def __init__(self, tree) -> None:
        self.tree = tree
        self.inbox: dict = {}
        self.cuts: dict = {}
        self.stops: dict = {}
        self.pauses: dict = {}
        self.shutdown: Optional[dict] = None

    def _rec(self, via: str, **extra) -> dict:
        return {"via": via or "Studio", "ts": time.time(), **extra}

    # ---- the inbox ----------------------------------------------------------
    def post(self, aid: str, note: str, *, cut_by: Optional[str] = None) -> int:
        """`cut_by` is a redirect's via (3.6.0.2 P3): the cut results read "not run: redirected from <via>"."""
        with self.tree.cv:
            self.inbox.setdefault(aid, []).append(note)
            if cut_by:
                self.cuts[aid] = cut_by
            self.tree.cv.notify_all()
            return len(self.inbox[aid])

    def drain(self, aid: str) -> list:
        with self.tree.lock:
            return self.inbox.pop(aid, [])

    def take_cut(self, aid: str) -> Optional[str]:
        with self.tree.lock:
            return self.cuts.pop(aid, None)

    # ---- stop / shutdown ------------------------------------------------------
    def stop(self, aid: str, reason: str, via: str = "Studio") -> list:
        with self.tree.cv:
            self.stops[aid] = self._rec(via, reason=reason)
            self.tree.cv.notify_all()
        return self.tree.subtree(aid)

    def begin_shutdown(self, reason: str, via: str = "Studio") -> None:
        with self.tree.cv:
            self.shutdown = self._rec(via, reason=reason)
            self.tree.cv.notify_all()

    def stop_record(self, aid: str) -> Optional[dict]:
        with self.tree.lock:
            if self.shutdown is not None:
                return self.shutdown
            for a in self.tree.lineage(aid):
                if a in self.stops:
                    return self.stops[a]
        return None

    def clear(self, aid: str) -> None:
        """A respawned agent (a task_id resume) starts with no flags."""
        with self.tree.lock:
            for table in (self.stops, self.pauses, self.cuts, self.inbox):
                table.pop(aid, None)
            pub = self._pause_row(aid)
        self.tree._publish(pub)

    # ---- pause / resume ---------------------------------------------------------
    # 3.6.0.15 F3: an agent's row carries `pause_set` -- its OWN key is in `pauses` (the pause its Resume takes
    # back), true from the press until a resume, also before it holds; a session-wide pause sets it on no row.
    # 3.6.0.16 C4: the row is written under the ONE lock that guards `pauses` (tree.lock; tree.cv is built on it), from
    # the truth at that moment, so a Pause and a Resume that cross leave it true; no other lock is taken. The frame
    # goes to the listeners after the lock is left.
    def _pause_row(self, aid: Optional[str]):
        """Under tree.lock: the row's `pause_set` = `aid in pauses` now -> the frame to publish once the lock is left."""
        row = self.tree.rows.get(aid) if aid else None
        if row is None:
            return None
        before = dict(row)
        row["pause_set"] = aid in self.pauses
        return self.tree._commit(aid, row, before)

    def pause(self, aid: Optional[str], via: str = "Studio") -> bool:
        """False when it was paused already (the parent is told once)."""
        with self.tree.cv:
            key = aid or ALL
            fresh = key not in self.pauses
            self.pauses[key] = self._rec(via)
            pub = self._pause_row(aid)
        self.tree._publish(pub)
        return fresh

    def resume(self, aid: Optional[str]) -> bool:
        with self.tree.cv:
            had = self.pauses.pop(aid or ALL, None) is not None
            self.tree.cv.notify_all()
            pub = self._pause_row(aid)
        self.tree._publish(pub)
        return had

    def pause_record(self, aid: str) -> Optional[dict]:
        with self.tree.lock:
            if ALL in self.pauses:
                return self.pauses[ALL]
            for a in self.tree.lineage(aid):
                if a in self.pauses:
                    return self.pauses[a]
        return None


# ---- the loop's two checkpoints ---------------------------------------------------

def _ctx(session):
    tree = getattr(session, "_agent_tree", None)
    if tree is None:
        return None, None
    from halo_harness.agent.agent_registry import agent_key
    return tree, agent_key(session)


def _hold(tree, aid: str, abort) -> None:
    """Block while this agent (or an ancestor, or the session) is paused;
    a stop, a shutdown or the session's interrupt ends the hold too."""
    c = tree.controls
    if c.pause_record(aid) is None:
        return
    tree.update(aid, state="paused")
    try:
        with tree.cv:
            while c.pause_record(aid) is not None and c.stop_record(aid) is None \
                    and not (abort is not None and abort.is_set()):
                tree.cv.wait(POLL_S)
    finally:
        if tree.state_of(aid) == "paused":
            tree.update(aid, state="running")


def before_tool(session) -> "Optional[tuple]":
    """Checked before every tool call: None runs it; `(reason, end_turn)`
    leaves it and the rest of this round unrun with `reason` as their
    results (`end_turn` True for a stop, False for a redirect)."""
    tree, aid = _ctx(session)
    if tree is None:
        return None
    try:
        _hold(tree, aid, getattr(session, "abort", None))
        rec = tree.controls.stop_record(aid)
        if rec is not None:
            return f"not run: stopped {who(rec)}", True
        via = tree.controls.take_cut(aid)
        if via:
            return f"not run: redirected from {via}", False
    except Exception:
        return None
    return None


def before_model(session, turn_no: int):
    """Checked before every model call (a generator): holds while paused,
    returns True when this agent is stopped, else applies its inbox."""
    tree, aid = _ctx(session)
    if tree is None:
        return False
    try:
        _hold(tree, aid, getattr(session, "abort", None))
        if tree.controls.stop_record(aid) is not None:
            return True
        notes = tree.controls.drain(aid)
        if notes:  # delivered now: the round this call plans already reads the redirect, so it is not cut
            tree.controls.take_cut(aid)
    except Exception:
        return False
    if notes:
        with session._steer_lock:
            session._steer_queue.extend(notes)
        yield from session._apply_pending_steers_events(turn_no)
    return False


def was_stopped(child) -> bool:
    tree, aid = _ctx(child)
    return tree is not None and tree.controls.stop_record(aid) is not None


def handback(child, text: str) -> str:
    """What a stopped child's parent receives instead of its final text."""
    tree, aid = _ctx(child)
    rec = tree.controls.stop_record(aid) if tree is not None else None
    if rec is None:
        return text
    line = f"stopped {who(rec)}: {rec.get('reason') or 'no reason given'}"
    partial = (text or "").strip()
    if partial and partial != _NO_TEXT:
        line += "\n\nWhat it had written before it stopped:\n" + partial[-PARTIAL_CAP:]
    return line
