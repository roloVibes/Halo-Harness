"""halo_harness.fleet.relay_runtime -- the relay of a joined harness (Halo
3.0.5.0 "Fleet" round R2).

remote/runtime.py calls `session_opened(act)` when a session of this process
opens its control socket and `session_closed(act)` when it closes (also on
`/private on`). When `~/.halo/fleet.json` lists a joined hub (a watcher
notices a later `halo fleet join` within WATCH_S), one daemon thread per hub
(`HubRelay`) announces this process's sessions with their agent trees,
forwards each session's feed as far as that hub's share level allows
(protocol.scrub_frame), reads the hub's signed command stream and hands each
command to control.py on a worker thread. It reconnects with backoff (1 s
doubling to 60 s); everything network-bound runs on these threads, so a hub
that is down never slows a session. Offline mode stops it; a kick (or a
`halo fleet leave`) ends it.
"""

from __future__ import annotations

import threading
import time

from halo_harness.fleet import identity, store
from halo_harness.fleet.relay_hub import HubRelay

WATCH_S = 5.0
_lock = threading.RLock()
_relays: dict = {}
_sessions: list = []
_watcher: list = []


def actives() -> list:
    with _lock:
        return list(_sessions)


def relays() -> list:
    with _lock:
        return list(_relays.values())


def session_opened(act) -> None:
    """A session of this process opened its socket: start (or wake) the relays."""
    try:
        with _lock:
            if act not in _sessions:
                _sessions.append(act)
        _sync()
        _watch()
    except Exception:
        pass


def session_closed(act) -> None:
    with _lock:
        if act in _sessions:
            _sessions.remove(act)
    poke()


def poke() -> None:
    """Announce now (a session opened or closed, a share level changed)."""
    for r in relays():
        r.poke()


def stop_all() -> None:
    with _lock:
        rs = list(_relays.values())
        _relays.clear()
    for r in rs:
        r.stop()


def _sync() -> None:
    if identity.offline() or not store.has_hubs():
        return
    with _lock:
        for entry in store.hubs():
            if entry.get("state", "joined") != "joined":
                continue
            key = entry.get("hub_id") or entry.get("url")
            r = _relays.get(key)
            if r is None or not r.is_alive():
                r = _relays[key] = HubRelay(entry, actives)
                r.start()
            else:
                r.poke()


def _watch() -> None:
    with _lock:
        if _watcher and _watcher[0].is_alive():
            return

        def loop() -> None:
            seen = store.mtime()
            while actives():
                time.sleep(WATCH_S)
                now = store.mtime()
                if now != seen:
                    seen = now
                    _sync()
        t = threading.Thread(target=loop, daemon=True, name="halo-fleet-watch")
        _watcher[:] = [t]
        t.start()
