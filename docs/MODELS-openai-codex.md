# Models: the OpenAI API and the Codex subscription

Read this when you use `oai:` with an OpenAI key or `cx:` with a ChatGPT subscription through Codex.

Part of [Models](MODELS.md), which lists every part.

## OpenAI API

Halo 2.0.3 round 5i part 1 (`plans/2.0.3-ollama-round2-brief.md` "Round
5i", design doc `docs/harness/OPENAI-RESEARCH.md`). `oai:<model>` against
the real `https://api.openai.com/v1`, `Authorization: Bearer
$OPENAI_API_KEY` -- separate from a Codex subscription login (`cx:`,
5i part 2), and separate from a Databricks-hosted `gpt-*` foundation-model
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

## Codex subscription (ChatGPT)

Halo 2.0.3 round 5i part 2 (`plans/2.0.3-ollama-round2-brief.md` "Round
5i", design doc `docs/harness/CODEX-RESEARCH.md`). `cx:<model>` drives
the installed `codex` CLI headlessly under the user's own ChatGPT
subscription login -- the Codex counterpart of `cc:`, mirroring its
design wherever Codex's own architecture allows and documenting where it
genuinely differs. **No one is logged into Codex on the build host as of
this round -- every behaviour below is verified against the parameterized
fake (`tests/helpers/fake_codex.py`) only, never against the real CLI;
treat it as unverified live until a ChatGPT login is available and the
orchestrator runs a real check.**

**Detection.** The `codex` binary on PATH (bare, `.exe`, or `.cmd` -- the
same resolution `cc:` uses for `claude`, deliberately never probing
`codex.ps1`) plus `codex login status` reporting a real ChatGPT login.
That command prints PLAIN TEXT, never JSON -- the one string that counts
as a subscription login is `"Logged in using ChatGPT"`; every other
answer (an API key, Bedrock, an access/personal-access token, workload
identity) is logged in but NOT the subscription cx: wants, so it is
refused with a message pointing at `oai:` instead. Halo never reads
`~/.codex/auth.json`.

**Models.** `gpt-6-astra`, `gpt-6.1-sol`, `gpt-6-luna` are the documented
ChatGPT-plan ids (`gpt-5.5` is API-key only, retired from ChatGPT products
2026-10-14) -- short aliases `cx:astra`/`cx:sol`/`cx:luna`, or the full id
directly. Context/output/vision come from the SAME vendored `openai`
models.dev catalog `oai:` reads (the model is identical either way); price
is always `None` on this route -- a ChatGPT subscription has no metered
per-token price, so the cost meter records token usage with no dollar
figure rather than inventing one.

**Execution, one subprocess per turn.** Unlike `cc:` (one `claude`
process held open across the whole session, fed one stdin line per turn),
`codex exec` has no stdin-streaming protocol at all -- each Halo turn
spawns a FRESH `codex exec [resume <thread-id>] --json -` and runs it to
completion. The thread id is Codex's own (learned from its first
`thread.started` event, logged as a `cx_session_id` meta node, exactly
like `cc_session_id`) -- every turn after the first resumes it, so the
conversation is continuous on Codex's own side even though the OS process
is not. Halo's permission mode maps onto Codex's `approval_policy`/
`sandbox_mode`, keyed on the engine's own six real mode names: `auto` and
`bypassPermissions` -> `never`/`danger-full-access` (full access, never
asks); `default` and `acceptEdits` -> `on-request`/`workspace-write`;
`dontAsk` -> `never`/`workspace-write`; `plan` -> `never`/`read-only` (plan
mode never writes at all, so this is also the one row with nothing for an
unanswerable approval request to block on). Both values ride on
`-c approval_policy=<value> -c sandbox_mode=<value>` on
EVERY invocation, a fresh `exec` and a `resume` alike -- `codex exec
resume` has no `-s/--sandbox` flag of its own at all, only `exec` does, so
the sandbox is never passed that way on either subcommand.

**The prompt rides on stdin, never on argv.** The preamble, any carried-
over conversation (a mid-session switch into `cx:`), the user's own text
and a queued steer are all written to the subprocess's stdin in one
shot and the pipe is closed right behind it -- the trailing bare `-` in
the argv above is `codex exec`'s/`codex exec resume`'s own "read the
prompt from stdin" marker, confirmed in both subcommands' `--help`. A
prompt never appears in argv at all: on POSIX it would otherwise sit in
a world-readable `/proc/<pid>/cmdline`; on Windows, when the resolved
`codex` is the npm global install's `codex.cmd`/`codex.CMD` batch shim,
argv is handed to cmd.exe for a SECOND, unwanted parse pass (a quoted
`&` truncates the command there, `%VAR%` expands, and the practical
length ceiling is a few KB) -- Halo resolves that shim's real entry
point instead (`node <...\node_modules\@openai\codex\bin\codex.js>`,
sitting right beside the shim in an npm global install) and launches
that directly, falling back to the shim itself only when the script
isn't found beside it. There is no length cap on the prompt itself any
more; a model's own context window is the only remaining limit.

**Tools.** Codex keeps its OWN native tools (shell, apply_patch) running
in its own sandbox -- no flag was found to disable them the way `cc:`'s
`--tools ""` disables Claude Code's. Halo's own tool catalog is
ADDITIONALLY exposed through an inline `-c mcp_servers.halo.<field>=
<value>` override pointing at the SAME `python -m halo_harness.ccbridge`
child + bridge server `cc:` already uses -- a genuine MCP tool call
through it is dispatched through Halo's own permission engine/hooks/log
exactly like every other route's tools; a native Codex action is logged
read-only, after the fact, from its own `item.completed` event, never
gated by Halo (there is nothing left to gate -- it already ran). The
bridge's own secret token/socket address are never spelled out on Codex's
command line -- they ride on the subprocess's own environment, forwarded
to the MCP child by NAME via `mcp_servers.halo.env_vars`, the same privacy
property `cc:` gets from folding its bridge env into the claude
subprocess's own env.

**Steering.** `codex exec` has no live channel into an already-running
turn (no queued-stdin-line concept the way `cc:` has). A steer is
accepted immediately and queued; the moment the CURRENT subprocess exits,
it is sent as its own follow-up `codex exec resume <id> -` call (the
steer text on stdin, same as every other turn -- see above) (logged as a
`steer` node), repeating until nothing is left queued,
before the whole chain reports one `turn_done` back to Halo -- "finish
the turn, then send", literally. (A separate `codex queue --thread <id>
--message <text>` command exists and MIGHT inject into a still-running
turn from a second process -- unconfirmed without a live login, and not
wired in; see `docs/harness/CODEX-RESEARCH.md` section 7.)

**Setup.** `halo init`'s "Codex subscription" tab (same "Check login"
button as the Claude Code tab -- nothing is stored, it only confirms the
login) or run `codex login` directly; auto-enabled only on a genuine
ChatGPT login, never merely because `codex` is installed. `/providers`
and `halo doctor` show it under `codex_subscription`.

## Codex settings and instructions

Round 5i part 2 also reads Codex's OWN `config.toml` and `AGENTS.md`
chain, beside Claude Code's settings/CLAUDE.md, into one merged view --
`/settings`, `halo doctor`'s `codex_settings` line, and the init wizard's
"Settings sources" step all show the SAME thing. Halo never writes to
either Claude Code's or Codex's own files; this is read-only awareness,
not a second configuration mechanism.

**What gets read.** Codex's `config.toml` (`$CODEX_HOME`, default
`~/.codex`, plus `.codex/config.toml` at a trusted project root, layered
over the home one) for `model`/`model_provider`/`model_reasoning_effort`/
`approval_policy`/`sandbox_mode`/`mcp_servers.<name>`/`profiles.<name>`/
`shell_environment_policy`/`notify`/`history`; its `AGENTS.md` chain
(global `AGENTS.override.md` else `AGENTS.md` under `$CODEX_HOME`, then
the SAME override-or-plain rule from the git repo root down to the
working directory, concatenated root-to-leaf, capped at `project_doc_
max_bytes`, 32 KiB by default) -- a DIFFERENT walk than the one Halo
already uses for CLAUDE.md/AGENTS.md (`halo_harness/config/claude_md.py`,
a filesystem-root walk with no git-root concept), kept deliberately
separate since the two rules genuinely differ. `config.toml`'s own
`profiles.<name>` table is read when present; no persisted "default
profile" pointer was found in either the table or the installed CLI's
separate `-p/--profile` per-file scheme, so Halo never guesses which
profile (if any) is active.

**How it merges.** Each setting Halo tracks (model, permission/approval
mode, sandbox, reasoning effort) gets one row showing EVERY source's own
value plus which one is "effective". Non-overlapping entries always
merge: a Codex-only MCP server joins the MCP list labeled `(codex)`;
Codex's AGENTS.md chain is its own block, never silently folded into
Claude Code's own CLAUDE.md block. Overlapping entries follow one
precedence: Halo's own config first, then Claude Code's settings, then
Codex's -- EXCEPT on a live `cx:` session, where Codex's own model/
reasoning-effort/approval-and-sandbox policy leads for those specific
keys (it is, after all, what is actually about to run). `settings.
primary: "claude"|"codex"` (`~/.halo/config.json`, default `"claude"`)
flips which of Claude Code's or Codex's value is preferred when both are
set and Halo's own config and a live cx: session don't already decide
it -- set it from the init wizard's "Settings sources" step, `/settings
primary claude|codex`, or `halo config set settings.primary codex`.
