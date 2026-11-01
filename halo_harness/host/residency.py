"""halo_harness.host.residency -- the host's residency clock (Halo 3.3.7.0 R4; docs/HOST.md "The residency clock").

When a halo host serves the card, every peer's warm, pin and pivot lands through the host's typed operations, so the
host is the one place that knows when each model was loaded and by whom. It keeps that in `<state>/host/residency.json`
`{"<server>|<model>": {at, by, op, keep_alive}}` (a load writes the row, an unload removes it), answers it on `GET
residency`, and every peer's scheduler reads it for `held_for` (local_sched/pivot.py): one shared clock per card
instead of one per process. Two halos with no host each keep their own clock (pivot's `_SINCE`) and say so.

    mark(home, host_name, model, *, by="", op="warm", keep_alive=None, now=None)   a load landed
    forget(home, host_name, model)                                                    an unload landed
    read(home) -> {key: row}         rows(home) -> [{host, model, at, by, op, keep_alive}]   the GET answer
    held_for(rows, host_name, model, min_s, *, now=None) -> seconds still held (0.0 when free or not on the clock)
    claims(home, now=None) -> the live claims on the cards this host serves (3.3.8.0 R3: a claim past its lease
        `until` is not a claim -- its holder stopped renewing it; local_sched/claims_file.py)
No request is sent; nothing here loads or unloads a model.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

FILE = "residency.json"


def _path(home) -> Path:
    from halo_harness.host.state import host_dir
    return host_dir(home) / FILE


def _key(host_name: str, model: str) -> str:
    from halo_harness.ollama_steward.profiles import short_model
    return f"{str(host_name or '').lower()}|{short_model(model)}"


def read(home) -> dict:
    try:
        got = json.loads(_path(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in got.items() if isinstance(v, dict)} if isinstance(got, dict) else {}


def _write(home, data: dict) -> None:
    from halo_harness.privateio import write_private_atomic
    p = _path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_private_atomic(p, json.dumps(data, indent=1))


def _change(home, fn) -> None:
    try:
        from halo_harness.filelock import file_lock
        with file_lock(_path(home), timeout=2.0):
            data = read(home)
            fn(data)
            _write(home, data)
    except OSError:
        pass


def mark(home, host_name: str, model: str, *, by: str = "", op: str = "warm", keep_alive=None,
         now: Optional[float] = None) -> None:
    if not model or home is None:
        return
    row = {"at": round(time.time() if now is None else now, 3), "by": by or "", "op": op, "keep_alive": keep_alive}
    _change(home, lambda d: d.__setitem__(_key(host_name, model), row))


def forget(home, host_name: str, model: str) -> None:
    if not model or home is None:
        return
    _change(home, lambda d: d.pop(_key(host_name, model), None))


def rows(home) -> list:
    out = []
    for k, v in read(home).items():
        host, _, model = k.partition("|")
        out.append({"host": host, "model": model, **{f: v.get(f) for f in ("at", "by", "op", "keep_alive")}})
    return sorted(out, key=lambda r: -float(r.get("at") or 0))


def held_for(table: list, host_name: str, model: Optional[str], min_s: float, *, now: Optional[float] = None) -> float:
    """The seconds `model` still stays resident by the shared clock (`table`: the host's `rows`)."""
    if not model:
        return 0.0
    want = _key(host_name, model)
    now = time.time() if now is None else now
    for r in table or []:
        if isinstance(r, dict) and _key(r.get("host") or "", r.get("model") or "") == want \
                and isinstance(r.get("at"), (int, float)):
            return max(0.0, float(min_s) - (now - float(r["at"])))
    return 0.0


def claims(home, now: Optional[float] = None) -> list:
    from halo_harness.local_sched.claims_file import host_file, read as read_claims
    return read_claims(host_file(home), now=now)
