# Studio: steering and exporting a session

Read this when you steer an agent from Session's Live column and want to know which agent and which call it reaches, or save a session as one Markdown trace file, or ask why an answer came out as it did.

Part of [Halo Studio](STUDIO.md), which lists every part. The rest of the Session section (the map, Cost, the strips) is in [Session](STUDIO-sections.md#session).

## The steer's target

Halo 3.3.0.0 R6. The Steer box at the foot of the Live column always says
who your words reach, on one line above the field:

```
Steering: ● coder · Bash (pytest -q), 12 s
```

The agent's name in its own colour with its state glyph, then what it does
right now, live from the feed: the tool it runs, what it runs on and for how
long; `thinking` while it works between tools; `waiting on you`, `paused`,
or its end state; `idle` when nothing runs.

The target is, in this order: the agent you chose, else the agent you
pinned (its tag, its lane, the agent pick), else the session's main agent.
You choose it by:

- **clicking a row** in the column (its time, kind or text; the tag still
  pins, a tool row that opens still opens, an ask's keys still answer);
- **clicking a node** on the map;
- **`s`** on a focused row (the row becomes the target and the field gets
  the keyboard);
- **`Tab`** in the field: the next live agent of the session, in tree
  order; **`Shift+Tab`** the previous one. The field keeps the keyboard and
  the text you typed.

The target row (the row you chose, else that agent's newest row) carries a
steady outline in the agent's colour, and so does its node on the map, with
its **steer** chip lit; the timeline lane of the target is lit too. When the
target changes the line says what it was for a few seconds (`(was main)`).

A steer you send lands as a row right under its target row:
`↳ steer to coder: check the tax rule`. The row the agent answers with (its
next text, tool call or output) carries **after your steer**, so you see
the effect. The turn-end marker (`◼ done · 42 s · 3 tools`, `◼ waiting on
you: ...`, `◼ stopped: ...`) is a row of the same list.

## Follow, and the view holding still

The column follows its newest row unless:

- **the Steer field has the keyboard**: while you type a steer the view
  does not move;
- **you scrolled up**.

New rows then append below without moving the view, and a pill at the foot
counts them: **N new rows · follow**. A click on the pill, `Escape` out of
the field, the header's **Follow** or a scroll down to the newest row
follows again.

When you choose a target its row is scrolled into view once. While that
choice is held, following never pushes its row out of view: the column
stops there and the pill counts what arrives. Following again (the pill,
`Escape`, Follow, a scroll to the bottom) lets the row go; the target stays.

## Keys

| Key | Where | What it does |
|---|---|---|
| `Tab` / `Shift+Tab` | the Steer field | the next / previous live agent becomes the target (with no other live agent, the focus moves on as usual) |
| `Enter` / `Shift+Enter` | the Steer field | send / a new line |
| `Escape` | the Steer field | leave the field and follow again |
| `s` | a focused row | that row's agent becomes the target, the field gets the keyboard |
| `A` / `R` / `S` / `O` | the column | answer the newest ask card (`s` on a focused row steers instead) |
| `Esc` | the column | show every agent again after a pin |

## Export: the session as a trace file

**Export** sits on the Live column's header and on its timeline strip. It
saves the chosen session as one Markdown file the browser downloads,
`halo-trace-<session id>-<yyyy-mm-dd-hhmm>.md`:

- a header: the session id, the model and the lineup, when it started and
  ended, the totals (turns, tool calls, tokens in and out, cost);
- then one `###` entry per row, in time order, each led by the clock and
  the agent with its tier and model: a user prompt, the assistant's text, a
  tool call with its name and a one-line summary of its arguments, the
  tool's result in a fenced block (at most 40 lines, then `... (N more
  lines)`), a steer with its target, a nudge, a permission answer, the
  turn-end marker, a compaction, an error. A sub-agent's rows carry its own
  name and model.

The file carries no provider key (every text passes the same redactor as
`halo export --sanitize`) and no path under a home folder (it reads `~`).

The same bytes come from the terminal: `halo session export <id>` writes the
file in the current folder (`--md FILE` names it, `--md -` prints it; see
[`halo session export`](COMMANDS-sessions.md#halo-session-export)), and `/export`
in the TUI writes it beside the session log and says the path. Studio
serves it at `GET /api/sessions/<sid>/trace.md` (`text/markdown`), behind
the same token as every route.

## Why this answer? (3.3.6.0 R4)

Every text or output row of the Live column carries **why?** (`session-live-why`). A click opens the Inspector on the
Live panel -- no pop-up; Esc closes it -- with what the model saw for that turn, rebuilt from the traffic ledger and
the session log (`agent/postmortem.py`): one plain line ("the prompt was cut at 16,386 of 32,768; ... the task summary
at the front was dropped", or "nothing cut; 92 % of the prompt reused from cache") and the details beneath -- the
model and host, Ollama's read against what was sent, the prompt's parts (system, memory, topics, tools, history, you),
the tools offered, the reply's length and why it ended, the server log's kinds, the dialect in force, the degradation
ladder's rungs and a loop the guard saw. The row's agent and time pick the turn (a sub-agent's turn reads its own
lines). The same answer comes from `/why [turn]` in the TUI and `halo session postmortem [--session ID] [--turn N]
[--agent ID]`; Studio serves it at `GET /api/sessions/<sid>/postmortem?turn=&agent=&at=`
([MODELS-ollama-logs.md](MODELS-ollama-logs.md#the-answer-post-mortems-sources-3360-r4) lists the sources).

## Files

`ui/src/routes/session/steer.ts` (the target, the held row, Tab, `s`),
`follow.ts` (when the column follows), `LiveTarget.tsx` (the target line),
`LiveRows.tsx` (the outline, the steer row, "after your steer"),
`TraceExport.tsx` (Export), `Why.tsx` (why?, 3.3.6.0 R4), `routes/shared/liveFeed.ts` (`addSteer`),
`styles/session-target.css`; `halo_harness/session_trace.py` (the trace),
`session_trace_cli.py` (`halo session export`), `studio/sessions_api.py`
(the route), `studio/postmortem_api.py` (Why this answer?). Tests: `tests/test_postmortem.py`, `tests/test_session_trace.py`,
`tests/test_studio_session_target.py` (headless Chrome).
