# Teams: people, blocks and stages (Halo 3.0.8.0)

Read this when you set up a team file: who works on a repo, where their work lands and in which order.

A **team** is one file that says who works on a project, where their work
lands and in which order: the brief every agent reads first, the members,
the blocks (a file, a folder or a git tree, each with its own claim
ledger) and the workflow's stages. `halo team` runs it; Studio's Team routes
(`/api/team/...`) show it live.

## Where a team, a lineup, an Orchestra run, a flow and a mission sit

A **lineup** ([ROLES.md](ROLES.md)) is who can play which part: aliases
assigned to agent bios, with routing, budgets and tiers. An **Orchestra
run** ([ORCHESTRA.md](ORCHESTRA.md)) is several workers editing the same
files at once on one goal, merged and tested. A **flow**
([FLOWS.md](FLOWS.md)) is a fixed pipeline of steps (intake, roles, org,
render, confirm, post, metrics) with human gates. A **mission**
([MISSIONS.md](MISSIONS.md)) is one goal split across the harnesses of a
fleet. A **team** sits above them: its members are instances of lineup
aliases, its stages are agent turns, Orchestra runs or flows, a stage can
hand a member's work to another harness the way a mission part goes out,
and the blocks and the board tie it together: what each stage reads and
writes, who holds which part of a block, and what waits on whom.

**One unit of work (Halo 3.1.2.0):** a team stage is a *unit* of work, the same thing an Orchestra lane, a mission part and a flow step are, with one state machine, one ledger line, one report row and one coach; `halo work` prints a run's stages as that shared table. See [WORK.md](WORK.md).

## The file

