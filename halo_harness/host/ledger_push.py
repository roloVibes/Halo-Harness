"""halo_harness.host.ledger_push -- a peer's calls to a host-served Ollama reach that host (Halo 3.3.7.0 R2; the host's
side is host/ledger_take.py).

`push_all(home)` sends, to every paired `halo host` (fleet.json's `hosts`), the new lines of this machine's ledger
whose server that host serves (an entry's `serves` [{addr, port}]): one signed `POST /host/v1/ledger {lines}` every
FLUSH_S (30 s) or as soon as BATCH_LINES wait. A cursor per host (`<state>/ollama/share-host-<id>.json`, the hub
forwarder's own shape) survives restarts; several processes take turns through its lock, so a line goes once. The
host's answer carries its profiles keyed by this machine's own host names, kept with `by: "hub"`
(fleet/ollama_share_take.take_profiles). The steward job runs it on each tick (ollama_steward/host_fold.py).
"""

from __future__ import annotations

import json
import time
from typing import Optional

from halo_harness.fleet.ollama_share import BATCH_LINES, FLUSH_S, MAX_LINES, Forwarder

_PUSHERS: dict = {}  # (str(home), host url) -> HostPush


class HostPush(Forwarder):
    def __init__(self, entry: dict, home=None) -> None:
        super().__init__({"hub_id": "host-" + str(entry.get("host_id") or entry.get("url"))[:40]}, home)
        self.entry = entry
        self.last_flush = 0.0  # the first pass sends what waits

    def serves(self, line: dict) -> bool:
        from halo_harness.fleet import identity
        from halo_harness.ollama_steward.host_client import _addr_port, _matches
        if not isinstance(line, dict) or line.get("from") not in (None, "", identity.fleet_name()):
            return False  # a line this machine took in from another is never sent on
        addr, port = _addr_port(str((line.get("host") or {}).get("url") or ""))
        return bool(addr) and _matches(self.entry, addr, port)

    def tick(self, client, force: bool = False) -> int:  # type: ignore[override]
        """Send what is due to this host; returns how many lines went. Never raises."""
        from halo_harness.fleet.ollama_share_take import take_profiles
        from halo_harness.filelock import file_lock
        try:
            current, _rotated, cpath = self._paths()
            now = time.monotonic()
            due = force or now - self.last_flush >= FLUSH_S
            if not current.exists():
                return 0
            with file_lock(cpath, timeout=0) as held:
                if not held:
                    return 0
                rows, cursor = self.pending()
                send = [x for x, _c in rows if self.serves(x)]
                if not due and len(send) < BATCH_LINES:
                    return 0
                if len(send) > MAX_LINES:
                    send = send[:MAX_LINES]
                    cursor = next(c for x, c in rows if x is send[-1])
                if send:
                    take_profiles(client.push_ledger(send))
                cpath.parent.mkdir(parents=True, exist_ok=True)
                cpath.write_text(json.dumps(cursor), encoding="utf-8")
                self.last_flush = now
                return len(send)
        except Exception:
            self.last_flush = time.monotonic()  # a host that cannot take them now is tried again next period
            return 0


def push_all(home=None, *, force: bool = False) -> int:
    from halo_harness.fleet import identity, store
    from halo_harness.ollama_steward.host_client import HostClient, _usable, any_paired
    if not any_paired(home) or identity.offline():
        return 0
    home = home if home is not None else identity.home()
    sent = 0
    for e in store.hosts(home):
        if e.get("state", "joined") != "joined":
            continue
        key = store.key_for(e, home)
        if key is None:
            continue
        c = HostClient(e, key, identity.harness(home)["id"])
        if not _usable(c):
            continue
        p = _PUSHERS.get((str(home), e["url"]))
        if p is None:
            p = _PUSHERS[(str(home), e["url"])] = HostPush(e, home)
        sent += p.tick(c, force=force)
    return sent


def reset(home: Optional[object] = None) -> None:
    for k in [k for k in _PUSHERS if home is None or k[0] == str(home)]:
        _PUSHERS.pop(k, None)
