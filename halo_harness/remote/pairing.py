"""halo_harness.remote.pairing -- who may drive Halo from Signal (Halo 2.0.9
round 3). Identity is the sender's ACI (`sourceUuid`), never a phone number.

The contact-request flow (SIGNAL-RESEARCH.md section 8, shape B), with
signal-cli running `--trust-new-identities never`:

1. An unknown sender's envelope (including the untrusted-identity
   notification) is NEVER answered. `note_contact()` records a request
   `{aci, number, safety_number, first_seen}`; `pending()` lists them for
   `/remote` and `halo remote signal pair`.
2. The owner compares the safety number on the phone and calls
   `approve(aci)`: a 6-digit one-time code (10-minute expiry) is generated
   and returned for display, and `trust` runs with the safety number as
   `verifiedSafetyNumber` (right away when a transport is attached; otherwise
   queued in pending.json and run by the bridge's next `service()` tick).
3. The phone's next message must be exactly that code. `redeem()` writes the
   peer (a fresh signing secret included) and returns the secret to the
   bridge, which tells the phone only "Paired."; the phrase and link are shown on
   the computer (`halo remote signal pair`, the /remote dialog). Three wrong codes (a wrong six-digit
   message; other chatter is not a guess), or expiry, drop the request.

A changed safety number (`block()`, from the receive-side notification or a
`-4` on send) marks the peer `blocked_until_reverified` and adds a notice;
`reverify()` repeats the trust step with the confirmed number. State files
(0600, directory 0700): `peers.json` and `pending.json` under `<state>/remote/`.
The one-time code is stored only as a salted hash.
"""

from __future__ import annotations

import hmac
import secrets
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.remote import signing
from halo_harness.remote.pairing_files import (CODE_DIGITS, CODE_TTL_S, MAX_ATTEMPTS, MAX_NOTICES, MAX_PENDING,
                                               Approval, PairingError, Redeem, _digits, _edit, _hash, _read)
from halo_harness.remote.signal_config import remote_dir
from halo_harness.remote.signal_errors import SignalError, UserFailure


