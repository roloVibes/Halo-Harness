"""halo_harness.studio.local_hosts_view -- Halo 3.3.5.0 R1: the Local tab's
Hosts page, every server Halo knows as one card (the routes are
studio/local_api.py). Built on the Ollama panel's view
(studio/ollama_hosts_view.hosts_view: the card, the findings, the fit plan),
never a model call and never a write to a server.

    hosts(state_dir, hub=None) -> {hosts: [host], at, mode}
    host {name, url, kind, source (configured | discovered | local server |
          member), version, served_here, served_by, loaded [{model, size,
          size_vram, vram_pct, expires, context_length}], card_lines, profiles
          {model: profile}, users [{from, calls}] (the ledger's `from`, 24 h),
          finding (the newest open one's line) | None, findings, plan {says,
          fits_now, chosen {kind, says, lose, fits, changes}} | None, models
          [names], controls {ok, via, why}}

`controls` says whether Load / Unload / keep-alive work from here: a host this
machine serves, yes; a host a fleet member serves (its resources samples say
so) through that member when this Studio runs the hub, unless the member's
`fleet.allow_control` is `none`; anything else no, with the reason.
"""

from __future__ import annotations

import time
from typing import Optional

KINDS = {"ollama": "Ollama", "openai": "OpenAI-dialect gateway"}


def kind_of(host) -> str:
    from halo_harness.providers.ollama import host_is_openai_dialect
    return KINDS["openai" if host_is_openai_dialect(host) else "ollama"]


def _loaded(rows) -> list:
    out = []
    for x in rows or []:
        size, vram = x.get("size"), x.get("size_vram")
        pct = round(100.0 * vram / size) if isinstance(size, int) and size > 0 and isinstance(vram, int) else None
        out.append({"model": x.get("model"), "size": size, "size_vram": vram, "vram_pct": pct,
                    "expires": x.get("expires"), "context_length": x.get("context_length")})
    return out


def users_by_host(state_dir) -> dict:
    """{host name here: [{from, calls}]} over the last 24 h (None = this machine)."""
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.studio.local_traffic import _ctx
    from halo_harness.studio.ollama_hosts_view import line_host
    hosts, servers = _ctx()
    out: dict = {}
    for x in read_calls(state_dir, since=86400.0):
        h = line_host(x, hosts, servers)
        who = out.setdefault(h, {})
        who[x.get("from")] = who.get(x.get("from"), 0) + 1
    return {h: sorted(({"from": k, "calls": v} for k, v in who.items()), key=lambda r: -r["calls"]) for h, who in out.items()}


def _member(hub, name: str):
    if hub is None or not name:
        return None
    try:
        return next((m for m in hub.state.members.values() if m.name == name), None)
    except Exception:
        return None


def controls(host_url: str, host_name: str, served: bool, hub=None) -> dict:
    """{ok, via, why, member, member_host} for Load / Unload on this host from here."""
    if served:
        return {"ok": True, "via": "this machine", "why": ""}
    from halo_harness.ollama_steward.resources_share import serving
    who = serving(host_url, host_name)
    if who is None:
        return {"ok": False, "via": "", "why": "served by another machine: its own Studio's Local tab loads it, or "
                "that machine joins this hub (halo fleet join) and runs a session, and Load goes through it"}
    m = _member(hub, who["member"])
    if m is None:
        return {"ok": False, "via": "", "why": f"served by {who['member']}: Load goes through it from the hub "
                f"it joined (this Studio is not that hub)", **who}
    if m.allow_control == "none":
        return {"ok": False, "via": "", "why": f"{m.name} has fleet.allow_control: none, so a hub does not load "
                "models there (its owner sets ask or all)", **who}
    if not m.sessions():
        return {"ok": False, "via": "", "why": f"{m.name} has no live session to take the command right now", **who}
    via = f"fleet member {m.name}" + (" (its owner is asked first)" if m.allow_control == "ask" else "")
    return {"ok": True, "via": via, "why": "", **who}


def _finding(fs: list) -> Optional[str]:
    open_ = [f for f in fs if not f.get("applied")]
    return (open_[-1].get("finding") if open_ else None) or None


