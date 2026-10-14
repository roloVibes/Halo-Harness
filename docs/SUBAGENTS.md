# Sub-agent visibility and scale

Halo 2.0.2 round 3 (brief C): the tasks panel (`/tasks`, Ctrl+T), the
`agents.max_concurrent`/`agents.max_depth` config knobs, the Agent tool's
`count`/`batch` parameters, and the shared task board (`TaskCreate`/
`TaskUpdate`/`TaskList`). Builds on [ROLES.md](ROLES.md) (per-role model/
effort) and [ORGS.md](ORGS.md) (trees of positions run as sub-agents) --
an org run's own tree shows up in this same panel. Verified against
`halo_harness/agent/subagent.py`, `halo_harness/tui/dialogs/tasks.py`,
`halo_harness/tools/task_board.py`, `halo_harness/tools/agent.py`, and
`halo_harness/tui/widgets/statusbar.py`.

## The tasks panel

`/tasks` and Ctrl+T open a full-height panel with two tabs (`Tab`
switches between them):

- **Agents** -- every running, queued, background and finished sub-agent
  (and background Bash job) of this session: position/role, model,
  status, elapsed time, tool-call count and cost so far. An org run's
  own descendants are indented under their parent. A finished agent
  stays listed for the rest of the session, with its final status
  (`done`/`error`) and result.
- **Board** -- the shared task board (see below).

| Key | Does |
|---|---|
| `Tab` | switch between the Agents and Board tabs |
| `Enter` (Agents tab) | open a live transcript viewer of the highlighted agent |
| `Ctrl+T` / `Esc` | close the panel |

Refreshes once a second for as long as it stays open. Data comes
straight off disk (`subagents/agent-<id>.meta.json` + each child's own
`agent-<id>.jsonl`), so it is correct even right after a `-c` resume,
before a single new turn has run.

### The transcript viewer

Enter on an agent row opens a live, follow-mode reader of that agent's
own `subagents/agent-<id>.jsonl` (one entry per model/tool event,
polled every second while open):

