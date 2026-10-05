"""tests.test_w5_betas_header -- W5 (carried from W4a): `--betas` must send
`anthropic-beta` only on an Anthropic-family route (`ant:`, or a Databricks
Claude PASSTHROUGH model) -- live bug found wiring this in: the old code
set `extra_headers["anthropic-beta"]` regardless of route, and `providers/
http.py::call_openai_chat` (the `or:`/Databricks-CHAT wire path) merges
WHATEVER headers it's handed with no allowlist of its own, so the header
was actually reaching OpenRouter and Databricks-chat requests too.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()
ensure_default_provider_credentials()
test, TESTS = new_registry()


def _build(model_ref_raw: str, betas):
    from halo_harness import headless
    cwd = Path(tempfile.mkdtemp(prefix="w5-betas-"))
    return headless.build_session(cwd=cwd, model_ref_raw=model_ref_raw, bare=True, print_mode=True,
                                   max_turns=3, cli_flags={"betas": betas})


@test
def test_betas_header_sent_on_ant_route(ctx: Ctx):
    build = _build("ant:claude-opus-4", ["beta-x"])
    ctx.check(f"dialect is anthropic-passthrough, got {build.session.model_ref.dialect}",
              build.session.model_ref.dialect == "anthropic-passthrough")
    ctx.check(f"anthropic-beta IS sent on ant:, got {build.session.extra_headers}",
              build.session.extra_headers.get("anthropic-beta") == "beta-x")


@test
def test_betas_header_sent_on_databricks_claude_passthrough(ctx: Ctx):
    build = _build("dbx:databricks-claude-test@anthropic", ["beta-x"])
    ctx.check(f"dialect is anthropic-passthrough, got {build.session.model_ref.dialect}",
              build.session.model_ref.dialect == "anthropic-passthrough")
    ctx.check(f"anthropic-beta IS sent on a Databricks Claude passthrough model, got {build.session.extra_headers}",
              build.session.extra_headers.get("anthropic-beta") == "beta-x")


@test
def test_betas_header_never_sent_on_databricks_chat(ctx: Ctx):
    build = _build("dbx:databricks-meta-llama-3-1-70b-instruct", ["beta-x"])
    ctx.check(f"dialect is openai-chat (NOT passthrough), got {build.session.model_ref.dialect}",
              build.session.model_ref.dialect == "openai-chat")
    ctx.check(f"anthropic-beta is NEVER sent on Databricks chat, got {build.session.extra_headers}",
              "anthropic-beta" not in (build.session.extra_headers or {}))


@test
def test_betas_header_never_sent_on_openrouter(ctx: Ctx):
    build = _build("or:some-vendor/some-model", ["beta-x"])
    ctx.check(f"dialect is openai-chat, got {build.session.model_ref.dialect}",
              build.session.model_ref.dialect == "openai-chat")
    ctx.check(f"anthropic-beta is NEVER sent on OpenRouter, got {build.session.extra_headers}",
              "anthropic-beta" not in (build.session.extra_headers or {}))


@test
def test_betas_header_never_reaches_a_real_openrouter_wire_request(ctx: Ctx):
    """The brief's own acceptance line, end to end: drive a REAL turn
    against a mock OpenRouter upstream with `--betas` set and confirm the
    actual HTTP request headers never carry `anthropic-beta` -- not just
    that `Session.extra_headers` looks right, but that nothing ELSE in the
    request-building pipeline re-adds it."""
    from tests.helpers.mock_openai import MockUpstream

    mock = MockUpstream().start()
    old_base_url = os.environ.get("BRIDGE_OPENROUTER_BASE_URL")
    os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
    try:
        build = _build("or:mock/model", ["beta-x"])
        list(build.session.turn("hi"))
        ctx.check(f"the mock upstream received exactly one call, got {len(mock.requests)}",
                  len(mock.requests) == 1)
        headers = mock.requests[0]["headers"]
        ctx.check(f"anthropic-beta never reached the real wire request, got headers={headers}",
                  "anthropic-beta" not in headers)
    finally:
        mock.stop()
        if old_base_url is None:
            os.environ.pop("BRIDGE_OPENROUTER_BASE_URL", None)
        else:
            os.environ["BRIDGE_OPENROUTER_BASE_URL"] = old_base_url


# ---- pass-B finding 10 (major): extra_headers rebuilt per request's route ----

@test
def test_databricks_custom_headers_absent_after_switching_to_openrouter(ctx: Ctx):
    """The brief's own pinning scenario: a session that STARTS on `dbx:`
    with `ANTHROPIC_CUSTOM_HEADERS` set carries the Databricks headers at
    session start (sanity-checked below) -- `extra_headers` used to be
    computed ONCE from the starting route and handed to every later
    `_build_request` call verbatim, so those same headers (the custom one
    AND the default `x-databricks-use-coding-agent-mode`) kept riding on
    every request after a `/model` switch onto a completely different
    provider. A REAL turn against a mock OpenRouter upstream, after
    switching, must never carry either one."""
    from halo_harness.model import ModelProfile, parse_model_ref
    from tests.helpers.mock_openai import MockUpstream

    old_custom = os.environ.get("ANTHROPIC_CUSTOM_HEADERS")
    os.environ["ANTHROPIC_CUSTOM_HEADERS"] = "X-Test-Dbx-Org: dbx-secret-org"
    mock = MockUpstream().start()
    try:
        build = _build("dbx:databricks-meta-llama-3-1-70b-instruct", None)
        session = build.session
        ctx.check(f"sanity: the custom header IS present at session start, got {session.extra_headers}",
                  session.extra_headers.get("X-Test-Dbx-Org") == "dbx-secret-org")
        ctx.check(f"sanity: the default coding-agent-mode header is ALSO present at start, got {session.extra_headers}",
                  "x-databricks-use-coding-agent-mode" in session.extra_headers)

        from halo_harness.providers.stream import ProviderCreds
        new_ref = parse_model_ref("or:mock/model")
        session.set_model(new_ref, ModelProfile(), creds=ProviderCreds(base_url=mock.base_url, api_key="or-key"))
        list(session.turn("hi"))
        ctx.check(f"the mock upstream received exactly one call, got {len(mock.requests)}",
                  len(mock.requests) == 1)
        headers = mock.requests[0]["headers"]
        ctx.check(f"the Databricks custom header never reached the openrouter wire request, got headers={headers}",
                  "x-test-dbx-org" not in headers)
        ctx.check(f"the default coding-agent-mode header never reached it either, got headers={headers}",
                  "x-databricks-use-coding-agent-mode" not in headers)
    finally:
        mock.stop()
        if old_custom is None:
            os.environ.pop("ANTHROPIC_CUSTOM_HEADERS", None)
        else:
            os.environ["ANTHROPIC_CUSTOM_HEADERS"] = old_custom


@test
def test_hf_bill_to_absent_after_switching_away_from_the_router(ctx: Ctx):
    """The mirror case, `X-HF-Bill-To` (round 4's Team/Enterprise billing
    header): present at session start on the hf: router, must never reach
    a request after switching to `or:`."""
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.theme import set_config_value
    from tests.helpers.mock_openai import MockUpstream

    mock = MockUpstream().start()
    try:
        set_config_value("huggingface.bill_to", "test-org")
        os.environ.setdefault("HF_TOKEN", "hf-test-default")
        build = _build("hf:some-org/some-model", None)
        session = build.session
        ctx.check(f"sanity: X-HF-Bill-To IS present at session start, got {session.extra_headers}",
                  session.extra_headers.get("X-HF-Bill-To") == "test-org")

        from halo_harness.providers.stream import ProviderCreds
        new_ref = parse_model_ref("or:mock/model")
        session.set_model(new_ref, ModelProfile(), creds=ProviderCreds(base_url=mock.base_url, api_key="or-key"))
        list(session.turn("hi"))
        ctx.check(f"the mock upstream received exactly one call, got {len(mock.requests)}",
                  len(mock.requests) == 1)
        headers = mock.requests[0]["headers"]
        ctx.check(f"X-HF-Bill-To never reached the openrouter wire request, got headers={headers}",
                  "x-hf-bill-to" not in headers)
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
