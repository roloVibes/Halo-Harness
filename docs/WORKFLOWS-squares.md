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

## When

Halo 3.3.16.3. A square on a lineup's board has a **when**: the rule for when main hands it work, carried by the line
from main to its block in Studio. A lineup's `workflows:` item is a plain ref (today's meaning: the square's `covers`
against the gaps) or a mapping with its rule:

```yaml
workflows:
  - media                                         # plain: its covers (pdf, vision, audio, video)
  - {ref: review, when: {words: [review, audit]}} # when the task says review or audit
  - {ref: thinking, when: {mode: always}}         # always first, before main answers
  - {ref: my-media, when: {needs: [pdf]}}         # when main needs a PDF read (its covers narrowed)
```

| `mode` | When the router hands it work |
| --- | --- |
| `auto` (the default) | a hand-off whose gaps meet `needs` (the square's covers narrowed; none given = its covers), or whose task says one of `words` (a whole word, any case) |
| `named` | only when main asks for it by name (`Workflow(name: ...)`) |
| `always` | first: a hand-off that names no need goes to it before any other square, and the Workflow tool's description tells main to hand it the task before it answers |
| `off` | not connected: it stays on the board (dashed in Studio, listed in Problems) and main never uses it, not even by name |

The order for a hand-off that names no need: an `always` square, then a square whose words the task says, then the
needs pick above. A hand-off with `need` goes by the need. The receipt's reason names the rule that fired
(`handing the PDF to media: when main needs pdf`) and the receipt carries it as `rule`; a plain ref keeps today's
reason. On the auto lineup (no lineup file) the rules live in config, `workflows.when.<ref>` beside
`workflows.enabled`. `halo workflows enable <ref> --when needs=pdf,audio | words=review,audit | named | always | off |
auto` writes it, `halo workflows when <ref>` prints it, `halo workflows list` and `/workflows` show a `when:` column, and
`halo teams show` prints a `block <ref> (square): when ...` line per square. A tier's reach stays its `routing` words and
its cards' `use_for`.

## Block templates

Halo 3.3.16.3. Blocks you can start from, shipped as small YAML under `halo_harness/templates/blocks/`; each is a square
or a tier, and every agent in it sits on an `auto` model (a square member's `model: auto`, a bio whose
`models.preference` is `auto` with the `models.needs` that fit the purpose), so no template names a provider you did not
set up -- pin the models afterwards (the block's Agents page, or the file).

| Template | Kind | Inside |
| --- | --- | --- |
| `thinking` ("thinking: three reasoning models") | square | auto-planner leads, auto-reviewer and a second auto-planner weigh the call (needs: reasoning) |
| `media` ("media: read PDFs, images, audio and video") | square, adds as `media-team` | auto-media leads, auto-researcher for the long ones, auto-writer for the answer |
| `review-panel` ("review panel of three") | square | auto-reviewer leads, auto-planner on the approach, auto-coder on the code |
| `local-workers` ("local workers") | tier | local-coder, local-writer, local-ops on bios that ask for nothing, so Auto picks the cheapest model that fits (a free or local one first) |

A square template writes a square of YOURS (`~/.halo/workflows/<name>.yaml`; the template file stays as shipped) and
enables it, wired to main by its covers. A tier template adds its agents (an alias already taken gets a `-2`), a tier
below the lineup's last one with its purpose, and the routing words the lineup does not have yet; a shipped lineup is
copied to yours under its name first (as Studio's Save does), a pack's is never written, a lineup with no tiers says to
add one first. `halo blocks list | add <template> [--as <name>] | show <name>`; in Studio the library's "Blocks you can
start from" ([STUDIO-blocks.md](STUDIO-blocks.md)).

## Who is inside a square

An agent dragged into a square block in Studio joins its `lineup.members` on `auto` (`PUT workflows/members {ref,
add}`); one dragged out leaves (`remove`; the last agent cannot -- the block's `x` takes the block off). A square of
yours or the project's is written in place; a shipped or a pack's square is copied to yours first as `my-<name>`, the
lineup's board swaps to the copy and keeps its rule, and the confirm card and the result line both say so.

## Commands

`halo workflows list | show | enable [--when] | disable | when | test | new | check | run`, `halo blocks list | add | show`
([COMMANDS-workflows.md](COMMANDS-workflows.md)); the TUI's `/workflows`
prints the same lines ([SLASH-COMMANDS-tui.md](SLASH-COMMANDS-tui.md)).
