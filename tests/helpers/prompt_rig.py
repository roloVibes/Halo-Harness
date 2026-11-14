"""tests.helpers.prompt_rig -- Halo 3.3.11.0 R1: what the Prompt panel's Chrome driver
(tests/helpers/studio_prompt.py) looks at. In the driver's scratch home:

* an in-process Studio (the real routes and feed) on loopback;
* one live session of this harness: the remote tests' scripted fake (tests/helpers/fake_remote_session.py:
  a turn streams "hello from the fake session"; a turn whose text says "ask" parks on permission card
  `perm_1` until it is answered; its Command meta moves the receipts as the real loop's seam does) behind the
  real Controller, its control socket opened the way the TUI opens it (`runtime.start_for_controller`); its
  slash commands answer "ran /<name> <args>" (FakeRegistry).

`close()` quits the session, stops Studio and restores every variable it set. No model is called.
"""
from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

_VARS = ("BRIDGE_STATE_DIR", "HALO_PRIVATE", "HALO_SESSION_PARENT")


class PromptRig:
    def __init__(self) -> None:
        self._saved = {k: os.environ.get(k) for k in _VARS}
        for k in _VARS:
            os.environ.pop(k, None)
        from halo_harness.peers import identity
        from halo_harness.providers.config import default_state_dir
        from halo_harness.theme import set_config_value
        self.state = Path(default_state_dir())
        self.state.mkdir(parents=True, exist_ok=True)
        set_config_value("remote.enabled", False)  # the Signal bridge's switch, never the socket's
        set_config_value("harness.name", "you@studio")
        identity.forget_cache()
        self.cwd = Path(tempfile.mkdtemp(prefix="prompt-cwd-"))
        self.closers: list = []
        from halo_harness.studio.server import start_server
        self.server = start_server(port=0, cwd=self.cwd, state_dir=self.state)
        threading.Thread(target=self.server.serve_forever, daemon=True, name="prompt-studio").start()
        self.closers += [self.server.server_close, self.server.shutdown]
        from halo_harness.controller import Controller
        from halo_harness.remote import runtime
        from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
        self.session = FakeSession()
        self.session.cwd = self.cwd
        self.controller = Controller(session=self.session, cwd=self.cwd, registry=FakeRegistry()).start()
        self.act = runtime.start_for_controller(self.controller)
        if self.act is None:
            raise RuntimeError("the fake session's control socket did not open")
        self.sid = self.act.session_id
        self.closers.append(self._quit)

    def _quit(self) -> None:
        from halo_harness.remote import runtime
        try:
            self.controller.quit()
        finally:
            runtime.stop()

    def url(self, extra: str = "") -> str:
        from halo_harness.studio.server import url_for
        return url_for(self.server, "session").replace("#t=", f"&tour=off{extra}#t=")

    def users(self) -> list:
        """The user turns the session ran, in order."""
        return [n["content"][0]["text"] for n in self.session.log.nodes() if n["type"] == "user"]

    def receipts(self) -> list:
        from halo_harness.remote.receipts import Receipts, session_folder
        return Receipts(session_folder(self.sid, self.cwd)).read_all()

    def close(self) -> None:
        for fn in reversed(self.closers):
            try:
                fn()
            except Exception:
                pass
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def __enter__(self) -> "PromptRig":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False
