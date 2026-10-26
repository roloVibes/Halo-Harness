# Commands: config, sessions, stats and reports

Read this when you read or set config, replay or export a session, read stats, or file a bug report.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo config`

Reads and writes **this harness's own** small store,
`~/.halo/config.json` -- never Claude Code's `settings.json`, which
this project only ever reads. See `docs/CONFIG.md` for every key this file
can hold.

```sh
halo config --help
```
```
Usage: halo config [list|get <key>|set <key> <value>]
```

```sh
BRIDGE_TEST_HOME=/tmp/demo-home halo config list
```
```
(no config set -- ~/.halo/config.json is empty or missing)
```
```sh
BRIDGE_TEST_HOME=/tmp/demo-home halo config set model or:deepseek/deepseek-v4.1-flash
```
```
model="or:deepseek/deepseek-v4.1-flash"
```
```sh
BRIDGE_TEST_HOME=/tmp/demo-home halo config get model
```
```
"or:deepseek/deepseek-v4.1-flash"
```

A key may be dotted (`improve.model`) to read/write a nested value without
disturbing its siblings; `halo config key=value` (one argv token) is
accepted as shorthand for `config set key value`. The value is parsed as
JSON when possible (`true`, `123`, a quoted string), so non-string values
round-trip too.

## `halo replay`

Replay one turn of a recorded session against a different model and
compare the outcomes side by side -- "did swapping the researcher from
one model to another help?", answered with a diff over real task
history instead of a synthetic gym battery. The session is forked
first (the original file is never appended to), the fork is truncated
to just before the chosen turn's user prompt, and that turn's own
prompt is re-sent through plain print mode against the swapped model
-- same cwd, same tools, same hooks as any `halo -p`.

```sh
halo replay <session-id> --model or:qwen/qwen3.8-flash [--turn 2] [--json]
```

`--turn N` (1-based, default 1) picks which real user turn to replay;
the report shows both outcomes (chars, tokens, cost, tools used) and
`SAME` / `DIFFERENT (first divergence at line N)` for the final
answer. `--json` prints the machine-readable report.

## `halo stats`

A headless, cross-session version of the TUI's own `/stats` -- aggregates
tokens/cost/tool-calls straight from the existing session `.jsonl` logs,
never a new model-visible field.

```sh
halo stats --help
```
```
usage: halo stats [-h] [--all] [--all-projects] [--cwd DIR] [--json]
                         [--models] [--tools] [--roles] [--wide]
                         [--since SINCE] [--session ID] [--experiential]
                         [--id REQUEST_ID]

Aggregate tokens/cost/tool-calls across session logs (headless /stats).

options:
  -h, --help       show this help message and exit
  --all            Aggregate every project's sessions, not just the current
                   directory's
  --all-projects   Alias for --all
  --cwd DIR        Project directory to aggregate (default: the current
                   directory; ignored with --all)
  --json           Print machine-readable JSON instead of a text report
  --models         Show the richer per-(model,provider) telemetry table
                   (repairs, edit failures, ttft/latency, ...)
  --tools          Show the per-tool telemetry table
  --roles          Show spend per role, including the session's own
                   ("main") -- with task counts (Agent-call completions),
                   accepted/total, cost per task and per accepted result,
                   so a role assignment can be judged by evidence
  --wide           Show every --models column instead of the terminal-fit
                   compact default
  --since SINCE    Time window for --models/--tools: "all", or "<N>d" (e.g.
                   "1d", "7d", "30d"; default 7d). Ignored by the plain report
                   below.
  --session ID     Scope to one session id
  --experiential   Settled usage rows from the Experiential Labs account API
                   (GET /api/v1/usage) instead of the local session-log
                   aggregate -- needs EXPLABS_API_KEY
  --id REQUEST_ID  With --experiential: look up ONE call by its x-request-id
                   (GET /api/v1/generation) instead of listing settled usage
                   rows
```

Halo 2.0.4 round 2: `halo stats --experiential` is a DIFFERENT data source
from every other mode above -- a bounded, best-effort LIVE read of the
Experiential Labs gateway's own settled-usage rows, not this command's
usual local session-log aggregate. There is no standalone `halo cost`
command; this and the in-session `/cost` are the two cost-reporting
surfaces. Halo 2.0.4 round 5: `--id <x-request-id>` switches to a
single-call lookup (`GET /api/v1/generation`) instead -- the id a real
`xp:` turn's own response carries (shown in `/xp routes`'s "last
response" block, or the session's raw log) pasted back in for
after-the-fact attribution.

Bare `halo stats` (no `--models`/`--tools`/`--roles`) is the original,
cheap report: turns, total cost, per-model token/cost totals, per-tool call
counts -- works even on a session log recorded before the richer telemetry
fields existed. `--models`/`--tools` switch to `halo_harness.telemetry`'s
aggregation (cached at `~/.halo/stats-cache.json`, keyed by
path+size+mtime so an unchanged log is never re-parsed): per-(model,
provider) sessions/calls/tokens/cost/avg-latency/tool-error%/repair-hit%/
edit-failure%/steers/compactions/loop-breaker-trips (14 columns by default,
`--wide` adds route/cached-tokens/avg-ttft/finish=length%/retries/overflow/
interrupts -- columns are dropped right-to-left to fit the terminal width,
never wrapped or truncated when piped to a file). `--roles` (V2c/H15): sub-
agent spend (sessions/calls/tokens/cost) per role name, summed from every
Agent-tool call's own rolled-up usage node -- see `docs/ROLES.md`.

```sh
BRIDGE_TEST_HOME=/tmp/demo-home halo stats
```
```
halo stats (/path/to/project, 0 session(s)):
  Turns: 0
  Total cost: $0.0000
