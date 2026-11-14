# Studio: Agents -> Live, the living canvas

Read this when you watch what runs now on Studio's Agents -> Live: why it shows only what is happening, where the past went (History and replays), the plan drawn under the agents, what each agent waits on, the one sentence under the bar, the three zoom levels, the scrubber that takes the canvas back in time, the glance (one phone-width page) and the alert when something starts waiting on you.

Part of [Halo Studio](STUDIO.md), which lists every part. [Studio: Agents](STUDIO-agents.md) has the section's views and doors; [Studio: blocks and groups](STUDIO-blocks.md) the blocks and groups Live draws.

## Truth first (3.3.18.0)

The owner, 2026-11-10: "I always see like unused older version of orchestrations that aren't even happening when I look at
it. I'd love to see what is actually happening." Before 3.3.18.0 Agents opened on Cast (a plan, its cards glowing for every
failed agent of any open session after each reload), and Live drew the newest session of this harness, idle or not, with
every agent it ever had. Now:

- **Agents opens on Live.** Alt+2, the rail, `?mode=agents`, `halo studio --mode agents` and a `focus` frame without a view
  land on Live: what runs now, or, when nothing does, one sentence -- "Nothing is running. Start a session, or open the last
  one as a replay." -- with two actions, **Open the plan (Cast)** and **Replay the last session**. A door that names a view
  (`?view=cast`, `C` / `R` / `L` / `W`, `?mode=roles`, `/roles`, `--edit`) still lands where it says.
- **Nothing past is drawn as present** (`routes/agents/live/now.ts`). An agent is drawn while it is queued, running,
  waiting or paused. One that finishes stays **ten seconds** (its green fades over them), then leaves; one that fails stays
  until you press its **dismiss** (Cast stops glowing for it too). A finish or a failure from before the page loaded is past
  and not drawn. The parents of what is drawn stay (the tree keeps its spine); a group goes with its last agent; a session
  goes when nothing of it is drawn. An Orchestra run is drawn only while it runs.
