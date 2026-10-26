"""tests.test_ollama_prompt_floor -- Halo 3.2.3.0 R1: `providers.
ollama_prompt` (the request estimate, the window it gets, the lines), the
`prompt_trimmed` error kind and the Ollama retry ceiling
(`providers.errors`), the reply's room -- pure functions and the request
builder; no network, no real model (`num_gpu` and the prompt reading
speed: tests/test_ollama_gpu_speed.py).
"""
from __future__ import annotations

import json
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


# ---- the estimate --------------------------------------------------------

@test
def test_estimate_is_chars_over_3_5_plus_the_reply_reserve(ctx: Ctx):
    from halo_harness.providers.ollama_prompt import REPLY_RESERVE_TOKENS, estimate_request_tokens
    messages = [{"role": "user", "content": "x" * 7000}]
    chars = len(json.dumps({"system": "", "messages": messages, "tools": []}, ensure_ascii=False))
    got = estimate_request_tokens(messages, None, "")
    ctx.check(f"ceil(chars / 3.5) + 1024, got {got}", got == -(-chars * 2 // 7) + REPLY_RESERVE_TOKENS)
    with_tools = estimate_request_tokens(messages, [{"name": "Read", "description": "d" * 3500}], "")
    ctx.check("tool definitions count", with_tools >= got + 1000)


@test
def test_inline_image_bytes_are_left_out_of_the_estimate(ctx: Ctx):
    from halo_harness.providers.ollama_prompt import estimate_request_tokens
    img = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "A" * 500000}}
    got = estimate_request_tokens([{"role": "user", "content": [img]}], None, "")
    ctx.check(f"a 500 kB image is not 140k tokens, got {got}", got < 2000)


@test
def test_tool_output_tokens_counts_tool_results_only(ctx: Ctx):
    from halo_harness.providers.ollama_prompt import tool_output_tokens
    msgs = [{"role": "user", "content": "q" * 3500},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "r" * 35000}]}]
    got = tool_output_tokens(msgs)
    ctx.check(f"about 10k tokens of tool output, got {got}", 9900 < got < 10200)


# ---- the window ----------------------------------------------------------

@test
def test_window_for_raises_over_the_base_to_a_power_of_two(ctx: Ctx):
    from halo_harness.providers.ollama_prompt import window_for
    small = window_for(5000, base=8192, base_source="learned cap", trained_context=40960)
    ctx.check(f"a request under the base keeps it, got {small}", small.num_ctx == 8192 and small.source == "learned cap")
    big = window_for(11000, base=8192, base_source="learned cap", trained_context=40960)
    ctx.check(f"11k -> 16384 [prompt floor], got {big}", big.num_ctx == 16384 and big.source == "prompt floor"
              and big.fits and big.floor == 11000)
    factor = window_for(11000, base=8192, base_source="learned cap", trained_context=40960, factor=1.5)
    ctx.check(f"x 1.5 -> 32768, got {factor.num_ctx}", factor.num_ctx == 32768)


@test
def test_window_for_never_passes_the_ceiling_and_says_when_it_does_not_fit(ctx: Ctx):
    from halo_harness.providers.ollama_prompt import window_for
    choice = window_for(20000, base=8192, base_source="trained context", trained_context=8192)
    ctx.check(f"the trained context is the ceiling, got {choice}", choice.num_ctx == 8192 and not choice.fits
              and choice.ceiling == 8192)
    mem = window_for(30000, base=8192, base_source="fit estimate", trained_context=131072, fit_estimate=16384)
    ctx.check(f"the memory estimate caps it, got {mem}", mem.num_ctx == 16384 and not mem.fits)
    host = window_for(30000, base=8192, base_source="fallback", trained_context=131072, host_max_ctx=24576)
    ctx.check(f"host max_ctx caps it, got {host}", host.num_ctx == 24576 and not host.fits)


@test
def test_source_words(ctx: Ctx):
    from halo_harness.providers.ollama_prompt import source_word
    got = [source_word(s) for s in ("trained context", "fit estimate", "learned cap", "host max_ctx", "prompt floor")]
    ctx.check(f"trained / memory / calibrated / max_ctx / prompt floor, got {got}",
              got == ["trained", "memory", "calibrated", "max_ctx", "prompt floor"])


# ---- the lines -------------------------------------------------------------

@test
def test_the_lines(ctx: Ctx):
    from halo_harness.providers.ollama_prompt import fmt_tokens, fmt_window, too_large_line, trim_line
    ctx.check("4.1k / 11k / 900", (fmt_tokens(4100), fmt_tokens(11000), fmt_tokens(900)) == ("4.1k", "11k", "900"))
    ctx.check("8k / 32k / 65k", (fmt_window(8192), fmt_window(32768), fmt_window(65536)) == ("8k", "32k", "65k"))
    line = too_large_line(14000, 9000, "qwen3.8:27b", "pc", 8192)
    ctx.check(f"the compaction line, got {line!r}", line ==
              "the request (14k tokens, 9k of it tool output) is larger than qwen3.8:27b's window on pc (8k): compacted")
    ctx.check("no tool part when small", "tool output" not in too_large_line(14000, 100, "m", "pc", 8192))
    ctx.check("the raise line", trim_line("pc", 4100, 12024, window=16384) ==
              "pc trimmed the request (4.1k of 11k tokens): re-sent with a 16k window")
    ctx.check("the compact line", trim_line("pc", 4100, 12024) == "pc trimmed the request (4.1k of 11k tokens): "
              "compacted and re-sent")


