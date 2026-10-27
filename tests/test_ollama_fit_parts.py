"""tests.test_ollama_fit_parts -- Halo 3.3.4.0 R3: the corrected fit
arithmetic (providers/ollama_fit_parts.py), pinned with R1's worked numbers
from the measured host's server.log (ollama_steward/knowledge/memory.md):
the KV layers of a hybrid model, a per-layer head count list, the
recurrent state, the compute buffer, Ollama's per-card minimum, llama.cpp's
fit margin, the parallel slots, the server's own cache type when the host
entry has no hint, and the hardware card reading a host served here.
Pure arithmetic and fixture logs only: no server, no model.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()
MIB = 2 ** 20
FIX = Path(__file__).resolve().parent / "fixtures" / "ollama_steward"

Q27 = {"qwen35.block_count": 65, "qwen35.attention.head_count_kv": 4, "qwen35.attention.key_length": 256,
       "qwen35.attention.value_length": 256, "qwen35.full_attention_interval": 4, "qwen35.nextn_predict_layers": 1,
       "qwen35.embedding_length": 5120, "qwen35.ssm.conv_kernel": 4, "qwen35.ssm.state_size": 128,
       "qwen35.ssm.group_count": 16, "qwen35.ssm.inner_size": 6144, "qwen35.vocab_size": 248320}
C30 = {"qwen3moe.block_count": 48, "qwen3moe.attention.head_count_kv": 4, "qwen3moe.attention.key_length": 128,
       "qwen3moe.attention.value_length": 128, "qwen3moe.embedding_length": 2048, "qwen3moe.vocab_size": 151936}
W27, W30 = 16804059546, 18554258719
FREE = 21506 * MIB
Q8 = 1.0625


def _near(a, b, tol=0.05):
    return abs(a - b) <= tol * max(abs(b), 1.0)


@test
def test_a_hybrid_model_caches_one_layer_in_four(ctx: Ctx):
    from halo_harness.providers.ollama_fit import kv_bytes_per_token
    from halo_harness.providers.ollama_fit_parts import kv_layers
    ctx.check(f"16 of 65 blocks (64 layers, the draft apart) hold a cache, got {kv_layers(Q27)}", kv_layers(Q27) == 16)
    got = kv_bytes_per_token(Q27, bytes_per_elem=Q8)
    ctx.check(f"34,816 bytes per token at q8_0 (the log's 2,176 MiB at 65,536), got {got}", got == 34816)
    ctx.check("2,176 MiB at 65,536", got * 65536 / MIB == 2176)
    ctx.check(f"a dense model still counts every block: 48 for the 30B, got {kv_layers(C30)}", kv_layers(C30) == 48)


@test
def test_a_per_layer_head_count_list_counts_its_attention_layers(ctx: Ctx):
    """lfm2moe gives `head_count_kv` per layer (0 for its conv layers): no
    estimate at all before R3."""
    from halo_harness.providers.ollama_fit import kv_bytes_per_token
    heads = [0, 0, 8, 0, 0, 8, 0, 0, 8, 0, 8, 0, 8, 0, 8, 0, 8, 0, 8, 0, 8, 8, 0, 0]
    info = {"lfm2moe.block_count": 24, "lfm2moe.attention.head_count_kv": heads,
            "lfm2moe.attention.key_length": 64, "lfm2moe.attention.value_length": 64}
    got = kv_bytes_per_token(info, bytes_per_elem=Q8)
    ctx.check(f"10 attention layers x 8 heads x 128 x 1.0625, got {got}", got == 10 * 8 * 128 * Q8)


@test
def test_the_recurrent_state_and_the_draft(ctx: Ctx):
    from halo_harness.providers.ollama_fit_parts import load_parts, recurrent_bytes
    one = recurrent_bytes(Q27) / MIB
    ctx.check(f"one sequence: the log's 149.63 MiB, got {one:.3f}", abs(one - 149.63) < 0.01)
    parts = load_parts(Q27, weight_bytes=W27, window=65536, bytes_per_elem=Q8)
    ctx.check(f"with the draft (1 seq + 4 rs_seq): 748.13 MiB, got {parts['recurrent'] / MIB:.2f}",
              abs(parts["recurrent"] / MIB - 748.13) < 0.01)
    ctx.check(f"the draft's f16 cache 256 MiB + its 130 MiB compute, got {parts['draft'] / MIB:.0f}",
              round(parts["draft"] / MIB) == 386)
    off = load_parts(Q27, weight_bytes=W27, window=65536, bytes_per_elem=Q8, draft=False)
    ctx.check("a server that ignores the draft: one sequence, no draft cache",
              abs(off["recurrent"] / MIB - 149.63) < 0.01 and off["draft"] == 0)
    ctx.check("a dense model has no recurrent state", load_parts(C30, weight_bytes=W30, window=4096)["recurrent"] == 0)


@test
def test_the_compute_buffer_follows_the_window(ctx: Ctx):
    from halo_harness.providers.ollama_fit_parts import compute_bytes
    for window, measured in ((16384, 180.29), (32768, 260.29), (65536, 420.29)):
        got = compute_bytes(Q27, window) / MIB
        ctx.check(f"27B at {window}: the log's {measured} MiB within 5 %, got {got:.1f}", _near(got, measured))
    for window, measured in ((49152, 204.09), (65536, 252.09), (131072, 444.09)):
        got = compute_bytes(C30, window) / MIB
        ctx.check(f"30B at {window}: the log's {measured} MiB within 5 %, got {got:.1f}", _near(got, measured))


@test
def test_the_minimum_the_margin_and_the_projector(ctx: Ctx):
    from halo_harness.providers.ollama_fit_parts import projector_for, reserve_bytes
    ctx.check("Ollama keeps 457 MiB per CUDA card", reserve_bytes() == 457 * MIB)
    ctx.check("and 512 MiB on Metal", reserve_bytes(metal=True) == 512 * MIB)
    ctx.check("OLLAMA_GPU_OVERHEAD comes on top", reserve_bytes(gpu_overhead=MIB) == 458 * MIB)
    margin = reserve_bytes(forced=False, projector_bytes=1161 * MIB) / MIB
    ctx.check(f"num_gpu unset: --fit's 1,024 MiB + the 912 MiB projector file = 1,936, got {margin:.0f}",
              round(margin) == 1936)
    ctx.check("a model without vision has no projector", projector_for({"capabilities": ["tools"]}) == 0)
    ctx.check("the vision capability alone: the measured 1,161 MiB worst case",
              projector_for({"capabilities": ["vision"]}) == 1161 * MIB)


@test
def test_the_measured_fits(ctx: Ctx):
    """R1: the 27B fits 65,536 with every layer forced on and spills past
    49,152 by default; the 30B fits 65,536 forced with 466 MiB left."""
    from halo_harness.providers.ollama_fit_parts import fit_window
    p27 = dict(weight_bytes=W27, free_bytes=FREE, bytes_per_elem=Q8, projector_bytes=1161 * MIB)
    ctx.check("27B forced: 65,536", fit_window(Q27, **p27) == 65536)
    ctx.check("27B by default, in 4k steps: 49,152", fit_window(Q27, forced=False, step=4096, **p27) == 49152)
    p30 = dict(weight_bytes=W30, free_bytes=FREE, bytes_per_elem=Q8)
    ctx.check("30B forced: 65,536", fit_window(C30, **p30) == 65536)
    ctx.check("30B by default: 32,768 (llama.cpp overflowed 3 layers at 65,536)",
              fit_window(C30, forced=False, **p30) == 32768)
    old = fit_window(Q27, **{**p27, "bytes_per_elem": 2.0})
    ctx.check(f"the 27B at f16: 32,768 (the old 65-block count said 16,384), got {old}", old == 32768)


@test
def test_parallel_slots_multiply_the_cache(ctx: Ctx):
    from halo_harness.providers.ollama_fit_parts import fit_window, load_parts
    one = load_parts(C30, weight_bytes=W30, window=32768, bytes_per_elem=Q8)["kv"]
    two = load_parts(C30, weight_bytes=W30, window=32768, bytes_per_elem=Q8, parallel=2)["kv"]
    ctx.check("two slots, twice the KV cache", two == 2 * one)
    got = fit_window(C30, weight_bytes=W30, free_bytes=FREE, bytes_per_elem=Q8, parallel=2)
    ctx.check(f"the 30B with two slots fits 32,768, not 65,536, got {got}", got == 32768)


@test
def test_the_host_without_a_hint_reads_the_servers_cache_type(ctx: Ctx):
    """The host entry has no kv_cache_type: a host served here takes the
    server log's own (`OLLAMA_KV_CACHE_TYPE:q8_0` in the fixture), and the
    estimate follows; a hint still wins."""
    from halo_harness.ollama_steward import hardware
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers import ollama_hw
    hardware._SETTINGS_CACHE.clear()
    host = OllamaHost(name="pc", url="http://0.0.0.0:11434")
    real = hardware.server_settings_for
    hardware.server_settings_for = lambda h, log_path=None: real(h, log_path=FIX / "windows-server.txt")
    try:
        got = ollama_hw.host_fit_settings(host)
        ctx.check(f"q8_0 and one slot from the log, got {got}", got == {"kv_cache_type": "q8_0", "parallel": 1})
        hinted = OllamaHost(name="pc", url="http://0.0.0.0:11434", kv_cache_type="q4_0", num_parallel_hint=2)
        ctx.check("the host entry's hints win", ollama_hw.host_fit_settings(hinted) == {"kv_cache_type": "q4_0",
                                                                                        "parallel": 2})
    finally:
        hardware.server_settings_for = real
        hardware._SETTINGS_CACHE.clear()
    far = OllamaHost(name="far", url="http://192.0.2.10:11434")
    ctx.check("a host on another machine: f16 and one slot", ollama_hw.host_fit_settings(far) ==
              {"kv_cache_type": "f16", "parallel": 1})


@test
def test_the_card_reads_the_log_of_a_host_served_here(ctx: Ctx):
    """R2's finding: OLLAMA_HOST=0.0.0.0:11434 -- the card read no log for
    it while it asked `is_local_host` (loopback only)."""
    from halo_harness.ollama_steward.hardware import hardware_card
    from halo_harness.providers.ollama import OllamaHost
    card = hardware_card(OllamaHost(name="pc", url="http://0.0.0.0:11434"), log_path=FIX / "windows-server.txt",
                         api=lambda path: None, runner=lambda argv, timeout: None, platform="win32")
    src = {s["reader"]: s for s in card["sources"]}
    ctx.check(f"the server log was read, got {src.get('server.log')}", src.get("server.log", {}).get("ok") is True)
    ctx.check("and the live read is the local one", "nvidia-smi / system_profiler" in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