def _plan(p: Optional[dict]) -> Optional[dict]:
    if not p:
        return None
    ch = p.get("chosen")
    opt = p["options"][ch] if isinstance(ch, int) and 0 <= ch < len(p.get("options") or []) else None
    keep = ("kind", "says", "lose", "fits", "changes", "server_hint")
    return {"says": p.get("says"), "fits_now": p.get("fits_now"), "chosen": {k: opt.get(k) for k in keep} if opt else None}


def _configured(h: dict, host_obj, users: dict, hub) -> dict:
    card = h.get("card") or {}
    from halo_harness.studio.ollama_hosts_view import catalog_of
    names = [str(r.get("model") or r.get("name")) for r in (catalog_of(host_obj).get("models") or []) if isinstance(r, dict)]
    return {"name": h["name"], "url": h["url"], "kind": kind_of(host_obj), "source": "configured",
            "version": (card.get("server") or {}).get("version"), "served_here": h["served_here"],
            "served_by": "this machine" if h["served_here"] else "another machine",
            "loaded": _loaded(h.get("loaded")), "card_lines": h.get("card_lines") or [],
            "profiles": {k.split("|", 1)[1]: v for k, v in (h.get("profiles") or {}).items()},
            "users": users.get(h["name"], []), "finding": _finding(h.get("findings") or []),
            "findings": len([f for f in h.get("findings") or [] if not f.get("applied")]), "plan": _plan(h.get("plan")),
            "models": names, "controls": controls(h["url"], h["name"], h["served_here"], hub)}


def _blank(name: str, url: str, kind: str, source: str, why: str, **kw) -> dict:
    row = {"name": name, "url": url, "kind": kind, "source": source, "version": None, "served_here": False,
           "served_by": "", "loaded": [], "card_lines": [], "profiles": {}, "users": [], "finding": None, "findings": 0,
           "plan": None, "models": [], "controls": {"ok": False, "via": "", "why": why}}
    row.update(kw)
    return row


def _discovered(configured_urls: set) -> list:
    from halo_harness.providers.ollama_discover import url_key
    from halo_harness.studio import setup_discover_jobs as J
    rows = list(J.found())
    try:
        from halo_harness.providers import ollama_discover as D
        rows += list(D._cache[2]) if D._cache else []  # the 60 s cache as it is: no probe from here
    except Exception:
        pass
    out, seen = [], set(configured_urls)
    for r in rows:
        key = url_key(r.url)
        if r.configured or key in seen:
            continue
        seen.add(key)
        out.append(_blank(r.name, r.url, "Ollama", "discovered", "add it to hosts first (Add to hosts writes the "
                          "ollama.hosts entry)", version=r.version, models=list(r.models), served_here=r.where != "lan",
                          served_by="this machine" if r.where != "lan" else "another machine"))
    return out


def _members(known: set, hub) -> list:
    from halo_harness.ollama_steward.resources import STORE
    out = []
    for name in STORE.hosts():
        s = STORE.latest(name) or {}
        if not s.get("from") or name in known:
            continue
        loaded = [{"model": x.get("name"), "size": None, "size_vram": x.get("bytes"), "vram_pct": None, "expires": None,
                   "context_length": None} for x in s.get("holders") or [] if x.get("kind") == "model"]
        row = _blank(name, s.get("url") or "", "Ollama", "member", "", served_by=s["from"], loaded=loaded)
        row["controls"] = controls(s.get("url") or "", name, False, hub)
        out.append(row)
    return out


def hosts(state_dir, *, hub=None, now: Optional[float] = None) -> dict:
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.providers.ollama_discover import url_key
    from halo_harness.studio.ollama_hosts_view import hosts_view
    now = time.time() if now is None else now
    view = hosts_view(state_dir, now=now)
    objs = {h.name: h for h in resolve_ollama_hosts()}
    users = users_by_host(state_dir)
    out = [_configured(h, objs.get(h["name"]), users, hub) for h in view["hosts"] if h["name"] in objs]
    for s in view["local_servers"]:
        out.append(_blank(s["name"], s["url"], "local server (OpenAI dialect)", "local server",
                          "a local server serves the model it was started with (starting and stopping one is Local "
                          "-> Hugging Face, next)", users=users.get(s["name"], []), models=[m["model"] for m in s["models"]],
                          finding=_finding(s.get("findings") or []), findings=len(s.get("findings") or [])))
    out += _discovered({url_key(h.url) for h in objs.values()})
    out += _members({r["name"] for r in out}, hub)
    return {"hosts": out, "at": now, "mode": view.get("mode")}
