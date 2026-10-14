# The Orchestra

Halo 3.0.3.0. Several agents write to the same files at the same time and
nothing is lost. The idea comes from Kem Tossoun's reel "5 agents write to
the same file at the same time and nothing is lost" (Glitch Cat Club); this
page is Halo's version of it.

The rule behind it: **code decides wherever it can, a model judges only
when it must.** Code owns the claims, the merge order, the tests and the
gate. A model writes the functions, and when two pieces conflict at merge
time a FRESH agent resolves the conflict and the tests check its answer.

Round R1 (this release so far) builds the code-decides foundation: the
graph, the goal, the claims, the guard, the timed log and the CLI. Round R2
adds the split, the workers, the merge, the judge, the gate, the report and
the runner on top (see [What R2 adds](#what-r2-adds)).

## The seven parts

| # | Part | Where it lives |
|---|---|---|
| 1 | A workflow graph designed in code before anything runs: goal -> lead orchestrator -> split -> N workers -> merge one at a time -> quality gate -> finished branch + report, with the gate looping a failed piece back to its worker | `orchestra/workflow.py`, `workflow.json` |
| 2 | `goal.json`: WHAT YOU WANT, DONE WHEN, STOP WHEN | `orchestra/goal.py` |
| 3 | `split.json`: one job per worker | R2 |
| 4 | Claims on parts of a file, recorded in code (claimed -> writing -> written) | `orchestra/claims.py`, `orchestra/index.py`, `claims.jsonl` |
| 5 | One git worktree per worker | R2 (the guard already matches a worker's worktree copy of a goal file) |
| 6 | Code decides, a model judges only when it must | the guard (`orchestra/guard.py`) today; merge, tests and gate in R2 |
| 7 | Every state change logged with its time, and a run report of checks | `orchestra/events.py`, `events.jsonl`; the report in R2 |

## The files on disk

A run lives in the repo it works on, in `<repo>/.halo/orchestra/<run-id>/`.
The run id is `YYYYMMDD-HHMMSS-<4 hex>`, so runs sort by time. The
`.halo/orchestra/` folder carries its own `.gitignore` (`*`): run state is
never committed and never merged.

| File | What it holds |
|---|---|
| `run.json` | `run_id`, `created` (the clock every `elapsed_s` counts from), `repo_root`, `lead_holder` |
| `goal.json` | the goal (below) |
| `workflow.json` | the designed graph: `steps` (`id`, `kind`, `lane`, `state`, `label`) and `edges` (`from`, `to`, `kind`: `flow` or `loop`) |
| `events.jsonl` | the timed log: `{"ts", "elapsed_s", "lane", "kind", "text", "data"}`, kinds `state`, `claim`, `merge`, `gate`, `report`, `note` |
| `claims.jsonl` | the claim log: `{"ts", "elapsed_s", "op", "holder", "key", "ttl_s", "note"}`, ops `claim`, `writing`, `written`, `release`, `expire`, `steal` |

### goal.json

| Field | Default | Meaning |
|---|---|---|
| `what` | required | WHAT YOU WANT |
| `done_when` | required | DONE WHEN: what the gate checks |
| `stop_when` | required | STOP WHEN: when the run gives up |
| `workers` | 5 | worker lanes, 1 to 50 |
| `return_cap` | 2 | how many times the gate may send one piece back |
| `test` | "" | the test command the gate runs |
| `files` | [] | the files the workers share, relative to the repo root |
| `lineup` | "" | the lineup (team template) that plays the parts |
| `lead` | `main` | the lead orchestrator's role (the lineup's main, the boss) |
| `worker` | `subagent` | how a worker runs |

A worked example ships in
`halo_harness/templates/orchestra/goal.example.json`: the reel's
`basket.py`, five functions, `python -m unittest`.

### The workflow graph

    goal -> lead -> split -> worker-1 .. worker-N -> merge -> test -> gate -> done
                                  ^------------------ loop ------------------'

Every step starts `pending` and moves through `running` to `done`,
`failed` or `skipped`. `workflow.advance(graph, step_id, state)` returns a
new graph; `loop_back(graph, lane)` re-opens one worker and every step
behind it; `ready(graph)` lists the pending steps whose flow predecessors
are all finished.

## Claims

A key names one claimable unit of a file:

| Key | Unit |
|---|---|
| `basket.py` | the whole file |
| `basket.py#total` | a Python function or class (`ast`) |
| `basket.py#Basket.total` | a method, or any nested def (`outer.inner`) |
| `README.md#install` | a Markdown heading, from its line to the line before the next heading of any level |
| `web/app.js#addItem` | other languages: a top-level `function`, `def`, `func` or `fn` |

Two keys overlap when they are in the same file and one is the whole file,
the same unit, or a dotted parent of the other. A claim does not go through while an
overlapping claim by someone else is live; the answer names the holder and
the time the claim expires. A claim lasts `ttl_s` seconds (default 900)
from its last line, so marking it `writing` renews it.

Holders are `<session_id>/<agent_id>`: the top session is
`<session_id>/main`, a sub-agent `<session_id>/<agent id>`. Only the run's
lead can steal a claim: the `lead_holder` in run.json, or, with none
recorded, a `<session_id>/main` holder.

Every claim op reads, checks and appends under the run's lock
(`claims.jsonl.lock` plus a thread lock), so two sessions on one machine
never interleave and agents racing for one key get exactly one winner.

### The rule an agent follows

1. Read the goal (`goal.json`: what, done when, stop when, the files).
2. List the claims: `OrchestraClaims` shows every live claim and every
   claimable unit of the goal's files.
3. Claim the smallest key you need: `OrchestraClaim(key)`. When it is taken,
   pick another unit, wait, or ask the lead.
4. Edit. The guard lets your edit through and marks the claim `writing`.
5. Release: `OrchestraRelease(key)` marks it `written` and lets it go.
6. Note: `OrchestraNote(text)` says what you changed in the run log.

### The guard

Inside a run (`HALO_ORCHESTRA_RUN=<run folder>` in the session's
environment) every session, sub-agents included, checks Write, Edit,
MultiEdit and NotebookEdit on the goal's files against the claims. The
check runs after the ordinary permission decision when that decision is
allow or ask; a deny from your own rules or mode always stands.

| The edit touches | Decision |
|---|---|
| a unit someone else holds | deny: "`<key>` is held by `<holder>` until <time>: wait for the release or ask the lead" |
| a unit no claim of yours covers | ask: "no claim on `<key>`; claim it first (OrchestraClaim) or allow once" (a deny where nothing can be asked: print mode, dontAsk) |
| only units your claims cover | allow, and the claim moves to `writing` |

Edit and MultiEdit touch the lines where each `old_string` occurs; Write
and NotebookEdit touch the whole file. A file that is not in the goal keeps
its ordinary decision, so auto and bypassPermissions behave exactly as
before everywhere else. A worker's own worktree copy of a goal file is
matched too (the path relative to the session's working folder).

The four tools appear only inside a run and never ask for permission: they
write nothing but the run's own logs.

## The session feed

`orchestra.events.emit(session, kind, data)` writes the line and publishes
`orchestra_state`, `orchestra_claim`, `orchestra_merge`, `orchestra_gate`
or `orchestra_report` on the session's event feed (the TUI, the remote
feed, Studio). `note` lines stay in the file.

## The CLI

```sh
halo orchestra new [--what T --done-when T --stop-when T] [--workers N] [--test CMD]
                   [--file F ...] [--lineup L] [--goal FILE] [--repo DIR]
halo orchestra status [RUN]          the goal, the steps, live claims, the last events
halo orchestra claims [RUN]          every live claim: key, holder, state, expiry
halo orchestra log [RUN] [--since N] the timed run log
halo orchestra runs                  every run of this repo, oldest first
```

`new` asks for WHAT YOU WANT, DONE WHEN and STOP WHEN on a terminal when
they are not given as flags. RUN is a run id, a unique prefix of one, or a
run folder; the latest run when omitted. Every subcommand takes
`--repo DIR` (default: the current folder).

## What R2 adds

- `split.json` and the split step: one job per worker, each job naming its
  keys.
- The workers: one git worktree each, one session each with
  `HALO_ORCHESTRA_RUN` set, the lineup's worker role.
- The merge: the workers' pieces one at a time, in an order code decides;
  a conflict goes to a fresh agent, checked by the tests.
- The judge and the gate: the test command and DONE WHEN; a failed piece
  loops back to its worker up to `return_cap` times; STOP WHEN ends the run.
- The report: every check with its result and time; the finished branch.
- The runner (`halo orchestra run`) and Studio's view of the graph.

R2 builds on these functions:

| Module | Functions |
|---|---|
| `workflow` | `designed_graph(workers)`, `advance(graph, step_id, state)`, `loop_back(graph, lane)`, `ready(graph)`, `step`, `steps_of_kind`, `summary`, `validate_graph` |
| `goal` | `Goal`, `validate_goal`, `load_goal`, `save_goal`, `new_run(repo_root, goal, lead_holder=None)`, `list_runs`, `latest_run`, `resolve_run`, `run_meta`, `set_lead_holder`, `repo_root_of` |
| `index` | `index_file(path, root=None)`, `index_text(text, rel)`, `unit_for_line`, `units_for_lines`, `overlaps`, `covers`, `split_key` |
| `claims` | `ClaimLog(run_dir, clock=time.time)`: `active`, `claim`, `mark_writing`, `mark_written`, `release`, `steal`, `expire_stale`, `held_by`, `conflicts`, `is_lead`; `holder_for(session_dir)` |
| `guard` | `ClaimGuard(run_dir, holder)`, `install_from_env(engine, session_dir)`, `run_dir_from_env()` |
| `events` | `log(run_dir, kind, text, lane=None, **data)`, `read(run_dir, since=0)`, `emit(session, kind, data, run_dir=None)`, `format_line` |
