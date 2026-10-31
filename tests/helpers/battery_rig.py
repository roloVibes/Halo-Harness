"""tests.helpers.battery_rig -- Halo 3.3.6.0 R1: a scratch home whose one
Ollama host (`fake`) is a scripted fake on 127.0.0.1:0 answering the
battery's probes (tests/helpers/mock_ollama_battery.py), for the battery,
placement, card and failure-line tests. Never a real server, never a model
call.

    with BatteryRig(names=None, card=None) as rig:
        p = rig.probe("bt-coder:30b")            # the battery through the real HTTP client
        rig.host, rig.mock, rig.state, rig.ref("bt-mute:24b")
"""

from __future__ import annotations

import json

from tests.helpers.mock_ollama import MockUpstream
from tests.helpers import mock_ollama_battery as MB
from tests.helpers.steward_seed import GIB, Home


def gpu_card(total_gib: float = 24.0, kv: str = "q8_0") -> dict:
    """A hardware card (the Ollama panel's shape) with one GPU of `total_gib`."""
    return {"gpus": [{"name": "RTX test", "total_bytes": int(total_gib * GIB), "library": "CUDA"}],
            "other_users": [], "server": {"kv_cache_type": kv, "parallel": 1}, "ram_bytes": 64 * GIB}


class BatteryRig:
    def __init__(self, names=None, *, extra=None, version: str = "0.40.13"):
        self.names, self.extra, self.version = names, extra or {}, version

    def __enter__(self):
        self.mock = MockUpstream().start()
        MB.install(self.mock, self.names, version=self.version)
        self.home = Home(hosts=({"name": "fake", "url": self.mock.base_url},), extra=self.extra).__enter__()
        self.state = self.home.state
        from halo_harness.providers.ollama import resolve_ollama_host
        self.host = resolve_ollama_host("fake")
        return self

    def __exit__(self, *exc):
        self.home.__exit__(*exc)
        self.mock.stop()

    def ref(self, name: str) -> str:
        return f"ol:{name}@fake"

    def probe(self, name: str, **kw) -> dict:
        from halo_harness.providers.capability_battery import run
        return run(self.host, name, state_dir=self.state, **kw)

    def chats(self) -> list:
        return [r["body"] for r in self.mock.requests if r.get("path") == "/api/chat"]

    def cache(self) -> dict:
        return json.loads((self.state / "ollama-capabilities.json").read_text(encoding="utf-8"))
