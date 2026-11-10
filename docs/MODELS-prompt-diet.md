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
covers), then the built-ins in the registry's order, then the rest (MCP
tools) by relevance to the task. The block is held to a token budget of the
window the call gets: 2,200 up to 16,384, 4,500 under 65,536. A tool left out
stays callable by name and ToolSearch shows its schema, exactly as a deferred
tool; one line of the system message names them.

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
it would go out at, then one row per tool (its tokens, offered as core, the
lineup's square or built-in, or left out and why). Nothing is sent to the
model; an `ol:` model's window is resolved as a call would (its catalog row,
the host, a steward profile). `/status` and `halo doctor`'s default-model row
say the same line for a local model, and Studio's Local -> a model's card
has the row "Halo's first turn: N tokens (P % of the window)".

## The budget test

`tests/test_prompt_budget_pins.py` pins the first turn of the five cases
above as upper bounds, on Windows and on Linux: the prompt, the lean tool
block (4,500; 2,200 at 16,384), the window sent, and for the unknown remote
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
