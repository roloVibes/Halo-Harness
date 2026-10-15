"""halo_harness.fleet.capabilities_view -- a capability catalog in short
forms (Halo 3.0.6.0 "Fleet Missions" round R6):

    summary(cat)              the one line a relay's announce carries: counts + tags
    chips(cat, n=3)           the map's chips on a harness box: tags first, then the GPU, the OS, craft apps
    spec_lines(cat, tools=)   `halo fleet capabilities`' spec sheet, one harness
    tool_count(cat)           every MCP tool listed
"""

from __future__ import annotations

import re
import time
from typing import Optional

_GPU = re.compile(r"\b([A-Z]{0,2}\d{3,4}(?:\s?Ti)?)\b")
GENERIC_OS = ("linux", "windows", "darwin", "")


def tool_count(cat: dict) -> int:
    return sum(len(s.get("tools") or []) for s in cat.get("mcp") or [])


def gpu_short(name: str) -> str:
    m = _GPU.search(str(name or ""))
    if m:
        return m.group(1).replace(" ", "")
    words = str(name or "").split()
    return words[-1] if words else ""


def _gpu_words(hw: dict) -> list:
    out = []
    for g in hw.get("gpu") or []:
        vram = g.get("vram_gb")
        out.append(f"{g.get('name')}" + (f" {vram:g} GB" if isinstance(vram, (int, float)) else ""))
    return out


def summary(cat: dict) -> str:
    if not cat:
        return ""
    servers = cat.get("mcp") or []
    parts = [f"{len(servers)} MCP server{'s' if len(servers) != 1 else ''} ({tool_count(cat)} tools)",
             f"{len(cat.get('skills') or [])} skills", f"{len(cat.get('models') or [])} models"]
    crafts = cat.get("craft_apps") or []
    if crafts:
        parts.append(f"{len(crafts)} craft app{'s' if len(crafts) != 1 else ''}")
    hw = cat.get("hardware") or {}
    gpus = _gpu_words(hw)
    if gpus:
        parts.append(gpus[0])
    if isinstance(hw.get("ram_gb"), (int, float)):
        parts.append(f"{hw['ram_gb']:g} GB RAM")
    tags = cat.get("tags") or []
    line = ", ".join(parts)
    return f"{line}; tags: {', '.join(tags)}" if tags else line


def chips(cat: dict, n: int = 3) -> list:
    if not cat:
        return []
    hw = cat.get("hardware") or {}
    cand = list(cat.get("tags") or [])
    cand += [gpu_short(g.get("name")) for g in hw.get("gpu") or []]
    distro = str(hw.get("distro") or "").lower()
    if distro and distro not in GENERIC_OS:
        cand.append(distro)
    cand += list(cat.get("craft_apps") or [])
    if hw.get("os"):
        cand.append(str(hw["os"]).lower())
    out: list = []
    for c in cand:
        c = str(c).strip()
        if c and c.lower() not in {x.lower() for x in out}:
            out.append(c)
        if len(out) >= n:
            break
    return out


def age_words(at, now: Optional[float] = None) -> str:
    if not isinstance(at, (int, float)) or at <= 0:
        return "age unknown"
    s = max(0, int((now or time.time()) - at))
    if s < 90:
        return f"{s} s old"
    if s < 5400:
        return f"{s // 60} min old"
    return f"{s // 3600} h old" if s < 172800 else f"{s // 86400} days old"


def _join(items, empty: str = "none", n: int = 14) -> str:
    items = [str(i) for i in items if str(i)]
    if not items:
        return empty
    more = f" (+{len(items) - n} more)" if len(items) > n else ""
    return ", ".join(items[:n]) + more


def spec_lines(cat: dict, *, tools: bool = False, name: Optional[str] = None, now: Optional[float] = None) -> list:
    h = cat.get("harness") or {}
    hw = cat.get("hardware") or {}
    os_name, distro = str(hw.get("os") or h.get("os") or "?"), str(hw.get("distro") or "")
    head = f"{name or h.get('name') or h.get('id') or 'harness'}  ({os_name}"
    head += f" {distro}" if distro and distro != os_name else ""
    head += f", halo {h.get('version')})" if h.get("version") else ")"
    out = [head + f"   catalog {age_words(cat.get('at'), now)}, hash {cat.get('hash') or '-'}"]
    hwp = [str(hw.get("cpu") or "")] if hw.get("cpu") else []
    if hw.get("cores"):
        hwp.append(f"{hw['cores']} cores")
    if isinstance(hw.get("ram_gb"), (int, float)):
        hwp.append(f"{hw['ram_gb']:g} GB RAM")
    hwp += _gpu_words(hw) or ["no GPU found"]
    if isinstance(hw.get("disk_free_gb"), (int, float)):
        hwp.append(f"{hw['disk_free_gb']:g} GB free")
    rows = [("hardware", ", ".join(hwp)),
            ("models", _join([m.get("id") + (f" ({', '.join(m['best_for'])})" if m.get("best_for") else " (local)"
                                             if m.get("local") else "") for m in cat.get("models") or []], n=8)),
            ("craft apps", _join(cat.get("craft_apps") or []))]
    media = cat.get("media") or {}
    if media.get("comfyui"):
        rows.append(("media", f"ComfyUI, {len(media.get('models') or [])} models: "
                              + _join([m.get("name") for m in media.get("models") or []], n=6)))
    servers = cat.get("mcp") or []
    rows.append(("mcp", _join([f"{s.get('name')} {len(s['tools'])} tools" if isinstance(s.get("tools"), list)
                               else f"{s.get('name')} ({s.get('note') or 'tools unknown'})" for s in servers], n=40)))
    rows += [("skills", _join(cat.get("skills") or [], n=24)),
             ("clis", _join([f"{k} {v}" for k, v in sorted((cat.get("clis") or {}).items()) if v], n=30)),
             ("projects", _join([f"{p.get('name')} ({p.get('repo')}@{p.get('branch') or '?'})"
                                 for p in cat.get("projects") or []])),
             ("providers", _join([p.get("name") for p in cat.get("providers") or [] if p.get("ok")])),
             ("roles", _join(sorted({f"{r.get('lineup')}: {r.get('role')}={r.get('bio')}" for r in cat.get("roles") or []}), n=10)),
             ("connects", ", ".join(f"{k} {'on' if v else 'off'}" for k, v in (cat.get("integrations") or {}).items()) or "none"),
             ("tags", _join(cat.get("tags") or []))]
    out += [f"  {k:<10} {v}" for k, v in rows]
    if tools:
        for s in servers:
            if isinstance(s.get("tools"), list) and s["tools"]:
                out.append(f"  {s.get('name')} ({s.get('transport')}):")
                out += [f"      {t.get('name'):<28} {t.get('desc') or ''}"[:160] for t in s["tools"]]
    return out
