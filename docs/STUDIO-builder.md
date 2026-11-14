# Studio: Agents -> 1 · Agents and the builder (3.6.0.0)

Read this when you make or change an agent in Studio's Agents tab, ask the builder box to do it for you, try an agent once before you use it, or want to know what the builder can and cannot change, what it costs and how Undo works.

Part of [Halo Studio](STUDIO.md), which lists every part; the section's other views are [Studio: Agents](STUDIO-agents.md).

![The Agents tab: the list on the left, an agent's form, Try it's result, the builder docked below](media/studio-agents-tab.png)

## The tab

`Alt+2` opens Agents on **1 · Agents** -- on **Live** instead while a session runs here (the design's "the Map while a session runs"; Live is this round's running picture), and on the tab you used last after that; `1` from anywhere in the section. The old
views stay one click away in the same switch: **Cast**, **Live** and **Workflows** (a link or door that names one,
such as `?mode=agents` or `&view=live`, still opens it). `?mode=agents&view=crew` opens this tab.

- **The list** (a drawer on the left, open with the tab): **+ New agent**, then **Yours** (yours and this project's;
  `new` when made in the last day, `not used yet` when no workflow or map names it, `problem` when the file has one),
  then **Starters to copy**: a click copies a starter into the form as yours, not saved yet.
- **The form**: name (and where it is used), **what it does**, **Write it for me**, the instructions it gets, the
  **model** (the shared picker; **Auto** is its first row), **what it may use** (a switch per kind of tool, each with
  what it can do on and what it cannot off), **how careful**, **Try it**, **More** (fallback model, effort, thinking,
  turns, minutes and dollars a task, files it always reads, its own worktree, offline, its check) and the save bar:
  **Save**, **Discard changes**, **Copy**, **Delete...** (it asks on the page; while a workflow or map names the
  agent it says which, and nothing is deleted). Nothing is written until Save.

## Try it

A test request runs the agent **once, as the form holds it now** (saved or not), as a real agent:

1. Before you send, the line under the box says what one typical task costs on its model (about 20k tokens in and 2k
   out at the catalog's price; with Auto, the model is picked when it runs and the cost shows after).
2. The run is `halo -p` as that agent (`--agents` with its definition, `--agent <name>`) in a **throwaway copy**: a
   detached git worktree of the project's last commit in a temp folder (an empty temp folder when the project is not
   a git repo), removed when the run ends. Your working tree is never touched.
3. Its **careful** mode is the run's permission mode. A print run cannot wait for you, so an ask is answered no and
   listed under the result ("asked: Bash ... answered no"); `own` runs it.
4. **Stop** ends it. The result shows in the tab: the reply, the tools it used, its time and cost, where it ran.
5. A run that ends while you are not looking (another section, another tab) is an **Attention** row ("Try it
   finished: <agent>"): open takes you to the agent and its result; set aside, or seeing it in the tab, clears it.

## The builder

The box docked at the foot of the tab. Type what you want ("make a security reviewer that reads pull requests on
GitHub"; "make it stricter"; "write the instructions for security-reviewer") and press Enter. Its conversation opens
above it after your first request and never by itself; the browser keeps it (the last 40 lines).

**What it can change: your agents' files, nothing else.** Its tools are `agent_make`, `agent_change`, `agent_copy`,
`agent_remove` and `agent_draft_instructions` (halo_harness/crew/tools.py). It has no tool to run a command, read or
change a project file, or reach the web; asked for one, it says what it would need instead (paste the text into the
box). Workflows and maps come with their tabs.

**Preview, Apply, Undo.**

![The builder's preview: one line per change, the widening lines amber and unticked](media/studio-builder-preview.png)

- A reply that would change something is a **preview**: one line per change, each with a tick, and a new agent shown
  as a dashed row in the list.
- A line that **lets an agent do more** is amber and **never ticked for you**: a tool beyond reading (change files,
  run commands, the web, a skill, a connected tool), a less careful mode, a higher or no money cap, offline turned off.
  The server marks it so, and Apply writes only the lines you sent ticked, so a description, a pasted page or the
  model's own words cannot tick one.
- **Apply** writes the ticked lines (each result is checked against the agent format first; nothing is written when
  one fails) and a receipt line offers **Undo**, which puts every file it touched back byte for byte (a file it made
  goes). The last 20 applies can be undone (`~/.halo/crew/.undo/`). **Discard** drops the preview.
- **Write it for me** fills the box with "Write the instructions for <name> from what it does". For a saved agent the
  draft is a change line; for one not saved yet it goes into the form when you Apply (still nothing saved).
- A question it cannot settle comes as two or three choices, its recommendation first.

**Its model and its cap.** Settings -> Studio -> Builder: `studio.builder.model` (unset: the strongest reasoning model
your model index names, else your main model) and `studio.builder.cap_usd`, what it may spend in a day (default
$1.00). The line beside the box shows the model, "about $0.01-0.03 a request" and today's spend against the cap. The
cap is kept by the server: a request past it answers with one line on how to raise it, and a turn that reaches it
stops there. A call with no catalog price counts at $3 / $15 per million tokens; a local model at nothing.

## Routes

Every write is owner-only (the owner proof, [the shell](STUDIO-shell.md)).

| Route | What |
|---|---|
| `GET crew/agents` | `{agents, starters}`: name, does, model, uses, careful, scope, new, used, problems |
| `GET / POST / PUT / DELETE crew/agent/<name>` | read, make, save, delete one of yours (422 with the problem lines; 409 for a starter or a name in use) |
| `GET crew/workflows`, `GET crew/maps` | the rows of those kinds (read-only this round) |
| `GET crew/estimate?model=<ref>` | `{usd, line}` before a Try it |
| `POST crew/try {kind: agent, body, request}` | starts a run: `{try}`; `crew` frames on `/api/events` |
| `GET crew/try/<id>`, `POST crew/try/<id>/stop`, `POST crew/try/<id>/seen` | the run's record, Stop, seen |
| `GET builder` | its model, the typical cost, today's spend, the cap |
| `POST builder/ask {tab, selection, text, conversation_id, history}` | one turn: `{reply, question?, changes, cost_usd, meta}`; 429 past the cap |
| `POST builder/apply {conversation_id, change_ids}` | writes the ticked ids: `{undo_id, wrote, removed, skipped, filled}` |
| `POST builder/undo {undo_id}` | `{restored}` |

The files: [Crew files](CREW-FORMATS.md). Tests: `tests/test_crew_formats.py`, `tests/test_builder_flows.py`,
`tests/test_builder_injection.py`, `tests/test_crew_try.py`, `tests/test_studio_crew.py` (Chrome), and the room rules
over this tab in `tests/test_studio_room.py`.
