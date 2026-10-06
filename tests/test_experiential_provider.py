"""tests.test_experiential_provider -- Halo 2.0.4 round 2: the `xp:` route
onto the Experiential Labs gateway (plans/2.0.3-ollama-round2-brief.md
"Round 5h"), wired into the real agent loop end to end through the real
`-p` CLI entry point, against the parameterized tests.helpers.mock_openai/
mock_anthropic fakes -- plus direct unit tests for the pieces that need no
network at all (dialect selection, the error table, the gateway object,
tool search, the learned-rule notice). No real EXPLABS_API_KEY exists on
this build host and none is requested here: these fakes ARE the
verification; see docs/harness/EXPERIENTIAL-RESEARCH.md and this round's
hand-back for the exact live checks the orchestrator should run.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tests.helpers.mock_openai as mock_openai_mod
from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_openai import MockUpstream
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()


def _hermetic_child_env() -> dict:
    env = dict(os.environ)
    env.pop("BRIDGE_STATE_DIR", None)
    for k in [k for k in env if k.startswith("HALO_")]:
        env.pop(k, None)
    env.pop("EXPLABS_API_KEY", None)
    env.pop("EXPLABS_PROVISIONING_KEY", None)
    return env


def _run_cli(fh, prompt, *, model: str, extra_env=None, extra_args=None, timeout=30):
    env = _hermetic_child_env()
    env.update({"BRIDGE_TEST_HOME": str(fh["home"]), "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
                "PYTHONPATH": str(REPO_DIR)})
    env.update(extra_env or {})
    args = [sys.executable, "-m", "halo_harness", "-p", prompt, "--model", model,
            "--cwd", str(fh["proj"]), "--permission-mode", "auto"] + (extra_args or [])
    return subprocess.run(args, env=env, cwd=str(REPO_DIR), capture_output=True, text=True, timeout=timeout)


def _posts(mock, path_suffix: str) -> list:
    return [r for r in mock.requests if r["method"] == "POST" and r["path"].rstrip("/").endswith(path_suffix)]


# ---------------------------------------------------------------------------
# Deliverable 1 (provider): ref parsing, three dialects, credentials
# ---------------------------------------------------------------------------

@test
def test_xp_prefix_parses_three_dialects(ctx: Ctx):
    from halo_harness.model import parse_model_ref

    chat = parse_model_ref("xp:space-bunny-alpha")
    ctx.check(f"default dialect is openai-chat, got {chat!r}",
              chat.provider == "experiential" and chat.dialect == "openai-chat" and chat.model == "space-bunny-alpha")

    claude = parse_model_ref("xp:claude-haiku-4.5")
    ctx.check(f"a Claude slug goes anthropic-passthrough, got {claude!r}",
              claude.provider == "experiential" and claude.dialect == "anthropic-passthrough")

    try:
        parse_model_ref("xp:")
        ctx.check("xp: with no slug must raise", False)
    except Exception as e:
        ctx.check(f"clear message naming xp:, got {e}", "xp:" in str(e))

    # the generic "no route" message lists xp: among the accepted forms.
    try:
        parse_model_ref("not-a-real-provider:anything")
    except Exception as e:
        ctx.check(f"xp: listed in the accepted-forms message, got {e}", "xp:" in str(e))


@test
def test_resolve_experiential_config(ctx: Ctx):
    from halo_harness.providers.config import resolve_experiential
    ctx.check("None with no key", resolve_experiential({}) is None)
    cfg = resolve_experiential({"EXPLABS_API_KEY": "xpl_" + "a" * 40})
    ctx.check(f"default base_url, got {cfg.base_url!r}", cfg.base_url == "https://api.experientiallabs.ai/v1")
    ctx.check(f"default account_base_url, got {cfg.account_base_url!r}",
              cfg.account_base_url == "https://api.experientiallabs.ai/api/v1")
    overridden = resolve_experiential({
        "EXPLABS_API_KEY": "xpl_" + "a" * 40,
        "HALO_EXPERIENTIAL_BASE_URL": "http://127.0.0.1:9/v1",
        "HALO_EXPERIENTIAL_ACCOUNT_BASE_URL": "http://127.0.0.1:9/api/v1",
    })
    ctx.check(f"base_url override honored, got {overridden.base_url!r}", overridden.base_url == "http://127.0.0.1:9/v1")
    ctx.check(f"account_base_url override honored, got {overridden.account_base_url!r}",
              overridden.account_base_url == "http://127.0.0.1:9/api/v1")


@test
def test_profile_resolution_reads_catalog_capabilities(ctx: Ctx):
    from halo_harness.providers.experiential_catalog import write_xp_models_json
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.routing import Route
    state_dir = Path(tempfile.mkdtemp(prefix="xp-profile-"))
    write_xp_models_json(state_dir, {
        "no-tools-model": {"supports_tools": False, "supports_reasoning": False,
                            "supports_structured_output": False},
        "reasoning-model": {"supports_tools": True, "supports_reasoning": True,
                             "supported_reasoning_efforts": ["low", "high"], "reasoning_effort": "high"},
    })
    route = Route(provider="experiential", upstream_model="no-tools-model", dialect="openai-chat")
    profile = resolve_profile(route, state_dir=state_dir)
    ctx.check("no OpenRouter-only fields on this profile", profile.host_specific_fields is False)
    ctx.check(f"tools_supported reads the catalog row, got {profile.tools_supported!r}",
              profile.tools_supported is False)
    ctx.check(f"supports_structured_output reads the catalog row, got {profile.supports_structured_output!r}",
              profile.supports_structured_output is False)

    route2 = Route(provider="experiential", upstream_model="reasoning-model", dialect="openai-chat")
    profile2 = resolve_profile(route2, state_dir=state_dir)
    ctx.check("reasoning_effort_supported True from the catalog", profile2.reasoning_effort_supported is True)
    ctx.check(f"effort_values_supported comes from the catalog row, got {profile2.effort_values_supported!r}",
              profile2.effort_values_supported == ("low", "high"))
    ctx.check(f"reasoning_default_effort from the catalog, got {profile2.reasoning_default_effort!r}",
              profile2.reasoning_default_effort == "high")

    # An untracked model (no catalog row at all) keeps the generic
    # profile's own permissive defaults -- "untracked, assume yes".
    route3 = Route(provider="experiential", upstream_model="brand-new-unlisted", dialect="openai-chat")
    profile3 = resolve_profile(route3, state_dir=state_dir)
    ctx.check("untracked model stays tools_supported=True", profile3.tools_supported is True)
    ctx.check("untracked model stays supports_structured_output=True", profile3.supports_structured_output is True)


@test
def test_creds_not_configured_messages_name_the_real_env_var(ctx: Ctx):
    from halo_harness.controller import _not_configured_message
    from halo_harness.agent.subagent import _child_credential_message
    from halo_harness.model import ModelRef
    ref = ModelRef(raw="xp:space-bunny-alpha", provider="experiential", model="space-bunny-alpha", dialect="openai-chat")
    for fn in (_not_configured_message, _child_credential_message):
        msg = fn(ref)
        ctx.check(f"{fn.__name__} names EXPLABS_API_KEY, got {msg!r}", "EXPLABS_API_KEY" in msg)


# ---------------------------------------------------------------------------
# End to end: chat dialect through the real CLI entry point
# ---------------------------------------------------------------------------

@test
def test_chat_dialect_end_to_end_bearer_and_wire_shape(ctx: Ctx):
    fh = build_fake_home()
    mock = MockUpstream(path_prefix="/v1", expected_bearer="chat-test-token").start()
    try:
        result = _run_cli(fh, "say hi please", model="xp:mock/xp-echo-body",
                           extra_env={"EXPLABS_API_KEY": "chat-test-token", "HALO_EXPERIENTIAL_BASE_URL": mock.base_url})
        ctx.check(f"exit 0, got {result.returncode} stderr={result.stderr[-800:]!r}", result.returncode == 0)

        chats = _posts(mock, "/chat/completions")
        ctx.check(f"exactly one chat-completions call recorded, got {len(chats)}", len(chats) == 1)
        req = chats[0]
        ctx.check(f"model on the wire, got {req['body'].get('model')!r}", req["body"].get("model") == "mock/xp-echo-body")
        ctx.check(f"bearer is EXPLABS_API_KEY, got {req['headers'].get('authorization')!r}",
                  req["headers"].get("authorization") == "Bearer chat-test-token")

        ctx.check(f"no OpenRouter-only fields on the wire, got body keys {sorted(req['body'].keys())!r}",
                  "usage" not in req["body"] and "provider" not in req["body"] and "transforms" not in req["body"])
        ctx.check(f"gateway.retry default sent, got {req['body'].get('gateway')!r}",
                  req["body"].get("gateway") == {"retry": {"max_attempts_per_route": 1}})
        ctx.check(f"safety_identifier carries a real session id, got {req['body'].get('safety_identifier')!r}",
                  isinstance(req["body"].get("safety_identifier"), str) and req["body"]["safety_identifier"])
    finally:
        mock.stop()


@test
def test_claude_slug_routes_through_anthropic_passthrough_with_x_api_key(ctx: Ctx):
    """research doc section 1/3.3: a Claude slug goes through Halo's
    existing Anthropic passthrough at `/v1/messages` with `x-api-key` --
    `ExpConfig.base_url` already carries the gateway's own `/v1` path
    segment, so the path actually requested must be `/v1/messages`
    exactly once, never a doubled `/v1/v1/messages`."""
    from tests.helpers.mock_anthropic import MockAnthropic
    fh = build_fake_home()
    mock = MockAnthropic().start()
    try:
        result = _run_cli(fh, "say hi please", model="xp:claude-xp-plain-test",
                           extra_env={"EXPLABS_API_KEY": "claude-test-token",
                                      "HALO_EXPERIENTIAL_BASE_URL": mock.base_url + "/v1"})
        ctx.check(f"exit 0, got {result.returncode} stderr={result.stderr[-800:]!r}", result.returncode == 0)
        ctx.check(f"the scenario's reply reached stdout, got {result.stdout!r}", "pong" in result.stdout)
        ctx.check(f"exactly one call recorded, got {len(mock.requests)}", len(mock.requests) == 1)
        req = mock.requests[-1]
        ctx.check(f"path is /v1/messages exactly (not doubled), got {req['path']!r}", req["path"] == "/v1/messages")
        ctx.check(f"x-api-key carries the key, got {req['headers'].get('x-api-key')!r}",
                  req["headers"].get("x-api-key") == "claude-test-token")
        ctx.check("no Bearer Authorization header on this dialect", "authorization" not in req["headers"])
    finally:
        mock.stop()


# ---------------------------------------------------------------------------
# Cost/provider/is_byok/request_id capture (direct oai_stream unit test --
# no network: proves the capture mechanism itself, the end-to-end test
# above already proves the wire shape reaches a real stream_completion call).
# ---------------------------------------------------------------------------

@test
def test_cost_provider_is_byok_request_id_captured(ctx: Ctx):
    from halo_harness.providers.oai_stream import OpenAIStreamToAnthropic
    sm = OpenAIStreamToAnthropic("xp:qwen3.8-27b", 10, capture_reasoning=True, strict_tool_json=True)
    sm.request_id = "req_mock_abc"  # set by providers.stream.stream_completion from result.headers
    sm.ignored_parameters_header = "top_p->dropped(...)"
    sm.gateway_warning = "empty_completion"
    sm.feed_chunk({"choices": [{"index": 0, "delta": {"role": "assistant"}}]})
    sm.feed_chunk({"choices": [{"index": 0, "delta": {"content": "pong"}}]})
    sm.feed_chunk({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                   "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.00018208},
                   "provider": "experiential_cloud", "is_byok": False})
    events = sm.on_eof()
    delta = next(e for e in events if e["type"] == "message_delta")
    ctx.check(f"usage.cost flows through map_usage, got {delta['usage']!r}", delta["usage"].get("cost") == 0.00018208)
    meta = delta["harness_meta"]
    ctx.check(f"responding_provider captured, got {meta.get('responding_provider')!r}",
              meta.get("responding_provider") == "experiential_cloud")
    ctx.check(f"responding_is_byok captured, got {meta.get('responding_is_byok')!r}",
              meta.get("responding_is_byok") is False)
    ctx.check(f"request_id carried through, got {meta.get('request_id')!r}", meta.get("request_id") == "req_mock_abc")
    ctx.check("ignored_parameters_header carried through", meta.get("ignored_parameters_header") == "top_p->dropped(...)")
    ctx.check("gateway_warning carried through", meta.get("gateway_warning") == "empty_completion")


@test
def test_round5_body_sourced_ignored_params_and_usage_is_byok_and_route_headers(ctx: Ctx):
    """Halo 2.0.4 round 5 (xp: contract alignment): llms.txt states that
    `x-experiential-ignored-parameters` is a JSON BODY field (not a
    header, despite the name) and that BYOK is `usage.is_byok`, not (only)
    a top-level per-chunk field -- both read straight off the wire chunks
    here, overriding whatever a header-sourced preset left behind. The
    four new per-response headers (`x-gateway-provider`/`-zdr`/
    `-route-depth`/`-route-reason`) are set the same way `request_id`
    already is -- by the caller, right after construction -- and must
    reach `harness_meta` unchanged."""
    from halo_harness.providers.oai_stream import OpenAIStreamToAnthropic
    sm = OpenAIStreamToAnthropic("xp:qwen3.8-27b", 10, capture_reasoning=True, strict_tool_json=True)
    sm.request_id = "req_mock_def"
    sm.ignored_parameters_header = None  # never set by a header this time -- only the body field below
    sm.gateway_provider = "bedrock"
    sm.gateway_zdr = "true"
    sm.gateway_route_depth = "2"
    sm.gateway_route_reason = "primary_unavailable"
    sm.feed_chunk({"choices": [{"index": 0, "delta": {"role": "assistant"}}]})
    sm.feed_chunk({"choices": [{"index": 0, "delta": {"content": "pong"}}],
                   "x-experiential-ignored-parameters": ["reasoning_effort->none(max_tokens_headroom)"]})
    sm.feed_chunk({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                   "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0, "is_byok": True},
                   "provider": "fireworks"})
    events = sm.on_eof()
    meta = next(e for e in events if e["type"] == "message_delta")["harness_meta"]
    ctx.check(f"ignored params came from the BODY field, got {meta.get('ignored_parameters_header')!r}",
              meta.get("ignored_parameters_header") == "reasoning_effort->none(max_tokens_headroom)")
    ctx.check(f"is_byok came from usage.is_byok, got {meta.get('responding_is_byok')!r}",
              meta.get("responding_is_byok") is True)
    ctx.check(f"gateway_provider carried through, got {meta.get('gateway_provider')!r}",
              meta.get("gateway_provider") == "bedrock")
    ctx.check(f"gateway_zdr carried through, got {meta.get('gateway_zdr')!r}", meta.get("gateway_zdr") == "true")
    ctx.check(f"gateway_route_depth carried through, got {meta.get('gateway_route_depth')!r}",
              meta.get("gateway_route_depth") == "2")
    ctx.check(f"gateway_route_reason carried through, got {meta.get('gateway_route_reason')!r}",
              meta.get("gateway_route_reason") == "primary_unavailable")


@test
def test_responding_provider_label_and_route_label_for_experiential(ctx: Ctx):
    """agent/loop.py's `_responding_provider_label`/`_ROUTE_LABELS` --
    unit-tested directly against a minimal stand-in rather than a full
    Session (that class needs a live turn to construct `_StepResult`)."""
    import types
    from halo_harness.agent.loop import Session
    ctx.check(f"route label, got {Session._ROUTE_LABELS.get('experiential')!r}",
              Session._ROUTE_LABELS.get("experiential") == "xp")
    fake_self = types.SimpleNamespace(model_ref=types.SimpleNamespace(provider="experiential"))
    fake_result = types.SimpleNamespace(responding_provider="experiential_cloud")
    label = Session._responding_provider_label(fake_self, fake_result)
    ctx.check(f"uses the per-chunk provider when captured, got {label!r}", label == "experiential_cloud")
    fake_result_blank = types.SimpleNamespace(responding_provider=None)
    label_blank = Session._responding_provider_label(fake_self, fake_result_blank)
    ctx.check(f"falls back to the bare label, got {label_blank!r}", label_blank == "experiential")


# ---------------------------------------------------------------------------
# Error translation: the gateway's own `error.code` table (section 7)
# ---------------------------------------------------------------------------

@test
def test_error_table_plain_sentences_and_idempotency_409_split(ctx: Ctx):
    from halo_harness.providers.errors import map_upstream_error

    def body(code, message="boom"):
        return {"error": {"message": message, "code": code}}

    status, jbody, hdrs = map_upstream_error(400, body("unsupported_capability"), "experiential")
    ctx.check(f"plain sentence replaces the raw message, got {jbody['error']['message']!r}",
              "pick a model whose catalog row says it can" in jbody["error"]["message"])
    ctx.check("never retried", hdrs.get("x-should-retry") == "false")

    status, jbody, hdrs = map_upstream_error(402, body("pro_required"), "experiential")
    ctx.check(f"pro_required plain sentence, got {jbody['error']['message']!r}",
              "Pro plan" in jbody["error"]["message"])

    # The SAME HTTP 409 splits two ways by the gateway's own code -- a
    # status-only table cannot tell these apart.
    _, jbody_a, hdrs_a = map_upstream_error(409, body("idempotency_conflict"), "experiential")
    ctx.check("idempotency_conflict is never retried", hdrs_a.get("x-should-retry") == "false")
    _, jbody_b, hdrs_b = map_upstream_error(409, body("idempotency_replay_unavailable"), "experiential")
    # Halo 2.0.4 round 3 (deliverable 4, corrected against the gateway's
    # own published reference, 2026-10-05): the retryable set is EXACTLY
    # unavailable_route/gateway_overloaded/all_routes_failed/
    # backend_unavailable -- NOT idempotency_replay_unavailable (the
    # gateway's own fix needs a NEW Idempotency-Key, never a blind
    # identical retry, which Halo's own retry ladder would send).
    ctx.check("idempotency_replay_unavailable is NOT retried automatically", hdrs_b.get("x-should-retry") == "false")

    # A code this table doesn't recognize now falls through to the
    # GENERIC per-status sentence (round 3: a bare, non-JSON 502 body --
    # "error code: 502", no "code" field at all -- must also be
    # translated, not left as untranslated raw text).
    _, jbody_c, hdrs_c = map_upstream_error(500, {"error": {"message": "weird upstream text"}}, "experiential")
    ctx.check(f"unrecognized code gets the generic sentence, not the raw text, got {jbody_c['error']['message']!r}",
              jbody_c["error"]["message"] != "weird upstream text" and "Experiential Labs" in jbody_c["error"]["message"])
    ctx.check("5xx still retryable by the generic table", hdrs_c.get("x-should-retry") == "true")

    # A non-experiential provider is completely unaffected.
    _, jbody_d, _ = map_upstream_error(400, body("unsupported_capability"), "openrouter")
    ctx.check("openrouter never goes through the experiential table",
              jbody_d["error"]["message"] == "boom")


@test
def test_pro_required_402_and_unsupported_parameter_400_through_run_phase1(ctx: Ctx):
    from halo_harness.providers.routing import Route
    from halo_harness.providers.stream import CompletionRequest, ProviderCreds, UpstreamError, _run_phase1
    mock = MockUpstream(path_prefix="/v1").start()
    try:
        state_dir = Path(tempfile.mkdtemp(prefix="xp-err-"))
        route = Route(provider="experiential", upstream_model="mock-err", dialect="openai-chat")
        for scenario, expect_status, expect_substr in (
            ("xp-pro-required-402", 402, "Pro plan"),
            ("xp-unsupported-parameter-400", 400, "doesn't accept"),
        ):
            creds = ProviderCreds(base_url=mock.base_url, api_key="irrelevant")
            req = CompletionRequest(body={}, route=route, profile={}, creds=creds, state_dir=state_dir,
                                     extra_headers={}, model_label="xp:mock-err",
                                     prebuilt_oai_body={"model": f"mock/{scenario}"})
            try:
                _run_phase1(req)
                ctx.check(f"{scenario} must raise UpstreamError", False)
            except UpstreamError as e:
                ctx.check(f"{scenario}: status {expect_status}, got {e.status}", e.status == expect_status)
                ctx.check(f"{scenario}: plain message contains {expect_substr!r}, got {e.message!r}",
                          expect_substr in e.message)
    finally:
        mock.stop()


@test
def test_unavailable_route_retries_once_then_succeeds_end_to_end(ctx: Ctx):
    """research doc section 7: `unavailable_route` (429/503) is retryable
    -- Halo's own outer retry ladder (agent/loop.py) must actually retry
    it, not just classify it correctly in isolation."""
    fh = build_fake_home()
    mock = MockUpstream(path_prefix="/v1").start()
    scenario_name = "xp-unavailable-then-ok"
    mock_openai_mod.SCENARIOS[scenario_name] = mock_openai_mod._XpUnavailableRouteThenOk()
    try:
        result = _run_cli(fh, "say hi please", model=f"xp:mock/{scenario_name}",
                           extra_env={"EXPLABS_API_KEY": "retry-test-token", "HALO_EXPERIENTIAL_BASE_URL": mock.base_url})
        ctx.check(f"exit 0, got {result.returncode} stderr={result.stderr[-800:]!r}", result.returncode == 0)
        ctx.check(f"recovered after the retry, got {result.stdout!r}", "recovered" in result.stdout)
        calls = _posts(mock, "/chat/completions")
        ctx.check(f"exactly two attempts (503 then 200), got {len(calls)}", len(calls) == 2)
    finally:
        mock.stop()
        mock_openai_mod.SCENARIOS.pop(scenario_name, None)


# Tool search, the gateway object, structured-output gate, dialect
# overrides, the ignored-parameters learned rule, and the init wizard tab
# are tested in tests/test_experiential_wire.py (split out to keep this
# file under the house ~400-line convention).


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
