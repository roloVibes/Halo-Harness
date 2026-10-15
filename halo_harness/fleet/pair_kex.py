"""halo_harness.fleet.pair_kex -- the six-word pairing code and the key
agreement behind `halo fleet join` (Halo 3.0.5.0 "Fleet" round R2).

The code is six words from the signing word list (remote/signing_words.py:
256 words, one byte each, so 48 random bits); `code_key` is its SHA-256 and
is all the hub keeps of it. The join is one round trip of finite-field
Diffie-Hellman in the RFC 3526 2048-bit MODP group (g = 2, 256-bit
exponents), both halves authenticated with the code:

    joiner  A = g^a,  mac_j = HMAC(code_key, "join|<harness id>|<A>|<ts>|<nonce>")
    hub     B = g^b,  mac_h = HMAC(code_key, "joined|<A>|<B>|<hub id>|<fingerprint>")
    both    pair key = HMAC(SHA-256(A^b = B^a), "halo-fleet-key|" + code_key + "|<A>|<B>")

Someone who only listens learns neither the code nor the pair key; the
hub's certificate fingerprint rides inside mac_h, so a joiner that did not
know the fingerprint still pins the right one. The code is single use and
expires (`halo fleet pair --ttl`, default 10 minutes).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from halo_harness.remote.signing_words import WORDS

CODE_WORDS = 6
P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF", 16)
G = 2
_WORDSET = frozenset(WORDS)


def new_code() -> str:
    return " ".join(secrets.choice(WORDS) for _ in range(CODE_WORDS))


def normalize_code(text: str) -> str:
    """The code as six lowercase words joined by single spaces, or ValueError."""
    words = (text or "").replace("-", " ").lower().split()
    if len(words) != CODE_WORDS:
        raise ValueError(f"a pairing code is {CODE_WORDS} words, got {len(words)}")
    unknown = [w for w in words if w not in _WORDSET]
    if unknown:
        raise ValueError(f"not a pairing word: {unknown[0]!r}")
    return " ".join(words)


def code_key(code: str) -> bytes:
    return hashlib.sha256(("halo-fleet-code|" + normalize_code(code)).encode("utf-8")).digest()


def mac(key: bytes, *parts) -> str:
    return hmac.new(key, "|".join(str(p) for p in parts).encode("utf-8"), hashlib.sha256).hexdigest()


def keypair() -> "tuple[int, str]":
    """`(secret exponent, public value as hex)`."""
    x = secrets.randbits(256) | (1 << 255)
    return x, format(pow(G, x, P), "x")


def _public(value_hex: str) -> int:
    try:
        y = int(str(value_hex), 16)
    except (TypeError, ValueError):
        raise ValueError("the key-agreement value is not hex") from None
    if not 1 < y < P - 1:
        raise ValueError("the key-agreement value is out of range")
    return y


def pair_key(secret: int, peer_hex: str, ckey: bytes, a_hex: str, b_hex: str) -> bytes:
    shared = pow(_public(peer_hex), secret, P)
    z = hashlib.sha256(shared.to_bytes((P.bit_length() + 7) // 8, "big")).digest()
    return hmac.new(z, b"halo-fleet-key|" + ckey + f"|{a_hex}|{b_hex}".encode("ascii"), hashlib.sha256).digest()


def check_public(value_hex: str) -> str:
    """The value back when it is a usable public value (ValueError otherwise)."""
    _public(value_hex)
    return str(value_hex)
