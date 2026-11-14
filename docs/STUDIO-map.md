# Studio: Agents -> 3 · Map (3.6.0.0)

Read this when you connect your agents and workflows on Studio's Map tab, add a box, draw a line and say when it hands work on, keep more than one map, pick the map your sessions run on, or lock a map.

Part of [Halo Studio](STUDIO.md); the agents are made in [1 · Agents](STUDIO-builder.md), the workflows in
[2 · Workflows](STUDIO-workflows.md); what a session does with a map is [How a session runs on a map](CREW-sessions.md),
and the file is a `map/1` [crew file](CREW-FORMATS.md#a-map-format-map1).

![The Map tab: main at the left, a box per agent or workflow, each line's When in words in the lane between the columns](media/studio-map.png)

## The tab

Agents (`Alt+2`), then **3 · Map** (the `3` key). The switch reads **1 · Agents | 2 · Workflows | 3 · Map | Cast | Live |
Board** (Cast, Live and Board are the older views, still there in this version). It opens on the starter map, or the
map you opened last, a link's `&map=<name>`, this project's map, or the one your sessions use. Nothing opens by itself:
the list to add from is a drawer you open from the bar ("Agents and workflows"), the builder is a box docked below.

**What you see.** **main** -- the agent you talk to -- is always at the left. Every other box is an agent (its name and
model; Auto: "picked per task") or a workflow (its name, its steps as dots, "click to open"). There is one kind of line,
"hands work to", and each line's **When** is a label in the lane between the columns, never over a box. A box's column
is its longest chain of lines from main, so every line runs left to right; many lines from one box share one trunk.
Hovering a box lifts its lines and dims the rest; a box grows with its text and is never cut.

**Reading it bigger or smaller.** Ctrl (Cmd on a Mac) + wheel or a pinch zooms; `-` / `%` / `+` / Fit on the canvas;
`0` or a double-click on the background fits. Fit never goes under 75 %: past that the map pans, from main. A zoom you
made by hand stays when you open or close the list drawer; Fit makes it automatic again.

## Adding

Open **Agents and workflows** from the bar: a slim list, your agents (this project's, then the starters) and then the
workflows. Every row has a grip and **Add**; Enter on a row adds it.

- **Add** (or Enter) puts it under **Not connected yet**, the strip under the map: on this map, but nothing hands it
  work yet. It costs nothing until it is connected.
- **Drag** a row over the map: the drop places light up and say what a drop does -- a box says "drop: main hands work
  to it" (or "drop: <box> hands work to it"), the strip says "drop: add, connect later". Dropped on a box, it is added
  with a line from that box and its When card opens at once.

![A row dragged over the map: each box and the strip say what a drop there does](media/studio-map-drag.png)

## Connecting

Every box has a **connect dot** on its right edge (a box under Not connected yet: on its left). Drag the dot to another
box, or click it (Enter on it) for a list of the boxes it may hand work to. A box's dot dropped on another box means
"this hands work to that"; a waiting box's dot dropped on main (or any box) means "main hands work to it".

The **When card** opens at the new line:

| When | It means |
|---|---|
| Always | every task this box finishes (from main: every task main hands on) goes there first |
| When the task needs: a PDF, an image, audio, video, code, a review | the task (and its files) needs one of them -- the router's own reading of a task |
| When the task says: words | the task says one of the words (a whole word) |
| Only when I ask | only when the person names it |
| Main decides per task | no rule: main picks among everything it can hand to (the old Auto pool) |

**Save** writes it; **Cancel** on a line you just made takes it back out. Click a line's label to change its When or
**Take the line out** (the box then waits under Not connected yet). Chains are allowed (main -> plan -> code -> reviewer):
the runtime follows them itself ([Chains](CREW-sessions.md#chains)). A line that would make a circle is refused in
one sentence, on the page and by the route: a loop lives inside a workflow as "repeat until".

![The When card at a new line](media/studio-map-when.png)

**A workflow box** opens in place when you click it: its steps (the same read-out as the Workflows tab) and a link,
"open it in Workflows", to change them; nothing is wired inside it here. An agent box opens to what it may use and how
careful it is, with a link to its form.

## Every change saves, with Undo

Each change -- a box, a line, a When, a line taken out, a new map -- is saved at once, and a receipt line says what
changed with **Undo**. It is the builder's own undo store (`~/.halo/crew/.undo/`, the last 20): Undo puts the file back
byte for byte. A starter map is saved as yours, under its name, on its first change; a trusted project's map stays the
project's.

## More than one map

The switcher at the top left lists your maps, this project's first ("this project's", a trusted folder's
`.halo/crew/maps/`), then the starters (`starter`: main decides per task among seven agents; `ship-it`: main -> plan ->
code -> review), and **+ New map** (a name, then main alone). Beside it is the one switch, **My sessions use this**:
new sessions run on that map (config `crew.map`; `halo maps use <name>` writes the same). A running session keeps the
map it started with. **Lock** (off by default, kept in this browser) stops every change: no dot, no Add, no label card.

## The builder on this tab

The box at the foot: "Say how things should connect, or ask why something happened". "send anything touching auth to
my-reviewer after the code workflow" comes back as one preview -- a line for the box, a line for the line with its When
in words (and, on a starter, the copy that makes it yours) -- drawn on the map as a dashed ghost box and a dashed line
with its label. Untick what you do not want, **Apply**, **Undo**. One request may touch agents, workflows and the map:
it is one preview. "what is my map?", "show me my workflows" or "why did reviewer run?" are answered from `studio_show`
with no change lines ([STUDIO-builder.md](STUDIO-builder.md#on-the-map-tab)).

## Routes

| Route | Answer |
|---|---|
| `GET crew/maps` | `{maps: [{name, scope, in_use, boxes, lines, problems}], in_use, source}` -- one row per name, nearest first |
| `GET crew/map/<name>` | `{map, scope, path, writable, in_use, problems, boxes: {id: {kind, names, facts}}, main}` |
| `PUT crew/map/<name> {map}` | save (a new name makes a map): `{undo_id, map, ...}`; 422 with the problem lines (a circle named) |
| `POST crew/map/<name>/use {on}` | config `crew.map`: `{undo_id, in_use}` |
| `DELETE crew/map/<name>` | yours only (a starter or the project's: 409) |

Every write is owner-only and keeps its before-image (`POST builder/undo {undo_id}` puts it back).
