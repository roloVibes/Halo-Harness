"""tests.helpers.sched_rig -- Halo 3.3.7.0 R3: a scratch home for the scheduler's tests (tests/test_sched_*.py,
test_local_warm_cli, test_teams_swap_preview, test_loading_tax).

`SchedHome(card=..., loaded=[...])` scopes this process to a fresh `BRIDGE_TEST_HOME` (the test flag on,
`OLLAMA_HOST` at a refused port) whose `ollama.hosts` has `pc`: a MockUpstream on 127.0.0.1:0 that knows the
fixture models (qwen3.8:27b, qwen3-coder:30b, qwen3.5:9b, qwen2.5:1.5b) for `/api/ps` and the load / unload
generate. The hardware card and the catalog reach the scheduler through studio/ollama_hosts_view.READERS (the
fixture rows: tests/helpers/steward_seed.rows, a 22,000 MiB q8_0 card unless `card` is given); `loaded` seeds the
fake's `/api/ps`. Nothing leaves 127.0.0.1, no model is called, every variable it touches is restored.

    home.mock, home.host (the OllamaHost), home.state (the state dir)
    home.loads(model, *seconds, session="s1")    ledger lines that paid a load (load_ms over 2 s)
    home.config(**{"dotted.key": value})
"""
from __future__ import annotations

import os
import shutil
import tempfile

from tests.helpers.mock_ollama import MockUpstream
from tests.helpers.steward_seed import card as make_card, rows as seed_rows

BIG, CODER, SMALL, TINY = "qwen3.8:27b", "qwen3-coder:30b", "qwen3.5:9b", "qwen2.5:1.5b"
TINY_ROW = {"model": TINY, "size": 986000000, "capabilities": ["tools"],
            "model_info": {"qwen2.block_count": 28, "qwen2.attention.head_count_kv": 2, "qwen2.attention.key_length":
                           128, "qwen2.attention.value_length": 128, "qwen2.embedding_length": 1536},
            "details": {"quantization_level": "Q4_K_M", "parameter_size": "1.5B"}}
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "OLLAMA_HOST", "HALO_OFFLINE")


def rows() -> dict:
    r = seed_rows()
    r[TINY] = dict(TINY_ROW)
    return r


def ps_row(model: str, gb: float, ctx: int = 32768) -> dict:
    n = int(gb * 2 ** 30)
    return {"name": model, "model": model, "size": n, "size_vram": n, "context_length": ctx,
            "expires_at": "2099-01-01T00:00:00Z"}


class SchedHome:
    def __init__(self, *, card=None, loaded=None, hosts=None) -> None:
        self.card_ = card if card is not None else make_card(total_mib=22000, kv="q8_0")
        self.loaded_, self.extra_hosts = list(loaded or []), list(hosts or [])

    def __enter__(self) -> "SchedHome":
        self._saved = {k: os.environ.get(k) for k in _VARS}
        for k in ("BRIDGE_STATE_DIR", "HALO_OFFLINE"):
            os.environ.pop(k, None)
        self.root = tempfile.mkdtemp(prefix="hs_sched-")
        os.environ.update(BRIDGE_TEST_HOME=self.root, BRIDGE_TEST_NO_BACKGROUND_NET="1", OLLAMA_HOST="http://127.0.0.1:9")
        r = rows()
        show = {m: {"capabilities": x.get("capabilities") or [], "details": x["details"], "model_info": x["model_info"],
                    "parameters": "", "template": "", "modelfile": ""} for m, x in r.items()}
        tags = {"models": [{"name": m, "model": m, "size": x["size"], "details": x["details"]} for m, x in r.items()]}
        self.mock = MockUpstream(tags_response=tags, show_responses=show, ps_response={"models": self.loaded_}).start()
        from halo_harness.config.paths import bridge_home
        from halo_harness.providers.ollama import OllamaHost
        self.state = bridge_home()
        self.state.mkdir(parents=True, exist_ok=True)
        self.host = OllamaHost(name="pc", url=self.mock.base_url)
        self.config(**{"ollama.hosts": [{"name": "pc", "url": self.mock.base_url}] + self.extra_hosts})
        from halo_harness.studio import ollama_hosts_view as V
        self._readers = dict(V.READERS)
        V.READERS["card"] = lambda h: self.card_ if h.name == "pc" else (self.cards.get(h.name) or {})
        V.READERS["catalog"] = lambda h: {"models": list(r.values())} if h.name == "pc" else (self.catalogs.get(h.name)
                                                                                             or {"models": []})
        self.cards, self.catalogs = {}, {}
        self._reset()
        return self

    def _reset(self) -> None:
        from halo_harness.local_sched import pivot
        from halo_harness.ollama_steward import host_client
        from halo_harness.providers.ollama import reset_catalog_cache
        from halo_harness.studio import ollama_hosts_view as V
        V.reset_cache()
        host_client.reset()
        reset_catalog_cache()
        pivot._SINCE.clear()

    def config(self, **values) -> None:
        from halo_harness.theme import set_config_value
        for k, v in values.items():
            set_config_value(k, v)

    def loads(self, model: str, *seconds: float, session: str = "s1", host: str = "pc") -> None:
        from halo_harness.ollama_steward.ledger import append_lines
        from tests.helpers.steward_seed import line
        append_lines(self.state, [line(host={"name": host, "url": self.mock.base_url}, model=model, session=session,
                                       load_ms=s * 1000.0, ago=60 + i) for i, s in enumerate(seconds)])

    def __exit__(self, *exc) -> None:
        from halo_harness.studio import ollama_hosts_view as V
        self.mock.stop()
        V.READERS.clear()
        V.READERS.update(self._readers)
        self._reset()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.root, ignore_errors=True)
