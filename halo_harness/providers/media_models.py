"""halo_harness.providers.media_models -- the media-model inventory (Halo
3.0.4.0 round R2): diffusion checkpoints, video models, upscalers, TTS and
their LoRAs, VAEs and encoders, keyed by what a model PRODUCES. These are a
different kind of asset from LLMs: nothing here is imported by the LLM
catalog (`model_enumeration`, `local_models`) or by any picker, so a
`comfy:` ref never shows up in `/model`, the roles table or the org tables.

A row is a dict: `{ref: "comfy:<file>", provider: "comfyui", folder, file,
kind, modalities_in, modalities_out, local: True, price_in_per_m: 0,
price_out_per_m: 0, size_bytes, quant, family, notes}`; `kind` is one of
image-gen | video-gen | upscale | tts | encoder | lora | vae | other. Only the
first four are generators (ranked by `capabilities.best_for_media`); the rest
are supporting rows, listed and never ranked.

`scan(client, state_dir)` reads the server (`GET /models/<folder>`, sizes from
`GET /experiment/models/<folder>`, `GET /object_info`) and writes
`<state_dir>/media-models.json` `{"scanned", "url", "rows", "workflows"}`;
`load_cached` and `rows_for` read it back with no network.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

CACHE_NAME = "media-models.json"
GENERATORS = ("image-gen", "video-gen", "upscale", "tts")
SUPPORTING = ("encoder", "lora", "vae", "other")
ALIASES = {"audio-gen": "tts", "audio": "tts", "image": "image-gen", "video": "video-gen"}
SKIP_FOLDERS = ("custom_nodes", "configs")
_FOLDER_KIND = {"loras": "lora", "vae": "vae", "text_encoders": "encoder", "clip": "encoder",
                "clip_vision": "encoder", "audio_encoders": "encoder", "upscale_models": "upscale"}
_WEIGHT_EXT = (".safetensors", ".sft", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx", ".pkl")
_VIDEO = re.compile(r"i2v|s2v|t2v|scail|(^|[^a-z])wan|ltx|hunyuan.?video|cogvideo|mochi|framepack")
_FAMILIES = (("qwen-image", r"qwen[_-]?image|qwen3vl"), ("seedvr", r"seedvr"), ("sam", r"^sam\d"),
             ("wan", r"(^|[^a-z])wan|scail|lightx2v|umt5"), ("flux", r"flux"), ("ltx", r"ltx"),
             ("hunyuan", r"hunyuan"), ("wav2vec", r"wav2vec"), ("clip", r"clip"))


def _quant(name: str) -> str:
    for label, pat in (("bf16", r"bf16"), ("fp8", r"fp8|e4m3|e5m2"), ("int8", r"int8|q8"), ("fp16", r"fp16|f16")):
        if re.search(rf"(?<![a-z0-9]){pat}(?![a-z0-9])", name):
            return label
    return "unknown"


def _family(name: str) -> str:
    for family, pat in _FAMILIES:
        if re.search(pat, name):
            return family
    return ""


def tts_nodes(object_info: Optional[dict]) -> list:
    """Engine node classes of a TTS suite in the server's /object_info."""
    out = []
    for cls, info in (object_info or {}).items():
        cat = str((info or {}).get("category") or "")
        if cat.lower().startswith(("partner", "comfy cloud")):
            continue
        if re.search(r"tts", cat, re.I) and cls.endswith("EngineNode"):
            out.append(cls)
    return sorted(out)


