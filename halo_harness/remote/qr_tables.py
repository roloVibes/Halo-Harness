"""halo_harness.remote.qr_tables -- the number-crunching under qr.py (Halo
2.0.9 round 4): the Reed-Solomon field and generator polynomials (computed
here from the field polynomial 0x11D, never pasted), the format and version
information codes (BCH, computed), and the small per-version tables for
error-correction level L, versions 1 to 10.
"""

from __future__ import annotations

# ---- GF(256), x^8 + x^4 + x^3 + x^2 + 1 -----------------------------------
EXP = [0] * 512
LOG = [0] * 256


def _build_field() -> None:
    x = 1
    for i in range(255):
        EXP[i] = x
        LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        EXP[i] = EXP[i - 255]


_build_field()


def gf_mul(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else EXP[LOG[a] + LOG[b]]


_GENERATORS: dict = {}


def generator(n: int) -> list:
    """Coefficients (highest degree first, leading 1 dropped) of
    (x - a^0)(x - a^1) ... (x - a^(n-1))."""
    if n not in _GENERATORS:
        poly = [1]
        for i in range(n):
            nxt = [0] * (len(poly) + 1)
            for j, c in enumerate(poly):
                nxt[j] ^= c
                nxt[j + 1] ^= gf_mul(c, EXP[i])
            poly = nxt
        _GENERATORS[n] = poly[1:]
    return _GENERATORS[n]


def rs_remainder(data: list, n_ec: int) -> list:
    """The `n_ec` Reed-Solomon error-correction codewords of `data`."""
    gen = generator(n_ec)
    rem = [0] * n_ec
    for byte in data:
        factor = byte ^ rem[0]
        rem = rem[1:] + [0]
        if factor:
            for i, g in enumerate(gen):
                rem[i] ^= gf_mul(g, factor)
    return rem


# ---- format and version information ----------------------------------------
EC_L_BITS = 1  # the two-bit level indicator of level L


def format_bits(mask: int, ec_bits: int = EC_L_BITS) -> int:
    """15 bits: BCH(15,5) of (level, mask), xor the fixed pattern 0x5412."""
    data = ec_bits << 3 | mask
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    return (data << 10 | rem) ^ 0x5412


def version_bits(version: int) -> int:
    """18 bits: BCH(18,6) of the version number (versions 7 and up)."""
    rem = version
    for _ in range(12):
        rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
    return version << 12 | rem


# ---- per-version tables, level L, versions 1..10 ---------------------------
# version -> (EC codewords per block, [(block count, data codewords per block), ...])
EC_L = {
    1: (7, [(1, 19)]),
    2: (10, [(1, 34)]),
    3: (15, [(1, 55)]),
    4: (20, [(1, 80)]),
    5: (26, [(1, 108)]),
    6: (18, [(2, 68)]),
    7: (20, [(2, 78)]),
    8: (24, [(2, 97)]),
    9: (30, [(2, 116)]),
    10: (18, [(2, 68), (2, 69)]),
}
ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38],
         8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}
MAX_VERSION = 10


def data_capacity(version: int) -> int:
    """Data codewords at level L."""
    return sum(n * d for n, d in EC_L[version][1])


def remainder_bits(version: int) -> int:
    return 7 if 2 <= version <= 6 else 0
