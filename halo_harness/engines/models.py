"""halo_harness.engines.models -- the models each engine names in its own docs (the descriptor table's data), as the
Library's download targets and the fit's sizes. Every figure is the engine's own, unverified until a live run.

One row shape for every engine: {engine, id, name, size_gb, ram_gb, gpu_gb, ssd_gb, context, backends, machines, nvfp4,
apple_min, min_vram_gb, min_ram_gb, pool, speed, pull, note}
    size_gb: the download or checkpoint as the project states it; ram_gb (paged-moe): what host RAM must hold for the
    experts (the engine's spare is the fit's figure); gpu_gb (paged-moe): what stays on the card; pool "ram+vram": the
    figure counts VRAM and RAM together and nothing is mapped from disk; None: the project states no size.

    rows(engine=None) -> [row]     match(engine, text) -> row | None (a repo, a family/set, a served id, a lane's model)
    library_rows(engine, q="") -> [LibraryRow]   kind = the engine id; pull_line = the owner's download command
"""

from __future__ import annotations

from typing import Optional

GIB = 2 ** 30
BPW = {"nvfp4": 0.5625, "mxfp4": 0.53125, "fp8": 1.0, "bf16": 2.0, "fp4": 0.5625}  # FreeToken's formats, bytes/weight


def _row(engine, id_, name, size=None, **kw) -> dict:
    out = {"engine": engine, "id": id_, "name": name, "size_gb": size, "ram_gb": None, "gpu_gb": None, "ssd_gb": 0.0,
           "context": None, "backends": None, "machines": 1, "nvfp4": "nvfp4" in id_.lower(), "apple_min": 0,
           "min_vram_gb": 0.0, "min_ram_gb": 0.0, "pool": "ram", "speed": None, "pull": None, "note": ""}
    out.update(kw)
    return out


def _ft(name, repo, fmt, total=None, active=None, ram=0.0, nvme=0.0, note=""):
    bpw = BPW[fmt]
    size = total * 1e9 * bpw / GIB if total else None
    gpu = active * 1e9 * bpw / GIB if active else None
    need = (size - gpu + ram) if size and gpu else None
    return _row("freetoken", repo, name, size, ram_gb=need, gpu_gb=gpu, ssd_gb=nvme, extra_gb=ram, format=fmt,
                pull=f"halo local download {repo}", note=note or fmt)


_FN, _5070 = "Qwen3.8-Flash-Next", "RTX 5070 12 GB, 64 GB RAM"
_DS = "4 to 6 tok/s (RTX 5070 12 GB, 64 GB RAM); 9 to 11 (RTX 3060 12 GB, 46 GB RAM); 21 to 25 (one Radeon AI PRO R9700)"


def _st(family, set_, dl, need, *, model=_FN, ssd=29.0, speed=None, hw=_5070, **kw):
    return _row("strata", f"{family}/{set_}", f"{model} {set_}", dl, ram_gb=need, ssd_gb=ssd,
                speed=f"{speed} tok/s ({hw})" if speed and "(" not in speed else speed,
                pull=f"strata launch --family {family} --model {set_} --yes --no-tui --access local", **kw)


def _ud(set_, dl, ram, speed):
    return _st("unsloth", set_, dl, ram - 10.0, speed=speed, hw="Radeon AI PRO R9700 32 GB")


def _ds(set_, dl, note="what does not fit in memory is read from the SSD: keep about the download free on an NVMe"):
    return _st("deepseek41", set_, dl, 54.0, model="DeepSeekV4.1-Flash-1017", ssd=dl, speed=_DS, context=8192,
               min_vram_gb=12.0, min_ram_gb=46.0, slots=1, note=note)


def _tf(repo, name, size=None, unit="GiB", *, pin=None, backends=None, **kw):
    gib = size * (1.0 if unit == "GiB" else 1e9 / GIB) if size else None
    pull = kw.pop("pull", None) or f"tensorfold pull {repo}" + (f"@{pin}" if pin else "")
    return _row("tensorfold", repo, name, gib, backends=backends, pull=pull, size_words=f"{size:g} {unit}" if size else
                None, **kw)


