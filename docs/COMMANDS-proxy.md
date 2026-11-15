# Commands: the proxy, exit codes and config checks

Read this when you run the old proxy, read an exit code, or list and check the config files in effect.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo proxy`

The original `claude-bridge`: a single-file HTTP proxy (`bridge.py`) that
sits in front of the **real** `claude` binary and translates its
Anthropic-Messages-API calls to OpenRouter/Databricks, leaving `claude`'s
own subscription, config, hooks and permissions completely untouched. Kept
unchanged, as its own subcommand, for anyone who wants the real `claude` CLI
itself (its own update cadence, its own bug-for-bug behavior) driven by a
non-Anthropic model, rather than halo's own agent loop.

```sh
halo proxy --help
```
```
usage: claude-bridge [-h] [--serve] [--port PORT] [--state-dir STATE_DIR]
                     [--config] [--stop] [--version] [--probe]

options:
  -h, --help            show this help message and exit
  --serve               Run the bridge server
  --port PORT           Port to bind (default: 8787)
  --state-dir STATE_DIR
                        State directory path
  --config              Print configuration and exit
  --stop                Stop a running server
  --version             Print version and exit
  --probe               Probe Databricks/OpenRouter reachability and cache
                        model list
```

| Form | What |
|---|---|
| `halo proxy launch [claude flags...] [prompt]` | starts (or reuses) the proxy server, then execs the **real** `claude` binary pointed at it -- every argument after `launch` is forwarded to `claude` verbatim, including `-h`/`--help` (so `halo proxy launch --help` prints the real Claude Code help, not this project's own) |
| `halo proxy --serve [--port PORT] [--state-dir DIR]` | runs the proxy server in the foreground |
| `halo proxy --probe` | outbound reachability check for both providers, caches the OpenRouter model list |
| `halo proxy --config` | resolved configuration as JSON, secrets redacted |
| `halo proxy --stop` | shuts down a running proxy server |

```sh
BRIDGE_TEST_HOME=/tmp/demo-home halo proxy --probe
```
```
Databricks: not configured
OpenRouter: not configured (no OPENROUTER_API_KEY)
```

State lives in `~/.claude-bridge/` (`BRIDGE_STATE_DIR` to override),
loopback-only bind, bearer-token-gated, redacted logs -- see
`docs/harness/` (via `docs/harness/README.md`) for the proxy's own
historical design notes (request translation, the 128-tool cap,
context-overflow rewriting) if you need the low-level detail; they are
unchanged from before this project became a standalone harness and are not
re-derived on this page.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | success |
| `1` | the command ran and something it reported on failed (a `-p` turn ended in error, `doctor` found a `[MISSING]`, `improve --apply` on a bad spec) |
| `2` | usage/config error (bad flag value, no prompt given, an invalid `--model`) |
| `130` | `Ctrl+C` during a `-p` turn |
| `129` | `SIGHUP` (a closed terminal/dropped SSH connection) during any run |
| `143` | `SIGTERM` |

## `halo config where` and `halo doctor --config` (3.1.1.0)

```sh
halo config where              # every file in effect for this folder and home, one table
halo config where --json       # the same rows as JSON
halo config where --cwd DIR    # as if run from DIR
halo doctor --config           # check every one of those files
halo doctor --config --json    # the findings as JSON
```

`halo config where` lists, in groups, every file that sets something here:
`~/.halo/config.json` (and `routes.json`; a repo `.halo/config.json` is
listed as not read, because Halo reads only the home one), the env file
`~/.config/halo/env` and a repo `.env` (variable **names** only, never a
value; Halo does not read `.env`), Claude Code's `settings.json` layers
(managed, `--settings`, local, project, user), the MCP server files
(`managed-mcp.json`, `~/.claude.json` and its entry for this folder,
`.mcp.json`), the agent, workflow and map folders (3.6.0.0 R5d: the project's `.halo/crew/<kind>s/`, listed
and marked not read in a folder you have not trusted, yours `~/.halo/crew/<kind>s/`, the shipped starters, and
each enabled pack's, read-only), the Databricks preset (`team.json`) and the packs.
Each row: the
file, its scope (`home`, `repo`, `env`, `shipped`), whether it exists, what
it sets (its top-level keys, or the names of the agents, workflows, maps,
servers or variables it holds) and its rank (1 = the file the resolver
reads first). When two files set the same key, `wins` and `loses to` say
which one decides, as the resolvers decide it (the crew finder, the settings merge, the MCP resolver, the start-model and theme
order, the env file's "the environment wins" rule). `/config where` in the
TUI prints the same table.

`halo doctor --config` checks every file that table lists: against the
schema set (`halo_harness/schemas/`) for unknown keys (with the closest known
key) and wrong types, and against the existing validators for meaning. A key
the Settings catalog types a list that holds one plain value is one warning
line naming the `halo config set` that writes the list (3.6.0.0 R5d). A
section of a removed feature is one warning line: `orgs: removed in 3.1.4.0,
the section is ignored` (and the same for `paperclip`). Lineups and bios are
not read since 3.6.0.0, so their files are not checked. It also reports a key
two files set to different values, with the file that wins. Shipped
templates are not re-checked. Exit 0 when nothing is found, 1 otherwise
(`GET /api/doctor/config` answers the same findings).

```
halo doctor --config
  [WARN] ~/.halo/config.json: unknown key 'modle' (closest known key: 'model'); nothing reads it -> fix: rename it to model
  [WARN] ~/.halo/config.json: workflows.enabled is a list, not "review" -> fix: halo config set workflows.enabled review (it writes the list)
RESULT: 2 finding(s) in 9 file(s) checked (0 error(s), 2 warning(s)).
```
