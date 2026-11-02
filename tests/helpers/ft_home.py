"""tests.helpers.ft_home -- Halo 3.3.9.1: the FreeToken rig. `with FtHome() as h:` is tests/helpers/hf_local_env.HfHome
(a fresh home, the fake hub, the box card) plus `huggingface.freetoken_bin` = [python, tests/helpers/fake_ft_server.py],
the platform seam saying Linux x86_64 (freetoken/requirements.SEAMS: the requirement checks never run a real
nvidia-smi or nvcc), HALO_ENV_FILE in the scratch home (a `--lan` key lands there), and `h.checkpoint(name)` writing a
checkpoint folder: a config.json of Qwen3.6-35B-A3B's shape and a safetensors index stating its bytes (no weights).
Nothing reaches anything but the fakes.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from tests.helpers.hf_local_env import HfHome

FAKE_FT = Path(__file__).resolve().parent / "fake_ft_server.py"
LINUX = {"os": "linux", "arch": "x86_64", "linux": True, "x86": True, "wsl": False}
QWEN36 = {"architectures": ["Qwen3_5MoeForCausalLM"], "num_hidden_layers": 40, "hidden_size": 2048, "num_experts": 256,
          "moe_intermediate_size": 512, "num_experts_per_tok": 8, "num_attention_heads": 16, "num_key_value_heads": 2,
          "head_dim": 256, "full_attention_interval": 4, "quantization_config": {"quant_method": "modelopt",
                                                                                 "quant_algo": "NVFP4"}}
QWEN36_BYTES = 19_800_000_000
_VARS = ("FAKE_FT_LOAD_S", "FAKE_FT_EXIT", "FAKE_FT_HIT", "FAKE_FT_CTX", "FAKE_FT_GATHER", "HALO_ENV_FILE",
         "HALO_SECRET_FREETOKEN_API_KEY", "FREETOKEN_API_KEY", "HF_LOCAL_PROBE_PORTS")


def reset_caches() -> None:
    from halo_harness.freetoken import bench, link, peer, requirements
    from halo_harness.ollama_steward import server_log_hf, servers_hf
    from halo_harness.providers.huggingface_local_probe import reset_auto_detect_cache
    for seams in (bench.SEAMS, link.SEAMS, requirements.SEAMS):
        seams.clear()
    peer.reset()
    servers_hf.reset()
    server_log_hf.reset()
    reset_auto_detect_cache()


class FtHome(HfHome):
    def __enter__(self):
        self._ft_saved = {k: os.environ.get(k) for k in _VARS}
        for k in _VARS:
            os.environ.pop(k, None)
        super().__enter__()
        os.environ["HALO_ENV_FILE"] = str(self.root / "env")
        self.set_hf(freetoken_bin=[sys.executable, str(FAKE_FT)])
        reset_caches()
        from halo_harness.freetoken import requirements
        requirements.SEAMS["platform"] = lambda: dict(LINUX)
        return self

    def set_hf(self, **keys) -> None:
        cfg = self.config()
        cfg.setdefault("huggingface", {}).update(keys)
        (self.state / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        from halo_harness.ollama_steward import servers_hf
        servers_hf.reset()

    def checkpoint(self, name: str = "Qwen3.6-35B-A3B-NVFP4", config=None, total: int = QWEN36_BYTES) -> Path:
        d = self.models / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(json.dumps(config or QWEN36), encoding="utf-8")
        (d / "model.safetensors.index.json").write_text(json.dumps({"metadata": {"total_size": total},
                                                                     "weight_map": {}}), encoding="utf-8")
        return d

    def __exit__(self, *exc):
        try:
            super().__exit__(*exc)
        finally:
            reset_caches()
            for k, v in self._ft_saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


__all__ = ["FAKE_FT", "FtHome", "LINUX", "QWEN36", "QWEN36_BYTES", "reset_caches"]