`<repo>/.halo/team.yaml`, else `~/.halo/teams/<project>.team.yaml` (`<project>`
is the repo folder's name; the repo file wins). `halo team init` writes the
repo file from the shipped template and a starter `docs/BRIEF.md`.

```yaml
name: launch
brief: docs/BRIEF.md            # the one file every agent reads first
budget_usd: 2.0                 # 3.1.2.0: what the whole run may cost (see Budgets)
members:
  - name: writer                 # an instance name
    lineup: local-first          # a lineup (halo teams lists them)
    role: main                   # the alias inside that lineup (default main)
    harness: null                # null = here; a fleet member's name = delegated
blocks:
  - id: copy
    kind: folder                 # file | folder | git
    path: content/
    claims: section              # section | file | none (what a claim locks)
  - id: site
    kind: git
    path: .
    claims: file
workflow:
  stages:
    - id: draft
      kind: agent                # agent | orchestra | flow
      members: [writer]          # member names, lineup aliases or a tier name
      reads: [brief]             # block ids (brief is always readable)
      writes: [copy]
      trigger: manual            # manual | block_change:<block> | stage_done:<stage>
      lead: writer               # who merges and decides (default: the first member)
      gate: required             # required | optional | none
      acceptance: {prompt: "", expect: "non-empty"}
      prompt: "Draft the launch copy the brief asks for."
      settle_s: 20               # block_change only: quiet time before it fires
    - id: build
      kind: orchestra
      goal: {what: "...", done_when: "...", workers: 3}
      harness: null              # 3.1.2.0: a fleet member's name runs this orchestra (or flow) stage there
      budget_usd: 1.0            # 3.1.2.0: what this stage may cost, every round of it
      writes: [site]
      trigger: stage_done:draft
    - id: post
      kind: flow
      flow: social-post
      inputs: {}                 # the flow's intake
      reads: [copy]
      trigger: stage_done:build
```

Defaults: a block's `claims` is `section` (`file` for a git block), a
stage's `kind` is `agent`, its `trigger` `manual`, its `gate` `none`, its
`settle_s` 20. An orchestra stage's goal gets a STOP WHEN, the files of its
write blocks and the lead's lineup when it does not name them.

`halo team validate` (and `validate_team` in `halo_harness/team/spec.py`)
lists every problem as one line: unique member, block and stage ids; each
member's lineup exists and has its `role` as an alias; a block's kind and
claim mode, its path inside the repo (an existing path has the block's kind,
a missing one can be created, a git block sits in a git tree); each stage's
kind, members (a member name, an alias some member plays, or a tier of the
members' lineups), lead, reads and writes (block ids), gate and trigger
(`stage_done:` names an earlier stage, `block_change:` a declared block);
no trigger loop (a stage whose writes, directly or through later stages,
start it again); an orchestra stage's goal; a flow stage's flow loads; and
the lineup preflight's blocking findings for every member that runs here
(`preflight: member `writer` (lineup `x`): ... -- fix: ...`).

## Blocks and claims

Each block keeps a ledger: `<block>/.halo-block/` for a folder or git
block, `<dir>/<name>.halo-block/` beside a file block. It is never
committed (a `.gitignore` of `*`).

* `claims.jsonl` -- the Orchestra's claim log. Keys by the block's mode:
  `section:<relpath>` (a whole file) and `section:<relpath>#<heading-slug>`
  (a markdown heading; a function or class in code) under `section`,
  `file:<relpath>` under `file`; `none` takes no claims and only logs.
* `changes.jsonl` -- one line per write: `{ts, by, member, stage, op, key, summary}`.
* `state.json` -- `{block, last_change, holders: {holder: [keys]}}`.

A holder is `<member>@<stage>`. While a stage runs, each member's session
carries `HALO_TEAM_SCOPE` and its permission engine checks every Write,
Edit, MultiEdit and NotebookEdit inside the repo: a path whose innermost
block is not one of the stage's `writes` (or in no block, or in a ledger)
comes back with the block and the stage's write blocks named; a part another
holder has comes back naming the block, the key, the holder and when the
claim runs out; otherwise the member claims each free part by writing it,
the claim moves to `writing`, and the write lands in `changes.jsonl` and the
run's log. When the stage ends, its claims are released. Paths outside the
repo keep their usual decision. `halo team blocks [block]` shows the
holders and the last changes.

## Stages, triggers and gates

A run lives in `<repo>/.halo/team/<run-id>/`: `board.json` (each stage's
state pending, ready, running, gated, done, failed or skipped, its members,
lead, started, ended, cost, summary, error, round and gate answer; 3.1.2.0:
`members_state`, `remote` and `budget`, below),
`events.jsonl` (kinds state, claim, change, gate, trigger, report, note)
and `stages/<id>/` (refs.json with the agent session ids, the Orchestra run
id or the flow run id; handback.md; result.json; gate.json and answer.json;
one scope file per member).

* `manual` -- `halo team run <stage>` (or Studio's Run).
* `stage_done:<stage>` -- that stage reached done; with a gate, once it is
  answered `accept`.
* `block_change:<block>` -- the runner watches the block (its
  `changes.jsonl` and its files); a change opens a `settle_s` window, a
  further change restarts it, and when the block has been quiet that long
  the stage fires, once per window.

An **agent** stage runs every member that is not the lead at the same time
(3.1.2.0, `team/parallel.py`: a thread pool bounded by the tightest
`max_parallel` of their lineup tiers; no tiers, all at once, at most 8),
then the lead with their hand-backs to merge. The row's `members_state`
(`{name: ready | running | waiting | done | failed | skipped}`) carries each
member's state and every move is a `state` line, so Studio's board draws a
dot per member. A member that fails does not stop the others: once they
end the stage fails, naming it, and the lead does not run. Each gets one prompt:
the brief, each block it reads (its path, `state.json` and the last ten
change lines), the blocks it writes, the stage's `prompt` and, on a redo,
the redo's text. Locally a member is `halo -p --team <lineup> --agent <bio>`
in the repo. An **orchestra** stage starts an Orchestra run with the goal;
a **flow** stage starts a run of the named flow with `inputs` as its
intake (its own gates answer with `halo flow answer`).

When a stage ends: a failed result fails it; a `required` gate holds it at
`gated` with `stages/<id>/gate.json` (the acceptance's result shown with it)
until `halo team answer <stage> accept|redo|stop`: accept marks it done and
starts its `stage_done` stages, redo runs it again with `--text` as the
instruction, stop ends the run (every stage not done is skipped). Without a
required gate a failed acceptance fails the stage; an `optional` gate opens
too but does not hold the next stage. `acceptance` runs as a lineup's
pipeline stages do: `expect` checked on the stage's result (`non-empty` or
a word it must contain).

## Delegating a member to the fleet

`harness: <name>` sends that member's task to that harness of the fleet
([FLEET.md](FLEET.md)) instead of running it here. It goes the way a mission
part does ([MISSIONS.md](MISSIONS.md)): the hub on this machine (`halo
studio --fleet` or `halo fleet serve`) sends `run_task` to one of the
member's live sessions (a TUI session first), so under `fleet.allow_control:
ask` its owner sees the card. The answer sets the stage's `waiting`: 200
running, 202 asked (the owner's card is open), 403 refused (the stage fails
with the member's reason). Each delegated member is a one-part mission in
the hub's store (it also shows in `halo fleet mission status`); its
hand-back comes back into that mission folder and the stage goes on. A
member's harness writes its files there under its own permission engine.

An **orchestra** or **flow** stage with `harness: <member>` (3.1.2.0,
`team/remote_stage.py`) goes the same way: a one-part mission whose part is
`kind: orchestra` (its `run` the stage's goal) or `kind: flow` (the flow's
name and inputs). The member runs `orchestra.run` in its checkout of the
repo (or `flows.run`) and hands back `result.json`, the run's `report.json`
(it lands in `stages/<id>/report.json`) and its one line. The row's
`remote` is `{harness, kind, mission, part_state, run}`: asked (the owner's
card is open; the stage's unit is `waiting`), running, then done or failed
with the remote run id; the board shows the harness chip and that id. A
refused dispatch fails the stage with the reason. The finished branch of a
remote Orchestra run stays in the member's checkout, named in its report.

A delegated agent stage (with its gate answered on the hub) and a delegated
flow stage are exercised against a real second machine by the scripted
two-machine check ([FLEET.md](FLEET.md) "The two-machine check",
`tools/live_fleet_check.py`, 3.1.2.0 R3).

## Budgets

Halo 3.1.2.0 (`team/budget.py`). `budget_usd` on the team file caps the
whole run, on a stage that stage (every round of it). Before a stage starts
its forecast is added to what was spent: the run's cost so far against the
team's line, the stage's own cost so far against its line. The forecast:
an agent stage, one turn per member at the member's model's catalog price
(60k in, 6k out tokens; $0.10 for a model the catalog does not price); an
orchestra stage, the Orchestra forecast of its goal
([ORCHESTRA.md](ORCHESTRA.md#the-forecast)); a flow stage, its steps'
`budget_usd`. Over a line the stage does not start: its row goes back to
`pending` with `waiting: "budget: ..."` (and `stages/<id>/budget.json`), and
Fleet's Attention queue shows a `team_budget` row: **Raise** opens the team
file (edit `budget_usd`, run the stage again: the file is read each time),
**Skip** skips the stage (`POST team/budget {stage, action: skip}`),
**Stop** stops the run. `halo team status` shows what was spent, the
forecast of the stages still to run and the budget.

## The CLI

```sh
halo team init [--force]
halo team validate [--json]
halo team run [stage] [--force] [--new] [--run ID] [--watch] [--json]
halo team status [--run ID] [--json]
halo team board [--run ID] [--json]
halo team answer <stage> accept|redo|stop [--text T] [--run ID] [--json]
halo team stop [--reason R] [--run ID] [--json]
halo team log [--since N] [--run ID] [--json]
halo team blocks [block] [--json]
```

`run` checks the file (exit 2 on a problem), runs the lineup preflight for
every member that works here (exit 2 with each finding and its fix;
`--force` runs anyway), then starts the stage (default: the first pending
manual one) in the open run (a new one with `--new`, or when the last one
ended) and drives the run in the foreground until it is idle or waits at a
gate, one line per event. `--watch` keeps it running so `block_change`
stages fire. `answer` writes the answer and, when no runner is live on the
run, drives the run on from there; `stop` does the same for a stop (a stop
lands once the member that is running returns; a delegated member gets
`agent_stop`). Exit
codes: 0 done, 1 could not (the reason on stderr), 2 usage, a problem or
the preflight. Full flag list: [COMMANDS-studio.md](COMMANDS-studio.md#halo-team).

## Studio

`halo_harness/studio/team_api.py`: `GET team`, `POST team/validate`,
`GET team/board`, `POST team/run {stage, force}`, `POST team/answer {stage,
action, text}`, `POST team/stop`, `GET team/blocks`,
`GET team/blocks/<id>/changes?since=`, `GET team/events?since=`, and
`POST team/init` (3.0.8.0 R2: what `halo team init` writes; 409 when a file
exists). Studio runs the run on a thread of its own (with the block watchers
armed) and sends every stage, gate, claim and change line on `/api/events`
as a `team` frame `{action: stage|gate|change|claim, run, kind, stage, text,
ts, data, row?}`.

## The coach

`halo team coach [run] [--json]` and the run bar's **Coach** button in Studio
(once the run is done or stopped; `GET team/coach?run=`, kept in the run
ledger's `coach.json`) read the run ledger (board.json, events.jsonl) and
suggest what to change: a stage gated two or more times (coordination: put
what the redo asked for in the stage's brief or its acceptance; the redo
answers are the evidence) and a write the team guard denied because another
member held the block (tools). The cards come from the ledger alone;
3.1.3.0: **Ask the model** (`--model`) has the lead explain a card, `halo
team status` of a done or stopped run ends with the coach line, and the ids
are the shared rules' (`coordination-<stage>-loops`,
`tools-<stage>-claim-<key>`). The rules are in
[ORCHESTRA.md](ORCHESTRA.md#the-coach).

## In Studio

`halo studio --mode team` (or `Alt+7`, `/studio team`) opens the **Team**
section: with no team file a Start view whose **Make my first team** writes
the template; then the **Board** (members as columns, stages as boxes in
their members' columns, blocks in a band underneath with a claim badge,
the `stage_done:` / reads / writes / `block_change:` edges, the run bar with
Run next, Stop and Validate), the **Inspector** (a stage's row, Run and its
gate card with Accept, Redo and Stop; a block's holders and changes; a
member's lineup, opening in Roles) and the **Change feed** (the run's event
lines with kind chips). A stage at its gate is also a `team_gate` row in
Fleet's Attention queue (`A` accept, `R` redo, `S` stop, `O` open). Details:
[STUDIO-team-roles-org.md](STUDIO-team-roles-org.md#team-people-blocks-and-stages-on-one-board).

![Team in Studio: draft done, review at its gate, notes held by a hand edit](media/studio-team.png)