```

## `halo improve`

The headless surface for the same human-gated loop the TUI's `/improve`
drives interactively -- clusters recent failures, drafts up to 8 candidate
memory/rule/skill files with one model call, and **never writes anything
without `--apply`**.

```sh
halo improve --help
```
```
usage: halo improve [-h] [--since {7d,30d,all}] [--all-projects]
                           [--json] [--out FILE] [--apply FILE#ID] [--cwd DIR]
                           [--bare] [--max-candidates MAX_CANDIDATES]

Human-gated self-improvement: draft memory/rule/skill candidates from recent
session failures (never applied without --apply).

options:
  -h, --help            show this help message and exit
  --since {7d,30d,all}
  --all-projects
  --json
  --out FILE
  --apply FILE#ID       Write exactly this candidate (repeatable). Skips
                        drafting.
  --cwd DIR
  --bare                Disable everything -- no scan, no draft, no apply
  --max-candidates MAX_CANDIDATES
```

Bare `halo improve` scans, drafts (one model call -- `improve.model`
config, else the small model, else the session model), prints every
candidate, and saves them to `~/.halo/improve/<timestamp>.json`:

```sh
BRIDGE_TEST_HOME=/tmp/demo-home halo improve --bare
```
```
halo improve: --bare disables /improve entirely.
```

`--apply <file>#<id>` (repeatable) writes exactly that saved candidate to
disk -- the only way a headless invocation ever writes a memory/rule/skill
file. `--json`/`--out FILE` are for scripting; `--all-projects` scans every
project's sessions instead of just the current directory's.

## `halo export`

A headless version of the TUI's own `/export` -- writes a session's raw
JSONL transcript to a file or stdout, optionally sanitized.

```sh
halo export --help
```
```
usage: halo export [-h] [--session ID] [--sanitize] [-o FILE]
                          [--cwd DIR]

Export a session's transcript as JSONL (headless /export).

options:
  -h, --help            show this help message and exit
  --session ID          Session id or unique prefix (default: the latest
                        session for this directory)
  --sanitize            Redact common credential shapes (API keys, tokens,
                        secret env var values) before writing
  -o FILE, --output FILE
                        Write to FILE instead of stdout
  --cwd DIR             Project directory whose sessions to look in (default:
                        the current directory)
```

```sh
BRIDGE_TEST_HOME=/tmp/demo-home halo export
```
```
halo export: no sessions found for this directory
```

`--sanitize` redacts (never just masks) OpenRouter/Anthropic/Databricks/
GitHub/AWS-shaped tokens, quoted or JSON-encoded `export KEY="value"`/
`"KEY": "value"` assignments (by exact known name, and generically for any
`*_API_KEY`/`*TOKEN*`/`*SECRET*`-shaped name), `Bearer <token>`, `Cookie`/`Set-Cookie`/
`Proxy-Authorization` headers,
by round-tripping each log node through JSON text -- the same sanitizer the
TUI's own `/export --sanitize` calls, so the two can never disagree.

## `halo session export`

Halo 3.3.0.0: a session as one Markdown **trace** file, the same bytes
Studio's **Export** button downloads and the TUI's `/export` writes: a
header (the session id, the model and the lineup, when it started and
ended, the totals: turns, tool calls, tokens in and out, cost), then one
`###` entry per row in time order (the clock, the agent with its tier and
model, then a user prompt, the assistant's text, a tool call and a one-line
summary of its arguments, the tool's result fenced and trimmed to 40 lines,
a steer and its target, a nudge, a permission answer, the turn-end marker,
a compaction, an error). Keys are masked and home paths read `~`.

```sh
halo session export --help
```
```
usage: halo session export [-h] [--md FILE] ID

options:
  -h, --help  show this help message and exit
  --md FILE   Write to FILE (- prints it; default: halo-trace-<id>-<yyyy-mm-
              dd-hhmm>.md here)
```

```sh
halo session export 3f2a9c         # a unique prefix is enough
wrote ./halo-trace-3f2a9c41d0e8-2026-10-26-1412.md
halo session export 3f2a9c --md -  # print it
```

The id is looked up across every project's sessions in the state dir. How
the trace reads in Studio: [Export](STUDIO-session.md#export-the-session-as-a-trace-file).

## `halo bugreport`

"One paste instead of screenshots" -- writes a redacted diagnostic report
to `~/.halo/bugreports/<timestamp>.md` (or `--out FILE`) against the most
recent session for the cwd (or `--session ID`). `/bugreport` in the TUI/`-p`
is the same report, built from the live session instead.

```sh
halo bugreport --help
```
```
usage: halo bugreport [-h] [--last N] [--session ID] [--out FILE] [--copy]
                      [--include-content] [--cwd DIR]

Write a redacted diagnostic report (one paste instead of screenshots).

options:
  -h, --help         show this help message and exit
  --last N           Session events to include (default 20)
  --session ID       Session id or unique prefix
  --out FILE         Write to FILE instead of ~/.halo/bugreports/
  --copy             Also copy the report text to the clipboard
  --include-content  Include prompt/output text, not just shapes
  --cwd DIR
```

Contents, in order: halo version, Python/OS/terminal/shell/cwd/git branch,
install mode; which providers are enabled and WHY (env file, settings env,
`~/.databrickscfg`, claude.ai login -- never a key, not even a fingerprint);
the current route (ref, provider, api_type, dialect, profile, effort
requested and effort SENT); permission mode; MCP servers with state;
`~/.halo/config.json` with secret-shaped values replaced; settings source
paths (paths only); catalog cache age per provider; this session's own
learned permission rules; the last turn's timeline (see `halo timeline`
below); the last N session events (types, durations, tool names, status
codes and error messages -- prompt/output text only with
`--include-content`); and the last 50 `bridge.log` lines. Every line passes
through the same redactor `halo export --sanitize` uses, plus a stronger
pass (long hex/base64 runs, `sk-`/`dapi`/`Bearer ` shapes, and the literal
value of any secret env var this process can see) -- a planted fake key
never survives into the report from any of these sources. `--copy` copies
the report text to the clipboard with whatever exists (`clip` on Windows,
`pbcopy` on macOS, `wl-copy`/`xclip` on Linux; otherwise just the path is
printed).

## `halo timeline`

Reads the per-turn request/tool/hook/permission-wait/compaction timing
timeline a session's own log already recorded (`agent.loop.Session.turn`'s
own wrapper, for every turn regardless of dialect) back from that session's
log file -- works for a session from an earlier process, not just a live
one. `/timeline [N]` in the TUI/`-p` shows the SAME shape for the live
session's own in-memory copy instead (identical fields); `--debug` prints
the same lines live as they happen.

