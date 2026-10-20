# Models: families, Qwen and reasoning effort

Read this when a model family behaves differently (DeepSeek, Kimi, GLM, Qwen) or you set the reasoning effort.

Part of [Models](MODELS.md), which lists every part.

## Families and their rules

`providers/profiles.py::model_family(model_id)` classifies a bare upstream
id into `claude`, `deepseek`, `kimi`, `glm`, `qwen`, `gemini`, `grok`,
`minimax`, `gpt`, or `generic` by substring match. That family (plus the
exact model id, plus the host) looks up a row in
`providers/model_table.json` -- the single data file every per-model
request-shaping decision comes from, never a per-model `if` branch in the
request builder. Fields a row can override:

- **`reasoning_replay`**: how a "thinking" model's prior reasoning is sent
  back on the next request -- `text`/`deepseek_reasoning_content` (a plain
  field), `details`/`openrouter_details` (OpenRouter's structured array),
  `thinking`/`anthropic_thinking` (a real signed Anthropic block, always
  used for the native passthrough dialect), or `empty` (no known
  requirement).
- **Sampling** (`use_temperature`, `use_top_p`, fixed `temperature`/`top_p`/
  `top_k`, `sampling_unsupported_params`): some families reject a sampling
  parameter outright (e.g. Kimi K2.x-K2.7 fix temperature/top_p server-side
  and 400 if you send them); the request builder pops whichever ones a
  row lists right before sending, regardless of what a caller asked for.
- **`edit_format`**: `diff` (the default) vs. a family that prefers a
  different Edit-tool convention.
- **`tool_id_format`**: `preserve` / `kimi_functions_idx` (Kimi's own
  conversation-global `functions.{name}:{idx}` scheme) / `alnum9` /
  `minimax_preserve` -- different hosts accept different tool-call id
  shapes.
- **`tool_choice_required_supported`**: whether the harness may ever send
  `tool_choice: "required"` (the whole Qwen/GLM family and DeepSeek's
  thinking mode reject it).
- **`tool_leak_patterns`**: named per-family regexes for
  `providers/hooks.py::leak_parser` to recognize a text-embedded tool call
  and promote it to a real `tool_use` block (the repair layer -- see
  `docs/ARCHITECTURE.md`).
- **`context_tokens`**, **`max_tokens_default`**, **`max_tokens_cap`**,
  **`databricks_rate_limits`**, **`unverified`** (which fields this row's
  own data has no primary source for -- informational, never gates
  anything).
- **`reasoning_effort_with_tools`** (1.0.1 hotfix 22, narrowed by the H14c
  fixpass finding 12): when set, a request that carries `tools` sends this
  value for `reasoning_effort` REGARDLESS of `--effort`/the session's own
  effort (a tool-less request on the same model is unaffected). Databricks
  ONLY (an OpenRouter model whose id happens to contain "gpt-6" is never
  affected) -- driven by explicit `model_table.json` rows for both real
  models.dev name shapes, `databricks-gpt-6-{sol,luna,terra}` AND
  `databricks-gpt-5-6-{sol,luna,terra}` (the bare substring "gpt-6" is not
  even a substring of the second shape), each setting `"none"`: verified
  live, `dbx:databricks-gpt-6-sol` 400'd on every turn with "Function tools
  with reasoning_effort are not supported for gpt-6-sol in
  /v1/chat/completions... set reasoning_effort to 'none'", since omitting
  the field left the endpoint's own (non-none) default in place. A live
  400 with this exact wording ("function tool" + "reasoning_effort") on
  any OTHER Databricks OpenAI-family endpoint retries once with
  `reasoning_effort` set to `"none"` explicitly; if THAT retry also fails,
  the general strip-the-field retry below gets its own independent chance
  (a shared one-shot flag used to block it after a failed "none" retry),
  and a successful strip resets the session's own effort so later steps
  stop re-sending the rejected value first.

**The Edit-tool context hint**: a DeepSeek/Kimi/GLM/Qwen/MiniMax-family
session's Edit tool description gets one extra sentence asking for at least
three lines of `old_string` context (computed once per session, so the
wire request stays cache-prefix-stable) -- added after telemetry showed
these families' models under-quote `old_string` and hit "Found multiple
matches" far more often than Claude/GPT do. A specific `(provider,
model_id)` row's own `edit_hint` key (including an explicit empty string)
overrides the family default for just that one model.

## Qwen at work

Halo 2.0.2 round 5: a Databricks work box exposes Qwen two different ways,
and the model picker/`/model` no longer let you confuse them.

**General chat/tool-calling Qwen** -- `dbx:databricks-qwen35-122b-a10b` and
`dbx:databricks-qwen3-next-80b-a3b-instruct` (plus every OpenRouter
`qwen/qwen3-*`/`qwen/qwen3.5-*` id): Hermes-style `<tool_call>{json}</tool_call>`
tool calls, parallel calls on OpenRouter (Databricks sends/accepts one tool
call per turn -- no `parallel_tool_calls` field exists on its strict body
allowlist), `arguments` as a JSON-encoded string on the wire (decoded once
into a real dict on the way in, re-encoded with real `json.dumps` -- never
Python's `str()`/repr -- on replay), no `tool_choice: "required"`
(`tool_choice_required_supported: false` on every row), and the Qwen3-Coder/
Qwen3.5 XML shape (`<function=NAME><parameter=KEY>VALUE</parameter></function>`)
on top of the plain Hermes JSON form. `providers/hooks.py::leak_parser`
recovers a call that leaked into plain text under any of FOUR patterns a
Qwen row declares (`hermes_tool_call`, `qwen3_coder_xml`, `python_repr_args`
-- a bare single-quoted Python-dict-literal call with no wrapper at all,
and `missing_tool_call_opener` -- the documented Qwen3-Coder #475 shape, a
`}</tool_call>` tail with no opening tag); `think_tag_strip` also strips a
bare leading `</think>` with no opening tag (Qwen3-235B-Thinking-2507/QwQ's
own documented replay shape).

**OpenJev -- a decision-only judge model, not a chat model.**
`dbx:databricks-openjev-qwen35-4b` is Databricks' own "OpenJev (Qwen3.5 4B)
evaluates yes/no, choice, and scoring questions" endpoint: a constrained
classifier, never meant to receive `tools`/`tool_choice` at all. Halo
classifies this from data, not a hardcoded model id --
`providers/model_table.json`'s top-level `decision_only_name_patterns`
(substrings like `"openjev"`/`"jev-judge"`, so a differently-named judge
endpoint this box has never seen is still caught) and, for the tabled row
above, its own `capabilities.decision_only` + `capabilities.description`.
Effects, all driven by `providers.profiles.decision_only_info`/
`ProviderProfile.decision_only`/`.tools_supported`:
- The `/model` picker lists it under its own **"Databricks (judge /
  decision)"** group with that one-line description as its detail, instead
  of lumping it in with the ordinary `qwen` chat rows.
- `/model dbx:databricks-openjev-qwen35-4b` (or picking it) never becomes
  the session model -- it is written to the `judge` role instead
  (`roles.judge` in `~/.halo/config.json`, the same thing `/roles set judge
  <model>` does) and the command reports the redirect plainly. Launching
  `halo` with `--model`/a remembered last-model pointed at it behaves the
  same way, falling the session back to the ordinary configured default.
- A request that still carries `tools` for this model (or for ANY
  Databricks endpoint a live request previously proved rejects tools, even
  with no table row at all -- see `~/.halo/learned-rules.json`'s
  `tools_rejected` flag, `providers.learned_rules.learn_tools_rejected`)
  never reaches the wire at all: `providers.request.ToolsNotSupported`
  raises a clear, one-line error naming the model and the `judge` role.
  `agent/loop.py` catches the same condition live, the first time an
  UNTABLED endpoint's own 400 says so (Databricks' `json: unknown field
  "tools"`, or OpenRouter's `no endpoints... support tool use`) -- that one
  call teaches the per-endpoint cache so the next one never repeats it.

**Reading the exact 400 from `halo bugreport`.** If a Databricks Qwen
endpoint still errors on tool calls in a shape this round didn't already
cover, run `halo bugreport` right after the failing turn: its route section
names the resolved `provider`/endpoint, and the `bridge.log` tail it embeds
usually carries the raw HTTP status and error body verbatim (Databricks'
own shape is `{"error_code": "BAD_REQUEST", "message": "..."}`; the message
text is what `providers.errors.is_tools_rejected_message`/
`is_effort_with_tools_rejected_message`/`is_reasoning_replay_bug` each try
to recognize). Quote that exact text in a new issue/brief rather than
re-describing it -- see `docs/harness/QWEN-RESEARCH.md` for what was
already confirmed from Databricks' and Qwen's own docs versus what still
needs a real bug report to pin down.

## Reasoning effort

`--effort`, `/effort <level>`, or `settings.json`'s `effortLevel`/
`modelSettings.<id>.effortLevel` when neither of those was given, maps
through `providers/profiles.py::map_effort`/`providers/request.py::
map_effort_anthropic` to whatever field the resolved profile actually
needs: `output_config.effort` (adaptive-thinking Opus/Sonnet 4.6+, Haiku
5+, Fable/Mythos) or a `thinking.budget_tokens` value (4096/10000/24000/32000/32000
for low/medium/high/xhigh/max, older Claude models) on the native Anthropic
dialect, `reasoning.effort` on OpenRouter, or `reasoning_effort` on a
Databricks chat endpoint. A profile with `reasoning_no_disable: true`
(GLM-5.3/5.3-Flash -- `thinking.type: disabled` is a hard 400 on that
family) forces an explicitly-disabling effort value back up to that row's
own default instead of ever sending `disabled`.

**The "high" default (1.0.1 hotfix 19, scoped by the H14c fixpass finding
11).** When NOTHING more specific is set anywhere (no `--effort`, no
`/effort`, no settings `effortLevel`) AND the model is ADAPTIVE-capable
(Fable/Mythos always, Opus/Sonnet 4.6+, Haiku 5+), the route now defaults to `high`
rather than omitting the field. A NON-adaptive Anthropic-family model
(Haiku 4.5, Sonnet 4.5 or older) keeps the old "omit -> provider default"
behavior instead -- that family has no `{type: "adaptive"}` mode at all,
so "high" became a `thinking.budget_tokens` value close to `max_tokens`
(see below), leaving thinking free to crowd out the actual answer. Every
non-Anthropic family keeps the "omit -> provider default" behavior
regardless. A `/model` switch re-clamps (see below) whatever effort the
session already had for the new route, defaulting a chat-route session
that switches INTO an adaptive-capable Anthropic route the same way.

**Accepted levels per route family, and clamping.** Each
`ProviderProfile` carries `effort_values_supported`
(`providers/profiles.py::clamp_effort` enforces it right before a value
reaches the wire):

| Route family | Accepted levels |
|---|---|
| Anthropic Messages (`ant:`, Databricks Claude foundation), Opus/Sonnet 4.7+, Haiku 5.5+, Fable, Mythos | `low`, `medium`, `high`, `xhigh`, `max` |
| Anthropic Messages, Opus/Sonnet 4.6 and older, Haiku 4.5 | `low`, `medium`, `high`, `max` (no `xhigh` -- that generation's endpoint schema rejects it outright) |
| Databricks GLM (`databricks-glm-*`) | `low`, `high`, `max` ONLY -- narrower than the general chat-dialect set below; see "Databricks GLM" just under this table |
| OpenRouter / Databricks chat, every other family (DeepSeek, Kimi, Qwen, ...) | `low`, `medium`, `high`, `xhigh` (no `max` as of the H14c fixpass finding 13 -- that's an Anthropic-only level; a chat route 400'd on it before this) |
| OpenRouter GLM 5.x (`z-ai/glm-5`, `-5.2`, `-5.3`, `-5.3-flash`) | the full seven Z.ai-direct values: `max`, `high`, `low`, `medium`, `minimal`, `none`, `xhigh` -- OpenRouter forwards them to Z.ai as-is |

A tabled row whose own `reasoning_default_effort` needs a value outside
its route family's default set (GLM's family genuinely defaults to `max`
on OpenRouter/Z.ai directly, per the ingested adapter-rules report --
`reasoning_no_disable` forces a disabling `--effort none` UP to it there)
still accepts that one value too; an explicit `effort_values_supported`
row key, when a future row sets one, always wins outright.

### Databricks GLM (2.0.1, GLM-brief.md)

Verified against the Databricks Foundation Model APIs "supported models"
and "query reasoning models" pages (2026-10-01): every `databricks-glm-*`
endpoint (`databricks-glm-5-2`, `-5-3`, `-5-3-flash`, and any future
`databricks-glm-*` id with no `model_table.json` row of its own yet --
this is a FAMILY-level rule, not per-model) keeps reasoning ALWAYS on and
accepts `reasoning_effort` values `low`, `high`, `max` ONLY -- `max` is
both the default AND the gateway's own SILENT fallback for anything else
(`medium`, `minimal`, `xhigh`, `none`); `none` is rejected outright.
`thinking`/`tool_stream`/`clear_thinking` (all three real Z.ai parameters)
are not in Databricks' parameter list at all, and an unknown field there
is a 400, so none of them can be sent on this route.

**The consequence this fixes**: before 2.0.1, `/effort medium` on a
Databricks GLM route sent `reasoning_effort: "medium"` on the wire, which
the GATEWAY silently coerced to `max` -- the harness never saw an error,
and the user's effort choice was quietly ignored every single turn. That
silent "always max" is also the "GLM seems to pause" symptom
([TROUBLESHOOTING.md](TROUBLESHOOTING.md)): `max` is the model's slowest,
most expensive thinking setting, and a chat-dialect gateway sends nothing
at all -- no reasoning text, no ping -- during that phase; only the
connection stays open. Halo 2.0.1 clamps to the route's REAL default
(`high`, not `max`) and shows the sent value everywhere (`/effort`,
`/status`, `/context`, the stream-json init line's `effort_sent`) instead
of ever silently disagreeing with the gateway.

**The default is sent, not omitted.** Because an omitted field on this
route means `max`, a call with no effort configured anywhere sends
`reasoning_effort: "high"` explicitly (`ProviderProfile.default_effort_
when_unset`, on for the Databricks GLM family only; every other
chat-dialect family keeps "omit -> provider default"). The same rule
applies to an effort inherited from Claude Code's settings (`effortLevel`
or `modelSettings.<id>.effortLevel`, written for Claude models and
typically `xhigh`): a settings value this route does not accept lands on
`high`, not on the clamp map's `max`. An explicit `--effort xhigh` or
`/effort xhigh` is a deliberate choice and still goes through the clamp
map to `max`; `/status` shows the requested and sent values either way.

**Clamp table** (`providers/profiles.py`'s `ProviderProfile.effort_clamp_map`,
consulted by `clamp_effort`/`resolve_effective_effort` before the generic
xhigh/max-narrowing rule):

| Requested | Sent |
|---|---|
| `low` | `low` |
| `medium` | `high` |
| `high` | `high` |
| `xhigh` | `max` |
| `max` | `max` |
| `minimal` | `low` (the cheapest accepted level, not the route default) |
| `none` | `low` (never sent literally -- Databricks rejects it outright) |

`/effort` on a Databricks GLM route therefore offers `low [high] max` (its
real accepted set) and marks any other requested value with "sent as X on
this route" rather than a plain, misleading echo.

Temperature is clamped to `[0, 1]` on every GLM-family route (Z.ai GLM API
docs: "temperature range [0, 1] default 1.0") -- a safety net, since every
seeded GLM row's temperature is already 1.0; and GLM never receives
`tool_choice: "required"` (the gateway accepts `auto` only -- the repair
layer's text-nudge fallback is used instead, same as DeepSeek-thinking/Qwen).

`xhigh` on a route that doesn't list it becomes `max` ONLY when that
route's own accepted set includes `max` (Anthropic 4.6-generation models,
or a GLM-5.3-style tabled exception) -- that route's own strongest level.
A request for LESS reasoning (`none`, `minimal`, or `low` on a route
without it) becomes the route's WEAKEST accepted level -- `oai:o3
--effort minimal` sends `low`, never the route's strongest-level default.
Any other unrecognized value (including a now-rejected `max` on an
ordinary chat route) falls back to the route's own default. This is what fixed a live
400 on `dbx:databricks-claude-opus-4-6`: the user's own
`~/.claude/settings.json` `effortLevel: "xhigh"` (valid for real Claude
Code's own routes) reached `output_config.effort` verbatim and was
rejected (`Input should be 'low', 'medium', 'high' or 'max'`) on the very
first prompt. As a backstop for a route whose accepted set isn't modeled
correctly yet, a live 400 naming the effort field retries ONCE with it
stripped from the body before the turn is treated as failed -- recognized
wordings now include Databricks/Anthropic's own `output_config.effort`/
`reasoning_effort` field names, OpenRouter's nested `reasoning.effort`
path, and a generic OpenAI-style "Invalid value: '`max`'"/"'`xhigh`'"
enum-validation 400 that names neither field by name.

**Thinking budget cap (non-adaptive models).** When effort maps to a
`thinking.budget_tokens` value (any non-adaptive Anthropic-family model),
the budget is capped at HALF of `max_tokens` (never below Anthropic's own
1,024-token minimum), not `max_tokens - 1` -- the old near-`max_tokens`
budget left thinking free to crowd out the actual answer. The version
parser behind the adaptive-capability check reads hyphenated ids
(`claude-sonnet-4-6`, `databricks-claude-sonnet-4-6`) as `4.6`, not a bare
major version `4` (a literal-dot `claude-sonnet-4.6` was already read
correctly). Thinking is dropped entirely on the one-shot
`tool_choice: "any"` repair retry (the leak-parser fallback) -- Anthropic
rejects extended thinking together with any forced (non-`"auto"`)
`tool_choice`. Claude Opus 5.5, Sonnet 5.5, Fable 5.1 and Mythos 5.1
reject a forced `tool_choice` outright (400), so the repair retry is not
issued on those models; the reply stands as the model sent it.

Which Claude model does what (adaptive thinking, `xhigh`, forced
`tool_choice`) is DATA: `model_table.json`'s `anthropic_model_capabilities`
lists, per family, the version each behaviour starts at, read through
`providers/anthropic_caps.py`. A new Claude generation is a one-line edit
there.

**`/effort`** (1.0.1 hotfix 20): shows the effective level, its source
(`flag`/`settings`/`default`/`session`), and this route's own accepted
levels when given no argument; `/effort <level>` sets it immediately
(clamped the same way), remembered for the rest of the session. In the
TUI, bare `/effort` instead opens an inline selector card in the
transcript -- a horizontal row of this route's accepted levels, current
one bracketed, Left/Right or h/l to move, Enter to apply, Esc to cancel
and keep the old value; a model with no adjustable effort at all shows a
one-line card that closes on any key. The status bar shows a short effort
tag next to the mode glyph.
