"""tests.helpers.remote_rig -- shared fixture for the remote-control tests:
a scoped state dir (`BRIDGE_TEST_HOME`, never `BRIDGE_STATE_DIR`), a real
`Controller` over `FakeSession`, its `ControllerHandle` and a live
`ControlServer`, plus a connected `ControlClient`."""
from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from tests.helpers.fake_remote_session import FakeRegistry, FakeSession

_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET")


class Rig:
    def __init__(self, *, serve: bool = True, start_controller: bool = True, sndbuf=None, session_id=None):
        self._saved = {k: os.environ.get(k) for k in _VARS}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="remote-home-")
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        self.cwd = Path(tempfile.mkdtemp(prefix="remote-cwd-"))
        self.session = FakeSession(session_id) if session_id else FakeSession()
        self.models: list = []
        from halo_harness.controller import Controller
        self.controller = Controller(session=self.session, cwd=self.cwd, registry=FakeRegistry(),
                                     model_resolver=self._resolve)
        if start_controller:
            self.controller.start()
        from halo_harness.remote.handle import ControllerHandle
        self.handle = ControllerHandle(self.controller)
        self.server = None
        self.clients: list = []
        if serve:
            self.handle.attach()
            from halo_harness.remote.control_socket import ControlServer
            self.server = ControlServer(self.handle, sndbuf=sndbuf).start()

    def _resolve(self, raw):
        if raw.startswith("bad"):
            raise ValueError(f"no such model {raw!r}")
        self.models.append(raw)
        return SimpleNamespace(provider="mock", model=raw, raw=raw), None, object()

    def client(self, *, token="auto"):
        from halo_harness.remote.client import ControlClient
        tok = self.server.token if token == "auto" else token
        c = ControlClient(self.server.endpoint, tok)
        self.clients.append(c)
        return c

    def wait_idle(self, timeout: float = 5.0) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.session.turn_count and not self.session.busy:
                return True
            time.sleep(0.02)
        return False

    def close(self) -> None:
        for c in self.clients:
            c.close()
        if self.server is not None:
            self.server.close()
        try:
            self.handle.detach()
        except Exception:
            pass
        try:
            self.controller.quit()
        except Exception:
            pass
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
