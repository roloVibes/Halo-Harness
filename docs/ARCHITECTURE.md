# Architecture

Read this when you want how Halo works inside: the session loop and every subsystem around it.

How a keystroke becomes a model request, how that request is reconstructed
from history every single time, and how every subsystem around that loop
(permissions, hooks, MCP, compaction, sub-agents, telemetry) plugs into it.
Verified against the modules named in each section, not memory. For
*where* the config driving each of these lives, see
[CONFIG.md](CONFIG.md); for the CLI/slash-command surface built on top of
it, see [COMMANDS.md](COMMANDS.md) and [SLASH-COMMANDS.md](SLASH-COMMANDS.md).

```
 prompt / steer                                    ┌─────────────┐
      │                                             │  TUI (app.py)│
      ▼                                             │  or -p print │
┌───────────┐   append_user()   ┌───────────────┐   │  mode        │
│  Session  │ ─────────────────▶│  SessionLog   │◀──┤  (headless.py)│
│ (agent/   │                   │ (append-only  │   └──────┬──────┘
│  loop.py) │◀── derive_request()  JSONL)        │          │ events
└─────┬─────┘                   └───────────────┘          ▼
      │ build request body                              drain_queue /
      ▼                                                  apply_event
┌───────────────┐   profile    ┌────────────────────┐
│ providers/    │◀─────────────│ providers/profiles  │
│ request.py /  │              │  .py (per-family)   │
│ anthropic_sse │              └────────────────────┘
└──────┬────────┘
       ▼
  HTTP to OpenRouter / Databricks / api.anthropic.com / the `claude` binary
       │
       ▼
┌───────────────┐  tool_use   ┌────────────────┐  permission  ┌──────────┐
│ providers/    │────────────▶│ repair layer   │─────decide──▶│ Permission│
│ stream.py     │             │ (agent/repair) │              │ Engine    │
└───────────────┘             └───────┬────────┘              └────┬─────┘
                                       ▼                            │allow
                                ┌─────────────┐   dispatch          ▼
                                │ ToolRegistry│◀───────────── tools/*.py
                                └──────┬──────┘
                                       ▼
                              tool_result → SessionLog.append_tool_result()
                                       (back to the top: derive again)
```

This page is the entry point; the content lives in the parts below, one per task.

## The parts

| Part | Read it when | What is in it |
|---|---|---|
| [Architecture: the session loop](ARCHITECTURE-session.md) | you change how a request is built: the session log, pruning, providers, reasoning replay, the tool catalog and the repair layer | The session log is the single source of truth · Deriving and pruning a request · Providers and compatibility profiles · Reasoning replay per family · The frozen tool catalog and ToolSearch · Tools and the repair layer |
| [Architecture: permissions, hooks and MCP](ARCHITECTURE-permissions.md) | you change permission rules and modes, the hooks protocol, or how MCP servers start and cache | Permissions: grammar, modes, and what "auto" means here · Hooks protocol · MCP: scopes, lazy start, cache, plugin servers |
| [Architecture: steering, compaction, sub-agents and telemetry](ARCHITECTURE-runtime.md) | you change steering and interrupts, compaction, sub-agents and plan mode, or telemetry | Steering, interrupts, and pairing invariants · Compaction · Sub-agents and plan mode · Telemetry and `/improve` |
| [Architecture: the TUI event model](ARCHITECTURE-tui.md) | you change how the TUI turns session events into widgets | The TUI event model |
| [Architecture: the module map](ARCHITECTURE-modules.md) | you look for the module behind a Studio, fleet, Orchestra or team feature | Module map: Studio, fleet, Orchestra, team |
| [Architecture: the module map, part two](ARCHITECTURE-modules-two.md) | you look for the module behind the Ollama steward, packs, the extension API, isolation, Setup or Settings | Module map, part two: the steward, packs, isolation, Setup, Settings |
