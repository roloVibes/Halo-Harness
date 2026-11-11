# Studio: the shell

Read this when you find your way around Studio's header, sections, panels and Start views, or open it on a bio, a lineup or the team's door.

Part of [Halo Studio](STUDIO.md), which lists every part.

## The shell (3.0.3.0)

`halo studio` opens a React shell with six sections in the icon rail on the left (3.3.2.0; the top bar's tab strip
before): **Session | Agents | Local | Packs | Setup | Settings** (`Alt+1`..`Alt+6`, or `?mode=` in the URL). 3.3.16.0
folded Team, Roles and Orchestra into Agents (R1, [STUDIO-agents.md](STUDIO-agents.md): Cast, Live and Workflows, 3.4.0.0 D: Runs went; the doors
`?mode=roles|orchestra|team` keep) and the Fleet section into Agents -> Live, Setup -> Machines and Local (R2,
[Fleet in Agents, Setup and Local](STUDIO-fleet.md#fleet-in-agents-setup-and-local); `?mode=fleet` lands on Live on the
fleet); Org and Flow went in 3.1.4.0, Design is the design pack's since 3.3.13.0. The order is one list, `SECTIONS` in
`ui/src/routes/index.tsx`: the rail's rows, the `Alt+N` keys, the palette's groups, the first key of each section's
**How this works** and the status bar's key hint all read it. Session is this session, live (the fleet's pieces scoped
to this harness, [Session](STUDIO-sections.md#session)); with nothing saved for the browser Studio opens on it while a
session of this harness is live. Agents is the cast, what runs now on every machine (a goal run too) and what ran (Cast: [the
canvas](STUDIO-agents.md#cast-the-lineup-and-its-bios), a goal run: [on Live and in
History](STUDIO-orchestra.md)); Packs is `Alt+4` ([STUDIO-packs.md](STUDIO-packs.md)). A
pack's own sections come after the core ones (the first on `Alt+7`); one may be drawn whole by the pack's own module
(3.3.13.0 R2: a view, as the design pack's Design section is: [EXTENSION_API.md](EXTENSION_API.md#a-sections-view)).
The classic plain-JS page (`/legacy/`) is gone since 3.0.7.0 R2: every section is part of the shell.

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
  two rows of them, side by side): Session on **Live**, Agents on Cast's **Canvas** (Live on the tree;
  a goal run's plan review folds it while open, 3.4.0.0 D), Local on Resources (the design pack's Design on its
  **Artboards**), Packs on **Installed**; Setup is pages and keeps
  them. A click on a strip (or its row in the **+**) opens it in the column on
  the main panel's right (as wide as the widest panel there, at most half
  the stage; the panels in it share its height); a Cast card you select opens its Inspector strip. Your saved layout wins over the
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
  are gone). (3.4.0.0: Start here, the one exception, left with the guided first run for the first-run pack.) The old exception was **Start here** on a fresh home, over the
  section the page opened on, once per browser (below).
