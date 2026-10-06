"""tests.test_providers_huggingface_catalog -- Halo 2.0.3 round 4: the
router's `GET /v1/models` catalog (`probe_huggingface_models` parsing,
`write_hf_models_json`/`load_hf_models_json` round trip,
`refresh_huggingface_catalog_if_stale`'s TTL/force/not-configured
contract) and error translation (401/402/429/404, through the existing
`providers.stream`/`providers.errors` path every other provider already
goes through) -- against `tests/helpers/mock_openai.py`'s parameterized
`MockUpstream` (round 4's own `path_prefix`/`expected_bearer`/
`models_response` additions), never a second fake server.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.mock_openai import MockUpstream
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _req(mock: MockUpstream, scenario: str, *, api_key: str = "test-key"):
    from halo_harness.providers.routing import Route
    from halo_harness.providers.stream import CompletionRequest, ProviderCreds
    model = f"mock/{scenario}"
    return CompletionRequest(
        body={"model": model, "max_tokens": 100, "messages": [{"role": "user", "content": "hi"}]},
        route=Route(provider="huggingface", upstream_model=model, dialect="openai-chat"),
        profile={"context_tokens": 128000, "max_output_tokens": 16384},
        creds=ProviderCreds(base_url=mock.base_url, api_key=api_key),
        state_dir=Path(tempfile.mkdtemp(prefix="hf-catalog-stream-")),
        extra_headers={}, model_label=model,
    )


# ---- probe_huggingface_models -----------------------------------------------

@test
def test_probe_huggingface_models_parses_router_response(ctx: Ctx):
    from halo_harness.providers.huggingface_catalog import probe_huggingface_models
    mock = MockUpstream(path_prefix="/v1").start()
    mock.models_response = {"data": [
        {"id": "Qwen/Qwen3-32B", "context_length": 40960, "pricing": {"prompt": "0.0000002", "completion": "0.0000006"}},
        {"id": "no-numbers/model"},
        {"not-an-id": "skipped"},
    ]}
    try:
        rows = probe_huggingface_models(mock.base_url, "probe-token")
        by_id = {r["id"]: r for r in rows}
        ctx.check(f"two valid rows parsed (the id-less one skipped), got {sorted(by_id)}",
                  sorted(by_id) == ["Qwen/Qwen3-32B", "no-numbers/model"])
        ctx.check(f"context_length carried through, got {by_id['Qwen/Qwen3-32B'].get('context_length')}",
                  by_id["Qwen/Qwen3-32B"]["context_length"] == 40960)
        ctx.check("a row with neither field omits both rather than inventing None",
                  "context_length" not in by_id["no-numbers/model"] and "pricing" not in by_id["no-numbers/model"])
        gets = [r for r in mock.requests if r["method"] == "GET"]
        ctx.check(f"exactly one GET recorded, got {len(gets)}", len(gets) == 1)
        ctx.check(f"bearer carries the probe's own token, got {gets[0]['headers'].get('authorization')!r}",
                  gets[0]["headers"].get("authorization") == "Bearer probe-token")
    finally:
        mock.stop()


@test
def test_probe_huggingface_models_nested_provider_fallback(ctx: Ctx):
    """When the top level has neither field, a `providers` list's own
    row carrying either is used instead -- pricing is now normalized to
    a real float (Halo 2.0.4 round 3: `_normalize_provider_row`'s own
    `_to_float`, so sorting by cheapest provider works regardless of
    whether a real response sends a string or a JSON number), not kept
    as the raw string this pre-round-3 test pinned."""
    from halo_harness.providers.huggingface_catalog import probe_huggingface_models
    mock = MockUpstream(path_prefix="/v1").start()
    mock.models_response = {"data": [
        {"id": "nested/model", "providers": [{"context_length": 8192, "pricing": {"prompt": "0.000001", "completion": "0.000002"}}]},
    ]}
    try:
        rows = probe_huggingface_models(mock.base_url, "tok")
        ctx.check(f"context_length recovered from the nested providers list, got {rows[0]}",
                  rows[0].get("context_length") == 8192 and rows[0].get("pricing", {}).get("prompt") == 1e-06)
    finally:
        mock.stop()


# ---- Halo 2.0.4 round 3: the REAL per-provider shape (owner live report
# 2026-10-05, plans/2.0.3-release-notes-for-fix-pass.md's own "MUST FIX") --
# two providers at different prices, one of them down.
# ---------------------------------------------------------------------------

_TWO_PROVIDER_ENTRY = {
    "id": "org/two-provider-model", "object": "model", "owned_by": "org",
    "providers": [
        {"provider": "expensive-co", "status": "live", "context_length": 32768,
         "pricing": {"input": 0.000005, "output": 0.000015}, "is_free": False,
         "supports_tools": True, "first_token_latency_ms": 900, "throughput": 20},
        {"provider": "cheap-co", "status": "live", "context_length": 131072,
         "pricing": {"input": 0.0000002, "output": 0.0000008}, "is_free": False,
         "supports_tools": True, "first_token_latency_ms": 300, "throughput": 80},
        {"provider": "down-co", "status": "error", "context_length": 999999,
         "pricing": {"input": 0.00000001, "output": 0.00000001}},
    ],
}


@test
def test_two_provider_fixture_picks_the_cheapest_live_provider(ctx: Ctx):
    """The owner's live report: HF rows showed blank price/context
    because the parser read top-level fields the real response never
    has. The cheapest-overall provider ("down-co") is NOT live and must
    be ignored; "cheap-co" (cheaper of the two LIVE ones) supplies every
    column together."""
    from halo_harness.providers.huggingface_catalog import _parse_catalog_entry, hf_picker_fields
    parsed = _parse_catalog_entry(_TWO_PROVIDER_ENTRY)
    ctx.check(f"chose the cheaper LIVE provider, got {parsed.get('provider')!r}", parsed.get("provider") == "cheap-co")
    ctx.check(f"context from THAT provider, got {parsed.get('context_length')!r}", parsed.get("context_length") == 131072)
    fields = hf_picker_fields(parsed)
    # abs(...) < 1e-9: a *1e6 float conversion (0.0000002 -> 0.2) lands a
    # tiny binary-float epsilon off exact (0.19999999999999998) -- a real
    # bug would be off by far more than that.
    ctx.check(f"price_in_per_m from cheap-co, got {fields.get('price_in_per_m')!r}",
              abs(fields.get("price_in_per_m", -1) - 0.2) < 1e-9)
    ctx.check(f"price_out_per_m from cheap-co, got {fields.get('price_out_per_m')!r}",
              abs(fields.get("price_out_per_m", -1) - 0.8) < 1e-9)
    ctx.check(f"speed from cheap-co, got {fields.get('speed_ttft_s')!r}/{fields.get('speed_tokens_per_second')!r}",
              fields.get("speed_ttft_s") == 0.3 and fields.get("speed_tokens_per_second") == 80)


@test
def test_two_provider_fixture_reaches_the_picker_row_end_to_end(ctx: Ctx):
    """The SAME fixture, through probe -> write -> load -> Controller.
    list_models()'s own hf: branch -- the picker row must show real
    numbers, never "?", for a model with two differently-priced live
    providers."""
    from halo_harness.model_display import format_picker_row, unknown_as_qmark
    from halo_harness.providers.huggingface_catalog import (
        _parse_catalog_entry, hf_picker_fields, load_hf_models_json, write_hf_models_json,
    )
    state_dir = Path(tempfile.mkdtemp(prefix="hf-two-provider-"))
    write_hf_models_json(state_dir, [_parse_catalog_entry(_TWO_PROVIDER_ENTRY)])
    loaded = load_hf_models_json(state_dir)
    entry = loaded["org/two-provider-model"]
    fields = hf_picker_fields(entry)
    row = format_picker_row({"ref": "hf:org/two-provider-model", **fields})
    ctx.check(f"a real price shows, never '?', got {row!r}", "in=$0.20/M" in row and "out=$0.80/M" in row)
    ctx.check(f"a real context shows, got {row!r}", "ctx=131k" in row)
    ctx.check(f"a real speed shows, got {row!r}", "speed=?" not in row)


@test
def test_write_and_load_hf_models_json_round_trip(ctx: Ctx):
    from halo_harness.providers.huggingface_catalog import load_hf_models_json, write_hf_models_json
    state_dir = Path(tempfile.mkdtemp(prefix="hf-catalog-roundtrip-"))
    write_hf_models_json(state_dir, [{"id": "a/b", "context_length": 1234}, {"no_id_here": "skipped"}])
    loaded = load_hf_models_json(state_dir)
    ctx.check(f"keyed by id, got {sorted(loaded)}", sorted(loaded) == ["a/b"])
    ctx.check(f"context_length round-trips, got {loaded['a/b']}", loaded["a/b"]["context_length"] == 1234)
    ctx.check("a missing file loads as {}", load_hf_models_json(Path(tempfile.mkdtemp(prefix="hf-empty-"))) == {})


@test
def test_refresh_huggingface_catalog_if_stale_none_when_not_configured(ctx: Ctx):
    from halo_harness.providers.huggingface_catalog import refresh_huggingface_catalog_if_stale
    state_dir = Path(tempfile.mkdtemp(prefix="hf-refresh-noconfig-"))
    ctx.check("None (nothing configured) rather than False -- not a failure, just nothing to do",
              refresh_huggingface_catalog_if_stale(state_dir, env={}) is None)


@test
def test_refresh_huggingface_catalog_if_stale_fetches_then_respects_ttl_then_force(ctx: Ctx):
    from halo_harness.providers.huggingface_catalog import hf_models_json_age_seconds, load_hf_models_json, \
        refresh_huggingface_catalog_if_stale
    state_dir = Path(tempfile.mkdtemp(prefix="hf-refresh-ttl-"))
    env = {"HF_TOKEN": "tok"}
    mock = MockUpstream(path_prefix="/v1").start()
    mock.models_response = {"data": [{"id": "a/b", "context_length": 999}]}
    try:
        env["HALO_HF_ROUTER_BASE_URL"] = mock.base_url
        ok1 = refresh_huggingface_catalog_if_stale(state_dir, env=env, max_age_hours=24)
        ctx.check(f"first call (no cache yet) fetches, got {ok1!r}", ok1 is True)
        ctx.check("the catalog file now has the fetched model", "a/b" in load_hf_models_json(state_dir))
        age_after_first = hf_models_json_age_seconds(state_dir)

        mock.clear()
        ok2 = refresh_huggingface_catalog_if_stale(state_dir, env=env, max_age_hours=24)
        ctx.check(f"a fresh cache is not re-fetched, got {ok2!r}", ok2 is None)
        ctx.check("no GET sent for the skipped refresh", not any(r["method"] == "GET" for r in mock.requests))

        ok3 = refresh_huggingface_catalog_if_stale(state_dir, env=env, max_age_hours=24, force=True)
        ctx.check(f"force=True re-fetches regardless of freshness, got {ok3!r}", ok3 is True)
        # -1.0s tolerance: a full suite run under heavy parallel disk I/O can
        # see the filesystem's own mtime lag slightly behind time.time() by a
        # few hundred ms (observed in a 3000+-test run) -- this still catches
        # a real bug (None, a wildly wrong value) without being flaky on a
        # busy box.
        ctx.check(f"age_after_first is a real, roughly-zero-or-positive number, got {age_after_first!r}",
                  isinstance(age_after_first, float) and age_after_first >= -1.0)
    finally:
        mock.stop()


# ---- error translation: through the SAME path every other provider gets --

@test
def test_error_401_maps_to_authentication_error(ctx: Ctx):
    from halo_harness.providers.stream import UpstreamError, stream_completion
    mock = MockUpstream().start()
    try:
        try:
            next(stream_completion(_req(mock, "error-401")))
            ctx.check("expected UpstreamError", False)
        except UpstreamError as e:
            ctx.check(f"status 401, got {e.status}", e.status == 401)
            ctx.check(f"err_type authentication_error, got {e.err_type!r}", e.err_type == "authentication_error")
            ctx.check(f"not retryable, got {e.retryable!r}", e.retryable is False)
    finally:
        mock.stop()


@test
def test_error_402_maps_to_permission_error(ctx: Ctx):
    from halo_harness.providers.stream import UpstreamError, stream_completion
    mock = MockUpstream().start()
    try:
        try:
            next(stream_completion(_req(mock, "error-402")))
            ctx.check("expected UpstreamError", False)
        except UpstreamError as e:
            ctx.check(f"status 402, got {e.status}", e.status == 402)
            ctx.check(f"err_type permission_error, got {e.err_type!r}", e.err_type == "permission_error")
    finally:
        mock.stop()


@test
def test_error_429_maps_to_rate_limit_error_and_is_retryable(ctx: Ctx):
    from halo_harness.providers.stream import UpstreamError, stream_completion
    mock = MockUpstream().start()
    try:
        try:
            next(stream_completion(_req(mock, "error-429")))
            ctx.check("expected UpstreamError", False)
        except UpstreamError as e:
            ctx.check(f"status 429, got {e.status}", e.status == 429)
            ctx.check(f"err_type rate_limit_error, got {e.err_type!r}", e.err_type == "rate_limit_error")
            ctx.check(f"retryable, got {e.retryable!r}", e.retryable is True)
            ctx.check(f"Retry-After carried through, got {e.retry_after!r}", e.retry_after == "2")
    finally:
        mock.stop()


@test
def test_error_404_maps_to_not_found_error(ctx: Ctx):
    """The round 4 brief's own framing: "404 unknown model or provider
    suffix" -- the mock's generic error-<code> scenario stands in for
    either real cause (this layer only cares about the status code)."""
    from halo_harness.providers.stream import UpstreamError, stream_completion
    mock = MockUpstream().start()
    try:
        try:
            next(stream_completion(_req(mock, "error-404")))
            ctx.check("expected UpstreamError", False)
        except UpstreamError as e:
            ctx.check(f"status 404, got {e.status}", e.status == 404)
            ctx.check(f"err_type not_found_error, got {e.err_type!r}", e.err_type == "not_found_error")
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
