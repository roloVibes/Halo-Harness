# The Orchestra

Read this when several agents should write the same files at once: the Orchestra and its plan, lanes and judge.

Halo 3.0.3.0. Several agents write to the same files at the same time and
nothing is lost. The idea comes from Kem Tossoun's reel "5 agents write to
the same file at the same time and nothing is lost" (Glitch Cat Club); this
page is Halo's version of it.

**In a team (Halo 3.0.8.0):** a team stage of `kind: orchestra` starts an Orchestra run with the stage's goal (the files of its write blocks when the goal names none); see [TEAM.md](TEAM.md).

**One unit of work (Halo 3.1.2.0):** a lane is a *unit* of work -- the same thing a mission part and a team stage are, with one state machine, one ledger line, one report row and one coach. `halo work` prints the lanes of a run as that shared table; see [WORK.md](WORK.md).

The rule behind it: **code decides wherever it can, a model judges only
when it must.** Code owns the claims, the merge order, the tests and the
gate. A model writes the functions, and when two pieces conflict at merge
time a FRESH agent resolves the conflict and the tests check its answer.

Round R1 built the code-decides foundation: the graph, the goal, the
claims, the guard, the timed log and the CLI. Round R2 adds the run
pipeline on top: the split, the workers, the merge, the judge, the gate, the
report and the runner (see [The run pipeline](#the-run-pipeline)).

## The seven parts

| # | Part | Where it lives |
|---|---|---|
| 1 | A workflow graph designed in code before anything runs: goal -> lead orchestrator -> split -> N workers -> merge one at a time -> quality gate -> finished branch + report, with the gate looping a failed piece back to its worker | `orchestra/workflow.py`, `workflow.json` |
| 2 | `goal.json`: WHAT YOU WANT, DONE WHEN, STOP WHEN | `orchestra/goal.py` |
| 3 | `split.json`: one job per worker | `orchestra/split.py` |
| 4 | Claims on parts of a file, recorded in code (claimed -> writing -> written) | `orchestra/claims.py`, `orchestra/index.py`, `claims.jsonl` |
| 5 | One git worktree per worker | `orchestra/workers.py`, `orchestra/lanes.py`, `lanes/<n>.json` |
| 6 | Code decides, a model judges only when it must | the guard, `orchestra/merge.py` (a fresh judge on a conflict), `orchestra/gate.py` |
| 7 | Every state change logged with its time, and a run report of checks | `orchestra/events.py`, `events.jsonl`, `orchestra/report.py`, `report.json` |

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
| `split.json` | the lead's split: `base` (the commit every worktree starts from), `lead_cost_usd`, `lead_sessions`, `jobs` (`id`, `title`, `claims`, `worker`, `order`) |
| `lanes/<n>.json` | one worker lane (below) |
| `merge.json` | the merge: `branch`, `base`, `order`, `merged`, `conflicts`, `finished` |
| `report.json` | the run's report and its checks |
| `stop.json` | a stop request (`halo orchestra stop`): `reason`, `ts` |
| `wt/worker-<n>/`, `wt/merge/` | the git worktrees: one per worker lane, and the finished branch's |

### goal.json

| Field | Default | Meaning |
|---|---|---|
| `what` | required | WHAT YOU WANT |
| `done_when` | required | DONE WHEN: what the gate checks |
| `stop_when` | required | STOP WHEN: when the run gives up |
| `workers` | 5 | worker lanes, 1 to 50 |
| `return_cap` | 2 | how many times the gate may send one piece back |
| `test` | "" | the test command the gate runs |
| `test_timeout_s` | 600 | seconds the test command may run before it is stopped |
| `files` | [] | the files the workers share, relative to the repo root |
| `lineup` | "" | the lineup (team template) that plays the parts |
| `lead` | `main` | the lead orchestrator's role (the lineup's main, the boss) |
| `worker` | `subagent` | how a worker runs |
| `handoffs` | {} | 3.0.9.0: per job id, `{gives, needs, after}`: what a lane hands on, what it takes and which lanes it starts after (see [Hand-offs](#hand-offs)) |
| `budget_usd` | none | 3.1.2.0: what the run may cost; the plan's [forecast](#the-forecast) is shown against it (Approve warns over it, it does not refuse) |
| `workflow` | none | 3.2.0.0 R5: the pinned plan of the pack workflow the goal was compiled from (see [Workflows](#workflows)) |

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
are all finished. A lane that starts after another (3.0.9.0) hangs off it by
an `after` edge instead of off the split ([Hand-offs](#hand-offs)).

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
halo orchestra run [RUN] [--model REF] [--dry-run] [--force]
                                     the pipeline: split, workers, merge, tests, gate, report
halo orchestra lanes [RUN]           every lane: state, pieces sent back, cost, holder, keys
halo orchestra report [RUN]          the report and its checks
halo orchestra stop [RUN] [--reason T]  ask a running run to stop at its next step
halo orchestra run [RUN] --review    pause after the split until the plan is approved
halo orchestra plan [RUN]            the plan of a review run, its problems
halo orchestra approve [RUN] [--file F]  check the plan and let the waiting run take it
halo orchestra reject [RUN] --reason T   the waiting run stops with the reason
halo orchestra coach [RUN] [--model] [--apply ID [--yes]] [--json]   the post-run coach's card (halo coach)
halo orchestra coach [RUN] --probe [--k N] [--yes]   3.1.6.0: try candidate overlays first (Probes, below)
halo coach library [list|show|forget|fetch]   3.1.6.0: the improvement library (The library, below)
```

`--review`, `plan`, `approve` and `reject` are the reviewed plan: see
[Review the plan](#review-the-plan). `coach` is [the coach](#the-coach).

`new` asks for WHAT YOU WANT, DONE WHEN and STOP WHEN on a terminal when
they are not given as flags. RUN is a run id, a unique prefix of one, or a
run folder; the latest run when omitted. Every subcommand takes
`--repo DIR` (default: the current folder).

`run` prints one line per step as it happens (the run log's `state`,
`merge`, `gate` and `report` lines), then the report; exit 0 when the run
finished, 1 when it stopped. `--dry-run` asks the lead for the split and
prints the jobs; nothing is claimed and no worktree is made. `--model REF`
is the model every part uses; without it each part takes its role's model
from the role table (`halo roles`): the goal's `lead` for the split and the
judge, the goal's `worker` for the workers, else the default model.

**Preflight** (Halo 3.0.7.0). Before the split, and before a `--dry-run`, the
run-start preflight (`lineup_preflight.py`) checks the lineup the run uses
(the goal's `lineup`, else the active team) for what would make the lanes
come back empty: a model id its provider's catalog does not know (requests for it 404 and the member comes back empty), an assignment naming a bio that does not exist, a bio whose `tools.allow` is an empty list (it may call no tool), and a `tiers` problem ([ROLES.md](ROLES.md#tiers-halo-3070)). Each
blocking problem prints with its fix and the run stops before anything is
claimed (exit 2); `--force` runs anyway. Studio's `POST /api/orchestra/run`
answers 422 `{error, problems, preflight: true}` (each problem `{id,
severity: "blocks"|"warns", text, fix}`) and runs with `{"force": true}`.
A lineup with only `warns` findings (a dead fallback, aliases in no tier)
runs. `halo doctor --roles` lists the same findings for the active lineup.

`/orchestra [RUN]` in the TUI opens a panel like `/tasks`: the run's steps,
one row per lane (state, pieces sent back, cost, holder, title) and the last
run log lines, refreshed when the run log grows. Outside the TUI the same
text prints.

## The run pipeline

`halo orchestra run` (`orchestra/run.py`, `run(run_dir, *, model_calls,
spawn, judge, clock)`) walks the graph:

1. **lead -> split** (`orchestra/split.py`). ONE model call through the
   lead's role. The lead sees the goal (WHAT YOU WANT, DONE WHEN, STOP WHEN),
   the worker count and every claimable unit of the goal's files, and answers
   JSON: `{"jobs": [{"title", "claims": ["file#unit", ...]}]}`, or
   `{"stop": "reason"}` when STOP WHEN already applies. Code checks it: every
   key is a unit of the goal's files, no key (or overlapping key) is in two
   jobs, every job has a title and a key, at most `workers` jobs (fewer is
   fine; the unused worker steps are `skipped`). A failed check retries the
   call once with the problems listed; a second failure stops the run.
   split.json records the jobs and the base commit, and every key is claimed
   for its lane under the placeholder holder `lane:<n>`.
2. **workers** (`orchestra/workers.py`). Each job gets a lane: a worktree
   `wt/worker-<n>` on branch `orchestra/<run-id>-worker-<n>` from the base
   commit, and a worker, all lanes in parallel. When the worker's session
   starts (`HALO_ORCHESTRA_LANE=<n>` in its environment) it joins its lane:
   the lead's code hands it the `lane:<n>` claims (`ClaimLog.reassign`, a
   `steal` line in the worker's name). The worker follows the claim rule;
   its OrchestraRelease stores the unit's text as written (the lane's
   `written` snapshot). When the worker returns, code closes any claim it
   still holds and commits the worktree. A reply line `STOP: <reason>` (the
   worker's STOP WHEN) stops the run. A worker that ends with an error of
   its own (a dropped connection, a crash) runs once more in the same
   worktree, told what happened; the new session takes over the claims its
   predecessor still held, and an edit made before the takeover still counts
   as written when the new session releases the unit.
3. **merge** (`orchestra/merge.py`). Code decides the order: the split's
   order (a job's `order`), then the smaller diff (`git diff --shortstat`).
   The finished branch `orchestra/<run-id>` starts at the base commit in its
   own worktree `wt/merge`; each worker branch merges with `git merge
   --no-ff`, one at a time. On a conflict both versions stay between git's
   markers (diff3: ours, base, theirs); code extracts the hunks and calls the
   judge, a FRESH agent whose whole prompt is the goal and the hunks; code
   applies its text and runs the tests. The merge is kept when the tests pass
   or, mid-sequence while later pieces are still unwritten, fail no test that
   was not already failing before this merge. Otherwise the merge is undone
   and the piece goes back to its worker with the failure (`pieces_returned
   += 1`, lane `waiting`, the graph's loop edge), then merges again; at
   `return_cap` the run stops with the reason.
4. **test -> gate** (`orchestra/gate.py`). The goal's `test` command runs on
   the finished branch (the scrubbed tool-child environment, stopped after
   `test_timeout_s` with its whole process tree, the last 40 lines kept).
   Passing tests finish the run. Failing tests send back each lane whose
   unit names appear in the output, except a lane whose own code calls
   another named lane's unit (its failure is explained by that one); a lane
   at its cap, or output that names no lane, stops the run.
   3.1.8.0 R3, the gate reads the evidence ([OUTCOMES.md](OUTCOMES.md#the-judge-reads-the-evidence)):
   after each worker pass a lane's `lanes/<n>/evidence.json` holds what its
   workers' transcripts show -- the test runs (command, exit, passed, failing
   names), the files written with their diff, the sources read -- never the
   worker's own summary. Before the record check, a `code` lane whose work
   ran no test (the goal has a `test`) goes back once with "no test run in
   this lane's work: run <test>", a `research` lane with no source with "no
   source fetched or read" (one `gate` line each; once per lane, never past
   the return cap, never for a lane that left no transcript). The gate's
   verdict and each report lane carry the evidence lines, and the conflict
   judge's prompt gains an EVIDENCE block with the lanes' tests, sources and
   reproductions.
5. **done**: report.json, the finished branch and its sha.

Every transition advances `workflow.json` and writes a `state` line; merges
write `merge` lines, the gate `gate` lines, the end a `report` line, each
with its time. A re-run picks up at the first unfinished step: split.json,
`lanes/*.json` and merge.json say what is done (a written lane is not run
again, a merged lane is not merged again; the run log says `resume: picking
up at <step>`). `halo orchestra stop` writes `stop.json`; the runner checks
it between steps. A stopped run still writes its report, with the reason.

### `lanes/<n>.json`

```json
{"lane": 2, "job": "job-2", "title": "write remove_item", "claims": ["basket.py#remove_item"],
 "order": 2, "state": "merged", "holder": "<session>/main",
 "branch": "orchestra/<run>-worker-2", "worktree": "<run>/wt/worker-2", "head": "<sha>",
 "cost_usd": 0.0031, "started": 1760300000.1, "ended": 1760300042.7, "pieces_returned": 0,
 "session_ids": ["<session>"], "written": {"basket.py#remove_item": "def remove_item(...):\n    ..."},
 "error": "", "reply": "the worker's last reply (tail)",
 "history": [{"state": "joined", "ts": 1760300000.2, "elapsed_s": 3.1, "text": "worktree worker-2 on ..."}]}
```

Lane states: `joined` (worktree ready) -> `writing` (the worker runs) ->
`written` (piece committed) -> `in_review` (being merged) -> `merged`;
`waiting` (a piece sent back, or, 3.0.9.0, a lane waiting for its upstreams),
`failed` (the worker failed or stopped). The hand-off fields (`handoff`,
`after`, `base`, `gave`) are under [Hand-offs](#hand-offs). 3.0.9.0 R3 adds `bio`, `model` and `denied`
(see [The coach](#the-coach)); 3.1.8.0 R3 adds `evidence_returned` (the line a lane went back with
for missing evidence, at most once); 3.1.8.0 R5 adds `isolation`, `secrets`, `tools` and `opt_ins` when
the lane's lineup or bio declares one ([ISOLATION.md](ISOLATION.md#where-it-shows)).

### `merge.json`

```json
{"branch": "orchestra/<run>", "base": "<sha>", "order": [1, 2, 3, 4, 5], "merged": [1, 2, 3, 4, 5],
 "finished": "<sha>",
 "conflicts": [{"lane": 2, "file": "basket.py", "attempt": 1,
                "hunks": [{"index": 1, "start_line": 2, "end_line": 8, "ours": "...", "base": "...",
                           "theirs": "...", "ours_label": "HEAD", "theirs_label": "orchestra/<run>-worker-2"}],
                "judge_session": "<session>", "fresh": true, "messages_before": 0,
                "resolution": "the judge's text", "applied_by": "code", "applied": true,
                "tests_ok": true, "tests_tail": "...", "cost_usd": 0.0004, "ts": 0, "elapsed_s": 0}]}
```

## Hand-offs

Halo 3.0.9.0. By default every lane runs at once from the split's base and
sees only the goal and its own job. A lane may instead **wait for another
lane** and **take what that lane left**: its summary, the units it wrote, or
a file it saved. The lead declares this in its job answer; `goal.json` may
pre-declare it per job id under `handoffs:` (the goal's declaration wins
field by field).

```yaml
# the lead's answer (JSON in practice), one job:
- title: write remove_item
  claims: [basket.py#remove_item]
  after: [job-3]                     # start after job-3, without taking anything from it
  handoff:
    gives:                           # what this job hands on
      - {name: notes, kind: artifact, paths: [notes.md]}
      - {name: summary, kind: summary}
      - {name: units, kind: files, paths: [basket.py]}
    needs:                           # what it takes, and from whom
      - {from: job-1, take: summary}   # all | summary | the name of something job-1 gives
      - {from: job-1, take: notes}

# goal.json
handoffs:
  job-2: {needs: [{from: job-1, take: all}], after: []}
```

**The rules, checked in code** (`orchestra/handoff_spec.py`; a failed check
retries the lead once with the problems, as every split check does):
`from` and `after` name real jobs (`job-<n>`, its position `<n>`, or the
lead's own `id` for it), never the job itself; the upstreams (`after` plus
every `needs.from`) form no cycle; `take` is `all`, `summary`, or the name
of one of the upstream job's `gives`. Every lane gives its summary and its
written units whether it declares them or not, so `all` and `summary`
always name something. A `gives` entry has a `name`, a `kind` (`files`,
`summary` or `artifact`) and optional `paths`.

**Layers.** A job with upstreams sits one layer below its deepest upstream.
`workflow.json` then hangs it off its upstreams by an `after` edge
(`{"from": "worker-1", "to": "worker-2", "kind": "after", "label":
"summary + notes"}`) instead of off the split, every worker step carries
its `layer`, and the graph has `layers: [[1, 3], [2]]`; `ready` honours the
`after` edges. The merge keeps the layer order, then the split's order
inside a layer. With nothing declared the graph, the order and every file
are exactly as before.

**The base rule** (`orchestra/handoff.py`, `handoff_run.py`). A lane with
upstreams is `waiting` ("waits for job-1 (hand-off)") until every upstream
lane is written. Then its worktree starts from the upstream's finished
`head`; with two or more upstreams, from the merge of their heads
(`merge.merge_heads`, on the scratch branch `orchestra/<run>-base-<n>`; a
head that already contains another is not merged again). Heads that
conflict leave the lane `waiting` with the reason, and the run stops
naming it. An upstream that failed leaves it waiting too. A lane without
upstreams starts from the split's base.

**What a lane sees.** A lane with `needs` gets a **Hand-offs** section in
its prompt:

```
Hand-offs (what earlier jobs left for you; nothing else from other jobs reaches you):
- From job-1 (lane 1: write add_item), take summary:
  its summary:
    <lane 1's final reply>
- From job-1 (lane 1: write add_item), take notes:
  its artifact notes: .halo/handoff/job-1/notes.md in your folder
```

`take: summary` is the upstream's final reply; `take: all` is the reply,
the list of its written keys (already in the lane's files, since it starts
from that head) and its artifacts; `take: <name>` is just that give.
Artifacts are copied into the lane's worktree under `.halo/handoff/<job>/`,
which is git-ignored and never committed. A lane that declares `gives` is
told where to save each artifact (`<run>/lanes/<n>/artifacts/`, outside its
worktree) and that its final reply is the summary later jobs read. **A lane
with no `needs` sees nothing from other lanes**: the goal and its own job
only, as before, even when it starts after another lane.

**The lane's record.** `lanes/<n>.json` gains:

```json
{"handoff": {"needs": [{"from": "job-1", "take": "summary"}, {"from": "job-1", "take": "notes"}]},
 "after": ["job-1"],
 "base": "<the commit its worktree started from>",
 "gave": [{"name": "summary", "kind": "summary", "path": "lanes/2/summary.md", "bytes": 812},
          {"name": "files", "kind": "files", "path": "basket.py#remove_item", "bytes": 164},
          {"name": "notes", "kind": "artifact", "path": "lanes/2/artifacts/notes.md", "bytes": 230}]}
```

`handoff` is the job's declaration (refs made job ids), `after` every job
it starts after (its `after` plus each `needs.from`), `base` where its
worktree started, `gave` what it produced, filled when the lane is
written: the summary (`lanes/<n>/summary.md`, its final reply), one `files`
row per written key (the path is the key), one `artifact` row per file it
saved under `lanes/<n>/artifacts/`. Paths are relative to the run folder.
An undeclared lane gives `summary`, `files` and any artifact it saved; a
declared artifact that is missing is a `note` in the run log. split.json's
jobs carry `handoff` and `after` only when declared.

## Review the plan

Halo 3.0.9.0. A goal with `plan: review` (the default is `plan: auto`, a run
that goes straight from the split to the workers) stops after the lead's
split: `split.json` is written, the workflow's split step turns `planned`
(the run's state is `planned`), no lane starts, and the run waits for your
decision in `<run>/plan.json`:

```json
{"approved": true, "jobs": [{"id": "job-1", "title": "write add_item", "claims": ["basket.py#add_item"],
                             "bio": "coder", "model": "or:vendor/model"},
                            {"id": "job-2", "title": "write remove_item", "claims": ["basket.py#remove_item"],
                             "after": ["job-1"], "handoff": {"needs": [{"from": "job-1", "take": "summary"}]}}],
 "ts": 1760700000.0, "by": "cli"}
{"approved": false, "reason": "one lane per file instead", "ts": 1760700000.0, "by": "studio"}
```

The jobs are split.json's shape plus the [hand-off](#hand-offs) fields
(`after`, `handoff`) and, new, the worker's own `bio` and `model` (the
worker runs `halo -p --agent <bio> --model <model>`; empty = the goal's
worker role, as before). A rejected plan stops the run with "the plan was
rejected: <reason>" in its report; nothing ran.

```sh
halo orchestra run [RUN] --review           the goal's plan becomes review, then the run starts and waits
halo orchestra plan [RUN]                   the plan as a table (job, after, bio, model, cost, title, claims, needs), the
                                            forecast's total against the goal's budget_usd, its problems
halo orchestra approve [RUN] [--file F]     check the plan (F: {"jobs": [...]} or the list; else Studio's draft, else the split)
halo orchestra reject [RUN] --reason TEXT   the run stops with that reason
```

`approve` writes `plan.json` only when the plan passes every check, and
prints every problem otherwise (exit 2; the run keeps waiting). What is
checked (`workflow.validate_plan(jobs)`, orchestra/plan_check.py):

- at least one and at most 50 jobs; every job has a unique id and a title;
- every job claims at least one unit, and every claim is a key of the
  goal's files;
- `after` and `needs.from` name real jobs, never the job itself, and the
  upstreams make no cycle;
- a `take` names something the upstream gives: `all`, `summary` or one of
  its `gives`;
- no two jobs claim the same or an overlapping key unless an `after` (or a
  need) puts one after the other;
- each job's bio and model pass the lineup preflight: the bio exists, its
  `tools.allow` is not an empty list, the model (the job's own, else the
  bio's preference) is in its provider's catalog.

On approval code renumbers the jobs `job-1..N` in their order (rewriting
`after` and `needs.from`), keeps the lead's own split as
`split.lead.json`, rewrites split.json's jobs (`"plan": "approved"`), moves
the placeholder claims to the new lanes (in layer order: of two sequenced
jobs on one key the earlier one holds it; the later one claims it when it
starts), and gives workflow.json a step per lane when the plan has more
lanes than the goal's `workers`. Two sequenced lanes may write the same
unit: the later lane starts from the earlier one's head, and the gate's
record check takes the later lane's text as the record. A `plan.json`
written by hand that fails the check is moved to `plan.bad.json` with its
problems, and the run keeps waiting. While it waits the runner touches
`<run>/plan.wait.json` every two seconds; Studio uses it to know whether a
runner (Studio's own or `halo orchestra run --review` in a terminal) will
take the decision.

Studio draws the plan as a canvas you edit (see [In Studio](#in-studio) and
[STUDIO-orchestra.md](STUDIO-orchestra.md#the-plan-canvas-3090)); its draft lives in
`<run>/plan.draft.json` until you approve it.

## The forecast

Halo 3.1.2.0. Before a lane runs, what will it cost? `orchestra/forecast.py`
answers it for any plan (the lead's split, Studio's draft or an approved
plan.json): one line per lane and a total against the goal's `budget_usd`,
written as `<run>/forecast.json` beside split.json (after the split, and on
every look at the plan):

```json
{"lanes": [{"lane": 1, "job": "job-1", "model": "or:vendor/mid", "tokens_in": 30000, "tokens_out": 5000,
            "usd": 0.05, "usd_low": 0.04, "usd_high": 0.075, "source": "lead", "priced": true}],
 "total": {"usd": 0.05, "usd_low": 0.04, "usd_high": 0.075, "budget_usd": 0.5, "over": false, "unpriced": 0, "units": 1}}
```

The tokens are the lead's own estimate when it gives one: the split prompt
asks for `"est_tokens": {"in": n, "out": n}` on each job in one sentence (a
bare number counts 80% in, 20% out). Without one the heuristic is
`tokens_in = 6000 + the goal's text / 4 + 3 x the claimed files' bytes / 4`
and `tokens_out = 800 + 3 x the claimed units' bytes / 4` (4 characters to
a token: the worker's prompt and tool schemas, the files it reads a few
times, each unit rewritten about three times). The price is the model
catalog's (the coach's `coach_prices.catalog`: in and out per million
tokens; no out price = 4 x the in price; Ollama and Hugging Face models
cost 0; a model the catalog does not list leaves the lane unpriced). The
lane's model is the job's `model`, else its bio's preference, else the goal's
worker role's. The band says how sure it is: a lead's estimate x0.8 to
x1.5, the heuristic x0.5 to x2. The total is `over` when its high end
passes `budget_usd`. `halo orchestra plan` prints a Cost column and the
total line; `GET orchestra/<run>/forecast` serves it (and the plan payload
and each `PUT` carry it); Studio's plan canvas shows each lane's cost chip
and the total in its header, red when over. **Approve** warns when the
forecast is over the budget and approves all the same.

## Budgets stop

Halo 3.1.8.0 R1. Under the supervisor ([SUPERVISE.md](SUPERVISE.md)) a run's
`budget_usd` is a cap, not a warning: before a lane's worker starts, what the
run has spent plus what the lanes running now are expected to cost plus this
lane's forecast must stay under the cap, and all of that plus the other
goals' spend under the queue's `supervise.budget_usd`. A lane that would pass
a cap does not start; the run stops with `stop_reason: budget` and the goal
parks with a `goal budget` row in Attention (`supervise/budget.py`, the probe
guard's rule generalized). A plain `halo orchestra run` from a terminal still
only warns -- the stop is the supervisor's.

Halo 3.1.8.0 R2: with `supervise.replan: auto | review` the supervisor also
replans a run that drifts (its forecast, its returns, a blocked or a stalled
lane): it pauses the lanes left through the run's own stop file (running
workers finish their step), asks the lead for a new plan for them (a
different model, a split, a second specialist, a retry with the contrast) and
applies it at once or parks it for review; a merged lane is never touched.
plan.json gains `revisions`, report.json `replans`. See
[SUPERVISE.md](SUPERVISE.md#replanning).

## The heartbeat

Halo 3.1.8.0 R1. Every runner -- `halo orchestra run`, Studio and the
supervisor -- writes `<run>/runner.json {pid, pstart, beat}` every 15 seconds
while it drives a run (`supervise/heartbeat.py`). A run with a live runner
reads as `running`, not `interrupted`, and a second process will not start a
runner on it (a 409 from Studio, skipped by the supervisor). The supervisor
uses it to resume only its own goals whose run has no live runner and no
report: the resume above picks up at the first unfinished step, and a written
or merged lane is never run again.

## Stale lanes

Halo 3.1.2.0 (the 3.0.9.0 open item). A lane that starts after another
starts from that lane's head. When the gate sends the upstream's piece back
(the tests fail on the finished branch, or its merge failed the tests), the
downstream's start is out of date, and it is never merged that way
(`orchestra/stale.py`):

1. Every lane whose `base` holds the upstream's head is marked `stale` in
   its lane file (`{"upstreams": [3], "jobs": ["job-3"], "reason": "upstream
   job-3 was sent back"}`) and moves to `waiting` with that reason ("lane 5
   is stale: upstream job-3 was sent back"); its worker step goes back to
   pending.
2. Once the upstream is written again, the lane is re-based: the
   upstream's branch is merged into its worktree and the goal's tests run
   there (no worse than at the upstream's new head). Clean, the lane is
   written again with `rebased: {onto: [{lane, job, head}], head, tests_ok}`
   ("lane 5 re-based onto lane 3's new head <sha>; tests no worse") and the
   merge takes it. A conflict (the markers stay in the files) or worse tests
   send the piece back to the lane's own worker with the retry text, as a
   returned piece (`return_cap` counts it); its next pass is the re-base.
3. `merge_lanes` refuses a lane whose `stale` flag is still set (the run
   stops with "lane 5 is stale (...): it is re-based before it merges").

A run where no lane starts after another never marks anything. The run
console shows a STALE badge on the lane while it waits and the re-base line
after it.

## The report

report.json: `run_id`, `status` (`finished` or `stopped`), `stop_reason`,
`branch`, `finished` (the sha, null when stopped), `tests_ok`, `tests_tail`,
`cost_usd` (lead + workers + judges), `ts`, `elapsed_s`, `goal_done_when`,
`lanes` (`lane`, `title`, `state`, `pieces_returned`, `cost_usd`; 3.1.8.0 R3:
`evidence`, the lane's evidence lines, which `halo orchestra report` prints
under it; writing the report also writes one row per lane to
`~/.halo/coach/outcomes.jsonl`, [OUTCOMES.md](OUTCOMES.md#outcomesjsonl)) and
`checks` (`id`, `ok`, `detail`):

| Check | True when |
|---|---|
| `reviewer_fresh` | every judge call was a new session with no earlier messages, never reused, never a worker's or the lead's session (true with no conflicts) |
| `reviewer_applied_by_code_tests_pass` | every conflict's last answer was applied by code and the tests passed |
| `no_piece_over_cap` | no lane was sent back more than `return_cap` times |
| `all_branches_merged` | every worker branch is merged into the finished branch |
| `record_equals_disk` | every claimed unit's text on the finished branch equals the lane's `written` snapshot (a unit in a file the judge resolved may differ and is flagged) |
| `every_edit_streamed` | every claimed unit went claimed -> writing -> written -> released in claims.jsonl |
| `tests_pass_finished_branch` | the test command passes on the finished branch |
| `goal_done_when` | the DONE WHEN text, echoed (`ok` is null) |

## Workflows

3.2.0.0 R5 ([WORKFLOWS.md](WORKFLOWS.md)). A pack's workflow file compiles
to a goal of this pipeline: its stages become the jobs (`after` and `takes`
the hand-offs, the roles the bios, `gate: human` the plan review, the
stages' `verify.test` the goal's `test`), and goal.json's `workflow` holds
the pinned plan. The run is an ordinary run with five hooks, each a no-op
for a goal without `workflow`: the split asks the lead only to refine the
briefs of the pinned jobs (`workflows/pinned.py`; a reviewed plan keeps the
stage set and a stage that edits no file claims nothing); each lane's
prompt carries its stage, and a lane whose `when` on an upstream output is
false is skipped (`workflows/runtime.py`; the step reads skipped), waits for
its `after_event`, stops the run at its stage's `budget_usd`, and takes its
stage's `timeout_s`; the gate checks every typed output against its schema
and reads the evidence into the record check, sending a lane back with the
problems up to its stage's `retries` (`workflows/gate.py`); and the report
lists the artifacts, copied to `<run>/artifacts/<name>/`, and the bounds
not held yet (`workflows/outputs.py`).

## The coach

After a run ends, the coach reads the run folder and suggests what to change
next time: a bio's prompt, a lane's model, a bio's tools, the plan's
structure, or how the run was coordinated. The cards come from the run's
files only (report.json, events.jsonl, lanes/<n>.json, merge.json,
split.json, the bios and the model catalog on disk); no model writes them.
`halo coach [RUN]` (any run kind; `halo orchestra coach [RUN]` for an
Orchestra run) prints the card; Studio's Report panel shows it on its Coach
tab. Since 3.1.3.0 the loop closes on each card: the run's lead can explain
it in one paragraph ([Ask the model](#ask-the-model)), Apply writes the change
after one confirm, and Undo puts the file back ([Apply and
Undo](#apply-and-undo)). Since 3.1.6.0, when asked, the coach first runs the
goal again under two candidate overlays the lead drafts, has an anonymized
judge compare the deliverables with the run's and offers what wins as one
card ([Probes](#probes)).

```json
{"run": "<run-id>", "kind": "orchestra",
 "suggestions": [{"id": "model-2-stronger", "kind": "model", "severity": "high",
                  "lane_or_part": 2, "bio": "coach-cheap",
                  "text": "give bio `coach-cheap` the model lane 1 used: or:vendor/strong",
                  "why": ["lane 2 on or:vendor/cheap ($0.10/M in): hit the return cap (2)",
                          "lane 1 on or:vendor/strong ($2.00/M in): finished first try"],
                  "apply": {"target": "bio", "name": "coach-cheap", "field": "models.preference",
                            "value": "or:vendor/strong"}}],
 "evidence": {"status": "finished", "return_cap": 2, "gate_loops": 1, "conflicts": 1,
              "lanes": [{"lane": 2, "bio": "coach-cheap", "model": "or:vendor/cheap", "pieces_returned": 2, "...": "..."}]}}
```

`kind` is `prompt`, `model`, `tools`, `structure` or `coordination`;
`severity` is `high`, `medium` or `low` (the card sorts by it); `why` is the
evidence, one line each. `apply` is null, or the change the card names:
`target` `bio` (a field of that bio: `models.preference`, `tools.allow`,
`tools.deny`, `context.prompt_notes`), `lineup` (`roles.<role>`: the model of
the lineup's role the lane ran as, when it had no bio of its own) or `plan`
(`job-<n>.after`, or `job-<n>.drop: true`, in that run's plan).

The rules and their evidence:

| Kind | Finding | Evidence | Apply |
|---|---|---|---|
| prompt | a lane whose piece came back two or more times for the same reason | the lane's history: "the gate sent the piece back" (the tests failed on the finished branch) or "piece sent back" (the merge's resolution failed the tests) | the bio's `context.prompt_notes`: one line for that reason |
| prompt | a lane that wrote no unit and whose reply repeats the goal's WHAT YOU WANT | its `written` (empty) and its `reply` | the bio's `context.prompt_notes` |
| model | a lane at the return cap, or sent back by the gate, on a cheap model (under $0.50/M input, or local), while a sibling on a dearer model finished first try | both lanes' models with their catalog prices, the cap | the bio's `models.preference` = the sibling's model (no bio: the lineup's worker role) |
| model | a lane that finished first try on a top-tier model ($3/M input and up) at a high cost (at least $0.05 and twice the run's median lane) with a small diff (40 lines or fewer) | its cost against the median, the lines it wrote, the best-for kinds | a cheaper catalog model under the top tier whose best-for kinds cover the lane's model's |
| tools | a tool call the worker's permission engine denied | lanes/<n>.json `denied`, from the worker's `permission_denials` | `tools.deny` without the tool when the bio denies it, `tools.allow` with it when the bio has an allow list; null otherwise (a permission rule denied it) |
| tools | a claim refused because another lane held the unit | the `claim` event with `op: refused` | null |
| structure | a lane that spent half its time or more waiting on another lane's claims | the refused claims and the time to the lane's next claim of that key | the plan's `job-<n>.after` plus the other lane's job |
| structure | a merge conflict a judge resolved between two lanes | merge.json `conflicts` and the merge order: the last lane merged before it that claims a unit of that file | the plan's `job-<n>.after` |
| structure | a lane that wrote no unit | its `written` and its state | the plan's `job-<n>.drop` |
| coordination | the quality gate failed more than twice | the `gate` events "tests fail on ..." with the lanes sent back | null |

Since 3.0.9.0 R3 the run records what these rules read: a lane file keeps the
`bio` and `model` it ran with (the job's, else the model the worker's result
names) and `denied` (`[{tool_name, reason}]`, each also a `note` line with
`denied: true` in events.jsonl); a refused `OrchestraClaim` is a `claim` line
with `op: refused`, the holder, the key, `by` (who holds it) and the lane
(`lane_n`, from `HALO_ORCHESTRA_LANE`). A bio's `context.prompt_notes` is
added after its `context.system_prompt` wherever the bio's prompt is composed
(`teams_yaml.member_system_context_addition`).

**The rules live once.** Since 3.1.3.0 every run kind's rules are the same
functions (`orchestra/coach_rules.py`); each kind keeps a thin loader
(`coach_<kind>_rules.py`) that turns its files into unit facts (a lane, a
part, a stage) and calls them. So a mission and a team run
get the same ids and texts as an Orchestra run for the same finding: a
refused write is `tools-<unit>-claim-<key>`, a gate past its limit
`coordination-<unit>-loops` ("the gate at stage copy looped 2 times"), a
judged conflict `structure-<unit>-after-<other>` (`depends_on` for a part),
a unit that wrote nothing `structure-<unit>-drop`. Each kind's loader sets
its gate's limit (the quality gate: more than two
rounds; a team stage: more than one).

### Ask the model

`halo coach <run> --model` (the three kind verbs take it too), `/coach
--model` and the card's **Ask the model** button ask the run's own lead for
one paragraph per card: what the evidence shows, why the change would help
the next run, what to watch after it. The lead is the goal's `lead` role
with the model its lineup gives that role (the entry's `models.preference`,
else its bio's), else the role table's model, else the default model; a
mission or team run asks the `main` role. The call is one turn of a
fresh bare session with no tools (`adapters.one_shot`, the normal provider
layer), given the card, its why lines and the run's evidence. The paragraph
is kept beside the cache in `<run>/coach.ask.json`
(`{"<id>": {paragraph, error, model, role, cost_usd, ts}}`), so a second ask
reads it back without a call; `--refresh` (Studio: **Ask again**) asks
again. A model error is one line on that card ("the lead could not answer:
..."), never a crash, and the next ask tries again. `--json` carries
`paragraph` (null until asked), `paragraph_error` and `applied` on every
suggestion. `HALO_COACH_FAKE=1` answers with a fixed paragraph and no model
(`error`: a failed call), for tests and a dry look.

### Apply and Undo

Apply performs the change the card names, through the writers Studio's
editors use: a bio field through `agents_yaml.save_agent_bio` in the scope
the bio was found in (a shipped bio gets a user copy; a prompt note goes
after the bio's own notes, once), a lineup role's `models.preference`
through `teams_yaml.save_team_template`, a plan job's `after` or `drop` into
the run's plan draft (`plan.draft.json`, `plan.write_draft`: the run already
ran, so the draft is the plan the next run starts from). It first shows one
confirm card: the file, whether Apply creates it, and the before -> after
diff. `halo coach <run> --apply <id>` prints it and asks `y/N` (`--yes`
skips; `--json` without `--yes` prints `{preview, applied: null}` and writes
nothing); `/coach --apply <id>` shows it and `--yes` writes; Studio's card
shows it under the card with Apply and Cancel. Every applied change is one
line of `~/.halo/coach/applied.jsonl`:

```json
{"op": "apply", "apply_id": "a-3f9c0d12ab", "id": "model-2-stronger", "run": "<run-id>",
 "run_dir": "<the run folder>", "kind": "orchestra", "target": "bio", "name": "coach-cheap",
 "field": "models.preference", "value": "or:vendor/strong", "file": "~/.halo/agents/coach-cheap.yaml",
 "existed": true, "before": "<the file's text before>", "after": "<the file's text after>", "ts": 1760800000.0}
```

`halo coach --undo [<apply id>]` (no id: the last apply not undone), `/coach
--undo` and the card's **Undo** put the `before` text back (or remove the
file when the apply created it) only if the file still holds the `after`
text exactly; otherwise Undo is refused with the reason ("changed after the
apply: edit it by hand") and nothing is written. An undo is an
`{"op": "undo", "apply_id", "file", "ts"}` line. The card then shows
**Applied** or **Undone** (`applied: {state, apply_id, file, ts}`). Edit
(Studio's 3.0.9.0 Apply) still opens the editor that owns the field with
the value filled in and saves nothing.

**The coach line.** The run reports carry the coach's summary, "coach: N
suggestions, M applied, top: <the first card>": last in `halo orchestra
report` and the report printed after `halo orchestra run`, a mission's
report (`report.coach`, the markdown's last line) and `halo team status` of a
done or stopped run. The Fleet digest lists one coach row per run the coach
read since `--since` (`~/.halo/coach/runs.json`).

Studio reads it through `GET orchestra/<run>/coach`, computed once and kept
in `<run>/coach.json`; it is computed again when a run file it reads
(report.json, events.jsonl, merge.json, split.json, plan.json or a lane
file) is newer. The same coach reads a mission and a team run:
[MISSIONS.md](MISSIONS.md#the-coach), [TEAM.md](TEAM.md#the-coach).

### Probes

Since 3.1.6.0 the coach can try a change before it offers it (after Google's
Harness², arXiv 2610.14224): `halo coach <run> --probe [--k N] [--yes]` (and
`halo orchestra coach`), `/coach --probe` and the Coach tab's **Probe**
button. Off unless asked: nothing probes on its own, and only an Orchestra
run with its report can be probed (`orchestra/coach_probe.py`).

1. **The cost first.** "probe: N runs, up to $X (each stops at $C: the run's
   $R x F)": N = 2k (k = `--k`, else `coach.probe.k`, 1; at most 4), C = the
   run's `cost_usd` x `coach.probe.budget_factor` (1.5). The CLI asks `y/N`
   (`--yes` skips; `--json` without `--yes` prints the estimate and runs
   nothing); Studio shows it in a confirm under the Coach tab's header row;
   `/coach --probe` shows it, `/coach --probe --yes` starts the probe on a
   thread and answers at once.
2. **The candidates.** The run's lead (the same lead, one-shot path and
   `HALO_COACH_FAKE` seam as [Ask the model](#ask-the-model)) drafts k pairs
   from the goal, the lanes, the plan, the bios, the lineup and the coach's
   cards. A pair is an `invariant` candidate (how the agents work whatever
   the goal: planning, tool use, context budget, delegation) and a `domain`
   one (procedure, knowledge and constraints for this goal):

```json
{"pairs": [{"invariant": {"lead": {"model": "<ref>", "effort": "high", "prompt_notes": "..."},
                          "workers": {"model": "<ref>", "prompt_notes": "...", "max_iterations": 40,
                                      "tools": {"allow": ["Read", "Edit"], "deny": ["WebFetch"]}},
                          "bios": {"<bio>": {"model": "<ref>", "prompt_notes": "...", "max_iterations": 30, "tools": {}}},
                          "why": "one line"},
            "domain": {"workers": {"prompt_notes": "..."},
                       "bios": {"<bio>": {"prompt_notes": "...", "use_for": ["word"]}},
                       "plan": [{"job": "job-2", "after": ["job-1"]}], "why": "one line"}}]}
```

   A strict check (`orchestra/coach_probe_schema.py`) keeps what fits and
   lists what it dropped: an unknown key, a model ref that does not resolve
   (not `<route>:<id>`, a removed cc:/cx: route, an id its provider's catalog
   does not list), a bio that is not one of the run's (the lanes' and the
   lineup's), a job that is not in the plan, a note over 600 characters, an
   effort or a number out of range. A candidate with nothing left is skipped.
3. **The probe runs.** One Orchestra run per candidate, in
   `<run>/probes/<cand-id>/` (`goal.new_run(repo, goal, parent=<run>)`; no
   run list, `resolve_run` or Studio run row ever shows one; its run.json
   keeps `repo_root` and `parent`). Its split.json is the run's own (the
   same base commit; the lead is not asked again), its goal is the run's with
   `plan: review`, and an approved plan.json -- the run's jobs with the
   overlay's per-job bio, model and `after` (a bio or model the plan check
   names a problem with is left as the run had it) -- is taken on the plan wait's first
   poll (`orchestra/probe_runs.py`). Each lane worktree gets the overlay as a
   project scope when its worker starts (`.halo/agents/<bio>.yaml`,
   `.halo/teams/<lineup>.yaml`, `.halo/.gitignore` = `*`; a file git already
   tracks is marked skip-worktree, so the run never commits any of it) and
   the worker's argv gets `--team <lineup>` plus `--append-system-prompt`
   with the lane's notes, `--max-turns`, `--allowedTools` and
   `--disallowedTools` (a `halo -p` session does not compose its own bio's
   notes; the sub-agents it starts under `--team` do; `orchestra/probe_overlay.py`).
   The lead's model and effort reach the merge judge through `judge`. The
   pairs run on threads (in parallel when k > 1, a pair's two in turn),
   never through Studio's one live run slot.
4. **The budget.** Each probe run may spend C. Before a lane's worker starts,
   what the probe spent + the lanes still running + this lane's forecast
   (what the run's own lane cost, else its forecast.json line) is checked
   against C; over it the worker does not start, the run is asked to stop and
   the outcome's `stop_reason` is `budget`.
5. **The compare** (`orchestra/coach_compare.py`). A deliverable, the same for
   the run and each probe: its patch (`base..finished`, kept as
   `deliverable.patch`; the run's own is `<run>/probes/reference.patch`) and
   its diffstat, whether it finished, its tests (pass or fail, the passed
   count, the failing names), its cost after the split, its time, lanes and
   steps (worker passes + judged conflicts). The judge -- one fresh bare
   session on the `judge` role's model, else the lead's -- gets the goal's
   WHAT YOU WANT and DONE WHEN, then the deliverables labelled A, B, C ... in
   a shuffled order with no harness, run, bio, model or candidate named (the
   prompt is kept as `<run>/probes/judge.prompt.txt`), and answers
   `{"best", "ranking", "why"}`; an answer that cannot be read is ranked by
   code (finished, tests, passed, steps, cost) and says so. The contrast, per
   candidate: the tests delta, the cost delta and ratio, the steps delta, the
   judge's rank and the run's, and the axes it won (`tests`, `rank`, `cost`:
   cheaper with no fewer tests). A probe that did not finish wins nothing.
6. **Compose** (`orchestra/coach_compose.py`), in order: *adopt* the judged
   best candidate when it beat the run on the tests or on the judge's rank at
   no more than 1.5x the run's cost (the pick is its kind, `invariant` or
   `domain`); else *merge* when the best-ranked invariant and domain
   candidates each won on an axis and on different axes (the invariant
   overlay's parts plus the domain one's, notes joined: `merged`); else
   *keep* the run's harness (`kept`). The why line cites the contrast.
7. **The card** (`orchestra/coach_probe_card.py`). One card leads the run's
   card: `kind: probe`, id `probe-<ts>`, the contrast as a table, the judge's
   why in the paragraph slot. Its Apply is the composed overlay through the
   writers above: `lead.model` the lineup's lead role (else the lead's bio),
   the lead's effort and notes its bio, `workers` and `bios.<b>` each bio the
   lanes ran as (`context.prompt_notes`, `models.preference`,
   `limits.max_iterations`, `tools.allow` / `tools.deny`), `use_for` the
   lineup entry (`agents.<b>.use_for`), `plan` the run's plan draft
   (`job-<n>.after`); what has nowhere to go is listed on the card. One
   confirm lists every file with its diff; Apply records one row per file
   under one `group` id (`g-<hex>`, the id the card shows), and Undo puts the
   whole group back -- or, when any of its files changed since, writes
   nothing and says which file.
8. **Cleanup.** After the compare every probe's worktrees are removed and its
   branches deleted (`orchestra/<cand-id>`, `-worker-<n>`, `-base-<n>`); the
   probe folder keeps its report, lanes, events and patch.

Everything lands in `<run>/probe.json`, written as each step ends:

```json
{"state": "done", "step": "done", "line": "probe: 2 runs, $0.0080, picked: invariant", "k": 1, "factor": 1.5,
 "cap_usd": 0.0075, "runs": 2, "card": "probe-1792508552",
 "candidates": [{"id": "p02ec-invariant-1", "kind": "invariant", "pair": 1, "overlay": {"...": "..."}, "dropped": []}],
 "reference": {"status": "finished", "tests_ok": true, "passed": 5, "cost_usd": 0.004, "steps": 2, "stat": "...", "patch": "reference.patch"},
 "outcomes": {"p02ec-invariant-1": {"status": "finished", "stop_reason": "", "deliverable": {"...": "..."},
                                    "delivered": {"1": {"files": [".halo/.gitignore", "..."], "flags": ["--append-system-prompt", "..."]}},
                                    "cleanup": {"worktrees": ["merge", "worker-1"], "branches": ["orchestra/p02ec-invariant-1"]}}},
 "judge": {"labels": {"A": "p02ec-invariant-1", "B": "reference", "C": "p02ec-domain-1"}, "best": "p02ec-invariant-1",
           "ranking": ["p02ec-invariant-1", "reference", "p02ec-domain-1"], "why": "...", "model": "<ref>", "cost_usd": 0.0},
 "contrast": [{"id": "p02ec-invariant-1", "kind": "invariant", "tests_delta": 0, "cost_delta": -0.002, "cost_x": 0.5,
               "steps_delta": 0, "rank": 1, "ref_rank": 2, "wins": ["rank", "cost"]}],
 "pick": "invariant", "picked": ["p02ec-invariant-1"], "why": "adopted the invariant candidate: ...",
 "overlay": {"...": "..."}, "apply": {"changes": [{"target": "bio", "name": "coach-cheap", "field": "context.prompt_notes",
                                                   "value": "..."}], "skipped": []},
 "cost": {"draft": 0.0, "runs": 0.008, "judge": 0.0, "total": 0.008}, "started": 1792508550.1, "ended": 1792508552.6}
```

The run report's coach line and the Fleet digest's coach row end with the
probe once one ended: "coach: 1 suggestion, 0 applied, top: ...; probe: 2
runs, $0.0080, picked: invariant". Studio: `POST orchestra/<run>/coach/probe`
([In Studio](#in-studio)); the probe runs on a thread in Studio's process
(`studio/coach_probe_job.py`) and its step lines reach the Coach tab's
progress line as `orchestra_state` frames carrying `probe_of` (session id
`coach-probe:<run>`, no `run`, so the console's own views are not refreshed by
them); `GET orchestra/<run>/coach` carries `probe` (its status, `live` while
it runs in this Studio).

### The library

Since 3.1.6.0 every Apply is remembered (after Harness²'s improvement
library: an adopted harness plus an EXPERIENCE file that says when it
applies, the lessons and the evidence). A card's Apply (its one change) and
a probe card's Apply (its whole group) each leave one entry in the state
dir (`orchestra/coach_library.py`); the Apply's answer and the CLI's
"applied ..." line name it. An Undo of that apply or group marks the entry
`undone: true`: it stays on disk, is never cited and is left out of recall.

```
~/.halo/coach/library/e-20261020-3f21/          e-<yyyymmdd>-<4 hex>
  entry.json        {id, ts, run, run_dir, kind, project: {name, remote}, lineup, goal: {what, done_when},
                     source: apply|probe, pick?, card, title, apply_ids, files, changes, undone, from?}
  overlay.json      the composed overlay (a probe's), or the same shape built from the one change, with `changes`
  files/agents/coach-cheap.yaml   the written file's text after the Apply (each <= 64 KB; a bigger one is listed only),
                                  its path relative to the halo home or the repo's .halo
  EXPERIENCE.md
```

`project.remote` is `git remote get-url origin` of the run's repo as a path
only (`https://user:token@github.com/rolo/basket.git` and
`git@github.com:rolo/basket.git` are both `github.com/rolo/basket`: no
scheme, user, token, port or query); `project.name` is the repo's folder
name. `apply_ids` holds the apply id, or the probe's group id and each
file's row id. EXPERIENCE.md (`orchestra/coach_experience.py`):

```
# give bio `coach-cheap` the model lane 2 used: or:vendor/strong
## When it applies
project basket (github.com/rolo/basket) · lineup (none) · goal "Write the five functions of basket.py"
## Lessons
- give bio `coach-cheap` the model lane 2 used: or:vendor/strong
- <the lead's paragraph, once asked>
## Evidence
- lane 1 on or:vendor/cheap ($0.10/M in): hit the return cap (2)
- lane 2 on or:vendor/strong ($2.00/M in): finished first try
## Files
- agents/coach-cheap.yaml (models.preference -> or:vendor/strong)
```

A probe's entry is titled "adopted the invariant candidate" (or domain, or
merged), its lesson is the judge's why and its evidence the compose line
and one contrast line per candidate (tests, rank, cost, steps).

**The citation rule** (`orchestra/coach_citations.py`). An entry is cited
for a run when it is not undone, it was not born from that same run, and
either its project is the run's (the same remote path; with no remote on
either side, the same folder name) or its EXPERIENCE.md ranks for the run's
goal words through recall (`recall.search`, score 0.35 or more). At most
three are cited, newest first, and a card whose change touches the same
target, name and field as a cited entry carries that entry's id
(`library_hits`; a plan job's field matches whatever run it was in).
`coach.library.cite: false` turns every citation off (the entries stay).
The text card prints one line under its head, "the library: 3 earlier runs
like this adopted bio coach-cheap models.preference -> or:vendor/strong
(e-..., e-..., e-...)", and `[lib e-...]` after a matching card's severity;
`--json` and `GET orchestra/<run>/coach` carry `library` (`[{entry, title,
when, ts, project, same_project, source, from, fields}]`), `library_line`
and each suggestion's `library_hits`; Studio's Coach tab shows the same line,
a `lib` chip on a matching card and a **Library (n)** fold under the header
row (title, when, project, **Forget** with a confirm: `POST
coach/library/<entry>/forget`). A probe's draft gives the lead the cited
entries' Lessons as "What earlier runs like this learned".

**The base lineup stays.** Nothing is inherited: the next run starts from
the lineup and the bios as they are on disk. An entry comes back only
through a proposal -- a citation on a card you Apply after one confirm (with
Undo), or a lesson the lead may turn into a probe candidate.

**The CLI.** `halo coach library` lists the entries (id, when, project,
lineup, source, the title; `--json`), `show <entry>` prints its
EXPERIENCE.md and the files it keeps, `forget <entry>` deletes its folder
after `y/N` (`--yes`), `fetch <harness> <entry>` takes one from another
harness ([COMMANDS-studio.md](COMMANDS-studio.md#halo-coach)).

**The fleet.** Recall indexes every entry's EXPERIENCE.md as its own kind,
`coach_library` (the title is its first heading; an entry gone from the
folder is pruned), so `halo recall --fleet` finds what another box learned:
a member answers such a hit with its Lessons as the excerpt, and
`fleet.recall.hide: [coach_library]` keeps the library out. `halo coach
library fetch <harness> <entry>` asks the hub this machine runs
(`local/coach-library`), which sends the read-only `coach_library {entry}`
command to one live session of that member; the member answers its
entry.json, EXPERIENCE.md, overlay.json and files/ (at most 256 KB in all,
else it refuses with the size) under the same switch as recall
(`fleet.recall.share`) and logs a `library_asked` journal line. The entry is
written here under the SAME id with `from: <harness>` in entry.json and is
never written over an entry already here
([FLEET.md](FLEET.md#recall-across-the-fleet-3120-r3)).

## The adapters

`orchestra/adapters.py` wires `run()` to real models:

- the lead (`model_call`) and the judge (`fresh_judge`): a brand-new bare
  halo session per call, no tools, one turn (the same in-process path `halo
  init`'s live check uses). The judge reports its session id and how many
  messages its log held before the prompt (0), which `reviewer_fresh` checks.
- a worker (`spawn_worker`): a fresh `halo -p` child process with
  `--output-format json --permission-mode auto`, its cwd the lane's
  worktree, and `HALO_ORCHESTRA_RUN` / `HALO_ORCHESTRA_LANE` in its
  environment, so the claim guard and the Orchestra tools are live in it and
  its holder is its own session. (The in-process sub-agent path takes the
  parent's folder and the process-wide environment, so it cannot give each
  lane its own worktree and lane number; a child process can.) In `-p` mode
  the guard's ask is a deny, so a worker claims before it edits.
- 3.1.6.0 (the coach's [probes](#probes)): `spawn_worker(..., team=,
  cwd_overlay=)` adds `--team <lineup>` and calls `cwd_overlay(lane)` before
  the worker starts (it writes the overlay into the worktree and answers
  extra worker flags); `model_call` and `fresh_judge` take an `effort` that
  reaches `one_shot` only when set. Without them the argv is as before.
- 3.1.8.0 R5 ([ISOLATION.md](ISOLATION.md)): right before a worker runs,
  `isolation/lane.py` `prepare` applies the lane's opt-ins, read from the
  goal's lineup and the lane's bio (the plan's `bio`, else the lineup's
  member for the goal's `worker` role): `isolation: container | user` makes
  the argv a `docker run` (or `podman run`) of the worker image or a `sudo -n
  -u <user>` run on a scoped state dir `<run>/state-<n>/`, `secrets: broker`
  reads the bio's `environment.secrets` refs into the worker's environment
  only, and `tools.capabilities` rides in `HALO_TOOLS_CAPS` so the worker's
  registry holds only those tools. The lane file gains `isolation`, `secrets`,
  `tools` and `opt_ins` (the lines) and the report `opt_ins: [{lane,
  lines}]`. A lane that cannot run as declared (no docker or podman, no
  `op`, a scoped user on Windows, a ref not read) fails with that one line,
  like a worker whose harness would not start. Nothing declared: the argv,
  the environment and the lane file are as before.

## In Studio

`halo studio`, started in the repo, opens the Orchestra section: the run
console described in [STUDIO-orchestra.md](STUDIO-orchestra.md#orchestra-the-run-console). Its
backend is `studio/orchestra_api.py`. The routes sit under `/api/orchestra/`
behind the same loopback, origin and token guard as every Studio route.

| Route | Answer |
|---|---|
| `GET orchestra/runs` | `[{run_id, created, state, workers, goal_what, cost_usd}]`, newest first; `state` is `running`, `planned` (3.0.9.0: waiting for the reviewed plan), `finished`, `stopped`, `dry run`, `new` or `interrupted` |
| `POST orchestra/run` | body `{what, done_when, stop_when, workers, return_cap, test, files, lineup, lead, worker, model?, dry_run?, review?}` (`review: true` = the goal's `plan: review`) -> `201 {run_id}`; an invalid goal is a 422 with `validate_goal`'s lines, a file that is not in the repo is a 422, and a second run while one is live is a 409 naming it |
| `GET orchestra/<run>` | `{run, goal, workflow, split, lanes, claims (live), merge, report, dry_run, events_count, live}` |
| `GET orchestra/<run>/events?since=N` | `{events, next}`: the run log from line N |
| `GET orchestra/<run>/file?path=<rel>` | the one-file view: `{path, base_ref, base: [lines], regions: [{key, lane, holder, state, lane_state, start_line, end_line, text}]}` |
| `POST orchestra/<run>/stop` | `{ok}`: writes stop.json, as `halo orchestra stop` does |
| `POST orchestra/<run>/release {key}` | the live claim on `key` lets go (422 when nobody holds it, 403 when `holder` is given and is not the holder) |
| `POST orchestra/<run>/steal {key}` | the run's lead takes `key` (403 when `by` is given and is not the lead) |
| `GET orchestra/<run>/plan` | 3.0.9.0: `{run_id, state, planned, mode, source: draft or split, jobs, lead_jobs, problems: [{jobs, field, text}], preflight: [the lineup's findings], units: [every key of the goal's files], decision}` |
| `PUT orchestra/<run>/plan {jobs}` | checks the jobs, keeps them as `plan.draft.json`, answers `{ok, problems, jobs}`; never approves (409 once decided) |
| `POST orchestra/<run>/approve {jobs?}` | checks the body's jobs (else the draft, else the split) and writes `plan.json` approved: `{ok, run_id, jobs, resumed}`; 422 `{error, problems}` with a problem; 409 when decided, when the goal is `plan: auto` or the run is not waiting |
| `POST orchestra/<run>/reject {reason}` | writes `plan.json` rejected: `{ok, reason, resumed}`; 422 without a reason |
| `GET orchestra/<run>/coach` | 3.0.9.0 R3: the coach's result `{run, kind, suggestions, evidence, model, computed, source_mtime, cached}`, kept in `<run>/coach.json` ([The coach](#the-coach)); 404 for an unknown run |
| `POST orchestra/<run>/coach/ask {id, refresh?}` | 3.1.3.0: the lead's paragraph for one card `{id, paragraph, error, model, role, cached}` ([Ask the model](#ask-the-model)) |
| `POST orchestra/<run>/coach/apply {id, confirm?}` | 3.1.3.0: without `confirm` the confirm card `{preview: {id, target, name, field, value, file, exists, before, after, diff}, applied: null}`; with it the write, `applied` = the record row; 422 `{error}` when the change cannot be made ([Apply and Undo](#apply-and-undo)) |
| `POST orchestra/<run>/coach/undo {apply_id}` | 3.1.3.0: `{ok, message, apply_id}`; 409 with the reason when the file changed. The mission and team coach paths take the same three verbs |
| `POST orchestra/<run>/coach/probe {k?, confirm?}` | 3.1.6.0: without `confirm` the cost line `{estimate: {k, factor, runs, ref_usd, cap_usd, total_usd, line}, running}` and nothing runs; with it `202 {started, estimate}` and the probe on a thread ([Probes](#probes)); 409 while one of the run runs; 422 for a mission, a team run or a run with no report |
| `POST coach/library/<entry>/forget` | 3.1.6.0: deletes one library entry's folder `{ok, entry, message}`; 404 for an unknown entry. Every coach GET (the three run kinds) carries `library`, `library_line` and each suggestion's `library_hits` ([The library](#the-library)) |

`<run>` is a run id or a unique prefix of one. The file view is composed by
code (`studio/orchestra_model.py`):

- `base` is the file on the finished branch `orchestra/<run-id>`, which
  grows one merge at a time; else at the split's base commit; else at HEAD.
- Each lane's claimed unit is located in `base` by its key (`index`). Its
  `text` is the lane's current version from its worktree, or its `written`
  snapshot once the worktree is gone.
- Its `state` is the live claim's own state (`claimed`, `writing` or
  `written`); else `merged` once the lane merged; else `written` when the
  lane holds a snapshot; else `claimed`.

`POST run` never blocks the request (`studio/orchestra_live.py`).
`new_run` makes the run folder, then `run()` starts on a daemon thread with
the real adapters (a dry run only asks the lead for the split and checks it
in code, writing `dry_run.json`; nothing is claimed). A second thread tails
`events.jsonl` every 0.25 s and publishes each `state`, `claim`, `merge`,
`gate` and `report` line on Studio's live feed (`EventBridge.publish_local`)
as `orchestra_<kind>`, with `session_id: "orchestra:<run-id>"` and the line
plus `run` as data. Lines a worker's child process writes reach the
browser the same way as the runner's own. `orchestra_api.RUNNER(run_dir,
goal, model)` replaces the adapters; the tests set it to the fake lead,
workers and judge (`tests/test_studio_orchestra_api.py`). Approve and reject
start a runner the same way when none waits for the run (Studio was
restarted while it waited, and `plan.wait.json` is stale), so the run takes
the decision at once.

## Walkthrough: the reel's basket.py

`halo_harness/templates/orchestra/` ships `basket.py` (five functions that
raise NotImplementedError), `test_basket.py` and `goal.example.json`.

```sh
mkdir basket && cd basket && git init
cp <halo>/templates/orchestra/basket.py <halo>/templates/orchestra/test_basket.py .
printf '__pycache__/\n' > .gitignore && git add -A && git commit -m "basket: five functions"
halo orchestra new --goal <halo>/templates/orchestra/goal.example.json
halo orchestra run --dry-run --model or:anthropic/claude-haiku-5.5   # the split only
halo orchestra run --model or:anthropic/claude-haiku-5.5             # the whole run
halo orchestra lanes && halo orchestra report
git log --oneline orchestra/<run-id>                                  # five merges
```

The lead splits the five functions into five jobs; five workers write
them in five worktrees at the same time; the merge takes them one at a time
(a module-level line such as `from decimal import ...` belongs to the
whole-file unit, which overlaps every function, so a worker keeps its change
inside its own function; when two pieces do change the same lines, a fresh
judge resolves them); the gate runs `python -m unittest`; the report lists the
checks. The finished branch is left for you to review and merge.

## Module functions

| Module | Functions |
|---|---|
| `workflow` | `designed_graph(workers, after=None, labels=None)`, `with_layers(graph, after, labels)`, `advance(graph, step_id, state)`, `loop_back(graph, lane)`, `ready(graph)`, `step`, `steps_of_kind`, `summary`, `validate_graph` |
| `goal` | `Goal`, `validate_goal`, `load_goal`, `save_goal`, `new_run(repo_root, goal, lead_holder=None, parent=None, name="")`, `list_runs`, `latest_run`, `resolve_run`, `run_meta`, `set_lead_holder`, `repo_root_of` |
| `index` | `index_file(path, root=None)`, `index_text(text, rel)`, `unit_for_line`, `units_for_lines`, `overlaps`, `covers`, `split_key` |
| `claims` | `ClaimLog(run_dir, clock=time.time)`: `active`, `claim`, `mark_writing`, `mark_written`, `release`, `steal`, `reassign`, `expire_stale`, `held_by`, `conflicts`, `is_lead`; `holder_for(session_dir)` |
| `guard` | `ClaimGuard(run_dir, holder)`, `install_from_env(engine, session_dir)` (also joins the lane), `run_dir_from_env()` |
| `events` | `log(run_dir, kind, text, lane=None, **data)`, `read(run_dir, since=0)`, `emit(session, kind, data, run_dir=None)`, `format_line` |
| `split` | `split_goal(run_dir, goal, units, *, call_model, base)`, `validate_jobs`, `parse_answer`, `split_prompt`, `load_split`, `StopRun` |
| `workers`, `lanes` | `start_workers(run_dir, goal, jobs, *, spawn)`, `run_lane`, `join_lane`, `record_written`, `finish_lane`; `Lane`, `load_lane`, `list_lanes`, `lane_rows`, `unit_text` |
| `merge`, `hunks` | `merge_lanes(run_dir, goal, lanes, *, judge, base, respawn)`, `merge_order`; `extract_hunks`, `judge_prompt`, `parse_resolution`, `apply_resolution` |
| `handoff_spec`, `handoff`, `handoff_run` | `shape_problems`, `clean`, `resolve`, `upstream_ids`, `layers`, `edge_label`; `start_base(run_dir, lane, split_base)`, `deliver(run_dir, lane)`, `gives_text`, `record_gave(run_dir, lane, reply)`, `artifacts_dir`; `start_layered(...)`, `stuck(lanes)`; `merge.merge_heads(run_dir, lane_n, heads)` |
| `gate` | `run_tests(run_dir, goal, cwd)`, `record_equals_disk(run_dir, lanes, ref)`, `quality_gate(run_dir, goal, lanes, cwd)` |
| `report` | `write_report(run_dir, *, goal, lanes, gate, status, stop_reason)`, `format_report(report)`, `load_report` |
| `plan`, `plan_check` | `await_plan(run_dir, flow, jobs, *, check_stop)`, `approve(run_dir, jobs, by=)`, `reject(run_dir, reason, by=)`, `apply`, `normalize`, `current_jobs`, `read_decision`, `write_draft`, `is_planned`, `waiting_alive`; `plan_problems(jobs, unit_keys=, cwd=, state_dir=)`, `validate_plan` (re-exported by `workflow`) |
| `coach`, `coach_rules`, `coach_orchestra_rules`, `coach_lane_facts`, `coach_prices`, `coach_mission_rules`, `coach_team_rules` | `coach(run_dir, *, catalog=None, cwd=None, state_dir=None)`, `cached(run_dir)`, `overlay(result, run_dir)`, `format_card(result)`, `run_kind`, `source_mtime`; the rules once (`prompt_rules`, `outputs_rules`, `model_rules`, `tools_rules`, `wait_pairs`, `conflict_pairs`, `structure_rules`, `coordination_rules`); `orchestra(run_dir, ...)`; `lane_facts`; `catalog(state_dir)`, `price_of`, `best_for`, `price_words`; `mission`; `team` (one thin loader per run kind, `coach_<kind>_rules.<kind>`) |
| `coach_ask`, `coach_apply`, `coach_record` | 3.1.3.0: `ask(run_dir, result, id, *, refresh)`, `ask_all`, `lead_of`, `read_store`; `preview(result, id, run_dir)`, `apply(result, id, run_dir)`, `ApplyError`; `undo(apply_id)`, `applies`, `states(run_dir)`, `summary(run_dir)`, `summary_line`, `note_run`, `runs_since` |
| `coach_probe`, `coach_probe_schema`, `probe_runs`, `probe_overlay`, `coach_compare`, `coach_compose`, `coach_probe_card` | 3.1.6.0: `estimate(run_dir, k, factor)`, `draft(run_dir, k)`, `probe(run_dir, *, k, factor, on_step, rng)`, `start`, `live`, `read`, `probe_line`; `facts(run_dir)`, `clean(kind, raw, facts)`, `for_bio`, `merge`; `create`, `plan_jobs`, `Budget`, `real_adapters`, `run_one`, `run_all`, `cleanup`; `scope_files`, `flags`, `write_scope`, `writer`; `deliverable(run_dir, patch_path=)`, `judge_prompt`, `judge(goal, rows, *, model, rng)`, `parse_verdict`, `contrast`; `compose(cands, rows, ref)`, `changes(overlay, facts)`; `card(run_dir)`, `status`, `table`, `preview`, `apply`, `format_probe` |
| `coach_library`, `coach_experience`, `coach_citations`, `coach_library_share`, `coach_probe_prompt` | 3.1.6.0 R3: `born(result, s, run_dir, applied)`, `write(doc, experience, overlay, files)`, `read(entry)`, `entries()`, `mark_undone(apply_id)`, `forget(entry)`, `matches(run_dir, state_dir, limit=3)`, `stored_files`, `safe_rel`; `project_of(run_dir, kind, cwd)`, `remote_path(url)`, `context_of`, `overlay_of`, `markdown`, `section`; `matches`, `cite(result, run_dir)`, `line(rows)`, `lessons(run_dir)`, `same_project`; `answer(fields, *, by, hub)`, `fetch(harness, entry)`; `draft_prompt(f, k, cards, lessons)` |
| `run`, `adapters` | `run(run_dir, *, model_calls, spawn, judge, clock, on_event)`, `request_stop`; `model_call`, `spawn_worker` (3.1.6.0: `team=`, `cwd_overlay=`), `fresh_judge`, `real_adapters` |
