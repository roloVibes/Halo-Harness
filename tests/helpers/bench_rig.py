"""tests.helpers.bench_rig -- Halo 3.3.6.0 R5: a scratch home whose one Ollama host (`fake`) is the bench's scripted
fake on 127.0.0.1:0 (tests/helpers/mock_ollama_bench.py), its hardware card a 24 GiB test card (q8_0 KV), and the
Ollama panel's readers (studio/ollama_hosts_view.READERS) answering from them. Never a real server, never a model call.

    with BenchRig(kv="q8_0") as rig:
        card = rig.bench("bn-coder:30b")      # providers/local_bench.bench through the gym's send path
        rig.host, rig.mock, rig.state, rig.card
"""

from __future__ import annotations

import json

from tests.helpers import mock_ollama_bench as MB
from tests.helpers.battery_rig import gpu_card
from tests.helpers.mock_ollama import MockUpstream
from tests.helpers.steward_seed import Home


class BenchRig:
    def __init__(self, names=None, *, kv: str = "q8_0", version: str = "0.40.13"):
        self.names, self.kv, self.version = names, kv, version

    def __enter__(self):
        self.mock = MockUpstream().start()
        MB.install(self.mock, self.names, version=self.version)
        self.home = Home(hosts=({"name": "fake", "url": self.mock.base_url},)).__enter__()
        self.state = self.home.state
        self.card = gpu_card(24.0, self.kv)
        self.card["server"]["version"] = self.version
        from halo_harness.providers.ollama import resolve_ollama_host
        from halo_harness.studio import ollama_hosts_view as V
        self.host = resolve_ollama_host("fake")
        V.reset_cache()
        V.READERS.update(card=lambda _h: self.card, catalog=lambda _h: self.catalog())
        return self

    def catalog(self) -> dict:
        names = self.names or list(MB.MODELS)
        return {"models": [{**MB.row(n), "model_info": MB.MODELS[n]["info"]} for n in names]}

    def __exit__(self, *exc):
        from halo_harness.providers.local_bench_runs import _INDEX
        from halo_harness.studio import ollama_hosts_view as V
        V.READERS.clear()
        V.reset_cache()
        _INDEX.clear()
        self.home.__exit__(*exc)
        self.mock.stop()

    def bench(self, name: str, **kw) -> dict:
        from halo_harness.providers.local_bench import bench
        kw.setdefault("sessions", lambda: [])
        return bench(self.host, name, card=self.card, state_dir=self.state, **kw)

    def chats(self) -> list:
        return [r["body"] for r in self.mock.requests if r.get("path") == "/api/chat"]

    def cache(self) -> dict:
        return json.loads((self.state / "ollama-capabilities.json").read_text(encoding="utf-8"))
