"""halo_harness.providers.local_bench_busy -- the busy wait's third reason: a client that is not a halo (Halo 3.3.7.0
R4; providers/local_bench_runs.busy reads it after the ledger and the sessions).

    host_of(host_name) -> the configured OllamaHost of exactly that name, else None (no default stands in)
    foreign_reason(state_dir, host_name, *, ps=None, now=None) -> "" | "a client that is not a halo holds ..."

A model in `/api/ps` that no Halo record explains (ollama_steward/idle.py) is a user of the card like any other: the
bench and the off-hours refresh wait for it. One `/api/ps` read; nothing loads.
"""

from __future__ import annotations

from typing import Optional


def host_of(host_name: str):
    try:
        from halo_harness.providers.ollama import resolve_ollama_hosts
        return next((h for h in resolve_ollama_hosts() if h.name.lower() == str(host_name or "").lower()), None)
    except Exception:
        return None


def foreign_reason(state_dir, host_name: str, *, ps: Optional[list] = None, now: Optional[float] = None) -> str:
    if state_dir is None:
        return ""
    host = host_of(host_name)
    if host is None and ps is None:
        return ""
    from halo_harness.ollama_steward.idle import busy_reason, foreign
    try:
        return busy_reason(foreign(state_dir, host or host_name, ps=ps, now=now), host_name)
    except Exception:
        return ""
