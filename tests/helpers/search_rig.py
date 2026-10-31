"""tests.helpers.search_rig -- Halo 3.3.6.0 R2: a scratch home for the capability-filtered search
(models_library/search.py): one Ollama host `box` (a refused address unless a fake is given), its hardware card and
catalog through the Ollama panel's READERS seam, the disk through search_query.DISK_SEAM, the library from the
shipped snapshot and the hub's fixtures (BRIDGE_TEST_NO_BACKGROUND_NET=1). Never a real server, never a model call.

    with SearchHome(card=box_card(), url=None) as h:
        h.state, h.profile("qwen3-coder:30b", tools="yes", ...), h.library(search={...}), h.event(...)
    box_card(total_gib=24, loaded=(), version="0.40.6", kv="q8_0")   a 24 GB CUDA card
    profile(model, host="box", **fields)                             a battery profile (providers/battery_profile.py)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

GIB = 2 ** 30
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST", "BRIDGE_TEST_NO_BACKGROUND_NET", "OLLAMA_API_KEY")


def box_card(total_gib: float = 24.0, loaded=(), version: str = "0.40.6", kv: str = "q8_0", fa: bool = True,
             library: str = "CUDA", max_loaded: int = 2) -> dict:
    return {"gpus": [{"name": "a 24 GB card", "library": library, "total_bytes": int(total_gib * GIB)}],
            "unified": library == "Metal", "ram_bytes": 64 * GIB, "other_users": [],
            "server": {"version": version, "kv_cache_type": kv, "flash_attention": fa, "parallel": 1,
                       "max_loaded": max_loaded, "source": "fixture"},
            "loaded": [dict(x) for x in loaded], "sources": [], "read_at": "fixture"}


def profile(model: str, host: str = "box", **fields) -> dict:
    import time
    p = {"model": model, "host": host, "digest": f"sha256:{abs(hash((model, host))) % 10 ** 12:012d}",
         "ollama_version": "0.40.6", "probed_at": time.time() - 60, "tools": "yes", "system_role": "honoured",
         "instruction": "strict", "output": "json", "identifiers": "trusted", "reasoning": "none",
         "window": {"trained": 262144, "usable": 65536, "used": 32768, "verified": True}, "size_gb": 18.6,
         "speed": {"tok_s": 188.0, "ttft_ms": 120, "cold_load_s": 31.0, "at_window": 32768},
         "resident": {"co_resides_with": [], "pivot_only": False}, "interactive": "yes", "quirks": [],
         "agentic_ready": True, "sits": "full agent", "chips": ["full agent"]}
    from halo_harness.providers.battery_probes import PROBE_SET
    p["probe_set"] = PROBE_SET
    p.update(fields)
    return p


class SearchHome:
    def __init__(self, card=None, url: str = "http://127.0.0.1:9", catalog=None, disk=(500 * 10 ** 9, "fixture disk")):
        self.card, self.url, self.catalog, self.disk = card, url, catalog or {"models": []}, disk

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _VARS}
        self.root = Path(tempfile.mkdtemp(prefix="se_search-")).resolve()
        self.state = self.root / ".halo"
        self.state.mkdir(parents=True)
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_STATE_DIR=str(self.state),
                          OLLAMA_HOST="http://127.0.0.1:9", BRIDGE_TEST_NO_BACKGROUND_NET="1")
        os.environ.pop("OLLAMA_API_KEY", None)
        (self.state / "config.json").write_text(json.dumps({"ollama": {"hosts": [{"name": "box", "url": self.url}]}}),
                                                encoding="utf-8")
        from halo_harness.models_library import search_query
        from halo_harness.providers import ollama as O
        from halo_harness.studio import ollama_hosts_view as V
        V.reset_cache()
        O.reset_catalog_cache()
        V.READERS.update({"card": lambda host: self.card, "catalog": lambda host: self.catalog})
        search_query.DISK_SEAM["free"] = lambda host: self.disk
        return self

    def __exit__(self, *exc):
        from halo_harness.models_library import search_query
        from halo_harness.studio import ollama_hosts_view as V
        V.READERS.clear()
        V.reset_cache()
        search_query.DISK_SEAM.clear()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def profile(self, model: str, **fields) -> dict:
        from halo_harness.providers.ollama_capability import save_profile
        p = profile(model, **fields)
        save_profile(self.state, p)
        return p

    def library(self, **kw) -> dict:
        from halo_harness.models_library.browse import library
        kw.setdefault("host", "box")
        kw.setdefault("per", 2000)
        return library(self.state, **kw)

    def events(self, *evs, host: str = "box") -> list:
        from halo_harness.ollama_steward.server_events import record_events
        return record_events(self.state, list(evs), host=host)
