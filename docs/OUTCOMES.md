# Verified outcomes and measured routing

Read this when you want to know what an agent's work showed (its tests, sources, commands, files), how each outcome is recorded per bio and model, and how a bio can route to the model that succeeded most here.

Halo 3.1.8.0 R3. Every agent task -- an Orchestra lane, a session's
sub-agent -- ends with **evidence** of its kind, read out of its transcript:
the tests it ran, the sources it read, the commands it reproduced, the files
it wrote. Nothing new is asked of the model, and the agent's own summary is
kept apart: a verdict reads the evidence, never the summary. Every outcome
is one line in `~/.halo/coach/outcomes.jsonl`, per bio and model;
`halo models --measured` and the Roles pill show measured success per model
and task kind; and `models.preference: measured` routes a bio to the model
that has succeeded most at its kind here. Halo 3.1.9.0 R3: the `auto` pick
weighs the same numbers, the roster drops a model that keeps failing a kind,
and `halo outcomes learned` / `forget` show and reset what was learned
([What was learned](#what-was-learned)). You see every verdict with its
evidence; nothing here is a classifier or a refusal.

## The kinds

One mapping (`halo_harness/outcomes/kinds.py`), read in this order: the
bio's `kind` (coder -> code, researcher -> research, reviewer and judge ->
review, planner -> plan, writer -> writing, media -> media, ops -> check);
else the first word Halo knows among the names around the agent (its role,
its lineup alias, its bio or agent name: `Explore` is research, `Plan` is
plan, a `tester` is a check); else `code` for an Orchestra lane (a lane
edits code units) and `other` for a sub-agent.

## Evidence

`outcomes/evidence.py` `gather(transcript, bio, cwd=...)` reads the tool
calls and their results:

| Item | What counts | Shape |
|---|---|---|
| `tests` | a shell call that runs tests (pytest, unittest, `python -m tests.x`, `run_all.py`, npm / pnpm / yarn test, jest, vitest, go / cargo / dotnet test, mvn / gradle test, `make test`, tox ...), or the goal's own `test`, or the bio's `acceptance.test` | `{command, exit, passed, failed: [names], tail}` |
| `diff` | the files it wrote, with `git diff --numstat` when the folder is a repo (a new file counts as all added) | `{files, added, removed}` |
| `sources` | WebFetch (and a `curl` / `wget` of a URL), WebSearch, Read, Grep | `{kind: fetch, search or read, target, when}` |
| `reproduction` | a check's shell calls that are not test runs (the last ten) | `{command, exit, tail}` |
| `written` | Write, Edit, NotebookEdit targets | `[paths]` |
| `acceptance` | the bio's acceptance on the final text, or the spawn path's own verdict | `{expect, met, why}` |

Plus `summary` (the final text, kept apart), `cost_usd`, `model`, `bio`,
`sessions`. A call that failed is not evidence (a fetch that errored read
nothing). A shell call's exit is its `[exit code N]` note; no note is 0; a
timeout, an abort or a result capped in the transcript is unknown (`?`).

Where it is written:

- an Orchestra lane: `<run>/lanes/<n>/evidence.json`, after each worker pass,
  over every session the lane's workers ran (`session_ids`, each found in
  `~/.halo/sessions/`);
- a session's sub-agent: beside its transcript,
  `<session>/subagents/agent-<id>.evidence.json` (the transcript is
  `agent-<id>.jsonl`), when it ends -- a foreground spawn, a background one,
  a fan-out job or a resumed task.

What a person reads of it (`outcomes/lines.py`), never the summary -- a
kind's own item always has its line, "none" included:

