# Workflows

Read this when you write or run a pack's workflow: its stages compiled to an Orchestra run, its typed artifacts, events and memory.

Halo 3.2.0.0 R5. A pack ships WORKFLOWS: declarative files any compatible
model can run. A workflow names what it needs, what it takes and gives, its
stages (in order or at once), their conditions, roles, budgets, gates and
checks; Halo COMPILES it to an Orchestra goal, its hand-offs and a pinned
plan ([ORCHESTRA.md](ORCHESTRA.md)), and the Orchestra runs it. There is no
second engine: a workflow run is an Orchestra run (`halo orchestra status |
report | stop <run>`, Studio's Orchestra section). Nothing changes for a
repo with no pack and no workflow file.

The contract (every key, the tables) is [EXTENSION_API.md](EXTENSION_API.md#workflow-contracts);
the commands are [COMMANDS-workflows.md](COMMANDS-workflows.md).

## The file

`<pack>/workflows/<name>.yaml`, its name in pack.yaml's
`contributes.workflows`. The doc-review reference pack's
(`halo_harness/templates/packs/doc-review/workflows/review.yaml`), abridged:

```yaml
name: review
description: Review the Markdown files under a folder and write one review report.
prerequisites: {grants: [bash], capabilities: [docs.review]}
inputs:
  docs: {type: path, required: true}           # text | path | json | artifact:<schema>
  style: {type: text, default: short}
outputs:
  report: {type: "artifact:review-report", from: write}
stages:
  - id: read                                   # one job per Markdown file, all at once
    title: Read {item}
    brief: Read {item} and list what is unclear, wrong or missing, one finding per line.
    role: reviewer                             # the pack's bio doc-review--reviewer
    for_each: {input: docs, match: "*.md"}
    needs: [docs.review]
    gives: [{name: notes, kind: summary}]
    retries: 1
    timeout_s: 900
  - id: judge
    title: Judge the findings
    brief: Keep the findings that matter. Reply with nothing when none matters.
    role: reviewer
    after: [read]
    takes: [{from: read, take: notes}]
    gives: [{name: verdict, kind: summary}]
    gate: human                                # you approve the plan before it runs
    budget_usd: 0.5
  - id: write
    title: Write the review report
    brief: "Write the review report as JSON: {summary, findings: [{file, line, finding, severity}]}."
    role: writer
    after: [judge]
    when: {output: judge.verdict, not-empty: true}   # skipped when the judge kept nothing
    takes: [{from: judge, take: verdict}]
    gives: [{name: report, kind: artifact}]
    retries: 2
    verify: {evidence: [report]}
done_when: The report lists every finding the judge kept, each with its file.
budget_usd: 2.0
checkpoint: true
```

`gives` and `takes` are the Orchestra's hand-off words (`files`, `summary`,
`artifact`; `all`, `summary` or a give's name). A stage without `after` (and
without `takes`) starts at once, beside the others. A bad file is one
manifest line naming the key and its line, so the pack does not install or
run until it is fixed:

```
workflows/flow.yaml line 4: stages.draft.after: draft waits for itself (its after and takes go round in a circle)
workflows/flow.yaml line 6: stages.audit.role 'auditor' is not a bio of the pack (by name or kind) nor a bio Halo ships
workflows/flow.yaml line 4: outputs.notes: no stage gives it -- stage write gives summary (summary); give it {name: notes, kind: artifact}
workflows/flow.yaml line 4: inputs.docs.default is a path (a string relative to the repo) (the input's type is path)
```

## The compile

`halo workflow check doc-review/review --input docs=docs` compiles without
running (`halo_harness/workflows/compile.py`):

```
doc-review/review compiles: 4 job(s), plan review, budget $2.00
  job-1   read       doc-review--reviewer     after -                        Read docs/guide.md
  job-2   read       doc-review--reviewer     after -                        Read docs/intro.md
  job-3   judge      doc-review--reviewer     after job-1:notes, job-2:notes Judge the findings
  job-4   write      doc-review--writer       after job-3:verdict            Write the review report
```

- The inputs are checked (a path is inside the repo and there; an artifact
  input matches its schema), then the prerequisites (each grant given, each
  capability available here, each tool on PATH, each file there) and every
  stage's `needs`. A problem is one line and nothing runs.
- Each stage becomes a job (one per file for `for_each`), `job-1..N` in the
  file's order: its `bio` from the role, `after` and `handoff.needs` from its
  `after` and `takes`, `handoff.gives` from its `gives` (an artifact is saved
  as `<name>.json`), its claims from a `files` give's paths.
- The Goal: WHAT YOU WANT from the description and the inputs, DONE WHEN and
  STOP WHEN from the file, `workers` the number of jobs, `return_cap` the
  largest stage `retries`, `test` every stage's `verify.test` joined with
  `&&`, `lineup` the pack's lineup whose `workflows:` names it, `plan:
  review` when a stage has `gate: human`, `budget_usd` the file's, and
  `workflow`: the pinned plan (its stages, jobs, outputs, bounds).
- A `when` on an input is resolved here: a false one skips the stage (the
  run's log says so) and a stage after it runs after the skipped stage's
  own upstreams.

## The run

`halo workflow run doc-review/review --input docs=docs` compiles and runs it
now as an Orchestra run (`halo orchestra run`: the lineup preflight, a line
per step, the report). `halo orchestra new --workflow doc-review/review
--input docs=docs` only makes the run; `halo workflow run ... --as goal`
queues it for the supervisor (`halo supervise`, 3.1.8.0), which runs it and
resumes it from its checkpoint (a build without the supervisor says so in
one line). In Studio, the Pack Manager's Run <workflow> and Orchestra's own
Start view ("or run a pack's workflow" under the goal form, 3.2.1.0 R2) fill
in the same form, and its Run compiles the workflow the same way.

- **The pinned plan.** The lead is asked once to refine each job's brief for
  this repo; it may not add, drop, merge or reorder a job (asked again once,
  then the workflow's own briefs run). A reviewed plan (`gate: human`) may
  change titles, bios and models, never the stage set. Nor does the
  supervisor's replanner (3.2.1.0 R2): a workflow run is never paused for a
  replan, and with `supervise.replan` set its goal says "a workflow run keeps
  its stage set (its plan is pinned by doc-review/review)" once.
- **Each lane** gets its stage in its prompt: the item, the brief, what
  verifies it, the schema its artifact must match. A `when` on an upstream
  output is checked when the lane starts; a false one skips it (`worker-4
  skipped: stage write when output judge.verdict is not empty is false (it
  is nothing)`, the step reads skipped). An `after_event` holds the lane until
  the event comes. A stage at its `budget_usd` stops the run before another pass,
  and so does the run at the workflow's own `budget_usd` (3.2.1.0 R2: `STOP:
  budget: the run spent <spent> of <cap> USD (the workflow's budget_usd)`).
- **The gate** runs the tests and the record check, then reads every typed
  output and checks it against its schema, and reads the evidence: a
  mismatch, a missing artifact or missing evidence sends that lane back with
  one line per problem, up to its stage's `retries`; then the run stops.
  Each evidence item is also a line under its lane in the gate's verdict
  (`evidence report: 213 bytes, sha256 3f9a1c0b7d2e`, or `evidence report:
  missing`), and the conflict judge reads the incoming lane's (3.2.1.0 R2).
- **The report** lists the artifacts (schema, viewer, state, path), the
  workflow's stages, each lane's evidence lines, the workflow's budget with
  the run's spend (`budget: the run spent 0.0400 of 2.0000 USD (the
  workflow's budget_usd, a stop)`), and any bound a run does not hold yet.

## Artifacts

An output of type `artifact:<schema>` is a JSON document its stage saves as
`lanes/<n>/artifacts/<name>.json`; the schema is the pack's
`artifacts/<schema>.json` (JSON schema's type, properties, required, items,
enum, plus `x-halo-view: table | markdown | keyvalue`). When the run
finishes it is copied to `<run>/artifacts/<name>/`. Studio draws it by its
view: in the pack's own section (a panel `{kind: artifact, schema:
review-report, source: latest}` shows the newest run's) and in the Report
panel's Artifacts tab of Orchestra's run view.

## Events

A pack's event kinds may have a schema (`events/<kind>.json`).
`publish_event` checks a declared kind's data against it and publishes a
mismatch with its problems (Studio shows them under the line); a disabled
pack's event is refused with one line. Every event is kept in the pack's
events log, so subscriptions work from any process: a bio's trigger
`{event: doc-review:review.done}` starts it once on that event, and a stage's
`after_event: doc-review:review.done` waits for it.

## Memory

A stage's worker writes to its pack's memory namespace with
`ext.memory.write(namespace, text, provenance)`: each note gets a
`_meta.json` (source workflow run, its run and stage, when, retention keep |
`days:<n>` | run, the packs it is shared with). A namespace reads its own
notes plus those shared with its pack; a `retention: run` note goes when the
run ends; `halo recall prune` removes notes past their days; `halo recall
--namespace doc-review/reviews --provenance` lists them.

## Bounds

| Bound | Held by |
|---|---|
| a stage's `retries` | the gate: the stage's own return cap |
| a stage's `timeout_s` | the worker's time limit |
| a stage's `budget_usd` | checked before each pass of the stage's worker; at it the run stops |
| `gate: human` | the plan review before the run starts (once, for the whole run); a hold before one stage is not a thing yet |
| `after_event` | the lane waits for the event |
| `checkpoint` | the run resumes at its first unfinished step |
| the workflow's `budget_usd` | a stop (3.2.1.0 R2): the goal's budget; before each pass of any stage's worker the run's spend (the lead's split, every lane, the judge's conflicts) is checked against it, and at it the run stops, in a plain run as under `--as goal` |
