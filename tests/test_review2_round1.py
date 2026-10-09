"""tests.test_review2_round1 -- pins for the vibes/review.md findings fixed
in this round (drafted by the local Ollama model, corrected by the main
session -- the owner's token-thrift offload flow):

  * f24/f25  subagent.py `model_ref`/`is_error` NameErrors (crash class)
  * f79      doctor.py `resolve_settings` never imported (swallowed)
  * f32      call_small_model built an openai-chat body for ant:/dbx-Claude
  * f34      ant:/xp: branches dropped governor_ctx (no retry, no limiting)
  * f35      a Connection:close'd overload silently auto-reconnected on the
             8 s constructor timeout instead of open_upstream's 300 s
  * f36      dbx-Claude 404 fallback: candidate order now includes the
             documented literal pay-per-token route; empty model never
             produces a `//` path; the final 404 keeps its error body
  * f37      _dbx_post returns the Governor-peeked 500 body (3-tuple)
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

REPO = Path(__file__).resolve().parent.parent

from tests.helpers.mock_anthropic import MockAnthropic
from halo_harness.providers.http import (
    UpstreamResult, _dbx_post, _reopened_if_needed, call_anthropic_native,
)
from halo_harness.providers.profiles import ProviderProfile
from halo_harness.providers.request import build_anthropic_request_body
from halo_harness.providers.routing import Route
import halo_harness.providers.http as httpmod


def _profile():
    return ProviderProfile(family="claude", thinking_format="anthropic_thinking",
                           reasoning_effort_supported=True, max_tokens_default=8192)


def _route_dbx():
    return Route(provider="databricks", upstream_model="claude-sonnet-ok",
                 dialect="anthropic-passthrough")


def _body():
    return build_anthropic_request_body(
        system_text="SYS", messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        tools=None, route=_route_dbx(), profile=_profile())


# ---- findings 24/25/79: no undefined names left in the flagged modules ----


@test
def test_f24_f25_f79_no_undefined_names(ctx: Ctx):
    try:
        import pyflakes  # noqa: F401
    except ImportError:
        ctx.check("pyflakes not installed; skipping (roadmap adds it to CI)", True)
        return
    proc = subprocess.run(
        [sys.executable, "-m", "pyflakes",
         "halo_harness/agent/subagent.py", "halo_harness/doctor.py"],
        cwd=str(REPO), capture_output=True, text=True,
    )
    bad = [ln for ln in proc.stdout.splitlines() if "undefined name" in ln]
    ctx.check(f"pyflakes ran over both modules (rc={proc.returncode})", proc.returncode in (0, 1))
    ctx.check(f"no 'undefined name' diagnostics remain, got {len(bad)}", not bad)


# ---- finding 36: dbx Claude 404 fallback candidate order ----


@test
def test_f36_dbx_claude_candidate_order(ctx: Ctx):
    mock = MockAnthropic().start()
    try:
        # Gateway AND the literal pay-per-token route both 404: only the
        # by-name invocations candidate can succeed.
        mock.force_404_paths = {"/ai-gateway/anthropic/v1/messages",
                                "/serving-endpoints/anthropic/v1/messages"}
        result = call_anthropic_native(mock.base_url, "k", _body(), {},
                                       Path(tempfile.mkdtemp()), route_provider="databricks")
        ctx.check(f"final 200 from the by-name endpoint, got {result.status}", result.status == 200)
        ctx.check("last hit is the by-name invocations path",
                  mock.requests[-1]["path"].startswith("/serving-endpoints/claude-sonnet-ok/invocations"))
        ctx.check("the documented literal pay-per-token path was tried",
                  any(r["path"] == "/serving-endpoints/anthropic/v1/messages" for r in mock.requests))
        paths = [r["path"] for r in mock.requests]
        first_idx = lambda p: next(i for i, x in enumerate(paths) if x.startswith(p))  # noqa: E731
        ctx.check("gateway attempted before the literal pay-per-token route",
                  first_idx("/ai-gateway/anthropic/v1/messages")
                  < first_idx("/serving-endpoints/anthropic/v1/messages"))
    finally:
        mock.stop()


@test
def test_f36_literal_anthropic_path_succeeds_when_gateway_404s(ctx: Ctx):
    mock = MockAnthropic().start()
    try:
        # A workspace WITHOUT the AI gateway: the documented pay-per-token
        # route is now the one that answers (V2b had deleted it).
        mock.force_404_paths = {"/ai-gateway/anthropic/v1/messages"}
        result = call_anthropic_native(mock.base_url, "k", _body(), {},
                                       Path(tempfile.mkdtemp()), route_provider="databricks")
        ctx.check(f"200 via the pay-per-token route, got {result.status}", result.status == 200)
        ctx.check(f"winner is the literal route, got {mock.requests[-1]['path']}",
                  mock.requests[-1]["path"] == "/serving-endpoints/anthropic/v1/messages")
    finally:
        mock.stop()


@test
def test_f36_final_404_keeps_error_body(ctx: Ctx):
    mock = MockAnthropic().start()
    try:
        mock.force_404_paths = {"/ai-gateway/", "/serving-endpoints/"}
        result = call_anthropic_native(mock.base_url, "k", _body(), {},
                                       Path(tempfile.mkdtemp()), route_provider="databricks")
        ctx.check(f"every candidate 404'd, got {result.status}", result.status == 404)
        ctx.check("the drained 404 body survived into body_bytes", result.body_bytes is not None
                  and b"not found" in (result.body_bytes or b"").lower())
    finally:
        mock.stop()


@test
def test_f36_empty_model_never_double_slash(ctx: Ctx):
    mock = MockAnthropic().start()
    try:
        mock.force_404_paths = {"/ai-gateway/", "/serving-endpoints/anthropic/"}
        body = dict(_body())
        body.pop("model", None)  # degenerate no-model body
        call_anthropic_native(mock.base_url, "k", body, {},
                              Path(tempfile.mkdtemp()), route_provider="databricks")
        bad = [r["path"] for r in mock.requests if "//" in r["path"]]
        ctx.check(f"no request path contains '//', got {bad}", not bad)
    finally:
        mock.stop()


# ---- finding 34: governor_ctx plumbed through ant:/xp: ----


@test
def test_f34_ant_route_passes_governor_ctx(ctx: Ctx):
    captured = {}

    def fake(base_url, api_key, body, headers, state_dir, path="/v1/messages",
             query_suffix="", on_connect=None, governor_ctx=None):
        captured["governor_ctx"] = governor_ctx
        return UpstreamResult(status=200, headers={}, resp=None, conn=None)

    original = httpmod.proxy_anthropic
    httpmod.proxy_anthropic = fake
    try:
        call_anthropic_native("https://x", "k", {"model": "m"}, {}, Path(tempfile.mkdtemp()),
                              route_provider="anthropic", governor_ctx={"marker": "ctx-77"})
        ctx.check("anthropic route forwards governor_ctx",
                  captured.get("governor_ctx") == {"marker": "ctx-77"})
        captured.clear()
        call_anthropic_native("https://x", "k", {"model": "m"}, {}, Path(tempfile.mkdtemp()),
                              route_provider="experiential", governor_ctx={"marker": "ctx-99"})
        ctx.check("experiential route forwards governor_ctx",
                  captured.get("governor_ctx") == {"marker": "ctx-99"})
    finally:
        httpmod.proxy_anthropic = original


# ---- finding 35: _reopened_if_needed semantics ----


@test
def test_f35_reopened_if_needed(ctx: Ctx):
    class FakeConn:
        def __init__(self, sock):
            self.sock = sock

    live = FakeConn(object())
    ctx.check("a live connection is returned unchanged",
              _reopened_if_needed(live, "h", 1, False) is live)

    calls = {}
    sentinel = FakeConn(object())

    def fake_open(host, port, tls, on_connect=None):
        calls["args"] = (host, port, tls)
        calls["on_connect"] = on_connect
        return sentinel

    original = httpmod.open_upstream
    httpmod.open_upstream = fake_open
    try:
        dead = FakeConn(None)
        on_connect = lambda c: None  # noqa: E731
        out = _reopened_if_needed(dead, "hosta", 2, True, on_connect=on_connect)
        ctx.check("a Connection:close'd conn is rebuilt through open_upstream", out is sentinel)
        ctx.check("open_upstream got (host, port, tls)", calls.get("args") == ("hosta", 2, True))
        ctx.check("on_connect passed through (abort watcher re-registers)", calls.get("on_connect") is on_connect)
    finally:
        httpmod.open_upstream = original


# ---- finding 37: _dbx_post returns the peeked 500 body ----


@test
def test_f37_dbx_post_returns_peeked_body(ctx: Ctx):
    class FakeConn:
        def __init__(self, sock):
            self.sock = sock

    def fake_open(host, port, tls, on_connect=None):
        return FakeConn(object())

    def fake_governed(*args, **kwargs):
        return UpstreamResult(status=500, headers={}, resp=None, conn=None,
                              body_bytes=b'{"error":"peeked"}')

    original_open, original_gov = httpmod.open_upstream, httpmod.governed_upstream
    httpmod.open_upstream, httpmod.governed_upstream = fake_open, fake_governed
    try:
        _resp, _conn, peeked = _dbx_post("https://x", "/p", "k", {"a": 1}, {},
                                         Path(tempfile.mkdtemp()))
        ctx.check("the Governor-peeked 500 body survives _dbx_post's return",
                  peeked == b'{"error":"peeked"}')
    finally:
        httpmod.open_upstream, httpmod.governed_upstream = original_open, original_gov


# ---- finding 32: call_small_model on an ant: route ----


@test
def test_f32_call_small_model_on_ant_route(ctx: Ctx):
    mock = MockAnthropic().start()
    try:
        import halo_harness.headless as headless
        from halo_harness.providers.stream import ProviderCreds
        build = headless.build_session(cwd=REPO, model_ref_raw="ant:claude-sonnet-ok")
        s = build.session
        # Force the one-shot onto the MAIN ant: model (a configured
        # small_model_ref would re-resolve creds from settings and bypass
        # the override below) -- the exact repro shape of finding 32.
        s.small_model_ref = None
        s.creds = ProviderCreds(base_url=mock.base_url, api_key="k")
        text = s.call_small_model(system_text="SYS", user_text="hi")
        ctx.check(f"one-shot call answered 'pong', got {text!r}", text == "pong")
        ctx.check(f"path is /v1/messages, got {mock.requests[-1]['path'] if mock.requests else None}",
                  bool(mock.requests) and mock.requests[-1]["path"] == "/v1/messages")
        ctx.check("the posted body carries non-empty anthropic messages",
                  bool(mock.requests) and bool(mock.requests[-1]["body"].get("messages")))
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
