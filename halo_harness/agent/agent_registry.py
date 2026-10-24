"""halo_harness.agent.agent_registry -- the live tree of one session's agents
(Halo 3.0.5.0 "Fleet" round R1).

The main agent is the root (`agent_id` "main"); every sub-agent at every
depth (an Agent/Task call, a count/batch job, a team member,
a background sub-agent) is a node under the agent that spawned it, and the
session's background Bash jobs are leaves under main (`kind: job`, read from
the job registry whenever the tree is listed). A row:

    {agent_id, parent, name, role, bio, lineup, model, kind, task, since,
     state, turns, cost_usd, current, last_text, transcript, tokens_in, tokens_out, model_reason}

`state` is one of STATES; `kind` main | subagent | member | background |
job; `task` the first line of what the agent was asked; `turns` its model
calls; `tokens_in` / `tokens_out` its own session meter's running totals
(3.1.8.0 R6: from each `message_end`, None before its first model call);
`current` the tool in flight with one line of its arguments, or
"thinking"; `last_text` the last characters it wrote; `transcript` its own
session log (a child's `subagents/agent-<id>.jsonl`). How events move a row:
agent/agent_observe.py. Stop, pause and the steer inbox: agent/agent_inbox.py.

Where the harness feeds it (turn start/end, every event, each spawn):
agent/agent_hooks.py. Listeners (the control
socket's feed) get `("agent_state", agent_id, row)` on every change of
state, tool, turns or task (text and cost alone at most once per QUIET_S;
3.1.8.0 R6: a change held inside that window goes out when it ends, so the
last text and cost are never left unsent), and `("agent_event", agent_id,
entry)` for agents someone follows.
"""

from __future__ import annotations

import threading
import time
import weakref
from typing import Optional

from halo_harness.agent.agent_observe import ObserveMixin

MAIN = "main"
STATES = ("queued", "running", "waiting", "paused", "done", "failed", "stopped")
LIVE_STATES = ("queued", "running", "waiting", "paused")
FIELDS = ("agent_id", "parent", "name", "role", "bio", "lineup", "model", "kind", "task", "since", "state",
          "turns", "cost_usd", "current", "last_text", "transcript", "tokens_in", "tokens_out",
          "model_reason")  # 3.1.9.0 R2: why an `auto` member runs on `model` (models_auto.py)
QUIET_FIELDS = frozenset({"last_text", "cost_usd"})
QUIET_S = 1.0
_make_lock = threading.Lock()


def agent_key(session) -> str:
    return getattr(session, "agent_id", None) or MAIN


def _model(session) -> Optional[str]:
    return getattr(getattr(session, "model_ref", None), "raw", None)


def _log_path(session) -> Optional[str]:
    path = getattr(getattr(session, "log", None), "path", None)
    return str(path) if path is not None else None


def tree_for(session) -> "AgentTree":
    """The tree `session` belongs to (a root session gets one on first use)."""
    tree = getattr(session, "_fleet_tree", None)
    if tree is None:
        with _make_lock:
            tree = getattr(session, "_fleet_tree", None)
            if tree is None:
                tree = AgentTree(session)
                session._fleet_tree = tree
    return tree


