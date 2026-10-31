"""halo_harness.ollama_steward.fingerprints -- Halo 3.3.6.0 R2: a crash fingerprint per host and model
(plans/local-model-fit-brief.md G11, the first half; the fleet half is 3.3.7.0's).

    signature_of(event) -> "CUDA IMA" | "CUDA error" | "GPU out of memory" | "runner died (0xc0000409)" |
                           "runner died" | "load failed" | None (not a crash)
    record(state_dir, rows, host, *, card=None, catalog=None) -> [fingerprint]   server_events.record_events calls it
    read(state_dir, host=None) -> [fingerprint], newest first        line(fp) -> "crashed here on <date>: ..."
    read_recent(state_dir, since) / take(state_dir, member, rows)   the ledger push to the hub and its side

Fingerprint = {host, model, model_from, family, quant, window_used, kv_cache_type, flash_attention, spill
(size_vram < size), signature, at, count, evidence [lines]} in `<state>/ollama/fingerprints.jsonl` (one line a
crash). The events of one crash (the CUDA line, `llama-server terminated`, the 500) within JOIN_S of each other on
one host and model are one fingerprint, its signature the most specific. The model is the event's, else the newest
load on that host before it ("the newest load before it"); the window and the spill come from that load's `/api/ps`
reading, else the battery profile's window; the KV type and flash attention from the host card at that time (the
Ollama panel's cache, read when it is empty: a crash is rare); the family and quant from the catalog this process
cached, else the name.
"""

from __future__ import annotations

import json
import time
from typing import Optional

FILE = "fingerprints.jsonl"
JOIN_S = 120.0
LOOKBACK_S = 1800.0
KEEP = 500
ORDER = ("CUDA IMA", "CUDA error", "GPU out of memory", "runner died (0xc0000409)", "runner died", "load failed")
WORDS = {"CUDA IMA": "CUDA error (an illegal memory access)", "CUDA error": "a CUDA error",
         "GPU out of memory": "the GPU ran out of memory", "runner died (0xc0000409)": "llama-server died (exit 0xc0000409)",
         "runner died": "llama-server died", "load failed": "the load failed"}
KEY = ("host", "model", "signature", "window_used", "kv_cache_type", "flash_attention", "spill")


def _path(state_dir):
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / FILE


def signature_of(ev: dict) -> Optional[str]:
    text = f"{ev.get('evidence') or ''} {ev.get('say') or ''}".lower()
    kind = ev.get("kind")
    if kind not in ("gpu-memory", "other-error", "load-failed"):
        return None
    if "illegal memory access" in text:
        return "CUDA IMA"
    if "0xc0000409" in text:
        return "runner died (0xc0000409)"
    if "llama-server terminated" in text or "runner terminated" in text or "runner process has terminated" in text:
        return "runner died"
    if kind == "load-failed":
        return None if (ev.get("data") or {}).get("client_abort") else "load failed"
    if "out of memory" in text or "cudamalloc failed" in text or "oom detected" in text:
        return "GPU out of memory"
    if "cuda error" in text:
        return "CUDA error"
    return "GPU out of memory" if kind == "gpu-memory" else None


def _t(at) -> float:
    from halo_harness.ollama_steward.ledger import parse_at
    t = parse_at(at) if not isinstance(at, (int, float)) else at
    return float(t) if t is not None else 0.0


def _load_before(state_dir, host, model, at: float) -> "tuple[Optional[str], Optional[dict], bool]":
    """(the model, its newest load's data, a cpu-spill event seen) from the events before `at` on this host."""
    from halo_harness.ollama_steward.server_events import read_events
    rows = [r for r in read_events(state_dir, host=host) if at - LOOKBACK_S <= _t(r.get("at")) <= at + 1]
    from halo_harness.providers.ollama import ollama_names_match
    resident: dict = {}
    spill = False
    for r in rows:
        k, m = r.get("kind"), r.get("model")
        if k in ("loaded", "reloaded") and m:
            resident[m] = r.get("data") or {}
        elif k == "unloaded" and m:
            resident.pop(m, None)
        elif k == "cpu-spill" and (not model or not m or ollama_names_match(m, model)):
            spill = True
    if model:
        hit = next((d for m, d in resident.items() if ollama_names_match(m, model)), None)
        return model, hit, spill
    if resident:
        m = list(resident)[-1]
        return m, resident[m], spill
    return None, None, spill


def _facts(state_dir, host, model, card, catalog) -> dict:
    from halo_harness.providers import model_card_purpose as P
    row = next((r for r in (catalog or {}).get("models") or [] if isinstance(r, dict) and model
                and str(r.get("model") or r.get("name") or "").split(":latest")[0] == model.split(":latest")[0]), None)
    details = (row or {}).get("details") or {}
    server = (card or {}).get("server") or {}
    out = {"family": P.family_of(model or "", details)[0] or None, "quant": P.quant_of(model or "", details)[0] or None,
           "kv_cache_type": server.get("kv_cache_type"), "flash_attention": server.get("flash_attention")}
    if model and state_dir is not None:
        from halo_harness.providers.ollama_capability import profile_for
        p = profile_for(state_dir, model, host)
        out["profile_window"] = ((p or {}).get("window") or {}).get("used")
    return out


