# Architecture: permissions, hooks and MCP

Read this when you change permission rules and modes, the hooks protocol, or how MCP servers start and cache.

Part of [Architecture](ARCHITECTURE.md), which lists every part.

## Permissions: grammar, modes, and what "auto" means here

`permissions.py::PermissionEngine.decide(tool_name, tool_input, tool)` is
grammar and modes **only** -- the owner's explicit "no cyber blocks" decision:
there is no classifier, no destructive-command list, no protected-path
list, and no security-tool flagging anywhere in this engine or the tool
layer. `Tool.is_read_only`/`is_destructive` exist purely for the read-only
concurrency pool and a tool card's own display; the permission engine never
reads either one to gate or auto-deny anything.

`decide()`'s own order, every call, every mode:

1. A `deny` rule match → deny, always (checked before anything else, in
   every mode including `bypassPermissions`).
2. Not in `bypassPermissions`: an `ask` rule match → resolve as an ask
   (interactive: a real card; print mode: a clean deny naming what would
   have been asked, since there is no one to answer it).
3. `auto` or `bypassPermissions` mode, nothing denied/asked above → **allow
   outright**. This is the entire definition of "auto mode": allow
   everything not matched by the user's own explicit deny/ask rule. No
   other logic runs.
4. An `allow` rule match → allow.
5. Otherwise, the **mode table** below decides.

| Category | `default` | `acceptEdits` | `plan` | `dontAsk` |
|---|---|---|---|---|
| Read inside a working dir | allow | allow | allow | allow |
| Read outside a working dir | ask | ask | ask | deny |
| Read-only Bash/PowerShell | allow | allow | allow | allow |
| A read tool (`read_tool`, below) | allow | allow | allow | allow |
| The web reads: WebFetch, WebSearch (`web_read`) | ask | ask | allow | deny |
| Edit/Write inside a working dir | ask | allow | deny | deny |
| Everything else | ask | ask | deny | deny |

(`auto` and `bypassPermissions` never consult this table at all -- step 3
above already resolved them.) The **read tools** (3.2.2.0 R4,
`READ_TOOL_NAMES` in permissions.py) are LS, BashOutput, ToolSearch, Skill,
knowledge_search, recall, ListMcpResourcesTool, ReadMcpResourceTool,
TaskList, and every MCP tool whose server marks it `readOnlyHint` in its
`tools/list` annotations (`McpTool.read_only`, kept in the per-server tools
cache too; a server that sends no annotations leaves its tools in
"Everything else"). Read, Glob and Grep keep their own path-aware rows. A handful of tools are categorized outside
this table entirely, in every mode: `TodoWrite`/`ToolSearch` (no side
effects requiring permission), `AskUserQuestion` (allowed everywhere except
`dontAsk`, where it errors instead of hanging), `Agent`/`Task` (spawning is
never mode-gated -- the depth-1 and concurrency caps are the real
guardrail), and `EnterPlanMode` in print mode (always allowed -- it only
ever *narrows* what happens next). Plan mode additionally always allows
Write/Edit on exactly the one active plan file, regardless of the table
above.

**Plan mode lets every read through and refuses writes in plain words**
(3.2.2.0 R4). Its write check runs before `allow` rules (an allow rule for
`Bash(npm:*)` does not let `npm install` run in plan mode): Edit/Write
outside the plan file, a Bash or PowerShell command that is not read-only,
and any tool in "Everything else" (an MCP tool without `readOnlyHint`
included) are refused with one text that says what the call does and the
way out:

    plan mode: Write writes; research with the read tools and the web, then call
    ExitPlanMode with the plan (Shift+Tab or /plan off leaves plan mode)

(`plan mode: this Bash command writes; ...` for Bash, the tool's own name
for the rest -- `plan_mode_refusal` in permissions.py). Every read runs:
Read/Glob/Grep, read-only Bash, the read tools above, WebFetch and
WebSearch. The model is told when plan mode starts and ends, however it
was switched (agent/mode_notice.py): the same note EnterPlanMode gives,
with the plan file's path, before the next model call after Shift+Tab,
`/plan on`, config or `--permission-mode plan`; "Plan mode is off:
implement the plan." after Shift+Tab, `/plan off` or the plan card's
approve; and each turn carries one line naming the current mode
(`permission mode: plan (read-only; call ExitPlanMode with the plan)`).

