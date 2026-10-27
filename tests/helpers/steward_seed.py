"""tests.helpers.steward_seed -- Halo 3.3.4.0 R3: a fresh home with a
configured host, fixture ledger lines and server events for the steward's
rules, planner and profiles tests (tests/test_steward_*.py). Every address
is a 192.0.2.x placeholder; nothing is sent anywhere.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

PC = {"name": "pc", "url": "http://192.0.2.10:11434"}
SAMUS = {"name": "samus", "url": "http://192.0.2.20:11434"}
GIB = 2 ** 30
MIB = 2 ** 20
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST", "BRIDGE_TEST_NO_BACKGROUND_NET")


class Home:
    """A scratch home; `hosts` go into its config.json (`ollama.hosts`)."""

    def __init__(self, hosts=(PC,), extra: "dict | None" = None):
        self.hosts, self.extra = list(hosts), extra or {}

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _VARS}
        self.root = Path(tempfile.mkdtemp(prefix="r3_steward-")).resolve()
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_STATE_DIR=str(self.root / ".halo"),
                          OLLAMA_HOST="http://127.0.0.1:11434", BRIDGE_TEST_NO_BACKGROUND_NET="1")
        self.state = self.root / ".halo"
        self.state.mkdir(parents=True)
        cfg = {"ollama": {"hosts": self.hosts}}
        for section, values in self.extra.items():
            cfg.setdefault(section, {}).update(values)
        (self.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def calls(self, *lines) -> None:
        from halo_harness.ollama_steward.ledger import append_lines
        append_lines(self.state, list(lines))

    def events(self, *evs, host: str = "pc") -> None:
        from halo_harness.ollama_steward.server_events import record_events
        record_events(self.state, list(evs), host=host)

    def cap(self, model: str, cap: int, host: dict = PC) -> None:
        from halo_harness.providers.ollama_calibrate import record_calibration
        record_calibration(self.state, host_url=host["url"], model=model, digest=None, max_full_gpu_ctx=cap,
                           ollama_version=None)


def at(ago_s: float = 60.0) -> str:
    from halo_harness.ollama_steward.ledger import now_iso
    return now_iso(time.time() - ago_s)


def line(**kw) -> dict:
    from halo_harness.ollama_steward.ledger import blank_line
    base = {"host": PC, "model": "qwen3.8:27b", "dialect": "ollama", "status": 200, "num_ctx_sent": 32768,
            "prompt_eval_count": 10000, "eval_count": 300, "eval_tok_s": 40.0, "load_ms": 50.0, "from": None,
            "session": "s1", "window_source": "fit estimate", "at": at(kw.pop("ago", 600.0))}
    return blank_line(**{**base, **kw})


def event(kind: str, model: str = "qwen3.8:27b", ago: float = 600.0, **data) -> dict:
    from halo_harness.ollama_steward.server_rules import event as make
    return make(kind, f"{kind} for {model}", f"fixture {kind}", at=time.time() - ago, model=model, **data)


QWEN27 = {"qwen35.block_count": 65, "qwen35.attention.head_count_kv": 4, "qwen35.attention.key_length": 256,
          "qwen35.attention.value_length": 256, "qwen35.full_attention_interval": 4, "qwen35.nextn_predict_layers": 1,
          "qwen35.embedding_length": 5120, "qwen35.ssm.conv_kernel": 4, "qwen35.ssm.state_size": 128,
          "qwen35.ssm.group_count": 16, "qwen35.ssm.inner_size": 6144, "qwen35.vocab_size": 248320}
CODER30 = {"qwen3moe.block_count": 48, "qwen3moe.attention.head_count_kv": 4, "qwen3moe.attention.key_length": 128,
           "qwen3moe.attention.value_length": 128, "qwen3moe.embedding_length": 2048, "qwen3moe.vocab_size": 151936}
QWEN9 = {"qwen35.block_count": 32, "qwen35.attention.head_count_kv": 4, "qwen35.attention.key_length": 256,
         "qwen35.attention.value_length": 256, "qwen35.full_attention_interval": 4, "qwen35.embedding_length": 4096}


def rows() -> dict:
    """Catalog rows (`/api/tags` + `/api/show`) for the measured host's models."""
    return {"qwen3.8:27b": {"model": "qwen3.8:27b", "size": 16804059546, "model_info": QWEN27,
                            "capabilities": ["vision", "tools", "thinking"],
                            "details": {"quantization_level": "Q4_K_M", "parameter_size": "27.0B"}},
            "qwen3-coder:30b": {"model": "qwen3-coder:30b", "size": 18554258719, "model_info": CODER30,
                                "capabilities": ["tools"],
                                "details": {"quantization_level": "Q4_K_M", "parameter_size": "30.5B"}},
            "qwen3.5:9b": {"model": "qwen3.5:9b", "size": 6600000000, "model_info": QWEN9, "capabilities": ["tools"],
                           "details": {"quantization_level": "Q4_K_M", "parameter_size": "9.0B"}}}


def card(*, total_mib: int = 24564, others: "list | None" = None, kv: str = "q8_0", unified: bool = False,
         available_mib: "int | None" = None) -> dict:
    """A hardware card (ollama_steward/hardware.py's shape): one GPU."""
    gpu = {"id": "0", "name": "Apple M-series" if unified else "a 24 GB card", "library": "Metal" if unified else "CUDA",
           "total_bytes": total_mib * MIB,
           "available_bytes": (available_mib if available_mib is not None else total_mib) * MIB}
    return {"gpus": [gpu], "unified": unified, "ram_bytes": None, "loaded": [], "other_users": others or [],
            "server": {"kv_cache_type": kv, "parallel": 1, "max_loaded": 3}, "sources": []}
