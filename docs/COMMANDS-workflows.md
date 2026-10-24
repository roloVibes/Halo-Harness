# Commands: workflows

Read this when you list, show, check or run a pack's workflow from the command line (`halo workflow`).

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
