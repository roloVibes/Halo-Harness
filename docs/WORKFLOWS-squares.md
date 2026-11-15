# Workflow squares

Read this when you want the main agent to hand a task to a saved workflow (a square): the contract, where squares come from, how the router picks one and the receipts.

Halo 3.3.16.0 R3. A **square** is a workflow with a contract: one unit the main
agent can hand a task to when the task needs something the session's model
cannot do (read a PDF, look at an image, hear audio) or asks for a plan, a
review or research. The square names what it takes and what it gives, the
needs it covers, the agents and models it runs on and its limits. The main
agent never picks a model for it: it points at the square, and the square's
own lead does the work. The file is the workflow file you know
([WORKFLOWS.md](WORKFLOWS.md)) with a few more keys at its root; an old file
keeps working as it was.

## The contract

```yaml
name: media
does: Reads and makes images, audio, video and PDFs for a model that cannot, and hands back what it found.
takes: [text, files, pdf, images, audio, video]   # what the square accepts
gives: [text]                                     # what comes back; no gives = not a square
covers: [pdf, vision, audio, video, media]        # the needs it answers
lineup:
  lead: {bio: auto-media, model: auto}            # or a lineup name: `lineup: quality`
engine: session                                   # session | orchestra | mission
budget: {band: low, cap_usd: 1}
limits: {depth: 1, turns: 30, wall_s: 900}
inputs:
  task: {type: text, required: true}
  files: {type: text, default: ""}
stages:
  - id: look
    role: auto-media
    brief: "{task} Files: {files}."
```

| Key | What it says |
| --- | --- |
| `does` | One sentence. `description` stays its alias for old files. |
| `takes` | What the square accepts: `text`, `files`, `pdf`, `images`, `audio`, `video`, `urls`. |
| `gives` | What comes back: `text`, `files`, `report`, `repo-change`. Required for a square, and checked when the square returns. |
| `covers` | The needs it answers: `pdf`, `vision`, `audio`, `video`, `code`, `plan`, `research`, `media`, `review`, `work-data` (Auto's need words where they overlap). |
| `lineup` | The bios on their models (`lead: {bio, model}`, `members: [...]`), or a lineup name. |
| `engine` | `session`: one agent on the lead, no worktree. `orchestra`: the compile, a full Orchestra run. `mission`: runs as `orchestra` (3.5.0.0: the word stays readable). |
| `budget` | `band` (low, mid, high) and `cap_usd`, the most one hand-off may spend. |
| `limits` | `depth` (default 1), `turns`, `wall_s`. |

The root `takes` and `gives` are the square's contract. A stage's `takes`
(`[{from, take}]`) and `gives` (`[{name, kind}]`) stay what they were: the
hand-offs between its stages. A hand-off written at the root gets one line
saying it belongs on a stage. A workflow without `gives` is not a square: it
lists and runs as before, and the router never picks it. Once a file says any
other contract key, `gives` is required (`halo workflows test` and a pack's
manifest check say so in one line).

## Where squares come from

Four places, in this precedence:

1. yours: `~/.halo/workflows/<name>.yaml`
2. the project's: `.halo/workflows/<name>.yaml`
3. a running pack's: `contributes.workflows`, named `<pack>/<name>` ([PACKS.md](PACKS.md#a-packs-squares))
4. the shipped ones: `media`, `plan`, `code`, `review`, `research`

A bare `<name>` resolves yours, then the project's, then the shipped one;
`<pack>/<name>` names a pack's. `halo workflows new <name> --from <square>`
copies a square into yours, where you can change it.

**A project's squares need a trusted folder (3.4.1.2).** A cloned repo's `.halo/workflows/` is read only when you
trusted the folder, and a project file never takes a shipped name (`media`, `plan`, ...) or a pack's: the shipped
square is used and `halo workflows list` says, one line per file, which project file is not used and why. A square on the `orchestra`
engine that the `Workflow` tool starts runs its lanes in the session's own permission mode and under its rules (never
a fixed `auto`), and a `verify.test` that a project file wrote is decided as a Bash
call first -- your deny and ask rules, the pack policies, your hooks -- and runs only when that call would be allowed.