- **History** (Live's bar, `History · N`, closed on load) lists the past, newest first: this harness's sessions (an open
  one with nothing running says so), Orchestra runs of Studio's repo; each row what it was, when, how
  long, its cost and how it ended. A row opens it as a **replay**: drawn as it ended, muted, never in the live colours,
  under a "replay -- <the moment drawn>" banner whose **Back to now** returns, with the scrubber under the canvas
  (Time, below). 3.4.1.0: a saved replay file is a row too, and **Open a file** takes one from disk; each row has a
  tick, and two ticked -> **Compare** (one ticked: before / after a moment), a page of the drawer with Back
  ([REPLAY.md](REPLAY.md#compare-two-runs)). 3.4.1.0 R3: each row has its own **Report** door: a
  session's or a file's **report card** opens as a page of the drawer (the story in about ten lines, where the time and
  the money went, what failed, what waited on you, which model did what, the files; Copy Markdown, Replay, Back), a goal
  run's report page has the card as its first block ([REPLAY.md](REPLAY.md#the-report-card)). With nothing running,
  Live's empty state ends with a row for the session that ended last and its **Report card** (a row, never a pop-up).
  Esc or the `x` closes the drawer.
- **Cast is the plan and says so**: its bar says "the lineup new sessions use: <name>", and while agents run a chip
  "N live -- see Live" goes to Live. The cards light only for agents running under them now.
- **The rail's Agents badge** counts the agents at work on this harness.

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

The **far | mid | near** switch on the bar sets the zoom to 50%, 100% or 150%; **Ctrl + wheel** (Cmd on a Mac) or a
trackpad pinch zooms around the pointer (a wheel notch is one 10% step, a pinch a smooth fraction), `+` / `-` around the
middle, `0` (or a double-click on the background) fits, a drag on the background pans and Shift + wheel pans sideways
(3.4.1.3: the same on every drawing in Studio -- Live and its replay, Session's Map, Cast, the design pack's artboards
-- from one module, `lib/canvasNav.ts`; over a drawing the browser's own page zoom is held back, nowhere else). A level changes only at those thresholds, and the box, block or group under the
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
start and end) and a saved `.halo-replay` file all play on it; a session and a goal run save as a file and
film a clip (R2). [REPLAY.md](REPLAY.md) has the file, the clip, what an older session cannot show, Compare and
`halo replay list | save | open | clip | compare`.

## The glance

`/?mode=glance` (3.4.1.0 R4) is ONE phone-width page of this Studio -- no rail, no panels -- for a look from across the
room or from a phone (`routes/glance/`):

- **the sentence** of what is going on now, Live's own (`narrate.ts`) over the session Live would draw (this harness's
  newest with an agent at work, else its newest); with no agent tree to read, what waits on you;
- **what waits on you**, oldest first, each with its answers as **large buttons** (the row's own allow once / deny /
  stop, approve / send back, answer ...), each saying in one line what it does; an answer that needs words opens a text
  box first, a permission's deny takes an optional reason;
- **the spend** against its cap: today's spend as the caps count it (`GET live/costs`: each harness's today from its
  records, finished sessions too -- the figure History and the Cost panel read; 3.4.1.1) for the first cap
  set of this machine's, the session's project's, else this machine's; a model Halo cannot price makes it
  `$x+`, never `$0`; none set reads **no cap set**; a cap reached says its sessions are paused;
- **the elapsed time** of that session, and **the last three events** (a tool run, a line written, an ask), newest first;
- a status word: **live**; **live figures; the feed is reconnecting** while the feed reconnects; **stale: last heard N s
  ago, reconnecting** when Studio has not answered for 15 seconds. It reconnects by itself to the same Studio (a network
  blip, the SSH forward re-made: the feed backs off and retries; the queue is read every six seconds; while Studio is
  not heard the page asks every three seconds; a page that shows again reads everything once more). A Studio that was
  **restarted** has a new key (the token is made per launch and never kept or reused): the page's asks turn from "no
  answer" to refused, and it says **Studio was restarted and has a new key: open the glance again from Studio
  (Session's ... menu -> Open the glance)** and stops asking (3.4.1.1).

Open it from **Open the glance** (the palette's View group, and Session's "..." under ELSEWHERE), `halo studio --mode
glance`, or the address itself. The dialog says what Open does, costs and writes (opens a tab; nothing; nothing), shows
this machine's address and, for a phone, either the steps and a code to scan or, plainly, that the page is
this-machine-only ([REMOTE.md](REMOTE.md#the-glance-from-a-phone)).

**What it may do.** It is the same loopback Studio with the same token, served the same page; nothing new listens and
no port is added. It reads what Studio's own page reads (`GET live`, `live/attention`, `live/caps`, an agent's tail,
`settings/values`, `/api/events`) and its one write is an answer, `POST /api/live/attention/answer`, the request
Attention's keys send, with the token AND the owner proof (`X-Halo-Owner`): since 3.4.1.0 R4 that route is an owner
route, so neither Attention nor the glance answers a card without the shell's own page
([STUDIO-security.md](STUDIO-security.md#security-model)). It calls no model.

## The alert

When something **starts** waiting on you -- a new row of the attention queue: a permission, a question, a plan, a gate,
a cap -- ONE alert by the channel you picked in **Settings -> Studio -> Alerts** (`studio.alerts`, `lib/alerts.ts`),
naming what waits and on which session ("Waiting on you: Permission: Bash", "shop on you@laptop · main"). Never one per
feed event (a card is one row however many frames say it), never for what already waited when the page opened, and rows
that land together are one alert ("and 2 more").

**Background work that finished while a session was idle** (3.4.1.3) is a row of that queue too, `background_done`
("Background work finished", the job or sub-agent and what happens next): no prompt is needed to learn it. It shows on
Agents -> Live's attention chip, on the glance and in the alert; further finishes before your next message there keep
the one row (one alert); your next message, or **A** set aside, takes it away. The session's side:
[SUBAGENTS.md](SUBAGENTS.md#when-background-work-finishes-while-the-session-is-idle-halo-3413).

| Choice | What it does |
|---|---|
| **None** (the default) | nothing is sent |
| **This browser's notification** | the click asks THIS browser for permission, once (never on load, never on its own); then each Studio page or glance open in a browser that allowed it shows one notification per new ask; a click on it opens the ask (in Studio: Session's Attention on that row; on the glance: the row, lit) |

The line under the choices says what this browser will do: it allows it; it has not been asked (press the choice and it
asks); it blocked notifications for this page (allow them in its site settings); or it has none here (a page off
127.0.0.1 or localhost has none). Two pages in one browser show one notification (each carries the row's tag).
A second channel is one more entry of `CHANNELS` in `lib/alerts.ts`; the owner has not chosen one yet, so nothing else is
built (the signal pack's phones already get the queue's new rows as `asks` notes, [REMOTE.md](REMOTE.md#transports)).