@test
def test_is_trimmed(ctx: Ctx):
    from halo_harness.providers.ollama_prompt import is_trimmed
    ctx.check("4.1k read of an 11k request is a trim", is_trimmed(4100, 12024))
    ctx.check("10k read of 11k is not", not is_trimmed(10000, 12024))
    ctx.check("a small request is never called", not is_trimmed(10, 2000))
    ctx.check("no count is not a trim", not is_trimmed(None, 12024) and not is_trimmed(0, 12024))


# ---- errors: prompt_trimmed and the Ollama retry ceiling -----------------

@test
def test_the_no_user_query_500_is_prompt_trimmed_not_retried_raw_text_kept(ctx: Ctx):
    from halo_harness.providers.errors import (
        PROMPT_TRIMMED, is_retryable_message, map_upstream_error, max_retries_for,
    )
    status, body, hdrs = map_upstream_error(500, {"error": "no user query found in messages"}, "ollama")
    err = body["error"]
    ctx.check(f"kind prompt_trimmed, got {err['type']!r}", err["type"] == PROMPT_TRIMMED)
    ctx.check(f"not retryable, got {hdrs}", hdrs.get("x-should-retry") == "false")
    ctx.check(f"plain line then the raw text, got {err['message']!r}",
              err["message"].startswith("the prompt was trimmed and lost your message")
              and err["message"].endswith("(Ollama: no user query found in messages)"))
    ctx.check("the message never reads as retryable", not is_retryable_message(500, err["message"]))
    ctx.check("its max_retries is 0", max_retries_for("ollama", PROMPT_TRIMMED) == 0)


@test
def test_another_ollama_500_keeps_its_raw_text_and_three_sends(ctx: Ctx):
    from halo_harness.providers.errors import MAX_RETRIES, map_upstream_error, max_retries_for
    _s, body, hdrs = map_upstream_error(500, {"error": "llama runner process has terminated"}, "ollama")
    ctx.check(f"raw text kept, got {body['error']['message']!r}",
              "(Ollama: llama runner process has terminated)" in body["error"]["message"])
    ctx.check("still retryable", hdrs.get("x-should-retry") == "true")
    ctx.check("ollama: 2 retries (three sends)", max_retries_for("ollama", "api_error") == 2)
    ctx.check("other providers unchanged", max_retries_for("openrouter", "api_error") == MAX_RETRIES)
    _s2, other, _h = map_upstream_error(500, {"error": "boom"}, "openrouter")
    ctx.check("other providers keep the plain sentence", "(Ollama:" not in other["error"]["message"])


# ---- the reply's room: num_predict, not a fixed 1,024 --------------------

@test
def test_the_reserve_follows_num_predict(ctx: Ctx):
    from halo_harness.providers.ollama_prompt import estimate_request_tokens, reply_reserve
    msgs = [{"role": "user", "content": "x" * 7000}]
    base = estimate_request_tokens(msgs, None, "")
    ctx.check("no num_predict -> 1,024", reply_reserve(None) == 1024 and reply_reserve(0) == 1024)
    ctx.check("a small num_predict -> still 1,024", reply_reserve(200) == 1024)
    got = estimate_request_tokens(msgs, None, "", reply_tokens=16384)
    ctx.check(f"num_predict 16384 -> the estimate carries 16384 for the reply, got {got - base + 1024}",
              got == base - 1024 + 16384)


@test
def test_prompt_plus_reply_must_fit_the_window(ctx: Ctx):
    """30k of prompt + a 16k reply on a 32k-trained model: the window is
    the trained context and the reply gets the room left (not a cut at
    the window's end); a prompt that does not fit even with 1,024 left
    does not fit."""
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_prompt import window_for
    from halo_harness.providers.ollama_request import build_ollama_request_body
    choice = window_for(30000 + 16384, base=16384, base_source="fallback", trained_context=32768, reserve=16384)
    ctx.check(f"the ceiling, the reply's room shrinks to fit, got {choice}",
              choice.num_ctx == 32768 and choice.fits and choice.num_predict == 2768)
    over = window_for(32000 + 16384, base=16384, base_source="fallback", trained_context=32768, reserve=16384)
    ctx.check(f"no room even for 1,024 -> does not fit, got {over}", not over.fits and over.num_predict is None)
    route, profile = _route_profile()
    body = build_ollama_request_body(system_text="s", messages=[{"role": "user", "content": "hi"}], tools=None,
                                     tool_choice=None, route=route, profile=profile, effort=None,
                                     host=OllamaHost(name="pc", url="http://127.0.0.1:1"), trained_context=32768,
                                     requested_max_tokens=16384, prompt_tokens=30000 + 16384)
    ctx.check(f"on the wire: num_ctx 32768, num_predict 2768, got {body['options']}",
              body["options"]["num_ctx"] == 32768 and body["options"]["num_predict"] == 2768)


@test
def test_is_window_cut(ctx: Ctx):
    from halo_harness.providers.ollama_prompt import is_window_cut, trim_line
    ctx.check("length at the window's end is a cut", is_window_cut("length", 60000, 4829, 65536, 16384))
    ctx.check("length well before the window (its own num_predict) is not", not is_window_cut("length", 20000, 4096, 65536, 4096))
    ctx.check("stop is never a cut", not is_window_cut("stop", 60000, 5000, 65536))
    ctx.check("the line", trim_line("pc", 64829, 70000, window=131072, cut_at=65536) ==
              "pc cut the reply at the window (65k of 65k tokens): re-sent with a 131k window")


if __name__ == "__main__":
    os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
