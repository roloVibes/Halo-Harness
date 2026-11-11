"""halo_harness.providers.local_bench_runs -- Halo 3.3.6.0 R5: the speed card's store, when it is stale, where it shows,
and whether a host is quiet enough to bench (providers/local_bench.py runs the bench).

    save(state_dir, card)                  cache[digest]["speed_card"][host] (3.3.8.1: a LAN-measured card in
                                           ["speed_card_lan"][host]; all_cards / load read the pick) (the capability file,
                                           beside the battery profile and the measured facts, never over them); the
                                           battery profile's `speed` mirrors the ceiling row
    load(state_dir, host_name, model, digest=None) -> card | None      all_cards(state_dir, host=None) -> [card]
    stale(card, *, digest=None, version=None) -> "" | "measured on 0.40.6" | "measured on an older build of this tag"
    mirror(card) -> {tok_s, ttft_ms, cold_load_s, at_window, from: "bench", at}   the ceiling row
    lines(card) -> the card's three-window table, one line each      view(card, stale_word) -> the page's form
    with_speed_card(card, state_dir) -> a model card with `speed_card`, the badge's `speed`, the Measured lines and
                                        "where it sits" citing the largest window that stayed on the GPU
    speed_index(state_dir, host_name) -> {model: mirror}   the Library and Hosts rows (cached CACHE_S)
    busy(state_dir, host_name, *, sessions=None, ps=None) -> "" | why    a call on that host in the last BUSY_S, a session
                                           on it, or (3.3.7.0 R4) a model in /api/ps no Halo record explains
"""

from __future__ import annotations

import os
import time
from typing import Callable, Optional
from halo_harness.newest_first import newest_first  # 3.3.8.1: a same-ms tie, the later row first

BUSY_S = 60.0
CACHE_S = 10.0
LAN_SLOT = "speed_card_lan"  # 3.3.8.1: a card measured over the LAN from a peer, beside the machine-own one
_INDEX: dict = {}


def _k(n) -> str:
    return f"{n // 1024}k" if isinstance(n, int) and n >= 1024 else str(n)


def load(state_dir, host_name: str, model: str, digest: Optional[str] = None) -> Optional[dict]:
    from halo_harness.providers.ollama import ollama_names_match
    for c in all_cards(state_dir, host_name):
        if (digest and c.get("digest") == digest) or (not digest and ollama_names_match(c.get("model"), model)):
            return c
    return None


def all_cards(state_dir, host: Optional[str] = None) -> list:
    """Per digest and host the card the readers read (3.3.8.1: a machine-own card over a LAN-measured one of the same age
    class, else the newer -- providers/local_bench_link.pick), newest first."""
    from halo_harness.providers.local_bench_link import pick
    from halo_harness.providers.ollama_capability import load_capability_cache
    out = []
    for entry in load_capability_cache(state_dir).values() if state_dir is not None else ():
        own, lan = ((entry.get(k) or {}) for k in ("speed_card", LAN_SLOT)) if isinstance(entry, dict) else ({}, {})
        for name in list(own) + [n for n in lan if n not in own]:
            c = pick(own.get(name) if isinstance(own.get(name), dict) else None,
                     lan.get(name) if isinstance(lan.get(name), dict) else None)
            if c is not None and (not host or str(name).lower() == host.lower()):
                out.append(c)
    return newest_first(out, lambda c: float(c.get("at") or 0))


def mirror(card: dict) -> dict:
    rows = [r for r in card.get("windows") or [] if isinstance(r.get("tok_s"), (int, float))]
    top = rows[-1] if rows else {}
    return {"tok_s": top.get("tok_s"), "ttft_ms": top.get("ttft_ms"), "cold_load_s": card.get("cold_load_s"),
            "at_window": top.get("window"), "from": "bench", "at": card.get("at"), "on_gpu": top.get("on_gpu"),
            "over_lan": bool(card.get("over_lan")), "measured_from": card.get("measured_from")}


