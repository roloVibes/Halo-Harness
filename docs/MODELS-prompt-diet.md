# Models: the local prompt diet

Read this when you want to know what Halo's own first turn costs a local model before you use it, why a tool is not in a local model's list, or why the reply's room is smaller than 16,384.

Part of [Models](MODELS.md), which lists every part.

## Why

Halo 3.3.16.1. Every token Halo spends on itself is one the conversation does
not get. Measured on 3.3.16.0 (a first turn to an unknown Ollama model, one
plain "hi", the test rig's fake home): 29 tools on the wire (about 9,300
tokens, `Agent` and `Task` the same tool twice), a system message of about
7,260 tokens, and a reply's room of 16,384 whatever the window. Prompt plus
room came to 33,354: past a 32,768 window, so the window doubled to 65,536
and the model reloaded at a size its card may not hold on the GPU.

## Before and after

The same first turn measured on both (`agent/prompt_measure.py`, a fake home
with a 250-line MEMORY.md and two topic files, Windows tools): Halo's own
prompt, the reply's room, and the window it goes out at.

| Case | 3.3.16.0 | 3.3.16.1 |
|---|---|---|
| an unknown remote model (the 32,768 default) | 16,639 + 16,384 -> 65,536 | 7,778 + 8,192 -> 32,768 |
| a 16,384 window | 16,640 + 16,384 -> 65,536 | 6,232 + 4,096 -> 16,384 |
| a 49,152 window | 16,637 + 16,384 -> 49,152 | 7,776 + 12,288 -> 49,152 |
| a 65,536 window (lean) | 16,637 + 16,384 -> 65,536 | 7,776 + 16,384 -> 65,536 |
| a 200k cloud model | 16,627 + 16,384 | 16,627 + 16,384 (unchanged, byte for byte) |

On Linux the numbers are within a few dozen tokens (one shell either way).
The tool block of the lean cases is 3,747 tokens (25 tools; 2,160 and 13
tools at 16,384); the lean system message, memory included, is 3,792.

## What changed

**The reply's room follows the window** (`agent/reply_room.py`). A call to
the session's own Ollama model asks for at most a quarter of the window it
gets, never under the window class's floor (2,048 under 16,384, 4,096 under
32,768, 8,192 under 65,536, 16,384 from there): 8,192 at 32,768, 12,288 at
49,152. A request is only ever lowered to that, never raised. A steward
profile's `num_predict` and a `max_tokens` you set keep their own rule. A
session's first call starts in a window where Halo's own prompt is half at
most (an 8,192 conservative default holds Halo's prompt and little else, and
compaction cannot shrink Halo's own part), and no later call drops under the
window the session last asked of the model, so it is not reloaded. The turn
says it once per session: "the reply's room is 8,192 tokens, sized by the
32,768 window (a quarter at most; it was 16,384) so the window does not grow
for it". A reply that runs into a room the window squeezed still takes the
trim recovery (`squeezed_cut`); one that stops at its own room ends the turn
as a max_tokens stop, as before.

**An alias goes on the wire once** (`agent/prompt_diet.py`, `ALIASES`).
`Task` and `Agent` are one tool: the lean wire carries `Agent`, and a call
named `Task` still resolves and runs. Bios and rules that name `Task` keep
working. A test fails when two registry tools share a definition and are not
in `ALIASES`.

**One shell on Windows.** PowerShell is a Windows tool only; a lean Windows
session offers one shell, the one `prompt.shell` names (`auto`: Bash when Git
Bash is found, else PowerShell; `bash`; `powershell`), and the other is left
out like any tool the window has no room for.

**Lean descriptions** (`tools/lean_descriptions.py`). Every built-in tool has
a short description for the lean profile: one or two sentences and a
one-line meaning per parameter, every instruction that changes what the model
does kept (read before edit, `old_string` unique, the timeouts, where
background output is read). The long guidance stays for a large-window model.
A test fails when a new built-in tool has none.

**The order and the budget.** The lean tool cap fills, in order: the core
tools (Read, Write, Edit, the session's shell, Glob, Grep, Agent, the task
tools, ToolSearch), then what the session's lineup needs (`Workflow` only when
a square is enabled for this lineup and the model lacks something a square
covers), then `copilot_ask` when Copilot is set up (3.3.17.0: it is registered
only then, so the user asked for it), then the built-ins in the registry's order, then the rest (MCP
tools) by relevance to the task. The block is held to a token budget of the
window the call gets: 2,200 up to 16,384, 4,500 under 65,536. A tool left out
stays callable by name and ToolSearch shows its schema, exactly as a deferred
tool; one line of the system message names them. Since 3.6.0.19 a set-up
`copilot_ask` rides on top of the 4,500 budget (its 150 tokens are not counted
there), so it never takes the Builder's room and every other tool is in or
out exactly as in a home without Copilot.

**The window the block is shaped for (3.6.0.19).** A session's tool block is
the block of the window its first request is SENT at, and it stays that for
the session: the line "N tools not offered to <model> (window W)" names that
window. That matters where Halo sends another window than the
one it first resolved: a model held at a smaller window because the larger
one runs partly on the CPU, a first request raised over a default, a larger
window another program loaded and Halo holds. A switch to another model
starts over.

**The system text, lean** (`agent/prompt_lean_system.py`). On the lean
profile the wire copy of Halo's system prompt keeps what a local model needs
to act: who it is, the narration rule, the rules as one list (native tool
calls, CLAUDE.md binds, read before edit and verify, plan mode, where memory
goes, hooks, the delegation rule -- `role:` when roles are on, `model:` when
off), the MCP servers when any are configured, the family notation, the
working directory and your appended prompt. Out: the per-tool list (each tool
carries its own description) and the prose that explains rather than
instructs. The log keeps the full prompt; a cloud model with a window of
128k or more gets byte for byte what it got before (a hash test pins it).

