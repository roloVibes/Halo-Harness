"""tests.helpers.glance_rig -- what the glance's Chrome driver (tests/helpers/studio_glance.py) and its route tests
(tests/test_studio_glance.py) look at (Halo 3.4.1.0 R4). In the caller's scratch home, with every pack off:

* an in-process Studio (the real routes, the real guard and the real feed) on loopback;
* one live session of this harness: the remote tests' scripted fake (tests/helpers/fake_remote_session.py) behind the
  real Controller and its control socket (`runtime.start_for_controller`). A turn whose text says "ask" parks on
  permission card `perm_1`, "ask-question" on question `q_1`; here a card waits up to `WAIT_S` for its answer (the
  fake's own 10 s is too short for a page on a loaded runner).

`ask(text)` starts such a turn; `decision(id)` is what the card was answered; `restart()` stops Studio and serves it
again on the same port with the same token and owner salt (the glance reconnects by itself); `close()` quits the
session, stops Studio and puts back every variable it set. No model is called.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from pathlib import Path

from tests.helpers.fake_remote_session import FakeSession

_VARS = ("BRIDGE_STATE_DIR", "HALO_FLEET_PRIVATE", "HALO_FLEET_PARENT")
WAIT_S = 180.0


class PatientSession(FakeSession):
    """The fake session, its cards waiting up to WAIT_S for an answer."""

    def _wait(self, table, key, emit, event, timeout=10.0):
        return super()._wait(table, key, emit, event, timeout=WAIT_S)


class GlanceRig:
    def __init__(self) -> None:
        self._saved = {k: os.environ.get(k) for k in _VARS}
        for k in _VARS:
            os.environ.pop(k, None)
        from halo_harness.peers import identity
        from halo_harness.providers.config import default_state_dir
        from halo_harness.theme import set_config_value
        self.state = Path(default_state_dir())
        self.state.mkdir(parents=True, exist_ok=True)
        set_config_value("remote.enabled", False)  # the transports' switch, never the socket's
        set_config_value("fleet.name", "you@studio")
        identity.forget_cache()
        self.cwd = Path(tempfile.mkdtemp(prefix="glance-cwd-"))
        self.closers: list = []
        self._serve()
        from halo_harness.controller import Controller
        from halo_harness.remote import runtime
        from tests.helpers.fake_remote_session import FakeRegistry
        self.session = PatientSession()
        self.session.cwd = self.cwd
        self.controller = Controller(session=self.session, cwd=self.cwd, registry=FakeRegistry()).start()
        self.act = runtime.start_for_controller(self.controller)
        if self.act is None:
            raise RuntimeError("the fake session's control socket did not open")
        self.sid = self.act.session_id
        self.closers.append(self._quit)

    def _serve(self, port: int = 0, token: "str | None" = None, salt: str = "") -> None:
        from halo_harness.studio.server import start_server
        self.server = start_server(port=port, cwd=self.cwd, state_dir=self.state, token=token)
        if salt:
            self.server.owner_salt = salt  # the open page keeps its proof across the restart
        threading.Thread(target=self.server.serve_forever, daemon=True, name="glance-studio").start()

    def stop_studio(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def restart(self) -> None:
        """Serve Studio again on the same port, with the same token and salt (call stop_studio first)."""
        port, token, salt = self.server.server_address[1], self.server.token, self.server.owner_salt
        for _ in range(50):
            try:
                self._serve(port, token, salt)
                return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError(f"port {port} did not come back")

    def _quit(self) -> None:
        from halo_harness.remote import runtime
        try:
            self.controller.quit()
        finally:
            runtime.stop()

    def url(self, query: str = "mode=glance") -> str:
        from halo_harness.studio.server import url_for
        return url_for(self.server).replace("/#t=", f"/?{query}&tour=off#t=")

    def ask(self, text: str = "ask") -> None:
        self.controller.submit(text)

    def frame(self, event: str, data: dict, n: int = 0) -> None:
        """One frame of the session's main agent on Studio's feed, as the session's own tap sends it."""
        from halo_harness.peers.identity import harness
        self.server.events.publish({"session_id": self.sid, "harness": harness()["id"], "event": event, "agent_id": "main",
                                    "turn": 1, "data": data, "ts": time.time() + n * 0.001})

    def decision(self, rid: str = "perm_1"):
        return self.session.permission_decisions.get(rid) if rid.startswith("perm") else self.session.answers.get(rid)

    def close(self) -> None:
        for fn in reversed(self.closers):
            try:
                fn()
            except Exception:
                pass
        try:
            self.stop_studio()
        except Exception:
            pass
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def __enter__(self) -> "GlanceRig":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False
