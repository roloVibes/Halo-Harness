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
provider configured (`halo init`, which opens Setup in Studio).

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
| [Commands: `halo init`, `halo start`, `halo check`, `halo explain` and `halo setup`](COMMANDS-init.md) | you set Halo up (`halo init` opens Setup in Studio, `halo init --terminal` is the terminal wizard; `halo setup`), run the guided first run (`halo start`) or the checks (`halo check`), or look up a word (`halo explain`) | `halo init` · `halo start` (Halo 3.1.1.0) · `halo check` (Halo 3.2.2.0) · `halo explain` · `halo setup` / `/setup` (Halo 2.0.2 round 7) |
| [Commands: doctor, audit, update and the installers](COMMANDS-health.md) | you check, audit, update or reinstall Halo | `halo doctor` · `halo audit` · `halo update` · The installer scripts (`install-halo.sh`, `install-halo.ps1`) |
| [Commands: providers, rate limits and models](COMMANDS-providers.md) | you set up providers, read balances and rules, or refresh the model list | `halo providers` · `halo gov` · `halo balances` · `halo rules` · `halo work-matrix` · `halo models` |
| [Commands: MCP servers and connectors](COMMANDS-mcp.md) | you add, list, repair or log in to MCP servers and claude.ai connectors | `halo mcp` · `/mcp` (the repair dialog) · claude.ai connectors bridge · Unsupported MCP transports · MCP audio content |
| [Commands: Ollama](COMMANDS-ollama.md) | you run or watch an Ollama server: `halo ollama` and its subcommands | `halo ollama` · `halo ollama calibrate` · `halo ollama doctor` · `halo ollama tune` · `halo ollama discover` · `halo ollama hardware` · `halo ollama traffic` · `halo ollama events` · `halo ollama steward` |
| [Commands: the gym and local models](COMMANDS-local.md) | you run local models: `halo gym`, `halo local` | `halo gym` · `halo gym show` · `halo gym propose` · `halo local` |
| [Commands: config, sessions, stats and reports](COMMANDS-sessions.md) | you read or set config (`halo settings` opens Studio's Settings), replay or export a session, read stats, or file a bug report | `halo config` · `halo settings` · `halo replay` · `halo stats` · `halo improve` · `halo export` · `halo session export` · `halo bugreport` · `halo timeline` · `halo worktree` · `halo bg` |
| [Commands: roles, review, bios and lineups](COMMANDS-agents.md) | you manage roles, reviews, bios and lineups from the command line | `halo roles` · `halo review` · `halo agents` · `halo teams` |
| [Commands: Studio, design, media, Orchestra and teams](COMMANDS-studio.md) | you open Studio or run designs, media, an Orchestra goal or a team from the command line | `halo studio` · Design: a pack · `halo media` · `halo orchestra` · `halo team` · `/tasks` (Ctrl+T) · `halo completion` |
| [Commands: the supervisor, its goals and knowledge](COMMANDS-supervise.md) | you give Halo a goal to work on without sitting at a terminal, keep what it verified and decided, read what its agents' work showed, or isolate its workers | `halo supervise` · `halo goal` · `halo outcomes` · `halo knowledge` · `halo isolation` · `halo secrets` |
| [Commands: halo host](COMMANDS-host.md) | you run `halo host` on a machine that serves models, pair a harness with it, or install it as a service | `halo host serve` · `halo host status` · `halo host stop` · `halo host pair` · `halo host join` · `halo host install` · `halo host uninstall` · `halo host rpc` |
| [Commands: halo pool](COMMANDS-pool.md) | you put several machines' GPUs together for one model: list or edit the pool's members, scan the LAN for rpc-server ports, ask what the pool can run, or run the preflight, warm, stop and read the running pool | `halo pool members` · `halo pool add` · `halo pool remove` · `halo pool recommend` · `halo pool verdict` · `halo pool scan` · `halo pool preflight` · `halo pool rpc` · `halo pool status` · `halo pool stop` · `halo local serve --pool` |
| [Commands: halo copilot](COMMANDS-copilot.md) | you sign in to your work's Microsoft 365 Copilot from a terminal, ask it a question about your mail, meetings, chats or files, or sign out again | `halo copilot signin` · `halo copilot signout` · `halo copilot status` · `halo copilot ask` |
| [Commands: halo voice, the voice loop and the speech servers](COMMANDS-voice.md) | you talk to a session from the command line (`halo voice`, `halo voice on|off`, an input file, `halo voice client` through a halo host), list the microphones, read the voice turns' latency, or list, download, remove or serve a speech model | `halo voice` · `halo voice --input-file` · `halo voice on` and `off` · `halo voice devices` · `halo voice stats` · `halo voice models` · `halo voice download` · `halo voice rm` · `halo voice serve` · `halo local serve --stt` and `--tts` · `halo doctor --voice` |
| [Commands: a local server's log and events](COMMANDS-local-servers.md) | you want to read a llama-server, LM Studio or mlx_lm.server log from a terminal, see the events the steward found in it, or know why a server's log is not read | `halo local log <server> [-n N] [--kind fit\|headroom\|truncation\|failure\|all] [--follow]` · `halo local events <server> [--since 24h] [--kind K] [--from-start] [--json]` |
| [Commands: refresh, advise and the guards](COMMANDS-local-guards.md) | you re-measure stale local models by hand, ask Halo what to add or retire, or point a role at the nearest equivalent of a deleted tag | `halo local refresh` · `halo local advise` · `halo roles point` · `halo models probe hf:local/<model>` |
| [Commands: the steward's chat and candidates](COMMANDS-ollama-chat.md) | you ask the steward a question from a terminal, or want the list of models that could run it | `halo ollama steward chat` · `halo ollama steward candidates` |
| [Commands: remote control and the fleet](COMMANDS-fleet.md) | you control sessions remotely or run a fleet and its missions | `halo remote` · `halo fleet` |
| [Commands: packs](COMMANDS-packs.md) | you list, inspect, install, enable, grant, update, roll back or remove a pack, or name where packs come from, on the command line (`halo pack`) | `halo pack` · Bundles · Modes and policy hooks |
| [Commands: the pack kit](COMMANDS-packs-kit.md) | you start a pack, check one, or install your own folder so every edit shows at once (`halo pack new`, `halo pack test`, `halo pack install --link`) | `halo pack new` · `halo pack test` · `halo pack install --link` · `halo pack unlink` · the doctor's requirement rows |
| [Commands: workflows](COMMANDS-workflows.md) | you list, show, check or run a workflow (`halo workflow`), or list, enable and test squares (`halo workflows`) | `halo workflow` · `halo workflows` · `halo orchestra new --workflow` |
| [Commands: the proxy, exit codes and config checks](COMMANDS-proxy.md) | you run the old proxy, read an exit code, or list and check the config files in effect | `halo proxy` · Exit codes · `halo config where` and `halo doctor --config` (3.1.1.0) |