```sh
halo timeline --help
```
```
usage: halo timeline [-h] [--last N] [--session ID] [--cwd DIR] [--json]

Show the per-turn request/tool timing timeline for a session.

options:
  -h, --help    show this help message and exit
  --last N      Turns to show (default 1, the most recent)
  --session ID
  --cwd DIR
  --json        Print raw JSON instead of formatted text
```

Per turn: request-sent/headers/first-reasoning/first-text/first-tool-call/
message-end elapsed milliseconds; each tool call's own name/start/end/
status; each hook that ran (event name + real duration); each permission
ask that blocked the turn (start, end, resolved decision -- "allow"/"deny"/
"dismissed"); compactions (phase, trigger, tokens before/after when
known -- auto-compaction only, a manual `/compact` runs outside any turn);
steers; and retries/errors with status codes. `--json` prints the raw
records instead of the formatted text.

## `halo worktree`

```sh
halo worktree rm <path>
```

Removes a git worktree (`git worktree remove`, falling back to `--force`
once over uncommitted changes -- a session's own scratch worktree is
disposable by design) and fires `WorktreeRemoved`. The explicit counterpart
to `-w/--worktree`'s own creation: that flag's tree is left on disk when the
session ends by default (config `worktree.remove_on_exit`, default `false`
-- set it `true` to have the session remove its OWN worktree automatically
on exit instead, which fires the same event). No `list`/`add` subcommand
yet -- `-w/--worktree` itself is how one gets added.

## `halo bg`

```sh
halo bg list
halo bg logs <id> [-n LINES]
halo bg stop <id>
halo bg rm <id> [--force]
```

The read/manage side of `--bg`/`--background`, over the detached run's own
`~/.halo/bg/<id>/{output.log,meta.json}`: `list` shows each run's id, status
(`running`/`exited`, checked live, never trusted stale), pid, age and
command; `logs` prints the captured stdout+stderr (`-n` for just the tail);
`stop` kills the process tree by pid (same Windows orphan-grandchild-aware
kill background Bash jobs already use); `rm` deletes the run's directory,
refusing a still-running one unless `--force` (which stops it first).

Each run also joins `~/.halo/run/children.json` (3.2.2.0) with its owner: a
`halo --bg` run from a halo session's own Bash or PowerShell tool belongs to
that session and ends when it quits; one started from a plain shell belongs
to no session, so a quit leaves it (like the supervisor's runs). `halo
update` stops every run before it installs; `halo bg stop <id>` ends one at
any time.
