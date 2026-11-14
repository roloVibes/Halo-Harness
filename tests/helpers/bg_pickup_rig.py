"""tests.helpers.bg_pickup_rig -- Halo 3.4.1.3: a real `agent.loop.Session` driven by its worker pump
(`Session.run`, as the TUI's controller and Studio's session without a terminal drive it) against the
OpenAI-shaped mock upstream, for the "background work finished while idle" tests (tests/test_bg_pickup.py).
No model is called: every reply is scripted. Waits poll for what they assert, with a deadline.
"""
from __future__ import annotations

import queue
import threading
import time
from types import SimpleNamespace

import os
import tempfile
from pathlib import Path

from tests.helpers.mock_openai import MockUpstream, SCENARIOS, _finish
from tests.helpers.turn_session import Calls, request_text, text_step

FRAME_NEEDLE = "they have sent nothing since your last reply"  # agent/bg_pickup.py FRAME_HEAD
NOT_HUMAN = "NOT a message from the human"


def new_session(*, mock, model: str, agents=None):
    """turn_session.new_session's Session, with sub-agent definitions (a home and a state dir of its own)."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds

    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="bgp-home-")))
    cwd = Path(tempfile.mkdtemp(prefix="bgp-cwd-"))
    return Session(
        cwd=cwd, model_ref=parse_model_ref(model), model_profile=ModelProfile(),
        creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
        state_dir=Path(tempfile.mkdtemp(prefix="bgp-state-")), model_label=model,
        session_context=SessionContext(cwd=cwd, model_label=model, bare=True), openrouter_base_url=mock.base_url,
        max_turns=10, permission_engine=PermissionEngine(mode="auto", cwd=cwd), agents=agents or {}, routes={})


def general_purpose():
    from halo_harness.config.agents_md import AgentSpec
    return {"general-purpose": AgentSpec(name="general-purpose", description="general purpose sub-agent", tools=None,
                                         disallowed_tools=["Agent", "Task"], body="You are a helpful sub-agent.")}


class Gated:
    """A scenario whose every reply waits on `gate` (a background child that finishes when the test says)."""

    def __init__(self, text: str) -> None:
        self.gate = threading.Event()
        self.text = text

    def __call__(self, handler, body) -> None:
        self.gate.wait(20.0)
        _finish(handler, text_step(self.text))


class Rig:
    def __init__(self, name: str, replies: list, *, when_done: str = "continue", self_turns=None,
                 window_s: float = 0.4, agents=None, first=None) -> None:
        from halo_harness import theme
        from halo_harness.agent import bg_pickup
        self.mock = MockUpstream().start()
        self.name = name
        SCENARIOS[name] = first if first is not None else Calls([text_step(r) for r in replies])
        self.session = new_session(mock=self.mock, model=f"or:mock/{name}", agents=agents)
        theme.set_config_value("background.when_done", when_done)
        if self_turns is not None:
            theme.set_config_value("background.self_turns", self_turns)
        self._window = bg_pickup.WINDOW_S
        bg_pickup.WINDOW_S = window_s
        self.commands: "queue.Queue" = queue.Queue()
        self.events: list = []
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self.session.run, args=(self.commands, self._out), daemon=True)
        self._thread.start()
        self.wait(lambda: getattr(self.session, "_bg_pickup", None) is not None, "the pump attached")

    def _out(self, ev) -> None:
        with self._lock:
            self.events.append(ev)

    def evs(self, kind: str = None) -> list:
        with self._lock:
            return [e for e in self.events if kind is None or e.kind == kind]

    def markers(self, *, started=None) -> list:
        got = [e for e in self.evs("turn_marker") if e.data.get("state") == "background"]
        return got if started is None else [e for e in got if bool(e.data.get("started")) == started]

    def wait(self, pred, what: str, timeout: float = 15.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            got = pred()
            if got:
                return got
            time.sleep(0.02)
        raise AssertionError(f"waited {timeout}s for: {what}")

    def turns_done(self, n: int) -> None:
        self.wait(lambda: len([e for e in self.evs("turn_done") if e.agent_id is None]) >= n
                  and not self.session.busy, f"{n} main turn(s) done")

    def pumped(self, n: int) -> None:
        self.wait(lambda: self.session._bg_pickup.pumps >= n, f"{n} pickup command(s) handled")

    def submit(self, text: str) -> None:
        from halo_harness import events
        self.commands.put(events.Command("user_input", {"text": text}))

    def finish_job(self, job_id: str, label: str, output: str = "ok") -> None:
        """The real producer: the job registry's own completion path, for a job that finished."""
        rec = SimpleNamespace(lock=threading.Lock(), status="completed", exit_code=0, job_id=job_id, description=label,
                              command=label, collector=SimpleNamespace(result=lambda: output, spill_path=None))
        self.session.job_registry._push_notice(rec)

    def requests(self) -> list:
        """The main session's model calls (a child's go to its own scenario)."""
        return [r for r in self.mock.requests if r.get("method") == "POST"
                and str((r.get("body") or {}).get("model") or "").endswith(self.name)]

    def request_texts(self) -> list:
        return [request_text(r) for r in self.requests()]

    def user_nodes(self) -> list:
        return [n for n in self.session.log.nodes() if n.get("type") == "user" and n.get("kind") is None]

    def close(self) -> None:
        from halo_harness.agent import bg_pickup
        bg_pickup.WINDOW_S = self._window
        self.commands.put(None)
        self._thread.join(10.0)
        self.mock.stop()
