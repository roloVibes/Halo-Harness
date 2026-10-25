"""tests.helpers.turn_session -- Halo 3.2.2.0 R4: a real `agent.loop.Session`
against the OpenAI-shaped mock upstream, for the turn marker, nudge and
plan-mode tests. Every call scopes its own BRIDGE_TEST_HOME and state dir.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path

from tests.helpers.mock_openai import _finish
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()


def text_step(text: str) -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": text}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]


def tool_step(name: str, arguments: dict, call_id: str = "call_1") -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"tool_calls": [
            {"index": 0, "id": call_id, "type": "function",
             "function": {"name": name, "arguments": json.dumps(arguments)}},
        ]}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
    ]


class Calls:
    """A scenario that answers the Nth request with the Nth step (the last
    step repeats), whatever the conversation holds."""

    def __init__(self, steps: list):
        self.steps = steps
        self.n = 0
        self._lock = threading.Lock()

    def __call__(self, handler, body) -> None:
        with self._lock:
            idx = min(self.n, len(self.steps) - 1)
            self.n += 1
        _finish(handler, self.steps[idx])


def new_session(*, mock, model: str, mode: str = "default", interactive: bool = False, max_turns: int = 10):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds

    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="r4-turn-home-")))
    cwd = Path(tempfile.mkdtemp(prefix="r4-turn-cwd-"))
    # (a plan file lands under BRIDGE_TEST_HOME's ~/.claude/plans)
    session_ctx = SessionContext(cwd=cwd, model_label=model, bare=True)
    session = Session(
        cwd=cwd, model_ref=parse_model_ref(model), model_profile=ModelProfile(),
        creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
        state_dir=Path(tempfile.mkdtemp(prefix="r4-turn-state-")), model_label=model,
        session_context=session_ctx, openrouter_base_url=mock.base_url, max_turns=max_turns,
        permission_engine=PermissionEngine(mode=mode, cwd=cwd), agents={}, routes={},
    )
    session.interactive = interactive
    return session


def request_text(request: dict) -> str:
    """Every message of one recorded upstream request, as one JSON string."""
    body = request.get("body") if isinstance(request, dict) else None
    return json.dumps((body or {}).get("messages") or [], ensure_ascii=False)


def markers(evs: list) -> list:
    return [e for e in evs if e.kind == "turn_marker"]


class ThreadedTurn:
    """`session.turn(prompt)` on a thread, events collected as they arrive."""

    def __init__(self, session, prompt: str):
        self.events: list = []
        self.done = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(session, prompt), daemon=True)
        self._thread.start()

    def _run(self, session, prompt):
        for ev in session.turn(prompt):
            self.events.append(ev)
        self.done.set()

    def wait_for(self, kind: str, timeout: float = 8.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for ev in list(self.events):
                if ev.kind == kind:
                    return ev
            time.sleep(0.02)
        raise AssertionError(f"timed out waiting for a {kind!r} event")

    def join(self, timeout: float = 8.0):
        self._thread.join(timeout)
        if not self.done.is_set():
            raise AssertionError("turn did not finish in time")
