# Flows

Halo 3.0.4.0. A flow takes an input, runs it through agents in roles, hands
the result to an org (the marketing org researches and plans), passes the
org's image prompt to ComfyUI, shows you the render, and on your yes writes
the posts and starts the metrics. Every artifact lands in a design project
(`~/.halo/design/<slug>/`, the same folder Halo Design and Studio's Design
mode open). Posting and metrics go through Postiz in a later round; until
then the post step is a dry run and the metrics step a stub.

```sh
halo media init --url http://<comfy-host>:8188      # once: the ComfyUI server
halo flow new social-post --project demo-post       # ~/.halo/flows/social-post.flow.yaml
halo flow run social-post --brief "a one-line teaser for the 3.0.4 release" --yes
```

Without `--yes` the run stops at each human gate and waits; answer it from
any terminal with `halo flow answer <run> <step> accept|redo "<text>"|stop`.

## The flow file

`~/.halo/flows/<name>.flow.yaml` (yours), or `<project>/.halo/flow.yaml`
(a project's; it wins when its `name:` matches). The shipped templates live
in `halo_harness/templates/flows/`; `halo flow new <template>` copies one.

```yaml
name: social-post
version: 1
project: "{{intake.project}}"        # the design project slug (default: the flow name)
budget_usd: 6.00                      # the whole run; a step may cap lower
steps:
  - id: intake
    kind: intake
    form: {brief: text, platforms: [youtube, instagram, x, tiktok], assets: files, budget_usd: number}
  - id: plan
    kind: roles
    uses: lineup:standard
    roles: [planner, researcher]
    inputs: {brief: "$.intake.brief"}
    budget_usd: 0.50
  - id: marketing
    kind: org
    uses: org:marketing
    inputs: {goal: "$.plan.text", platforms: "$.intake.platforms", assets: "$.intake.assets"}
    budget_usd: 3.00
  - id: render
    kind: render
    uses: "comfy:text-to-image-qwen"   # a starter, a saved workflow name, or a file
    set: {prompt: "$.marketing.positions['Art Director'].prompt", width: 1080, height: 1350, seed: random}
    outputs: {kind: image, artboard: "hero"}
  - id: approve
    kind: confirm
    gate: human
    on_fail: redo:render
  - id: publish
    kind: post
    uses: postiz
    live: false
    inputs: {text: "$.marketing.positions.Copywriter.text", media: "$.approve.accepted", platforms: "$.intake.platforms"}
  - id: measure
    kind: metrics
    uses: postiz
    every: 6h
    days: 7
  - id: done
    kind: done
```

**References.** An `inputs` or `set` value that starts with `$.` reads an
earlier step's output: `$.<step id>.<path>` with dots, `['quoted key']` (for
keys with spaces) and `[n]` list indexes, e.g. `$.approve.accepted[0]`.

**`halo flow validate <name>`** prints plain lines: an unknown kind, a
duplicate id, a reference to a later or unknown step, a `confirm` with no
`render` before it, an `on_fail` that is not `redo:<an earlier render>`, an
`org:` that `halo org list` does not have, a `lineup:` that does not
resolve, a budget that is not a number. Lines starting with `warning:` do
not stop a run: a `comfy:` workflow that is neither a starter, a file nor a
saved workflow in the inventory cache (checked again on the server at run
time), `live: true` with no `POSTIZ_API_KEY` or `~/.postiz/credentials.json`,
and step budgets adding up to more than the run budget.

## The steps

