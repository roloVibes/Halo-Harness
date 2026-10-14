"""halo_harness.capabilities_media -- `best_for_media(rows, kind)` (Halo
3.0.4.0 round R2): ranks the ComfyUI inventory (`providers.media_models`
rows) for one output kind. Facts only: the file size on disk (bigger = more
parameters = quality), the quantization (bf16 > fp16 > fp8 > int8), and a
4-step distill LoRA for the same family (a speed chip, a small bonus).
Supporting rows (loras, vaes, encoders, other) are never ranked.
"""

from __future__ import annotations

import re
from typing import Iterable

from halo_harness.capabilities import OUTPUT_KINDS

_ROW_KIND = {"image-gen": "image-gen", "video-gen": "video-gen", "audio-gen": "tts", "upscale": "upscale"}
_QUANT = {"bf16": 1.0, "fp16": 0.9, "fp8": 0.6, "int8": 0.5, "unknown": 0.4}


def _gb(n) -> str:
    return f"{n / 1e9:.1f} GB"


def _tok(pattern: str, text: str) -> str:
    m = re.search(pattern, text.lower())
    return m.group(0).replace("_", ".") if m else ""


def four_step_loras(rows: Iterable[dict]) -> list:
    """The LoRA rows that name a 4-step (or step) distill."""
    return [r for r in rows if r.get("kind") == "lora" and re.search(r"4.?step|step_distill", str(r.get("file", "")).lower())]


def _fit(row: dict, lo: dict):
    """How well a speed LoRA fits a model (None = not for this model): same family,
    same i2v/t2v/s2v/scail mode, same version (2.1 vs 2.2) and noise expert when both name one."""
    if not row.get("family") or lo.get("family") != row.get("family"):
        return None
    a, b = str(row.get("file", "")), str(lo.get("file", ""))
    best = 0
    for pat, weight in ((r"i2v|t2v|s2v|scail", 2), (r"(?<!\d)\d[._]\d(?!\d)", 2), (r"high|low", 1)):
        x, y = _tok(pat, a), _tok(pat, b)
        if x and y:
            if x != y:
                return None
            best += weight
    return best


def _speed_lora(row: dict, loras: list):
    fits = [(f, lo["file"], lo) for lo in loras for f in [_fit(row, lo)] if f is not None]
    return max(fits, key=lambda t: (t[0], t[1]))[2] if fits else None


def best_for_media(rows: Iterable[dict], kind: str, *, limit: int = 10) -> list:
    """The top `limit` generators for `kind` (image-gen | video-gen | audio-gen | upscale),
    each `{ref, score, reason, chips, provider, kind, family, size_bytes, quant}`."""
    if kind not in OUTPUT_KINDS:
        raise ValueError(f"unknown kind {kind!r}; one of {', '.join(OUTPUT_KINDS)}")
    rows = [r for r in rows if r.get("ref")]
    cands = [r for r in rows if r.get("kind") == _ROW_KIND[kind]]
    loras = four_step_loras(rows)
    top = max([r["size_bytes"] for r in cands if isinstance(r.get("size_bytes"), (int, float))] or [0])
    ranked = []
    for r in cands:
        size, quant = r.get("size_bytes"), r.get("quant") or "unknown"
        size_s = (size / top) if top and isinstance(size, (int, float)) else 0.5
        lora = _speed_lora(r, loras)
        score = 0.55 * size_s + 0.4 * _QUANT.get(quant, 0.4) + (0.05 if lora else 0.0)
        why = [_gb(size) if isinstance(size, (int, float)) else "size unknown", quant]
        if r.get("family"):
            why.append(r["family"])
        if lora:
            why.append("4-step LoRA " + str(lora["file"]))
        chips = " ".join([quant] + (["4-step"] if lora else []))
        ranked.append({"ref": r["ref"], "score": round(score, 3), "reason": ", ".join(why), "chips": chips,
                       "provider": r.get("provider", "comfyui"), "kind": r["kind"], "family": r.get("family", ""),
                       "size_bytes": size, "quant": quant})
    ranked.sort(key=lambda x: (-x["score"], x["ref"]))
    return ranked[:limit]
