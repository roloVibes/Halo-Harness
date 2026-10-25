# Architecture: the TUI event model

Read this when you change how the TUI turns session events into widgets.

Part of [Architecture](ARCHITECTURE.md), which lists every part.

## The TUI event model

`halo_harness/events.py` is pure data with no dependency on the rest of the
package: an `Event(kind, data, turn, agent_id, ts)` / `Command(kind, data)`
pair, each `kind` drawn from a fixed, validated vocabulary
(`EVENT_KINDS`/`COMMAND_KINDS`), with one small factory function per kind
documenting its own `data` shape. `Session.turn()` is a generator that
yields these events as the turn actually progresses; **print mode and the
TUI consume the literal same iterator** -- `PrintModeSink`/`StreamJsonSink`
(`output.py`) drain it into text/JSON, and the TUI's `Controller` runs it on
a worker thread and pushes each event onto a queue instead.

`tui/app.py`'s `BridgeApp` polls that queue on a 30 Hz timer (`_drain`, an
8 ms per-tick budget), coalesces what it collected
(`tui/events.py::drain_queue`), and hands each item to
`tui/dispatch.py::apply_event` -- **the only code path that ever touches a
widget**, so nothing in this application is ever mutated from a thread other
than the UI thread. `apply_event` wraps its real work in a broad
try/except: a handler that raises on a reachable-but-unusual payload (a
repair-rejected tool call's raw `None` argument, an unfamiliar question
shape) becomes one error note plus a toast, never a crashed session with an
orphaned child process. A `tool_use_ready`/`permission_request`/`question`/
`plan_review` event each mount their own widget (`ToolCard`/`PermissionCard`/
`QuestionCard`/`PlanCard`) and, for the three cards, call
`app.set_pending_card()`, which both gives the card keyboard focus (so its
own number-key/letter `BINDINGS` win over the prompt input) and rings the
terminal bell; a card that needs one line of free-text follow-up
temporarily borrows the prompt input (`app.borrow_input`) rather than
growing a text widget of its own. Every event carries an `agent_id`
(`None` for the top-level session); a sub-agent's own `status`/`message_end`/
`turn_done` events are applied to its own transcript block but never touch
the main status bar or the auto-title/idle bookkeeping those same event
kinds drive for the top-level session.

