"""tests.helpers.place_rig -- Halo 3.3.7.0 R3: two `halo host`s and one plain Ollama for the placement solver
(tests/test_sched_place.py). Everything on 127.0.0.1:0.

    pc     a real halo host (tests/helpers/host_rig.HostRig on its own scratch home) serving a fake Ollama with
           qwen3.8:27b, qwen3-coder:30b, qwen3.5:9b; its card the Ollama panel seed's 24 GB one (ComfyUI holds 2 GB);
           qwen3-coder:30b loaded at 32,768 (warm)
    samus  a second real halo host (another scratch home, advertising 192.0.2.20) serving a fake with qwen3.5:9b on a
           10 GB q8_0 card, nothing loaded; its battery profile of qwen3.5:9b says an 18 s cold load
    box    a fake Ollama this machine reads directly (no halo host): qwen2.5:1.5b, the local-reads candidate

This process is the peer (`bob@peer`): its `ollama.hosts` names pc at 192.0.2.10:<pc's port>, samus at
192.0.2.20:<samus's port> (placeholders that match what each host serves; no request goes there) and box at its
loopback address; both hosts are paired. studio/ollama_hosts_view.READERS gives the peer each host's card and
catalog for the local reads (the fallback when a route answer is missing).
"""
from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

from tests.helpers.host_act_rig import SMALL, mock_for
from tests.helpers.host_rig import BIG, CODER, HostRig
from tests.helpers.mock_ollama import MockUpstream
from tests.helpers.sched_rig import TINY, TINY_ROW, ps_row


def _mock(rows: list, loaded=None) -> MockUpstream:
    tags = {"models": [{"name": r["model"], "model": r["model"], "size": r["size"], "details": r["details"]} for r in rows]}
    show = {r["model"]: {"capabilities": r.get("capabilities") or [], "details": r["details"], "model_info": r["model_info"],
                         "parameters": "", "template": "", "modelfile": ""} for r in rows}
    return MockUpstream(tags_response=tags, show_responses=show, ps_response={"models": list(loaded or [])}).start()


class PlaceRig:
    def __enter__(self) -> "PlaceRig":
        from tests.helpers.ollama_panel_seed import cards
        from tests.helpers.steward_seed import card, rows
        from halo_harness.providers.ollama import OllamaHost
        r = rows()
        self.pc_mock = mock_for()
        self.pc_mock.ps_response = {"models": [ps_row(CODER, 18.5)]}
        self.samus_mock = _mock([r[SMALL]])
        self.box_mock = _mock([dict(TINY_ROW)])
        self.cards = {"pc": {**cards()["pc"], "loaded": [ps_row(CODER, 18.5)]}, "samus": card(total_mib=10240, kv="q8_0"),
                      "box": card(total_mib=8192, kv="q8_0")}
        self.catalogs = {"pc": [r[BIG], r[CODER], r[SMALL]], "samus": [r[SMALL]], "box": [dict(TINY_ROW)]}
        pc = OllamaHost(name="pc", url=self.pc_mock.base_url)
        samus = OllamaHost(name="samus", url=self.samus_mock.base_url)
        self.rig = HostRig(readers_=self._readers(pc), seed=False).__enter__()
        self.pc_url = f"http://192.0.2.10:{self.pc_mock.port}"
        self.samus_url = f"http://192.0.2.20:{self.samus_mock.port}"
        self.rig.set_peer(**{"ollama.hosts": [{"name": "pc", "url": self.pc_url}, {"name": "samus", "url": self.samus_url},
                                              {"name": "box", "url": self.box_mock.base_url}],
                             "ollama.steward.probe_new": False})
        self.rig.start()
        self.rig.pair()
        self.root2 = tempfile.mkdtemp(prefix="hs_host2-")
        self.home2 = Path(self.root2) / ".halo"
        self.home2.mkdir(parents=True)
        (self.home2 / "config.json").write_text(json.dumps({"fleet": {"name": "samus-host"}, "ollama": {
            "steward": {"probe_new": False}}}), encoding="utf-8")
        from halo_harness.providers.ollama_capability import save_profile
        save_profile(self.home2, {"model": SMALL, "host": "samus", "digest": "sha256:5a", "probed_at": time.time(),
                                  "tools": "yes", "speed": {"tok_s": 60.0, "cold_load_s": 18.0}, "evidence": {}})
        from halo_harness.host.service import HostService
        self.svc2 = HostService(self.home2, port=0, bind="127.0.0.1", advertise="192.0.2.20",
                                readers=self._readers(samus), job=lambda h: None, forward=False).start()
        self._pair2()
        self._peer_readers()
        return self

    def _readers(self, host) -> dict:
        name = host.name
        return {"hosts": lambda: [host], "card": lambda h: self.cards[name],
                "catalog": lambda h: {"models": list(self.catalogs[name])},
                "tail": lambda h, n: ([], "fixture", None), "log": lambda h: {"state": "live", "line": "live"}}

    def _pair2(self) -> None:
        from halo_harness.fleet import identity, store
        from halo_harness.host.join import join
        from halo_harness.ollama_steward import host_client
        got = join(f"127.0.0.1:{self.svc2.port}", self.svc2.pairing.new_code(600)[0], identity.harness())
        key = got.pop("key")
        store.add_host(got, key)
        host_client.reset()

    def _peer_readers(self) -> None:
        from halo_harness.studio import ollama_hosts_view as V
        self._saved_readers = dict(V.READERS)
        V.READERS["card"] = lambda h: self.cards.get(h.name) or {}
        V.READERS["catalog"] = lambda h: {"models": list(self.catalogs.get(h.name) or [])}
        V.reset_cache()

    def __exit__(self, *exc) -> None:
        from halo_harness.studio import ollama_hosts_view as V
        try:
            self.svc2.stop()
            self.rig.__exit__(*exc)
        finally:
            V.READERS.clear()
            V.READERS.update(self._saved_readers)
            V.reset_cache()
            for m in (self.pc_mock, self.samus_mock, self.box_mock):
                m.stop()
            shutil.rmtree(self.root2, ignore_errors=True)
