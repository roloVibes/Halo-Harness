"""tests.helpers.qr_decode -- a minimal QR reader for the encoder's round-trip
tests (Halo 2.0.9 round 4). It shares nothing with the encoder's maths: the
format strings are the published table, field arithmetic is carry-less
multiplication reduced by 0x11D, and the Reed-Solomon check evaluates every
block at the roots a^0 .. a^(n-1) (all zero = no error)."""
from __future__ import annotations

from halo_harness.remote import qr_tables as T
from halo_harness.remote.qr import _Grid

# Published format strings for level L, mask 0..7 (ISO 18004, 15 bits).
FORMAT_L = ("111011111000100", "111001011110011", "111110110101010", "111100010011101",
            "110011000101111", "110001100011000", "110110001000001", "110100101110110")
ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"


def _mul(a: int, b: int) -> int:
    out = 0
    while b:
        if b & 1:
            out ^= a
        a <<= 1
        if a & 0x100:
            a ^= 0x11D
        b >>= 1
    return out


def _alpha(i: int) -> int:
    v = 1
    for _ in range(i):
        v = _mul(v, 2)
    return v


def _syndromes_zero(block: list, n_ec: int) -> bool:
    for i in range(n_ec):
        x, acc = _alpha(i), 0
        for c in block:
            acc = _mul(acc, x) ^ c
        if acc:
            return False
    return True


def read_format(m: list) -> int:
    n = len(m)
    first = [m[i][8] for i in range(6)] + [m[7][8], m[8][8], m[8][7]] + [m[8][14 - i] for i in range(9, 15)]
    second = [m[8][n - 1 - i] for i in range(8)] + [m[n - 15 + i][8] for i in range(8, 15)]
    s1, s2 = "".join(str(b) for b in reversed(first)), "".join(str(b) for b in reversed(second))
    if s1 != s2 or s1 not in FORMAT_L:
        raise ValueError("format information unreadable")
    return FORMAT_L.index(s1)


def decode(m: list) -> str:
    n = len(m)
    version = (n - 17) // 4
    mask = read_format(m)
    from halo_harness.remote.qr import MASKS
    g = _Grid(version)
    g.functions(version)
    bits = []
    x, up = n - 1, True
    while x > 0:
        if x == 6:
            x -= 1
        for y in (range(n - 1, -1, -1) if up else range(n)):
            for xx in (x, x - 1):
                if not g.fn[y][xx]:
                    bits.append(m[y][xx] ^ (1 if MASKS[mask](y, xx) else 0))
        up = not up
        x -= 2
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits) - len(bits) % 8, 8)]
    n_ec, groups = T.EC_L[version]
    sizes = [d for cnt, d in groups for _ in range(cnt)]
    total_data = sum(sizes)
    blocks = [[] for _ in sizes]
    pos = 0
    for i in range(max(sizes)):
        for b, size in enumerate(sizes):
            if i < size:
                blocks[b].append(words[pos])
                pos += 1
    ecs = [[] for _ in sizes]
    for _ in range(n_ec):
        for b in range(len(sizes)):
            ecs[b].append(words[pos])
            pos += 1
    for b in range(len(sizes)):
        if not _syndromes_zero(blocks[b] + ecs[b], n_ec):
            raise ValueError("Reed-Solomon check failed")
    data = [w for b in blocks for w in b][:total_data]
    bs = "".join(f"{w:08b}" for w in data)
    mode, p = bs[:4], 4
    if mode == "0100":
        w = 8 if version <= 9 else 16
        count = int(bs[p:p + w], 2)
        p += w
        return bytes(int(bs[p + 8 * i:p + 8 * i + 8], 2) for i in range(count)).decode("utf-8")
    if mode == "0010":
        w = 9 if version <= 9 else 11
        count = int(bs[p:p + w], 2)
        p += w
        out = ""
        for _ in range(count // 2):
            v = int(bs[p:p + 11], 2)
            p += 11
            out += ALNUM[v // 45] + ALNUM[v % 45]
        if count % 2:
            out += ALNUM[int(bs[p:p + 6], 2)]
        return out
    raise ValueError("unknown mode " + mode)
