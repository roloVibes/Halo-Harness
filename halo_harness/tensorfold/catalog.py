"""halo_harness.tensorfold.catalog -- the qualified models TensorFold's README names ("Pick a model", read 2026-11-02 at
main 532589e4; docs/WINDOWS.md for the 27B's 16 GiB: from the source, unverified against a live run), as download
targets the Library lists with a TensorFold fit badge (Halo 3.3.9.3; docs/MODELS-tensorfold.md "The models").

    ROWS: [{repo, title, size_bytes, size_words, backends, machines, nvfp4, convert, context, scope, note, pull}]
        repo: what `tensorfold pull` / `tensorfold serve` take; size_bytes: the checkpoint or weights size the README
        states (None where it publishes none: `tensorfold info REPO` reports the floor); backends: "metal" and / or
        "cuda" -- where the README qualifies it natively; machines: 2 for a model qualified only across two machines;
        nvfp4: an NVFP4 checkpoint (cards without thread-block clusters, sm_80 to sm_89, run a fallback path);
        convert: the upstream download needs a conversion first (Python and mlx: not TensorFold's serve);
        scope: the README's machine-and-memory words; pull: the download command the user runs
    get(repo) -> row | None     match(text) -> row | None   a repo, its basename, a served name or a lane's model
    listed(q="") -> the search names tensorfold, or the runtime is configured     library_rows(q="") -> [LibraryRow]
Speech (Fish Audio Drama 3) and decision models (Liquid AI d1-3B) are left out: Halo's sessions are chat.
"""

from __future__ import annotations

from typing import Optional

_SRC = "TensorFold's README \"Pick a model\" (from the source, unverified against a live run)"
GB, GIB = 1e9, 2 ** 30
PINS = {  # the revisions the README's pull commands pin
    "nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4": "82d93699acd3be9e4617c53360fe5b3f5dbeb1b3",
    "nvidia/GLM-5.3-Flash-FP4-Local": "76348ddb2be2e35e39ecfc00e75dc07703f4f3d5",
    "Bizuayeu/GLM-5.3-Flash-XSFP4": "88736f916f8939607fde8a4b881dcae749f7551d",
    "LiquidAI/LFM2.5-24B-A2B-MLX-4bit": "667408d494bde191c2cb9dd4f4549827816b9275",
    "LiquidAI/LFM2.5-24B-A2B-MLX-8bit": "67ab417dd02d0c9545802a726df668620eae049d",
    "TensorFold/Qwen3.6-35B-A3B-MLX-4bit-MTP": "81169a9bc511a27c1b4eedb77a2cd98ced431847",
    "nvidia/Qwen3.6-35B-A3B-NVFP4": "1355db6a052410cfd62085d94b58866fd0f2c3c5",
    "mlx-community/gemma-4-31B-it-4bit": "696d436c404745a59f30e4939a658162b0a9e57f",
    "Aleph-Alpha/Kolibri-1": "e52eb4627d11516b0c01de49210ab5a4e4061444",
}


def _r(repo, title, size=None, unit="GiB", *, backends=("metal", "cuda"), machines=1, nvfp4=False, convert=False,
       context=None, scope="", note="", pull=None) -> dict:
    pull = pull or (f"tensorfold pull {repo}@{PINS[repo]}" if repo in PINS else None)
    nbytes = int(size * (GIB if unit == "GiB" else GB)) if size else None
    return {"repo": repo, "title": title, "size_bytes": nbytes, "size_words": f"{size:g} {unit}" if size else None,
            "backends": tuple(backends), "machines": machines, "nvfp4": nvfp4, "convert": convert, "context": context,
            "scope": scope, "note": note, "pull": pull or f"tensorfold pull {repo}", "listed_by": _SRC}


