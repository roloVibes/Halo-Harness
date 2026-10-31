"""halo_harness.studio.local_traffic -- Halo 3.3.5.0 R1: the Local tab's
traffic view, the ledger (ollama_steward/ledger.py) as a stream: one row per
call to a local server, the steward's server events inline.

    row(line, hosts, servers)   {id, type: "call", t, host, model, from, kind,
                                 prompt_in, reply_out, window, window_source,
                                 trimmed, cut, status, ok, tok_s, fitted,
                                 switched_from, bytes_in, bytes_out, error,
                                 warming, cache_reused_pct, preflight, composition (3.3.5.0 R4)}
    event_row(ev)               {id, type: "event", t, host, model, kind (loaded,
                                 unloaded, reloaded, cpu-spill, ...), say,
                                 severity, notify}
    traffic(state_dir, host="", since_s=900)
                                {rows (newest last), events, spark {host:
                                 [{t, calls, trims, cuts, errors, bytes_in,
                                 bytes_out}] per minute}, since_s, hosts}
    tap(publish)                a ledger_tap listener: every line and event
                                written for this home becomes a `traffic` frame
                                {rows: [...]} on the live feed

`id` is the line's own text hashed (ledger_tap.line_id), so the page drops a
row it already has whether it came by the catch-up or the frame.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

MAX_ROWS = 600
DEFAULT_SINCE_S = 900.0


def _ctx():
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.studio.ollama_hosts_view import local_servers
    try:
        return resolve_ollama_hosts(), local_servers()
    except Exception:
        return [], []


def row(line: dict, hosts=None, servers=None) -> dict:
    from halo_harness.ollama_steward.ledger import parse_at
    from halo_harness.ollama_steward.ledger_tap import line_id
    from halo_harness.studio.ollama_hosts_view import line_host
    if hosts is None:
        hosts, servers = _ctx()
    status = line.get("status")
    return {"id": line_id(line), "type": "call", "t": parse_at(line.get("at")), "at": line.get("at"),
            "host": line_host(line, hosts, servers or []), "model": line.get("model"), "from": line.get("from"),
            "kind": line.get("kind") or "turn", "prompt_in": line.get("prompt_eval_count"),
            "estimate": line.get("estimate_tokens"), "reply_out": line.get("eval_count"),
            "window": line.get("num_ctx_sent"), "window_source": line.get("window_source"),
            "trimmed": bool(line.get("trimmed")), "cut": line.get("done_reason") == "length", "status": status,
            "ok": status == 200, "tok_s": line.get("eval_tok_s"), "fitted": bool(line.get("fitted")),
            "switched_from": line.get("switched_from"), "bytes_in": line.get("bytes_in"),
            "bytes_out": line.get("bytes_out"), "error": line.get("error"), "session": line.get("session"),
            "total_ms": line.get("total_ms"), "load_ms": line.get("load_ms"),
            "warming": bool(line.get("warming")), "cache_reused_pct": line.get("cache_reused_pct"),  # 3.3.5.0 R4
            "preflight": line.get("preflight"), "composition": line.get("composition")}


def event_row(ev: dict) -> dict:
    from halo_harness.ollama_steward.ledger import parse_at
    from halo_harness.ollama_steward.ledger_tap import line_id
    return {"id": line_id(ev), "type": "event", "t": parse_at(ev.get("at")), "at": ev.get("at"),
            "host": ev.get("host"), "model": ev.get("model"), "kind": ev.get("kind"), "say": ev.get("say"),
            "severity": ev.get("severity") or "info", "notify": bool(ev.get("notify"))}


def spark(rows: list, since_s: float, now: float) -> dict:
    """Per host, a bucket per minute over the window: calls, trims, cuts, errors and the bytes."""
    start = int((now - since_s) // 60) * 60
    n = int((now - start) // 60) + 1
    out: dict = {}
    for r in rows:
        if r["type"] != "call" or r["t"] is None or r["kind"] == "calibrate":
            continue
        i = int((r["t"] - start) // 60)
        if not 0 <= i < n:
            continue
        b = out.setdefault(r["host"], [{"t": start + 60 * k, "calls": 0, "trims": 0, "cuts": 0, "errors": 0,
                                       "bytes_in": 0, "bytes_out": 0} for k in range(n)])[i]
        b["calls"] += 1
        b["trims"] += int(r["trimmed"])
        b["cuts"] += int(r["cut"])
        b["errors"] += int(not r["ok"])
        b["bytes_in"] += int(r.get("bytes_in") or 0)
        b["bytes_out"] += int(r.get("bytes_out") or 0)
    return out


def traffic(state_dir, host: str = "", since_s: float = DEFAULT_SINCE_S, *, now: Optional[float] = None) -> dict:
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.server_events import read_events
    now = time.time() if now is None else now
    hosts, servers = _ctx()
    rows = [row(x, hosts, servers) for x in read_calls(state_dir, since=since_s)]
    events = [event_row(e) for e in read_events(state_dir, since=since_s)]
    if host:
        rows = [r for r in rows if str(r["host"]).lower() == host.lower()]
        events = [e for e in events if str(e["host"] or "").lower() == host.lower()]
    rows = sorted(rows, key=lambda r: r["t"] or 0)[-MAX_ROWS:]
    events = sorted(events, key=lambda e: e["t"] or 0)[-MAX_ROWS:]
    names = sorted({r["host"] for r in rows} | {e["host"] for e in events if e["host"]})
    return {"rows": rows, "events": events, "spark": spark(rows, since_s, now), "since_s": since_s, "hosts": names,
            "at": now}


def frame_rows(kind: str, payload: list) -> list:
    """A tap's payload as rows (lines and events; other kinds none)."""
    if kind == "lines":
        hosts, servers = _ctx()
        return [row(x, hosts, servers) for x in payload if isinstance(x, dict)]
    if kind == "events":
        return [event_row(e) for e in payload if isinstance(e, dict)]
    return []


def tap(publish: Callable) -> Callable:
    """The ledger tap's listener for a Studio server: lines and events -> `traffic` frames; frames as they are."""
    def on(kind: str, payload: list) -> None:
        if kind == "frames":
            for f in payload:
                publish(f)
            return
        rows = frame_rows(kind, payload)
        if rows:
            publish({"session_id": "local", "event": "traffic", "ts": time.time(), "data": {"rows": rows}})
    return on
