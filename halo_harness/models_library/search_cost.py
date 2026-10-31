"""halo_harness.models_library.search_cost -- Halo 3.3.6.0 R2: every search row's cost preview (F5).

    cost(row, fit, profile, host_card, *, budget, speeds) -> {download_gb, download_eta_s, line_from, vram_at_window,
        cold_load_s, cold_from, tok_s_expected, tok_from, evicts [model], installed, text}
    speeds(state_dir, host_name, profiles) -> {line_bps, line_from, disk_bps, disk_from, k_gbps, k_from}
    active_params(name, params) -> the billions read per token (a mixture of experts reads its active ones)

Each number says where it came from: the download's eta from the last pull's measured speed, else an assumed line
(ASSUMED_LINE_BPS); the cold load from this model's measured load, else this host's measured disk speed (the probed
models' size / cold load), else an assumed one; tok/s from the profile when probed, else this host's measured
"GB read per second" (tok/s x active GB of the probed models) over the row's active weights, else an assumed
ASSUMED_GBPS; `evicts` the resident models (`/api/ps` on the host card) it would push out to fit.
"""

from __future__ import annotations

import re
import statistics
from typing import Optional

ASSUMED_LINE_BPS = 50e6     # 400 Mbit/s
ASSUMED_DISK_BPS = 0.6e9    # the measured host: 20-55 s a load of 12-20 GB (the brief, G5)
ASSUMED_GBPS = 400.0        # decode reads the active weights once a token: a 4090-class card does ~400 GB/s of it
SPILL_SLOWDOWN = 5.0
MOE_ACTIVE = {"qwen3-coder:30b": 3.3, "qwen3:30b": 3.3, "qwen3:235b": 22.0, "qwen3-coder:480b": 35.0,
              "gpt-oss:20b": 3.6, "gpt-oss:120b": 5.1, "deepseek-r1:671b": 37.0, "deepseek-v3:671b": 37.0,
              "mixtral:8x7b": 12.9, "mixtral:8x22b": 39.0}
_ACTIVE = re.compile(r"-a(\d+(?:\.\d+)?)b", re.I)


def active_params(name: str, params) -> Optional[float]:
    low = str(name or "").lower().split("/")[-1]
    m = _ACTIVE.search(low)
    if m:
        return float(m.group(1))
    for k, v in MOE_ACTIVE.items():
        if low.startswith(k):
            return v
    return float(params) if isinstance(params, (int, float)) and params > 0 else None


def _median(xs) -> Optional[float]:
    xs = [x for x in xs if isinstance(x, (int, float)) and x > 0]
    return statistics.median(xs) if xs else None


def _pull_speed(state_dir) -> Optional[float]:
    try:
        from halo_harness.studio import local_pull_job as J
        jobs = list(J.current("pull")["jobs"]) + (J.read_file(state_dir) if state_dir is not None else [])
    except Exception:
        return None
    done = sorted((j for j in jobs if j.get("ok") and isinstance(j.get("speed"), (int, float)) and j["speed"] > 0),
                  key=lambda j: -float(j.get("started") or 0))
    return float(done[0]["speed"]) if done else None


def speeds(state_dir, host_name: str, profiles: list) -> dict:
    mine = [p for p in profiles or [] if not host_name or p.get("host") == host_name]
    disk = _median([(p.get("size_gb") or 0) * 1e9 / p["speed"]["cold_load_s"] for p in mine
                    if isinstance((p.get("speed") or {}).get("cold_load_s"), (int, float)) and p["speed"]["cold_load_s"] > 0])
    ks = []
    for p in mine:
        tok, size = (p.get("speed") or {}).get("tok_s"), p.get("size_gb")
        if isinstance(tok, (int, float)) and isinstance(size, (int, float)) and size > 0:
            from halo_harness.providers.model_card_purpose import params_of
            total = params_of(p.get("model") or "")[0]
            act = active_params(p.get("model") or "", total)
            share = act / total if act and total else 1.0
            ks.append(tok * size * share)
    k = _median(ks)
    line = _pull_speed(state_dir)
    return {"line_bps": line or ASSUMED_LINE_BPS,
            "line_from": f"measured {line / 1e6:.0f} MB/s (the last pull)" if line else f"assumed {ASSUMED_LINE_BPS / 1e6:.0f} MB/s",
            "disk_bps": disk or ASSUMED_DISK_BPS,
            "disk_from": (f"measured {disk / 1e9:.1f} GB/s (this host's probed loads)" if disk else
                          f"assumed {ASSUMED_DISK_BPS / 1e9:.1f} GB/s"),
            "k_gbps": k or ASSUMED_GBPS,
            "k_from": f"this host's probed models ({k:.0f} GB/s read)" if k else f"an assumed {ASSUMED_GBPS:.0f} GB/s read"}