_M, _C = ("metal",), ("cuda",)
ROWS = [
    _ft("DeepSeek-V4.1-Flash", "deepseek-ai/DeepSeek-V4.1-Flash", "fp4", ram=6.0, nvme=196.0,
        note="two 98 GiB Engram tables stream from the checkpoint shards (keep them on a fast NVMe)"),
    _ft("GLM-5.3-Flash", "RedHatAI/GLM-5.3-Flash-NVFP4", "nvfp4"), _ft("GLM-5.2", "nvidia/GLM-5.2-NVFP4", "nvfp4"),
    _ft(_FN, "nvidia/Qwen3.8-Flash-Next-NVFP4", "nvfp4", ram=47.7, note="a 47.7 GiB PLE n-gram table pinned in RAM"),
    _ft(_FN, "Qwen/Qwen3.8-Flash-Next-FP8", "fp8", ram=47.7, note="a 47.7 GiB PLE n-gram table pinned in RAM"),
    _ft("Qwen3.6-35B-A3B", "nvidia/Qwen3.6-35B-A3B-NVFP4", "nvfp4", 35.0, 3.0),
    _ft("Qwen3.6-35B-A3B", "Qwen/Qwen3.6-35B-A3B-FP8", "fp8", 35.0, 3.0),
    _ft("Qwen3.6-35B-A3B", "Qwen/Qwen3.6-35B-A3B", "bf16", 35.0, 3.0),
    _ft("Qwen3-30B-A3B", "Qwen/Qwen3-30B-A3B", "bf16", 30.0, 3.0),
    _ft("Qwen3-VL-30B-A3B", "Qwen/Qwen3-VL-30B-A3B-Instruct", "bf16", 30.0, 3.0, note="image input"),
    _ft("gpt-oss-120b", "openai/gpt-oss-120b", "mxfp4", 117.0, 5.1), _ft("gpt-oss-20b", "openai/gpt-oss-20b", "mxfp4", 21.0, 3.6),
    _ft("Gemma-4-26B-A4B", "nvidia/Gemma-4-26B-A4B-NVFP4", "nvfp4", 26.0, 4.0, note="image input"),
    _ft("Gemma-4-26B-A4B", "google/gemma-4-26B-A4B-it", "bf16", 26.0, 4.0, note="image input"),
    _ft("MiniMax-M2.5", "nvidia/MiniMax-M2.5-NVFP4", "nvfp4"), _ft("MiniMax-M3", "nvidia/MiniMax-M3-NVFP4", "nvfp4"),
    _st("qwen", "Q2_0", 66.0, 34.0, speed="94"), _st("qwen", "IQ2_XS", 68.0, 35.5, speed="79"),
    _st("qwen", "IQ3_XXS", 76.0, 43.0, speed="62"),
    _st("qwen", "IQ3_S", None, 50.0, speed="53", note="matches the full model on the published tests"),
    _st("coder", "IQ1_M", None, 23.0, speed="55", note="256 of each layer's 512 experts, for code"),
    _st("swift", "IQ2_XS", None, 35.5, note="UkisAI's fine-tune that thinks shorter; its own license"),
    _ud("UD-IQ4_XS", 94.0, 72.0, None), _ud("UD-Q4_K_XL", 111.0, 88.0, "63"), _ud("UD-Q5_K_XL", 158.0, 108.0, "57 to 60"),
    _ud("UD-Q6_K_XL", 169.0, 118.0, "54"), _ud("Q8_0", 188.0, 136.0, "53 to 57"),
    _st("gyro", "Gyro-S", 58.5, 27.6, ssd=28.0, pool="ram+vram", note="lower quality"),
    _st("gyro", "Gyro-M", 92.0, 35.0, ssd=28.0, pool="ram+vram"),
    _st("nvfp4", "NVFP4", 128.0, 70.0, ssd=0.0, backends=_C), _st("nvfp4", "NVFP4-NVIDIA", 128.0, 70.0, ssd=0.0, backends=_C),
    _st("nvfp4", "NVFP4-QAD", 102.0, 70.0, ssd=0.0, backends=_C, note="+110 GB of disk while setup prepares it"),
    _st("qwen36", "UD-Q4_K_XL", 22.9, 22.0, model="Qwen3.6-35B-A3B", ssd=0.0, backends=("cuda", "rocm"),
        speed="59.7 tok/s (RTX 3060 12 GB, most experts on the CPU); 117.8 (Radeon AI PRO R9700 32 GB)"),
    _st("qwen36", "UD-Q6_K_XL", 32.6, 34.0, model="Qwen3.6-35B-A3B", ssd=0.0, backends=("cuda", "rocm")),
    _st("qwen36", "Q8_0", 37.8, 42.0, model="Qwen3.6-35B-A3B", ssd=0.0, backends=("cuda", "rocm")),
    _ds("ist-das-1.75bpw", 239.0), _ds("ist-das-2.00bpw", 257.0), _ds("ist-das-2.25bpw", 274.0),
    _ds("ist-das-coder", 191.0, note="192 of the 384 experts in every layer kept, for code"), _ds("ud-q8_k_xl", 508.0),
    _tf("mlx-community/Qwen3.5-2B-MLX-4bit", "Qwen3.5-2B MLX 4-bit", pin="93760be4f1f69842a46bc13dbdc0f19e291392a3",
        note="text only; the quick start's model"),
    _tf("TensorFold/Qwen3.8-27B-MLX-4bit", "Qwen3.8-27B MLX 4-bit", 16, context=32768, note="--drafter for drafts"),
    _tf("TensorFold/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-MLX-4bit", "Nemotron 3.5 Lightning 30B-A3B MLX 4-bit"),
    _tf("TensorFold/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-oQ4", "Nemotron 3.5 Lightning oQ4", backends=_M),
    _tf("nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4", "Nemotron 3.5 Lightning NVFP4", backends=_C),
    _tf("nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4", "Nemotron 3.5 Super VL 120B-A12B NVFP4", 70.8,
        backends=_C, pin="82d93699acd3be9e4617c53360fe5b3f5dbeb1b3", note="73.2 GiB with vision"),
    _tf("nvidia/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB", "Nemotron 3.5 Bolt 74B-A9B", 24, "GB", backends=_C,
        pull="hf download nvidia/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB"),
    _tf("TensorFold/Qwen3.8-Flash-Next-MLX-6bit-MTP", "Qwen3.8 Flash Next MLX 6-bit", backends=_M),
    _tf("TensorFold/Qwen3.8-Flash-Next-MLX-4bit-MTP", "Qwen3.8 Flash Next MLX 4-bit", 73.3),
    _tf("TensorFold/GLM-5.3-Flash-MLX-4bit-MTP", "GLM-5.3-Flash MLX 4-bit", backends=_M, machines=2),
    _tf("Mia-AiLab/GLM-5.3-Flash-EXL3-TR3-4bpw", "GLM-5.3-Flash EXL3/TR3", backends=_C, machines=2),
    _tf("nvidia/GLM-5.3-Flash-NVFP4", "GLM-5.3-Flash NVFP4", 190.4, backends=_C, machines=2,
        pin="423acf37583782c51c142d145aef733d72943d93"),
    _tf("nvidia/GLM-5.3-Flash-FP4-Local", "GLM-5.3-Flash FP4-Local", 165.3, backends=_C, machines=2,
        pin="76348ddb2be2e35e39ecfc00e75dc07703f4f3d5"),
    _tf("Bizuayeu/GLM-5.3-Flash-XSFP4", "GLM-5.3-Flash XSFP4", 165.7, backends=_C, machines=2,
        pin="88736f916f8939607fde8a4b881dcae749f7551d"),
    _tf("kindlingai/glm-5.3-exlr8-k2-k3-k4", "GLM-5.3 EXLR8 home", 160, "GB", backends=_M, machines=2),
    _tf("LiquidAI/LFM2.5-24B-A2B-MLX-4bit", "LFM2.5-24B-A2B MLX 4-bit", backends=_M,
        pin="667408d494bde191c2cb9dd4f4549827816b9275"),
    _tf("LiquidAI/LFM2.5-24B-A2B-MLX-8bit", "LFM2.5-24B-A2B MLX 8-bit", backends=_M,
        pin="67ab417dd02d0c9545802a726df668620eae049d"),
    _tf("TensorFold/Qwen3.6-35B-A3B-MLX-4bit-MTP", "Qwen3.6-35B-A3B MLX 4-bit MTP", 20.9, "GB", backends=_C,
        pin="81169a9bc511a27c1b4eedb77a2cd98ced431847"),
    _tf("nvidia/Qwen3.6-35B-A3B-NVFP4", "Qwen3.6-35B-A3B NVFP4", 20.9, backends=_C,
        pin="1355db6a052410cfd62085d94b58866fd0f2c3c5"),
    _tf("mlx-community/gemma-4-31B-it-4bit", "Gemma 4 31B MLX 4-bit", backends=_M, apple_min=5,
        pin="696d436c404745a59f30e4939a658162b0a9e57f"),
    _tf("google/gemma-4-12B-it", "Gemma 4 12B (converted MLX 4-bit)", 6.3, "GB", backends=_M, apple_min=5,
        pull="hf download google/gemma-4-12B-it, then the recipe's conversion (Python, mlx and mlx-lm)"),
    _tf("stepfun-ai/Step-5-Preview", "Step-5-Preview (converted affine)", 166.9, backends=_M,
        pull="hf download stepfun-ai/Step-5-Preview, then the recipe's conversion (Python and mlx)"),
    _tf("BobClawblaw/MiniMax-M3.1-Flash-MLX-mix34", "MiniMax-M3.1-Flash MLX mix34", 203.7, backends=_M, context=32768,
        pull="hf download BobClawblaw/MiniMax-M3.1-Flash-MLX-mix34"),
    _tf("Aleph-Alpha/Kolibri-1", "Kolibri-1 block FP8", 74, "GB", backends=_C, pin="e52eb4627d11516b0c01de49210ab5a4e4061444"),
]


