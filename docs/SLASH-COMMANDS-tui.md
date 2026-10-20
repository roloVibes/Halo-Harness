# Slash commands: themes, Studio and the TUI

Read this when you change themes, open Studio, copy, rewind or tune the TUI, run the ten-minute start, look up a word, or add your own commands, skills and images.

Part of [Slash commands, keys, and prompt prefixes](SLASH-COMMANDS.md), which lists every part.

## Built-in commands: themes, Studio and the TUI

### `/theme [name]`
No argument: shows the current theme. With a name (`claude-dark`,
`claude-light`, either with a `-daltonized`/`-ansi` suffix), persists it to
`~/.halo/config.json` and (in the TUI) re-applies it live. In the TUI, Tab
completes theme names. The game themes and their toggles were removed in
3.1.5.0. See the Themes section of the [handbook](HANDBOOK.md).

### `/studio` `[session|roles|design|orchestra|fleet|team] [url]`
Halo 3.1.4.0: bare `/studio` (or `/studio session`) opens Studio on the
session you are in: the **Session** dashboard (`Alt+1`; `?mode=session&session=<this
session's id>`), its map, activity, attention, agent and cost. `/studio
<section>` opens that section. Either way the Studio already running for this
home is focused (every open page switches), else the browser opens it, else
one is started, and one line says what happened: opened, focused, or here is
the URL. The same as `halo studio --session` from a shell.

Halo 2.1.0, modes in 3.0.2.0: the sections are `roles` and `design`;
3.0.4.0: `orchestra` too; 3.0.5.0: `fleet`, every harness and agent live;
3.0.8.0: `team`, the team's board; 3.1.4.0: `session` (Org and Flow are gone
since 3.1.4.0). Bare `/roles` and `/design` are unchanged short forms. Roles
is your lineups and agent bios as an editable graph in the browser.
`/studio url` (or `/studio <section> url`) prints the URL of the Studio
this session serves without opening a browser; over SSH, forward the port it
names and open the same URL. See [STUDIO.md](STUDIO.md).

### `/design` `[url]`
Halo 3.0.2.0: opens Halo Studio's **Design mode**: artboards (HTML prototypes
in sandboxed frames, renders from the ArtCraft apps), chat, comment pins,
knobs, versions, variants, critique, contrast, exports and the handoff. The
same as `/studio design`; `/design url` prints the URL only. The command
family on the shell is `halo design` ([DESIGN.md](DESIGN.md)).

### `/exit`, `/quit` `[TUI-only for /quit]`
`/exit` in `-p` is a no-op note (the call already ends after this turn).
`/quit` is a TUI-only alias that actually closes the app (same as `Ctrl+D`
on an empty prompt).

### `/copy [code [N]|tool|draft]` `[TUI-only]`
2.0.1 (W4c): copies text to the system clipboard with no mouse needed.
Bare `/copy` copies the last assistant reply; `/copy code` copies that
reply's last fenced code block exactly as written (`/copy code 2` for the
2nd block, counting from the top); `/copy tool` copies the last tool
call's full, untruncated output (the same text its own `o` pager shows).
Every form shows a toast naming what was copied and how many characters.
In `-p` there is no transcript or clipboard to copy to/from, so it is a
no-op note instead.

3.1.6.0: **`/copy draft` copies the chat box's unsent text.** Type it over
your draft (or after `Esc` / `Ctrl+U` cleared the box) and it copies the
draft the box held just before the command, `[Pasted text #n]`
placeholders expanded to the pasted text; a message you sent is no longer
a draft. **`Ctrl+Shift+C`** copies the whole draft in one key, wherever
focus is (many terminals keep `Ctrl+Shift+C` as their own copy key and
never pass it on; `/copy draft` works in every terminal, and `Ctrl+A` then
`Ctrl+C` in most). A selection plus `Ctrl+C` still copies just the selection, and
`Ctrl+C` with nothing selected still copies the last reply (a second press
asks to quit).

3.1.6.0: **after every copy the status line says exactly what landed:**
"copied N characters via xclip" (or `wl-copy`, `xsel`, `clip.exe`,
`pbcopy`). When no clipboard tool landed the line says why -- on Linux with
none on PATH: "no clipboard tool: sudo apt install xclip (or wl-clipboard
on Wayland); sent OSC 52, which <your terminal> may ignore"; over SSH:
OSC 52 is the only path to your local clipboard -- and **the text is also
saved to `~/.halo/clipboard.txt`** (only you can read it, overwritten by
the next such copy), which the line names, so the words are never lost.
The first mouse drag in the transcript or the chat box shows one hint: hold
`Shift` while dragging for the terminal's own selection.

