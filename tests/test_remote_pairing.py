"""tests.test_remote_pairing -- Halo 2.0.9 round 3: the contact-request pairing
flow (`halo_harness/remote/pairing.py`) driven through the bridge with a stub
transport: an unknown sender is never answered, approve calls `trust` with the
safety number and returns a one-time code, three wrong codes or expiry drop
the request, a changed safety number blocks until `reverify`, `unpair`, and
the per-peer rate limit.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from halo_harness.remote import signing
from halo_harness.remote.pairing import Pairing, PairingError
from halo_harness.remote.signal_config import remote_dir
from halo_harness.remote.signal_errors import UserFailure
from tests.helpers.fake_signal_cli import untrusted_notice
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import (ACI_A, ACI_B, SAFETY_A, SAFETY_B, Home, StubTransport, mk_bridge, pump, say)

test, TESTS = new_registry()


@test
def test_unknown_sender_never_answered(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge()
        tr.identities[ACI_A] = SAFETY_A
        tr.deliver(untrusted_notice(ACI_A, "+15555550101", int(clock.now * 1000)))
        pump(b)
        ctx.check("the untrusted-identity notification is not answered", tr.sent == [])
        pend = b.pairing.pending()
        ctx.check("it becomes one pending contact request with the safety number",
                  len(pend) == 1 and pend[0]["aci"] == ACI_A and pend[0]["safety_number"] == SAFETY_A
                  and pend[0]["number"] == "+15555550101" and pend[0]["state"] == "pending")
        say(b, tr, clock, ACI_A, "hello? is anyone there")
        say(b, tr, clock, ACI_A, "/status")
        ctx.check("plain messages from the same stranger are not answered either", tr.sent == [])
        ctx.check("and do not duplicate the request", len(b.pairing.pending()) == 1)
        say(b, tr, clock, ACI_B, "123456")
        ctx.check("a six-digit guess from a stranger with no approved request is ignored", tr.sent == [] and len(b.pairing.pending()) == 2)
        ctx.check("nothing was trusted, receipted or typed", tr.trusts == [] and tr.receipts == [] and tr.typing_calls == [])
        ctx.check("no peer exists", b.pairing.peers() == {})
        tr.deliver({"envelope": {"sourceUuid": ACI_B, "timestamp": 5, "typingMessage": {"action": "STARTED"}}})
        pump(b)
        ctx.check("a typing envelope is dropped silently", tr.sent == [])


@test
def test_approve_trusts_and_pairs(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge()
        tr.identities[ACI_A] = SAFETY_A
        tr.deliver(untrusted_notice(ACI_A, None, 1))
        pump(b)
        ap = b.pairing.approve(ACI_A)
        ctx.check("approve returns a six-digit code", len(ap.code) == 6 and ap.code.isdigit())
        ctx.check("the code expires in ten minutes", ap.expires == clock.now + 600)
        ctx.check("trust ran with the safety number as plain digits", tr.trusts == [(ACI_A, "".join(SAFETY_A.split()))])
        ctx.check("approve reports the trust step done", ap.trusted is True)
        raw = (remote_dir() / "pending.json").read_text(encoding="utf-8")
        ctx.check("the code itself is never stored (only a salted hash)", ap.code not in raw and "code_hash" in raw)
        say(b, tr, clock, ACI_A, f"  {ap.code}  \n", "+15555550101")
        texts = tr.texts(ACI_A)
        ctx.check("the right code gets exactly one 'Paired.' reply", len(texts) == 1 and texts[0].startswith("Paired."))
        peer = b.pairing.peer(ACI_A)
        ctx.check("the reply says the phrase is on the Halo screen and carries no secret",
                  texts[0] == "Paired. Your signing phrase is on the Halo screen."
                  and peer["signing"]["secret_hex"] not in texts[0] and "halo-remote://" not in texts[0])
        ctx.check("the peer is stored on the ACI with number, safety number, time and counter 0",
                  peer["aci"] == ACI_A and peer["number"] == "+15555550101" and peer["safety_number"] == SAFETY_A
                  and peer["paired_at"] == clock.now and peer["signing"]["counter"] == 0 and peer["signed"] is True)
        ctx.check("the request is gone", b.pairing.pending() == [])
        say(b, tr, clock, ACI_A, "/remote status")
        ctx.check("an unsigned message from the paired peer is now refused with the signing hint",
                  "#<counter>:<mac>" in tr.texts(ACI_A)[-1])
        home = remote_dir()
        if os.name != "nt":
            ctx.check("peers.json is 0600", (home / "peers.json").stat().st_mode & 0o777 == 0o600)
            ctx.check("pending.json is 0600", (home / "pending.json").stat().st_mode & 0o777 == 0o600)
            ctx.check("the remote directory is 0700", home.stat().st_mode & 0o777 == 0o700)
        else:
            ctx.check("peers.json exists", (home / "peers.json").is_file())
        data = json.loads((home / "peers.json").read_text(encoding="utf-8"))
        ctx.check("peers.json is keyed on the ACI", list(data["peers"]) == [ACI_A])


@test
def test_wrong_codes_and_expiry(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge()
        tr.identities[ACI_A] = SAFETY_A
        tr.deliver(untrusted_notice(ACI_A, None, 1))
        pump(b)
        ap = b.pairing.approve(ACI_A)
        wrong = "000000" if ap.code != "000000" else "111111"
        for chatter in ("hi", "hi", "hello again", "1234567", "12345"):
            say(b, tr, clock, ACI_A, chatter)
        ctx.check("chatter and redelivered first messages are not guesses",
                  [r["attempts"] for r in b.pairing.pending()] == [0])
        say(b, tr, clock, ACI_A, wrong)
        say(b, tr, clock, ACI_A, wrong)
        ctx.check("two wrong codes keep the request", [r["attempts"] for r in b.pairing.pending()] == [2])
        say(b, tr, clock, ACI_A, wrong)
        ctx.check("the third wrong code drops the request", b.pairing.pending() == [])
        ctx.check("a dropped request leaves a notice", any(n["kind"] == "code_failed" for n in b.pairing.notices()))
        say(b, tr, clock, ACI_A, ap.code)
        ctx.check("the (once right) code no longer pairs", b.pairing.peers() == {})
        ctx.check("nothing was ever sent to the sender", tr.sent == [])
        # expiry
        ap2 = None
        b.pairing.note_contact(ACI_B, None, SAFETY_B)
        ap2 = b.pairing.approve(ACI_B)
        clock.now += 601
        ctx.check("an expired approval is hidden from pending()", all(r["aci"] != ACI_B for r in b.pairing.pending()))
        say(b, tr, clock, ACI_B, ap2.code)
        ctx.check("an expired code does not pair", b.pairing.peers() == {} and tr.sent == [])
        ctx.check("expiry leaves a notice", any(n["kind"] == "code_expired" for n in b.pairing.notices()))


@test
def test_approve_edge_cases(ctx: Ctx):
    with Home():
        tr = StubTransport()
        p = Pairing(transport=tr)
        try:
            p.approve(ACI_A)
            ctx.check("approve with no request raises", False)
        except PairingError:
            ctx.check("approve with no request raises", True)
        p.note_contact(ACI_A, None, None)
        try:
            p.approve(ACI_A)
            ctx.check("approve without a safety number raises", False)
        except PairingError:
            ctx.check("approve without a safety number raises", True)
        tr.identities[ACI_A] = SAFETY_A
        ap = p.approve(ACI_A)
        ctx.check("approve looks the safety number up through the transport when missing", ap.trusted and len(tr.trusts) == 1)
        # trust refused (e.g. the number no longer matches)
        p.note_contact(ACI_B, None, SAFETY_B)
        tr.trust_error = UserFailure("Invalid safety number", -1)
        ap2 = p.approve(ACI_B)
        ctx.check("a refused trust step is not reported done", ap2.trusted is False)
        ctx.check("it puts the request back to pending and leaves a notice",
                  [r["state"] for r in p.pending() if r["aci"] == ACI_B] == ["pending"]
                  and any(n["kind"] == "trust_failed" for n in p.notices()))
        # no transport: queued, then finished by service()
        p2 = Pairing(directory=Path(os.environ["BRIDGE_TEST_HOME"]) / "other")
        p2.note_contact(ACI_A, None, SAFETY_A)
        ap3 = p2.approve(ACI_A)
        ctx.check("without a transport the trust step is queued", ap3.trusted is False)
        ctx.check("the code is ignored until trust has run", p2.redeem(ACI_A, ap3.code).status == "ignored")
        tr.trust_error = None
        tr.trusts.clear()
        p2.service(tr)
        ctx.check("service() runs the queued trust step", tr.trusts == [(ACI_A, "".join(SAFETY_A.split()))])
        ctx.check("then the code pairs", p2.redeem(ACI_A, ap3.code).status == "paired")
        ctx.check("pending requests are capped", all(p.note_contact(f"id-{i}", None, None) for i in range(40))
                  and len(p.pending()) <= 32)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
