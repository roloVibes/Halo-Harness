"""halo_harness.local_sched.claims_file -- the file a bundle's claims live in (Halo 3.3.7.0 R5).

Two places hold claims, one shape: `<state>/host/claims.json` on a machine running `halo host` (the host's residency
state beside residency.json: every peer's claim on a card the host serves; host/ops_claim.py writes it, `GET
residency` answers it) and `<state>/ollama/claims.json` on a machine with no host (this machine's scheduler).

    Claim = {bundle, host, model, gb, window, priority, keep_alive, at, by, holder_pid, holder, scope, change_id,
             escalation, task_work}
        gb 0 and no model: a bundle that reserves nothing but is on (offline-only's escalation off, coder-first)
    read(path) -> [Claim]     put(path, claim) -> the rows (one per bundle and host: a new claim replaces its own)
    drop(path, bundle, host=None) -> the rows taken out
Written privately under a file lock; nothing here loads or unloads a model.
"""

from __future__ import annotations

import json
from pathlib import Path

FIELDS = ("bundle", "host", "model", "gb", "window", "priority", "keep_alive", "at", "by", "holder_pid", "holder", "scope",
          "change_id", "escalation", "task_work", "via", "name")


def host_file(home) -> Path:
    from halo_harness.host.state import host_dir
    return host_dir(home) / "claims.json"


def local_file(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / "claims.json"


def read(path) -> list:
    try:
        got = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = got.get("claims") if isinstance(got, dict) else None
    return [{k: r.get(k) for k in FIELDS} for r in rows or [] if isinstance(r, dict) and r.get("bundle")]


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
        rows = read(p)
        out = fn(rows)
        _write(p, rows)
    return out


def _same(a: dict, b: dict) -> bool:
    return a.get("bundle") == b.get("bundle") and str(a.get("host") or "").lower() == str(b.get("host") or "").lower()


def put(path, claim: dict) -> list:
    row = {k: claim.get(k) for k in FIELDS}

    def fn(rows: list) -> list:
        rows[:] = [r for r in rows if not _same(r, row)] + [row]
        return list(rows)
    return _change(path, fn)


def drop(path, bundle: str, host=None) -> list:
    def fn(rows: list) -> list:
        gone = [r for r in rows if r.get("bundle") == bundle and (host is None or str(r.get("host") or "").lower()
                                                                    == str(host).lower())]
        rows[:] = [r for r in rows if r not in gone]
        return gone
    return _change(path, fn)