Rule grammar (`parse_rule`) matches Claude Code's own exactly: `Tool` (bare,
the whole tool), `Tool(content)` (exact/prefix/glob string, or a `path`
value for a path-taking tool, or `domain:` for WebFetch), `Bash(cmd:*)`-
style glob content with real shell-segment-aware matching (a read-only
allowlist recognizes common git/gh read subcommands so `git status`/`git
log`/etc. never need an explicit rule), `mcp__server`/`mcp__server__tool`/
`mcp__server__*`, `Agent(subagent_type)`, `Skill(name)`, and a
deny/ask-only `Tool(param:value)` form. Rules are assembled once per
session (`build_rules_from_settings`) from the merged settings chain (see
`docs/CONFIG.md`) plus `--allowedTools`/`--disallowedTools` plus a session's
own interactively-granted rules; only `deny`/`ask` rules from an *untrusted*
project/local settings layer survive -- an untrusted layer's own `allow`
entries are dropped before the engine is even built.

Seven mode **names** exist (`default`/`manual` is a display alias for the
same mode, `acceptEdits`, `plan`, `dontAsk`, `auto`, `bypassPermissions`);
`Shift+Tab` cycles the first four of these in the TUI.

**`decide()`'s outcome is not the last word -- the user's own hooks still
run after it, in every mode.** `PreToolUse` (and, on an `ask` outcome,
`PermissionRequest`) fires for every call regardless of what `decide()` just
returned, including a call `auto`/`bypassPermissions` already allowed
outright -- a `PreToolUse` hook can still block the call, rewrite its input
(`decide()` is then re-run against the rewrite, so a rewritten call can't
silently dodge a rule that now matches it), or flip the decision itself. So
the precise, complete statement of what `auto` mode allows is: **everything
not matched by the user's own deny/ask rule *or* blocked by the user's own
hook** -- never a built-in judgment call, but a hook the user configured
themselves is exactly as much "the user's own rule" as a permission rule
is.

## Hooks protocol

`hooks.py` implements Claude Code's hook protocol verbatim -- matcher +
`if`-rule filtering, five handler types run in parallel, and the
`Stop`/`SessionEnd` special cases -- with, again, no safety heuristics of
its own: a hook is entirely the user's own gate.

- **Handler types**: `command` (a shell command; `shell: "bash"` forces
  real bash even on POSIX, where the unmarked default is `/bin/sh`),
  `http` (a URL call), `mcp_tool` (calls a tool on a configured MCP
  server), `prompt` (a small-model call, template `$ARGUMENTS` → the JSON
  payload), `agent` (same as `prompt`, semantically -- both are
  "informational only" about which model runs it, always the session's
  small model).
- **A plugin's `${CLAUDE_PLUGIN_ROOT}`** (3.2.1.0 R4): a plugin's (or a
  pack's) `hooks/hooks.json` is filled per field. In a `command` hook's
  shell `command` the path goes in as the hook's shell reads it: forward
  slashes on Windows (Git Bash runs it, and would eat a backslash), quoted
  when it holds a space or another character the shell reads (bare:
  `sh ${CLAUDE_PLUGIN_ROOT}/run.sh` from `D:\Tools\My Packs\p` is
  `sh 'D:/Tools/My Packs/p'/run.sh`; on Linux from `/opt/packs/p` it is
  `sh /opt/packs/p/run.sh`), and escaped instead inside the command's own
  `"..."` or `'...'`. `shell: "powershell"`, the exec form's `args` (no
  shell), every other field and the child's `CLAUDE_PLUGIN_ROOT` env var
  get the path as it is. Both forms run on every platform; the exec form
  is the recommended one (`packs/interpreter.py` `expand_hook`).
- **Matcher**: omitted/`""`/`"*"` → matches everything; a
  `^[A-Za-z0-9_,|-]*$`-shaped string → an exact name list split on `,`/`|`;
  anything else → an unanchored regex (an invalid one skips that hook with
  a logged warning, never crashes).
- **`if`**: reuses `permissions.py`'s own rule grammar/matching, so a
  hook's own conditional gate is the identical syntax to a `settings.json`
  permission rule.
- **Events actually fired**: `SessionStart`/`SessionEnd`,
  `UserPromptSubmit`, `PreToolUse`/`PostToolUse`(`Failure`),
  `PostToolBatch`, `PermissionRequest`/`PermissionDenied`,
  `Stop`/`SubagentStart`/`SubagentStop`, `PreCompact`/`PostCompact`, and (W4a/
  W5) `TaskCreated`/`TaskCompleted`, `FileChanged`, `CwdChanged`,
  `DirectoryAdded`, `ConfigChange`, `InstructionsLoaded`, `MessageDisplay`,
  `Setup`, `WorktreeCreated`/`WorktreeRemoved`,
  `PreModelSwitch`/`PostModelSwitch`, `UserPromptExpansion`, `StopFailure`.
  A configured hook for an event Claude Code also defines but this build
  doesn't fire yet (`ElicitationRequest`, `ElicitationResponse` --
  `hooks.NOT_EMITTED_V1`'s full set) parses fine and is silently never
  triggered, rather than erroring.