def classify(folder: str, filename: str, object_info: Optional[dict] = None) -> tuple:
    """`(kind, (modalities_in, modalities_out), family, quant)` for one file."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].lower()
    family, quant = _family(name), _quant(name)
    if folder == "TTS":
        parts = filename.replace("\\", "/").split("/")
        engine = parts[0].lower() if len(parts) > 1 else ""
        if tts_nodes(object_info):
            return "tts", (["text"], ["audio"]), engine, quant
        return "other", ([], []), engine, quant
    if folder in ("diffusion_models", "checkpoints", "unet"):
        if "seedvr" in name:
            return "upscale", (["image", "video"], ["image", "video"]), family, quant
        if family == "sam":
            return "other", (["image"], []), family, quant
        if _VIDEO.search(name):
            if "s2v" in name:
                mods = ["text", "audio"]
            elif "scail" in name:
                mods = ["text", "image", "video"]
            elif "i2v" in name:
                mods = ["text", "image"]
            else:
                mods = ["text"]
            return "video-gen", (mods, ["video"]), family or "video", quant
        return "image-gen", (["text", "image"] if "edit" in name else ["text"], ["image"]), family, quant
    kind = _FOLDER_KIND.get(folder, "other")
    if kind == "upscale":
        return kind, (["image"], ["image"]), family or Path(name).stem.split("_")[0], quant
    return kind, ([], []), family, quant


def _note(kind: str, name: str) -> str:
    n = name.lower()
    bits = []
    if re.search(r"4.?step", n):
        bits.append("4-step distill LoRA")
    if "high_noise" in n or "high-noise" in n:
        bits.append("high-noise expert (pairs with the low-noise model)")
    if "low_noise" in n or "low-noise" in n:
        bits.append("low-noise expert (pairs with the high-noise model)")
    if "scail" in n and kind == "video-gen":
        bits.append("pose-driven character animation")
    if kind == "other" and re.match(r"sam\d", n):
        bits.append("segmentation")
    return "; ".join(bits)


def _row(folder, file, size, kind, mods, family, quant, notes="") -> dict:
    return {"ref": "comfy:" + file.replace("\\", "/"), "provider": "comfyui", "folder": folder, "file": file, "kind": kind,
            "modalities_in": list(mods[0]), "modalities_out": list(mods[1]), "local": True, "price_in_per_m": 0,
            "price_out_per_m": 0, "size_bytes": size, "quant": quant, "family": family, "notes": notes}


def _tts_rows(files: list, sizes: dict, object_info: dict) -> list:
    engines = tts_nodes(object_info)
    groups: dict = {}
    for f in files:
        parts = f.replace("\\", "/").split("/")
        groups.setdefault(parts[0] if len(parts) > 1 else f, []).append(f)
    rows = []
    for top, members in sorted(groups.items()):
        kind, mods, family, quant = classify("TTS", members[0], object_info)
        known = [sizes[m] for m in members if m in sizes]
        engine = next((e for e in engines if top.lower().replace("-", "").replace("_", "") in e.lower()), "")
        note = f"{len(members)} file(s)" + (f"; engine node {engine}" if engine else "; no engine node of this name on the server")
        rows.append(_row("TTS", top, sum(known) if known else None, kind, mods, family or top.lower(), quant, note))
    return rows


def _folder_rows(folder: str, files: list, sizes: dict, object_info: dict) -> list:
    if folder == "TTS":
        return _tts_rows(files, sizes, object_info)
    out = []
    for f in files:
        if not f.lower().endswith(_WEIGHT_EXT):
            continue
        kind, mods, family, quant = classify(folder, f, object_info)
        out.append(_row(folder, f, sizes.get(f), kind, mods, family, quant, _note(kind, f)))
    return out


def cache_path(state_dir) -> Path:
    return Path(state_dir) / CACHE_NAME


def scan(client, state_dir) -> list:
    """Read the server, write the cache, return the rows (a ComfyError from
    the model listing propagates; a missing /object_info or size route does not)."""
    from halo_harness.media.comfy_client import ComfyError
    try:
        object_info = client.object_info()
    except ComfyError:
        object_info = {}
    rows, seen = [], set()
    for folder in client.model_folders():
        if folder in SKIP_FOLDERS:
            continue
        files = client.models(folder)
        if not files:
            continue
        for row in _folder_rows(folder, files, client.model_sizes(folder), object_info):
            if row["ref"] in seen:
                row["ref"] = f"comfy:{folder}/{row['file'].replace(chr(92), '/')}"
            seen.add(row["ref"])
            rows.append(row)
    try:
        workflows = client.workflows()
    except ComfyError:
        workflows = []
    doc = {"scanned": time.time(), "url": client.url, "rows": rows, "workflows": workflows}
    path = cache_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return rows


def load_cached(state_dir) -> dict:
    """The cached `{"scanned", "url", "rows", "workflows"}`, or `{}`."""
    try:
        doc = json.loads(cache_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) and isinstance(doc.get("rows"), list) else {}


def rows_for(kind: Optional[str] = None, state_dir=None) -> list:
    """Cached rows of one kind (`image-gen`, `audio-gen` for `tts`, ...) or all of them."""
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    rows = load_cached(state_dir).get("rows") or []
    if not kind or kind == "all":
        return rows
    kind = ALIASES.get(kind, kind)
    return [r for r in rows if r.get("kind") == kind]
