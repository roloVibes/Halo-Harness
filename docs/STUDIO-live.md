# Studio: Agents -> Live, the living canvas

Read this when you watch what runs now on Studio's Agents -> Live: why it shows only what is happening, where the past went (History and replays), the plan drawn under the agents, what each agent waits on, the one sentence under the bar, the three zoom levels, and the scrubber that takes the canvas back in time.

Part of [Halo Studio](STUDIO.md), which lists every part. [Studio: Agents](STUDIO-agents.md) has the section's views and doors; [Studio: blocks and groups](STUDIO-blocks.md) the blocks and groups Live draws.

## Truth first (3.3.18.0)

The owner, 2026-11-10: "I always see like unused older version of orchestrations that aren't even happening when I look at
it. I'd love to see what is actually happening." Before 3.3.18.0 Agents opened on Cast (a plan, its cards glowing for every
failed agent of any open session after each reload), and Live drew the newest session of this harness, idle or not, with
every agent it ever had, and on the fleet the open mission's parts whatever their state. Now:

- **Agents opens on Live.** Alt+2, the rail, `?mode=agents`, `halo studio --mode agents` and a `focus` frame without a view
  land on Live: what runs now, or, when nothing does, one sentence -- "Nothing is running. Start a session, or open the last
  one as a replay." -- with two actions, **Open the plan (Cast)** and **Replay the last session**. A door that names a view
  (`?view=cast`, `C` / `R` / `L` / `W`, `?mode=roles`, `/roles`, `--edit`) still lands where it says.
- **Nothing past is drawn as present** (`routes/agents/live/now.ts`). An agent is drawn while it is queued, running,
  waiting or paused. One that finishes stays **ten seconds** (its green fades over them), then leaves; one that fails stays
  until you press its **dismiss** (Cast stops glowing for it too). A finish or a failure from before the page loaded is past
  and not drawn. The parents of what is drawn stay (the tree keeps its spine); a group goes with its last agent; a session
  goes when nothing of it is drawn; on the fleet the machines stay (they are here) with the empty sentence as a strip
  over them. An Orchestra run is drawn only while it runs, a mission's parts only while it runs or is being planned.