- **Combining outcomes**: several hooks matching the same event run
  concurrently; their outcomes combine as `deny > defer > ask > allow` for
  the permission decision, `additional_context` concatenated, the *last*
  `updated_input`/`set_mode` wins (well-defined since result order follows
  match order, not completion order).
- **`Stop`/`SubagentStop`**: a consecutive-block cap
  (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`, default 8) force-ends the turn with an
  explanatory system message once a hook has blocked that many times in a
  row, so a misbehaving Stop hook can never wedge a session forever.
- **`SessionEnd`**: a real time budget (default 1.5s, raised to the largest
  matched hook's own `timeout` up to a 60s cap, or
  `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS` outright) -- every matched hook
  runs concurrently within that one shared window, never sequentially.
- **Child environment**: every hook subprocess gets `tool_child_env()`-
  stripped env (no provider API keys) plus `CLAUDE_PROJECT_DIR`/
  `CLAUDE_PLUGIN_ROOT`/`CLAUDE_EFFORT`/`CLAUDE_ENV_FILE` (for the four
  events whose whole point is exporting more env for later Bash calls to
  pick up: `SessionStart`, and three not-yet-emitted events it's ready for).

## MCP: scopes, lazy start, cache, plugin servers

`mcp/manager.py::resolve_server_configs()` assembles the final `{name:
McpServerConfig}` map, first-name-wins, in this exact order: `managed-
mcp.json` (if present at all, **exclusive** -- every other source is
skipped) → else `--mcp-config` (repeatable) and this run's own `--chrome`/
`--playwright` dynamic entries, same precedence tier → (stop here under
`--strict-mcp-config`) → local `projects[cwd].mcpServers` in
`~/.claude.json` → `<cwd>/.mcp.json` (subject to `.mcp.json`-server-only
approval/`disabledMcpjsonServers`) → user `mcpServers` in `~/.claude.json`
→ installed-plugin-provided servers (lowest precedence). Managed
`allowedMcpServers`/`deniedMcpServers` and a project's own
`disabledMcpServers` (no "json") are applied last, on every path,
regardless of which tier a name came from. Every surviving entry then gets
`${VAR}`/`${VAR:-default}` expansion against the session's effective
environment.

**Lazy by default** (H13): a server connects only the first time one of its
tools is actually called, or when `/mcp` explicitly reconnects it --
`alwaysLoad` servers and one marked `"mcpLazy": false` (per-server, or
globally via a top-level `"mcpLazy": false` in `settings.json`) connect
eagerly at session start instead. A per-server cache under
`~/.halo/mcp/tools-cache/<server>.json`, keyed by a hash of the
server's own identity-relevant config fields (command/args/env/url/
headers -- never `cwd`/`timeout`/scope, which don't change what
`tools/list` returns), keeps a lazy server's tool names/descriptions known
-- and therefore searchable/preloadable by `ToolSearch` -- with **zero live
connections**. A cache hit seeds a `"cached"` handle state directly; a miss
(first run, or the identity-relevant config changed) connects that server
for real, once, to learn its tools and write the cache. Every server
needing a real first-time connect does so **concurrently**, one shared
timeout window for the whole batch, never one-at-a-time.

Handle states: `pending` → `pending_approval` (an unapproved `.mcp.json`
server) → `cached` → `connecting` → `connected` | `failed` | `needs_auth` |
`closed`. The status bar's "MCP n/m" counts only real connections, so a
fresh session with several lazy servers typically starts at "MCP 0/m" and
climbs as tools are actually used.

Plugin-provided servers (`config/plugins.py`) are discovered from
`~/.claude/plugins/installed_plugins.json` (both the V1 single-dict and the
real V2 per-scope-array manifest shapes), each plugin's own `.mcp.json` or
`.claude-plugin/plugin.json`, with `${CLAUDE_PLUGIN_ROOT}` expanded to that
one plugin's own install directory. A discovered plugin server is named
`plugin_<plugin>_<server>` on the wire (`mcp__plugin_<plugin>_<server>__
<tool>`), sanitized the same way any other server name is -- nothing
downstream needs to know a tool came from a plugin at all.
