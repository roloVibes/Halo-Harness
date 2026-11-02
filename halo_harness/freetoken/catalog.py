"""halo_harness.freetoken.catalog -- the Mixture-of-Experts checkpoints FreeToken names as known-good (its docs/models.md
table, read 2026-11-02: from the source, unverified against a live run), as download targets the Library lists with a
FreeToken fit badge (Halo 3.3.9.1; docs/MODELS-freetoken.md "Which checkpoints").

    ROWS: [{name, repo, format, total_b, active_b, params_from, ram_extra_gib, nvme_gib, note}]
        total_b / active_b: billions of weights, from the model's name ("35B-A3B") or its maker's card (gpt-oss), None
        when neither says (the repo's own files and config.json size it once opened or downloaded)
        ram_extra_gib / nvme_gib: what docs/models.md says beyond the experts -- DeepSeek-V4.1-Flash's two 98 GiB tables
        streamed from the checkpoint shards (keep them on a fast NVMe) and their 6 GiB of scales in host RAM,
        Qwen3.8-Flash-Next's 47.7 GiB PLE n-gram table pinned in host RAM
    BPW: bytes per weight of each format (NVFP4: 4 bits + an FP8 scale per 16 = 4.5 bits; MXFP4: 4 + 8 per 32 = 4.25)
    get(name_or_repo) -> row | None      match(text) -> row | None (a checkpoint folder's name, a repo id, a model id)
    library_rows(q="") -> [LibraryRow]   kind "freetoken", pull_line `halo local download <repo>`, runtime freetoken
    listed(q="") -> the Library shows them: the search names freetoken, or the runtime is configured (doctor_freetoken)

Dense checkpoints FreeToken also serves (Qwen3.8-27B, Gemma-4 31B) are left out on purpose: Ollama, llama-server and
the pool stay the answer for dense models; FreeToken is the answer for an MoE bigger than the card.
"""

from __future__ import annotations

from typing import Optional

BPW = {"nvfp4": 0.5625, "mxfp4": 0.53125, "fp8": 1.0, "bf16": 2.0, "fp4": 0.5625}
_SRC = "FreeToken's docs/models.md (from the source, unverified against a live run)"


def _r(name, repo, fmt, total=None, active=None, src="the model's name", ram=0.0, nvme=0.0, note="") -> dict:
    return {"name": name, "repo": repo, "format": fmt, "total_b": total, "active_b": active,
            "params_from": src if total else "", "ram_extra_gib": ram, "nvme_gib": nvme, "note": note, "listed_by": _SRC}


ROWS = [
    _r("DeepSeek-V4.1-Flash", "deepseek-ai/DeepSeek-V4.1-Flash", "fp4", ram=6.0, nvme=196.0,
       note="two 98 GiB Engram tables stream from the checkpoint shards (keep them on a fast NVMe); 6 GiB of their "
            "scales stay in host RAM; fp8 dense weights, fp4 experts on the offload cache"),
    _r("GLM-5.3-Flash", "RedHatAI/GLM-5.3-Flash-NVFP4", "nvfp4"),
    _r("GLM-5.2", "nvidia/GLM-5.2-NVFP4", "nvfp4"),
    _r("Qwen3.8-Flash-Next", "nvidia/Qwen3.8-Flash-Next-NVFP4", "nvfp4", ram=47.7,
       note="keeps a 47.7 GiB PLE n-gram table pinned in host RAM"),
    _r("Qwen3.8-Flash-Next", "Qwen/Qwen3.8-Flash-Next-FP8", "fp8", ram=47.7,
       note="keeps a 47.7 GiB PLE n-gram table pinned in host RAM"),
    _r("Qwen3.6-35B-A3B", "nvidia/Qwen3.6-35B-A3B-NVFP4", "nvfp4", 35.0, 3.0),
    _r("Qwen3.6-35B-A3B", "Qwen/Qwen3.6-35B-A3B-FP8", "fp8", 35.0, 3.0),
    _r("Qwen3.6-35B-A3B", "Qwen/Qwen3.6-35B-A3B", "bf16", 35.0, 3.0),
    _r("Qwen3-30B-A3B", "Qwen/Qwen3-30B-A3B", "bf16", 30.0, 3.0),
    _r("Qwen3-VL-30B-A3B", "Qwen/Qwen3-VL-30B-A3B-Instruct", "bf16", 30.0, 3.0, note="image input"),
    _r("gpt-oss-120b", "openai/gpt-oss-120b", "mxfp4", 117.0, 5.1, "OpenAI's model card"),
    _r("gpt-oss-20b", "openai/gpt-oss-20b", "mxfp4", 21.0, 3.6, "OpenAI's model card"),
    _r("Gemma-4-26B-A4B", "nvidia/Gemma-4-26B-A4B-NVFP4", "nvfp4", 26.0, 4.0, note="image input"),
    _r("Gemma-4-26B-A4B", "google/gemma-4-26B-A4B-it", "bf16", 26.0, 4.0, note="image input"),
    _r("MiniMax-M2.5", "nvidia/MiniMax-M2.5-NVFP4", "nvfp4"),
    _r("MiniMax-M3", "nvidia/MiniMax-M3-NVFP4", "nvfp4", note="image input"),
]