ROWS = [
    _r("mlx-community/Qwen3.5-2B-MLX-4bit", "Qwen3.5-2B MLX 4-bit", scope="one Mac (M5 Max checked) or one GB10",
       note="text only; the quick start's model", pull="tensorfold pull mlx-community/Qwen3.5-2B-MLX-4bit@93760be4f1f69842a46bc13dbdc0f19e291392a3"),
    _r("TensorFold/Qwen3.8-27B-MLX-4bit", "Qwen3.8-27B MLX 4-bit", 16, context=32768,
       scope="one Mac (M5 Max / M3 Ultra) or one GB10", note="add --drafter z-lab/Qwen3.8-27B-DFlash2 for drafts"),
    _r("TensorFold/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-MLX-4bit", "Nemotron 3.5 Lightning 30B-A3B MLX 4-bit",
       scope="one Mac (M1-M5) or one GB10; also checked on RTX 3090 / RTX PRO 6000", note="includes MTP"),
    _r("TensorFold/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-oQ4", "Nemotron 3.5 Lightning oQ4", backends=("metal",),
       scope="one M3 Ultra checked", note="Metal only"),
    _r("nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4", "Nemotron 3.5 Lightning NVFP4", backends=("cuda",),
       nvfp4=True, scope="one GB10 checked; sm_80 to sm_89 cards use a fallback path"),
    _r("nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4", "Nemotron 3.5 Super VL 120B-A12B NVFP4", 70.8,
       backends=("cuda",), nvfp4=True, scope="one or two GB10s; 73.2 GiB with vision", note="--vision for images"),
    _r("nvidia/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB", "Nemotron 3.5 Bolt 74B-A9B", 24, "GB", backends=("cuda",),
       scope="native CUDA, checked on RTX PRO 6000", pull="NVIDIA's checkpoint on the Hub (hf download "
                                                          "nvidia/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB)"),
    _r("TensorFold/Qwen3.8-Flash-Next-MLX-6bit-MTP", "Qwen3.8 Flash Next MLX 6-bit", backends=("metal",),
       scope="one M5 Ultra checked; RAM minimum not published"),
    _r("TensorFold/Qwen3.8-Flash-Next-MLX-4bit-MTP", "Qwen3.8 Flash Next MLX 4-bit", 73.3,
       scope="one GB10 (73.3 GiB uploaded, plus mapped tables and caches); Metal 4-bit on an M3 Ultra too"),
    _r("TensorFold/GLM-5.3-Flash-MLX-4bit-MTP", "GLM-5.3-Flash MLX 4-bit", backends=("metal",), machines=2,
       scope="two M5 Ultras; single-Mac native serving is not qualified"),
    _r("Mia-AiLab/GLM-5.3-Flash-EXL3-TR3-4bpw", "GLM-5.3-Flash EXL3/TR3", backends=("cuda",), machines=2,
       scope="two CUDA ranks (two GB10s)"),
    _r("nvidia/GLM-5.3-Flash-NVFP4", "GLM-5.3-Flash NVFP4", 190.4, backends=("cuda",), machines=2, nvfp4=True,
       scope="two GB10s at TP=2", pull="tensorfold pull nvidia/GLM-5.3-Flash-NVFP4@423acf37583782c51c142d145aef733d72943d93"),
    _r("nvidia/GLM-5.3-Flash-FP4-Local", "GLM-5.3-Flash FP4-Local", 165.3, backends=("cuda",), machines=2,
       scope="two GB10s at TP=2, or three at TP=3"),
    _r("Bizuayeu/GLM-5.3-Flash-XSFP4", "GLM-5.3-Flash XSFP4", 165.7, backends=("cuda",), machines=2,
       scope="two GB10s at TP=2, or three at TP=3"),
    _r("kindlingai/glm-5.3-exlr8-k2-k3-k4", "GLM-5.3 EXLR8 home", 160, "GB", backends=("metal",), machines=2,
       scope="two 256 GB M5 Ultra Macs, about 160 GB resident on each", note="Thunderbolt 5 and MCDMA; no CUDA backend"),
    _r("LiquidAI/LFM2.5-24B-A2B-MLX-4bit", "LFM2.5-24B-A2B MLX 4-bit", backends=("metal",), scope="one Mac (M4 Pro checked)"),
    _r("LiquidAI/LFM2.5-24B-A2B-MLX-8bit", "LFM2.5-24B-A2B MLX 8-bit", backends=("metal",), scope="one Mac (M4 Pro checked)"),
    _r("TensorFold/Qwen3.6-35B-A3B-MLX-4bit-MTP", "Qwen3.6-35B-A3B MLX 4-bit MTP", 20.9, "GB", backends=("cuda",),
       scope="one GB10; native CUDA", note="the recipe's Metal path is the older Python engine's: not native on a Mac"),
    _r("nvidia/Qwen3.6-35B-A3B-NVFP4", "Qwen3.6-35B-A3B NVFP4", 20.9, backends=("cuda",), nvfp4=True,
       scope="one GB10; 20.3 GiB on the device, 20.9 GiB with the drafter"),
    _r("mlx-community/gemma-4-31B-it-4bit", "Gemma 4 31B MLX 4-bit", backends=("metal",),
       scope="one M5 Mac (M5 Ultra checked); M1-M4 refused", note="name the drafter with --drafter"),
    _r("google/gemma-4-12B-it", "Gemma 4 12B (converted MLX 4-bit)", 6.3, "GB", backends=("metal",), convert=True,
       scope="one M5 Mac; M1-M4 refused; 6.3 GB of converted text weights, 100 MB of image weights",
       pull="hf download google/gemma-4-12B-it, then the recipe's conversion (Python, mlx and mlx-lm)"),
    _r("stepfun-ai/Step-5-Preview", "Step-5-Preview (converted affine)", 166.9, backends=("metal",), convert=True,
       scope="one 256 GB Mac; MTP adds 2.5 GiB, vision 3.7 GiB", pull="hf download stepfun-ai/Step-5-Preview, then the "
                                                                    "recipe's conversion (Python and mlx)"),
    _r("BobClawblaw/MiniMax-M3.1-Flash-MLX-mix34", "MiniMax-M3.1-Flash MLX mix34", 203.7, backends=("metal",),
       context=32768, scope="one 256 GB M5 Ultra (189.2 GiB at a 147,456-token window for mix256k)",
       pull="hf download BobClawblaw/MiniMax-M3.1-Flash-MLX-mix34"),
    _r("Aleph-Alpha/Kolibri-1", "Kolibri-1 block FP8", 74, "GB", backends=("cuda",), scope="one NVIDIA GPU (GB10 measured)",
       note="text only, research"),
]


