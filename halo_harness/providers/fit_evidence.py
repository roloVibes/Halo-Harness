"""halo_harness.providers.fit_evidence -- Halo 3.3.6.0 R3: the fit badge cites the log
(plans/local-model-fit-brief.md Part C's deliverable).

    evidence(state_dir, host_name, model) -> {state: "verified" | "spilled" | "unverified", line, layers [n, of],
        splits, kv_gpu_mib, kv_cpu_mib, on_gpu_pct, tok_s, window, at, source ("the log" | "/api/ps" | None), why}
    line_of(state, *, layers=None, splits=None, tok_s=None, window=None, on_gpu_pct=None, why="")
        -> "verified -- 41/41 layers, splits = 2, 258 tok/s" | "spilled -- 59/66 layers, 16 tok/s" | "unverified"
    for_card(card, state_dir) -> the evidence of a local card's model on its host, or None

From the model's newest load on that host: the server log's `load-result` event (`offloaded N/N`, `graph splits`,
the KV buffers, ollama_steward/fingerprint_facts.py) or the steward's `/api/ps` reading (`size_vram == size`,
server_events.ps_delta), whichever is newer, and the measured tok/s from the ledger (the median of the newest five
answered, not warming, calls). Spilled: fewer layers on the GPU than the model has, a KV buffer on the CPU, more than
two graph splits, or `size_vram < size`. Verified: every layer (or every byte) on the GPU. Unverified: no load seen.
ollama_twin_verify's line (R1) is the same `line_of`.
"""

from __future__ import annotations

import statistics
import time
from typing import Optional

CACHE_S = 10.0
SINCE_S = 30 * 86400.0
_CACHE: dict = {}


def line_of(state: str, *, layers=None, splits=None, tok_s=None, window=None, on_gpu_pct=None, why: str = "") -> str:
    lay = f"{layers[0]}/{layers[1]} layers" if isinstance(layers, (list, tuple)) and len(layers) == 2 else ""
    tok = f"{tok_s:.0f} tok/s" if isinstance(tok_s, (int, float)) else ""
    if tok and isinstance(window, int):
        tok += f" at {window:,}"
    if state == "verified":
        bits = [b for b in (lay or ("every byte on the GPU" if on_gpu_pct is not None else ""),
                            f"splits = {splits}" if splits is not None else "", tok) if b]
        return "verified -- " + (", ".join(bits) or "every byte on the GPU")
    if state == "spilled":
        pct = f"{on_gpu_pct}% on the GPU" if on_gpu_pct is not None else ""
        bits = [b for b in (lay or pct, f"splits = {splits}" if not lay and isinstance(splits, int) and splits > 2 else "",
                            tok) if b]
        return "spilled -- " + (", ".join(bits) or "part of it runs on the CPU")
    return "unverified" + (f" -- {why}" if why else "")


def _rows(state_dir, host_name: str) -> "tuple[list, list]":
    key, now = (str(state_dir), host_name), time.monotonic()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < CACHE_S:
        return hit[1], hit[2]
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.server_events import read_events
    from halo_harness.ollama_steward.host_reads import events_of  # 3.3.7.0 R1: the events a paired halo host keeps
    evs = [e for e in read_events(state_dir, since=SINCE_S, host=host_name) + events_of(state_dir, host_name, SINCE_S)
           if e.get("kind") in ("load-result", "loaded", "reloaded")]
    evs.sort(key=lambda e: str(e.get("at") or ""))
    calls = [x for x in read_calls(state_dir, since=7 * 86400.0, host=host_name)
             if x.get("status") == 200 and not x.get("warming") and isinstance(x.get("eval_tok_s"), (int, float))]
    _CACHE[key] = (now, evs, calls)
    return evs, calls


def evidence(state_dir, host_name: Optional[str], model: Optional[str]) -> dict:
    out = {"state": "unverified", "layers": None, "splits": None, "kv_gpu_mib": None, "kv_cpu_mib": None,
           "on_gpu_pct": None, "tok_s": None, "window": None, "at": None, "source": None, "why": "no load seen yet"}
    if state_dir is None or not host_name or not model:
        out["line"] = line_of("unverified")
        return out
    from halo_harness.ollama_steward.fingerprint_facts import spilled
    from halo_harness.ollama_steward.ledger import parse_at
    from halo_harness.providers.ollama import ollama_names_match
    evs, calls = _rows(state_dir, host_name)
    mine = [e for e in evs if e.get("model") and ollama_names_match(e["model"], model)]
    load = next((e for e in reversed(mine) if e["kind"] == "load-result"), None)
    ps = next((e for e in reversed(mine) if e["kind"] in ("loaded", "reloaded")), None)
    toks = [x["eval_tok_s"] for x in calls if x.get("model") and ollama_names_match(x["model"], model)][-5:]
    out["tok_s"] = round(statistics.median(toks), 1) if toks else None
    t_load, t_ps = (parse_at(load.get("at")) or 0) if load else -1, (parse_at(ps.get("at")) or 0) if ps else -1
    if load is not None and t_load >= t_ps:
        d = load.get("data") or {}
        out.update(layers=d.get("layers"), splits=d.get("splits"), kv_gpu_mib=d.get("kv_gpu_mib"), at=load.get("at"),
                   kv_cpu_mib=d.get("kv_cpu_mib"), window=d.get("window"), source="the log", why="")
        spill = spilled(d)
        out["state"] = "spilled" if spill else "verified" if spill is False else "unverified"
    elif ps is not None:
        d = ps.get("data") or {}
        size, vram = d.get("size"), d.get("size_vram")
        out.update(at=ps.get("at"), window=d.get("context_length"), source="/api/ps", why="")
        if isinstance(size, int) and size > 0 and isinstance(vram, int):
            out["on_gpu_pct"] = round(100.0 * vram / size)
            out["state"] = "verified" if vram >= size else "spilled"
    if out["state"] == "unverified" and not out["why"]:
        out["why"] = "the newest load names no placement"
    out["line"] = line_of(out["state"], layers=out["layers"], splits=out["splits"], tok_s=out["tok_s"],
                          on_gpu_pct=out["on_gpu_pct"], why="" if out["state"] != "unverified" else out["why"])
    return out


def for_card(card: dict, state_dir) -> Optional[dict]:
    if not isinstance(card, dict) or card.get("kind") != "ollama" or not card.get("host"):
        return None
    try:
        if state_dir is None:
            from halo_harness.config.paths import bridge_home
            state_dir = bridge_home()
        e = evidence(state_dir, card.get("host"), card.get("name"))
        return {k: e.get(k) for k in ("state", "line", "layers", "splits", "tok_s", "on_gpu_pct", "source", "at", "why")}
    except Exception:
        return None
