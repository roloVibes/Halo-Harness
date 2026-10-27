"""halo_harness.providers.ollama_fit_parts -- Halo 3.3.4.0 R3: what a model
at a window really needs on a card (ollama_steward/knowledge/memory.md is
the spec; every constant below is a measured or cited figure there).

    kv_layers(model_info)            the layers that hold a KV cache: a hybrid
                                     model (`<arch>.full_attention_interval` N)
                                     caches one layer in N, a draft layer
                                     (`<arch>.nextn_predict_layers`) is not one
                                     of them, a per-layer `head_count_kv` list
                                     counts its non-zero entries
    kv_bytes(model_info, bpe)        the KV cache per token (summed over those
                                     layers, a list's own head counts used)
    recurrent_bytes(model_info)      a hybrid model's fixed recurrent state per
                                     sequence (`<arch>.ssm.*`, f32)
    load_parts(...)                  every part of one load, in bytes: weights,
                                     KV (window x parallel), recurrent state,
                                     the draft layer's f16 cache and compute,
                                     the compute buffer, the vision projector
    reserve_bytes(...)               what the loader keeps free per card:
                                     Ollama's minimum (457 MiB CUDA, 512 Metal)
                                     + OLLAMA_GPU_OVERHEAD, or -- the layers
                                     left to llama.cpp's --fit (num_gpu unset)
                                     -- its 1,024 MiB margin + the projector
    fit_window(...)                  the largest window (a power of two, or a
                                     multiple of `step`) whose parts + reserve
                                     fit the free bytes

Pure arithmetic: no I/O. `providers.ollama_fit.kv_bytes_per_token` counts
its layers through `kv_layers`, and `providers.ollama_hw` and the steward's
fit planner (ollama_steward/fit.py) call `fit_window`.
"""

from __future__ import annotations

from typing import Optional

MIB = 2 ** 20
CUDA_MIN_FREE = 457 * MIB      # Ollama's per-device minimum on CUDA [S3][S11]
METAL_MIN_FREE = 512 * MIB     # ... and on Metal
FIT_MARGIN = 1024 * MIB        # llama.cpp --fit's margin per device when num_gpu is unset [S4][S12]
COMPUTE_BASE = 33 * MIB        # the compute buffer's fixed part (fitted to the measured 27B 420 MiB and 30B 252 MiB at 65,536)
ACT_BYTES = 27                 # ... plus this many bytes per embedding unit per micro-batch token
UBATCH = 512                   # Ollama's -ub
DRAFT_COMPUTE = 130 * MIB      # the draft context's own compute buffer (measured 130.02 MiB)
DRAFT_RS_SEQS = 4              # the recurrent state's extra sequences for the draft ("1 seqs 4 rs_seq")
PROJECTOR_DEFAULT = 1161 * MIB  # the measured worst case of a vision projector, when only "vision" is known
PROJECTOR_FILE_SHARE = 912 / 1161  # its file (what Ollama adds to --fit's margin) against that worst case
EMBD_BYTES_PER_PARAM = 0.5625  # the token embedding stays in RAM; Q4_K is the smallest it is stored at
WINDOW_MIN = 2048
WINDOW_MAX = 2 ** 20


def _num(info: dict, suffix: str) -> Optional[float]:
    for key, value in (info or {}).items():
        if key.endswith(suffix) and isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _list(info: dict, suffix: str) -> Optional[list]:
    for key, value in (info or {}).items():
        if key.endswith(suffix) and isinstance(value, list) and value:
            if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
                return [float(v) for v in value]
    return None


def head_counts(model_info: dict) -> Optional[list]:
    """The KV head count of each layer that holds a cache (None when unknown)."""
    per_layer = _list(model_info, ".attention.head_count_kv")
    if per_layer is not None:
        return [h for h in per_layer if h > 0] or None
    blocks = _num(model_info, ".block_count")
    heads = _num(model_info, ".attention.head_count_kv")
    if not blocks or not heads:
        return None
    layers = int(blocks) - int(_num(model_info, ".nextn_predict_layers") or 0)
    interval = int(_num(model_info, ".full_attention_interval") or 1)
    if interval > 1:
        layers = layers // interval
    return [heads] * max(1, layers)


