"""halo_harness.models_library.row_builders -- Halo 3.3.5.0 R2: LibraryRow from what each listing says.

    ollama_row(entry, size, tags, manifest=None, tags_source="") -> row   one model at one tag (a size chip, else latest)
    hf_repo_row(repo) -> row                                              one hub repo from a search (sizes estimated)
    hf_file_row(repo, file, shape=None) -> row                            one GGUF file (or an MLX repo's weights)

LibraryRow (rows.py documents it) = {source, id, tag_or_file, name, family, params, quant, size_bytes,
weights_bytes, projector_bytes, capabilities, context, downloads, updated, license, gated, description,
pull_line, kind, key, shape, sources {field: where it came from}}.
"""

from __future__ import annotations

import re
from typing import Optional

from halo_harness.providers import model_card_purpose as P

DEFAULT_QUANT = "Q4_K_M"
BYTES_PER_PARAM = {"Q2_K": 0.41, "Q3_K_M": 0.49, "Q4_0": 0.5625, "Q4_K_S": 0.58, "Q4_K_M": 0.606, "Q5_K_M": 0.71,
                   "Q6_K": 0.82, "Q8_0": 1.0625, "F16": 2.0, "BF16": 2.0, "4BIT": 0.5625, "8BIT": 1.0625,
                   "MXFP4": 0.53}
_CHIP = re.compile(r"^e?(\d+(?:\.\d+)?)([bm])(?:-a\d+(?:\.\d+)?b)?$", re.I)
VISION_PIPES = ("image-text-to-text", "visual-question-answering", "image-to-text")
EMBED_PIPES = ("feature-extraction", "sentence-similarity")


def params_of_chip(size: str) -> Optional[float]:
    m = _CHIP.match(str(size or ""))
    if not m:
        return None
    n = float(m.group(1))
    return round(n if m.group(2).lower() == "b" else n / 1000.0, 3)


def estimate_bytes(params: Optional[float], quant: str) -> Optional[int]:
    if not isinstance(params, (int, float)) or params <= 0:
        return None
    q = str(quant or DEFAULT_QUANT).upper().replace("UD-", "")
    bpp = BYTES_PER_PARAM.get(q) or BYTES_PER_PARAM.get(q.split("_")[0] + "_0") or BYTES_PER_PARAM[DEFAULT_QUANT]
    return int(params * 1e9 * bpp)


def _base(**kw) -> dict:
    row = {"source": "", "id": "", "tag_or_file": "", "name": "", "family": "", "params": None, "quant": "",
           "size_bytes": None, "weights_bytes": None, "projector_bytes": 0, "capabilities": [], "context": None,
           "downloads": None, "updated": "", "license": "", "gated": False, "description": "", "pull_line": "",
           "kind": "", "key": "", "shape": None, "sources": {}}
    row.update(kw)
    return row


def ollama_row(entry: dict, size: str, tags: list, manifest: Optional[dict] = None, tags_source: str = "") -> dict:
    name = entry["name"]
    tag = next((t for t in tags or [] if t.get("tag") == size), None) or {}
    m = manifest or {}
    src: dict = {}
    caps = [c for c in entry.get("capabilities") or [] if c != "cloud"]
    if "Image" in (tag.get("input") or []) and "vision" not in caps:
        caps.append("vision")
    params = m.get("params") or params_of_chip(size) or P.params_of(f"{name}:{size}")[0]
    src["params"] = m.get("source") or "registry config" if m.get("params") else "the size chip" if params_of_chip(size) else "the name"
    quant, qsrc = P.quant_of(f"{name}:{size}")
    if m.get("quant"):
        quant, qsrc = m["quant"], f"{m.get('source') or 'the registry'} (config file_type)"
    elif not quant:
        quant, qsrc = DEFAULT_QUANT, "estimate: the library's default quantization"
    src["quant"] = qsrc
    weights, proj = m.get("weights"), int(m.get("projector") or 0)
    if isinstance(weights, int) and weights > 0:
        size_bytes = weights + proj
        src["size_bytes"] = f"{m.get('source') or 'registry'}: the model layer {weights:,} + projector {proj:,} bytes"
    else:
        size_bytes = tag.get("size_bytes")
        src["size_bytes"] = (f"{tags_source or 'the tags page'}: {tag['size_text']} (the smaller of a range)"
                             if tag.get("size_text") else "unknown until the tags page is read")
        weights = None
    family = m.get("family") or P.family_of(name)[0]
    src["family"] = "registry config model_family" if m.get("family") else "the name"
    src["context"] = f"{tags_source or 'the tags page'}: {tag.get('context_text')}" if tag.get("context") else "unknown"
    src["capabilities"] = "the library's chips" + (" and the tag's input (Image)" if "Image" in (tag.get("input") or []) else "")
    src["downloads"] = "ollama.com/library: pulls"
    full = f"{name}:{size}" if size else name
    return _base(source="ollama", id=name, tag_or_file=size, name=full, family=family, params=params, quant=quant,
                 size_bytes=size_bytes, weights_bytes=weights, projector_bytes=proj, capabilities=caps,
                 context=tag.get("context"), downloads=entry.get("pulls_n"), updated=entry.get("updated") or "",
                 description=entry.get("description") or "", pull_line=f"ollama pull {full}", kind="ollama",
                 key=f"ollama/{full}", sources=src, input=tag.get("input") or [], tags_count=entry.get("tags_count"))


