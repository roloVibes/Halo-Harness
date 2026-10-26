"""tests.test_ollama_gpu_speed -- Halo 3.2.3.0 R1: `options.num_gpu` (every
layer on the GPU when Halo's estimate says the model fits there at the
window sent) and the prompt reading speed (`prompt_tok_s`, a rolling
average per host and model) -- the request builder and the store; no
network, no real model.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _route_profile():
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.routing import Route
    route = Route(provider="ollama", upstream_model="qwen3:30b", dialect="ollama")
    return route, resolve_profile(route)


# ---- num_gpu: every layer on the GPU when the estimate says it fits -----

@test
def test_num_gpu_present_when_the_estimate_fits_and_absent_otherwise(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate_steps import gpu_layers_for
    from halo_harness.providers.ollama_request import build_ollama_request_body
    route, profile = _route_profile()
    layers = gpu_layers_for({"qwen3.block_count": 64, "qwen3.context_length": 40960})
    ctx.check(f"block_count + 1, got {layers}", layers == 65)
    ctx.check("unknown -> 999", gpu_layers_for({}) == 999)
    kwargs = dict(system_text="s", messages=[{"role": "user", "content": "hi"}], tools=None, tool_choice=None,
                  route=route, profile=profile, effort=None, host=OllamaHost(name="pc", url="http://127.0.0.1:1"),
                  trained_context=40960, gpu_layers=layers)
    fits = build_ollama_request_body(fit_estimate=32768, gpu_fits_up_to=32768, **kwargs)
    ctx.check(f"fits at the window sent -> num_gpu, got {fits['options']}",
              fits["options"].get("num_gpu") == 65 and fits["options"]["num_ctx"] == 32768)
    capped = build_ollama_request_body(fit_estimate=32768, gpu_fits_up_to=32768, prompt_tokens=50000, **kwargs)
    ctx.check(f"the memory estimate caps the floor, num_gpu kept, got {capped['options']}",
              capped["options"]["num_ctx"] == 32768 and capped["options"].get("num_gpu") == 65)
    over = build_ollama_request_body(fit_estimate=None, learned_cap=16384, gpu_fits_up_to=16384,
                                     prompt_tokens=20000, **kwargs)
    ctx.check(f"the floor raised the window past the calibrated size -> no num_gpu, got {over['options']}",
              "num_gpu" not in over["options"] and over["options"]["num_ctx"] == 32768)
    unknown = build_ollama_request_body(fit_estimate=None, gpu_fits_up_to=None, **kwargs)
    ctx.check(f"no estimate -> Ollama decides, got {unknown['options']}", "num_gpu" not in unknown["options"])


# ---- prompt reading speed --------------------------------------------------

@test
def test_prompt_speed_and_its_rolling_average(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import get_prompt_speed, record_prompt_speed
    from halo_harness.providers.ollama_prompt import prompt_speed
    ctx.check("10k tokens in 4 s -> 2500 tok/s", prompt_speed(10000, 4_000_000_000) == 2500.0)
    ctx.check("a tiny prompt is not timed", prompt_speed(20, 1_000_000) is None)
    d = Path(tempfile.mkdtemp(prefix="ol-speed-"))
    record_prompt_speed(d, host_url="http://h", model="m", tok_s=2000.0)
    record_prompt_speed(d, host_url="http://h", model="m:latest", tok_s=3000.0)
    got = get_prompt_speed(d, host_url="http://h", model="m")
    ctx.check(f"the rolling average over both spellings, got {got}", got == 2500.0)
    from halo_harness.providers.ollama_calibrate import has_calibration_entry
    ctx.check("a speed never makes a calibration entry", not has_calibration_entry(d, host_url="http://h", model="m"))


@test
def test_prompt_tok_s_recorded_from_a_chat_responses_eval_fields(ctx: Ctx):
    """A real turn's timing (`prompt_eval_count`/`prompt_eval_duration`
    from Ollama's final line) lands in the store through the session's
    own throughput hook."""
    from types import SimpleNamespace
    from halo_harness.agent.loop import Session
    from halo_harness.providers.ollama_calibrate import get_prompt_speed
    d = Path(tempfile.mkdtemp(prefix="ol-speed-turn-"))
    fake = SimpleNamespace(state_dir=d, _last_ollama_host_url="http://h", _last_ollama_offloaded=False,
                           model_ref=SimpleNamespace(model="qwen3:30b"), _last_ollama_throughput=None)
    Session._record_ollama_throughput(fake, {"prompt_eval_count": 12000, "prompt_eval_duration": 4_800_000_000,
                                             "eval_count": 50, "eval_duration": 1_000_000_000})
    got = get_prompt_speed(d, host_url="http://h", model="qwen3:30b")
    ctx.check(f"12000 tokens / 4.8 s = 2500 tok/s, got {got}", got == 2500.0)


if __name__ == "__main__":
    os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