2.0.7 (the copy-out fix): every copy also confirms WHICH mechanism
actually landed (the external-tool floor, worded as above since 3.1.6.0),
and a total failure becomes a visible error
with the fix spelled out. A transcript mouse-drag copies the SELECTED
RANGE (a grazing drag no longer copies whole widgets), a leading BOM is
stripped on paste reads, and `halo doctor`'s clipboard line states the
full write/read path verdict. **Over SSH on Linux (e.g. a Kali VM)**:
OSC 52 is the only path to your REAL local clipboard, and **tmux drops
it unless `set-clipboard` is on** -- halo detects this (`tmux set -gv
set-clipboard`) and both the copy failure and `halo doctor` name the
one-line fix: `tmux set -g set-clipboard on`, then detach and re-attach.
Without tmux, OSC 52 passes straight through SSH to Windows Terminal
and just works.

### `/rename <title>`
Sets the session's title, real in both `-p` and the TUI (no live worker
thread needed -- it's a plain index-file write).

### `/fork` `[TUI-only live switch]`
Copies the current session's log to a new session id right now, leaving
the original untouched. In `-p`, this only gives you the new id to `-r`
into afterward; the TUI additionally switches the live session to the fork
immediately.

### `/stats [--models] [--tools]`
Bare: turns/cost/per-model/per-tool counts for *this* session only (from
already-in-memory log nodes -- cheap, synchronous). `--models`/`--tools`
switch to the richer cross-session telemetry aggregation (run off the UI
thread in the TUI) documented under `halo stats` in
`docs/COMMANDS.md`.

### `/tasks` (Ctrl+T)
H8 scope A: lists every background Bash job started this session
(`run_in_background`, or a foreground command that outran its timeout),
with status and a truncated command line. Halo 2.0.2 round 3: in the
TUI, `/tasks`/Ctrl+T instead opens a full-height panel -- every
running, queued, background and finished sub-agent of this session
(a sub-agent's own descendants indented under their parent), plus the
shared task board on a second tab (`Tab` switches); Enter opens a live
transcript viewer of the highlighted agent; Ctrl+T again, or Esc,
closes it. Print mode has no panel, so it keeps the original plain-text
background-jobs listing. See `docs/SUBAGENTS.md`.

### `/orchestra [run]`
Halo 3.0.3.0: the latest Orchestra run of this folder's repo (or the run
named): its workflow steps, one row per worker lane (state, pieces sent
back, cost, holder, title) and the last run log lines. In the TUI it is a
panel like `/tasks` that refreshes when the run log grows (`r` refreshes,
Esc closes); elsewhere the same text prints. Runs start with `halo
orchestra new` and `halo orchestra run`. See `docs/ORCHESTRA.md`.

### `/rewind [step-id]` `[TUI-only]`
Restores the working tree (every file a Write/Edit/NotebookEdit touched,
shadow-copied step by step, plus every file a Bash command created or
modified in a git repo cwd -- a `git status` diff before and after the
command, both newly-untracked files and a pre-existing tracked file the
command changed) to a recorded point. In `-p`, this needs the interactive
confirmation card and is refused with a note. With no `step-id` in the
TUI, opens a picker; a `RewindCard` always confirms before touching real
files. Limits: a Bash command run outside a git repo isn't shadow-copied
at all; a file already dirty before the command that the command modifies
further isn't separately captured (the before/after diff can't tell "still
dirty" from "dirtied again"); a rename/copy isn't tracked either.

### `/undo`, `/redo` `[TUI-only]`
One step back/forward through the same shadow history `/rewind` uses.

### `/keybindings`
Prints the fully-resolved `{context: {chord: action}}` keymap (built-in
defaults merged with `~/.claude/keybindings.json`).

### `/editor` `[TUI-only]`
Halo 2.0.2 round C: the keyboard-independent twin of Ctrl+E -- opens the
current prompt draft in `$VISUAL`/`$EDITOR` exactly like the shortcut
does, so a terminal that never delivers the Ctrl+E chord to halo at all
(VS Code's integrated terminal on macOS being the reported case -- see
`docs/TROUBLESHOOTING.md`'s "a shortcut does nothing on macOS") still
has a way to reach it: typing a command always works. `$EDITOR`/
`$VISUAL` unset shows the same toast either way. In `-p`, there's no
prompt draft to edit at all; prints a note saying so.

### `/keys` `[TUI-only]`
Halo 2.0.2 round C: opens a tester dialog that shows the exact key NAME
halo's own app received for each press -- so you can tell whether halo
is receiving a shortcut at all before assuming it's broken (the
terminal may simply be eating it first). Esc leaves. A key bound to a
`priority=True` app-level shortcut (Ctrl+E, Ctrl+X, Ctrl+End) still
shows up here too, even though its own action also still fires -- both
are useful signal. In `-p`, there are no keystrokes to show; prints a
note saying so.

