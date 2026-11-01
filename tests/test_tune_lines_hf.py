"""tests.test_tune_lines_hf -- Halo 3.3.8.0 R2: a local server's server-side lines (ollama_steward/tune_lines_hf.py):
each runtime's exact flag or setting with the line that reverts it and `applied: false` (llama-server's --ctx-size,
--n-gpu-layers, --cache-type-k/-v, --n-predict, --flash-attn; LM Studio's load settings; mlx_lm.server's --max-tokens
and nothing for what it has no setting for), the restart through Halo for a server Halo started, the finding's hint,
and a repeated crash's fixes. Nothing runs: the lines are text.
Run: python -m tests.test_tune_lines_hf
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _srv(runtime, source="manual", sid=None, name="box"):
    from halo_harness.ollama_steward.servers_hf import Server
    return Server(name, "http://127.0.0.1:8080", runtime, source, id=sid)


@test
def test_llama_server_lines_and_their_reverts(ctx: Ctx):
    from halo_harness.ollama_steward.tune_lines_hf import line
    s = _srv("llama-server")
    want = {("ctx-size", 32768, 16384): ("--ctx-size 32768", "--ctx-size 16384"),
            ("n-gpu-layers", 37, 30): ("--n-gpu-layers 37", "--n-gpu-layers 30"),
            ("cache-type", "q8_0", None): ("--cache-type-k q8_0 --cache-type-v q8_0", "--cache-type-k f16 --cache-type-v f16"),
            ("n-predict", -1, 512): ("--n-predict -1", "--n-predict 512"),
            ("flash-attn", "on", None): ("--flash-attn on", "--flash-attn auto")}
    for (change, value, was), (set_, revert) in want.items():
        got = line(s, change, value, was=was)
        ctx.check(f"{change}: {got}", got["set"] == set_ and got["revert"] == revert and got["applied"] is False
                  and got["cost"] and "restart llama-server on box" in got["how"])


@test
def test_a_server_halo_started_restarts_through_halo_said_not_done(ctx: Ctx):
    from halo_harness.ollama_steward.tune_lines_hf import hint, line
    got = line(_srv("llama-server", "halo", "llama-8080", "llama-8080"), "ctx-size", 32768, was=16384)
    ctx.check(f"halo local stop, then serve --window, got {got['how']}", got["how"] ==
              "halo local stop llama-8080, then halo local serve <the model> --window 32768")
    h = hint(got)
    ctx.check(f"the hint carries the revert and applied false, got {h}", "revert: --ctx-size 16384" in h["line"]
              and h["applied"] is False)
    ctx.check("no hint without a line", hint(None) is None)


@test
def test_lm_studio_settings_and_mlx_flags(ctx: Ctx):
    from halo_harness.ollama_steward.tune_lines_hf import line
    lms = line(_srv("lmstudio"), "ctx-size", 16384, was=4096)
    ctx.check(f"LM Studio's Context Length, got {lms}", "Context Length: 16384 (then reload the model)" in lms["set"]
              and "Context Length: 4096" in lms["revert"] and lms["applied"] is False)
    ctx.check("LM Studio's GPU Offload", "GPU Offload: max" in line(_srv("lmstudio"), "n-gpu-layers", "max")["set"])
    ctx.check("LM Studio has no n_predict flag", line(_srv("lmstudio"), "n-predict", -1) is None)
    ctx.check("mlx: --max-tokens", line(_srv("mlx"), "n-predict", 4096)["set"].endswith("--max-tokens 4096"))
    ctx.check("mlx keeps no fixed window and offloads nothing", line(_srv("mlx"), "ctx-size", 8192) is None
              and line(_srv("mlx"), "n-gpu-layers", 1) is None)


@test
def test_a_repeated_crash_says_the_runtimes_lines(ctx: Ctx):
    from halo_harness.ollama_steward.tune_lines_hf import crash_fixes
    fixes = crash_fixes({"host": "llama-8080", "model": "qwen3-8b", "runtime": "llama-server", "window_used": 32768,
                         "kv_cache_type": "q8_0"})
    sides = [f["side"] for f in fixes]
    ctx.check(f"Halo's side first, then the server's, got {fixes}", sides[0] == "halo" and "host" in sides)
    ctx.check("q8_0 in force: f16 said", any("--cache-type-k f16" in f["line"] for f in fixes))
    ctx.check("a smaller --ctx-size said", any("--ctx-size 16384" in f["line"] for f in fixes))
    ctx.check("never applied", all(f.get("applied") is False for f in fixes if f["side"] == "host"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