def kv_layers(model_info: dict) -> Optional[int]:
    hc = head_counts(model_info)
    return len(hc) if hc else None


def _per_head(model_info: dict) -> Optional[float]:
    k = _num(model_info, ".attention.key_length")
    v = _num(model_info, ".attention.value_length")
    if k and v:
        return k + v
    embd = _num(model_info, ".embedding_length")
    heads = _num(model_info, ".attention.head_count") or _num(model_info, ".attention.head_count_kv")
    if not embd or not heads:
        return None
    return 2.0 * embd / heads


def kv_bytes(model_info: dict, bytes_per_elem: float = 2.0) -> Optional[float]:
    """KV cache bytes per token of the main model (the draft layer apart)."""
    hc, per_head = head_counts(model_info), _per_head(model_info)
    if not hc or not per_head:
        return None
    return sum(hc) * per_head * bytes_per_elem


def draft_layers(model_info: dict) -> int:
    return int(_num(model_info, ".nextn_predict_layers") or 0)


def recurrent_bytes(model_info: dict) -> float:
    """A hybrid model's recurrent state for one sequence: per linear layer,
    (conv_kernel - 1) x (inner + 2 x groups x state) + state x inner, in f32."""
    conv, state = _num(model_info, ".ssm.conv_kernel"), _num(model_info, ".ssm.state_size")
    inner, groups = _num(model_info, ".ssm.inner_size"), _num(model_info, ".ssm.group_count") or 1.0
    blocks = _num(model_info, ".block_count")
    if not (conv and state and inner and blocks):
        return 0.0
    layers = int(blocks) - draft_layers(model_info)
    linear = layers - (kv_layers(model_info) or 0)
    if linear <= 0:
        return 0.0
    per_layer = (conv - 1) * (inner + 2 * groups * state) + state * inner
    return linear * per_layer * 4.0


def compute_bytes(model_info: dict, window: int) -> float:
    """The compute buffer: a fixed part, plus per token of the window the
    attention mask (f16 x the micro-batch) and one layer's K and V in f16."""
    embd = _num(model_info, ".embedding_length") or 4096.0
    heads = max(head_counts(model_info) or [8.0])
    per_head = _per_head(model_info) or 256.0
    return COMPUTE_BASE + embd * UBATCH * ACT_BYTES + window * (2 * UBATCH + heads * per_head * 2)


def embedding_on_host(model_info: dict) -> float:
    """The token embedding llama.cpp keeps in system RAM (0 when the vocabulary is unknown)."""
    vocab = _num(model_info, ".vocab_size")
    tokens = _list(model_info, "tokenizer.ggml.tokens") if vocab is None else None
    embd = _num(model_info, ".embedding_length")
    vocab = vocab or (len(tokens) if tokens else None)
    return vocab * embd * EMBD_BYTES_PER_PARAM if vocab and embd else 0.0


def projector_for(row: Optional[dict]) -> int:
    """The vision projector's worst-case bytes for a catalog row: 0 for a model without vision."""
    row = row or {}
    caps = row.get("capabilities") if isinstance(row.get("capabilities"), list) else []
    info = row.get("projector_info") if isinstance(row.get("projector_info"), dict) else {}
    if "vision" not in caps and not info:
        return 0
    params = _num(info, "parameter_count")
    if params:
        return int(params * 2)
    blocks, embd = _num(info, "vision.block_count"), _num(info, "vision.embedding_length")
    if blocks and embd:
        return int(12 * blocks * embd * embd * 2 * 1.3)  # f16 weights + the worst-case activations
    return PROJECTOR_DEFAULT


