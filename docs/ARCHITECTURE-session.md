# Architecture: the session loop

Read this when you change how a request is built: the session log, pruning, providers, reasoning replay, the tool catalog and the repair layer.

Part of [Architecture](ARCHITECTURE.md), which lists every part.

## The session log is the single source of truth

`agent/log.py`'s `SessionLog` is an append-only JSONL file,
`~/.halo/sessions/<project-slug>/<session-id>.jsonl`
(`SessionLog.latest_for_cwd` picks the most-recently-modified file under a
project's slug directory for `-c`/`--continue`). Every node the loop ever
appends is one of: `meta`, `system`, `user`, `assistant` (content blocks
including raw thinking/reasoning, plus a sibling `tool_meta` map -- never a
content block itself -- recording per-tool-call repair status), `tool_result`,
`snapshot` (dynamic context delivered as a user-role block -- permission
mode, CLAUDE.md chain, memory index, skills, notices), `usage`, `error`,
`interrupted`, `compacted` (a pure shadow-range marker, never a rewrite of
earlier nodes), `rewind` (an audit trail entry for `/rewind`/`/undo`/`/redo`),
`prune_commit` (which tool-result stub ids `agent/prune.py`'s stable-batch
commit just fixed in place), and `improve_applied` (an approved `/improve`
write). `NODE_TYPES` in `agent/log.py` is the exhaustive, asserted-on-every-
append list.

The invariant this exists to make checkable (dsh's own phrase, adopted
directly): **"model-visible means logged. Anything that reaches a model
request must be reconstructable from the log, and a runtime invariant
asserts it."** Concretely: `agent/derive.py`'s `derive_request()` rebuilds
the exact `(system_text, messages, tools)` triple a real request would send,
*purely* from the log -- nothing the loop does to build a request reads any
other in-memory state. Two mechanisms back this, at different times: at
*runtime*, `agent/invariants.py::synthesize_missing_results` guarantees the
log itself can never be left in an unreconstructable state (every `tool_use`
id gets exactly one `tool_result` before the next assistant node, even on a
crash/interrupt); at *test* time, the assistant node's own `request_hash`
field (`agent/derive.py::content_hash_from_oai_body`, hashing the wire body
that was **actually sent**, policy fields like `max_tokens`/`temperature`
excluded) is compared against `content_hash()` re-derived from the log up to
(excluding) that same node -- an equal hash proves the request that produced
that reply is byte-reconstructable from the log alone. This is also *why*
`/rewind`, compaction, and session resume can never disagree with each other
or with what actually happened -- they all read the same one append-only
file, never a separate in-memory model.

Two direct consequences:

- **Resume** (`-c`/`-r`, `agent/sessions.py`) just points a new process at
  the same log file and calls `derive_request()` again -- there is no
  separate "session state" to reconstruct.
- **A sub-agent** gets its own log (`<parent_session_dir>/subagents/
  agent-<id>.jsonl`), never appends into the parent's, and its rolled-up
  cost/usage reaches the parent as one ordinary `usage` node the parent's
  own log gains when the child finishes -- so the parent's own history stays
  a complete, ordinary derivable log too.

## Deriving and pruning a request

`derive_request()` (agent/derive.py) walks the log forward once, producing
the model-shaped `(system_text, messages, tools)`. `agent/prune.py`'s
`prune_messages()` then runs **after** derivation and **before**
`providers/request.py` ever builds a wire body, so the log itself always
keeps the full, unpruned text -- only what actually goes out over the wire
shrinks. One rule (from dsh's own tool-result pruner, plus OpenCode's
protection-window constants): a `tool_result` whose distance from the end
of the message list -- summed, in estimated tokens, over every
`tool_result` newer than it -- exceeds `PRUNE_PROTECT_TOKENS` (40,000) is
replaced with a short excerpt plus a fixed marker string. A result inside
that protection window is left exactly as its own tool already truncated it
at logging time (`tools/truncate.py`); this module never re-truncates
something already inside its cap.

`providers/request.py::build_request_body` (OpenAI-chat dialect) and
`providers/anthropic_sse.py::build_anthropic_body` (native Anthropic
Messages) turn the pruned, derived triple into the exact wire body for the
resolved `ProviderProfile` -- system/developer placement, `max_tokens`
field name, the body allowlist (Databricks' gateway 400s on any unlisted
key), tool schema simplification, and per-family sampling parameters all
live there, driven entirely by data (`providers/model_table.json`), never
per-model `if` branches sprinkled through the request builder.

## Providers and compatibility profiles

Four routes, one `ModelRef`/`ModelProfile` pair (`model.py`) describing
each: `openrouter` and `databricks` (both `openai-chat` dialect, i.e. an
OpenAI-style `/chat/completions` body), `anthropic` (native Anthropic
Messages, used by `ant:` and Databricks' own Claude passthrough), and `cc`
(not a wire dialect at all -- see "The subscription route" below).
`providers/profiles.py::resolve_profile(route, model_table)` resolves a
`ProviderProfile` from `(host, model family)` plus any per-model override
row in `model_table.json` -- the central finding this design starts from is
that **a gateway's behavior cannot be guessed from its base URL alone**, so
every field a request needs (system-vs-developer placement, reasoning
replay format, sampling parameter support, tool-call id format, tool-choice
modes, leak-text patterns, context window) is explicit, data-driven, and
per-(family, host) rather than inferred.

`model_family(model_id)` classifies a bare upstream id into one of `claude`,
`deepseek`, `kimi`, `glm`, `qwen`, `gemini`, `grok`, `minimax`, `gpt`, or
`generic` by substring match -- this is what selects a `model_table.json`
row, and what a handful of narrow fallback defaults (for a family the
open-weight adapter research never had to cover, i.e. `claude`/`gpt`/
`gemini`/`generic`) key off when no per-model row exists at all.

## Reasoning replay per family

A "thinking" model's own reasoning tokens have to be sent back on the
*next* request (so a tool-calling turn keeps its own train of thought
intact) in whatever shape that specific API expects them in --
`ProviderProfile.reasoning_replay` picks one of:

- `"text"` / `"deepseek_reasoning_content"` -- a plain `reasoning_content`
  string field alongside the message (DeepSeek/Kimi/GLM/Grok/MiniMax family
  default).
- `"details"` / `"openrouter_details"` -- OpenRouter's own structured
  `reasoning_details` array, verbatim.
- `"thinking"` / `"anthropic_thinking"` -- a real Anthropic `thinking`
  content block with its cryptographic `signature`, for the native
  passthrough dialect (always used for a `dbx:`/`ant:` Claude ref).
- `"empty"` -- the fallback for a family/host with no known replay
  requirement at all.

`providers/hooks.py` (not the settings-hooks protocol -- a same-named,
unrelated module of small per-request transform functions) implements the
actual mechanics per format: `reasoning_echo` (DeepSeek V4's own
dual-field quirk: OpenRouter wants *both* `reasoning_content` and
`reasoning_details` on the same replayed message), `tool_id_normalize`
(`preserve` / `kimi_functions_idx` / `alnum9` / `minimax_preserve` --
different hosts accept different tool-call id shapes), and `leak_parser`
(promoting a text-embedded tool call some models emit instead of a real
`tool_use` block, keyed to that family's own known leak-text patterns).

## The frozen tool catalog and ToolSearch

`agent/catalog.py`'s `SessionCatalog` freezes the tool list **once**, before
a session's first model call: built-ins plus every already-connected MCP
tool are split into **preload** (an MCP tool's own
`_meta["anthropic/alwaysLoad"]`, or a wire name listed in
`~/.halo/config.json`'s `mcpPreload`) versus **deferred** (everything
else, reachable only through the `ToolSearch` tool), respecting the
resolved profile's `tools_max` (32 on Databricks, 128 on OpenRouter).
Growth from a `ToolSearch` load is **append-only** to an explicit ordered
name list, independent of `ToolRegistry.definitions()`'s own
(always-alphabetical) ordering -- once a session exists, that growing list
is what every later request's tool array is built from, and what a new
`meta` log node records, so `derive_request()` reconstructs the exact same
growing-but-never-reordered catalog on every replay. "Adding a tool mid-
session is an accepted one-time cache-miss, never a reorder" is the design
rule this exists to satisfy (reordering the tool array on every turn would
invalidate a provider's own prompt cache far more often than a rare
catalog growth does).

`ToolSearch("select:<name>[,<name>...]")` loads specific deferred names by
exact match; `ToolSearch("free text")` ranks by name/description (an MCP
tool's own `_meta["anthropic/searchHint"]` is weighted above both). A name
that resolves but can't be loaded because the catalog is already at its cap
and nothing loaded-but-deferred can be evicted is reported as refused,
explicitly, in that same call's result -- it is never silently promised for
"next turn" when it isn't actually going to be there.

## Tools and the repair layer

`tools/registry.py::ToolRegistry` holds the frozen catalog (`without()`/
`filtered()` build the deny-rule/`--tools`-restricted view at session
start; `add_tool()`/`remove_tool()` are the only in-place mutations,
reserved for `ToolSearch`'s lazy load/LRU eviction). Every dispatch goes
through the one `ToolRegistry.dispatch()` choke point, which never lets a
tool's own exception escape (a raising `run()` becomes an ordinary
`is_error=True` `ToolResult` instead of killing the loop) and stamps
`duration_ms` for telemetry. A batch of consecutive read-only calls
(`Tool.is_read_only`, informational-only -- see "Permissions" below) runs
concurrently on a small bounded thread pool, results returned in call
order, never completion order.

Before a model's raw `tool_use` block ever reaches dispatch, `agent/
repair.py::repair_assistant_turn` runs, in this fixed order (agent/loop.py's
own scope-D contract): `agent/invariants.py::validate_tool_use` (non-empty
id, dict-shaped input) → name resolution/schema validation+coercion/
duplicate-call detection/promoting a text-embedded call to a real
`tool_use` (via `providers/hooks.py::leak_parser`) → `permissions.py::
PermissionEngine.decide()` → dispatch → `tools/truncate.py::
spill_and_truncate` → the logged `tool_result`. Nothing in this chain
silently drops a call: every outcome is either a usable (possibly repaired)
block or a clear, quoted error text the model can act on.

`agent/invariants.py` also enforces the loop's own "session poisoning"
guards at well-defined points: every `tool_use` id gets exactly one
`tool_result` before the next assistant node (`synthesize_missing_results`
manufactures an `ABORTED_BEFORE_DISPATCH`/"Tool call interrupted by user"
result for any left dangling on cancel/crash/interrupt), and a lone UTF-16
surrogate from a stream truncated mid-character is repaired rather than
left to crash whatever reads it next.
