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
About 2 minutes per model with three trials when the model runs on a GPU (five real runs took 9 minutes together); a model that runs on the CPU takes much longer.
A scratch copy of a small project, removed at the end, and one card per model under ~/.halo/gym-handout/<host>/.
```

- **The job.** A small project (three modules, three test files, one failing test) is written into a scratch folder.
  Main is asked for four parts: find the functions that read one setting, add a docstring to every function, run
  the tests and say which fail, write down what changed. The folder is removed at the end, also when a request fails.
- **The two arms.** "now" is the first request a new Auto session sends today; "before" is the same request with the
  helpers words turned off. For a local main today's request also carries one reminder line after the task; "before" has neither. Each trial is at most 10 requests. No session runs: the gym answers every tool call
  itself, inside the copy, and a helper is never started (each part gets a fixed answer). A path or a pattern that
  leaves the copy is refused before the system is asked anything about it.
- **`--trials N`**: trials per arm (default 3; at least 1). The arms take turns: before 1, now 1, before 2, ...
- **Local models only**: `ol:`, `hf:local/` and `hf:mlx/` refs. Any other ref prints
  `{ref}: the gym runs local models only.` and sends nothing; with no local model left the command exits 1. A local
  model whose host is not found, or whose host answers no request of an arm, prints
  `{ref}: not measured: {the cause}` and gets no card: each cause is named once, with how many trials it ended
  (`(2 trials)`). When the first trial of both arms got no answer the run stops there. When no model ran, the
  command exits 1.
- **A gateway in front of Ollama** (a host entry with `dialect: "openai"`): the gym speaks to it as a session does, with the entry's key. It cannot unload the model through a gateway, and says so on the errors line.
- **One line per trial**, printed as each trial ends, before the model's line:
  `  now 2 of 3: 2 of 4 parts in 2 calls · own steps 1 · finished · 41 s`. A trial ends `finished`,
  `not finished in 10 requests`, `stopped by an error after 5 requests` (it got answers, then a request failed) or
  with `no answer` (its first request got no reply).
- **What it counts, per model**: one line,
  `{model}: hands out {a} of 4 parts in {c} calls (before {b}) · bundled {u} · names right {r} of {n} · own steps {o} (before {p}) · finished {f} of 3 (before {g}) · 3 trials`.
  `a` and `b` are the mean parts handed out per trial (a call earns at most one part; a call that holds several
  counts once as bundled), `c` the mean calls, `r of n` the calls that named a helper and named it right, `o` and `p`
  the mean steps main did itself, `f` and `g` the trials that finished (a reply with no tool call within 10
  requests). The means count the trials that got an answer. The two 3s are the trials per arm: they follow
  `--trials N`. The verdict follows on its own line, then the errors during the run.
- **A model sent the same words in both arms** (it takes no tools, or today's words do not fit its window) is not
  measured, gets no card and prints why.
- **The cards** lie under `~/.halo/gym-handout/<host>/handout-<digest>.json`, one per model and host; a new run
  replaces it. They are kept apart from the battery's cards, so the `/model` picker's score and
  `halo gym propose` never read them. `halo gym show` prints the cards after the battery's, under
  "Main hands work out (halo gym handout):".

It counts hand-outs, not whether the work is better. A model passes when "now" hands out at least one part more
than "before" (the mean of the trials), names a helper right in at least 90 % of the calls that name one, and
finishes no fewer trials. The verdict under each model's line (and under each card in `halo gym show`) says which:

```text
  Verdict: passes. Today's words make it hand out 1.7 more of 4 parts.
  Verdict: does not pass. Today's words do not make it hand out more (0.3 of 4 parts, before 0).
  Verdict: does not pass. It names a helper right in 7 of 10 calls (it needs 9 in 10).
  Verdict: does not pass. It finishes fewer trials with today's words (2 of 3, before 3).
  Verdict: none. 1 of 6 trials got no answer: run it again.
```

A model that fails more than one rule gets each sentence, in that order, on the one line.
