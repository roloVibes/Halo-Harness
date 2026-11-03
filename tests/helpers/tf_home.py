"""tests.helpers.tf_home -- Halo 3.3.9.3: the TensorFold rig. `with TfHome() as h:` is tests/helpers/hf_local_env.HfHome
(a fresh home, the fake hub, the box card) plus `huggingface.tensorfold_bin` = [python, tests/helpers/fake_tensorfold_server.py],
HF_HUB_CACHE in the scratch home (never the real Hugging Face cache), HALO_ENV_FILE in the scratch home (Halo's key
lands there), the platform seam saying Linux x86_64 unless a test says otherwise, `h.cached(repo)` writing a Hub-cache
snapshot of a repo (config.json, refs/main, no weights) and `h.checkpoint(name)` a checkpoint folder. Nothing reaches
anything but the fakes.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from tests.helpers.hf_local_env import HfHome

FAKE_TF = Path(__file__).resolve().parent / "fake_tensorfold_server.py"
REPO = "TensorFold/Qwen3.8-27B-MLX-4bit"
CONFIG = {"architectures": ["Qwen3_5ForConditionalGeneration"], "model_type": "qwen3_5", "num_hidden_layers": 64,
          "hidden_size": 5120, "quantization": {"group_size": 64, "bits": 4}}
_VARS = ("FAKE_TF_LOAD_S", "FAKE_TF_EXIT", "FAKE_TF_BACKEND", "FAKE_TF_SM", "FAKE_TF_STREAMS", "FAKE_TF_WAITING",
         "HALO_ENV_FILE", "HALO_SECRET_TENSORFOLD_API_KEY", "TENSORFOLD_API_KEY", "HF_HUB_CACHE", "HF_HOME",
         "HF_LOCAL_PROBE_PORTS", "TENSORFOLD_LOG_TIME")


def reset_caches() -> None:
    from halo_harness.ollama_steward import server_log_hf, servers_hf
    from halo_harness.providers.huggingface_local_probe import reset_auto_detect_cache
    from halo_harness.tensorfold import peer, requirements
    requirements.SEAMS.clear()
    peer.reset()
    servers_hf.reset()
    server_log_hf.reset()
    reset_auto_detect_cache()


class TfHome(HfHome):
    def __enter__(self):
        self._tf_saved = {k: os.environ.get(k) for k in _VARS}
        for k in _VARS:
            os.environ.pop(k, None)
        super().__enter__()
        os.environ["HALO_ENV_FILE"] = str(self.root / "env")
        self.hub_cache = self.root / "hf-cache" / "hub"
        self.hub_cache.mkdir(parents=True)
        os.environ["HF_HUB_CACHE"] = str(self.hub_cache)
        self.set_hf(tensorfold_bin=[sys.executable, str(FAKE_TF)])
        reset_caches()
        from halo_harness.tensorfold import requirements
        requirements.SEAMS.update(os=lambda: "linux", machine=lambda: "x86_64")
        return self

    def set_hf(self, **keys) -> None:
        cfg = self.config()
        cfg.setdefault("huggingface", {}).update(keys)
        (self.state / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        from halo_harness.ollama_steward import servers_hf
        servers_hf.reset()

    def cached(self, repo: str = REPO, root=None) -> Path:
        d = Path(root or self.hub_cache) / ("models--" + repo.replace("/", "--"))
        snap = d / "snapshots" / "0123abcd"
        snap.mkdir(parents=True, exist_ok=True)
        (snap / "config.json").write_text(json.dumps(CONFIG), encoding="utf-8")
        (d / "refs").mkdir(exist_ok=True)
        (d / "refs" / "main").write_text("0123abcd", encoding="utf-8")
        return snap

    def checkpoint(self, name: str = "qwen27-local") -> Path:
        d = self.models / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(json.dumps(CONFIG), encoding="utf-8")
        return d

    def __exit__(self, *exc):
        try:
            super().__exit__(*exc)
        finally:
            reset_caches()
            for k, v in self._tf_saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


__all__ = ["CONFIG", "FAKE_TF", "REPO", "TfHome", "reset_caches"]
