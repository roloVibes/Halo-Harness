"""tests.helpers.fake_remote_session -- a scripted stand-in for
`agent.loop.Session` (plus a tiny slash registry) for the remote-control
tests: the real `Controller` and the real control socket drive it, so the
tee, the answers and the status payload are exercised for real.

Script: a `user_input` Command whose text contains "ask" makes the session
emit a `permission_request` (id `perm_1`, suggested_rule `Bash(echo:*)`) and
park on its waiter until `resolve_permission` answers; every turn streams a
few `text_delta`s and ends with `message_end` + `turn_done`.
"""
from __future__ import annotations

import threading
from types import SimpleNamespace

from halo_harness import events


class FakeLog:
    def __init__(self, session_id: str = "fakesession0000000000000000000001") -> None:
        self.session_id = session_id
        self._nodes: list = []
        self._lock = threading.Lock()

    def nodes(self) -> list:
        with self._lock:
            return list(self._nodes)

    def add(self, role: str, text: str) -> None:
        with self._lock:
            self._nodes.append({"type": role, "content": [{"type": "text", "text": text}]})

    def append_meta(self, **fields) -> None:
        with self._lock:
            self._nodes.append({"type": "meta", **fields})


class FakeEngine:
    def __init__(self) -> None:
        self.mode = "default"
        self.session_rules: list = []

    def add_session_allow_rule(self, rule: str, **kw) -> bool:
        self.session_rules.append(rule)
        return True


class FakeSession:
    def __init__(self, session_id: str = "fakesession0000000000000000000001") -> None:
        self.log = FakeLog(session_id)
        self.permission_engine = FakeEngine()
        self.abort = threading.Event()
        self._stopping = threading.Event()
        self._busy = threading.Event()
        self.interactive = False
        self.turn_count = 0
        self.effort = "medium"
        self.steered: list = []
        self.permission_decisions: dict = {}
        self.answers: dict = {}
        self._permission_waiters: dict = {}
        self._question_waiters: dict = {}
        self._plan_waiters: dict = {}
        self._approval_waiters: dict = {}
        self.job_registry = SimpleNamespace(kill_all=lambda: None)
        self.model_ref = SimpleNamespace(raw="mock/fake", provider="mock")

    @property
    def busy(self) -> bool:
        return self._busy.is_set()

    def steer(self, text: str) -> bool:
        if not self._busy.is_set():
            return False
        self.steered.append(text)
        return True

    def status_event(self, **kw):
        return events.status(phase="idle", model="mock/fake", turn=self.turn_count,
                             permission_mode=self.permission_engine.mode, session_id=self.log.session_id,
                             effort=self.effort)

    def _fire_session_end(self, reason: str) -> None:
        pass

    def close_cc(self) -> None:
        pass

    # ---- waiters ----------------------------------------------------------
    def _resolve(self, table: dict, key, field: str, value) -> bool:
        slot = table.get(key)
        if slot is None:
            return False
        slot[field] = value
        slot["event"].set()
        return True

    def resolve_permission(self, request_id, decision) -> bool:
        return self._resolve(self._permission_waiters, request_id, "decision", decision)

    def resolve_question(self, request_id, answer) -> bool:
        return self._resolve(self._question_waiters, request_id, "answer", answer)

    def resolve_approval(self, request_id, decision) -> bool:
        return self._resolve(self._approval_waiters, request_id, "decision", decision)

    def resolve_plan(self, decision) -> bool:
        return self._resolve(self._plan_waiters, "plan_1", "decision", decision)

    def _wait(self, table: dict, key: str, emit, event: "events.Event", timeout: float = 10.0):
        slot = {"event": threading.Event()}
        table[key] = slot
        emit(event)
        slot["event"].wait(timeout)
        table.pop(key, None)
        return slot

    # ---- the worker loop ------------------------------------------------------
    def run(self, commands, emit, mcp_status_fn=None) -> int:
        emit(self.status_event())
        while True:
            cmd = commands.get()
            if cmd is None:
                return 0
            if cmd.kind != "user_input":
                continue
            text = cmd.data.get("text", "")
            self.turn_count += 1
            n = self.turn_count
            self._busy.set()
            try:
                self.log.add("user", text)
                emit(events.user_message(text, turn=n))
                emit(events.message_start(turn=n, model="mock/fake"))
                if "ask-question" in text:
                    self.answers["q_1"] = self._wait(self._question_waiters, "q_1", emit, events.Event(
                        "question", {"id": "q_1", "name": "AskUserQuestion", "input": {"question": "which?"}}, turn=n))
                elif "ask-plan" in text:
                    self.answers["plan_1"] = self._wait(self._plan_waiters, "plan_1", emit, events.Event(
                        "plan_review", {"id": "plan_1", "plan": "do the thing", "path": ""}, turn=n))
                elif "ask-approval" in text:
                    self.answers["appr_1"] = self._wait(self._approval_waiters, "appr_1", emit, events.Event(
                        "approval_request", {"id": "appr_1", "position": "reviewer", "text": "ok?", "is_error": False},
                        turn=n))
                elif "ask" in text:
                    slot = self._wait(self._permission_waiters, "perm_1", emit, events.Event(
                        "permission_request", {"id": "perm_1", "name": "Bash", "input": {"command": "echo hi"},
                                               "reason": "needs approval", "suggested_rule": "Bash(echo:*)"}, turn=n))
                    self.permission_decisions["perm_1"] = slot.get("decision")
                for word in ("hello ", "from ", "the ", "fake ", "session"):
                    emit(events.text_delta(word, turn=n))
                self.log.add("assistant", f"reply to: {text}")
                emit(events.message_end(turn=n, stop_reason="end_turn"))
                emit(events.turn_done(turn=n, reason="end_turn"))
            finally:
                self._busy.clear()


class FakeRegistry:
    """`resolve(name)` -> a core command echoing its args."""

    def resolve(self, name: str):
        if name == "boom":
            return None
        return SimpleNamespace(kind="core", source="builtin", name=name,
                               run=lambda args, facade, _n=name: f"ran /{_n} {args}".strip())
