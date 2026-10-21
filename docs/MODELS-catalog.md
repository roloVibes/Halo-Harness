# Models: the catalog, prices and the picker

Read this when you refresh the model list, read a price or DBU cost, use the `/model` picker, or go offline.

Part of [Models](MODELS.md), which lists every part.

## The model table, catalogs, and refresh

Three cached files under `~/.halo/` back model-profile resolution,
consulted in this order before falling back to a hardcoded guess
(`model.py::resolve_model_profile`):

1. **`models.json`** (OpenRouter) / **`dbx-endpoints.json`** (Databricks) --
   the live-probed catalog (`halo models --refresh`; see
   `docs/COMMANDS.md`). Supplies real context window, max output tokens,
   vision support, and (OpenRouter) pricing including cache-read/cache-write
   rates.
2. **`routes.json`**'s own `profiles` map -- a hand-authored override,
   keyed by bare model name or `"default"`.
3. **The vendored fallback tier** (`providers/catalog/*.json`, shipped
   inside the package) -- OpenRouter's own catalog and models.dev's
   `databricks` provider entries, frozen at release time, so a **fresh
   install with no network yet** (most notably a Databricks work box behind
   a VPN that might not be up) still resolves real context/output/pricing
   for every model this harness ships defaults for, instead of the bare
   128k/16k dataclass guess.