def load_parts(model_info: dict, *, weight_bytes: int, window: int, bytes_per_elem: float = 2.0,
               parallel: int = 1, projector_bytes: int = 0, draft: Optional[bool] = None) -> Optional[dict]:
    """Every part of one load in bytes (None when the model's shape is unknown)."""
    kv = kv_bytes(model_info, bytes_per_elem)
    if kv is None or not isinstance(weight_bytes, (int, float)) or weight_bytes <= 0:
        return None
    parallel = max(1, int(parallel or 1))
    has_draft = draft_layers(model_info) > 0 if draft is None else bool(draft)
    hc, per_head = head_counts(model_info) or [0.0], _per_head(model_info) or 0.0
    draft_kv = draft_layers(model_info) * max(hc) * per_head * 2.0 * window if has_draft else 0.0
    seqs = parallel + (DRAFT_RS_SEQS if has_draft and recurrent_bytes(model_info) else 0)
    parts = {
        "weights": float(weight_bytes) - embedding_on_host(model_info),
        "kv": kv * window * parallel,
        "recurrent": recurrent_bytes(model_info) * seqs,
        "draft": draft_kv + (DRAFT_COMPUTE if has_draft else 0.0),
        "compute": compute_bytes(model_info, window),
        "projector": float(projector_bytes or 0),
    }
    parts["total"] = sum(parts.values())
    return parts


def reserve_bytes(*, forced: bool = True, metal: bool = False, gpu_overhead: int = 0,
                  projector_bytes: int = 0) -> int:
    minimum = (METAL_MIN_FREE if metal else CUDA_MIN_FREE) + max(0, int(gpu_overhead or 0))
    if forced:
        return minimum
    return max(minimum, FIT_MARGIN + int((projector_bytes or 0) * PROJECTOR_FILE_SHARE))


def _windows(step: Optional[int], top: int):
    if step:
        w = (top // step) * step
        while w >= WINDOW_MIN:
            yield w
            w -= step
        return
    w = WINDOW_MAX
    while w >= WINDOW_MIN:
        if w <= top:
            yield w
        w //= 2


def fit_window(model_info: dict, *, weight_bytes: int, free_bytes, bytes_per_elem: float = 2.0,
               parallel: int = 1, projector_bytes: int = 0, forced: bool = True, metal: bool = False,
               gpu_overhead: int = 0, cards: int = 1, draft: Optional[bool] = None,
               step: Optional[int] = None, top: int = WINDOW_MAX):
    """The largest window whose parts + the reserve (once per card) fit
    `free_bytes`; None when an input is unknown, `ollama_fit.WEIGHTS_DO_NOT_FIT`
    when not even the smallest window fits."""
    from halo_harness.providers.ollama_fit import WEIGHTS_DO_NOT_FIT
    if not isinstance(free_bytes, (int, float)) or isinstance(free_bytes, bool) or free_bytes <= 0:
        return None
    if load_parts(model_info, weight_bytes=weight_bytes, window=WINDOW_MIN, bytes_per_elem=bytes_per_elem) is None:
        return None
    budget = free_bytes - reserve_bytes(forced=forced, metal=metal, gpu_overhead=gpu_overhead,
                                        projector_bytes=projector_bytes) * max(1, cards)
    for w in _windows(step, top):
        parts = load_parts(model_info, weight_bytes=weight_bytes, window=w, bytes_per_elem=bytes_per_elem,
                           parallel=parallel, projector_bytes=projector_bytes, draft=draft)
        if parts["total"] <= budget:
            return w
    return WEIGHTS_DO_NOT_FIT


def need_bytes(model_info: dict, *, weight_bytes: int, window: int, forced: bool = True, metal: bool = False,
               gpu_overhead: int = 0, **kw) -> Optional[float]:
    """The bytes one load at `window` takes off a card, the reserve included."""
    parts = load_parts(model_info, weight_bytes=weight_bytes, window=window, **kw)
    if parts is None:
        return None
    return parts["total"] + reserve_bytes(forced=forced, metal=metal, gpu_overhead=gpu_overhead,
                                          projector_bytes=kw.get("projector_bytes", 0))
