"""halo_harness.models_library.search_filters -- Halo 3.3.6.0 R2: the F2 filters on fit, resources, supply,
licence and platform (models_library/search.py ranks what passes).

    keep_fit(row, fit_f, ctx) -> (ok, why)        fits_at, fully_on_gpu, co_resides_with, quant_max, params_max,
                                                  disk_max_gb, speed_min, cold_load_max_s, kv_efficiency (KB/token)
    keep_supply(row, supply, ctx) -> (ok, why)    licence, gated, source, runs_here, ollama_supports,
                                                  fresh_within_months (exclude_crashed greys, search.py)
    runs_here(row, host_card) -> (ok, why)        MLX only on a Mac; CUDA on NVIDIA, ROCm / Vulkan on AMD (Ollama)
    ollama_supports(row, version) -> (ok | None, why)   the architecture against the host's Ollama version
    quant_bits(q), licence_class(lic), months_old(text)

`ctx` = {host_card, budget, window, cost, version}. LOADS is the knowledge's table of architectures per version:
each was seen loading on that Ollama release (ollama_steward/knowledge: the measured host ran 0.40.6 and 0.40.13);
an architecture not in it, or seen only on a newer release, "may not load on <version>".
"""

from __future__ import annotations

import re
from typing import Optional

NEWEST_KNOWN = "0.40.13"
LOADS = {a: "0.40.6" for a in ("llama", "qwen2", "qwen3", "qwen3moe", "qwen35", "qwen35moe", "qwen3next", "qwen3vl",
                               "gemma2", "gemma3", "phi3", "gptoss", "deepseek2", "nomicbert", "bert", "mistral3",
                               "lfm2", "mllama", "granite", "command-r", "glm4", "nemotronh", "qwen25vl")}
PERMISSIVE = ("apache", "mit", "bsd", "openrail", "cc-by-4", "cc0", "unlicense", "isc")
RESEARCH = ("nc", "non-commercial", "research", "noncommercial")
RESTRICTED = ("llama", "gemma", "qwen", "deepseek", "other", "openai", "nvidia", "mistral", "falcon")
LICENCE_CLASSES = ("permissive", "research", "restricted", "unknown", "other")
_Q = re.compile(r"(?:^|[^a-z])(?:i?q)(\d)|(\d+)\s*-?bit|^(?:b?f)(16|32)$|mxfp(\d)", re.I)
_AGO = re.compile(r"(\d+|an?|one)\s+(minute|hour|day|week|month|year)s?\s+ago", re.I)
_UNIT_MONTHS = {"minute": 0.0, "hour": 0.0, "day": 1 / 30, "week": 0.25, "month": 1.0, "year": 12.0}


def quant_bits(q) -> Optional[int]:
    """Q4_K_M -> 4, IQ3_XS -> 3, 8bit -> 8, F16 -> 16, MXFP4 -> 4; None when it does not say."""
    t = str(q or "").strip()
    m = _Q.search(t)
    if not m:
        return None
    return int(next(g for g in m.groups() if g))


def licence_class(lic) -> str:
    t = str(lic or "").lower()
    if not t:
        return "unknown"
    if any(w in t for w in RESEARCH):
        return "research"
    if any(w in t for w in PERMISSIVE):
        return "permissive"
    return "restricted" if any(w in t for w in RESTRICTED) else "other"


def months_old(text, now_iso: str = "") -> Optional[float]:
    """"2 weeks ago" -> 0.25; "2026-08-14" -> months before today; None when it does not say."""
    t = str(text or "").strip()
    m = _AGO.search(t)
    if m:
        n = 1 if m.group(1).lower() in ("a", "an", "one") else int(m.group(1))
        return n * _UNIT_MONTHS[m.group(2).lower()]
    if re.match(r"^\d{4}-\d\d-\d\d", t):
        import datetime as _dt
        try:
            then = _dt.date.fromisoformat(t[:10])
            today = _dt.date.fromisoformat(now_iso[:10]) if now_iso else _dt.date.today()
            return max(0.0, (today - then).days / 30.44)
        except ValueError:
            return None
    return None


def _vt(v) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", str(v or ""))[:3]) or (0,)


def arch_of(row: dict) -> str:
    fam = str(row.get("family") or "").lower()
    if not fam:
        fam = next((t for t in (str(x).lower() for x in row.get("tags") or []) if re.sub(r"[_.-]", "", t) in LOADS), "")
    return re.sub(r"[_.\-\s]", "", fam)


def ollama_supports(row: dict, version) -> "tuple[Optional[bool], str]":
    if row.get("kind") == "mlx":
        return None, "an MLX model: Ollama does not serve it (halo local serve does)"
    arch, v = arch_of(row), str(version or "")
    if not v:
        return None, "the host's Ollama version is not read yet"
    seen = LOADS.get(arch)
    if seen and _vt(seen) <= _vt(v):
        return True, f"{arch} loads on Ollama {seen} and later (the knowledge)"
    fresh = months_old(row.get("updated"))
    if seen or (fresh is not None and fresh <= 3) or not arch:
        what = f"{arch} was seen loading on {seen}" if seen else (f"{arch} is not in the table of architectures"
                                                                   if arch else "its architecture is not known")
        return None, f"may not load on {v}: {what}"
    return True, f"{arch} is older than {v} (not in the table, not new)"


