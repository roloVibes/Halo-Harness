"""halo_harness.local_sched.bundle_options -- the ways out a verdict names, each a number (Halo 3.3.7.0 R5;
plans/local-model-fit-brief.md L3: "Options: run STT on CPU (-1.5 GB); the 1.7 B voice model instead of the 7 B (-3 GB);
the coder's window 32 k -> 16 k frees 4 GB").

    options(bundle, picks, res, coder, *, total, free, reserve_gb, rd) -> [{says, frees_gb, kind}]
        warn     what would break a bundle that fits ("GPU STT (faster-whisper:large-v3-turbo, 1.5 GB) would break that:
                 the coder would no longer fit beside it"), frees_gb negative
        device   a speech model on the GPU run on the CPU instead
        smaller  a smaller model of the need's own any_of (the adviser's budget arithmetic: weights + KV at its window)
        window   the coder's window halved; a need's window down to 8 k
        claims   another bundle turned off
        instead  an installed model like one the bundle would download (models_library/nearest.py), saving the download
Warnings first, then the ways out by what they free, at most MAX. Arithmetic only.
"""

from __future__ import annotations

from typing import Optional

GIB = 2 ** 30
MAX = 4
FLOOR = 8192


def _k(n: int) -> str:
    return f"{n // 1024} k"


def _warns(picks: dict, coder: Optional[dict], total: float, free: float) -> list:
    out = []
    for p in picks.values():
        if p["runtime"] != "voice" or p["placed"] != "cpu" or p["device"] != "cpu-or-gpu" or not p.get("gpu_gb"):
            continue
        more = total + float(p["gpu_gb"])
        coder_gb = float((coder or {}).get("gb") or 0)
        if more > free:
            why = "the bundle would no longer fit"
        elif coder_gb and total + coder_gb <= free < more + coder_gb:
            why = "the coder would no longer fit beside it"
        else:
            continue
        out.append({"kind": "warn", "frees_gb": -float(p["gpu_gb"]),
                    "says": f"GPU {p['role'].upper()} ({p['gpu_model']}, {p['gpu_gb']:.1f} GB) would break that: {why}"})
    return out


def _installed(rd) -> list:
    from halo_harness.local_sched import facts as F
    if rd.host is None or F._guarded("catalog", rd.host):
        return []
    from halo_harness.studio import ollama_hosts_view as V
    return [r for r in (V.catalog_of(rd.host) or {}).get("models") or [] if isinstance(r, dict)]


def _ways(bundle: dict, picks: dict, res: Optional[dict], coder: Optional[dict], rd, reserve_gb: float) -> list:
    out = []
    for p in picks.values():
        if p["runtime"] == "voice" and p["placed"] == "gpu" and p.get("gb"):
            out.append({"kind": "device", "frees_gb": round(float(p["gb"]), 1),
                        "says": f"run {p['role']} on the CPU instead of the GPU (-{p['gb']:.1f} GB)"})
        if p["runtime"] != "ollama" or p["placed"] != "gpu" or not p.get("gb"):
            continue
        base = float((res or {}).get("gb") or p["gb"]) if (res or {}).get("role") == p["role"] else float(p["gb"])
        for s in p.get("smaller") or []:
            if base - s["gb"] >= 0.5:  # a smaller model that frees less than half a GB is not a way out
                out.append({"kind": "smaller", "frees_gb": round(base - s["gb"], 1),
                            "says": f"the {s['words']} {s['model']} instead of the {p.get('words') or p['model']} "
                                    f"{p['model']} for {p['role']} (-{base - s['gb']:.1f} GB)"})
                break
        w = p.get("window") or 0
        if w > FLOOR:
            got = rd.need(p["model"], FLOOR)
            if got.get("bytes"):
                freed = round(base - got["bytes"] / GIB, 1)
                if freed >= 0.1:
                    out.append({"kind": "window", "frees_gb": freed,
                                "says": f"{p['role']}'s window {_k(w)} -> {_k(FLOOR)} frees {freed:g} GB"})
    if coder and coder.get("gb") and int(coder.get("window") or 0) >= 2 * FLOOR:
        half = int(coder["window"]) // 2
        got = rd.need(coder["model"], half)
        if got.get("bytes"):
            freed = round(float(coder["gb"]) - got["bytes"] / GIB, 1)
            if freed >= 0.1:
                out.append({"kind": "window", "frees_gb": freed,
                            "says": f"the coder's window {_k(int(coder['window']))} -> {_k(half)} frees {freed:g} GB"})
    return out


def _claims(bundle: dict, rd) -> list:
    from halo_harness.local_sched.reserve import claims
    out = []
    for c in claims(rd.host, state_dir=rd.state_dir) if rd.host is not None else []:
        if c.get("bundle") != bundle["id"] and float(c.get("gb") or 0) > 0:
            out.append({"kind": "claims", "frees_gb": float(c["gb"]),
                        "says": f"turn {c['bundle']} off (halo pack off {c['bundle']}) frees {float(c['gb']):.1f} GB"})
    return out


def _instead(picks: dict, rd) -> list:
    from halo_harness.models_library.nearest import nearest
    rows = None
    out = []
    for p in picks.values():
        if p["runtime"] != "ollama" or p.get("installed") is not False or not p.get("model"):
            continue
        rows = _installed(rd) if rows is None else rows
        near = nearest(p["model"], rows, window=p.get("window"))
        if near:
            out.append({"kind": "instead", "frees_gb": 0.0, "saves_download_gb": p.get("download_gb"),
                        "says": f"use {near['name']} (installed: {near['line']}) instead of downloading {p['model']}"
                                + (f" (saves {p['download_gb']:g} GB)" if p.get("download_gb") else "")})
    return out


def options(bundle: dict, picks: dict, res: Optional[dict], coder: Optional[dict], *, total: float, free: float,
            reserve_gb: float, rd) -> list:
    warns = _warns(picks, coder, total, free)
    ways = _ways(bundle, picks, res, coder, rd, reserve_gb) + _claims(bundle, rd)
    ways.sort(key=lambda o: (-o["frees_gb"], o["says"]))
    return warns + ways[:MAX] + _instead(picks, rd)