class AgentTree(ObserveMixin):
    def __init__(self, root) -> None:
        from halo_harness.agent.agent_inbox import Controls
        self.lock = threading.RLock()
        self.cv = threading.Condition(self.lock)
        self.rows: dict = {}
        self.followed: set = set()
        self._sessions: dict = {}
        self._listeners: list = []
        self._live: dict = {}
        self._inflight: dict = {}
        self._last_pub: dict = {}
        self._held: dict = {}  # aid -> the timer of its trailing flush (a quiet change waiting for its window to end)
        self._reason: dict = {}
        self.controls = Controls(self)
        self.root_id = agent_key(root)
        team = getattr(root, "team_control", None) or getattr(getattr(root, "agent_runtime", None), "team_control", None)
        self.add(self.root_id, session=root, parent=None, name="main", role=getattr(root, "role_name", None) or "main",
                 lineup=getattr(team, "name", None), model=_model(root), kind="main", state="done",
                 transcript=_log_path(root))

    @staticmethod
    def _ref(session):
        try:
            return weakref.ref(session)
        except TypeError:
            return lambda: session

    def _new_row(self, aid: str, **fields) -> dict:
        row = self.rows[aid] = {k: None for k in FIELDS}
        row.update(agent_id=aid, since=time.time(), state="queued", turns=0, current="", last_text="", task="")
        row.update(fields)
        return row

    # ---- listeners --------------------------------------------------------
    def add_listener(self, fn) -> None:
        with self.lock:
            self._listeners.append(fn)

    def remove_listener(self, fn) -> None:
        with self.lock:
            if fn in self._listeners:
                self._listeners.remove(fn)

    def _emit(self, kind: str, aid: str, data: dict) -> None:
        for fn in list(self._listeners):
            try:
                fn(kind, aid, data)
            except Exception:
                pass

    def _commit(self, aid: str, row: dict, before: dict, force: bool = False):
        changed = {k for k in FIELDS if row.get(k) != before.get(k)}
        now = time.monotonic()
        quiet = now - self._last_pub.get(aid, 0.0)
        if force or (changed - QUIET_FIELDS) or (changed and quiet >= QUIET_S):
            self._last_pub[aid] = now
            self._held.pop(aid, None)
            return aid, dict(row)
        if changed and aid not in self._held:  # 3.1.8.0 R6: sent when the quiet window ends, never dropped
            timer = self._held[aid] = threading.Timer(max(0.0, QUIET_S - quiet), self._flush, (aid,))
            timer.daemon = True
            timer.start()
        return None

    def _flush(self, aid: str) -> None:
        """The trailing flush: the row as it stands now, unless a frame went out since the change was held."""
        with self.lock:
            if self._held.pop(aid, None) is None or aid not in self.rows:
                return
            self._last_pub[aid] = time.monotonic()
            pub = aid, dict(self.rows[aid])
        self._publish(pub)

    def _publish(self, pub) -> None:
        if pub is not None:
            self._emit("agent_state", pub[0], pub[1])

    # ---- rows ---------------------------------------------------------------
    def add(self, aid: str, *, session=None, **fields) -> None:
        with self.lock:
            row = self.rows.get(aid)
            before = dict(row) if row else {}
            row = row or self._new_row(aid)
            row.update({k: v for k, v in fields.items() if k in FIELDS and v is not None})
            if session is not None:
                self._sessions[aid] = self._ref(session)
            pub = self._commit(aid, row, before, force=True)
        self._publish(pub)

    def update(self, aid: str, **fields) -> None:
        with self.lock:
            row = self.rows.get(aid)
            if row is None:
                return
            before = dict(row)
            row.update({k: v for k, v in fields.items() if k in FIELDS})
            pub = self._commit(aid, row, before)
        self._publish(pub)

    def row(self, aid: str) -> Optional[dict]:
        with self.lock:
            row = self.rows.get(aid)
            return dict(row) if row else None

    def state_of(self, aid: str) -> Optional[str]:
        with self.lock:
            return (self.rows.get(aid) or {}).get("state")

    def session_of(self, aid: str):
        ref = self._sessions.get(aid)
        return ref() if ref is not None else None

    def lineage(self, aid: str) -> list:
        """`aid`, its parent, its grandparent ... up to the root."""
        out: list = []
        with self.lock:
            while aid and aid not in out:
                out.append(aid)
                aid = (self.rows.get(aid) or {}).get("parent")
        return out

    def subtree(self, aid: str) -> list:
        with self.lock:
            out, todo = [], [aid]
            while todo:
                cur = todo.pop(0)
                if cur not in out:
                    out.append(cur)
                    todo += [k for k, r in self.rows.items() if r.get("parent") == cur]
            return out

    def follow(self, aid: str, on: bool) -> list:
        with self.lock:
            if on:
                self.followed.add(aid)
            else:
                self.followed.discard(aid)
                self._live.pop(aid, None)
            return sorted(self.followed)

    def public_rows(self) -> list:
        """Every row (jobs included), parents before their children."""
        with self.lock:
            rows = [dict(r) for r in self.rows.values()]
        from halo_harness.agent.agent_hooks import job_rows
        rows += job_rows(self)
        kids: dict = {}
        for r in sorted(rows, key=lambda r: (r.get("since") or 0, r["agent_id"])):
            kids.setdefault(r.get("parent"), []).append(r)
        order, seen = [], set()

        def walk(r) -> None:
            if r["agent_id"] not in seen:
                seen.add(r["agent_id"])
                order.append(r)
                for k in kids.get(r["agent_id"], []):
                    walk(k)
        for r in kids.get(None, []):
            walk(r)
        return order + [r for r in rows if r["agent_id"] not in seen]

    def live_count(self) -> int:
        with self.lock:
            return sum(1 for a, r in self.rows.items() if a != self.root_id and r.get("state") in LIVE_STATES)
