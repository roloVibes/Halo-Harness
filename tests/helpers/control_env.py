"""tests.helpers.control_env -- Halo 3.3.5.0 R3: a fresh home whose one
configured Ollama host `box` is the fake on 127.0.0.1:0 (tests/helpers/
mock_ollama.py with tests/helpers/mock_ollama_pull.py's /api/pull and
/api/copy), the test flag on and `OLLAMA_HOST` pinned to a refused port, for
tests/test_ollama_control.py, tests/test_local_pull_job.py and the CLI test.
Nothing is sent anywhere but the fake.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

REFUSED = "http://127.0.0.1:9"
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST", "OLLAMA_API_KEY", "BRIDGE_TEST_NO_BACKGROUND_NET",
         "HALO_OFFLINE")
QWEN_SHOW = {"capabilities": ["completion", "tools"], "license": "Apache License 2.0 (fixture)",
             "details": {"family": "qwen35", "format": "gguf", "parameter_size": "9.0B", "quantization_level": "Q4_K_M"},
             "model_info": {"qwen35.context_length": 262144, "qwen35.block_count": 32},
             "parameters": 'temperature                    0.7\nstop                           "<|im_end|>"',
             "template": "{{ .Prompt }}", "modelfile": "FROM /blobs/sha256-aaaa"}


class Box:
    """`with Box() as b:` -- b.mock (the fake), b.host (the OllamaHost `box`), b.state (the home's .halo)."""

    def __init__(self, delay: float = 0.0):
        self.delay = delay

    def __enter__(self):
        from tests.helpers.mock_ollama import MockUpstream
        self._saved = {k: os.environ.get(k) for k in _VARS}
        self.root = Path(tempfile.mkdtemp(prefix="l3_ctl-")).resolve()
        for k in ("OLLAMA_API_KEY", "HALO_OFFLINE", "BRIDGE_STATE_DIR"):
            os.environ.pop(k, None)
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), OLLAMA_HOST=REFUSED, BRIDGE_TEST_NO_BACKGROUND_NET="1")
        self.state = self.root / ".halo"
        self.state.mkdir(parents=True)
        self.mock = MockUpstream().start()
        self.mock.pullable["qwen3.5:9b"] = json.loads(json.dumps(QWEN_SHOW))
        self.mock.pull_delay_s = self.delay
        (self.state / "config.json").write_text(json.dumps({"ollama": {"hosts": [
            {"name": "box", "url": self.mock.base_url, "default": True}]}}), encoding="utf-8")
        from halo_harness.providers.ollama import reset_catalog_cache, resolve_ollama_host
        reset_catalog_cache()
        self.host = resolve_ollama_host("box")
        return self

    def paths(self, method: str = "") -> list:
        return [r["path"] for r in self.mock.requests if not method or r["method"] == method]

    def __exit__(self, *exc):
        self.mock.stop()
        from halo_harness.providers.ollama import reset_catalog_cache
        reset_catalog_cache()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
