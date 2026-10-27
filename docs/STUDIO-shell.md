# Studio: the shell

Read this when you find your way around Studio's header, sections, panels and Start views, or open it on a bio, a lineup or the Team.

Part of [Halo Studio](STUDIO.md), which lists every part.

## The shell (3.0.3.0)

`halo studio` opens a React shell with eight sections in the icon rail on the left (3.3.2.0; the top bar's tab strip before):
**Session | Team | Roles | Fleet | Design | Orchestra | Packs | Setup** (`Alt+1`..`Alt+8`, or `?mode=` in
the URL for the first six; Fleet since 3.0.5.0, Team since 3.0.8.0, Session since 3.1.4.0, Packs since 3.2.0.0, Setup since 3.3.0.0; Org and Flow are
gone since 3.1.4.0). The order is one list, `SECTIONS` in `ui/src/routes/index.tsx`
(3.1.6.0: Session `Alt+1`, Team `Alt+2`, Roles `Alt+3`, Fleet `Alt+4`, Design `Alt+5`,
Orchestra `Alt+6`; 3.2.0.0 R6: Packs `Alt+7`, [STUDIO-packs.md](STUDIO-packs.md); 3.3.0.0 R1: Setup `Alt+8`): the rail's rows, the `Alt+N` keys, the palette's groups, the first key of each
section's **How this works** and the status bar's key hint all read it.
Session is this session, live: the Fleet panels scoped to this harness (see
[Session](STUDIO-sections.md#session)); with nothing saved for the browser Studio opens on it while a
session of this harness is live. Orchestra is the live run console (see [Orchestra](STUDIO-orchestra.md#orchestra-the-run-console)
below),
Fleet every harness and every agent, live (see [Fleet](STUDIO-fleet.md#fleet-every-harness-every-agent)),
Team the project's team file as one board (see [Team](STUDIO-team-roles.md#team-people-blocks-and-stages-on-one-board));
Roles and Design are React sections since 3.0.7.0 (see
[What you see (Roles)](STUDIO-team-roles.md#what-you-see-roles) and
[Design mode](STUDIO-design.md#design-mode-prototypes-pages-and-decks-on-your-own-apps)).
The classic plain-JS page (`/legacy/`, `halo studio --legacy`) is gone since
3.0.7.0 R2: every section is part of the shell.

- **One header.** Every section is drawn by the shell itself: one top bar,
  one status bar, no page framed inside another (3.0.7.0 R2 removed the last
  framed page, Roles).
- **A movable workspace.** Every section is a set of panels on a 24-column
  grid (8 px rows). **Click anywhere on a panel to work in it**: a ring
  marks the panel you are on, and an open Inspector follows it. Drag a
  panel's title bar to move it, an edge or corner to resize it; everything
  snaps to the grid and the others make room (3.2.2.0), live while you drag:
  a panel you drop on another takes columns from it first (the neighbour
  gives up columns on the side facing it, down to its smallest width, and
  the moved panel takes what is left); two panels in the same columns (both
  full width among them) trade places, the neighbour taking the moved
  panel's old rectangle; only when neither fits does the neighbour go down,
  and never below the visible rows, so no panel leaves the window on a move.
  An edge or corner you drag is a splitter: the panel on the other side of
  that edge shrinks or grows by the same columns or rows (down to its
  smallest size). A panel is one title line (3.3.2.0): its title, its
  **?** (its help, the one-line "what it is" first), the strip button
  (**Collapse to a strip**; on a strip the chevron that opens it), a close
  on an optional panel (the **+** adds it again) and ONE **...** menu:
  **Float** over the grid (or dock it back), **Compact / Expand** (also a
  double-click on the title), **Collapse** to a one-line strip (or open
  it), **Reset this panel**, **Settings** and **Help**. A strip that opens
  in an arrangement you did not move by hand joins the column on the main
  panel's right (the main panel gives up those columns, collapsing it
  again gives them back); in your own arrangement it pushes the panels it now covers
  down. With a panel focused, `Alt`+arrows move it and
  `Alt+Shift`+arrows resize it. The arrangement is remembered per section in
  your browser (`localStorage` key `halo.studio.layout.<section>`, version 2:
  an arrangement saved by 3.0.3.0 keeps its places, not its faces);
  **Arrange panels** (the header's **...** menu, or the palette)
  puts every panel you have open back in the section's default place and
  size in one press, and keeps what you chose (a strip stays a strip, a face
  stays, a floating panel floats); **Reset layout** (the same two places)
  returns to the defaults, which follow the window size until you
  rearrange something.
- **One thing per section** (3.3.2.0). Each section opens on its main
  panel filling the stage, every other panel a strip at the foot (one or
  two rows of them, side by side): Session on **Live**, Team on the
  **Board**, Roles on the **Canvas**, Fleet on the **Map**, Design on the
  **Artboards**, Orchestra on the **Workflow** (the run's plan; a planned
  run is the plan canvas), Packs on **Installed**; Setup is pages and keeps
  them. A click on a strip (or its row in the **+**) opens it in the column on
  the main panel's right (as wide as the widest panel there, at most half
  the stage; the panels in it share its height); a Roles card or a Team stage
  you select opens its Inspector strip. Your saved layout wins over the
  default; **Reset layout** returns to it, and **Arrange panels** lays out
  the panels open now by the same rule. `?open=all` in the URL draws every
  panel in its own place instead (the arrangement before 3.3.2.0, for a
  link or a capture); `?open=a,b` opens those strips.
- **The section header's menus** (3.3.2.0 R2; the expanded rail's PANELS
  list and LAYOUT block before). Beside the section's title and its **?**:
  the **+** lists the section's panels, each row saying what a press does:
  **add** an optional panel that is not on the page, **bring back** a strip
  or a panel that is not up (with the **strip** badge), **focus** an open one
  (with **float** when it floats); a section may add its own group under the
  panels (Orchestra: **New run** and its runs, newest first). The **...** holds
  **Arrange panels**, **Reset layout** and **How panels move** (the section
  help, opened on its **Moving panels** part: drag a title bar to move a
  panel, an edge to resize it, `Alt+Shift+Down` grows the focused one); a row
  with nothing to do stays in the list, disabled, its word saying why
  ("already default"). Both open from the keyboard (`Enter`, or `ArrowDown`
  on the button), the arrows, `Home` and `End` move, `Esc` closes. A small
  **custom layout** badge shows beside them only while the section's layout is
  your own. Setup (pages, not panels) draws none of the three. In the palette,
  **Arrange panels** and **Reset layout** name the section in their hint and
  say so when there is nothing to do.
- **Two faces and the settings.** Every panel opens on its **full face**,
  ready to use with no button to press first; **Compact** (its **...**
  menu, or a double-click on the title) is its summary (what
  it is, one live indicator, one or two big numbers, readable from across the
  room) and is the default only where a section says so (Orchestra's
  Workflow, Run grid and Log, where it is the whole graph, every tile and the
  newest lines). **Settings** opens the Inspector on the right: what the
  panel is and how to use it, the face, strip, float, the exact grid
  position, reset, and the panel's own options.
- **Help where you are.** `?` on a focused panel (or the **?** on its
  title line, or Help in its ... menu) opens a small popover with its
  `about` line first and a few lines on how to use it (the **?** again
  closes it); `?` again, `?` away from a panel, the **?** in the header beside the
  section's title and
  the palette's **Help: how <section> works** open **How this works** for the
  section: what it is, five to eight numbered steps, every panel with its
  about line, and the keys, `Focus` last (the copy is below, in
  [How each section works](STUDIO-sections.md#how-each-section-works)).
- **Nothing opens on its own** (3.3.2.0). A section shows its own content
  when you open it, the first time or any time: no welcome card, no help, no
  dialog (the first-visit welcome and its `halo.studio.seen.<section>` keys
  are gone). The one exception is **Start here** on a fresh home, over the
  section the page opened on, once per browser (below).
- **The rail** (left, 3.3.2.0) is an icon rail, 56 px: one icon per
  section, its title as the tooltip, the current one lit, a dot on Session
  while a session is live, the number of agents at work on Fleet, the packs'
  own sections under a thin divider with the diamond. The rows print no key:
  `Alt+N` is in the palette's **Go to** and in **How this works**. The
  chevron at its foot expands it to 200 px (remembered per browser,
  `halo.studio.rail`; `?rail=open` expands it for one page): each section's
  title beside its icon, and nothing else (3.3.2.0 R2: the rail holds the
  sections only, collapsed or expanded). The panels are the header's **+**,
  Arrange and Reset its **...**, Orchestra's runs a group in its **+**, and the
  **Fleet tree** (every harness, its sessions and their agents with a status
  dot each, the live and need-you counts on top, a session that waits on you
  with its inline answer, the "While you were away" card) is Fleet's
  optional **Tree** panel, added with the **+**. While that card waits, the
  Fleet icon carries an amber dot; a click on it opens Fleet on its Tree.
- **The inspector asks first** (3.3.2.0). The 340 px column on the right is
  closed until something opens it: a panel's **Settings**, a Design
  artboard's knobs. Its close button (or `Esc`) gives the width back to the
  stage; open or closed is remembered per browser (`halo.studio.inspector`),
  and the next selection opens it again.
- **Focus** (3.3.2.0): `F` (outside a text field), the corners button in the
  header or the palette's **Focus** hide the rail, the inspector and the
  status bar; the stage takes the whole window. `F` again brings them back as
  they were. Where a section's own `F` follows an agent or the Log (Session,
  Fleet, Orchestra, the Roles Live tab) or fits the Roles canvas,
  `Shift+F` is Focus. Remembered per browser (`halo.studio.focus`).
- **Density** (3.3.2.0): the header's rows button beside the theme (or
  the palette's **Density: compact** / **Density: comfortable**) switches
  two token sets in `ui/src/styles/tokens.css`: compact has tighter spacing
  (a 30 px title line, 9 px inside a panel, 2 px between panels, a 46 px
  header) and a type scale one step smaller; the colours stay. Remembered
  per browser (`halo.studio.density`), `data-density` on `<html>`.
- **The palette** (`Ctrl`/`Cmd`+`K`): a mono prompt with fuzzy matching and
  grouped results (Go to, Help, then the sections in the tab order: Team, Roles,
  Fleet, Design, Orchestra; then Media, View, Layout), keyboard first: arrows,
  `Enter`, `Esc`. Every shortcut is shown next to its command.
- **The status bar** shows the live feed (a dot that is green when
  connected, amber while connecting or reconnecting, red when unreachable,
  and ticks once per event), the session count, the fleet (agents at work
  and how many wait on you), the team (3.0.8.0: its stages running now, when
  the repo has a team file), the event count, the section's own status
  line (Roles: the open lineup, its cards and problems, saved or not;
  Design's project) and the section's layout
  state. `Esc` closes the palette, a menu or a help card, then the Inspector.

**Visual language.** The dark theme ("holo", the default) is a near-black
navy with glass panels: a translucent surface and a 1 px edge; the focused
panel alone (3.3.2.0) adds a soft glow, small corner brackets
(`--bracket-alpha`, 0 turns them off) and a mono data line (its size and
face), and an idle panel breathes only while focused. Cyan is
the one accent for "live" and "do this", amber means "needs you", magenta-red
an error, green done. Data labels and numbers are monospaced next to a clean
sans for prose. The light theme is Catppuccin Latte; the theme menu offers
dark, light and "follow the system". Every colour is a token in
`ui/src/styles/tokens.css` (`--bg`, `--surface`, `--surface-glass`,
`--line`, `--glow`, `--accent`, `--accent-2`, `--warn`, `--bad`, `--ok`,
`--text`, `--muted`, `--mono`, `--sans`, `--radius`, `--ease`, ...).
Motion is short (150-250 ms, ease-out) and always means the same state,
through `data-motion` on any element:

| `data-motion` | Looks like | Means |
|---|---|---|
| `idle` | a slow breathing glow on the border (4 s) | present, nothing running |
| `working` | a thin light flowing along the top edge | something is running |
| `waiting` | a soft amber pulse (1.2 s) | it needs you |
| `done` | one brief green sweep, then still | it just finished |
| `error` | one red flash, then a steady red edge | it failed |
| `live` | a small dot that ticks once per event | a feed is connected |

Under `prefers-reduced-motion` none of it moves; each state keeps its colour
cue. A section tab "works" while that section has fresh activity, toasts
sweep green or flash red once, and nothing loops except `idle`, `working`
and `waiting`, which describe an ongoing state.

## What is on disk, as it changes (3.2.2.0)

`studio/files_live.py` is one daemon
thread per Studio server (started and stopped with it) that lists, every
1.5 s, the user `teams/` and `agents/` folders, the project's `.halo/teams/`
and `.halo/agents/`, `config.json` and `studio/layouts/` (names, mtimes,
sizes). A change is gathered for 300 ms (longer while files keep moving) and
sent once per kind as `{"session_id": "studio", "event": "files_changed",
"data": {"kind": "lineups" | "bios" | "config" | "layouts", "names": [...],
"removed": [...]}}`, to every browser (a one-session feed too). Nothing that
writes the files publishes anything: the watcher sees every writer, a
session's Edit tool, `halo teams apply`, `halo agents`, `halo config set`,
another Studio. The pages subscribe through `lib/filesLive.ts`
(`onFilesChanged`, 300 ms merge) and re-read: Roles (the lineup list, the
open lineup, the Bios panel, the bio form, the card positions, the active
mark and the default model), Team (`GET team` and the board), Session (`GET
fleet`, on config), Orchestra's LINEUP list, the model selects' "the
lineup's" / "the default" answers, the Pack Manager's Templates. Studio's own
saves come back as a frame too and change nothing: the page compares the
file with what it holds. A pack's files are the `pack_changed` frame's.

## Opening Studio on a bio, a lineup or the Team (`halo studio --edit`)

3.1.1.0: Studio is the one editor of bios and lineups; the terminal shows
them and opens Studio on the one to change. An **edit target** is
`bio:<name>`, `lineup:<name>` or `team`, and it rides in the page URL:

```
http://127.0.0.1:<port>/?mode=roles&edit=bio:coder#t=<token>
http://127.0.0.1:<port>/?mode=roles&edit=lineup:halo-dev-cycle#t=<token>
http://127.0.0.1:<port>/?mode=team&edit=team#t=<token>
```

A page opened on `?edit=` goes straight to it (`shell/edit.ts`): `bio:` opens
Roles with the Bios panel on that bio's form, `lineup:` opens that lineup
with the Inspector on its Lineup tab, `team` the Team section. Start here
stays shut on such a page.

`halo studio --edit <target>` (and `halo agents edit`, `halo teams edit`,
the TUI's `/edit`, `e` in the terminal's bio and lineup views, the wizard's
**Edit in Studio**) finds the Studio running for this home
(`~/.halo/studio.json`) and sends `POST /api/focus {edit}`. Studio puts a
`focus` frame on its live feed, every open page opens the target the same
way, and the answer says how many pages took it (`{edit, mode, pages}`); no
new tab opens. With no page open the browser opens the URL; with no browser
the URL is printed. With no Studio running, one starts in the background
with `--edit` and opens the browser on the target. `--no-open` only prints
the URL (over SSH: forward the port and open it on your machine).

## The guided first run (3.1.1.0)

**Start here.** On a fresh home -- no lineup of your own (only the shipped
lineups or their untouched copies, none active) and no run (no Orchestra run
in Studio's repo, no `halo start` sample under `~/.halo/start/`) -- Studio
opens on a **Start here** card over the section the page opened on (3.3.2.0:
only there, and once per browser). Above its
button the card shows the same lines `halo start` opens on (3.2.2.0;
`GET /api/start` carries them as `card`): what it does in seven steps, the
models it will call, the estimated cost, the time, what it writes, and that
your active lineup is not touched. **Run the guided first run** runs
`halo start --yes` as a background job in Studio's
process (`POST /api/start`): the same seven steps as in a terminal (a lineup
copied into your scope as `my-halo-dev-cycle`, the sample repo, one
Orchestra goal with `plan: review`, the plan approved, the lanes, the report
and the coach, where to go next), each listed with its state while the
running one shows its command and its last lines; the outcome names the
lineup, the run and its repo, with buttons into Roles, Team and Fleet.
Closing the card keeps the start running (the palette's **Start: the
guided first run** brings it back; **Stop the start** ends it). **Just look
around** dismisses the card for this home (`~/.halo/start/dismissed.json`,
every browser). Any answer (**Set up this box**, a run, **Just look around**,
closing it, leaving for another section) is remembered in this browser
(`halo.studio.start`) and the card does not come back on its own; the
palette's **Start: the guided first run** opens it on any section. It runs on the
model you configured; with none, the card says so and points at `halo init`.
`?tour=off` keeps it shut.

**Set up this box** (3.3.0.0 R3) is the card's first button: it opens the
Setup section and closes the card (3.3.2.0: for this browser; the home
still counts as fresh). While no provider is set up (no key, login or
default model: what `halo start` checks), it is the primary button, and a
fresh home opens on Setup whatever section this browser saved (`?mode=`
still wins; the served page says `data-no-provider`), where the card is not
drawn (3.3.2.0: Setup's Summary offers the guided first run instead). **Run the guided first
run** with no provider set up is answered `422 no_provider`: the card closes,
Setup opens and a toast says "no provider is set up yet: Setup".

The steps arrive as `start` frames on the live feed (`/api/events`; Studio
also polls `GET /api/start` while the card is open):

```json
{"session_id": "start:<job id>", "event": "start",
 "data": {"job": "<job id>", "step": 4, "total": 7, "key": "plan", "title": "The plan",
          "why": "...", "command": "halo orchestra plan --repo ...", "state": "running", "lines": ["..."]}}
```

`state` is `running`, `done`, `failed` or `stopped`; one last frame has
`key: "summary"`, `state: "finished"` and `summary: {ok, stopped_at, reason,
lineup, repo, run, report, coach}`. Routes: `GET /api/start` (`{fresh,
dismissed, show, own_lineups, active_team, runs, starts, job, plan}`), `POST
/api/start` (202, 409 while one runs, 422 with `reason: "no_provider"`),
`POST /api/start/dismiss`, `POST /api/start/stop`.

**One story.** Every section's Start view ends on a **Next** footer that
names the next section and why, in this order: Roles -> Orchestra ->
Team -> Design -> Fleet (Fleet's points back to Roles); the button
opens it.

**The Glossary.** The **?** in the header is a menu: **How
<section> works** (also `?`) and **Glossary**, a dialog listing every word
Halo uses (lineup, bio, role, tier, team, member, block, stage, lane, part,
step, mission, gate, claim, hand-off, plan, coach, orchestra run,
fleet, hub, harness, capability), each expandable to its one paragraph. Each
section's How this works card has a **WORDS** row: the glossary words that
section uses, each opening the Glossary on that word. The text is served by
`GET /api/glossary` (`{words: [{word, text}], source}`) from
[GLOSSARY.md](GLOSSARY.md), the same paragraphs `halo explain` prints; the
bundle carries no copy. The palette has **Help: glossary** too.