def _n(text) -> str:
    return str(text or "").strip().lower().removeprefix("hf:local/").split("@", 1)[0]


def get(repo) -> Optional[dict]:
    want = _n(repo)
    return next((r for r in ROWS if r["repo"].lower() == want), None)


def match(text) -> Optional[dict]:
    want = _n(text)
    if not want:
        return None
    hit = get(want)
    if hit is not None:
        return hit
    base = want.rsplit("/", 1)[-1]
    return next((r for r in ROWS if r["repo"].lower().rsplit("/", 1)[-1] == base), None)


def listed(q: str = "") -> bool:
    if "tensorfold" in str(q or "").lower():
        return True
    from halo_harness.doctor_tensorfold import configured
    return configured()


def library_rows(q: str = "") -> list:
    words = [w for w in str(q or "").lower().split() if w and w != "tensorfold"]
    out = []
    for r in ROWS:
        hay = f"{r['repo']} {r['title']} {' '.join(r['backends'])} tensorfold".lower()
        if words and not all(w in hay for w in words):
            continue
        out.append({"source": "hf", "id": f"tensorfold:{r['repo']}", "tag_or_file": "", "name": r["title"],
                    "family": r["title"].split(" ")[0], "params": None, "quant": None, "size_bytes": r["size_bytes"],
                    "weights_bytes": r["size_bytes"], "projector_bytes": 0, "capabilities": ["tools"],
                    "context": r["context"], "downloads": None, "updated": None, "license": "", "gated": False,
                    "description": f"a TensorFold model ({r['scope']}){': ' + r['note'] if r['note'] else ''}",
                    "pull_line": r["pull"] + "   (the download is yours to run)", "kind": "tensorfold",
                    "key": f"tf:{r['repo']}", "shape": None, "runtime": "tensorfold",
                    "sources": {"listing": _SRC, "size": "the size TensorFold states" if r["size_bytes"] else "not stated"}})
    return out
