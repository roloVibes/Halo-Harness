"""halo_harness.strata.catalog -- the families and sets Strata names (its README.md, docs/MODELS.md, docs/DETAILS.md
"Which model?" and docs/TERMINAL_LAUNCH.md, read 2026-11-02 at main ffa80d73: from the source, unverified against a live
run), as download targets the Library lists with a Strata fit badge (Halo 3.3.9.2; docs/MODELS-strata.md "The sets").

    ROWS: [{family, set, model, provider, download_gb, experts_gb, ram_gb, memory_gb, ssd_gb, first_gb, rule,
            nvidia_only, mac, context, measured: [(hardware, vram_gb, tok_s words)], note}]
        family / set: what `strata launch --family F --model S` takes; model: the model's own name
        download_gb: the set's download (None where Strata states none for it); experts_gb: the experts held in RAM;
        ram_gb / memory_gb: the RAM (or RAM + VRAM) figure the docs state; ssd_gb: what stays on the SSD (Flash-Next's
        29 GB n-gram table); first_gb: what the first start fetches beside the set (the MTP draft layer, ~6 GB)
        rule: experts | all-experts | memory | plan | deepseek -- which of Strata's memory statements the fit reads
    get(family, set) -> row | None    parse(text) -> row | None ("qwen/iq3_xxs", "deepseek41/ist-das-2.00bpw", "IQ3_XXS")
    match(text) -> row | None   a served model id or a lane's model ("hf:local/qwen3.8-flash-next-iq3_xxs@pc")
    measured_for(row, vram_gb) -> (tok/s words, hardware) | None   the docs' measured row on the biggest card at or
        under this one (the smallest measured when none is)
    set_name(row) -> "qwen3.8-flash-next-iq3_xxs"   launch_words(row) -> the `strata launch` command the user runs
    library_rows(q="") -> [LibraryRow]   kind "strata"; listed(q="") -> the search names strata, or it is configured
"""

from __future__ import annotations

from typing import Optional

_SRC = "Strata's README.md and docs/MODELS.md (from the source, unverified against a live run)"
_FN = "Qwen3.8-Flash-Next"
_RTX5070 = "RTX 5070 12 GB, 64 GB RAM (engine 0.1.26, short chat)"


def _r(family, set_, model, provider, dl, experts, *, ram=None, mem=None, ssd=0.0, first=0.0, rule="experts",
       nvidia=False, mac=True, ctx=None, measured=(), note="") -> dict:
    return {"family": family, "set": set_, "model": model, "provider": provider, "download_gb": dl,
            "experts_gb": experts, "ram_gb": ram, "memory_gb": mem, "ssd_gb": ssd, "first_gb": first, "rule": rule,
            "nvidia_only": nvidia, "mac": mac, "context": ctx, "measured": list(measured), "note": note,
            "listed_by": _SRC}


def _fn(set_, dl, experts, mem, tok, family="qwen", provider="ISTA-DASLab", note=""):
    return _r(family, set_, _FN, provider, dl, experts, mem=mem, ssd=29.0, first=6.0,
              measured=[(_RTX5070, 12, tok)] if tok else [], note=note)


def _ud(set_, dl, experts_gib, ram, tok):
    return _r("unsloth", set_, _FN, "Unsloth", dl, round(experts_gib * 1.073741824, 1), ram=ram, ssd=29.0, first=6.0,
              rule="all-experts", measured=[("Radeon AI PRO R9700 32 GB", 32, tok)] if tok else [])


_DS = [("RTX 5070 12 GB, 64 GB RAM (2.00 bpw)", 12, "4 to 6"), ("RTX 3060 12 GB, 46 GB RAM (2.00 bpw)", 12, "9 to 11"),
       ("1x Radeon AI PRO R9700, 251 GB RAM (2.00 bpw)", 32, "21 to 25")]


def _ds(set_, dl, note=""):
    return _r("deepseek41", set_, "DeepSeekV4.1-Flash-1017", "ISTA-DAS" if set_.startswith("ist") else "Unsloth", dl,
              None, ram=64.0, ssd=dl, rule="deepseek", ctx=8192, measured=_DS,
              note=note or "what does not fit in memory is read from the SSD: keep about the download free on an NVMe")


