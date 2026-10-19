# Studio: Fleet

Read this when you watch or steer every harness and agent from Studio's Fleet section.

Part of [Halo Studio](STUDIO.md), which lists every part.

## Fleet: every harness, every agent

`Alt+6` (or `?mode=fleet`, `halo studio --mode fleet`, `/studio fleet`) is
every Halo harness you run or joined, live: this machine's sessions (each
opens its control socket by default, [FLEET.md](FLEET.md)) and every harness
joined to this machine's hub, each session with its agents at every depth.
Watch what any agent thinks, runs and writes, and steer, pause or stop that
one agent, not only the main one.

![Fleet: two harnesses and five agents; the researcher's streams open, the implementer pinned as a mini stream](media/studio-fleet.png)

**The Start view.** While only this harness is here and nothing runs on it,
the section is one Start view instead of an empty map: what Fleet is in five
lines; "Start a session in a terminal, it appears here"; **Make a pair code**
(a one-time six-word code, the `halo fleet join <url> --code "..."` line for
the other machine and its QR, which carries the hub's address and
fingerprint; **Start the hub here** when none runs: it listens on the LAN
port, so Windows asks once about its firewall); the share and control
settings as radio rows (`fleet.share`: status | events | full;
`fleet.allow_control`: none | ask | all); the hubs this harness joined and
the members of this machine's hub, each with **kick**; and "open the
workspace anyway". The panels come up by themselves the moment a session
registers or a member joins (`?view=start` / `?view=workspace` force one).

Nine panels on a 24-column grid (seven from 3.0.5.0 R4, Capabilities from
3.0.6.0 R6, Mission from 3.0.6.0 R8). **The default layout** (3.1.4.0) opens
five of them, in three columns: on the left People and Costs on their
compact faces with Attention under them; in the middle the Map with Activity
under it, as wide as the map. The other four wait down the right edge as
title strips, one click away: **Health**, **Capabilities**, **Agent** and
**Mission**. The chevron on a strip's title bar opens it in that column (the
strips under it move down; nothing else moves); so do its row in the rail
(marked "strip") and the palette. Picking an agent (a click on the map, a
lane, a log line or the rail) opens Agent by itself, and `M` opens Mission.
**Reset layout** (the rail or the palette) brings this default back. An
arrangement you saved before 3.1.4.0 (`halo.studio.layout.fleet` in your
browser) opens as you left it; Reset layout moves it to the new default.
Every panel has its one-line about in its title bar and `?` for how to use
it.

![Fleet's eight panels: People, Costs and Health on top, Attention with the member's two cards, a conflict edge on the map, the timeline and the live log, Capabilities over the researcher in Agent, While you were away in the rail](media/studio-fleet-panels.png)

