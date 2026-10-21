"""tests.helpers.studio_live_rig -- scripted activity over
tests/helpers/studio_fleet_rig.py for the Session Live column, the map's
tree and the Roles glow (Halo 3.1.5.0 R3): the drivers
(studio_session_live.py, studio_session_cost_map.py, studio_roles_glow.py)
and tools/capture_session_anim.py.

* `Live(rig)` adds extra agents to this harness's session as GET fleet
  lists it (fleet/local_view.session_row is wrapped for the rig's session,
  so a reload keeps them) and pushes the feed frames a real session sends
  (text_chunk, tool_use_start, tool_result, agent_state, the asks) through
  Studio's own event bridge, so the page sees exactly what a live session
  shows. `close()` restores session_row.
No model is called.
"""
from __future__ import annotations

import time

EXTRA = (
    ("t7e5s1t0", "tester", "tester", "or:mock/qwen3-coder", "Test: run the basket suite"),
    ("d0c5w1r1", "docs", "doc-writer", "or:mock/glm-5-coder", "Docs: note the discount order in CHANGES.md"),
    ("r3v1e2w0", "reviewer", "reviewer", "or:mock/kimi-k3-research", "Review: the basket diff"),
)


class Live:
    def __init__(self, rig, extra=EXTRA, parent: str = "main") -> None:
        from halo_harness.fleet import local_view
        from halo_harness.fleet.identity import harness
        self.rig, self.hid, self.sid = rig, harness()["id"], rig.act.session_id
        self.rows: dict = {}
        self.fields: dict = {}  # session row fields over the session's own (context_tokens, cost_usd, ...)
        for aid, name, role, model, task in extra:
            self.rows[aid] = {"agent_id": aid, "parent": parent, "name": name, "role": role, "bio": role, "lineup": "halo-dev-cycle", "model": model,
                              "kind": "subagent", "task": task, "since": time.time(), "state": "running", "turns": 1, "cost_usd": 0.0,
                              "current": "thinking", "last_text": "", "transcript": None}
        self._lv = local_view
        self._orig = local_view.session_row
        sid, rows, fields = self.sid, self.rows, self.fields

        def session_row(entry, status, agents):
            row = self._orig(entry, status, agents)
            if entry.get("session_id") == sid:
                row["agents"] = list(row.get("agents") or []) + [dict(r) for r in rows.values()]
                row.update(fields)
            return row
        local_view.session_row = session_row
        local_view.forget()
        rig.closers.append(self.close)

    def close(self) -> None:
        self._lv.session_row = self._orig
        self._lv.forget()

    def refresh(self, **fields) -> None:
        """Set session row fields and make the page read GET fleet again (a `sessions` frame). The cache drops go
        through local_view.forget() (3.1.8.0 R6): a snapshot read while the fields moved is never cached."""
        self.fields.update(fields)
        self._lv.forget()
        self.rig.server.events.publish({"session_id": None, "event": "sessions", "agent_id": None, "turn": None, "data": {}, "ts": time.time()})

    def aid(self, name: str) -> str:
        """An agent id by name: an extra one, else the rig's real implementer / researcher / main."""
        for aid, r in self.rows.items():
            if r["name"] == name:
                return aid
        if name == "main":
            return "main"
        return self.rig.agent({"implementer": "Implement", "researcher": "Research"}.get(name, name)).get("agent_id") or name

    def key(self, name: str) -> str:
        return f"{self.hid}|{self.sid}|{self.aid(name)}"

    def frame(self, name: str, event: str, data: dict, ts: "float | None" = None) -> None:
        self.rig.server.events.publish({"session_id": self.sid, "harness": self.hid, "event": event, "agent_id": self.aid(name),
                                        "turn": 1, "data": data, "ts": ts or time.time()})

    def say(self, name: str, text: str) -> None:
        self.frame(name, "text_chunk", {"text": text})

    def tool(self, name: str, tool: str, call_id: str, current: str = "") -> None:
        if current:
            self.state(name, current=f"{tool}: {current}")
        self.frame(name, "tool_use_start", {"id": call_id, "name": tool})

    def result(self, name: str, call_id: str, text: str, is_error: bool = False, tool: str = "Bash") -> None:
        self.frame(name, "tool_result", {"id": call_id, "name": tool, "content": text, "is_error": is_error})

    def ask(self, name: str, event: str = "permission_request", data: "dict | None" = None) -> None:
        self.frame(name, event, data or {"id": "perm-1", "name": "Bash", "input": {"command": "git push origin feature/basket"}})

    def state(self, name: str, **fields) -> None:
        """Change an extra agent's row (kept for the next GET) and send its `agent_state` frame; a real one gets the frame only."""
        aid = self.aid(name)
        row = self.rows.get(aid)
        if row is None:
            row = {**self.rig.agent({"implementer": "Implement", "researcher": "Research"}.get(name, name)), "agent_id": aid}
        row.update(fields)
        self._lv.forget()
        self.frame(name, "agent_state", dict(row))

    def spawn(self, aid: str, name: str, role: str, model: str, task: str, parent: str = "main") -> None:
        """A new extra agent appears under `parent` (its spawn edge lights, its line lands in Live)."""
        self.rows[aid] = {"agent_id": aid, "parent": self.aid(parent), "name": name, "role": role, "bio": role, "lineup": "halo-dev-cycle",
                          "model": model, "kind": "subagent", "task": task, "since": time.time(), "state": "running", "turns": 0,
                          "cost_usd": 0.0, "current": "thinking", "last_text": "", "transcript": None}
        self.state(name)