```
tests: `python -m pytest -q test_basket.py` exit 1, 4 passed, failing: test_basket.py::test_total; `python -m unittest -q test_basket` exit 0, 5 passed
sources: 4 -- search python decimal ROUND_HALF_UP quantize; fetch https://docs.python.org/3/library/decimal.html; read docs/ROUNDING.md (+1)
reproduction: `curl -sI http://localhost:8080/health` exit 0 -- Content-Type: application/json
written: basket.py (+9 -3)
acceptance: 'non-empty' met
```

## The judge reads the evidence

In an Orchestra run (`orchestra/gate.py`, `outcomes/lane.py`):

- **One rule, before the record check.** A `code` lane whose work ran no
  test (when the goal has a `test`) goes back to its worker once with "no test
  run in this lane's work: run <test>"; a `research` lane with no source goes
  back once with "no source fetched or read". Each send-back is one `gate`
  line in events.jsonl ("lane 1 sent back for its evidence: ...") and counts
  as a return. Bounded: never twice for the same lane (`evidence_returned` on
  its file), never past the return cap, and never for a lane whose worker left
  no transcript (nothing to read).
- **The verdict carries the evidence.** The gate's result holds each lane's
  evidence lines; so does each lane of `report.json` (`lanes[].evidence`),
  `halo orchestra report` prints them under the lane, and the supervisor's
  `failure.report.evidence` keeps them per lane ([SUPERVISE.md](SUPERVISE.md#verified-outcomes)).
- **The conflict judge.** When two lanes changed the same lines, the fresh
  judge's prompt gains an EVIDENCE block: the incoming lane's and every
  merged lane's (that wrote the file) tests, sources and reproductions.
- **A team member's acceptance.** A sub-agent checked against its bio's
  `acceptance` records the verdict -- met or not, why, and how many attempts
  (the critique's retry is the second) -- in its evidence.

## outcomes.jsonl

One line per agent task, in `~/.halo/coach/outcomes.jsonl`
(`outcomes/records.py`):

```json
{"run": "20261023-213446-5249", "task": "lane 1", "source": "orchestra", "run_dir": "<run folder>",
 "bio": "", "model": "or:mock/lane-coder", "kind": "code", "outcome": "returned", "check": "gate",
 "returns": 1, "cost_usd": 0.004, "tests_passed": 9, "tests_failed": 1, "sources": 1,
 "evidence": "<run folder>/lanes/1/evidence.json", "ts": 1792809287.962, "picked": "none", "reason": ""}
