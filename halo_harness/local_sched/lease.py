"""halo_harness.local_sched.lease -- the heartbeat that renews this process's leased claims (Halo 3.3.8.0 R3;
local_sched/claims_file.py has the `until` field).

A claim with a lease ends on its own when nobody renews it: the pool's claim on every member (local_pool/claims.py)
and a bundle's claim held by a halo process (Studio's tick: local_sched/reserve_act.py) are renewed here, every
`lease_s / 3` seconds while this process lives. A killed Studio renews nothing more, so its claims expire within the
lease (pool.claim_lease_s, 120 s) on the host and in the local file alike; a claim from the CLI has no lease.

    hold(key, renew)      renew: fn(until) -> [line] (renew every row of that holder: the local file, each host)
    release(key)          stop renewing it (the holder released its claims itself)
    beat(now=None) -> {key: [line]}      one renewal pass (the tests call it; the thread calls it)
    held() -> [key]        running() -> bool
The thread is a daemon started on the first hold; nothing here loads or unloads a model.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

_HELD: dict = {}
_LOCK = threading.Lock()
_THREAD: list = []
_LAST: dict = {}


def hold(key: str, renew: Callable) -> None:
    with _LOCK:
        _HELD[key] = renew
    _start()


def release(key: str) -> None:
    with _LOCK:
        _HELD.pop(key, None)
        _LAST.pop(key, None)


def held() -> list:
    with _LOCK:
        return sorted(_HELD)


def last(key: str) -> dict:
    return dict(_LAST.get(key) or {})


def beat(now: Optional[float] = None) -> dict:
    from halo_harness.local_sched.claims_file import lease_s
    now = time.time() if now is None else now
    until = round(now + lease_s(), 3)
    with _LOCK:
        items = list(_HELD.items())
    out = {}
    for key, fn in items:
        try:
            lines = list(fn(until) or [])
        except Exception as e:  # one holder's failed renewal never stops the others
            lines = [f"{key}: the renewal did not land ({type(e).__name__}: {str(e)[:120]})"]
        out[key] = lines
        _LAST[key] = {"at": now, "until": until, "lines": lines}
    return out


def running() -> bool:
    return bool(_THREAD) and _THREAD[0].is_alive()


def _loop() -> None:
    from halo_harness.local_sched.claims_file import lease_s
    while True:
        time.sleep(max(1.0, lease_s() / 3.0))
        if not held():
            continue
        beat()


def _start() -> None:
    if running():
        return
    t = threading.Thread(target=_loop, name="halo-claim-lease", daemon=True)
    _THREAD[:] = [t]
    t.start()


def reset() -> None:
    """Tests: forget every holder (the thread finds nothing to renew)."""
    with _LOCK:
        _HELD.clear()
        _LAST.clear()
