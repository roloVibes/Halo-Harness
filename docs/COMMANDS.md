# Commands

Read this when you want every `halo` subcommand and flag, with examples.

Every CLI subcommand `halo` accepts, and every flag any of them
accepts, verified against the real `--help` output and the argparse
definitions in `halo_harness/cli.py` and each subcommand's own module. For
the in-app `/slash` commands, key bindings, `@file` and `!cmd` prefixes, see
[SLASH-COMMANDS.md](SLASH-COMMANDS.md); for the architecture behind these
commands, see [ARCHITECTURE.md](ARCHITECTURE.md).

**How this page is organised (and kept honest)**: every flag/subcommand
heading below wraps the exact token in backticks, e.g. `#### \`--model\``
or `## \`halo doctor\``. `tests/test_docs_commands.py` calls every
real `--help` in-process (no subprocess, no network) and fails the suite if
a flag/subcommand exists in the code but isn't mentioned here, or if a
`` `-x`/`--xxx` `` token inside a heading here doesn't match a real one --
so this page cannot silently drift from `cli.py` again in either direction.
A `[not-yet]` flag parses (never an argparse error) but its feature isn't
built; see [Flags parsed but not implemented yet](COMMANDS-main-misc.md#flags-parsed-but-not-implemented-yet).

Every worked example below uses `--demo` (a scripted turn needing no
network, API key, or model) or a scratch `BRIDGE_TEST_HOME` so it is safe to
paste into a shell verbatim; swap in your own model/prompt once you have a
provider configured (`halo init`).

```sh
export PYTHONPATH=/path/to/halo-harness   # a dev checkout; skip if installed
halo --version
```
```
 _   _      _      _        ___
| | | |    / \    | |      / _ \
| |_| |   / _ \   | |     | | | |
|  _  |  / ___ \  | |___  | |_| |
|_| |_| /_/   \_\ |_____|  \___/
halo <version>
```

There is no `sessions` subcommand in this build -- session resume/fork/
rename/list lives entirely under the default command's own `-c`/`-r`/
`--fork-session`/`-n` flags and the TUI's `/resume`/`/rename`/`/fork` (see
`docs/SLASH-COMMANDS.md`).

This page is the entry point; the content lives in the parts below, one per task.

## The parts

| Part | Read it when | What is in it |
|---|---|---|
| [Commands: `halo` and its model and session flags](COMMANDS-main.md) | you start `halo` with flags: the main command, its model and session flags | `halo` (the main command) · Model & session flags |
| [Commands: `halo` output, prompt, settings, budget, browser, MCP and image flags](COMMANDS-main-io.md) | you change what `halo` prints or reads, its system prompt, settings, budget, browser, MCP or images | `halo` flags: output, prompt, settings, budget, browser, MCP and images · Output & input format flags · System prompt flags · Settings & permissions flags · Budget flags · Browser flags · MCP flags · Image flags |
| [Commands: the other `halo` flags](COMMANDS-main-misc.md) | a `halo` flag is not in the other parts: misc flags, the ones not built yet or not applicable | `halo` flags: the rest · Misc flags · Flags parsed but not implemented yet · Flags not applicable to a standalone harness · New in 2.0.1 (W4a) |
| [Commands: `halo init`, `halo start`, `halo explain` and `halo setup`](COMMANDS-init.md) | you set Halo up (`halo init`, `halo setup`), run the ten-minute start (`halo start`) or look up a word (`halo explain`) | `halo init` · `halo start` (Halo 3.1.1.0) · `halo explain` · `halo setup` / `/setup` (Halo 2.0.2 round 7) |
| [Commands: doctor, audit, update and the installers](COMMANDS-health.md) | you check, audit, update or reinstall Halo | `halo doctor` · `halo audit` · `halo update` · The installer scripts (`install-halo.sh`, `install-halo.ps1`) |
| [Commands: providers, subscriptions, rate limits and models](COMMANDS-providers.md) | you set up providers and subscriptions, read balances and rules, or refresh the model list | `halo providers` · `halo subscriptions` · `halo gov` · `halo balances` · `halo rules` · `halo work-matrix` · `halo models` |
| [Commands: MCP servers and connectors](COMMANDS-mcp.md) | you add, list, repair or log in to MCP servers and claude.ai connectors | `halo mcp` · `/mcp` (the repair dialog) · claude.ai connectors bridge · Unsupported MCP transports · MCP audio content |
| [Commands: Ollama, the gym and local models](COMMANDS-local.md) | you run local models: `halo ollama`, `halo gym`, `halo local` | `halo ollama` · `halo ollama calibrate` · `halo ollama doctor` · `halo gym` · `halo gym show` · `halo gym propose` · `halo local` |
| [Commands: config, sessions, stats and reports](COMMANDS-sessions.md) | you read or set config, replay or export a session, read stats, or file a bug report | `halo config` · `halo replay` · `halo stats` · `halo improve` · `halo export` · `halo bugreport` · `halo timeline` · `halo worktree` · `halo bg` |
| [Commands: roles, review, bios and lineups](COMMANDS-agents.md) | you manage roles, reviews, bios and lineups from the command line | `halo roles` · `halo review` · `halo agents` · `halo teams` · `halo subscriptions scrub` |
| [Commands: Studio, design, media, Orchestra and teams](COMMANDS-studio.md) | you open Studio or run designs, media, an Orchestra goal or a team from the command line | `halo studio` · `halo design` · `halo media` · `halo orchestra` · `halo team` · `/tasks` (Ctrl+T) · `halo completion` |
| [Commands: remote control and the fleet](COMMANDS-fleet.md) | you control sessions remotely or run a fleet and its missions | `halo remote` · `halo fleet` |
| [Commands: the proxy, exit codes and config checks](COMMANDS-proxy.md) | you run the old proxy, read an exit code, or list and check the config files in effect | `halo proxy` · Exit codes · `halo config where` and `halo doctor --config` (3.1.1.0) |
