"""halo_harness.providers.experiential -- Halo 2.0.4 round 2: the `xp:`
route onto the Experiential Labs gateway (`docs/harness/EXPERIENTIAL-
RESEARCH.md`, `plans/2.0.3-ollama-round2-brief.md` "Round 5h"). The
gateway is OpenAI-compatible for chat completions (reuses `providers.
request`/`providers.stream`/`providers.oai_stream` as-is), shares the
Responses dialect 5i part 1 built (`providers.responses_request`/
`responses_stream`), and uses Halo's existing Anthropic passthrough
(`providers.request.build_anthropic_request_body`, `providers.stream.
stream_anthropic_completion`) for Claude slugs -- this module carries
only what's genuinely NEW to this gateway: which slugs go native-Claude
(section 1/3.3), the dialect-override table (section 3.2), the gateway's
own error-code table (section 7), the `gateway.routing`/`gateway.retry`
object (section 3.4), and the tool-search wire convention (section 3.5).
"""

from __future__ import annotations

import re
from typing import Optional

# ---- which slugs go through the Anthropic passthrough dialect ------------

_CLAUDE_SLUG_RE = re.compile(r"^claude-", re.IGNORECASE)


def is_claude_slug(model_id: str) -> bool:
    """True for a catalog slug naming a Claude model (`claude-opus-5`,
    `claude-haiku-4.5`, every example the docs/catalog give) -- section
    1/3.3: these route through Halo's existing Anthropic passthrough at
    `/v1/messages` with `x-api-key` so thinking stays native WHILE an
    Anthropic-shaped rung actually serves the call (a waterfall fallback
    onto a non-Anthropic rung can still translate/drop it -- see this
    module's own `thinking_disclosure` below). Anchored to the slug's
    START, never a bare substring match."""
    return bool(_CLAUDE_SLUG_RE.match(model_id or ""))


# ---- dialect selection for the non-Claude slugs (chat vs Responses) ------

_DIALECT_ALIASES = {"chat": "openai-chat", "openai-chat": "openai-chat",
                     "responses": "openai-responses", "openai-responses": "openai-responses"}


def resolve_experiential_dialect(model_id: str, *, overrides: "Optional[dict]" = None) -> str:
    """"openai-chat" (the default) or "openai-responses" for a NON-Claude
    `xp:<slug>` -- Claude slugs never reach this (model.py's
    `parse_model_ref` routes them to "anthropic-passthrough" directly,
    before dialect selection is a question). `overrides` (test seam;
    `None` reads `experiential.dialect_overrides` from `~/.halo/
    config.json`) always wins, either direction -- the SAME shape
    `providers.responses_request.resolve_openai_dialect` uses for `oai:`,
    a separate config key/function since no live-confirmed Experiential
    model needs the Responses dialect by default yet (research doc
    section 3.2: unconfirmed whether its own refused/dropped parameter
    list even matches Chat Completions') -- unlike `oai:`, there is no
    static required-id table here, only the override."""
    if overrides is None:
        from halo_harness.theme import get_config_value
        overrides = get_config_value("experiential.dialect_overrides", default=None)
    if isinstance(overrides, dict) and model_id in overrides:
        raw = overrides.get(model_id)
        mapped = _DIALECT_ALIASES.get(str(raw).strip().lower()) if raw is not None else None
        if mapped is not None:
            return mapped
    return "openai-chat"


# ---- error translation: the gateway's own `error.code` (research doc
# section 7) -> (plain sentence, retryable). `map_upstream_error`
# (providers.errors) consults this FIRST for an "experiential" route,
# falling back to its own generic status-code table for a code this
# table doesn't name. ----------------------------------------------------

ERROR_TABLE = {
    "model_location_not_supported": ("This model can't be served to your account's region; pick a different one.", False),
    "invalid_json": ("The request body wasn't valid JSON (a Halo bug, not a user error).", False),
    "invalid_request": ("The gateway rejected this request; see its message for which field.", False),
    "invalid_parameter": ("One field in the request was invalid (max 65,536 chars on text fields).", False),
    "unsupported_capability": ("This model can't do what was asked (e.g. structured output); pick a model whose catalog row says it can.", False),
    "unsupported_parameter": ("This gateway doesn't accept that field; it was removed from the request.", False),
    "refusal": ("The model or provider declined this request; try a different model or rephrase.", False),
    "previous_response_not_found": ("That conversation handle expired; resend the full conversation instead of continuing it.", False),
    "invalid_key": ("The Experiential Labs key is missing or wrong; check it in `/providers`.", False),
    "model_not_granted": ("This account can't use that model slug; use the exact slug from the catalog.", False),
    "idempotency_conflict": ("That idempotency key was already used for a different request; Halo mints a fresh one per turn.", False),
    "idempotency_replay_unavailable": ("The gateway couldn't replay the earlier result; resend with a new idempotency key.", True),
    "insufficient_quota": ("Out of credit (or past a free daily allowance); add credits or wait for the allowance to reset.", False),
    "org_under_review": ("The account is paused for review; contact Experiential Labs support.", False),
    "unavailable_route": ("No working route for this model right now; retrying once after a short backoff.", True),
    "gateway_overloaded": ("The gateway itself is overloaded; back off and retry.", True),
    "request_cancelled": ("The request was cancelled mid-flight; resend if the result is still needed.", True),
    "provider_internal": ("The upstream provider had an internal error; retry with backoff.", True),
    "all_routes_failed": ("Every rung for this model failed; retry, and if this is a BYOK model, check that key.", True),
    "provider_output_too_large": ("The model's answer was too large for the provider to return; lower the output-length limit.", False),
    "gateway_draining": ("This gateway instance is shutting down; retry (a different instance will pick it up).", True),
    "deadline_exceeded": ("The request took too long; shorten the task or retry.", True),
    "internal_error": ("The gateway had an internal error; retry with backoff.", True),
    "pro_required": ("This needs the Experiential Labs Pro plan -- see platform.experientiallabs.ai/credits.", False),
}