ROWS = [
    _fn("Q2_0", 66.0, 34.0, 37.6, "94"), _fn("IQ2_XS", 68.0, 35.5, 39.2, "79"), _fn("IQ3_XXS", 76.0, 43.0, 47.0, "62"),
    _fn("IQ3_S", None, 50.0, 54.8, "53", note="matches the full model on the published tests"),
    _fn("IQ1_M", None, 23.0, 29.6, "55", family="coder", note="the Coder: 256 of each layer's 512 experts, for code"),
    _fn("IQ2_XS", None, 35.5, 39.2, None, family="swift", provider="UkisAI (Swift 1.5)",
        note="a fine-tune that thinks shorter; its own license"),
    _ud("UD-IQ4_XS", 94.0, 55, 72.0, None), _ud("UD-Q4_K_XL", 111.0, 72, 88.0, "63"),
    _ud("UD-Q5_K_XL", 158.0, 92, 108.0, "57 to 60"), _ud("UD-Q6_K_XL", 169.0, 102, 118.0, "54"),
    _ud("Q8_0", 188.0, 120, 136.0, "53 to 57"),
    _r("gyro", "Gyro-S", _FN, "agentionai (Gyro)", 58.5, None, mem=27.6, ssd=28.0, rule="memory", note="lower quality"),
    _r("gyro", "Gyro-M", _FN, "agentionai (Gyro)", 92.0, None, mem=35.0, ssd=28.0, rule="memory"),
    _r("nvfp4", "NVFP4", _FN, "Strata's NVFP4", 128.0, 80.0, ram=80.0, rule="all-experts", nvidia=True, mac=False),
    _r("nvfp4", "NVFP4-NVIDIA", _FN, "NVIDIA's NVFP4", 128.0, 80.0, ram=80.0, rule="all-experts", nvidia=True, mac=False),
    _r("nvfp4", "NVFP4-QAD", _FN, "NVIDIA (trained for FP4)", 102.0, 80.0, ram=80.0, rule="all-experts", nvidia=True,
       mac=False, note="+110 GB of disk while setup prepares it"),
    _r("qwen36", "UD-Q4_K_XL", "Qwen3.6-35B-A3B", "Unsloth", 22.9, None, ram=32.0, rule="plan", mac=False,
       measured=[("RTX 3060 12 GB, most experts on the CPU", 12, "59.7"), ("Radeon AI PRO R9700 32 GB", 32, "117.8")]),
    _r("qwen36", "UD-Q6_K_XL", "Qwen3.6-35B-A3B", "Unsloth", 32.6, None, ram=44.0, rule="plan", mac=False),
    _r("qwen36", "Q8_0", "Qwen3.6-35B-A3B", "Unsloth", 37.8, None, ram=52.0, rule="plan", mac=False),
    _ds("ist-das-1.75bpw", 239.0), _ds("ist-das-2.00bpw", 257.0), _ds("ist-das-2.25bpw", 274.0),
    _ds("ist-das-coder", 191.0, note="192 of the 384 experts in every layer kept, for code"),
    _ds("ud-q8_k_xl", 508.0),
]


def _n(text) -> str:
    return str(text or "").strip().lower().replace("-", "_").replace(".", "_")


def get(family, set_) -> Optional[dict]:
    return next((r for r in ROWS if r["family"] == str(family or "").lower() and _n(r["set"]) == _n(set_)), None)


def parse(text) -> Optional[dict]:
    """`<family>/<set>` as `strata launch` takes them, or a bare set (the first family that has it: qwen first)."""
    t = str(text or "").strip()
    if "/" in t:
        fam, _, s = t.partition("/")
        return get(fam, s)
    return next((r for r in ROWS if _n(r["set"]) == _n(t)), None)


def match(text) -> Optional[dict]:
    """The row a served model id or a lane's model names: its family's model name and the longest set it contains."""
    raw = str(text or "").strip()
    raw = (raw[len("hf:local/"):] if raw.lower().startswith("hf:local/") else raw).split("@", 1)[0]
    hit = parse(raw)
    if hit is not None:
        return hit
    t = _n(raw)
    named = [r for r in ROWS if _n(r["model"]) in t or ("deepseek" in t and r["family"] == "deepseek41")]
    best = sorted((r for r in named if _n(r["set"]) in t), key=lambda r: -len(_n(r["set"])))
    return best[0] if best else None


def measured_for(row: dict, vram_gb) -> "Optional[tuple]":
    rows = row.get("measured") or []
    if not rows:
        return None
    v = round(float(vram_gb or 0))
    under = [m for m in rows if m[1] <= v]  # the biggest measured card this one matches, else the smallest measured
    hw, _vram, tok = max(under, key=lambda m: (m[1], -rows.index(m))) if under else min(rows, key=lambda m: m[1])
    return tok, hw


def set_name(row: dict) -> str:
    """Halo's name for a set ("qwen3.8-flash-next-iq3_xxs"): the registry row's model until the server says its id, and
    the name its speed card is kept under (strata/bench.py)."""
    return f"{row['model']}-{row['set']}".lower()


def launch_words(row: dict) -> str:
    return f"strata launch --family {row['family']} --model {row['set']} --yes --no-tui --access local"


def listed(q: str = "") -> bool:
    if "strata" in str(q or "").lower():
        return True
    from halo_harness.doctor_strata import configured
    return configured()


def library_rows(q: str = "") -> list:
    words = [w for w in str(q or "").lower().split() if w and w != "strata"]
    out = []
    for r in ROWS:
        hay = f"{r['model']} {r['family']} {r['set']} {r['provider']} strata moe".lower()
        if words and not all(w in hay for w in words):
            continue
        size = int(r["download_gb"] * 1e9) if r["download_gb"] else None
        out.append({"source": "hf", "id": f"strata:{r['family']}/{r['set']}", "tag_or_file": "",
                    "name": f"{r['model']} {r['set']}", "family": r["model"], "params": None, "quant": r["set"],
                    "size_bytes": size, "weights_bytes": size, "projector_bytes": 0, "capabilities": ["tools"],
                    "context": r["context"], "downloads": None, "updated": None, "license": "", "gated": False,
                    "description": f"a Strata set ({r['provider']}){': ' + r['note'] if r['note'] else ''}",
                    "pull_line": launch_words(r) + "   (Strata's download: yours to run)", "kind": "strata",
                    "key": f"st:{r['family']}/{r['set']}", "shape": None, "runtime": "strata",
                    "sources": {"listing": _SRC, "size": "the download Strata states" if size else "not stated"}})
    return out
