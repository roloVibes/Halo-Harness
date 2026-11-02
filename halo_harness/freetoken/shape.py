"""halo_harness.freetoken.shape -- a FreeToken checkpoint's sizes for the fit (Halo 3.3.9.1; local_sched/fit_ft.py):
what stays on the GPU (the dense layers: attention, embeddings, shared experts -- "active" here), what lives in host RAM
(the routed experts' banks, docs/models.md "MoE strategies": offload keeps the experts in host RAM and an LRU cache of
expert slots on the GPU; from the source, unverified against a live run), and the KV per token.

    of_dir(path) -> Shape | None     a checkpoint folder: its config.json (the text config of a multimodal one) and its
                                     bytes (the index's total_size, else the safetensors summed); the expert bytes from the config's expert count, the
                                     expert width, the hidden size and the MoE layers, at the format's bytes per weight
    of_row(row) -> Shape             a catalog row (freetoken/catalog.py) or a Library row: the weights from its
                                     parameter counts (total, active), no KV figure without a config; no counts:
                                     the name and the stated tables only (expert_bytes None)
    of_config(cfg, total_bytes, *, name, fmt) -> Shape
    Shape = {name, format, total_bytes, expert_bytes, dense_bytes, layer_expert_bytes, kv_per_token, ram_extra_bytes,
             nvme_bytes, from}

The arithmetic is the fit's estimate, said as one: three projections (gate, up, down) of hidden x expert width per
expert per MoE layer, and the KV as 2 (K and V) x the full-attention layers x the KV heads x the head size x 2 bytes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from halo_harness.freetoken.catalog import BPW, match

GIB = 2 ** 30


def _text(cfg: dict) -> dict:
    t = cfg.get("text_config") if isinstance(cfg.get("text_config"), dict) else None
    return {**cfg, **t} if t else cfg


def _int(cfg: dict, *keys) -> Optional[int]:
    for k in keys:
        v = cfg.get(k)
        if isinstance(v, int) and not isinstance(v, bool) and v > 0:
            return v
    return None


def fmt_of(cfg: dict, name: str = "") -> str:
    q = cfg.get("quantization_config") if isinstance(cfg.get("quantization_config"), dict) else {}
    words = f"{q.get('quant_method', '')} {q.get('quant_algo', '')} {name}".lower()
    for f in ("nvfp4", "mxfp4", "fp8"):
        if f in words:
            return f
    return "fp4" if "fp4" in words else "bf16"


def _full_layers(cfg: dict, layers: int) -> int:
    kinds = cfg.get("layer_types")
    if isinstance(kinds, list) and kinds:
        return sum(1 for k in kinds if "full" in str(k)) or layers
    every = _int(cfg, "full_attention_interval")
    return max(1, layers // every) if every else layers


def of_config(cfg: dict, total_bytes: Optional[int], *, name: str, fmt: str = "") -> dict:
    c = _text(cfg if isinstance(cfg, dict) else {})
    fmt = fmt or fmt_of(c, name)
    bpw = BPW.get(fmt, 2.0)
    layers = _int(c, "num_hidden_layers", "n_layers") or 0
    hidden = _int(c, "hidden_size", "d_model") or 0
    experts = _int(c, "num_experts", "n_routed_experts", "num_local_experts") or 0
    width = _int(c, "moe_intermediate_size", "expert_intermediate_size") or (
        _int(c, "intermediate_size") if _int(c, "num_local_experts") else None) or 0
    moe_layers = max(0, layers - (_int(c, "first_k_dense_replace") or 0))
    expert_bytes = int(moe_layers * experts * 3 * hidden * width * bpw)
    kv_heads = _int(c, "num_key_value_heads", "num_attention_heads") or 0
    head = _int(c, "head_dim") or (hidden // (_int(c, "num_attention_heads") or 1) if hidden else 0)
    kv = 2 * _full_layers(c, layers) * kv_heads * head * 2 if layers and kv_heads and head else None
    total = total_bytes if isinstance(total_bytes, int) and total_bytes > 0 else None
    if total is None and expert_bytes:
        total = expert_bytes + int(layers * 12 * hidden * hidden * bpw)  # an estimate: the experts plus the dense layers
    expert_bytes = min(expert_bytes, int(total * 0.97)) if total else expert_bytes
    row = match(name) or {}
    return {"name": name, "format": fmt, "total_bytes": total, "expert_bytes": expert_bytes or None,
            "dense_bytes": (total - expert_bytes) if total and expert_bytes else None,
            "layer_expert_bytes": expert_bytes // moe_layers if moe_layers and expert_bytes else None,
            "kv_per_token": kv, "ram_extra_bytes": int(float(row.get("ram_extra_gib") or 0) * GIB),
            "nvme_bytes": int(float(row.get("nvme_gib") or 0) * GIB), "from": "the checkpoint's config.json"}


def of_dir(path) -> Optional[dict]:
    p = Path(path).expanduser()
    try:
        cfg = json.loads((p / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:  # a sharded checkpoint's index states its tensors' bytes (metadata.total_size)
        total = int(json.loads((p / "model.safetensors.index.json").read_text(encoding="utf-8"))["metadata"]["total_size"])
    except (OSError, ValueError, KeyError, TypeError):
        total = 0
    for f in p.glob("*.safetensors") if not total else ():
        try:
            total += f.stat().st_size
        except OSError:
            continue
    out = of_config(cfg, total or None, name=p.name)
    if not total:
        out["from"] += " (no safetensors on disk yet: the size is an estimate)"
    return out


def of_row(row: dict) -> Optional[dict]:
    """A catalog or Library row with parameter counts -> the split from the counts (active = what stays on the GPU)."""
    hit = match(row.get("repo") or row.get("id") or row.get("name") or "") or {}
    total_b = row.get("total_b") or row.get("params") or hit.get("total_b")
    active_b = row.get("active_b") or hit.get("active_b")
    fmt = str(row.get("format") or row.get("quant") or hit.get("format") or "bf16").lower()
    if not total_b or not active_b:  # the counts unknown: the name and the tables FreeToken states, no split
        return {"name": hit.get("name") or row.get("name"), "format": fmt, "total_bytes": None, "expert_bytes": None,
                "dense_bytes": None, "layer_expert_bytes": None, "kv_per_token": None,
                "ram_extra_bytes": int(float(hit.get("ram_extra_gib") or 0) * GIB),
                "nvme_bytes": int(float(hit.get("nvme_gib") or 0) * GIB), "from": "not stated: download it"}
    bpw = BPW.get(fmt, 2.0)
    total = int(float(total_b) * 1e9 * bpw)
    dense = int(float(active_b) * 1e9 * bpw)
    return {"name": hit.get("name") or row.get("name"), "format": fmt, "total_bytes": total,
            "expert_bytes": total - dense, "dense_bytes": dense, "layer_expert_bytes": None, "kv_per_token": None,
            "ram_extra_bytes": int(float(hit.get("ram_extra_gib") or 0) * GIB),
            "nvme_bytes": int(float(hit.get("nvme_gib") or 0) * GIB),
            "from": f"the parameter counts ({total_b:g}B total, {active_b:g}B active, {hit.get('params_from') or 'the row'})"}
