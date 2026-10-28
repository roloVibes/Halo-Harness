"""halo_harness.models_library.browse -- Halo 3.3.5.0 R2: the library query the route and the CLI share.

    library(state_dir, *, source="all", q="", host="", window=None, fits=False, intent="", family="", quant="",
            cap="", max_gb=None, license="", page=1, per=PER_PAGE, refresh=False)
        -> {rows, total, page, pages, per, cached_at, sources {ollama, hf}, notes, host, hosts, window, intents, snapshot}
    detail(state_dir, source, model_id, *, host="", window=None, refresh=False) -> {source, id, rows, note, about}
    refresh(state_dir)  the cache dropped: the next read is live

A row (rows.py's LibraryRow, its `shape` left out) gains {model, card (studio/model_card_api.view's card), fit
(rows.fit_for_row), intent {id: score}}. The list has one Ollama row per size chip (`qwen3.5:9b`, `qwen3.5:27b`),
its sizes from the snapshot or a tags page this cache has read, and one row per hub repo (its size an estimate
until the repo is opened); `detail` lists every tag or file of one model, each with its fit. The intent order is
studio/local_models_view's `intent_scores` + `rank`.
"""

from __future__ import annotations

import math
from typing import Optional

from halo_harness.models_library import cache, hf_hub, ollama_library, ollama_registry, snapshot
from halo_harness.models_library.row_builders import hf_file_row, hf_repo_row, ollama_row
from halo_harness.models_library.rows import card_for_row, fit_for_row, window_default

PER_PAGE = 300
CAPS = ("tools", "vision", "embedding", "thinking", "audio")


def _host(name: str):
    from halo_harness.providers.ollama import resolve_ollama_hosts
    hosts = resolve_ollama_hosts()
    pick = next((h for h in hosts if name and h.name.lower() == name.lower()), None) or (hosts[0] if hosts else None)
    return pick, hosts


def _host_card(host) -> Optional[dict]:
    if host is None:
        return None
    from halo_harness.studio.ollama_hosts_view import card_of
    return card_of(host)


def _view(row: dict, host_card, window: int, host_name: str) -> dict:
    from halo_harness.studio.local_models_view import intent_scores
    from halo_harness.studio.model_card_api import view
    card = card_for_row(row)
    fit = fit_for_row(row, host_card, window, host_name=host_name)
    out = {k: v for k, v in row.items() if k != "shape"}
    return {**out, "model": row["name"], "card": view(card, fit)["card"], "fit": fit,
            "intent": intent_scores(_runs_here(card, fit), fit)}


def _runs_here(card: dict, fit: dict) -> dict:
    """The card with the window it runs at here (the largest that stays on the GPU, capped by its context), so
    "long documents" ranks what holds a long window on this card, not the longest trained context."""
    level, gpu, ctx = fit.get("level"), fit.get("gpu_window"), (card.get("window") or {}).get("tokens")
    if level in ("unknown", "cloud"):
        return card
    tokens = min(gpu, ctx) if isinstance(gpu, int) and isinstance(ctx, int) else gpu if isinstance(gpu, int) else 0
    return {**card, "window": {**(card.get("window") or {}), "tokens": tokens if level in ("fits", "tight") else 0}}


def _cached_tags(state_dir, model: str):
    hit = cache.get(state_dir, f"ollama:tags:{model}", cache.CATALOG_TTL_S)
    return (hit[0], "the tags page") if hit else (snapshot.tags_of(model), f"the snapshot from {snapshot.taken()}")


def _manifest_known(state_dir, model: str, tag: str) -> Optional[dict]:
    hit = cache.get(state_dir, f"ollama:manifest:{model}:{tag}", cache.CATALOG_TTL_S)
    if hit:
        return {**hit[0], "source": "registry.ollama.ai manifest"}
    snap = snapshot.manifest_of(model, tag)
    return {**snap, "source": f"the snapshot from {snapshot.taken()}"} if snap else None


def _ollama_rows(state_dir, q: str, refresh: bool) -> "tuple[list, dict]":
    cat = ollama_library.catalog(state_dir, refresh=refresh)
    words = [w for w in q.lower().split() if w]
    rows = []
    for e in cat["models"]:
        if e.get("cloud") and not e.get("sizes") and not e.get("capabilities"):
            continue  # a cloud-only listing: nothing to install
        if words and not all(w in f"{e['name']} {e.get('description', '')}".lower() for w in words):
            continue
        tags, tsrc = _cached_tags(state_dir, e["name"])
        sizes = e.get("sizes") or ["latest"]
        for s in sizes:
            rows.append(ollama_row(e, s, tags, _manifest_known(state_dir, e["name"], s), tsrc))
    return rows, cat


def _hf_rows(state_dir, q: str, refresh: bool) -> "tuple[list, dict]":
    out, src, notes, at = [], set(), [], []
    for kind in ("gguf", "mlx"):
        got = hf_hub.search(state_dir, q, kind, refresh=refresh)
        out += [hf_repo_row(r) for r in got["repos"]]
        src.add(got["source"])
        if got.get("note"):
            notes.append(got["note"])
        if got.get("at"):
            at.append(got["at"])
    return out, {"source": "fixtures" if "fixtures" in src else "live", "note": "; ".join(dict.fromkeys(notes)),
                 "at": min(at) if at else None}


def _keep(r: dict, *, fits, family, quant, cap, max_gb, license) -> bool:
    if fits and (r.get("fit") or {}).get("level") not in ("fits", "tight"):
        return False
    if family and family.lower() not in f"{r.get('family') or ''} {r.get('id')}".lower():
        return False
    if quant and quant.lower() not in str(r.get("quant") or "").lower():
        return False
    if cap and cap.lower() not in [c.lower() for c in r.get("capabilities") or []]:
        return False
    if max_gb and (not isinstance(r.get("size_bytes"), int) or r["size_bytes"] > float(max_gb) * 1e9):
        return False
    if license and license.lower() not in str(r.get("license") or "").lower():
        return False
    return True