def save(state_dir, card: dict) -> None:
    digest, host = card.get("digest"), card.get("host")
    if not digest or not host or state_dir is None:
        return
    from halo_harness.filelock import file_lock
    from halo_harness.providers import ollama_capability as C
    with file_lock(C._capability_cache_path(state_dir)):
        cache = C.load_capability_cache(state_dir)
        entry = cache.get(digest) if isinstance(cache.get(digest), dict) else {}
        if card.get("over_lan"):  # 3.3.8.1: kept beside the machine's own card; a later own card replaces it
            entry.setdefault(LAN_SLOT, {})[host] = card
        else:
            entry.setdefault("speed_card", {})[host] = card
            (entry.get(LAN_SLOT) or {}).pop(host, None)
        entry.setdefault("model", card.get("model"))
        p = (entry.get("battery") or {}).get(host)
        if isinstance(p, dict):
            from halo_harness.providers.local_bench_link import pick
            read = pick((entry.get("speed_card") or {}).get(host), (entry.get(LAN_SLOT) or {}).get(host)) or card
            p["speed"] = {**(p.get("speed") or {}), **mirror(read)}
        cache[digest] = entry
        C.save_capability_cache(state_dir, cache)
    _INDEX.clear()


def stale(card: Optional[dict], *, digest: Optional[str] = None, version: Optional[str] = None) -> str:
    if not card:
        return ""
    if digest and card.get("digest") and digest != card["digest"]:
        return "measured on an older build of this tag"  # 3.3.7.0 R4: ollama_steward/tag_digests.WORD, the drift mark
    if version and card.get("ollama_version") and version != card["ollama_version"]:
        return f"measured on {card['ollama_version']}"
    return ""


def _row_line(r: dict) -> str:
    if r.get("error"):
        return f"{_k(r['window'])}: {r['error']}"
    gpu = "on the GPU" if r.get("on_gpu") else "spills to the CPU" if r.get("on_gpu") is False else "placement unknown"
    lay = r.get("layers")
    lay = f", {lay[0]}/{lay[1]} layers" if isinstance(lay, list) and len(lay) == 2 else ""
    n = lambda v: f"{v:,.0f}" if isinstance(v, (int, float)) else "?"  # noqa: E731
    return (f"{_k(r['window'])}: prompt {n(r.get('prompt_tok_s'))} tok/s · reply {n(r.get('tok_s'))} tok/s · "
            f"first token {n(r.get('ttft_ms'))} ms · {gpu}{lay}")


def lines(card: dict, stale_word: str = "") -> list:
    day = time.strftime("%Y-%m-%d", time.localtime(card.get("at") or 0))
    if card.get("pool"):  # 3.3.8.0 R4: the pool's own card (local_pool/bench.py): its members and split say where
        from halo_harness.local_pool.speed import head_line
        return [head_line(card, day, stale_word)] + ["  " + _row_line(r) for r in card.get("windows") or []] + [
            f"  reply reserve: at least {card['reserve_floor']:,}" if card.get("reserve_floor") else
            "  reply reserve: " + ("cut even at 512" if card.get("reserve_probes") else "not probed")]
    head = (f"speed card (the bench, {day}, Ollama {card.get('ollama_version') or '?'}"
            + (f", verified by {card['verified_by']}" if card.get("verified_by") else "")  # 3.3.7.0 R4: the refresh
            + (f"; {stale_word}: re-bench" if stale_word else "") + ")"
            + (f": cold load {card['cold_load_s']:g} s" if isinstance(card.get("cold_load_s"), (int, float)) else ""))
    from halo_harness.providers.local_bench_link import card_label
    lan = card_label(card)  # 3.3.8.1: a card measured over the LAN says so first
    out = ([lan] if lan else []) + [head] + ["  " + _row_line(r) for r in card.get("windows") or []]
    g, plan = card.get("max_gpu_window"), card.get("planner_window")
    out.append("  stays on the GPU up to " + (_k(g) if g else "none of the windows tried")
               + (f" (the planner says {_k(plan)})" if plan and plan != g else ""))
    rf = card.get("reserve_floor")
    out.append(f"  reply reserve: at least {rf:,} (a 256-token reply was cut below it)" if rf
               else "  reply reserve: cut even at 512 (it thinks at length: raise the reserve)"
               if card.get("reserve_probes") else "  reply reserve: not probed")
    return out


def view(card: dict, stale_word: str = "") -> dict:
    keep = ("model", "host", "digest", "ollama_version", "at", "cold_load_s", "windows", "max_gpu_window",
            "planner_window", "reserve_floor", "quick", "kv", "took_s", "verified_by", "refreshed_at", "over_lan",
            "measured_from", "link")
    return {**{k: card.get(k) for k in keep}, "stale": stale_word, "lines": lines(card, stale_word)}


