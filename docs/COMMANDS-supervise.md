# Commands: the supervisor and its goals

Read this when you give Halo a goal to work on without sitting at a terminal.

The supervisor (`halo supervise`) and its goal queue (`halo goal`).
Part of [Commands](COMMANDS.md), which lists every part.

The full description -- what the supervisor is, the morning view, the pulse,
the service files and the parked decisions -- is in [SUPERVISE.md](SUPERVISE.md).

## `halo supervise`

Halo 3.1.8.0. The supervisor: a daemon that owns a goal queue and runs it
without a TUI. Each goal is an Orchestra run or a plain `halo -p` job; while
it runs it keeps every lineup's schedules and triggers armed (a session no
longer has to be open), resumes a run from its last checkpoint after a crash,
stops a goal at its budget, and parks every decision it cannot take in
Studio's Attention queue. One supervisor per state dir; a second one says who
runs. Exit codes: 0 done, 1 could not (the reason on stderr), 2 usage.

```sh
halo supervise                 # run in the foreground; Ctrl+C stops it
halo supervise --daemon        # detach and return (it keeps running in the background)
halo supervise --service       # write the service-manager file (never enabled) and print the one enable command
halo supervise --service --os linux   # write the file for another OS
halo supervise status          # the pulse: pid, state, the goal counts, what waits on you
halo supervise status --json   # the same, machine-readable
halo supervise stop            # ask a running supervisor to end (a stop file it polls)
```

### `halo supervise` flags

- `--daemon`: detach the supervisor (Windows `DETACHED_PROCESS`, POSIX a new
  session) and return once its pulse is live.
- `--service`: write the service-manager file for this OS under
  `~/.halo/supervise/` (a systemd user unit, a launchd plist or a Task
  Scheduler XML) and print the single command that enables it. Halo never
  enables it.
- `--os linux|macos|windows`: with `--service`, write the file for another OS.
- `--json`: one JSON object on stdout.

## `halo goal`

Halo 3.1.8.0. The supervisor's goal queue from a terminal. `halo goal add`
only queues a goal; the supervisor (`halo supervise`) runs it. Exit codes: 0
done, 1 could not (the reason on stderr), 2 usage.

```sh
halo goal add "write the release notes" --repo . --budget 2 --lineup halo-dev-cycle
halo goal add "summarise the open issues" --as job --budget 0.5
halo goal add "port the parser" --file parser.py --test "python -m pytest" --replan review
halo goal list
halo goal show g-ab12
halo goal hold g-ab12        # keep a queued goal from starting
halo goal release g-ab12     # let it start
halo goal pause g-ab12       # hold a queued goal, or stop a running one's work and re-queue it
halo goal resume g-ab12      # a paused, parked, stopped or failed goal goes back in the queue
halo goal cancel g-ab12      # stop a running goal's run or job (state stopped, why cancelled)
halo goal rm g-ab12          # drop a goal (not one that runs)
```

### `halo goal add` flags

- `--repo DIR`: the repo the goal works on (default: the current folder).
- `--done-when TEXT` / `--stop-when TEXT`: DONE WHEN / STOP WHEN for the goal.
- `--budget USD`: the goal's spend cap -- a stop, not a warning (see
  [SUPERVISE.md](SUPERVISE.md#budgets-are-stops) and
  [ORCHESTRA.md](ORCHESTRA.md#budgets-stop)).
- `--lineup NAME`: the lineup (team template) that plays the parts.
- `--as orchestra|job`: run it as an Orchestra run (several agents on one set
  of files, the default) or a plain background `halo -p` job.
- `--file F`: a file the workers share, relative to the repo root (repeatable,
  an Orchestra goal).
- `--test CMD`: the test command the gate runs (an Orchestra goal).
- `--review`: pause for the plan's review before it runs (an Orchestra goal);
  the review waits in Attention as a `goal plan` row.
- `--replan none|auto|review`: what the supervisor does when this goal's run
  drifts (default: `supervise.replan`): `auto` applies the lead's new plan for
  the lanes left, `review` parks it as a `goal plan` row, `none` stops only
  (see [SUPERVISE.md](SUPERVISE.md#replanning)).

### `halo goal list` / `show` flags

- `--json`: the goals (or the one goal and its history lines) as JSON.
