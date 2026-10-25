# Halo Harness handbook

Read this when you want the long-form guide: configuration, providers, permissions, steering, hooks, skills, MCP, sessions and themes.

The long-form guide. It opens with the ten-minute start; the front-page
[README](../README.md) covers install, quick start and what makes Halo
intuitive; this document keeps the full
detail for configuration, config reuse, providers, permissions, steering,
hooks, skills, commands, MCP, browser, sessions, print mode, telemetry,
troubleshooting, security posture, tests and proxy mode.

## The ten-minute start: `halo start`

```sh
halo init       # a provider, a default model; its last step offers the ten-minute start
halo start      # seven screens, Enter to go on, q to stop (--yes runs straight through)
```

`halo start` walks one real piece of work through the pieces Halo is made of,
one screen per step, each with one sentence of why and the command it runs:

1. **The lineup** -- the shipped `halo-dev-cycle` copied into your scope as
   `my-halo-dev-cycle`, its cards shown as a table with their tiers (your
   active lineup stays what it was).
2. **The sample repo** -- `~/.halo/start/<date>/basket/`: `basket.py` with five
   functions to write and `test_basket.py`, a git repo with one commit.
3. **The goal** -- an Orchestra run, "Write the five functions of basket.py",
   with `plan: review`, so it pauses after the lead's split.
4. **The plan** -- the lead's lanes as a table; Enter approves it, `s` opens
   it on Studio's plan canvas and waits for your decision there.
5. **The run** -- the lanes table as each worker claims, writes and merges its
   function, until the gate runs the tests.
6. **The report and the coach** -- every check with a tick or a cross, then
   the coach's cards (Apply opens the bio in Studio).
7. **Where to go next** -- Roles, Team and Fleet, each with its command.

It runs on the model you configured (with none, it says so and points at
`halo init`). The same start runs in the TUI (`/start`, a panel) and in
Studio (the **Start here** card a fresh home opens on). Any word on the way
-- lineup, lane, claim, gate, hand-off -- is one `halo explain <word>` away
([GLOSSARY.md](GLOSSARY.md)); the full reference is
[COMMANDS.md](COMMANDS.md) (`halo start`).

## A 10-minute walkthrough


How a session fits together, in one picture: [the session flow](media/diagrams/session-flow.svg). The pictures themselves are made by `tools/capture_screens.py` ([MEDIA.md](MEDIA.md)).

```sh
halo init                    # pick a provider, set credentials, doctor, live pong
halo                         # full-screen TUI
```

1. **`halo init`** opens on **Quick setup vs. Full setup** (Halo 2.0.5
   round 2c, `docs/WIZARD.md`'s own interaction model -- a step rail
   across the top of everything below, Ctrl+Left/Ctrl+Right walking it
   from anywhere): Quick (the highlighted default) is just **Providers**
   then **Default model** then **Summary** -- every role, including a
   sub-agent halo spawns on its own, uses that one model. **Full setup**
   walks every step, Back/Skip/Next (Finish on the last step) in the
   footer, nothing exiting to the console in between: **Providers** (one
   tab each for Databricks/OpenRouter/the Anthropic API/Ollama/Hugging
   Face/the OpenAI API/TypeSafe -- paste the credential a tab is
   missing, add a local/LAN host or server where that applies,
   Save, repeat for another, any tab Skippable); **Default model** (a
   picker across everything just configured); **Permission mode** (`auto`
   recommended); **Theme** (the six built-in themes, with a live preview); **Team**
   (Halo 2.0.5 round 2c: a "Custom roles: off / on" switch -- off shows
   one sentence and nothing else; on shows **Lineups** (pick, edit, or
   build a new lineup assigning bios or plain models to roles) and
   **Agents** (list/create/edit/duplicate/delete agent bios, or import
   one from a `.claude/agents/*.md` file) side by side, Enter opens
   either kind's own editor, Ctrl+N/Ctrl+D/Del act on whichever pane is
   focused); **Linux fixes** (skipped when nothing needs it); **Summary**
   (what was written, doctor, a live "pong", and a "Change" row that
   jumps back into any step this run used). `--step <key-or-number>`
   (e.g. `--step team`, `--step agents`/`--step roles` kept as aliases)
   jumps straight to any one step, skipping the Quick/Full choice.
   Reach Team again later with `/setup team` or `halo setup team`, or the
   bios and lineups any
   time with `/agents`/`/teams` (they show bios and lineups; Studio edits them:
   `halo agents|teams edit <name>`, `/edit <thing>`, `e` in a view) --
   see `docs/WIZARD.md` for the full ten-rule interaction model and chord
   table, `docs/COMMANDS.md`'s `init`/`setup`/`agents`/`teams` sections,
   and `docs/AGENTS.md`'s own wizard section for exactly what each step
   reads and writes.
2. **The first session** opens with an empty prompt line and a status bar
   showing the model, permission mode, and MCP server count. Type a prompt
   and press `Enter`.
3. **`/model`** opens a picker of every model this box can currently reach
   (OpenRouter's cache, Databricks' own discovered endpoints grouped by
   family, and the `ant:` Claude aliases once `ANTHROPIC_API_KEY` is
   set); pick one, or type `/model or:deepseek/deepseek-v3.2` directly.
4. **A tool call with a permission card**: ask for something that edits a
   file (`"add a .gitignore entry for *.log"`). In the default permission
   mode, an `Edit`/`Write` inside your working directory shows a
   `PermissionCard` -- `1` allow once, `2` allow for the rest of this
   session, `3` allow always (writes a rule to
   `.claude/settings.local.json`), `4`/`Esc` deny (optionally typing one
   line telling the model what to do differently first). `Shift+Tab`
   cycles into `auto` mode any time you'd rather not be asked at all --
   auto mode allows everything except a rule *you* wrote yourself, never a
   built-in judgment call.
