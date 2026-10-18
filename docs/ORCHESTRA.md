# The Orchestra

Halo 3.0.3.0. Several agents write to the same files at the same time and
nothing is lost. The idea comes from Kem Tossoun's reel "5 agents write to
the same file at the same time and nothing is lost" (Glitch Cat Club); this
page is Halo's version of it.

**In a team (Halo 3.0.8.0):** a team stage of `kind: orchestra` starts an Orchestra run with the stage's goal (the files of its write blocks when the goal names none); see [TEAM.md](TEAM.md).

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
```

`--review`, `plan`, `approve` and `reject` are the reviewed plan: see
[Review the plan](#review-the-plan).

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
come back empty: a model id its provider's catalog does not know (requests for it 404 and the member comes back empty), an assignment or org position naming a bio that does not exist, a bio whose `tools.allow` is an empty list (it may call no tool), and a `tiers` problem ([ROLES.md](ROLES.md#tiers-halo-3070)). Each
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
`after`, `base`, `gave`) are under [Hand-offs](#hand-offs).

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
halo orchestra plan [RUN]                   the plan as a table (job, after, bio, model, title, claims, needs), its problems
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
[STUDIO.md](STUDIO.md#the-plan-canvas-3090)); its draft lives in
`<run>/plan.draft.json` until you approve it.

## The report

report.json: `run_id`, `status` (`finished` or `stopped`), `stop_reason`,
`branch`, `finished` (the sha, null when stopped), `tests_ok`, `tests_tail`,
`cost_usd` (lead + workers + judges), `ts`, `elapsed_s`, `goal_done_when`,
`lanes` (`lane`, `title`, `state`, `pieces_returned`, `cost_usd`) and
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

## In Studio

`halo studio`, started in the repo, opens the Orchestra section: the run
console described in [STUDIO.md](STUDIO.md#orchestra-the-run-console). Its
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
| `goal` | `Goal`, `validate_goal`, `load_goal`, `save_goal`, `new_run(repo_root, goal, lead_holder=None)`, `list_runs`, `latest_run`, `resolve_run`, `run_meta`, `set_lead_holder`, `repo_root_of` |
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
| `run`, `adapters` | `run(run_dir, *, model_calls, spawn, judge, clock, on_event)`, `request_stop`; `model_call`, `spawn_worker`, `fresh_judge`, `real_adapters` |