def rows(engine: Optional[str] = None) -> list:
    return [r for r in ROWS if engine is None or r["engine"] == engine]


def _n(text) -> str:
    t = str(text or "").strip().lower()
    t = t[len("hf:local/"):] if t.startswith("hf:local/") else t
    return t.split("@", 1)[0].removeprefix("strata:").removeprefix("tensorfold:").replace("_", "-")


def match(engine: str, text) -> Optional[dict]:
    """The row an id, a repo's basename, a served name or a lane's model names: the exact id first, then the
    basename, then the longest row name it contains (a format word picking among a model's checkpoints)."""
    want, mine = _n(text), rows(engine)
    if not want:
        return None
    hit = next((r for r in mine if _n(r["id"]) == want), None) or next(
        (r for r in mine if _n(r["id"]).rsplit("/", 1)[-1] == want.rsplit("/", 1)[-1]), None)
    if hit is not None:
        return hit
    named = [r for r in mine if _n(r["name"]).split(" ")[0] in want]
    best = sorted((r for r in named if _n(r["id"]).rsplit("/", 1)[-1] in want), key=lambda r: -len(r["id"])) or named
    return best[0] if best else None


def library_rows(engine: str, q: str = "") -> list:
    from halo_harness.engines.descriptors import get
    d = get(engine)
    words = [w for w in str(q or "").lower().split() if w and w != engine]
    out = []
    for r in rows(engine):
        if words and not all(w in f"{r['id']} {r['name']} {r['note']} {engine} moe".lower() for w in words):
            continue
        size = int(r["size_gb"] * GIB) if r["size_gb"] else None
        out.append({"source": "hf", "id": r["id"] if engine == "freetoken" else f"{engine}:{r['id']}", "tag_or_file": "",
                    "name": r["name"], "family": r["name"].split(" ")[0], "params": None, "quant": r.get("format"),
                    "size_bytes": size, "weights_bytes": size, "projector_bytes": 0,
                    "capabilities": ["tools"] + (["vision"] if "image" in r["note"] else []), "context": r["context"],
                    "downloads": None, "updated": None, "license": "", "gated": False,
                    "description": f"a model {d['label']} names{': ' + r['note'] if r['note'] else ''}",
                    "pull_line": r["pull"] + ("" if engine == "freetoken" else "   (the download is yours to run)"),
                    "kind": engine, "key": f"{engine}:{r['id']}", "shape": None, "runtime": engine,
                    "sources": {"listing": f"{d['label']}'s own docs ({d['source']}), unverified against a live run",
                                "size": "the size it states" if size else "not stated"}})
    return out
