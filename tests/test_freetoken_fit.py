"""tests.test_freetoken_fit -- Halo 3.3.9.1 deliverable 4: the fit for a FreeToken server is RAM + link, not VRAM
(halo_harness/local_sched/fit_ft.py, freetoken/{catalog,shape,link}.py):

1. the table: catalog checkpoints on the fixture boxes (samus: a 10 GB RTX 3080 and 64 GB of RAM on Linux; pc: a 24 GB
   4090 and 64 GB under WSL2; small: an 8 GB 3060 and 32 GB) -> one deterministic line each, the link measured or
   extrapolated, the WSL pin cap, the tables FreeToken states, a Windows box out;
2. a checkpoint folder's config.json and safetensors index -> the dense / expert / KV split, and the fit from it;
3. `halo local bench --bw --yes` runs `ft bench bw` (the fake) with the cost line first, saves the link, and the fit
   then says "measured";
4. the Library lists FreeToken's checkpoints as download targets (kind freetoken, `halo local download <repo>`) with
   the FreeToken fit as the badge's why; they stay out of a search that does not name FreeToken when it is not set up.
Run: python -m tests.test_freetoken_fit
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.ft_home import LINUX, QWEN36, QWEN36_BYTES, FtHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MIB, GIB = 2 ** 20, 2 ** 30
EXTRA = "PCIe at 32-64 GB/s extrapolated (FreeToken's figure; halo local bench --host freetoken --bw measures it)"
WSL = {**LINUX, "wsl": True}
WIN = {"os": "windows", "arch": "amd64", "linux": False, "x86": True, "wsl": False}


def _card(gpu: str, mib: int, ram_gib: int) -> dict:
    return {"gpus": [{"id": "0", "name": gpu, "library": "CUDA", "total_bytes": mib * MIB}], "unified": False,
            "ram_bytes": ram_gib * GIB, "other_users": [], "server": {}}


SAMUS, PC, SMALL = _card("NVIDIA GeForce RTX 3080", 10240, 64), _card("NVIDIA GeForce RTX 4090", 24564, 64), \
    _card("NVIDIA GeForce RTX 3060", 8192, 32)
TABLE = [
    ("nvidia/Qwen3.6-35B-A3B-NVFP4", "samus", SAMUS, LINUX, 27.9, "fits",
     "fits: Qwen3.6-35B-A3B on samus, 1.6 GB active on the 3080, 17 GB of experts in RAM over PCIe at 27.9 GB/s "
     "measured; speed not measured yet"),
    ("Qwen/Qwen3.6-35B-A3B", "samus", SAMUS, LINUX, None, "no",
     "does not fit: Qwen3.6-35B-A3B needs 60 GB of experts in RAM, 64 GB on samus (58 GB usable)"),
    ("openai/gpt-oss-120b", "samus", SAMUS, LINUX, None, "tight",
     f"fits, tight: gpt-oss-120b on samus, 2.5 GB active on the 3080, 55 GB of experts in RAM over {EXTRA}; little "
     "RAM is left for the rest of the machine; speed not measured yet"),
    ("openai/gpt-oss-120b", "pc", PC, WSL, None, "tight",
     f"fits, slower: gpt-oss-120b on pc, 2.5 GB active on the 4090, 55 GB of experts in RAM over {EXTRA}; under WSL "
     "about 26 GB pins (FreeToken budgets 40 % of RAM), the rest decodes on the CPU (--moe-cpu-layers auto); speed not "
     "measured yet"),
    ("openai/gpt-oss-120b", "small", SMALL, LINUX, None, "no",
     "does not fit: gpt-oss-120b needs 55 GB of experts in RAM, 32 GB on small (29 GB usable)"),
    ("nvidia/Qwen3.6-35B-A3B-NVFP4", "pc", PC, WIN, None, "no",
     "does not fit: FreeToken runs on Linux x86_64 (pc is windows; on Windows, WSL2 runs it with the pinned-memory cap)"),
    ("deepseek-ai/DeepSeek-V4.1-Flash", "samus", SAMUS, LINUX, None, "unknown",
     "DeepSeek-V4.1-Flash on samus: its dense and expert sizes are not known yet (download it: its config.json and "
     "files split them); its 196 GiB of tables stream from NVMe and 6 GiB stay in RAM"),
    ("Qwen/Qwen3.8-Flash-Next-FP8", "samus", SAMUS, LINUX, None, "unknown",
     "Qwen3.8-Flash-Next on samus: its dense and expert sizes are not known yet (download it: its config.json and "
     "files split them); its 47.7 GiB table stays pinned in RAM"),
]


def _local(*argv) -> "tuple[int, str]":
    from halo_harness.local_cli import cmd_local
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cmd_local(list(argv))
    return code, out.getvalue()


@test
def test_the_fit_table_on_the_fixture_boxes(ctx: Ctx):
    from halo_harness.freetoken.catalog import get
    from halo_harness.freetoken.shape import of_row
    from halo_harness.local_sched.fit_ft import fit, host_from_card
    with FtHome():
        for repo, host, card, facts, gbs, level, line in TABLE:
            got = fit(of_row(get(repo)), host_from_card(host, card, facts=facts, link_gbs=gbs), window=32768)
            ctx.check(f"{repo} on {host} ({facts['os']}{' WSL' if facts.get('wsl') else ''}): {level}, got "
                      f"{got['level']} {got['line']!r}", got["level"] == level and got["line"] == line)


@test
def test_a_checkpoint_folder_splits_from_its_config(ctx: Ctx):
    from halo_harness.freetoken.shape import of_dir
    from halo_harness.local_sched.fit_ft import fit, host_from_card
    with FtHome() as h:
        sh = of_dir(h.checkpoint())
        ctx.check(f"the split from config.json + the index, got {sh}", sh["format"] == "nvfp4"
                  and sh["total_bytes"] == QWEN36_BYTES and sh["expert_bytes"] == 40 * 256 * 3 * 2048 * 512 * 0.5625
                  and sh["dense_bytes"] == QWEN36_BYTES - sh["expert_bytes"] and sh["kv_per_token"] == 2 * 10 * 2 * 256 * 2
                  and sh["layer_expert_bytes"] == sh["expert_bytes"] // 40)
        got = fit(sh, host_from_card("samus", SAMUS, facts=LINUX, link_gbs=27.9))
        ctx.check(f"it fits samus with the KV at 32k counted, got {got['line']!r}", got["level"] == "fits"
                  and got["numbers"]["kv"] == 20480 * 32768 and got["line"].startswith(
                      "fits: Qwen3.6-35B-A3B-NVFP4 on samus, 1.6 GB active on the 3080, 17 GB of experts"))
        big = dict(QWEN36, moe_intermediate_size=4096)
        got = fit(of_dir(h.checkpoint("Wide-MoE", big, total=160 * 10 ** 9)), host_from_card("samus", SAMUS, facts=LINUX))
        ctx.check(f"a layer of experts too wide for the card is out, got {got['line']!r}", got["level"] == "no"
                  and "one layer of experts" in got["line"] and "on the 3080" in got["line"])


@test
def test_ft_bench_bw_measures_the_link_the_fit_reads(ctx: Ctx):
    from halo_harness.freetoken.link import measured, parse
    from halo_harness.freetoken.catalog import get
    from halo_harness.freetoken.shape import of_row
    from halo_harness.local_sched.fit_ft import fit, host_from_card
    with FtHome() as h:
        ctx.check("nothing measured yet", measured(h.state) is None)
        code, out = _local("bench", "--bw", "--yes")
        lines = out.strip().splitlines()
        ctx.check(f"the cost line first, then the link, got {code} {out!r}", code == 0 and lines[0].startswith(
            "local: ~120 s on this machine (the GPU and the CPU are busy for it)") and "no tokens, no network" in lines[0]
            and lines[-1] == "the link: PCIe-gather 27.9 GB/s (linear H2D 24.6, CPU STREAM read 41.0 GB/s)")
        m = measured(h.state)
        ctx.check(f"the link saved, got {m}", m and m["gbs"] == 27.9 and m["from"] == "PCIe-gather"
                  and m["argv"][-2:] == ["bench", "bw"])
        got = fit(of_row(get("nvidia/Qwen3.6-35B-A3B-NVFP4")), host_from_card("samus", SAMUS, facts=LINUX), state_dir=h.state)
        ctx.check(f"the fit says measured, got {got['line']!r}", "over PCIe at 27.9 GB/s measured" in got["line"]
                  and got["link_gbs"] == 27.9)
        ctx.check("a report with no PCIe row falls back to the H2D ceiling",
                  parse("  ceilings: CPU STREAM read 30.0  |  PCIe linear H2D 12.5  D2H 12.0  GB/s")["h2d_gbs"] == 12.5)


@test
def test_the_library_lists_freetokens_checkpoints_with_its_fit(ctx: Ctx):
    from halo_harness.freetoken import requirements
    from halo_harness.models_library.browse import library
    with FtHome() as h:
        requirements.SEAMS["platform"] = lambda: dict(LINUX)
        got = library(h.state, source="hf", q="qwen3.6", host="box", window=32768)
        rows = [r for r in got["rows"] if r.get("kind") == "freetoken"]
        ids = sorted(r["id"] for r in rows)
        ctx.check(f"the three Qwen3.6 checkpoints, got {ids}", ids == ["Qwen/Qwen3.6-35B-A3B", "Qwen/Qwen3.6-35B-A3B-FP8",
                                                                        "nvidia/Qwen3.6-35B-A3B-NVFP4"])
        nv = next(r for r in rows if r["id"] == "nvidia/Qwen3.6-35B-A3B-NVFP4")
        ctx.check(f"a download target with the FreeToken fit, got {nv['pull_line']!r} {nv['fit']}", nv["pull_line"] ==
                  "halo local download nvidia/Qwen3.6-35B-A3B-NVFP4" and nv["fit"]["level"] == "fits"
                  and nv["fit"]["runtime"] == "freetoken" and nv["fit"]["why"].startswith(
                      "fits: Qwen3.6-35B-A3B on box, 1.6 GB active on a 24 GB card, 17 GB of experts in RAM"))
        bf = next(r for r in rows if r["id"] == "Qwen/Qwen3.6-35B-A3B")
        ctx.check(f"BF16 needs more RAM than the box, got {bf['fit']['why']!r}", bf["fit"]["level"] == "no"
                  and "60 GB of experts in RAM, 64 GB on box" in bf["fit"]["why"])
        h.set_hf(freetoken_bin=None)
        got = library(h.state, source="hf", q="qwen3.6", host="box", window=32768)
        ctx.check("not set up and not asked: no FreeToken rows", not [r for r in got["rows"] if r.get("kind") == "freetoken"])
        got = library(h.state, source="hf", q="freetoken gpt-oss", host="box", window=32768)
        ctx.check(f"asked by name: listed, got {[r['id'] for r in got['rows'] if r.get('kind') == 'freetoken']}",
                  sorted(r["id"] for r in got["rows"] if r.get("kind") == "freetoken") == ["openai/gpt-oss-120b",
                                                                                         "openai/gpt-oss-20b"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
