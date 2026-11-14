# Studio: steering and exporting a session

Read this when you steer an agent from Session's Live column and want to know which agent and which call it reaches, or save a session as one Markdown trace file, or ask why an answer came out as it did, or type a turn into the session from Studio with the Prompt panel, or run a session from Studio with no terminal at all.

Part of [Halo Studio](STUDIO.md), which lists every part. The rest of the Session section (the map, Cost, the view bar's drawers) is in [Session](STUDIO-sections.md#session).

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
you: ...`, `◼ stopped: ...`) is a row of the same list, and so (3.4.1.3) is background work that finished while the
session was idle (`◼ background work finished: ...`) and the turn the agent then takes by itself (`↻ Halo picks up
the finished background work`), with no prompt sent ([SUBAGENTS.md](SUBAGENTS.md)).

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

## The Map: zoom and the readable opening (3.4.1.3)

Session's **Map** (`session-map`, Live's tree as a thumbnail) zooms like every drawing in Studio: **Ctrl + wheel** (Cmd
on a Mac) or a pinch around the pointer, `+` / `-` / `0` on the focused map, a drag on the background pans, a
double-click there fits, and the **- / % / + / Fit** buttons in its corner for a mouse with no wheel. It opens fitted to
its panel but never smaller than the zoom where its text is 12 px on screen (3.6.0.0; 75% before): a tree too big for
that opens on the picked agent (else the main one) and pans inside its box, with "more than fits at a readable size:
drag to pan, Ctrl + wheel to zoom out" on the line under it, beside the buttons. Its drawer is the widest (560 px, less
where Live needs its 60 %). When the drawer's box changes (opened, dragged, the window crossing a breakpoint) it fits
again, unless you zoomed or panned it by hand: then your view stays until Fit gives it back to the automatic fit
(docs/STUDIO-shell.md, the one rule for every drawing).

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
  name and model. 3.3.16.2: the model's thinking is a `thinking` row before
  the text it led to, and the talk between agents has its own rows: a
  sub-agent's first prompt reads `talk: main -> researcher (task)`, its last
  words `talk: researcher -> main (hand-back)` (in place of its last
  `assistant text`, never beside it), a Workflow square's receipt
  `talk: main -> square media (square)`.

The file carries no provider key (every text passes the same redactor as
`halo export --sanitize`) and no path under a home folder (it reads `~`).

The same bytes come from the terminal: `halo session export <id>` writes the
file in the current folder (`--md FILE` names it, `--md -` prints it; see
[`halo session export`](COMMANDS-sessions.md#halo-session-export)), and `/export`
in the TUI writes it beside the session log and says the path. Studio
serves it at `GET /api/sessions/<sid>/trace.md` (`text/markdown`), behind
the same token as every route.

## The Prompt panel (3.3.11.0 R1)

The owner: "a box to just type into like it is the tui but it's in session view, and you can open it if you want like
how the cost and map modules work. I love looking at live, but that's more for steering". **Prompt**
(`session-prompt`) is a drawer of Session (its button in the view bar, like Cost and Map); `Alt+Enter`, the
palette's "Prompt: type into this session", `?prompt=1` and `halo studio --session <id> --prompt` open it with the
keyboard in its box. It talks to the chosen session (the map's, else the newest live one here).

**The box** (3.3.15.0 R3: the one text box with `fill`, three lines at the least; it grows with the draft and takes the
panel's free height while the conversation is short, and a conversation taller than the panel scrolls on its own)
behaves like the terminal's prompt: `Enter` sends, `Shift+Enter` is a new line, `Up` / `Down` walk this
session's history (kept in this browser, per session; a private window keeps none) when the caret is on the first /
last line. `/` opens the **slash list** -- the same table the TUI completes from (`commands/builtins.py`) plus the
session's project and user commands and skills, each with its arguments and one line of help (`GET
/api/sessions/<sid>/slash`) -- filtered as you type: `Up` / `Down` move in it, `Tab` (or `Enter` on a name not yet
complete) completes, `Esc` closes it. A `/` line runs in the session through the control socket's `slash` and its
output lands in the panel as the lines the terminal would print. Ctrl+V with an image, or an image file dropped on the
box, becomes the chip under it, as on the steer box; a dropped file path lands in the text.

**While a turn runs**, a send asks first (`submit` with `when_busy: refuse`): the busy line keeps your text and offers
**Queue it** (the session holds it, one turn at a time, and starts it the moment the running turn ends; the terminal's
prompt hint says "1 queued from Studio") and **Steer** (it goes into the running turn now). Cancel keeps the text in
the box.

**The conversation** reads like the terminal: your turns (marked **from Studio** when this page sent them; the
terminal's transcript says `(from Studio) prompt: ...` above the turn), the assistant's text, each tool call on one line
(with a pack policy's line when one answered it), the turn's end line and the asks. An ask the terminal shows as a card
(a permission, a question, a plan, an approval) shows here with the same buttons -- Allow, Allow for this session,
Deny; the question's options; Approve the plan, Keep planning; Accept, Stop -- and answers through the socket's
`answer`. Live stays the stream for steering.

**The receipt's four marks** sit beside each turn you sent: **sent** (Studio stored it, before it talked to the
session), **delivered** (the session took it), **read** (it is in the model's input: the user node the request is
built from carries the receipt's id, so the transcript is the evidence), **replied** (the turn that read it ended).
A mark lights cyan when reached (replied green); a failed send is red with the reason in its title (`busy`, `held`,
`expired` after 24 hours unread, or the socket's error). The ladder and its file are in
[REMOTE.md](REMOTE.md#receipts-33110-r1).

## A session without a terminal (3.3.11.0 R2)

**New session** starts one from Studio with no terminal open anywhere: on Session's Start view (while this harness
has no live session) and in the Prompt panel when no session is here. Pick the **model** -- the configured catalog,
grouped by provider, the rows the Setup default-model block lists, the default first -- and the **folder** (Studio's
own by default), then **New session**. Studio's server starts `halo --headless --session-for studio` as a child: the
same loop the terminal runs, the same session log, its control socket the only door
([REMOTE.md](REMOTE.md#a-session-without-a-terminal-33110-r2)). Session opens on it with the keyboard in the Prompt
box; it registers a moment later and shows on Agents -> Live and on the Map as a session of this harness, its chip saying
**no terminal**.

You drive it from the Prompt panel exactly as a terminal session: a turn, a `/` command, Queue it and Steer while a
turn runs. **Its asks wait for you there** -- a permission, a question, a plan, an approval shows in the panel with
the card's buttons and the turn holds until you answer. With no Studio page open, the Attention row says
"waiting on you in Studio", so whoever opens Studio next sees it.

**Closing the tab does not end it**; nor does stopping Studio. The Prompt header of a session with no terminal has
**Open in terminal** (copies `halo --cwd "<folder>" --resume <id>`, which opens the same log in a terminal once the
session ended) and **End session** (asks first, then sends `shutdown`: the session finishes its step and leaves the
registry). A Studio that restarts finds the sessions it started in `~/.halo/studio-sessions.json`.

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
`styles/session-target.css`; 3.3.11.0 R1 the Prompt panel: `Prompt.tsx`, `PromptComposer.tsx`, `PromptFeed.tsx`,
`promptStore.ts`, `promptSend.ts`, `styles/prompt.css`, `studio/sessions_prompt_api.py`, `remote/prompt_queue.py`,
`remote/receipts.py`, `remote/receipt_seams.py` (tests: `tests/test_studio_prompt.py` in headless Chrome,
`tests/test_remote_submit.py`, `tests/test_receipts.py`, `tests/test_sessions_api_prompt.py`);
3.3.11.0 R2 a session without a terminal: `NewSession.tsx`, `studio/sessions_new_api.py`, `halo_harness/headless_session.py`
(tests: `tests/test_studio_headless.py` in headless Chrome, `tests/test_sessions_new_api.py`, `tests/test_headless_session.py`,
`tests/test_attention_headless.py`);
`halo_harness/session_trace.py` (the trace),
`session_trace_cli.py` (`halo session export`), `studio/sessions_api.py`
(the route), `studio/postmortem_api.py` (Why this answer?). Tests: `tests/test_postmortem.py`, `tests/test_session_trace.py`,
`tests/test_studio_session_target.py` (headless Chrome).

## The steer's image and the Screenshot button

(3.3.6.0 R6.) Ctrl+V with an image on the clipboard, or an image file dropped on the Live column's Steer box, becomes a
chip under it: the file name, its width x height and size, and a remove button; one image per steer, 5 MB at most.
Send posts the steer with it (`live/<harness>/<sid>/command {cmd: steer, text, image: {media_type, data_b64}}`):
Studio writes the PNG to the session's images folder and the control socket's steer carries its path; the session
builds the same blocks the TUI's paste builds, its log keeps `image_path` only, and a steer sent while the turn works
lands at the steer's safe point. The **Screenshot** button in the Live header captures the screen of the machine the
session's harness runs on (a Mac or Kali driving this Studio captures this PC's screen, as its title says) and puts
the capture on the chip for the next steer. When the session's model cannot see, the chip carries the eyes offer's
line and its three buttons (Visual lane, Describe it, Text only; the one picked rides with the steer); a running
turn's own eyes card shows the same three above the target line. Typing a whole new prompt from Studio is the
Prompt panel's (3.3.11.0 R1, above), whose paste and drop take the same path.

## The mode word (3.4.1.0 R3)

The Live column's header says the session's **permission mode** as one small word (`session-mode`): auto, default,
acceptEdits, plan, bypassPermissions or dontAsk, with the mode's one-line meaning on hover (the words the model itself
is told each turn: auto, "every call runs except your own deny and ask rules"; plan, "read-only: the agent writes a plan
and asks you to approve it"; ...). It is read from the session's row (the registry's `mode`) and moves with the session's
own status frames, so Shift+Tab in the terminal or `/plan on` changes the word. Nothing shows before the session has
said its mode.
