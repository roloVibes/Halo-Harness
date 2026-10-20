# Models: the OpenAI API

Read this when you use `oai:` with an OpenAI key.

Part of [Models](MODELS.md), which lists every part.

## OpenAI API

Halo 2.0.3 round 5i part 1 (`plans/2.0.3-ollama-round2-brief.md` "Round
5i", design doc `docs/harness/OPENAI-RESEARCH.md`). `oai:<model>` against
the real `https://api.openai.com/v1`, `Authorization: Bearer
$OPENAI_API_KEY` -- separate from a Databricks-hosted `gpt-*` foundation-model
endpoint (`dbx:databricks-gpt-...`), which is a different host entirely.
`BRIDGE_OPENAI_BASE_URL` (or the `HALO_`/`ROLO_CLAUDE_` twin,
`config/paths.py::env_compat`) overrides the base URL for tests, exactly
like every other provider's own base-URL knob. **No OpenAI key exists on
the build host as of this round -- every behaviour below is verified
against the parameterized fake (`tests/helpers/mock_openai.py`) only,
never against the real API; treat it as unverified live until a key is
available and the orchestrator runs a real check.**

**Two dialects.** Chat completions (`openai-chat`, the default) goes
through the SAME request/stream/profile code every other openai-chat-
dialect provider already uses -- tools supported, reasoning effort
passthrough, no OpenRouter-only fields. The Responses dialect
(`openai-responses`, `POST /v1/responses`) is a full second wire shape:
`instructions` for the system prompt, `input` items (message items;
`function_call`/`function_call_output` items for tool use, replacing
chat completions' `tool_calls`/`tool` messages) instead of `messages`,
`tools` as flat function items (never nested under a `"function"` key),
`reasoning: {effort}` from the session's effort, `store: false` and
NEVER `previous_response_id` on every request -- Halo always keeps
owning the transcript itself, the same way every other dialect here
replays its own history rather than leaning on server-side state. A
reply's reasoning item is captured for DISPLAY only (like the `ollama`
dialect's own `reasoning_replay="empty"`) -- never replayed on the wire;
replaying it would need `store` on plus `previous_response_id`, or the
encrypted-reasoning-content alternative, neither of which this round
implements (`docs/harness/OPENAI-RESEARCH.md`'s own documented scope
cut). Streamed `response.*` SSE events decode into the same Anthropic-
shaped events every other dialect's decoder produces
(`providers/responses_stream.py`).

**Dialect selection.** Exactly the two bare ids the Responses API
reference names as REQUIRING this dialect for function calling --
`gpt-6-astra`, `gpt-6.1-sol` -- default to `openai-responses`; every
other `oai:` model defaults to `openai-chat`. Similarly-named ids the
same page does NOT name (`gpt-6-sol`, `gpt-6-luna`, `gpt-5.6-sol`, ...)
are deliberately left on chat completions by default -- a substring match
would have wrongly swept them in. `openai.dialect_overrides`
(`~/.halo/config.json`, `{"<bare id>": "chat"|"responses"}`) always wins
over the table, in either direction, since the guide only ever documents
a requirement, never a complete negative list.

**Reasoning effort.** `none`, `minimal`, `low`, `medium`, `high`,
`xhigh`, `max` are all real, current, documented values on this dialect
(confirmed live against the Responses API reference) -- a strict
superset of this harness's own `--effort`/`/effort` vocabulary, so
nothing the harness itself can ask for is ever clamped on this route.

**Catalog.** `GET /v1/models` cached in its own `~/.halo/openai-
models.json` with the same TTL knob every other network catalog here
shares (`databricks.catalog_max_age_hours`) -- this endpoint carries no
context length or pricing at all (confirmed live), so it only ever
proves "this key can see this id" for the `/model` picker's OpenAI group
and `halo providers`' model-count column. Price and context come from
the SEPARATE models.dev cross-check instead (`providers/catalog/
models_dev_openai_fallback.json`, all 53 current ids, vendored the same
way the Databricks fallback is; a refreshed `~/.halo/models-dev.json`
cache -- `halo models --refresh` -- wins when fresher).

**Balance.** The OpenAI API has no public balance endpoint for ordinary
keys -- `/providers`/`halo providers` say so plainly and show this
session's computed spend instead (from the catalog's own price, the
same rule part B of the original 2.0.3 brief gives for TypeSafe), falling
back to "see `/cost`" when no live session is attached (the standalone
CLI).

**Setup.** `halo init`'s "OpenAI API (key)" tab (same pattern as the
Hugging Face tab: paste the key, Save) or hand-write `OPENAI_API_KEY` to
the env file; auto-enabled once detected, same rule every other key-only
provider here follows. `halo doctor`'s provider count already includes
it once enabled (the generic `PROVIDER_NAMES` table, no bespoke doctor
line needed).

