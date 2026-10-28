"""halo_harness.models_library.ollama_registry -- Halo 3.3.5.0 R2: what Ollama's registry says of a tag.

    manifest_url(model, tag)   https://registry.ollama.ai/v2/library/<model>/manifests/<tag>
    parse_manifest(obj) -> {weights, projector, total, layers [{type, size}], config_digest}
    parse_config(obj) -> {format, family, families, params (billions), quant}
    manifest(state_dir, model, tag, refresh=False) -> {weights, projector, total, family, params, quant, source} | None

The registry is an OCI distribution: the manifest lists the layers by media type with their bytes --
`application/vnd.ollama.image.model` is the weights (the GGUF), `.projector` a vision projector, `.params`,
`.template`, `.license` the small text parts -- and its `config` blob (a few hundred bytes) says the family
(`model_family`), the size (`model_type`, "9.0B") and the quantization (`file_type`, "Q4_K_M"). Only those two
small JSON documents are read; no layer is fetched. `/v2/library/<model>/tags/list` answers 404 on this
registry (2026-10-28), so the tag names come from the tags page (ollama_library.py). Under
BRIDGE_TEST_NO_BACKGROUND_NET the snapshot's manifests answer.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from halo_harness.models_library import cache, snapshot

REGISTRY = "https://registry.ollama.ai/v2/library"
ACCEPT = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
MODEL = "application/vnd.ollama.image.model"
PROJECTOR = "application/vnd.ollama.image.projector"


def manifest_url(model: str, tag: str) -> str:
    return f"{REGISTRY}/{model}/manifests/{tag or 'latest'}"


def blob_url(model: str, digest: str) -> str:
    return f"{REGISTRY}/{model}/blobs/{digest}"


def parse_manifest(obj) -> dict:
    if isinstance(obj, str):
        obj = json.loads(obj)
    layers = obj.get("layers") if isinstance(obj, dict) else None
    if not isinstance(layers, list):
        raise ValueError("a registry manifest without layers")
    rows = [{"type": str(x.get("mediaType") or "").rsplit(".", 1)[-1], "size": int(x.get("size") or 0),
             "media_type": x.get("mediaType")} for x in layers if isinstance(x, dict)]
    weights = sum(x["size"] for x in rows if x["media_type"] == MODEL)
    projector = sum(x["size"] for x in rows if x["media_type"] == PROJECTOR)
    cfg = obj.get("config") if isinstance(obj.get("config"), dict) else {}
    return {"weights": weights or None, "projector": projector, "total": sum(x["size"] for x in rows),
            "layers": [{"type": x["type"], "size": x["size"]} for x in rows], "config_digest": cfg.get("digest")}


def _billions(text) -> Optional[float]:
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([BMK])\s*$", str(text or ""), re.I)
    if not m:
        return None
    n, u = float(m.group(1)), m.group(2).upper()
    return round(n if u == "B" else n / 1e3 if u == "M" else n / 1e6, 3)


def parse_config(obj) -> dict:
    if isinstance(obj, str):
        obj = json.loads(obj)
    obj = obj if isinstance(obj, dict) else {}
    fams = obj.get("model_families") if isinstance(obj.get("model_families"), list) else []
    return {"format": obj.get("model_format") or "", "family": obj.get("model_family") or (fams[0] if fams else ""),
            "families": fams, "params": _billions(obj.get("model_type")), "quant": obj.get("file_type") or ""}


def manifest(state_dir, model: str, tag: str, *, refresh: bool = False) -> Optional[dict]:
    """The tag's bytes and config, live (a day in the cache) or the snapshot's; None when neither knows."""
    model, tag = str(model or "").split(":", 1)[0], str(tag or "latest")
    snap = snapshot.manifest_of(model, tag)
    if cache.offline() and "fetch" not in cache.SEAMS:
        return {**snap, "source": f"snapshot {snapshot.taken()}"} if snap else None

    def _both(text: str) -> dict:
        m = parse_manifest(text)
        conf = {}
        if m.get("config_digest"):
            try:
                conf = parse_config(cache.fetch(blob_url(model, m["config_digest"])))
            except (cache.FetchError, ValueError):
                conf = {}
        return {"weights": m["weights"], "projector": m["projector"], "total": m["total"], "layers": m["layers"], **conf}

    try:
        got, _at, _how = cache.cached(state_dir, f"ollama:manifest:{model}:{tag}", manifest_url(model, tag),
                                      cache.CATALOG_TTL_S, _both, refresh=refresh, headers=ACCEPT)
        return {**got, "source": "registry.ollama.ai manifest"}
    except (cache.FetchError, ValueError):
        return {**snap, "source": f"snapshot {snapshot.taken()}"} if snap else None
