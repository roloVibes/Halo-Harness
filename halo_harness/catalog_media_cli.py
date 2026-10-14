"""halo_harness.catalog_media_cli -- the media-model side of `halo models`
(Halo 3.0.4.0 round R2):

    halo models --media [image|video|audio|all] [--refresh] [--json]
    halo models --best-for image-gen|video-gen|audio-gen|upscale [--refresh]
    halo media models [image|video|audio] [--url U]

All three print the ComfyUI inventory (`providers.media_models`) grouped by
what a model produces, with size, quant and family, then the supporting rows
(loras, vaes, encoders) that are listed and never ranked. The inventory is
read from `~/.halo/media-models.json`; `--refresh` (or no cache yet) rescans
the server named by `COMFY_URL` / `comfy.url`.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Optional

from halo_harness.providers import media_models as MM

MODALITIES = {"image": ("image-gen", "upscale"), "video": ("video-gen",), "audio": ("tts",), "all": MM.GENERATORS}
_SUPPORT_FOLDERS = {"audio": ("audio_encoders", "voices", "TTS")}  # TTS weights without an engine node on the server


def _size(n) -> str:
    return f"{n / 1e9:.1f} GB" if isinstance(n, (int, float)) and n >= 0 else "?"


def _line(r: dict) -> str:
    return f"  {r['file']:<58} {_size(r.get('size_bytes')):>9}  {r.get('quant', '?'):<7} {r.get('family') or '-'}"


def format_lines(doc: dict, modality: str = "all") -> list:
    rows = doc.get("rows") or []
    kinds = MODALITIES[modality]
    gens = [r for r in rows if r.get("kind") in kinds]
    families = {r.get("family") for r in gens if r.get("family")}
    support = [r for r in rows if r.get("kind") in MM.SUPPORTING]
    if modality != "all":
        folders = _SUPPORT_FOLDERS.get(modality, ())
        support = [r for r in support if r.get("family") in families or r.get("folder") in folders]
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(doc["scanned"])) if doc.get("scanned") else "never"
    out = [f"ComfyUI media models at {doc.get('url', '?')} (scanned {when}): {len(gens)} generator(s), "
           f"{len(support)} supporting"]
    for kind in kinds:
        group = [r for r in gens if r["kind"] == kind]
        if group:
            out.append(f"{kind} ({len(group)})")
            out += [_line(r) + (f"   {r['notes']}" if r.get("notes") else "") for r in group]
    if support:
        out.append("supporting (listed, never ranked)")
        for kind in MM.SUPPORTING:
            group = [r for r in support if r["kind"] == kind]
            if group:
                out.append(f"{kind} ({len(group)})")
                out += [_line(r) for r in group]
    if not gens and not support:
        out.append("no model files for this on that server")
    return out


def load_or_scan(refresh: bool, url: Optional[str] = None) -> dict:
    """The cached inventory, or a fresh scan (`--refresh`, no cache yet, or `url` given)."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.media.comfy_client import ComfyClient, resolve_url
    state_dir = bridge_home()
    if not refresh and not url:
        doc = MM.load_cached(state_dir)
        if doc:
            return doc
    MM.scan(ComfyClient((url or resolve_url()).rstrip("/"), timeout=30), state_dir)
    return MM.load_cached(state_dir)


def cmd_media_inventory(modality: str = "all", *, refresh: bool = False, as_json: bool = False, url: Optional[str] = None) -> int:
    from halo_harness.media.comfy_client import ComfyError
    modality = modality or "all"
    try:
        doc = load_or_scan(refresh, url)
    except ComfyError as e:
        print(f"halo models --media: {e}", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps({**doc, "rows": [r for r in doc["rows"] if modality == "all" or r["kind"] in MODALITIES[modality]
                                         or r["kind"] in MM.SUPPORTING]}, indent=1, ensure_ascii=False))
        return 0
    print("\n".join(format_lines(doc, modality)))
    return 0


def cmd_best_for_media(kind: str, *, refresh: bool = False) -> int:
    from halo_harness.capabilities import best_for_media
    from halo_harness.media.comfy_client import ComfyError
    try:
        doc = load_or_scan(refresh)
    except ComfyError as e:
        print(f"halo models --best-for {kind}: {e}", file=sys.stderr)
        return 1
    ranked = best_for_media(doc.get("rows") or [], kind)
    if not ranked:
        print(f"No {kind} model in the ComfyUI inventory at {doc.get('url', '?')}; `halo models --media --refresh` rescans it.")
        return 1
    print(f"Best for {kind} (ComfyUI media models at {doc.get('url', '?')}; size, quant and a 4-step LoRA; score 0-1):")
    for i, r in enumerate(ranked, 1):
        print(f"{i:>2}. {r['ref']:<52} {r['score']:.2f}  {r['chips']:<14} {r['reason']}")
    return 0
