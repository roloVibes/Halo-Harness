# Commands: halo gym handout

Read this when you want to know whether main hands work out more on your local model: `halo gym handout`.

Part of [Commands](COMMANDS.md), which lists every part. The battery (`halo gym`, `halo gym show`, `halo gym propose`) is in [Commands: the gym and local models](COMMANDS-local.md).

## `halo gym handout`

```sh
halo gym handout ol:qwen3:8b
halo gym handout ol:qwen3:8b@gpu-box ol:tiny:3b --trials 1
```

Since 3.6.0.10, main on Auto is told to hand work out and which helpers it can start. This command measures, on a
local model, whether main hands out more with those words ("now") than without them ("before"). It prints four facts
before it sends its first request:

```text
Runs one fixed four-part job with each local model you name as main, three times with the words main had before 3.6.0.10 and three times with today's, and counts the parts it hands to helpers, not whether the work is better. Helpers are not run: each gets a fixed answer.
Free: local models only; nothing is sent to a cloud.
About 20 to 40 minutes per model with three trials (not measured yet: the first run sets this line).
A scratch copy of a small project, removed at the end, and one card per model under ~/.halo/gym-handout/<host>/.
```

- **The job.** A small project (three modules, three test files, one failing test) is written into a scratch folder.
  Main is asked for four parts: find the functions that read one setting, add a docstring to every function, run
  the tests and say which fail, write down what changed. The folder is removed at the end, also when a request fails.
- **The two arms.** "now" is the first request a new Auto session sends today; "before" is the same request with the
  helpers words turned off. Each trial is at most 10 requests. No session runs: the gym answers every tool call
  itself, inside the copy, and a helper is never started (each part gets a fixed answer).
- **`--trials N`**: trials per arm (default 3; at least 1). The arms take turns: before 1, now 1, before 2, ...
- **Local models only**: `ol:`, `hf:local/` and `hf:mlx/` refs. Any other ref prints
  `{ref}: the gym runs local models only.` and sends nothing; with no local model left the command exits 1.
- **What it counts, per model**: one line,
  `{model}: hands out {a} of 4 parts in {c} calls (before {b}) · bundled {u} · names right {r} of {n} · own steps {o} (before {p}) · finished {f} of 3 (before {g}) · 3 trials`.
  `a` and `b` are the mean parts handed out per trial (a call earns at most one part; a call that holds several
  counts once as bundled), `c` the mean calls, `r of n` the calls that named a helper and named it right, `o` and `p`
  the mean steps main did itself, `f` and `g` the trials that finished (a reply with no tool call within 10
  requests). The two 3s are the trials per arm: they follow `--trials N`. Errors during the run follow on their own
  line.
- **A model sent the same words in both arms** (it takes no tools, or today's words do not fit its window) is not
  measured, gets no card and prints why.
- **The cards** lie under `~/.halo/gym-handout/<host>/handout-<digest>.json`, one per model and host; a new run
  replaces it. They are kept apart from the battery's cards, so the `/model` picker's score and
  `halo gym propose` never read them. `halo gym show` prints the cards after the battery's, under
  "Main hands work out (halo gym handout):".

It counts hand-outs, not whether the work is better. A model passes when "now" hands out at least one part more
than "before" (the mean of the trials), names a helper right in at least 90 % of the calls that name one, and
finishes no fewer trials.
