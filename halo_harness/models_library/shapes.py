"""halo_harness.models_library.shapes -- Halo 3.3.5.0 R2: a model's shape before it is installed.

The memory arithmetic (providers/ollama_fit_parts.py, ollama_steward/knowledge/memory.md) needs the layers that
hold a KV cache, the KV heads and the head size; an installed model has them in `/api/show`'s model_info, a
library row does not. `shape_for(name, params, family, info=None)` answers, in this order:

    1. `info`: a shape the caller already has (a Hugging Face repo's config.json, hf_hub.shape_from_config)
    2. KNOWN: the published configs of the families the library's most pulled models belong to, by "<model>:<size>"
       (each line: layers, KV heads, head size, embedding, vocabulary, and the one-in-N KV interval of a hybrid);
       qwen3.5's 9b and 27b are memory.md's measured shapes
    3. a typical grouped-query shape for the size: 8 KV heads of 128, about 9.8 x sqrt(billions) layers -- within
       a third of the KV bytes per token of every dense model in KNOWN

-> (model_info, source); source names which, and 2-3 are estimates (the fit badge says so).
"""

from __future__ import annotations

import math
from typing import Optional

# "<model>:<size>": (block_count, head_count_kv, head_dim, embedding_length, vocab_size, full_attention_interval)
KNOWN = {
    "llama3.1:8b": (32, 8, 128, 4096, 128256, 1), "llama3.1:70b": (80, 8, 128, 8192, 128256, 1),
    "llama3.1:405b": (126, 8, 128, 16384, 128256, 1), "llama3:8b": (32, 8, 128, 4096, 128256, 1),
    "llama3:70b": (80, 8, 128, 8192, 128256, 1), "llama3.3:70b": (80, 8, 128, 8192, 128256, 1),
    "llama3.2:1b": (16, 8, 64, 2048, 128256, 1), "llama3.2:3b": (28, 8, 128, 3072, 128256, 1),
    "llama2:7b": (32, 32, 128, 4096, 32000, 1), "llama2:13b": (40, 40, 128, 5120, 32000, 1),
    "llama2:70b": (80, 8, 128, 8192, 32000, 1), "codellama:7b": (32, 32, 128, 4096, 32016, 1),
    "codellama:13b": (40, 40, 128, 5120, 32016, 1), "codellama:34b": (48, 8, 128, 8192, 32000, 1),
    "codellama:70b": (80, 8, 128, 8192, 32016, 1),
    "qwen2.5:0.5b": (24, 2, 64, 896, 151936, 1), "qwen2.5:1.5b": (28, 2, 128, 1536, 151936, 1),
    "qwen2.5:3b": (36, 2, 128, 2048, 151936, 1), "qwen2.5:7b": (28, 4, 128, 3584, 152064, 1),
    "qwen2.5:14b": (48, 8, 128, 5120, 152064, 1), "qwen2.5:32b": (64, 8, 128, 5120, 152064, 1),
    "qwen2.5:72b": (80, 8, 128, 8192, 152064, 1),
    "qwen3:0.6b": (28, 8, 128, 1024, 151936, 1), "qwen3:1.7b": (28, 8, 128, 2048, 151936, 1),
    "qwen3:4b": (36, 8, 128, 2560, 151936, 1), "qwen3:8b": (36, 8, 128, 4096, 151936, 1),
    "qwen3:14b": (40, 8, 128, 5120, 151936, 1), "qwen3:32b": (64, 8, 128, 5120, 151936, 1),
    "qwen3:30b": (48, 4, 128, 2048, 151936, 1), "qwen3:235b": (94, 4, 128, 4096, 151936, 1),
    "qwen3-coder:30b": (48, 4, 128, 2048, 151936, 1), "qwen3-coder:480b": (62, 8, 128, 6144, 151936, 1),
    "qwen3.5:9b": (32, 4, 256, 4096, 248320, 4), "qwen3.5:27b": (64, 4, 256, 5120, 248320, 4),
    "gemma3:270m": (18, 1, 256, 640, 262144, 1), "gemma3:1b": (26, 1, 256, 1152, 262144, 1),
    "gemma3:4b": (34, 4, 256, 2560, 262208, 1), "gemma3:12b": (48, 8, 256, 3840, 262208, 1),
    "gemma3:27b": (62, 16, 128, 5376, 262208, 1), "gemma2:2b": (26, 4, 256, 2304, 256000, 1),
    "gemma2:9b": (42, 8, 256, 3584, 256000, 1), "gemma2:27b": (46, 16, 128, 4608, 256000, 1),
    "mistral:7b": (32, 8, 128, 4096, 32768, 1), "mistral-nemo:12b": (40, 8, 128, 5120, 131072, 1),
    "mistral-small:24b": (40, 8, 128, 5120, 131072, 1), "phi3:3.8b": (32, 32, 96, 3072, 32064, 1),
    "phi3:14b": (40, 10, 128, 5120, 32064, 1), "phi4:14b": (40, 10, 128, 5120, 100352, 1),
    "gpt-oss:20b": (24, 8, 64, 2880, 201088, 1), "gpt-oss:120b": (36, 8, 64, 2880, 201088, 1),
    "deepseek-r1:671b": (61, 1, 288, 7168, 129280, 1),  # MLA: the 576-wide latent cached per layer
    "nomic-embed-text:latest": (12, 12, 64, 768, 30522, 1), "mxbai-embed-large:335m": (24, 16, 64, 1024, 30522, 1),
    "tinyllama:1.1b": (22, 4, 64, 2048, 32000, 1),
}
# a library model that is another family's weights: "<model>:<size>" -> the KNOWN key
ALIASES = {"deepseek-r1:1.5b": "qwen2.5:1.5b", "deepseek-r1:7b": "qwen2.5:7b", "deepseek-r1:8b": "qwen3:8b",
           "deepseek-r1:14b": "qwen2.5:14b", "deepseek-r1:32b": "qwen2.5:32b", "deepseek-r1:70b": "llama3.1:70b",
           "qwen2.5-coder:0.5b": "qwen2.5:0.5b", "qwen2.5-coder:1.5b": "qwen2.5:1.5b", "qwen2.5-coder:3b": "qwen2.5:3b",
           "qwen2.5-coder:7b": "qwen2.5:7b", "qwen2.5-coder:14b": "qwen2.5:14b", "qwen2.5-coder:32b": "qwen2.5:32b",
           "nomic-embed-text:v1.5": "nomic-embed-text:latest", "mxbai-embed-large:latest": "mxbai-embed-large:335m"}
