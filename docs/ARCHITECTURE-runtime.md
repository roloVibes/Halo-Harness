# Architecture: steering, compaction, sub-agents and telemetry

Read this when you change steering and interrupts, compaction, sub-agents and plan mode, or telemetry.

Part of [Architecture](ARCHITECTURE.md), which lists every part.

## Steering, interrupts, and pairing invariants

Typing while a turn is running calls `Session.steer(text)` directly (the
worker thread is parked inside the running turn's own generator, so there is
no separate command queue to go through). Under one lock, it atomically
checks whether the session is busy and appends to `_steer_queue` -- busy-
check and enqueue must be a single atomic step, or a turn could finish in
the gap between them and the text would never be drained. A steer is
**never** applied instantly; it waits for the next safe point inside
`_step()`'s per-chunk stream loop, `_dispatch_tools()`'s per-call loop, or
`_turn_body()`'s post-dispatch/post-stream points, all funneled through
`_apply_pending_steers_events()`. Each one becomes a user-role log message
through the **same `UserPromptSubmit` hook** the first message of a turn
uses -- a hook that filters/blocks prompts cannot be bypassed by typing
mid-turn. A steer that arrives while a permission/question card is still
waiting for its own answer does not answer that card; it just queues,
exactly like at any other moment.

**Esc (interrupt) is a different signal from a steer in every dimension.**
It sets one `threading.Event` (`Session.abort`) that:

- cuts the current `_step()` mid-stream with no retry (the partial text is
  still logged, tagged `[Request interrupted by user]`, but the model call
  itself is over);
- inside tool dispatch, lets anything **already dispatched** (a running
  read-only batch, a solo call in flight) finish normally, but never starts
  anything after it, and manufactures an `is_error` tool_result for every
  remaining `tool_use` via `agent/invariants.py::synthesize_missing_results`
  (reason `"Tool call interrupted by user"`/`"ABORTED_BEFORE_DISPATCH"`);
- **ends the turn** (`turn_done(reason="interrupted")`) rather than
  continuing, which a steer never does on its own.