- **The rail** (left, 3.3.2.0) is an icon rail, 52 px (3.3.15.0; 56 px
  before): one 40 x 40 icon per
  section, its title as the tooltip, the current one in the accent with a
  2 px bar at its left edge, a square on Session
  while a session is live, the number of agents at work across the fleet on Agents, the packs'
  own sections under a thin divider with the diamond. The rows print no key:
  `Alt+N` is in the palette's **Go to** and in **How this works**. The
  chevron at its foot expands it to 176 px (3.3.15.0; 200 px before; remembered per browser,
  `halo.studio.rail`; `?rail=open` expands it for one page): each section's
  title beside its icon, and nothing else (3.3.2.0 R2: the rail holds the
  sections only, collapsed or expanded). The panels are the header's **+**,
  Arrange and Reset its **...**, (3.4.0.0 D: Runs' runs group went with Runs). While "While you were away" waits, the
  Agents icon carries an amber dot; a click on it opens Live on the fleet with the card (3.3.16.0 R2).
- **The inspector asks first** (3.3.2.0). The 344 px column on the right (340 before 3.3.15.0) is
  closed until something opens it: a panel's **Settings**, an artboard's knobs
  (the design pack's). Its close button (or `Esc`) gives the width back to the
  stage; open or closed is remembered per browser (`halo.studio.inspector`),
  and the next selection opens it again.
- **Focus** (3.3.2.0): `F` (outside a text field), the corners button in the
  header or the palette's **Focus** hide the rail, the inspector and the
  status bar; the stage takes the whole window. `F` again brings them back as
  they were. Where a section's own `f` follows an agent or the Log (Session,
  an agent watched on Agents) or fits a canvas, `Shift+F` is Focus (on Live's canvas it switches the scope). Remembered per browser (`halo.studio.focus`).
- **Density** (3.3.2.0): the header's rows button (or the palette's **Density: compact** / **comfortable**) switches
  two token sets in `ui/src/styles/tokens.css`: compact is tighter (a 32 px title line, 9 px inside a panel, 2 px
  between panels, a 42 px header; comfortable since 3.3.15.0: 40, 12, 12, 48) with a type scale one step smaller;
  the colours stay. Remembered per browser (`halo.studio.density`), `data-density` on `<html>`. **The rules
  (comfortable, 3.3.16.0 R1b):** no control bar (a panel's title bar, Tabs, a section's bar, a form's button row)
  under 36 px (`--ctl-h`), no row that is a target (a strip, a page rail's item, an inspector Edit row) under 40 px
  (`--row-h`), 12 px inside every panel body and 12 px between panels, one thing open per section on load. The
  primitives mark themselves (`data-density="bar|row|body"`) and `tests/test_studio_density.py` measures every
  section against them; a fix changes a token or a primitive, never exempts an element.
- **The palette** (`Ctrl`/`Cmd`+`K`): a mono prompt with fuzzy matching and
  grouped results (Go to, Help, then the sections in the tab order: Agents -- its views, then the Roles and
  Orchestra lines and the fleet's; then Local, Setup, Settings, Media, View, Layout, then each pack's group), keyboard first: arrows,
  `Enter`, `Esc`. Every shortcut is shown next to its command.
- **The status bar** (26 px, 11 px mono) shows the live feed (a square that is green when
  connected, amber while connecting or reconnecting, red when unreachable;
  3.3.15.0: it no longer ticks per event, the EVENTS count says it), the session count, the fleet (agents at work
  and how many wait on you), the event count, the section's own status
  line (Roles: the open lineup, its cards and problems, saved or not;
  a pack's page its own) and the section's layout
  state. `Esc` closes the palette, a menu or a help card, then the Inspector.

**Visual language: the Instrument look (3.3.15.0).** The design session's proposal
([design/studio-instrument/PROPOSAL.md](design/studio-instrument/PROPOSAL.md)) as shipped: solid surfaces (no glass),
1 px hairlines, one shadow level for menus, dialogs and floating cards, and no glow. Cyan is work, selection and
focus; amber is what waits on you; red failed; green done. Data, labels and numbers are mono (12 px), prose sans (13 px);
a title is mono caps. A state is told four ways at once: a square, a colour, a rule and a word.

- **The panel frame** (`.glass`, `lib/ui/Surface.tsx` and every workspace panel): the surface, a hairline, a 6 px
  radius and four corner ticks, 10 x 1 px in the accent at the top left and the bottom right; the panel you are on
  (the focused one) has them in the text colour. Its three faces: the **full** face (title row and body), the
  **compact** summary and the **strip** (the collapsed title row: 44 px, 12 px apart, its bar centred); the title row is
  40 px (`--bar-h`; 36 at the least) with the state square, the mono-caps title and the mono data line; a body pads 12 px.
- **A confirmation says what it does.** A Dialog that asks before an action shows **DOES**, **COSTS** and **WRITES** as three
  mono lines before its buttons (`lib/ui/DialogCost.tsx`, `Dialog`'s `cost`): a pack's remove and update, Roles' Apply and
  its deletes, stopping a mission or a team run, a hand-off, a kick, deleting a local model.
- **The text box** (`lib/ui/TextBox.tsx`, `Field`'s `multiline`): every multi-line box is three lines at the least, grows with
  its text to 12 then scrolls, has no resize handle, takes its panel's free height with `fill`; a placeholder is two lines at most.
- **Map nodes** (the Session Map, Agents' Live on either scope): a 2 px rule across the top in the state colour,
  a 1 px outline 3 px out when the node is selected or a Live line for it is hovered, the model without its provider
  prefix (the full id in the tooltip and the Inspector).

Every colour is a variable of `ui/src/styles/tokens.css` (`--bg`, `--surface`, `--border`, `--line`, `--line-soft`, `--accent`, `--warn`,
`--bad`, `--ok`, `--text`, `--muted`, `--faint`, ...) beside the scales (`--r-panel`, `--s-1`..`--s-6`, `--t-title`, `--t-data`, `--dur-fast`, ...); no component file carries a colour literal.

**The palette set (3.3.12.0).** The terminal and Studio draw from one palette
set, chosen by one key: `theme` in `~/.halo/config.json`. The registry
(`halo_harness/themes/palettes.py`) holds eleven palettes, each `{id, label,
posture, tokens}` in one token vocabulary: `claude-dark`, `claude-light`,
`holo` (Studio's look before 3.3.15.0), `instrument` (3.3.15.0, the look above),
`paper`, `midnight`, `ember`, `forest`, `slate`,
`dusk`, `dawn`; `-daltonized` and `-ansi` modify any of them. Studio's
colours are one `:root[data-theme="<name>"]` rule per palette, generated
between two marker comments of `tokens.css` by `scripts/themes_css.py`
(`tests/test_themes_css_drift.py` regenerates and compares); the surfaces,
lines, ring, soft fills, shadow and scrim are derived from the tokens by posture
(`halo_harness/themes/studio_css.py`).
The server paints the first frame in the saved palette (`data-theme` on
`<html>`); 3.3.15.0 R4: unset is `instrument` on any system, Halo's default (and
the terminal's); `theme: auto` is the choice "Follow the system": `instrument` dark, `paper` light. The header's **theme menu** lists
"Follow the system" and the eleven, each with a swatch row (surface, text,
accent, accent-2, ok, warn, bad), the current one checked (unset: instrument); a pick writes the
key through `POST settings/set` (Follow writes `auto`; `halo config unset theme` is the default again), so `/theme`,
`halo config set theme`, Settings -> Themes and the header move one value,
and a change made in a terminal reaches an open page through
`files_changed`. The palette (Mod+K) has "Theme: <id>" per palette and
"Theme: follow the system". The per-browser dark / light choice of before is
read once: written to the key when the key is unset (`dark` -> `holo`,
`light` -> `claude-light`), then dropped.
**A pack's palettes (3.3.12.0 R2).** An enabled pack's `contributes.themes`
([EXTENSION_API.md](EXTENSION_API.md#themes)) join the set as
`<pack-id>/<id>`: the theme menu and Settings -> Themes list them after the
eleven in a group under the pack's id, with the same swatches; the palette has a
"Theme: <pack-id>/<id>" command each. tokens.css has no block for them (they
are not known at build time): `GET settings/themes` sends each one's CSS
variables (`halo_harness/themes/studio_css.py`, the derivation the eleven's
blocks are generated with) and `lib/theme.ts` sets them on `<html>` while the
palette is drawn, taking them off for any other; the server inlines the
saved pack palette's variables as one `<style id="halo-pack-theme">` rule the
page's CSP allows by its hash, so the first frame is already in it. When the
pack is disabled or removed, the theme saved before it comes back and the
page follows the `files_changed` frame.
**Motion (3.3.15.0: the Instrument look's rule).** Four animations carry meaning and everything else is still:

| What moves | How | When |
|---|---|---|
| an agent starts and ends | its node fades in and its edge draws from the parent (240 ms); a working child's edge carries a 4/8 dash moving toward it; done, the node and edge go green and fade to rest over 10 s | on a map: the Session Map, Roles Live |
| a receipt ladder climbs | each of the four marks fills 160 ms after the one before, once | the Prompt panel, beside your turn |
| the fit meter fills | once, from 0 to its level over 600 ms | a model row's fit meter |
| a toast arrives | a 16 px rise and fade over 220 ms; it holds 4 s and leaves with a 180 ms fade; an error stays until its ✕ | top right, under the header |

Besides those, the working state square blinks at 1.4 s, a waiting one pulses three times and then holds, and the
agent's Live caret blinks at 1 Hz, each only while that agent works or waits. `data-motion` on any element still names
the state (`idle`, `working`, `waiting`, `done`, `error`, `live`), drawn as a colour and a steady rule: working a 2 px
accent rule across the top, waiting an amber edge, done a green rule, error a red edge; nothing breathes, flows or
sweeps. **Nothing moves on a section load**: an animation plays only for a thing that appears after its page drew
(`lib/motion/born.ts`), never for what a section shows when it opens or opens again. Under `prefers-reduced-motion`
each one is an instant state swap: the dash stops and a working edge is solid accent.

**Toasts sit top right, under the header** (3.3.5.0 R0), on every section
(`.toasts` in `styles/base.css`: `top: calc(var(--topbar-h) + 8px); right:
16px`), so one never covers a page's foot (Setup's Back / Next). A paged
section (Setup, Settings) raises none for its own blocks: a block's result
is its own line.

**The hover card** (3.3.16.1, `lib/ui/HoverCard.tsx`, `lib/hover/`): one card for the whole page, mounted by the shell. A
box spreads `useHover(kind, key, render)` on itself; the pointer resting on it 350 ms (or the keyboard focusing it) shows
the card beside it, measured after it draws, right, left, below or above, inside the window with an 8 px margin, never
over its box (`lib/hover/place.ts`). It goes on leaving the box and the card, Esc, a scroll, a press, a drag, a section
switch and the box's "..." menu. `role="tooltip"` (`hover-card`, `data-kind`, `data-for`), the box `aria-describedby`;
no buttons on it. `lib/hover/HoverBody.tsx` is its one shape (a title, what the box is, at most eight rows, NOW, what a
click does); each kind's rows are a file of `routes/agents/hover/`. A box with a card drops its plain `title`; a button
or a `data-hover-skip` chip in it keeps its own. `studio.hover_cards` (Settings -> Studio) off: no card, the titles back
([Hover and click](STUDIO-agents.md#hover-and-click-33161)).

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
mark and the default model), Session (`GET
fleet`, on config), Orchestra's LINEUP list, the model selects' "the
lineup's" / "the default" answers, the Pack Manager's Templates. Studio's own
saves come back as a frame too and change nothing: the page compares the
file with what it holds. A pack's files are the `pack_changed` frame's.

## The owner's page and a pack's key

3.3.14.0 R1. A pack's page (a bundle panel, a section's view) runs in the shell's own
page, so the launch token alone cannot tell the owner's clicks from a pack's
script. Two values Studio derives from the token keep the two apart
(`studio/owner_proof.py`):

- **The owner proof.** The served `index.html` carries a per-launch salt as
  `data-owner-salt` on `<html>` (only for a page the browser navigates to: a
  `fetch("/")` or a frame of `/` gets none). `ui/src/lib/owner.ts` is the
  first module the shell runs: it reads the salt and removes the attribute
  before any pack module can load, and keeps it in its own closure (never on
  `globalThis`, never in storage, never through `packlib/`). The shell's own
  client (`lib/api.ts` `call`) sends `X-Halo-Owner: <hex HMAC-SHA256 of the
  salt keyed by the token>`; a write to a pack's grant, enable, disable,
  install, sources, update, rollback, remove, service, settings or config,
  the bundles, Setup, Settings or a session (new, a command, a prompt)
  without it answers 403 "this needs the owner's own page". A pack's page
  gets `api.lib`'s client instead, scoped to its own routes
  ([EXTENSION_API.md](EXTENSION_API.md#apilib)).
- **A pack's key.** What a page embeds where no header can go (an iframe,
  an image, a video, a module import) carries `?k=<hex HMAC-SHA256 of
  "pack-raw:<id>" keyed by the token>`, not the token: Studio takes it on a
  GET of that pack's own `/api/packs/<id>/...` and `/api/pack/<id>/file/...`
  only, never on a write, another pack's path or a core route, and no longer
  takes `?t=` there. `GET pack/registry` hands the shell each pack's `key`.

The shell itself is never framed by another page (`frame-ancestors 'self'`
in its CSP and `X-Frame-Options: SAMEORIGIN`), and `HALO_STUDIO_LOG` writes
`t=...` / `k=...` in place of their values.

## Opening Studio on a bio, a lineup or the Team (`halo studio --edit`)

3.1.1.0: Studio is the one editor of bios and lineups; the terminal shows
them and opens Studio on the one to change. An **edit target** is
`bio:<name>`, `lineup:<name>` or `team`, and it rides in the page URL (3.3.16.0 R1: `?mode=agents&view=...`;
`?mode=roles|team&edit=` from before still land):

```
http://127.0.0.1:<port>/?mode=agents&view=cast&edit=bio:coder#t=<token>
http://127.0.0.1:<port>/?mode=agents&view=live&edit=team#t=<token>
```

A page opened on `?edit=` goes straight to it (`shell/edit.ts`): `bio:` opens Agents on Cast with the Bios panel on
that bio's form, `lineup:` that lineup with the Inspector on its Lineup tab's summary (`lineup:<name>:<block>`, 3.3.16.0
R1b: that block's page), `team` Agents on Live (3.4.0.0 D; the page says so once). Start here stays shut on such a page.

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

## The guided first run (the first-run pack, 3.4.0.0)

"Start here" and Agents -> Runs' "Test this lineup" (Runs went in 3.4.0.0 D) were the guided first run's doors in Studio until 3.4.0.0. The
guided first run is the first-run pack since 3.4.0.0 (`halo pack install first-run`, then `halo pack enable first-run --grant-all`): enabled, its **First run** panel in the Agents section shows the card, Run, the seven
steps live and Stop, through the pack's own routes (`/api/packs/first-run/start/...`). A fresh home opens with nothing
over it. [The pack's README](../halo_harness/templates/packs/first-run/README.md).

