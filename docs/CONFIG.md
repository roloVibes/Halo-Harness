# Configuration

Read this when you want to know which file sets what: every config file, key and environment variable Halo reads.

Exactly which files this harness reads (Claude Code's own config, unchanged)
and which it owns (its own small state under `~/.halo/`), how they're
merged, every environment variable, and precisely what is never written.
Permissions/hooks *behavior* (as opposed to where their config lives) is
covered in [ARCHITECTURE.md](ARCHITECTURE.md); Databricks credential
discovery specifically is covered in [DATABRICKS.md](DATABRICKS.md).

## Which file sets what, here: `halo config where`

`halo config where` prints every file below that is in effect for the folder
you run it in, what each one sets and which file wins when two set the same
key; `halo doctor --config` checks all of them against Halo's schemas and
validators. See [COMMANDS.md](COMMANDS.md)'s last section.

## Claude Code files -- read only, never written (except where noted)

### `settings.json` precedence

Five layers, later wins, merged by `config/settings.py::resolve_settings`:

| Layer | Path | Notes |
|---|---|---|
| `policySettings` (managed) | `C:\Program Files\ClaudeCode\managed-settings.json` (Windows) / `/etc/claude-code/managed-settings.json` / `/Library/Application Support/ClaudeCode/managed-settings.json`, plus every `*.json` under a sibling `managed-settings.d/` | highest precedence, always read, never trust-gated |
| `flagSettings` | `--settings` (inline JSON or a file path) | second-highest |
| `localSettings` | `<cwd>/.claude/settings.local.json` | |
| `projectSettings` | `<cwd>/.claude/settings.json` | |
| `userSettings` | `~/.claude/settings.json` (`$CLAUDE_CONFIG_DIR` if set) | lowest precedence |

`--setting-sources` restricts which of `user`/`project`/`local` are read at
all (`policySettings`/`flagSettings` are always included). Merge rules,
applied key by key across the whole stack: most scalar keys are plain
highest-layer-wins; a **list**-valued key is concatenated across every layer
that set it and de-duplicated (order-preserving) -- *unless* the
highest-precedence layer that touched it set something else entirely
(a scalar), in which case that wins outright, never merged; `env` and
`hooks` are always accumulated (a lower layer's own hook/env entry is never
discarded by a higher layer setting more); `permissions.allow/ask/deny/
additionalDirectories` follow the same list-concatenation rule, scoped to
that one sub-object. `fallbackModel`/`modelPicker`/`availableModels`/
`modelSettings` are whole-value, highest-layer-wins, never merged field by
field.

**Trust**: an *untrusted* `project`/`local` layer has `permissions.allow`,
`permissions.additionalDirectories`, `permissions.defaultMode`, `env`, `hooks`,
`disableAllHooks`, `plansDirectory`,
`autoMemoryDirectory`, `enableAllProjectMcpServers`/`enabledMcpjsonServers`
and the command-naming keys (`statusLine`, `apiKeyHelper`,
`otelHeadersHelper`, ...) stripped before merging -- `permissions.deny`/`.ask`
always survive regardless of trust (a repo you haven't trusted yet can still
have its own denials honored, just never its own extra permissions/secrets/
hooks). Trust itself (`config/claude_json.py::is_trusted`) is true when any
of: `projects[cwd].hasTrustDialogAccepted` for `cwd` or an ancestor up to
the git root (or the filesystem root if not in a repo); `CLAUDE_CODE_SANDBOXED`
is set to any non-empty value; or `~/.halo/trust.json` has an entry
for the normalized cwd (this harness's own trust store -- written by a
future trust-prompt flow, not yet interactive).

### Permissions and hooks

The rule grammar, mode table, and hook protocol are architecture, not
config -- see `docs/ARCHITECTURE.md`'s "Permissions" and "Hooks protocol"
sections. Configuration-relevant summary: `permissions.allow`/`.ask`/`.deny`
live inside `settings.json` at every layer above; hooks live in that same
file's top-level `hooks` key at every layer (concatenated, never
overridden -- every matching hook from every layer runs); a plugin's own
`hooks/hooks.json` is a separate, additional source, with
`${CLAUDE_PLUGIN_ROOT}` substituted first (per field since 3.2.1.0 R4: a
shell `command` gets the path as its shell reads it, forward slashes on
Windows; `args` and the rest get it as it is -- docs/ARCHITECTURE-permissions.md
"Hooks protocol"). There is no separate freestanding
`hooks.json` for an ordinary user/project outside a plugin.

### CLAUDE.md / AGENTS.md / rules / memory

Discovery order (`config/claude_md.py::discover_instructions`; `bare`/
`--bare` skips this whole section): managed `CLAUDE.md` (never excluded,
always loaded) -> `~/.claude/CLAUDE.md` + `~/.claude/rules/**/*.md` -> a
root-to-leaf walk of every ancestor directory from the filesystem root down
to `cwd` (root itself excluded), at each one: `CLAUDE.md` and/or
`.claude/CLAUDE.md`, then `AGENTS.md`/`.claude/AGENTS.md` if
`instructionFiles` calls for it (see below), then that ancestor's own
`.claude/rules/**/*.md`, then `CLAUDE.local.md`. A `.claude/rules/*.md` file
with a `paths:` frontmatter glob is **scoped** -- held back and only
injected the first time a matching file is Read/Edited/Globbed this
session, rather than loaded unconditionally at launch like an ordinary
`CLAUDE.md`. `@path`/`@~/path`/`@//abs/path` imports inside any of these
files are expanded recursively (max 4 hops, 4 MiB per file, cycle-safe); an
import outside `cwd`/`~/.claude` from an **untrusted** project is skipped
with a warning, never silently included.

`settings.instructionFiles` (really
`pluginConfigs.<the agents-md plugin>.options.instructionFiles`, with a
legacy top-level `projectInstructions` mapping onto the same four values)
picks the `CLAUDE.md`/`AGENTS.md` policy per ancestor: `managed-only`
(nothing below the managed tier), `claude-md` (never read `AGENTS.md`),
`claude-md-or-agents-md` (the default -- `AGENTS.md` only where no
`CLAUDE.md` was found at that ancestor), or `claude-md-and-agents-md`
(both, always). `claudeMdExcludes` (a glob list) removes specific files from
this whole walk regardless of policy.

**Memory** (`config/memory.py`): the directory is
`~/.claude/projects/<slug-of-the-git-root-or-cwd>/memory/`, unless
`settings.autoMemoryDirectory` overrides it (that key is **never** honored
from an untrusted, or any, `projectSettings` layer -- policy/flag/local/user
only). `MEMORY.md` there is the index (capped at 200 lines / 25,000 bytes
when injected into a session, truncated with a marker beyond that); every
sibling `*.md` is a topic file, indexed by its own frontmatter
`name`/`description`/`type`/`modified` (checked at the top level first, a
nested `metadata:` block overriding per-key if present). `autoMemoryEnabled`
(default true) and `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` both disable it
entirely.

### Skills, custom commands, agents

- **Skills**: `~/.claude/skills/`, `.claude/skills/`, one `SKILL.md` per
  directory. `disable-model-invocation: true` hides a skill from the
  model's own Skill *tool* only -- a user can still always type `/name`.
- **Custom commands**: `~/.claude/commands/`, `.claude/commands/`, one
  `.md` file per command. See `docs/SLASH-COMMANDS.md` for the shared
  `$ARGUMENTS`/`` !`cmd` ``/`@path` body-expansion pipeline both of these
  (and skills) go through.
- **Agents** (`config/agents_md.py::discover_agents`), nearest-wins within
  each tier, later tier overrides an earlier one by `name`: three built-ins
  (`general-purpose`, `Explore`, `Plan`) -> `~/.claude/agents/**/*.md` ->
  every `.claude/agents/**/*.md` walking from `cwd` up to the git root
  (nearest directory wins) -> `--agents` (inline JSON or a file) -> plugin
  `agents/**/*.md` -> managed `agents/**/*.md` (highest). Frontmatter
  `tools:`/`disallowedTools:`/`skills:` accept a comma string or a YAML
  list; `model:` resolves invocation override -> frontmatter -> env
  `CLAUDE_CODE_SUBAGENT_MODEL`/`settings.subagentModel` -> the parent
  session's own model (`haiku` maps to the parent's *small* model
  specifically); a bare `Agent`/`Task` tools entry (or `Agent(name)`/
  `Task(name)`) restricts which `subagent_type`s that agent may itself
  invoke.

### Plans, keybindings, `~/.claude.json`, `.mcp.json`, plugins

- **Plans**: `~/.claude/plans/` by default, or `settings.plansDirectory`.
- **Keybindings**: `~/.claude/keybindings.json`, merged additively onto the
  built-in defaults (see `docs/SLASH-COMMANDS.md`).
- **`~/.claude.json`**: trust dialog state (`projects[cwd].
  hasTrustDialogAccepted`), user-scope `mcpServers`, and
  `projects[cwd].mcpServers` (local-scope MCP servers) -- read on every
  session; **written only by `halo mcp add`/`add-json`/`remove`**
  (see `docs/COMMANDS.md`), which preserve the file's own existing indent
  width, trailing newline, BOM, and every key they don't touch, exactly
  matching what the real `claude mcp add`/`remove` would do. No other code
  path in this harness ever writes this file.
