"""tests.test_error_translation -- Halo 2.0.4 round 3 (deliverable 4):
providers.errors.map_upstream_error's generalised per-provider error-code/
type -> one plain Halo sentence table (OpenRouter, Anthropic, Databricks,
Hugging Face, OpenAI, Ollama's exceed_context_size_error already handled
elsewhere, and the generic status table), the context-overflow/connect-
failure/offline-refusal guards that keep those three message shapes byte-
for-byte unchanged, the Experiential `model_requires_purchase` 429 (named
model, never retried), and the print-mode empty-result fix (an unconfigured
provider, and a turn that exhausts its retries on a repeated upstream
failure) in halo_harness.output.PrintModeSink.
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_openai import MockUpstream, SCENARIOS, send_json_response
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()


# ---------------------------------------------------------------------------
# Table-driven: every provider's error shapes -> one plain sentence.
# ---------------------------------------------------------------------------

@test
def test_openrouter_code_table_and_generic_fallback(ctx: Ctx):
    from halo_harness.providers.errors import map_upstream_error

    # A code this round's OpenRouter table names.
    _, jbody, hdrs = map_upstream_error(402, {"error": {"message": "boom", "code": 402}}, "openrouter")
    ctx.check(f"402 -> the out-of-credit sentence, got {jbody['error']['message']!r}",
               "out of credit" in jbody["error"]["message"])
    ctx.check("402 never retried", hdrs.get("x-should-retry") == "false")

    # A status with no matching code -> the generic status sentence, never
    # the raw upstream text (and never empty).
    _, jbody2, hdrs2 = map_upstream_error(500, {"error": {"message": "weird raw text"}}, "openrouter")
    ctx.check(f"500 falls back to the generic sentence, got {jbody2['error']['message']!r}",
               "OpenRouter" in jbody2["error"]["message"] and jbody2["error"]["message"] != "weird raw text")
    ctx.check("500 still retryable", hdrs2.get("x-should-retry") == "true")


@test
def test_anthropic_error_type_table(ctx: Ctx):
    from halo_harness.providers.errors import map_upstream_error

    _, jbody, hdrs = map_upstream_error(401, {"error": {"type": "authentication_error", "message": "x"}}, "anthropic")
    ctx.check(f"authentication_error -> the key sentence, got {jbody['error']['message']!r}",
               "key" in jbody["error"]["message"].lower())
    ctx.check("authentication_error never retried", hdrs.get("x-should-retry") == "false")

    _, jbody2, hdrs2 = map_upstream_error(529, {"error": {"type": "overloaded_error", "message": "x"}}, "anthropic")
    ctx.check(f"overloaded_error -> a retry sentence, got {jbody2['error']['message']!r}",
               "overloaded" in jbody2["error"]["message"].lower())
    ctx.check("overloaded_error retried", hdrs2.get("x-should-retry") == "true")


@test
def test_databricks_error_code_table(ctx: Ctx):
    from halo_harness.providers.errors import map_upstream_error

    _, jbody, hdrs = map_upstream_error(429, {"error_code": "RESOURCE_EXHAUSTED", "message": "x"}, "databricks")
    ctx.check(f"RESOURCE_EXHAUSTED -> a rate-limit sentence, got {jbody['error']['message']!r}",
               "rate-limited" in jbody["error"]["message"])
    ctx.check("RESOURCE_EXHAUSTED retried", hdrs.get("x-should-retry") == "true")

    _, jbody2, hdrs2 = map_upstream_error(403, {"error_code": "PERMISSION_DENIED", "message": "x"}, "databricks")
    ctx.check(f"PERMISSION_DENIED -> a plain sentence, got {jbody2['error']['message']!r}",
               "can't reach" in jbody2["error"]["message"])
    ctx.check("PERMISSION_DENIED never retried", hdrs2.get("x-should-retry") == "false")


@test
def test_openai_error_code_table(ctx: Ctx):
    from halo_harness.providers.errors import map_upstream_error

    _, jbody, hdrs = map_upstream_error(401, {"error": {"code": "invalid_api_key", "message": "x"}}, "openai")
    ctx.check(f"invalid_api_key -> the key sentence, got {jbody['error']['message']!r}",
               "OPENAI_API_KEY" in jbody["error"]["message"])
    ctx.check("invalid_api_key never retried", hdrs.get("x-should-retry") == "false")

    _, jbody2, hdrs2 = map_upstream_error(429, {"error": {"code": "rate_limit_exceeded", "message": "x"}}, "openai")
    ctx.check(f"rate_limit_exceeded -> a retry sentence, got {jbody2['error']['message']!r}",
               "OpenAI" in jbody2["error"]["message"])
    ctx.check("rate_limit_exceeded retried", hdrs2.get("x-should-retry") == "true")


@test
def test_huggingface_and_ollama_use_the_generic_status_table(ctx: Ctx):
    """Neither provider has a dedicated code table (deliverable 4: "Ollama's
    exceed_context_size_error already handled" -- that shape never reaches
    this function at all, see providers.stream._ollama_overflow_info; any
    OTHER Ollama/HF error is an ordinary status this generic table covers)."""
    from halo_harness.providers.errors import map_upstream_error

    _, jbody, _ = map_upstream_error(404, {"error": "model not found"}, "huggingface")
    ctx.check(f"huggingface 404 -> the generic sentence naming the provider, got {jbody['error']['message']!r}",
               "Hugging Face" in jbody["error"]["message"])

    _, jbody2, _ = map_upstream_error(503, {"error": "no instance"}, "ollama")
    ctx.check(f"ollama 503 -> the generic sentence naming the provider, got {jbody2['error']['message']!r}",
               "Ollama" in jbody2["error"]["message"])


@test
def test_unrecognized_provider_still_gets_a_generic_sentence(ctx: Ctx):
    """A provider string this module has never heard of (a future route, or
    a test double) never crashes -- falls straight to the generic table."""
    from halo_harness.providers.errors import map_upstream_error
    _, jbody, _ = map_upstream_error(502, {"error": {"message": "x"}}, "some-future-provider")
    ctx.check(f"unrecognized provider -> still a non-empty, non-raw sentence, got {jbody['error']['message']!r}",
               bool(jbody["error"]["message"]) and jbody["error"]["message"] != "x")


# ---------------------------------------------------------------------------
# The three message shapes that must survive translation byte-for-byte.
# ---------------------------------------------------------------------------

@test
def test_overflow_wording_is_never_translated(ctx: Ctx):
    from halo_harness.providers.errors import build_prompt_too_long_message, map_upstream_error

    # The harness's own internally-built rewrite (bridge.py's ContextOverflow
    # branch) -- Claude Code's own compaction regex depends on this exact text.
    rewritten = build_prompt_too_long_message(9000, 8192)
    _, jbody, _ = map_upstream_error(400, {"error": {"message": rewritten}}, "anthropic")
    ctx.check(f"the harness-built overflow rewrite survives verbatim, got {jbody['error']['message']!r}",
               jbody["error"]["message"] == rewritten)

    # A real upstream overflow wording, for a provider that otherwise has a
    # code-table entry that would ALSO match this status/type.
    overflow_body = {"error": {"type": "invalid_request_error",
                                "message": "This model's maximum context length is 8192 tokens. "
                                           "However, you requested 9000 tokens."}}
    _, jbody2, _ = map_upstream_error(400, overflow_body, "anthropic")
    ctx.check(f"a real overflow wording survives verbatim even though 'invalid_request_error' is in the "
               f"Anthropic table, got {jbody2['error']['message']!r}",
               jbody2["error"]["message"] == overflow_body["error"]["message"])


@test
def test_connect_failure_and_offline_refusal_wordings_are_never_translated(ctx: Ctx):
    from halo_harness.providers.errors import map_upstream_error
    from halo_harness.providers.http import format_connect_error, format_offline_refusal

    raw = format_connect_error("your-workspace.cloud.databricks.com", "boom")
    _, jbody, _ = map_upstream_error(502, {"error": {"message": raw}}, "databricks")
    ctx.check(f"a connect-failure message survives map_upstream_error verbatim, got {jbody['error']['message']!r}",
               jbody["error"]["message"] == raw)

    offline_raw = format_offline_refusal("api.openai.com")
    _, jbody2, _ = map_upstream_error(502, {"error": {"message": offline_raw}}, "openai")
    ctx.check(f"an offline-refusal message survives map_upstream_error verbatim, got {jbody2['error']['message']!r}",
               jbody2["error"]["message"] == offline_raw)


# ---------------------------------------------------------------------------
# Experiential model_requires_purchase (added after the round 2 live checks).
# ---------------------------------------------------------------------------

@test
def test_experiential_model_requires_purchase_names_the_model_and_never_retries(ctx: Ctx):
    from halo_harness.providers.errors import map_upstream_error
    body = {"error": {"code": "model_requires_purchase",
                       "message": "space-bunny-alpha is locked on your account until you make a purchase"}}
    _, jbody, hdrs = map_upstream_error(429, body, "experiential")
    ctx.check(f"the model name reaches the client, got {jbody['error']['message']!r}",
               "space-bunny-alpha" in jbody["error"]["message"])
    ctx.check(f"one plain line, got {jbody['error']['message']!r}",
               jbody["error"]["message"] == "space-bunny-alpha is locked on your account until you make a purchase")
    ctx.check("never retried even though the generic 429 row defaults to True",
               hdrs.get("x-should-retry") == "false")


@test
def test_experiential_retryable_set_is_exactly_four_codes(ctx: Ctx):
    """Coordinator correction, 2026-10-05: the retryable set is EXACTLY
    unavailable_route/gateway_overloaded/all_routes_failed/
    backend_unavailable -- table-driven across every OTHER code this
    round added or already had, including two round-2 codes that were
    WRONGLY `True` before this fix (idempotency_replay_unavailable,
    internal_error) and one round-3 addition (zdr_continuation_disabled)."""
    from halo_harness.providers.errors import map_upstream_error

    def body(code):
        return {"error": {"code": code, "message": "x"}}

    retryable_codes = {"unavailable_route", "gateway_overloaded", "all_routes_failed", "backend_unavailable"}
    non_retryable_codes = {
        "invalid_json", "invalid_request", "invalid_parameter", "unsupported_capability", "unsupported_parameter",
        "refusal", "previous_response_not_found", "zdr_continuation_disabled", "invalid_key", "model_not_granted",
        "idempotency_conflict", "idempotency_replay_unavailable", "insufficient_quota", "org_under_review",
        "request_cancelled", "provider_internal", "provider_output_too_large", "gateway_draining",
        "deadline_exceeded", "internal_error", "pro_required", "model_requires_purchase",
    }
    for code in retryable_codes:
        _, _, hdrs = map_upstream_error(500, body(code), "experiential")
        ctx.check(f"{code} IS retryable, got {hdrs.get('x-should-retry')!r}", hdrs.get("x-should-retry") == "true")
    for code in non_retryable_codes:
        _, _, hdrs = map_upstream_error(500, body(code), "experiential")
        ctx.check(f"{code} is NOT retryable, got {hdrs.get('x-should-retry')!r}", hdrs.get("x-should-retry") == "false")


@test
def test_experiential_bare_non_json_502_still_gets_translated(ctx: Ctx):
    """Measured live, 2026-10-05: space-bunny-alpha answered "error code:
    502" with NO JSON body at all -- the synthetic body providers/
    stream.py builds on a JSON-parse failure (`{"error": {"message":
    raw_text}}`, no "code" field) must still reach a translated, non-
    empty sentence naming the status/provider, never the bare raw text."""
    from halo_harness.providers.errors import map_upstream_error
    _, jbody, hdrs = map_upstream_error(502, {"error": {"message": "error code: 502"}}, "experiential")
    ctx.check(f"translated, not the bare raw text, got {jbody['error']['message']!r}",
              jbody["error"]["message"] != "error code: 502" and bool(jbody["error"]["message"]))
    ctx.check(f"names the provider, got {jbody['error']['message']!r}", "Experiential Labs" in jbody["error"]["message"])
    ctx.check("502 still retryable (matches backend_unavailable/all_routes_failed in spirit)",
              hdrs.get("x-should-retry") == "true")


# ---------------------------------------------------------------------------
# output.PrintModeSink: the empty-print-mode-result bug.
# ---------------------------------------------------------------------------

@test
def test_json_mode_unconfigured_provider_result_is_not_empty(ctx: Ctx):
    """plans/2.0.3-release-notes-for-fix-pass.md: `halo -p ... --model or:x`
    with no OpenRouter credentials used to end with subtype
    error_during_execution and an EMPTY `result` in --output-format json,
    nothing on stderr either."""
    from halo_harness import events as ev
    from halo_harness.output import PrintModeSink

    stream = io.StringIO()
    sink = PrintModeSink(output_format="json", stream=stream)
    stderr_buf = io.StringIO()
    with redirect_stderr(stderr_buf):
        sink.consume(iter([ev.error("OpenRouter not configured -- set OPENROUTER_API_KEY", err_type="not_configured")]))
    obj = json.loads(stream.getvalue())
    ctx.check(f"subtype is error_during_execution, got {obj.get('subtype')!r}",
               obj.get("subtype") == "error_during_execution")
    ctx.check("is_error is True", obj.get("is_error") is True)
    ctx.check(f"result carries the provider's own sentence (never empty), got {obj.get('result')!r}",
               obj.get("result") == "OpenRouter not configured -- set OPENROUTER_API_KEY")
    ctx.check(f"the SAME sentence also reaches stderr, got {stderr_buf.getvalue()!r}",
               "OpenRouter not configured -- set OPENROUTER_API_KEY" in stderr_buf.getvalue())


@test
def test_text_mode_unconfigured_provider_result_is_not_empty(ctx: Ctx):
    """The text-format twin of the test above -- `finish()`'s text branch
    already worked before this round; pinned here so a future change can't
    silently regress it while fixing the JSON branch."""
    from halo_harness import events as ev
    from halo_harness.output import PrintModeSink

    stream = io.StringIO()
    sink = PrintModeSink(output_format="text", stream=stream)
    stderr_buf = io.StringIO()
    with redirect_stderr(stderr_buf):
        code = sink.consume(iter([ev.error("Databricks not configured -- run `halo init --preset work`",
                                            err_type="not_configured")]))
    ctx.check(f"non-zero exit code, got {code}", code == 1)
    ctx.check(f"stdout stays empty (text mode never prints a bare error to stdout), got {stream.getvalue()!r}",
               stream.getvalue() == "")
    ctx.check(f"the sentence reaches stderr, got {stderr_buf.getvalue()!r}",
               "Databricks not configured" in stderr_buf.getvalue())


@test
def test_json_mode_budget_exceeded_still_gets_a_stderr_line(ctx: Ctx):
    """The --max-budget-usd branch stayed untouched by this fix (`result`
    keeps showing whatever partial reply was captured) -- only the NEW
    stderr line is this round's addition, mirrored from the text branch."""
    from halo_harness import events as ev
    from halo_harness.output import PrintModeSink

    def _events():
        # consume() calls event_iter.close() once the budget trips (so a
        # still-open upstream generator stops promptly) -- a real
        # generator, never a bare list_iterator (which has no .close()).
        yield ev.message_start()
        yield ev.text_delta("partial")
        yield ev.message_end(stop_reason="end_turn", usage={}, cost_usd=0.05)

    stream = io.StringIO()
    sink = PrintModeSink(output_format="json", stream=stream, max_budget_usd=0.01)
    stderr_buf = io.StringIO()
    with redirect_stderr(stderr_buf):
        sink.consume(_events())
    obj = json.loads(stream.getvalue())
    ctx.check(f"subtype is error_max_budget_usd, got {obj.get('subtype')!r}", obj.get("subtype") == "error_max_budget_usd")
    ctx.check(f"stderr names the budget, got {stderr_buf.getvalue()!r}",
               "max-budget-usd" in stderr_buf.getvalue())


