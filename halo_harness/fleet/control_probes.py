"""halo_harness.fleet.control_probes -- Halo 3.3.6.0 R1: a member's battery
profiles reach the hub with the member's ledger push (fleet/ollama_share.py),
the way its pull jobs do (fleet/control_pulls.py).

    read_probes(home, now=None)         the member's side: the profiles it made in the last RECENT_S
                                        (the capability cache), without the raw evidence
    take_probes(home, member, rows)     the hub's side: each kept in the hub's own capability cache
    read_events / take_events           3.3.6.0 R3: the member's server events (the hub's log ladder)
                                        (`from` = the member, `host` = the hub's name for that host when a
                                        probe job of the hub asked for it) and onto that job
"""

from __future__ import annotations

import time
from typing import Optional

RECENT_S = 600.0
MAX_ROWS = 10


def read_probes(home, now: Optional[float] = None) -> list:
    from halo_harness.providers.ollama_capability import all_profiles
    from halo_harness.studio.local_probe_job import compact
    now = time.time() if now is None else now
    rows = [p for p in all_profiles(home) if not p.get("from") and now - float(p.get("probed_at") or 0) < RECENT_S]
    return [compact(p) for p in rows[:MAX_ROWS]]


def take_probes(home, member: str, rows) -> int:
    from halo_harness.providers.ollama_capability import save_profile
    from halo_harness.studio.local_probe_job import take_remote
    if not isinstance(rows, list) or not member:
        return 0
    n = 0
    for p in rows[:MAX_ROWS]:
        if not isinstance(p, dict) or not p.get("digest") or not p.get("model"):
            continue
        hub_host = take_remote(member, p)
        keep = {**p, "from": member, "member_host": p.get("host"),
                "host": hub_host if isinstance(hub_host, str) and hub_host else f"{member}:{p.get('host')}"}
        save_profile(home, keep)
        n += 1
    return n


def read_crashes(home) -> list:
    """3.3.6.0 R2: the member's crash fingerprints of the last RECENT_S (ollama_steward/fingerprints.py)."""
    from halo_harness.ollama_steward.fingerprints import read_recent
    return read_recent(home, RECENT_S)


def take_crashes(home, member: str, rows) -> int:
    from halo_harness.ollama_steward.fingerprints import take
    return take(home, member, rows)


MAX_EVENTS = 50
_SENT: dict = {}  # str(home) -> the newest event `at` this member pushed


def read_events(home, now: Optional[float] = None) -> list:
    """3.3.6.0 R3: the member's new server events of the hosts it serves, each with `addr` / `port` (this machine's
    LAN address and the server's port): the hub ties them to its own host entry by address (log_status.ladder)."""
    import urllib.parse
    from halo_harness.fleet.ollama_share import served_here
    from halo_harness.ollama_steward.ledger import parse_at
    from halo_harness.ollama_steward.server_events import read_events as events
    from halo_harness.providers.ollama import resolve_ollama_hosts
    now = time.time() if now is None else now
    hosts = {h.name: h for h in resolve_ollama_hosts() if served_here(h.url)}
    since = _SENT.get(str(home), now - RECENT_S)
    rows = [r for r in events(home, since=RECENT_S) if not r.get("from") and r.get("host") in hosts
            and (parse_at(r.get("at")) or 0) >= since][-MAX_EVENTS:]
    if not rows:
        return []
    _SENT[str(home)] = max(parse_at(r.get("at")) or 0 for r in rows) + 0.001
    try:
        from halo_harness.fleet.hub import lan_address
        addr = lan_address()
    except Exception:
        return []
    keep = ("kind", "severity", "say", "evidence", "at", "model", "data", "host")
    return [{**{k: r.get(k) for k in keep}, "addr": addr, "port": urllib.parse.urlparse(hosts[r["host"]].url).port or 11434}
            for r in rows]


def take_events(home, member: str, rows) -> int:
    """The hub's side: a member's events kept in its events.jsonl under `<member>:<host>` with `from` (never notified)."""
    import json
    from halo_harness.filelock import file_lock
    from halo_harness.ollama_steward.server_events import events_path, read_events as events
    if not isinstance(rows, list) or not member or home is None:
        return 0
    seen = {(r.get("host"), r.get("at"), r.get("kind")) for r in events(home, since=86400.0) if r.get("from") == member}
    clean = []
    for r in rows[:MAX_EVENTS]:
        if not isinstance(r, dict) or not r.get("kind"):
            continue
        row = {**{k: r.get(k) for k in ("kind", "severity", "say", "evidence", "at", "model", "data", "addr", "port")},
               "host": f"{member}:{r.get('host')}", "from": member, "notify": False}
        if (row["host"], row["at"], row["kind"]) not in seen:
            clean.append(row)
    if clean:
        path = events_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(path, timeout=2.0):
            with open(path, "a", encoding="utf-8", newline="\n") as f:
                for row in clean:
                    f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return len(clean)


__all__ = ["read_crashes", "read_events", "read_probes", "take_crashes", "take_events", "take_probes"]
