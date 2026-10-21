"""halo_harness.agent.agent_observe -- how a session's own events move its
row in the agent tree (Halo 3.0.5.0 "Fleet" round R1; the tree itself is
agent/agent_registry.py).

    turn start      -> running, `current` "thinking", `task` (main: every turn;
                       a sub-agent: the first line of what it was asked)
    message_start   -> `current` "thinking"
    tool_use_ready  -> `current` "<Tool>: <one line of its arguments>"
    tool_result     -> the next tool still in flight, else "thinking"
    a card opens    -> waiting (permission_request, question, plan_review)
    text_delta      -> `last_text` (the last LAST_TEXT characters)
    message_end     -> `turns` + 1, `cost_usd` (the session's own running total),
                       `tokens_in` / `tokens_out` (its meter's totals, 3.1.8.0 R6)
    turn end        -> done | failed | stopped (from the turn's turn_done reason,
                       or stopped when Studio stopped it)

A followed agent's events also become `agent_event` entries
(agent/agent_transcript.py's `LiveText`).
"""

from __future__ import annotations

from halo_harness.agent.agent_transcript import LiveText, first_line, tool_label

LAST_TEXT = 200
END_STATE = {"end_turn": "done", "max_tokens": "done", "interrupted": "stopped", "error": "failed",
             "max_turns": "failed", "blocked": "failed"}
ASKS = ("permission_request", "question", "plan_review")


def _running(row: dict) -> None:
    if row.get("state") in ("queued", "waiting", "done", "failed"):
        row["state"] = "running"


class ObserveMixin:
    """Mixed into `AgentTree` (which provides lock, rows, _commit, _publish,
    _emit, _new_row, _ref and the per-agent scratch dicts)."""

    def started(self, aid: str, session, text: str) -> None:
        with self.lock:
            row = self.rows.get(aid) or self._new_row(aid, kind="subagent")
            before = dict(row)
            if aid == self.root_id or not row.get("task"):
                row["task"] = first_line(text)
            if row.get("state") != "paused":
                row["state"] = "running"
            model = getattr(getattr(session, "model_ref", None), "raw", None)
            row["current"], row["model"] = "thinking", model or row.get("model")
            self._reason.pop(aid, None)
            self._inflight.pop(aid, None)
            self._sessions[aid] = self._ref(session)
            pub = self._commit(aid, row, before, force=True)
        self._publish(pub)

    def observe(self, aid: str, ev) -> None:
        kind, data = getattr(ev, "kind", ""), getattr(ev, "data", None) or {}
        with self.lock:
            row = self.rows.get(aid)
            if row is None:
                return
            entries = self._live.setdefault(aid, LiveText()).feed(ev) if aid in self.followed else ()
            before = dict(row)
            if kind == "text_delta":
                row["last_text"] = (row.get("last_text", "") + str(data.get("text") or ""))[-LAST_TEXT:]
            elif kind == "message_start":
                row["current"] = "thinking"
                _running(row)
            elif kind == "tool_use_ready":
                label = tool_label(str(data.get("name") or "?"), data.get("input"))
                self._inflight.setdefault(aid, {})[data.get("id")] = label
                row["current"] = label
                _running(row)
            elif kind == "tool_result":
                inflight = self._inflight.get(aid) or {}
                inflight.pop(data.get("id"), None)
                row["current"] = next(reversed(list(inflight.values())), "thinking")
                _running(row)
            elif kind in ASKS and row.get("state") == "running":
                row["state"] = "waiting"
            elif kind == "message_end":
                row["turns"] = (row.get("turns") or 0) + 1
                if isinstance(data.get("cost_usd"), (int, float)):
                    row["cost_usd"] = round(float(data["cost_usd"]), 6)
                for src, field in (("total_input_tokens", "tokens_in"), ("total_output_tokens", "tokens_out")):
                    v = data.get(src)
                    if isinstance(v, int) and not isinstance(v, bool):
                        row[field] = v
            elif kind == "turn_done":
                self._reason[aid] = data.get("reason")
            pub = self._commit(aid, row, before)
        self._publish(pub)
        for entry in entries:
            self._emit("agent_event", aid, entry)

    def ended(self, aid: str) -> None:
        with self.lock:
            row = self.rows.get(aid)
            if row is None:
                return
            before = dict(row)
            stopped = self.controls.stop_record(aid) is not None
            row["state"] = "stopped" if stopped else END_STATE.get(self._reason.pop(aid, None), "done")
            row["current"] = ""
            self._inflight.pop(aid, None)
            live = self._live.get(aid)
            entries = live.flush() if live is not None else []
            pub = self._commit(aid, row, before, force=True)
        self._publish(pub)
        for entry in entries:
            self._emit("agent_event", aid, entry)
