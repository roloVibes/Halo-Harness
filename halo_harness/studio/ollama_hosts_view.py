"""halo_harness.studio.ollama_hosts_view -- what Studio's Ollama panel shows per host (Halo 3.3.4.0 R5; the
routes are studio/ollama_steward_api.py). Built from the functions `halo ollama hardware | traffic | steward
findings | plan` use; never a model call and never a write to a server.

    hosts_view(state_dir) -> {hosts: [host], local_servers: [server], mode, at}

    host    {name, url, served_here, card (hardware_card, cached CARD_TTL_S per url), card_lines (format_card),
             loaded (the card's /api/ps rows), rollups {"1h", "24h"} (traffic.rollup), models [model],
             profiles {key: profile}, findings [finding + {applied, proposed}], plan (fit.plan) | None}
    model   {model, loaded {size, size_vram, vram_pct, expires, context_length} | None, hour {calls, trims, cuts,
             reloads, errors, p95_prompt, window, p95_pct} | None, day_calls, profile {num_ctx, num_predict,
             keep_alive, by, note, at} | None, vision}
    server  a `huggingface.local_servers` entry and its OpenAI-dialect ledger lines: {name, url, kind: "local
             server", models [model], findings (the window and reply-reserve rules only)}

READERS {"card": fn(host) -> card, "catalog": fn(host) -> {"models": [...]}} is the seam the tests use.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

CARD_TTL_S = 60.0
HOUR_S = 3600.0
HF_RULES = ("window-asked-small", "window-small", "window-large", "reply-cut")
READERS: dict = {}
_CACHE: dict = {}
_LOCK = threading.Lock()


def _default(kind: str):
    if kind == "card":
        from halo_harness.ollama_steward.hardware import hardware_card
        return hardware_card
    from halo_harness.providers.ollama import get_catalog
    return get_catalog


def _cached(kind: str, host):
    key = (kind, str(getattr(host, "url", "")))
    with _LOCK:
        hit = _CACHE.get(key)
    if hit is not None and time.monotonic() - hit[0] < CARD_TTL_S:
        return hit[1]
    try:
        value = (READERS.get(kind) or _default(kind))(host)
    except Exception:  # a host that does not answer still gets its row
        value = None if kind == "card" else {"models": []}
    with _LOCK:
        _CACHE[key] = (time.monotonic(), value)
    return value


def card_of(host) -> Optional[dict]:
    return _cached("card", host)


def catalog_of(host) -> dict:
    return _cached("catalog", host) or {"models": []}


def reset_cache() -> None:
    with _LOCK:
        _CACHE.clear()


def readers() -> dict:
    """The rules' and the planner's readers, through the 60 s cache."""
    return {"card_reader": card_of, "catalog_reader": catalog_of}


def _short(m) -> str:
    from halo_harness.ollama_steward.profiles import short_model
    return short_model(m)


def _base(url) -> str:
    u = str(url or "").rstrip("/")
    return u[:-3] if u.endswith("/v1") else u


def local_servers() -> list:
    try:
        from halo_harness.providers.huggingface import resolve_huggingface_local_servers
        return list(resolve_huggingface_local_servers())
    except Exception:
        return []


def line_host(line: dict, hosts: list, servers: list) -> str:
    """The name a ledger line's host has here: an Ollama host, a local server entry, else the line's own."""
    from halo_harness.ollama_steward.traffic import canonical_host
    url = _base((line.get("host") or {}).get("url"))
    if line.get("dialect") == "openai":
        s = next((s for s in servers if _base(s.url) == url), None)
        if s is not None:
            return s.name
    return canonical_host(line.get("host") or {}, hosts)[0]


def _hour(r: Optional[dict]) -> Optional[dict]:
    if not r:
        return None
    return {"calls": r["calls"], "trims": r["trims"], "cuts": r["cuts"], "reloads": r["reloads"],
            "errors": r["s499"] + r["s500"] + r["timeouts"] + r["failed"], "p95_prompt": r["p95_prompt"],
            "window": r["window"], "p95_pct": r["p95_pct"]}


def _loaded(x: Optional[dict]) -> Optional[dict]:
    if not x:
        return None
    size, vram = x.get("size"), x.get("size_vram")
    pct = round(100.0 * vram / size) if isinstance(size, int) and size > 0 and isinstance(vram, int) else None
    return {"size": size, "size_vram": vram, "vram_pct": pct, "expires": x.get("expires"),
            "context_length": x.get("context_length")}


def model_rows(host_name: str, hour: list, day: list, loaded: list, profiles: dict, catalog: dict) -> list:
    """One row per model with calls in the last 24 h, loaded now, or holding a profile here."""
    from halo_harness.ollama_steward.profiles import key_for, split_key
    names: list = []
    for m in [r["model"] for r in hour + day] + [x.get("model") for x in loaded or []] + \
            [split_key(k)[1] for k in profiles]:
        m = _short(m)
        if m and m != "?" and m not in names:
            names.append(m)
    out = []
    for m in names:
        h = next((r for r in hour if _short(r["model"]) == m), None)
        d = next((r for r in day if _short(r["model"]) == m), None)
        ld = next((x for x in loaded or [] if _short(x.get("model")) == m), None)
        prof = profiles.get(key_for(host_name, m))
        row = catalog.get(m) or {}
        caps = row.get("capabilities") if isinstance(row.get("capabilities"), list) else []
        out.append({"model": m, "loaded": _loaded(ld), "hour": _hour(h), "day_calls": d["calls"] if d else 0,
                    "profile": {k: prof.get(k) for k in ("num_ctx", "num_predict", "keep_alive", "by", "note", "at")}
                    if prof else None, "vision": "vision" in caps})
    return out


def _clean(rows: list) -> list:
    return [{k: v for k, v in r.items() if k != "host_obj"} for r in rows]


def _judge(state_dir, hosts: list) -> "tuple[list, dict]":
    from halo_harness.ollama_steward.fit import plan
    from halo_harness.ollama_steward.rules import gather, run_rules
    from halo_harness.ollama_steward.rules_host import _asked, _serving
    ctx = gather(state_dir, since="24h", hosts=hosts, **readers())
    found = run_rules(ctx)
    by_host: dict = {}
    for g in ctx["groups"]:
        by_host.setdefault(g["host"], []).append(g)
    plans = {h: plan(ctx["cards"].get(h) or {}, [_asked(g) for g in gs], ctx["catalogs"].get(h) or {}, host_name=h,
                     other_hosts=lambda m, h=h: _serving(ctx, m, h)) for h, gs in by_host.items()}
    return found, plans


def _marked(found: list, journal: list) -> list:
    from halo_harness.ollama_steward.steward import _in_place
    live = _in_place(journal)
    asked = {r.get("id") for r in journal if r.get("kind") == "proposal"}
    from halo_harness.ollama_steward.profiles import split_key
    out = []
    for f in found:
        applied = next((c for c in reversed(live) if c.get("finding") == f["id"]), None)
        out.append({**f, "applied": applied.get("id") if applied else None, "proposed": f["id"] in asked})
    seen = {f["id"] for f in found}
    for c in live[-10:]:  # a change in place whose finding the rules no longer raise: its row says applied
        if c.get("finding") in seen:
            continue
        seen.add(c.get("finding"))
        host, model = split_key(c.get("key"))
        out.append({"id": c.get("finding"), "rule": c.get("rule"), "host": host, "model": model, "key": c.get("key"),
                    "severity": "info", "finding": c.get("say") or "", "evidence": c.get("evidence") or {},
                    "proposal": {k: c.get(k) for k in ("field", "from", "to", "why")}, "server_hint": None,
                    "applied": c.get("id"), "proposed": False})
    return out


def hosts_view(state_dir, *, now: Optional[float] = None) -> dict:
    from halo_harness.fleet.ollama_share import served_here
    from halo_harness.ollama_steward import steward
    from halo_harness.ollama_steward.hardware import format_card
    from halo_harness.ollama_steward.ledger import parse_at, read_calls
    from halo_harness.ollama_steward.profiles import all_profiles, split_key
    from halo_harness.ollama_steward.traffic import rollup
    from halo_harness.providers.ollama import resolve_ollama_hosts
    now = time.time() if now is None else now
    hosts, servers = resolve_ollama_hosts(), local_servers()
    day = read_calls(state_dir, since=86400.0)
    hour = [x for x in day if (parse_at(x.get("at")) or 0) >= now - HOUR_S]
    found, plans = _judge(state_dir, hosts)
    found = _marked(found, steward.read_journal(state_dir))
    profiles = all_profiles()
    r1, r24 = _clean(rollup(hour, hosts)), _clean(rollup(day, hosts))
    out = []
    for h in hosts:
        card = card_of(h)
        rows = catalog_of(h).get("models") or []
        catalog = {_short(r.get("model") or r.get("name")): r for r in rows if isinstance(r, dict)}
        mine = {k: v for k, v in profiles.items() if split_key(k)[0] == h.name}
        h1, h24 = [r for r in r1 if r["host"] == h.name], [r for r in r24 if r["host"] == h.name]
        loaded = (card or {}).get("loaded") or []
        out.append({"name": h.name, "url": h.url, "served_here": served_here(h.url), "card": card,
                    "card_lines": format_card(card) if card else [], "loaded": loaded,
                    "rollups": {"1h": h1, "24h": h24}, "models": model_rows(h.name, h1, h24, loaded, mine, catalog),
                    "profiles": mine, "findings": [f for f in found if f["host"] == h.name], "plan": plans.get(h.name)})
    return {"hosts": out, "local_servers": _servers_view(servers, hour, day, found, profiles), "mode": steward.mode(),
            "at": now}


def _servers_view(servers: list, hour: list, day: list, found: list, profiles: dict) -> list:
    """The OpenAI-dialect local servers' rows (3.3.5.0's Models section shows the rest of Hugging Face)."""
    from halo_harness.ollama_steward.profiles import split_key
    from halo_harness.ollama_steward.traffic import rollup
    out = []
    for s in servers:
        def mine(lines):
            return [{**x, "host": {"name": s.name, "url": s.url}} for x in lines if x.get("dialect") == "openai"
                    and _base((x.get("host") or {}).get("url")) == _base(s.url)]
        h1, h24 = _clean(rollup(mine(hour), [])), _clean(rollup(mine(day), []))
        netloc = _base(s.url).split("://", 1)[-1]
        prof = {k: v for k, v in profiles.items() if split_key(k)[0] == s.name}
        out.append({"name": s.name, "url": s.url, "kind": "local server",
                    "models": model_rows(s.name, h1, h24, [], prof, {}),
                    "findings": [{**f, "host": s.name} for f in found if f["host"] in (netloc, s.name)
                                 and f["rule"] in HF_RULES]})
    return out
