"""halo_signal.pairing -- who may talk to Halo from Signal (Halo 2.0.9 round 3; 3.3.13.0 R3: pairing in one message).
Identity is the sender's ACI (`sourceUuid`), never a phone number.

Pairing: the owner runs `/signal pair` (or Setup's "Pair a phone"): `invite()` makes a six-word phrase from the 256
signing words, good for `pair_ttl_s` (600 s), shown on the computer as text and as a QR code; only a salted hash is
stored (invites.json). The phone texts the phrase to Halo's number (or, with a linked account, to Note to Self) and
`redeem()` pairs it: `signed: false` -- the Signal session is the channel's authentication; `/signal sign on <phone>`
adds the per-command signature (signing.py). One invite is open at a time; a new one replaces it.

With a dedicated number signal-cli runs `--trust-new-identities never`: a new phone's first message arrives as the
untrusted-identity notification. While an invite is open, `note_untrusted()` queues the trust of that sender's
current key (its safety number is kept and shown on the computer), signal-cli then hands over the held message, and
that message must be the phrase. Without an open invite an unknown sender is never answered (one notice a day per
sender). Six words from the list that are not the phrase are a wrong guess; three wrong guesses close the invite.
Other chatter is not a guess.

A changed safety number of a paired phone (`block()`) marks it `blocked_until_reverified`; `reverify()` trusts the
confirmed new key. Files (0600): peers.json, invites.json, pending.json (queued trust steps and notices).
"""

from __future__ import annotations

import hmac
import json
import re
import secrets
import threading
import time
from hashlib import sha256
from pathlib import Path
from typing import Callable, NamedTuple, Optional

from halo_signal import files, signing

WORDS_IN_PHRASE = 6
MAX_ATTEMPTS = 3
MAX_NOTICES = 20
STRANGER_NOTICE_S = 86400.0


class Redeem(NamedTuple):
    status: str            # ignored | wrong | dropped | expired | paired
    peer: Optional[dict]


class PairingError(Exception):
    pass


def normalize(text: str) -> str:
    return " ".join(w for w in re.split(r"[\s,.;:_/-]+", (text or "").lower()) if w)


def _hash(phrase: str, salt: str) -> str:
    return sha256(f"{salt}|{normalize(phrase)}".encode("utf-8")).hexdigest()


