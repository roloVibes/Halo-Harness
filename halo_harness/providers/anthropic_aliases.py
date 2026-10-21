"""halo_harness.providers.anthropic_aliases -- the `ant:` route's
first-class Claude model aliases (ANTHROPIC_API_KEY, the real Anthropic
API): eleven short names (`fable`, `opus`, `opus-5.5`, ... `haiku`) resolved
to real API model ids, the vendored profile rows (context, output,
pricing, vision) for those ids, and the route a BARE alias word takes.

3.1.5.0 R1: the API-key half of the old `providers/cc_models.py`.
A full id, an already-prefixed ref, or anything not in the table passes
through unchanged, like every other alias in this harness.
"""

from __future__ import annotations

import os
from typing import Optional

# Seeded from live discovery (2026-09-28). `sonnet` and `haiku` are the
# two names whose target moves as Anthropic ships new point releases;
# `opus-5.5` / `sonnet-5.5` pin today's ids so they keep meaning 5.5 after
# the bare pointers move.
ANT_ALIASES: "dict[str, str]" = {
    "fable": "claude-fable-5-1",
    "opus": "claude-opus-5-5",
    "opus-5.5": "claude-opus-5-5",
    "opus-5": "claude-opus-5",
    "opus-5.0": "claude-opus-5",
    "opus-4.8": "claude-opus-4-8",
    "opus-4.6": "claude-opus-4-6",
    "sonnet": "claude-sonnet-5-5",
    "sonnet-5.5": "claude-sonnet-5-5",
    "sonnet-5": "claude-sonnet-5",
    "haiku": "claude-haiku-4-5-20251001",
}

BARE_ALIAS_NAMES = frozenset(ANT_ALIASES)

_1M_SUFFIX = "[1m]"

# 3.1.9.0 R1: what a table model takes in, for the catalog row's
# `modalities_in` -- the Messages API accepts image blocks and document
# (PDF) blocks on every model in ANT_MODEL_TABLE; no Claude model takes
# audio or video input.
ANT_INPUT_MODALITIES = ("text", "image", "pdf")

# Vendored fallback tier (model.py's "Aider-shaped data file" pattern),
# keyed by the API id `resolve_ant_alias` produces. context/output/pricing
# from the OpenRouter `anthropic/*` catalog rows (verified 2026-09-28).
# `adaptive_thinking` is informational metadata (shown by `halo models
# --ant`), never consulted by request building. Every current Claude model
# accepts image input, hence `vision=True` on every row.
ANT_MODEL_TABLE: "dict[str, dict]" = {
    "claude-fable-5-1": {
        "context_tokens": 1_000_000, "max_output_tokens": 128_000, "adaptive_thinking": True, "vision": True,
        "price_in": 0.00001, "price_out": 0.00005,
        "price_cache_read": 0.00000025, "price_cache_write": 0.0000125,
    },
    "claude-opus-5-5": {
        "context_tokens": 1_000_000, "max_output_tokens": 128_000, "adaptive_thinking": True, "vision": True,
        "price_in": 0.000004, "price_out": 0.00002,
        "price_cache_read": 0.0000002, "price_cache_write": 0.000005,
    },
    "claude-opus-5": {
        "context_tokens": 1_000_000, "max_output_tokens": 128_000, "adaptive_thinking": True, "vision": True,
        "price_in": 0.000005, "price_out": 0.000025,
        "price_cache_read": 0.0000005, "price_cache_write": 0.00000625,
    },
    "claude-opus-4-8": {
        "context_tokens": 1_000_000, "max_output_tokens": 128_000, "adaptive_thinking": True, "vision": True,
        "price_in": 0.000005, "price_out": 0.000025,
        "price_cache_read": 0.0000005, "price_cache_write": 0.00000625,
    },
    "claude-opus-4-6": {
        "context_tokens": 1_000_000, "max_output_tokens": 128_000, "adaptive_thinking": True, "vision": True,
        "price_in": 0.000005, "price_out": 0.000025,
        "price_cache_read": 0.0000005, "price_cache_write": 0.00000625,
    },
    "claude-sonnet-5": {
        "context_tokens": 1_000_000, "max_output_tokens": 128_000, "adaptive_thinking": True, "vision": True,
        "price_in": 0.000002, "price_out": 0.00001,
        "price_cache_read": 0.0000002, "price_cache_write": 0.0000025,
    },
    # No direct OpenRouter anthropic/claude-sonnet-5.5 row was cached as of
    # 2026-09-28 -- proxied from claude-sonnet-5's pricing (same tier).
    "claude-sonnet-5-5": {
        "context_tokens": 1_000_000, "max_output_tokens": 128_000, "adaptive_thinking": True, "vision": True,
        "price_in": 0.000002, "price_out": 0.00001,
        "price_cache_read": 0.0000002, "price_cache_write": 0.0000025,
    },
    "claude-haiku-4-5-20251001": {
        "context_tokens": 200_000, "max_output_tokens": 64_000, "adaptive_thinking": False, "vision": True,
        "price_in": 0.000001, "price_out": 0.000005,
        "price_cache_read": 0.0000001, "price_cache_write": 0.00000125,
    },
}


def _split_1m_suffix(bare: str) -> "tuple[str, str]":
    """`claude-sonnet-5[1m]` -> `("claude-sonnet-5", "[1m]")`: the `[1m]`
    suffix is stripped only long enough to look an alias up, then
    reattached verbatim."""
    if bare.endswith(_1M_SUFFIX):
        return bare[:-len(_1M_SUFFIX)], _1M_SUFFIX
    return bare, ""


def resolve_ant_alias(bare: str) -> str:
    """An alias word -> a real API model id for ANTHROPIC_API_KEY; anything
    not in the table (e.g. `ant:claude-opus-4`) passes through unchanged."""
    base, suffix = _split_1m_suffix(bare)
    return ANT_ALIASES.get(base, base) + suffix


# The two names kept as deliberately moving "latest" pointers -- every
# other alias is already a specific version.
_LATEST_POINTER_NOTE = {"opus": "latest Opus", "sonnet": "latest Sonnet"}


def alias_display_detail(alias: str) -> str:
    """`-> <resolved-id>` (plus "(latest Opus)" / "(latest Sonnet)" for
    those two names), shown next to every `ant:` alias row in `/model`,
    `halo models` and the init picker -- the same `detail` bracket a
    Databricks row's `<family> · <path>` tag uses. Without it a reader has
    to already know that `ant:opus` and `ant:opus-5.5` are the same model."""
    resolved = resolve_ant_alias(alias)
    note = _LATEST_POINTER_NOTE.get(alias)
    return f"-> {resolved}" + (f" ({note})" if note else "")


def default_bare_alias_route(*, api_key: Optional[str] = None) -> str:
    """A bare alias (`--model opus`, no prefix) resolves to `"ant"` when
    ANTHROPIC_API_KEY is set, else `"none"` (the caller raises, naming the
    `ant:` form and the key). Never spawns anything."""
    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    return "ant" if api_key else "none"


def profile_fields_for_ant_model(model_id: str) -> Optional[dict]:
    """Plain-dict profile fields (model.py builds the ModelProfile, to
    avoid an import cycle) for an `ant:` model id or alias word; None when
    `model_id` (after stripping an optional [1m] suffix) is not a known
    name or id."""
    base, _ = _split_1m_suffix(model_id)
    return ANT_MODEL_TABLE.get(ANT_ALIASES.get(base, base))
