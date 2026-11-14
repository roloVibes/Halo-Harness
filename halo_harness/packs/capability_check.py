"""halo_harness.packs.capability_check -- what the active packs can do on this machine (Halo 3.2.0.0 R4;
docs/EXTENSION_API.md "Pack capabilities"): a pack workflow's capability `requires` are checked with it, and a pack
declaring capabilities shows its rows (`halo pack inspect`, `halo pack doctor`).

    section(cat, cwd=, state_dir=)   [{id, name, version, capabilities: [entry], inspector: [{label, source}]}] for the
                                     packs that run here (a disabled pack adds nothing)
    entry(pack, granted, cat, ...)   one capability: {name, description, available, why, checks: [{key, ok, line}],
                                     requires, capacity}; `why` says which requires hold on this host (the
                                     tools present, the runtime found, the platform, the GPU, the models in the
                                     catalog, the grants given), or what is missing when it is not available
    refusal(needs, cwd=, state_dir=) ''; or the one line a need is refused with when it is a pack capability whose
                                     pack does not run here with its grants
    inspector_text(root, source)     {text, cut?}: an inspector line's file (a markdown, text or JSON file
                                     inside the pack, its first INSPECTOR_BYTES, paths scrubbed); {} otherwise
    host_catalog(state_dir, cwd)     the cached catalog, else a light view of this host (inspect, doctor)

The checks read `cat` (this host's catalog: hardware, CLIs, MCP servers, models, repos; peers/needs.has), PATH, and
the model catalog rows a bio's `models.capabilities` resolves against (packs/bio_models.py). Every string is
scrubbed afterwards.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from halo_harness.packs.capability_rules import INSPECTOR_SUFFIXES, capabilities_of, contribution_of
from halo_harness.peers.catalog import scrub
from halo_harness.peers.needs import has, norm_need

INSPECTOR_BYTES = 8192


def inspector_text(root, source) -> dict:
    src = str(source or "")
    rel = Path(src)
    if not src or rel.is_absolute() or ".." in rel.parts or ":" in src or rel.suffix.lower() not in INSPECTOR_SUFFIXES:
        return {}
    try:
        base = Path(root).resolve()
        target = (base / rel).resolve()
        if base not in target.parents or not target.is_file():
            return {}
        with open(target, "rb") as fh:
            raw = fh.read(INSPECTOR_BYTES + 1)
    except (OSError, ValueError, TypeError):
        return {}
    text = scrub(raw[:INSPECTOR_BYTES].decode("utf-8", errors="ignore"))
    return {"text": text, "cut": True} if len(raw) > INSPECTOR_BYTES else {"text": text}


def _req(c: dict) -> dict:
    return c.get("requires") if isinstance(c.get("requires"), dict) else {}


def _names(d: dict, key: str) -> "list[str]":
    v = d.get(key)
    return [str(x) for x in v if isinstance(x, (str, int, float))] if isinstance(v, list) else []


def _tool(cat: dict, name: str) -> str:
    return has(cat, name) or (f"{name} (on PATH)" if shutil.which(name) else "")


def _model(m: str, cat: dict, rows) -> str:
    from halo_harness.packs import bio_models as BM
    if m in BM.TAGS:
        got = BM.pick({"capabilities": [m]}, rows=rows)
        return f"{m}: {got['ref']}" if got and got.get("how") == "capabilities" else ""
    low = m.lower()
    hit = has(cat, f"model:{m}") or next((f"model {r['ref']}" for r in rows if r.get("ref") and low in str(r["ref"]).lower()), "")
    return hit


def _locality(kind: str, pack, cat: dict, state_dir) -> str:
    if kind == "repo":
        projects = cat.get("projects") or []
        return f"a checkout of {projects[0].get('repo') or projects[0].get('name')}" if projects else ""
    if kind.startswith("repo:"):
        return has(cat, kind) or ""
    from halo_harness.packs.discover import user_packs_dir
    d = user_packs_dir(state_dir) / ".data" / pack.id
    return "the pack's data folder" if d.is_dir() and any(d.iterdir()) else ""


def checks(c: dict, pack, granted, cat: dict, *, running: bool = True, cwd=None, state_dir=None, rows=None) -> list:
    """`[{key, ok, line}]`: each thing the capability requires, held or not on this host."""
    req, out = _req(c), []
    hw = cat.get("hardware") if isinstance(cat.get("hardware"), dict) else {}

    def add(key: str, ok, held: str, missing: str) -> None:
        out.append({"key": key, "ok": bool(ok), "line": held if ok else missing})
    for t in _names(req, "tools"):
        why = _tool(cat, t)
        add("tools", why, why, f"no {t} here")
    clis = cat.get("clis") if isinstance(cat.get("clis"), dict) else {}
    for r in _names(req, "runtimes"):
        have = clis.get(r) or ("found" if shutil.which(r) else "")
        add("runtimes", have, f"{r} {have}", f"no {r} runtime here")
    plat = [p.lower() for p in _names(req, "platform")]
    if plat:
        here = [w for w in (str(hw.get("os") or "").lower(), str(hw.get("distro") or "").lower()) if w]
        add("platform", set(plat) & set(here), f"platform {'/'.join(dict.fromkeys(here))}",
            f"this host is {'/'.join(dict.fromkeys(here)) or 'unknown'}, not {', '.join(plat)}")
    want = (req.get("hardware") or {}) if isinstance(req.get("hardware"), dict) else {}
    gpus = [str(g.get("name") or "") for g in hw.get("gpu") or [] if isinstance(g, dict)]
    gpu = want.get("gpu")
    if gpu is True:
        add("hardware", gpus, f"GPU {gpus[0] if gpus else ''}", "no GPU here")
    elif isinstance(gpu, str) and gpu.strip():
        hit = next((g for g in gpus if gpu.strip().lower() in g.lower()), "")
        add("hardware", hit, f"GPU {hit}", f"no {gpu.strip()} GPU here" + (f" ({', '.join(gpus)})" if gpus else ""))
    ram = want.get("ram_gb")
    if isinstance(ram, (int, float)) and not isinstance(ram, bool) and ram > 0:
        have = hw.get("ram_gb") if isinstance(hw.get("ram_gb"), (int, float)) else None
        add("hardware", have is not None and have >= ram, f"{have:g} GB RAM" if have else "",
            f"{have:g} GB RAM here, it needs {ram:g}" if have else f"RAM unknown here, it needs {ram:g} GB")
    models = _names(req, "models")
    if models:
        from halo_harness.packs import bio_models as BM
        rows = BM.catalog_rows(state_dir, cwd) if rows is None else rows
        for m in models:
            why = _model(m, cat, rows)
            add("models", why, why, f"no model in the catalog has {m}" if m in BM.TAGS else f"no model {m} in the catalog")
    have = set(granted or []) if running else set()
    for g in _names(req, "grants"):
        add("grants", g in have, f"{g} granted", f"{g} not granted (halo pack enable {pack.id} --grant {g})")
    for kind in _names(req, "locality"):
        why = _locality(kind, pack, cat, state_dir)
        add("locality", why, why, f"no {kind.replace('repo:', 'checkout of ')} here" if kind != "pack-data"
            else "the pack's data folder is empty here")
    return out


def entry(c: dict, pack, granted, cat: dict, **kw) -> dict:
    got = checks(c, pack, granted, cat, **kw)
    ok = all(x["ok"] for x in got)
    lines = [x["line"] for x in got if x["ok"] == ok and x["line"]]
    why = "; ".join(lines) if lines else ("nothing required" if ok else "not available")
    cap = c.get("capacity") if isinstance(c.get("capacity"), dict) else {}
    return {"name": str(c["name"]), "description": str(c.get("description") or ""), "available": ok, "why": why,
            "checks": got, "requires": _req(c), "capacity": {"parallel": cap["parallel"]} if cap.get("parallel") else {}}


def pack_entry(pack, granted, cat: dict, *, running: bool = True, cwd=None, state_dir=None, rows=None) -> dict:
    block = contribution_of(pack.manifest)
    return {"id": pack.id, "name": pack.name, "version": pack.version, "scope": pack.scope,
            "capabilities": [entry(c, pack, granted, cat, running=running, cwd=cwd, state_dir=state_dir, rows=rows)
                             for c in capabilities_of(pack.manifest)],
            "inspector": [{"label": str(x.get("label") or ""), "source": str(x.get("source") or ""),
                           **inspector_text(pack.root, x.get("source"))}
                          for x in block.get("inspector") or [] if isinstance(x, dict)]}


def section(cat: dict, *, cwd=None, state_dir=None) -> list:
    from halo_harness.packs import state as S
    from halo_harness.packs.registry import snapshot
    snap = snapshot(cwd=cwd, state_dir=state_dir)
    return [pack_entry(p, S.granted(p.id, snap.state), cat, cwd=cwd, state_dir=state_dir)
            for p in snap.active if contribution_of(p.manifest)]


def refusal(needs, *, cwd=None, state_dir=None) -> str:
    """'' when every need that is a pack capability here has its pack running with the grants it requires;
    else the one line it is refused with (a `pack:<name>` need no pack here declares, too)."""
    from halo_harness.packs import state as S
    from halo_harness.packs.registry import snapshot
    snap = snapshot(cwd=cwd, state_dir=state_dir)
    for need in needs or []:
        n = norm_need(need)
        word = n[len("pack:"):] if n.startswith("pack:") else n
        holders = [(p, c) for p in snap.packs for c in capabilities_of(p.manifest) if c["name"].lower() == word]
        if not holders:
            if n.startswith("pack:"):
                return f"this machine has no pack with {word}"
            continue
        holders.sort(key=lambda h: h[0].id not in snap.order)
        p, c = holders[0]
        grants = _names(_req(c), "grants")
        have = set(S.granted(p.id, snap.state)) if p.id in snap.order else set()
        if p.id in snap.order and all(g in have for g in grants):
            continue
        missing = [g for g in grants if g not in have]
        return f"this machine does not run pack {p.id}" + (f" with {', '.join(missing)}" if missing else "")
    return ""


def host_catalog(state_dir=None, cwd=None) -> dict:
    """The cached capabilities catalog (any age), else this host's hardware, PATH tools and repos now."""
    from halo_harness.config.paths import background_net_disabled, bridge_home
    from halo_harness.peers import capabilities_host as host
    from halo_harness.peers.catalog import load
    from halo_harness.peers.projects import projects
    cat = load(state_dir)
    if cat:
        return cat
    home = Path(state_dir or bridge_home())

    def section(fn, default):
        try:
            got = fn()
            return default if got is None else got
        except Exception:
            return default
    out = {"hardware": section(lambda: host.hardware(home, spawn=not background_net_disabled()), {}),
           "clis": section(lambda: host.clis(spawn=False), {}), "mcp": [], "models": []}
    out["projects"] = section(lambda: projects(home, Path(cwd or Path.cwd())), [])
    return out