| Panel | What it shows |
|---|---|
| **People** (`fleet-people`) | One row per harness: name, host and OS, the Halo version (a chip with "halo update" when it differs from this one), what it shares and what it lets you do there, the project and top session it is on, **live** (an agent of it works now) / **idle** / **away** (the hub has not heard from it for two minutes), spend today. **Message** sends its owner a note in that session (the `note` command; the model never reads it); **Kick** (this machine's hub only) asks first. Compact face: how many are online and their names. |
| **Costs** (`fleet-costs`) | Today's spend (sessions started today, local day) as a ticker for the whole fleet, then per harness, per project and per session; the provider balances the balances workers last read, when there are any; the **spend caps** editor (per harness, per project, the whole fleet, dollars per day; empty is no cap) and every cap reached, with **Lift for today**. Compact face: the fleet's spend and the caps reached. |
| **Health** (`fleet-health`) | A doctor summary per harness: all good / check it / needs you, the providers set up and whether they answer, the Halo, Studio and Python versions, free disk, how many sessions have their control socket open, and how old the reading is; **Refresh** asks again now. Compact face: healthy and to check. |
| **Attention** (`fleet-attention`) | Every decision that waits on you, across the fleet, oldest first: who (harness, session, agent), what, for how long, and its one-key answers. Compact face: the count and the oldest row. |
| **Activity** (`fleet-activity`) | The **timeline**: one lane per live agent over the last 5, 15 or 60 minutes, a bar per state (cyan working, amber waiting or paused, green done, red failed), each tool call a tick; hover for who and since when, a click selects that agent. Under it the merged **live log** of every harness, session and agent (state changes, tool calls, the text they write, the cards they open, errors, harnesses joining and leaving), with filters by harness, session, agent and kind, and Follow. A log line is one row (time, kind, who, then the text, which keeps at least 160 px and breaks between words; who shortens to its ellipsis first); when the log is narrower than 440 px, time, kind and who share the first row and the text takes the full width under them. The timeline draws at its real width, so the lane names keep their size in a narrow panel. Compact face: agents live and the newest line. |
| **Map** (`fleet-map`) | One labelled box per harness (this one first; the group-box look of the Roles and Org canvases), a card per session (title, kind chip, project and branch, cost, status dot) and its agents as a tree under it (name and role, what it does now, the model pill, the tool's icon while a tool runs, a cost ticker that counts up, `...`), an edge from each parent to its children. **By project** regroups the cards into one box per repo, the harness colour on each card. Compact face: harnesses, agents live, need you. |
| **Capabilities** (`fleet-capabilities`) | 3.0.6.0 R6. The **Who can...** box on top (see below), then one spec card per harness: its chips (the owner's tags, the GPU, the OS, craft apps), the hardware (CPU, cores, RAM, GPUs and VRAM, free disk), the models it is best with and its local ones, its craft apps and ComfyUI models, every MCP server with its tool count (click one for its tools and what each does), skills, command-line tools, tags, the catalog's age and **Refresh**. The map's harness boxes carry the same chips; People has a **specs** link per harness. Compact face (the face its strip opens on): the Who can... box and its best three, else each harness's chips; Expand for the spec cards. |
| **Mission** (`fleet-mission`) | 3.0.6.0 R8. One goal for the whole fleet. **Start**: "What should the fleet do?", constraints, **prefer** (a chip per harness, clicked in the order you prefer them: the planner breaks ties with it), a budget, **Plan it**; under it every mission (goal, state, parts by state, harnesses, cost, **Open**). Five numbered lines on how a mission works show in full while there is no goal text and no mission yet; once you type a goal or a mission exists they fold into one **How this works** line, and a click on it opens them. **Plan**: a row per part (its number, title and kind, the harness with the reason on hover and a lock when it was pinned by capability, needs, claims, what it waits for, the estimate, **Drop**), the notes, the merge order, **Plan again**, **Approve**, **Run** (approves first) and what still stops an approval. **Running**: each part live (asked: waiting on that member's owner; running: the line its agent is on; then done / failed / stopped / skipped) with **Open the part's agent**, the cost per harness ticking, the merge queue, **Stop the mission...** (asks for a reason). **Report**: who did what on which harness, cost per harness and per part, decisions, refused edits, failures, the merge, the artifacts and hand-backs with **Open**. **Coach** (3.0.9.0, once the mission ended): the post-run coach's cards (a part asked long, a refused edit, a judged conflict, a part that changed nothing, missing outputs). Compact face: the running mission's goal and its parts by state, else "no mission". |
| **Agent** (`fleet-agent`) | The selected agent: harness, session, role, model, cost, elapsed, state; **What it was asked**; its three streams, tabbed or side by side (Settings): **Thinking** (what it writes and reasons, the newest text typing out character by character; steers, notes, the cards it opened), **Working** (one row per tool call with its arguments, the file it touches, its result, and for Edit / Write the diff as it grows), **Output** (its hand-back, else the text after its last tool call); **Pause** / **Resume**, **Stop** (asks first), **Follow**, **Pin**; **Take over**, **Hand to...**, **Record**, **Replay** (this harness); the **Steer** box. With no agent picked, the last sessions on this harness with **replay** and **record**. Compact face: the agent, its state and cost, what it does now and its last words. |

**Motion** (the shell's vocabulary): a working agent's outline flows (a
dashed light running round it), one that waits on you or is paused pulses
amber, one that just finished gets one green sweep, a failed one flashes red
and keeps a red edge, a queued or stopped one breathes slowly. When an agent
spawns another (or sends it a message), the edge between them lights for
three seconds.

**Click, double-click, `...`.** A click selects (the Agent panel opens from
its strip and follows, so does an open Inspector, the agent is followed so
its stream is pushed, its backlog is read once; the keyboard stays where it
was); a double-click opens Agent expanded and focused; `...` on an
agent is **Steer**, **Pause** / **Resume**, **Pin**, **Stop...**, **Take over...**,
**Hand to...**, **Record this agent**, and on a session card **Record the
session** and **Shut the session down...**; **Open in Orchestra** /
**Open in Flow** when the session is an Orchestra worker or a flow run.

**Steer.** Type in the Steer box and press Enter (or Send): **nudge** is a
note the agent reads before its next model call, **redirect** gives it a new
task. Only that agent hears it, its stream shows your words marked "you",
and its transcript records who sent it. A steer never widens a permission or
answers a card. To a member's agent it goes through the hub: that harness's
`fleet.allow_control` decides (`ask` opens an allow / deny card for its
owner, and Studio says it is waiting), `none` takes no commands, `all` runs it.

**Stop, Pause, Shutdown.** Pause holds the agent at its next tool or model
call (Resume releases it). Stop asks first, then the agent stops at its next
step with its own sub-agents, and the agent that spawned it gets the stopped
hand-back and carries on. Shutdown ends the whole session after its current
tool call. The palette also has **Fleet: pause all** and **resume all**.

### How this works: Attention

One queue holds every decision a human has to make on any harness:
permission, question, plan and approval cards, a fleet command a member's
owner has to allow, an agent that waits or is paused, a Flow gate, an
Orchestra gate, a spend cap reached, two agents on one file. Each row
answers with one key, through the route that already handles that kind
(`GET /api/fleet/attention`, `POST /api/fleet/attention/answer`): **A**
accepts, allows or resumes, **R** denies, redoes or answers with the text
you type (a deny reason is optional), **S** stops the agent, **O** opens the
panel the row belongs to (the agent in Agent, Costs, the map, Flow,
Orchestra) and sends nothing. Click a row (or move with `J` / `K` or the
arrows while the panel has the focus), then press the key; every decision
is journaled with who made it. The count is live in the status bar and the
rail in every section (a `fleet` frame with action `attention` each time it
changes); a click on the rail's count opens Attention. With the phone
bridge enabled and paired, new rows go to the phone too ([FLEET.md](FLEET.md)).

### How this works: Costs and caps

Costs reads `GET /api/fleet/costs` every ten seconds while it shows. A cap
is `fleet.caps.per_harness_usd_per_day`, `per_project_usd_per_day` or
`fleet_usd_per_day` (`POST /api/fleet/caps`, saved in the hub's
config.json). When today's spend reaches one, the sessions in its scope
pause at their next step and an attention row says so; **Lift for today**
(in Costs or the row's `A`) resumes them and holds that cap off until
tomorrow.

### How this works: Conflicts and project rooms

The hub watches what each agent is editing (its current Edit / Write, and
the Orchestra claims). When two agents of different sessions, on any
harnesses, edit the same file of the same repo, the map joins them with an
amber dashed edge (hover it for who and which file), both session cards
carry a `!` chip with the file, and an attention row names both; its `O`
opens the map. **By project** groups the cards by repo and shows each
card's git chips: clean or dirty, ahead / behind, the worktree
(`GET /api/fleet/conflicts`, polled with the queue).

### How this works: Hand-offs

On an agent (the Agent panel, the map's `...`, the palette): **Take over**
asks for your brief; the agent reads it before its next step in place of
its task, and both transcripts record the hand-off and who made it.
**Hand to...** asks which harness picks the work up (and a note for them):
with Org mode on, Paperclip gets an issue for that harness's company agent
with the task, the last hand-back and the files it touched; with it off,
the same goes into a markdown hand-off note in the repo (`.halo/handoffs/`).
Then the agent stops. The dialog shows the issue id (Open goes to Org) or
the note's path (Open copies it). `POST /api/fleet/<harness>/<sid>/agents/<aid>/handoff`.

### How this works: Recordings

**Record** on the Agent panel (one agent) or a session card's `...` (the
whole session) writes one self-contained HTML file: the three streams, a
timeline you can scrub, every tool call, the cost curve; no network, so
it opens in any browser and can be sent to anyone. The dialog's
**Download** fetches it with Studio's token and saves it
(`POST /api/fleet/<harness>/<sid>/recording[?agent=]`, then
`GET /api/fleet/recordings/<name>`; `halo fleet record` in a terminal).

### How this works: Replay

A finished session plays back on the **Roles** canvas: the cards light up
in the order the agents worked (glowing while they run, amber while they
wait, a green sweep when they finish). Start it from a card's Live tab
history (the **replay** button on a run), the Agent panel (**Replay**, or
the last sessions when no agent is picked) or the palette. A scrub bar
along the bottom of the canvas has play / pause, the speed (1x to 960x;
it starts at a speed that plays the session in about forty seconds), the
clock, the cost so far, who works at that moment, and `x` (or `Esc`) to
go back to what runs now; live updates wait while it plays. The shell
reads `GET /api/fleet/replay` into the Roles store (3.0.7.0 R2) and the
React canvas plays it.

### How this works: Who can do what

Every harness gathers its own capability catalog in code: its MCP servers
and their tools (from their tool caches; a server that does not answer in
time is listed without tools and fills in on the next gather), skills,
models, craft apps, ComfyUI, hardware, command-line tools, projects and the
tags its owner set (`fleet.tags`). Names only: no full path, server command
or key ever leaves the machine, and `fleet.capabilities.hide` keeps a
server, tool or skill off it. A member's announce carries a one-line summary
and the catalog's hash; the hub asks for the whole catalog once per hash and
a `fleet` frame with action `capabilities` refreshes the panel
(`GET /api/fleet/capabilities`). **Who can...** ranks the fleet for what you
type, in code: an exact name beats a word of a name, which beats a word of a
description, and a tag counts double; each result shows what matched and
why (`GET /api/fleet/who?q=`, `halo fleet who`). Click a result and that
harness is picked: its card opens, its box on the map lights up, its
session's main agent is selected. The palette has **Fleet: who can...** and
**Fleet: specs of** each harness. See [FLEET.md](FLEET.md#capabilities-3060-r6).

![Fleet Capabilities: "gridcraft" in Who can... ranks kali@lab first and picks it on the map; both spec cards with their chips](media/studio-fleet-capabilities.png)

### How this works: Missions

One goal, every harness, nobody stepping on anyone ([MISSIONS.md](MISSIONS.md)):

1. **Goal**: type it in the Mission panel (`M`, or the palette's **Fleet:
   new mission**) and press **Plan it** (`POST /api/fleet/missions`). The
   hub's lead splits it into parts with every harness's capability catalog
   in front of it; a part that needs what only one harness has is pinned
   there (a lock, the reason on hover), a tie goes to your **prefer** order
   then the least busy harness, and a part nobody can run gets a red
   **unassignable** chip.
2. **The plan on the map**: each part is a node in its harness box's lane,
   dashed while planned; an edge for each part it waits for, amber with a
   **claims** chip where two repo parts claim the same files and so run one
   after the other, and on every other edge a chip naming what it hands on
   (the outputs' names, `all` or `hand-back`); a repo part shows its base
   (the mission's base, or "base: 1's head" when it starts from an earlier
   part's work). The table under the map is the same plan.
3. **Edit by hand**: drag a part's node into another harness box to move it
   there (`POST .../parts/<n> {harness}`, checked in code: a harness that
   lacks what the part needs answers 422, the toast says why and the node
   snaps back); **Drop** takes a part out; **Plan again** asks the lead anew.
   Attention has the plan as a row too: `A` approves and runs, `R` edits
   with a text ("part 2 to kali", "drop 3"), `S` drops the mission.
4. **Approve, Run**: Run approves first. Parts start by their dependencies:
   a part on this harness runs here, a part on a member goes to it as the
   `run_task` command. Under `fleet.allow_control: ask` that member's owner
   gets a card ("hub asks to run mission ... part 1 here: ... (claims:
   ...)"), and the node and its row pulse amber, "waiting on <harness>'s
   owner"; on the member's own Studio the card is a **mission part** row in
   Attention (`A` allow, `R` deny, `O` opens the Mission panel on that
   mission). A running part is solid, its row shows the line its agent is
   on, and its `mission-worker` session shows on the map and in the rail
   with a **mission** chip.
5. **Report**: when the last part is over (or you **Stop** it, with a
   reason) the panel turns to the report: who did what on which harness, the
   cost per harness and per part, the decisions, the edits refused outside a
   part's claims, the merge, and the artifacts to open.

The status bar's FLEET cell counts the missions running; the palette has
**Fleet: new mission**, **approve mission**, **stop mission** and **mission
report**.

![Fleet Mission: a planned mission drawn on the map, one part pinned to each harness, part 3 after part 1 because their claims overlap; its table in the Mission panel](media/studio-fleet-mission.png)

### How this works: While you were away

When the tab comes back after more than ten minutes (or Studio opens after
that long), a card sums up what happened since you last looked, computed
in code per harness: sessions started and ended, cost, decisions made and
by whom, files touched, errors, hand-offs (`GET /api/fleet/digest?since=`;
`halo fleet digest` in a terminal). It shows on the Fleet Start view, else
in the rail. When you last looked is the browser's
`halo.fleet.lastSeen`, refreshed every minute while the tab shows;
**Dismiss** sets it to now. The palette's **Fleet: while you were away**
shows it on demand.

### Keys: hop around

| Key | Where | What |
|---|---|---|
| `Alt+6` | everywhere | Fleet |
| `Alt+7` | everywhere | Team (3.0.8.0) |
| `J` / `K` | Fleet map, the Roles canvas, Orchestra lanes | the next / previous live agent (Orchestra: the next lane at work) |
| `F` | Fleet; Roles with the Live tab open; Orchestra | follow: the stream scrolls with the agent (Orchestra: the Log follows) |
| `Space` | Fleet; Roles with a card's agent watched | pin the stream: a **mini stream** floats over whatever you look at, in every section |
| `Esc` | everywhere | unpin the mini stream (once the palette, a menu or the Inspector is closed) |
| `P` | Fleet; Roles with the Live tab open | pause or resume the agent |
| `K` | inside the Agent panel | stop the agent (asks first; on the map and the canvases `K` is previous) |
| `A` / `R` / `S` / `O` | inside the Attention panel | answer the selected row: accept, deny or redo (with a text), stop, open |
| `J` / `K`, arrows | inside the Attention panel | the next / previous row |
| `M` | Fleet | the Mission panel: one goal for the whole fleet (3.0.6.0) |
| `Esc` | Roles during a replay | close the replay, back to what runs now |

**The mini stream** (picture in picture) shows the pinned agent's state, cost,
what it does now and the newest lines of its stream, typing as they arrive;
drag it by its bar, its arrow opens the agent in Fleet, `x` or `Esc` unpins.
It hides while the Agent panel already shows that agent.

**The rail and the palette.** The Fleet tree in every section's rail
(harness > session > agent, a status dot each, the live and need-you counts)
opens Fleet on the node you click, and a session that waits on you keeps its
inline answer there (for a member too); its need-you count opens Attention,
and "While you were away" shows above it; a mission part's session carries a
**mission** chip and its **part** link opens the Mission panel on it. The palette's **Fleet** group: pair a
harness, kick a member, group the map by project, follow / steer / pause /
stop the selected agent, take it over, hand it to..., record it, replay its
session, answer next (Attention, the oldest row), while you were away,
who can... and the specs of each harness (3.0.6.0), new mission, approve
mission, stop mission, mission report (3.0.6.0),
follow any live agent by name, pause all, resume all, open the session in
Orchestra or Flow.

### Live Roles: the lineup lights up

On the **Roles** canvas the cards whose agents work right now glow (3.0.7.0
R2: the React canvas; the React Org chart shows each agent's Paperclip
status instead). Every live agent (any harness, any session) is matched to
the card it runs under: the lineup must be the open one, then its alias,
else its bio, else a role only one card has (a session's main agent on the
main card). The glow is in the card's band colour and follows what the agent
does: **typing** a steady flow along the top, a **tool call** one pulse per
call and the tool on the card's badge (✎ Edit, ›_ Bash, ▤ Read, ◉ Agent ...),
**waiting on you** the amber pulse and the gate's diamond, **done** one sweep
then still, **failed** one flash. A badge counts the agents when several
share a card (`×2`) and ticks their cost. The edge into a card whose agent
runs flows while it runs.

![Roles: the implementer and the researcher at work, the main card waiting with two leads, the implementer's Live tab](media/studio-roles-live.png)

Select a card with a live agent and the Inspector opens its **Live** tab:
a chip per agent when several run on the card, then the agent's header,
what it was asked, its Thinking / Working / Output streams (the text typing
as it arrives, one row per tool call with its result), Pause / Resume, Stop
(asks first), Follow, Pin, and the Steer box. A card nobody runs right now
shows its track record instead: the last runs under that role or bio on this
harness (`GET /api/fleet/history`, from the sessions' transcripts: when,
which bio, the outcome, the cost, the task), each with **replay**. The
canvas reads the live agents from the Fleet store (`routes/fleet/frames.ts`
writes them into the Roles store) and the Live tab uses the Fleet
section's own streams, Steer box and commands.

**Recall across the fleet (3.1.2.0 R3).** The recall box's **Fleet** switch
asks `GET /api/recall?q=&fleet=1`: the hub Studio runs (`--fleet`), else a
`halo fleet serve` on this machine, else the first hub this harness joined,
fans the query out to every online member, each answering from its own
index, and the box shows the hits merged by score, each labelled with its
harness, with a line for every harness that did not answer. `GET
/api/fleet/recall?q=` is the hub's merged view on its own. The index never
leaves a box; a member keeps out with `fleet.recall.share: false` and hides
kinds with `fleet.recall.hide` ([FLEET.md](FLEET.md) "Recall across the
fleet").

**Where it reads and writes.** `GET /api/fleet` once, then the live feed
keyed by harness, session and agent (`agent_state` rows in place,
`agent_event` entries of a followed agent, the raw `text_chunk` /
`tool_use_start` / `tool_result` frames, a member's `fleet` frames with
action `sessions`); polling every 4 s only while the feed is down. Commands:
`POST /api/fleet/<harness>/<sid>/agents/<aid>/command` (`local` for this
harness) and `.../<sid>/command` for a session; a backlog is `GET
/api/sessions/<sid>/agents/<aid>/tail` here, the `tail` command through the
hub for a member. The Start view uses `POST /api/fleet/pair`, `GET` / `POST
/api/fleet/settings`, `POST /api/fleet/kick` and `POST /api/fleet/hub`. The
R4 panels read `GET /api/fleet/attention`, `costs`, `caps`, `health`,
`conflicts`, `digest`, `replay` and `history`, and post to
`attention/answer`, `caps`, `.../handoff`, `.../recording` and a session's
`command` (`note`); [FLEET.md](FLEET.md) has every shape.