| Key | Does |
|---|---|
| `PgUp` / `PgDn` | scroll (PgUp turns off follow mode, so a live-growing log doesn't yank the view back down mid-read) |
| `o` | open the full, untruncated log in the same pager a tool card's own `o` uses |
| `Esc` | back to the tasks panel |

### The status bar

`agents N` (the count of sub-agents currently *running* -- a queued
fan-out job doesn't count until it actually starts) appears next to
`needs you` whenever N > 0, and is omitted entirely at 0, same
convention as every other optional segment.

## Scale: config and the concurrency queue

| Key | Default | Meaning |
|---|---|---|
| `agents.max_concurrent` | 4 | how many sub-agents one call/turn may run at once; any positive integer. An org's own `max_concurrent` overrides this for every position in that org. |
| `agents.max_depth` | 1 | how many levels of delegation are allowed; 1-3. An org's own tree shape overrides this (unclamped -- `company`'s own CEO -> VP -> manager -> worker chain needs 4). |

`halo config set agents.max_concurrent 8` / `halo config set
agents.max_depth 2` (or `/config agents.max_concurrent=8`). Beyond the
concurrency cap, a spawn (a separate Agent tool_use block in one turn,
or a `count`/`batch` job -- see below) **queues**: the tasks panel shows
it as `queued` immediately (a `subagent_queued` event fires for every
job up front, in spawn order, before the pool has even looked at any of
them) and it **starts as a slot frees**, in the order it was spawned.

The cap is **session-wide** (or org-wide for an org run), not per-call:
two separate `count`/`batch` calls in the same turn, or a nested
delegation chain, share the SAME counter, so they can never multiply
past the configured limit between them. The counter is also
**resizable** -- the limit is re-read from `agents.max_concurrent` (or
the org's own override) at every single spawn, not fixed once when the
session started, so a config change made mid-session (`/config`, or
`/setup`) applies starting with the very next spawn rather than only
the next session. A parent that is itself waiting on its own children
gives its slot back for the duration of that wait, and each child takes
a real slot of its own -- without this, a cap smaller than the nesting
depth (e.g. `agents.max_concurrent: 1` with a parent delegating to a
child that delegates again) would deadlock: the parent would block
holding its slot while waiting for a child that can never acquire one.

## `count` / `batch`: several sub-agents in one Agent-tool call

The Agent tool accepts two extra, mutually-exclusive parameters:

- **`count`** (integer): spawns that many identical copies of `prompt`.
- **`batch`** (a list of `{prompt, role?, model?, effort?, description?}`
  objects): spawns one sub-agent per entry, each with its own prompt and
  optional per-item overrides (falling back to the call's own top-level
  `role`/`model`/`effort` when an item omits one).

Either way, the parent **waits on every child** and gets back **one
combined result**: one `<task_result>` section per child, in SPAWN
order (never completion order -- a slow 2nd job never reshuffles a fast
5th one ahead of it). Concurrency is capped exactly like several
separate Agent calls in one turn already are (`agents.max_concurrent`,
above). `count`/`batch` cannot be combined with `run_in_background` --
the parent is already waiting on every child, so there is nothing left
for backgrounding to do.

The orchestrator's own system prompt (the Agent tool's own guidance
line, drawn from its `description`) tells the model it may spawn
several agents in one call this way, and that `/tasks` shows them.

## The shared task board

`TaskCreate`/`TaskUpdate`/`TaskList` -- a small JSON-backed TODO list at
`~/.halo/sessions/<session-id>/tasks.json`, shared by every sub-agent of
the SAME session (however deeply nested) through the exact same file,
so an organization's root can hand out work and its workers can claim
and report on it:

| Field | Meaning |
|---|---|
| `id` | the task's own id (returned by `TaskCreate`) |
| `title` | a short description |
| `status` | `open` \| `claimed` \| `done` \| `blocked` |
| `owner` | free text (the claiming agent's own name/title -- nothing tracks "who am I" automatically; the caller supplies it) |
| `notes` | free text, settable at any time |
| `result` | a free-text pointer to the outcome (a file path, a one-line summary, ...) |
| `kind` | Halo 2.0.2 round 7: `"task"` (default) or `"goal"` -- an org run's own goal (see [ORGS.md](ORGS.md)) |
| `parent` | Halo 2.0.2 round 7: another task's own id this one works toward, optional |

`TaskCreate(title, notes?, parent?)` adds an `open` task (Round 7:
`parent` links it under another task, typically an org run's own goal,
so `/tasks`' board tab can show goal -> tasks -> results instead of a
flat list). `TaskUpdate(id, status?, owner?, notes?, result?)` updates
one -- claiming (`status: "claimed"`) **requires `owner`** and is
**refused** if the task isn't currently `open`, under the same
process-wide lock every read-modify-write cycle takes: this is an
**atomic task checkout** -- two agents racing to claim the same task
resolve to exactly one winner, never a lost update or a double-claim.
`TaskList()` prints every task, any status. This is distinct from
`TodoWrite` (one model's own private, whole-list-replacing todos) -- the
task board is shared and additive.

This is the SAME board the tasks panel's own "Board" tab shows live.


## The live agent tree and what Studio can do to an agent

Halo 3.0.5.0 (Fleet, round R1): every sub-agent at every depth is something
you can list, watch, steer, pause and stop, from Studio, from `halo remote`
or over the control socket ([REMOTE.md](REMOTE.md#agent-level-commands-3050-fleet)
has the wire; [FLEET.md](FLEET.md) the bigger picture). Verified against
`halo_harness/agent/agent_registry.py`, `agent_observe.py`, `agent_hooks.py`,
`agent_inbox.py`, `agent_transcript.py` and `halo_harness/remote/agent_control.py`.

**The tree.** Each session keeps a live tree of its agents: the main agent is
the root (`main`); every Agent/Task call, count/batch job, org position, team
member and background sub-agent registers under the agent that spawned it the
moment it is built (a queued fan-out job as soon as it is minted), and the
session's background Bash jobs are leaves under main (`job:<id>`). A row has
`agent_id, parent, name, role, bio, lineup, model, kind, task` (the first line
of what it was asked), `since, state` (`queued`, `running`, `waiting` on a
card, `paused`, `done`, `failed`, `stopped`), `turns` (its model calls),
`cost_usd, current` (the tool in flight with one line of its arguments, or
`thinking`), `last_text` (the last 200 characters it wrote) and `transcript`
(its own `subagents/agent-<id>.jsonl`). `/agents live` prints it in the TUI;
`halo remote agents <session>` from any terminal; `agent_tail` reads one
agent's transcript as entries (its prompt, text, reasoning, tool calls and
results, the agents it spawned, its hand-back, and the commands it received).

**Steer.** A steer is delivered to THAT agent, not to main:

- `nudge` (the default): the note goes to the agent's inbox and is applied
  right before its next model call, as a user-role note `[steer from <by> via
  Studio] <text>`, through the path a typed steer takes (UserPromptSubmit
  hooks run on it). The tool calls already planned this round still run.
- `redirect`: the same, and the rest of the agent's current tool round is
  left unrun (`not run: redirected by <by> from Studio`), so its next model
  call starts from the note: `Redirect: the rest of your current task is
  replaced. Your task is now: <text>`. Its `task` in the tree becomes the
  note's first line. A round the agent planned after it read the note is not
  cut.
- For the main agent a steer is today's steer (the text steers the turn in
  flight, or starts the next one).
- A `cc:` child takes the note through its own claude process; a `cx:` child
  has no live channel, so the steer answers "that agent runs in an external
  process; stop and respawn". A finished agent takes no steer.

**Stop.** `agent_stop` stops that agent and every agent under it at their
next tool boundary: the flag is checked before every tool call and before
every model call, so a model call already streaming finishes first and a
running tool call finishes too. The calls it had not started are answered
`not run: stopped by <by> from Studio`. Its parent receives the ordinary
hand-back, shaped `stopped by <by> from Studio: <reason>` followed by what the
agent had written so far, and carries on with its own turn (a stopped child
is not sent back for an acceptance retry). For the main agent a stop is the
turn-level interrupt. A `cc:` child's process is ended; a background Bash job
is killed.

**Pause and resume.** `pause` holds an agent and its subtree (or, without an
agent id, every agent of the session) at the next tool boundary until
`resume`; its state reads `paused` meanwhile, and a stop, a shutdown or Esc
end the hold too. `shutdown` ends every agent at its next boundary and then
closes the session.

**What the parent sees.** One line in its own transcript for a steer, stop or
pause (`<agent> steered from Studio by <by>: <first 80 characters>`, `...
stopped from Studio by <by>: <reason>`, `... paused from Studio by <by>`, once
per pause), the same line in the TUI, and for a stop the hand-back above as
the Agent tool's result. The agent's own transcript records every command
(`cmd`, `by`, `via`).

**What a steer never does.** It is a user-role note like any typed steer:
it never widens a permission, approves or answers a card, changes an
Orchestra claim or skips a gate (an approval gate, a pipeline gate, a
budget). The owner's permission engine still decides every tool call the
agent makes, exactly as before; `by` is a label naming who sent it.