def _norm(text) -> str:
    return str(text or "").strip().lower().replace("_", "-").removeprefix("hf:local/").split("@", 1)[0]


def get(name_or_repo) -> Optional[dict]:
    n = _norm(name_or_repo)
    return next((r for r in ROWS if n in (r["repo"].lower(), r["repo"].split("/")[-1].lower())), None) or \
        next((r for r in ROWS if n == r["name"].lower()), None)


def match(text) -> Optional[dict]:
    """The row a checkpoint folder's name, a repo id or a served model id is: the exact repo first, then the
    longest model name it contains, the format words (NVFP4, FP8) picking among a model's checkpoints."""
    hit = get(text)
    if hit is not None:
        return hit
    n = _norm(text).split("/")[-1]
    named = sorted((r for r in ROWS if r["name"].lower() in n), key=lambda r: -len(r["name"]))
    if not named:
        return None
    best = [r for r in named if r["name"] == named[0]["name"]]
    fmt = next((r for r in best if r["format"] in n), None)
    return fmt or next((r for r in best if r["format"] == "bf16"), best[0])


def size_bytes(row: dict) -> Optional[int]:
    return int(row["total_b"] * 1e9 * BPW.get(row["format"], 1.0)) if row.get("total_b") else None


def listed(q: str = "") -> bool:
    """The Library lists these rows when the search names FreeToken, or the runtime is configured here."""
    if "freetoken" in str(q or "").lower():
        return True
    from halo_harness.doctor_freetoken import configured
    return configured()


def library_rows(q: str = "") -> list:
    words = [w for w in str(q or "").lower().split() if w and w != "freetoken"]
    out = []
    for r in ROWS:
        hay = f"{r['name']} {r['repo']} {r['format']} freetoken moe".lower()
        if words and not all(w in hay for w in words):
            continue
        size = size_bytes(r)
        out.append({"source": "hf", "id": r["repo"], "tag_or_file": "", "name": r["repo"], "family": r["name"],
                    "params": r["total_b"], "quant": r["format"].upper(), "size_bytes": size, "weights_bytes": size,
                    "projector_bytes": 0, "capabilities": ["tools"] + (["vision"] if "image" in r["note"] else []),
                    "context": None, "downloads": None, "updated": None, "license": "", "gated": False,
                    "description": f"a Mixture-of-Experts checkpoint FreeToken serves ({r['note'] or r['format']})",
                    "pull_line": f"halo local download {r['repo']}", "kind": "freetoken", "key": f"ft:{r['repo']}",
                    "shape": None, "runtime": "freetoken", "active_b": r["active_b"],
                    "sources": {"listing": _SRC, "params": r["params_from"] or "not stated: open the repo",
                                "size": "the format's bits per weight x the weights (an estimate)" if size else ""}})
    return out
