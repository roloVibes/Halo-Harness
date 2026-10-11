"""halo_harness.remote.signing -- per-peer command signing (Halo 2.0.9
round 3): authentication of each command inside the Signal message.

The exact bytes (what a phone-side HMAC app has to compute):

    secret   32 random bytes from `secrets.token_bytes`; shown once as a
             hex string inside the `halo-remote://pair?...` link and as a
             32-word phrase (256 distinct words, one byte per word)
    message  the command text, then a space, then `#<counter>:<mac>`
             e.g.  /status #5:0a1b2c3d
    mac      the first 8 lowercase hex characters of
             HMAC-SHA256(key = the 32 secret bytes,
                         data = UTF-8 of "<counter>|<text>")
             where <counter> is the decimal counter without leading zeros
             and <text> is the command text exactly as typed (the trailer
             and the single space before it removed, the whole message
             trimmed of leading/trailing whitespace first)

Checks, in this order: the trailer parses; the mac matches (constant-time);
the envelope timestamp is within `window_s` of now (default 300 s); the
counter is strictly greater than the stored one. Only a command that passes
all four advances the stored counter. A peer with `signed: false` skips
this module entirely; a `signed: true` peer whose stored secret is missing or
not 64 hex characters is refused by the bridge (`secret_from_hex` raises) and
never verified against an empty key.
"""

from __future__ import annotations

import hmac
import re
import secrets
from hashlib import sha256
from typing import NamedTuple, Optional

from halo_harness.remote.signing_words import WORDS

SECRET_BYTES = 32
MAC_CHARS = 8
WINDOW_S = 300
_TRAILER = re.compile(r"\s#(\d{1,15}):([0-9a-fA-F]{8})\Z")
_INDEX = {w: i for i, w in enumerate(WORDS)}
_HEX_SECRET = re.compile(r"[0-9a-fA-F]{%d}\Z" % (SECRET_BYTES * 2))


class Verdict(NamedTuple):
    ok: bool
    text: str
    counter: int
    reason: str  # "" when ok, else unsigned | bad_mac | stale | replay


def new_secret() -> bytes:
    return secrets.token_bytes(SECRET_BYTES)


def secret_to_phrase(secret: bytes) -> str:
    """One word per byte: 32 words for a 32-byte secret (an exact round trip)."""
    return " ".join(WORDS[b] for b in secret)


def phrase_to_secret(phrase: str) -> bytes:
    """The 32 bytes behind a signing phrase. Exactly `SECRET_BYTES` known words
    or `ValueError`: a short or empty key is a valid HMAC key anyone can guess,
    so a mistyped phrase must fail loudly (2.0.10 review finding 1)."""
    words = (phrase or "").lower().split()
    if len(words) != SECRET_BYTES:
        raise ValueError(f"a signing phrase is exactly {SECRET_BYTES} words, got {len(words)}")
    try:
        return bytes(_INDEX[w] for w in words)
    except KeyError as e:
        raise ValueError(f"not a signing word: {e.args[0]!r}") from None


def secret_from_hex(value) -> bytes:
    """The secret stored in `peers.json` (`secret_hex`), or `ValueError` unless it
    is exactly 64 hex characters. Never an empty or short key (finding 4)."""
    if not isinstance(value, str) or not _HEX_SECRET.match(value):
        raise ValueError(f"a signing secret is exactly {SECRET_BYTES * 2} hex characters")
    return bytes.fromhex(value)


def parse_pair_uri(uri: str) -> "tuple[bytes, str]":
    """`(secret, aci)` from a `halo-remote://pair?...` link; `ValueError` when the
    scheme, `v`, `alg` or `len` is wrong or `secret` is not 64 hex characters."""
    from urllib.parse import parse_qs, urlsplit
    parts = urlsplit((uri or "").strip())
    if parts.scheme != "halo-remote" or parts.netloc != "pair":
        raise ValueError("not a halo-remote://pair link")
    q = {k: v[-1] for k, v in parse_qs(parts.query).items()}
    if q.get("v") != "1" or q.get("alg") != "hmac-sha256" or q.get("len") != str(MAC_CHARS):
        raise ValueError("unsupported pairing link version or algorithm")
    return secret_from_hex(q.get("secret")), q.get("aci", "")


def pair_uri(secret: bytes, aci: str = "") -> str:
    """The text a phone-side app can turn into its HMAC key (QR rendering is
    the CLI's job). `alg` and `len` document the mac."""
    q = f"v=1&alg=hmac-sha256&len={MAC_CHARS}&secret={secret.hex()}"
    return "halo-remote://pair?" + (f"aci={aci}&" if aci else "") + q


def mac8(secret: bytes, counter: int, text: str) -> str:
    data = f"{int(counter)}|{text}".encode("utf-8")
    return hmac.new(secret, data, sha256).hexdigest()[:MAC_CHARS]


def sign(secret: bytes, counter: int, text: str) -> str:
    """What the phone sends: `<text> #<counter>:<mac>`."""
    text = text.strip()
    return f"{text} #{int(counter)}:{mac8(secret, counter, text)}"


def parse_signed(message: str) -> "Optional[tuple]":
    """`(text, counter, mac)` or None when there is no trailer."""
    msg = (message or "").strip()
    m = _TRAILER.search(msg)
    if not m:
        return None
    return msg[:m.start()], int(m.group(1)), m.group(2).lower()


def verify(secret: bytes, last_counter: int, message: str, ts_ms: Optional[int], now_s: float,
           window_s: int = WINDOW_S) -> Verdict:
    parsed = parse_signed(message)
    if parsed is None:
        return Verdict(False, "", 0, "unsigned")
    text, counter, mac = parsed
    if not hmac.compare_digest(mac, mac8(secret, counter, text)):
        return Verdict(False, text, counter, "bad_mac")
    if ts_ms is None or abs(now_s - ts_ms / 1000.0) > window_s:
        return Verdict(False, text, counter, "stale")
    if counter <= int(last_counter):
        return Verdict(False, text, counter, "replay")
    return Verdict(True, text, counter, "")
