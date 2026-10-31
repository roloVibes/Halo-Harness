"""halo_harness.fleet.hub_hosts -- the hub's half of `halo host` (Halo 3.3.7.0 R1; docs/FLEET.md "The hub knows hosts").

A host this machine's member runs announces itself to every hub that machine joined (host/service.forward_tick):

    POST /fleet/v1/host {v, link, host: true, port, fingerprint, url, name, serves: [{name, port, addr}]}
      200 {v, ok, known}           signed with the member's pair key (the hub's 120 s window, the replay guard)

The hub keeps the newest announce per member in memory (`HOSTS[str(home)]`, gone when the hub stops), and its merged
view (`hub_state.view()["hosts"]`) lists them, so a hub-side Studio can find each host: `[{member, harness, addr,
port, url, fingerprint, serves, at, fresh}]` (`fresh`: announced within FRESH_S). Nothing here contacts the host.
"""

from __future__ import annotations

import threading
import time

from halo_harness.fleet import protocol

FRESH_S = 180.0
HOSTS: dict = {}  # str(hub home) -> {harness id: row}
_LOCK = threading.Lock()


def _clean(v, n: int = 128) -> str:
    return " ".join(str(v or "").split())[:n]


def record(home, hid: str, member_name: str, ip: str, body: dict, now: float = None) -> dict:
    serves = []
    for r in (body.get("serves") or [])[:16]:
        if isinstance(r, dict):
            try:
                serves.append({"name": _clean(r.get("name"), 64), "port": int(r.get("port") or 11434),
                               "addr": _clean(r.get("addr"), 64) or ip})
            except (TypeError, ValueError):
                continue
    try:
        port = int(body.get("port") or 0)
    except (TypeError, ValueError):
        port = 0
    row = {"member": member_name, "harness": hid, "addr": ip, "port": port, "url": _clean(body.get("url"), 200),
           "fingerprint": _clean(body.get("fingerprint"), 80) or None, "name": _clean(body.get("name"), 64),
           "serves": serves, "at": time.time() if now is None else now}
    with _LOCK:
        HOSTS.setdefault(str(home), {})[hid] = row
    return row


def listing(home, now: float = None) -> list:
    now = time.time() if now is None else now
    with _LOCK:
        rows = list((HOSTS.get(str(home)) or {}).values())
    return sorted(({**r, "fresh": now - r["at"] <= FRESH_S} for r in rows), key=lambda r: r["member"].lower())


def serve(handler):
    """`POST /fleet/v1/host` on the hub port (a member's signed request)."""
    try:
        raw = handler._raw_body()
    except ValueError as e:
        return handler._json(413, {"error": str(e)})
    hid = handler._signed(raw)
    if not hid:
        return None
    try:
        body = protocol.decode(raw)
    except ValueError as e:
        return handler._json(400, {"error": f"bad request: {e}"})
    member = handler.hub.state.members.get(hid)
    if member is None or body.get("host") is not True:
        return handler._json(400 if member is not None else 403, {"error": "a host announce is {host: true, port, ...}"
                                                                   if member is not None else "not a member of this hub"})
    record(handler.hub.home, hid, member.name, handler.client_address[0], body)
    return handler._json(200, protocol.doc(ok=True, known=len(listing(handler.hub.home))))
