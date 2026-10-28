"""tests.helpers.model_card_fixtures -- Halo 3.3.5.0 R0b: fixture `/api/show`
answers (merged with `/api/tags` the way `providers.ollama.get_catalog`
does) and tool-call probe results for the model card tests
(tests/test_model_card.py, tests/test_fit_meter.py,
tests/test_main_model_check.py). They mirror the models the owner runs --
qwen3-coder:30b (tools declared, the probe got no call on his server),
qwen3.8:27b, qwen3.5:9b, mythos-sec:24b, the obliterated twins (the bare
upload with no tool template, and the q4 twin that passed a tool round trip)
-- plus a reasoning model, a vision model, an embedding model and gpt-oss.
The shapes (`qwen35.*`, `qwen3moe.*`) are tests/helpers/steward_seed.py's
measured ones. No address but placeholders; nothing is sent anywhere.
"""
from __future__ import annotations

from tests.helpers.steward_seed import CODER30, QWEN27, QWEN9

GIB = 2 ** 30


def _row(name: str, size: int, caps: list, family: str, params: str, quant: str, info: dict, digest: str) -> dict:
    return {"name": name, "model": name, "modified_at": "2026-10-01T00:00:00Z", "size": size, "digest": digest,
            "details": {"family": family, "families": [family], "parameter_size": params, "quantization_level": quant,
                        "format": "gguf"},
            "capabilities": caps, "model_info": info}


MISTRAL24 = {"llama.block_count": 40, "llama.attention.head_count_kv": 8, "llama.attention.key_length": 128,
             "llama.attention.value_length": 128, "llama.embedding_length": 5120, "llama.context_length": 131072}
R1_14 = {"qwen2.block_count": 48, "qwen2.attention.head_count_kv": 8, "qwen2.embedding_length": 5120,
         "qwen2.attention.head_count": 40, "qwen2.context_length": 131072}
VL7 = {"qwen25vl.block_count": 28, "qwen25vl.attention.head_count_kv": 4, "qwen25vl.embedding_length": 3584,
       "qwen25vl.attention.head_count": 28, "qwen25vl.context_length": 128000}
NOMIC = {"nomic-bert.block_count": 12, "nomic-bert.attention.head_count_kv": 12, "nomic-bert.embedding_length": 768,
         "nomic-bert.attention.head_count": 12, "nomic-bert.context_length": 2048}
GPTOSS = {"gptoss.block_count": 24, "gptoss.attention.head_count_kv": 8, "gptoss.attention.key_length": 64,
          "gptoss.attention.value_length": 64, "gptoss.embedding_length": 2880, "gptoss.context_length": 131072}

ROWS = {
    "qwen3-coder:30b": _row("qwen3-coder:30b", 18554258719, ["completion", "tools"], "qwen3moe", "30.5B", "Q4_K_M",
                            {**CODER30, "qwen3moe.context_length": 262144}, "sha256:c0der"),
    "qwen3.8:27b": _row("qwen3.8:27b", 16804059546, ["completion", "vision", "tools", "thinking"], "qwen35", "27.0B",
                        "Q4_K_M", {**QWEN27, "qwen35.context_length": 262144}, "sha256:q27"),
    "qwen3.5:9b": _row("qwen3.5:9b", 6600000000, ["completion", "tools"], "qwen35", "9.0B", "Q4_K_M",
                       {**QWEN9, "qwen35.context_length": 262144}, "sha256:q9"),
    "mythos-sec:24b": _row("mythos-sec:24b", 14300000000, ["completion", "tools"], "llama", "23.6B", "Q4_K_M",
                           MISTRAL24, "sha256:myth"),
    "tinyrick/Qwen3.8-27B-OBLITERATED:Q6_K": _row("tinyrick/Qwen3.8-27B-OBLITERATED:Q6_K", 23400000000,
                                                  ["completion", "vision"], "qwen35", "27.0B", "Q6_K",
                                                  {**QWEN27, "qwen35.context_length": 262144}, "sha256:obl6"),
    "qwen3.8-obliterated:27b-q4-gpu": _row("qwen3.8-obliterated:27b-q4-gpu", 16810000000,
                                           ["completion", "vision", "tools", "thinking"], "qwen35", "27.0B", "Q4_K_M",
                                           {**QWEN27, "qwen35.context_length": 262144}, "sha256:obl4"),
    "deepseek-r1:14b": _row("deepseek-r1:14b", 9000000000, ["completion", "thinking"], "qwen2", "14.8B", "Q4_K_M",
                            R1_14, "sha256:r1"),
    "qwen2.5vl:7b": _row("qwen2.5vl:7b", 6000000000, ["completion", "vision"], "qwen25vl", "8.3B", "Q4_K_M", VL7,
                         "sha256:vl"),
    "nomic-embed-text:latest": _row("nomic-embed-text:latest", 274302450, ["embedding"], "nomic-bert", "137M", "F16",
                                    NOMIC, "sha256:nomic"),
    "gpt-oss:20b": _row("gpt-oss:20b", 13780000000, ["completion", "tools", "thinking"], "gptoss", "20.9B", "MXFP4",
                        GPTOSS, "sha256:oss"),
}
# what the tool-call probe got on the owner's server (ollama-capabilities.json, keyed by digest)
PROBES = {"sha256:c0der": False, "sha256:obl4": True}
CLOUD = {"ref": "or:anthropic/claude-sonnet-4.5", "provider": "openrouter", "modalities_in": ["text", "image"],
         "modalities_out": ["text"], "tools": True, "reasoning": {"kind": "native", "efforts": []},
         "context_tokens": 200000, "price_in_per_m": 3.0, "price_out_per_m": 15.0}


def tags_and_show(names=None) -> "tuple[dict, dict]":
    """The `/api/tags` answer and the per-model `/api/show` answers for a mock Ollama."""
    names = list(names or ROWS)
    tags = {"models": [{k: v for k, v in ROWS[n].items() if k not in ("capabilities", "model_info")} for n in names]}
    show = {n: {"modelfile": "", "parameters": "", "template": "", "capabilities": ROWS[n]["capabilities"],
                "details": ROWS[n]["details"], "model_info": ROWS[n]["model_info"]} for n in names}
    return tags, show


def write_probes(state_dir, probes=None) -> None:
    from halo_harness.providers.ollama_capability import save_capability_cache
    save_capability_cache(state_dir, {d: {"tool_calls": v, "checked_at": 0.0, "model": "", "host": "pc"}
                                      for d, v in (probes if probes is not None else PROBES).items()})


def host_card(*, total_gib: int = 24, ram_gib=None, others_gib: int = 0, kv: str = "f16") -> dict:
    """A one-GPU hardware card (ollama_steward/hardware.py's shape)."""
    from tests.helpers.steward_seed import card
    c = card(total_mib=total_gib * 1024, kv=kv,
             others=[{"name": "python (ComfyUI)", "bytes": others_gib * GIB}] if others_gib else None)
    c["ram_bytes"] = ram_gib * GIB if ram_gib else None
    return c