A **shared** abort (a foreground sub-agent uses the same `Event` object as
its parent, so the parent's own Esc also interrupts it) is only ever
`.clear()`-ed by whichever `Session` actually owns it -- a child never
clears a signal a concurrent sibling or the parent itself might still be
relying on.

This machinery exists to guarantee one rule everywhere, always: **every
`tool_use` block gets exactly one `tool_result` before the next assistant
node.** Any exception unwinding out of a turn (`GeneratorExit`, a genuine
crash) still runs `synthesize_missing_results` before propagating -- a
provider that 400s on an assistant message with an unanswered tool call
should never be reachable from a real interrupt or a real bug.

**The loop breaker** guards against a model calling the same tool with the
same arguments over and over. The key is `(tool_name, canonical_json(args))`
(property order ignored); a run of identical calls gets a `[reminder: ...]`
suffix on the tool_result once it reaches **3**, is denied outright at **5**,
and force-ends the turn at **8** (`agent/loop.py`'s own
`_LOOP_BREAKER_REMIND_AT`/`_LOOP_BREAKER_DENY_AT`/`_LOOP_BREAKER_END_AT`).
`BashOutput` is fully exempt (polling a background job by the same id is a
normal pattern, not a loop) -- a genuinely runaway poll is bounded by
`--max-turns` instead. A second detector catches strict A/B/A/B alternation
(two *different* calls trading off) the plain repeat-count would miss
entirely; whichever of the two counts is higher for a given call is what's
actually compared against the thresholds above. Both counters reset at the
start of every new `turn()`, never across turns.

## Compaction

Checked once, right after every successful model call
(`Session._maybe_auto_compact`, called from inside `_turn_body`): the
trigger token count is `min(dsh's own 80%-of-(context minus a 65,536-token
headroom) formula, OpenCode's own "usable" formula -- context minus a
capped max-output minus a capped reserve)`, then **floored** at 70% of the
raw context window (so a small-context open-weight model still gets a
sensible trigger instead of one near zero) unless an explicit
`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` genuinely lowers the 80% further. A model's
advertised `max_output_tokens` is itself capped at 32,000 before any of this
math runs, fixing real catalog rows whose advertised output made the naive
trigger come out at zero. Two guards stop back-to-back compaction attempts:
`_just_compacted` (skips one check immediately after a compaction ran) and a
5-step backoff after a compaction that failed or didn't free enough room.

A compaction is a real model call: the exact derived+pruned prefix so far,
plus one final instruction message demanding a checkpoint summary under
**eight fixed headings, in order** -- Primary Request and Intent, Key
Technical Concepts, Files and Code, Errors and Fixes, Pending Jobs, Current
Work, Next Step, Critical Context -- explicitly told to merge (not just
re-quote) any prior `<compacted-summary>` block already in the prefix, with
the conversation winning on conflict. A reply missing a heading, or one that
was truncated (`stop_reason` of `max_tokens`/`length`), gets exactly one
corrective retry naming what was wrong; if that still fails, or the call
itself hits a context overflow, one further fallback re-serializes the
whole transcript as flattened plain text and summarizes that instead.
**On any failure the session log is left byte-for-byte unchanged** -- the
`compacted` marker node is only ever written once a usable summary actually
exists. `PreCompact`/`PostCompact` hooks fire around the attempt either way.

On success, the replacement content re-injects every session-start snapshot
kind (CLAUDE.md, memory index, environment, a deferred-tools reminder, and
the active plan file if plan mode is on) plus a "files read this session"
snapshot, then a verbatim tail of the most recent messages (assistant
`tool_use`/matching `tool_result` pairs are kept glued together as one atomic
unit, never split; any `thinking` block in that tail is stripped, since a
replayed signature is bound to the exact prefix that produced it, which
compaction just changed). `/compact [instructions]` runs the identical
mechanism synchronously; a session with no prior history to summarize is a
plain no-op.

## Sub-agents and plan mode

The `Agent`/`Task` tool call is dispatched directly from `agent/loop.py`
(bypassing the ordinary `ToolRegistry.dispatch()` choke point) so several
calls in one assistant turn can run **concurrently**, up to
`MAX_CONCURRENT_AGENTS = 4` (`agent/subagent.py`), each streaming its own
live events back into the parent's stream immediately rather than being
buffered until the whole batch finishes -- this is what lets a foreground
child's own permission ask reach a real, answerable card while it's still
running. `MAX_DEPTH = 1`: a sub-agent's own `Agent`/`Task` call is refused
outright (a sub-agent cannot itself spawn a sub-agent).

A child gets its own real `Session`, logging to
`<parent_session_dir>/subagents/agent-<id>.jsonl` (never the parent's own
file): a tool registry **filtered down from the parent's already-frozen
catalog** (`AgentSpec.resolved_tools()` intersects/subtracts, never adds --
this is the concrete mechanism behind "a sub-agent never grows the parent's
catalog"), its own model (invocation override → frontmatter `model:` →
`CLAUDE_CODE_SUBAGENT_MODEL`/`settings.subagentModel` → the parent's own
model, with `haiku` mapping to the parent's *small* model specifically), its
own permission mode/engine (sharing the parent's deny/ask rules by
reference, a **copy** of its allow rules), and its own `HookRunner` tagged
with `agent_id`/`agent_type` so `SubagentStart`/`SubagentStop` matchers can
target it. A **foreground** child shares the parent's own `abort` Event (the
parent's Esc interrupts it too); a **background** one (`run_in_background`,
or an `AgentSpec`'s own `background: true`) gets an independent `Event` of
its own, so an unrelated Esc never kills it -- only `TaskStop(task_id=...)`
or the whole process quitting does. Either way the child shares the
*parent's* `job_registry`, so the parent's own shutdown kills a Bash job a
sub-agent started too.

A foreground child of an **interactive** parent gets genuinely live,
answerable permission cards (the same `_permission_waiters` dict, keyed
`f"{agent_id}:{tool_id}"` so parallel children never collide, resolved by
the exact same `Controller.answer_permission` path a top-level call uses); a
background child, or any child in print mode, falls back to an immediate
deny (recorded in `permission_denials`) since there is no live stream to
show a card on. When a child finishes, its own newly-appended `usage` nodes
are summed and rolled into the parent as **one** ordinary `usage` node
(`CostMeter.add_child_total`), and its `permission_denials` are merged into
the parent's -- the parent's own log stays a complete, ordinary derivable
log, never a log with holes a viewer has to know to look inside a
`subagents/` directory to fill in. A `task_id` lets a caller resume the same
child session later (`Agent(task_id=..., prompt=...)`); a still-running
background task refuses a concurrent resume rather than racing its own log
writer.

**Plan mode** writes to exactly one file, `~/.claude/plans/<three-word-
name>.md` (honoring `settings.plansDirectory`) -- the permission engine's
`plan_file`/`set_plan_file()` plus the mode table's dedicated
`plan_file_write` category (allow, in every mode, but only when the target
*is* that one file and the session is actually in `plan` mode) is what makes
it the sole writable path while every other Write/Edit is denied.
`EnterPlanMode`/`ExitPlanMode` are wire-schema-only tool definitions;
`agent/loop.py` special-cases both names the same tier as `AskUserQuestion`,
never running them through the ordinary `decide()`/dispatch path. Entering
plan mode (model-initiated, or `--permission-mode plan`/Shift+Tab) injects
a fixed system-prompt note: investigate and propose, make no changes except
to the plan file itself. `ExitPlanMode(plan)` writes the file and surfaces a
`plan_review` event; the reply -- the TUI's `PlanCard` offers exactly three
-- is one of `{"approved": true, "mode_after": "acceptEdits"}` (approve,
auto-accept edits from here), `{"approved": true, "mode_after": "default"}`
(approve, manual), or `{"approved": false, "feedback": "..."}` (keep
planning, with optional free-text feedback borrowed from the prompt input).
With no reviewer (`-p`), the plan is approved when the mode in force before
plan mode was entered is `acceptEdits` or `bypassPermissions` (that mode comes
back); otherwise the plan text is the turn's answer.

## Telemetry and `/improve`

`halo_harness/telemetry.py` derives **everything** it reports from
non-wire metadata already sitting on existing log nodes (`usage.route`/
`.provider`/`.finish_reason`/`.ttft_ms`/`.latency_ms`/`.retries`/`.status`,
an assistant node's `tool_meta`, a `tool_result`'s `tool`/`error_class`/`ms`/
`bytes`/`spilled`) -- never a new model-visible field, and a corrupt JSONL
line is skipped and counted, never a crash. `telemetry.scan()` walks
`~/.halo/sessions/<slug>/*.jsonl`, caching one `SessionSummary` per
file at `~/.halo/stats-cache.json` keyed by `(path, size, mtime)` so
an unchanged log is never re-parsed; `aggregate_by_model`/`aggregate_by_tool`
turn a batch of summaries into the rows `halo stats --models/--tools`
and `/stats --models` render.

`/improve` is entirely human-gated and never runs on its own: `improve/
evidence.py` clusters the same telemetry-adjacent signal into six kinds
(repeated tool errors by `error_class`, repair-layer hits by kind, loop-
breaker trips, user corrections following a tool error or matching a fixed
cue list, `Read` ENOENT/wrong-cwd patterns, and a 3-tool sequence recurring
across at least 3 sessions), each excerpt tagged with whether it came from
the user's own words or from tool output. `improve/draft.py` makes **one**
model call (config `improve.model` → the session's small model → the
session model) asking for at most 8 JSON-shaped candidates, with one retry
on malformed JSON; a candidate citing an evidence reference that never
actually appeared in a cluster has that reference silently dropped, never
invented. Nothing reaches disk until a card's `a`/`e` key (or an explicit
headless `improve --apply FILE#ID`) approves it: `improve/apply.py` writes
atomically, tags the file with an HTML-comment provenance marker
(`<!-- halo improve: created=... sessions=... model=... -->`), and
only ever **updates** a file that already carries that exact marker --
colliding with a user-authored file picks a new name instead of touching
it. `d` (dismiss forever) records a content hash
(`sha256(kind|scope|path|body)`) in `~/.halo/improve/dismissed.json`
so the same candidate never resurfaces. A separate, much cheaper check
(`improve/hint.py`) counts a session's own repair-hits/edit-failures/loop-
breaker-trips against a configurable threshold and, if crossed, shows a
**one-time, counters-only** notification -- never a model call, never a
card, identical in auto mode.
