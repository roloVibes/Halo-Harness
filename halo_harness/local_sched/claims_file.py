"""halo_harness.local_sched.claims_file -- the file a bundle's claims live in (Halo 3.3.7.0 R5; 3.3.8.0 R3: the lease).

Two places hold claims, one shape: `<state>/host/claims.json` on a machine running `halo host` (the host's residency
state beside residency.json: every peer's claim on a card the host serves; host/ops_claim.py writes it, `GET
residency` answers it) and `<state>/ollama/claims.json` on a machine with no host (this machine's scheduler).

    Claim = {bundle, host, model, gb, window, priority, keep_alive, at, by, holder_pid, holder, scope, change_id,
             escalation, task_work, via, name, until}
        gb 0 and no model: a bundle that reserves nothing but is on (offline-only's escalation off, coder-first)
        until (3.3.8.0 R3): the claim's lease -- a time (epoch seconds) after which it is not a claim: nothing reads it,
        nothing counts it, `put` and `renew` clear it away. Its holder renews it (the peer's heartbeat:
        local_pool/claims.py), so the claim of a holder that died (a killed Studio) ends within the lease. None: no
        lease (a claim from the CLI, kept until `halo pack off`).
    read(path, *, now=None, expired=False) -> [Claim]   the live claims (expired=True: every row, the dead included)
    put(path, claim) -> the rows (one per bundle and host: a new claim replaces its own)
    renew(path, bundle, until, *, host=None, by=None) -> the rows renewed (only live ones: an expired claim stays dead)
    drop(path, bundle, host=None) -> the rows taken out (an expired one too: its release still lands)
    lease_s() -> pool.claim_lease_s (120)       live(row, now=None) -> bool
Written privately under a file lock; nothing here loads or unloads a model.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

FIELDS = ("bundle", "host", "model", "gb", "window", "priority", "keep_alive", "at", "by", "holder_pid", "holder", "scope",
          "change_id", "escalation", "task_work", "via", "name", "until")
LEASE_S = 120.0


def lease_s() -> float:
    from halo_harness.theme import get_config_value
    v = get_config_value("pool.claim_lease_s", default=LEASE_S)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else LEASE_S


def host_file(home) -> Path:
    from halo_harness.host.state import host_dir
    return host_dir(home) / "claims.json"


def local_file(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / "claims.json"


def live(row: dict, now: Optional[float] = None) -> bool:
    u = row.get("until")
    return not isinstance(u, (int, float)) or isinstance(u, bool) or float(u) >= (time.time() if now is None else now)


def _rows(path) -> list:
    try:
        got = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = got.get("claims") if isinstance(got, dict) else None
    return [{k: r.get(k) for k in FIELDS} for r in rows or [] if isinstance(r, dict) and r.get("bundle")]


def read(path, *, now: Optional[float] = None, expired: bool = False) -> list:
    rows = _rows(path)
    return rows if expired else [r for r in rows if live(r, now)]


def _write(path, rows: list) -> None:
    from halo_harness.privateio import write_private_atomic
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_private_atomic(p, json.dumps({"version": 1, "claims": rows}, indent=1))


def _change(path, fn) -> list:
    from halo_harness.filelock import file_lock
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(p, timeout=2.0):
        rows = _rows(p)
        out = fn(rows)  # drop sees an expired claim too (its release still lands); every write clears the dead ones
        _write(p, [r for r in rows if live(r)])
    return out


def _same(a: dict, b: dict) -> bool:
    return a.get("bundle") == b.get("bundle") and str(a.get("host") or "").lower() == str(b.get("host") or "").lower()


def put(path, claim: dict) -> list:
    row = {k: claim.get(k) for k in FIELDS}

    def fn(rows: list) -> list:
        rows[:] = [r for r in rows if not _same(r, row)] + [row]
        return list(rows)
    return _change(path, fn)


def renew(path, bundle: str, until: float, *, host=None, by: Optional[str] = None) -> list:
    def fn(rows: list) -> list:
        hit = [r for r in rows if r.get("bundle") == bundle and isinstance(r.get("until"), (int, float)) and live(r)
               and (host is None or str(r.get("host") or "").lower() == str(host).lower())
               and (by is None or str(r.get("by") or "") == by)]
        for r in hit:
            r["until"] = round(float(until), 3)
        return [dict(r) for r in hit]
    return _change(path, fn)


def drop(path, bundle: str, host=None) -> list:
    def fn(rows: list) -> list:
        gone = [r for r in rows if r.get("bundle") == bundle and (host is None or str(r.get("host") or "").lower()
                                                                    == str(host).lower())]
        rows[:] = [r for r in rows if r not in gone]
        return gone
    return _change(path, fn)