**On Auto main knows what it can hand out (3.6.0.10).** In a top session on
Auto the delegation rule becomes two lines: when to hand work out, and the
kinds of helper this session can start, your own agents first
(`agent/helpers_words.py`, `crew/kinds.py`). They are made once, at the first
request, and stay byte for byte the same (made again only when main's model
changes). Per request, after the tools are capped, one line names the Workflow
tool's workflows and one the Builder, only when that request sends them. The
whole is held to 300 tokens: past it the few words after each name leave
first, then names from the end, and main reads "and {n} more (a wrong name
lists them all)". A cloud model reads the same kinds at the end of the Agent
and Task tools' words. Studio's Map tab ("Main can hand work to") lists every
name of the same list, and the session's status row says what main read
(`kinds_told`, `kinds_more`); those fields never reach a model.

**On a local model main is also reminded at each task (3.6.0.14).** When main
runs on a local model on Auto and has been told the helpers above, every task
it is given carries one more line, right after the line that names the
permission mode: "If this job has parts that can run on their own, hand each
one to a helper with the Agent tool before you work on it yourself (one call
per part; `subagent_type` names the helper). A small job you do yourself."
(`agent/helpers_words.py` `remind`, written by `agent/mode_notice.py`; about
60 tokens a task by Halo's own count). The line is the same every turn; a turn that background results open,
not a task of yours, does not carry it; it goes when main switches
to a cloud model and comes back with a local one. A cloud main, a map of your
own, a helper and a session whose helper list does not fit read exactly what
they read before. What the gym measured: of the local models tried, two handed
out about two parts more of four with this line, and two did not change; a job
with one small part was never handed out. `halo gym handout <model>`
([COMMANDS-gym-handout.md](COMMANDS-gym-handout.md)) tells you which kind
yours is.

**The estimate is the wire's** (`providers/ollama_wire_estimate.py`). The
window used to be picked from an estimate over the Anthropic-shaped request
while the body sent is Ollama-shaped, about 0.5 % apart. It is now the
estimate of the body that is sent, so a request is never on the wrong side of
a power of two by the difference.

## `halo local prompt`

```
halo local prompt [<model ref>] [--window N] [--platform win32|linux|darwin] [--json]
```

What a model's first turn costs, before you use it: "Halo's own first turn:
N tokens of W (P %)", the composition line, the reply's room and the window
it would go out at, then the lines a turn's start sends, a row each with
its tokens and its words: `mode line` (the permission mode a new session in
this folder starts in) and, for a local main on Auto, `reminder`; the total
includes them. Then one row per tool (its tokens, offered as core, the
lineup's square or built-in, or left out and why). Nothing is sent to the
model; an `ol:` model's window is resolved as a call would (its catalog row,
the host, a steward profile). `/status` and `halo doctor`'s default-model row
say the same line for a local model, and Studio's Local -> a model's card
has the row "Halo's first turn: N tokens (P % of the window)". Since 3.6.0.19
the session measured is the one you get: a session someone answers has the
Builder tool (about 400 tokens from a 32,768 window on; one rule decides it
for the session and for the measure).

Since 3.6.0.20 it also counts your other tool servers (the MCP servers a
session in this folder reads from your settings) from Halo's own cache of
their tool lists, and starts none of them: their lines in the system text
and their tools as a session sends them. A local model (the lean prompt)
gets one line per server with its tool count; a model that is not lean gets
the list of their tool names, shown in the composition line as its own part
("other servers' tools N"). It then says "other tool servers: N, M tools
(from Halo's cache of their tool lists; none was started)", and for a server
whose cache is missing or was made for other settings "not counted: the
tools of N other tool servers (<names>); a session's /status counts them".
`--json` carries the same facts (`other_servers`). `/status` in a session
says that session's own first request: the one its conversation's first
request was sent as (after `/clear` or a compaction, the new
conversation's), or, before any request, the one its own log, tools and
servers make now. Studio's card and `halo doctor` measure a new session
without the other tool servers.

A lean request (a local model, any model with a window under 65,536, their
helpers, the smaller request after a failed answer, the lean prompt switched
on) no longer sends the list of every other server's
tool names: each server's line says how many tools it has (its words cut to
their first sentence, at most 160 characters) and ToolSearch finds a tool by
words. The session's log keeps the list, so a switch to a cloud model with a
large window sends it again as before.

## The budget test

`tests/test_prompt_budget_pins.py` pins the first turn of the five cases
above as upper bounds, on Windows and on Linux: the prompt, the lean tool
block (4,500; 2,200 at 16,384; 4,500 plus `copilot_ask`'s size with Copilot
set up), the window sent, and for the unknown remote
model prompt plus room at or under 26,000 of 32,768 and the lean system
message at or under 4,000. A new tool or new prompt text that crosses one
fails with what to do: give it a lean description, defer it, or raise the
bound on purpose and say why in the CHANGELOG.

## The steward

The fit plan (`ollama_steward/fit.py`) never shrinks a model's window under
Halo's own measured first turn plus a reply (`floor_window`; 8,192 when it
cannot be measured). The rule `prompt-heavy` fires when Halo's own part of
the newest call (system text, memory, topic index, tool schemas: the ledger
line's composition) is over half the window it went out at, with one next
step: the lean profile on when it is off, else a bigger window when the cap
allows (Halo's part half of it at most), else the core tools (`tools_max`).
