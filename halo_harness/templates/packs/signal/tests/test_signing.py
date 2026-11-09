"""tests.test_signing -- Halo 2.0.9 round 3: per-peer command signing
(`halo_signal/signing.py`): the phrase round trip, the documented HMAC
vector, replay and the window, and that `signed: false` skips the check.
"""
from __future__ import annotations

import hashlib
import hmac
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from halo_signal import signing
from halo_signal.signing import WORDS
from tests.support import Ctx, main, new_registry
from tests.support import ACI_A, Home, StubTransport

test, TESTS = new_registry()

# The vector the pack's README documents (Signing).
VEC_SECRET = bytes(range(32))
VEC_HEX = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
NOW = 1_800_000_000.0
TS = int(NOW * 1000)


@test
def test_phrase_round_trip(ctx: Ctx):
    ctx.check("the word list has 256 distinct words", len(WORDS) == 256 and len(set(WORDS)) == 256)
    ctx.check("all words are lowercase ASCII letters", all(w.isascii() and w.isalpha() and w.islower() for w in WORDS))
    for secret in (VEC_SECRET, signing.new_secret(), signing.new_secret(), bytes(32), bytes([255]) * 32):
        phrase = signing.secret_to_phrase(secret)
        ctx.check(f"phrase of {secret[:2].hex()}.. is 32 words", len(phrase.split()) == 32)
        ctx.check(f"phrase round-trips {secret[:2].hex()}..", signing.phrase_to_secret(phrase) == secret)
    ctx.check("phrase parsing ignores case and spacing",
              signing.phrase_to_secret("  " + signing.secret_to_phrase(VEC_SECRET).upper().replace(" ", "   ") + " ") == VEC_SECRET)
    try:
        signing.phrase_to_secret("acorn notaword")
        ctx.check("an unknown word is a ValueError", False)
    except ValueError:
        ctx.check("an unknown word is a ValueError", True)
    ctx.check("secrets are 256 bits and differ", len(signing.new_secret()) == 32
              and signing.new_secret() != signing.new_secret())
    uri = signing.pair_uri(VEC_SECRET, ACI_A)
    ctx.check("the pairing link is a halo-remote://pair URI carrying the secret hex",
              uri.startswith("halo-remote://pair?") and f"secret={VEC_HEX}" in uri and f"aci={ACI_A}" in uri
              and "alg=hmac-sha256" in uri)


@test
def test_hmac_vector(ctx: Ctx):
    ctx.check("vector secret is bytes 0..31", VEC_SECRET.hex() == VEC_HEX)
    ctx.check("mac8 for counter 1 / '/status' is 9ef2aa6c", signing.mac8(VEC_SECRET, 1, "/status") == "9ef2aa6c")
    ctx.check("mac8 for counter 7 / 'run the tests' is e3173adf",
              signing.mac8(VEC_SECRET, 7, "run the tests") == "e3173adf")
    ref = hmac.new(VEC_SECRET, b"1|/status", hashlib.sha256).hexdigest()[:8]
    ctx.check("mac8 equals first 8 hex of HMAC-SHA256(secret, 'counter|text')", ref == "9ef2aa6c")
    ctx.check("sign() builds '<text> #<counter>:<mac>'", signing.sign(VEC_SECRET, 1, "/status") == "/status #1:9ef2aa6c")
    ctx.check("sign() trims the text first", signing.sign(VEC_SECRET, 7, "  run the tests  ") == "run the tests #7:e3173adf")
    ctx.check("parse_signed splits the trailer",
              signing.parse_signed("run the tests #7:e3173adf") == ("run the tests", 7, "e3173adf"))
    ctx.check("parse_signed on plain text is None", signing.parse_signed("run the tests") is None)
    ctx.check("a '#3' inside the text is not a trailer", signing.parse_signed("fix issue #3 please") is None)
    ctx.check("non-ASCII text signs over its UTF-8 bytes",
              signing.mac8(VEC_SECRET, 2, "café")
              == hmac.new(VEC_SECRET, "2|café".encode("utf-8"), hashlib.sha256).hexdigest()[:8])