**The turn marker** (3.2.2.0 R4). Every finished turn yields one
`turn_marker` event right before its `turn_done` (`agent/turn_marker.py`'s
`with_markers`, wrapped around `Session._turn_inner`); dispatch shows its
`text` as one muted transcript line (`.system-note-marker`, no box):
`◼ done · 42 s · 3 tools · $0.012`, `◼ waiting on you: <what>` (the reply
ends on a question, or print mode's plan), `◼ stopped: <why>` (max_tokens,
max turns, the provider's error in one line, a UserPromptSubmit hook, the
loop breaker, Esc). A card the turn waits on gets a `waiting` marker with
`mid_turn: true` as it is shown; the TUI skips that one (the card's own
`⏸ ..., see below` line is already there) and Studio's Session feed shows
it. The same event kind carries the loop's `↳` notes: `↳ nudged: the reply
promised work and stopped` (state `nudged`) and `↳ no data for 60 s,
resending the call` (state `resend`). A sub-agent's markers never reach the
main transcript (its card says how it ended); the status bar's `go_idle`
on `turn_done` is unchanged. The plan card puts its keys line first, above
the plan, and caps the plan to the dock's room with a `... (N more lines;
the plan file: <path>)` line (`o` still opens the whole plan).

**The status bar** (`tui/widgets/statusbar.py`) reads `context_tokens`/
`context_limit`/`cost_usd`/`total_input_tokens`/`total_output_tokens` off
every `status` and `message_end` event (1.0.1 hotfix 14) -- the same raw
numbers `Session.status_event`/`agent/loop.py`'s per-step `message_end`
already compute for `/cost`/`stats`, never re-derived in the UI. Two pure
formatters in `halo_harness/model_display.py` (shared with the hotfix-12
model-listing row format) turn those numbers into text that is NEVER the
bare `ctx ?`/`$?` a Databricks model with no known context limit/price
showed permanently before 1.0.1: `format_status_context(tokens, limit)`
renders `"ctx 12k/1M 1%"` with a limit or `"ctx 12k"` (used tokens alone)
without one; `format_status_cost(cost_usd, total_in, total_out)` renders a
real `"$0.0123"` when a cost is known (provider-reported, or `CostMeter`'s
fallback formula computed from a models.dev-resolved Databricks price) or
`"in 12k out 3k"` (running token totals) when no price is known at all. On
a narrow terminal the cwd/branch segment shrinks first (down to nothing),
and only then is the model label itself left-truncated with a leading
ellipsis (`truncate_label_left`) -- ctx and cost stay visible before cwd
does.

**OpenRouter balance (H15 part 2 addendum 4).** A segment right after
cost, two decimals (`StatusBar.set_or_balance`) -- the one provider with a
balance API, this round. Populated by a background worker
(`tui/slash.py::or_balance_refresh_worker`, never the UI thread): once at
app launch, again every `BALANCE_REFRESH_INTERVAL_S` (5 minutes,
`providers/openrouter_account.py`), and once after every turn (debounced to
at most once every `BALANCE_POST_TURN_DEBOUNCE_S`, 60 seconds).

Two DIFFERENT OpenRouter endpoints, two different keys (`resolve_balance`'s
own 3-way preference order, checked in this exact sequence):
1. `"OR $12.40 left"` -- `GET /key`'s own `limit_remaining`, sent with the
   ordinary `OPENROUTER_API_KEY` (same key every other call already uses),
   when THIS key has a real `limit` set.
2. `"OR $12.40 left"` -- else, when a SEPARATE, higher-privilege
   `OPENROUTER_MANAGEMENT_KEY` is configured, `GET /credits`'s whole-account
   `total_credits - total_usage` (OpenRouter's own spec requires the
   management key here -- the ordinary key is never sent to `/credits`, and
   the management key is never sent to `/key` or anywhere else).
3. `"OR $3.21 used"` -- else, this key's own `/key` `usage` figure (a
   SPEND, not a remaining balance -- the honest fallback for an unlimited
   key with no management key, where no "remaining" number can be known).

Both calls are best-effort and never raise; a failed refresh leaves
whatever was cached before untouched rather than blanking the segment, and
the segment dims (never disappears) once that reading is more than 10
minutes old. Omitted entirely (no segment, no trailing separator) when
OpenRouter isn't enabled or a fetch has never once succeeded. `/cost` and
`/providers` print the same cached figure
(`providers/openrouter_account.py::format_balance_line`), naming WHICH of
the three it is, plus the key's own label and the wall-clock time of the
reading.

**Auto-scroll (1.0.1 hotfix 16).** `Transcript` (`tui/widgets/transcript.py`,
a `VerticalScroll` itself) calls Textual's own `self.anchor()` once in
`on_mount` -- the compositor then keeps `scroll_y` pinned to the live
bottom on every layout pass for as long as the widget stays "following",
which covers a child growing mid-stream (a `MarkdownStream.write()`
reflow), not just a fresh mount. Textual's own `scroll_y` watcher releases
that following on any ordinary user scroll (PageUp, mouse wheel) and
re-acquires it automatically once the view is scrolled back to the true
bottom -- `Transcript.is_following()` reads this indirectly (`is_at_bottom()`,
already used for the pre-1.0.1 one-shot mount scroll) rather than reaching
into a private Textual flag. `new_since_scroll` (the status bar's "↓ N new")
increments on every mount AND on every delta that lands while released
(`Transcript.note_growth()`, called from `append_text`/`append_thinking`
for a block that already exists); `Ctrl+End`, a click on the indicator, or
submitting a new prompt all call `scroll_end()` and reset the counter,
which is exactly what Textual's own watcher treats as "the user returned
to the bottom".

**A pending card intercepts free text (1.0.1 hotfix 17).**
`on_prompt_input_submitted` (`tui/app.py`) checks `self.pending_card`
before ever reaching `Controller.submit`'s steer path: when the card
implements `resolve_with_message` (`PermissionCard`/`PlanCard`/
`QuestionCard` all already did, for their own borrowed-input flows), the
typed text answers the card directly instead of becoming a "↳ steering…"
note the pending ask never sees. `action_cycle_mode` (Shift+Tab) likewise
re-evaluates an already-pending `PermissionCard` under the NEW mode right
away (`auto`/`bypassPermissions` resolves it allowed, `dontAsk` denied) --
`Controller.set_permission_mode` itself only ever affected FUTURE asks,
a plain attribute write with no knowledge of one already parked in
`Session._await_permission_decision`.
