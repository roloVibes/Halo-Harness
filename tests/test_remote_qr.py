"""tests.test_remote_qr -- Halo 2.0.9 round 4: the stdlib QR encoder
(`halo_harness/remote/qr.py`, `qr_tables.py`). Pinned against published
vectors (the Reed-Solomon codewords of two well-known messages, the fifteen
format strings of level L, the version information words), checked
structurally (finders, timing, size per version), round-tripped through an
independent reader (tests/helpers/qr_decode.py, every version 1 to 10, both
modes), and its terminal rendering is checked cell by cell."""
from __future__ import annotations

import hashlib
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from halo_harness.remote import qr, qr_tables as T, signing
from tests.helpers.qr_decode import FORMAT_L, decode
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _digest(matrix: list) -> str:
    return hashlib.sha256("".join("".join(map(str, r)) for r in matrix).encode()).hexdigest()[:16]


@test
def test_reed_solomon_vectors(ctx: Ctx):
    hello = [0x20, 0x5B, 0x0B, 0x78, 0xD1, 0x72, 0xDC, 0x4D, 0x43, 0x40, 0xEC, 0x11, 0xEC, 0x11, 0xEC, 0x11]
    ctx.check("HELLO WORLD (1-M) error-correction codewords",
              T.rs_remainder(hello, 10) == [0xC4, 0x23, 0x27, 0x77, 0xEB, 0xD7, 0xE7, 0xE2, 0x5D, 0x17])
    iso = [0x10, 0x20, 0x0C, 0x56, 0x61, 0x80, 0xEC, 0x11, 0xEC, 0x11, 0xEC, 0x11, 0xEC, 0x11, 0xEC, 0x11]
    ctx.check("01234567 (ISO 18004 example) error-correction codewords",
              T.rs_remainder(iso, 10) == [0xA5, 0x24, 0xD4, 0xC1, 0xED, 0x36, 0xC7, 0x87, 0x2C, 0x55])
    ctx.check("the field has 255 distinct non-zero powers of 2", len(set(T.EXP[:255])) == 255 and T.EXP[8] == 0x1D)
    ctx.check("generator(7) is the published polynomial (exponents 87, 229, 146, 149, 238, 102, 21)",
              [T.LOG[c] for c in T.generator(7)] == [87, 229, 146, 149, 238, 102, 21])


@test
def test_alphanumeric_packing_vector(ctx: Ctx):
    seg = qr._segment("HELLO WORLD", 1)
    words = qr.data_codewords(seg, 16)
    ctx.check("HELLO WORLD packs to the published data codewords (1-M capacity)",
              words == [0x20, 0x5B, 0x0B, 0x78, 0xD1, 0x72, 0xDC, 0x4D, 0x43, 0x40, 0xEC, 0x11, 0xEC, 0x11, 0xEC, 0x11])
    ctx.check("lower case falls to byte mode", qr._segment("hello", 1).bits[:4] == [0, 1, 0, 0])


@test
def test_format_and_version_codes(ctx: Ctx):
    ctx.check("all eight level-L format strings match the published table",
              all(format(T.format_bits(m), "015b") == FORMAT_L[m] for m in range(8)))
    ctx.check("version information words 7 and 10", T.version_bits(7) == 0x07C94 and T.version_bits(10) == 0x0A4D3)
    ctx.check("capacities at level L (data codewords)",
              [T.data_capacity(v) for v in range(1, 11)] == [19, 34, 55, 80, 108, 136, 156, 194, 232, 274])
    ctx.check("total codewords per version are the published 26 .. 346",
              [sum(n * (d + T.EC_L[v][0]) for n, d in T.EC_L[v][1]) for v in range(1, 11)]
              == [26, 44, 70, 100, 134, 172, 196, 242, 292, 346])