# ---------------------------------------------------------------------------
# End to end: a turn that exhausts its retries on a repeated 502 (added
# after the round 2 live checks). No Retry-After header the mock sends
# would otherwise cost real wall time through the exponential backoff
# ladder -- `Retry-After: 0` keeps this test fast, same seam
# tests/test_w5_fallback_model.py already uses for its own 429 case.
# ---------------------------------------------------------------------------

@test
def test_retries_exhausted_on_repeated_502_reports_status_and_sentence(ctx: Ctx):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds

    calls = {"n": 0}

    def _scn_always_502(h, body):
        calls["n"] += 1
        send_json_response(h, 502, {"error": {"message": "error code: 502"}}, {"Retry-After": "0"})

    SCENARIOS["always-502-exhausted"] = _scn_always_502
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
        os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
        session_ctx = SessionContext(cwd=fh["proj"], model_label="or:mock/always-502-exhausted")
        model_ref = parse_model_ref("or:mock/always-502-exhausted")
        session = Session(
            cwd=fh["proj"], model_ref=model_ref, model_profile=ModelProfile(),
            creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
            state_dir=Path(tempfile.mkdtemp(prefix="error-exhaustion-")), model_label=model_ref.raw,
            session_context=session_ctx, openrouter_base_url=mock.base_url, max_turns=4,
        )
        events_seen = list(session.turn("hi"))
        ctx.check(f"six attempts (MAX_RETRIES=5 + the first), got {calls}", calls["n"] == 6)
        errors = [e for e in events_seen if e.kind == "error"]
        ctx.check(f"exactly one error event ended the turn, got {len(errors)}", len(errors) == 1)
        message = errors[0].data.get("message", "") if errors else ""
        ctx.check(f"names the LAST upstream status (502), got {message!r}", "502" in message)
        ctx.check(f"carries the translated sentence, not the bare raw text, got {message!r}",
                   "OpenRouter" in message and message != "error code: 502")

        # The SAME events, fed through PrintModeSink (JSON mode) -- the
        # empty-result bug this round's "Added after the round 2 live
        # checks" section names: result/stderr must carry this exact line.
        from halo_harness.output import PrintModeSink
        stream = io.StringIO()
        sink = PrintModeSink(output_format="json", stream=stream)
        stderr_buf = io.StringIO()
        with redirect_stderr(stderr_buf):
            sink.consume(iter(events_seen))
        obj = json.loads(stream.getvalue())
        ctx.check(f"print-mode result is the SAME line, never empty, got {obj.get('result')!r}",
                   obj.get("result") == message and bool(message))
        ctx.check(f"the SAME line also reaches stderr, got {stderr_buf.getvalue()!r}", message in stderr_buf.getvalue())
    finally:
        mock.stop()
        os.environ.pop("BRIDGE_OPENROUTER_BASE_URL", None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
