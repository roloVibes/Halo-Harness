"""tests.test_pairing -- pairing in one message (3.3.13.0 R3; Halo's own test_remote_pairing and test_remote_peers
before it): the phrase is six of the 256 words and only its salted hash is kept; chatter is not a guess; three wrong
phrases close the invite; an expired one pairs nothing; a new invite replaces the old; the untrusted first message is
trusted only while a phrase is open; a changed safety number blocks a paired phone until reverify; unpair; a stranger
is noted once a day. Run: python -m tests.test_pairing"""

from __future__ import annotations

import json

from halo_signal import signing
from halo_signal.pairing import Pairing, normalize
from tests.support import ACI_A, ACI_B, SAFETY, FakeClock, Home, StubTransport, main, registry

test, TESTS = registry()


def _mk(clock=None, trust=True):
    tr = StubTransport()
    tr.identities[ACI_A] = SAFETY
    return Pairing(transport=tr, clock=(clock or FakeClock()).time, ttl=600, trust_needed=trust), tr


@test
def test_the_phrase(ctx):
    with Home():
        p, _ = _mk()
        got = p.invite()
        words = got["phrase"].split()
        ctx.check("six words of the signing list", len(words) == 6 and all(w in signing.WORDS for w in words))
        raw = p.invites_path.read_text(encoding="utf-8")
        ctx.check("only a salted hash is kept", got["phrase"] not in raw and json.loads(raw)["invite"]["hash"])
        ctx.check("case, commas and dashes do not matter", normalize("Acorn, ALARM-amber") == "acorn alarm amber")
        ctx.check("chatter is not a guess", p.redeem(ACI_A, "hello there", "+15550100").status == "ignored")
        ctx.check("the phrase pairs", p.redeem(ACI_A, got["phrase"].upper(), "+15550100").status == "paired")
        ctx.check("a used phrase pairs nothing more", p.redeem(ACI_B, got["phrase"], "+15550101").status == "ignored")


@test
def test_wrong_expired_replaced(ctx):
    with Home():
        clock = FakeClock()
        p, _ = _mk(clock)
        good = p.invite()["phrase"]
        wrong = " ".join(signing.WORDS[:6]) if good != " ".join(signing.WORDS[:6]) else " ".join(signing.WORDS[6:12])
        outcomes = [p.redeem(ACI_B, wrong, None).status for _ in range(3)]
        ctx.check(f"three wrong phrases close the invite, got {outcomes}", outcomes == ["wrong", "wrong", "dropped"])
        ctx.check("then the right one pairs nothing", p.redeem(ACI_A, good, None).status == "ignored"
                  and p.invite_state()["state"] == "closed")
        good = p.invite()["phrase"]
        clock.advance(601)
        ctx.check("an expired phrase pairs nothing", p.redeem(ACI_A, good, None).status == "expired"
                  and not p.is_paired(ACI_A))
        first = p.invite()["phrase"]
        second = p.invite()["phrase"]
        ctx.check("a new invite replaces the old", p.redeem(ACI_A, first, None).status in ("wrong", "ignored")
                  and p.redeem(ACI_A, second, None).status == "paired")


@test
def test_trust_only_while_a_phrase_is_open(ctx):
    with Home():
        p, tr = _mk()
        ctx.check("no invite: the untrusted first message is not trusted", p.note_untrusted(ACI_A, None, None) is False
                  and tr.trusts == [])
        p.invite()
        ctx.check("an open invite: its key is trusted with the safety number", p.note_untrusted(ACI_A, None, None)
                  and tr.trusts == [(ACI_A, "".join(SAFETY.split()))])


@test
def test_block_reverify_unpair(ctx):
    with Home():
        p, tr = _mk(trust=False)
        p.redeem(ACI_A, p.invite()["phrase"], None)
        ctx.check("a changed key blocks the phone with one notice", p.block(ACI_A, "999") and p.block(ACI_A, "999")
                  and sum(1 for n in p.notices() if n["kind"] == "identity_changed") == 1)
        ctx.check("reverify trusts the confirmed key and unblocks", p.reverify(ACI_A)
                  and not p.peer(ACI_A)["blocked_until_reverified"] and tr.trusts[-1] == (ACI_A, "999"))
        ctx.check("unpair forgets the phone", p.unpair(ACI_A) and not p.is_paired(ACI_A))


@test
def test_a_stranger_is_noted_once_a_day(ctx):
    with Home():
        clock = FakeClock()
        p, _ = _mk(clock)
        p.note_stranger(ACI_B, "+15550101")
        p.note_stranger(ACI_B, "+15550101")
        ctx.check("one notice", sum(1 for n in p.notices() if n["kind"] == "stranger") == 1)
        clock.advance(86401)
        p.note_stranger(ACI_B, "+15550101")
        ctx.check("a day later, another", sum(1 for n in p.notices() if n["kind"] == "stranger") == 2)


if __name__ == "__main__":
    raise SystemExit(main(TESTS))
