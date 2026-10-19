# Slash commands, keys, and prompt prefixes

Read this when you want what a `/command`, a key or a prompt prefix does in the TUI.

Everything the full-screen TUI's prompt input understands: `/name` slash
commands (built-in, custom, skill-provided, MCP-provided), the `@path`/
`!cmd` prefixes, key bindings and chords, and the cards a permission/
question/plan/rewind/improve moment shows -- with the exact keys each one
answers to. For the headless CLI surface (`halo <subcommand>`), see
[COMMANDS.md](COMMANDS.md).

**How this page is kept honest**: `tests/test_docs_slash_commands.py`
imports the real command registry (`halo_harness.commands.registry.Registry`)
and `halo_harness.commands.builtins._BUILTIN_SPECS`, and fails the suite if a
registered built-in command has no `### \`/name\`` section in this page or
one of its parts.

Every built-in command works the same in `-p` print mode and the TUI for
its **core**-kind behavior (`/cost`, `/help`, `/context`, ...); a handful of
**ui**-kind commands (`/resume`, `/plan`, `/rewind`, ...) need the
interactive picker/card machinery and, in `-p`, print one honest line
saying so instead of performing the action -- these are marked `[TUI-only]`
below. `/init` is the one **prompt**-kind command: its "output" is a real
prompt fed back into the model, not printed directly.

This page is the entry point; the content lives in the parts below, one per task.

## The parts

| Part | Read it when | What is in it |
|---|---|---|
| [Slash commands: sessions, models and context](SLASH-COMMANDS-session.md) | you manage the session, its model, memory, permissions or config from the prompt (`/clear`, `/model`, `/recall`, `/config` ...) | Built-in commands · `/help` · `/clear` · `/compact` · `/cost` · `/context` · `/model` · `/models` · `/dbx` · `/xp` · `/mcp` · `/ollama` · `/local` · `/memory` · `/recall` · `/ask` · `/permissions` · `/plan` · `/resume` · `/status` · `/config` · `/skills` |
| [Slash commands: agents, lineups, roles and review](SLASH-COMMANDS-agents.md) | you work with bios, lineups, roles or `/review` from the prompt | Built-in commands: agents, lineups, roles and review · `/agents` · `/teams` · `/roles` · `/role` · `/review` · `/setup` |
| [Slash commands: providers, fleet and upkeep](SLASH-COMMANDS-providers.md) | you set up providers, subscriptions, rate limits, remote control or the fleet, or run `/doctor`, `/update` and `/bugreport` | Built-in commands: providers, fleet and upkeep · `/providers` · `/subscriptions` · `/gov` · `/balances` · `/rules` · `/settings` · `/effort` · `/remote` · `/private` · `/mission` · `/fleet` · `/offline` · `/escalation` · `/init` · `/doctor` · `/update` · `/export` · `/bugreport` · `/timeline` · `/add-dir` |
| [Slash commands: themes, Studio and the TUI](SLASH-COMMANDS-tui.md) | you change themes, open Studio, copy, rewind or tune the TUI, run the ten-minute start, look up a word, or add your own commands, skills and images | Built-in commands: themes, Studio and the TUI · Custom commands and skills · Image attachments |
| [Slash commands: prefixes, keys and cards](SLASH-COMMANDS-keys.md) | you want the `@path` and `!cmd` prefixes, a key binding, or the keys a card answers to | Prefixes in the prompt input · Key bindings · Cards and their keys |
