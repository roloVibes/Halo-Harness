# Concord, as a Halo pack

[Concord](https://github.com/Get-Concord-AI/concord-mcp) (MIT) keeps a shared record of who works on what in one
repository: tasks with the files they claim, hand-offs, and messages between the agents working there (Claude Code,
Codex, Cursor, Gemini, ...). This pack lets a Halo session take part: it runs your own `concord-mcp` as an MCP server,
carries Concord's message-delivery hooks, and adds a policy that keeps a session's writes off files another task
claims while you coordinate. It ships with Halo (`halo pack list --available`) and stays off until you turn it on.

**Telemetry.** Concord's telemetry to getconcord.ai is on by default upstream (the server keeps request IP and
country without automatic expiry, its own notice says); this pack turns it off: the MCP server, every hook command
and the policy's `concord check` run with `CONCORD_TELEMETRY_DISABLED=1`.

## Install Concord (once per machine; Halo never does this for you)

```sh
npm install -g @concord-ai/concord-mcp
```

That puts `concord-mcp` (the MCP server) and `concord` (the CLI the hooks and the policy run) on your PATH. In the
repository you coordinate in, run Concord's own setup once to create its `.concord/` folder (`concord setup --no-mcp
--no-adapters`: the pack registers the server and carries the hooks itself; Concord's setup also writes its own
instruction block into the repo's agent files, which is Concord's doing, not the pack's). Until `concord-mcp` is on PATH, `halo pack doctor` says so in
one row (`not-on-path`).

## Turn it on

```sh
halo pack install concord
halo pack enable concord --grant hooks --grant mcp:concord
halo pack mode concord coordinating on      # arms the claimed-files policy
```

Concord tells agents apart by an id. Claude Code hands it its session id; Halo does not, so name the Halo session
before you start it: `export CONCORD_AGENT_ID=halo-main` (PowerShell: `$env:CONCORD_AGENT_ID = "halo-main"`). To keep
your own claim from counting against your own writes, also set `CONCORD_TASK=<your task id>` (the variable Concord's
own Claude Code hook reads); without it, any active claim on a file counts.

## What each file is

| File | What it does |
|---|---|
| `pack.yaml` | the manifest: the MCP server, the hooks, the `coordinating` mode, the `claimed-files` policy, `permissions: [hooks, "mcp:concord"]` |
| `.mcp.json` | the `concord` server: `concord-mcp` with `CONCORD_TELEMETRY_DISABLED=1` and `CONCORD_REPO_ROOT=${CLAUDE_PROJECT_DIR}` (Halo puts the project folder in) |
| `hooks/hooks.json` | Concord's Claude Code hook commands, below |
| `policy/claimed_files.py` | the policy: `concord check [--task $CONCORD_TASK] <path>` for each Write or Edit; exit 1 is a deny with `concord: <path> is claimed by task <id>`; no `concord` on PATH, a timeout or another exit is allow (and `on_error: allow`), so a box without Concord blocks nothing |
| `.claude-plugin/plugin.json` | the Claude-plugin half's name |

## The hook commands, and where they come from

Read from the upstream repository at commit `75c4516060948d4f6d07ba886305cd283ffae04b` (2026-11-02):
`plugin/concord-relay/hooks/hooks.json`, the `concord-relay` plugin `concord setup` installs for Claude Code, and
`docs/claude-code.md` (the read-receipt rules: UserPromptSubmit records what the prompt showed, PostToolUse and Stop
deliver what arrived mid-turn, SessionEnd puts unread messages back). Upstream, exactly:

```
UserPromptSubmit   concord inbox observe
PostToolUse        concord inbox drain --from-hook --format post-tool-use
Stop               concord inbox drain --from-hook --format stop
SessionEnd         concord inbox observe
```

The pack runs each with `CONCORD_TELEMETRY_DISABLED=1 ` in front (a hook's command runs in a shell). Not taken from
that plugin in this version: its SessionStart (`concord inbox register`, `concord inbox observe`), PreToolUse on
AskUserQuestion and Notification (`concord inbox observe`: the waiting-on-the-user flag), and its idle monitor
(`monitors/monitors.json`, `scripts/watch-inbox.sh`, a Claude Code experimental feature Halo does not run). The
policy's command is `src/cli/commands/check.ts` (`concord check [--task <id>] <file>...`: exit 1 on an overlap with
another active task, each `  - <task id> (<title>): same file(s): ...`).

## The live check

A Halo session and a Codex session in one repository, both with Concord installed and `concord setup` run once
(Codex needs its adapter, so there without `--no-adapters`): in Halo, `halo pack mode concord coordinating on`; the Codex session starts a task that claims a file; the Halo
session is asked to write that file, and the tool result is the pack's line, `policy: deny -- claimed-files: concord:
<path> is claimed by task <id> (pack concord, rule claimed)`; the two sessions trade a prompt and a reply through
Concord's messages. `halo pack policy log concord` lists the verdicts.
