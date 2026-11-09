"""tests.test_auth -- who is answered and what is kept (Halo 2.0.9 round 3, ported from Halo's own
test_remote_bridge_auth for the signal pack): a phone with signing on (good, unsigned, forged, replayed, stale), the
audit line a hash and no message text at rest, read receipts only after the checks, Note to Self with a linked
account, a group message ignored, the rate limit, and the whole path over the real transport against the fake
signal-cli (pairing by phrase, the held message handed over after the trust, a text answered).
Run: python -m tests.test_auth"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from halo_signal import signing
from tests.support import (ACI_A, ACI_B, NUM_B, data_message, main, now_ms, registry, sync_sent, wait_for)
from tests.rig import Phone

test, TESTS = registry()
SENTINEL = "zebra-sentinel-4417"


@test
def test_signed_messages(ctx):
    with Phone() as p:
        p.pair()
        secret = p.b.pairing.set_signed(ACI_A, True)
        p.text(signing.sign(secret, 1, "/signal"))
        ctx.check("a good signed message is answered", p.wait("signing on"))
        p.text("/signal")
        ctx.check("an unsigned one is refused with the format", p.wait("set to signed messages"))
        p.text("/signal #2:00000000")
        ctx.check("a forged one is refused", p.wait("did not match"))
        good = signing.sign(secret, 2, "/signal")
        p.text(good)
        wait_for(lambda: p.joined().count("signing on") == 2, 3.0)
        p.text(good)
        ctx.check("the same one again is a replay", p.wait("already used"))
        p.tr.deliver(data_message(ACI_A, signing.sign(secret, 9, "/signal"), now_ms() - 900_000))
        ctx.check("a stale one is refused", p.wait("outside the allowed time window"))
        ctx.check("receipts only for the accepted ones", wait_for(lambda: len(p.tr.receipts) == 2, 2.0))


@test
def test_audit_is_a_hash_and_nothing_is_at_rest(ctx):
    with Phone() as p:
        p.pair()
        p.text(f"hello {SENTINEL}")
        p.wait("hello from the fake session")
        rows = p.b.audit.lines()
        last = rows[-1]
        ctx.check("a line has exactly ts, peer, h, kind, outcome", set(last) == {"ts", "peer", "h", "kind", "outcome"})
        ctx.check("h is sha256(aci|counter|text)[:16]",
                  last["h"] == hashlib.sha256(f"{ACI_A}|0|hello {SENTINEL}".encode()).hexdigest()[:16])
        hits = [str(f) for f in Path(p.home).rglob("*") if f.is_file()
                and SENTINEL in f.read_text(encoding="utf-8", errors="replace")]
        ctx.check(f"no file under the data folder holds the message, got {hits}", hits == [])


@test
def test_receipts_only_after_the_checks(ctx):
    with Phone() as p:
        p.pair()
        n = len(p.tr.receipts)
        p.text("hi", ACI_B, NUM_B)
        time.sleep(0.2)
        ctx.check("a stranger gets no receipt", len(p.tr.receipts) == n)
        p.text("hello")
        ctx.check("a paired phone's message gets one", wait_for(lambda: len(p.tr.receipts) == n + 1, 3.0))


@test
def test_note_to_self(ctx):
    own = ACI_A
    with Phone(identity_model="linked", own_aci=own) as p:
        phrase = p.b.pairing.invite()["phrase"]
        p.tr.deliver(sync_sent(own, phrase, now_ms()))
        ctx.check("the phrase in Note to Self pairs the account itself", p.wait("Paired."))
        ctx.check("no trust step with a linked account", p.tr.trusts == [])
        p.tr.deliver(sync_sent(own, "hello", now_ms()))
        ctx.check("a Note to Self text is a prompt", p.wait("hello from the fake session"))
        n = len(p.tr.sent)
        p.text("from someone else", ACI_B, NUM_B)
        time.sleep(0.2)
        ctx.check("anything but the own sync is dropped", len(p.tr.sent) == n)


@test
def test_groups_and_rate_limit(ctx):
    with Phone(rate_per_minute=3) as p:
        p.pair()
        n = len(p.tr.sent)
        p.tr.deliver(data_message(ACI_A, "in a group", now_ms(), group="g1"))
        time.sleep(0.2)
        ctx.check("a group message is never a command", len(p.tr.sent) == n
                  and any(x["kind"] == "group_message" for x in p.b.pairing.notices()))
        for i in range(5):
            p.text(f"/signal {i}")
        ctx.check("past the rate the phone is told once", p.wait("Too many messages") and
                  p.joined().count("Too many messages") == 1)


@test
def test_end_to_end_with_the_fake_signal_cli(ctx):
    import os
    import tempfile
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="signal-e2e-")
    from halo_signal.bridge import Bridge
    from halo_signal.transport import SignalTransport
    from tests.fake_session import FakeSessions
    from tests.fake_signal_cli import FakeSignal
    import threading
    fake = FakeSignal()
    t = SignalTransport(fake.config(), backoff=(0.05,), typing_interval=0.05, request_timeout=5.0)
    b = Bridge({"rate_per_minute": 100}, t, sessions=FakeSessions(), notes=False)
    stop = threading.Event()
    th = threading.Thread(target=b.run, args=(stop, 0.02), daemon=True)
    th.start()
    try:
        ctx.check("the transport is up", t.wait_connected(15))
        time.sleep(0.3)
        phrase = b.pairing.invite()["phrase"]
        fake.order(op="identity", uuid=ACI_A, number="+15550100", safetyNumber="11111" * 12)
        fake.order(op="untrusted", uuid=ACI_A, number="+15550100", held_text=phrase)
        ctx.check("the trust step ran with the safety number",
                  wait_for(lambda: fake.requests("trust"), 8.0))
        ctx.check("the held message, handed over after the trust, pairs the phone",
                  wait_for(lambda: b.pairing.is_paired(ACI_A), 8.0))
        fake.emit(data_message(ACI_A, "hello", now_ms(), "+15550100"))
        sends = lambda: [r["params"].get("message") for r in fake.requests("send")]  # noqa: E731
        ctx.check("the answer went out through signal-cli", wait_for(lambda: any(
            "hello from the fake session" in str(m) for m in sends()), 10.0))
        ctx.check("every send went to the paired phone only",
                  all(r["params"].get("recipient") == [ACI_A] for r in fake.requests("send")))
    finally:
        stop.set()
        th.join(5)


if __name__ == "__main__":
    raise SystemExit(main(TESTS))
