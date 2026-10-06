"""tests.test_experiential_catalog -- Halo 2.0.4 round 2: `GET /v1/models`
catalog caching/parsing for the Experiential Labs gateway
(halo_harness.providers.experiential_catalog), using the vendored snapshot
(halo_harness/providers/catalog/experiential-models.json) as the fixture
shape the brief asks for. No network.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _scratch_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="xp-catalog-"))


@test
def test_vendored_fallback_loads_and_carries_no_secret(ctx: Ctx):
    from halo_harness.providers.experiential_catalog import load_vendored_experiential_fallback
    data = load_vendored_experiential_fallback()
    ctx.check("non-empty vendored catalog", len(data) > 0)
    ctx.check("space-bunny-alpha is present", "space-bunny-alpha" in data)
    ctx.check("claude-haiku-4.5 is present (the Claude-slug catalog row)", "claude-haiku-4.5" in data)
    blob = json.dumps(data)
    ctx.check("no xpl_ key-shaped token anywhere in the vendored file", "xpl_" not in blob)


@test
def test_load_xp_models_json_falls_back_to_vendored_when_no_cache_file(ctx: Ctx):
    from halo_harness.providers.experiential_catalog import load_vendored_experiential_fallback, load_xp_models_json
    state_dir = _scratch_dir()
    data = load_xp_models_json(state_dir)
    ctx.check("fresh install still has real rows (vendored floor)", data == load_vendored_experiential_fallback())


@test
def test_write_and_load_round_trip(ctx: Ctx):
    from halo_harness.providers.experiential_catalog import load_xp_models_json, write_xp_models_json
    state_dir = _scratch_dir()
    fetched = {"space-bunny-alpha": {"context_window_tokens": 999, "owned_by": "exp"}}
    write_xp_models_json(state_dir, fetched)
    loaded = load_xp_models_json(state_dir)
    ctx.check(f"writes then reads back exactly, got {loaded!r}", loaded == fetched)


@test
def test_nano_pricing_to_per_m_divides_by_1e9_and_preserves_null_vs_zero(ctx: Ctx):
    from halo_harness.providers.experiential_catalog import nano_pricing_to_per_m
    out = nano_pricing_to_per_m({
        "input_nano_usd_per_million_tokens": 60_000_000,
        "output_nano_usd_per_million_tokens": 0,
        "cached_input_nano_usd_per_million_tokens": None,
    })
    ctx.check(f"60_000_000 nano -> $0.06/M, got {out.get('price_in_per_m')!r}", out.get("price_in_per_m") == 0.06)
    ctx.check(f"0 stays a real 0.0 (never dropped), got {out.get('price_out_per_m')!r}",
              out.get("price_out_per_m") == 0.0)
    ctx.check("a null/missing field is OMITTED, not coerced to 0",
              "price_cache_read_per_m" not in out)


@test
def test_data_policy_badge_zdr_wins_over_no_training(ctx: Ctx):
    from halo_harness.providers.experiential_catalog import data_policy_badge
    ctx.check("zdr wins", data_policy_badge({"no_training": True, "zdr": True}) == "zdr")
    ctx.check("no_training alone", data_policy_badge({"no_training": True, "zdr": False}) == "no_training")
    ctx.check("neither set -> no badge", data_policy_badge({"no_training": False, "zdr": False}) is None)
    ctx.check("malformed input never raises", data_policy_badge(None) is None)


@test
def test_xp_picker_fields_reads_every_documented_field(ctx: Ctx):
    from halo_harness.providers.experiential_catalog import write_xp_models_json, xp_picker_fields
    state_dir = _scratch_dir()
    write_xp_models_json(state_dir, {
        "space-bunny-alpha": {
            "context_window_tokens": 1_000_000, "maximum_output_tokens": 524_288,
            "supports_tools": True, "supports_reasoning": True, "supports_structured_output": True,
            "supported_reasoning_efforts": ["low", "medium", "high", "xhigh", "max"],
            "reasoning_effort": "max", "reasoning_output_hidden": True,
            "owned_by": "exp", "data_policy": {"no_training": True, "zdr": False},
            "pricing": {"input_nano_usd_per_million_tokens": 0, "output_nano_usd_per_million_tokens": 0},
            "retention": "preview",
        },
    })
    fields = xp_picker_fields("space-bunny-alpha", state_dir)
    ctx.check(f"context, got {fields!r}", fields.get("context_tokens") == 1_000_000)
    ctx.check(f"is_free_preview flagged, got {fields.get('is_free_preview')!r}",
              fields.get("is_free_preview") is True)
    ctx.check("max output", fields.get("max_output_tokens") == 524_288)
    ctx.check("supports_tools", fields.get("supports_tools") is True)
    ctx.check("supported_reasoning_efforts", fields.get("supported_reasoning_efforts") == ["low", "medium", "high", "xhigh", "max"])
    ctx.check("reasoning_effort_default", fields.get("reasoning_effort_default") == "max")
    ctx.check("reasoning_output_hidden", fields.get("reasoning_output_hidden") is True)
    ctx.check("owned_by", fields.get("owned_by") == "exp")
    ctx.check("data_policy_badge", fields.get("data_policy_badge") == "no_training")
    ctx.check("$0 preview price is a real 0.0, not blank", fields.get("price_in_per_m") == 0.0)


@test
def test_is_free_preview_requires_both_zero_price_and_preview_retention(ctx: Ctx):
    from halo_harness.providers.experiential_catalog import write_xp_models_json, xp_picker_fields
    state_dir = _scratch_dir()
    write_xp_models_json(state_dir, {
        # $0 but no "preview" retention -- a plainly, permanently free model.
        "plain-free": {"pricing": {"input_nano_usd_per_million_tokens": 0}, "retention": "stable"},
        # "preview" retention but a real price -- not free at all.
        "priced-preview": {"pricing": {"input_nano_usd_per_million_tokens": 60_000_000}, "retention": "preview"},
    })
    ctx.check("plain free (no preview tag) is not flagged",
              xp_picker_fields("plain-free", state_dir).get("is_free_preview") is False)
    ctx.check("preview tag alone (real price) is not flagged",
              xp_picker_fields("priced-preview", state_dir).get("is_free_preview") is False)


@test
def test_xp_picker_fields_unknown_model_returns_empty(ctx: Ctx):
    from halo_harness.providers.experiential_catalog import xp_picker_fields
    ctx.check("unknown model id -> {} (never raises)", xp_picker_fields("nope-not-real", _scratch_dir()) == {})


@test
def test_probe_experiential_models_parses_real_shape(ctx: Ctx):
    """Mirrors `probe_huggingface_models`/`probe_openai_models`'s own test
    convention: a real HTTP round trip against `tests.helpers.mock_openai`,
    `GET <path_prefix>/models` serving the vendored snapshot's own shape
    (`mock.models_response`)."""
    from halo_harness.providers.experiential_catalog import load_vendored_experiential_fallback, probe_experiential_models
    from tests.helpers.mock_openai import MockUpstream
    vendored = load_vendored_experiential_fallback()
    mock = MockUpstream(path_prefix="/v1", expected_bearer="xpl_test").start()
    try:
        mock.models_response = {"data": [{"slug": k, **v} for k, v in vendored.items()]}
        fetched = probe_experiential_models(mock.base_url, "xpl_test")
        ctx.check(f"every vendored slug round-trips, got {sorted(fetched)!r}", set(fetched) == set(vendored))
        ctx.check("context_window_tokens survives the round trip",
                  fetched["space-bunny-alpha"]["context_window_tokens"] == 1_000_000)
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
