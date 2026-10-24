# The supervisor

Read this when you want to give Halo a goal at night and open Studio in the morning to see what finished, what waits on you and what it cost.

The supervisor (`halo supervise`) is a daemon that owns a goal queue and runs
it without a TUI. You queue goals with `halo goal add`; the supervisor starts
each one as an Orchestra run (several agents on one set of files) or a plain
`halo -p` job, keeps every lineup's schedules and triggers armed while it
runs, resumes a run from its last checkpoint after a crash, stops a goal at
its budget, and parks every decision it cannot take -- a plan review, a gate
past the return cap, a budget cap, a supervised job's question -- in Studio's
Attention queue with one key each. See [COMMANDS-supervise.md](COMMANDS-supervise.md)
for the commands and flags.

## The morning view

Open Studio's Session section. When a supervisor's pulse is live its landing
shows one line -- **"N goals done, M waiting on you, $X"** -- and the
decisions that wait are the Attention queue's `goal plan`, `goal gate`,
`goal budget`, `goal ask` and `goal replan` rows, each with one key:

- **goal plan** -- a goal you queued with `--review`, or a replan's new plan
  for the lanes left ([Replanning](#replanning)): Approve, Reject (with a
  reason) or Open the plan.
- **goal gate** -- the quality gate sent a piece back past the return cap:
  raise the cap by 1 and resume, raise it by N, Stop, or Open the run.
- **goal budget** -- a lane (or a job) would pass the goal's or the queue's
  cap: raise by its cap and resume, raise by $N, Stop, or Open.
- **goal ask** -- a supervised job's permission card or question (with
  `supervise.asks: park`): Allow / Answer, Deny / Edit, Stop the goal, or Open
  the session.
- **goal replan** -- a replan's new plan failed its check twice: Apply the new
  plan (after editing it), Keep the old plan (with a reason), Stop the goal, or
  Open the plan.

Every parked row lives in `~/.halo/supervise/decisions/<id>.json`, so it
survives Studio starting later and the supervisor restarting; the supervisor
polls the answer and acts on it.

## The goal queue

Each goal is a file under `~/.halo/supervise/goals/<g-id>.json`:

    {id, what, done_when, stop_when, repo, budget_usd, lineup, kind: orchestra | job,
     state: queued | running | parked | done | stopped | failed, created, started, ended,
     run_dir | bg_id, cost_usd, why, held, retries, failure, files, test, workers, plan,
     replan: "" | none | auto | review, replans: [{n, at, why, lines, state, settled, by, note}], taken?}

