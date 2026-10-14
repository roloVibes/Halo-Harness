"""tests.helpers.fleet_rig -- Halo 3.0.5.0 "Fleet" R1: a REAL agent.loop.Session
behind the real Controller, its control socket opened the way the TUI opens it
(`runtime.start_for_controller`), over the mock OpenAI-chat upstream with
scripted models whose steps can be gated on a threading.Event (so a test
decides when a sub-agent's model call answers). The home is a fresh
BRIDGE_TEST_HOME; every touched variable and runtime flag is restored."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path

from tests.helpers.mock_openai import SCENARIOS, MockUpstream, ScriptedTurns, _finish
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "HALO_FLEET_PRIVATE",
         "HALO_FLEET_PARENT")


def text_step(text: str) -> list:
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"content": text}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}]


def tool_step(*calls) -> list:
    """`calls` = (name, arguments, call_id) tuples: one assistant message."""
    tcs = [{"index": i, "id": cid, "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
           for i, (n, a, cid) in enumerate(calls)]
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": tcs}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]}]


def gated(gate: threading.Event, chunks: list, seen: "list | None" = None):
    """A step that records the request body, then answers once `gate` is set."""
    def step(handler, body):
        if seen is not None:
            seen.append(body)
        gate.wait(30)
        _finish(handler, chunks)
    return step


def recorded(chunks: list, seen: list):
    def step(handler, body):
        seen.append(body)
        _finish(handler, chunks)
    return step


def agent_call(name: str, prompt: str, model: str) -> tuple:
    return ("Agent", {"description": prompt.split(":")[0], "prompt": prompt, "subagent_type": "general-purpose",
                      "model": model}, f"call_{name}")


def wait_for(fn, timeout: float = 15.0, step: float = 0.05):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            got = fn()
        except Exception:
            got = None
        if got:
            return got
        time.sleep(step)
    return None


class FrameReader:
    """A subscribed client drained on its own thread (never a dropped feed)."""

    def __init__(self, client) -> None:
        self.client, self.frames, self._stop = client, [], threading.Event()
        client.call("subscribe")
        self.frames.extend(client.events)
        client.events.clear()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                ev = self.client.next_event(0.2)
            except Exception:
                return
            if ev is not None:
                self.frames.append(ev)

    def of(self, kind: str, agent_id=None) -> list:
        return [f for f in list(self.frames) if f.get("event") == kind and (agent_id is None or f.get("agent_id") == agent_id)]

    def close(self) -> None:
        self._stop.set()
        self._t.join(2)


class FleetRig:
    def __init__(self) -> None:
        self._saved = {k: os.environ.get(k) for k in _VARS}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        for k in ("HALO_FLEET_PRIVATE", "HALO_FLEET_PARENT"):
            os.environ.pop(k, None)
        os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="fleet-home-")
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        from halo_harness.theme import set_config_value
        set_config_value("agents.max_depth", 2)
        set_config_value("remote.enabled", False)  # the Signal bridge's switch: never the socket's
        self.cwd = Path(tempfile.mkdtemp(prefix="fleet-cwd-"))
        (self.cwd / "notes.md").write_text("hello\n", encoding="utf-8")
        self.mock = MockUpstream().start()
        self.controllers: list = []
        self.clients: list = []
        self.readers: list = []
        self.scenarios: list = []

    def script(self, name: str, steps: list) -> str:
        SCENARIOS[name] = ScriptedTurns(steps)
        self.scenarios.append(name)
        return f"or:mock/{name}"

    def session(self, model: str):
        from halo_harness.agent.assemble import SessionContext
        from halo_harness.agent.loop import Session
        from halo_harness.config.agents_md import AgentSpec
        from halo_harness.model import ModelProfile, parse_model_ref
        from halo_harness.permissions import PermissionEngine
        from halo_harness.providers.stream import ProviderCreds
        spec = AgentSpec(name="general-purpose", description="general purpose sub-agent", tools=None,
                         disallowed_tools=[], body="You are a helpful sub-agent.")
        return Session(cwd=self.cwd, model_ref=parse_model_ref(model), model_profile=ModelProfile(),
                       creds=ProviderCreds(base_url=self.mock.base_url, api_key="k"),
                       state_dir=Path(tempfile.mkdtemp(prefix="fleet-state-")), model_label=model,
                       session_context=SessionContext(cwd=self.cwd, model_label=model, bare=True),
                       openrouter_base_url=self.mock.base_url, max_turns=10,
                       permission_engine=PermissionEngine(mode="auto", cwd=self.cwd),
                       agents={"general-purpose": spec}, routes={})

    def controller(self, session):
        from halo_harness.controller import Controller
        from tests.helpers.fake_remote_session import FakeRegistry
        c = Controller(session=session, cwd=self.cwd, registry=FakeRegistry()).start()
        self.controllers.append(c)
        return c

    def client(self, act):
        from halo_harness.remote.client import ControlClient
        c = ControlClient(act.endpoint, act.server.token, timeout=10.0)
        self.clients.append(c)
        return c

    def reader(self, act) -> FrameReader:
        r = FrameReader(self.client(act))
        self.readers.append(r)
        return r

    def close(self) -> None:
        from halo_harness.remote import runtime
        for r in self.readers:
            r.close()
        for c in self.clients:
            c.close()
        for c in self.controllers:
            try:
                c.quit()
            except Exception:
                pass
        runtime.stop()
        runtime._private_flag = None
        runtime._reopeners[:] = []
        self.mock.stop()
        for name in self.scenarios:
            SCENARIOS.pop(name, None)
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def __enter__(self) -> "FleetRig":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False
