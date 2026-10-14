# Halo Studio

`halo studio` opens your lineups and agent bios as an editable graph in the
browser. It is the visual front door to the same files the wizard and the
CLI edit: a lineup is `~/.halo/teams/<name>.yaml` (or `.halo/teams/` in a
project), a bio is `~/.halo/agents/<name>.yaml`, and Studio reads and writes
them through the exact functions `halo teams` and `halo agents` use. Nothing
is a second source of truth.

```sh
halo studio                 # starts a local server, opens the browser in the mode you used last
halo studio --mode roles    # straight into Roles (lineups and bios), --mode org, --mode design
halo studio --no-open       # prints the URL only (SSH, a headless box)
halo studio --port 8765     # a fixed port instead of a free one
halo studio --stop          # stop the Studio running in the background
halo studio --legacy        # the classic page (/legacy/) instead of the shell
```

One Studio per machine (3.0.2.0): while it serves, `~/.halo/studio.json`
holds its pid, port and token (private), and a second `halo studio` reuses
that instance (prints its URL, opens the browser) instead of starting
another. The wizard's **Open Studio (Roles)** and **Open Studio (Org)**
buttons start it detached, so it outlives `halo init`; `halo studio --stop`
ends it. `halo_harness/studio/launch.py` is the small module behind both.

Inside the TUI, `/roles`, `/org` and `/design` open Studio straight into that
mode from the live session; `/studio [roles|org|design|orchestra|flow]` is the long form and
`/studio url` prints the URL without opening a browser. A model running in a
Halo session knows this too: the system prompt names Studio, its three modes
and the command, so "open the GUI for roles" runs `halo studio --mode roles`.

## The shell (3.0.3.0)

