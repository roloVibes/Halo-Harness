"""halo_harness.fleet.hub_join -- the hub's half of `halo fleet join` (Halo
3.0.5.0 "Fleet" round R2; the exchange is described in pair_kex.py).

    POST /fleet/v1/join {v, harness: {id, name, host, user, version, os}, share, allow_control,
                         a, ts, nonce, mac}
      200 {v, ok, hub: {id, name, version, tls, fingerprint}, member_name, b, mac}
      403 the code was not accepted (wrong, already used or expired)
      400 a malformed request; 409 the hub's own harness; 429 too many wrong codes from that address

The code that matches is spent; the new member's record and pair key go
into members.json and a `fleet` frame `{action: join}` goes to Studio.
"""

from __future__ import annotations

import hmac
import re
import threading
import time

from halo_harness.fleet import pair_kex, protocol
from halo_harness.fleet.identity import CONTROL_LEVELS, SHARE_LEVELS

FAILS_PER_MIN = 5
_ID = re.compile(r"[0-9a-f]{16,64}")


class JoinGate:
    """Wrong codes per peer address: FAILS_PER_MIN a minute, then 429."""

    def __init__(self) -> None:
        self._fails: dict = {}
        self._lock = threading.Lock()

    def blocked(self, ip: str, now: float) -> bool:
        with self._lock:
            recent = [t for t in self._fails.get(ip, []) if now - t < 60]
            self._fails[ip] = recent
            return len(recent) >= FAILS_PER_MIN

    def fail(self, ip: str, now: float) -> None:
        with self._lock:
            self._fails.setdefault(ip, []).append(now)


def _clean(value, n: int = 64) -> str:
    return " ".join(str(value or "").split())[:n]


def handle_join(state, body: dict, peer_ip: str, gate: JoinGate):
    now = time.time()
    if gate.blocked(peer_ip, now):
        return 429, {"error": "too many wrong pairing codes from this address; wait a minute"}
    h = body.get("harness") if isinstance(body.get("harness"), dict) else {}
    hid = str(h.get("id") or "")
    a, ts, nonce, mac = (str(body.get(k) or "") for k in ("a", "ts", "nonce", "mac"))
    if not _ID.fullmatch(hid) or not (a and ts and nonce and mac):
        return 400, {"error": "a join needs harness.id, a, ts, nonce and mac"}
    try:
        pair_kex.check_public(a)
        stale = abs(now - float(ts)) > protocol.WINDOW_S
    except ValueError as e:
        return 400, {"error": str(e)}
    if stale:
        return 400, {"error": "the join request's clock is more than two minutes off the hub's"}
    if hid == state.identity.get("id"):
        return 409, {"error": "that is this hub's own harness; it is already a member of its own hub"}

    def matches(ckey: bytes) -> bool:
        return hmac.compare_digest(mac.lower(), pair_kex.mac(ckey, "join", hid, a, ts, nonce))

    ckey = state.pairing.take_code(matches)
    if ckey is None:
        gate.fail(peer_ip, now)
        return 403, {"error": "that pairing code was not accepted (wrong, already used or expired); "
                              "run `halo fleet pair` on the hub for a new one"}
    b_secret, b = pair_kex.keypair()
    key = pair_kex.pair_key(b_secret, a, ckey, a, b)
    record = {"id": hid, "name": _clean(h.get("name")) or hid[:8], "host": _clean(h.get("host")),
              "user": _clean(h.get("user")), "version": _clean(h.get("version"), 32), "os": _clean(h.get("os"), 16),
              "share": body.get("share") if body.get("share") in SHARE_LEVELS else None,
              "allow_control": body.get("allow_control") if body.get("allow_control") in CONTROL_LEVELS else None,
              "address": peer_ip}
    state.pairing.add_member(record, key)
    state.reload(force=True)
    hub = state.hub_public()
    fp = str(hub.get("fingerprint") or "")
    return 200, protocol.doc(ok=True, hub=hub, member_name=record["name"], b=b,
                             mac=pair_kex.mac(ckey, "joined", a, b, hub.get("id"), fp))