def hub_tags(repo: dict) -> list:
    """The repo's tags a search reads (3.3.6.0 R2: tools, security, math, languages ...), without the papers,
    regions and base models."""
    skip = ("arxiv:", "region:", "base_model:", "dataset:", "doi:")
    return [str(t) for t in repo.get("tags") or [] if isinstance(t, str) and not t.startswith(skip)][:40]


def _hf_caps(repo: dict) -> list:
    caps = []
    pipe, tags = repo.get("pipeline_tag") or "", [str(t).lower() for t in repo.get("tags") or []]
    if pipe in VISION_PIPES or "vision" in tags or "multimodal" in tags:
        caps.append("vision")
    if pipe in EMBED_PIPES or P.name_rule(repo["id"]) == "embedding":
        caps.append("embedding")
    if P.name_rule(repo["id"]) == "reasoning":
        caps.append("thinking")
    return caps


def _mlx_quant(repo: dict) -> str:
    tags = [str(t).lower() for t in repo.get("tags") or []]
    for b in ("4", "8", "6", "3", "2"):
        if f"{b}-bit" in tags or f"{b}bit" in repo["id"].lower():
            return f"{b}bit"
    return ""


def hf_repo_row(repo: dict) -> dict:
    rid, kind = repo["id"], repo.get("kind") or "gguf"
    params, psrc = P.params_of(rid)
    quant = DEFAULT_QUANT if kind == "gguf" else _mlx_quant(repo)
    est = estimate_bytes(params, quant or "4BIT")
    src = {"params": psrc, "quant": "estimate: a typical file (open the repo for its files)" if kind == "gguf" else
           "the repo's tags" if quant else "unknown", "context": "unknown until the repo is opened",
           "size_bytes": f"estimate: {params:g}B at {quant or '4bit'} (open the repo for its files)" if est else "unknown",
           "capabilities": "the repo's pipeline tag and tags", "downloads": "huggingface.co: downloads",
           "family": "the name", "license": "the repo's tags" if repo.get("license") else "unknown"}
    pull = f"ollama pull hf.co/{rid}" if kind == "gguf" else f"halo local download {rid}"
    return _base(source="hf", id=rid, name=rid, family=P.family_of(rid)[0] or repo.get("base_model", ""),
                 params=params, quant=quant, size_bytes=est, capabilities=_hf_caps(repo), downloads=repo.get("downloads"),
                 updated=(repo.get("updated") or "")[:10], license=repo.get("license") or "", gated=repo.get("gated") or False,
                 description=f"from {repo['base_model']}" if repo.get("base_model") else "", pull_line=pull,
                 kind=kind, key=f"hf/{rid}", sources=src, estimate=True, tags=hub_tags(repo))


def hf_file_row(repo: dict, f: dict, shape: Optional[dict] = None) -> dict:
    rid, kind = repo["id"], repo.get("kind") or "gguf"
    params = round(repo["params_total"] / 1e9, 3) if isinstance(repo.get("params_total"), int) and kind == "gguf" else None
    psrc = "the repo's gguf metadata (total)" if params else "the name"
    if params is None:
        params = P.params_of(rid)[0]
    quant = f.get("quant") or ("" if kind == "gguf" else _mlx_quant(repo))
    proj = int(repo.get("projector") or 0) if kind == "gguf" else 0
    pull = (f"ollama pull hf.co/{rid}:{quant}" if kind == "gguf" and quant else
            f"ollama pull hf.co/{rid}" if kind == "gguf" else f"halo local download {rid}")
    src = {"params": psrc, "quant": "the file name" if f.get("quant") else "the repo's config" if quant else "unknown",
           "size_bytes": f"huggingface.co ?blobs=true: {f.get('parts', 1)} file{'s' if f.get('parts', 1) != 1 else ''}"
                         + (f" + projector {proj:,} bytes" if proj else ""),
           "context": "the repo's gguf metadata (context_length)" if repo.get("context") else "unknown",
           "capabilities": "the repo's pipeline tag and tags", "downloads": "huggingface.co: downloads",
           "family": "the repo's gguf architecture" if repo.get("arch") else "the name",
           "license": "the repo's card" if repo.get("license") else "unknown"}
    return _base(source="hf", id=rid, tag_or_file=f.get("file") or "", name=f"{rid}" + (f" {f['file']}" if f.get("file") else ""),
                 family=repo.get("arch") or P.family_of(rid)[0], params=params, quant=quant,
                 size_bytes=(f.get("size") or 0) + proj or None, weights_bytes=f.get("size") or None, projector_bytes=proj,
                 capabilities=_hf_caps(repo), context=repo.get("context"), downloads=repo.get("downloads"),
                 updated=(repo.get("updated") or "")[:10], license=repo.get("license") or "", gated=repo.get("gated") or False,
                 description=f"from {repo['base_model']}" if repo.get("base_model") else "", pull_line=pull, kind=kind,
                 key=f"hf/{rid}/{f.get('file') or quant}", shape=shape or None, sources=src,
                 alt_line=f"halo local download {rid} {f['file']}" if f.get("file") else "", tags=hub_tags(repo))