### `/improve` `[TUI-only card review]`
In `-p`, prints a note pointing at the real headless surface,
`halo improve` (a *separate top-level subcommand* -- see
`docs/COMMANDS.md` -- never this slash command, since `-p` sessions must
never draft or write on their own). In the TUI, scans recent sessions,
drafts candidates with one model call, and reviews them one `ImproveCard`
at a time (see [Cards](SLASH-COMMANDS-keys.md#cards-and-their-keys)).

### `/intro` `[TUI-only]`
Replays the 2.0.0 launch intro (the typewriter line a fresh interactive
session shows above its first turn) -- a fresh `IntroLine` mounted at the
current transcript position and typed out again from scratch; any
keypress or a submitted prompt finishes it instantly, same as the
launch-time one. `/intro <n>` replays line n of the pool (1 the block-art
wordmark, revealed row by row with the ring in gold and the letters in a
gradient; 2 the copy-of-a-copy line; 3 the Red Dragon line). In `-p`,
prints a note pointing at the interactive TUI (there is no transcript to
replay it into).

### `/tips`
Halo 2.0.1: prints every tip that applies to this session right now --
the curated list plus one generated line per registered command the
curated list doesn't already cover (custom commands and skills included),
filtered the SAME way the TUI's own rotating input placeholder is (a tip
naming Databricks/OpenRouter/`--chrome`/MCP is shown only once that
provider or feature is actually enabled/present). Identical output in
`-p` and the TUI.

### `/start`
Halo 3.1.1.0: the ten-minute start in a panel over the session (the TUI runs
it; it does not open a terminal pane): a lineup copied into your scope, the
sample repo, one Orchestra goal with a reviewed plan, the run, the report
and the coach -- the seven steps one under another with their state, and the
newest step's why, command and lines below them. The panel runs straight
through like `halo start --yes` (the lead's plan is approved as it comes);
for one screen per step, or to change the plan on Studio's plan canvas
first, run `halo start` in a terminal. Esc stops a running start at its next
check (a waiting plan is rejected, a running Orchestra run asked to stop);
Esc again closes the panel. Outside the TUI `/start` says how to run it. See
`docs/COMMANDS.md` (`halo start`).

### `/explain [thing]`
Halo 3.1.1.0: what a Halo word means -- its one paragraph from
`docs/GLOSSARY.md` in a card over the session (Esc or Enter closes it), the
same text `halo explain <thing>` prints and Studio's Glossary lists. The
match is loose (`/explain lineups`, `/explain handoff`, `/explain orch`); an
unknown word lists the closest ones, and bare `/explain` lists every word.
Outside the TUI it prints the paragraph.

### `/coach [run] [--model] [--apply ID [--yes]] [--probe [--k N] [--yes]] [--undo [ID]]`
Halo 3.1.3.0: the post-run coach's card for a run of any kind (this
folder's latest run when no run is named), the same text `halo coach`
prints: each suggestion with its id, its why lines, what Apply writes, its
applied / undone state and the lead's paragraph once asked. `--model` asks
the run's lead for one paragraph per card (kept with the run; `--refresh`
asks again). `/coach --apply ID` shows the confirm card (the file and the
before -> after diff) and writes nothing; `/coach --apply ID --yes` writes
it. `/coach --undo [ID]` puts the file of the last apply (or that apply)
back when nothing changed it since. 3.1.6.0: `/coach --probe [--k N]` shows
the probe's cost line ("probe: 2 runs, up to $X") and runs nothing; `/coach
--probe --yes` starts the probe on a thread and answers at once, and `/coach`
shows its card first once it ends. 3.1.6.0: `/coach library [show|forget|fetch]
...` is `halo coach library`; `/coach library forget <entry>` says what it
would delete, and `--yes` deletes it. See `docs/ORCHESTRA.md` ("The coach",
"Probes", "The library").

## Custom commands and skills

Discovered from the same directories Claude Code uses, in the same
precedence, alongside the built-ins above: `~/.claude/commands/`,
`.claude/commands/` (custom commands, one `.md` file per command, filename
minus extension is the invocation), `~/.claude/skills/`, `.claude/skills/`
(skills, one `SKILL.md` per directory). A skill's frontmatter may set
`disable-model-invocation: true` -- this hides it from the model's own
Skill *tool* only; the user can still always type it as `/name`. A skill
wins over a same-named custom command; neither ever overrides a built-in.

Both share one body-expansion pipeline
(`commands/registry.py::expand_command_body`):

1. **`$ARGUMENTS`** -> the raw text typed after the command name, verbatim.
   **`$0`..`$9`** -> the typed text's own whitespace/quote-split tokens,
   **0-based** (not 1-based). If neither placeholder appears anywhere in
   the body and arguments were actually given, `ARGUMENTS: <input>` is
   appended to the end automatically.
2. **`${CLAUDE_SKILL_DIR}`, `${CLAUDE_SESSION_ID}`, `${CLAUDE_PROJECT_DIR}`,
   `${CLAUDE_EFFORT}`, `${CLAUDE_PLUGIN_ROOT}`** -- substituted from the
   running session; a variable the caller can't supply (or whose value is
   empty) is left **unsubstituted** rather than silently becoming blank.
3. **`` !`cmd` ``** -- runs `cmd` and splices its stdout in place, gated by
   the *current* permission engine/mode exactly like an ordinary `Bash`
   call would be (`auto`/`bypassPermissions` allow it outright; the manual
   modes honor the user's own ask/deny rules) -- a command's own
   frontmatter `allowed-tools: Bash(...)` entries are registered as
   temporary session allow rules first, cleared again at the next user
   message. An unpermitted or nonzero-exit command **aborts the whole
   invocation**.

A command/skill body may also reference `@path` (a local file) or
`@server:resource` (an MCP resource) -- both are read and appended as a
**separate context snapshot**, never inlined into the text the model
actually receives as the command's own body.

MCP server prompts become their own slash commands automatically, named
`/mcp__<server>__<prompt>` -- typing one calls `prompts/get` and feeds the
result back as the turn's prompt, same "prompt"-kind contract as a custom
command.

## Image attachments

Halo 2.0.3.1: Ctrl+V and Shift+Insert, when the clipboard carries an
image rather than text, read it (a short subprocess call, off the UI
thread) and insert an attachment chip at the cursor -- `[Image #1
1024x768]` (or `[Image #1]` when the size can't be read). A real
terminal paste or Ctrl+V whose text is the path of an existing
`.png`/`.jpg`/`.jpeg`/`.gif`/`.webp` file (a drag from Explorer/Finder,
with or without quotes) attaches that file the same way instead of
inserting the path. Backspace removes the last chip when the input is
nothing but chip labels (no other text typed); typing real text around a
chip leaves it alone, same as a long pasted-text placeholder does. Select a
chip and type over it (or cut it, or clear the box) and its image is dropped
with it; the other chips keep their numbers. A slash command typed with chips
pending keeps them for the next real prompt. Up-arrow recall of a prompt that
held a long paste brings the pasted text back with it.
Every pending chip becomes a real image on the NEXT submit, carried all
the way to the model (shown inline in the transcript when the terminal
supports it, else the same caption text the chip itself showed); a
model whose catalog row says it has no vision gets one notice instead
and the turn still runs, with the saved path mentioned in place of the
image. Over SSH (no remote clipboard reaches the terminal at all) every
reader comes back empty -- the one-line notice names the other two
ways in: `/paste <path>` or dragging a file.

- **`/paste`** -- reads the OS clipboard DIRECTLY (never through the
  terminal's own paste path) and inserts whatever it holds: text first
  (any size, through the same 4-line placeholder rule), then an image
  chip. This is the RELIABLE paste: a terminal that confirms its
  "large paste" warning and then silently drops the payload (observed
  on Windows -- the loss is in the console-event input layer below the
  terminal, not in halo) loses nothing here, because nothing travels
  through stdin. Uses a generous 10s clipboard read.
- **`/paste <path>`** -- attaches an existing image file by path, no
  clipboard involved.
- **`/images`** -- lists every pending attachment (its number, size,
  and saved path); **`/images clear`** removes all of them (Backspace removes the last one; same
  "chip-only input" rule Backspace follows -- with other text typed
  around a chip, only the internal record is dropped, the leftover
  label text is left for you to edit by hand).
