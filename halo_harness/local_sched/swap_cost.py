"""halo_harness.local_sched.swap_cost -- how long a model takes to load on a host (Halo 3.3.7.0 R3; D1 3).

    load_s_for(host, model, *, state_dir=None, row=None, fetch=True) -> {s, source, n, line}
    switch_fields(ref, state_dir, row=None) -> {load_s, load_source}   model_switch.plan's two fields
    words(r) -> " · ~25 s to load when cold (the ledger, 4 loads)" | ""  model_switch.line_for's phrase
    secs(s) -> "25 s" | "3 m 02 s"

The sources, in order, the first that has a number wins and is named:
1. the ledger: the median of the newest LEDGER_N calls of that model on that host whose `load_ms` was over 2 s
   (the call that paid a load; ollama_steward/ledger_prompt.WARM_LOAD_MS), over the last 30 days;
2. the speed card: the bench's cold load (providers/local_bench_runs), else the battery profile's
   `speed.cold_load_s` -- 3.3.7.0 R4: neither when it was measured on an older build of this tag (the digest
   ollama_steward/tag_digests.py last saw differs);
3. the weights: the catalog row's size at DISK_GB_S GB/s (an estimate, said so).
Nothing is loaded and nothing is sent (`fetch=False`: no catalog read either, the row given or none).
"""

from __future__ import annotations

import statistics
from typing import Optional

LEDGER_N = 5
DISK_GB_S = 0.7
SINCE_S = 30 * 86400.0
GB = 1e9


def secs(s) -> str:
    if not isinstance(s, (int, float)) or s < 0:
        return "?"
    s = int(round(s))
    return f"{s} s" if s < 60 else f"{s // 60} m {s % 60:02d} s"


def _state(state_dir):
    if state_dir is not None:
        return state_dir
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _ledger(state_dir, name: str, model: str) -> "tuple[Optional[float], int]":
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.ledger_prompt import WARM_LOAD_MS
    try:
        lines = read_calls(state_dir, since=SINCE_S, host=name, model=model)
    except Exception:
        return None, 0
    loads = [x["load_ms"] / 1000.0 for x in lines if isinstance(x.get("load_ms"), (int, float))
             and not isinstance(x.get("load_ms"), bool) and x["load_ms"] > WARM_LOAD_MS][-LEDGER_N:]
    return (round(statistics.median(loads), 1), len(loads)) if loads else (None, 0)


def _card(state_dir, name: str, model: str) -> "tuple[Optional[float], str]":
    now_digest = None
    try:
        from halo_harness.providers.local_bench_runs import load
        sc = load(state_dir, name, model)
        from halo_harness.ollama_steward.tag_digests import current  # 3.3.7.0 R4: a card from an older build is dropped
        now_digest = current(state_dir, name, model)
        if sc and now_digest and sc.get("digest") and sc["digest"] != now_digest:
            sc = None
        if sc and isinstance(sc.get("cold_load_s"), (int, float)):
            return float(sc["cold_load_s"]), "the speed card (the bench)"
    except Exception:
        pass
    try:
        from halo_harness.providers.ollama_capability import profile_for
        p = profile_for(state_dir, model, name) or {}
        if now_digest and p.get("digest") and p["digest"] != now_digest:
            p = {}
        v = (p.get("speed") or {}).get("cold_load_s")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v), "the speed card (the battery)"
    except Exception:
        pass
    return None, ""


def load_s_for(host, model: str, *, state_dir=None, row: Optional[dict] = None, fetch: bool = True) -> dict:
    name = str(getattr(host, "name", host) or "")
    state = _state(state_dir)
    s, n = _ledger(state, name, model) if name else (None, 0)
    if s is not None:
        return {"s": s, "source": "the ledger", "n": n, "line": f"~{secs(s)} to load (the ledger, {n} load{'s' * (n != 1)})"}
    s, src = _card(state, name, model) if name else (None, "")
    if s is not None:
        return {"s": s, "source": src, "n": 1, "line": f"~{secs(s)} to load ({src})"}
    if row is None and fetch and name:
        from halo_harness.local_sched.facts import host_named, row as row_of
        row = row_of(host_named(name) if isinstance(host, str) else host, model)[0]
    size = (row or {}).get("size")
    if isinstance(size, int) and size > 0:
        s = round(size / GB / DISK_GB_S, 1)
        src = f"an estimate from the weights ({size / GB:.1f} GB at ~{DISK_GB_S:g} GB/s)"
        return {"s": s, "source": src, "n": 0, "line": f"~{secs(s)} to load ({src})"}
    return {"s": None, "source": "unknown", "n": 0, "line": "load time unknown (no load measured, no weights read)"}


def switch_fields(ref, state_dir, row: Optional[dict] = None) -> dict:
    """model_switch.plan's `load_s` / `load_source` for an `ol:` target (None elsewhere); never raises."""
    if getattr(ref, "provider", "") != "ollama":
        return {"load_s": None, "load_source": None}
    try:
        from halo_harness.local_sched.facts import host_named
        host = host_named(getattr(ref, "host", None))
        got = load_s_for(host or getattr(ref, "host", ""), ref.model, state_dir=state_dir, row=row, fetch=False)
    except Exception:
        return {"load_s": None, "load_source": None}
    return {"load_s": got["s"], "load_source": got["source"] if got["s"] is not None else None}


def words(r: dict) -> str:
    s = r.get("load_s")
    if not isinstance(s, (int, float)):
        return ""
    return f" · ~{secs(s)} to load when cold ({r.get('load_source')})"