def _has_budget(hc) -> bool:
    if not hc:
        return False
    from halo_harness.ollama_steward.fit import card_budget
    return card_budget(hc)["budget"] > 0


def _hosts_view(hosts) -> list:
    return [{"name": h.name, "max_ctx": getattr(h, "max_ctx", None), "url": h.url} for h in hosts]


def library(state_dir, *, source: str = "all", q: str = "", host: str = "", window: Optional[int] = None,
            fits: bool = False, intent: str = "", family: str = "", quant: str = "", cap: str = "",
            max_gb: Optional[float] = None, license: str = "", page: int = 1, per: int = PER_PAGE,
            refresh: bool = False) -> dict:
    from halo_harness.studio.local_models_view import INTENTS, rank
    source = source if source in ("ollama", "hf", "all") else "all"
    h, hosts = _host(host)
    hc = _host_card(h)
    window = int(window) if isinstance(window, int) and window > 0 else window_default(h)
    rows, sources, notes, ats = [], {}, {}, []
    if source in ("ollama", "all"):
        got, cat = _ollama_rows(state_dir, q, refresh)
        rows += got
        sources["ollama"], notes["ollama"] = cat["source"], cat.get("note") or ""
        ats.append(cat.get("at"))
    if source in ("hf", "all"):
        got, info = _hf_rows(state_dir, q, refresh)
        rows += got
        sources["hf"], notes["hf"] = info["source"], info["note"]
        ats.append(info["at"])
    name = h.name if h is not None else ""
    views = [_view(r, hc, window, name) for r in rows]
    views = [v for v in views if _keep(v, fits=fits, family=family, quant=quant, cap=cap, max_gb=max_gb, license=license)]
    if intent:
        views = rank(views, intent)
    per = max(1, min(int(per or PER_PAGE), 2000))
    pages = max(1, math.ceil(len(views) / per))
    page = max(1, min(int(page or 1), pages))
    ats = [a for a in ats if isinstance(a, (int, float))]
    return {"rows": views[(page - 1) * per: page * per], "total": len(views), "page": page, "pages": pages, "per": per,
            "cached_at": min(ats) if ats else None, "sources": sources, "notes": notes, "window": window,
            "host": {"name": name or None, "max_ctx": getattr(h, "max_ctx", None), "card": _has_budget(hc)},
            "hosts": _hosts_view(hosts), "intents": [{"id": i, "title": t, "why": w} for i, t, w in INTENTS],
            "intent": intent or "", "snapshot": {"taken": snapshot.taken()}}


def _ollama_detail(state_dir, model: str, refresh: bool) -> "tuple[list, str, dict]":
    name, _, want = model.partition(":")
    entry = next((e for e in ollama_library.catalog(state_dir)["models"] if e["name"] == name), None) or \
        snapshot.entry_of(name) or {"name": name, "capabilities": [], "sizes": []}
    got = ollama_library.tags(state_dir, name, refresh=refresh)
    tsrc = "the tags page" if got["source"] == "live" else f"the snapshot from {snapshot.taken()}"
    asked = set(entry.get("sizes") or []) | ({want} if want else set())
    rows = []
    for t in got["tags"]:
        m = ollama_registry.manifest(state_dir, name, t["tag"], refresh=refresh) if t["tag"] in asked \
            else _manifest_known(state_dir, name, t["tag"])
        rows.append(ollama_row(entry, t["tag"], got["tags"], m, tsrc))
    about = {"description": entry.get("description") or "", "pulls": entry.get("pulls") or "", "updated": entry.get("updated") or ""}
    return rows, got.get("note") or got["source"], about


def _hf_detail(state_dir, rid: str, refresh: bool) -> "tuple[list, str, dict]":
    repo = hf_hub.repo(state_dir, rid, refresh=refresh)
    if repo is None:
        return [], f"the hub did not answer for {rid}", {}
    if repo.get("gated") and not repo.get("files"):
        repo = hf_hub.repo(state_dir, rid, refresh=True, gated=True) or repo
    shape = hf_hub.config(state_dir, rid, gated=repo.get("gated")) if repo.get("has_config") else {}
    rows = [hf_file_row(repo, f, shape) for f in repo.get("files") or []]
    about = {"license": repo.get("license"), "gated": repo.get("gated"), "private": repo.get("private"),
             "pipeline_tag": repo.get("pipeline_tag"), "context": repo.get("context"), "arch": repo.get("arch"),
             "base_model": repo.get("base_model"), "shape": "the repo's config.json" if shape else "no config.json read"}
    return rows, repo.get("source") or "", about


def detail(state_dir, source: str, model_id: str, *, host: str = "", window: Optional[int] = None,
           refresh: bool = False) -> dict:
    h, _hosts = _host(host)
    hc = _host_card(h)
    window = int(window) if isinstance(window, int) and window > 0 else window_default(h)
    if source == "hf":
        rows, note, about = _hf_detail(state_dir, model_id, refresh)
    else:
        rows, note, about = _ollama_detail(state_dir, model_id, refresh)
    name = h.name if h is not None else ""
    return {"source": source, "id": model_id, "rows": [_view(r, hc, window, name) for r in rows], "note": note,
            "about": about, "window": window, "host": name or None}


def refresh(state_dir) -> dict:
    return {"ok": True, "cleared": cache.clear(state_dir)}