def evicts(total: int, host_card: Optional[dict], budget: int, name: str = "") -> list:
    """The resident models this one would push out to fit (largest first), [] when it fits beside them."""
    from halo_harness.providers.ollama import ollama_names_match
    loaded = [x for x in (host_card or {}).get("loaded") or [] if isinstance(x, dict) and x.get("model")]
    if not loaded or any(name and ollama_names_match(x["model"], name) for x in loaded):
        return []
    held = lambda x: int(x.get("size_vram") or x.get("size") or 0)  # noqa: E731
    free = budget - sum(held(x) for x in loaded)
    out = []
    mx = ((host_card or {}).get("server") or {}).get("max_loaded")
    if isinstance(mx, int) and mx > 0 and len(loaded) >= mx:
        first = min(loaded, key=lambda x: str(x.get("expires") or ""))
        out.append(first)
        free += held(first)
    for x in sorted((x for x in loaded if x not in out), key=held, reverse=True):
        if total <= free:
            break
        out.append(x)
        free += held(x)
    return [x["model"] for x in out]


def _secs(s: Optional[float]) -> str:
    if not isinstance(s, (int, float)):
        return "?"
    return f"{s:.0f} s" if s < 90 else f"{s / 60:.0f} min" if s < 5400 else f"{s / 3600:.1f} h"


def cost(row: dict, fit: dict, profile: Optional[dict], host_card: Optional[dict], *, budget: int, speeds: dict) -> dict:
    size = row.get("size_bytes") if isinstance(row.get("size_bytes"), int) else None
    installed = bool(row.get("installed"))
    nums = (fit or {}).get("numbers") or {}
    total = int(nums.get("total") or 0) or None
    sp = (profile or {}).get("speed") or {}
    if isinstance(sp.get("cold_load_s"), (int, float)):
        cold, cold_from = float(sp["cold_load_s"]), "measured (its probe)"
    elif size:
        cold, cold_from = size / speeds["disk_bps"], speeds["disk_from"]
    else:
        cold, cold_from = None, "no size"
    if isinstance(sp.get("tok_s"), (int, float)):
        tok, tok_from = float(sp["tok_s"]), f"measured at {sp.get('at_window') or '?'} (its probe)"
    else:
        act = active_params(row.get("name") or "", row.get("params"))
        bpp = (size / (row["params"] * 1e9)) if size and isinstance(row.get("params"), (int, float)) and row["params"] > 0 else 0.606
        tok = round(speeds["k_gbps"] / (act * bpp), 0) if act else None
        level = (fit or {}).get("level")
        if tok and level == "spill":
            tok = round(tok / SPILL_SLOWDOWN, 0)
        tok = None if level == "no" or not host_card else tok
        tok_from = ("no hardware card read" if not host_card else
                    f"expected: {act:g}B active x {speeds['k_from']}" + (" / 5 (part on the CPU)" if level == "spill" else "")
                    if act else "no size to estimate from")
    ev = evicts(total or size or 0, host_card, budget, row.get("pull_target") or row.get("name") or "") if host_card else []
    out = {"download_gb": 0.0 if installed else round(size / 1e9, 2) if size else None,
           "download_eta_s": 0 if installed else round(size / speeds["line_bps"]) if size else None,
           "line_from": "installed" if installed else speeds["line_from"], "vram_at_window": total,
           "cold_load_s": round(cold, 1) if cold else None, "cold_from": cold_from,
           "tok_s_expected": tok, "tok_from": tok_from, "evicts": ev, "installed": installed}
    bits = [("installed" if installed else f"{out['download_gb']:g} GB, ~{_secs(out['download_eta_s'])} ({speeds['line_from']})")
            if out["download_gb"] is not None else "size unknown",
            f"{total / 2 ** 30:.1f} GiB at {int(nums.get('window') or 0):,}" if total else "VRAM unknown",
            f"cold load ~{_secs(out['cold_load_s'])}" if out["cold_load_s"] else "",
            f"~{tok:.0f} tok/s" + ("" if sp.get("tok_s") else " expected") if tok else "",
            ("evicts " + ", ".join(ev)) if ev else ""]
    out["text"] = " · ".join(b for b in bits if b)
    return out