def _now_version(host_name: str) -> Optional[str]:
    """The host's Ollama version now: the cached hardware card's, else one `/api/version` probe cached for the
    rest of this process (3.3.16.0 R1 fix: the Benchmarks page loads once and never re-reads, so a page answered
    before the hosts strip had filled the card cache showed no stale mark; the guard keeps the test flag's rule:
    loopback fakes only)."""
    try:
        from halo_harness.providers import ollama as O
        from halo_harness.providers.fit_meter import host_card_of
        from halo_harness.providers.ollama_guard import control_blocked
        host = O.resolve_ollama_host(host_name)
        if host is None:
            return None
        v = ((host_card_of(host) or {}).get("server") or {}).get("version")
        if v:
            return v
        if control_blocked(host) is None:
            return O.cached_ollama_version(host)
        with O._VERSION_CACHE_LOCK:
            return O._version_cache.get(host.url)
    except Exception:
        return None


def with_speed_card(card: dict, state_dir, row: Optional[dict] = None) -> dict:
    if not isinstance(card, dict) or card.get("kind") != "ollama" or not card.get("host") or state_dir is None:
        return card
    if row is None:
        from halo_harness.providers.fit_meter import _row_of
        row = _row_of(card) or {}
    sc = load(state_dir, card["host"], card.get("name") or "", (row or {}).get("digest"))
    if sc is None:
        sc = load(state_dir, card["host"], card.get("name") or "")
    if sc is None:
        return card
    word = stale(sc, digest=(row or {}).get("digest"), version=_now_version(card["host"]))
    card["speed_card"] = view(sc, word)
    card["speed"] = {**(card.get("speed") or {}), **mirror(sc), "stale": word}
    blocks = card.get("blocks") if isinstance(card.get("blocks"), dict) else None
    if blocks is not None:
        blocks["measured"] = list(blocks.get("measured") or []) + [{"text": t.strip(), "mark": "verified"}
                                                                   for t in lines(sc, word)]
        g = sc.get("max_gpu_window")
        if isinstance(blocks.get("sits"), dict):
            blocks["sits"]["gpu"] = (f"on the GPU up to {_k(g)} (the bench" + (f", {word})" if word else ")")) if g \
                else "spills at every window the bench tried"
    return card


def speed_index(state_dir, host_name: str) -> dict:
    key, now = (str(state_dir), host_name), time.monotonic()
    hit = _INDEX.get(key)
    if hit and now - hit[0] < CACHE_S:
        return hit[1]
    got = {c.get("model"): mirror(c) for c in reversed(all_cards(state_dir, host_name)) if c.get("model")}
    _INDEX[key] = (now, got)
    return got


def _on_host(ref, host_name: str) -> bool:
    ref = str(ref or "")
    if not ref.startswith("ol:"):
        return False
    at = ref.rsplit("@", 1)[1] if "@" in ref else None
    if at is None:
        from halo_harness.providers.ollama import resolve_ollama_host
        h = resolve_ollama_host(None)
        at = h.name if h is not None else ""
    return str(at).lower() == str(host_name).lower()


def _sessions() -> list:
    from halo_harness.peers.local_view import sessions
    return sessions()


def busy(state_dir, host_name: str, *, sessions: Optional[Callable] = None, now: Optional[float] = None,
         ps: Optional[list] = None) -> str:
    """Why a bench waits on this host now ("" when the card is quiet)."""
    from halo_harness.ollama_steward.ledger import parse_at, read_calls
    now = time.time() if now is None else now
    recent = [x for x in read_calls(state_dir, since=BUSY_S, host=host_name) if x.get("kind") != "calibrate"]
    if recent:
        last = recent[-1]
        ago = max(0, int(now - (parse_at(last.get("at")) or now)))
        return (f"{host_name} answered a call {ago} s ago ({last.get('model') or 'a model'}): a bench needs the card to "
                "itself; run it when the card has been quiet for a minute")
    try:
        rows = (sessions or _sessions)() or []
    except Exception:
        rows = []
    for r in rows:
        if r.get("pid") != os.getpid() and _on_host(r.get("model"), host_name):
            return (f"session {r.get('session_id') or '?'} is using {r.get('model')} on {host_name}: a bench needs the "
                    "card to itself; run it after that session ends")
    from halo_harness.providers.local_bench_busy import foreign_reason  # 3.3.7.0 R4: a client that is not a halo
    return foreign_reason(state_dir, host_name, ps=ps, now=now)