class Pairing:
    def __init__(self, *, directory=None, transport=None, clock: Callable[[], float] = time.time,
                 ttl: int = CODE_TTL_S, trust_needed: bool = True) -> None:
        self.dir = Path(directory) if directory else remote_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.peers_path = self.dir / "peers.json"
        self.pending_path = self.dir / "pending.json"
        self.transport, self.clock, self.ttl = transport, clock, ttl
        self.trust_needed = trust_needed  # False in Note-to-Self mode (nothing to trust)
        self._mu = threading.RLock()

    def peers(self) -> dict:
        return dict(_read(self.peers_path, {}).get("peers", {}))

    def peer(self, aci: str) -> Optional[dict]:
        return self.peers().get(aci)

    def is_paired(self, aci: str) -> bool:
        return aci in self.peers()

    def _edit_peers(self):
        return _edit(self.peers_path, {"version": 1, "peers": {}})

    def advance_counter(self, aci: str, counter: int) -> None:
        with self._mu, self._edit_peers() as d:
            p = d.setdefault("peers", {}).get(aci)
            if p is not None:
                p["signing"]["counter"] = max(int(p["signing"].get("counter", 0)), int(counter))

    def set_signed(self, aci: str, signed: bool) -> bool:
        with self._mu, self._edit_peers() as d:
            p = d.setdefault("peers", {}).get(aci)
            if p is not None:
                p["signed"] = bool(signed)
            return p is not None

    def unpair(self, aci: str) -> bool:
        with self._mu:
            with self._edit_peers() as d:
                gone = d.setdefault("peers", {}).pop(aci, None) is not None
            with self._pending_edit() as q:
                q.setdefault("requests", {}).pop(aci, None)
        return gone

    def _pending_edit(self):
        return _edit(self.pending_path, {"version": 1, "requests": {}, "ops": [], "notices": []})

    def add_notice(self, kind: str, aci: str, text: str) -> None:
        with self._mu, self._pending_edit() as q:
            notices = q.setdefault("notices", [])
            notices.append({"ts": self.clock(), "kind": kind, "aci": aci, "text": text})
            del notices[:-MAX_NOTICES]

    def notices(self) -> list:
        return list(_read(self.pending_path, {}).get("notices", []))

    def clear_notices(self) -> None:
        with self._mu, self._pending_edit() as q:
            q["notices"] = []

    def pending(self) -> list:
        """Open contact requests, oldest first, without the code hash."""
        now = self.clock()
        out = []
        for r in _read(self.pending_path, {}).get("requests", {}).values():
            if r.get("state") == "approved" and r.get("expires", 0) < now:
                continue
            out.append({k: v for k, v in r.items() if k not in ("code_hash", "salt")})
        return sorted(out, key=lambda r: r.get("first_seen", 0))

    def note_contact(self, aci: str, number=None, safety_number: Optional[str] = None) -> dict:
        with self._mu, self._pending_edit() as q:
            reqs = q.setdefault("requests", {})
            r = reqs.get(aci)
            if r is None:
                if len(reqs) >= MAX_PENDING:  # throwaway accounts must not block new pairings forever
                    stale = sorted((x for x in reqs.values() if x.get("state") != "approved"),
                                   key=lambda x: x.get("first_seen", 0))
                    if not stale:
                        return {"aci": aci, "state": "ignored"}
                    reqs.pop(stale[0]["aci"], None)
                    q["ops"] = [o for o in q.get("ops", []) if o.get("aci") != stale[0]["aci"]]
                r = reqs[aci] = {"aci": aci, "number": number, "safety_number": safety_number,
                                 "first_seen": self.clock(), "state": "pending", "attempts": 0}
            r["number"] = r.get("number") or number
            r["safety_number"] = safety_number or r.get("safety_number")
            return dict(r)

    def _drop_request(self, aci: str) -> None:
        with self._pending_edit() as q:
            q.setdefault("requests", {}).pop(aci, None)
            q["ops"] = [o for o in q.get("ops", []) if o.get("aci") != aci]

    def approve(self, aci: str) -> Approval:
        with self._mu:
            req = next((r for r in self.pending() if r["aci"] == aci), None)
            if req is None:
                raise PairingError("no contact request from that sender")
            sn = req.get("safety_number")
            if self.trust_needed and not sn and self.transport is not None:
                sn = self.transport.safety_number(aci)
            if self.trust_needed and not sn:
                raise PairingError("no safety number is known for that sender yet")
            code, salt = f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}", secrets.token_hex(8)
            expires = self.clock() + self.ttl
            with self._pending_edit() as q:
                r = q["requests"][aci]
                r.update(state="approved", salt=salt, code_hash=_hash(code, salt), expires=expires, attempts=0,
                         safety_number=sn, trusted=not self.trust_needed)
                if self.trust_needed:
                    q.setdefault("ops", []).append({"op": "trust", "kind": "approve", "aci": aci, "safety_number": sn})
            self.service()
            now_req = next((r for r in self.pending() if r["aci"] == aci), {})
            return Approval(code, expires, bool(now_req.get("trusted")))

    def reverify(self, aci: str, safety_number: Optional[str] = None) -> bool:
        """Trust the (confirmed) current key of a blocked peer; True once done."""
        with self._mu:
            p = self.peer(aci)
            if p is None:
                raise PairingError("that sender is not paired")
            sn = safety_number or p.get("pending_safety_number")
            if not sn and self.transport is not None:
                sn = self.transport.safety_number(aci)
            if not sn:
                raise PairingError("no safety number is known for that peer yet")
            with self._pending_edit() as q:
                q.setdefault("ops", []).append({"op": "trust", "kind": "reverify", "aci": aci, "safety_number": sn})
            self.service()
            return not self.peer(aci).get("blocked_until_reverified")

    def service(self, transport=None) -> list:
        """Run the queued `trust` steps. Returns the ops that finished."""
        tr = transport or self.transport
        done: list = []
        if tr is None:
            return done
        with self._mu:
            ops = list(_read(self.pending_path, {}).get("ops", []))
            for op in ops:
                try:
                    tr.trust(op["aci"], _digits(op["safety_number"]))
                except UserFailure as e:
                    self._finish(op, ok=False, why=e.message or "trust refused")
                except SignalError:
                    continue  # network trouble: keep it queued, try on the next tick
                else:
                    self._finish(op, ok=True)
                done.append(op)
        return done

    def _finish(self, op: dict, *, ok: bool, why: str = "") -> None:
        aci = op["aci"]
        with self._pending_edit() as q:
            q["ops"] = [o for o in q.get("ops", []) if o is not op and o != op]
            r = q.setdefault("requests", {}).get(aci)
            if op["kind"] == "approve" and r is not None:
                if ok:
                    r["trusted"] = True
                else:
                    r.update(state="pending", code_hash=None, trusted=False)
        if op["kind"] == "reverify":
            with self._edit_peers() as d:
                p = d.setdefault("peers", {}).get(aci)
                if p is not None and ok:
                    p.update(safety_number=op["safety_number"], blocked_until_reverified=False,
                             pending_safety_number=None)
        if not ok:
            self.add_notice("trust_failed", aci, f"trust step failed: {why}")

    def redeem(self, aci: str, text: str, number=None) -> Redeem:
        with self._mu:
            req = next((r for r in _read(self.pending_path, {}).get("requests", {}).values()
                        if r.get("aci") == aci), None)
            if req is None or req.get("state") != "approved" or not req.get("trusted"):
                return Redeem("ignored", None, b"")
            if req.get("expires", 0) < self.clock():
                self._drop_request(aci)
                self.add_notice("code_expired", aci, "pairing code expired; the contact request was dropped")
                return Redeem("expired", None, b"")
            given = (text or "").strip()
            if not (len(given) == CODE_DIGITS and given.isdigit()):
                return Redeem("ignored", None, b"")  # chatter (or a message redelivered after trust) is not a guess
            if not hmac.compare_digest(_hash(given, req["salt"]), req["code_hash"]):
                attempts = int(req.get("attempts", 0)) + 1
                if attempts >= MAX_ATTEMPTS:
                    self._drop_request(aci)
                    self.add_notice("code_failed", aci, f"{MAX_ATTEMPTS} wrong pairing codes; request dropped")
                    return Redeem("dropped", None, b"")
                with self._pending_edit() as q:
                    q["requests"][aci]["attempts"] = attempts
                return Redeem("wrong", None, b"")
            secret = signing.new_secret()
            peer = {"aci": aci, "number": number or req.get("number"), "safety_number": req.get("safety_number"),
                    "paired_at": self.clock(), "signing": {"secret_hex": secret.hex(), "counter": 0},
                    "signed": True, "blocked_until_reverified": False, "pending_safety_number": None}
            with self._edit_peers() as d:
                d.setdefault("peers", {})[aci] = peer
            self._drop_request(aci)
            return Redeem("paired", peer, secret)

    def block(self, aci: str, new_safety_number: Optional[str] = None) -> bool:
        with self._mu:
            with self._edit_peers() as d:
                p = d.setdefault("peers", {}).get(aci)
                if p is None:
                    return False
                p["blocked_until_reverified"] = True
                p["pending_safety_number"] = new_safety_number or p.get("pending_safety_number")
            self.add_notice("identity_changed", aci,
                            "the safety number changed; commands are refused until `reverify` confirms the new one")
            return True