def error_code(body) -> Optional[str]:
    """The gateway's own `error.code` (distinct from HTTP status and from
    an OpenAI-style `error.type`) -- `None` for a malformed body or one
    with no `code` field at all."""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            code = err.get("code")
            if isinstance(code, str) and code:
                return code
    return None


def plain_sentence(body) -> Optional[str]:
    """The one-line Halo wording for this error body's gateway `code`
    (`ERROR_TABLE`) -- `None` when `code` is unset or not one of this
    table's rows, so the caller's own generic upstream-message path still
    applies unchanged."""
    row = ERROR_TABLE.get(error_code(body) or "")
    return row[0] if row else None


def is_retryable_code(body) -> Optional[bool]:
    """`True`/`False` when this body's gateway `code` is in `ERROR_TABLE`
    (needed because the gateway's `idempotency_conflict` (never retry) and
    `idempotency_replay_unavailable` (retry) share the SAME HTTP 409,
    which a status-only retry table can't tell apart) -- `None` otherwise,
    so the caller's generic status-based retry flag still applies."""
    row = ERROR_TABLE.get(error_code(body) or "")
    return row[1] if row else None


def is_empty_completion_warning(status: int, headers: Optional[dict]) -> bool:
    """`empty_completion` (research doc section 7) is the one "error" that
    is actually an HTTP 200 with a warning header, not a failure status --
    `True` when `headers` (already lower-cased, as `providers.http`'s
    `UpstreamResult.headers` always is) carries `x-gateway-warning` on an
    otherwise-successful response."""
    return status == 200 and bool((headers or {}).get("x-gateway-warning"))


# ---- gateway.routing / gateway.retry (research doc section 3.4) ----------

def build_gateway_object(*, config: Optional[dict] = None) -> dict:
    """`{"routing": {...}, "retry": {...}}` for the request body's
    `gateway` key. `retry.max_attempts_per_route` is ALWAYS 1 by default
    (sent on every `xp:` request, configured or not) -- Halo's own outer
    retry loop (`agent/loop.py`'s `_step`) is the outer layer already, so
    the gateway's own per-rung retries must never also retry underneath
    it ("SDK-style double retries avoided", the brief's own wording);
    `experiential.retry.max_attempts_per_route`/`max_total_attempts`/
    `backoff` override it explicitly. `routing` is omitted entirely
    unless `experiential.routing.allow_fallbacks`/`route_id` is actually
    configured -- there is no sensible default routing preference, and
    the docs describe leaving it out as a real operator choice, not a gap."""
    if config is None:
        from halo_harness.theme import get_config_value
        config = get_config_value("experiential", default=None) or {}
    config = config if isinstance(config, dict) else {}
    routing_cfg = config.get("routing")
    retry_cfg = config.get("retry")
    out: dict = {}
    if isinstance(routing_cfg, dict):
        routing: dict = {}
        if "allow_fallbacks" in routing_cfg:
            routing["allow_fallbacks"] = bool(routing_cfg["allow_fallbacks"])
        route_id = routing_cfg.get("route_id")
        if isinstance(route_id, str) and route_id:
            routing["route_id"] = route_id
        if routing:
            out["routing"] = routing
    retry: dict = {"max_attempts_per_route": 1}
    if isinstance(retry_cfg, dict):
        for key in ("max_attempts_per_route", "max_total_attempts"):
            if isinstance(retry_cfg.get(key), int):
                retry[key] = retry_cfg[key]
        backoff = retry_cfg.get("backoff")
        if isinstance(backoff, dict):
            retry["backoff"] = backoff
    out["retry"] = retry
    return out


# ---- tool search (research doc section 3.5) -------------------------------

def apply_tool_search(oai_tools: "Optional[list]", anthropic_tools: "Optional[list]") -> "Optional[list]":
    """Converts Halo's own ToolSearch deferred-tool decision (each
    Anthropic tool def's `defer_loading` flag, already computed upstream
    of request building -- the SAME flag `providers.routing.select_tools`
    reads for the Anthropic-native tool-search beta) into this gateway's
    OWN wire convention: a `{"type": "openrouter:tool_search"}` sentinel
    tool plus `defer_loading: true` on each OpenAI-shaped tool item that
    matches a deferred name. Returns `oai_tools` UNCHANGED (no sentinel
    added) when nothing is actually deferred -- "the whole tool_search
    declaration is pointless and gets dropped" is the gateway's own rule
    (same page); Halo mirrors that instead of sending a sentinel the
    gateway would just disclose right back as ignored."""
    deferred_names = {t.get("name") for t in (anthropic_tools or [])
                       if isinstance(t, dict) and t.get("defer_loading")}
    if not deferred_names or not oai_tools:
        return oai_tools
    out = []
    any_deferred = False
    for t in oai_tools:
        fn = (t.get("function") or {}) if isinstance(t, dict) else {}
        if fn.get("name") in deferred_names:
            t = dict(t)
            t["defer_loading"] = True
            any_deferred = True
        out.append(t)
    if not any_deferred:
        return oai_tools
    return [{"type": "openrouter:tool_search"}] + out


def tool_search_enabled(config: Optional[dict] = None) -> bool:
    """`experiential.tool_search`, default False -- "off by default ...
    until the live check confirms the shape" (the brief's own words)."""
    if config is not None:
        return bool(config)
    from halo_harness.theme import get_config_value
    return bool(get_config_value("experiential.tool_search", default=False))