def _seams(host_name):
    try:
        from halo_harness.providers.fit_meter import host_card_of
        from halo_harness.providers.local_models_cached import cached_catalog
        from halo_harness.providers.ollama import resolve_ollama_host
        h = resolve_ollama_host(host_name) if host_name else None
        return (host_card_of(h, read=True) if h else None), (cached_catalog(h) if h else None)  # a crash is rare: read it
    except Exception:
        return None, None


def read(state_dir, host: Optional[str] = None) -> list:
    if state_dir is None:
        return []
    out = []
    try:
        with open(_path(state_dir), "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                try:
                    fp = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(fp, dict) and (not host or str(fp.get("host") or "").lower() == host.lower()):
                    out.append({**fp, "line": line(fp)})
    except OSError:
        return []
    return sorted(out, key=lambda fp: -_t(fp.get("at")))


def _write(state_dir, rows: list) -> None:
    path = _path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for fp in rows[-KEEP:]:
            f.write(json.dumps({k: v for k, v in fp.items() if k != "line"}, ensure_ascii=False, default=str) + "\n")
    import os
    os.replace(tmp, path)


def record(state_dir, rows: list, host: Optional[str], *, card=None, catalog=None) -> list:
    """One fingerprint per crash among `rows` (record_events' rows); the ones written or joined."""
    crashes = [(r, s) for r in rows or [] if (s := signature_of(r))]
    if not crashes or state_dir is None:
        return []
    if card is None and catalog is None:
        card, catalog = _seams(host)
    from halo_harness.filelock import file_lock
    from halo_harness.ollama_steward.ledger import now_iso
    done = []
    with file_lock(_path(state_dir), timeout=2.0):
        have = list(reversed(read(state_dir)))
        for ev, sig in crashes:
            at = _t(ev.get("at")) or time.time()
            model, load, spilled = _load_before(state_dir, host, ev.get("model"), at)
            f = _facts(state_dir, host, model, card, catalog)
            size, vram = (load or {}).get("size"), (load or {}).get("size_vram")
            spill = (vram < size) if isinstance(size, int) and isinstance(vram, int) else (True if spilled else None)
            near = next((x for x in reversed(have) if x.get("host") == host and x.get("model") == model
                         and abs(_t(x.get("at")) - at) <= JOIN_S), None)
            if near is not None:
                if ORDER.index(sig) < ORDER.index(near.get("signature") if near.get("signature") in ORDER else ORDER[-1]):
                    near["signature"] = sig
                near["evidence"] = (list(near.get("evidence") or []) + [str(ev.get("evidence") or "")[:300]])[-4:]
                done.append(near)
                continue
            fp = {"host": host, "model": model, "model_from": "the event" if ev.get("model") else
                  ("the newest load before it" if model else "unknown"), "family": f["family"], "quant": f["quant"],
                  "window_used": (load or {}).get("context_length") or f.get("profile_window"),
                  "kv_cache_type": f["kv_cache_type"], "flash_attention": f["flash_attention"], "spill": spill,
                  "signature": sig, "at": now_iso(at), "evidence": [str(ev.get("evidence") or "")[:300]]}
            fp["count"] = 1 + sum(1 for x in have if all(x.get(k) == fp.get(k) for k in KEY))
            have.append(fp)
            done.append(fp)
        _write(state_dir, have)
    return [{**fp, "line": line(fp)} for fp in done]


def line(fp: dict) -> str:
    t = _t(fp.get("at"))
    date = time.strftime("%Y-%m-%d", time.localtime(t)) if t else "?"
    w, kv = fp.get("window_used"), fp.get("kv_cache_type")
    out = f"crashed here on {date}: {WORDS.get(fp.get('signature'), fp.get('signature') or 'a crash')}"
    out += " after a spill" if fp.get("spill") else ""
    out += f" at {w:,}" if isinstance(w, int) else ""
    out += f" with {kv} KV" if kv else ""
    out += ", flash attention on" if str(fp.get("flash_attention")).lower() in ("true", "1", "on", "enabled") else ""
    return out + (f" ({fp['count']} times)" if int(fp.get("count") or 1) > 1 else "")


def read_recent(state_dir, since_s: float = 600.0) -> list:
    """The member's side of the ledger push: its own fingerprints of the last `since_s` (none taken from a member)."""
    now = time.time()
    return [{k: v for k, v in fp.items() if k != "line"} for fp in read(state_dir)
            if not fp.get("from") and now - _t(fp.get("at")) <= since_s][:20]


def take(state_dir, member: str, rows) -> int:
    """The hub's side: a member's fingerprints kept under `<member>:<host>` with `from` (the fleet half is 3.3.7.0's)."""
    if not isinstance(rows, list) or not member or state_dir is None:
        return 0
    from halo_harness.filelock import file_lock
    with file_lock(_path(state_dir), timeout=2.0):
        have = list(reversed(read(state_dir)))
        seen = {(x.get("host"), x.get("model"), x.get("at")) for x in have}
        n = 0
        for fp in rows[:20]:
            if not isinstance(fp, dict) or not fp.get("signature"):
                continue
            keep = {**fp, "host": f"{member}:{fp.get('host')}", "from": member}
            if (keep["host"], keep.get("model"), keep.get("at")) in seen:
                continue
            have.append(keep)
            n += 1
        if n:
            _write(state_dir, have)
    return n
