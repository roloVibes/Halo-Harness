"""halo_harness.models_library.advise_lines -- the roster adviser's words and its reads of the library snapshot (Halo
3.3.7.0 R4; plans/local-model-fit-brief.md Part J; models_library/advise.py runs it).

    facts(row) -> {name, base, stem, version, suffix, family, params_b, size_gb, purpose (code | embed | vision | chat)}
    superseded_by(name) -> {name, updated} | None   the library has the same line at a newer version (qwen2.5-coder ->
                                                    qwen3-coder; gemma3 -> gemma4), by the name's stem and suffix
    options(want, budget_gb, *, n=3, avoid_family=None) -> [{name, ref, download_gb, params_b, updated}]
        want: embed | vision | small | chat; the library's entries carrying it, most pulled first, each at its largest
        tag that fits the budget (small: the smallest tag under 3B)
    option_for(name, params_b, budget_gb) -> the entry at the tag nearest that size (freshness: the same size, newer)
    cost(download_gb, vram_gb, window, fits_beside) -> {download_gb, vram_gb, window, beside, minutes}
    say(s) -> one line: "[gap] ... -- unlocks ...; costs 0.3 GB download (~1 min at 40 MB/s), 0.3 GB VRAM at 8k,
               co-resides; add: ollama pull nomic-embed-text"
No request: the snapshot ships with Halo (models_library/snapshot.py).
"""

from __future__ import annotations

import math
import re
from typing import Optional

DOWNLOAD_MB_S = 40.0
_LINE = re.compile(r"^([a-z]+)(\d+(?:\.\d+)?)(.*)$")


def lineage(name: str) -> "Optional[tuple]":
    base = str(name or "").split(":", 1)[0].lower()
    m = _LINE.match(base)
    if not m:
        return None
    return m.group(1), tuple(int(x) for x in m.group(2).split(".")), m.group(3)


def purpose(name: str, caps=None) -> str:
    low, caps = str(name or "").lower(), [str(c).lower() for c in caps or []]
    if "embedding" in caps or "embed" in low or "minilm" in low:
        return "embed"
    if "code" in low:
        return "code"
    if re.search(r"vl\b|vl[:-]|vision|llava|moondream|minicpm-v", low):
        return "vision"
    return "chat"


def facts(row: dict) -> dict:
    from halo_harness.models_library.nearest import facts as nf
    name = str(row.get("model") or row.get("name") or "")
    f = nf(name, row)
    lin = lineage(name) or ("", (), "")
    size = row.get("size") if isinstance(row.get("size"), (int, float)) else None
    return {"name": name, "base": f["base"], "stem": lin[0] or f["base"].rstrip("0123456789.-"), "version": lin[1],
            "suffix": lin[2], "family": f["family"] or lin[0], "params_b": f["params_b"], "quant": f["quant"],
            "size_gb": round(size / 1e9, 1) if size else None,
            "purpose": purpose(name, row.get("capabilities")),
            "sees": "vision" in [str(c).lower() for c in row.get("capabilities") or []]}


def superseded_by(name: str) -> Optional[dict]:
    from halo_harness.models_library.snapshot import models
    me = lineage(name)
    if not me or not me[1]:
        return None
    best = None
    for e in models():
        other = lineage(e.get("name") or "")
        if other and other[0] == me[0] and other[2] == me[2] and other[1] > me[1]:
            if best is None or other[1] > best[0]:
                best = (other[1], e)
    return {"name": best[1]["name"], "updated": best[1].get("updated") or ""} if best else None


def _tags(e: dict) -> list:
    out = []
    for tag, m in (e.get("manifests") or {}).items():
        if isinstance(m, dict) and isinstance(m.get("total"), (int, float)):
            out.append((tag, m["total"] / 1e9, m.get("params"), m.get("family")))
    return sorted(out, key=lambda t: t[1])


def options(want: str, budget_gb: Optional[float], *, n: int = 3, avoid_family: Optional[str] = None) -> list:
    from halo_harness.models_library.snapshot import models
    room = (budget_gb or 24.0) * 0.9
    out = []
    for e in sorted(models(), key=lambda e: -int(e.get("pulls_n") or 0)):
        caps = [str(c).lower() for c in e.get("capabilities") or []]
        if (e.get("cloud") and not e.get("manifests")) or (want == "embed") != ("embedding" in caps)                 or (want == "vision" and "vision" not in caps):  # a cloud entry with local tags keeps them
            continue
        if want in ("small", "chat") and "tools" not in caps:
            continue
        if avoid_family and (lineage(e["name"]) or (e["name"],))[0] == avoid_family:
            continue
        tags = [t for t in _tags(e) if t[1] <= room]
        if want == "small":
            tags = [t for t in tags if isinstance(t[2], (int, float)) and t[2] <= 3.0]
        if not tags:
            continue
        tag = tags[-1] if want != "small" else tags[-1]
        ref = e["name"] if tag[0] == "latest" else f"{e['name']}:{tag[0]}"
        out.append({"name": e["name"], "ref": ref, "download_gb": round(tag[1], 1), "params_b": tag[2],
                    "updated": e.get("updated") or ""})
        if len(out) >= n:
            break
    return out


def option_for(name: str, params_b: Optional[float], budget_gb: Optional[float]) -> Optional[dict]:
    """The library entry `name` at the tag nearest `params_b` that fits the budget (freshness: the same size, newer)."""
    from halo_harness.models_library.snapshot import entry_of
    e = entry_of(name) or {}
    tags = [t for t in _tags(e) if t[1] <= (budget_gb or 24.0) * 0.9]
    if not tags:
        return None
    tag = min(tags, key=lambda t: abs(float(t[2] or 0) - float(params_b or t[2] or 0)))
    ref = name if tag[0] == "latest" else f"{name}:{tag[0]}"
    return {"name": name, "ref": ref, "download_gb": round(tag[1], 1), "params_b": tag[2], "updated": e.get("updated") or ""}


def cost(download_gb: float, vram_gb: Optional[float], window: Optional[int], beside: Optional[bool]) -> dict:
    mins = math.ceil(download_gb * 1000 / DOWNLOAD_MB_S / 60) if download_gb else 0
    return {"download_gb": round(download_gb or 0, 1), "vram_gb": round(vram_gb, 1) if vram_gb else None,
            "window": window, "beside": "co-reside" if beside else "pivot" if beside is False else None,
            "minutes": mins}


def _k(n) -> str:
    return f"{n // 1024}k" if isinstance(n, int) and n >= 1024 else str(n or "?")


def cost_words(c: dict) -> str:
    bits = []
    if c.get("download_gb"):
        bits.append(f"{c['download_gb']:g} GB download (~{c['minutes']} min at {DOWNLOAD_MB_S:g} MB/s)")
    if c.get("vram_gb"):
        bits.append(f"{c['vram_gb']:g} GB VRAM" + (f" at {_k(c['window'])}" if c.get("window") else " plus its window"))
    if c.get("beside"):
        bits.append("co-resides with what is loaded" if c["beside"] == "co-reside" else "a pivot (it does not fit beside main)")
    return ", ".join(bits) or "nothing to download"


def say(s: dict) -> str:
    head = f"[{s['kind']}] {s['says']}"
    gain = s.get("unlocks") or s.get("frees")
    a = s.get("action") or {}
    act = f"; {a['verb']}: {a.get('cli') or a.get('what')}" if a.get("verb") not in (None, "none") else ""
    return f"{head}" + (f" -- {'unlocks' if s.get('unlocks') else 'frees'} {gain}" if gain else "") + \
        f"; costs {cost_words(s.get('cost') or {})}" + act