5. **Steering**: type another line and hit `Enter` while a turn is still
   running -- it queues and is woven in at the next safe point (a chunk
   boundary, or right after the tool call in progress finishes), shown as
   "steering..." until then. It never needs you to wait for the turn to
   finish first, and it never answers a permission/question card that
   happens to be pending at the same moment.
6. **`/resume`** (or `-r` on the command line next time) opens a picker of
   recent sessions for this directory, live-filtered as you type by title,
   first prompt, cwd, or model.
7. **`/stats --models`** aggregates tokens/cost/tool-error-rate/repair-hit-
   rate across every session logged for this project -- the same data
   `halo stats --models` prints headlessly (`docs/COMMANDS.md`).
8. **`/improve`** scans recent sessions for repeated friction (tool errors,
   repair-layer hits, corrections you typed), drafts up to eight candidate
   memory/rule/skill files with one model call, and reviews them one card
   at a time -- `a` apply, `e` edit first, `s` skip, `d` dismiss forever,
   `q` stop. Nothing is written to disk until you say so.


## Configuration

`halo init` (see Quick start above) does everything below in one
command; this section is the manual/reference version of the same steps.

Put `OPENROUTER_API_KEY` in `~/.config/halo/env` (`KEY=value`, `#`
comments, optional leading `export`; override the path with
`HALO_ENV_FILE`, legacy `BRIDGE_ENV_FILE` still honoured) or export it
yourself -- that's the only required setup. A pre-2.0.0
`~/.config/vibes-hacker/env` is no longer read at all (removed in 2.0.5
round 3, announced back in the [2.0.1] CHANGELOG); `halo init` still
copies its content forward into the new file, once, the first time it
writes there, so nothing already configured in it is lost
for OpenRouter models. Databricks credentials are discovered automatically,
same chain the whole project has always used: explicit `HALO_DBX_BASE_
URL`+`HALO_DBX_TOKEN` (legacy `BRIDGE_DBX_BASE_URL`/`BRIDGE_DBX_TOKEN`)
wins outright, then `ANTHROPIC_BASE_URL`+
`ANTHROPIC_AUTH_TOKEN`/the settings `env` chain when the host is a real
Databricks host, then `DATABRICKS_HOST`+`DATABRICKS_TOKEN`, then (H8)
`~/.claude/ucode-settings.json` if Databricks' own `ug`/unity-gateway CLI
already wrote one, then `~/.databrickscfg`'s `[DEFAULT]` section last (a
generic, possibly stale/unrelated-workspace fallback).
Nothing to configure if any of those already work for the real `claude` CLI
on the same box.

`halo doctor` is a read-only environment check (Python version,
`~/.claude` layout, env file, OpenRouter/Databricks reachability, catalog
cache ages, chrome/playwright/plugin detection, `rg`/`$VISUAL`/`$EDITOR`/
tmux mouse mode/Bash-shell presence, clipboard backend, configured MCP
servers, the default model in `~/.halo/config.json`); every `WARN`/
`MISSING` line ends with the exact fix command (or a doc reference when
there's no single command), and `doctor --json` prints the same checks as
`{id, status, message, fix}` records. `halo doctor --work`
is the Databricks-specific preset for a VPN-gated work box (VPN
reachability, token validity, the reasoning-replay/route-split probes) --
see INSTALL.md's "Work box" section.

## First run

```sh
halo                          # full-screen TUI (needs a real terminal)
halo "read README.md"         # TUI, prompt pre-filled as the first turn
halo -p "reply with the word pong"   # print mode, scriptable/headless
halo --demo                   # scripted TUI walkthrough, no network/model needed
```

Bare `halo` (no `-p`) checks `stdin.isatty()` before importing
`textual`; outside a real terminal it prints one line to stderr and exits 2
instead of hanging -- expected, use `-p` for anything non-interactive
(cron, CI, a subprocess).

## Updating

```sh
halo update --check    # report only: installed vs. available, the exact command
halo update             # apply it -- or /update inside the TUI
```

`halo update --check` prints what's installed (version, commit, branch --
`halo --version`/`halo doctor` show the same), what's available (cached up
to 24h; `--channel stable` tracks the newest `v*` tag instead of the
branch halo came from), the commits between them, and the exact reinstall
command for however this install was made (uv tool, pipx, pip, an
editable checkout, or a bare checkout on PYTHONPATH). Exit 0 up to date,
10 an update is available, 1 unknown (offline, no git, rate-limited).

`halo update` (no `--check`) first stops every other process of this
install (a Studio, background runs, schedule fires, other sessions, the
supervisor -- started again afterwards), one line each, since the venv
can't be replaced while a process still has it open; then it runs that
command live and reports the before/after commit from a fresh `halo
--version`. `--keep-running` names what runs and installs nothing;
`--force` installs without stopping anything. `--to <tag|branch|commit>`
picks an exact revision instead of the channel's latest.

`/update` in the TUI runs the same check off the UI thread and opens a
dialog with the report plus `Enter: quit, then update` / `Esc: not now`.
Enter quits the TUI and a detached updater runs the update once halo has
exited -- the only safe order on Windows (never while a halo process still
holds the install open); its log is `~/.halo/update.log`, and `halo
--continue` resumes the session on the new code. A background
check also adds a one-line "update available" note at startup, at most
once a day, when one is already known to be available -- off with
`update.check: false` or `update.notify: false` in `~/.halo/config.json`.
See "Update" in [docs/INSTALL.md](INSTALL.md) for the manual command per
install kind.

## Config reuse from Claude Code

