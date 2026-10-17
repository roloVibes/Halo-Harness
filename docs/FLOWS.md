# Flows

Halo 3.0.4.0. A flow takes an input, runs it through agents in roles, hands
the result to an org (the marketing org researches and plans), passes the
org's image prompt to ComfyUI, shows you the render, and on your yes writes
the posts and starts the metrics. Every artifact lands in a design project
(`~/.halo/design/<slug>/`, the same folder Halo Design and Studio's Design
mode open). Posting and metrics go through the Postiz CLI; every post is a
dry run until you set `live: true` on the flow's post step (see "Posting with
Postiz" below).

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
| `post` | `live: false`: one dry-run entry per platform in `<project>/posts.json`, nothing spawned; `live: true`: uploads the media once and runs `postiz posts:create` per platform | `{posts, dry_run, path}` |
| `metrics` | samples `analytics:post` for the run's live posts into `<project>/metrics.jsonl` (a dry run logs "dry run: no metrics") | `{samples, every, days, path}` |
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

**Preflight** (Halo 3.0.7.0). Before `halo flow run` makes the run folder,
the run-start preflight checks every lineup the flow's `roles` steps use:
a model id its provider's catalog does not know (requests for it 404 and the member comes back empty), an assignment or org position naming a bio that does not exist, a bio whose `tools.allow` is an empty list (it may call no tool), and a `tiers` problem ([ROLES.md](ROLES.md#tiers-halo-3070)). Each blocking
problem prints with its fix, prefixed with its lineup, and nothing runs (exit
2); `--force` runs anyway. Studio's `POST /api/flow/runs` answers 422
`{error, problems, preflight: true}` and runs with `{"force": true}`.
Findings that only warn (a dead fallback, aliases in no tier) do not stop it.

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
  path, prompt_id}], accepted, posts: [{platform, dry_run, chars, media,
  post_id, scheduled_at, error}], metrics: {notes, samples, posts, totals:
  {views, likes, comments, shares}, summary}}`.

The run stops (status `stopped`, a reason in the report) when its budget is
spent, when `stop.json` appears, when a gate answers stop, or when a step
fails. `halo flow resume <run>` picks up at the first unfinished step: done
steps are not run again, a render killed half-way renders again into the
same artboard, a gate left waiting opens again.

## Posts and metrics

`posts.json` and `metrics.jsonl` sit beside `design.json` in the project
(`Project.posts()` and `Project.metrics(limit=None)` read them). A post entry
is `{platform, text, title?, media, dry_run, argv, run, step, ts}`; a live one
adds `{integration_id, media_urls, post_id, scheduled_at}`, a failed one
`{error}`. A metrics line is `{ts, post_id, platform, days, metrics: <the
raw Postiz answer>, run, step}`.

The text of each platform comes from the Copywriter position. The marketing
org asks it for one fenced JSON block, `{"youtube": {"title", "text"},
"instagram": {"text"}, "x": {"text"}, "tiktok": {"text"}}` (keys may be
`twitter`, `ig`, `tik tok`; a value may be a plain string; `caption` and
`description` count as `text`). Without that block the text is split by
platform headings (`X:`, `## Instagram`), else every platform gets the whole
text.

## Posting with Postiz

Halo never talks to the social platforms itself: it runs the Postiz CLI with
your API key, for youtube, instagram, x and tiktok.

```sh
npm i -g postiz                      # the CLI
postiz auth:login                    # or put POSTIZ_API_KEY=... in the env file (~/.config/halo/env)
halo postiz doctor                   # the CLI, the credentials (never the key), the connected integrations
```

`POSTIZ_API_URL` points the CLI at a self-hosted Postiz. Halo hands the key
to the CLI by name only; it is never logged and never written to
`posts.json`, `metrics.jsonl`, `events.jsonl` or the report.

**Dry run is the default.** With `live: false` (or no `live`) the post step
writes one `dry_run: true` entry per platform, with the `postiz posts:create`
command that would publish it, and spawns nothing. Look at them with
`halo flow posts <run>`. To post for real, set `live: true` on the post step
(`halo flow validate` warns when no credentials are found). A live post step:

1. stops the run with a one-line reason when the `postiz` CLI is not on PATH
   or no credentials exist;
2. matches each requested platform to a connected, enabled integration (the
   integration's `identifier`: `youtube`, `instagram`, `x` or `twitter`,
   `tiktok`);
3. uploads each media file once (`postiz upload`, the returned URL is what
   `-m` takes) and runs `postiz posts:create -c <text> -m <urls> -s <when> -i
   <integration> --settings <json>` per platform; `when` is the step's
   `when:` (ISO time) or one minute from now. The settings carry YouTube's
   title, TikTok's `DIRECT_POST` and Instagram's `post_type`;
4. records `post_id` and `scheduled_at` as each post lands. A platform that
   fails (no integration, a disabled one, a CLI error with its stderr tail)
   is recorded with its `error` and stops the run once the others went out;
   `halo flow resume <run>` posts only the platforms still missing.

**Metrics.** The `metrics` step samples `postiz analytics:post <post id> -d
<days>` for each live post of the run into `metrics.jsonl`, once when the run
reaches it. `every` (`30m`, `6h`, `1d`) and `days` set the cadence:
`halo flow run <name> --watch` (or `halo flow resume <run> --watch`) keeps
sampling on that interval until `days` have passed since the first post,
`halo flow stop <run>` or Ctrl-C. `halo flow metrics <run> [--days N]` samples
once on demand and prints the totals. The report totals the latest sample of
each post (views, likes, comments, shares, read from the labels Postiz
returns: Views/Impressions, Likes, Comments, Shares/Retweets). Dry-run posts
have no metrics: the step says "dry run: no metrics".

On Windows the npm CLI is a `postiz.cmd` shim, and cmd.exe can cut an
argument at a line break or mangle a `&`; live posting of multi-line texts is
meant for Linux and macOS hosts.

## In Studio

`halo studio` serves the runs under `/api/flow/`. The full table is in
[STUDIO.md, "Flow and Media routes"](STUDIO.md#flow-and-media-routes-3040).

    GET  flow/templates                  the shipped, user and project flows: steps and the intake form
    GET  flow/runs                       the runs, newest first (waiting_step when a gate is open)
    POST flow/runs {template, intake, model?, set?, yes?, start?}   201 {run}; 409 while another run is live
    GET  flow/runs/<id>                  flow.json, steps/<n>.json, the open gate, report, posts, metrics, artboards
    GET  flow/runs/<id>/events?since=N   {events, next}
    POST flow/runs/<id>/assets {name, data_base64}   into the project's assets/
    POST flow/runs/<id>/stop | resume
    POST flow/runs/<id>/answer {step, action, instruction?, round?}   writes steps/<n>.answer.json
    GET  flow/runs/<id>/report | posts | metrics?limit=N

A run started from Studio runs on a background thread of the Studio
process with the real adapters (the same as `halo flow run`). Its log
lines reach the live feed as `flow_<kind>` frames with `session_id:
"flow:<run id>"`. The answer route writes the same answer file as `halo
flow answer`, so a gate opened by a CLI run can be answered from Studio
too, and the other way round. To start a run with uploaded files, post
`start: false`, upload each file to `assets`, then post `resume`. The
intake step then finds the files in the project's `assets/` folder.

## For the next rounds

Studio draws the run from `flow.json` and `events.jsonl` (or the `flow_*`
feed events) and answers gates by writing the answer file; its Posts and
Metrics panels read `Project.posts()` and `Project.metrics()`. The runner's seams
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
