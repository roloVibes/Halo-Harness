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

# Halo 2.0.4 round 5 (xp: contract alignment, pinned against the gateway's
# OWN machine-readable https://platform.experientiallabs.ai/llms.txt,
# fetched 2026-10-06 -- its "Error envelope" section's stable code table is
# literal and authoritative here, superseding round 3's own docstring,
# which it contradicted on three codes): the retryable set is EXACTLY
# `unavailable_route`/`gateway_overloaded`/`all_routes_failed`/
# `backend_unavailable`/`gateway_draining`/`deadline_exceeded`/
# `internal_error` -- every other code is False, INCLUDING `idempotency_
# replay_unavailable` (the contract's own fix is "resend with a NEW
# Idempotency-Key," never a blind identical retry -- Halo's own retry
# ladder reuses the SAME key for every attempt of one turn, so an
# automatic retry would just hit this exact error again) and
# `request_cancelled` (the client itself disconnected; nothing upstream to
# retry against). `provider_internal` (round 2/3 had a row for it, True
# then False) is REMOVED here -- it does not appear anywhere in the
# published contract (superseded by `internal_error`); an unrecognized
# code still falls through to the generic status-based table in
# `providers.errors`, which is the correct answer for whatever HTTP status
# it actually carries.
#
# Three retryable flips from round 3's own table, each the contract's own
# per-row recovery text, not a guess: `gateway_draining` 503 ("retry (hits
# another)"), `deadline_exceeded` 504 ("shorten or retry"), and
# `internal_error` 500 ("-> retry with backoff") are all explicitly
# RETRYABLE per the contract -- round 3's docstring claimed the generic
# status-based fallback "still retries... when nothing more specific is
# known," but that is not how `map_upstream_error` actually behaves: a
# code that matches a row in THIS table (any row, any boolean) always
# WINS over the generic per-status default (`retry_override is not None`
# unconditionally overrides `should_retry`) -- so a False row here for one
# of these three codes was actively SUPPRESSING a retry the contract says
# should happen, not merely declining to add one on top of an
# already-retrying default.
ERROR_TABLE = {
    "model_location_not_supported": ("This model can't be served to your account's region; pick a different one.", False),
    "invalid_json": ("The request body wasn't valid JSON (a Halo bug, not a user error).", False),
    "invalid_request": ("The gateway rejected this request; see its message for which field.", False),
    "invalid_parameter": ("One field in the request was invalid (the error's own `param` names which); fix it.", False),
    "unsupported_capability": ("This model can't do what was asked (e.g. structured output, a modality, a tool); "
                                "pick a model whose catalog row says it can.", False),
    # Contract wording (llms.txt "Error envelope"): "a specific field the
    # route rejects ... ('param' names it) -> remove the field or pick a
    # model that lists it" -- a 400 REFUSAL of the whole request, same as
    # every other row in this table, never a silent, still-served drop
    # (that's `x-experiential-ignored-parameters`' own job, a disclosure on
    # an otherwise-successful response, not this error code).
    "unsupported_parameter": ("This gateway doesn't accept one of the fields sent (the error names which); "
                               "remove it, or pick a model whose catalog row lists it.", False),
    "refusal": ("The provider declined this request on policy grounds; retrying the identical request won't "
                "help -- rephrase it or pick a different model.", False),
    "previous_response_not_found": ("That conversation handle expired; resend the full conversation instead of continuing it.", False),
    "zdr_continuation_disabled": ("That conversation was routed with zero data retention, so the gateway kept no state for it; "
                                   "resend the full conversation instead of continuing it.", False),
    "invalid_key": ("The Experiential Labs key is missing, wrong, expired or revoked; check it in `/providers`.", False),
    # Contract wording: slugs are the DOT form (claude-fable-5.1); an
    # Anthropic-style dashed wire id (claude-fable-5-1) gets this same 403
    # -- the single most common way to actually hit this code.
    "model_not_granted": ("This account can't use that model slug (or it's misspelled -- slugs use dots, e.g. "
                          "claude-sonnet-5.5, never dashed Anthropic wire ids); use the exact slug from the catalog.", False),
    "idempotency_conflict": ("That idempotency key was already used for a different request; Halo mints a fresh one per turn.", False),
    "idempotency_replay_unavailable": ("The gateway lost the earlier result it would have replayed; resend as a new request "
                                        "(never retried automatically with the same key, which would just repeat this).", False),
    "insufficient_quota": ("Out of credit, a daily cap, or a free-tier allowance (the upstream message names which); "
                           "add credits, raise the cap, or wait for the allowance to reset.", False),
    "org_under_review": ("The account is paused for review; contact Experiential Labs support.", False),
    "unavailable_route": ("No working route for this model right now; retrying with backoff.", True),
    "gateway_overloaded": ("The gateway itself is overloaded; retrying with backoff.", True),
    "request_cancelled": ("The client disconnected before this request finished; resend if the result is still needed.", False),
    "all_routes_failed": ("Every route for this model failed; retrying, and if this is a BYOK model, check that key.", True),
    "backend_unavailable": ("The gateway's own serving backend could not be reached (a deploy or an outage); retrying with backoff.", True),
    "provider_output_too_large": ("The model's answer was too large for the provider to return; lower the output-length limit.", False),
    "gateway_draining": ("This gateway instance is shutting down; retrying so a different instance picks it up.", True),
    "deadline_exceeded": ("The request ran past its deadline; retrying (shorten the task if this keeps happening).", True),
    "internal_error": ("The gateway had an internal error; retrying with backoff.", True),
    "pro_required": ("This needs the Experiential Labs Pro plan -- see platform.experientiallabs.ai/credits.", False),
    # Halo 2.0.4 round 3 (deliverable 4, added after the round 2 live
    # checks): a 429 for a preview/paid model this account hasn't bought
    # yet. `None` here (not a sentence string, unlike every other row)
    # means "recognize the code and treat it as non-retryable, but leave
    # `msg` as the raw upstream text" -- `plain_sentence`'s own `row[0] if
    # row else None` then returns `None` too, so `map_upstream_error`'s
    # caller never overwrites it. That is deliberate: the gateway's own
    # wording already names the model and reads as one plain line ("<model>
    # is locked on your account until you make a purchase" -- confirmed
    # live), so there is nothing to translate; purchasing it mid-retry-loop
    # isn't going to happen, so the one thing this row MUST do is stop the
    # generic 429 row's `should_retry=True` default from retrying it.
    "model_requires_purchase": (None, False),
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


# ---- zero data retention (llms.txt "Zero data retention") ----------------

def zdr_provider_constraint(config: Optional[bool] = None) -> "Optional[dict]":
    """Halo 2.0.4 round 5: `{"zdr": True}` -- the INNER value of the
    request body's top-level `"provider"` key (the contract's own
    OpenRouter-compatible shape: `POST /v1/chat/completions`, `/v1/
    responses` or `/v1/messages` with `"provider": {"zdr": true}`) that
    demands zero-data-retention routing for exactly this one request, read
    from the `experiential.zdr` config key (default False) -- the "ZDR
    toggle" (this one key drives both the toggle and the per-request
    constraint it sends; there is no separate account-wide switch here,
    since flipping that needs a Pro-gated Management API call this
    harness never makes on its own -- see `docs/CONFIG.md`). `None` (add
    nothing to the body) when the key is off/unset, so a session that
    never asked for ZDR sends an identical body to before this key
    existed. `config`, when given (a test seam), is the resolved boolean
    directly, skipping the config-file read."""
    if config is None:
        from halo_harness.theme import get_config_value
        config = bool(get_config_value("experiential.zdr", default=False))
    return {"zdr": True} if config else None