GENERIC_KV_HEADS = 8
GENERIC_HEAD = 128


def _info(arch: str, t: tuple) -> dict:
    blocks, kv, head, embd, vocab, interval = t
    out = {"general.architecture": arch, f"{arch}.block_count": blocks, f"{arch}.attention.head_count_kv": kv,
           f"{arch}.attention.key_length": head, f"{arch}.attention.value_length": head,
           f"{arch}.embedding_length": embd, f"{arch}.vocab_size": vocab}
    if interval > 1:
        out[f"{arch}.full_attention_interval"] = interval
    return out


def key_of(name: str, size: str) -> str:
    return f"{str(name or '').split(':', 1)[0].lower()}:{str(size or '').lower()}"


def generic(params: Optional[float]) -> Optional[dict]:
    if not isinstance(params, (int, float)) or params <= 0:
        return None
    layers = max(8, int(round(9.8 * math.sqrt(params))))
    embd = int(max(1024, min(16384, round(1450 * math.sqrt(params) / 128) * 128)))
    return _info("generic", (layers, GENERIC_KV_HEADS, GENERIC_HEAD, embd, 0, 1))


def shape_for(name: str, size: str = "", params: Optional[float] = None, info: Optional[dict] = None) -> "tuple[Optional[dict], str]":
    if isinstance(info, dict) and info:
        return info, "the repo's config.json"
    key = key_of(name, size)
    key = ALIASES.get(key, key)
    if key in KNOWN:
        return _info(key.split(":", 1)[0].replace(".", "").replace("-", ""), KNOWN[key]), f"the published shape of {key} (estimate)"
    got = generic(params)
    if got is not None:
        return got, f"a typical shape for {params:g}B (estimate: this family's shape is not known here)"
    return None, "unknown (no size to estimate a shape from)"
