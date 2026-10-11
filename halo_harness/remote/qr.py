"""halo_harness.remote.qr -- a small QR Code encoder (Halo 2.0.9 round 4),
standard library only, written for the one job the remote-control CLI has:
turning a `sgnl://linkdevice` or `halo-remote://pair` URI into something a
phone camera reads off a terminal.

* byte mode (UTF-8) and alphanumeric mode, picked automatically
* error-correction level L, versions 1 to 10 (up to 271 bytes)
* the eight masks tried and the lowest penalty score kept
* `render()` draws the matrix with half-block glyphs (two module rows per
  text row); `render_ascii()` is the plain `#` form

`encode(text)` returns the matrix as a list of rows of 0/1 (1 = dark).
The Reed-Solomon field, generator polynomials and BCH codes are computed in
`qr_tables.py`; the codes are pinned in tests/test_remote_qr.py against
published vectors.
"""

from __future__ import annotations

from halo_harness.remote import qr_tables as T
from halo_harness.remote.qr_render import QUIET, render, render_ascii  # noqa: F401  (re-exported)

ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"


class QrTooLong(ValueError):
    pass


class _Bits:
    def __init__(self) -> None:
        self.bits: list = []

    def put(self, value: int, count: int) -> None:
        self.bits.extend((value >> i) & 1 for i in range(count - 1, -1, -1))


def _segment(text: str, version: int) -> "_Bits":
    out = _Bits()
    if text and all(c in ALNUM for c in text):
        out.put(0b0010, 4)
        out.put(len(text), 9 if version <= 9 else 11)
        for i in range(0, len(text) - 1, 2):
            out.put(ALNUM.index(text[i]) * 45 + ALNUM.index(text[i + 1]), 11)
        if len(text) % 2:
            out.put(ALNUM.index(text[-1]), 6)
    else:
        raw = text.encode("utf-8")
        out.put(0b0100, 4)
        out.put(len(raw), 8 if version <= 9 else 16)
        for b in raw:
            out.put(b, 8)
    return out


def data_codewords(seg: "_Bits", capacity: int) -> list:
    """Terminator, byte padding and the alternating EC/11 pad bytes."""
    bits = list(seg.bits)
    room = capacity * 8
    bits.extend([0] * min(4, room - len(bits)))
    bits.extend([0] * (-len(bits) % 8))
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = (0xEC, 0x11)
    while len(words) < capacity:
        words.append(pad[(len(words) - len(bits) // 8) % 2])
    return words


def _choose(text: str) -> tuple:
    for version in range(1, T.MAX_VERSION + 1):
        seg = _segment(text, version)
        if len(seg.bits) <= T.data_capacity(version) * 8:
            return version, seg
    raise QrTooLong(f"{len(text.encode('utf-8'))} bytes do not fit a version {T.MAX_VERSION} QR code at level L")


def interleave(version: int, words: list) -> list:
    """Split into blocks, add each block's EC codewords, interleave."""
    n_ec, groups = T.EC_L[version]
    blocks, pos = [], 0
    for count, size in groups:
        for _ in range(count):
            blocks.append(words[pos:pos + size])
            pos += size
    ecs = [T.rs_remainder(b, n_ec) for b in blocks]
    out = []
    for i in range(max(len(b) for b in blocks)):
        out.extend(b[i] for b in blocks if i < len(b))
    for i in range(n_ec):
        out.extend(e[i] for e in ecs)
    return out


class _Grid:
    def __init__(self, version: int) -> None:
        self.size = 4 * version + 17
        self.m = [[0] * self.size for _ in range(self.size)]
        self.fn = [[False] * self.size for _ in range(self.size)]

    def set(self, x: int, y: int, dark: int, fn: bool = True) -> None:
        if 0 <= x < self.size and 0 <= y < self.size:
            self.m[y][x] = 1 if dark else 0
            if fn:
                self.fn[y][x] = True

    def finder(self, cx: int, cy: int) -> None:
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                d = max(abs(dx), abs(dy))
                self.set(cx + dx, cy + dy, d not in (2, 4))

    def alignment(self, cx: int, cy: int) -> None:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                self.set(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)

    def format(self, mask: int) -> None:
        bits, n = T.format_bits(mask), self.size
        bit = lambda i: (bits >> i) & 1  # noqa: E731
        for i in range(6):
            self.set(8, i, bit(i))
        self.set(8, 7, bit(6))
        self.set(8, 8, bit(7))
        self.set(7, 8, bit(8))
        for i in range(9, 15):
            self.set(14 - i, 8, bit(i))
        for i in range(8):
            self.set(n - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self.set(8, n - 15 + i, bit(i))
        self.set(8, n - 8, 1)  # the always-dark module

    def functions(self, version: int) -> None:
        n = self.size
        for i in range(n):
            self.set(6, i, i % 2 == 0)
            self.set(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
            self.finder(cx, cy)
        pos = T.ALIGN[version]
        for i, cy in enumerate(pos):
            for j, cx in enumerate(pos):
                if not ((i == 0 and j == 0) or (i == 0 and j == len(pos) - 1) or (i == len(pos) - 1 and j == 0)):
                    self.alignment(cx, cy)
        self.format(0)
        if version >= 7:
            bits = T.version_bits(version)
            for i in range(18):
                a, b = n - 11 + i % 3, i // 3
                self.set(a, b, (bits >> i) & 1)
                self.set(b, a, (bits >> i) & 1)

    def place(self, codewords: list, rem_bits: int) -> None:
        bits = [(w >> i) & 1 for w in codewords for i in range(7, -1, -1)] + [0] * rem_bits
        n, k, up = self.size, 0, True
        x = n - 1
        while x > 0:
            if x == 6:
                x -= 1
            rows = range(n - 1, -1, -1) if up else range(n)
            for y in rows:
                for dx in (0, 1):
                    xx = x - dx
                    if not self.fn[y][xx] and k < len(bits):
                        self.m[y][xx] = bits[k]
                        k += 1
            up = not up
            x -= 2


MASKS = (
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
)


def _masked(grid: "_Grid", mask: int) -> list:
    f = MASKS[mask]
    return [[grid.m[r][c] ^ (1 if (not grid.fn[r][c] and f(r, c)) else 0) for c in range(grid.size)]
            for r in range(grid.size)]


def penalty(m: list) -> int:
    n, score = len(m), 0
    for lines in (m, [list(col) for col in zip(*m)]):
        for line in lines:
            run = 1
            for i in range(1, n + 1):
                if i < n and line[i] == line[i - 1]:
                    run += 1
                    continue
                if run >= 5:
                    score += 3 + run - 5
                run = 1
            s = "".join(map(str, line))
            score += 40 * (s.count("10111010000") + s.count("00001011101"))
    for r in range(n - 1):
        for c in range(n - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    dark = sum(map(sum, m))
    return score + 10 * (abs(dark * 20 - n * n * 10) // (n * n))


def encode(text: str) -> list:
    """The QR matrix of `text` (rows of 0/1, 1 = dark module)."""
    version, seg = _choose(text)
    words = interleave(version, data_codewords(seg, T.data_capacity(version)))
    grid = _Grid(version)
    grid.functions(version)
    grid.place(words, T.remainder_bits(version))
    best = None
    for mask in range(8):
        cand = _Grid(version)
        cand.m = [row[:] for row in _masked(grid, mask)]
        cand.fn = grid.fn
        cand.format(mask)
        score = penalty(cand.m)
        if best is None or score < best[0]:
            best = (score, cand.m)
    return best[1]


def render_text(text: str, ascii_only: bool = False) -> str:
    m = encode(text)
    return render_ascii(m) if ascii_only else render(m)
