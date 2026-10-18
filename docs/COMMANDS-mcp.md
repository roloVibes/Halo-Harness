# Commands: MCP servers and connectors

Read this when you add, list, repair or log in to MCP servers and claude.ai connectors.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo mcp`

Inspect and edit MCP server configuration -- reads/writes the exact same
`~/.claude.json`/`.mcp.json` files `claude mcp add`/`claude mcp list` do, so
a server either CLI adds is immediately visible to the other.

```sh
halo mcp --help
```
```
Usage: halo mcp [options] [command]

Commands:
  list                    List configured MCP servers with live health
  get <name>              Get details about an MCP server
  add [options] <name> <commandOrUrl> [args...]  Add a server
  add-json <name> <json>  Add a server via JSON
  remove <name>           Remove a server
  add-from-claude-desktop Import MCP servers from Claude Desktop's config
  reset-project-choices   Reset approved project-scoped (.mcp.json) servers
  serve                   Expose halo's own built-in tools as an MCP server
  login <name>            OAuth-authenticate a remote MCP server
  logout <name>           Clear stored OAuth credentials for a server
  fix <name> [--apply]    Diagnose (and, with --apply, fix) a failed server
  test <name>             A tools/list round trip with timing
```

### `mcp list [--cwd DIR] [--refresh]`
Builds a real (temporary) MCP manager against the resolved config and prints
one line per server, same format as the real `claude` binary:
`<name>: <command> <args> - <status>`, or `<name>: <url> (HTTP|SSE) - <status>`.
Status labels: `✔ Connected`, `✗ Failed to connect`, `! Needs authentication`,
`⏸ Pending approval`, `- Not configured`, `! Connected · tools fetch failed`,
and halo's own `◐ Cached (connects on first use)` for a lazy server
that hasn't connected yet (Claude Code has no lazy-start concept, so there is
no binary-derived wording for this one state). A `failed`/`needs_auth`/
`disabled` line also names WHY in parentheses (command not found on PATH,
connection refused on host:port, or the reason a transport is disabled).

Before the health check, `mcp list` always explains what it searched:
every scope (user `~/.claude.json`, project-local, this directory's own
`.mcp.json`, plugins, managed) with its own count, another directory's
`.mcp.json` when your own `~/.claude.json` history remembers one, and the
claude.ai connectors `claude` itself reports (see below) -- never a bare
"0 servers". `--refresh` forces a fresh connectors discovery first,
ignoring the `~/.halo/mcp/connectors.json` cache; without it, an EMPTY
cache still gets one bounded (20s) synchronous discovery when eligible
("connector cold start" -- a fresh box's first `mcp list` shows real
connectors, not an empty cache a background worker hadn't gotten to yet),
and an eligible-but-still-empty result says so explicitly rather than
staying silent.
```sh
halo mcp list
```
```
Checking MCP server health...
Searched -- user (~/.claude.json): 0; project-local (~/.claude.json (projects[...])): 0; this directory's .mcp.json (.../.mcp.json): 0; plugins (installed, enabled plugins): 0; managed (...): 0.
No MCP servers configured in this directory (see above for connectors/other scopes).
```

### `mcp get <name> [--cwd DIR]`
Prints one server's Scope/Status/Type/Command-or-URL/Instructions/Error/Tool
count. Exit 1, `No MCP server found with name: <name>`, if unconfigured.

### `mcp add [-t stdio|sse|http] [-s local|user|project] [-e KEY=VALUE ...] [-H 'Key: Value' ...] <name> <commandOrUrl> [args...]`
Writes a new server entry. `-s local` (default) -> `~/.claude.json`'s
`projects[cwd].mcpServers`; `-s user` -> `~/.claude.json`'s top-level
`mcpServers`; `-s project` -> `<cwd>/.mcp.json`. A stdio entry always writes
`"env": {}` even with no `-e`, byte-for-byte matching the real `claude mcp
add`. A `--` separator lets the command's own flags follow without argparse
mistaking them for `mcp add`'s own:
```sh
halo mcp add my-server -- npx -y @some/mcp-server --flag
```
```
Added stdio MCP server 'my-server' (local scope) to ~/.claude.json: npx -y @some/mcp-server --flag
```

### `mcp add-json [-s, --scope local|user|project] <name> <json>`
Same storage path as `mcp add`, but the entry is a literal JSON object
string:
```sh
halo mcp add-json my-remote '{"type":"http","url":"https://example.com/mcp"}'
```

### `mcp remove [-s, --scope local|user|project] <name>`
Without `-s`, tries `local`, then `user`, then `project`, removing from the
first scope where the name is found.

### `mcp add-from-claude-desktop [-s local|user|project] [--dry-run]`
Imports every server from Claude Desktop's own `claude_desktop_config.json`
(macOS `~/Library/Application Support/Claude/`, Windows `%APPDATA%\Claude\`,
or -- from WSL -- the Windows side's own AppData under `/mnt/c`; a plain
Linux box has no Claude Desktop to import from, same restriction the real
`claude mcp add-from-claude-desktop` documents). `--dry-run` lists what
would be imported and writes nothing.

### `mcp reset-project-choices [--cwd DIR]`
Forgets every approval halo recorded for a server currently listed in this
directory's `.mcp.json` -- it goes back to `⏸ Pending approval` and halo
asks again next time. Halo's own approval store only ever tracks
approvals (there is no separate "rejected" state to also reset).

### `mcp serve [--cwd DIR]`
Starts halo itself as a stdio MCP server, exposing a curated, stateless
subset of its own built-in tools (Bash/PowerShell, Read, Write, Edit, Glob,
Grep, NotebookEdit, TodoWrite, WebFetch -- never Agent/AskUserQuestion/
ToolSearch/background-job tools, which all need a live session) to any
other MCP client. The ccbridge code (`halo_harness/ccbridge/__main__.py`,
the `cc:` route's own tool bridge) is the base this reuses. Bash and
PowerShell run with halo's environment minus its own provider keys, the
same environment every other tool child gets.

### `mcp login <name> [--no-browser] [--timeout SECONDS]` / `mcp logout <name>`
A generic OAuth 2.0 authorization-code (+ PKCE) flow for one already-added
`http`/`sse` server: opens (or prints, with `--no-browser`) an authorize URL
built from that server's own `oauth` config block (`mcp add --client-id ...
--client-secret ... --callback-port ...`) or, failing that, OAuth 2.0
Authorization Server Metadata discovery (RFC 8414) at the server's own
`/.well-known/oauth-authorization-server`; waits for the browser's redirect
on a local callback, exchanges the code for tokens, and stores them at
`~/.halo/mcp/oauth/<name>.json` -- never in any of Claude Code's files, and
halo never reads `~/.claude/.credentials.json` either. `logout` deletes that
one file. Both endpoints must be `https` (or `http` on localhost); the token
endpoint used at login is recorded in the token file and is the one a later
refresh posts to. Tested only against a local fake OAuth server
(`tests/helpers/fake_oauth_server.py`); this flow has not been verified
against any specific vendor's real endpoints, and no vendor is named here
or in the code.

### `mcp fix <name> [--apply] [--cwd DIR]`
Halo 2.0.2 round 4: the same diagnosis the `/mcp` dialog shows per row --
prints the server's status, the WHY (`failure_reason`, the same text
`mcp list` shows in parentheses) and the one fix line (`fix_line_for`,
shared code, never duplicated between this command and the dialog).
Without `--apply`, prints only. With it, actually runs the matching
action: approves a pending `.mcp.json` server, runs the OAuth login for a
`needs_auth` http/sse server, reconnects a server that's merely down, or
-- for a command-not-found server -- prints the install hint (never runs
it; that line is for you to run):
```sh
halo mcp fix my-server
```
```
my-server: ✗ Failed to connect
  reason: command not found on PATH: npx
  fix: install Node.js (npx ships with it): https://nodejs.org/
