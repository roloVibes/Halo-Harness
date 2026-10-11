"""tests.helpers.signal_rig -- shared pieces for the Signal remote-control
tests: a scoped state home, `wait_for`, an in-process `StubTransport` (the
transport surface the bridge and pairing use, recording everything) and a
helper that pairs a fake peer through the real contact-request flow."""
from __future__ import annotations

import os
import tempfile
import threading
import time

from halo_harness.remote.signal_typing import TypingKeeper

ACI_A = "00000000-0000-4000-8000-000000000001"
ACI_B = "00000000-0000-4000-8000-000000000002"
ACI_X = "00000000-0000-4000-8000-0000000000ff"
SAFETY_A = "11111 22222 33333 44444 55555 66666 77777 88888 99999 00000 11111 22222"
SAFETY_B = "99999 88888 77777 66666 55555 44444 33333 22222 11111 00000 99999 88888"
SENTINEL = "zebra-sentinel-4417"


class Home:
    """A fresh `BRIDGE_TEST_HOME` (never `BRIDGE_STATE_DIR`), restored on exit."""

    def __init__(self) -> None:
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        self.path = tempfile.mkdtemp(prefix="signal-home-")
        os.environ["BRIDGE_TEST_HOME"] = self.path

    def __enter__(self) -> "Home":
        return self

    def __exit__(self, *exc) -> bool:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


def wait_for(cond, timeout: float = 5.0, step: float = 0.02) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(step)
    return bool(cond())


def now_ms() -> int:
    return int(time.time() * 1000)


class FakeClock:
    def __init__(self, start: float = 1_800_000_000.0) -> None:
        self.now = start

    def time(self) -> float:
        return self.now

    def monotonic(self) -> float:
        return self.now


class StubTransport:
    """Records every call; `deliver(item)` plays an inbound item to the sink."""

    def __init__(self) -> None:
        self.sent: list = []
        self.receipts: list = []
        self.trusts: list = []
        self.typing_calls: list = []
        self.identities: dict = {}
        self.attachment_text: dict = {}
        self.discarded: list = []
        self.trust_error = None
        self.send_error = None
        self.linked = False
        self.sink = lambda item: None
        self.started = False
        self.typing = TypingKeeper(self, 0.05)
        self._lock = threading.Lock()

    def set_sink(self, fn) -> None:
        self.sink = fn

    def start(self) -> "StubTransport":
        self.started = True
        return self

    def stop(self) -> None:
        self.typing.stop_all()

    def deliver(self, params: dict) -> None:
        self.sink({"kind": "envelope", "envelope": params["envelope"], "exception": params.get("exception"),
                   "account": params.get("account")})

    def send(self, recipient, text="", *, attachment=None, styles=None, note_to_self=None):
        if self.send_error is not None:
            raise self.send_error
        with self._lock:
            self.sent.append({"to": recipient, "text": text, "attachment": attachment, "styles": styles})
        return {}

    def texts(self, to=None) -> list:
        with self._lock:
            return [s["text"] for s in self.sent if to in (None, s["to"])]

    def send_typing(self, recipient, stop=False):
        with self._lock:
            self.typing_calls.append((recipient, stop))

    def send_receipt(self, recipient, timestamp, kind="read"):
        self.receipts.append((recipient, timestamp, kind))

    def safety_number(self, aci):
        return self.identities.get(aci)

    def trust(self, recipient, safety_number):
        if self.trust_error is not None:
            raise self.trust_error
        self.trusts.append((recipient, safety_number))

    def take_attachments(self, attachments, want_text):
        text = None
        for a in attachments or []:
            self.discarded.append(a.get("id"))
            if want_text and text is None and a.get("contentType") == "text/x-signal-plain":
                text = self.attachment_text.get(a.get("id"))
        return text


def pair_peer(pairing, aci: str, number=None, safety=SAFETY_A, *, signed: bool = True) -> bytes:
    """Pair `aci` through the real flow (contact request, approve, code); returns its secret."""
    pairing.note_contact(aci, number, safety)
    ap = pairing.approve(aci)
    res = pairing.redeem(aci, ap.code, number)
    assert res.status == "paired", res.status
    if not signed:
        pairing.set_signed(aci, False)
    return res.secret


class NoRegistry:
    def list_live(self):
        return []


def mk_bridge(**cfg):
    """A Bridge over a StubTransport and a FakeClock, no live sessions."""
    from halo_harness.remote.bridge import Bridge
    tr = StubTransport()
    clock = FakeClock()
    b = Bridge({"rate_per_minute": 30, **cfg}, tr, registry=NoRegistry(), clock=clock)
    tr.set_sink(b.inbox.put)
    return b, tr, clock


def pump(b) -> None:
    while not b.inbox.empty():
        b.step(0.01)


def say(b, tr, clock, aci, text, number=None):
    """Deliver a message from `aci` and let the bridge handle it."""
    from tests.helpers.fake_signal_cli import data_message
    tr.deliver(data_message(aci, text, int(clock.now * 1000), number))
    pump(b)
