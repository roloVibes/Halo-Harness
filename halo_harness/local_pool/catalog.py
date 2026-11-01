"""halo_harness.local_pool.catalog -- the pool's model catalog (Halo 3.3.8.0 R1), the rows of
plans/pooled-inference-model-candidates.md (Tier 1 and 2) with their facts. Every estimate says so: `measured: false`
on a speed that was extrapolated or comes from a class of setups, and a `*_from` line on each figure that is not a
published measurement.

    Row = {name, display, repo, file, weights_gb, total_b, active_b, kv_bytes_per_token, kv_from, routing_table_gb,
           routing_from, min_build, batch_only, speed {tok_s_low, tok_s_high, measured, source}, single_node, tier}
    CATALOG: {name: Row}     ORDER: the candidates doc's rank     get(name) -> Row | None (a display name or repo too)

weights_gb is the GGUF's size (GB = 2^30 bytes, as the host cards count). kv_bytes_per_token is the F16 KV cache per
token across every layer (Q8_0 halves it). routing_table_gb is the expert routing data llama.cpp RPC replicates to
EVERY device (measured ~20 GB for gpt-oss-120b regardless of the split); a dense model has none. min_build is the
llama.cpp build a model needs (Qwen3-Next: b7186+). `repo` and `file` are what the one Download button fetches
(the existing Hugging Face download + verify job; `file` may be a quantization the job picks the files by).
"""

from __future__ import annotations

from typing import Optional

CATALOG = {
    "qwen3-next-80b-a3b-q4km": {
        "name": "qwen3-next-80b-a3b-q4km", "display": "Qwen3-Next-80B-A3B Q4_K_M", "tier": 1,
        "repo": "Qwen/Qwen3-Next-80B-A3B-Instruct-GGUF", "file": "Q4_K_M",
        "weights_gb": 46.0, "total_b": 80.0, "active_b": 3.0,
        "kv_bytes_per_token": 102400, "kv_from": "an estimate from the model's shape (hybrid attention; no measured figure)",
        "routing_table_gb": 2.0, "routing_from": "an estimate: 512 experts route far less than gpt-oss's measured 20 GB",
        "min_build": 7186, "batch_only": False,
        "speed": {"tok_s_low": 30.0, "tok_s_high": 45.0, "measured": False,
                  "source": "extrapolated from the measured 28-55 % RPC penalty; no published RPC number for this model"},
        "single_node": "one 48 GB card runs it at Q4 (53-89 tok/s reported): if a node has 48 GB, do not pool it"},
    "gpt-oss-120b": {
        "name": "gpt-oss-120b", "display": "gpt-oss-120b MXFP4", "tier": 1,
        "repo": "ggml-org/gpt-oss-120b-GGUF", "file": "",
        "weights_gb": 59.0, "total_b": 117.0, "active_b": 5.1,
        "kv_bytes_per_token": 327680, "kv_from": "an estimate: the 70B-class 320 KB per token (no gpt-oss figure)",
        "routing_table_gb": 20.0, "routing_from": "measured: ~20 GB replicated to every RPC device regardless of the split",
        "min_build": None, "batch_only": False,
        "speed": {"tok_s_low": 33.8, "tok_s_high": 33.8, "measured": True,
                  "source": "measured 33.8 tok/s on a 2-node layer split vs 42.7 on one node (llamaperf.com), not on this "
                            "pool"},
        "single_node": "a 64-80 GB box serves it at ~30-58 tok/s: pool it only when no node holds it"},
    "llama-3.3-70b-q4km": {
        "name": "llama-3.3-70b-q4km", "display": "Llama 3.3 70B Q4_K_M", "tier": 2,
        "repo": "unsloth/Llama-3.3-70B-Instruct-GGUF", "file": "Q4_K_M",
        "weights_gb": 42.5, "total_b": 70.0, "active_b": 70.0,
        "kv_bytes_per_token": 327680, "kv_from": "80 layers, 8 KV heads, 128 dims at F16: 320 KB per token",
        "routing_table_gb": 0.0, "routing_from": "dense: no routing tables",
        "min_build": None, "batch_only": True,
        "speed": {"tok_s_low": 3.0, "tok_s_high": 6.0, "measured": False,
                  "source": "the measured class (2.8 tok/s at 1 GbE, 5.9 at 10 GbE, 4.9-5.5 all-GPU RPC; single "
                            "sources), not this model on this pool"},
        "single_node": "a 48 GB card holds it at 16k"},
}
ORDER = tuple(CATALOG)


def get(name: str) -> Optional[dict]:
    """A catalog row by its name, its display name or its repo (case-insensitive), else None."""
    n = str(name or "").strip().lower()
    for row in CATALOG.values():
        if n in (row["name"], row["display"].lower(), row["repo"].lower()):
            return row
    return None


def names() -> list:
    return list(ORDER)
