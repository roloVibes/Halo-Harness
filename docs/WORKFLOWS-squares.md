# Workflow squares

Read this when you want the main agent to hand a task to a saved workflow (a square): the contract, where squares come from, how the router picks one, the receipts and the Workflows board.

Halo 3.3.16.0 R3. A **square** is a workflow with a contract: one unit the main
agent can hand a task to when the task needs something the session's model
cannot do (read a PDF, look at an image, hear audio) or asks for a plan, a
review or research. The square names what it takes and what it gives, the
needs it covers, the bios and models it runs on and its limits. The main
agent never picks a model for it: it points at the square, and the square's
own lineup does the work. The file is the workflow file you know
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
| `engine` | `session`: one agent on the lead, no worktree. `orchestra`: the compile, a full Orchestra run. `mission`: across the fleet; it runs as `orchestra` while only this harness is here. |
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

| Shipped | Covers | Engine | Gives |
| --- | --- | --- | --- |
| `media` | pdf, vision, audio, video, media | session (lead `auto-media` on `auto`: the square's own Auto pick for the modality) | text |
| `plan` | plan | session | text |
| `code` | code | orchestra (build, then review) | repo-change, report |
| `review` | review | session | text |
| `research` | research | session | text |

**Enabled per lineup.** A square works only when the session's lineup has it
enabled. A lineup's `workflows:` list names the squares it may use (any ref).
The auto lineup (and a session with no lineup) reads `workflows.enabled` in
config ([CONFIG.md](CONFIG.md)); the default is the shipped `media` square on
and the rest off. `halo workflows enable <ref>` writes the active lineup's
list (the config key on auto); a shipped or a pack's lineup is read-only and
the line says to copy it first.

## The router

One tool, `Workflow(need | name, task, files)`, on the main agent and on every
bio its lineup lets delegate (a bio allowed `Agent` is allowed `Workflow`).

- With `name`: that square (it must be enabled).
- With `need`, or neither: the gaps. Halo reads the task and its files the way
  Auto does (a PDF, an image, audio or video in the task or its files; the
  words plan, review, research in the ask) and takes away what the current
  model takes (the `takes` column `/model` shows: a model whose inputs are not
  known counts as text only). The enabled squares whose `covers` meet the gaps
  are the candidates; the one covering the most wins, then the one whose band
  is nearest the session's, then the first enabled.
- One line says why: `handing the PDF to media: your model takes text only`.
- No square: one line says what could not be read, and the main model goes on
  with what it can do. The router never opens a dialog.

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

## The board

Studio's Agents section has a fourth view, Workflows (`W`,
`?mode=agents&view=workflows`): one card per enabled square, the library of
every square beside it, the inspector on hover or select. The rules it is built
by are in [STUDIO-agents.md](STUDIO-agents.md#workflows-the-board-of-squares-33160-r3).

## A square as a block (3.3.16.3)

On Studio's Cast a lineup's enabled squares are **blocks** beside its tiers ([STUDIO-blocks.md](STUDIO-blocks.md)): the title bar says the square's name and its DOES line, the block opens to show the bios of its lineup (the
lead, then `lineup.members`) on their models, and its footer says its limits and cost band. The block's **Purpose** page
writes `does` into a square of yours (`PUT workflows/contract {ref, does}`; a shipped or a pack's square answers how to
copy it: `halo workflows new <name> --from <square>`). On Agents -> Live a square's agent and the agents under it are
one group titled `square <name>` with the DOES line under it; the agent row's `square` carries `does` for that.

## Commands

`halo workflows list | show | enable | disable | test | new | check | run`
([COMMANDS-workflows.md](COMMANDS-workflows.md)); the TUI's `/workflows`
prints the same lines ([SLASH-COMMANDS-tui.md](SLASH-COMMANDS-tui.md)).