- **History** (Live's bar, `History · N`, closed on load) lists the past, newest first: this harness's sessions (an open
  one with nothing running says so), Orchestra runs of Studio's repo, finished missions; each row what it was, when, how
  long, its cost and how it ended. A row opens it as a **replay**: drawn as it ended, muted, never in the live colours,
  under a "replay -- <the moment drawn>" banner whose **Back to now** returns, with the scrubber under the canvas
  (Time, below). 3.4.1.0: a saved replay file is a row too, and **Open a file** takes one from disk; each row has a
  tick, and two ticked -> **Compare** (one ticked: before / after a moment), a page of the drawer with Back
  ([REPLAY.md](REPLAY.md#compare-two-runs)). Esc or the `x` closes the drawer.
- **Cast is the plan and says so**: its bar says "the lineup new sessions use: <name>", and while agents run a chip
  "N live -- see Live" goes to Live. The cards light only for agents running under them now.
- **The rail's Agents badge** counts the agents at work on this harness and on members that are online, never an away
  member's last rows.

Live lays out only when the tree's shape changes (which agents, their parents, their boxes) and repaints between, so a
long session's frames never move a box.

## The plan under it (3.3.18.0)

**Plan under it** on Live's bar (on by default when the session's lineup has tiers or enabled squares; `?plan=on|off`)
draws that lineup as the map: main's block, each tier (titled by its `purpose`), each square, quiet and still, and every
live agent inside the block it belongs to (`routes/agents/live/planModel.ts`):

| Agent | Its block |
|---|---|
| main (the session's root) | main |
| a square's agent and every agent under it | that square (a square the lineup does not enable: "not in the plan") |
| one a lineup card matches (alias, bio, a role only one card has) | that card's tier |
| one no card matches, under an agent in a block | that agent's block (a member's helpers stay in its tier) |
| one no card matches, under main | **not in the plan**, with why ("no card of <lineup> matches its role ... or its bio ...") |
| an Orchestra run's lead and lanes | a block of the run |

A block in use carries its count, state and cost on its title bar; one nobody uses is dashed and dim, its name and purpose
readable. Main's line into each tier and square is the plan's connection with its **when** label ("says implement, fix";
a square's own when); the line into a block at work carries the moving dash, every other line is still. Off, Live is the
grouped tree of [STUDIO-blocks.md](STUDIO-blocks.md).

## Work you can see moving (3.3.18.0)

- **A line's latest hand-off.** For eight seconds after main hands a task to an agent of a block (or it hands back) the
  line's label says it in a few words ("task: Check the tax notes", "back: ..."), then returns to the when. Hover the label
  for the last three exchanges on that line; a click opens Session's Conversations on that pair.
- **What each agent waits on** (`waits.ts`), one row on every live box, derived from the agent's row and the feed, never
  invented: **you** (an ask, its words), **an agent** (its open Agent / Task / Workflow call and the agent it started that
  still runs), **a tool** (which, and how long), **a model reply** (how long since its last line), **nothing** (it is writing,
  or queued).
- **The waiting path**: from main down to what the whole session waits on -- an ask anywhere first, else main's wait
  followed through the agents it waits on -- drawn as a brighter hairline on those boxes and lines.
- **The one sentence** under the bar (`narrate.ts`, at most 140 characters): what waits on you first, then the agents at work
  by block or group and what they do ("2 agents reading in square media, 1 running commands in the builders"), then what
  the session waits on, the models in play and the spend ("waiting on: scribe -> Bash pytest -q · on 3 models · $0.42").
  The wait's seconds and the elapsed time sit beside it and tick; the sentence changes only when a fact does. Hover it for
  a row per block or group; a click centres the agent the session waits on. Nothing runs: no sentence (the empty state
  says it).

## Zoom that changes meaning (3.3.18.0)

| Level | Zoom | What is drawn |
|---|---|---|
| far | under 60% | blocks only (the plan's, or with the plan off the tree's groups), twice the size, each with its count, state, cost and the waiting marker; no agent box |
| mid | 60% to 130% | every agent's box (with its waits-on row) |
| near | 130% and up | each box grows by its current thought (the newest THINK row, three lines) and its running tool with its last output line |

The **far | mid | near** switch on the bar sets the zoom to 50%, 100% or 150%; **Ctrl+wheel** (Cmd on a Mac) zooms around
the pointer, `+` / `-` around the middle. A level changes only at those thresholds, and the box, block or group under the
pointer stays under it (`zoomAnchor.ts`). **Fit** picks the level that shows the whole session readably: mid when it fits at
60% or more, else far (thirty agents open at far). `?level=far|mid|near` pins the level whatever the zoom until the
switch is used (a capture's or a driver's door; Fit is then a plain fit).

## Time: the scrubber (3.4.1.0)

Under the canvas, one bar is the ONE replay control (Cast's replay bar went): **Play** at **1x / 4x / 16x**, the clock,
the cost so far, **Save this run's replay**, **Export a clip** and **Now**, over the session's time axis -- its phase
bands (waiting on you, a tool, thinking, writing, idle) and a tick per spawn, hand-off, ask, failure and finish (hover:
what it was). Drag it and the canvas is redrawn as it was at that moment: who existed, in which block, each state, the
plan's line labels, the sentence under the bar and the cost, under "replay -- <time>" in muted colours. Over the session
running now it shows the axis up to now and a drag rewinds it; Now returns. A session, a goal run (coarse: each lane's
start and end), a mission and a saved `.halo-replay` file all play on it; a session and a goal run save as a file and
film a clip (R2). [REPLAY.md](REPLAY.md) has the file, the clip, what an older session cannot show, Compare and
`halo replay list | save | open | clip | compare`.
