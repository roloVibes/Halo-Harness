"""tests.test_external_review_fixes -- the pinning module for the external
review's confirmed findings (2026-10-08), fixed in one pass:

  * R1  governor_state_unpersisted registered in EVENT_KINDS (crash class)
  * R2  flatten_content_parts: null reasoning summary text (crash class)
  * R3  manager.state_serves -- one predicate for "serving" states
  * R5  translate: plain-string content survives
  * R6  translate: parallel tool_calls in a non-streaming body stay SEPARATE
  * R7  StreamJsonSink: budget-exceeded captures THIS turn's partial text
  * R9  overflow retry exhausting the attempt budget raises ContextOverflow,
        never a retryable generic 502
  * R11 temporary allow rules are swept BY IDENTITY (a later permanent
        grant survives the same-turn sweep)
  * R13 stop_sequences translated to `stop`; negative-derived prompt_tokens
        floored at 0; tool-result text kept alongside an image marker
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()


# ---- R1: the event kind registry ---------------------------------------------


@test
def test_governor_state_unpersisted_kind_is_registered(ctx: Ctx):
    from halo_harness import events
    from halo_harness.events import EVENT_KINDS
    ctx.check("governor_state_unpersisted is in EVENT_KINDS",
              "governor_state_unpersisted" in EVENT_KINDS)
    ev = events.governor_state_unpersisted("disk unwritable")
    ctx.check("constructing it validates against the registry (no ValueError)",
              ev.kind == "governor_state_unpersisted" and ev.data == {"reason": "disk unwritable"})


# ---- R2: null reasoning summary text -------------------------------------------


@test
def test_flatten_content_parts_null_reasoning_text_never_raises(ctx: Ctx):
    from halo_harness.providers.errors import flatten_content_parts
    out = flatten_content_parts([
        {"type": "text", "text": "answer part"},
        {"type": "reasoning", "summary": [{"type": "text", "text": None}]},
        {"type": "reasoning", "summary": [{"type": "text", "text": "thinking"}]},
    ])
    ctx.check("null reasoning text is coerced, never len(None)", out == "answer part")
    out2 = flatten_content_parts([{"type": "text", "text": None}])
    ctx.check("null text block coerces to empty", out2 == "")
    out3 = flatten_content_parts([
        {"type": "reasoning", "summary": None},
        {"type": "text", "text": "after"},
    ])
    ctx.check("null summary list is tolerated", out3 == "after")


# ---- R3: state_serves -----------------------------------------------------------


@test
def test_state_serves_is_the_one_predicate(ctx: Ctx):
    from halo_harness.mcp.manager import state_serves
    ctx.check("connected serves", state_serves("connected"))
    ctx.check("cached serves (the deferred pool admits it)", state_serves("cached"))
    for non in ("pending", "pending_approval", "connecting", "failed", "disabled",
                "needs_auth", "closed", None):
        ctx.check(f"{non!r} does not serve", not state_serves(non))


# ---- R5/R6: translate -------------------------------------------------------------


def _anthropic_to_openai(body):
    from halo_harness.providers.routing import Route
    from halo_harness.providers.translate import anthropic_to_openai
    route = Route("openrouter", body.get("model", "x/y"), "openai-chat")
    payload = dict(body)
    payload.setdefault("max_tokens", 1024)
    return anthropic_to_openai(payload, route)


@test
def test_plain_string_content_survives_translation(ctx: Ctx):
    body = {"messages": [
        {"role": "user", "content": "Hello there"},
        {"role": "assistant", "content": [
            {"type": "text", "text": "I will check."},
            {"type": "tool_use", "id": "call_1", "name": "Read", "input": {"file_path": "x"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call_1", "content": "the file body"},
        ]},
    ]}
    oai = _anthropic_to_openai(body)
    texts = [m for m in oai["messages"] if m.get("role") == "user"]
    ctx.check(f"a user message SURVIVED (string content), got {[m.get('content') for m in texts]}",
              any(m.get("content") == "Hello there" for m in texts))
    ctx.check("the plain-string content rides as its own user turn",
              len([m for m in texts if m.get("content") == "Hello there"]) == 1)


@test
def test_parallel_tool_calls_nonstreaming_stay_separate(ctx: Ctx):
    from halo_harness.providers.oai_stream import MessageCollector, OpenAIStreamToAnthropic
    body = {"choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
        "role": "assistant",
        "content": "doing two things",
        "tool_calls": [
            {"id": "call_a", "type": "function", "function": {"name": "Read", "arguments": '{"file_path": "a"}'}},
            {"id": "call_b", "type": "function", "function": {"name": "Grep", "arguments": '{"pattern": "b"}'}},
        ],
    }}]}
    sm = OpenAIStreamToAnthropic("m", 10)
    evs = MessageCollector.to_events(body, sm)
    starts = [e for e in evs if e.get("type") == "content_block_start"
              and (e.get("content_block") or {}).get("type") == "tool_use"]
    names = [(e["content_block"].get("name"), e["content_block"].get("id")) for e in starts]
    ctx.check(f"exactly TWO separate tool_use blocks, got {names}", len(starts) == 2)
    if len(starts) == 2:
        # ids are normalized to the mint format (normalize_tool_id) -- the
        # pin is that each call keeps its own NAME and a DISTINCT id.
        ids = [s["content_block"]["id"] for s in starts]
        ctx.check("first call keeps its own name",
                  starts[0]["content_block"]["name"] == "Read")
        ctx.check("second call keeps its own name",
                  starts[1]["content_block"]["name"] == "Grep")
        ctx.check(f"the two ids are distinct, got {ids}", ids[0] != ids[1])
        deltas = [e for e in evs if e.get("type") == "content_block_delta"
                  and e.get("delta", {}).get("type") == "input_json_delta"]
        args = [e["delta"]["partial_json"] for e in deltas]
        ctx.check(f"arguments never concatenated across calls, got {args}",
                  args == ['{"file_path": "a"}', '{"pattern": "b"}'])


# ---- R7: StreamJsonSink budget capture ----------------------------------------------


@test
def test_streamjson_sink_budget_line_carries_this_turns_text(ctx: Ctx):
    import io
    from halo_harness import events
    from halo_harness.output import StreamJsonSink

    sink = StreamJsonSink(stream=io.StringIO(), model="m", session_id="s",
                          cwd=".", permission_mode="default", max_budget_usd=0.04)
    def _gen(evs):
        yield from evs

    # Turn 1 completes normally -> _final_text = "first answer".
    sink.consume(_gen([
        events.message_start(turn=1),
        events.text_delta("first answer", turn=1),
        events.message_end(turn=1, cost_usd=0.01),
        events.turn_done(turn=1, reason="end_turn"),
    ]))
    ctx.check("turn 1 recorded", sink.finish() == 0)
    # Turn 2 blows the budget mid-message (0.05 >= 0.04) -> must capture
    # "partial ", never "first answer".
    sink.consume(_gen([
        events.message_start(turn=2),
        events.text_delta("partial ", turn=2),
        events.message_end(turn=2, cost_usd=0.05),
    ]), finish=False)
    ctx.check("budget exceeded flagged", sink._budget_exceeded)
    ctx.check(f"the result text is THIS turn's partial, got {sink._final_text!r}",
              sink._final_text == "partial ")


# ---- R9: overflow vs re-dial budget ----------------------------------------------------


@test
def test_overflow_retry_exhausting_attempts_raises_contextoverflow(ctx: Ctx):
    from halo_harness.providers.stream import ContextOverflow, UpstreamError, _run_phase1_attempts

    class _Resp:
        def __init__(self, status):
            self.status = status
            self.headers = {}
            self.resp = None
            self.body_bytes = None

    calls = {"n": 0}

    def _call_upstream():
        calls["n"] += 1
        # Attempt 1: a post-connect failure (re-dial consumes attempt 0).
        # Attempt 2: a FIXABLE context overflow -- the fixable branch
        # `continue`s, the for/else fires, and the old code raised a
        # retryable generic 502 instead of ContextOverflow.
        if calls["n"] == 1:
            from halo_harness.providers.http import UpstreamConnectError
            raise UpstreamConnectError("connection reset by peer mid-response")
        return _Resp(400)

    class _Req:
        route = type("R", (), {"provider": "openrouter"})()
        creds = None

    class _ErrBody:
        status = 400

    # Feed the 400 body through a fake resp.read path: simplest is to
    # monkeypatch nothing -- _run_phase1_attempts reads result.resp; give
    # it a stub resp whose read() returns an OpenAI-shaped overflow body.
    class _Resp400(_Resp):
        def __init__(self):
            super().__init__(400)
            import http.client
            self.resp = type("FakeResp", (), {
                "read": lambda s: (b'{"error": {"message": "This model\'s maximum context length is 8192 tokens. '
                                   b'However, you requested 9000 tokens (7000 in the messages, 2000 max_tokens). '
                                   b'Please reduce the length of the messages or completion."}}'),
            })()

    def _call_upstream2():
        calls["n"] += 1
        if calls["n"] == 1:
            from halo_harness.providers.http import UpstreamConnectError
            raise UpstreamConnectError("connection reset by peer mid-response")
        return _Resp400()

    oai_body = {"max_tokens": 2000, "messages": []}
    try:
        _run_phase1_attempts(_Req(), oai_body, _call_upstream2, None, 2)
        ctx.check("raised ContextOverflow", False)
    except ContextOverflow as e:
        ctx.check(f"ContextOverflow raised (limit={e.limit})", e.limit == 8192)
    except UpstreamError as e:
        ctx.check(f"raised a retryable UpstreamError instead -- the bug: {e.message}", False)


# ---- R11: identity-based temporary sweep --------------------------------------------


@test
def test_temporary_rule_sweep_keeps_later_permanent_grants(ctx: Ctx):
    from halo_harness.permissions import PermissionEngine
    eng = PermissionEngine(mode="default", cwd=Path(tempfile.mkdtemp(prefix="permfix-")))
    ok1 = eng.add_session_allow_rule("Bash(echo hi:*)", temporary=True)
    ok2 = eng.add_session_allow_rule("Read(~/notes/**)", temporary=False)  # permanent, LATER same turn
    ctx.check("both rules added", ok1 and ok2)
    ctx.check("both live before the sweep", len(eng.allow_rules) == 2)
    eng.clear_temporary_allow_rules()
    remaining = [r.raw_text if hasattr(r, "raw_text") else str(r) for r in eng.allow_rules]
    ctx.check(f"exactly the permanent grant survives, got {remaining}",
              len(eng.allow_rules) == 1 and "Read" in str(remaining[0]))
    # And a second sweep is a clean no-op.
    eng.clear_temporary_allow_rules()
    ctx.check("second sweep no-op", len(eng.allow_rules) == 1)


# ---- R13: the three one-liners ---------------------------------------------------------


@test
def test_stop_sequences_translated_to_stop(ctx: Ctx):
    oai = _anthropic_to_openai({"messages": [{"role": "user", "content": "hi"}],
                                "stop_sequences": ["\nObservation:", "\nThought:"]})
    ctx.check("stop_sequences -> stop", oai.get("stop") == ["\nObservation:", "\nThought:"])
    oai2 = _anthropic_to_openai({"messages": [{"role": "user", "content": "hi"}]})
    ctx.check("absent stop_sequences stays absent", "stop" not in oai2)


@test
def test_negative_derived_prompt_tokens_is_floored(ctx: Ctx):
    from halo_harness.providers.errors import parse_context_overflow
    # A wording with total 500 but a requested max_tokens of 2000: the old
    # derivation made prompt_tokens = -1500, and the "clamped" retry budget
    # landed ABOVE the limit.
    ov = parse_context_overflow(400,
                                "maximum context length is 8192 tokens (requested: 500)",
                                None, requested_max_tokens=2000)
    ctx.check("parsed an overflow", ov is not None)
    if ov:
        ctx.check(f"prompt_tokens floored at 0, got {ov.prompt_tokens}", ov.prompt_tokens == 0)
        ctx.check("the retry budget never exceeds the limit",
                  (not ov.fixable) or (8192 - ov.prompt_tokens - 256) <= 8192)


@test
def test_tool_result_text_kept_alongside_image_marker(ctx: Ctx):
    body = {"messages": [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "call_img", "name": "Read", "input": {"file_path": "x.png"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call_img", "content": [
                {"type": "text", "text": "the image shows a chart"},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"}},
            ]},
        ]},
    ]}
    oai = _anthropic_to_openai(body)
    tool_msgs = [m for m in oai["messages"] if m.get("role") == "tool"]
    ctx.check("the tool message exists", len(tool_msgs) == 1)
    content = tool_msgs[0].get("content", "")
    ctx.check(f"the TEXT is kept alongside the marker, got {content!r}",
              "the image shows a chart" in content and "image in next message" in content)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
