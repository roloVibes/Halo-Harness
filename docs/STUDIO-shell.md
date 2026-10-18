# Studio: the shell

Read this when you find your way around Studio's header, sections, panels and Start views.

Part of [Halo Studio](STUDIO.md), which lists every part.

## The shell (3.0.3.0)

`halo studio` opens a React shell with seven sections in the top bar:
**Orchestra | Roles | Org | Design | Flow | Fleet | Team** (`Alt+1`..`Alt+7`, or `?mode=` in
the URL; Flow since 3.0.4.0, Fleet since 3.0.5.0, Team since 3.0.8.0). Orchestra is the live run console (see [Orchestra](STUDIO-orchestra-flow.md#orchestra-the-run-console)
below), Flow the workflow console (see [Flow](STUDIO-orchestra-flow.md#flow-the-workflow-console)),
Fleet every harness and every agent, live (see [Fleet](STUDIO-fleet.md#fleet-every-harness-every-agent)),
Team the project's team file as one board (see [Team](STUDIO-team-roles-org.md#team-people-blocks-and-stages-on-one-board));
Roles, Org and Design are React sections since 3.0.7.0 (see
[What you see (Roles)](STUDIO-team-roles-org.md#what-you-see-roles),
[Org mode](STUDIO-team-roles-org.md#org-mode-the-company-in-paperclip) and
[Design mode](STUDIO-design.md#design-mode-prototypes-pages-and-decks-on-your-own-apps)).
The classic plain-JS page (`/legacy/`, `halo studio --legacy`) is gone since
3.0.7.0 R2: every section is part of the shell.

- **One header.** Every section is drawn by the shell itself: one top bar,
  one status bar, no page framed inside another (3.0.7.0 R2 removed the last
  framed page, Roles).
- **A movable workspace.** Every section is a set of panels on a 24-column
  grid (8 px rows). **Click anywhere on a panel to work in it**: a ring
  marks the panel you are on, and an open Inspector follows it. Drag a
  panel's title bar to move it, an edge or corner to resize it; the others
  make room and everything snaps to the grid. The title bar is the title,
  the panel's one-line **about** (what it is), ONE **Compact / Expand**
  toggle (on a collapsed strip: the chevron that opens it) and ONE **...**
  menu: **Float** over the grid (or dock it back),
  **Collapse** to a one-line strip (or open it), **Reset this panel**,
  **Settings** and **Help**. With a panel focused, `Alt`+arrows move it and
  `Alt+Shift`+arrows resize it. The arrangement is remembered per section in
  your browser (`localStorage` key `halo.studio.layout.<section>`, version 2:
  an arrangement saved by 3.0.3.0 keeps its places, not its faces);
  **Reset layout** (the rail, or the palette) returns to the defaults, which
  follow the window size until you rearrange something.
- **Two faces and the settings.** Every panel opens on its **full face**,
  ready to use with no button to press first; **Compact** is its summary (what
  it is, one live indicator, one or two big numbers, readable from across the
  room) and is the default only where a section says so (Orchestra's
  Workflow, Run grid and Log, where it is the whole graph, every tile and the
  newest lines). **Settings** opens the Inspector on the right: what the
  panel is and how to use it, the face, strip, float, the exact grid
  position, reset, and the panel's own options.
- **Help where you are.** `?` on a focused panel (or Help in its ... menu)
  opens a small popover with its `about` line and a few lines on how to use
  it; `?` again, `?` away from a panel, the **?** beside the section tabs and
  the palette's **Help: how <section> works** open **How this works** for the
  section: what it is, five to eight numbered steps, every panel with its
  about line, and the keys (the copy is below, in
  [How each section works](STUDIO-sections.md#how-each-section-works)). The first time a
  section shows in a browser the same card comes up as its welcome, with
  **Got it** (`halo.studio.seen.<section>`; `?tour=off` in the URL keeps it
  shut).
- **The rail** (left) has the section's own block (Orchestra and Flow: **New
  run** and the runs), lists the section's panels (click one to bring it back
  and focus it), the **Fleet tree** (3.0.5.0; it replaced the plain list of
  live sessions): every harness, its sessions and their agents with a status
  dot each, the live and need-you counts on top, a click opens Fleet on that
  node, and a session that waits on you keeps its inline answer; then the
  layout actions.
- **The palette** (`Ctrl`/`Cmd`+`K`): a mono prompt with fuzzy matching and
  grouped results (Go to, Help, Orchestra, Roles, Org, Design, Flow, Fleet, Team, Media,
  View, Layout), keyboard first: arrows,
  `Enter`, `Esc`. Every shortcut is shown next to its command.
- **The status bar** shows the live feed (a dot that is green when
  connected, amber while connecting or reconnecting, red when unreachable,
  and ticks once per event), the session count, the fleet (agents at work
  and how many wait on you), the team (3.0.8.0: its stages running now, when
  the repo has a team file), the event count, the section's own status
  line (Roles: the open lineup, its cards and problems, saved or not; Org's company and
  Design's project) and the section's layout
  state. `Esc` closes the palette, a menu or a help card, then the Inspector.

**Visual language.** The dark theme ("holo", the default) is a near-black
navy with glass panels: a translucent surface, a 1 px luminous edge, a soft
glow and small corner brackets (`--bracket-alpha`, 0 turns them off). Cyan is
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