3b. **The vendor-family fallback** (Halo 2.0.4 round 5, `providers.
   models_dev.vendor_family_profile_fields`) -- models.dev's own
   `databricks` provider entry lists only 30 ids and lacks every endpoint
   newer than that snapshot (`claude-opus-5`/`-5.5`, `claude-sonnet-5`/
   `-5.5`, `claude-opus-4.8`, `deepseek-v4-flash`/`-pro`, `gemini-3.5`/
   `3.7`/`3.8-flash`, `gemma-3-12b`, `glm-5.3`/`-flash`, as of this round),
   but the VENDOR providers in the same models.dev dump (`anthropic`,
   `google`, `deepseek`, `zai`) do carry those families under their own,
   un-prefixed ids. Consulted between tiers 1/3 and 4 above: strip a
   leading `databricks-`, normalize version punctuation (`opus-4-5` ->
   `opus-4.5`, `gemini-3-5-flash` -> `gemini-3.5-flash`; a parameter-count
   id like `gemma-3-12b` is left alone), parse a Bedrock-style external
   endpoint id (`us-anthropic-claude-sonnet-4-5-20250929-v1-0` ->
   `claude-sonnet-4.5`, read off `foundation_model.name` when the bare
   endpoint `name` itself doesn't resolve), and guess the vendor from the
   slug's own family prefix. The SAME lookup, keyed off the vendor segment
   of an `or:<vendor>/<slug>` id instead, also fills an OpenRouter row with
   no vendored entry of its own, and an `xp:` slug this session's
   `experiential-models.json` cache has no row for yet -- "the same gap
   Databricks had," per the round's own brief. A row sourced this way
   carries a `vendor list price` marker (the picker's own `detail` column)
   since the vendor's published list price can differ from what
   Databricks/the gateway actually bills per token.
4. `providers/model_table.json`'s own `context_tokens`/`max_tokens_cap`
   (request-shaping data, not economics, but a real, hand-verified number
   for this harness's own pinned Databricks work-default models even if
   nothing else above has one).

`ant:` alias models are resolved from a **separate**, fourth table
(`providers/anthropic_aliases.py::ANT_MODEL_TABLE`) first; `halo models
--ant --refresh` lists every id the key can actually reach.

`models-dev.json` (models.dev's own public, unauthenticated `api.json`) is
fetched by `halo models --refresh` regardless of which providers are
configured -- it backs the Databricks vendored-fallback tier and
`doctor`'s cache-freshness check.

## Pricing and DBUs

**Live per-turn cost** (`stats`/`/cost`, and the status bar's own `$` field
since 1.0.1 hotfix 14) still works exactly as before for OpenRouter: real
per-token USD pricing in `models.json` (`price_in`/`price_out`/
`price_cache_read`/`price_cache_write`); when a response itself doesn't
carry a `usage.cost` field, `CostMeter` derives one from those rates
(input × price_in + (output + reasoning) × price_out + cache_read/
cache_write at their own rates, falling back to `price_in` for cache tokens
when no specific rate is known). **Databricks** used to always report
`n/a` regardless of pricing; since 1.0.1 hotfix 14, `resolve_model_profile`
feeds the SAME per-endpoint price used for the listed columns below (source
(a), the models.dev `databricks` entry) into this session's `CostMeter` at
start-of-session, so a Databricks turn on an endpoint models.dev prices
gets a real computed running cost through the identical fallback formula
above -- and still shows `n/a` (falls back to token totals in the status
bar) whenever no models.dev price exists for that endpoint, which remains
the common case.

**Listed (not live) context/output/price columns** -- what `/model`,
`/models`, `halo models`, and `init`'s own picker show per row
(`halo_harness.model_display.format_model_row`, one implementation shared
by every one of those surfaces) -- are a DIFFERENT, catalog-level concept:
a normalized (`200000` -> `200k`, `1048576`/`1050000` -> `1M`) reference
figure for the model itself, never a live spend number, sourced per
provider:
  - **OpenRouter**: `models.json`'s own `context_length`/`max_output_tokens`/
    `pricing.prompt`/`pricing.completion` (the exact same fields `CostMeter`
    above reads, just displayed rather than multiplied against real usage).
  - **`ant:`**: the Claude aliases' own static table
    (`providers.anthropic_aliases.profile_fields_for_ant_model`).
  - **Databricks**: (a) the [models.dev](https://models.dev) `databricks`
    provider's entry whose id equals the endpoint name (the live
    `~/.halo/models-dev.json` cache, refreshed by `models --refresh`/
    `/models refresh`, else the package-vendored fallback) -- `limit.context`/
    `limit.output` for context/output, `cost.input`/`cost.output` (already
    USD per million tokens) for the prices, used AS-IS, never re-multiplied;
    (b) missing that, the vendor-family fallback above (the row's `detail`
    column then adds a `vendor list price` marker, and `not ready` when the
    serving-endpoints probe's own `state.ready` says so); (c) missing that
    too, `model_table.json`'s own `context_tokens` (output/prices then stay
    blank); (d) none of the above -- every field blank. **A blank field is
    never shown as `?`** -- it just keeps its column's width.

`databricks.dbu_price_usd` (`~/.halo/config.json`, or a team.json's
`dbu_price_usd`) is a THIRD, separate figure, in a different unit again: it
converts an endpoint's own **catalog-advertised** DBU rate
(`usage_policy.output_dbu_per_1k_tokens`, when the workspace publishes one)
into a dollar figure, appended after the ctx/output/price columns as
`dbu=<rate>` only when actually known -- a reference price, never a real
per-turn spend, and never conflated with the USD/1M-token prices above.

## The `/model` picker

Opening `/model` with no argument triggers a background refresh of the
Databricks/OpenRouter/Hugging Face catalogs (each gated on that provider
being enabled) if older than `databricks.catalog_max_age_hours` (default
24h, the one shared staleness knob every network catalog here uses) --
the picker itself opens immediately with whatever's already cached; the
refresh only ever notifies afterward if something changed. The picker is
a filterable, arrow-key list (`Up`/`Down`/`PageUp`/`PageDown`/`Home`/`End`
move the highlight, typing filters, `Enter` confirms, `Esc` cancels -- the
filter box itself keeps keyboard focus throughout) grouped by provider/
family, one header per group: OpenRouter, `Hugging Face` (Halo 2.0.3
round 4 -- the router's own cached catalog, shown once the provider is
enabled), `Anthropic API (key)` (shown once `ANTHROPIC_API_KEY` is
set), and
`Databricks (<family>)` per family, each row showing which gateway path
type it resolves to (see [DATABRICKS.md](DATABRICKS.md)) alongside the
ctx/output/price columns above; non-chat endpoints (embeddings/whisper) are
hidden entirely. `halo init`'s own per-provider and final
cross-provider model pickers (see [COMMANDS.md](COMMANDS.md)'s `init`
section) use this exact same list widget and row format. See
[DATABRICKS.md](DATABRICKS.md) for exactly how a Databricks model
reference resolves to a URL, and [COMMANDS.md](COMMANDS.md) for
`halo models`'s own flags.

Ollama hosts and Hugging Face local servers never appear in THIS picker
(by design -- an `ol:`/`hf:local/*` model is a `roles.small` pick far more
often than "the one main model," and listing every host's live catalog
here would mean a network read on every `/model` open); `/local` (round
5) is the dedicated discovery view for both.

A `<ref>:free` row (OpenRouter's own free-lane suffix) always sorts
immediately beside its paid `<ref>` sibling, under every one of `Ctrl+S`'s
sort keys (name/price/context/speed/best) -- not just the alphabetical default,
where a free row's own `$0` price would otherwise scatter it to the front
of a price-sorted group, far from the paid row it's a variant of.

## Enforced offline mode (Halo 2.0.3 round 5e)

`halo --offline`/`/offline on`/`network.offline` in `~/.halo/config.json`
make the one HTTP choke point (`providers/http.py`'s `open_upstream`/
`urlopen_tls` -- every provider call in this document, every catalog
refresh, every update check, and the WebFetch/WebSearch tools all funnel
through one of the two) refuse any connection whose host is not loopback
or an allow-listed local host (`ollama.hosts`, `huggingface.
local_servers`, or a `halo local serve` managed server); a refusal is
always the one plain sentence "offline mode: not connecting to \<host\>",
never retried. In practice this means every route this document describes
except `ol:`, `hf:local/*` and `hf:mlx/*` (and a `hf:endpoint`/manual
`hf:local` entry that happens to point at a LAN address the user never
configured) simply refuses outright while offline mode is on -- see
[CONFIG.md](CONFIG.md)'s `network.offline` section for the full allow-list
and [COMMANDS.md](COMMANDS.md)'s `--offline`/[SLASH-COMMANDS.md](SLASH-COMMANDS.md)'s
`/offline` for how to turn it on.

## Hybrid escalation (Halo 2.0.3 round 5e)

`routing.escalation` (`~/.halo/config.json`) lets a local-first session
(`ol:`/`hf:local/*`/`hf:mlx/*` -- never a cloud-model session) name a
cloud fallback ref and the conditions that should escalate to it:
`low_confidence` (a one-word CONFIDENT/UNSURE check against the `judge`
role -- the exact same role-resolution and one-shot-call shape `roles.
small`'s own answers already use, never a new scoring mechanism of its
own), `tool_failures` (two or more failed tool calls in the current
turn), and `context_overflow` (the existing compaction-overflow retry path
firing this turn). `ask: true` (the default) only ever notifies, staying
on the local model; `ask: false` switches for the rest of the turn (`tool_
failures`/`context_overflow`) or starting with the next model call
(`low_confidence`, since the triggering turn has already finished) and
says so in the transcript. A role-table entry's own `"escalation": false`
turns this off for every sub-agent resolved under that role, regardless of
the top-level policy. `/escalation` shows the active policy and this
session's last few decisions; see [CONFIG.md](CONFIG.md)'s `routing.
escalation` section for the full config shape.

## Saved versus cloud (Halo 2.0.3 round 5e)

For an `ol:`/`hf:local/*`/`hf:mlx/*` turn, the cost meter also prices that
turn's real input/output/cache token counts (the exact same arithmetic
`CostMeter`'s own cloud-pricing fallback formula uses) against a
REFERENCE price -- the session's configured `routing.escalation.to`, when
one is set, else the median `price_in`/`price_out` across every model the
package's own vendored fallback catalogs carry a real price for (no
network call, so this works identically online or under `--offline`) --
and accumulates the difference as "saved". The status bar's cost chip
shows it as " · saved $x" next to the ordinary cost figure; `/cost` prints
the running total, the turn/token counts it is over, and which reference
price it used and why. Always `$0.00`/omitted on a cloud-model session --
there is nothing to compare it against.
