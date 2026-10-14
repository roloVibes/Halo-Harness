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

- **A movable workspace.** Every section is a set of panels on a 24-column
  grid (8 px rows). Drag a panel's title bar to move it, an edge or corner to
  resize it; the others make room and everything snaps to the grid. Each
  title bar has **Expand / Glance**, **Collapse** (to a one-line strip),
  **Pop out** (float over the grid; dock it back the same way) and a **gear**.
  With a panel focused, `Alt`+arrows move it and `Alt+Shift`+arrows resize
  it. The arrangement is remembered per section in your browser
  (`localStorage` key `halo.studio.layout.<section>`); **Reset layout** (the
  rail, or the palette) returns to the defaults, which follow the window size
  until you rearrange something.
- **Three depths per panel.** The **Glance** face says what the panel is,
  shows one live indicator and one or two big numbers, readable from across
  the room; **Expand** shows the details; the **gear** opens the Inspector on
  the right with that panel's settings (face, strip, float, exact grid
  position, reset, and the panel's own options).
- **The rail** (left) lists the section's panels (click one to bring it back
  and focus it), the live sessions with their status (and an inline answer
  for one that waits on you, 3.0.4.0), and the layout actions.
- **The palette** (`Ctrl`/`Cmd`+`K`): a mono prompt with fuzzy matching and
  grouped results (Go to, View, Layout, Open), keyboard first: arrows,
  `Enter`, `Esc`. Every shortcut is shown next to its command.
- **The status bar** shows the live feed (a dot that is green when
  connected, amber while connecting or reconnecting, red when unreachable,
  and ticks once per event), the session and event counts and the section's
  layout state. `Esc` closes the palette, then the Inspector.

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
there, or `--cwd`). It opens on the newest run. Its eight panels sit on the
same movable workspace as everything else. Each panel has a **Glance** face
(what it is, one live indicator, one or two big numbers), an **Expand** face
(the details) and the **gear**, which opens the panel's options in the
Inspector.

![Orchestra: a finished five-lane run over basket.py](media/studio-orchestra.png)

| Panel | Glance | Expand | Motion |
|---|---|---|---|
| **Goal** | WHAT YOU WANT / DONE WHEN / STOP WHEN as a card, the workers, the cost, the run state badge | the goal form (workers, return cap, test, files, lineup, lead and worker roles, model) with **Run** and **Dry run**; the runs of this repo, click one to open it | the badge follows the run: flowing while it runs, a green sweep when it finishes, red when it stops, amber when it was interrupted |
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
5 s instead. Palette commands (`Ctrl`/`Cmd`+`K`): **Orchestra: new run**,
**stop run**, **open run <id>** and **focus lane N**.

One run goes at a time. **Run** is disabled while a run is live, and the
glance's **stop** asks the runner to stop at its next step. Routes:
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
Glance face is the compact summary); each has a one-line `about` and a few
lines of `help` in its PanelSpec.

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
`PATCH` of the agent's `reportsTo`). The rail lists the agents and the
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

![Org mode: the halo-dev-cycle lineup as a Paperclip company](media/studio-org.png)

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

![The Knobs tab with Spacing at 48 and the Contrast table](media/studio-design-knob.png)

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
  starting box to hang it off main again.
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
through `tools/capture_studio.py --mode flow --dom`). The Flow and Media
panels are `ui/src/routes/flow/` and `ui/src/routes/media/`.