| kind | what it does | output |
|---|---|---|
| `intake` | checks the run's input against `form` (text is required, a list field takes values from its choices and defaults to all of them, files must exist) and copies dropped files into `<project>/assets/` | the form values + `project` |
| `roles` | one call per role in `roles`, in order, each seeing the earlier answers; the model is `--model`, else the lineup's role table, else the session default | `{text, per_role, models, cost_usd}` |
| `org` | runs the org with the goal and the other inputs; its budget is min(the org's, the step's, what is left of the run's) | `{text, cost_usd, positions: {title: {text, prompt?}}}` |
| `render` | builds the workflow with `set` (refs resolved, `--set` on top), queues it, waits, fetches every output over HTTP into an artboard | `{artboards: [{id, kind, path, prompt_id}], prompt_id, prompt, workflow, set}` |
| `confirm` | the human gate over the render | `{accepted: [paths], artboards, rounds}` |
| `post` | `live: false`: one dry-run entry per platform in `<project>/posts.json`; `live: true` stops (Postiz arrives in R4) | `{posts, dry_run, path}` |
| `metrics` | logs one `metric` line with its schedule | `{}` |
| `done` | marks the end | `{}` |

A position of the org whose tools include `mcp__comfyui__*` (the Art
Director) gets its final text as `prompt` too, cleaned of fences, labels
and quotes. A render writes `artboards/<id>/render.png` (or `.mp4` for
video) and `source.json {"app": "comfyui", "workflow", "prompt_id", "set"}`,
then `Project.snapshot()`: a redo writes over the same artboard, so every
round is a new version (`v1`, `v2`, ...).

## The human gate

A `confirm` step (and an org position with `requires_approval: true`)
writes `steps/<n>.gate.json`, logs a `gate` line, and waits for
`steps/<n>.answer.json`:

```json
{"id": "<run>:<step>", "run": "<run>", "step": "approve", "n": 5, "round": 1,
 "position": "You", "text": "<artboard paths>\n<prompt>", "artboards": [...],
 "actions": ["accept", "redo", "stop"], "target": "render", "opened": 1760000000.0}
```

```json
{"id": "<run>:<step>", "round": 1, "action": "accept|redo|stop", "instruction": "warmer colours", "ts": 1760000000.0}
```

`halo flow answer <run> approve redo "warmer colours"` writes the answer
(Studio writes the same file). `accept` moves on; `redo` runs the
`on_fail` render again with the instruction appended to its `set.prompt`
and opens the gate again (at most 5 renders, like the org approval gate's
own revision cap); `stop` stops the run. An answer for another id or round
is ignored. For an org gate the id is `<run>:<step>:<position>` and `redo`
re-runs that position with the instruction. `--yes` accepts every gate, and
`halo flow stop` answers an open gate with stop.

## The run folder

`~/.halo/flows/runs/<YYYYMMDD-HHMMSS-xxxx>/`:

- `flow.json` -- `{name, version, run, created, source, project,
  project_path, budget_usd, intake, spec, overrides, status:
  pending|running|finished|stopped, cost_usd, steps: [{id, kind, state}]}`;
  a step's state is `pending|running|waiting|done|failed|skipped`.
- `steps/<n>.json` -- `{id, kind, started, finished, cost_usd, output,
  error, rounds}` (`n` is the step's 1-based position; a render keeps
  `instructions`, the redo texts).
- `events.jsonl` -- `{ts, elapsed_s, step, kind, text, data}` with kind
  `state|step|gate|post|metric|report|note`, appended under a lock; the
  session feed gets `flow_state|flow_step|flow_gate|flow_post|flow_metric|
  flow_report` (data = the line plus `run`).
- `stop.json` -- `{reason, ts}`, written by `halo flow stop`; the runner
  stops between steps and inside a gate.
- `report.json` -- `{run, name, project, project_path, status, stop_reason,
  created, finished, elapsed_s, cost_usd, budget_usd, steps: [{id, kind,
  state, cost_usd, elapsed_s, rounds, error}], artboards: [{step, id, kind,
  path, prompt_id}], accepted, posts: [{platform, dry_run, chars, media}],
  metrics: {notes, summary}}`.

The run stops (status `stopped`, a reason in the report) when its budget is
spent, when `stop.json` appears, when a gate answers stop, or when a step
fails. `halo flow resume <run>` picks up at the first unfinished step: done
steps are not run again, a render killed half-way renders again into the
same artboard, a gate left waiting opens again.

## Posts and metrics

`posts.json` and `metrics.jsonl` sit beside `design.json` in the project.
A dry-run post is `{platform, text, media, dry_run: true, argv, run, step,
ts}`; `argv` is the Postiz command that would publish it (`postiz
posts:create -c <text> -m <media> -i <integration id>`). The text is the
Copywriter's block for that platform (a heading per platform), else the
whole text.

## For the next rounds

R4 (Postiz) fills `post` with `live: true` (the `argv` above, run for real,
the post ids into `posts.json`) and `metrics` (one line per sample into
`metrics.jsonl` on the `every`/`days` schedule). R5 (Studio) draws the run
from `flow.json` and `events.jsonl` (or the `flow_*` feed events) and
answers gates by writing the answer file. The runner's seams
(`halo_harness/flows/adapters.py`):

```python
Adapters(model=None, auto_accept=False, poll_s=0.5, render_timeout_s=1800, state_dir=None,
         cwd=None, comfy_url=None, feed=None, one_shot=None, run_org=None, comfy_client=None,
         answer_gate=None)
one_shot(role, prompt, model) -> {"text", "cost_usd", "ok", "error"}
run_org(org_name, goal, budget_usd, on_event, approval_sink) -> {"text", "cost_usd", "positions", "is_error"}
    on_event(text, data=None); approval_sink({"id", "position", "text", "is_error"}) -> {"action": "accept|edit|stop", "instruction"}
comfy_client() -> ComfyClient
run(run_dir, *, adapters, on_event=None, clock=time.time) -> report
```