@test
def test_structure(ctx: Ctx):
    m = qr.encode("HELLO WORLD")
    n = len(m)
    ctx.check("version 1 is 21 modules square", n == 21 and all(len(r) == 21 for r in m))
    finder = ["1111111", "1000001", "1011101", "1011101", "1011101", "1000001", "1111111"]
    for name, (x0, y0) in (("top-left", (0, 0)), ("top-right", (n - 7, 0)), ("bottom-left", (0, n - 7))):
        got = ["".join(str(m[y0 + y][x0 + x]) for x in range(7)) for y in range(7)]
        ctx.check(f"{name} finder pattern", got == finder)
    ctx.check("timing patterns alternate", all(m[6][i] == (i + 1) % 2 and m[i][6] == (i + 1) % 2 for i in range(8, n - 8)))
    ctx.check("the dark module is set", m[n - 8][8] == 1)
    ctx.check("encode is deterministic", qr.encode("HELLO WORLD") == m)
    sizes = {len(qr.encode("x" * k)) for k in (17, 18, 53, 54, 271)}
    ctx.check("sizes follow 4v+17", sizes == {21, 25, 29, 33, 57})
    ctx.check("272 bytes do not fit", _raises(lambda: qr.encode("x" * 272)))


def _raises(fn) -> bool:
    try:
        fn()
    except qr.QrTooLong:
        return True
    return False


@test
def test_pinned_matrices(ctx: Ctx):
    ctx.check("HELLO WORLD matrix digest", _digest(qr.encode("HELLO WORLD")) == "fd8287e68916269f")
    ctx.check("URL matrix digest", _digest(qr.encode("https://example.invalid/")) == "0be0c44ec6b0da27")
    uri = signing.pair_uri(bytes(range(32)), "00000000-0000-4000-8000-000000000001")
    ctx.check("a 157-byte pairing link is a version 8 code with a pinned digest",
              len(qr.encode(uri)) == 49 and _digest(qr.encode(uri)) == "f921d55058019149")


@test
def test_round_trip_through_an_independent_reader(ctx: Ctx):
    rng = random.Random(7)
    alphabet = "abcdefgh/:?&=-0123_%"
    for n in (1, 17, 18, 32, 33, 53, 54, 78, 79, 106, 107, 134, 135, 154, 155, 192, 193, 230, 231, 271):
        s = "".join(rng.choice(alphabet) for _ in range(n))
        try:
            ok = decode(qr.encode(s)) == s
        except ValueError:
            ok = False
        ctx.check(f"{n}-byte text round-trips (Reed-Solomon verified in every block)", ok)
    for s in ("HELLO WORLD", "A" * 100, "0123456789ABC", "SGNL://LINKDEVICE?UUID=ABC-DEF"):
        ctx.check(f"alphanumeric {s[:12]!r} round-trips", decode(qr.encode(s)) == s)
    ctx.check("non-ASCII text round-trips as UTF-8", decode(qr.encode("café ✓")) == "café ✓")
    uri = signing.pair_uri(bytes(range(32)), "00000000-0000-4000-8000-000000000001")
    ctx.check("the pairing link round-trips", decode(qr.encode(uri)) == uri)
    link = "sgnl://linkdevice?uuid=AAAAAAAAAAAAAAAAAAAAAA&pub_key=" + "B" * 60
    ctx.check("a linking URI round-trips", decode(qr.encode(link)) == link)


@test
def test_masks_are_chosen_by_penalty(ctx: Ctx):
    m = qr.encode("HELLO WORLD")
    ctx.check("the chosen matrix carries a readable format string", decode(m) == "HELLO WORLD")
    flat = [[0] * 21 for _ in range(21)]
    ctx.check("an all-light grid scores far worse than a code", qr.penalty(flat) > 5 * qr.penalty(m))


@test
def test_rendering(ctx: Ctx):
    m = qr.encode("HELLO WORLD")
    text = qr.render(m)
    lines = text.split("\n")
    ctx.check("half-block rows: (21 + 2*4) rounded up to pairs, so 15 lines", len(lines) == 15)
    ctx.check("every line is 29 cells wide", all(len(line) == 29 for line in lines))
    ctx.check("the quiet zone is light (full blocks)", set(lines[0]) == {"█"})
    top, bottom = m[0], m[1]
    row = lines[2]  # module rows 0 and 1 (quiet 4 = two text rows)
    want = "".join({(0, 0): "█", (1, 0): "▄", (0, 1): "▀", (1, 1): " "}[(top[c], bottom[c])]
                   for c in range(21))
    ctx.check("module rows 0 and 1 map to the right glyphs", row[4:25] == want)
    art = qr.render_ascii(m)
    ctx.check("ascii form is 2 columns per module with a 2-module quiet zone",
              len(art.split("\n")) == 25 and all(len(x) == 50 for x in art.split("\n")))
    ctx.check("render_text switches on ascii_only", qr.render_text("HELLO WORLD", ascii_only=True) == art)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