- **`.mcp.json`** (project-scope MCP servers): read from `<cwd>/.mcp.json`;
  a server there needs first-time approval (`enabledMcpjsonServers`/
  `enableAllProjectMcpServers` in `~/.claude.json` or user settings, or a
  print-mode run in a trusted folder, or a prior approval recorded in
  `~/.halo/mcp-approvals.json`, which holds for that exact entry in that
  one folder only) before it's ever started. A repo's own
  settings cannot approve its servers, and `-p` in an untrusted folder does
  not auto-approve them. Server names cannot contain `__` (it separates the
  server and tool in `mcp__<server>__<tool>`); such an entry shows as
  invalid. `${VAR}` in an entry expands from the environment minus the
  harness's own provider keys.
- **Plugins**: `~/.claude/plugins/installed_plugins.json` (both the V1
  single-dict and the real V2 per-scope-array manifest shapes), each
  enabled plugin's own `.mcp.json`/`.claude-plugin/plugin.json` (MCP
  servers) and `hooks/hooks.json` (hooks), with `${CLAUDE_PLUGIN_ROOT}`
  expanded to that plugin's own install directory.

## halo's own files

None of these are read by Claude Code; nothing here is ever confused with
the files above.

| Path | Holds |
|---|---|
| `~/.halo/config.json` | this harness's own settings -- see the key table below |
| `~/.config/halo/env` (`HALO_ENV_FILE`/legacy `BRIDGE_ENV_FILE` to override) | `OPENROUTER_API_KEY`/`DATABRICKS_HOST`/`DATABRICKS_TOKEN` etc., `KEY=value` lines, `#` comments, optional `export`; written mode 0600, dir 0700 (POSIX) by `halo init`. The PRE-2.0.0 location, `~/.config/vibes-hacker/env`, was read as a fallback through 2.0.4 (announced in the [2.0.1] CHANGELOG, WARNed by `halo doctor` since [2.0.2]) -- as of 2.0.5 round 3 it is no longer read at all; `halo init` still copies it forward into this file (with an import marker, one time) the first time it writes here, so nothing already configured there is lost, and the legacy file itself is never modified or deleted (other tools on the same box may still read it). |
| `~/.halo/learned-rules.json` | per-endpoint learned facts, keyed `"<provider>:<model>"`: `tools_rejected` (24h TTL), `reasoning_effort_with_tools`, `ignored_params` (the `xp:` gateway's disclosed-ignored-parameters header), `mcp_fix`, and `params` (Halo 2.0.5: `{"<field>": {"action": "drop"\|"clamp", "value", "error", "date"}}`, one entry per request field a live 400/422 proved this endpoint rejects -- 30-day TTL; `halo rules`/`/rules` lists these, `halo rules --forget <endpoint>`/`halo models refresh --forget-rules` clear them; see `docs/COMMANDS.md`) |
| `~/.halo/sessions/<project-slug>/<id>.jsonl` | one append-only session log per session (see `docs/ARCHITECTURE.md`) |
| `~/.halo/sessions/<project-slug>/index.json` | per-session title/first-prompt/turns/cost, for `/resume`'s picker and `-r <text>` |
| `~/.halo/models.json`, `dbx-endpoints.json`, `models-dev.json`, `ant-models.json` | cached model catalogs (`docs/MODELS.md`) |
| `~/.halo/ollama-capabilities.json` | the `ol:` capability probe's durable cache, keyed by model digest (`docs/MODELS.md`'s "Ollama" section) -- the `/api/tags`+`/api/show` catalog itself is cached in memory only, short TTL, never written to disk |
| `~/.halo/stats-cache.json` | telemetry aggregation cache, keyed by (path, size, mtime) |
| `~/.halo/mcp/tools-cache/<server>.json`, `~/.halo/mcp/<server>.log` | a lazy MCP server's cached tool list, and its stderr |
| `~/.halo/mcp-approvals.json` | remembered `.mcp.json` server approvals |
| `~/.halo/mcp/connectors.json` | cached claude.ai connectors (name/url/status/tools) discovered through `claude mcp list` -- see `docs/COMMANDS.md`'s "claude.ai connectors bridge" section |
| `~/.halo/mcp/oauth/<server-name>.json` | `halo mcp login`'s own OAuth tokens for one remote (http/sse) MCP server -- never written to any Claude Code file |
| `~/.halo/trust.json` | this harness's own trust-dialog store |
| `~/.halo/history.jsonl` | this harness's own prompt history (merged with Claude Code's own `~/.claude/history.jsonl` at read time, never written to) |
| `~/.halo/improve/dismissed.json`, `~/.halo/improve/<ts>.json` | `/improve` dismissed-candidate hashes, and saved candidate batches |
| `~/.halo/work-matrix-<date>.json` | `doctor --work --probe-all` reports (endpoint names only, never a host or token) |
| `~/.halo/sessions/<slug>/<id>/shadow/`, `shadow-index.jsonl` | `/rewind`'s git-shadow snapshots |
| `<state_dir>/routes.json` | optional, proxy-era per-box defaults (`aliases`, `default`/`small` model, per-model `profiles`) -- still read by the harness's own default-model resolution chain; see `routes.example.json` |
| `.halo/team.json` (project) or `~/.halo/team.json` | shared Databricks team preset -- see `docs/DATABRICKS.md` |
| `~/.halo/agents/<name>.yaml` (`.halo/agents/<name>.yaml` project) | an agent BIO -- models/tools/context/limits/output/environment/acceptance for one named agent; see [AGENTS.md](AGENTS.md) |
| `~/.halo/teams/<name>.yaml` (`.halo/teams/<name>.yaml` project) | a TEAM TEMPLATE ("lineup") -- assigns agent bios to roles/positions; `team` (below) names the active one; see [AGENTS.md](AGENTS.md) |
| `~/.halo/packs/<id>/` (`.halo/packs/<id>/` project) | an installed PACK, read in place and never written by Halo: `pack.yaml` plus a Claude-plugin layout and its bios (`agents/*.yaml`, listed as `<id>--<name>`) and lineups (`teams/*.yaml`); see [PACKS.md](PACKS.md) |
| `~/.halo/packs/state.json`, `~/.halo/packs/journal.jsonl` | which packs are installed, from where, enabled and granted (0600); every file a pack's install, update or remove wrote or deleted, with its hash -- see [EXTENSION_API.md](EXTENSION_API.md) |
| `~/.halo/packs/.data/<id>/` | a pack's own place to write (`halo_harness.ext.write_private`) |
| `<state_dir>/agents-schedules.json` | what schedule/trigger set is ARMED right now (written by live sessions' team schedulers; `halo agents schedule list` reads it) -- see [AGENTS.md](AGENTS.md) |

### `~/.halo/config.json` keys

Read/written with `halo config get/set` (dotted paths supported),
directly by the features that own them, or in Studio's Settings section
(Halo 3.3.3.0, `Alt+9`, `halo settings [group]`): every key below is a row
there, on the page the Studio column names, with its help line, its value
against its default, Reset to default and the exact `halo config set` line.
The rows come from one catalog (`halo_harness/settings_catalog.py`), and
`tests/test_settings_catalog.py` holds the catalog, the config schema and
this table to the same keys, so a new key lands in all three:

| Key | Default | Set by | Studio |
|---|---|---|---|
| `model` | unset (built-in default applies) | `halo init`, `halo config set model ...` | Settings -> General |
| `team` | unset: the `auto` lineup runs (Halo 3.1.9.0; with `roles.enabled: false`, no lineup) | `halo teams use <name>` / `halo config set team <name>` / Studio Roles -> Apply -- names the ACTIVE lineup; a session running under it enforces its sections through `teams_runtime.py` (Halo 2.0.5 round 5; `--team <name>` overrides per-run, never persisted). Unset, a session runs the shipped `auto` lineup: main on your model, a pool whose models are picked at spawn for each task ([ROLES.md](ROLES.md#the-auto-lineup-halo-3190)); the session's own role table (your `roles.*`, or the Databricks cost-aware defaults) and `agents.max_depth` / `agents.max_concurrent` still win over it. Nothing writes `team: auto` for you, and a `team:` you set is never changed; see [AGENTS.md](AGENTS.md) | Settings -> General |
| `agents.max_concurrent` | `4` | hand-edited; how many sub-agents may run at the same time | Settings -> Agents and roles |
| `agents.max_depth` | `1` | hand-edited; how deep sub-agents may spawn sub-agents of their own (1 to 3) | Settings -> Agents and roles |
| `roles.enabled` | `true` | `halo init`'s Team step, Studio's Setup (One model for everything sets it `false`); `false` runs one model for everything, no role routing | Settings -> Agents and roles |
| `roles.editor` | unset (the form) | `halo config set roles.editor external` makes `/roles edit` open your `$EDITOR` instead of the form | Settings -> Agents and roles |
| `roles.<role>` | unset (the lineup's, else the built-in role table) | `/roles set`, `halo roles set`, Studio Roles; the model one role runs on (a model ref, or `{model, effort}`) -- see [ROLES.md](ROLES.md) | Settings -> Agents and roles |
| `theme` | auto-detected from terminal truecolor support | `/theme`, the wizard's Theme step, `halo config set theme ...` (six names: `claude-dark`, `claude-light`, each with `-daltonized`/`-ansi`). A game theme left here from before 3.1.5.0 (`doom`, `metroid`, `mario`, `beetlejuice`, `alien`) falls back to the default with one line at startup and in `halo doctor --config` | Settings -> General |
| `images` | `"inline"` | `--no-inline-images` overrides per-run | Settings -> General |
| `intro` | `true` | `--no-intro` overrides per-run; set `false` to turn off the launch intro for good | Settings -> General |
| `tips` | `true` | `halo config set tips false` turns the rotating tips in the input line off (`/tips` still lists them) | Settings -> General |
| `permission_mode` | unset (Claude Code's own settings chain, else `default`) | `halo init`'s Permissions step, Studio's Setup, `halo config set permission_mode auto`; one of `auto`, `acceptEdits`, `default`, `plan` -- the mode every new session starts in (`--permission-mode` overrides it per run) | Settings -> General |
| `effort` | unset (the last-used effort, else the settings chain) | `halo config set effort high`; the reasoning effort a session starts with when no `--effort` flag and no last-used effort says otherwise (`low`, `medium`, `high`, `xhigh`, `max`) | Settings -> General |
| `model_memory` | `cwd` | `halo config set model_memory global`; whether `/model`'s last-used model and effort are remembered per folder (`cwd`) or once for every folder (`global`) | Settings -> General |
| `mcpPreload` | unset | hand-edited: a list of wire tool names to preload regardless of the catalog's own `alwaysLoad` rule | Settings -> General |
| `compactionModel` | unset (uses the session model) | hand-edited; its summary calls are billed at its own rates | Settings -> General |
| `databricks.gateway.<endpoint>` | unset | `halo init --provider databricks` (from a team.json `gateway_preference`), or hand-edited | Settings -> Providers |
| `databricks.dbu_price_usd` | `0.07` (USD per DBU: Databricks' AWS US East example price, read 2026-10-27; every cost Halo shows is in dollars) | team.json, `halo config set databricks.dbu_price_usd 0.0x`, or hand-edited | Settings -> Providers |
| `databricks.prices.<endpoint>` | unset (Databricks' published pay-per-token rate times `databricks.dbu_price_usd`, else unpriced and the total carries a `+`) | hand-edited: `{"in": 3.0, "out": 15.0}` USD per 1M tokens (`cache_read` / `cache_write` optional) | Settings -> Providers |
| `databricks.catalog_max_age_hours` | `24` | hand-edited | Settings -> Providers |
| `improve.enabled` | `true` | hand-edited | Settings -> Coach and improve |
| `improve.hint` | `true` | hand-edited | Settings -> Coach and improve |
| `improve.model` | unset (small model, then session model) | `halo config set improve.model or:...` | Settings -> Coach and improve |
| `improve.since_days` | `7` | hand-edited | Settings -> Coach and improve |
| `improve.max_candidates` | `8` (hard-capped at 8) | hand-edited | Settings -> Coach and improve |
| `improve.hint_threshold.repairs` | `3` | hand-edited; repairs in a session before the improve hint shows | Settings -> Coach and improve |
| `improve.hint_threshold.edit_failures` | `2` | hand-edited; failed edits in a session before the improve hint shows | Settings -> Coach and improve |
| `improve.hint_threshold.loop_breaker` | `1` | hand-edited; loop-breaker stops in a session before the improve hint shows | Settings -> Coach and improve |
| `connectors.bridge` | `true` | `halo config set connectors.bridge false` disables claude.ai connector discovery and every `connector__<slug>` tool outright | Settings -> Connectors |
| `connectors.<slug>.enabled` | `true` | hand-edited; `false` removes just that one connector's tool | Settings -> Connectors |
| `connectors.<slug>.alwaysLoad` | `false` | hand-edited; preloads that connector's tool instead of leaving it to ToolSearch | Settings -> Connectors |
| `connectors.<slug>.max_turns` | `4` | hand-edited; forwarded as the bridge's own `claude -p --max-turns` | Settings -> Connectors |
| `connectors.discover_on_start` | `false` | `halo config set connectors.discover_on_start true`; print mode (`-p`) normally never blocks a run on a cold-cache connector discovery -- this opts every run in (the TUI always discovers in the background regardless; `--tools` naming a `connector__<slug>` tool, or a `ToolSearch` call mentioning "connector", also triggers it for just that run) | Settings -> Connectors |
| `providers.<name>.enabled` | unset (a provider whose credentials are found is on) | `halo providers enable/disable`, `halo init`, Studio's Setup; an explicit `true` or `false` always wins over detection | Settings -> Providers |
| `quit_on_double_ctrl_c` | `true` | `halo config set quit_on_double_ctrl_c false` turns off the "Quit Halo?" card the second Ctrl+C (within 3 s) opens -- every Ctrl+C press then just copies (`/exit`/`Ctrl+D`/`Ctrl+Q` still leave) | Settings -> General |
| `clipboard.crlf` | `false` | hand-edited; `true` makes a copy use `\r\n` line endings instead of `\n` | Settings -> General |
| `coach.probe.k` | `1` | Halo 3.1.6.0: how many pairs of candidate overlays `halo coach <run> --probe` (and Studio's Probe) drafts and runs when `--k` is not given (2 runs a pair, at most 4 pairs); see [ORCHESTRA.md](ORCHESTRA.md#probes) | Settings -> Coach and improve |
| `coach.probe.budget_factor` | `1.5` | Halo 3.1.6.0: each probe run may spend the reference run's `cost_usd` times this; a lane whose forecast would pass it does not start and the probe stops with `stop_reason: budget` | Settings -> Coach and improve |
| `coach.library.cite` | `true` | Halo 3.1.6.0: the coach cites its improvement library -- the entries earlier Applies left for runs like this one (the line under the card's head, `[lib e-...]` on a matching card, the probe draft's "What earlier runs like this learned"); `false` turns every citation off and keeps the entries; see [ORCHESTRA.md](ORCHESTRA.md#the-library) | Settings -> Coach and improve |
| `knowledge.write` | `true` | Halo 3.1.8.0 R4: the Orchestra judge and gate, the coach's Apply and the supervisor's answered decisions write findings and decisions to `~/.halo/knowledge/`; `false` turns every one of those writers off (the entries already there stay; `halo knowledge add` and the agents' `knowledge_add` still write); see [KNOWLEDGE.md](KNOWLEDGE.md) | Settings -> Knowledge and recall |
| `knowledge.brief` | `true` | Halo 3.1.8.0 R4: an Orchestra worker's brief carries up to three findings and decisions recall ranks for its job (only with embeddings configured and the store holding one), ending with the line that asks it to cite the id of any it reuses; `false` leaves the block out | Settings -> Knowledge and recall |
| `recall.sources` | `[]` | Halo 3.1.8.0 R4: folders of your own Markdown notes recall reads in place (an Obsidian vault is one): `halo config set recall.sources '["~/vault"]'` (one folder as a string works too; `~` is your home); every `.md` file under them is indexed as kind `note` and never written, `.obsidian/` and every other dot-folder skipped; `halo recall sources` lists them with their note counts; see [RECALL.md](RECALL.md#your-own-notes) | Settings -> Knowledge and recall |
| `models.roster` | `true` | Halo 3.1.9.0: the main session reads the model roster -- what each model in the catalog is good at, the strongest and the cheapest per kind, at most 40 lines -- as a user-role snapshot at its start, after `/clear` and after a compaction, and the Agent tool's description says so; `false` appends nothing (the system prompt never carries it either way). `HALO_MODELS_ROSTER=0`/`1` overrides it for one run. See [MODELS-references.md](MODELS-references.md#the-roster) | Settings -> Models |
| `models.learn` | `true` | Halo 3.1.9.0 R3: the `auto` pick weighs what was measured for the task's kind (a weight of 0.5 + 0.5 x the first-time success rate on each candidate's score) and the roster drops a model that keeps failing a kind, naming it with its numbers; `halo config set models.learn false` turns both off (the pick of 3.1.9.0 R2). It may also be an object holding the knobs below (`enabled: false` turns it off then); setting a knob while it is `false` makes it an object, which is on again. See [ROLES.md](ROLES.md#auto-learns-halo-3190) | Settings -> Models |
| `models.learn.min_tasks` | `3` | Halo 3.1.9.0 R3: how many checked tasks of a kind a model needs before its rate weighs the pick or drops it | Settings -> Models |
| `models.learn.window_days` | `30` | Halo 3.1.9.0 R3: only outcome rows of the last N days count; `0` counts every row | Settings -> Models |
| `models.learn.drop_below` | `0.34` | Halo 3.1.9.0 R3: a model whose rate for a kind is below this (over `min_tasks` or more tasks) is dropped for the kind in the roster, `halo models --measured` / `analyze` and Studio's picker; `0` drops nothing | Settings -> Models |
| `worktree.remove_on_exit` | `false` | `halo config set worktree.remove_on_exit true`; a `-w/--worktree` session removes its OWN worktree (fires `WorktreeRemoved`) when it ends instead of leaving it on disk | Settings -> Worktree |
| `steer.restart_when_silent` | `true` | a steer typed while a model call has sent nothing yet aborts that call and resends it with the steer (`false`: the steer waits for the stream's next chunk); see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Settings -> Steer and turn |
| `steer.silent_restart_s` | `60` | Halo 3.2.2.0 R4: a model call with no first token after this many seconds is aborted and resent once with the same messages (the transcript says `↳ no data for 60 s, resending the call`); the second try waits the provider's read timeout. `0` turns it off; a stream that has started is never cut. See [HANDBOOK.md](HANDBOOK.md#how-a-turn-ends) | Settings -> Steer and turn |
| `turn.nudge_promises` | `true` | Halo 3.2.2.0 R4: a reply that ends promising work ("Now I'll ...", "Let me ...") and calls no tool gets one notice, "You ended your turn while saying you would do more. Continue.", and one more model call (`↳ nudged: the reply promised work and stopped`); once per turn, never when the reply asks you something; `false` turns it off | Settings -> Steer and turn |
| `fleet.enabled` | `true` | Halo 3.0.5.0: every session (the TUI, `halo -p` and `--bg`, Orchestra workers, mission workers) opens a local control socket and lists itself in `~/.halo/run/sessions.json`, so Studio, `halo remote` and the Signal bridge can see and drive it (see [REMOTE.md](REMOTE.md), [FLEET.md](FLEET.md)); `halo config set fleet.enabled false` turns that off for sessions started afterwards; `/remote` shows whether this session's socket is on | Settings -> Fleet |
| `fleet.name` | `user@host` | this harness's name in the registry (`harness.name`) and the `by` on every command Studio and `halo remote` send | Settings -> Fleet |
| `fleet.private` | `false` | every session starts private (as with `halo --private`): no control socket, no registry entry; `/private off` lists one again | Settings -> Fleet |
| `fleet.share` | `events` | Halo 3.0.5.0 R2: what this harness sends a hub it joined: `status` (session rows and agent trees, no text), `events` (every feed frame but the text and thinking streams), `full` (everything, and the hub may read an agent's tail or follow it); a hub entry in `~/.halo/fleet.json` may carry its own (`halo fleet join --share`) (see [FLEET.md](FLEET.md)); the Ollama ledger's lines have their own switch, `fleet.ollama.share` | Settings -> Fleet |
| `fleet.allow_control` | `ask` | what a hub may do to this harness's sessions: `none` (refused, with the reason), `ask` (a card in the owner's TUI for each command; print-mode sessions deny), `all` (applied, recorded with who sent it); `halo fleet join --allow-control` sets one hub's own | Settings -> Fleet |
| `fleet.allow_answers` | `false` | with `fleet.allow_control: all`, a hub may also answer this harness's permission, question, plan and approval cards (once only: a hub never learns a rule) | Settings -> Fleet |
| `fleet.hub.port` | `7430` | the LAN port `halo fleet serve` and `halo studio --fleet` listen on (`--port` overrides it) | Settings -> Fleet |
| `fleet.caps.per_harness_usd_per_day` | unset | Halo 3.0.5.0 R4, read on the hub: when one harness's sessions started today have spent this many dollars, the hub pauses that harness's live sessions (the `pause` command with reason `cap`: every agent holds at its next tool boundary) and raises a `cap` row in Studio's Fleet attention queue; answering it resumes them for the rest of the day. `0` or unset: no cap. Studio's Costs panel sets it (`POST /api/fleet/caps`) (see [FLEET.md](FLEET.md#caps)) | Settings -> Fleet |
| `fleet.caps.per_project_usd_per_day` | unset | the same for every session on one repo (by its repo name), on any harness | Settings -> Fleet |
| `fleet.caps.fleet_usd_per_day` | unset | the same for every session the hub sees | Settings -> Fleet |
| `fleet.attention.signal` | `true` | when the Signal bridge is enabled, running and paired, each new row of the Fleet attention queue (any harness's permission, question, plan or approval card, a fleet ask, a waiting agent, a cap, a conflict) goes to the phone as the bridge's own card, prefixed with the harness name; `false` keeps the queue in Studio only (see [REMOTE.md](REMOTE.md#the-signal-bridge)) | Settings -> Fleet |
| `fleet.tags` | `[]` | Halo 3.0.6.0 R6: `halo config set fleet.tags '["gpu", "studio"]'`; your own words for this harness in its capability catalog: they show first on its chips on the Fleet map, in People and on its spec card, and a match on one counts double in `halo fleet who` and Studio's Who can... (see [FLEET.md](FLEET.md#capabilities-3060-r6)) | Settings -> Fleet |
| `fleet.capabilities.hide` | `[]` | names its capability catalog never lists, so no hub ever sees them: an MCP server (and every tool of it), one tool (`write_range` or `gridcraft/write_range`), a skill, a craft app or (3.2.1.0 R3) a pack's fleet capability (`docs.review`, or `doc-review/docs.review` for one pack's: no mission is planned onto it here, and `halo pack doctor` counts it); `halo config set fleet.capabilities.hide '["private-notes"]'` (see [FLEET.md](FLEET.md#what-never-leaves-the-machine)) | Settings -> Fleet |
| `fleet.ollama.share` | `auto` | Halo 3.3.4.0 R2: what of this machine's Ollama ledger a joined hub receives (one signed `POST /fleet/v1/ollama` every 30 s or 50 lines), stored in the hub's own ledger with `from` set to this harness's name: `auto`, the calls to a host this machine does not serve itself (a host url that is not a loopback name or one of this machine's own addresses: the Mac's calls to the PC reach the PC's hub, the Mac's calls to its own local server stay on the Mac); `all`, every line (`true` is read the same); `off`, none (`false` too: the lines recorded while it is off are never sent later) (see [MODELS-ollama-steward.md](MODELS-ollama-steward.md)) | Settings -> Fleet |
| `fleet.recall.share` | `true` | 3.1.2.0 R3: `false` keeps this box out of recall across the fleet (`halo recall --fleet`) -- it answers no recall query ([FLEET.md](FLEET.md)) | Settings -> Fleet |
| `fleet.recall.hide` | `[]` | 3.1.2.0 R3: memory kinds its recall never answers (same shape as `fleet.capabilities.hide`): `session`, `memory`, `coach_library` (3.1.6.0: the coach's library entries, and `halo coach library fetch` of them), `finding`, `decision` (3.1.8.0 R4; `knowledge` both, and `halo knowledge fetch` of them), or a memory topic's own `type`; your own notes (`recall.sources`) never leave the box | Settings -> Fleet |
| `fleet.shared_dir` | unset | Halo 3.0.6.0 R7: a folder every machine of the fleet sees (an SMB or NFS mount, set on each machine to its own path for it): fleet missions live there (`<shared_dir>/<id>/`) instead of `~/.halo/fleet/missions/`, and nothing is mirrored over the fleet protocol (see [MISSIONS.md](MISSIONS.md#the-shared-folder)) | Settings -> Fleet |
| `fleet.mission.prefer` | `[]` | read on the hub: harness names, in order (`halo config set fleet.mission.prefer '["win@studio", "kali@lab"]'`), that break a tie when several harnesses meet a mission part's needs; `halo fleet mission new --prefer` overrides it for one mission | Settings -> Fleet |
| `fleet.mission.max_parallel` | the number of harnesses | how many parts of one mission run at once | Settings -> Fleet |
| `fleet.mission.max_file_mb` | `25` | the largest file a mission folder takes or gives over the fleet protocol (`mission_files`); a bigger one is refused (413) | Settings -> Fleet |
| `remote.enabled` | `false` | the Signal bridge's switch: `halo remote signal run` starts only with it on (`halo config set remote.enabled true`). Before 3.0.5.0 it also opened the control sockets; that is `fleet.enabled` now | Settings -> Remote |
| `remote.signal.enabled` | `false` | whether the Signal bridge may run: `halo remote signal setup` and `halo remote signal on` set it to `true`; `halo remote signal off` and `/remote` Off set it to `false` (and stop a running bridge); `halo remote signal run` does nothing while it is `false` (see [REMOTE.md](REMOTE.md), "Running the bridge") | Settings -> Remote |
| `remote.rate_per_minute` | `30` | the Signal bridge: commands per minute per paired phone; over it commands are dropped and the phone is told once (see [REMOTE.md](REMOTE.md), "How pairing works") | Settings -> Remote |
| `remote.verbosity` | `loud` | the Signal bridge: `loud` relays the session's text as well as cards and errors, `quiet` only cards, errors and the closing line; `/quiet` and `/loud` change it per phone | Settings -> Remote |
| `remote.stale_window_s` | `300` | the Signal bridge: a signed command whose message timestamp is further than this many seconds from the computer's clock is refused (see "Signing") | Settings -> Remote |
| `remote.pair_code_ttl_s` | `600` | the Signal bridge: seconds the one-time pairing code stays valid | Settings -> Remote |
| `supervise.tick_s` | `5` | Halo 3.1.8.0: seconds between two ticks of the supervisor (`halo supervise`, [SUPERVISE.md](SUPERVISE.md)) | Settings -> Supervise |
| `supervise.max_running` | `1` | how many goals the supervisor runs at once | Settings -> Supervise |
| `supervise.replan` | `none` | what the supervisor does with a run that drifts (3.1.8.0 R2, [SUPERVISE.md](SUPERVISE.md#replanning)): `none` stops only; `auto` asks the lead for a new plan for the lanes left and applies it; `review` parks it as a `goal plan` row (a goal with `plan: review` always reviews); `halo goal add --replan` sets it for one goal | Settings -> Supervise |
| `supervise.replan_forecast` | `1.25` | forecast drift: the live spend plus the lanes left at their forecast pass the goal's (or the queue's) cap times this | Settings -> Supervise |
| `supervise.replan_returns` | `2` | returns drift: a lane sent back this many times (by the gate or a failed merge) | Settings -> Supervise |
| `supervise.replan_block_s` | `600` | blocked drift: seconds a lane waited on a hand-off or a refused claim | Settings -> Supervise |
| `supervise.replan_stall_s` | `900` | stalled drift: seconds a writing lane logged no event | Settings -> Supervise |
| `supervise.replan_cooldown_s` | `300` | seconds after a goal's last replan before it may replan again | Settings -> Supervise |
| `supervise.replan_max` | `2` | replans per goal; past it a drift is left to the stops (`goal budget`, `goal gate`) | Settings -> Supervise |
| `supervise.asks` | `park` | a supervised `job` goal's permission card or question: `park` waits in Attention (at most `tick_s * 720`), `deny` denies it at once as any `halo -p` run | Settings -> Supervise |
| `supervise.budget_usd` | unset | the whole queue's spend cap -- every goal's spend together; a lane that would pass it does not start and the goal parks ([SUPERVISE.md](SUPERVISE.md#budgets-are-stops)) | Settings -> Supervise |
| `supervise.retries` | `1` | how many times a goal whose run stopped on a crash or a failed worker is retried from its checkpoint before it parks with `why: retries` | Settings -> Supervise |
| `supervise.max_minutes` | `0` | a goal's time limit (`0` = none); past it the run gets `request_stop` and the goal parks with `why: time` | Settings -> Supervise |
| `update.check` | `true` | `halo config set update.check false` turns off `halo update`/`/update`'s own check entirely (never shells out, never touches the network) | Settings -> Update |
| `update.notify` | `true` | `halo config set update.notify false` turns off just the once-a-day "update available" startup note (the check itself, and `/update`'s own dialog, still work) | Settings -> Update |
| `update.channel` | unset (derived from the install: `stable` when pinned to a `v*` tag, else `main`) | `halo update --channel stable\|main` | Settings -> Update |
| `ollama.hosts` | unset (synthesizes one default host from `OLLAMA_HOST`/`127.0.0.1:11434`) | hand-edited, or `halo init`'s Ollama tab; a list of `{name, url, default, keep_alive, max_ctx, num_parallel_hint, api_key_env, kv_cache_type, ssh, offline_ok, dialect}` -- `ol:<model>@<hostname>` selects an entry by `name`; a saved key lives in the shared env file under the name `api_key_env` points at (never plaintext here -- an older `api_key` value still works and is migrated to `api_key_env` the next time that entry is saved); `offline_ok: true` marks a host that is not otherwise recognized as local (see `network.offline` below) explicitly local anyway; `"dialect": "openai"` marks the entry an OpenAI-dialect host (a gateway in front of Ollama serving only `/v1/chat/completions` + `/v1/models` -- the `ol:` route then rides the openai-chat machinery with the entry's own `url` + `api_key`, and enumeration reads `/v1/models`; an unrecognized value falls back to native with a `halo doctor` WARN), see `docs/LOCAL-MODELS.md`'s "OpenAI-dialect hosts" section; see `docs/MODELS.md`'s "Ollama" section | Settings -> Ollama |
| `ollama.tools_max` | unset (derived from the effective `num_ctx`'s context class -- under 16k: 16, 16k-32k: 32, 32k-64k: 64, 64k+: 128) | `halo config set ollama.tools_max 64`; overrides the `ol:` ProviderProfile's tool-catalog cap outright, still never below however many built-in tools this platform ships -- see `docs/MODELS.md`'s "Ollama" section | Settings -> Ollama |
| `ollama.auto_calibrate` | `true` | `halo config set ollama.auto_calibrate false`; opts out of running `halo ollama calibrate`'s own stepping procedure automatically the first time a model is used on a host with no learned cap -- see `docs/MODELS.md`'s "Fit calibration" section | Settings -> Ollama |
| `ollama.ledger` | `true` | Halo 3.3.4.0 R2: `halo config set ollama.ledger false`; every call to a local model server (an `ol:` host that is not Ollama's own cloud, an `hf:local` / `hf:mlx` server) appends one JSON line to `~/.halo/ollama/traffic.jsonl` (rotated to `traffic.1.jsonl` at 20 MB): the host, the model, the window sent and its source, the estimate, the counts, `done_reason`, the durations and the eval rate, trimmed, the status or error, the retry, the session and turn; `false` writes none. `halo ollama traffic` prints the rollups (see [MODELS-ollama-steward.md](MODELS-ollama-steward.md)) | Settings -> Ollama |
| `ollama.profiles` | unset (no profile: the window follows the estimate, the reply room and keep_alive the defaults) | Halo 3.3.4.0 R3: written by the steward (`halo ollama steward run` / `apply <id>`, reverted by `undo`), or by hand; a map of `"<host>\|<model>"` (the host's name on this machine) to `{num_ctx, num_predict, keep_alive, tools_max, host_for, compact_at, note, by, at}`, read before every call to that model: `num_ctx` is the window sent (it wins over the memory estimate, never over the learned cap in `~/.halo/ollama-fit.json` or the host's `max_ctx`), `num_predict` the least room the reply keeps (the prompt compacts first), `keep_alive` and `tools_max` over the host's, `host_for` asks the model on that host instead, `compact_at` (0.3-0.95, default 0.8) compacts before a call whose prompt passes that share of the window; a hub hands its profiles to its members with `by: "hub"`, never over a member's own `by: "user"` entry (see [MODELS-ollama-steward.md](MODELS-ollama-steward.md)) | Settings -> Ollama |
| `ollama.steward.apply` | `auto` | Halo 3.3.4.0 R3: what `halo ollama steward run` does with a finding's profile change: `auto` applies it and says one line (and a session's next call to that model shows the profile's note), `review` writes it down as a proposal for `halo ollama steward apply <id>`, `off` only reports the findings; every change is one line in `~/.halo/ollama/steward.jsonl`, at most one per host and model per ten minutes, never above a measured cap, and rolled back on its own when the next 10 calls go worse; server-side changes are only ever shown | Settings -> Ollama |
| `ollama.steward.slow_tok_s` | unset (by model size: up to 8B 15, 16B 10, 40B 6, larger 3 tokens per second) | Halo 3.3.4.0 R3: `halo config set ollama.steward.slow_tok_s 5`; the eval rate (p50) under which the steward calls a host a slow box for a model, one number for every size | Settings -> Ollama |
| `ollama.hosts[].kv_cache_type` | unset (`f16`, the conservative default -- never under-estimates memory) | per-host-entry field in `ollama.hosts` (not its own top-level key); `"q8_0"`/`"q4_0"` when that host's own `OLLAMA_KV_CACHE_TYPE` server flag is set to match -- a HINT Halo cannot read back on its own, see `docs/MODELS.md`'s "KV cache type per host" | Settings -> Ollama |
| `ollama.hosts[].ssh` | unset (no ssh GPU read; the fit estimate relies on calibration/`/api/ps` alone) | per-host-entry field, e.g. `"ssh": "user@host"` -- an OPTIONAL read-only GPU probe over ssh for a REMOTE host, never required, never prompted for; see `docs/MODELS.md`'s "Optional ssh GPU read" section | Settings -> Ollama |
| `ollama.discover.ports` | `[11434]` | `halo config set ollama.discover.ports '[11434, 11435]'`; the ports `halo ollama discover` and the wizard's **Find Ollama servers** / **Scan this network** ask on every candidate address (Halo 3.2.3.0) -- add the port of a second daemon here; see `docs/MODELS-ollama.md`'s "Discovery" | Settings -> Ollama |
| `ollama.discover.subnets` | `[]` (the /24 of this machine's LAN address only) | `halo config set ollama.discover.subnets '["192.0.2.0/24"]'`; extra IPv4 CIDRs the network scan (`halo ollama discover --lan`) sweeps besides this machine's own /24 -- one wider than a /24 is skipped with one line | Settings -> Ollama |
| `huggingface.endpoints` | unset (no dedicated endpoints configured) | hand-edited; a list of `{name, url, token_env, default}` -- `hf:endpoint/<name>` selects an entry by `name`; each entry's own `url`/token are used as-is, never the router's `HF_TOKEN`/base URL; a saved token lives in the shared env file under the name `token_env` points at (an older `token` value still works and is migrated the next time the entry is saved); see `docs/MODELS.md`'s "Hugging Face" section | Settings -> Providers |
| `huggingface.bill_to` | unset (no header sent) | `halo config set huggingface.bill_to my-org`; a Team/Enterprise org name sent as `X-HF-Bill-To` on every ROUTER (`hf:<org>/<model>`) request only -- never on an `hf:endpoint/<name>` call | Settings -> Providers |
| `huggingface.local_servers` | unset (relies on auto-detection alone) | hand-edited, or `halo init`'s Hugging Face tab; a list of `{name, url, api_key_env, default, offline_ok}` -- `hf:local/<model>@<name>` selects an entry by `name`; `hf:local/<model>` (bare) prefers this list's default entry, else the first AUTO-detected local server; a saved key lives in the shared env file under the name `api_key_env` points at (an older `api_key` value still works and is migrated the next time the entry is saved); `offline_ok: true` marks a server not otherwise recognized as local (see `network.offline` below) explicitly local anyway; see `docs/MODELS.md`'s "Hugging Face" section | Settings -> Providers |
| `huggingface.local_probe_ports` | unset (`8080, 8000, 1234` -- see `docs/MODELS.md`) | hand-edited; a list of ints overriding which ports the `hf:local/*` auto-detect sweep probes (loopback only); `HF_LOCAL_PROBE_PORTS` (env) wins over this when both are set | Settings -> Providers |
| `huggingface.lmstudio_models_dir` | unset (`~/.lmstudio/models`, LM Studio's own documented default) | `halo config set huggingface.lmstudio_models_dir /path/to/models`; only needed when LM Studio's own in-app "Model Storage" setting moved the folder -- see `docs/MODELS.md`'s "LM Studio's own model folder" | Settings -> Providers |
| `huggingface.model_dirs` | unset (nothing scanned) | `/local add <path>`/`/local forget <path>` (persisted immediately), `halo init`'s "Local models" step, or hand-edited; a list of folder paths Halo scans recursively for `.gguf` files and safetensors/MLX model folders -- see `docs/MODELS.md`'s "Finding and using file-backed models" | Settings -> Providers |
| `huggingface.preferred_runtime` | unset (Halo picks the only valid runtime per file format: `llama-server` for `.gguf`, `mlx_lm` for safetensors/MLX on Apple Silicon) | `halo init`'s "Local models" step; `"llama-server"` or `"mlx_lm"` -- a `halo local serve --runtime` flag always wins over this; stored for a future round where the same file could genuinely be served more than one way | Settings -> Providers |
| `network.offline` | `false` | `halo config set network.offline true`; only local hosts are called -- every request to a remote host fails at once (see its own section below, and `offline_ok` on `ollama.hosts`) | Settings -> Network and routing |
| `routing.escalation` | unset (no escalation) | hand-edited; `{to: <cloud model ref>, when: [<triggers>], ask: true}` hands a local session's turn to a cloud model -- see its own section below | Settings -> Network and routing |
| `local.servers` | unset | hand-edited; named OpenAI-compatible local servers, `{<name>: {base_url, model}}`, a local route calls | Settings -> Local |
| `embeddings.model` | unset (embeddings off) | `halo config set embeddings.model nomic-embed-text`; the embeddings model recall ranks with -- see [RECALL.md](RECALL.md) | Settings -> Local |
| `embeddings.enabled` | `false` | hand-edited; `true` turns embeddings on with the default model when no model is named | Settings -> Local |
| `embeddings.host` | unset (the default Ollama host) | hand-edited; the `ollama.hosts` entry (by name) that serves embeddings | Settings -> Local |
| `embeddings.base_url` | unset | hand-edited; an OpenAI-compatible `/v1/embeddings` server used instead of Ollama | Settings -> Local |
| `embeddings.api_key` | unset | hand-edited; that server's key (masked by `halo config get`, never shown in Studio) | Settings -> Local |
| `comfy.url` | `http://127.0.0.1:8188` | `halo media init`; the ComfyUI server Media renders on -- see [MEDIA.md](MEDIA.md) | Settings -> Local |
| `governor.enabled` | `true` | `halo config set governor.enabled false`; the Governor paces every model call per host and backs off an overloaded gateway (`HALO_GOVERNOR=0`/`1` overrides it) | Settings -> Local |
| `governor.rate_rps` | `2.0` | hand-edited; requests per second per host the Governor starts from | Settings -> Local |
| `governor.max_inflight` | `2` | hand-edited; calls in flight per host at most | Settings -> Local |
| `governor.max_wait` | `120` | hand-edited; seconds a call may wait for its turn | Settings -> Local |
| `governor.max_retries` | `5` | hand-edited; retries of an overloaded call | Settings -> Local |
| `governor.hosts` | unset | hand-edited; per-host overrides of the Governor's numbers, `{<host>: {rate_rps, max_inflight, ...}}` | Settings -> Local |
| `openai.dialect_overrides` | unset (the built-in table alone: `gpt-6-astra`/`gpt-6.1-sol` default to the Responses dialect, every other `oai:` id to chat completions) | `halo config set openai.dialect_overrides '{"gpt-5": "responses"}'`; a map of bare `oai:` model id to `"chat"`/`"responses"` -- always wins over the table, in either direction; see `docs/MODELS.md`'s "OpenAI API" section | Settings -> Providers |
| `experiential.dialect_overrides` | unset (every `xp:` slug uses chat completions by default; no static required-dialect table) | `halo config set experiential.dialect_overrides '{"some-slug": "responses"}'`; same shape as `openai.dialect_overrides`, always wins over the default either direction; see `docs/MODELS.md`'s "Experiential Labs" section | Settings -> Providers |
| `experiential.tool_search` | `false` | `halo config set experiential.tool_search true`; opts into the gateway's `openrouter:tool_search`/`defer_loading` wire convention for Halo's own already-deferred tools on `xp:` routes -- off by default until a live check confirms the shape | Settings -> Providers |
| `experiential.routing.allow_fallbacks` | unset (the gateway's own default, effectively `true`) | `halo config set experiential.routing.allow_fallbacks false`; sent as `gateway.routing.allow_fallbacks` on every `xp:` request once set | Settings -> Providers |
| `experiential.routing.route_id` | unset | `halo config set experiential.routing.route_id rt_...`; pins every `xp:` request to one specific waterfall rung, from `/xp routes <slug>`'s own output | Settings -> Providers |
| `experiential.retry.max_attempts_per_route` | `1` (always sent -- Halo's own outer retry loop is the outer layer already) | `halo config set experiential.retry.max_attempts_per_route 2` | Settings -> Providers |
| `experiential.retry.max_total_attempts` | unset (the gateway's own default) | `halo config set experiential.retry.max_total_attempts 4` | Settings -> Providers |
| `experiential.retry.backoff` | unset (the gateway's own operator policy -- "omitting it keeps the existing policy" is a real, documented choice) | hand-edited; `{"type": "exponential", "base_delay_ms": ..., "max_delay_ms": ..., "multiplier": ...}` or `{"type": "none"}` | Settings -> Providers |
| `experiential.zdr` | `false` | `halo config set experiential.zdr true`; Halo 2.0.4 round 5 -- adds `"provider": {"zdr": true}` to every `xp:` request body (both the chat/Responses dialect and the Anthropic-shaped dialect for a Claude slug), demanding zero-data-retention routing for each one; never touches a bare `ant:`/Databricks-Claude-passthrough body; see `docs/MODELS.md`'s "Zero data retention" note under "Experiential Labs" | Settings -> Providers |
| `packs.sources` | unset (a bare id is not looked up anywhere) | `halo config set packs.sources '["~/packs", "https://example.com/team/doc-review.git"]'`; folders holding packs (or one pack) and git urls of packs -- `halo pack install <id>` takes the first that holds `<id>`; a folder that is not there is a `halo pack doctor` line; see [PACKS.md](PACKS.md) | Settings -> Packs |
| `packs.settings.<id>` | the pack's own `config.defaults` (pack.yaml) | `halo config set packs.settings.doc-review.style long`; one pack's settings, checked against its `config.schema` (`halo pack doctor` names a value that does not fit); `halo pack remove` leaves them in place | Settings -> Packs |

The Signal bridge's own settings (the signal-cli binary, account, identity model, transport, receive mode ...) are not `config.json` keys: they live in `~/.halo/remote/signal.json`, which `halo remote signal setup`, `register` and `link` write (see [REMOTE.md](REMOTE.md), "signal.json").

## Every environment variable

2.0.0 rename: every harness-owned knob's CANONICAL name is now `HALO_*`;
the legacy `BRIDGE_*` name (and, for the handful that briefly carried it,
`ROLO_CLAUDE_*`) each still work exactly as before, forever -- resolved in
that order (`HALO_*` first), with one DEBUG-level log line the first time a
legacy name is what actually supplied the value (`--debug`'s own log file).
A handful of test-only seams (`BRIDGE_STATE_DIR`, `BRIDGE_TEST_*`) are
deliberately NOT part of this -- they keep their bare `BRIDGE_` names for
good, with no `HALO_` twin, since the test suites depend on the exact name.

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter credential |
| `OPENROUTER_MANAGEMENT_KEY` | a SEPARATE, higher-privilege OpenRouter key (never the ordinary one above) for the whole-account balance (`GET /credits`) the status bar's "OR $X left" segment/`/cost`/`/providers` show (H15 part 2 addendum 4) -- optional; without it, that segment falls back to the ordinary key's own `/key` usage/limit figures |
| `HALO_OPENROUTER_BASE_URL` (legacy `BRIDGE_OPENROUTER_BASE_URL`) | override the OpenRouter base URL (default `https://openrouter.ai/api/v1`) |
| `DATABRICKS_HOST`, `DATABRICKS_TOKEN` | Databricks credential (see `docs/DATABRICKS.md` for the full discovery chain) |
| `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` | Claude Code's own work-box env names -- read as a Databricks credential when the host matches a Databricks domain |
| `ANTHROPIC_API_KEY` | `ant:` route credential (`api.anthropic.com` directly) |
| `HALO_ANTHROPIC_BASE_URL` (legacy `BRIDGE_ANTHROPIC_BASE_URL`) | override the `ant:` route's own base URL (default `https://api.anthropic.com`) |
| `ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_HAIKU_MODEL` | at a Databricks work box, set the default model and what bare `opus`/`sonnet`/`haiku` resolve to |
| `ANTHROPIC_CUSTOM_HEADERS` | one-or-more `Name: value` lines, merged onto every Databricks request |
| `HALO_DBX_BASE_URL`, `HALO_DBX_TOKEN` (legacy `BRIDGE_DBX_BASE_URL`/`BRIDGE_DBX_TOKEN`) | explicit override, wins outright over every other Databricks discovery step |
| `HALO_MODEL`, `HALO_MODEL_SMALL` (legacy `BRIDGE_MODEL`/`BRIDGE_MODEL_SMALL`) | override the resolved default main/small model (also used by `halo proxy`) |
| `HALO_ENV_FILE` (legacy `BRIDGE_ENV_FILE`) | path to the `KEY=value` env file (default `~/.config/halo/env`; the legacy `~/.config/vibes-hacker/env` fallback read was removed in 2.0.5 round 3 -- `halo init`'s one-time copy-forward is the migration) |
| `BRIDGE_STATE_DIR` | this harness's own state directory (default `~/.halo`; a test-only-style seam that keeps its bare `BRIDGE_` name for good -- see the note above) |
| `BRIDGE_TEST_HOME` | test/scratch seam: overrides `home()` everywhere (`~/.claude`, `~/.halo`, ...) -- never set this for real use |
| `HALO_CLAUDE_EXE` (legacy `BRIDGE_CLAUDE_EXE`) | override how the `claude` binary is launched (the claude.ai connectors bridge, `--chrome`) |
| `HALO_DUMP=1` (legacy `BRIDGE_DUMP=1`) | dump raw request/response JSON for debugging (proxy mode) |
| `HALO_CA_BUNDLE` (legacy `BRIDGE_CA_BUNDLE`) | a custom CA bundle path, tried after `NODE_EXTRA_CA_CERTS`/`REQUESTS_CA_BUNDLE` |
| `HALO_MODELS_ROSTER` | `0` keeps the model roster out of this run's context, `1` puts it in, whatever `models.roster` says (the test suite runs with `0`) |
| `HALO_AUTO_INDEX_BUILD` | `0`: an `auto` member's model pick reads `~/.halo/models/best-at.json` only and never builds the catalog itself (Halo 3.1.9.0; the test suite runs with `0`); unset, a stale index answers at once and is rebuilt in the background, a missing one is waited for at most 4 s |
| `HALO_TOOLS_CAPS`, `HALO_TOOLS_CAPS_BY`, `HALO_OPT_INS`, `HALO_SECRET_KEYS`, `HALO_SECRET_PASS` | set by an Orchestra run for one worker when its lineup or bio declares an opt-in (Halo 3.1.8.0 R5, [ISOLATION.md](ISOLATION.md)): the worker's tool capabilities and who set them, its report lines, and the NAMES of the broker keys its tool children never see (and the ones they may) -- names only, never a value; not for setting by hand |
| `HALO_INPUT_TRACE` | Windows only: a file to which the TUI appends every raw console input batch and what the parser was given (3.1.3.0), for diagnosing stray mouse-report text in the prompt from the terminal's own records |
| `CLAUDE_CONFIG_DIR` | relocate `~/.claude` (and `~/.claude.json`, honoring a legacy `<dir>/.config.json`) |
| `CLAUDE_CODE_SANDBOXED` | any non-empty value counts as "trusted" for the current directory |
| `CLAUDE_CODE_GIT_BASH_PATH` | override Git Bash's location on Windows |
| `CLAUDE_CODE_SUBAGENT_MODEL` | a settings-independent way to set the sub-agent model fallback |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` | disables auto-memory entirely |
| `VISUAL`, `EDITOR` | external editor for `Ctrl+E` (prompt draft) and `/improve`'s `e` (edit a candidate) |
| `HALO_THEME` (legacy `CLAUDE_BRIDGE_THEME`, `ROLO_CLAUDE_THEME`) | override the resolved theme (checked in that order -- `HALO_THEME` first) |
| `NO_COLOR` | disables ANSI color in `stats`' rich-rendered tables |
| `RC_TERM_WIDTH` | pin `stats`' table width instead of auto-detecting the terminal |
| `DISABLE_COMPACT` | disable auto-compaction entirely (manual `/compact` still works) |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | override the compaction trigger's context-window figure |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | lower (never raise) the 80% compaction trigger percentage, 1-100 |
| `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` | consecutive `Stop`-hook-block cap before the turn is force-ended (default 8) |
| `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS` | override the `SessionEnd` hook time budget outright |
| `TMUX` | presence gates `doctor`'s tmux-mouse-mode check |
| `OLLAMA_HOST` | seeds the `ol:` default host's URL when `ollama.hosts` has no entries configured yet (Ollama's own documented var; a bare `host:port` is normalized to a full URL) |
| `OLLAMA_API_KEY` | seeds that SAME synthesized default host's `api_key` (Ollama Cloud, `Authorization: Bearer`) -- a configured `ollama.hosts` entry's own `api_key` always wins once one exists |
| `HF_TOKEN` | Hugging Face router credential (`hf:<org>/<model>`) -- the ONLY accepted name; `HUGGING_FACE_HUB_TOKEN`/`HF_API_TOKEN` are NOT read (neither was confirmed as a router-specific alias) |
| `HALO_HF_ROUTER_BASE_URL` (legacy `BRIDGE_HF_ROUTER_BASE_URL`) | override the Hugging Face router base URL (default `https://router.huggingface.co/v1`) -- never consulted for `hf:endpoint/<name>`, which always uses that entry's own configured `url` |
| `HF_HUB_CACHE` | the Hugging Face Hub local cache directory itself (used as-is); `/local`'s hub-cache scan walks this when set, else `$HF_HOME/hub`, else `~/.cache/huggingface/hub` |
| `HF_HOME` | the Hugging Face Hub root directory -- `/local`'s hub-cache scan walks `$HF_HOME/hub` when `HF_HUB_CACHE` is unset |
| `HF_LOCAL_PROBE_PORTS` | comma-separated ints overriding which ports the `hf:local/*` auto-detect sweep probes (default `8080,8000,1234` -- see `docs/MODELS.md`); wins over `huggingface.local_probe_ports` when both are set |
| `OPENAI_API_KEY` | the real OpenAI API credential (`oai:<model>`) -- the ONLY name read, same as every other provider's single-key env var here |
| `HALO_OPENAI_BASE_URL` (legacy `BRIDGE_OPENAI_BASE_URL`) | override the OpenAI API base URL (default `https://api.openai.com/v1`) -- the test seam that stands in for the real API everywhere this round's own fake is used |
| `EXPLABS_API_KEY` | the Experiential Labs INFERENCE credential (`xp:<slug>`, prefix `xpl_`) -- calls models, reads `/api/v1/credits`/`/api/v1/usage`; the ONLY key Halo ever asks for or reads |
| `EXPLABS_PROVISIONING_KEY` | a SEPARATE, higher-privilege Experiential Labs key for key management and the full Spend API -- Halo never asks for or assumes this one; listed here only so a redaction pass still knows its name |
| `HALO_EXPERIENTIAL_BASE_URL` (legacy `BRIDGE_EXPERIENTIAL_BASE_URL`) | override the bare inference base URL (default `https://api.experientiallabs.ai/v1`) |
| `HALO_EXPERIENTIAL_ACCOUNT_BASE_URL` (legacy `BRIDGE_EXPERIENTIAL_ACCOUNT_BASE_URL`) | override the account base URL (default `https://api.experientiallabs.ai/api/v1`) -- credits/usage, separate from the inference root above |

## Providers (`halo init --provider ...`)

1.0.1 hotfix 13: `init` selects a PROVIDER to set up, not a "preset" naming
a bundle of choices; the old `--preset home|work|claude` still works, as a
deprecated alias for `--provider openrouter|databricks|claude` respectively
(one-line notice printed, no behavior change).

| Provider | Default model | Credential asked for |
|---|---|---|
| `openrouter` | `or:deepseek/deepseek-v4.1-flash` | `OPENROUTER_API_KEY` |
| `databricks` | `dbx:databricks-deepseek-v4-1-flash` | `DATABRICKS_HOST` + `DATABRICKS_TOKEN` (host often already known -- see `docs/DATABRICKS.md`) |
| `anthropic` | `ant:sonnet` | `ANTHROPIC_API_KEY` |

Ollama, Hugging Face, OpenAI API (key) and Experiential Labs each get
their own tab in `halo init`'s INTERACTIVE
Providers step (Halo 2.0.3 round 5 for Ollama/Hugging Face, round 5i for
OpenAI, Halo 2.0.4 round 2 for Experiential Labs --
`init_providers.TAB_PROVIDERS`). `halo setup`/`/setup` never reach a
Providers step at all (their own step list is `roles`/`summary`
only -- see `docs/COMMANDS.md`'s `setup` section), so none of these tabs
appear there; only `halo init` itself shows them. None of these is a
`halo init --provider`/`--preset` CLI-flag CHOICE, though, and that's
deliberate: that flag drives the OLDER sequential, non-interactive
picker, which has no sensible single hardcoded default model for any of
them (unlike the three providers in the table above, which always have
one well-known catalog entry) -- the same reason that picker's own
no-TTY/Textual-failure fallback never offers any of these tabs. Configure
`HF_TOKEN`/`huggingface.endpoints`/`huggingface.local_servers`/
`ollama.hosts`/`OPENAI_API_KEY`/`EXPLABS_API_KEY` directly instead on a
non-interactive box (see `docs/MODELS.md`'s "Ollama"/"Hugging
Face"/"OpenAI API"/"Experiential Labs" sections). The
wizard's
own "Local models" step (round 5c, right after the Providers step) is
the SAME kind of interactive-only addition -- `huggingface.model_dirs`/
`huggingface.preferred_runtime` above are its two config keys; `/local
add`/`forget` manage the first one from a non-interactive box instead.

### Default permission mode (1.0.1 hotfix 18)

After the provider(s)/default model are settled, `init` also asks for a
**default permission mode** -- `auto` (recommended, listed first),
`acceptEdits`, `default`, `plan` -- written to `~/.halo/config.json`'s
own flat `permission_mode` key. Precedence for a session's actual starting
mode, highest first:

1. `--dangerously-skip-permissions`
2. `--permission-mode` (this run's own flag)
3. `~/.halo/config.json`'s `permission_mode` (this section)
4. `settings.json`'s `permissions.defaultMode` (user layer, or
   project/local for the manual modes, as before)
5. the hardcoded `default`

`halo doctor` prints the effective mode and which layer decided it.
Never touches `~/.claude/settings.json` -- `halo config set
permission_mode auto` (or any of the four modes) sets the same key directly
without re-running `init`.

As of the H14c fixpass (finding 9), this step (and the default-model pick
just before it) only ever writes a value you actually chose THIS run --
`--yes`/non-interactive and Esc both keep whatever is already in
`config.json` unchanged (writing nothing at all for `permission_mode` on a
fresh box, so layer 4 above still applies) instead of forcing `auto`/an
arbitrary other-provider's model over it.

### `network.offline` (Halo 2.0.3 round 5e, locality rule tightened in fix
pass C-1)

`~/.halo/config.json`'s `network.offline` -- `true`/`false`, default
`false`. Set directly (`halo config set network.offline true`) or through
`/offline on|off` (persists the same key); `--offline`/`HALO_OFFLINE=1`
override it for one process WITHOUT persisting anything (checked first,
ahead of this key). While on, the one HTTP choke point
(`halo_harness.providers.http`'s `open_upstream`/`urlopen_tls`) refuses any
connection whose host is not loopback (`127.0.0.1`/`localhost`/`::1`) or
ACTUALLY local by one of three tests:

- a private, loopback, link-local or IPv6 ULA IP literal (RFC1918,
  169.254.0.0/16/fe80::/10, fc00::/7, ...) -- never a hostname that merely
  *resolves* to one; computing this allow-list never itself makes a DNS
  query,
- a bare single-label name (`gpubox`, no dot) or an `.local` mDNS name,
- an `ollama.hosts`/`huggingface.local_servers` entry the user marked
  `offline_ok: true` explicitly.

Checked against every `ollama.hosts[].url` entry, every `huggingface.
local_servers[].url` entry, and every entry in the managed local-server
registry (`halo local serve`'s own `~/.halo/run/local-servers.json` --
always loopback by construction). A hostname that is merely *configured*
is no longer enough by itself: `ollama.com` (saved as an `ollama.hosts`
entry keyed by `api_key`, or reached via an ambient `OLLAMA_HOST=https://
ollama.com` with no config at all) and any other public hostname a user
pastes into either list are refused exactly like any other cloud host.
A loopback or allow-listed host is also never sent through
`HTTPS_PROXY`/`HTTP_PROXY`, and a redirect response is re-checked against
the same gate before it is ever followed.

Covers update checks (including the update command's own `git ls-remote`
fast path, never only its API fallback), catalog refreshes, the Hugging
Face router, OpenRouter, Databricks, Anthropic, the WebFetch/WebSearch
tools, `--plugin-url`'s `git
clone`, and `hf:mlx`'s first-use model download. `halo update`'s apply
step (the actual reinstall, not just `--check`) returns an error result
instead of running `git pull`/`uv tool install`/`pip install --upgrade`.
The claude.ai connectors bridge's own background/cold-start discovery is
skipped (one DEBUG line) rather than refused, since its real network call
happens inside a spawned `claude` subprocess, outside this process's own
choke point -- an explicit `halo mcp list --refresh`/`/mcp` reconnect still
runs that subprocess regardless (same as running `claude mcp list`
directly in an offline shell would). A refusal is always one plain
sentence: `offline mode: not connecting to <host>` -- never retried, never
treated as a reason to try a `--fallback-model` entry. See
[COMMANDS.md](COMMANDS.md)'s `--offline` and
[SLASH-COMMANDS.md](SLASH-COMMANDS.md)'s `/offline`.

### `routing.escalation` (Halo 2.0.3 round 5e)

`~/.halo/config.json`'s `routing.escalation` -- hybrid escalation as an
explicit policy, local-first:

```json
{
  "routing": {
    "escalation": {
      "to": "or:anthropic/claude-haiku-4.5",
      "when": ["low_confidence", "tool_failures", "context_overflow"],
      "ask": true
    }
  }
}
```

- `to`: the cloud model ref to escalate to.
- `when`: any of `low_confidence` (the `judge` role's own one-word
  confidence check on the local model's final reply -- see `docs/
  ROLES.md`), `tool_failures` (two or more `is_error` tool results in the
  current turn), `context_overflow` (the existing compaction-overflow path
  fired this turn).
- `ask`: `true` (default) asks -- a plain notification naming the trigger
  and target, stays on the local model; `false` switches automatically for
  the rest of the turn (`tool_failures`/`context_overflow`) or from the
  next model call on (`low_confidence`, since the turn that triggered it
  is already over), with a transcript note ("escalated to \<ref\>:
  \<trigger\>").

Only ever evaluated on a local-model session (`ol:`/`hf:local`/`hf:mlx`) --
never on a cloud-model session, and never onto a target `network.offline`/
`--offline` would itself refuse (fix pass C-2): the session stays local,
with one plain notice naming the trigger, when the two conflict -- never a
silent switch onto a model every later request would then also be refused
for. A role-table entry's own `"escalation": false` turns it off for every
sub-agent built under that role (`halo roles`/`docs/ROLES.md`), regardless
of this top-level setting. An auto-switch (`ask: false`) leaves a real
trace, not just a 5-second toast: a permanent transcript line, an
immediate status-bar model update, and -- in print mode -- an
`escalations` entry on the `-p --output-format json` result object.
`/escalation` shows the active policy and this session's last few
decisions. See [MODELS.md](MODELS.md)'s "Hybrid escalation" section.

### Saved versus cloud (Halo 2.0.3 round 5e)

A local-model session (`ol:`/`hf:local`/`hf:mlx`) tracks what the same
input/output/cache tokens would have cost on a reference cloud price (the
configured `routing.escalation.to`, or, with no escalation policy at all,
the vendored catalog's median priced model) and reports the running total
as `saved_usd`. Fix pass C-2: it only ever accrues while the session is
CURRENTLY running on a local model -- after an escalation, a `/model`
switch, or a `--fallback-model` swap onto a cloud ref it stops growing
immediately, and resumes with no re-pinning needed the moment the session
is back on a local one (the reference price itself, once resolved, stays
pinned for the session's life either way). `/cost` shows the full
breakdown; the status bar appends "· saved $x" to the cost segment. See
[MODELS.md](MODELS.md)'s "Saved versus cloud" section.

## What is never written

- `~/.claude.json`, `~/.claude/settings.json` -- **never** touched by
  `init`/`doctor`/the agent loop; the ONE deliberate exception is
  `halo mcp add`/`add-json`/`remove` writing `~/.claude.json`'s
  `mcpServers` keys, precisely mirroring what `claude mcp add`/`remove`
  itself writes.
- `~/.claude/.credentials.json` -- **never opened at all**, not even to
  check it exists. The claude.ai connectors bridge's login check reads
  only `claude auth status`'s own JSON output.
- A provider API key or Databricks token is never written into a session
  log, a cache file, or a `doctor`/`--config`/`stats` line -- `redact()`
  keeps the first four characters and elides the rest; `halo export
  --sanitize`/`/export --sanitize` additionally scrub anything that slipped
  into a transcript via a tool's own output (a Bash `env` dump, a Read of a
  settings file).
- An `ollama.hosts`/`huggingface.endpoints`/`huggingface.local_servers` key
  saved through `halo init`'s tabs is never written into `config.json` as
  plaintext either (fix pass C-1) -- it goes into the same shared env file
  `DATABRICKS_TOKEN`/`HF_TOKEN` already use, under a generated name
  (`HALO_SECRET_<KIND>_<NAME>`), and `config.json` keeps only that name
  (`api_key_env`/`token_env`). `~/.halo/config.json` is written 0600 on
  POSIX whenever the platform supports it, and `halo config list`/`config
  get` mask any secret-shaped value (an older plaintext `api_key`/`token`
  entry included) rather than printing it verbatim. A malformed config
  entry is ever only logged by its own `name`, never `%r` of the whole
  entry.
