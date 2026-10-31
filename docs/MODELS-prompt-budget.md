# Models: what Halo sends a local model

Read this when a local model answers as if it never saw the task, you want to know what a request to a model is made of in tokens, or a request is larger than the model's window.

Part of [Models](MODELS.md), which lists every part.

## What Halo sends a local model

Halo 3.3.5.0 R4 ("the prompt budget"). A real session against a 32k local
model once sent a 41,104-token prompt where the user had typed two words:
the auto-memory block was in it twice, the topic index alone was 25,000
characters, and Ollama cut the prompt to half the window, keeping 4 tokens of
the start and the tail -- the task summary at the front was lost, the memory
at the end survived, and the model answered without knowing the task. Since
R4 the memory goes out once, a local model gets a lean prompt, every
request's parts are counted, and a request that will not fit is a decision you
see before it is sent.

### The composition

Every request is counted by part before it goes out
(`agent/prompt_composition.py`, the same chars / 3.5 estimate the window
uses): Halo's own system prompt and snapshots with CLAUDE.md (`system`), the
memory (`memory`, MEMORY.md), the topic index (`topics`), the tool schemas
(`tools`), the conversation (`history`, tool output included) and what you
typed (`you`). One line says it, on `/cost` and `/status`:

```
prompt 30,756: system 3,587 · memory 9,900 · topics 6,400 · tools 2,100 · history 8,700 · you 69
```

The same parts go on the call's ledger line (`composition`, see
[the steward](MODELS-ollama-steward.md)) and on Studio's Cost
panel as one stacked bar (see [STUDIO-sections.md](STUDIO-sections.md#session)).
A block that is in the request twice is taken out of the wire copy (the newest
kept) and the line says how many tokens that was.

**The double block.** It came from compaction: a compaction keeps a verbatim
tail of the conversation and adds every session-start snapshot again after its
marker (CLAUDE.md, the memory and topic index, the environment, the roster,
the deferred tool names). In a short session the tail is the first user
message, which already holds those snapshots, so the compacted request carried
the memory and CLAUDE.md twice, and every further compaction added another
copy. The tail is now selected without them (`agent/compact_budget.py`).

**Where the memory goes.** On a local model (`ol:`, `hf:local`, `hf:mlx`)
the memory block moves to the end of the system message: the front of the
prompt, part of the prefix the KV cache keeps, and the part Ollama may cut. A
model whose card says its system role is weak (`system_role: "weak"`, the
dialect record) gets it at the front of its first user message instead. A
cloud model keeps it in its user-role snapshot, as before.

### The lean profile

`prompt.lean` (`auto` | `on` | `off`; auto is a local model or a window
under 64k) sends a small model less (`agent/prompt_lean.py`):

- the topic index is one pointer line per topic file (its name and one
  sentence), the `prompt.topics_max` (12) most recently touched, then
  "N more: `/memory topics` lists every topic file";
- MEMORY.md is held to `prompt.memory_max_tokens` (4,000): its headings and
  the newest entries that fit, then one line saying how many older lines were
  not sent;
- the tool catalog is capped by the window: under 16,384 the core tools
  (Read, Write, Edit, Bash, Glob, Grep, Agent, the task tools, ToolSearch), up
  to 32,768 the built-in set, under 65,536 sixty-four; the steward profile's
  `tools_max` wins when set; a model whose card says it takes no tools gets
  none. One line says it: "14 tools not offered to ol:qwen3.5:9b@lan (window
  12,288): the core tools first, the long tail left out".

The lean answer for a memory block is kept for the session, so touching a
topic file mid-session never reorders the prompt's front. A cloud session with
a large window is never changed.

### The preflight

Before a local call whose request (the prompt and the reply's room) is
larger than the largest window the call can get, the turn says one line
(`agent/preflight.py`):

```
prompt 41,104 tokens · window 32,768 · usable 16,386 · this will be cut
```

(`usable` is what Ollama keeps of an over-window prompt: half the window plus
two.) It offers three answers: **compact** (the default), **a bigger-window
model** (the model on the same host with the smallest window that holds the
request, named; none when nothing fits) and **send anyway**. The TUI shows
them as keys (Enter or 1 compact, 2 the bigger-window model, 3 send anyway);
Studio's Live composer shows three buttons above the steer box; Fleet's
attention row answers it too (a compact, r the bigger-window model, s stop).
In `-p`, a run nobody can answer and a sub-agent the default applies
(`prompt.preflight`: `ask` | `compact` | `send`; `ask` compacts when nobody
can answer) and the line goes in the log. The choice goes on the next ledger
line (`preflight`: "compact" | "switch" | "sent") and into the session log as
a `preflight` node; the steward's `window-asked-small` / `prompt-trimmed`
rules skip a cut you chose.

**Order for survival.** A request sent anyway is ordered so what Ollama keeps
holds the task: the memory sits at the front (the end of the system message,
the part that may be cut) and the compaction summary moves into the last user
message, just before your own words, which go last. The trimmed reply of such
a call is not "recovered" by compacting behind your back.

**Compaction to the window.** On a local model the compaction is sized to
the window of the model it runs on: the budget is `compact_at x window -
reserve - (system + tools)` (`compact_at` 0.8 or the profile's); the summary
gets at most half of it (never more than 4,096 tokens) and the verbatim tail
what is left. A compacted request still past the budget is compacted once
more, then a line says so; when the system prompt, the memory and the tools
alone are larger than the window holds, the line says a bigger-window model
holds them.

### The prompt cache

Ollama reuses the KV cache of a prompt's front when it is byte-stable from
turn to turn. Halo keeps it stable within a session (the system prompt, the
tools in one order, the memory placed at the end of the system message, the
lean answer kept). Each ledger line carries `prefix_tokens` (the system
message and the tools), `prefix_changed` (the front differs from the previous
call's) and `cache_reused_pct` (the share of the prompt Ollama did not read
again, from `prompt_eval_count` against Halo's estimate; 0 for a full read, a
trimmed call or a gap under 5 %). The Ollama panel's last-turn line and
Studio's traffic view and Local -> Models rows say "cache reused N %". A model
whose server log says "forcing full prompt re-processing due to lack of cache
data" (sliding-window or hybrid/recurrent memory; the steward's
`no-prompt-cache` event) gets the card quirk "re-reads the whole prompt every
turn", in its `how` lines and on its Local tab row.

### Warm-up truth

The first call after a load (`load_ms` over 2 s) is graph capture and
loading, not speed: its ledger line carries `warming: true`, the status bar
shows "warming" instead of a tok/s figure, and no speed figure counts it (the
steward's p50 and slow-box rule, `halo ollama traffic`, the saved last-turn
reading). Studio's Local -> Models rows say "warm (loaded now)" or "cold (~N s
to load)" from the last load the ledger saw, and the traffic view says
"warming" on such a call.
