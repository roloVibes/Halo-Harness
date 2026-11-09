"""tests.test_engines_fit -- Halo 3.3.13.0 R1 deliverable 3 (the fit): the two generic rules of
halo_harness/engines/fit.py reproduce the verdicts the three folded fit modules gave on their own fixtures:

1. paged-moe with FreeToken's figures (local_sched/fit_ft.py's table: samus a 10 GB 3080 + 64 GB on Linux, pc a 24 GB
   4090 + 64 GB under WSL2, small an 8 GB 3060 + 32 GB): fits, no (RAM), tight, tight (the WSL pin cap), no, no
   (Windows), unknown (no counts) x2;
2. paged-moe with Strata's figures (fit_st.py's table, eleven sets and boxes: RAM + spare, the mapped "slower" case,
   DeepSeek's 12 GB card, Gyro's VRAM + RAM, NVFP4 off NVIDIA, Qwen3.6 off the Mac, no GPU);
3. vram with TensorFold's figures (fit_tf.py's table, twelve rows: the reserve, unified memory, CUDA-only and Metal-only
   models, two machines, the M1-M4 refusal, no size, an AMD card, no GPU) and the NVFP4 fallback words on sm_89;
4. the Library lists an engine's models as download targets (kind <id>) with its fit as the badge's why, only when the
   search names the engine or it is set up here.
Run: python -m tests.test_engines_fit
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MIB, GIB = 2 ** 20, 2 ** 30
LINUX, WSL, WIN = {"os": "linux", "arch": "x86_64"}, {"os": "linux", "arch": "x86_64", "wsl": True}, {"os": "windows",
                                                                                                       "arch": "amd64"}


def _card(gpu, mib: int, ram: int, lib: str = "CUDA", unified: bool = False, avail_mib=None) -> dict:
    g = {"id": "0", "name": gpu, "library": lib, "total_bytes": mib * MIB, **({"available_bytes": avail_mib * MIB}
                                                                                if avail_mib else {})}
    return {"gpus": [g] if gpu else [], "unified": unified, "ram_bytes": ram * GIB, "other_users": [], "server": {}}


PC, SAMUS, SMALL = (_card("NVIDIA GeForce RTX 4090", 24564, 64), _card("NVIDIA GeForce RTX 3080", 10240, 64),
                    _card("NVIDIA GeForce RTX 3060", 8192, 32))
MAC, AMD, CPU = (_card("Apple M3 Max", 65536, 64, "Metal", True, 49152), _card("AMD Radeon RX 7900 XTX", 24560, 64, "ROCm"),
                 _card(None, 0, 64))
FREETOKEN = [("nvidia/Qwen3.6-35B-A3B-NVFP4", SAMUS, LINUX, "fits"), ("Qwen/Qwen3.6-35B-A3B", SAMUS, LINUX, "no"),
             ("openai/gpt-oss-120b", SAMUS, LINUX, "tight"), ("openai/gpt-oss-120b", PC, WSL, "tight"),
             ("openai/gpt-oss-120b", SMALL, LINUX, "no"), ("nvidia/Qwen3.6-35B-A3B-NVFP4", PC, WIN, "no"),
             ("deepseek-ai/DeepSeek-V4.1-Flash", SAMUS, LINUX, "unknown"), ("Qwen/Qwen3.8-Flash-Next-FP8", SAMUS, LINUX,
                                                                             "unknown")]
STRATA = [("qwen/IQ3_XXS", PC, "fits"), ("unsloth/UD-Q4_K_XL", PC, "tight"), ("deepseek41/ist-das-2.00bpw", PC, "fits"),
          ("qwen/IQ3_XXS", SAMUS, "fits"), ("deepseek41/ist-das-2.00bpw", SAMUS, "no"), ("qwen/IQ3_XXS", SMALL, "tight"),
          ("qwen36/UD-Q4_K_XL", SMALL, "fits"), ("gyro/Gyro-M", SMALL, "no"), ("qwen36/UD-Q4_K_XL", MAC, "no"),
          ("nvfp4/NVFP4", AMD, "no"), ("qwen/Q2_0", CPU, "no")]
TENSORFOLD = [("TensorFold/Qwen3.8-27B-MLX-4bit", PC, "fits"), ("nvidia/Qwen3.6-35B-A3B-NVFP4", PC, "tight"),
              ("google/gemma-4-12B-it", PC, "no"), ("TensorFold/Qwen3.8-27B-MLX-4bit", SAMUS, "no"),
              ("nvidia/GLM-5.3-Flash-NVFP4", SMALL, "no"), ("TensorFold/Qwen3.8-27B-MLX-4bit", MAC, "fits"),
              ("TensorFold/Qwen3.6-35B-A3B-MLX-4bit-MTP", MAC, "no"), ("mlx-community/gemma-4-31B-it-4bit", MAC, "no"),
              ("BobClawblaw/MiniMax-M3.1-Flash-MLX-mix34", MAC, "no"),
              ("TensorFold/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-MLX-4bit", MAC, "unknown"),
              ("TensorFold/Qwen3.8-27B-MLX-4bit", AMD, "no"), ("TensorFold/Qwen3.8-27B-MLX-4bit", CPU, "no")]


def _fit(engine, model, card, facts=None, window=None):
    from halo_harness.engines.fit import fit, host_for
    from halo_harness.engines.models import match
    return fit(engine, match(engine, model), host_for("box", card, facts=facts), window=window)


@test
def test_paged_moe_with_freetokens_figures(ctx: Ctx):
    for model, card, facts, level in FREETOKEN:
        got = _fit("freetoken", model, card, facts)
        ctx.check(f"{model} on {card['gpus'][0]['name']} {facts}: {level}, got {got['level']} {got['line']!r}",
                  got["level"] == level and got["runtime"] == "freetoken")
    got = _fit("freetoken", "openai/gpt-oss-120b", PC, WSL)
    ctx.check(f"the WSL pin cap is said, got {got['line']!r}", got["line"].startswith("fits, slower: gpt-oss-120b on box")
              and "under WSL about 26 GB pins" in got["line"] and "PCIe at 32-64 GB/s" in got["line"])
    got = _fit("freetoken", "deepseek-ai/DeepSeek-V4.1-Flash", SAMUS, LINUX)
    ctx.check(f"no counts: the tables it states, got {got['line']!r}", "publishes no size" in got["line"]
              and "196 GB of tables stream from the SSD" in got["line"] and "6 GB stay in RAM" in got["line"])


@test
def test_paged_moe_with_stratas_figures(ctx: Ctx):
    for model, card, level in STRATA:
        got = _fit("strata", model, card)
        ctx.check(f"{model} on {(card['gpus'] or [{'name': 'no GPU'}])[0]['name']}: {level}, got {got['level']} "
                  f"{got['line']!r}", got["level"] == level)
    got = _fit("strata", "qwen/IQ3_XXS", SMALL)
    ctx.check(f"short of RAM: slower, from the SSD, got {got['line']!r}", got["line"].startswith("fits, slower:")
              and "read from the SSD" in got["line"] and "1 slot by the VRAM guide" in got["line"])
    got = _fit("strata", "qwen/IQ3_XXS", PC)
    ctx.check(f"the guide's slots, the table's speed and the download, got {got['line']!r}", "3 slots" in got["line"]
              and "expect 62 tok/s (RTX 5070 12 GB, 64 GB RAM)" in got["line"] and "strata launch --family qwen" in got["line"])


@test
def test_vram_with_tensorfolds_figures(ctx: Ctx):
    for model, card, level in TENSORFOLD:
        got = _fit("tensorfold", model, card)
        ctx.check(f"{model} on {(card['gpus'] or [{'name': 'no GPU'}])[0]['name']}: {level}, got {got['level']} "
                  f"{got['line']!r}", got["level"] == level)
    got = _fit("tensorfold", "TensorFold/Qwen3.8-27B-MLX-4bit", MAC)
    ctx.check(f"unified memory less the reserve, got {got['line']!r}", "48 GB of unified memory for the GPU, less "
              "TensorFold's 6.4 GB reserve, leaves 26 GB for the 32,768-token window" in got["line"])
    got = _fit("tensorfold", "nvidia/Qwen3.6-35B-A3B-NVFP4", PC)
    ctx.check(f"NVFP4 on sm_89: the fallback path, got {got['line']!r}", "sm_89) runs TensorFold's fallback path"
              in got["line"])
    from halo_harness.engines.fit import fit, host_for
    ctx.check("no card read: unknown", fit("tensorfold", None, host_for("x", None))["level"] == "unknown")


@test
def test_the_library_lists_an_engines_models_with_its_fit(ctx: Ctx):
    from tests.helpers.engine_home import EngineHome
    from halo_harness.models_library.browse import library
    with EngineHome() as h:
        got = library(h.state, source="hf", q="strata qwen36", host="box", window=32768)
        rows = [r for r in got["rows"] if r.get("kind") == "strata"]
        ctx.check(f"asked by name: the three Qwen3.6 sets, got {[r['id'] for r in rows]}", len(rows) == 3
                  and all(r["pull_line"].startswith("strata launch --family qwen36") for r in rows))
        ctx.check(f"the badge is the engine's fit, got {rows[0]['fit']}", rows[0]["fit"]["runtime"] == "strata"
                  and rows[0]["fit"]["level"] == "fits" and rows[0]["fit"]["why"].startswith("fits:"))
        got = library(h.state, source="hf", q="qwen3.6", host="box", window=32768)
        kinds = {r.get("kind") for r in got["rows"]}
        ctx.check(f"configured here (huggingface.engine_bins): listed, got {kinds}", {"freetoken", "tensorfold"} <= kinds)
        h.set_hf(engine_bins={})
        got = library(h.state, source="hf", q="qwen3.6", host="box", window=32768)
        ctx.check("not set up and not asked: no engine rows", not [r for r in got["rows"] if r.get("kind") in
                                                                    ("freetoken", "strata", "tensorfold")])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
