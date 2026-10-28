"""tests.helpers.local_api_rig -- Halo 3.3.5.0 R1: the in-process rig of tests/test_local_api.py: `Local` is a
fresh home (tests/helpers/steward_seed.Home) with tests/helpers/local_seed.py's fixture and `box`, the fake Ollama on
127.0.0.1:0, its routes called through studio/api.dispatch; `FakeHub` a hub with one member `mac@studio` and a
command log (the remote control path without a relay).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from tests.helpers import local_seed as L
from tests.helpers.steward_seed import Home


class Local(Home):
    def __init__(self, server=None):
        super().__init__(hosts=[])
        self.server = server

    def __enter__(self):
        super().__enter__()
        from halo_harness.studio import ollama_hosts_view as V
        self.mock = L.start_box()
        L.seed(self.state, self.mock)
        V.reset_cache()
        V.READERS.clear()
        V.READERS.update(L.readers(self.mock))
        return self

    def __exit__(self, *exc):
        from halo_harness.ollama_steward import resources
        from halo_harness.studio import ollama_hosts_view as V
        V.READERS.clear()
        V.reset_cache()
        resources.stop_all()
        resources.STORE.clear()
        self.mock.stop()
        return super().__exit__(*exc)

    def api(self, method: str, path: str, body=None, query=None):
        from halo_harness.studio.api import Request, dispatch
        return dispatch(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=self.root,
                                state_dir=self.state, server=self.server))

    def card(self, name: str) -> dict:
        return next(h for h in self.api("GET", "local/hosts")[1]["hosts"] if h["name"] == name)

    def config(self) -> dict:
        return json.loads((self.state / "config.json").read_text(encoding="utf-8"))


class FakeHub:
    """A hub with one member `mac@studio` (its allow_control as given, one live session) and a command log."""

    def __init__(self, level: str, home) -> None:
        self.sent: list = []
        member = SimpleNamespace(id="hid-mac", name=L.MEMBER, allow_control=level,
                                 sessions=lambda: [{"session_id": "s-mac"}])
        cmds = SimpleNamespace(send=lambda hid, sid, cmd, fields, by, wait_s: self.sent.append((hid, sid, cmd, fields))
                               or (200, {"ok": True, "result": {"ok": True, "say": "loaded there"}}))
        self.fleet_hub = SimpleNamespace(state=SimpleNamespace(members={"hid-mac": member}, commands=cmds), home=home)
