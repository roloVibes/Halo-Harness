"""halo_harness.ollama_steward.hardware_servers -- Halo 3.3.8.0 R2: the local servers on a machine, as its hardware
card lists them (`halo ollama hardware`, the host's `GET card`, Local -> Hosts): each llama-server, LM Studio or
mlx_lm.server with its runtime, its model, its window per slot (the newest load in its log) and its log's status line.
Sizes and names only; nothing is sent to a server.

    rows(state_dir=None, servers=None) -> [{name, port, url, runtime, source, model, window, log}]
    lines(rows) -> ["local server llama-8080: llama-server, qwen3-8b, window 8,192 per slot · log: live ..."]
"""

from __future__ import annotations

from typing import Optional


def _newest_load(state_dir, name: str) -> dict:
    from halo_harness.ollama_steward.server_events import read_events
    rows = [e for e in read_events(state_dir, since=7 * 86400.0, kind="load-result", host=name)]
    return {"model": rows[-1].get("model"), **(rows[-1].get("data") or {})} if rows else {}


def rows(state_dir=None, servers: Optional[list] = None) -> list:
    from halo_harness.ollama_steward.log_status_hf import status
    from halo_harness.ollama_steward.servers_hf import _state, is_local, port_of, roster
    state_dir = _state(state_dir)
    out = []
    for s in roster(state_dir) if servers is None else servers:
        if not (is_local(s) or s.log):
            continue
        ld = _newest_load(state_dir, s.name)
        try:
            st = status(state_dir, s)
            log = {k: st.get(k) for k in ("state", "line", "path", "readable", "why", "last_line_at", "rung")}
        except Exception:
            log = None
        out.append({"name": s.name, "port": port_of(s.url), "url": s.url, "runtime": s.runtime, "source": s.source,
                    "model": ld.get("model") or s.model, "window": ld.get("window"), "slots": ld.get("n_slots"),
                    "log": log})
    return out


def lines(server_rows) -> list:
    out = []
    for r in server_rows or []:
        if not isinstance(r, dict):
            continue
        bits = [r.get("runtime") or "a local server", r.get("model") or "",
                f"window {r['window']:,} per slot" if isinstance(r.get("window"), int) else ""]
        log = (r.get("log") or {}).get("line")
        out.append(f"local server {r.get('name')}: " + ", ".join(b for b in bits if b) + (f" · log: {log}" if log else ""))
    return out