```

Halo 3.1.9.0 R3: `picked` says whether the model was picked when the agent
spawned -- `auto` (an `auto` bio), `measured` (a `measured` bio), or `none`
(a pinned model, the call's own `model:`, a tier's model, an Orchestra lane,
or a pick that fell back to main's model) -- and `reason` is that pick's one
line ("" without one), the words the Roles pill shows. Nothing else in the
row changed; an older row without them reads as `none`.

The outcome: an Orchestra lane's comes from the run's report -- the run
finished: `passed` (never sent back) or `returned` (sent back at least once);
the run stopped: `failed` for a lane that failed or reached the return cap,
else `stopped`. A sub-agent's is its acceptance check's (`passed` first time,
`returned` after the retry, `failed`; a background, fan-out or resumed child
gets the same check on its final text), else its stage gate's, else
`stopped`, `failed` (it ended on an error) or `done` (nothing checked it).
`check` names what gave the verdict (`gate`, `acceptance`, `stage`, or empty).
The run's rows are written once per report (the report and the coach both
record them); `runs.json` gains `outcomes: n`.

```sh
halo outcomes                       # the newest 50 tasks
halo outcomes --kind code --since 7d
halo outcomes --bio auto-coder --json
```

## Measured success

`outcomes/measured.py` `success_by_model_kind` -> `{(model, kind): {n,
passed, returned, failed, rate, cost_mean}}`. A rate counts the tasks
something checked whose outcome is `passed`, `returned` or `failed` (the
newest row per task); `stopped` and `done` rows are not rated, nor a row
whose model is `auto`, `measured` or empty. `rate` is first-time success,
`passed / n`. It is shown and routed on from 3 checked tasks.

```
$ halo models --measured
model                                        kind        n  passed   rate  mean cost
or:mock/auto-cheap                           code        3    1/3     33%  $  0.0040
or:mock/auto-cheap                           writing     2    2/2    100%  $  0.0020  (fewer than 3: not routed on)
or:mock/auto-eyes                            code        5    4/5     80%  $  0.0310
```

A catalog row's `measured` gains `outcomes: {kind: {n, passed, rate}}`; the
best-at line appends "measured: code 4/5"
([MODELS-references.md](MODELS-references.md#measured-success-halo-3180)); `halo
models analyze` lists the table; the roster's model line says "code 4/5"
among what was measured; Studio's best-at column shows it in the line (and on
hover), and a measured pick's reason ends "(measured 4/5 code)" on the Roles
pill and in the Inspector's Live tab.

## Route by it

`models.preference: measured` on a bio (with `models.needs` and the lineup's
`budget.band` as for `auto`): the model is picked when the agent spawns.
Among the candidates that carry the task's needs -- the ones the `auto` pick
weighs -- those measured for the bio's kind here from 3 checked tasks are
ranked by their rate; a tie goes by the band's own rule. With nothing
measured for that kind yet, the pick is the `auto` pick, its reason saying
so. The Roles canvas shows the source word `measured`. The shipped `auto`
lineup's bios stay `auto`. See [ROLES.md](ROLES.md#measured-a-bio-that-routes-by-what-succeeded-halo-3180).

## What was learned

Halo 3.1.9.0 R3 (`outcomes/learn.py`): the `auto` pick itself weighs these
numbers for the member's task kind -- the checked tasks of the last 30 days,
from 3 of them, a weight of `0.5 + 0.5 x rate` on each candidate's score --
and the model roster drops a model whose rate for a kind is under 34%, with
one line naming it and its numbers. The rule, the drop line and the switch
are in [ROLES.md](ROLES.md#auto-learns-halo-3190); these two commands show
and reset what it learned:

```
$ halo outcomes learned
Learning on; the last 30 days; weighed from 3 checked tasks (weight 0.5 + 0.5 x rate); dropped below 34%.
model                                        kind        n  passed   rate  weight  picks  dropped
ant:fable                                    research    3    0/3      0%   0.500   0/3   dropped for research
dbx:databricks-gemini-9-flash                media       5    0/5      0%   0.500   5/5   dropped for media
or:v/cheap                                   plan        3    1/3     33%   0.666   3/3   dropped for plan
or:v/cheap                                   code        2    2/2    100%   1.000   2/2   (fewer than 3: not weighed)
or:v/ears                                    code        4    1/4     25%   0.625   4/4   dropped for code
or:v/eyes                                    code        4    4/4    100%   1.000   3/4
picks = tasks whose model was picked at spawn (auto / measured); `halo outcomes forget --model REF` starts a model over, ...
```

(`halo models --measured` keeps its all-time numbers -- or:v/eyes reads 4/5
there with a failure 40 days old -- and marks the dropped rows "dropped for
code (1/4 in the last 30 days)".)

`--kind K` and `--model REF` narrow it; `--json` prints `{"learn": the
settings, "since": the window's start, "rows": [{model, kind, n, passed,
returned, failed, rate, cost_mean, picked, weight, counted, dropped}]}`. With
`models.learn: false` the first line says the pick and the roster ignore
the numbers.

```sh
halo outcomes forget --model or:v/ears --kind code --yes   # that model starts over at code
halo outcomes forget --before 2026-09-01 --yes             # forget the old rows
halo outcomes forget --yes                                 # start over entirely
```

`forget` removes the rows matching every filter it is given (every row with
none), keeps the other lines exactly as they were, and keeps the file before
beside it as `outcomes.jsonl.bak-<time>`; one line says how many rows went
and where the backup is, and the best-at cache rebuilds on its next read.
Without `--yes` it asks in a terminal, and elsewhere says how many rows match
and removes nothing.

## Two examples

**A lane that ran no test.** A two-lane run of the reel's basket with the
goal's test `python -m unittest -q test_basket`; lane 1's worker edits
`basket.py` and stops. The gate sends it back once:

```
lane 1 sent back for its evidence: no test run in this lane's work: run python -m unittest -q test_basket
```

Its second prompt ends "The gate sent your piece back: no test run in this
lane's work: run python -m unittest -q test_basket."; the second pass runs
the tests, the run finishes, the report prints lane 1's evidence under it,
and outcomes.jsonl has lane 1 `returned (gate)` and lane 2 `passed (gate)`.

**A bio that routes by what succeeded.** A coder bio with `preference:
measured` and `needs: [tools]`. Before anything was measured:

```
auto: or:mock/auto-cheap -- nothing measured for code yet, so the auto pick: the bio asks for tools, the best tools model within 3x the cheapest ($0.05/$0.20 per 1M)
```

After five checked code tasks on `or:mock/auto-eyes` (4 passed) and three on
`or:mock/auto-cheap` (1 passed):

```
auto: or:mock/auto-eyes -- the best measured code rate here among the tools models ($0.30/$1.20 per 1M) (measured 4/5 code)
```
