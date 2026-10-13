"""tests.test_review3_g1b -- 3.0.2.0 review fix pass, round G1 (providers
wire), the request/response half:

  * review item 56   a definitive 4xx is never retried because its text
                     happens to contain 429/500/502/... digits
  * review item 57   `--effort minimal`/`none` on an `oai:` chat route is
                     sent as the route's weakest level, never its strongest
  * review items 58/127/129  per-model Claude behaviour from the model
                     table: Haiku 5.5 adaptive (no budget_tokens), xhigh
                     kept on 4.7+/Fable/Mythos, no forced tool_choice on
                     Opus/Sonnet 5.5 and Fable/Mythos 5.1
  * review item 126  alnum9 tool ids are unique (hashed, de-duplicated)
  * review item 128  a mid-stream error chunk keeps its own code/type
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _ant(model: str):
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.routing import Route
    return resolve_profile(Route("anthropic", model, "anthropic-passthrough"))


@test
def test_4xx_with_status_like_digits_is_not_retryable(ctx: Ctx):
    from halo_harness.providers.errors import is_retryable_message
    cases = [
        (400, "max_tokens must be at most 15000 for this model"),
        (400, "max_tokens: 25000 > 8192, which is the maximum allowed"),
        (422, "Input validation error: `inputs` tokens + `max_new_tokens` must be <= 4096. Given: 5024 inputs tokens"),
        (403, "forbidden (request id req-502-a1b2)"),
        (400, "rate limit settings are invalid for this key"),
    ]
    for status, msg in cases:
        ctx.check(f"{status} {msg!r} is not retryable", is_retryable_message(status, msg) is False)
    ctx.check("429 is still retryable", is_retryable_message(429, "slow down") is True)
    ctx.check("408 is retryable", is_retryable_message(408, "request timeout") is True)
    ctx.check("a mid-stream (no status) 'HTTP 503' is still retryable",
              is_retryable_message(None, "upstream answered HTTP 503") is True)
    ctx.check("a bare token count with no status is not a status code",
              is_retryable_message(None, "context is 15000 tokens") is False)


@test
def test_disabling_effort_on_oai_chat_is_the_weakest_level(ctx: Ctx):
    from halo_harness.providers.profiles import clamp_effort, resolve_profile
    from halo_harness.providers.routing import Route
    for model in ("o3", "o4-mini"):
        p = resolve_profile(Route("openai", model, "openai-chat"))
        lo = p.effort_values_supported[0]
        for asked in ("minimal", "none", "off"):
            got = clamp_effort(asked, p)
            ctx.check(f"oai:{model} --effort {asked} -> {lo!r} (weakest of {p.effort_values_supported}), "
                      f"got {got!r}", got == lo)
        ctx.check(f"oai:{model} max still narrows to its strongest level",
                  clamp_effort("max", p) == p.effort_values_supported[-1])


@test
def test_haiku_5_5_is_adaptive_and_haiku_4_5_keeps_a_budget(ctx: Ctx):
    from halo_harness.providers.request import map_effort_anthropic
    for model in ("claude-haiku-5-5", "databricks-claude-haiku-5-5", "claude-haiku-5.5"):
        body = map_effort_anthropic("high", model, max_tokens=16384)
        ctx.check(f"{model}: adaptive thinking, no budget_tokens, got {body}",
                  body == {"thinking": {"type": "adaptive"}, "output_config": {"effort": "high"}})
    body = map_effort_anthropic("high", "claude-haiku-4-5-20251001", max_tokens=16384)
    ctx.check(f"Haiku 4.5 still takes budget_tokens, got {body}",
              body.get("thinking", {}).get("type") == "enabled" and "budget_tokens" in body["thinking"])


@test
def test_xhigh_kept_where_the_model_accepts_it(ctx: Ctx):
    from halo_harness.providers.profiles import clamp_effort
    for model in ("claude-opus-5-5", "claude-opus-4-7", "claude-sonnet-5-5", "claude-haiku-5-5",
                  "claude-fable-5-1", "databricks-claude-opus-5-5"):
        ctx.check(f"{model}: xhigh passes through", clamp_effort("xhigh", _ant(model)) == "xhigh")
    for model in ("claude-opus-4-6", "databricks-claude-opus-4-6", "claude-sonnet-4-5"):
        ctx.check(f"{model}: xhigh still narrows to max", clamp_effort("xhigh", _ant(model)) == "max")


@test
def test_forced_tool_choice_off_on_models_that_reject_it(ctx: Ctx):
    for model in ("claude-opus-5-5", "databricks-claude-opus-5-5", "databricks-claude-sonnet-5-5",
                  "claude-fable-5-1", "claude-mythos-5-1"):
        ctx.check(f"{model}: no forced tool_choice repair retry",
                  _ant(model).tool_choice_required_supported is False)
    for model in ("claude-opus-5", "claude-sonnet-5", "claude-fable-5", "claude-opus-4-6", "claude-haiku-5-5"):
        ctx.check(f"{model}: forced tool_choice still allowed",
                  _ant(model).tool_choice_required_supported is True)


@test
def test_learned_params_never_clamps_a_structured_field_to_a_string(ctx: Ctx):
    from halo_harness.providers.learned_params import apply_param_fix, detect_param_rejection
    body = {"model": "m", "tool_choice": {"type": "any"}, "messages": []}
    fix = detect_param_rejection(400, 'tool_choice: type "tool" and "any" are not supported for this model', body)
    ctx.check(f"a dict-valued tool_choice is dropped, got {fix}", fix is not None and fix.action == "drop")
    ctx.check("the retried body has no tool_choice", "tool_choice" not in apply_param_fix(body, fix))
    fix = detect_param_rejection(400, "reasoning_effort must be one of 'low', 'high'", {"reasoning_effort": "medium"})
    ctx.check(f"a scalar still clamps, got {fix}", fix is not None and fix.action == "clamp")


@test
def test_alnum9_ids_are_unique_and_mistral_shaped(ctx: Ctx):
    from halo_harness.providers import hooks
    seen = set()
    ids = [hooks.normalize_tool_id(raw, name="f", tool_id_format="alnum9", counter=[0], seen=seen)
           for raw in ("chatcmpl-tool-9f8e7d6c5b", "chatcmpl-tool-0a1b2c3d4e", "abc", "abc-", "Ab3dE6gH9")]
    ctx.check(f"all 9 alphanumerics, got {ids}", all(len(i) == 9 and i.isalnum() for i in ids))
    ctx.check(f"all distinct within the stream, got {ids}", len(set(ids)) == len(ids))
    ctx.check("a Mistral-native 9-char id is kept verbatim", ids[-1] == "Ab3dE6gH9")
    again = hooks.normalize_tool_id("chatcmpl-tool-9f8e7d6c5b", name="f", tool_id_format="alnum9", counter=[0])
    ctx.check("hashing is deterministic across streams", again == ids[0])


@test
def test_oai_stream_parallel_host_ids_never_collide(ctx: Ctx):
    from halo_harness.providers.oai_stream import OpenAIStreamToAnthropic
    sm = OpenAIStreamToAnthropic("m", 10, tool_id_format="alnum9")
    sm.feed_chunk({"choices": [{"index": 0, "delta": {"tool_calls": [
        {"index": 0, "id": "chatcmpl-tool-aaaa1111", "function": {"name": "Read", "arguments": "{}"}},
        {"index": 1, "id": "chatcmpl-tool-bbbb2222", "function": {"name": "Read", "arguments": "{}"}}]}}]})
    out = sm.feed_chunk({"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]})
    evs = out.get("events", []) + sm.on_eof() if hasattr(sm, "on_eof") else out.get("events", [])
    ids = [e["content_block"]["id"] for e in evs
           if e.get("type") == "content_block_start" and e["content_block"].get("type") == "tool_use"]
    ctx.check(f"two tool_use blocks with distinct ids, got {ids}", len(ids) == 2 and ids[0] != ids[1])


@test
def test_mid_stream_error_keeps_its_own_code(ctx: Ctx):
    from halo_harness.providers.errors import is_retryable_message
    from halo_harness.providers.oai_stream import OpenAIStreamToAnthropic
    from halo_harness.providers.responses_stream import ResponsesStreamToAnthropic

    def oai(err):
        return OpenAIStreamToAnthropic("m", 1).feed_chunk({"error": err})["events"][0]["error"]

    e = oai({"code": 402, "message": "Insufficient credits"})
    ctx.check(f"402 -> permission_error with status, got {e}", e["type"] == "permission_error" and e["status"] == 402)
    ctx.check("and is not retryable", is_retryable_message(e["status"], e["message"]) is False)
    e = oai({"type": "invalid_request_error", "message": "bad"})
    ctx.check(f"the chunk's own type is kept, got {e}", e["type"] == "invalid_request_error")
    e = oai({"code": 502, "message": "upstream down"})
    ctx.check(f"502 stays an overload, got {e}", e["type"] == "overloaded_error" and e["status"] == 502)
    e = oai({"message": "boom"})
    ctx.check(f"nothing named -> overloaded_error, no status, got {e}",
              e["type"] == "overloaded_error" and "status" not in e)
    rs = ResponsesStreamToAnthropic("m", 1)
    out = rs.feed_sse_line('data: {"type": "response.failed", "response": {"error": '
                           '{"code": "invalid_prompt", "message": "prompt rejected"}}}')
    e = out["events"][0]["error"]
    ctx.check(f"Responses invalid_prompt -> invalid_request_error, got {e}", e["type"] == "invalid_request_error")
    out = ResponsesStreamToAnthropic("m", 1).feed_sse_line(
        'data: {"type": "error", "error": {"code": "rate_limit_exceeded", "message": "slow"}}')
    ctx.check(f"Responses rate_limit_exceeded -> rate_limit_error, got {out['events'][0]['error']}",
              out["events"][0]["error"]["type"] == "rate_limit_error")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
