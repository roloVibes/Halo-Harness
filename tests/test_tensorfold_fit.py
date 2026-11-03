"""tests.test_tensorfold_fit -- Halo 3.3.9.3 deliverable 4: the fit for a TensorFold server is the ordinary VRAM rule
with TensorFold's own figures (halo_harness/local_sched/fit_tf.py, tensorfold/catalog.py):

1. the table: TensorFold's qualified models on the fixture boxes (pc: a 24 GB 4090 and 64 GB on Windows; samus: a 10
   GB 3080 and 64 GB on Linux; small: an 8 GB 3060; a Mac with 64 GB unified, 48 GB of it for the GPU; an AMD box; a
   box with no GPU) -> one deterministic line each: the checkpoint's size, the card or unified budget, TensorFold's
   reserve, what is left for the window and the streams, the download the user runs; a model qualified on CUDA only is
   out on the Mac and one qualified on Metal only is out on NVIDIA, a two-machine model is out on one, Gemma 4 is out on
   an M1-M4 Mac, NVFP4 on an sm_89 card says the fallback path; no size published: unknown, `tensorfold info` said;
2. `halo local serve --runtime tensorfold` prints the fit here;
3. the Library lists TensorFold's models as download targets (kind tensorfold, the `tensorfold pull` line the user runs)
   with the TensorFold fit as the badge's why; they stay out of a search that does not name TensorFold when it is not
   set up.
Run: python -m tests.test_tensorfold_fit
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.tf_home import REPO, TfHome  # noqa: E402

test, TESTS = new_registry()
MIB, GIB = 2 ** 20, 2 ** 30


def _card(gpu, mib: int, ram: int, lib: str = "CUDA", unified: bool = False, avail_mib=None) -> dict:
    g = {"id": "0", "name": gpu, "library": lib, "total_bytes": mib * MIB}
    if avail_mib:
        g["available_bytes"] = avail_mib * MIB
    return {"gpus": [g] if gpu else [], "unified": unified, "ram_bytes": ram * GIB, "other_users": [], "server": {}}


PC, SAMUS, SMALL = (_card("NVIDIA GeForce RTX 4090", 24564, 64), _card("NVIDIA GeForce RTX 3080", 10240, 64),
                    _card("NVIDIA GeForce RTX 3060", 8192, 32))
MAC = _card("Apple M3 Max", 65536, 64, lib="Metal", unified=True, avail_mib=49152)
AMD, NOGPU = _card("AMD Radeon RX 7900 XTX", 24560, 64, lib="ROCm"), _card(None, 0, 32)
Q27, Q36N, Q36M = "TensorFold/Qwen3.8-27B-MLX-4bit", "nvidia/Qwen3.6-35B-A3B-NVFP4", "TensorFold/Qwen3.6-35B-A3B-MLX-4bit-MTP"
TABLE = (
    ("pc", PC, "windows", Q27, "fits", "fits: Qwen3.8-27B MLX 4-bit (16 GiB) on pc: the 4090's 24 GB, less TensorFold's "
     "1.0 GB reserve, leaves 7.0 GB for the 32,768-token window's KV and its streams"),
    ("pc", PC, "windows", Q36N, "tight", "fits, tight: Qwen3.6-35B-A3B NVFP4 (20.9 GiB) on pc: the 4090's 24 GB, less "
     "TensorFold's 1.0 GB reserve, leaves 2.1 GB"),
    ("pc", PC, "windows", "google/gemma-4-12B-it", "no", "does not fit: TensorFold qualifies Gemma 4 12B (converted MLX "
     "4-bit) on Metal (a Mac) only"),
    ("samus", SAMUS, "linux", Q27, "no", "does not fit: Qwen3.8-27B MLX 4-bit (16 GiB) needs 17 GB with TensorFold's 1.0 GB "
     "reserve; samus has the 3080's 10 GB"),
    ("small", SMALL, "linux", "nvidia/GLM-5.3-Flash-NVFP4", "no", "does not fit: TensorFold qualifies GLM-5.3-Flash NVFP4 "
     "across two machines (two GB10s at TP=2), not on one"),
    ("mac", MAC, "macos", Q27, "fits", "fits: Qwen3.8-27B MLX 4-bit (16 GiB) on mac: 48 GB of unified memory for the GPU, "
     "less TensorFold's 6.4 GB reserve, leaves 26 GB for the 32,768-token window's KV and its streams"),
    ("mac", MAC, "macos", Q36M, "no", "does not fit: TensorFold qualifies Qwen3.6-35B-A3B MLX 4-bit MTP on CUDA only (one "
     "GB10; native CUDA)"),
    ("mac", MAC, "macos", "mlx-community/gemma-4-31B-it-4bit", "no", "does not fit: TensorFold refuses Gemma 4 31B MLX "
     "4-bit on an M1-M4 Mac"),
    ("mac", MAC, "macos", "BobClawblaw/MiniMax-M3.1-Flash-MLX-mix34", "no", "does not fit: MiniMax-M3.1-Flash MLX mix34 "
     "(203.7 GiB) needs 210 GB with TensorFold's 6.4 GB reserve; mac has 48 GB of unified memory for the GPU"),
    ("mac", MAC, "macos", "TensorFold/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-MLX-4bit", "unknown", "Nemotron 3.5 Lightning "
     "30B-A3B MLX 4-bit on mac: TensorFold publishes no size for it (tensorfold info"),
    ("amd", AMD, "linux", Q27, "no", "does not fit: TensorFold runs on Apple Silicon (Metal) and NVIDIA cards (CUDA); amd "
     "has the AMD Radeon RX 7900 XTX"),
    ("nogpu", NOGPU, "linux", Q27, "no", "does not fit: TensorFold runs on Apple Silicon (Metal) and NVIDIA cards (CUDA); "
     "nogpu has no GPU on its card"),
)


@test
def test_the_table(ctx: Ctx):
    from halo_harness.local_sched.fit_tf import fit, host_for
    from halo_harness.tensorfold.catalog import get
    for name, card, os_name, repo, level, starts in TABLE:
        got = fit(get(repo), host_for(name, card, os_name=os_name))
        ctx.check(f"{repo} on {name}: {level}, got {got['level']} {got['line']!r}", got["level"] == level
                  and got["line"].startswith(starts) and got["runtime"] == "tensorfold")
    pc = fit(get(Q36N), host_for("pc", PC, os_name="windows"))
    ctx.check(f"NVFP4 on the 4090: the fallback path said, got {pc['line']!r}", "NVFP4 on the 4090 (sm_89, no "
              "thread-block clusters) runs TensorFold's fallback path: slower" in pc["line"] and pc["numbers"]["fallback"])
    ctx.check("the Windows build from source is said on pc", "(the Windows build is from source: docs/WINDOWS.md)" in pc["line"])
    ctx.check("the download line is the user's", "the download: tensorfold pull nvidia/Qwen3.6-35B-A3B-NVFP4@1355db6a"
              in pc["line"] and pc["line"].endswith("(yours to run)"))
    win = fit(get(Q27), host_for("mac", MAC, os_name="macos"), window=131072)
    ctx.check("--window is the window said", "the 131,072-token window" in win["line"])
    ctx.check("no card read: unknown, said", "no hardware card read yet" in fit(get(Q27), host_for("x", None))["line"])
    ctx.check("not in the table: unknown, said", fit(None, host_for("pc", PC))["level"] == "unknown")


@test
def test_serve_prints_the_fit_here(ctx: Ctx):
    from halo_harness.local_cli import cmd_local
    with TfHome() as h:
        h.cached()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_local(["serve", "--runtime", "tensorfold", "--model", REPO])
        text = out.getvalue()
        ctx.check(f"the fit here before the start, got {code} {text[:400]!r}", code == 0 and "fit here: fits: Qwen3.8-27B "
                  "MLX 4-bit (16 GiB) on this machine" in text and text.index("fit here:") < text.index("serving "))


@test
def test_the_library_lists_tensorfolds_models(ctx: Ctx):
    from halo_harness.models_library.browse import library
    with TfHome() as h:
        got = library(h.state, source="hf", q="tensorfold qwen3.8", host="box", window=32768)
        rows = [r for r in got["rows"] if r.get("kind") == "tensorfold"]
        ids = sorted(r["id"] for r in rows)
        ctx.check(f"the Qwen3.8 rows, got {ids}", "tensorfold:TensorFold/Qwen3.8-27B-MLX-4bit" in ids and all(
            "qwen3.8" in i.lower() for i in ids))
        r = next(x for x in rows if x["id"] == f"tensorfold:{REPO}")
        ctx.check(f"a download target the user runs, with the TensorFold fit, got {r['pull_line']!r} {r['fit']}",
                  r["pull_line"].startswith(f"tensorfold pull {REPO}") and "yours to run" in r["pull_line"]
                  and r["size_bytes"] == 16 * GIB and r["fit"]["level"] == "fits" and r["fit"]["runtime"] == "tensorfold"
                  and r["fit"]["why"].startswith("fits: Qwen3.8-27B MLX 4-bit (16 GiB) on box"))
        h.set_hf(tensorfold_bin=None)
        got = library(h.state, source="hf", q="qwen3.8", host="box", window=32768)
        ctx.check("not set up and not asked: no TensorFold rows", not [r for r in got["rows"] if r.get("kind") == "tensorfold"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