class Pairing:
    def __init__(self, *, directory=None, transport=None, clock: Callable[[], float] = time.time,
                 ttl: int = 600, trust_needed: bool = True) -> None:
        self.dir = Path(directory) if directory else files.home()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.peers_path, self.invites_path = self.dir / "peers.json", self.dir / "invites.json"
        self.pending_path = self.dir / "pending.json"
        self.transport, self.clock, self.ttl = transport, clock, ttl
        self.trust_needed = trust_needed  # False with a linked account (Note to Self: nothing to trust)
        self._mu = threading.RLock()
        self._retry: dict = {}

    # ---- peers ---------------------------------------------------------------------------
    def peers(self) -> dict:
        return dict(files.read_json(self.peers_path).get("peers", {}))

    def peer(self, aci: str) -> Optional[dict]:
        return self.peers().get(aci)

    def is_paired(self, aci: str) -> bool:
        return aci in self.peers()

    def _edit_peers(self):
        return files.edit_json(self.peers_path, {"version": 1, "peers": {}})

    def advance_counter(self, aci: str, counter: int) -> None:
        with self._mu, self._edit_peers() as d:
            p = d.setdefault("peers", {}).get(aci)
            if p is not None and isinstance(p.get("signing"), dict):
                p["signing"]["counter"] = max(int(p["signing"].get("counter", 0)), int(counter))

    def set_signed(self, aci: str, signed: bool) -> Optional[bytes]:
        """Turn signing on (a fresh secret, returned once for the computer to show) or off; None when not paired."""
        secret = signing.new_secret() if signed else None
        with self._mu, self._edit_peers() as d:
            p = d.setdefault("peers", {}).get(aci)
            if p is None:
                return None
            p["signed"] = bool(signed)
            if secret is not None:
                p["signing"] = {"secret_hex": secret.hex(), "counter": 0}
        return secret if signed else b""

    def unpair(self, aci: str) -> bool:
        with self._mu, self._edit_peers() as d:
            return d.setdefault("peers", {}).pop(aci, None) is not None

    # ---- notices ---------------------------------------------------------------------------
    def _pending_edit(self):
        return files.edit_json(self.pending_path, {"version": 2, "ops": [], "notices": [], "strangers": {}})

    def add_notice(self, kind: str, aci: str, text: str) -> None:
        with self._mu, self._pending_edit() as q:
            notices = q.setdefault("notices", [])
            notices.append({"ts": self.clock(), "kind": kind, "aci": aci, "text": text})
            del notices[:-MAX_NOTICES]

    def notices(self) -> list:
        return list(files.read_json(self.pending_path).get("notices", []))

    def clear_notices(self) -> None:
        with self._mu, self._pending_edit() as q:
            q["notices"] = []

    def note_stranger(self, aci: str, number) -> None:
        """An unknown sender with no invite open: never answered; one notice a day per sender."""
        with self._mu, self._pending_edit() as q:
            seen = q.setdefault("strangers", {})
            if self.clock() - float(seen.get(aci) or 0) < STRANGER_NOTICE_S:
                return
            seen[aci] = self.clock()
        self.add_notice("stranger", aci, "a number you have not paired texted Halo (no pairing phrase was open); "
                        "it was not answered -- /signal pair opens one")

    # ---- the invite ------------------------------------------------------------------------
    def invite(self) -> dict:
        """A new phrase (the only time it exists in the clear): {phrase, expires}."""
        phrase = " ".join(secrets.choice(signing.WORDS) for _ in range(WORDS_IN_PHRASE))
        salt = secrets.token_hex(8)
        row = {"salt": salt, "hash": _hash(phrase, salt), "created": self.clock(), "expires": self.clock() + self.ttl,
               "attempts": 0, "state": "waiting"}
        with self._mu:
            files.write_text(self.invites_path, json.dumps({"version": 1, "invite": row}, indent=2))
        return {"phrase": phrase, "expires": row["expires"]}

    def invite_state(self) -> dict:
        """{state: none | waiting | expired | closed | paired, expires, paired: {aci, number}} -- for the live view."""
        row = files.read_json(self.invites_path).get("invite") or {}
        if not row:
            return {"state": "none"}
        state = row.get("state") or "waiting"
        if state == "waiting" and float(row.get("expires") or 0) < self.clock():
            state = "expired"
        return {"state": state, "expires": row.get("expires"), "paired": row.get("paired"), "why": row.get("why")}

    def _close(self, state: str, **extra) -> None:
        with self._mu, files.edit_json(self.invites_path, {"version": 1, "invite": {}}) as d:
            if d.get("invite"):
                d["invite"].update(state=state, **extra)

    def open_invite(self) -> bool:
        return self.invite_state()["state"] == "waiting"

    def note_untrusted(self, aci: str, number, safety_number: Optional[str]) -> bool:
        """A new phone's first message (untrusted identity) while an invite is open: queue the trust of its key."""
        if not self.open_invite() or not self.trust_needed:
            return False
        sn = safety_number or (self.transport.safety_number(aci) if self.transport is not None else None)
        if not sn:
            return False
        with self._mu, self._pending_edit() as q:
            ops = q.setdefault("ops", [])
            if not any(o.get("aci") == aci for o in ops):
                ops.append({"op": "trust", "kind": "invite", "aci": aci, "safety_number": sn, "number": number})
        self.service()
        return True

    def redeem(self, aci: str, text: str, number=None) -> Redeem:
        with self._mu:
            row = files.read_json(self.invites_path).get("invite") or {}
            if not row or row.get("state") not in (None, "waiting"):
                return Redeem("ignored", None)
            words = normalize(text).split()
            if len(words) != WORDS_IN_PHRASE or not all(w in signing.WORDS for w in words):
                return Redeem("ignored", None)  # chatter, not a guess
            if float(row.get("expires") or 0) < self.clock():
                self._close("expired")
                self.add_notice("phrase_expired", aci, "the pairing phrase had expired; /signal pair makes a new one")
                return Redeem("expired", None)
            if not hmac.compare_digest(_hash(text, row["salt"]), row["hash"]):
                attempts = int(row.get("attempts", 0)) + 1
                with files.edit_json(self.invites_path, {"version": 1, "invite": {}}) as d:
                    d["invite"]["attempts"] = attempts
                if attempts >= MAX_ATTEMPTS:
                    self._close("closed", why=f"{MAX_ATTEMPTS} wrong phrases")
                    self.add_notice("phrase_failed", aci, f"{MAX_ATTEMPTS} wrong pairing phrases; the invite is closed")
                    return Redeem("dropped", None)
                return Redeem("wrong", None)
            sn = None
            for op in files.read_json(self.pending_path).get("ops", []) + self._done_ops():
                if op.get("aci") == aci:
                    sn = op.get("safety_number")
            peer = {"aci": aci, "number": number, "safety_number": sn, "paired_at": self.clock(), "signed": False,
                    "blocked_until_reverified": False, "pending_safety_number": None}
            with self._edit_peers() as d:
                d.setdefault("peers", {})[aci] = peer
            self._close("paired", paired={"aci": aci[:8], "number": mask(number)})
            return Redeem("paired", peer)

    def _done_ops(self) -> list:
        return list(files.read_json(self.pending_path).get("trusted", []))

    # ---- trust steps ---------------------------------------------------------------------------
    def block(self, aci: str, new_safety_number: Optional[str] = None) -> bool:
        with self._mu:
            with self._edit_peers() as d:
                p = d.setdefault("peers", {}).get(aci)
                if p is None:
                    return False
                was = p.get("blocked_until_reverified"), p.get("pending_safety_number")
                p["blocked_until_reverified"] = True
                p["pending_safety_number"] = new_safety_number or p.get("pending_safety_number")
                news = not was[0] or p["pending_safety_number"] != was[1]
            if news:
                self.add_notice("identity_changed", aci, "the safety number changed; its messages are refused until "
                                "/signal reverify confirms the new one")
            return True

    def reverify(self, aci: str, safety_number: Optional[str] = None) -> bool:
        with self._mu:
            p = self.peer(aci)
            if p is None:
                raise PairingError("that phone is not paired")
            sn = safety_number or p.get("pending_safety_number")
            if not sn and self.transport is not None:
                sn = self.transport.safety_number(aci)
            if not sn:
                raise PairingError("no safety number is known for that phone yet")
            with self._pending_edit() as q:
                q.setdefault("ops", []).append({"op": "trust", "kind": "reverify", "aci": aci, "safety_number": sn})
            self.service()
            return not (self.peer(aci) or {}).get("blocked_until_reverified")

    def service(self, transport=None) -> list:
        from halo_signal.pairing_trust import run_ops
        return run_ops(self, transport or self.transport)


def mask(number) -> str:
    digits = "".join(c for c in str(number or "") if c.isdigit())
    return f"+{digits[:1]}•••{digits[-4:]}" if len(digits) >= 6 else (str(number) if number else "no number")
