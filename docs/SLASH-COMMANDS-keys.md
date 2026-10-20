# Slash commands: prefixes, keys and cards

Read this when you want the `@path` and `!cmd` prefixes, a key binding, or the keys a card answers to.

Part of [Slash commands, keys, and prompt prefixes](SLASH-COMMANDS.md), which lists every part.

## Prefixes in the prompt input

These are recognized only when they're the very first character(s) typed
on an otherwise-plain line (not inside a pasted multi-line block):

- **`/name [args]`** -- a slash command, resolved through the registry
  above (builtin > custom > skill > MCP-provided, by whichever added the
  name first).
- **`!cmd`** -- runs `cmd` through the Bash tool and the ordinary
  permission engine, **outside the model loop entirely**: the command and
  its result appear in the transcript as an ordinary tool card, but the
  model is never invoked for this turn at all. This is the TUI's own
  prompt-line prefix, distinct from a command/skill body's `` !`cmd` ``
  backtick form above (same permission gating, different trigger).
- **`@path`** and **`@path#L10`** / **`@path#L10-20`** -- attaches a file
  (optionally one line, or an inclusive line range) as a log snapshot
  before the turn is sent, resolved the same way the Read tool itself
  would resolve a path. The `@mention` text itself is left in the visible
  prompt verbatim; the file content rides alongside it, never replacing it.

Typing `/` or `@` as the first character of the current word opens a
completion popup (`Tab` to accept the highlighted entry): `/` completes
against every registered command name/alias; `@` walks the filesystem from
`cwd` one directory level at a time (hidden entries and common
build/VCS directories like `.git`/`node_modules`/`__pycache__` are pruned).

## Key bindings

These single keys are bound globally, always available regardless of
focus: `Ctrl+C` (copies the selection, else the last assistant reply; never
interrupts a turn -- `Esc` does; a second press within 3s opens a "Quit
Halo? Enter quits, Esc stays" card, and the terminal stays open either way;
`quit_on_double_ctrl_c: false` in `~/.halo/config.json` removes the card,
leaving `/exit`/`Ctrl+D`/`Ctrl+Q` as the only ways to leave),
`Ctrl+Shift+C` (3.1.6.0: copies the whole chat-box draft; many terminals
keep this key for their own copy, and `/copy draft` does the same from the
chat box), `Ctrl+D`
(quit when the prompt is empty, else forward-delete), `Ctrl+Q` (1.0.1:
force quit -- exits even if the session is wedged; waits at most 2s for a
clean shutdown, then exits regardless), `Esc` (interrupt), `Shift+Tab` (cycle
permission mode through `default` -> `acceptEdits` -> `plan` -> `auto` ->
back to `default`; 1.0.1: if a permission card is still pending when the
mode lands on `auto`/`bypassPermissions` it's resolved as allowed right
away, `dontAsk` resolves it as denied), `Ctrl+L` (clear the transcript
view), `Ctrl+O` (toggle verbose -- shows every intermediate message/
expands tool cards), `Ctrl+R` (history search), `F1` (help), `Ctrl+P`
(command palette), `Ctrl+E` (edit the current prompt draft in `$VISUAL`/
`$EDITOR`). 1.0.1: `Ctrl+End` re-anchors the transcript to follow new
output (and clears the "N new" indicator); bare `End` does the same
EXCEPT while the prompt input has focus, where it means cursor-to-end-of-
line as usual (the overwhelmingly common case -- use `Ctrl+End`, or click
the "N new" indicator itself, to be sure it reaches the transcript).

`Ctrl+X` is a **chord prefix**: press it, then a second key within 1
second, while a small "which-key" overlay shows the live list of
continuations. The built-in chords:

| Chord | Action |
|---|---|
| `Ctrl+X Ctrl+S` | export the session |
| `Ctrl+X Ctrl+R` | rename the session |
| `Ctrl+X Ctrl+F` | fork the session |
| `Ctrl+X Ctrl+L` | open the resume picker |
| `Ctrl+X Ctrl+U` | rewind: undo |
| `Ctrl+X Ctrl+Y` | rewind: redo |
| `Ctrl+X Ctrl+K` | show session stats |
| `Ctrl+X ↓` | jump to the next sub-agent block in the transcript |
| `Ctrl+X ↑` | jump to the previous sub-agent block |

