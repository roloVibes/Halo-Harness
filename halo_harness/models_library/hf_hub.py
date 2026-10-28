"""halo_harness.models_library.hf_hub -- Halo 3.3.5.0 R2: the Hugging Face Hub's own API, for GGUF and MLX repos.

    search_url(q, kind, limit=50)  GET https://huggingface.co/api/models?filter=gguf|mlx&search=&sort=downloads&limit=
                                   (+ expand[] for gated, lastModified, downloads, likes, tags, pipeline_tag)
    parse_search(items, kind) -> [repo]   {id, downloads, likes, tags, pipeline_tag, updated, gated, private,
                                   license, base_model, kind}
    parse_repo(obj) -> {...}       GET /api/models/<repo>?blobs=true: the files with their sizes (a GGUF repo: one
                                   file per quant, shards summed; an MLX repo: its safetensors as one), gated,
                                   private, cardData.license, pipeline_tag, gguf.context_length / architecture
    shape_from_config(cfg)         the repo's config.json as a `model_info` (layers, heads, head size, vocab): the
                                   family shape for the memory arithmetic
    search(state_dir, q, kind) / repo(state_dir, repo_id) / config(state_dir, repo_id, gated) -- the sources

The token (HF_TOKEN, the env file) is sent only for a gated repo's files and config. Under
BRIDGE_TEST_NO_BACKGROUND_NET the sources answer from tests/fixtures/library (cache.fixture) and say "fixtures".
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Optional

from halo_harness.models_library import cache

API = "https://huggingface.co/api/models"
EXPAND = ("downloads", "gated", "lastModified", "pipeline_tag", "tags", "likes", "private", "library_name")
QUANT = re.compile(r"(?:^|[-_.])((?:UD-)?(?:IQ\d_[A-Z]+|Q\d_K(?:_[A-Z]+)?|Q\d_\d|Q\d_K|BF16|F16|F32|MXFP4))(?:[-_.]|$)", re.I)
SHARD = re.compile(r"-(\d{5})-of-(\d{5})\.gguf$", re.I)
SKIP = ("mmproj", "imatrix", "mtp-", "/mtp/")


def search_url(q: str, kind: str, limit: int = 50) -> str:
    params = [("filter", kind), ("search", q or ""), ("sort", "downloads"), ("limit", str(limit))]
    params += [("expand[]", e) for e in EXPAND]
    return f"{API}?{urllib.parse.urlencode(params)}"


def repo_url(repo_id: str) -> str:
    return f"{API}/{repo_id}?blobs=true"


def config_url(repo_id: str) -> str:
    return f"https://huggingface.co/{repo_id}/resolve/main/config.json"


def _license(tags, card=None) -> str:
    lic = (card or {}).get("license") if isinstance(card, dict) else None
    if isinstance(lic, str) and lic:
        return lic
    return next((t.split(":", 1)[1] for t in tags or [] if isinstance(t, str) and t.startswith("license:")), "")


def _base(tags, card=None) -> str:
    b = (card or {}).get("base_model") if isinstance(card, dict) else None
    if isinstance(b, list) and b:
        return str(b[0])
    if isinstance(b, str) and b:
        return b
    return next((t.split(":", 1)[1] for t in tags or [] if isinstance(t, str) and t.startswith("base_model:")
                 and t.count(":") == 1), "")


def parse_search(items, kind: str) -> list:
    if isinstance(items, str):
        items = json.loads(items)
    if not isinstance(items, list):
        raise ValueError("a hub search answer that is not a list")
    out = []
    for x in items:
        if not isinstance(x, dict) or not x.get("id"):
            continue
        tags = [t for t in x.get("tags") or [] if isinstance(t, str)]
        out.append({"id": x["id"], "downloads": x.get("downloads"), "likes": x.get("likes"), "tags": tags,
                    "pipeline_tag": x.get("pipeline_tag") or "", "updated": x.get("lastModified") or x.get("createdAt") or "",
                    "gated": x.get("gated") or False, "private": bool(x.get("private")), "license": _license(tags),
                    "base_model": _base(tags), "kind": kind})
    return out


def quant_of_file(name: str) -> str:
    m = QUANT.search(name.rsplit("/", 1)[-1])
    return m.group(1).upper() if m else ""


def _gguf_files(siblings) -> list:
    groups: dict = {}
    for s in siblings:
        f, size = str(s.get("rfilename") or ""), s.get("size")
        if not f.lower().endswith(".gguf") or any(k in f.lower() for k in SKIP):
            continue
        key = SHARD.sub(".gguf", f)
        g = groups.setdefault(key, {"file": key if key == f else f, "size": 0, "parts": 0, "quant": quant_of_file(key)})
        g["size"] += int(size or 0)
        g["parts"] += 1
    return sorted(groups.values(), key=lambda g: g["size"])


def parse_repo(obj) -> dict:
    if isinstance(obj, str):
        obj = json.loads(obj)
    if not isinstance(obj, dict) or not obj.get("id"):
        raise ValueError("a hub repo answer without its id")
    tags = [t for t in obj.get("tags") or [] if isinstance(t, str)]
    sib = [s for s in obj.get("siblings") or [] if isinstance(s, dict)]
    gguf = obj.get("gguf") if isinstance(obj.get("gguf"), dict) else {}
    conf = obj.get("config") if isinstance(obj.get("config"), dict) else {}
    kind = "gguf" if gguf or any(str(s.get("rfilename", "")).endswith(".gguf") for s in sib) else "mlx" if "mlx" in tags else "other"
    proj = [int(s.get("size") or 0) for s in sib if "mmproj" in str(s.get("rfilename", "")).lower()]
    if kind == "gguf":
        files = _gguf_files(sib)
    else:
        st = [s for s in sib if str(s.get("rfilename", "")).endswith(".safetensors")]
        bits = (conf.get("quantization_config") or conf.get("quantization") or {}) if isinstance(conf, dict) else {}
        q = f"{bits.get('bits')}bit" if isinstance(bits, dict) and bits.get("bits") else ""
        files = [{"file": "", "size": sum(int(s.get("size") or 0) for s in st), "parts": len(st), "quant": q}] if st else []
    st_total = (obj.get("safetensors") or {}).get("total") if isinstance(obj.get("safetensors"), dict) else None
    return {"id": obj["id"], "gated": obj.get("gated") or False, "private": bool(obj.get("private")),
            "license": _license(tags, obj.get("cardData")), "base_model": _base(tags, obj.get("cardData")),
            "pipeline_tag": obj.get("pipeline_tag") or (obj.get("cardData") or {}).get("pipeline_tag") or "",
            "updated": obj.get("lastModified") or "", "downloads": obj.get("downloads"), "likes": obj.get("likes"),
            "tags": tags, "kind": kind, "context": gguf.get("context_length") if isinstance(gguf.get("context_length"), int) else None,
            "arch": gguf.get("architecture") or conf.get("model_type") or "",
            "params_total": gguf.get("total") if isinstance(gguf.get("total"), int) else st_total,
            "projector": min(proj) if proj else 0, "files": files,
            "has_config": any(s.get("rfilename") == "config.json" for s in sib)}


def shape_from_config(cfg) -> dict:
    """config.json (its `text_config` folded in) as a model_info dict; {} when it has no shape."""
    if isinstance(cfg, str):
        cfg = json.loads(cfg)
    if not isinstance(cfg, dict):
        return {}
    from halo_harness.providers.safetensors_config import safetensors_model_info
    merged = {**cfg, **(cfg.get("text_config") if isinstance(cfg.get("text_config"), dict) else {})}
    merged["model_type"] = cfg.get("model_type") or merged.get("model_type")
    info = safetensors_model_info(merged)
    if not info:
        return {}
    arch = info["general.architecture"]
    for key in ("full_attention_interval", "vocab_size"):  # a hybrid model's one-in-N KV layers; the embedding in RAM
        v = merged.get(key)
        if isinstance(v, int) and v > 0:
            info[f"{arch}.{key}"] = v
    return info


def token() -> Optional[str]:
    try:
        from halo_harness.providers.config import resolve_huggingface
        hf = resolve_huggingface()
        return hf.api_key if hf else None
    except Exception:
        return None


def _fixture_name(prefix: str, repo_id: str) -> str:
    return f"{prefix}{repo_id.replace('/', '--')}.json"


def search(state_dir, q: str, kind: str, *, refresh: bool = False) -> dict:
    if cache.offline() and "fetch" not in cache.SEAMS:
        rows = parse_search(cache.fixture(f"hf_search_{kind}.json") or "[]", kind)
        words = [w for w in str(q or "").lower().split() if w]
        return {"repos": [r for r in rows if all(w in r["id"].lower() for w in words)], "source": "fixtures",
                "at": None, "note": "the hub's fixtures (background network reads are off)"}
    try:
        got, at, how = cache.cached(state_dir, f"hf:search:{kind}:{q}", search_url(q, kind), cache.SEARCH_TTL_S,
                                    lambda t: parse_search(t, kind), refresh=refresh)
        return {"repos": got, "source": "live", "at": at, "note": "from the cache" if how == "cache" else ""}
    except (cache.FetchError, ValueError) as e:
        return {"repos": [], "source": "live", "at": None, "note": f"the hub did not answer: {e}"}


def _headers(gated) -> dict:
    tok = token() if gated else None
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def repo(state_dir, repo_id: str, *, refresh: bool = False, gated=False) -> Optional[dict]:
    if cache.offline() and "fetch" not in cache.SEAMS:
        text = cache.fixture(_fixture_name("hf_repo_", repo_id))
        return {**parse_repo(text), "source": "fixtures"} if text else None
    try:
        got, _at, _how = cache.cached(state_dir, f"hf:repo:{repo_id}", repo_url(repo_id), cache.REPO_TTL_S, parse_repo,
                                      refresh=refresh, headers=_headers(gated))
        return {**got, "source": "huggingface.co/api/models"}
    except (cache.FetchError, ValueError):
        return None


def config(state_dir, repo_id: str, *, gated=False, refresh: bool = False) -> dict:
    """The repo's family shape from its config.json ({} when it has none or it cannot be read)."""
    if cache.offline() and "fetch" not in cache.SEAMS:
        text = cache.fixture(_fixture_name("hf_config_", repo_id))
        return shape_from_config(text) if text else {}
    try:
        got, _at, _how = cache.cached(state_dir, f"hf:config:{repo_id}", config_url(repo_id), cache.REPO_TTL_S,
                                      shape_from_config, refresh=refresh, headers=_headers(gated))
        return got or {}
    except (cache.FetchError, ValueError):
        return {}
