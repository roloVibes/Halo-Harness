# Commands: workflows

Read this when you list, show, check or run a workflow from the command line (`halo workflow`), or list, enable and test workflow squares (`halo workflows`).

Part of [Commands](COMMANDS.md), which lists every part.

## `halo workflow`

Halo 3.2.0.0 R5. A workflow is a pack's `workflows/<name>.yaml`, named
`<pack>/<name>` (`doc-review/review`); it compiles to an Orchestra goal, its
hand-offs and a pinned plan ([WORKFLOWS.md](WORKFLOWS.md)). Only the packs
that run here (installed, enabled, no problem) have workflows to run. Every
verb takes `--repo DIR` (default: the current folder). Exit codes: 0 done,
1 not found or the run stopped, 2 a bad request or a compile problem (one
line each on stderr).

### `halo workflow list`

One line per workflow of the packs that run here: its name, its stages, its
inputs, then its description. `--json` prints `{"workflows": [{ref, pack,
name, description, stages, inputs}]}`.

```sh
$ halo workflow list
  doc-review/review            3 stage(s): read, judge, write  inputs: docs, style
                               Review the Markdown files under a folder and write one review report.
```

### `halo workflow show`

`halo workflow show <pack>/<name>`: the inputs (type, required or the
default), the outputs, each stage (its role and the bio it runs as, after
what, for each file of which input, its condition, gate, retries, timeout,
budget, test and evidence), the prerequisites and DONE WHEN. `--json`
prints the file as read.

### `halo workflow check`

`halo workflow check <pack>/<name> [--input K=V ...]`: compiles it with
those inputs and prints the jobs (stage, bio, what each takes from which
job, its title) and the stages skipped by a `when` on an input; or every
problem (a missing or bad input, a prerequisite this host lacks, a
capability not available here) and exits 2. `--json` prints `{ok, goal,
jobs, skipped}` (the goal as goal.json would hold it).

```sh
halo workflow check doc-review/review --input docs=docs --input style=long
```

### `halo workflow run`

`halo workflow run <pack>/<name> [--input K=V ...] [--as orchestra|goal]
[--model REF] [--force]`: compiles it and, with `--as orchestra` (the
default), makes the Orchestra run and runs it now, as `halo orchestra run`
does (the lineup preflight first, `--force` past it; `--model` for every
part; a line per step; the report with its artifacts and the bounds it does
not hold yet). A stage with `gate: human` makes the run wait for its plan's
review: `halo orchestra plan|approve|reject <run>` in another terminal, or
Studio's plan canvas. `--as goal` queues the compiled run for the supervisor
(`halo supervise`, 3.1.8.0), which runs it and resumes it from its
checkpoint; a build without the supervisor answers one line and exits 2.

```sh
halo workflow run doc-review/review --input docs=docs
```

### `halo orchestra new --workflow`

`halo orchestra new --workflow <pack>/<name> [--input K=V ...]` makes the
compiled run without starting it (`halo orchestra run <run>` starts it).

## `halo workflows`

Halo 3.3.16.0 R3. The workflow squares ([WORKFLOWS-squares.md](WORKFLOWS-squares.md)):
yours (`~/.halo/workflows/`), the project's (`.halo/workflows/`), the running
packs' (`<pack>/<name>`) and the shipped ones. `halo workflow` stays the
command of the old verbs; `halo workflows check | run` reach them too.

| Verb | What it does |
| --- | --- |
| `list [--json]` | every square with its contract line, `NAME · DOES · TAKES -> GIVES · band · depth`, its group and `*` on the ones the active lineup enabled; a workflow without `gives` is listed as not a square |
| `show <ref> [--json]` | the contract: covers, lineup, engine, costs, limits, where the file is, any problem |
| `enable <ref> [--lineup <name>]` | on for the active lineup (or `--lineup`): the auto lineup writes config `workflows.enabled`, a lineup of yours its `workflows:` list; one line says what changed |
| `enable <ref> --when <rule>` | 3.3.16.3: on, wired with its "when" -- `needs=pdf,audio` (the needs it takes a hand-off for: pdf, images, audio, video, code, plan, research, review, work-data), `words=review,audit` (the task says one of them), `named` (only when main names it), `always` (first, before main answers), `off` (on the board, not connected: main never uses it) or `auto` (its covers, the plain rule); the auto lineup writes config `workflows.when.<ref>`, a lineup of yours the item `{ref, when}` in its `workflows:` list |
| `disable <ref> [--lineup <name>]` | off again, one line (the auto lineup forgets its rule) |
| `when <ref> [--lineup <name>]` | 3.3.16.3: the square's rule on the lineup -- its label (the line's words in Studio), the sentence, and what is written |
| `test <ref> [--task TEXT]` | the check pass (the contract words, the compile with a sample task) and a dry run of the router on a sample task for each need it covers, on a text-only model: which gaps it covers; exit 1 on a problem |
| `new <name> --from <square>` | copy a square into yours (`~/.halo/workflows/<name>.yaml`), never over a file |

Every verb takes `--repo DIR` (default: the current folder). Exit codes: 0
done, 1 not found or a problem, 2 a bad request.

```sh
halo workflows list
halo workflows enable media
halo workflows test media
halo workflows new my-media --from media
halo workflows enable media --when needs=pdf,audio
halo workflows when media
```

`/workflows` in the terminal prints the same list, with a `when:` column on every enabled square
(`/workflows when <ref>` the rule).

## `halo blocks`

Halo 3.3.16.3 "Blocks" ([WORKFLOWS-squares.md](WORKFLOWS-squares.md#block-templates),
[STUDIO-blocks.md](STUDIO-blocks.md)). The blocks you can start from -- small YAML templates shipped under
`halo_harness/templates/blocks/`, each a square or a tier whose agents sit on `auto` models -- and the blocks a
lineup has.

| Verb | What it does |
| --- | --- |
| `list [--json]` | the templates (name, square or tier, title, who is inside), then the lineup's blocks: each square with its when line, each declared tier with its purpose and the words that reach it |
| `add <template> [--as <name>]` | a square template: a square of yours (`~/.halo/workflows/<name>.yaml`; `--as` names it) enabled and wired to main by its covers; a tier template: its agents and a tier below the lineup's last one (a shipped lineup is copied to yours under its name first, as Studio's Save does; a pack's is never written) |
| `show <name>` | a template (what it does, who is inside on which model, its costs, the name it adds as), or a block of the lineup (a square ref or a tier name) |

Every verb takes `--lineup <name>` (default: the active one) and `--repo DIR`. Exit codes: 0 done, 1 not found or
refused, 2 a bad request. `halo teams show <lineup>` prints a `block <ref> (square): when ...` line per square.

```sh
halo blocks list
halo blocks add thinking
halo blocks add review-panel --as panel
halo blocks show local-workers
```