The whole point is that a box already set up for `claude` needs nothing
extra: `~/.claude.json` (trust, MCP servers, project state), `~/.claude/
settings.json` (managed -> user -> project -> project-local, later wins),
every `CLAUDE.md` up the directory tree, `~/.claude/agents/*.md` and
`.claude/agents/*.md` (subagent definitions), `~/.claude/commands/` and
`.claude/commands/` (custom slash commands), `~/.claude/skills/` and
`.claude/skills/` (skills), `.mcp.json` (with the same first-time-approval
flow), plugins under `~/.claude/plugins/`, and `~/.claude/keybindings.json`
are all read as-is. A server/command/skill/agent added to any of those
files (by hand, by `claude mcp add`, or by the real `claude` CLI) is picked
up by the next `halo` session with no separate config step; a server
added via `halo mcp add` is equally visible to `claude mcp list`.
`--settings`/`--setting-sources`/`--bare`/`--strict-mcp-config`/`--mcp-
config` all work the same as Claude Code's own flags.

## Models and providers


The route prefixes and what a session reuses, drawn: [routes](media/diagrams/routes.svg).

Every remote model request is paced by the Governor -- one shared,
adaptive per-host rate limiter across every halo process on the
machine, with priority fairness and host failover. See
[GOVERNOR.md](GOVERNOR.md) for the five properties, the config table
and how to read a 429 storm.

Model reference forms:

| Form | Example | Resolves to |
|---|---|---|
| `or:vendor/model` | `or:deepseek/deepseek-v3.2` | OpenRouter |
| bare `vendor/model` (contains `/`) | `deepseek/deepseek-v3.2` | OpenRouter |
| `dbx:databricks-<name>` | `dbx:databricks-kimi-k3` | Databricks, OpenAI-chat dialect |
| `dbx:system.ai.<name>` | `dbx:system.ai.my_model` | Databricks, OpenAI-chat dialect |
| any of the above with `claude` in the name | `dbx:databricks-claude-sonnet` | Databricks, raw Anthropic passthrough |
| `ant:<name>` | `ant:opus`, `ant:claude-3-5-haiku` | `api.anthropic.com`, pay-as-you-go (`ANTHROPIC_API_KEY`) |
| a bare Claude alias, no prefix | `opus`, `sonnet`, `fable` | `ant:` if `ANTHROPIC_API_KEY` is set, else an error |

