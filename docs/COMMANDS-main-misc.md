# Commands: the other `halo` flags

Read this when a `halo` flag is not in the other parts: misc flags, the ones not built yet or not applicable.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo` flags: the rest

### Misc flags

#### `--theme THEME`
What: one of `claude-dark`/`claude-light` (`-daltonized`/`-ansi` variants of
each) for this run; `/theme` persists a choice for future sessions.

#### `--no-intro`
What: skips the launch intro a fresh interactive launch otherwise shows
above the first turn (since 3.2.2.0 the HALO block-art wordmark, revealed
row by row, then `halo <version>` under it) -- same effect as `"intro": false` in
`~/.halo/config.json`. Never shown in print mode, a `--demo` run, or when
stdout isn't a real terminal, with or without this flag; `/intro` replays
it mid-session.

#### `--demo`
What: runs (or, with `-p`, prints) a scripted walkthrough turn that needs no
network, no API key and no configured model -- the safe example used
throughout this page and the README's own 10-minute walkthrough.

#### `--stress N`
What: repeats the demo script's own synthetic load N times (a throughput/UI
smoke test, not a real benchmark).

#### `-v`, `--version`
What: prints the ASCII banner (2.0.5 round 2d; the same wordmark the launch
intro types out and the README shows) followed by `halo <version>` -- with
the install's own `(commit, branch)` once known -- and exits 0, before any
config is read.

### Flags parsed but not implemented yet

Every flag listed here would be accepted by the argument parser (never an
"unrecognized arguments" error) and, the first time its value differs from
"never touched at all", would print one line to stderr naming the milestone
it's planned for, then continue the run as if the flag had not been given.
As of 2.0.1 (W4a) the table is **empty** -- every flag that used to be here
is now either a real flag (below) or declared not applicable to a
standalone harness (also below). The mechanism itself stays, ready for
whatever a future Claude Code release adds that genuinely isn't built here
yet; the canonical, always-current list is `halo_harness/cli.py`'s own
`_NOT_YET_FLAGS` table -- this page's test (`tests/test_docs_commands.py`)
fails if the two ever disagree.

### Flags not applicable to a standalone harness

These 7 flags are accepted (never an "unrecognized arguments" error) and,
the first time given, print one line to stderr naming the reason, then
continue the run as if the flag had not been given -- never "not supported
yet", since there is no future milestone that would change the answer:

```sh
halo --ide -p "hi"
```
```
halo: --ide is not applicable to a standalone harness (needs Anthropic's IDE extension protocol, which halo does not implement)
```

| Flag | Reason |
|---|---|
| `--cloud [DESCRIPTION_OR_ID]` | halo has no cloud session service -- every session runs on this machine |
| `--teleport [SESSION]` | teleport sessions are a claude.ai cloud feature halo has no equivalent of |
| `--remote-control [NAME]` | Remote Control pairs a session with the claude.ai mobile/web app, which halo does not integrate with |
| `--remote-control-session-name-prefix PREFIX` | only meaningful alongside `--remote-control`, which is not applicable here |
| `--from-pr [VALUE]` | resuming a session linked to a PR is a claude.ai cloud-session feature halo does not have |
| `--ide` | needs Anthropic's IDE extension protocol, which halo does not implement |
| `--safe-mode` | halo has no safety heuristics to disable by design -- accepted for compatibility, no effect |

### New in 2.0.1 (W4a)

The 21 flags below were "not supported yet" before 2.0.1 and are real now.

#### `--allow-dangerously-skip-permissions`
What: an alias for `--dangerously-skip-permissions` -- Claude Code's own
name for "enable bypass as an option, without it being on by default".
Identical behaviour either way in halo.

#### `--autocompact {auto|TOKENS}`
What: overrides the auto-compaction trigger window. `auto` (or omitting the
flag) keeps the normal 80%-of-headroom rule; a token count (`150000`,
`150k`) sets `CLAUDE_CODE_AUTO_COMPACT_WINDOW` for this run, the same env
var `/compact`'s own trigger math already reads.

#### `--ax-screen-reader`
What: runs a plain, line-oriented interactive loop instead of the
full-screen Textual UI -- flat text, no borders/animations/spinners, one
line per event. Permission/question/plan asks become a `y`/`n` or numbered
prompt read from stdin, and an approval ask (a position that requires
approval, or a team escalation) becomes an `a`/`e`/`s` accept / edit / stop
prompt. Not the TUI with styling stripped; a genuinely
separate, simpler renderer (`halo_harness/ax_mode.py`) driving the same
`Controller` the real TUI uses.

#### `--bg`, `--background`
What: spawns this same invocation (forced to `-p`, since a detached process
has no terminal a TUI could render into) as a background process; prints
its id and a log file path, then returns immediately. Manage it afterward
with `halo bg list|logs|stop|rm` (below) -- the OS's own process tools
(`kill`, Task Manager, ...) still work too, nothing here is exclusive.

#### `--betas BETA [BETA ...]`
What: one or more Anthropic beta feature names, sent as a comma-joined
`anthropic-beta` request header -- only on an Anthropic-family route
(`ant:`, or a Databricks Claude foundation model specifically, i.e. the
`anthropic-passthrough` dialect); accepted but never sent (no error) on
any other route, including an ordinary Databricks-hosted chat-dialect
model and OpenRouter.

#### `--brief`
What: adds the `SendUserMessage` tool to the session's catalog -- lets the
model send a short status update without ending its turn, for terser
running commentary instead of one long reply at the end.

#### `--environment KEY=VALUE`
What: repurposed for a standalone harness -- Claude Code's own
`--environment <id>` runs a cloud session on a self-hosted environment,
which does not exist here. One or more `KEY=VALUE` pairs (repeatable),
merged into the tool child environment (so `Bash`/`PowerShell` see them)
after the settings-env chain, so an explicit flag wins.

#### `--exclude-dynamic-system-prompt-sections`
What: accepted; halo's own system-prompt assembly already keeps the
per-machine sections (cwd, git status, environment) as a separate snapshot
block rather than baking them into the static system prompt, so this flag
describes behaviour halo already has by default.

#### `--fallback-model MODEL`
What: one or more comma-separated fallback models, tried when the primary
is exhausted-by-retries within a turn; reset to the primary fallback LIST at
the start of each new user turn. Wired into the live model-call retry
ladder (`agent/loop.py::Session._step`/`_try_fallback_after_exhaustion`): a
provider failure (the primary's retry ladder exhausted on a retryable
5xx/429-class error) swaps onto the next entry for the rest of the turn,
with one `notification` event (visible in the transcript and in
`--output-format stream-json`) naming the model that failed and the one
switched to; an entry that fails to resolve, or whose tool catalog is too
small for the session, is skipped in favour of the next one.

#### `--forward-subagent-text`
What: accepted; `--output-format stream-json` already forwards a
sub-agent's own text/thinking/tool blocks as `assistant`/`user` lines with
`parent_tool_use_id` set, unconditionally -- a strictly more-forthcoming
default than Claude Code's own opt-in, kept rather than gated behind this
flag to avoid a behaviour-breaking change for zero gain.

#### `--include-hook-events`
What: with `--output-format stream-json`, interleaves one
`{"type": "system", "subtype": "hook_event", ...}` line per hook
invocation (event name, whether it blocked, its permission decision) among
the turn's own lines, in the order they actually happened.

#### `--no-session-persistence`
What: only with `-p`. The turn still runs and logs normally, but its
session log file/directory and `index.json` entry are deleted before the
process exits -- nothing survives to be `-c`/`-r`-resumed later.

#### `--permission-prompt-tool TOOL`
What: `TOOL` is an MCP tool's full catalog name (`mcp__<server>__<tool>`).
In print mode, an "ask" decision that would otherwise be auto-denied is
instead sent to this tool (`{tool_name, tool_input, reason}`); a
`{"behavior": "allow"|"deny"}` reply (or bare `allow`/`deny` text) decides
it. No reply, an unreachable tool, or `--permission-prompts none` falls
back to the ordinary auto-deny.

#### `--permission-prompts {host,none}`
What: `none` (the default either way) auto-denies every print-mode ask, as
before. `host` consults `--permission-prompt-tool` when one is given.

#### `--plugin-dir PATH`
What: loads a plugin's agent definitions from `PATH` for this session only
(repeatable). Also wired into skill, hook and MCP server discovery for
this session (`commands/registry.py`, `hooks.load_plugin_hooks`,
`mcp_setup.build_manager`), plus a model-invoked `Skill` tool call via
`Session.plugin_roots`/`ToolContext.plugin_roots` -- the same sources an
*installed* plugin's skills/hooks/MCP servers (`config/plugins.py`) already
read from, now extended to cover a CLI-supplied directory too.

#### `--plugin-url URL`
What: like `--plugin-dir`, but `URL` is a git URL, shallow-cloned once into
`~/.halo/plugins-cache/` and reused on later launches (never re-cloned).
Claude Code's own `--plugin-url` fetches a `.zip`; halo takes the simpler,
already-everywhere git clone instead.

#### `--prompt-suggestions [true|false]`
What: the single-turn `-p TEXT` path AND (W5, carried from W4a)
`--input-format stream-json`'s own multi-turn loop, one suggestion per
turn. After each turn, one extra small-model call predicts the user's
likely next message; `text` output
prints it as a trailing `[next: ...]` line, `json` adds a
`prompt_suggestion` field, `stream-json` emits its own
`{"type": "prompt_suggestion", ...}` line. Costs one extra model call --
only when you ask for it.

#### `--restricted`
What: a read-only tool set -- removes `Bash`/`PowerShell`/`WebFetch`/
`Edit`/`Write`/`NotebookEdit` and every MCP server tool from the catalog
unless named explicitly in `--tools`, and ignores
`--dangerously-skip-permissions` (falls back to the default permission mode
with a notice). Also honored by an interactive launch now, not only `-p`.
Claude Code's own additional "ignores user/project/local settings files"
and "only a person may approve settings/git/tool-config writes" rules are
not modelled this round.

#### `--system-prompt-snapshot {on,off}`
What: `on` (the default either way): halo already computes the system
prompt once per session and reuses it verbatim for every request, matching
`on`'s own documented behaviour. `off` is accepted but not distinguished
from `on` this round -- halo has no per-request system-prompt re-render to
turn off yet.

#### `--tmux [classic]`
What: when the `tmux` binary exists and this isn't already running inside
one (`$TMUX` unset), re-execs the interactive launch inside a new tmux
window. Tmux-only (no iTerm2 native-pane backend); missing tmux is a
notice, never an error.

#### `-w`, `--worktree [NAME]`
What: creates a new git worktree (on a fresh branch) under
`~/.halo/worktrees/<repo-slug>/<name-or-id>` and runs the session there
instead of the real working tree -- isolates the session's own file edits
from the repo you're actually looking at. Falls back to the current
directory (one notice, never a hard failure) outside a git repo or if `git
worktree add` itself fails. The same mechanism backs a sub-agent's own
`isolation: worktree` frontmatter key. Fires `WorktreeCreated`; the tree is
left on disk when the session ends unless `worktree.remove_on_exit` is set
(see `halo worktree`, below) -- `rm` it yourself, or with `halo worktree rm`.
`--session-id`, `-c` and `-r` are checked before the worktree is created, so
a bad value leaves nothing behind; a session resumed with `-c`/`-r` is copied
into the worktree's own session directory.
