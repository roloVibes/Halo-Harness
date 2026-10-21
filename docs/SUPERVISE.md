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
`goal budget` and `goal ask` rows, each with one key:

- **goal plan** -- a goal you queued with `--review`: Approve, Reject (with a
  reason) or Open the plan.
- **goal gate** -- the quality gate sent a piece back past the return cap:
  raise the cap by 1 and resume, raise it by N, Stop, or Open the run.
- **goal budget** -- a lane (or a job) would pass the goal's or the queue's
  cap: raise by its cap and resume, raise by $N, Stop, or Open.
- **goal ask** -- a supervised job's permission card or question (with
  `supervise.asks: park`): Allow / Answer, Deny / Edit, Stop the goal, or Open
  the session.

Every parked row lives in `~/.halo/supervise/decisions/<id>.json`, so it
survives Studio starting later and the supervisor restarting; the supervisor
polls the answer and acts on it.

## The goal queue

Each goal is a file under `~/.halo/supervise/goals/<g-id>.json`:

    {id, what, done_when, stop_when, repo, budget_usd, lineup, kind: orchestra | job,
     state: queued | running | parked | done | stopped | failed, created, started, ended,
     run_dir | bg_id, cost_usd, why, held, retries, failure, files, test, workers, plan}

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
