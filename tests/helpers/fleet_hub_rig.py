"""tests.helpers.fleet_hub_rig -- Halo 3.0.5.0 "Fleet" R2: two Halo homes on
one machine. Home A runs the hub (bound to loopback, its state directory
passed explicitly) inside an in-process Studio server, so `GET /api/fleet`
and the live feed are the real routes; this process's own home is B
(BRIDGE_TEST_HOME), whose sessions (the remote tests' FakeSession behind the
real Controller, opened the way the TUI opens them) join A's hub with a pair
code. `cli(home_root, *args)` runs `halo fleet ...` in a child process with
a scrubbed environment. Every touched variable and module knob is restored.
"""
from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from tests.helpers.fleet_rig import wait_for  # noqa: F401  (re-exported for the suites)
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()
REPO = Path(__file__).resolve().parent.parent.parent
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "HALO_FLEET_PRIVATE",
         "HALO_FLEET_PARENT", "HALO_OFFLINE")
_SCRUB = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_")


class HubRig:
    def __init__(self, *, tls_on=None, record: bool = True) -> None:
        self._saved = {k: os.environ.get(k) for k in _VARS}
        for k in ("BRIDGE_STATE_DIR", "HALO_FLEET_PRIVATE", "HALO_FLEET_PARENT", "HALO_OFFLINE"):
            os.environ.pop(k, None)
        self.root_b = tempfile.mkdtemp(prefix="fleet-b-")
        self.root_a = tempfile.mkdtemp(prefix="fleet-a-")
        os.environ["BRIDGE_TEST_HOME"] = self.root_b
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        self.home_a = Path(self.root_a) / ".halo"
        self.home_a.mkdir(parents=True)
        (self.home_a / "config.json").write_text(json.dumps({"fleet": {"name": "alice@hub"}}), encoding="utf-8")
        from halo_harness.fleet import relay_hub, relay_runtime
        self._knobs = (relay_hub.ANNOUNCE_S,)
        relay_hub.ANNOUNCE_S = 0.5
        # a session an earlier module leaked keeps the 5 s watcher alive, and that watcher re-creates
        # relays for hubs that are gone: start from nothing
        relay_runtime.stop_all()
        with relay_runtime._lock:
            relay_runtime._sessions[:] = []
        self.set_b(**{"fleet.name": "bob@member"})
        from halo_harness.studio.events import EventBridge
        from halo_harness.studio.fleet_hub_api import start_hub
        from halo_harness.studio.server import start_server
        self.server = start_server(port=0, cwd=Path(self.root_a), state_dir=self.home_a)
        threading.Thread(target=self.server.serve_forever, daemon=True, name="rig-studio").start()
        self.server.events = EventBridge(list_live=lambda: [])  # A's own registry: nothing (B's sessions are B's)
        self.feed = self.server.events.subscribe("all")
        from halo_harness.fleet.local_view import harness_entry
        self.hub = start_hub(self.server, home=self.home_a, port=0, bind="127.0.0.1", name="hub-a", tls_on=tls_on,
                             local_view=lambda: harness_entry([], self.home_a))
        if not record:
            self.hub.record = False
        self.controllers: list = []
        self.frames: list = []

    # ---- config, identity ---------------------------------------------------
    def set_b(self, **values) -> None:
        from halo_harness.fleet import identity
        from halo_harness.theme import set_config_value
        for k, v in values.items():
            set_config_value(k, v)
        identity.forget_cache()

    @property
    def b_id(self) -> str:
        from halo_harness.fleet.identity import harness
        return harness()["id"]

    @property
    def a_id(self) -> str:
        return self.hub.state.identity["id"]

    def url(self) -> str:
        return self.hub.url("127.0.0.1")

    def join(self, **kw) -> dict:
        from halo_harness.fleet import identity, relay, store
        got = relay.join(self.url(), self.hub.pairing.new_code(600)[0], identity.harness(), **kw)
        key = got.pop("key")
        return store.add_hub(got, key)

    def session(self, session_id: str = "fakesession0000000000000000000001"):
        from halo_harness.controller import Controller
        from halo_harness.remote import runtime
        from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
        c = Controller(session=FakeSession(session_id), cwd=Path(self.root_b), registry=FakeRegistry()).start()
        self.controllers.append(c)
        return c, runtime.start_for_controller(c)

    def relay(self):
        """B's relay to THIS rig's hub (never a stale relay another test's leaked session kept alive)."""
        from halo_harness.fleet import relay_runtime
        rs = relay_runtime.relays()
        mine = [r for r in rs if r.entry.get("hub_id") == self.a_id]
        return mine[0] if mine else (rs[0] if rs else None)

    def poke(self) -> None:
        from halo_harness.fleet import relay_runtime
        relay_runtime.poke()

    # ---- the hub's side -----------------------------------------------------
    def member(self):
        return next((h for h in self.hub.state.view()["harnesses"] if h.get("id") == self.b_id), None)

    def member_session(self, sid: str):
        m = self.member() or {}
        return next((s for s in m.get("sessions") or [] if s.get("session_id") == sid), None)

    def member_session_online(self, sid: str):
        """The session row once the member is online too: a session is announced a beat before its stream attaches
        (and a re-attaching relay reads offline for one tick), so `online` is what `members`/commands look at."""
        return self.member_session(sid) if (self.member() or {}).get("online") else None

    def drain(self) -> list:
        while True:
            f = self.feed.get(0.05)
            if f is None:
                return self.frames
            self.frames.append(f)

    def seen(self, kind: str, **match) -> list:
        self.drain()
        return [f for f in self.frames if f.get("event") == kind and all(f.get(k) == v for k, v in match.items())]

    def api(self, method: str, path: str, body=None, timeout: float = 30.0):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=timeout)
        try:
            conn.request(method, "/api/" + path, body=json.dumps(body).encode("utf-8") if body is not None else None,
                         headers={"Authorization": "Bearer " + self.server.token, "Content-Type": "application/json"})
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
        finally:
            conn.close()

    def card(self, controller, timeout: float = 10.0):
        """The fleet card's request id once it is open in B's session."""
        return wait_for(lambda: next((k for k in list(controller.session._question_waiters)
                                      if k.startswith("fleet-ask:")), None), timeout)

    # ---- teardown -----------------------------------------------------------
    def close(self) -> None:
        from halo_harness.fleet import identity, relay_hub, relay_runtime
        from halo_harness.remote import runtime
        runtime.stop()
        relay_runtime.stop_all()
        for c in self.controllers:
            try:
                c.quit()
            except Exception:
                pass
        for fn in (self.hub.stop, self.server.shutdown, self.server.server_close):
            try:
                fn()
            except Exception:
                pass
        runtime._private_flag = None
        runtime._reopeners[:] = []
        (relay_hub.ANNOUNCE_S,) = self._knobs
        identity.forget_cache()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def __enter__(self) -> "HubRig":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False


def cli(home_root: str, *args: str, timeout: float = 60.0) -> "tuple[int, str, str]":
    """`halo fleet <args>` in a child process whose home is `home_root`."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(_SCRUB)}
    env.update(BRIDGE_TEST_HOME=home_root, BRIDGE_TEST_NO_BACKGROUND_NET="1", PYTHONPATH=str(REPO))
    r = subprocess.run([sys.executable, "-m", "halo_harness", "fleet", *args], capture_output=True, encoding="utf-8",
                       errors="replace", env=env, cwd=str(REPO), timeout=timeout, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout, r.stderr
