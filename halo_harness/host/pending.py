"""halo_harness.host.pending -- the pending rows of `fleet.allow_control: ask` (Halo 3.3.7.0 R2; host/grants.py).

`<state>/host/pending.jsonl`, one row per queued request: {id, at, peer, peer_id, kind ("op" | "grant"), grant, op,
params, why, evidence, digest, state ("pending" | "allowed" | "denied" | "spent"), expires, answered_at?, spent_at?}.
A row lives `host.ask_ttl_s` (600 s); an allowed `op` row lets the same request (op + params, its `digest`) from that
peer run once within the TTL; an allowed `grant` row adds the grant (grants.grant).

    pending(home, peer=None) / queue(...) / queued_line(home, row, now) / spend(...) / answer(home, id, allow)
"""

from __future__ import annotations

import hashlib
import secrets
import json
import time
from typing import Optional

from halo_harness.host import state as S

PENDING_FILE = "pending.jsonl"
ASK_TTL_S = 600.0
KEEP_ROWS = 200


def ask_ttl_s(home) -> float:
    try:
        v = float(S._cfg("host.ask_ttl_s", ASK_TTL_S, home))
    except (TypeError, ValueError):
        return ASK_TTL_S
    return v if v > 0 else ASK_TTL_S


def _host_name(home) -> str:
    from halo_harness.fleet import identity
    return identity.fleet_name(home)


def _name(rec: Optional[dict], hid: str = "") -> str:
    return str((rec or {}).get("name") or hid[:8] or "this peer")


def _path(home):
    return S.host_dir(home) / PENDING_FILE


def _rows(home) -> list:
    out = []
    try:
        raw = _path(home).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in raw:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("id"):
            out.append(row)
    return out


def _write(home, rows: list) -> None:
    from halo_harness.privateio import write_private_atomic
    S.host_dir(home).mkdir(parents=True, exist_ok=True)
    write_private_atomic(_path(home), "".join(json.dumps(r, default=str) + "\n" for r in rows[-KEEP_ROWS:]))


def _edit(home, fn):
    from halo_harness.filelock import file_lock
    with file_lock(_path(home), timeout=2.0):
        rows = _rows(home)
        out = fn(rows)
        _write(home, rows)
        return out


def digest(op: str, params) -> str:
    return hashlib.sha1(json.dumps({"op": op, "params": params or {}}, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _live(row: dict, now: float) -> bool:
    return row.get("state") in ("pending", "allowed") and float(row.get("expires") or 0) > now


def pending(home, *, now: Optional[float] = None, peer: Optional[str] = None) -> list:
    """The rows still open (pending or allowed and not spent), newest first."""
    now = time.time() if now is None else now
    rows = [r for r in _rows(home) if _live(r, now) and (peer is None or r.get("peer_id") == peer)]
    return sorted(rows, key=lambda r: -float(r.get("at") or 0))


def queue(home, hid: str, rec: dict, kind: str, grant: str, op: str, body: dict, now: float) -> dict:
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    d = digest(op, params)
    row = {"id": f"p-{int(now) % 100000}-{secrets.token_hex(3)}", "at": now, "peer": _name(rec, hid), "peer_id": hid, "kind": kind,
           "grant": grant, "op": op, "params": params, "why": str(body.get("why") or "")[:300],
           "evidence": body.get("evidence") if isinstance(body.get("evidence"), dict) else None, "digest": d,
           "state": "pending", "expires": now + ask_ttl_s(home)}

    def fn(rows):
        hit = next((r for r in rows if r.get("peer_id") == hid and r.get("digest") == d and r.get("kind") == kind
                    and r.get("state") == "pending" and _live(r, now)), None)
        if hit is not None:
            return hit
        rows.append(row)
        return row
    return _edit(home, fn)


def queued_line(home, row: dict, now: float) -> str:
    left = max(0, int(float(row.get("expires") or now) - now))
    return (f"queued for {_host_name(home)}'s owner (fleet.allow_control: ask): `halo host allow {row['id']}` there, "
            f"or the Hosts card of its Studio; the row expires in {left} s")


def spend(home, hid: str, op: str, params, now: float) -> bool:
    d = digest(op, params)

    def fn(rows):
        for r in rows:
            if r.get("peer_id") == hid and r.get("digest") == d and r.get("state") == "allowed" and _live(r, now):
                r.update(state="spent", spent_at=now)
                return True
        return False
    return _edit(home, fn) if _path(home).exists() else False


def answer(home, pid: str, allow: bool, *, now: Optional[float] = None) -> "tuple[bool, str]":
    now = time.time() if now is None else now

    def fn(rows):
        row = next((r for r in rows if r.get("id") == pid), None)
        if row is None:
            return None, f"no pending row {pid} (`halo host pending` lists them)"
        if row.get("state") != "pending" or float(row.get("expires") or 0) <= now:
            return None, f"{pid} is {'expired' if row.get('state') == 'pending' else row.get('state')}: nothing to answer"
        row.update(state="allowed" if allow else "denied", answered_at=now)
        if allow:
            row["expires"] = now + ask_ttl_s(home)
        return row, ""
    if not _path(home).exists():
        return False, f"no pending row {pid} (`halo host pending` lists them)"
    row, why = _edit(home, fn)
    if row is None:
        return False, why
    if not allow:
        return True, f"denied {row['op']} for {row['peer']}"
    if row.get("kind") == "grant":
        from halo_harness.host.grants import grant
        ok, line = grant(home, row["peer_id"], row["grant"])
        return ok, line
    return True, (f"allowed {row['op']} for {row['peer']}: the same request from it runs once within "
                  f"{int(ask_ttl_s(home))} s")