Re-run with --apply to run it.
```

### `mcp test <name> [--cwd DIR]`
The `/mcp` dialog's `t` action from the CLI: connects (lazy servers
connect on first use, same as any real tool call) and times a fresh
`tools/list` round trip:
```sh
halo mcp test my-server
```
```
halo mcp test: my-server: ok in 42ms -- 7 tool(s).
```

### `mcp learned [--forget <endpoint>]`
Halo 2.0.2 round D: lists every endpoint
`providers/learned_rules.py` has learned something about (a learned
`tools_rejected` rule from a live 400, or a learned `reasoning_effort_
with_tools` override), each under its own `"<provider>:<model>"` key;
`--forget <endpoint>` clears that endpoint's `tools_rejected` rule before
its TTL would otherwise expire it naturally, leaving any other learned
field for that same endpoint untouched:
```sh
halo mcp learned
halo mcp learned --forget databricks:my-endpoint
```

## `/mcp` (the repair dialog)

Halo 2.0.2 round 4: lists every configured server and claude.ai connector
with a status glyph, and -- for anything not healthy -- the WHY and the
one fix line (`halo mcp fix`'s own `fix_line_for`, never duplicated) plus,
for a server that died mid-session, its reconnect-backoff attempt count
and next retry. The key legend is always shown at the bottom. All actions
act on the highlighted row (`R` excepted) and run off the UI thread, so a
hung/slow server never freezes the dialog -- Esc while one is in flight
cancels the WAIT on it, never the app.

| Key | Does |
|---|---|
| `r` | Reconnect the highlighted server (re-reads its config first, so an on-disk edit or a brand-new name takes effect without restarting halo). |
| `R` | Reconnect every server, one at a time; also resets the backoff on each one. |
| `a` | Approve a `pending_approval` project (`.mcp.json`) server, then reconnect it. |
| `l` | For a local `http`/`sse` server: the 2.0.1 OAuth login flow (`halo mcp login`). For a claude.ai connector row: the re-auth instructions (there is no local OAuth flow for one of these -- the login lives in claude.ai/claude itself). |
| `L` | A tail of `~/.halo/mcp/<server>.log` (stdio stderr + connect/transport errors, rotated at 1 MB) in a small viewer; Esc returns. |
| `e` | Edit the entry: opens the source file at that server's own line in `$VISUAL`/`$EDITOR`, using THAT editor's own line syntax (`+<line>` for vim/nvim/nano/emacs, `--goto file:line` for `code`, `file:line` for `subl`; any other editor opens the file plain, with no line argument at all), or, with neither set, an inline form (command/args/env, or url/headers) that writes back to the exact same scope file `mcp add` uses; reconnects after either path. |
| `i` | An install hint for a command-not-found server, guessed from the missing command itself (`npx`/`node`/`uvx`/`uv`/`pipx`/`pip`/`python`) -- shown as a copyable line, never run for you. |
| `d` | Disable (or re-enable) the server for THIS directory only -- Claude Code's own per-directory `disabledMcpServers` list, so its definition is untouched and every other project keeps seeing it. |
| `t` | A `tools/list` round trip with timing, shown in the hint line. |
| Esc | Cancel a busy action, or close the dialog. |

**Reconnect backoff**: a server that dies mid-session reconnects on its
next use, but not on every next use while it's still down -- 1, 2, 4, 8
seconds, then every 30 seconds, giving up automatically after 10 minutes
(the row then says so); `r`/`R`/`halo mcp fix --apply` always reset this,
since asking by hand is itself the reset.

## claude.ai connectors bridge

When `claude` is installed and logged in with a claude.ai subscription,
halo discovers the account-side connectors it reports (Claude Docs today;
generic -- any future connector shows up the same way) through `claude`
itself, since halo can never see or authorize them directly and never
reads claude's own credentials file. Discovery (`claude mcp list` plus one
headless `claude -p --output-format stream-json` start, read only for its
`system/init` line's tool names) runs once per session on a background
worker -- never on the UI thread -- and is cached at
`~/.halo/mcp/connectors.json`; `halo mcp list --refresh` and the `/mcp`
dialog's `r` (reconnect) force a fresh one. "Connector cold start": when
that cache is still genuinely empty, both the session build (`-p` and the
TUI's first build alike) and a plain `halo mcp list` (no `--refresh`
needed) instead run ONE bounded (20s) synchronous discovery inline before
anything reads the cache, so the very first look at connectors on a fresh
box is the real list, not an empty one a background worker hadn't reached
yet; once anything real is cached, later launches go back to the
background-only path above.

Each connector becomes one halo tool, `connector__<slug>` (e.g.
`connector__claude_docs`), schema `{request: string, tool?: string, args?:
object}` -- describe what to do in plain words, or name one of the
connector's own tools directly. Running it spawns a scoped, headless
`claude -p --allowedTools "mcp__claude_ai_<Name>__*" --max-turns N
--output-format json` that performs exactly the request and returns the
result verbatim; halo's own permission rules gate the call exactly like
any other tool (`connector__claude_docs(batch)` targets one specific
underlying tool, the same parenthesised-content grammar every other tool
rule already has), and the bridge itself never refuses a call. A deny/ask
rule written for claude's own `mcp__claude_ai_<Name>__*` tool in Claude
Code's settings is automatically translated to the matching
`connector__<slug>` rule, so it still applies here. `tool`, when given, is
one of that connector's own tool names (the call reports an error
otherwise) and narrows `--allowedTools` to that single name; the session's
whole-tool deny rules (`Bash`, `Write`, `mcp__<server>`, ...) and the
connector's per-tool deny/ask rules are passed to the inner claude as
`--disallowedTools`.

Config (`~/.halo/config.json`, dotted `halo config` keys): `connectors.
bridge` (default `true`, `false` disables discovery and every connector
tool outright), `connectors.<slug>.enabled`, `connectors.<slug>.
alwaysLoad` (preload instead of leaving it to ToolSearch), `connectors.
<slug>.max_turns` (default 4). `/mcp`, `halo mcp list` and `halo doctor`
all show each connector's status, labelled `claude.ai connector (via
claude)`; a `needs_auth` one names the exact next step (authorize at
claude.ai or inside `claude` with `/mcp`, then reconnect here). When
`claude` is missing, not logged in with a subscription, or gateway-driven,
the connectors line says so in one sentence instead of being silently
absent. Nothing here is specific to any one vendor's connectors, by design.

## Unsupported MCP transports

`sdk`-type servers are always disabled: `'sdk'` describes embedding
another Claude Agent SDK process in the same run, not a subprocess or
network endpoint, so halo's out-of-process MCP manager has nowhere to
embed one (use stdio/http/sse/ws instead). `ws`/`websocket`-type servers
connect for real once halo's installed `mcp` package ships its own
websocket client (`mcp.client.websocket`) -- the pinned `mcp==2.2.0` this
build ships with does not, so they're disabled too today, with that exact
reason shown next to them (`halo doctor`, `mcp list`/`get`, `/mcp`).

## MCP audio content

An MCP tool's `audio` content block is passed through as a typed `audio`
block (same `{"source": {"type": "base64", ...}}` shape an image block
already uses) to a model whose profile declares audio support; every model
in this build's own table omits that today, so in practice every MCP
audio result still becomes the existing `[audio content (<mime>) omitted
-- this model has no audio support]` text note.