@test
def test_verify_paths(ctx: Ctx):
    s = VEC_SECRET
    v = signing.verify(s, 0, signing.sign(s, 1, "/status"), TS, NOW)
    ctx.check("a good command verifies", v.ok and v.text == "/status" and v.counter == 1 and v.reason == "")
    ctx.check("an unsigned message is refused as unsigned", signing.verify(s, 0, "/status", TS, NOW).reason == "unsigned")
    bad = "/status #1:00000000"
    ctx.check("a wrong mac is refused as bad_mac", signing.verify(s, 0, bad, TS, NOW).reason == "bad_mac")
    ctx.check("a tampered text is refused as bad_mac",
              signing.verify(s, 0, signing.sign(s, 1, "/status").replace("/status", "/stop"), TS, NOW).reason == "bad_mac")
    ctx.check("a mac from another secret is refused",
              signing.verify(bytes(32), 0, signing.sign(s, 1, "/status"), TS, NOW).reason == "bad_mac")
    ctx.check("the same counter again is a replay", signing.verify(s, 1, signing.sign(s, 1, "/status"), TS, NOW).reason == "replay")
    ctx.check("a lower counter is a replay", signing.verify(s, 5, signing.sign(s, 4, "/status"), TS, NOW).reason == "replay")
    ctx.check("a higher counter is accepted (gaps are fine)", signing.verify(s, 5, signing.sign(s, 9, "/x"), TS, NOW).ok)
    ctx.check("an envelope 6 minutes old is stale",
              signing.verify(s, 0, signing.sign(s, 1, "/status"), TS - 360_000, NOW).reason == "stale")
    ctx.check("an envelope 6 minutes in the future is stale",
              signing.verify(s, 0, signing.sign(s, 1, "/status"), TS + 360_000, NOW).reason == "stale")
    ctx.check("4 minutes is inside the window",
              signing.verify(s, 0, signing.sign(s, 1, "/status"), TS - 240_000, NOW).ok)
    ctx.check("a missing timestamp is stale", signing.verify(s, 0, signing.sign(s, 1, "/status"), None, NOW).reason == "stale")
    ctx.check("the check order is mac before window before counter",
              signing.verify(s, 9, "/x #1:00000000", TS - 999_000, NOW).reason == "bad_mac"
              and signing.verify(s, 9, signing.sign(s, 1, "/x"), TS - 999_000, NOW).reason == "stale")


@test
def test_counter_persisted_and_signing_per_phone(ctx: Ctx):
    with Home():
        from halo_signal.pairing import Pairing
        p = Pairing(transport=StubTransport(), trust_needed=False)
        phrase = p.invite()["phrase"]
        ctx.check("the phrase pairs the phone", p.redeem(ACI_A, phrase, "+15550100").status == "paired")
        ctx.check("3.3.13.0 R3: a phone paired by phrase has signing off and no secret",
                  p.peer(ACI_A)["signed"] is False and "signing" not in p.peer(ACI_A))
        secret = p.set_signed(ACI_A, True)
        peer = p.peer(ACI_A)
        ctx.check("sign on: a fresh secret with counter 0, returned once",
                  peer["signed"] is True and peer["signing"]["counter"] == 0 and len(secret) == 32
                  and bytes.fromhex(peer["signing"]["secret_hex"]) == secret)
        p.advance_counter(ACI_A, 5)
        p.advance_counter(ACI_A, 3)
        ctx.check("the stored counter only moves forward", p.peer(ACI_A)["signing"]["counter"] == 5)
        ctx.check("sign off turns signing off for that phone",
                  p.set_signed(ACI_A, False) == b"" and p.peer(ACI_A)["signed"] is False)
        ctx.check("set_signed on an unknown phone is None", p.set_signed("nobody", True) is None)


if __name__ == "__main__":
    raise SystemExit(main(TESTS))