`~/.claude/keybindings.json` merges onto these defaults the same way
Claude Code's own keybindings file is documented to work: additive (only
name a context to change something in it), a `null` action **unbinds**
that key in that context; `/keybindings` prints the fully-resolved result.
See the `keybindings-help` skill for the file format itself.

Inside the chat area specifically: `Enter` submits, `Ctrl+J`/`Alt+Enter`
inserts a newline without submitting, `Tab` accepts the completion popup,
`Up`/`Down` walk prompt history (prefix-filtered). Inside the transcript:
`o` on a focused tool card opens a full-screen pager of its untruncated
output; `Ctrl+O` there toggles that card's own expanded/collapsed state
(distinct from the global verbose toggle); 2.0.1 (W4c) `y` -- on the card
itself or inside its pager -- copies that same full output to the
clipboard without opening/closing anything. `Y` copies the whole current
turn (the last prompt plus everything produced for it so far) and works
anywhere EXCEPT while the chat box has focus, where a bare `Y` just types
a capital Y as normal; see "Copy and paste" in `docs/TROUBLESHOOTING.md`
and the `/copy` command above for the mouse-free copy actions.

**Auto-scroll (1.0.1).** The transcript follows new output (a streaming
reply, a growing tool card) automatically as long as it's scrolled to the
bottom. Scrolling up (`PageUp`, the mouse wheel, a drag-select) releases
that following and shows a "↓ N new" indicator in the status bar, counting
everything that's landed since; scrolling back to the bottom, pressing
`Ctrl+End`, clicking the indicator, or submitting a new prompt all
re-anchor to the bottom and clear the count.

## Cards and their keys

A card takes keyboard focus the instant it's mounted (so its own number/
letter keys win over the prompt input). **1.0.1:** typing free text while
a PermissionCard, PlanCard, or QuestionCard is pending now ANSWERS that
card directly, exactly like pressing its own deny/keep-planning/"Other"
key first -- a PermissionCard denies with the typed text as feedback, a
PlanCard keeps planning with it, a QuestionCard takes it as the "Other"
answer -- rather than becoming a steer on the turn underneath (which is
what typing while ANY other card, e.g. the `/effort` selector or a rewind
confirmation, still does).

- **PermissionCard**: `1`/`y` allow once, `2`/`a` allow for the session,
  `3` allow always (writes a rule to `.claude/settings.local.json`), `4`/
  `n`/`Esc` deny (borrows the prompt input for one line of optional
  feedback first, or just type the feedback directly -- see above). While
  pending, the status bar shows "permission needed: 1 yes · 2 session ·
  3 always · 4 no" and the prompt placeholder reads "1-4 answers the
  request above, or type why not".
- **QuestionCard**: an option list per question (arrow keys + `Enter`, or
  click); `Tab` moves to the next question when more than one was asked;
  `Esc` dismisses without answering; selecting "Other..." (or just typing
  an answer directly) borrows the prompt input for a free-text answer.
- **PlanCard**: `1`/`a` approve with auto-accept-edits mode after, `2`/`m`
  approve with manual mode after, `3`/`k`/`Esc` keep planning (borrows the
  prompt input for optional feedback, or just type it directly).
- **EffortCard** (`/effort` with no argument, 1.0.1): `Left`/`Right` or
  `h`/`l` move between this route's own accepted effort levels, `Enter`
  applies, `Esc` cancels and keeps the old value. A model with no
  adjustable effort shows a one-line card that closes on any key.
- **RewindCard** (`/rewind`/`/undo`/`/redo`): `1`/`y`/`Enter` restore,
  `2`/`n`/`Esc` cancel.
- **ImproveCard** (one per `/improve` candidate): `a` apply, `e` edit the
  drafted body in `$VISUAL`/`$EDITOR` then apply, `s` skip, `d` dismiss
  this exact candidate forever (content-hash-based, survives restarts),
  `q`/`Esc` stop reviewing, `o` opens the first cited evidence excerpt in a
  pager.
