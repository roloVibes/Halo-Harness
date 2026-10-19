# Fleet missions

Read this when you give one goal to the whole fleet and want to follow its parts.

Halo 3.0.6.0 "Fleet Missions". A mission is one goal done by the whole fleet:
the hub's lead splits it into parts, gives each part to the harness best placed
for it (by what each harness can do, see
[Capabilities](FLEET.md#capabilities-3060-r6)), runs the parts on their
harnesses at the same time, merges what they made and writes a report. Parts
never step on each other: each one may edit only what it claims, and two
parts that would touch the same file run one after the other.

**Teams (Halo 3.0.8.0):** a team member with `harness: <fleet member>` sends its stage's task the way a part goes out (`run_task`, as a one-part mission in the hub's store); see [TEAM.md](TEAM.md#delegating-a-member-to-the-fleet).

**Team stages on a member (Halo 3.1.2.0):** a team's orchestra stage with `harness: <member>` goes as a one-part mission whose part is `kind: orchestra` (its `run` the goal); the member runs it locally and hands back `result.json`, the run's `report.json` and its line; see [TEAM.md](TEAM.md#delegating-a-member-to-the-fleet).

**One unit of work (Halo 3.1.2.0):** a mission part is a *unit* of work, the same thing an Orchestra lane and a team stage are; `halo work <mission id>` prints its parts as that shared table. See [WORK.md](WORK.md).

Round R7 is the backend (this page): the mission folder, the planner, the
shared workspace over the fleet protocol, dispatch, the run, merge and report,
the routes and the command line. Round R8 is the Mission panel in Studio
([In Studio](#in-studio)).

## What a mission is

A mission lives on the hub, in `~/.halo/fleet/missions/<id>/` (`<id>` is
`m-<yyyymmdd>-<4 hex>`, for example `m-20261015-3fa2`):

| File | What it holds |
|---|---|
| `mission.json` | the mission document: goal, constraints, state, each part's progress, the decisions and who made them |
| `MISSION.md` | the goal, the plan as a readable table, who does what and why; every part sees it |
| `plan.json` | the plan: parts, merge order, notes |
| `claims.json` | what each part may edit |
| `parts/<n>/brief.md` | the part's brief |
| `parts/<n>/handback.md` | what its worker said when it finished |
| `parts/<n>/result.json` | `{ok, state, cost_usd, error, session_id, files, branch, bundle, refused}` |
| `inputs/` | files every part may read (put them there before the run) |
| `artifacts/<n>/` | what a files part made |
| `log.jsonl` | every event, one JSON line each |
| `report.md`, `report.json` | the report, written when the mission ends |

States: `drafted -> planned -> approved -> running -> merging -> done`, or
`failed` / `stopped`. A planned or approved mission can be edited (it goes
back to `planned` and needs approving again); a running one can only be
stopped. Parts go `pending -> asked -> running -> done | failed | stopped |
skipped`, and a merged repo part ends `merged`.

## The plan

`halo fleet mission new "<goal>"` (or `POST /api/fleet/missions`) drafts the
mission and asks the hub's lead once, through the same provider path as
Orchestra's lead. Its prompt carries the fleet's capability catalog, one
compact block per harness that can take a part now (this harness and every
online member): its name, tags, a hardware line, craft apps, MCP servers with
their tool names, skills, models, command-line tools and its load (live
agents), plus what only one harness has. The lead answers with JSON:

```json
{"parts": [{"id": "1", "title": "Scan the lab subnet", "brief": "...", "kind": "files",
            "harness": "kali@lab", "reason": "it has nmap", "needs": ["nmap"], "depends_on": [],
            "claims": [], "outputs": ["scan.xml"], "take": "outputs", "est_cost_usd": 0.2}],
 "merge_order": ["3", "2"]}
```

Code checks the answer (every part has a title and a brief, claims are
repo-relative, dependencies name real parts and make no loop; a failed check
asks once more with the problems listed) and then applies the rules:

- **Pinned.** A part whose `needs` only one harness meets goes there, with the
  reason (`only kali@lab has nmap 7.95 (CLI)`). A need is an MCP server or one
  of its tools, a craft app, a skill, a tag, an installed CLI, a model, `gpu`,
  a word of a GPU's name (`4090`), an OS or distro, `comfyui`, or
  `repo:<name>`; a `mcp:` / `cli:` / `skill:` ... prefix narrows it.
- **Ties.** When several harnesses meet the needs, the lead's pick stands;
  otherwise `fleet.mission.prefer` (an ordered list of names, or `--prefer`)
  breaks the tie, then the load, then the name.
- **Unassignable.** A part that needs something nobody has is flagged with the
  reason; the mission cannot be approved until it is reassigned or dropped.
- **Kinds.** A `repo` part changes the hub's repo (the folder the mission was
  made in) on its own branch; a `files` part works in `artifacts/<n>/` of the
  mission folder, which is then its claim.

`halo fleet mission plan <id>` prints the plan with each part's harness and
why; `--again` asks the lead again. An owner's edit (`halo fleet mission edit
<id> <n> --harness NAME | --drop`, `POST .../parts/<n>`, or `part 2 to kali` /
`drop 3` typed on the attention row) is checked again in code only: a harness
that lacks a part's needs is refused with what it lacks.

## Claims: never stepping on each other

Claims are paths or globs relative to the repo (`src/report/**`,
`docs/index.md`). Code computes whether two claims can name one file (`*`, `?`
and `**` included; a plain path also covers what is under it). Two repo parts
whose claims overlap get a `depends_on` so the later one in the merge order
waits for the earlier, and the plan's notes say why; the later one then
starts from the earlier one's head ([Hand-offs](#hand-offs)).

On the harness that runs it, the part's claims join the session's permission
engine as a guard (the same hook Orchestra's claim guard uses). An Edit,
Write, MultiEdit or NotebookEdit outside the claims is refused with a one-line
reason, the refusal goes to the hub as a `fleet` frame and in the part's
result, and the hub logs it and raises a `mission_claim` attention row. Inside
the claims the owner's own rules decide as always: a claim never allows
anything by itself, and the guard holds for the part's sub-agents too. The R4
conflict detector still watches every agent's edits across the fleet.

## The shared folder

**Without a mount** the hub serves the mission folder over the signed fleet
protocol (`POST /fleet/v1/mission_files {op: list | get | put}`). A member
mirrors `MISSION.md`, its own brief, `inputs/` and the outputs and hand-backs
of the parts it depends on ([Hand-offs](#hand-offs)) into its own `~/.halo/fleet/missions/<id>/` before its part runs,
and pushes its `artifacts/<n>/`, the hand-back, the result and, for a repo
part, a git bundle of its branch afterwards. A member reaches only a mission
it has a part in, reads only those files and writes only its own part's;
every path is relative, `..` is refused and no symlink is followed; one file
may be at most `fleet.mission.max_file_mb` (default 25).

**With a mount** (`fleet.shared_dir`: an SMB or NFS folder both machines see,
set on both), missions live there (`<shared_dir>/<id>/`) and nothing is
mirrored.

## What the member's owner sees and allows

A part reaches a member as the `run_task` fleet command, under its
`fleet.allow_control` like a steer or a stop:

- `ask` (the default): a card in the owner's TUI, "hub-a asks to run mission
  m-20261015-3fa2 part 1 here: Scan the lab subnet (claims: artifacts/1/**)",
  allow or deny; on the member's own Studio it is a `mission_ask` row;
- `none`: refused, with the reason; the part fails and the parts that wait for
  it are skipped;
- `all`: it starts.

The part runs as a `kind: mission-worker` session, built in-process the way
`halo -p` builds one, with the owner's own settings, MCP servers, skills and
permission rules (an ask becomes a deny: nobody waits on a card). Its registry
row carries `mission`, `part` and `parent` (the mission id), so it shows in
Studio, `halo fleet` and the hub's agent tree, and pause, resume and stop
reach it like any agent. A repo part needs a checkout of its repo on that
machine (a live session's project); it runs in a worktree on branch
`mission/<id>/<part>`.

## Hand-offs

Halo 3.0.9.0 (`fleet/mission_handoff.py`). A part's **`outputs` are its
hand-off vocabulary**: what it leaves for the parts that depend on it.

```json
{"id": "2", "title": "Build the findings workbook", "kind": "files", "depends_on": ["1"],
 "outputs": ["artifacts/2/findings.xlsx"], "take": "outputs"}
```

- **What a dependent part reads.** From each part it depends on, exactly
  that part's `outputs` and its `parts/<d>/handback.md`; with `"take":
  "all"` the dependency's whole `artifacts/<d>/**` instead. That is what
  `mission_files` lists and serves to a member (anything else of the
  dependency is a 403), what a member mirrors before its part runs, and
  what the part's prompt lists ("Hand-offs from part(s) 1 in the mission
  folder: parts/1/handback.md, artifacts/1/scan.xml."). `take` defaults to
  `outputs`; the lead may set it, and the plan keeps it.
- **The base rule.** A repo part with `depends_on` (declared by the lead or
  added by the claims sequencing) starts from its repo dependencies'
  finished work, not the mission's base: one dependency that changed files
  = its branch head; two or more = their merge, which the hub makes on
  `mission/<id>/<n>-base` (a conflict goes to a fresh judge as the
  mission's merge does: its answer applied by code, the mission's tests
  after it; a judge's answer that does not fit, or failing tests, fail the
  part with the reason). A dependency that ran on a member comes from its
  `parts/<d>/branch.bundle`; a part that runs on a member gets its start as
  `parts/<n>/base.bundle` and fetches it before making its worktree. A part
  with no repo dependency starts from the mission's base, as before.
- **Where it shows.** The part's state, its `result.json` and the report
  carry `base`; report.md's **Who did what** table has a Base column
  (`` `1a2b3c4` (after 1, 2) ``). The map labels each `depends_on` edge with
  what it carries (the outputs' names, `all`, or `hand-back`) and each repo
  part with its base.

Because the later part starts from the earlier one's head, two sequenced
parts that touch one file no longer conflict at the merge: the later part's
version is the one merged.

## The run, the merge, the cost and the report

Parts start by the dependency graph as their dependencies finish, at most
`fleet.mission.max_parallel` at once (default: the number of harnesses). A
part that fails skips every part that waits for it and the mission ends
`failed` with the reasons. `stop` stops every running part. Then the repo
parts merge one at a time in the merge order into `mission/<id>/merged`; a
conflict goes to a fresh judge as in Orchestra (the goal and the hunks only,
its answer applied by code) and, when the mission has a `test` command, the
tests run on the judged merge and a failure ends the mission with the reason.

Each part gets a budget share of `budget_usd` by its estimate (in its brief).
The report (`report.md`, `GET .../report`, `halo fleet mission report`) says
who did what on which harness, the cost per harness and per part (and the
lead's), the decisions and who made them, the files touched, the edits
refused outside a part's claims and what failed. The hub journals
`mission_planned`, `mission_approved`, `mission_run`, `mission_part`,
`mission_claim` and `mission_end`; the digest lists them. A planned mission
raises a `mission_plan` attention row: approve and run, edit, or drop.

**Preflight** (Halo 3.0.7.0). `run` first checks this harness's active
lineup with the run-start preflight: a model id its provider's catalog does not know (requests for it 404 and the member comes back empty), an assignment naming a bio that does not exist, a bio whose `tools.allow` is an empty list (it may call no tool), and a `tiers` problem ([ROLES.md](ROLES.md#tiers-halo-3070)). A blocking
problem answers 422 `{error, problems, preflight: true}` (the error lists each
problem with its fix) and the mission stays as it was; `{"force": true}` on
`POST /api/fleet/missions/<id>/run` (or `halo fleet mission run <id>
--force`) runs anyway.

## A worked example

The Windows host has GridCraft and the RTX 4090; the Kali box has nmap.

```sh
halo fleet mission new "Scan the lab subnet and turn the findings into a workbook with a chart" --budget 2
```

The lead's plan, after the rules:

```text
Mission m-20261015-3fa2 (planned): Scan the lab subnet and turn the findings into a workbook ...
   1  kali@lab (pinned)   pending   Scan the lab subnet
      why: only kali@lab has nmap 7.95 (CLI)
   2  win@studio (pinned) pending   Build the findings workbook  after 1
      why: only win@studio has gridcraft (MCP server)
```

`halo fleet mission run m-20261015-3fa2` approves it and follows it: the Kali
box's owner allows the card, its part writes `artifacts/1/scan.xml` and pushes
it to the hub; the workbook part starts on the Windows host with the scan
mirrored in, writes `artifacts/2/findings.xlsx`, and the report lists both
parts, their cost per harness and the files.

## Routes and the command line

| Route | Answer |
|---|---|
| `GET /api/fleet/missions` | `{missions: [summary], at, root_shared}` |
| `POST /api/fleet/missions {goal, constraints?, prefer?, budget_usd?, test?, repo?}` | drafts and plans: `{mission, plan, summary, running}` |
| `GET /api/fleet/missions/<id>` | the same shape |
| `POST .../<id>/plan` | the lead plans again |
| `POST .../<id>/parts/<n> {harness?, drop?}` | reassign or drop one part |
| `POST .../<id>/approve`, `.../run`, `.../stop {reason?}` | the state changes (409 when the state does not allow it) |
| `GET .../<id>/report` | `{report, markdown, final}` |
| `GET .../<id>/files[?path=]` | the folder's files, or one text file |

Every change is a `fleet` frame `{action: "mission", id, state, part?,
part_state?}` on Studio's live feed. `halo fleet mission new | plan | edit |
approve | run | status | stop | report | open` take `--json`
([COMMANDS-fleet.md](COMMANDS-fleet.md#halo-fleet-mission)); `/mission` in the TUI prints
the status. They use the running Studio, else the hub this machine serves,
else this harness alone.

## In Studio

Fleet's **Mission** panel (`M` in Fleet, or the palette's **Fleet: new
mission**) is the same flow on one screen: type the goal, pick the harnesses
to prefer and a budget, **Plan it**. The plan is drawn over the Fleet map,
each part a node in its harness's box (a lock where it was pinned by
capability, an amber edge and a **claims** chip where two parts were
sequenced, a chip naming what every other edge hands on, each repo part's
base, a red chip where nobody can run it), and as a table under the map.
Drag a part to another harness to move it (a harness that lacks what it
needs refuses with the reason), then **Approve** and **Run**: parts waiting
on a member's owner pulse amber, running ones show the line their agent is
on, and **Stop** asks for a reason. The report lists who did what, the cost
per harness and per part, and opens the artifacts. The plan, a part refused
an edit and a hub's run_task card are rows in Attention. See
[STUDIO-fleet.md](STUDIO-fleet.md#how-this-works-missions).

![Fleet Mission in Studio: the plan on the map and its table](media/studio-fleet-mission.png)

## The coach

Once a mission ends, `halo fleet mission coach <id> [--json]` and the Mission
panel's **Coach** face in Studio (`GET fleet/missions/<id>/coach`, kept in the
mission folder's `coach.json`) read the folder (report.json, log.jsonl) and
suggest what to change in the next plan: a part that sat `asked` (waiting for
its harness owner) longer than the mission's median part took
(coordination), an edit refused outside a part's claims (tools), a merge
conflict a judge resolved between two parts (structure: give the later part
`depends_on` the earlier one), a repo part that changed no file (structure:
drop or fold it), and outputs the plan named that nobody wrote (prompt). A
mission's plan is the lead's, so these cards carry no Apply: put the change
in the next mission's constraints, or Plan it again. 3.1.3.0: **Ask the
model** (`--model`) has the lead explain a card, the ended mission's report
ends with the coach line, and the ids are the shared rules' (a refused edit
is `tools-<part>-claim-<file>`). The rules are in
[ORCHESTRA.md](ORCHESTRA.md#the-coach).

A mission part delegated to a member is exercised end to end against a real
second machine by the scripted two-machine check ([FLEET.md](FLEET.md) "The
two-machine check", `tools/live_fleet_check.py`, 3.1.2.0 R3).

## Config keys

| Key | Default | Meaning |
|---|---|---|
| `fleet.shared_dir` | unset | a folder every machine sees: missions live there and nothing is mirrored |
| `fleet.mission.prefer` | `[]` | harness names, in order, that break a tie between harnesses that can all take a part |
| `fleet.mission.max_parallel` | the number of harnesses | how many parts run at once |
| `fleet.mission.max_file_mb` | `25` | the largest file the mission folder takes over the fleet protocol |
