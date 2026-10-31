"""halo_harness.studio.local_warm -- Halo 3.3.5.0 R4: warm-up truth and the
prompt cache on the Local tab's model rows, from the traffic ledger.

    warm_map(state_dir, since="7d") -> {(host name, model): {load_s, cache_reused_pct, at}}
    warm_view(entry, loaded) -> {state: "warm" | "cold", load_s, line, cache_reused_pct, cache_line}

A loaded model (in `/api/ps`) is "warm"; one that is not is "cold", with the
last load the ledger saw ("cold (~25 s to load)": the newest call whose
`load_ms` was over 2 s). `cache_reused_pct` is the newest turn's share of
the prompt Ollama did not read again (ollama_steward/ledger_prompt.py).
"""

from __future__ import annotations

from typing import Optional


def warm_map(state_dir, since: str = "7d") -> dict:
    out: dict = {}
    if state_dir is None:
        return out
    try:
        from halo_harness.ollama_steward.ledger import read_calls
        from halo_harness.ollama_steward.ledger_prompt import WARM_LOAD_MS
        from halo_harness.ollama_steward.profiles import short_model
        lines = read_calls(state_dir, since=since)
    except Exception:
        return out
    for x in lines:
        host = (x.get("host") or {}).get("name") if isinstance(x.get("host"), dict) else None
        if not host or not x.get("model"):
            continue
        e = out.setdefault((str(host), short_model(x["model"])), {"load_s": None, "cache_reused_pct": None, "at": None})
        load = x.get("load_ms")
        if isinstance(load, (int, float)) and not isinstance(load, bool) and load > WARM_LOAD_MS:
            e["load_s"] = round(load / 1000.0)
        if x.get("kind") in (None, "turn") and isinstance(x.get("cache_reused_pct"), int):
            e["cache_reused_pct"] = x["cache_reused_pct"]
        e["at"] = x.get("at")
    return out


def warm_view(entry: Optional[dict], loaded) -> dict:
    e = entry or {}
    load_s = e.get("load_s")
    if loaded:
        state, line = "warm", "warm (loaded now)"
    else:
        state = "cold"
        line = f"cold (~{load_s} s to load)" if isinstance(load_s, int) else "cold (not loaded)"
    pct = e.get("cache_reused_pct")
    return {"state": state, "load_s": load_s, "line": line, "cache_reused_pct": pct,
            "cache_line": f"cache reused {pct} %" if isinstance(pct, int) else ""}