An `orchestra` goal with a lineup (`halo goal add --lineup NAME`) takes that
lineup's acceptance the way `halo orchestra new --lineup` does (3.2.1.0 R1,
[PACKS.md](PACKS.md) "A pack's lineups"): an empty `test` gets the lineup's
`acceptance.test`, and `plan: auto` becomes `review` when it says `review:
true`. A `--test` you give wins; a job goal and a compiled workflow (`halo
goal add --workflow`, whose test and plan come from its stages) take
nothing. `taken` lists what it took, `halo goal add` prints the lines under
the queued line, and the goal's first history line says them:

    queued g-1a2b3c: review the docs (orchestra, repo my-docs)
      test from lineup doc-review--review: python -m pytest -q
      plan: review from lineup doc-review--review (the run pauses for the plan's review)

The supervisor starts the next queued goal that is not `held` when fewer than
`supervise.max_running` goals run. An `orchestra` goal runs through the real
Orchestra adapters (never Studio's live runner); a `job` goal runs `halo -p
<what> --output-format json --permission-mode auto [--max-budget-usd <cap>]`
as a background run (`halo bg list` shows it). A goal's end state and cost
come from the run's `report.json` or the job's `status.json` and result JSON.
`halo work` lists goals as a unit kind beside Orchestra lanes, mission parts
and team stages.

### Per-goal controls

`halo goal hold` / `release` keep a queued goal from starting and let it go.
`halo goal pause` holds a queued goal, or stops a running one's work and
re-queues it held (an Orchestra goal resumes from its checkpoint; a job goal,
which has none, starts over). `halo goal resume` puts a
paused, parked, stopped or failed goal back in the queue. `halo goal cancel`
stops a running goal's run or job (state `stopped`, `why: cancelled`).

### Bounded retries, limits and history

`supervise.retries` (default 1) is how many times a goal whose run stopped on
a crash or a failed worker is retried from its checkpoint; past that it parks
with `why: retries`. A retry never re-runs a lane that was merged -- the
resume path (events.jsonl + `lanes/*.json`) already guarantees it.
`supervise.max_minutes` (default 0 = none) is a goal's time limit: past it the
run gets `request_stop` and the goal parks with `why: time`. A failed goal's
file carries `failure: {kind: crash | worker | gate | budget | time |
cancelled, step, last_event, report?}`.

`~/.halo/supervise/history.jsonl` keeps one line per goal state change
(`{ts, goal, from, to, why, cost_usd, run_dir|bg_id}`) and one per decision
answered (`{ts, goal, row, key, by}`); `halo goal show` prints a goal's lines,
and the Session landing's morning line reads it.

## Schedules stay armed

A session's schedules and triggers die when the session closes (see
[AGENTS.md](AGENTS.md)). While the supervisor runs it
arms every lineup -- in the state dir and in each queued goal's repo -- that
declares a schedule or a trigger, with its store entries marked `owner:
supervisor`. A session that loads a lineup the supervisor already owns does
not arm it a second time (its `_arm_team_scheduler_once` checks the live
pulse), and the supervisor's `_persist`/`disarm` only ever replace or drop its
own entries, so nothing double-fires. A trigger firing while its previous fire
still runs does not start a second job -- the store keeps the running fire's
background-run id and a due fire is skipped with a log line. `on: event` and
`on: message` triggers are fed from the live sessions' control-socket feeds.

## Checkpoint resume

Every Orchestra runner -- the CLI, Studio and the supervisor -- writes
`<run>/runner.json {pid, pstart, beat}` every 15 seconds while it drives a
run. A run with a live runner reads as `running`, not `interrupted`, and a
second process will not start a runner on it (409). On start and on every tick
the supervisor resumes its own goals whose run has no live runner and no
report: `halo orchestra run` picks up at the first unfinished step, and a
written or merged lane is never run again.

## Budgets are stops

A goal's `budget_usd` and the queue's `supervise.budget_usd` are caps, not
forecasts. Before a lane's worker starts, what the run has spent plus what the
lanes running now are expected to cost plus this lane's forecast must stay
under the goal's cap, and all of that plus the other goals' spend under the
queue's. A lane that would pass a cap does not start: the run stops with
`stop_reason: budget` and the goal parks with a `goal budget` row. A `job`
goal runs with `--max-budget-usd`, which `halo -p` enforces itself.

## Verified outcomes

Halo 3.1.8.0 R3 ([OUTCOMES.md](OUTCOMES.md)). An Orchestra goal's lanes each
end with evidence read out of their workers' transcripts -- the tests run,
the sources read, the files written -- and the gate reads it: a code lane
that ran no test (when the goal has one) goes back once with "no test run in
this lane's work: run <test>", a research lane with no source with "no
source fetched or read". When a goal stops, its `failure.report` keeps each
lane's evidence lines (`failure.report.evidence`, `{lane: [lines]}`), and
`halo goal show` prints them under the failure: what the lanes actually ran,
not what they said.
Every lane's outcome is one row of `~/.halo/coach/outcomes.jsonl`
(`halo outcomes`); `halo models --measured` rates them per model and kind.

**Your answers outlive the goal (3.1.8.0 R4).** Each answer you give a parked
`goal_plan`, `goal_gate`, `goal_budget` or `goal_replan` row (from Studio's
Attention queue or anywhere else that answers it) is also a decision in
`~/.halo/knowledge/` by `supervisor` -- "Goal g-7: the gate sent a piece back
past the return cap -> raise the cap by N", your text as its why, the other
answers as its alternatives -- which recall finds next time, here or across
the fleet ([KNOWLEDGE.md](KNOWLEDGE.md)). "Open" and a `goal_ask` card write
none; the decision never names who answered; `knowledge.write: false` turns
it off.

## Replanning

Halo 3.1.8.0 R2. A budget, a gate and a crash only stop a run. With
`supervise.replan` set to `auto` or `review` (or `halo goal add --replan
auto|review` for one goal) the supervisor has a second move: when a run
**drifts** it pauses the lanes left and asks the run's lead for a new plan for
them, then re-approves that plan through the same plan review.

### What drift is

`supervise/drift.py` reads the run folder (forecast.json, lanes/*.json,
events.jsonl, the spend) and names each drift with its number. A lane LEFT is
a lane of the plan whose piece is not merged; a merged lane never drifts.

| Drift | When | Threshold (config, default) |
|---|---|---|
| `forecast` | the live spend plus every lane left at its forecast would pass the goal's `budget_usd` (or the queue's `supervise.budget_usd`) by this factor | `supervise.replan_forecast`, `1.25` (25 % over) |
| `returns` | a lane was sent back this many times (by the gate, or by a merge whose resolution failed the tests) | `supervise.replan_returns`, `2` |
| `blocked` | a lane waited on a hand-off from its upstream, or on a claim that was refused and never taken since, this long | `supervise.replan_block_s`, `600` |
| `stalled` | a writing lane logged no event this long | `supervise.replan_stall_s`, `900` |

The check runs before every lane's worker starts (the run's spawn guard, so
`returns` and `forecast` are caught before the next attempt is paid for) and
on every tick (where nothing spawns: `blocked` and `stalled`). The forecast
is only as good as the plan's prices: an unpriced model forecasts $0 (see
[Budgets are stops](#budgets-are-stops)).

### The pause and the ask

A drift found and allowed -- `supervise.replan` is not `none`, the goal
replanned fewer than `supervise.replan_max` (`2`) times, and its last replan
is more than `supervise.replan_cooldown_s` (`300`) old -- pauses the run:
`<run>/replan.json` says `pausing` and the run's own stop file asks it to stop
between steps. A worker that runs finishes its step, no lane is killed, and
no new lane starts. In the goal's own thread (never the tick) the lead then
gets the split prompt's shape with the plan so far: the merged lanes pinned,
every lane left with its state, model, returns and claim refusals, the drift
lines, and for a lane that came back what came back -- the probe's contrast
list when a probe of this run ran, else the gate's last verdict as its
worker read it. It answers for the lanes left only, with one or more of four
moves:

- **a different model** (or bio) for a lane: the lane keeps its id and claims;
- **a split**: two or more new jobs with `"from": "<its id>"` whose claims
  divide its claims; the lane is replaced (its file keeps its history and its
  spend, its claims are released) and the parts take the next lane numbers;
- **a second specialist** beside a stuck lane: a new job with `"assist":
  "<its id>"` and the same claims; it reads the units and cannot edit them
  (the lane it assists keeps them), and its final reply is handed to that
  lane's worker, which runs after it;
- **a retry with the contrast as context**: `"retry": true`; the lane's
  worker runs again with what came back in its hand-off.

The answer is checked (`supervise/replan_plan.py`: every lane left kept or
split, no merged lane named, then the whole plan through the plan review's
own check -- ids, claims, overlaps, cycles, the bio and model preflight). A
reply that fails is asked once more with the problems; a second failure parks
a **goal replan** row with the problems as its detail.

### The review

`auto` applies the checked plan at once and the run resumes from its
checkpoint. `review` -- and every goal with `plan: review`, whatever
`supervise.replan` says (unless it is `none`) -- parks a **goal plan** row
whose detail is the diff of the lanes, for example:

    goal plan  Goal g-3f9a1c: a new plan for the lanes left waits for your review
               lane 5 (job-5): model the default -> or:vendor/stronger-model; lane 5 (job-5): retry with the contrast as context

`a` applies it; `r` (with a why) keeps the old plan: the paused lanes resume
unchanged and the why goes to events.jsonl. A **goal replan** row takes `a`
(apply the proposal in `<run>/replan.plan.json`, the owner's edit of it
included, checked again; a failing one reopens the row with the problems),
`r` (keep the old plan), `s` (stop the goal) and `o` (open the plan).

Applying writes split.json's new plan (a merged lane is never touched),
re-queues the lanes whose worker runs again, gives the parts placeholder
claims, redesigns workflow.json and recomputes forecast.json. plan.json
gains `revisions: [{n, at, why: [drift lines], from, to, by: auto | <who>,
moves}]`; events.jsonl gets `replan_asked`, `replan_applied` and
`replan_rejected` lines with the numbers; the goal file keeps one row per
replan (`replans`). `halo supervise status`, `halo goal show` and the run
report print **"replanned N times (<why>)"**. Past `supervise.replan_max` a
drift is left to the stops: the budget guard parks `goal budget`, the gate
parks `goal gate`, as before.

## Isolated workers

Halo 3.1.8.0 R5. A goal's Orchestra run starts its workers through the same
`spawn_worker` as `halo orchestra run`, so a lineup or bio that declares
`isolation: container | user`, `secrets: broker` or `tools.capabilities`
holds under the supervisor too ([ISOLATION.md](ISOLATION.md)). A lane that
cannot run as declared (no docker or podman here, no `op`, a scoped user
on Windows, a ref that cannot be read) stops with its one line; the run
stops with `lane <n>: <line>` and the goal fails with `failure.kind:
worker`. `halo goal show` prints each lane's isolation, secrets and tool
lines under the run.

## The pulse

`~/.halo/supervise/pulse.json` is `{pid, pstart, started, updated, state,
goals: {queued, running, done, parked}}`, written every tick. `halo supervise
status` and Studio read it; `state` is `starting`, `running`, `stopping` or
`stopped`, and `running` is true only when the pid is alive and is the process
that wrote the pulse (`pstart`, a start token, so a reused pid does not count).
`~/.halo/supervise/stop` is the stop file the supervisor polls (`halo supervise
stop` writes it; Windows has no signal for it).

## The service files

`halo supervise --service` writes the service-manager file for this OS under
`~/.halo/supervise/` -- a systemd user unit, a launchd plist or a Task
Scheduler XML -- and prints the single command that enables it. Halo never
enables it; you run that one command to start the supervisor at login.
