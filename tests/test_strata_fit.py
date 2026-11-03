"""tests.test_strata_fit -- Halo 3.3.9.2 deliverable 4: the fit for a Strata server is FreeToken's RAM + link rule with
Strata's own figures (halo_harness/local_sched/fit_st.py, strata/catalog.py):

1. the table: Strata's sets on the fixture boxes (pc: a 24 GB 4090 and 64 GB on Windows; samus: a 10 GB 3080 and 64 GB
   on Linux; small: an 8 GB 3060 and 32 GB; a Mac with 64 GB unified; an AMD box; a box with no GPU) -> one
   deterministic line each: the slots by the VRAM guide, the experts against RAM, what streams from the SSD, the
   table's speed as the extrapolated figure, the download's GB; a set short of RAM is "fits, slower" (the SSD), a
   card under DeepSeek's 12 GB, NVFP4 off NVIDIA, Qwen3.6 on the Mac and a box with no GPU are out;
2. the VRAM guide (12 GB runs 1, 20 GB 2, 24 GB 3, 32 GB and more 4);
3. `halo local bench --host strata --yes --quick` against the fake server (the cost line first) keeps a card under the
   set's name, and the fit then says "measured";
4. the Library lists Strata's sets as download targets (kind strata, the `strata launch` command the user runs) with
   the Strata fit as the badge's why; they stay out of a search that does not name Strata when it is not set up.
Run: python -m tests.test_strata_fit
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.st_home import StHome  # noqa: E402

test, TESTS = new_registry()
MIB, GIB = 2 ** 20, 2 ** 30
FN, T5070 = "Qwen3.8-Flash-Next", "RTX 5070 12 GB, 64 GB RAM (engine 0.1.26, short chat)"
NOT_HERE = "not measured here yet"


def _card(gpu, mib: int, ram: int, lib: str = "CUDA", unified: bool = False) -> dict:
    return {"gpus": [{"id": "0", "name": gpu, "library": lib, "total_bytes": mib * MIB}] if gpu else [],
            "unified": unified, "ram_bytes": ram * GIB, "other_users": [], "server": {}}


PC, SAMUS, SMALL = (_card("NVIDIA GeForce RTX 4090", 24564, 64), _card("NVIDIA GeForce RTX 3080", 10240, 64),
                    _card("NVIDIA GeForce RTX 3060", 8192, 32))
MAC, AMD, CPU = _card("Apple M3 Max", 49152, 64, "Metal", True), _card("AMD Radeon RX 7900 XTX", 24560, 64, "ROCm"), \
    _card(None, 0, 64)
TABLE = [
    ("qwen/IQ3_XXS", "pc", PC, "windows", "fits",
     f"fits: {FN} IQ3_XXS on pc: 3 slots on the 4090 (the VRAM guide: 24 GB runs 3), 43 GB of experts in 64 GB of RAM, "
     f"its 29 GB n-gram table streams from the SSD; expect 62 tok/s class (Strata's table: {T5070}), {NOT_HERE}; the "
     "first launch downloads 76 GB (yours to run)"),
    ("unsloth/UD-Q4_K_XL", "pc", PC, "windows", "tight",
     f"fits, slower: {FN} UD-Q4_K_XL on pc: 3 slots on the 4090 (the VRAM guide: 24 GB runs 3), every expert needs ~88 "
     "GB of RAM, 64 GB here, so Strata keeps what fits and reads the rest from the SSD, its 29 GB n-gram table streams "
     f"from the SSD; expect 63 tok/s class (Strata's table: Radeon AI PRO R9700 32 GB), {NOT_HERE}; the first launch "
     "downloads 111 GB (yours to run)"),
    ("deepseek41/ist-das-2.00bpw", "pc", PC, "windows", "fits",
     "fits: DeepSeekV4.1-Flash-1017 ist-das-2.00bpw on pc: 1 slot on the 4090 (DeepSeek answers one at a time), 64 GB of "
     "RAM (46 GB at least, 64 GB the tested size); what does not fit is read from the SSD -- keep about 257 GB free on an "
     f"NVMe; expect 4 to 6 tok/s class (Strata's table: RTX 5070 12 GB, 64 GB RAM (2.00 bpw)), {NOT_HERE}; the first "
     "launch downloads 257 GB (yours to run)"),
    ("qwen/IQ3_XXS", "samus", SAMUS, "linux", "fits",
     f"fits: {FN} IQ3_XXS on samus: 1 slot on the 3080 (the VRAM guide: 10 GB runs 1), 43 GB of experts in 64 GB of RAM,"
     f" its 29 GB n-gram table streams from the SSD; expect 62 tok/s class (Strata's table: {T5070}), {NOT_HERE}; the "
     "first launch downloads 76 GB (yours to run)"),
    ("deepseek41/ist-das-2.00bpw", "samus", SAMUS, "linux", "no",
     "does not fit: DeepSeekV4.1-Flash-1017 ist-das-2.00bpw needs a 12 GB card or more, 10 GB on the 3080"),
    ("qwen/IQ3_XXS", "small", SMALL, "linux", "tight",
     f"fits, slower: {FN} IQ3_XXS on small: 1 slot on the 3060 (the VRAM guide: 8 GB runs 1), 43 GB of experts against "
     "32 GB of RAM, so Strata maps them from the model files and reads what RAM cannot hold from the SSD, its 29 GB "
     f"n-gram table streams from the SSD; expect 62 tok/s class (Strata's table: {T5070}), {NOT_HERE}; the first launch "
     "downloads 76 GB (yours to run)"),
    ("qwen36/UD-Q4_K_XL", "small", SMALL, "linux", "fits",
     "fits: Qwen3.6-35B-A3B UD-Q4_K_XL on small: 1 slot on the 3060 (the VRAM guide: 8 GB runs 1), Strata plans 32 GB of "
     f"RAM, 32 GB here; expect 59.7 tok/s class (Strata's table: RTX 3060 12 GB, most experts on the CPU), {NOT_HERE}; "
     "the first launch downloads 22.9 GB (yours to run)"),
    ("gyro/Gyro-M", "small", SMALL, "linux", "no",
     f"does not fit: {FN} Gyro-M needs 35 GB of VRAM + RAM together plus about 10 GB, 40 GB here"),
    ("qwen36/UD-Q4_K_XL", "mac", MAC, "macos", "no", "does not fit: Strata's Mac engine does not run Qwen3.6-35B-A3B "
     "UD-Q4_K_XL"),
    ("nvfp4/NVFP4", "amd", AMD, "linux", "no", f"does not fit: {FN} NVFP4 runs on NVIDIA cards only (amd has the RX 7900 "
     "XTX)"),
    ("qwen/Q2_0", "cpu", CPU, "linux", "no", "does not fit: Strata runs on a graphics card (cpu has none on its card: "
     "NVIDIA RTX 20-50, AMD Radeon RX 7000 / 9000, Apple Silicon)"),
]


def _local(*argv) -> "tuple[int, str]":
    from halo_harness.local_cli import cmd_local
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cmd_local(list(argv))
    return code, out.getvalue()


@test
def test_the_fit_table(ctx: Ctx):
    from halo_harness.local_sched.fit_st import fit, host_for
    from halo_harness.strata.catalog import parse
    for set_, name, card, os_name, level, line in TABLE:
        got = fit(parse(set_), host_for(name, card, os_name=os_name))
        ctx.check(f"{set_} on {name}: {level}, got {got['level']} {got['line']!r}", got["level"] == level
                  and got["line"] == line and got["runtime"] == "strata")
    got = fit(parse("qwen/IQ3_XXS"), host_for("nobody", None))
    ctx.check(f"no card read: unknown, said, got {got['line']!r}", got["level"] == "unknown"
              and "no hardware card read yet" in got["line"])
    mac = fit(parse("qwen/IQ3_XXS"), host_for("mac", MAC, os_name="macos"))
    ctx.check(f"the Mac's unified memory, got {mac['line'][:90]!r}", mac["level"] == "fits"
              and "4 slots on unified memory" in mac["line"])


@test
def test_the_vram_guide(ctx: Ctx):
    from halo_harness.local_sched.fit_st import slots
    got = [slots(v) for v in (8, 12, 16, 20, 23.99, 24, 31, 32, 48)]
    ctx.check(f"12 GB runs 1, 20 GB 2, 24 GB 3, 32 GB and more 4, got {got}", got == [1, 1, 1, 2, 3, 3, 3, 4, 4])


@test
def test_the_bench_card_makes_the_fit_measured(ctx: Ctx):
    from halo_harness.local_sched.fit_st import here_line
    from halo_harness.strata.catalog import parse
    with StHome() as h:
        ctx.check("before a bench: the table's figure", NOT_HERE in here_line(parse("qwen/IQ3_XXS"), h.state))
        _local("serve", "--runtime", "strata", "--model", "qwen/IQ3_XXS")
        code, out = _local("bench", "--host", "strata", "--yes", "--quick")
        lines = out.strip().splitlines()
        ctx.check(f"the cost line first, then the card, got {code} {out[:400]!r}", code == 0 and lines[0].startswith(
            "local: ~") and "on strata (its GPU, CPU and the SSD are busy for it)" in lines[0]
                  and "speed card: 1 windows" in out and "the first request after a start fills" in out)
        line = here_line(parse("qwen/IQ3_XXS"), h.state)
        ctx.check(f"after the bench: measured, got {line!r}", line.startswith("fit here: fits: Qwen3.8-Flash-Next IQ3_XXS "
                                                                           "on this machine") and "tok/s measured" in line
                  and NOT_HERE not in line)
        ctx.check("another set is not measured by this card", NOT_HERE in here_line(parse("qwen/Q2_0"), h.state))


@test
def test_the_library_lists_stratas_sets_with_its_fit(ctx: Ctx):
    from halo_harness.models_library.browse import library
    with StHome() as h:
        got = library(h.state, source="hf", q="strata iq3", host="box", window=32768)
        rows = [r for r in got["rows"] if r.get("kind") == "strata"]
        ids = sorted(r["id"] for r in rows)
        ctx.check(f"the IQ3 sets, got {ids}", ids == ["strata:qwen/IQ3_S", "strata:qwen/IQ3_XXS"])
        r = next(x for x in rows if x["id"] == "strata:qwen/IQ3_XXS")
        ctx.check(f"a download target the user runs, with the Strata fit, got {r['pull_line']!r} {r['fit']}",
                  r["pull_line"].startswith("strata launch --family qwen --model IQ3_XXS --yes --no-tui --access local")
                  and "yours to run" in r["pull_line"] and r["size_bytes"] == 76 * 10 ** 9 and r["fit"]["level"] == "fits"
                  and r["fit"]["runtime"] == "strata" and r["fit"]["why"].startswith(
                      "fits: Qwen3.8-Flash-Next IQ3_XXS on box: 3 slots on a 24 GB card"))
        h.set_hf(strata_bin=None)
        got = library(h.state, source="hf", q="iq3", host="box", window=32768)
        ctx.check("not set up and not asked: no Strata rows", not [r for r in got["rows"] if r.get("kind") == "strata"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
