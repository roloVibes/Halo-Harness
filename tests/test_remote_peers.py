"""tests.test_remote_peers -- Halo 2.0.9 round 3: a paired peer's life after
pairing (`halo_harness/remote/pairing.py`): a changed safety number blocks until
`reverify`, `unpair`, and the per-peer rate limit.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from halo_harness.remote.pairing import PairingError
from halo_harness.remote.signal_errors import UntrustedKey
from tests.helpers.fake_signal_cli import untrusted_notice
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import (ACI_A, ACI_B, SAFETY_A, SAFETY_B, Home, mk_bridge, pair_peer, pump, say)

test, TESTS = new_registry()


@test
def test_changed_safety_number_blocks_until_reverify(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge()
        pair_peer(b.pairing, ACI_A, "+15555550101", SAFETY_A, signed=False)
        say(b, tr, clock, ACI_A, "/remote status")
        ctx.check("a paired peer is answered", len(tr.sent) == 1)
        tr.sent.clear()
        tr.identities[ACI_A] = SAFETY_B
        tr.deliver(untrusted_notice(ACI_A, "+15555550101", int(clock.now * 1000)))
        pump(b)
        peer = b.pairing.peer(ACI_A)
        ctx.check("the notification blocks the peer", peer["blocked_until_reverified"] is True)
        ctx.check("the new safety number is kept for the reverify card", peer["pending_safety_number"] == SAFETY_B)
        ctx.check("the owner gets a notice", any(n["kind"] == "identity_changed" for n in b.pairing.notices()))
        say(b, tr, clock, ACI_A, "/remote status")
        ctx.check("a blocked peer is not answered", tr.sent == [])
        ctx.check("the refusal is audited", any(r["outcome"] == "blocked" for r in b.audit.lines()))
        tr.trusts.clear()
        done = b.pairing.reverify(ACI_A)
        ctx.check("reverify trusts the confirmed number as plain digits", done and tr.trusts == [(ACI_A, "".join(SAFETY_B.split()))])
        peer = b.pairing.peer(ACI_A)
        ctx.check("and unblocks with the new number stored",
                  peer["blocked_until_reverified"] is False and peer["safety_number"] == SAFETY_B)
        say(b, tr, clock, ACI_A, "/remote status")
        ctx.check("the peer is answered again", len(tr.sent) == 1)
        # a -4 on send blocks too
        tr.sent.clear()
        tr.send_error = UntrustedKey("untrusted", -4)
        b.say(ACI_A, "ping")
        tr.send_error = None
        ctx.check("a -4 on send marks the peer blocked", b.pairing.peer(ACI_A)["blocked_until_reverified"] is True)
        try:
            b.pairing.reverify("nobody")
            ctx.check("reverify of an unknown peer raises", False)
        except PairingError:
            ctx.check("reverify of an unknown peer raises", True)


@test
def test_unpair(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge()
        pair_peer(b.pairing, ACI_A, None, SAFETY_A, signed=False)
        ctx.check("unpair removes the peer", b.pairing.unpair(ACI_A) is True and b.pairing.peers() == {})
        ctx.check("unpairing twice is False", b.pairing.unpair(ACI_A) is False)
        say(b, tr, clock, ACI_A, "/remote status")
        ctx.check("an unpaired sender is a stranger again: not answered", tr.sent == [])
        pair_peer(b.pairing, ACI_B, None, SAFETY_B, signed=False)
        say(b, tr, clock, ACI_B, "/remote unpair")
        ctx.check("/remote unpair from the phone unpairs that peer after one reply",
                  b.pairing.peers() == {} and len(tr.texts(ACI_B)) == 1 and "Unpaired" in tr.texts(ACI_B)[0])
        say(b, tr, clock, ACI_B, "/remote status")
        ctx.check("and the phone is silent afterwards", len(tr.texts(ACI_B)) == 1)


@test
def test_rate_limit(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge(rate_per_minute=3)
        pair_peer(b.pairing, ACI_A, None, SAFETY_A, signed=False)
        for _ in range(3):
            say(b, tr, clock, ACI_A, "/remote status")
        ctx.check("three commands in a minute are answered", len(tr.sent) == 3)
        say(b, tr, clock, ACI_A, "/remote status")
        ctx.check("the fourth is dropped with one notice", len(tr.sent) == 4 and "Too many" in tr.sent[-1]["text"])
        say(b, tr, clock, ACI_A, "/remote status")
        say(b, tr, clock, ACI_A, "/remote status")
        ctx.check("further ones are dropped silently", len(tr.sent) == 4)
        ctx.check("dropped commands are audited", sum(1 for r in b.audit.lines() if r["outcome"] == "rate_limited") == 3)
        clock.now += 61
        say(b, tr, clock, ACI_A, "/remote status")
        ctx.check("after the window the peer is answered again", len(tr.sent) == 5 and "Paired as" in tr.sent[-1]["text"])
        pair_peer(b.pairing, ACI_B, None, SAFETY_B, signed=False)
        say(b, tr, clock, ACI_B, "/remote status")
        ctx.check("another peer has its own budget", "Paired as" in tr.sent[-1]["text"] and tr.sent[-1]["to"] == ACI_B)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
