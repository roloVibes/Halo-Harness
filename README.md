# Halo Harness

```
 _   _      _      _        ___
| | | |    / \    | |      / _ \
| |_| |   / _ \   | |     | | | |
|  _  |  / ___ \  | |___  | |_| |
|_| |_| /_/   \_\ |_____|  \___/
```

**The Claude Code-compatible harness for people who'd rather not be
locked into one AI coding ecosystem.**

Halo gives DeepSeek, GLM, Kimi, Qwen and Claude the same tools, the same
configuration and the same working habits as Claude Code -- over OpenRouter,
Databricks, the Anthropic API, the OpenAI API, your Claude Code or Codex
subscription, Ollama, Hugging Face, or any OpenAI-compatible server you
host -- and it reads your existing Claude Code setup in place
(`~/.claude` settings, CLAUDE.md, skills, commands, agents, MCP servers,
memory), so nothing is configured twice. Switch models mid-conversation
with `/model`; the session context comes with you. The same banner prints
on `halo --version`, and the launch intro types it out.

<p align="center">
  <img alt="version 2.0.7" src="https://img.shields.io/badge/version-2.0.7-5b4bd6">
  <img alt="python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776ab">
  <img alt="Linux first" src="https://img.shields.io/badge/platform-Linux%20first%20%7C%20macOS%20%7C%20Windows-2b2b2b">
  <img alt="tests" src="https://img.shields.io/badge/tests-4100%2B%20hermetic-2e8b57">
</p>

