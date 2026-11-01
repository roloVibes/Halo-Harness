"""halo_harness.local_pool.scan -- `halo pool scan` and Studio's Scan (Halo 3.3.8.0 R1; docs/POOL.md "Scan"): the
RPC port (pool.rpc_port, 50052) on the LAN and on every member, on explicit action only.

    scan(*, port=None, subnets=None, own_subnet=True, state_dir=None, home=None) -> {at, port, networks, candidates,
        members, notes, line}
        candidates: providers/rpc_probe.sweep's responders, each with `member` (the member it already is) and `paired`
        (the paired host at that address); members: each member's own probe (its paired host's address, 127.0.0.1
        for `local`, else its host). The answer is kept in `<state>/pool/scan.json` for the member rows.
    rtt_of(row, state_dir=None) -> {rtt_ms, rtt_alive, rtt_at, rtt_word}   from the last scan
    wifi_word(row) -> "Wi-Fi (adapter)" | "12 ms -- Wi-Fi?" | "0.4 ms" | "not probed (Scan)"
        the adapter type first, the RTT second: the host card's `link` says Wi-Fi for certain, an RTT only suspects it
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from halo_harness.local_pool.members import load, resolve, rpc_port, scan_subnets


def _file(state_dir=None) -> Path:
    from halo_harness.local_pool.members import path
    return path(state_dir).parent / "scan.json"


def last(state_dir=None) -> dict:
    try:
        got = json.loads(_file(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def _door(member: dict, home=None) -> str:
    how = resolve(member, home)
    return how["addr"] or member["host"]


def scan(*, port: Optional[int] = None, subnets=None, own_subnet: bool = True, state_dir=None, home=None) -> dict:
    from halo_harness.providers import rpc_probe as P
    port = int(port or rpc_port())
    subnets = scan_subnets() if subnets is None else list(subnets)
    lan = P.sweep(port, subnets=subnets, own_subnet=own_subnet)
    members = load(state_dir)
    doors = {(_door(m, home).lower(), int(m["rpc_port"])): m["name"] for m in members}
    try:
        from halo_harness.fleet import store
        from halo_harness.ollama_steward.host_client import _addr_port
        paired = {_addr_port(e.get("url") or "", 7431)[0]: str(e.get("name") or "") for e in store.hosts(home)}
    except Exception:
        paired = {}
    for c in lan["candidates"]:
        c["member"] = doors.get((c["host"].lower(), c["port"]))
        c["paired"] = paired.get(c["host"].lower()) or None
    probed = []
    for m in members:
        row = P.probe(_door(m, home), int(m["rpc_port"]))
        probed.append({"name": m["name"], **{k: row[k] for k in ("host", "port", "alive", "rtt_ms", "error",
                                                                  "wifi_suspect", "line")}})
    up = sum(1 for c in lan["candidates"] if c["alive"])
    line = (f"{up} rpc-server port{'s' if up != 1 else ''} answered on :{port}" + (f" across {', '.join(lan['networks'])}"
            if lan["networks"] else "") + f"; {sum(1 for p in probed if p['alive'])} of {len(probed)} members answer")
    out = {"at": time.time(), "port": port, "networks": lan["networks"], "candidates": lan["candidates"],
           "members": probed, "notes": lan["notes"], "line": line}
    try:
        from halo_harness.privateio import write_private_atomic
        _file(state_dir).parent.mkdir(parents=True, exist_ok=True)
        write_private_atomic(_file(state_dir), json.dumps(out, indent=1) + "\n")
    except OSError:
        pass
    return out


def _ago(at) -> str:
    s = max(0.0, time.time() - float(at or 0))
    return "just now" if s < 60 else f"{s / 60:.0f} min ago" if s < 7200 else f"{s / 3600:.0f} h ago"


def rtt_of(row: dict, state_dir=None) -> dict:
    got = last(state_dir)
    hit = next((m for m in got.get("members") or [] if m.get("name") == row.get("name")
                and int(m.get("port") or 0) == int(row.get("rpc_port") or 0)), None)
    if not hit:
        out = {"rtt_ms": None, "rtt_alive": None, "rtt_at": None}
    else:
        out = {"rtt_ms": hit.get("rtt_ms"), "rtt_alive": bool(hit.get("alive")), "rtt_at": got.get("at")}
    out["rtt_word"] = wifi_word({**row, **out})
    return out


def wifi_word(row: dict) -> str:
    from halo_harness.providers.rpc_probe import WIFI_MS, ms_word
    if (row.get("link") or {}).get("type") == "wireless":
        return "Wi-Fi (adapter)"
    if row.get("rtt_alive") is None:
        return "not probed (Scan)"
    if not row.get("rtt_alive"):
        return f"no answer on :{row.get('rpc_port')} ({_ago(row.get('rtt_at'))})"
    ms = row.get("rtt_ms")
    return f"{ms_word(ms)} -- Wi-Fi?" if isinstance(ms, (int, float)) and ms >= WIFI_MS else ms_word(ms)
