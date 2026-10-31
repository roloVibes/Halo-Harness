"""tests.helpers.hf_local_env -- Halo 3.3.5.0 R5: one rig for Local -> Hugging Face (tests/test_local_download_job.py,
tests/test_local_hf_api.py, tests/test_local_hf_cli.py): a fresh home whose `huggingface.model_dirs` is one scratch
folder (`models`), whose `huggingface.llama_server_bin` is the fake (tests/helpers/fake_llama_server.py), whose one
Ollama host `box` (127.0.0.1:9, never asked: its card comes from the ollama_hosts_view.READERS seam) is this
machine's card; the fake hub (tests/helpers/mock_hub.py) on 127.0.0.1:0 named by HF_ENDPOINT with a GGUF repo
(two quants), an MLX repo and a gated one; the test flag on, OLLAMA_HOST on a refused port, HF_TOKEN unset unless
a test sets it. Nothing reaches anything but the fakes.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from tests.helpers.mock_hub import MockHub, gguf_bytes

FAKE = Path(__file__).resolve().parent / "fake_llama_server.py"
GGUF = "example-org/Tiny-1B-GGUF"
MLX = "mlx-community/Tiny-4bit"
GATED = "example-org/Gated-2B-GGUF"
TOKEN = "hf_fixture_token"
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "HF_ENDPOINT", "HF_TOKEN", "OLLAMA_HOST",
         "FAKE_LLAMA_LOAD_S", "FAKE_LLAMA_EXIT")
GIB, MIB = 2 ** 30, 2 ** 20


def box_card() -> dict:
    return {"gpus": [{"id": "0", "name": "a 24 GB card", "library": "CUDA", "total_bytes": 24564 * MIB}], "unified": False,
            "ram_bytes": 64 * GIB, "other_users": [], "server": {"kv_cache_type": "f16", "parallel": 1}, "loaded": [],
            "sources": [], "read_at": "fixture"}


class HfHome:
    """`with HfHome() as h:` -- h.hub, h.state, h.models (the model folder), h.api(method, path, body, query)."""

    def __enter__(self):
        from halo_harness.studio import local_hf_view, local_pull_job as J, ollama_hosts_view as V
        self._saved = {k: os.environ.get(k) for k in _VARS}
        self.root = Path(tempfile.mkdtemp(prefix="l4_hf-")).resolve()
        for k in ("BRIDGE_STATE_DIR", "HF_TOKEN", "FAKE_LLAMA_LOAD_S", "FAKE_LLAMA_EXIT"):
            os.environ.pop(k, None)
        self.hub = MockHub().start()
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_TEST_NO_BACKGROUND_NET="1", HF_ENDPOINT=self.hub.base_url,
                          OLLAMA_HOST="http://127.0.0.1:9")
        self.state, self.models = self.root / ".halo", self.root / "models"
        self.state.mkdir(parents=True)
        self.models.mkdir()
        self.q4, self.q8 = gguf_bytes(300_000, "q4"), gguf_bytes(500_000, "q8")
        self.hub.add(GGUF, {"README.md": b"# Tiny\n", "Tiny-1B-Q4_K_M.gguf": self.q4, "Tiny-1B-Q8_0.gguf": self.q8})
        self.hub.add(MLX, {"config.json": b'{"model_type": "qwen2", "num_hidden_layers": 4, "hidden_size": 512, '
                                          b'"num_attention_heads": 8, "num_key_value_heads": 2, "max_position_embeddings": 32768}',
                           "model.safetensors": b"\0" * 80_000, "tokenizer.json": b"{}"}, kind="mlx")
        self.hub.add(GATED, {"Gated-2B-Q4_K_M.gguf": gguf_bytes(90_000, "g")}, gated="manual", token=TOKEN, license="gemma",
                     prompt="Accept the fixture licence.")
        self.write_config()
        V.reset_cache()
        V.READERS.update({"card": lambda host: box_card(), "catalog": lambda host: {"models": []}})
        J.reset()
        local_hf_view.reset()
        return self

    def write_config(self, **extra) -> None:
        cfg = {"ollama": {"hosts": [{"name": "box", "url": "http://127.0.0.1:9", "max_ctx": 32768}]},
               "huggingface": {"model_dirs": [str(self.models)], "llama_server_bin": [sys.executable, str(FAKE)]}}
        cfg.update(extra)
        (self.state / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    def config(self) -> dict:
        return json.loads((self.state / "config.json").read_text(encoding="utf-8"))

    def api(self, method: str, path: str, body=None, query=None):
        from halo_harness.studio.api import Request, dispatch
        return dispatch(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=self.root,
                                state_dir=self.state, server=None))

    def wait_job(self, job: str, s: float = 15.0) -> dict:
        import time
        end = time.monotonic() + s
        while time.monotonic() < end:
            got = next((j for j in self.api("GET", "local/downloads")[1]["jobs"] if j["job"] == job), {})
            if got.get("done"):
                return got
            time.sleep(0.05)
        return {}

    def __exit__(self, *exc):
        from halo_harness.providers.local_server import servers, stop
        from halo_harness.studio import local_hf_view, local_pull_job as J, ollama_hosts_view as V
        for e in servers(self.state):
            stop(e["id"], state_dir=self.state)
        J.reset()
        V.READERS.clear()
        V.reset_cache()
        local_hf_view.reset()
        self.hub.stop()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


__all__ = ["FAKE", "GATED", "GGUF", "HfHome", "MLX", "TOKEN", "box_card"]
