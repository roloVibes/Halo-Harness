# Agents

Read this when you want to know what an agent is in Halo, where its file lives and how a session reaches it.

Halo 3.6.0.0 has one way to set up agents: **agent -> workflow -> map**. An agent is one file saying what it does,
which model it runs on and which tools it may use; a workflow is steps of agents; a map connects the agents and
workflows main may hand work to. Bios and lineups (3.5) are gone and their files are not read:
[MOVING-from-3.5.md](MOVING-from-3.5.md) says what to use instead.

## Where agent files live

| Place | Folder | Note |
|---|---|---|
| Yours | `~/.halo/crew/agents/<name>.yaml` | the ones you make |
| This project's | `<repo>/.halo/crew/agents/<name>.yaml` | read only in a folder you trusted |
| An enabled pack's | the pack's `crew/agents/` | named `<pack>--<name>`, read in place |
| The ones that ship with Halo | shipped with Halo | read-only; `halo agents copy <name>` makes your own copy to edit (`--as <name>` names it) |

The format (`agent/1`: `does`, `instructions`, `model`, `needs`, `uses`, `careful`, `more`) is in
[CREW-FORMATS.md](CREW-FORMATS.md). `model: auto` picks a model for each task from your catalog by what the agent
`needs` (images, audio, video, pdf, reasoning, long-text, tools); a model of your own pins it.

## Making and changing an agent

- **Studio**: Agents -> 1 · Agents is the editor: the form, Write it for me, Try it, the builder box
  ([STUDIO-agents.md](STUDIO-agents.md)).
- **Terminal**: `halo agents list | show | new | copy | edit | try` ([COMMANDS-agents.md](COMMANDS-agents.md)).
- An agent does nothing until a map connects it, or until main names it in an `Agent` call.

## How a session reaches an agent

A session runs on the map in use (`halo maps use <name>`, `--map <name>`, Studio's Agents -> 3 · Map). With no map
set it runs exactly as a plain session always did, drawn as Auto (the default)
([CREW-sessions.md](CREW-sessions.md)). Main hands work along the map's lines through the `Agent` tool; each line
says when (a need such as a PDF, words in the task, or always).

The model table (`roles.<name>` in config, `halo roles point <role> <model>`) still decides which model a plain
session's helper of that name runs on: [ROLES.md](ROLES.md).

## Claude Code's sub-agents

Halo also reads Claude Code's own agent definitions in place (`~/.claude/agents/*.md`, a project's
`.claude/agents/*.md`, a plugin's): main spawns them by name with `Agent(subagent_type=...)`.
[SUBAGENTS.md](SUBAGENTS.md) has the rules (depth, concurrency, background runs).

## The `Workflow` tool: squares

Beside `Agent`, main has `Workflow(need | name, task, files)`: it hands a task to a workflow **square** (a saved
orchestration with a contract: what it takes, what it gives, the needs it covers) and answers with one receipt line
and what came back. The squares a session may use are config's: `workflows.enabled` (default `media`), and a square's
rule for when main uses it is `workflows.when.<square>`. Details: [WORKFLOWS-squares.md](WORKFLOWS-squares.md).

## The `copilot_ask` tool and `cp:work`

Once `copilot.tenant` and `copilot.client_id` are set, every session's tools include `copilot_ask {prompt, files?,
web?}`: it asks your work's Microsoft 365 Copilot and answers with the text and its citations. An agent may run on
Copilot itself with `model: cp:work`. Sign-in and every error line: [PROVIDERS-copilot.md](PROVIDERS-copilot.md).
