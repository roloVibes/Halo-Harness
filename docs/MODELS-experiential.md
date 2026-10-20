# Models: Experiential Labs

Read this when you route models through the Experiential Labs gateway (`xp:`).

Part of [Models](MODELS.md), which lists every part.

## Experiential Labs

`xp:<slug>` against the Experiential Labs gateway (platform.
experientiallabs.ai) -- an OpenAI-compatible gateway in front of hosted
providers, your own provider keys (BYOK), platform-funded credits, and
self-hosted/custom models. Full research: `docs/harness/EXPERIENTIAL-
RESEARCH.md`.

**Key and base URLs.** `EXPLABS_API_KEY` (the INFERENCE key, prefix
`xpl_`) -- never the separate, higher-privilege `EXPLABS_PROVISIONING_
KEY`, which the full Spend API and key-management endpoints need and
which Halo never asks for or assumes (an inference key gets a 403 on
those). Two base-URL families, each independently overridden for tests:
`BRIDGE_EXPERIENTIAL_BASE_URL` (default `https://api.experientiallabs.ai/
v1`, bare inference: chat/responses/messages) and `BRIDGE_EXPERIENTIAL_
ACCOUNT_BASE_URL` (default `https://api.experientiallabs.ai/api/v1`,
account: credits/usage/catalog management).

**Three dialects, one gateway.** A Claude slug (`xp:claude-*`) goes
through Halo's existing native Anthropic passthrough at `/v1/messages`
with `x-api-key`, so thinking stays native WHILE an Anthropic-shaped rung
actually serves the call -- the waterfall can still fail over to a
non-Anthropic rung, which translates `thinking` to that rung's own
`reasoning_effort` tier or drops it, disclosed by the gateway; every other
slug uses chat completions (`/v1/chat/completions`) by default, or the
Responses dialect (`/v1/responses`, shared with the `oai:` route's own
work) when `experiential.dialect_overrides` (`{"<slug>": "chat"|
"responses"}`, same shape as `openai.dialect_overrides`) says so -- there
is no static required-dialect table for this gateway, since no
live-confirmed model needs Responses by default yet.

**Its own profile.** None of OpenRouter's own fields (`usage.include`, a
`provider` preference object, `transforms`) are ever sent -- Experiential's
schema simply doesn't define them, and sending any of them 400s. `tools`/
`reasoning_effort`/structured output (`response_format`) are each gated on
that exact model's own catalog row (`supports_tools`/`supports_reasoning`/
`supports_structured_output`) -- the gateway's structured-output capability
check never silently degrades to prose; it refuses the whole request with
`unsupported_capability` instead, so Halo checks the catalog BEFORE even
trying.

**Catalog.** `GET /v1/models`, cached in `experiential-models.json` with
the same TTL knob every other catalog here uses (`databricks.catalog_max_
age_hours`), refreshed by `/models refresh`, `halo models --refresh`, and
the same launch/first-open auto-refresh every other provider group gets.
A vendored fallback (`halo_harness/providers/catalog/experiential-models.
json`, built from already-published facts, no key, no secret) means a
fresh install still shows real context/price/capability columns before
ever refreshing live. Per-model fields: `context_window_tokens`,
`maximum_output_tokens`, `pricing.*_nano_usd_per_million_tokens` (divided
by 1e9 for the picker's USD/M columns -- `0` renders "free", an unpublished
price stays blank), `supports_tools`/`supports_reasoning`/`supports_
structured_output`, `supported_reasoning_efforts` + a default `reasoning_
effort`, `reasoning_output_hidden`, `data_policy` (`no_training`/`zdr`,
shown as a one-word picker badge, `zdr` winning when both are set),
`owned_by`.