> **Using your Claude Code or Codex subscription through Halo.** The
> `cc:`/`cx:` routes drive the official `claude`/`codex` binaries under
> your own personal subscription, through a third-party harness that is
> not the provider's own product -- the provider's own terms govern your
> account, and there have been public reports of account restrictions for
> tools that use subscription tokens this way. Halo never reads either
> tool's stored credentials, and these two routes are **off until you
> accept** a one-time notice (`halo subscriptions accept`, or
> `/subscriptions` in the TUI) -- see
> [docs/MODELS.md](docs/MODELS.md#subscription-routes-consent-halo-207-round-7b).

## What it looks like

Real renders of the TUI, produced by `scripts/screenshots.py` -- Textual
pilots over fixture data with a fixed clock, so a rerun is byte-identical
(`python scripts/screenshots.py && git diff` shows nothing).

| Scene | What it shows |
|---|---|
| ![First launch](docs/screenshots/launch.svg) | First paint: the banner intro line, the prompt, the status bar. |
| ![A turn](docs/screenshots/turn.svg) | A reply mid-turn: the phase line, a running tool card, live counters. |
| ![The model picker](docs/screenshots/picker.svg) | The model picker: price, context and speed columns for every route. |
| ![The Team step](docs/screenshots/team-step.svg) | The wizard's Team step: custom roles on, the lineups pane (one pane at a time, roles explained as you go). |
| ![MCP status](docs/screenshots/mcp.svg) | The `/mcp` dialog: one failing server, its reason, the deep-dive action. |
| ![A permission ask](docs/screenshots/permission.svg) | A permission card docked above the prompt with its suggested rule. |
| ![Balances](docs/screenshots/balances.svg) | The balances chip in the status bar and the `/balances` table. |

## Features

| | |
|---|---|
| **Switch models mid-conversation** | `/model` swaps the lane without losing session context -- prompt, tools and history come with you. |
| **A provider per role** | YAML agent bios and lineups assign a model to each job: GLM can orchestrate while a local Qwen implements and a cheap flash model reviews. `halo teams use <lineup>` applies one. |
| **Steering** | Type while a turn runs and the steer reaches the work: a running command moves to the background instead of dying, sub-agents get your words forwarded into them, nothing is lost. |
| **Per-model tool-call repairs** | Fourteen model families' quirks are repaired on the fly -- Kimi's `functions.{name}:{idx}` ids, GLM's always-on thinking, Qwen's system-message rules, DeepSeek's reasoning echoes. Gateway quirks are learned once per model and remembered (`halo rules`). |
| **Measured, not guessed** | `/stats` per model and per tool, price/context/speed columns in the picker, per-role cost attribution, and `halo preflight` canaries each lane before a long run (a tool call the model must actually emit, an image a "vision" model must actually accept). |
| **Filter-aware routing** | A provider content filter is not an answer: a filtered reply never persists as one, and the request reroutes to a fallback lane you choose. |
| **Permissions without a nanny** | Auto mode allows everything except *your own* deny/ask rules -- no built-in safety classifier, no protected-path heuristics, no refusal layer. Rules use Claude Code's own grammar, in the same files. |
| **Routes** | `dbx:` `or:` `ant:` `cc:` `cx:` `oai:` `ol:` `hf:` `local:` -- one session, any of them. |
| **The wizard** | `halo init`: provider, model, permission mode, theme, roles, orgs -- every step explains itself and `halo doctor` ends each warning with its fix. |
| **MCP deep dive** | stdio/HTTP/SSE servers from every Claude Code scope, `D` diagnoses a failing server end to end, claude.ai connectors bridge through as tools. |
| **Balances and picker columns** | Per-provider balances in the status bar (remaining first); free variants sit beside their paid rows in the picker. |
| **Privacy audit** | `halo audit privacy` scans the tree for real paths, hosts and key-shaped strings; the release refuses to ship one red line. |
| **CI and release script** | Every push runs the three suites on Linux and Windows; `scripts/release.py` versions, tags, pushes and refreshes both installs. |

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/roloVibes/Halo-Harness/master/scripts/install-halo.sh | bash
halo init        # the wizard: provider, model, permission mode, theme, roles
halo             # the full-screen TUI, from any directory
```

Windows: `powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/roloVibes/Halo-Harness/master/scripts/install-halo.ps1 | iex"`.
No installer at all: `uv tool install git+https://github.com/roloVibes/Halo-Harness`
(or `pipx install git+https://github.com/roloVibes/Halo-Harness`). Updates:
`halo update`, or `/update` inside the TUI.
The full walkthrough -- offline work boxes, PEP 668, reproducible installs --
is [docs/INSTALL.md](docs/INSTALL.md).

## Themes

The gallery above is the default theme.

> The 2.0.8 theme pack adds one render each: **DOOM** (a HUD-style status
> bar, `/doom` toggles it and restores your previous theme), **Metroid**,
> and **Mario**.

## Documentation

| Document | What it covers |
|---|---|
| [docs/INSTALL.md](docs/INSTALL.md) | One-page install, upgrade and update guide |
| [docs/HANDBOOK.md](docs/HANDBOOK.md) | The long-form guide: configuration, providers, permissions, steering, hooks, skills, MCP, sessions, telemetry |
| [docs/COMMANDS.md](docs/COMMANDS.md) | Every CLI command and flag |
| [docs/SLASH-COMMANDS.md](docs/SLASH-COMMANDS.md) | Every slash command in the TUI |
| [docs/CONFIG.md](docs/CONFIG.md) | Config keys, paths and environment variables |
| [docs/MODELS.md](docs/MODELS.md) | Model families, effort levels and per-route rules |
| [docs/LOCAL-MODELS.md](docs/LOCAL-MODELS.md) | Ollama, Hugging Face, the OpenAI API and Codex -- end to end |
| [docs/DATABRICKS.md](docs/DATABRICKS.md) | Databricks endpoints, API types and the work matrix |
| [docs/ROLES.md](docs/ROLES.md) | Roles, agent bios and lineups |
| [docs/GOVERNOR.md](docs/GOVERNOR.md) | The Governor: shared per-host rate limiting, failover and lanes |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | "Is it frozen?", GLM pauses, copy and paste, connect timeouts |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the pieces fit together |
| [docs/harness/README.md](docs/harness/README.md) | Design briefs, review findings, acceptance records |
| [CHANGELOG.md](CHANGELOG.md) | Every release, with what changed and why |

## Tests

Three hermetic, exit-code-gated suites run on Windows, WSL and a Kali VM
before every commit, and in CI on every push: `python test_bridge.py` (the
proxy), `python tests/run_all.py` (the harness) and `python test_tui.py`
(the TUI, through Textual's headless pilot). Mock servers stand in for every
provider, a fake `claude` stands in for the subscription route, and guards
fail the run if a test touches the real `~/.halo` or `~/.claude`. See
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Licence

See [LICENSE](LICENSE).
