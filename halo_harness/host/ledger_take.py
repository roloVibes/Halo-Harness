"""halo_harness.host.ledger_take -- a peer's calls reach the host's ledger (Halo 3.3.7.0 R2; host/ledger_push.py is the
peer's side).

    POST /host/v1/ledger {v, lines: [ledger line]}   (the `view` grant)
      200 {v, ok, accepted, profiles}

The lines are a peer's calls to an Ollama server this host serves; they land in the host's own ledger with `from` =
the peer's name (fleet/ollama_share.accept, the hub's own take), so the host's rules, its `GET findings`, the verify
window of a fix (host/verify.py) and the bench's busy wait see every client's calls, not only this machine's. The
answer carries the host's profiles keyed by the peer's own host names (profiles.payload_for_member), which the peer
keeps with `by: "hub"` (never over its own `by: "user"` entry): a fix the host keeps reaches the peer's next call; one
it reverts goes with it.
"""

from __future__ import annotations

from halo_harness.fleet import protocol

MAX_LINES = 500


def take(svc, raw: bytes, hid: str, who: str) -> "tuple[int, dict]":
    from halo_harness.fleet.ollama_share import accept
    from halo_harness.ollama_steward.profiles import payload_for_member
    try:
        body = protocol.decode(raw) if raw else {}
    except ValueError as e:
        return 400, {"error": f"bad request: {e}"}
    rec = svc.pairing.member(hid) or {}
    name = str(rec.get("name") or who or hid[:8])
    lines = [x for x in (body.get("lines") or [])[:MAX_LINES] if isinstance(x, dict)]
    n = accept(svc.home, name, lines) if lines else 0
    try:
        profiles = payload_for_member(svc.home, name)
    except Exception:
        profiles = {}
    return 200, protocol.doc(ok=True, accepted=n, profiles=profiles)
