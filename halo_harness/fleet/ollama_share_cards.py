"""halo_harness.fleet.ollama_share_cards -- what else travels with the ledger push (Halo 3.3.7.0 R2; the push is
fleet/ollama_share.py, at its line cap; plans/local-model-fit-brief.md G11).

The member's side, `member_payload(home)` -> the fields beside `lines`:

    probes, crashes, events     3.3.6.0 R1-R3 (fleet/control_probes.py)
    speed_cards                 R2: the speed cards benched in the last RECENT_S on a host this machine serves
                                (providers/local_bench_runs.all_cards)
    dialect_records             R2: the dialect record of each model on a host this machine serves
                                (`ollama.profiles[...]["dialect"]`, providers/dialect.py), each with this machine's
                                LAN address and the server's port, sent when it changed

The hub's side, `take_member_payload(home, member, body)`: the probes, crashes and events as before; each speed card
kept in the hub's capability cache under `<member>:<host>` (`from` the member); each dialect record onto the hub's
own host entry at that address and port (dialect.set_fields by "hub": never over a field the hub's user set).
`reply_extra(home, member)` -> {fingerprints, fleet_from}: the fleet's crash fingerprints (the hub's own and every
other member's, newest first) go back in the hub's answer; the member keeps them (`take_fleet`) under
`<hub>:<host>` with `from`, so its `fingerprints.read` -- `exclude: crashed` and `halo ollama crashes` -- knows the
fleet's failures. (The hub's profiles, dialect records included, already go back: profiles.payload_for_member.)
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
from typing import Optional

RECENT_S = 600.0
MAX_ROWS = 10
FLEET_FPS = 20
_SENT: dict = {}  # str(home) -> {key: the digest of the dialect record last sent}


def _served() -> dict:
    from halo_harness.fleet.ollama_share import served_here
    from halo_harness.providers.ollama import resolve_ollama_hosts
    return {h.name: h for h in resolve_ollama_hosts() if served_here(h.url)}


def read_speed_cards(home, now: Optional[float] = None) -> list:
    from halo_harness.providers.local_bench_runs import all_cards
    now = time.time() if now is None else now
    served = _served()
    return [c for c in all_cards(home) if not c.get("from") and c.get("host") in served
            and now - float(c.get("at") or 0) < RECENT_S][:MAX_ROWS]


def read_dialects(home) -> list:
    from halo_harness.ollama_steward.profiles import all_profiles, split_key
    served, sent = _served(), _SENT.setdefault(str(home), {})
    try:
        from halo_harness.fleet.hub import lan_address
        addr = lan_address()
    except Exception:
        return []
    out = []
    for key, entry in all_profiles().items():
        host, model = split_key(key)
        d = entry.get("dialect")
        if host not in served or not isinstance(d, dict) or not d:
            continue
        digest = hashlib.sha1(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:12]
        if sent.get(key) == digest:
            continue
        sent[key] = digest
        out.append({"host": host, "model": model, "dialect": d, "addr": addr,
                    "port": urllib.parse.urlparse(served[host].url).port or 11434})
    return out[:MAX_ROWS]


def member_payload(home) -> dict:
    from halo_harness.fleet.control_probes import read_crashes, read_events, read_probes
    return {"probes": read_probes(home), "crashes": read_crashes(home), "events": read_events(home),
            "speed_cards": read_speed_cards(home), "dialect_records": read_dialects(home)}


def take_cards(home, member: str, rows) -> int:
    from halo_harness.providers.local_bench_runs import save
    n = 0
    for c in (rows if isinstance(rows, list) else [])[:MAX_ROWS]:
        if isinstance(c, dict) and c.get("digest") and c.get("host") and c.get("model"):
            save(home, {**c, "host": f"{member}:{c['host']}", "from": member, "member_host": c["host"]})
            n += 1
    return n


def _hub_host(addr: str, port: int) -> Optional[str]:
    from halo_harness.providers.ollama import resolve_ollama_hosts
    for h in resolve_ollama_hosts():
        u = urllib.parse.urlparse(h.url)
        if (u.hostname or "").lower() == str(addr).lower() and (u.port or 11434) == int(port or 11434):
            return h.name
    return None


def take_dialects(home, member: str, rows) -> int:
    from halo_harness.providers import dialect as D
    n = 0
    for r in (rows if isinstance(rows, list) else [])[:MAX_ROWS]:
        if not isinstance(r, dict) or not isinstance(r.get("dialect"), dict) or not r.get("model"):
            continue
        name = _hub_host(str(r.get("addr") or ""), int(r.get("port") or 11434))
        if not name:
            continue
        fields = {k: v for k, v in r["dialect"].items() if k in D.FIELDS}
        if fields:
            D.set_fields(name, str(r["model"]), fields, by="hub")
            n += 1
    return n


def take_member_payload(home, member: str, body: dict) -> None:
    from halo_harness.fleet.control_probes import take_crashes, take_events, take_probes
    take_probes(home, member, body.get("probes"))
    take_crashes(home, member, body.get("crashes"))
    take_events(home, member, body.get("events"))  # 3.3.6.0 R3: the member's server events (log_status.ladder)
    take_cards(home, member, body.get("speed_cards"))
    take_dialects(home, member, body.get("dialect_records"))


def reply_extra(home, member: str, hub_name: str) -> dict:
    from halo_harness.ollama_steward.fingerprints import read
    rows = [{k: v for k, v in fp.items() if k != "line"} for fp in read(home) if fp.get("from") != member][:FLEET_FPS]
    return {"fingerprints": rows, "fleet_from": hub_name}


def take_fleet(reply, home) -> int:
    """The member keeps the fleet's fingerprints from the hub's answer (never its own, sent back)."""
    from halo_harness.fleet import identity
    from halo_harness.ollama_steward.fingerprints import take
    if not isinstance(reply, dict) or not isinstance(reply.get("fingerprints"), list):
        return 0
    me = identity.fleet_name(home)
    rows = [fp for fp in reply["fingerprints"] if isinstance(fp, dict) and not str(fp.get("host") or "").startswith(f"{me}:")]
    return take(home, str(reply.get("fleet_from") or "hub"), rows)
