"""halo_harness.ollama_steward.host_reads -- what the harness reads through a paired halo host (Halo 3.3.7.0 R1;
host_client.py has the client and the matching), each under this machine's name for the Ollama host:

    card_of(host) -> the host's hardware card, its sources led by "halo host at <addr>" (`via: "host"`) | None
    log_of(host) -> the host's own log status for that server {state, line, path, ..., addr, answered} | None
    tail_of(host, n) -> (lines, "via host <addr>: <source>", why) | None   prompt sizes, never a request body
    events_of(state_dir, host, since) -> [event]   the host's classified events (cached host_client.CARD_TTL_S)
    profile_of(state_dir, model, host_name) -> a battery profile verified there, source "the host at <addr>" | None
    host_block(url) -> the Hosts card's {addr, url, name, started, last_seen, audit_count, error} | None
"""

from __future__ import annotations

import time
from typing import Optional

from halo_harness.ollama_steward.host_client import (CARD_TTL_S, PROFILES_TTL_S, _CACHE, HostError, _addr_port,
                                                       _usable, any_paired, for_host)


def _row(host) -> "tuple[Optional[object], Optional[dict]]":
    c = for_host(host)
    if not _usable(c):
        return c, None
    try:
        return c, c.served_row(_addr_port(host.url)[1])
    except HostError:
        return c, None


def card_of(host) -> Optional[dict]:
    """The host's hardware card for this Ollama host, its sources led by "halo host at <addr>", or None."""
    c, row = _row(host)
    if row is None or not isinstance(row.get("card"), dict):
        return None
    card = dict(row["card"])
    card["sources"] = [{"reader": "halo host", "ok": True, "detail": c.label}] + list(card.get("sources") or [])
    card.update(via="host", via_addr=c.addr, footprint=row.get("footprint"), other_clients=row.get("other_clients"))
    return card


def log_of(host) -> Optional[dict]:
    c, row = _row(host)
    if c is None:
        return None
    return {**(row or {}).get("log", {}), "addr": c.addr, "answered": row is not None}


def tail_of(host, n: int = 200) -> "Optional[tuple[list, str, Optional[str]]]":
    c = for_host(host)
    if c is None:
        return None
    if not _usable(c):
        return [], f"via host {c.addr}", f"the {c.label} did not answer a moment ago"
    try:
        got = c.tail(n)
    except HostError as e:
        return [], f"via host {c.addr}", str(e)
    return list(got.get("lines") or []), f"via host {c.addr}: {got.get('source') or 'its server log'}", got.get("why")


def _named(host_or_name):
    if not isinstance(host_or_name, str):
        return host_or_name
    from halo_harness.providers.ollama import resolve_ollama_hosts
    return next((h for h in resolve_ollama_hosts() if h.name.lower() == host_or_name.lower()), None)


def events_of(state_dir, host, since=86400.0) -> list:
    """The host's events for this Ollama host, under this machine's name for it (cached CARD_TTL_S)."""
    if not any_paired():
        return []
    h = _named(host)
    c = for_host(h) if h is not None else None
    if not _usable(c):
        return []
    key = (c.url, f"events:{since}")
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < CARD_TTL_S:
        return hit[1]
    port = _addr_port(h.url)[1]
    try:
        rows = [{**e, "host": h.name, "from_host": e.get("host"), "via": "host"}
                for e in c.events(since=since).get("events") or [] if int(e.get("port") or port) == port]
    except HostError:
        rows = []
    _CACHE[key] = (time.monotonic(), rows)
    return rows


def profile_of(state_dir, model: str, host_name: Optional[str]) -> Optional[dict]:
    """A battery profile verified on the host, as this machine names the host: source "the host at <addr>"."""
    if not model or not host_name or not any_paired():
        return None
    h = _named(host_name)
    c = for_host(h) if h is not None else None
    if not _usable(c):
        return None
    key = (c.url, "profiles")
    hit = _CACHE.get(key)
    if hit is None or time.monotonic() - hit[0] >= PROFILES_TTL_S:
        try:
            rows = list(c.profiles().get("profiles") or [])
        except HostError:
            rows = []
        hit = _CACHE[key] = (time.monotonic(), rows)
    from halo_harness.providers.ollama import ollama_names_match
    port = _addr_port(h.url)[1]
    p = next((p for p in hit[1] if ollama_names_match(p.get("model"), model) and int(p.get("port") or port) == port), None)
    if p is None:
        return None
    return {**p, "host": h.name, "from_host": p.get("host"), "source": f"the host at {c.addr}", "truth": "verified"}


def host_block(url: str) -> Optional[dict]:
    """The Hosts card's "served by halo host at <addr>" block: {addr, url, name, started, last_seen, audit_count,
    error}, or None when no paired host serves that url."""
    from types import SimpleNamespace
    c = for_host(SimpleNamespace(url=url, name=""))
    if c is None:
        return None
    out = {"addr": c.addr, "url": c.url, "name": c.entry.get("name"), "started": None, "last_seen": None,
           "audit_count": None, "error": ""}
    if not _usable(c):
        return {**out, "error": f"the {c.label} did not answer a moment ago"}
    try:
        got = c.card()
    except HostError as e:
        return {**out, "error": str(e)}
    hit = _CACHE.get((c.url, "card"))
    return {**out, "started": (got.get("host") or {}).get("started"), "audit_count": (got.get("audit") or {}).get("count"),
            "last_seen": time.time() - (time.monotonic() - hit[0]) if hit else c.last_seen}
