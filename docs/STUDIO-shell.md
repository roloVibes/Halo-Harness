# Studio: the shell

Read this when you find your way around Studio's header, sections, panels and Start views, or open it on a bio, a lineup or the Team.

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
with the Inspector on its Lineup tab, `team` the Team section. Start here and
the first-visit welcome stay shut on such a page.

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

## The first ten minutes (3.1.1.0)

**Start here.** On a fresh home -- no lineup of your own (only the shipped
lineups or their untouched copies, none active) and no run (no Orchestra run
in Studio's repo, no `halo start` sample under `~/.halo/start/`) -- Studio
opens on a **Start here** card instead of the section's welcome. **Run the
ten-minute start** runs `halo start --yes` as a background job in Studio's
process (`POST /api/start`): the same seven steps as in a terminal (a lineup
copied into your scope as `my-halo-dev-cycle`, the sample repo, one
Orchestra goal with `plan: review`, the plan approved, the lanes, the report
and the coach, where to go next), each listed with its state while the
running one shows its command and its last lines; the outcome names the
lineup, the run and its repo, with buttons into Roles, Team and Fleet.
Closing the card keeps the start running (the palette's **Start: the
ten-minute start** brings it back; **Stop the start** ends it). **Just look
around** dismisses the card for this home (`~/.halo/start/dismissed.json`,
every browser) and the section's welcome comes up instead. It runs on the
model you configured; with none, the card says so and points at `halo init`.
`?tour=off` keeps it shut, like the welcome.

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
names the next section and why, in this order: Roles -> Orchestra -> Flow ->
Team -> Org -> Design -> Fleet (Fleet's points back to Roles); the button
opens it.

**The Glossary.** The **?** beside the section tabs is a menu: **How
<section> works** (also `?`) and **Glossary**, a dialog listing every word
Halo uses (lineup, bio, role, tier, team, member, block, stage, lane, part,
flow, step, mission, gate, claim, hand-off, plan, coach, orchestra run,
fleet, hub, harness, capability), each expandable to its one paragraph. Each
section's How this works card has a **WORDS** row: the glossary words that
section uses, each opening the Glossary on that word. The text is served by
`GET /api/glossary` (`{words: [{word, text}], source}`) from
[GLOSSARY.md](GLOSSARY.md), the same paragraphs `halo explain` prints; the
bundle carries no copy. The palette has **Help: glossary** too.

