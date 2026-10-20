# Commands: `halo` output, prompt, settings, budget, browser, MCP and image flags

Read this when you change what `halo` prints or reads, its system prompt, settings, budget, browser, MCP or images.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo` flags: output, prompt, settings, budget, browser, MCP and images

### Output & input format flags

#### `--output-format {text,json,stream-json}`
What: `text` (default) prints the final reply only (or, with `--verbose`,
every intermediate message too, reasoning dimmed); `json` prints one
result object at the end (`session_id`, `num_turns`, `usage`,
`total_cost_usd`, `permission_denials`, `structured_output`, ...); `stream-json`
emits one JSON line per event (`init`, `assistant`/`user` messages, a final
`result`) -- Claude Code's own SDK wire shape.
```sh
halo --demo -p --output-format stream-json
```

#### `--input-format {text,stream-json}`
What: `text` (default) takes one prompt (positional or stdin); `stream-json`
reads one JSON turn object per stdin line, incrementally -- so an SDK-style
caller that waits for each turn's `result` before writing the next line
never deadlocks.

#### `--include-partial-messages`
What: with `--output-format stream-json`, also emits a `stream_event` line
per text/thinking delta (not just the final assembled message).

#### `-d`, `--debug [FILTER]`
What: turns on DEBUG file logging for the whole run, TUI or print mode. The
log goes to `~/.halo/bridge.log` (rotating, secrets redacted) and the
path is printed once on stderr as `halo: debug log -> <path>`. The
optional FILTER value is accepted for Claude Code parity and ignored:
everything is logged. Use it when the TUI misbehaves or a route fails, then
send the last lines of the log.
Reads: nothing new. Writes: `~/.halo/bridge.log`.
```sh
halo --debug
tail -60 ~/.halo/bridge.log
```

#### `--debug-file PATH`
What: same as `--debug`, but the log is written to `PATH` (parent
directories are created) instead of the state directory.
```sh
halo --debug-file /tmp/halo-debug.log -p "reply with the single word pong"
```

#### `--verbose`
What: in text mode, also prints every intermediate assistant message this
turn produced (dimmed) on the way to the final reply, plus reasoning; a
running commentary of model/tool calls on stderr.

#### `--json-schema SCHEMA`
What: appends the schema to the system prompt as an instruction and, on
success, re-parses the final reply text as JSON into the `json` result
object's `structured_output` field (`null` if the reply wasn't valid JSON --
no separate schema-validation library is used, this only checks "is it
JSON at all").

#### `--replay-user-messages`
What: mirrors every stdin line back out (stream-json modes) once actually
consumed; rarely needed directly.

### System prompt flags

#### `--system-prompt PROMPT`, `--system-prompt-file FILE`
What: **replaces** the built-in system prompt entirely (the harness
self-description, tool guidance, family notation -- see
`docs/ARCHITECTURE.md`) with this text. The `-file` form reads it from disk
(UTF-8); if both are given, the inline value wins.

#### `--append-system-prompt TEXT`, `--append-system-prompt-file FILE`
What: adds one more section after the built-in system prompt instead of
replacing it -- the common case (skills/commands/agents use the same
mechanism internally). Both may be combined with each other (file content is
appended after the inline text).

### Settings & permissions flags

#### `--settings JSON_OR_PATH`
What: one more settings layer, highest precedence except `policySettings`
(managed) -- a literal JSON string, or a path to a JSON file in the same
shape as `.claude/settings.json`. See `docs/CONFIG.md`'s precedence table.

#### `--setting-sources SOURCES`
What: a comma list restricting which of `user,project,local` settings layers
are read at all (managed/policy and `--settings` itself are never affected).
```sh
halo -p --setting-sources user "hi"
```

#### `--permission-mode {default,acceptEdits,plan,auto,dontAsk,bypassPermissions,manual}`
What: the session's starting permission mode (`manual` is a display alias
for `default`). See `docs/ARCHITECTURE.md`'s permissions section for exactly
what each mode allows/asks/denies -- there is no classifier or heuristic
layered on top of any of them.
```sh
halo -p --permission-mode auto "hi"
```

#### `--dangerously-skip-permissions`
What: shorthand for `--permission-mode bypassPermissions` (allow everything
not matched by an explicit deny rule).

#### `--allowedTools TOOLS` / `--allowed-tools`, `--disallowedTools TOOLS` / `--disallowed-tools`
What: a space- or comma-separated list of permission-rule-shaped strings
(`Bash(git *)`, `mcp__server`, a bare tool name, ...), merged into the
session's allow/deny rule set at the same precedence a settings-file rule of
the same kind would have.

#### `--tools TOOLS`
What: restricts the session's tool catalog itself to this comma/space list
of tool names (a tool not in this list is never offered to the model at
all, unlike `--disallowedTools`, which still shows the tool but denies
calling it).

#### `--bare`
What: skips CLAUDE.md/AGENTS.md/rules discovery, memory, hooks that read
those files, and `/improve`'s drafting -- a minimal-context session, mirrors
Claude Code's own `--bare` intent.

#### `--disable-slash-commands`
What: turns off `/name` parsing in this session entirely -- a line starting
with `/` is sent to the model as plain text instead.

### Budget flags

#### `--max-turns MAX_TURNS`
What: caps the number of *model calls* (not tool calls) a single `turn()`
may make before the harness forces a wrap-up reply ("MAXIMUM STEPS
REACHED") and ends the turn. When that wrap-up request overflows the
context window, the harness compacts and retries it once; if compaction
cannot free room the turn ends with a context-window error. Opt-in: with no flag there is NO cap, in the
TUI and in print mode alike (Claude Code parity; before 2.0.3 a default of
50 stopped long interactive tasks mid-stream). A non-positive value also
means no cap. The identical-call breaker and the cost/context meters stay
on regardless.

#### `--max-budget-usd MAX_BUDGET_USD`
What: stops the session (mid-turn, at the next safe point) once cumulative
cost meets or exceeds this many US dollars -- a route with no real per-token
pricing (Databricks) never counts toward it.

### Browser flags

#### `--chrome`, `--no-chrome`
What: `--chrome` starts the claude-in-chrome extension's native-messaging
bridge as a dynamic MCP server for this session (screenshots, page
reading/interaction tools); `--no-chrome` forces it off even if a settings
file would otherwise enable it by default. `halo doctor` reports
whether the native host is registered at all.

#### `--playwright`, `--playwright-cdp ENDPOINT`, `--playwright-headless`
What: `--playwright` drives a real local Chromium/Chrome/Brave via
Playwright as a dynamic MCP server instead; `--playwright-cdp` attaches to
an already-running browser's DevTools Protocol endpoint instead of
launching a new one; `--playwright-headless` runs without a visible window.
Needs `node`/`npx` on PATH (`halo doctor` checks for both).

### MCP flags

#### `--mcp-config CONFIG [CONFIG ...]`
What: one or more extra MCP server configs for this run only -- each value
is a JSON string or a path to a JSON file, `{"mcpServers": {...}}` or a bare
`{name: {...}}` map. Same precedence tier as `--chrome`/`--playwright`'s own
dynamic servers.

#### `--strict-mcp-config`
What: use *only* `--mcp-config` (plus `--chrome`/`--playwright` if also
given) -- every other source (`.mcp.json`, `~/.claude.json`, plugins) is
skipped for this run.
```sh
halo -p --strict-mcp-config --mcp-config '{"mcpServers":{}}' "hi"
```

### Image flags

#### `--image PATH`
What: attaches an existing image file (`.png`/`.jpg`/`.jpeg`/`.gif`/
`.webp`) to the one turn `-p`/`--print` sends -- repeatable (several
`--image` flags attach several images to the same turn). Claude Code
parity; the TUI's own equivalent is Ctrl+V/Shift+Insert (a real clipboard
image), `/paste <path>`, or dropping a path into the prompt. A path that
doesn't exist, or isn't one of those five extensions, is a clean
`halo: ...` stderr line and exit 2, never a provider error partway
through the turn. A model whose catalog row says it has no vision gets
one notice instead and the turn still runs, with the saved path
mentioned in place of the image.

```sh
halo -p --image ./screenshot.png "what's in this image?"
```

#### `--no-inline-images`
What: forces the plain type/size/dimensions caption for every image tool
result this run, same as `images: "caption"` in `~/.halo/config.json`
but scoped to one invocation (TUI only -- print mode has no inline-image
concept to disable).