`--model`/`--small-model` pick the main/background-task model for the
session; `halo models --refresh` pulls OpenRouter's `/api/v1/models`
and models.dev's `api.json` into `~/.halo/` (context window, max
output tokens, vision support per model); without ever having run that, a
vendored fallback copy shipped inside the package (`halo_harness/providers/
catalog/`) still lets profile resolution work completely offline. Databricks'
own endpoint list is cached by the same probe. Per-family prompt notation
(including a Kimi-specific block adapted from OpenCode's own) adjusts tool-
call/thinking conventions per model family automatically.

**Local and cloud models added in 2.0.3** -- Ollama (`ol:`), Hugging
Face (`hf:`) and the OpenAI API (`oai:`) -- aren't in the table above, which predates them; see
[docs/LOCAL-MODELS.md](LOCAL-MODELS.md) for the end-to-end guide and
[docs/MODELS.md](MODELS.md) for the exhaustive per-route reference.

### Databricks at work

If the box already runs Claude Code against a Databricks workspace, halo
needs zero setup: it reads the SAME `~/.claude/settings.json` `env` block
Claude Code itself uses (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`,
`ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`/`_SONNET_MODEL`/
`_HAIKU_MODEL`, `ANTHROPIC_CUSTOM_HEADERS`), the same host/gateway-path
convention (`https://<workspace>/ai-gateway/anthropic` splits into the bare
workspace root plus the gateway path), and maps the default model and bare
`opus`/`sonnet`/`haiku` through it -- `run halo` and it drives the
same models Claude Code would. **Nothing about the real workspace ever
leaves the box**: the hostname and token live only in the local env file
(or wherever Claude Code's own settings already put them) and are never
written into a session log, a cache file, or printed by `doctor`.

**Discovery, not a vendored list.** `halo models --refresh` (or
`init --provider databricks`) lists the workspace's own serving endpoints and caches
them, per user, to `~/.halo/dbx-endpoints.json` (name, `api_types`,
`foundation_model.name`, task) -- the ONLY source of truth for what a
workspace serves. A generic family x api_type table (detected from the
endpoint's own name) then decides each endpoint's route: Claude foundation
endpoints default to the native `anthropic/v1/messages` gateway; GLM/Kimi
default to `mlflow/v1/chat/completions` chat (the anthropic gateway is
selectable per model with `databricks.gateway.<endpoint>: anthropic` in
`~/.halo/config.json`, or a one-off `dbx:<endpoint>@anthropic` suffix);
DeepSeek/Qwen/Llama/Gemma/gpt-oss/GPT/Grok/Gemini default to mlflow chat
(the wire "model" value is the endpoint's own discovered
`foundation_model.name`, e.g. `system.ai.qwen35-122b-a10b`, never guessed by
prefixing); `databricks-gpt-5-5-pro` has no mlflow chat and uses `cursor/v1/
chat/completions` instead; Bedrock EXTERNAL Claude endpoints
(`us-anthropic-claude-*`) are invocations-only, never the native passthrough,
despite "claude" being in the name; an embeddings/whisper endpoint is
refused with a clear message and hidden from `/model`. An endpoint the cache
doesn't know about yet still works (the pre-discovery candidate order).

**Team setup.** A shared, checked-in `team.json` (see `team.example.json`)
holds the workspace host, a default model, a per-family gateway preference,
and a DBU price -- **never a token, never an endpoint list** -- discovered
at `.halo/team.json` in the project, `~/.halo/team.json`, or
`--team <path|url>`. With a host already known (from `team.json` or Claude
Code's own settings), `halo init --provider databricks` asks ONLY for the
personal Databricks token (hidden input, written to the env file at 0600),
refreshes the catalog, and prints how many endpoints are available and the
default model.

**Keeping the catalog fresh.** `/models refresh` (alias `/dbx`) re-lists the
workspace off the UI thread and reports what changed since last time;
`halo models --refresh --urls [--json]` prints the exact URL and path
type (mlflow/cursor/anthropic/invocations) each endpoint resolves to, for
scripting. The cache auto-refreshes off the UI thread, with a one-line diff
notification, whenever it's older than `databricks.catalog_max_age_hours`
(default 24) and `/model` is opened; an already-cached catalog also
refreshes silently (never a first-time discovery call) when a Databricks
session starts. A refresh that fails (offline, or 403 from the IP access
list) just keeps the existing cache and says so.

**Diagnostics.** `halo doctor --work` prints the derived workspace
root, the gateway path, the header NAMES it sends (never values), the
resolved default model and effort, and which config source supplied the
token; it distinguishes a bad token (401) from the IP access list (403 with
Databricks' own wording -- "connect to the VPN") from a token that can run
inference but not list endpoints (403 without that wording) from a wrong
path (404). `halo doctor --work --probe-all [--both] [--tools]
[--only <glob>]` is the full work matrix: one short pong through every
chat-shaped endpoint on its chosen path (plus the anthropic gateway too for
Claude/GLM/Kimi with `--both`; a tool-call check with `--tools`), a table of
status/latency/output tokens, and a JSON report at `~/.halo/
work-matrix-<date>.json` naming endpoints only -- no host, no token -- so it
can be pasted back for review.

**Turning probes into fixes.** `halo work-matrix show <report.json>`
reads that same JSON report and prints one line per failing endpoint with a
suggested action (a 403 -> get on the VPN; a wrong default gateway path ->
set `databricks.gateway.<endpoint>`; a family-wide tool-call/reasoning-replay
issue -> report only, no per-endpoint fix exists); `halo work-matrix
apply <report.json> [--yes]` writes the one class of fix that maps onto a
real `~/.halo/config.json` key, after listing exactly what it's about
to write and asking for confirmation. See
[docs/DATABRICKS.md](../docs/DATABRICKS.md)'s own **End-to-end team workflow**
section for how this fits together with `team.json` and `init`.

**A Databricks-only edition.** If your whole team only ever talks to a
Databricks workspace, a separate repository,
[databricks-claude](https://github.com/roloVibes/databricks-claude), is a
dedicated Databricks-only edition built for that case. halo itself
stays the general harness across all four routes above.

### Roles


Ten built-in roles (V2c, widened in Halo 2.0.2 --
`orchestrator`/`planner`/`coder`/`reviewer`/`judge`/`researcher`/`tester`/
`compaction`/`small`/`subagent_default`) let a team point different kinds of
work at different models -- cheap for exploration, strong for planning/
review -- without hand-editing every agent file; a role VALUE is a bare
model string or `{"model", "effort"}` (Halo 2.0.2), so a role can also pin
its own reasoning effort, not just its model. `~/.halo/config.json`'s (or a
shared `team.json`'s, or a loaded `~/.halo/roles/<name>.json` template's)
`roles` table sets this per role; built-in agents (`general-purpose`,
`Explore`, `Researcher`, `Plan`, `Reviewer`, `Coder`, `Judge`, `Tester`) each
carry a fixed default role, a custom `.claude/agents/*.md` sets one with a
`role:` frontmatter key, and `--role NAME=MODEL[:EFFORT]`/`Agent(role=...)`/
`/role NAME MODEL [EFFORT]` override one for a single run/call/session. Any
OTHER syntactically-valid name (`[a-z][a-z0-9_]*`) a team.json or a loaded
template actually defines is an equally valid role name everywhere above.
`/roles` shows the resolved table (model, effort, endpoint/path type, price)
per role and manages templates (`templates`/`save`/`load`/`new`/`edit`/
`show`); `halo roles template ...` is the CLI equivalent; `halo stats
--roles` sums sub-agent spend per role; `halo completion bash|zsh|
powershell` completes role names and cached model refs too. A switch,
`roles.enabled` (default on), turns the whole table off (every role
resolves to the session model) -- `halo roles on|off`, `/roles on|off`,
and the wizard's own top-of-step toggle all flip the SAME switch; `halo
roles` always prints the current state as its first line. The init
wizard's Roles step (`halo
init`, `/setup roles`, `halo setup roles`) offers three shipped presets
(`balanced`/`quality`/`local-first`) with a live preview. See
[docs/ROLES.md](../docs/ROLES.md) for the full resolution precedence
(including the new `compaction`/`subagent_default` rungs) and the
(documented, never automatic beyond one specific case) cost-aware defaults.

### Sub-agent visibility and scale

`/tasks` (or Ctrl+T) opens a panel listing every running, queued,
background and finished sub-agent of this session, with a second tab for
the shared task board; Enter opens a live transcript viewer of the
highlighted one. `agents.max_concurrent` (config, default 4) and
`agents.max_depth` (config, default 1, up to 3; a lineup's own
`delegation.max_depth` overrides this, unclamped) govern how many sub-agents may run at once
and how deep they may delegate; the Agent tool's `count`/`batch`
parameters spawn several in one call (one combined result, in spawn
order), queueing past the cap. The shared task board (`TaskCreate`/
`TaskUpdate`/`TaskList` tools, `~/.halo/sessions/<id>/tasks.json`) lets
a lead's sub-agents claim and report on open work. See
[docs/SUBAGENTS.md](../docs/SUBAGENTS.md).

## Permissions and auto mode

Seven modes, same names and mode-table semantics as Claude Code:
`default` (`manual` is a display alias for the same thing), `acceptEdits`,
`plan`, `dontAsk`, `auto`, `bypassPermissions`. Grammar and modes ONLY --
**no classifier, no destructive-command list, no protected-path list, no
security-tool flagging, anywhere**: `auto` allows everything not matched by
an explicit deny/ask rule or blocked by the user's own hook;
`bypassPermissions` allows everything not matched by a deny rule (hooks
still apply to both -- a `PreToolUse`/`PermissionRequest` hook the user
configured runs after every decision, in every mode, and can still block
or rewrite a call `auto` already allowed); the manual modes keep Claude
Code's own semantics because the user chose them deliberately, with no
extra heuristics bolted on. Rules are the same grammar Claude Code accepts
(`Bash(git status:*)`,
path globs, `mcp__server`/`mcp__server__tool`, WebFetch domains, etc.),
read from `permissions.allow`/`.ask`/`.deny` in the same settings chain,
plus `--allowedTools`/`--disallowedTools`/`--dangerously-skip-permissions`.

A deny or ask rule follows the command it names: it still fires when the
command is reached through `if`/`for`/`while`/`case` bodies, `!`, `exec`, a
wrapper (`sudo`, `env`, `watch`, `flock`, `strace`, `unshare`, ...), a `-c`
payload or `find -exec`, a tool's global options (`git -C x push`, `docker
--context x run`), PowerShell script blocks and `-Command` strings, and a
`Read(...)` rule also covers the Bash readers (`cat ~/.ssh/id_rsa`, `grep`,
`sed`, `awk`, `cp`, `< file`) and files below a directory handed to Grep or
Glob. An allow rule matches exactly as before and auto mode with no rules
still allows. A rule that does not parse is reported (a line at startup,
`/permissions`, `halo doctor`) instead of silently doing nothing.

## Steering


A steer landing mid-turn, as an animated capture: [steer-mid-turn](media/steer-mid-turn.anim.svg).

Typing while a turn is running queues a mid-turn steer (multiple steers
apply in order); a steer that arrives while a permission/question card is
still waiting for its own answer doesn't answer that card, it just queues.
Print mode gets the same thing via `--input-format stream-json` lines
arriving mid-turn. The transcript shows "steering..." while one is in
flight.

## Themes

`/theme <name>` (or `halo init`'s Theme step, `halo config set theme <name>`,
`--theme`, `HALO_THEME`) picks one of six names: `claude-dark`,
`claude-light` and their `-daltonized` and `-ansi` variants. The choice
persists in `~/.halo/config.json` under `theme`. With nothing chosen, Halo
uses `claude-dark` on a truecolor terminal and `claude-dark-ansi` elsewhere.
The status bar is the same single line under every theme.

The game themes (DOOM, Metroid, Mario, Beetlejuice, Alien) with their level
band, status-bar skins and toggles were removed in 3.1.5.0. A `config.json`
that still names one falls back to the default theme, and Halo says so in one
line at startup and in `halo doctor --config`, for example `theme: doom was a
game theme, removed in 3.1.5.0; using claude-dark`. The keys they wrote
(`theme_scene`, `theme_variant`, `theme_toggle_previous`) are ignored, one
doctor line each.

## Remote control from Signal


The path from phone to session, drawn: [remote control](media/diagrams/remote-control.svg).

Halo 2.0.9 can be driven from a phone: message a Signal number, and the text
becomes a prompt in a session running on your computer; permission cards, plan
reviews and questions come back to the phone and are answered by number or
letter. It is off until you turn it on:

```sh
halo config set remote.enabled true       # the bridge may run (sessions' sockets are on by default)
halo remote signal setup                  # dedicated number (recommended) or linked device
halo remote signal register +15555550123  # captcha, SMS code, registration lock (dedicated)
halo remote signal run                    # the bridge, in its own terminal
```

Then message the number, approve the contact request in `/remote` (compare the
safety number first), and send the six-digit code back; commands afterwards carry
an HMAC signature from a secret only your phone has. A `⇄ remote` chip shows in the
status bar while a phone is attached, `halo remote signal off` is the kill switch,
and `halo doctor` checks signal-cli, its version pin and the folder permissions.
The threat model, setup per OS (Kali, Windows, macOS, a proxied VM), the chat
commands and a live checklist are in [REMOTE.md](REMOTE.md).

## Keys: Ctrl+C copies, a second press asks before quitting

`Ctrl+C` is the copy key. One press copies the current selection (the chat
box, any text field, or a transcript drag), or, with nothing selected, your
last assistant reply, and says "Copied N characters" (or "Nothing to
copy"). It never interrupts a running turn -- `Esc` does that. Press it a
second time within 3 seconds and a card asks "Quit Halo? Enter quits, Esc
stays"; nothing closes until you press `Enter`. `halo config set
quit_on_double_ctrl_c false` removes the card (every press just copies).
`Ctrl+D` on an empty prompt, `Ctrl+Q` and `/exit` quit as before. On
Windows, Halo keeps the console from turning `Ctrl+C` into a process-ending
event for as long as the TUI runs, so a single press can no longer close
the session from PowerShell or Windows Terminal.

**Copying what you have typed.** `/copy draft` copies the chat box's unsent
text (type it over the draft; it copies what the box held before the
command), and `Ctrl+Shift+C` does the same in one key where the terminal
passes that key on. After every copy the status line says what landed --
"copied N characters via xclip" -- or, when no clipboard tool did, why
(on Linux: "no clipboard tool: sudo apt install xclip ...") and that the
text was saved to `~/.halo/clipboard.txt`. A plain mouse drag selects
inside Halo; hold `Shift` while dragging for the terminal's own selection.
See "Copy does nothing on Linux" in [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

**Clearing the chat box.** `Ctrl+U` empties it (text, pastes and image
chips) at any time. `Esc` does the same when nothing is running; while a
turn runs, `Esc` interrupts the turn and leaves your draft alone. `Ctrl+A`
then `Delete` works too.

**Stray `[<35;72;18M` or `8;17M` text while the mouse moves (Windows).**
Those are the terminal's mouse reports, or their tails. Textual's parser
gives up on an escape sequence 100 ms after its last character, so a
report that straddles two reads of the console while Halo is busy (the
first seconds after launch, while the catalog and the MCP servers load)
was typed into the box as text, and a console whose input mode flipped
mid-report handed over the tail alone. Halo 3.0.2.0 puts a stage between
the console and the parser that holds an incomplete trailing sequence
until the rest arrives and drops a batch that is nothing but report tails;
the box also strips any fragment that still lands the moment its final
`M` arrives, and `Ctrl+U` clears it. 3.1.3.0 closes the last gap: a
quiet console used to release a held partial report after 30 ms (a loaded
machine can split a report that far), and the parser typed it; a held
report head now waits up to two seconds for its tail and is dropped,
never typed. To send a report, run with `HALO_INPUT_TRACE=<file>` and
move the mouse: the file holds every raw console batch.

## Hooks, skills, commands, MCP, browser

Claude.ai connectors reaching a non-Claude model through the claude binary, drawn: [the connectors bridge](media/diagrams/connectors-bridge.svg).

**Hooks**: the events this harness actually fires are `SessionStart`/
`SessionEnd`, `UserPromptSubmit`/`UserPromptExpansion`, `PreToolUse`/
`PostToolUse`(`Failure`), `PostToolBatch`, `PermissionRequest`/
`PermissionDenied`, `Stop`/`SubagentStart`/`SubagentStop`/`StopFailure`,
`PreCompact`/`PostCompact`, `PreModelSwitch`/`PostModelSwitch`,
`TaskCreated`/`TaskCompleted`, `FileChanged`, `CwdChanged`,
`DirectoryAdded`, `ConfigChange`, `InstructionsLoaded`, `MessageDisplay`,
`Setup` and `WorktreeCreated` -- and every handler type a hook definition
can invoke for them -- `command` (shell), `prompt` (inject text), `agent`
(run a sub-agent), `http` (call a URL), `mcp_tool` (call a tool on a
configured MCP server) -- is wired. A settings.json/hooks.json entry for a
name Claude Code also recognizes but this build doesn't fire yet
(`ElicitationRequest`, `ElicitationResponse` -- see `hooks.py`'s own
`NOT_EMITTED_V1`) parses fine and is silently never triggered, rather than
erroring.

**Skills and custom commands**: discovered from both user and project
directories exactly like `claude`; a skill's/command's body can reference
`@path` (a local file, read the same way a model's own Read call would) and
`@server:resource` (an MCP server's resource, read via `resources/read`) --
both are appended as a separate context snapshot, never inlined into the
submitted text. An MCP server's own prompts show up as `/mcp__<server>__
<prompt>` slash commands automatically.

**MCP**: stdio/http/sse transports, user/project/local/managed/plugin
scopes, the `.mcp.json` first-time-approval flow, always-load servers,
`ToolSearch` for a large/deferred tool set, resources and prompts
(`ListMcpResourcesTool`/`ReadMcpResourceTool`, `@server:resource` mentions,
`/mcp__server__prompt`), `/mcp` to inspect/reconnect mid-session. **Lazy by
default**: a server connects the first time one of its tools is actually
called, or when `/mcp` reconnects it -- `alwaysLoad` servers and one marked
`"mcpLazy": false` (per-server, or globally via a top-level `"mcpLazy":
false` in `settings.json`) connect eagerly at session start instead. A
per-server cache (`~/.halo/mcp/tools-cache/`) keeps a lazy server's
tool names/descriptions searchable/preloadable even with zero live
connections -- the status bar's "MCP n/m" only counts real connections, so
a fresh session typically starts "MCP 0/m" and climbs as tools are used;
`doctor`/`mcp list`/`/mcp` show a `cached` (not yet connected, but known)
state alongside the usual connected/failed/pending ones.

**Browser**: `--chrome` (the claude-in-chrome extension's native-messaging
bridge) and `--playwright`/`--playwright-cdp`/`--playwright-headless`
(a real Chromium/Chrome/Brave via Playwright); a screenshot from either one
shows up as its own tool card in the TUI transcript. In a terminal that
speaks the kitty graphics protocol (kitty, WezTerm, Ghostty, foot) or sixel
(detected live; tmux needs `allow-passthrough on` first) it renders inline,
downscaled to a bounded size; everywhere else it's captioned with its media
type, real dimensions and size (e.g. "image/png, 1280x800, 84.2 KB"), same
as before -- `images: "inline"|"caption"|"off"` in `~/.halo/
config.json` (default `"inline"`) or `--no-inline-images` forces the plain
caption. The real image block is still what the model itself sees (subject
to the same vision/size gate as any other image) regardless of how it's
displayed to you.

**Images/vision**: Read returns a real `image` content block (not just a
path string) for png/jpg/gif/webp when the active model's profile says it
supports vision, resized/downscaled to at most 1568px and 5MB (omitted with
a plain note instead when it can't be brought under that even after
resizing, or when Pillow isn't installed at all -- the `vision` extra,
`pip install --user -e '.[vision]'` (or `uv tool install --editable
'.[vision]'`) from the checkout, same as every other install command in
this doc, is optional, never required); an MCP
tool's own image results get the same treatment. `@path` mentions to an
image file (TUI or a skill/command body) and `--file PATH [PATH ...]`
(a local path -- see `halo --help`; Claude Code's own `file_id:
relative_path` cloud-resource form isn't backed by anything in a
standalone harness and gets a clear notice instead of pretending to work)
both attach the same way.

**Background jobs**: `Bash(run_in_background: true)`, and a foreground
command that outruns its timeout is moved to the background instead of
being killed (Claude Code's own behavior) -- `BashOutput`/`TaskStop` poll/
kill a job by its shell id, completion is delivered as a notice at the next
turn (never silently lost), `/tasks` lists what's running, and every job is
killed when the session quits.

## Sessions

`-c`/`--continue` resumes the most recent session for the current
directory (in print mode, with no earlier session, it exits 2 with a message
rather than starting a new one); `-r`/`--resume [ID]` resumes a specific one, or opens a picker
with a live fuzzy text filter (title, first prompt, cwd, model -- `/resume
<text>` in the TUI opens it pre-filtered) when given no id at all; `-r
<text>` on the command line resumes the one session that text uniquely
matches, or (print mode) lists the ambiguous candidates instead of
silently guessing, or (interactive) opens that same picker pre-filtered by
`<text>`; `--fork-session` continues from one without overwriting it;
`-n`/`--name` labels a session. `/rewind` (and the TUI's undo) restores both the
conversation log and any file a Write/Edit/NotebookEdit touched, via a
shadow-copy mechanism, plus a Bash command's own file changes in a git repo
cwd (a `git status` diff before and after the command catches both a
brand-new file and a pre-existing tracked file the command modified; a
non-git cwd, a file already dirty before the command, and a rename/copy are
the documented limits -- see `tui/dispatch.py`'s `_maybe_record_shadow_step`/
`_bash_shadow_after_worker`). Snapshots are taken on one background worker
(never the UI thread), and `/undo`/`/redo`/`/rewind` wait for any still
queued before they restore. Auto-compaction
triggers well before the model's real context ceiling (an 80%-of-usable
default, floored so a small-context open-weight model still gets a
sensible trigger point instead of ~0), summarizing older turns while
keeping a verbatim recent tail; `count_tokens` is used for the trigger
instead of an estimate wherever the route actually supports it (Databricks/
Anthropic passthrough), falling back to an estimate otherwise.

**Recall over memory and past sessions.** `halo recall <query>` (and
`/recall` in the TUI) is semantic search over this machine's auto-memory
topics and session logs on a local embedding model (`docs/COMMANDS.md`).
`halo recall --fleet <query>` (and `/recall --fleet`, Studio's recall box
with its Fleet switch, 3.1.2.0 R3) asks the hub this machine runs or joined
to fan the query out to every online harness, each answering from its own
index; the hits are merged by score and shown with their harness, so a box
can draw on what another already learned without re-learning it. A member
keeps out with `fleet.recall.share: false` ([FLEET.md](FLEET.md) "Recall
across the fleet").

## Print mode

```sh
halo -p --permission-mode auto "reply pong"
halo -p --permission-mode auto --output-format json "..."
halo -p --permission-mode auto --output-format stream-json --input-format stream-json < turns.jsonl
```

`--output-format text|json|stream-json`, `--input-format text|stream-json`
(one turn per line, read incrementally so an SDK-style client that waits
for each turn's result before sending the next one never deadlocks),
`--include-partial-messages`, `--max-turns`, `--max-budget-usd`,
`--json-schema` (structured final output), `--replay-user-messages`. Exit
code is the last turn's; a background job still running when a single-
prompt `-p` call ends gets its completion notice printed before the
process exits rather than dropped.

**Permission mode for unattended runs**: `-p` has no terminal to ask a
permission question on, so the ordinary interactive default (`default`:
asks before Bash/Edit/Write/...) denies every one of those calls outright
-- a real model-quality finding (telemetry: a chunk of print-mode Bash
calls fail as `denied_by_rule` for exactly this reason). Pass
`--permission-mode auto` (no prompts, everything allowed except your own
deny/ask rules) for a script/CI/cron run that should actually DO things;
`acceptEdits`/`bypassPermissions`/`dontAsk` are the other non-interactive
choices when you want different rules (see `halo --help`).

`halo export --sanitize` and `halo stats` are headless
versions of the TUI's own `/export`/`/stats` slash commands -- the former
redacts API keys/tokens/secrets from a session log before handing it to
someone else, the latter aggregates turn/cost/token stats across sessions.

## Code review

`/review` (TUI) and `halo review` (print mode) review a change the way Claude
Code's `/code-review` does: five read-only reviewers run in parallel (one each
for correctness, security, performance, tests and docs-consistency), a judge
checks every finding against the code, and you get a ranked list with a
verdict on each (`CONFIRMED`, `PLAUSIBLE`; `DISMISSED` ones are dropped).

```sh
halo review                          # this branch against its base
halo review '#123'                   # a pull request (needs gh)
halo review main..feature --level high --dimensions security,correctness
halo review src/ --json              # files as they are, JSON out
halo review --fix                    # fix every CONFIRMED finding in the working tree
```

In the TUI the reviewers show up in `/tasks` while they work and the result
lands as one card per finding; click a card's `file:line` to copy it, press
Enter to unfold its failure scenario, Esc to abort. A review reports and never
gates anything; `--fix` edits the working tree but never commits. The
`code-review` team template (`halo teams use code-review`) maps the `reviewer`,
`judge` and `coder` roles so each part can run on its own model. Details,
the JSON shape and cost notes: [REVIEW.md](REVIEW.md).

## Telemetry and `/improve`

`halo stats --models [--tools] [--since 7d|30d|all] [--all-projects]
[--session ID] [--json]` (and `/stats --models` in the TUI, off the UI
thread) aggregates per-model/provider and per-tool counters -- tokens,
cost, avg ttft/latency, retries, overflows, tool error rates, repair-layer
hit rates, edit failures -- from the existing session logs; nothing here
adds a model-visible field. `doctor` shows the sessions count, stats-cache
age and the active `/improve` config.

`/improve` is human-gated self-improvement: it clusters recent failures
(repeated tool errors, repair-layer hits, loop-breaker trips, user
corrections, Read ENOENT, a recurring tool sequence), drafts candidate
memory notes / `.claude/rules/*.md` entries / skills with ONE model call,
and reviews them one card at a time -- `a` apply, `e` edit in
`$VISUAL`/`$EDITOR` then apply, `s` skip, `d` dismiss forever, `q` stop.
Nothing is written without that approval (or an explicit headless
`halo improve --apply FILE#ID`); provenance (source sessions,
evidence count, drafting model, whether an excerpt came from tool output)
is shown on the card, never used to block anything. `halo improve
[--since] [--all-projects] [--json]` prints/saves candidates without
applying; `-p` sessions never draft or write on their own. Configured via
`~/.halo/config.json`'s `improve` key, e.g. `halo config set
improve.model or:deepseek/deepseek-v4-flash`.

## Troubleshooting

- **Reporting a problem**: `halo bugreport` (or `/bugreport` in a live
  session) writes one redacted diagnostic report -- version, environment,
  provider/route/permission-mode state, MCP servers, catalog ages, the last
  turn's own timeline, and recent session events/log lines, with every
  secret-shaped value stripped -- to `~/.halo/bugreports/`, "one paste
  instead of screenshots" (`--copy` puts it on the clipboard too). `halo
  timeline`/`/timeline` shows just the per-turn request/tool/hook/
  permission-wait/compaction timing on its own, live with `--debug`. See
  `docs/COMMANDS.md` for both commands' full flags.
- **VPN hint**: any Databricks connect failure (`doctor --work`, `models
  --refresh`, or a live request) names the VPN as the likely cause.
- **`externally-managed-environment` from pip**: see INSTALL.md's PEP 668
  note; `uv tool install --editable .` sidesteps it entirely.
- **`halo: command not found` right after installing**: `~/.local/
  bin` isn't on PATH yet for a non-login shell -- see INSTALL.md.
- **Bare `halo` exits 2 immediately**: expected outside a real
  terminal (piped input, cron, a subprocess with no tty) -- use `-p`.
- **A tool isn't visible to the model**: check whether it's a deferred MCP
  tool not yet referenced this conversation (`ToolSearch` finds it by
  name/description) or excluded by `--tools`/a deny rule.
- **`--file file_id:relative_path` prints a notice and does nothing**:
  expected -- that's Claude Code's claude.ai-hosted file-resource form,
  which this standalone harness has no backing store for; a local path
  works directly.
- **A flag prints a `not yet` notice**: that flag is parsed (never an
  argparse error) but its feature isn't built yet; `--ide`, `--worktree`,
  `--remote-control`, `--teleport` and a handful of others are intentionally
  still in that state -- see `halo_harness/cli.py`'s `_NOT_YET_FLAGS`.
- **Where to look**: session logs under `~/.halo/sessions/`;
  `halo doctor` / `doctor --work` for environment issues;
  `--verbose` for a running commentary of intermediate model
  calls/tool calls on stderr in print mode; `-d`/`--debug` (or
  `--debug-file PATH`) for DEBUG-level file logging of the whole run (TUI
  or print mode) -- defaults to `~/.halo/bridge.log` (rotating, secrets
  redacted), `--debug-file` picks a different path.

## Security posture

- No local server/open port in the harness itself for the OpenRouter/
  Databricks/`ant:` routes -- a direct in-process HTTP client, not a proxy
  something else connects to. (`halo proxy` is the one exception, see
  below, security posture unchanged from `claude-bridge`'s.)
- Credentials come from the environment, the settings chain, or
  `~/.databrickscfg`/`ucode-settings.json`; they're never written to the
  repo, a command line, or committed config. `halo --config`-style
  output and logs redact keys/tokens/auth headers.
- The permission engine is pure grammar (see Permissions above) -- no
  hidden allow-list, no "trusted command" special-casing beyond what a
  rule/mode explicitly says.
- `export --sanitize` exists specifically for handing a session log to
  someone else without also handing them your API keys.

## Tests

```sh
python tests/run_all.py; echo exit=$?      # the core suite (agent loop, tools, config, MCP, permissions, ...)
python test_tui.py; echo exit=$?           # the TUI suite (Textual pilots + SVG snapshots)
python test_bridge.py; echo exit=$?        # the claude-bridge proxy's own black-box suite
```

All three are exercised on both Windows and WSL/Linux every milestone (see
INSTALL.md's "Cross-checking on WSL" recipe) -- Kali Linux being the actual
target, not an afterthought. Suites use mock upstreams throughout; no live
network call happens as part of `python tests/run_all.py` itself.

The README's pictures are a test surface too (`tools/capture_screens.py --check`, see [MEDIA.md](MEDIA.md)), and so is its screenshot gallery: `python
scripts/screenshots.py` drives the real TUI with Textual pilots over
fixture data (fixed seed, frozen clock, `BRIDGE_TEST_HOME` scoped to a
scratch dir) and writes one SVG per scene under `docs/screenshots/`;
`tests/test_screenshots.py` re-runs it and fails if the committed SVGs
are not byte-identical to a fresh render. The wordmark on `halo
--version`, in the launch intro, in the README's banner block and in the
hero image comes from one module, `halo_harness/banner.py` (the block art
on a UTF-8 stream, a plain-ASCII form on a stream that cannot encode
block elements); `tests/test_intro_lines.py` and
`tests/test_front_page_media.py` pin every copy against it.

## Proxy mode (`claude-bridge` / `halo proxy`)

Before halo became its own harness, this repo was `claude-bridge`: a
single-file HTTP proxy (`bridge.py`, stdlib only) that sits in front of the
REAL `claude` binary and translates its Anthropic-Messages-API calls to
OpenRouter or Databricks, leaving `claude`'s own subscription, `CLAUDE.md`,
settings, memory, MCP servers, skills, hooks and permissions completely
untouched -- it only intercepts the one HTTP call `claude` makes to its
model. That still exists, unchanged, as `halo proxy` (equivalently,
`python bridge.py ...` directly):

```sh
halo proxy launch --model or:deepseek/deepseek-v3.2 -p "reply pong"
halo proxy --probe        # outbound reachability check for both providers
halo proxy --config       # resolved configuration as JSON, secrets redacted
halo proxy --stop         # shut down a running proxy server
```

Use this mode specifically when you want to keep using the real `claude`
CLI itself (its own update cadence, its own bug-for-bug behavior) with a
non-Anthropic model underneath, rather than halo's own agent loop.
State lives in `~/.claude-bridge/` (`BRIDGE_STATE_DIR` to override); loopback-
only bind, bearer-token-gated, redacted logs -- see `docs/harness/` for the
proxy's own historical design notes if you need the low-level details
(request translation, the 128-tool cap, context-overflow rewriting, etc.),
which are unchanged from before this became a standalone harness.
