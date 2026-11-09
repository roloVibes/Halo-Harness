"""tests.test_transport_pins -- the transport's and the trust queue's pins from Halo's 3.0.2.0 review fix pass (ported
from test_review3_d1b, d2b and d2c when the bridge became the signal pack): item 30 a refused subscribeReceive is
retried then reported once (a daemon client names the account), item 102 typing and receipts wait out a `-5` pause
with one notice per pause, item 105 a trust step refused for another reason is finished and a network failure backs
off then gives up, item 106 a reader exception and a failed subscribe respawn the link. No signal-cli is spawned.
Run: python -m tests.test_transport_pins"""

from __future__ import annotations

import io
import json
import tempfile
from types import SimpleNamespace

from halo_signal import errors as E
from halo_signal.link import Link
from halo_signal.transport import SUBSCRIBE_TRIES, SignalTransport
from tests.support import ACI_A, SAFETY, FakeClock, Home, main, registry, wait_for

test, TESTS = registry()


def _stub(responses: list, transport: str = "stdio"):
    t = SignalTransport({"account": "+15550199", "transport": transport, "data_dir": tempfile.mkdtemp(prefix="pin-")},
                        backoff=(0.01,))
    notices, sent, interrupts = [], [], []
    t.set_sink(notices.append)
    t._link = SimpleNamespace(interrupt=lambda: interrupts.append(1))
    t._connected.set()

    def request(method, params=None, timeout=None):
        sent.append((method, params))
        r = responses.pop(0) if responses else None
        if callable(r):
            r = r(t)
        if isinstance(r, Exception):
            raise r
        return r
    t.request = request
    return t, notices, sent, interrupts


class _ReplyLink(Link):
    def __init__(self, t, reply) -> None:
        super().__init__(io.BytesIO(b""), io.BytesIO(), lambda: None)
        self.t, self.reply, self.methods, self.interrupts = t, reply, [], 0

    def write(self, obj: dict) -> None:
        self.methods.append(obj["method"])
        self.t._dispatch({"id": obj["id"], **self.reply(obj)})

    def interrupt(self) -> None:
        self.interrupts += 1


def _real(sink: list, **cfg) -> SignalTransport:
    t = SignalTransport({"data_dir": tempfile.mkdtemp(prefix="pin-"), "receive_mode": "on-start", **cfg},
                        backoff=(0.01,), request_timeout=1.0)
    t.set_sink(sink.append)
    return t


def _connect(t, reply) -> _ReplyLink:
    link = _ReplyLink(t, reply)
    t._link = link
    t._connected.set()
    return link


@test
def test_item30_subscribe_retried_then_reported(ctx):
    t, notices, sent, _ = _stub([E.UserFailure("busy", -1), 0])
    t._subscribe()
    ctx.check("a transient refusal is retried, nothing reported", len(sent) == 2 and notices == [])
    ctx.check("stdio sends no account", sent[0] == ("subscribeReceive", {}))
    t, notices, sent, _ = _stub([E.SignalError("Method not found", -32601)])
    t._subscribe()
    ctx.check("a permanent rejection is reported once, not retried", len(sent) == 1 and notices == [
        {"kind": "notice", "name": "subscribe_failed", "code": -32601, "message": "Method not found"}])
    t, notices, sent, _ = _stub([E.UserFailure("no", -1)] * 10)
    t._subscribe()
    ctx.check("retries are bounded", len(sent) == SUBSCRIBE_TRIES and len(notices) == 1)
    t, notices, sent, interrupts = _stub([E.IOFailure("no reply to subscribeReceive")])
    t._subscribe()
    ctx.check("no reply drops the link", len(notices) == 1 and interrupts == [1])
    t, notices, sent, _ = _stub([0], transport="tcp")
    t._subscribe()
    ctx.check("a daemon client names the account", sent == [("subscribeReceive", {"account": "+15550199"})])


@test
def test_item102_typing_and_receipts_wait_out_the_pause(ctx):
    sink: list = []
    t = _real(sink)
    link = _connect(t, lambda req: {"error": {"code": -5, "message": "rate limited",
                                              "data": {"results": [{"retryAfterSeconds": 300, "token": "tok-1"}]}}})
    for _ in range(3):
        try:
            t.request("send", {"message": "x"})
        except E.RateLimited:
            pass
    ctx.check("one rate_limited notice for one pause", len([n for n in sink if n.get("name") == "rate_limited"]) == 1)
    n = len(link.methods)
    ctx.check("typing and receipts are skipped in the pause", t.send_typing(ACI_A) is None
              and t.send_receipt(ACI_A, 123) is None and len(link.methods) == n)
    t.paused_until = 0.0
    link.reply = lambda req: {"result": {}}
    t.send_typing(ACI_A)
    ctx.check("typing resumes after", link.methods[-1] == "sendTyping")


class _CountingTrust:
    def __init__(self, error) -> None:
        self.error, self.calls = error, 0

    def trust(self, recipient, safety_number):
        self.calls += 1
        if self.error is not None:
            raise self.error


def _queued(clock):
    from halo_signal.pairing import Pairing
    tr = SimpleNamespace(safety_number=lambda aci: SAFETY)
    p = Pairing(clock=clock.time, transport=None)
    p.invite()
    p.transport = tr
    with p._pending_edit() as q:
        q["ops"] = [{"op": "trust", "kind": "invite", "aci": ACI_A, "safety_number": SAFETY}]
    return p


@test
def test_item105_trust_steps(ctx):
    with Home():
        clock = FakeClock()
        p = _queued(clock)
        tr = _CountingTrust(E.SignalError("internal error", -32603))
        for _ in range(5):
            p.service(tr)
        ctx.check(f"refused: one attempt, then finished (got {tr.calls})", tr.calls == 1
                  and not json.loads(p.pending_path.read_text())["ops"] and any(n["kind"] == "trust_failed" for n in p.notices()))
        from halo_signal.pairing_trust import TRUST_TRIES
        p = _queued(clock)
        tr = _CountingTrust(E.IOFailure("link closed"))
        for _ in range(10):
            p.service(tr)
        ctx.check("a network failure backs off", tr.calls == 1)
        for _ in range(TRUST_TRIES * 2):
            clock.advance(61)
            p.service(tr)
        ctx.check(f"then gives up after {TRUST_TRIES}", tr.calls == TRUST_TRIES)


@test
def test_item106_respawns(ctx):
    sink: list = []
    t = _real(sink)
    opened: list = []

    def fake_open():
        link = Link(io.BytesIO(b'{"jsonrpc":"2.0","id":[1],"result":1}\n'), io.BytesIO(), lambda: None)
        opened.append(link)
        return link
    real_read = t._read_loop

    def flaky_read(link):
        if len(opened) == 1:
            raise RuntimeError("reader blew up")
        real_read(link)
    t._open, t._read_loop = fake_open, flaky_read
    t.start()
    try:
        ok = wait_for(lambda: len(opened) >= 3, 5.0)
    finally:
        t.stop()
    ctx.check("the link was respawned after the exception", ok and "disconnected" in [n.get("name") for n in sink])
    sink2: list = []
    t2 = _real(sink2, receive_mode="manual")
    link = _connect(t2, lambda req: {"error": {"code": -32601, "message": "Method not implemented"}})
    t2._subscribe(link)
    ctx.check("a failed subscribe is surfaced and interrupts the link",
              any(n.get("name") == "subscribe_failed" for n in sink2) and link.interrupts == 1)


if __name__ == "__main__":
    raise SystemExit(main(TESTS))
