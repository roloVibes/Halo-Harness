"""tests.helpers.signal_rig -- what Halo's own tests keep of the Signal test kit after the bridge became the signal pack
(3.3.13.0 R3; the pack's own tests live in halo_harness/templates/packs/signal/tests/): fake ids, `wait_for`, and
`StubTransport` -- the transport surface the pack's bridge uses, recording every send -- for tests/test_pack_signal.py,
which drives the installed pack's bridge over real control sockets. Every id and number is fake."""
from __future__ import annotations

import threading
import time
from pathlib import Path

ACI_A = "00000000-0000-4000-8000-000000000001"
ACI_B = "00000000-0000-4000-8000-000000000002"
SAFETY_A = "11111 22222 33333 44444 55555 66666 77777 88888 99999 00000 11111 22222"


def wait_for(cond, timeout: float = 5.0, step: float = 0.02) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(step)
    return bool(cond())


def now_ms() -> int:
    return int(time.time() * 1000)


class _Typing:
    def __init__(self, tr) -> None:
        self.tr = tr

    def start(self, aci) -> bool:
        self.tr.typing_calls.append((aci, False))
        return True

    def stop(self, aci) -> None:
        self.tr.typing_calls.append((aci, True))

    def stop_all(self) -> None:
        pass


class StubTransport:
    """Records every call; `deliver(params)` plays an inbound envelope; `files` maps an attachment id to (bytes, type)."""

    def __init__(self) -> None:
        self.sent, self.receipts, self.trusts, self.typing_calls = [], [], [], []
        self.identities: dict = {}
        self.files: dict = {}
        self.sink = lambda item: None
        self.typing = _Typing(self)
        self._lock = threading.Lock()

    def set_sink(self, fn) -> None:
        self.sink = fn

    def start(self):
        return self

    def stop(self) -> None:
        pass

    def deliver(self, params: dict) -> None:
        self.sink({"kind": "envelope", "envelope": params["envelope"], "exception": params.get("exception"),
                   "account": params.get("account")})

    def send(self, recipient, text="", *, attachment=None, styles=None, note_to_self=None):
        with self._lock:
            self.sent.append({"to": recipient, "text": text, "attachment": attachment, "styles": styles})
        return {}

    def texts(self, to=None) -> list:
        with self._lock:
            return [s["text"] for s in self.sent if to in (None, s["to"])]

    def send_typing(self, recipient, stop=False):
        self.typing_calls.append((recipient, stop))

    def send_receipt(self, recipient, timestamp, kind="read"):
        self.receipts.append((recipient, timestamp, kind))

    def safety_number(self, aci):
        return self.identities.get(aci)

    def trust(self, recipient, safety_number):
        self.trusts.append((recipient, safety_number))

    def take_attachments(self, attachments, want_text, inbox=None):
        got = []
        for a in attachments or []:
            data, ctype = self.files.get(a.get("id"), (b"", a.get("contentType")))
            if want_text and inbox is not None:
                Path(inbox).mkdir(parents=True, exist_ok=True)
                dest = Path(inbox) / f"{a['id']}-{a.get('filename') or 'file'}"
                dest.write_bytes(data)
                got.append({"path": str(dest), "content_type": ctype, "filename": a.get("filename") or "file",
                            "voice": str(ctype).startswith("audio/")})
        return None, got


def envelope(uuid: str, text, ts: int, number=None, attachments=None, reaction=None) -> dict:
    dm = {"timestamp": ts, "message": text, "attachments": attachments or []}
    if reaction:
        dm["reaction"] = reaction
    env = {"source": number or uuid, "sourceNumber": number, "sourceUuid": uuid, "sourceDevice": 1, "timestamp": ts,
           "dataMessage": dm}
    return {"envelope": env, "account": "+15550199"}


def untrusted(uuid: str, number=None, ts: int = 0) -> dict:
    env = {"source": number or uuid, "sourceNumber": number, "sourceUuid": uuid, "sourceDevice": 1, "timestamp": ts}
    return {"envelope": env, "account": "+15550199",
            "exception": {"message": f"Untrusted identity: {number or uuid}", "type": "UntrustedIdentityException"}}