**Cost and credits.** Per-turn cost reads `usage.cost` (the live-confirmed
location; a future top-level `cost` the docs describe is read as a bonus,
never required). `provider` (which rung actually served the turn) rides a
top-level per-chunk field, same shape OpenRouter's own `provider` field
does -- the transcript's responding-provider label shows the real serving
rung (e.g. `experiential_cloud`) instead of the bare `xp:` route name.
**Two billing lanes** (llms.txt "Two lanes"): `pass_through` (BYOK -- your
own provider key, billed by the provider directly, `usage.cost` settles at
`0`) and `platform_funded` (the platform's own credits, at catalog list
price, no markup); `usage.is_byok` (read from the final usage object, Halo
2.0.4 round 5 -- an EARLIER round's top-level-chunk read is kept too,
defensively) is which lane served this call, carried on the session's own
transcript log (the `usage` node's `experiential_meta.is_byok`) and shown
as `lane: pass_through (BYOK)`/`platform_funded` in `/xp routes <slug>`'s
"last response" section -- a bare `$0.0000` in the cost line does NOT by
itself mean "this model is free": it can mean "your own key paid for it,
outside Halo's tracked credit spend" instead. `GET /api/v1/credits` feeds
the balance line in `halo doctor`/`halo providers` (a bounded, best-effort
live read -- never from `/providers`' own table-formatting function, which
stays network-free); `halo stats --experiential` pages the settled rows
from `GET /api/v1/usage` (there is no standalone `halo cost` command, only
`halo stats` and the in-session `/cost`); `halo stats --experiential --id
<x-request-id>` (Halo 2.0.4 round 5) instead looks up ONE call by its own
request id through `GET /api/v1/generation`, for after-the-fact
attribution -- paste in the id `/xp routes` or the raw session log just
showed. Every `xp:` chat-completions request carries `safety_identifier`
set to the Halo session id (documented, opt-out -- "customer tracking
across billing exports"), so per-session spend is visible in the owner's
own Experiential Labs dashboard.

**Zero data retention (Halo 2.0.4 round 5).** `experiential.zdr`
(`~/.halo/config.json`, default `False`) adds a top-level `"provider":
{"zdr": true}` to the request body (the contract's own OpenRouter-
compatible shape) on every `xp:` call that goes through either request
builder (the OpenAI-shaped chat/Responses dialect and the Anthropic-
shaped `/v1/messages` dialect for a Claude slug alike) -- never on a bare
`ant:`/Databricks-Claude-passthrough body, which has no business
carrying this field at all. Off by default, so an existing session's
request body is byte-identical to before this key existed. The gateway
answers `x-gateway-zdr: true` on a response actually served under the
constraint, or refuses with 403 `model_not_granted` (naming `provider.zdr`
and the excluded providers) when no rung in this model's waterfall
qualifies; there is no separate account-wide toggle this harness flips on
its own (that needs a Pro-gated Management API call, out of scope here).

**Waterfall and the `gateway` object.** `gateway.retry.max_attempts_per_
route` is always sent as `1` by default (Halo's own outer retry loop is
already the outer layer, so the gateway never double-retries underneath
it) -- override via `experiential.retry.max_attempts_per_route`/`max_
total_attempts`/`backoff` in `~/.halo/config.json`. `gateway.routing.
allow_fallbacks`/`route_id` are sent only when `experiential.routing` is
actually configured (there is no default routing preference to assume).
`/xp routes <slug>` (also `/xp` in the TUI, off the UI thread) prints the
rung list from `GET /api/models/<slug>/providers`, plus (Halo 2.0.4 round
5) a "last response" block of the per-response headers below for that
exact slug, when this session has actually called it at least once.

**Response headers (Halo 2.0.4 round 5, pinned against llms.txt).** Every
completion response carries `x-request-id`, `x-gateway-provider` (the
catalog provider of the rung that answered, e.g. `bedrock`/`fireworks`/
`azure_openai`; a platform-hosted lane reads `experiential_cloud`),
`x-gateway-zdr` (`true`/`false`), `x-gateway-route-depth`, and
`x-gateway-route-reason` -- all five captured and carried on the
session's own transcript log (the `usage` node's `experiential_meta`) and
shown in `/xp routes`' "last response" block above.

**Errors.** The gateway's own `error.code` (e.g. `unsupported_capability`,
`unavailable_route`, `pro_required`, `invalid_key`, `idempotency_
conflict`/`idempotency_replay_unavailable` -- the last two share one HTTP
409 but mean opposite retry behavior) maps to one plain sentence each,
read before the generic status-code fallback. The retryable set, pinned
against llms.txt's own "Error envelope" table (Halo 2.0.4 round 5 --
superseding an earlier round's guess that had three of these backwards):
`unavailable_route` (429/503), `gateway_overloaded` (429), `all_routes_
failed` (502), `backend_unavailable` (502), `gateway_draining` (503),
`deadline_exceeded` (504), and `internal_error` (500); every other code
(including `idempotency_replay_unavailable`, whose own fix is "resend
with a NEW Idempotency-Key," never a blind retry) is not retried in
place. A refused parameter (`unsupported_parameter`/`invalid_parameter`)
is always a 400 naming the field, never silently applied; a parameter the
gateway merely couldn't HONOR on the serving rung (dropped, not refused)
is instead disclosed in a top-level `x-experiential-ignored-parameters`
JSON array on the response body itself -- despite the header-shaped name,
the contract states twice that this is a body field, not a header (an
earlier round read it as a header; Halo 2.0.4 round 5 reads the body field
first, keeping the header read too as a defensive fallback) -- learned per
model and surfaced as a one-time notice, never repeated every turn for an
unchanged value. A bare `502` with no JSON body at all (every `error.code`
row above requires one to match) reads as "every route failed, try again
later" through the generic per-status fallback sentence, never as an
empty result or a raw Halo exception.

**Tool search.** `{"type": "openrouter:tool_search"}` plus per-tool
`defer_loading: true` is this gateway's own wire convention for the same
deferred-tool decision Halo's built-in ToolSearch already makes -- off by
default behind `experiential.tool_search` until a live check confirms the
shape; a no-op (no sentinel sent) whenever nothing is actually deferred.

**Local gateway (`exp run`).** A running local `exp` gateway (`pip install
experiential`, default `127.0.0.1:8000`) is recognized by `/local`/`halo
local` the same way any OpenAI-compatible server is -- by its `/v1/models`
response SHAPE, never by port (8000 collides with vLLM's own default) --
and usable as `hf:local/<model>@exp`. Whether it has any Ollama/llama.cpp-
specific attachment is unconfirmed (docs/harness/EXPERIENTIAL-RESEARCH.md
section 8); Halo treats it as a generic local OpenAI-compatible server
either way.

**Embeddings.** `POST /v1/embeddings` and the catalog's `supports_
embeddings` flag are recorded for 2.0.6; no embedding calls are made this
round.

**`jev-latest`.** TypeSafe's typed-decision model (`choice`/`score`/`noul`
answers, no streaming, not a chat model) is reachable as a catalog slug on
this gateway but is informational only -- it is not a `main`/session-chat
candidate, and the jev decision API itself was removed from the roadmap.

### How to run the 2.0.4 "new labs" models

| Model | Run as | Notes |
|---|---|---|
| Space Bunny Alpha | `xp:space-bunny-alpha` | Experiential-only (not on OpenRouter); 1M context, 524k max output, tools + structured output + reasoning (low/medium/high/xhigh/max, default `max`, reasoning hidden); `no_training: true`; priced $0 (preview) as of 2026-10-05 -- re-check pricing before relying on it staying free |
| Nemotron 3.5 Lightning | `xp:nemotron-3.5-lightning` (Experiential), `or:nvidia/nemotron-3.5-lightning` or `or:nvidia/nemotron-3.5-lightning:free` (OpenRouter), `oai:` with a custom base URL + an NVIDIA key (`https://integrate.api.nvidia.com/v1`) | three ways to run the same family; the OpenRouter `:free` variant and the Experiential preview pricing are each their own promotion -- check the data-policy note before sending private code to either |
| Tencent hy4-preview | `or:tencent/hy4-preview` | OpenRouter only; 1,048,576 context, tools + reasoning |
| TypeSafe jev-router | `or:typesafe/jev-router` | a chat-completions ROUTER (picks a model + effort per request), not the jev decision API; variable price, 1M context |

Data-policy note: a preview/promotional model's `no_training: true` is an
Experiential-side posture only -- check the SERVING provider's own policy
(the OpenRouter row's `data_policy`, or the vendor's own terms for `oai:`
with a custom base URL) before sending anything private through it.

Checked against the gateway's own fetched contract (Halo 2.0.4 round 5,
`https://platform.experientiallabs.ai/llms.txt`): the `:free` suffix and
BYOK-connection mechanics this table relies on are both generic, published
behavior (`llms.txt` "Models"/"Two lanes"), not Experiential-specific
guesses; nothing above contradicted it. Any row here that drifts out of
date before the next refresh (a price change, a slug rename) now falls
through to the vendor-family fallback (above, "The model table, catalogs,
and refresh") instead of showing blank context/price columns -- "the same
gap Databricks had."
