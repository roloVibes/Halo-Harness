# How a session runs on a map (3.6.0.0)

Read this when you want to know what a map does to a session: what compiles to what, which agents and workflows main may hand work to, when an edit to the map takes effect, how a chain is followed, what the map's money cap stops, or how a session with no map runs.

The map is drawn on [Studio's Map tab](STUDIO-map.md) and kept as a `map/1` [crew file](CREW-FORMATS.md#a-map-format-map1).

## Which map

A session runs on a map when one is named: `halo --map <name>` for this one run, else config `crew.map` (Studio's
**My sessions use this**, `halo maps use <name>`). With neither, a session runs exactly as before maps (its lineup,
`docs/ROLES.md`). A map in use replaces the lineup for that session. Each session row (Studio's sessions, `GET fleet`)
carries `map`: the map it started with.

## What compiles to what

At session start `halo_harness/crew/compile.py` reads the map and the agent and workflow files it names (yours, this
project's in a trusted folder, the starters: nearest wins) and makes three things the loop already runs:

1. **Main's session config** (from the map's `main`, the starter `main` by default): its model (`auto`: the session's
   own model, as today; a model ref pins it when no `--model` is given), its instructions (added to the system prompt),
   its tools (the kinds its `uses` does not list -- read, edit, bash, web -- are taken out; every other tool stays) and
   its permission mode from `careful` (ask-changes: default, ask-commands: acceptEdits, own: auto; a `--permission-mode`
   flag still wins).
2. **The hand-off table**: one entry per line from main, `{line, box, kind: agent | workflow, name, when}` (a box that
   names a list of agents is one entry per agent). The existing **Agent** tool spawns exactly the agents main has a line
   to; the existing **Workflow** tool runs exactly its workflows (on the step runner); a tool with nothing to hand to is
   not offered. Each tool's description names the targets and their When in words.
3. **The agent specs**: each agent file as the spec `agent/subagent.py` spawns (`crew/spec.py`), its role its own name:
   an `auto` agent's model is picked per task by `models_auto` with the agent's `needs` (images -> vision, long-text ->
   long-context, pdf, audio, video, reasoning, tools), exactly as a lineup card's `models.needs` was. The child is never
   more permissive than the session (subagent.py clamps it).

`crew/map_control.py` holds the result where a lineup was (`team_control`), so the loop, the spawn and the model pick
ask it the same questions.

## Routing a hand-off

Main names a target (`subagent_type` on Agent, `name` on Workflow), or names none and the first line from main whose
When fires routes it: `always`; `needs` (the router's reading of the task and its files: a PDF, an image, audio, video
named or attached; the asks plan / review / research; code, reasoning and long-text as words); `says` (a whole word of the
task); `ask` (the person named it). "Main decides per task" never routes by itself: main picks. A target with no line
from main is one line back to main naming the ones it has; an `ask` line the person did not name is one line too.
Every hand-off's receipt names the line that fired:

    map ship-it · line main -> plan (always) · plan

## Chains

A line from a box (not main) is a chain. When a target finishes, the runtime follows that box's lines itself, in the
map's order, before main gets the result: an `always` line, or a `needs` / `says` / `ask` line checked against the task
and its files (and the person's last message) -- deterministic, never a model call; a `main-decides` line is not followed.
The next target gets the task and what the last one handed back (as data). Each hop adds its receipt, and a line not
taken says why:

    map ship-it · line plan -> code (always) · code
    map ship-it · line code -> pdfs not taken (skipped: the task needs none of pdf)

The map has no circle (the format refuses one), so a chain ends. A box with two lines into it runs once per hand-off
that reaches it; it does not wait for both. A hand-off run in the background is not followed.

## When an edit takes effect

The map is compiled again before each hand-off when its file changed (an mtime check): a line, a When or a new box
applies at the next hand-off, and the session says "your map changed: lines and boxes apply at the next hand-off" once.
An agent already working keeps what it started with; main's own model, instructions and tools change with the next
session. A change that leaves the map with a problem keeps the last good one and says the problem once.

## A map with a problem

A missing agent or workflow, a file with problems, or a circle: the session does not start half-configured. It says
the problem lines (on stderr: "halo: the map <name> has a problem, so this session runs as with no map:" and one line
each) and runs as with no map; Studio's Map tab shows the same lines over the map.

## The cap

`caps.session_usd` on the map is the session's money cap: main's spend and every hand-off's (chains and workflow steps
included), checked before each hand-off. Reached, hand-offs stop with one plain line -- "the map ship-it's session cap
($20.00, caps.session_usd) is reached: $20.0137 spent; no more hand-offs this session (raise it in the map, or start a
new session)" -- and main carries on itself. It is a budget the person set, nothing else.

## In a session: the builder's tools

The terminal and Studio's sessions also offer main the builder's own tools (the `Builder` tool, one implementation:
`crew/tools.py`): "make me a reviewer agent and hand reviews to it" goes through the same preview as Studio's builder,
as one approval card -- the lines that let no agent do more in one question, each widening line its own question with
No first. Only what the person picks is written; the result names the undo id; Studio follows the files. Print mode has
no one to answer, so it previews and writes nothing ([STUDIO-builder.md](STUDIO-builder.md#in-a-session)).
