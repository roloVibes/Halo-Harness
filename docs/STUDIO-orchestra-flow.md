# Studio: the Orchestra and Flow consoles

Read this when you run an Orchestra goal or a flow from Studio: the plan canvas, the coach, the media renders and their routes.

Part of [Halo Studio](STUDIO.md), which lists every part.

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
send a part back. **Review the plan before it runs** (beside Run; on the Goal
panel under the disclosure) sends `review: true`: the run stops after the
lead's split and the plan canvas below takes the console's place.

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
| **Lanes** | joined, writing, merged, one strip per lane | the timeline: one trace per worker on the run's clock from "joined" to "merged", a node at each state change, a diamond where the gate sent the piece back; hover a node for its time and text; 3.0.9.0: an arc from a lane to each lane that starts after it, a chip on the later lane naming what it takes (`summary`, `all`, an artifact, or `after`) and a "base: <sha7>" line on every lane | the running lane's trace flows, a waiting lane pulses amber |
| **Live file** | units being written, units merged, a minimap of the bands | the goal file in mono with each lane's claimed unit as a band in its lane colour, labelled claimed, writing, written or merged, holding the lane's current text (its worktree copy); a picker when the goal has several files | a band being written shimmers; a claimed band is hatched |
| **Report** | checks passing, cost, one pip per check | the checks with ticks and crosses, the finished branch and sha, the tests, the cost and time; **Copy** puts the report text (as `halo orchestra report` prints it) on the clipboard; a dry run shows the lead's jobs here; 3.0.9.0: the **Coach** tab beside it (below) | one green sweep when the report lands |
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

### The plan canvas (3.0.9.0)

While the open run is `planned` (its goal has `plan: review`) one panel,
**Plan** (`orchestra-plan`), takes the console's place. Its toolbar names
the run, how many lanes there are and how many the lead planned, and has
**Add lane**, **Undo** / **Redo** (`Ctrl+Z` / `Ctrl+Shift+Z` on the canvas),
**Reject** and **Approve and run**. The canvas (`plan-canvas`) draws the
lanes as cards (`plan-lane`) in one labelled box per layer (`plan-layer`):
the first runs at once, each next box runs after the lanes it names, and an
empty box at the end opens a new layer. An `after` edge (`plan-edge`) joins
a lane to each lane it waits for, with a chip naming what it takes
(`summary`, `all`, an artifact) or `after`. Drag a card into another box:
the first box clears what it runs after (and what it takes), box *k* makes
it run after every lane of box *k-1*. Click a card: the inspector edits its
title, its claims (chips; add one from the goal's units, which names the
lane that already claims it), what it runs after, what it takes (needs:
from a lane, `summary`, `all` or one of that lane's gives), what it hands on
(gives: a name, a kind, paths), its bio (the Roles bios) and its model (the
Roles model picker with **Test this model**), and **Drop lane**. Every edit
is one undo step and is sent as the draft (`PUT orchestra/<run>/plan`); the
answer's problems show under the canvas (`plan-problem`, click one to select
its card) and on each card they name (a red outline and the text). **Approve
and run** (`plan-approve`) stays disabled while a problem remains and its
tooltip names them; it sends the plan and the console comes back as the run
goes on. **Reject** opens a card that asks for the reason; the run stops with
it.

The cost forecast (3.1.2.0, [ORCHESTRA.md](ORCHESTRA.md#the-forecast)): each
card carries its lane's cost chip in its header (`plan-cost`: the low-high
band, `? $` dashed when its model has no catalog price; its tooltip names
the tokens and whether the lead estimated them), and the toolbar the total
against the goal's `budget_usd` (`plan-forecast`: "forecast $0.03-$0.10 of
$0.50"), red with "over budget" when its high end passes the budget. Every
edit's `PUT` answers the new forecast. **Approve and run** over the budget
still runs, with a toast that says so. In the run console a lane whose
upstream the gate sent back shows a STALE badge (`lane-stale`) until it is
re-based, then the re-base line (`lane-rebase`).

![Orchestra: the plan canvas of a run waiting for review](media/studio-orchestra-plan.png)

### The Coach tab (3.0.9.0)

Once a run has its report, the Report panel has two tabs: **Report** and
**Coach** (`report-tab-coach`). Coach reads the run's files through `GET
orchestra/<run>/coach` (no model call; kept in the run's `coach.json`) and
shows the suggestions as cards (`coach-card`, with `data-kind` and
`data-severity`) grouped by kind: TOOLS, MODEL, PROMPT, STRUCTURE,
COORDINATION. Each card has its severity chip (high, medium, low), the lane
and the bio it is about, the suggestion, and its evidence in mono
(`coach-why`). **Apply** (`coach-apply`) is on the cards that name a change:

- a bio change opens Roles on that bio's form with the field filled in and
  marked, under a note naming it (`bio-coach-note`); nothing is saved until
  you press **Save bio**, and **Undo the change** reads the bio again;
- a lineup change opens the lineup with that role's model changed in the
  draft and the Inspector on its Lineup tab (Save keeps it);
- a plan change opens the plan editor on the run's plan with the edit
  staged as one undo step: the bar says STAGED and names the card, the run
  already ran so nothing is sent, **Copy the plan** puts the jobs on the
  clipboard (for `halo orchestra approve --file` on a run started with
  Review the plan before it runs) and **Back to the run** returns to the
  console.

**Dismiss** (`coach-dismiss`) hides a card for that run in this browser
(localStorage); **Show dismissed (n)** brings them back. A flow run's Report
panel has the same Coach tab, a mission that ended has a **Coach** face
beside Plan, Running and Report, and the Team run bar has **Coach** once
the run is done or stopped (the cards in a dialog). The rules:
[ORCHESTRA.md, "The coach"](ORCHESTRA.md#the-coach).

![Orchestra: the Coach tab of a finished run, three cards with their evidence](media/studio-orchestra-coach.png)

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

**As a graph (3.0.9.0).** **Show <flow> as a graph** under the flow picker
(or `?graph=<name>`) draws the picked flow on the plan canvas instead of the
section (`flow-graph`): its steps as cards (`flow-step`) in dependency
layers, one labelled box per layer, from their `$.<step>` refs; the confirm
step is marked as the gate. It is read-only except the order of
independent steps: drag a card onto another one in the same box and the flow
file is rewritten in that order (`PUT flow/templates/<name> {order}`; a
shipped template is copied to your `~/.halo/flows/` first). **Back to the
flow** returns ([FLOWS.md](FLOWS.md#as-a-graph)).

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
| **Report** | the status, the cost against the budget, the steps table, the artboards, the posts and the metrics summary; **Copy** puts the text `halo flow report` prints on the clipboard; 3.0.9.0: a **Coach** tab beside it (a gate that looped, a render drawn again, a budget stop) | one green sweep when the report lands |

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