def platform_of(host_card: Optional[dict]) -> str:
    gpus = [g for g in (host_card or {}).get("gpus") or [] if isinstance(g, dict)]
    libs = {str(g.get("library") or "").lower() for g in gpus}
    if "metal" in libs or (host_card or {}).get("unified") and not libs - {"metal", ""}:
        return "mac"
    if "cuda" in libs:
        return "nvidia"
    if libs & {"rocm", "vulkan", "hip"}:
        return "amd"
    return "cpu" if host_card else ""


def runs_here(row: dict, host_card: Optional[dict]) -> "tuple[bool, str]":
    plat = platform_of(host_card)
    if row.get("kind") == "mlx":
        return plat == "mac", "MLX runs on Apple silicon only" + ("" if plat == "mac" else f" (this host: {plat or 'unknown'})")
    word = {"nvidia": "CUDA on NVIDIA", "amd": "ROCm / Vulkan on AMD", "mac": "Metal on Apple silicon",
            "cpu": "the CPU (no GPU on the card)", "": "Ollama (no hardware card read yet)"}[plat]
    return True, f"a GGUF through Ollama: {word}"


def keep_fit(row: dict, f: dict, ctx: dict) -> "tuple[bool, str]":
    fit, nums, cost = row.get("fit") or {}, (row.get("fit") or {}).get("numbers") or {}, row.get("cost") or {}
    level = fit.get("level")
    known = bool(ctx.get("host_card"))  # no hardware card read: the fit is unknown, the row stays (fit "?")
    if f.get("fits_at") and level not in ("fits", "tight") and (known or level != "unknown"):
        return False, f"does not fit at {ctx.get('window') or 0:,} ({level})"
    if f.get("fully_on_gpu") and level != "fits" and (known or level != "unknown"):
        return False, f"not fully on the GPU at {ctx.get('window') or 0:,} ({level})"
    for other in [x for x in (f.get("co_resides_with") or []) if x]:
        held = next((int(x.get("size") or 0) for x in (ctx.get("host_card") or {}).get("loaded") or []
                     if str(x.get("model") or "").split(":")[0] == other.split(":")[0]), None)
        held = held if held is not None else int((ctx.get("sizes") or {}).get(other) or 0)
        if not nums.get("total") or not held or nums["total"] + held > int(ctx.get("budget") or 0):
            return False, f"does not fit beside {other}"
    bits, qmax = quant_bits(row.get("quant")), quant_bits(f.get("quant_max"))
    if qmax and (bits is None or bits > qmax):
        return False, f"quant {row.get('quant') or '?'} over {f['quant_max']}"
    p = row.get("params")
    if f.get("params_max") and (not isinstance(p, (int, float)) or p > float(f["params_max"])):
        return False, f"{p or '?'}B over {f['params_max']}B"
    size = row.get("size_bytes")
    if f.get("disk_max_gb") and (not isinstance(size, int) or size > float(f["disk_max_gb"]) * 1e9):
        return False, f"{(size or 0) / 1e9:.1f} GB on disk over {f['disk_max_gb']} GB"
    tok = cost.get("tok_s_expected")
    if f.get("speed_min") and (not isinstance(tok, (int, float)) or tok < float(f["speed_min"])):
        return False, f"~{tok or '?'} tok/s under {f['speed_min']}"
    cold = cost.get("cold_load_s")
    if f.get("cold_load_max_s") and (not isinstance(cold, (int, float)) or cold > float(f["cold_load_max_s"])):
        return False, f"cold load ~{cold or '?'} s over {f['cold_load_max_s']} s"
    kv = kv_kb_per_token(row)
    if f.get("kv_efficiency") and (kv is None or kv > float(f["kv_efficiency"])):
        return False, f"{kv or '?'} KB of cache a token over {f['kv_efficiency']}"
    return True, ""


def kv_kb_per_token(row: dict) -> Optional[int]:
    nums = (row.get("fit") or {}).get("numbers") or {}
    if nums.get("kv") and nums.get("window"):
        return round(nums["kv"] / nums["window"] / 1024)
    return None


def keep_supply(row: dict, s: dict, ctx: dict) -> "tuple[bool, str]":
    lic = s.get("licence") or s.get("license")
    if lic:
        cls = licence_class(row.get("license"))
        ok = (cls != "unknown" if lic == "known" else cls == lic if lic in LICENCE_CLASSES
              else str(lic).lower() in str(row.get("license") or "").lower())
        if not ok:
            return False, f"licence {row.get('license') or 'unknown'} ({cls})"
    if s.get("gated") is False and row.get("gated"):
        return False, "gated on the hub"
    if s.get("gated") is True and not row.get("gated"):
        return False, "not gated"
    src = s.get("source")
    if src:
        mine = "ollama" if row.get("source") == "ollama" else "mlx" if row.get("kind") == "mlx" else "hf-gguf"
        if src not in (mine, row.get("source"), row.get("kind")):
            return False, f"from {mine}"
    if s.get("runs_here"):
        ok, why = runs_here(row, ctx.get("host_card"))
        if not ok:
            return False, why
    if s.get("ollama_supports"):
        ok, why = ollama_supports(row, ctx.get("version"))
        if ok is None and why.startswith("may not load"):
            return False, why
    if s.get("fresh_within_months"):
        m = months_old(row.get("updated"))
        if m is None or m > float(s["fresh_within_months"]):
            return False, f"updated {row.get('updated') or 'when, unknown'}"
    return True, ""