`halo studio` opens a React shell with five sections in the top bar:
**Orchestra | Roles | Org | Design | Flow** (`Alt+1`..`Alt+5`, or `?mode=` in
the URL; Flow since 3.0.4.0). Orchestra is the live run console (see [Orchestra](#orchestra-the-run-console)
below), Flow the workflow console (see [Flow](#flow-the-workflow-console));
Roles, Org and Design are the
classic pages described below, framed inside the shell from `/legacy/`, so
everything in them works as before. `halo studio --legacy` opens the classic
page on its own.

- **One header (3.0.4.0).** The framed classic page opens with
  `?embedded=1`: its own logo and Roles / Org / Design buttons are gone (the
  shell's tabs do that), and what is left of its header is a slim one-line
  toolbar (the lineup, company or project, the scope, Validate / Save /
  Apply, Groups, Run view). Its status line ("valid", the active lineup, the
  company, the project) shows in the shell's status bar instead of a second
  footer (the page sends it with `postMessage`, same origin only), its theme
  follows the shell's, and `R` / `O` / `D` inside it switch the shell's
  section. `/legacy/` opened on its own keeps its full header.
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
  [How each section works](#how-each-section-works)). The first time a
  section shows in a browser the same card comes up as its welcome, with
  **Got it** (`halo.studio.seen.<section>`; `?tour=off` in the URL keeps it
  shut, as on the classic page).
- **The rail** (left) has the section's own block (Orchestra and Flow: **New
  run** and the runs), lists the section's panels (click one to bring it back
  and focus it), the live sessions with their status (and an inline answer
  for one that waits on you, 3.0.4.0), and the layout actions.
- **The palette** (`Ctrl`/`Cmd`+`K`): a mono prompt with fuzzy matching and
  grouped results (Go to, View, Layout, Open), keyboard first: arrows,
  `Enter`, `Esc`. Every shortcut is shown next to its command.
- **The status bar** shows the live feed (a dot that is green when
  connected, amber while connecting or reconnecting, red when unreachable,
  and ticks once per event), the session and event counts, the framed
  classic page's status line (Roles, Org, Design) and the section's layout
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

## How each section works

The same copy as Studio's **How this works** card (`ui/src/routes/sectionHelp.ts`
for the steps, `routes/help.ts` and `routes/help-orchestra.ts` for the panels'
about lines and help).

### Orchestra

**What it is.** Several agents write to the same files at once and nothing is
lost: a lead splits your goal into lanes, one worker per lane writes its part
in its own git worktree, and a gate checks the result before it lands.

**How to use it.**

1. **Write the goal**: WHAT YOU WANT, how Halo knows it is done (DONE WHEN)
   and when to give up (STOP WHEN), plus the files the workers share and the
   test the gate runs.
2. **Press Run**. Dry run asks the lead for the split only: nothing is
   claimed or written.
3. **The lead splits it into lanes**. Each lane claims a part of the files;
   one worker per lane builds its part in its own git worktree.
4. **The gate checks DONE WHEN**. The parts merge one at a time, your test
   runs, and a part that fails goes back to its worker (up to the return cap).
5. **Read the report**: every check with a tick or a cross, the finished
   branch and its sha, the tests, the cost and the time.

**Panels.** Goal: what you want, how it is checked and when to give up; then
Run. Workflow: the run's plan: goal, lead, split, one node per lane, merge,
test, gate. Run grid: one tile per lane: writing, in review, waiting or
merged. Live file: the shared file, each lane's claimed part a band in its
colour. Lanes: each worker's timeline on the run's clock, from joined to
merged. Report: the gate's verdict: every check, the finished branch, tests
and cost. Claims: who holds which part of the files right now, and until
when. Log: every claim, merge, gate decision and note, with its time.

### Roles

**What it is.** A lineup says which agent, on which model, plays each role in
your sessions. Studio shows it as cards you can arrange and edit; the files
are `~/.halo/teams/<name>.yaml` and `~/.halo/agents/<name>.yaml`.

**How to use it.**

1. **Pick a lineup** in the toolbar, or start from a shipped one. Each card
   is one assignment: an agent bio in a role, with the model that resolves
   for it.
2. **Read the boxes**: cards sit in boxes by role (Main, Workers, Reviewers,
   Researchers ...). **Groups** in the toolbar hides or shows them.
3. **Move and connect**: drop a card into another box to change its role, or
   onto another card to make it report there.
4. **Add an agent**: drag a bio from the left list onto the canvas, or
   straight into a box.
5. **Edit**: select a card; the right side has Assignment, Agent (the bio),
   Lineup and YAML.
6. **Validate, Save, Apply**: Validate runs the CLI's checks, Save writes the
   YAML to your scope, Apply makes it the lineup new sessions use.

**Panels.** Roles: your lineup as cards, boxed by role: who plays each part,
on which model.

![Roles in the shell: one header, the lineup boxed by role](media/studio-roles.png)

### Org

**What it is.** Your company of agents in Paperclip: an org chart with goals,
issues, heartbeats and budgets. Halo's lineups become its agents.

**How to use it.**

1. **Turn Org mode on**: the toolbar's Org mode button (or `/org on`, `halo
   paperclip on`). Off is the default: nothing runs on a heartbeat.
2. **Get Paperclip running**: without it the canvas offers Install Paperclip
   (Node 24 or newer); once it runs, pick the company in the toolbar.
3. **Read the boxes**: each card is an agent (title, role, adapter, status,
   spend against its budget). A box holds one manager's reports ("<manager>'s
   team", or the agent's `metadata.team`); the top box is **Leadership**.
4. **Change who reports to whom**: drop a card into another box, or onto a
   card; Studio asks first, then updates Paperclip.
5. **Work with an agent**: select a card for Agent (budget, wake, pause),
   Issues, its Paperclip page, and Company (sync a lineup into the company).

**Panels.** Org: your company in Paperclip: agents as cards, boxed by who
they report to.

### Design

**What it is.** Prototypes, pages, decks and logos made by your own apps. A
project is a folder of artboards under `~/.halo/design/<slug>/`, and every
turn saves a new version.

**How to use it.**

1. **Open a project**: make one in the left rail (`N`) or pick one.
2. **Say what to design**: type it in the Chat tab and press Enter: one turn,
   its cost shown as it streams.
3. **Look and compare**: each artboard is a card; drag it by its title,
   switch the device size, slide back through its versions.
4. **Comment**: `C` pins a comment on a frame; Send comments turns the pins
   into one turn. `K` asks a second model to critique.
5. **Tune without a model**: Knobs move spacing, colours and sizes; the
   Contrast table checks text against its background.
6. **Hand it off**: Export writes a folder, HTML, PNG, SVG or PDF; Handoff
   bundles it for a Halo or Claude Code session.
7. **Render pictures**: the palette's Media commands pop the ComfyUI panels
   over the canvas.

**Panels.** Design: prototypes, pages and decks your apps make, one card per
artboard; and from the palette, Media status, Media models, Workflows and
Render (see [Media](#media)).

### Flow

**What it is.** A brief goes through your roles and a marketing org, ComfyUI
renders the Art Director's prompt, you confirm the picture, then the posts go
out and their metrics come back, all in one design project.

**How to use it.**

1. **Write a brief** on the Start view: the brief, the platforms, the budget
   and the design project; drop assets if you have them.
2. **Press Run**: Run waits for your OK on the render, Run with --yes accepts
   every gate, Dry run keeps the posts dry.
3. **The roles and the org work**: a planner and a researcher plan it; a
   strategist, a copywriter and an art director write the campaign and the
   image prompt.
4. **Confirm the render**: ComfyUI renders it; the run waits in Renders until
   you Confirm, Redo with an instruction, or Stop.
5. **Posts and metrics**: one post per platform through Postiz (dry runs
   unless the flow says `live: true`); Metrics samples how they do.
6. **Read the report**: Report sums it up; New run in the rail goes back to
   the Start view.

**Panels.** Intake, Workflow, Renders, Step, Posts, Metrics, Log, Report and
the four Media panels; what each shows is in the [Flow](#flow-the-workflow-console)
table below.

## The live feed

`GET /api/events?t=<token>&sessions=all|<session id>` is a Server-Sent
Events stream. Studio watches the live-session registry
(`~/.halo/run/sessions.json`) every 2 s and attaches to each running
session's control socket (`subscribe`, 1 s timeouts, off the request
threads); every frame is `{session_id, event, data, turn, agent_id, ts}`
under `event: <kind>`, a `sessions` frame lists the attached sessions (title,
mode, kind, cwd, started, pid; never an endpoint or token) whenever one
attaches or detaches, and `: ping` keeps the stream open every 15 s. Each
browser gets its own queue of 512 frames (the oldest dropped first). The
shell's status bar, the Orchestra panels and the rail read it. Studio's own
Orchestra runner publishes its run log here too (`orchestra_*` frames).

## Orchestra: the run console

`Alt+1` (or `?mode=orchestra`) is the console for [Orchestra](ORCHESTRA.md)
runs in the git repo that holds Studio's folder (`halo studio` started
there, or `--cwd`). It opens on the newest run.

**Before a run (3.0.4.0)** the section is one centered **Start** view, not
eight empty panels: the goal form (WHAT YOU WANT, DONE WHEN, STOP WHEN with
examples, the files and the test command, the budget: workers and return
cap, the lineup, and who plays the parts and the model under a disclosure)
with **Run** and **Dry run**, what a run does in five numbered steps, and the
past runs to open. Starting or opening a run brings up the panels; **open the
workspace anyway** does too. **New run** (the rail, or the palette's
**Orchestra: new run**) returns to the Start view. An Orchestra goal has no
dollar budget: its budget is how many workers and how many times the gate may
send a part back.

![Orchestra before a run: the Start view](media/studio-orchestra-start.png)

Its eight panels sit on the same movable workspace as everything else, each
on its full face with its one-line about and its `?` help (Workflow, Run grid
and Log open on their compact face, which shows the whole graph, every tile
and the newest lines at the default size). The Goal panel's default height
shows every field and **Run** without scrolling. The rail lists the runs of
the repo (click one to open it).

![Orchestra: a finished five-lane run over basket.py](media/studio-orchestra.png)

| Panel | Compact face | Full face | Motion |
|---|---|---|---|
| **Goal** | WHAT YOU WANT / DONE WHEN / STOP WHEN as a card, the workers, the cost, the run state badge | the open run in one line (state, cost, **stop** while it runs, **new run**) over its goal form (as on the Start view) with **Run** and **Dry run** | the badge follows the run: flowing while it runs, a green sweep when it finishes, red when it stops, amber when it was interrupted |
| **Workflow** | steps finished, the running step, the graph | the graph and the step list | the designed graph laid out in SVG: goal, lead, split, one node per lane, merge, test, the gate diamond, done; pending steps are faint, the running step's outline flows, the diamond lights when the gate acts, a failed step is red, and the gate's return arrow turns amber once a piece has been sent back |
| **Run grid** | the counters (joined, writing, in review, waiting, merged) and one tile per lane, 5 to 50 | larger tiles with each lane's title | a tile that is writing flows, a waiting one pulses amber, a merged one turns green; click a tile to focus that lane in Lanes and Live file |
| **Lanes** | joined, writing, merged, one strip per lane | the timeline: one trace per worker on the run's clock from "joined" to "merged", a node at each state change, a diamond where the gate sent the piece back; hover a node for its time and text | the running lane's trace flows, a waiting lane pulses amber |
| **Live file** | units being written, units merged, a minimap of the bands | the goal file in mono with each lane's claimed unit as a band in its lane colour, labelled claimed, writing, written or merged, holding the lane's current text (its worktree copy); a picker when the goal has several files | a band being written shimmers; a claimed band is hatched |
| **Report** | checks passing, cost, one pip per check | the checks with ticks and crosses, the finished branch and sha, the tests, the cost and time; **Copy** puts the report text (as `halo orchestra report` prints it) on the clipboard; a dry run shows the lead's jobs here | one green sweep when the report lands |
| **Log** | line count, the last lines | the run log with each line's elapsed time, a lane filter, kind filters and **follow** | new lines slide in |
| **Claims** | live claims, writing, the lead | each live claim with its holder, state and expiry, with **Release** and **Steal** (the lead takes the unit) | a claim being written flows; one that expires within a minute pulses amber |

The lanes take their colours from a ten-step ramp mixed from the theme's
accent, accent-2, ok and text tokens. Amber and red are never used for a
lane, because they mean "needs you" and "failed". Settings: Lanes shows
times as elapsed (`+12.5s`) or clock (`14:02:09`); Live file picks the file
and can fold every unclaimed line; Log keeps its filters; Workflow can
label the worker lanes; Goal switches the open run. These options are kept
in your browser (`halo.studio.orchestra.opts`).

The panels update from the live feed. A run started here publishes every
state, claim, merge, gate and report line as an `orchestra_*` event (the
session id is `orchestra:<run id>`). A line for the open run refreshes the
panels within a quarter second; a claim or merge refetches the file view.
When the feed is not connected and a run is live, the panels poll every
5 s instead. Palette commands (`Ctrl`/`Cmd`+`K`): **Orchestra: new run**
(the Start view), **stop run**, **open run <id>** and **focus lane N**.

One run goes at a time. **Run** is disabled while a run is live, and
**stop** (the Goal panel's run line, or its compact face) asks the runner to
stop at its next step. Routes:
[ORCHESTRA.md, "In Studio"](ORCHESTRA.md#in-studio).

## Flow: the workflow console

`Alt+5` (or `?mode=flow`, `halo studio --mode flow`, `/studio flow`) is the
console for [flows](FLOWS.md): a brief goes through your roles and a
marketing org, ComfyUI renders the Art Director's prompt, you confirm the
picture, then the posts go out (dry runs unless the flow says `live:
true`) and their metrics come back, all in one design project.

![Flow: a run waiting at its confirm gate, the render inline](media/studio-flow.png)

**Before a run is open** the section is one centered **Start** view, not a
grid of empty panels: the intake form (the flow, the model, the brief, the
platforms to post on, the budget, the design project, a drop zone for
assets, the render overrides under a disclosure), what a flow does in six
numbered steps, whether ComfyUI answers, and the past runs to open.
**Run** waits for your OK on the render, **Run with --yes** accepts every
gate, **Dry run** goes through every step but keeps the posts dry. Files
dropped on the form make the run without starting it, upload each file
into the project's `assets/`, then resume it. Starting or opening a run
brings up the panels; **open the workspace anyway** does too. **New run**
(the rail, or the palette's **Flow: new run**) returns to the Start view.

**The panels.** Every Flow and Media panel opens on its full face (the
compact face is the summary a strip keeps); its one-line `about` shows in
the title bar and its few lines of `help` behind `?`.

| Panel | What it shows | Motion |
|---|---|---|
| **Intake** | the open run in one line (state, steps done, cost against the budget, **copy its brief**) over the intake form, sized so Run is always in view | the run's state: flowing while it runs, amber while it waits on you, a green sweep when it finishes, red when it stops |
| **Workflow** | steps done and what runs now (or **WAITING ON YOU**), the steps as nodes in order, the org step's positions as a sub-row, the last log line | pending nodes are faint, the running one's outline flows, done is green, failed red; a `confirm` step is a diamond (`gate-diamond`) that lights amber while it waits on you; the dashed redo arrow runs back to the render and turns amber once a render was sent back |
| **Renders** | the gate card while the confirm gate is open (the prompt, **Confirm**, an instruction field with **Redo**, **Stop**), the Art Director's prompt, every artboard inline (an image, or a video with controls) with its version badges | amber while the gate waits; after the answer a band says **ACCEPTED** (or sent back, or stopped) |
| **Step** | the selected step (click a node; by default the one waiting on you, else the running one, else the last done): cost, elapsed, rounds, the error, and its output -- per role for a roles step, per position for the org with the Art Director's prompt marked, the render's prompt and settings; the org's live positions from the run session's `subagent_*` frames; an org approval waiting on you is answered here | the step's state |
| **Posts** | one row per post: the platform, a grey **DRY RUN** or red **LIVE** badge, the text, the media count, the Postiz post id, the scheduled time, a failure's reason | flowing while the publish step runs |
| **Metrics** | per post and platform the latest views, likes, comments and shares, with a sparkline over the run's metrics tail; a dry run says "dry run: no metrics yet" | flowing while the measure step runs |
| **Log** | the run's `events.jsonl` with each line's elapsed time (or the clock), a step filter, kind filters and **follow** | new lines slide in |
| **Report** | the status, the cost against the budget, the steps table, the artboards, the posts and the metrics summary; **Copy** puts the text `halo flow report` prints on the clipboard | one green sweep when the report lands |

**The gate.** A `confirm` step (and an org position marked
`requires_approval`) waits for an answer file; Studio's Confirm / Redo /
Stop posts it through `flow/runs/<id>/answer`, the same file `halo flow
answer` writes, so a gate opened by a CLI run can be answered here and the
other way round. The palette offers **Flow: answer gate: accept**,
**redo...** (opens the gate card for the instruction) and **stop** while a
gate is open.

**The rail** shows **New run**, the runs (newest first; one that waits on
you pulses amber) and the flows a run can start from (click one to load it
into the Start view's form), above the panel list. The live sessions in the
rail carry their status (`waiting`, `busy`, `idle`); a session that waits on
you gets an inline **answer**: an org approval card takes Accept, an
instruction (Send) or Stop, a permission card Allow once or Deny, a plan
Approve or Send back, all through `sessions/<sid>/command`.

The panels refetch the open run within a quarter second of each `flow_*`
frame for it; when the feed is not connected and the run is live they poll
every 5 s. Palette (`Ctrl`/`Cmd`+`K`): **Flow: new run**, **open run
<id>**, **answer gate**, **stop run**, **resume run**. The panels' options
(log filters, times, the intake defaults) are kept in your browser
(`halo.studio.flow.opts`).

## Media

The ComfyUI panels. In Flow they sit as four strips along the bottom (open
one with its chevron); in Design the palette (**Media: status**, **scan**,
**models**, **quick render**) pops them out over the canvas, and the
Inspector's **Remove from Design** takes one away again.

![Media: ComfyUI status, models, workflows and a render](media/studio-media.png)

| Panel | What it shows |
|---|---|
| **Media status** | a dot that ticks green on every check (every 15 s while a Media panel is open), the ComfyUI version, the GPU's VRAM bar, the model count and the cache's age, **Scan** (reads the server's model folders and saved workflows into the cache) |
| **Media models** | tabs image / video / audio / upscale; each row is a file with its family, precision and size (and a note: a 4-step LoRA, the high- or low-noise expert); encoders, LoRAs and VAEs of the same families sit under **supporting files** |
| **Workflows** | Halo's starters and the workflows saved on the server; click one for the inputs a render can set (`*` marks a named input) |
| **Render** | the workflow, its named inputs (prompt, negative, size, seed, steps) and every node input under a disclosure, the design project and the artboard; **Render** queues it (`202`), the `media_render` frames show its progress, and the result shows inline (it is also an artboard in Design; a render over an existing artboard is its next version) |

While ComfyUI does not answer, the group is one card instead of four
panels: where Studio looked, the error, and the fix (start ComfyUI, then
`halo media init --url <its address>` or `COMFY_URL`, then **Check
again**). The models tab is remembered in your browser
(`halo.studio.media.tab`).

## Flow and Media routes (3.0.4.0)

The JSON routes behind the Flow and Media panels. Every one sits behind the
same loopback, Host, Origin and bearer-token guard as the rest of `/api/`.
Flow runs are `~/.halo/flows/runs/<id>/` ([FLOWS.md](FLOWS.md)); renders go
to ComfyUI at `COMFY_URL`, the config's `comfy.url`, or
`http://127.0.0.1:8188` ([COMFYUI.md](COMFYUI.md)).

| Route | Answer |
|---|---|
| `GET flow/templates` | `[{name, source: template\|user\|project, steps: [{id, kind}], form, budget_usd, version, path}]` |
| `GET flow/runs` | `[{run, name, status, created, cost_usd, project, budget_usd, live, waiting_step?}]`, newest first |
| `POST flow/runs {template, intake: {brief, platforms, budget_usd, project}, model?, set?, yes?, start?}` | `201 {run, started, warnings}`; 422 with the validator's lines; 409 naming the live run. `set` is `{"render.width": 64}` or `{"render": {"width": 64}}`; `start: false` makes the run without starting it |
| `GET flow/runs/<id>` | `{flow, steps, gate, report, posts, metrics_tail, artboards: [{id, kind, step, url, version, versions, file}], events, live, project}` |
| `GET flow/runs/<id>/events?since=N` | `{events, next}` |
| `POST flow/runs/<id>/assets {name, data_base64}` | `201 {name, size, kind, path, rel, project, intake}` into the project's `assets/` (15 MB); a run not started yet also gets the file in its intake |
| `POST flow/runs/<id>/stop {reason?}` / `resume {model?, yes?}` | `{ok, live}` / `{run, started}`; resuming a finished run is a 409 |
| `POST flow/runs/<id>/answer {step, action: accept\|redo\|stop, instruction?, round?}` | `{ok, message, gate}`; 422 when no gate is open at that step or the round is stale |
| `GET flow/runs/<id>/report` / `posts?all=1` / `metrics?limit=N` | report.json (404 until it exists) / `{posts}` / `{metrics}` |
| `GET media/status` | `{url, reachable, version, python, pytorch, gpus, registered, cache: {scanned, age_s, rows, workflows}, checked, age_s, checking}` |
| `GET media/models?kind=image-gen\|video-gen\|audio-gen\|upscale\|all` | `{kind, rows, scanned, url}` from the cached inventory |
| `POST media/scan` | `{rows, workflows, scanned, url}`: reads the server into the cache |
| `GET media/workflows` | `{workflows: [{name, source: starter\|saved}], reachable, url}` (the cache's names when the server is down) |
| `GET media/workflows/<name>/inputs?source=starter\|saved` | `{workflow, source, label, nodes}`: each node's settable inputs |
| `POST media/render {workflow, set, project, artboard}` | `202 {prompt_id, project, artboard, workflow, source}`; the render goes on in the background |
| `GET media/renders/<prompt id>` | the render's last state |

A run started from Studio runs on a background thread with the real
adapters. Its log reaches the live feed as `flow_state`, `flow_step`,
`flow_gate`, `flow_post`, `flow_metric` and `flow_report` frames
(`session_id: "flow:<run id>"`, data = the log line plus `run`). One flow
run is live per Studio at a time. A render publishes `media_render` frames
(`session_id: "media:<prompt id>"`, data `{prompt_id, state:
queued|progress|done|error, text, project, artboard, workflow, artboards?,
error?}`) and saves each output as an artboard of the design project. A
render over an existing artboard becomes that artboard's next version.
`media/status` refreshes in the background every 15 s and never holds a
request for more than 2 s. An artboard's `url` is a `/design-files/` path.
A `.mp4` is served as `video/mp4` with no sandbox directive.

## What you see (Roles)

- **The lock on a card** (`🔒 shipped`) is a badge, not a switch: the agent
  bio behind that slot ships with Halo and is read-only. Click it (or open
  the Agent tab) and press **Duplicate** to get an editable copy in your
  scope, which then shadows the shipped one. A card without the lock is
  yours already.
- **The rail (left):** every lineup you can reach (shipped, user, project; the
  active one marked), and every agent bio. Drag a bio onto the canvas to add
  an assignment to the open lineup.
- **The group boxes (3.0.4.0):** behind the cards, one labelled rounded box
  per role in the lineup (Main, Workers, Researchers, Reviewers, Judges,
  Custom roles ...; "Agents" for a card without one), tinted with that role's
  band colour, the label and the count on a strip at its top. Drag the strip
  to move the whole group; drop a card into another box and it takes that
  role (Main stays one card); drop a bio from the rail into a box and it is
  added in that role. `A` lays the groups out in rows (Main on top); a layout
  saved before the boxes existed is laid out once when the boxes would
  overlap. **Groups** in the toolbar hides them (`localStorage`
  `halo-studio-groups`); without them `A` is the layered layout again.
  Positions are kept in the same layout files as before.
- **The model dropdowns (3.0.4.0):** every model field (the bio form's
  preferred / fallback / escalation model, an assignment's override) is a
  dropdown over the whole catalog, grouped by route and vendor with price,
  context and capability chips, behind a filter box; "Type a ref..." takes
  a model the catalog lacks. Under it a line says how many models the
  catalog holds with a **refresh** link. When it holds none the line becomes
  a notice that says why, per provider (not set up, detected but not
  enabled, enabled but nothing cached yet) and a **Refresh models** button
  that pulls every enabled provider's catalog in place and redraws every
  dropdown on the page (`GET /api/models/status`, `POST /api/models/refresh`).
  The catalog is the same one `halo models` prints: a provider lists its
  models once it is enabled (`halo providers enable <name>` with its key in
  the environment, or the wizard's keys step).
- **The canvas:** one card per assignment -- the agent name, its role and
  alias, the model that resolves for it with price and context from the
  catalog, its tool count, a scope badge and a status dot (green valid, amber
  a warning, red a problem; hover reads the text). Edges are **delegation**
  from `main` (labelled with the routing keys that reach a member), **reports
  to** lines from the org section (dashed) and **pipeline** stage order
  (dotted). Pan by dragging, zoom with the wheel, `Shift`-drag to marquee-
  select, `A` lays the graph out again, `F` fits it. Positions are remembered
  per lineup under `~/.halo/studio/layouts/` (an Org company's layout is
  `_pc-<company id>.json` there, a name every file system accepts).
- **The inspector (right):** *Assignment* (agent, role, alias, instances,
  `use_for`, a per-assignment model override), *Agent* (the bio behind the
  card: every section as typed fields, with the "about N turns at this
  price" hint next to the budget), *Lineup* (description, about, and each
  top section -- delegation, routing, budget, escalation, context,
  permissions, org, pipeline, acceptance -- as a YAML body with its
  enforcement badge), *YAML* (the whole file as it will be written; edits go
  both ways).
- **The command palette:** `Ctrl`/`Cmd`+`K` lists every action and every
  lineup and bio; `?` replays the tour.
- **Run view:** overlays the newest session's sub-agents on the cards (which
  node is running, cost so far) and a timeline strip of them. Read-only.

## Org mode: the company in Paperclip

**Off by default.** The header's **Org mode: off/on** button is the switch
(`paperclip.enabled`; also `halo paperclip on|off` and `/org on|off`). While
it is off the canvas explains who orchestrates what (your session in Roles,
Paperclip's heartbeats in Org) and nothing runs on a heartbeat; on, the
company's Halo agents resume. See [PAPERCLIP.md](PAPERCLIP.md).

The **Roles | Org** toggle in the top bar (`R` / `O`) swaps the canvas to
your company in [Paperclip](PAPERCLIP.md). Agents are cards (title, role,
adapter, status, spend against budget), reporting lines are the edges, and
dragging a card onto another makes it report there (a confirm, then a
`PATCH` of the agent's `reportsTo`). The cards sit in labelled boxes (3.0.4.0),
one per manager's reports ("CEO's team", or the agent's `metadata.team`),
the top level in **Leadership**; dropping a card into a box makes it report
to that box's manager (into Leadership: to nobody), after the same confirm.
The rail lists the agents and the
company's goals and projects; the inspector has **Agent** (title, role,
reports-to, budget; Wake, Pause / Resume, Terminate; the adapter it runs),
**Issues** (the agent's issues, or all of them; create one, which wakes
its assignee), **Paperclip** (the agent's own Paperclip page embedded, with
"open" for a full tab) and **Company** (stats, **Sync lineup -> company**,
**Pull reporting lines -> lineup**, "Open Paperclip").

Studio talks to Paperclip through its own server (`/api/pc/...`), which adds
the board token from `~/.halo/paperclip.json` server-side; the page never
holds it. When Paperclip is not installed the Org canvas explains it and
offers **Install Paperclip** with the install log streamed into the page
(Node 24+ required); when it is installed but not running it says how to
start it.

![The Org section: the halo-dev-cycle lineup as a Paperclip company](media/studio-org.png)

## Design mode: prototypes, pages and decks on your own apps

The third button in the top bar, `Roles | Org | Design` (keys `R` / `O` / `D`,
or `?mode=design`; the choice is remembered). It is the page for `halo design`
projects under `~/.halo/design/<slug>/`.

![Design mode: the Launch page project](media/studio-design.png)

**What you see.** The left rail lists projects (with a New project form that
opens its model picker on the design ranking, capability chips included), the
open project's artboards (id, kind, app, latest version) and its design system
(token groups with counts, plus a "Sync from..." box that takes a folder path
or a URL). The canvas is a dot-grid of frame cards: title row (title, kind,
app, `v<n>`), the frame itself (a sandboxed iframe for an HTML artboard, an
image for a `render.png` / `render.svg`, a link card for a PDF or MP4), a
device select (phone 390, tablet 820, desktop 1280 wide; the frame scales to
fit the card) and a version slider. Drag a card by its title row; positions
are kept in your browser per project. Pan with space-drag, the middle button
or a drag on the empty background; zoom with `Ctrl`+wheel; `F` fits.

**The panel** replaces the inspector tabs: Chat, Comments, Knobs, System,
Export.

- **Chat**: the prompt box (`Enter` sends, `Shift+Enter` adds a line), a model
  override and a budget, the turn's events as they stream (assistant text,
  compact tool cards, the result with its cost), the project's running cost and
  the history. One turn runs per project at a time; the page polls the turn
  every 500 ms.
- **Comments**: press `C` (the Comment tool) and click a frame to pin a note
  (the position is kept as a percentage of the frame). Open pins are grouped by
  artboard with Resolve; **Send comments** turns every open pin into one prompt
  ("Address these comments: ...") and runs a turn, then resolves them when it
  succeeds.
- **Knobs**: the artboard's `controls.json` as sliders, colour inputs and
  selects. A `css:--name` knob rewrites that variable in the page's `:root`
  block in place, with no model call, and makes a new version; a `craft:` knob
  is saved and applied by the next turn. Ask for knobs in a turn: "add knobs for
  spacing and the accent colour".
- **System**: the design system's tokens by group, editable, saved with Save
  tokens; sources and components below.
- **Export**: folder, HTML, PNG, SVG or PDF (optionally for one artboard) with
  the returned lines, and **Handoff bundle**, which shows the bundle's path
  with a Copy button.

**Direct text edits.** "Edit text" on an HTML card reloads the frame with
`?edit=1`: the page becomes editable, and `Ctrl+S` or leaving the text posts
the page back to Studio, which saves it as a new version ("direct edit"). The
helper script is wrapped in `<!--halo-edit-->` markers and never reaches the
saved file.

**Versions.** Every turn, knob move, direct edit and restore is a version.
The slider under a card swaps the frame to `v<n>/...`; at an older version,
**Restore this version** makes it the newest one.

**The raw file route and its sandbox.** Artboard files are served at
`GET /design-files/<slug>/<artboard>/<file>` (and `.../v<n>/<file>`), loopback
only and confined to that artboard's folder (`..` is a 404). They carry their
own `Content-Security-Policy: default-src 'self' 'unsafe-inline' data: blob:`
and `nosniff`, not Studio's, because a prototype has inline CSS and JS. HTML
and SVG responses add `; sandbox allow-scripts` to that policy, so the
document gets an opaque origin even when it is framed without a sandbox
attribute or opened on its own; renders (PNG, PDF, MP4) keep the plain policy.
The page embeds them as `<iframe sandbox="allow-scripts">` without
`allow-same-origin`, so a prototype runs but cannot reach Studio's API or its
token. An artboard folder that is a symlink is never served.

**Plus more.**

- **Explore directions**: the **3 directions** button beside Run turn (or `V`)
  wraps the prompt as "Make 3 directions of: ..." with artboards named
  `<name>-a`, `-b`, `-c` (the name box beside the button, the selected artboard
  by default). It is one turn; afterwards the canvas tiles the new artboards
  side by side and selects the first. `POST design/<slug>/run` takes
  `{"variants": N, "base": "<id>"}`, and the CLI takes `--variants N --base ID`.
- **Critique**: **Critique <artboard>** (or `K`) starts a read-only turn (Read
  and Glob, no MCP servers) where a second model, the project's or the one picked,
  reviews the artboard. Its notes land as comment pins with a `critique` badge and
  a `[high]` / `[medium]` / `[low]` prefix; Send comments includes them.
  `POST design/<slug>/critique {artboard, model?}`.
- **Contrast**: the Knobs tab ends with a table of text-on-background pairs with
  ratio and AA / AAA verdicts (failing pairs first, red / amber / green dots),
  refreshed after every knob move. `GET design/<slug>/artboard/<id>/contrast`.
- **Assets**: the rail's Assets list (name, size, thumbnail) with a drop zone.
  Drop files from the desktop onto the rail or the canvas to upload them; the
  Chat box gets "Use assets/<name> ...". An image dropped on a frame card adds
  "Place assets/<name> on <artboard>". Click an asset to insert its path.
  `GET` / `POST design/<slug>/assets`, 15 MB at most.
- **Run view**: History shows "12 tool calls · 48 s · $0.03" per turn.

![The Design section: a hero prototype and a logo mark as artboards](media/studio-design.png)

| Key | Action (Design mode) |
|---|---|
| `D` / `R` / `O` | switch mode |
| `N` | new project |
| `Enter` in the Chat box | run the turn |
| `C` | toggle the comment tool (`Esc` returns to select) |
| `V` | explore 3 directions of the Chat prompt |
| `K` | critique the selected artboard |
| `X` | check contrast (opens Knobs) |
| `S` | send comments |
| `Y` | sync the design system |
| `U` | add assets |
| `E` / `H` | export folder / handoff bundle |
| `F` | fit the canvas |
| `Ctrl`+wheel, space-drag | zoom, pan |
| `Ctrl`/`Cmd`+`K` | the palette lists every Design command with its key |

Shortcuts are inactive while you type in a box. The tour (`?`) shows five Design
steps when the page is in Design mode.

## Connecting boxes (3.0.2.0)

Every member hangs off the starting box (the `main` assignment) until you
connect it elsewhere. Two ways, both writing the lineup's own
`org.positions[].reports_to` (a title is the assignment's alias, else its
role, else its agent):

- **Drag a card onto another card.** The dragged member now reports to
  the card you dropped it on, and its edge moves there; drop it on the
  starting box to hang it off main again. (Dropped into a group box
  instead, away from any card, it joins that box: in Roles it takes the
  box's role, in Org it reports to the box's manager.)
- **The Reports-to field** in the Assignment tab: pick any other box, or
  blank for the starting box.

The canvas redraws the tree as you connect (a member that reports to
another member no longer gets the main -> member delegation edge), Save
writes it like any other change, and `halo teams show` prints the same
org positions. Runtime: `reports_to` addresses the member's one-line
completion report (docs/AGENTS.md, "org").

## Validate, save, apply

**Validate** runs `teams_yaml.validate_team_template` (the CLI's own checks)
and redraws the graph. **Save** validates, then writes the YAML to your user
scope (or the project, with the scope toggle in the top bar). A shipped
lineup or bio is never edited in place: saving it writes a copy under the
same name into your scope, which then shadows the shipped one -- exactly
what the wizard's Duplicate does. **Apply** shows the role table it will
write and, on confirm, does what `halo teams use <name>` does: `roles.*`
and `team:` in `~/.halo/config.json`, with custom roles switched on.

Errors are the validator's own lines, shown under the field they name and
in the Lineup tab; a save that fails leaves the file untouched.

## Security model

- The server binds `127.0.0.1` only and refuses any request from a non-
  loopback peer.
- Every API call carries a per-launch token (the `#t=` fragment in the URL
  `halo studio` prints; the page keeps it in session storage and sends it as
  a bearer header). A request without it is a 401.
- A request carrying an `Origin` header that is not this server's own is a
  403, so a page on another site cannot drive Studio even with the port.
- **One exception to the bearer header: `/api/events`.** A browser's
  `EventSource` cannot send headers, so the live feed takes the same
  per-launch token in the query (`?t=`), compared in constant time; a
  missing or wrong token is a 403, and the loopback, Host and Origin checks
  are the same as for every other call. The token never leaves the machine
  and the response is `Cache-Control: no-store`.
- **The sessions routes (3.0.4.0).** `GET /api/sessions` lists the live
  sessions in `~/.halo/run/sessions.json`: `[{session_id, title, cwd, mode,
  kind, started, pid, status: idle|busy|waiting|unknown, busy, pending,
  model, status_age_s}]`. The status comes from each session's control
  socket (1 s timeouts, asked side by side, cached 2 s; the request waits
  at most 1.5 s). The endpoint and token are never returned. `POST
  /api/sessions/<sid>/command {cmd: answer|interrupt|steer|submit, kind?,
  request_id?, action?, instruction?, text?}` forwards one control-protocol
  request ([REMOTE.md](REMOTE.md)) to that session over its socket, using
  the token from the registry. That lets Studio answer a permission,
  question, plan or org approval card in a running TUI session, steer it,
  send it a prompt or interrupt it. The answers: `{ok, result}`, 404 for a
  session not in the registry, 422 for another `cmd`, and 502 with the
  socket's own error text (for example "no pending approval request"). It
  sits behind the same bearer-token guard as every other route, so only the
  page `halo studio` opened can use it.
- **The agent routes (3.0.5.0 Fleet, `studio/fleet_api.py`).** The session
  rows also carry `harness`, `project`, `parent` and `agents` (how many
  sub-agents are working right now; the rail shows it), and a private
  session is never listed. `GET /api/sessions/<sid>/agents` is the
  session's agent tree, `GET /api/sessions/<sid>/agents/<aid>/tail?n=&kinds=`
  one agent's last entries, `POST /api/sessions/<sid>/agents/<aid>/command
  {cmd: steer|stop|pause|resume|follow, text?, mode?, reason?, on?}` acts
  on one agent, and `POST /api/sessions/<sid>/command` also takes `shutdown`
  (`reason`), `pause` and `resume` (optional `agent_id`). Studio sends `by`
  = `fleet.name` and `via` = `Studio`. The live feed passes `agent_state`,
  `agent_event` and `fleet` frames with each frame's `harness`. Shapes and
  rules: [REMOTE.md](REMOTE.md#agent-level-commands-3050-fleet),
  [SUBAGENTS.md](SUBAGENTS.md), [FLEET.md](FLEET.md).
- **The fleet routes (3.0.5.0 R2, `studio/fleet_hub_api.py`).** `halo studio
  --fleet` (or `halo fleet serve` while Studio runs) starts the fleet hub
  inside Studio's process, on its own LAN port that serves only the fleet
  protocol; this API stays on loopback. `GET /api/fleet` is every harness
  (this one first, then each member of the hub) with its sessions and agent
  trees; `POST /api/fleet/<harness>/<sid>/command` and `POST
  /api/fleet/<harness>/<sid>/agents/<aid>/command` act on this harness
  directly and on a member through the hub, as that member's owner allows
  (200, 202 `asked`, 403 refused with the reason); `GET
  /api/fleet/commands/<id>` and `POST /api/fleet/hub {action: start|stop}`.
  Member frames reach the live feed with their `harness`. See
  [FLEET.md](FLEET.md#studio-get-apifleet-and-the-commands).
- No CDN, no fonts fetched, no analytics: the page is a handful of static
  files served from the package, under a strict content-security policy.
  The shell (`static/dist/`) gets `default-src 'self'; connect-src 'self'`
  with no inline styles or scripts; the classic page (`static/legacy/`)
  keeps its `style-src 'unsafe-inline'`. The built bundle contains no
  `http://` or `https://` URL at all (a CI test checks).
- Writes go only to `~/.halo` (and a project's `.halo/` when you choose that
  scope); shipped files under the package are never written or deleted.

## Over SSH

On a box you reach over SSH (the usual Kali case), run `halo studio
--no-open` there, then on your machine:

```sh
ssh -L 48761:127.0.0.1:48761 <host>
```

using the port Studio printed, and open the printed URL (token included)
in your own browser.

## Shortcuts

| Key | Action |
|---|---|
| `Ctrl`/`Cmd`+`K` | command palette |
| `Ctrl`/`Cmd`+`S` | save |
| `Ctrl`/`Cmd`+`Enter` | validate |
| `Ctrl`/`Cmd`+`N` | new lineup |
| `A` / `F` | auto-layout / fit |
| `Del` | remove the selected assignment |
| `[` / `]` | hide the rail / the inspector |
| `?` | the tour |

These keys belong to the classic page (in the shell: once you clicked into
it). The shell's own keys: `Alt+1`..`Alt+5` sections, `Ctrl`/`Cmd`+`K` the
palette, `?` the focused panel's help (again, or away from a panel: How this
works), `Alt`+arrows / `Alt+Shift`+arrows move / resize the focused panel,
`Esc` closes.

## Files

`halo_harness/studio/server.py` (the server, the guard, the command),
`events.py` (the live feed: the registry watcher and `/api/events`),
`ui/` (the React shell's sources; see docs/DEVELOPMENT.md "Studio UI"),
`static/dist/` (its committed build), `static/legacy/` (the classic page),
`api.py` (the routes), `flow_api.py` / `flow_model.py` / `flow_runs.py` (the Flow
routes and the one live flow run), `media_api.py` / `media_render.py` (the ComfyUI
routes and a render's background thread), `sessions_api.py` (the live sessions and
their commands), `design_api.py` / `design_api_io.py` / `design_api_turns.py` / `design_files.py` (Design mode), `model.py` (the graph, the catalog rows, the session
reader). Tests: `tests/test_studio_api.py`,
`tests/test_studio_model.py`, `tests/test_studio_dist.py` (the build and
its routes), `tests/test_studio_live.py` (the live feed),
`tests/test_studio_flow_api.py` and `tests/test_studio_media_sessions.py` (the 3.0.4.0 routes),
`tests/test_studio_ui.py` (headless Chrome over both pages; the Flow section
through `tools/capture_studio.py --mode flow --dom`, the Orchestra Start
view and grid through `--mode orchestra --dom` (tools/capture_orchestra.py),
and clicks and keys through `tests/helpers/studio_clarity.py` over the
DevTools protocol, `tests/helpers/cdp.py`). The Flow and Media
panels are `ui/src/routes/flow/` and `ui/src/routes/media/`; the Orchestra
Start view `ui/src/routes/orchestra/Start.tsx`; the help copy
`ui/src/routes/sectionHelp.ts`, `help.ts` and `help-orchestra.ts`. The
classic page's group boxes are `static/legacy/groups.js` (+ `groups.css`),
its embedded mode `embed.js` (+ `embed.css`).
