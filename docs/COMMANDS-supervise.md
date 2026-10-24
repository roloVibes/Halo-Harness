# Commands: the supervisor, its goals and knowledge

Read this when you give Halo a goal to work on without sitting at a terminal, or keep what it verified and decided.

The supervisor (`halo supervise`), its goal queue (`halo goal`), every agent task's outcome (`halo outcomes`)
and the findings and decisions that outlive a session (`halo knowledge`).
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
halo goal add --workflow doc-review/review --input path=docs/ --repo .
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

- `--workflow PACK/NAME`: a pack's workflow (3.2.0.0 R5, [WORKFLOWS.md](WORKFLOWS.md)): compiled to a
  run folder first, then queued as an Orchestra goal the supervisor resumes from its checkpoint; `what`
  is not needed;
- `--input K=V`: a workflow input (repeatable).

### `halo goal list` / `show` flags

- `--json`: the goals (or the one goal and its history lines) as JSON.

Halo 3.1.8.0 R3: `halo goal show` prints, under a stopped goal's failure,
each lane's evidence lines (what its workers' transcripts show: the tests
run, the sources read, the files written).

## `halo outcomes`

Halo 3.1.8.0 R3. Every agent task's outcome, one row each, newest last: an
Orchestra lane (written when its run's report is) and a session's sub-agent
(written when it ends), read from `~/.halo/coach/outcomes.jsonl`. Each row
says when, the run (or session), the task, its bio, model and kind, the
outcome and what checked it (`passed (gate)`, `returned (gate)`, `failed
(acceptance)`, `done`), the returns, the cost, the tests passed / failed and
the sources read. See [OUTCOMES.md](OUTCOMES.md); `halo models --measured`
rates the checked ones per model and kind.

```sh
halo outcomes                        # the newest 50 tasks
halo outcomes --kind code --since 7d # code tasks of the last week
halo outcomes --bio auto-coder       # one bio's tasks
halo outcomes --model or:vendor/model --json
```

- `--bio NAME` / `--model REF` / `--kind KIND`: only those tasks (`--kind`:
  code, research, check, writing, plan, review, media, other).
- `--since WHEN`: only tasks since `7d`, `24h`, `30m`, a date (`2026-10-20`)
  or an epoch; anything else exits 2 and says how to write it.
- `--limit N`: the newest N rows (default 50; `0`: all).
- `--json`: the rows as JSON.

## `halo knowledge`

Halo 3.1.8.0 R4. The findings and decisions under `~/.halo/knowledge/`: what
the Orchestra judge and gate, the coach's Apply and the supervisor's answered
decisions wrote, what you add, and what an agent saved with `knowledge_add`.
See [KNOWLEDGE.md](KNOWLEDGE.md).

```sh
halo knowledge add finding "basket.py#total rounds half up" --evidence "tests: \`python -m pytest -q\` exit 0, 5 passed"
halo knowledge add decision "money is Decimal, never float" --alternative "float" --body notes.md
halo knowledge list                   # the current entries, newest first
halo knowledge list decision --all    # superseded ones too
halo knowledge show f-20261024-3c9a1e # the entry, and every agent task that cited it
halo knowledge search rounding total  # through recall, else a word match
halo knowledge supersede f-20261024-3c9a1e "basket.py#total rounds half up, checked on 3.1"
halo knowledge forget d-20261024-8e41f0
halo knowledge fetch kali@lab f-20261023-0b7d2a   # take a fleet member's entry, read-only
halo knowledge fetch kali@lab --all decision      # every current decision it has
```

- `add finding|decision "<title>"`: write one, `by: user`. `--body FILE` (or
  `-` for stdin) is its what / where / why; `--evidence L`, `--alternative A`
  and `--tag T` repeat. A finding is `checked` when an evidence line names a
  test run or a reproduction, else `said`.
- `list [finding|decision] [--all]`: one line each (id, kind, by, day,
  confidence, title); `--all` adds the superseded ones, each marked with its
  successor. Exit 1 when there is none.
- `show <id>`: the entry -- its front matter, evidence, alternatives, body,
  where a fetched one came from -- and "reused by", from `outcomes.jsonl`.
- `search <words> [--k N]`: the entries that rank for the words.
- `supersede <id> "<title>"`: a new entry of the same kind naming the old one
  (which stays on disk and leaves recall); the same flags as `add`.
- `forget <id>`: remove the file and its `_meta.json`.
- `fetch <harness> <id>` / `fetch <harness> --all KIND`: through the hub this
  machine runs; written here under the same id, read-only; never over an
  entry already here. Exit 3 when no hub runs here.
- `--json` on every verb.