| Shipped | Covers | Engine | Gives |
| --- | --- | --- | --- |
| `media` | pdf, vision, audio, video, media | session (lead `auto-media` on `auto`: the square's own Auto pick for the modality) | text |
| `plan` | plan | session | text |
| `code` | code | orchestra (build, then review) | repo-change, report |
| `review` | review | session | text |
| `research` | research | session | text |

**Enabled for a session.** A square works only when it is on: config `workflows.enabled` names the squares a
session may use ([CONFIG.md](CONFIG.md)); the default is the shipped `media` square on and the rest off, and `[]` is
none, on purpose. With no square on, the `Workflow` tool is not offered at all. `halo doctor` says which squares are on
(`Squares a session enables: media (config workflows.enabled)`). 3.6.0.0: lineups are gone, so a lineup's own
`workflows:` list is not read any more, and `halo workflows enable` went with them: set the config key
(`halo config set workflows.enabled ...`, or Studio's Settings).

## The router

One tool, `Workflow(need | name, task, files)`, on the main agent and on every
agent allowed `Agent` (an agent allowed `Agent` is allowed `Workflow`).

- With `name`: that square (it must be on).
- With `need`, or neither: the gaps. Halo reads the task and its files the way
  Auto does (a PDF, an image, audio or video in the task or its files; the
  words plan, review, research in the ask) and takes away what the current
  model takes (the `takes` column `/model` shows: a model whose inputs are not
  known counts as text only). The enabled squares whose `covers` meet the gaps
  are the candidates; the one covering the most wins, then the one whose band
  is nearest the session's, then the first enabled.
- **The session's own roles before a plain square** (3.3.16.2,
  `workflows/lineup_roles.py`). When a helper of the session (a plain session's `media` card, or a role of yours) covers
  every read the task carries (a PDF, an image, audio, video) and the task
  names no plan, review or research, the task goes to that role, the Agent
  tool's way (`role: <alias>`, its model, rules and budget), and the receipt
  says `role media · in pdf (report.pdf) · ... -- handing the PDF to your
  media role: the lineup covers it`. A role covers a read when it is media
  work (the alias or role `media`, or its bio's `kind: media`: every read) or
  its bio's or card's `models.needs` / `models.capabilities` name it (`files`
  reads as pdf). A square named with `name`, or one whose `when` you set
  ([When](#when)), still goes to the square.
- One line says why: `handing the PDF to media: your model takes text only`.
- Nothing covers it: one line says what would -- `no role or square reads PDFs
  here (could not read report.pdf): add media to config workflows.enabled, or give a
  role a model that takes PDFs` -- and the main model goes on with what it can
  do. The router never opens a dialog.

### The order

Explicit beats implicit (`workflows/router.py` `route`, 3.3.16.2 + 3.3.16.3):

1. A square asked for by **name** runs. One whose when is `off` does not: the
   line says it is not connected and how to connect it.
2. A square whose **explicit when** fires takes the task: `always` first, then
   `words` the task says, then `needs` that meet the gaps. You drew that
   connection on purpose, so it wins over a role; the receipt carries the rule
   as `rule` (`when main needs pdf`).
3. Otherwise a **helper of the session** that covers the need takes it: `handing
   the PDF to your media role: the lineup covers it`.
4. Otherwise a square with a **plain ref** (no when, or `auto` with no `needs`
   and no `words`) whose `covers` meet the gaps takes it: today's pick and
   today's reason.
5. Otherwise the one line that says what would cover it.

A square in mode `named` is used only by 1; one in mode `off` never. The squares
config `workflows.enabled` turns on are plain refs unless `workflows.when` gives one a rule, so on a plain
session a PDF still goes to its own media helper (3) unless you give the media square an explicit when. The
`Workflow` tool is offered when at least one square is on and not every one of
them is `off`.

The run follows the engine. `session` spawns one agent the way the Agent tool
does, with the lead bio's prompt, the task and the files' names, on the lead's
model (`auto`: picked for the gaps). The child shares the parent's permission
engine and rules, so it never runs more permissive than the session.
`orchestra` compiles the square with `task` and `files` as its inputs and runs
the goal, waiting at most `limits.wall_s`. What comes back is checked against
`gives` (a `report` square must return an artifact, a `files` square a list of
paths that exist); a miss is one line on the receipt.

**Bounds, enforced in the tool.** `limits.depth` counts the hop into the
square: inside a square of depth 1 the Workflow tool answers that no further
square is allowed; depth 2 allows one more hop, and so on (never more than the
caller has left). The budget cap is the square's `cap_usd` or the session's
remaining lineup budget, whichever is less; nothing left means the square does
not start ("budget hit"). A running session square is stopped when its cost
passes the cap, its wall time passes `limits.wall_s` or its turns pass
`limits.turns`.

## Receipts

Every hand-off is written where you look:

- **the transcript**: one `receipt` node in the session's log (never sent to a
  model): which square, what went in (the need and the files' names, never
  their content), what came back, the cost and the one line. The tool's answer
  starts with the same line: `square media · in pdf (report.pdf) · back text ·
  $0.0200 -- handing the PDF to media: your model takes text only`;
- **the Live tree**: the square is a node under the agent that called it, its
  name in mono and the lane colour of its engine, its cost beside the
  session's;
- **the cost**: a session square's agent rolls its spend into the session the
  way every sub-agent does; an orchestra square's run cost is added once. The
  Session's Cost panel shows a `squares` line when any ran;
- **an Orchestra run**: when a lane hands off, the run's report lists the
  squares it used, in order (`squares: media (done, $0.0123) -> plan ...`).

## When

Halo 3.3.16.3. A square has a **when**: the rule for when main hands it work, in config
`workflows.when.<ref>` beside `workflows.enabled` (3.6.0.0: lineups, which could carry a rule per square, are gone).
No rule is a plain ref (the square's `covers` against the gaps); a rule is a mapping:

```json
{"workflows": {"when": {"review": {"words": ["review", "audit"]}, "media": {"needs": ["pdf"]}}}}
```

| `mode` | When the router hands it work |
| --- | --- |
| `auto` (the default) | a hand-off whose gaps meet `needs` (the square's covers narrowed; none given = its covers), or whose task says one of `words` (a whole word, any case) |
| `named` | only when main asks for it by name (`Workflow(name: ...)`) |
| `always` | first: a hand-off that names no need goes to it before any other square, and the Workflow tool's description tells main to hand it the task before it answers |
| `off` | not connected: main never uses it, not even by name |

The order for a hand-off that names no need: an `always` square, then a square whose words the task says, then a
square whose `needs` meet the gaps, then a helper of the session that covers it, then a plain ref's covers
([The order](#the-order)). A hand-off with `need` goes by the need. The receipt's reason names the rule that fired
(`handing the PDF to media: when main needs pdf`) and the receipt carries it as `rule`.

## Commands

`/workflows` lists the workflows a session runs by name and the squares it enables; `halo doctor` has the squares
line. The crew workflows (steps of agents, `halo workflows list | show | new | edit | try | run`) are a different thing:
[WORKFLOWS.md](WORKFLOWS.md), [COMMANDS-workflows.md](COMMANDS-workflows.md).
