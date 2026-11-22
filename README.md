<p align="center">
  <a href="docs/media/hero.png"><img alt="Halo Harness: the wordmark over Studio's Session dashboard, every agent live" src="docs/media/hero.png" width="100%"></a>
</p>

<p align="center">
  <a href="https://github.com/roloVibes/Halo-Harness/releases"><img alt="version 3.6.0.11" src="https://img.shields.io/badge/version-3.6.0.11-5b4bd6"></a>
  <a href="https://github.com/roloVibes/Halo-Harness/actions/workflows/suites.yml"><img alt="CI" src="https://github.com/roloVibes/Halo-Harness/actions/workflows/suites.yml/badge.svg"></a>
  <img alt="python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776ab">
  <img alt="Linux, macOS, Windows" src="https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-2b2b2b">
  <a href="LICENSE"><img alt="MIT" src="https://img.shields.io/github/license/roloVibes/Halo-Harness?color=2e8b57"></a>
  <a href="https://discord.gg/NXWXdg7B6v"><img alt="Discord: join the Halo Harness server" src="https://img.shields.io/badge/Discord-join%20the%20server-5865F2?logo=discord&logoColor=white"></a>
</p>

[![M8ven Score](https://m8ven.ai/badge/mcp/rolovibes-halo-harness-b6hvi0?v=56463921c5e318696a7daa26849ddc55)](https://m8ven.ai/mcp/rolovibes-halo-harness-b6hvi0?s=readme)

<h3 align="center">Multi-agent. Multi-workflow. Fully visible.</h3>

<p align="center">
The multi-agent, multi-workflow harness you can watch: every model's thinking, hand-offs and cost, live, and yours to steer.
</p>

See, shape and steer multi-model agent work, on any model, including your own. Halo runs the agent loop (a prompt,
tool calls, permission rules, hooks, MCP servers, skills, sub-agents, sessions) on the models you choose, and Halo
Studio, a page in your browser, is where you watch it and change it.
Opens and drives a browser by itself (Chrome, Chromium, Edge or Brave already on the machine).

<p align="center">
  <a href="#see">See</a> ·
  <a href="#shape">Shape</a> ·
  <a href="#mix">Mix</a> ·
  <a href="#local">Local</a> ·
  <a href="#start">Start</a> ·
  <a href="#install">Install</a> ·
  <a href="#everything-else-is-a-pack">Packs</a> ·
  <a href="#links">Docs</a> ·
  <a href="https://discord.gg/NXWXdg7B6v">Discord</a>
</p>

<details>
<summary>The same wordmark as text (what an interactive <code>halo</code> start shows)</summary>

```text
    ░▒▓▓▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▓▓▒░
  ▒▓█▀                               ▀█▓▒
    ░▒▓▓▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▓▓▒░
    ██╗  ██╗ █████╗ ██╗      ██████╗
    ██║  ██║██╔══██╗██║     ██╔═══██╗
    ███████║███████║██║     ██║   ██║
    ██╔══██║██╔══██║██║     ██║   ██║
    ██║  ██║██║  ██║███████╗╚██████╔╝
    ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝ ╚═════╝
```

</details>

## See

<a href="docs/media/studio-session.gif"><img alt="Studio's Session dashboard: every agent's thinking, tool calls, hand-backs and an ask card scrolling in the Live column, the agent tree and the cost beside it on the right" src="docs/media/studio-session.gif" width="100%"></a>

Every agent of a session in one live column: what it thinks (THINK), what it says to another agent (TALK), each tool
call with its time and result, and what each agent costs, beside a tree of who spawned whom. Agents -> Map is where
your agents are connected: while a session runs, its map lights up (who works, who waits on what, one sentence that says
what is going on). A finished goal run's report is its own page, and any session can be kept as one Markdown file,
the session export.

**How:** `halo studio`, then Session (`Alt+1`) or Agents -> Map (`Alt+2`, `3`); `/studio` from a terminal session.
[Session](docs/STUDIO-sections.md#session) · [the lit map](docs/STUDIO-live.md)

## Shape

<a href="docs/media/studio-map.png"><img alt="Studio's Agents section on 3 · Map: main and the agents it hands work to, each line labelled with its when, the map picker with New sessions run on this, Run a goal and the builder box under the map" src="docs/media/studio-map.png" width="100%"></a>

Your map connects agents and workflows (steps of agents) that main hands work to, each line labelled
with its `when` (a need such as a PDF, words the task says, or always first). Add a box from the list beside the map;
each add says what it adds and costs before it happens. Steer a running turn from Session's Steer box (main, or the
agent you pin), and run a goal (several agents writing the same files, each in its own git worktree) from the Map's
**Run a goal**.

**How:** Agents -> Map (`Alt+2`, `3`); `halo agents`, `halo workflows`, `halo maps`.
[Agents](docs/STUDIO-agents.md) · [the Map](docs/STUDIO-map.md) · [steering](docs/STUDIO-session.md) · [goal runs](docs/ORCHESTRA.md)

## Mix

<a href="docs/media/studio-agents-tab.png"><img alt="Studio's Agents section on 1 · Agents: your agents and the ones that ship with Halo to copy, an agent's form with how careful it is, Try it run once on a throwaway copy with what it cost, and the builder box under it" src="docs/media/studio-agents-tab.png" width="100%"></a>

One job, many models: each agent runs on its own model, across OpenRouter, Databricks, Anthropic, OpenAI,
Ollama, Hugging Face, your work's Microsoft 365 Copilot or any OpenAI-compatible server. An agent on `model: auto` gets
a model picked for each task, which learns from what succeeded here. `/model` swaps the model mid-session; the history, tools and rules
come along.

**How:** Agents -> 1 · Agents, an agent's model picker; `halo agents`; `/model` in a session.
[Models](docs/MODELS.md) · [Auto and the model table](docs/ROLES.md#auto) · [providers](docs/MODELS-references.md)

## Local

<a href="docs/media/studio-local.png"><img alt="Studio's Local section on Resources: two machines' VRAM, GPU, RAM, CPU and temperature live, and every call to a local server as it happens, with its model, tokens in and out, window and result" src="docs/media/studio-local.png" width="100%"></a>

Your own models are first-class. The steward, a small model you pick, watches every local server once you turn it on
(Settings -> Ollama; off by default since 3.6), explains a failed call and plans what fits the card. Each model carries a fit badge per host, and benchmarks measure what it does there.
`halo host serve` lets every harness on your network read a machine's models and log, the pool runs one model across
the GPUs of several machines, Halo finds the Ollama servers on your network, and it starts local servers for
Hugging Face models.

**How:** Local (`Alt+3`, or `halo local`); `halo host serve`, `halo pool`, `halo ollama discover`.
[Local](docs/STUDIO-local.md) · [the steward](docs/MODELS-ollama-steward.md) · [host](docs/HOST.md) · [pool](docs/POOL.md)

## Start

<a href="docs/media/studio-setup.png"><img alt="Studio's Setup section as halo init opens it: the step rail across the top, the line saying set up this box, OpenRouter set from the env file with its last four characters, the default model and the permission mode; the first page, Providers, one card per provider" src="docs/media/studio-setup.png" width="100%"></a>

Setup is a page in Studio: one step at a time, Back and Next, a Summary last. If you already use Claude Code, Halo
reads that setup where it is (settings, CLAUDE.md, skills, agents, commands, MCP servers) and Setup never writes to it.
No Claude Code? Halo needs none: pick a provider and a model, and start.

**How:** `halo init` (Setup is `Alt+5` later; `halo init --terminal` asks the essentials in a console).
[Setup](docs/STUDIO-setup.md) · [install](docs/INSTALL.md)

## Honest about what it knows

Halo records what each agent's work showed (its tests, commands, files) and routes by it; a hand-off to a workflow
leaves a receipt; a price or a context it cannot know is shown as `?`, and a cost it cannot price is unknown, never
`$0`. [Verified outcomes](docs/OUTCOMES.md) · [receipts](docs/WORKFLOWS-squares.md)

## Claude Code compatible

The on-ramp: Halo reads `~/.claude` settings, `CLAUDE.md`, skills, commands, agents, hooks, MCP servers and memory in
place, permission rules use Claude Code's grammar, and your claude.ai connectors reach whatever model drives Halo.
[Handbook](docs/HANDBOOK.md)

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/roloVibes/Halo-Harness/v3.6.0.11/scripts/install-halo.sh | bash
```

Windows:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/roloVibes/Halo-Harness/v3.6.0.11/scripts/install-halo.ps1 | iex"
```

The installer is fetched from a release tag and installs the newest tag; `--ref <tag>` (`-Ref` on Windows) pins
another. It may run `uv tool update-shell` to put `~/.local/bin` on your PATH: it asks first, and `--no-modify-path`
(`-NoModifyPath`, or `HALO_NO_MODIFY_PATH=1`) skips it. No installer:
`uv tool install git+https://github.com/roloVibes/Halo-Harness --constraints https://raw.githubusercontent.com/roloVibes/Halo-Harness/master/requirements.lock`
or `pipx install git+https://github.com/roloVibes/Halo-Harness`. Offline boxes and PEP 668: [docs/INSTALL.md](docs/INSTALL.md).

**Update:** `halo update` (or `/update` in a session); `halo update --check` says what it would do. An install older
than 3.3.16.0 that stops at `invalid peer certificate: UnknownIssuer` cannot update itself past it; this line repairs it
once (`$env:UV_SYSTEM_CERTS='1'; $env:UV_NATIVE_TLS='1'; uv tool install ...` in PowerShell,
[docs/INSTALL.md](docs/INSTALL.md) has both):

```sh
UV_SYSTEM_CERTS=1 UV_NATIVE_TLS=1 uv tool install --reinstall git+https://github.com/roloVibes/Halo-Harness
```

**From 3.5.0.1, once:** on Windows, do not run `halo update` in a shell: 3.5.0.1's own updater reinstalls from inside
the running halo and can leave the install half replaced. Type `/update` in a session instead (it installs after that
halo has exited), or close every Halo window, run `halo studio --stop`, and run the repair line (the installer does the
same, and stops while a halo still runs):

```powershell
uv tool install --reinstall --constraints https://raw.githubusercontent.com/roloVibes/Halo-Harness/v3.6.0.0/requirements.lock "git+https://github.com/roloVibes/Halo-Harness@v3.6.0.0"
```

On every platform, if you turned on `halo host install`, run `halo host stop` first: 3.5.0.1's updater does not see the
LAN host. From 3.6.0.0 on, `halo update` sees and stops both itself.

**Your first run:**

1. `halo init` opens Studio on Setup: paste a provider key, pick a default model and a permission mode.
2. `halo` in any folder starts a session; type a request, and type again while it works to steer it.
3. `/studio` (or `halo studio`) opens the dashboard on that session; `halo doctor` explains anything that is not right.

## Everything else is a pack

The core is what the five above need. The rest ships as packs, off until you turn one on:
`halo pack install <id>`, then `halo pack enable <id> --grant-all` (or Studio's Packs, `Alt+4`).

| Pack | What it adds |
|---|---|
| `first-run` | The guided first run: `halo start`, one real goal run on a sample repo |
| `coach` | The post-run coach: suggestions from a finished run, Apply after one confirm, `halo improve` |
| `design` | Prototypes, pages, decks and logos on artboards in Studio, made by a Halo turn |
| `signal` | Halo on your phone as a chat: a text message starts or continues a session (it runs signal-cli) |
| `concord` | Joins a repo's Concord workspace, so a session claims work and trades messages with other agents |
| `doc-review` | Reviews a repo's Markdown documents with a reviewer and a writer, and a typed review report |

Write your own: `halo pack new <id>` starts one, [docs/PACKS.md](docs/PACKS.md) says how a pack plugs in, and the
template repo [halo-pack-template](https://github.com/roloVibes/halo-pack-template) is a ready GitHub starting point.

## Links

- [Discord](https://discord.gg/NXWXdg7B6v): the Halo Harness server. Ask a question, show what you built, talk to the author.
  (A security problem goes through [SECURITY.md](SECURITY.md), not a public channel.)
- [The docs map](docs/README.md): every doc, by what you want to do.
- [CHANGELOG.md](CHANGELOG.md): every release, what changed and why.
- [Moving from 3.5: lineups, bios and blocks are gone, Studio closes with its command, the steward is off until you turn it on](docs/MOVING-from-3.5.md): what to use instead and what else changes in 3.6.
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) and [SECURITY.md](SECURITY.md): sending a change, reporting a problem.
- Licence: MIT, see [LICENSE](LICENSE).
