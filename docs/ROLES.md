# Roles: the model table

Read this when you want a job of your sessions (planning, coding, review, research ...) to run on a model you chose.

Since Halo 3.6.0.0 a role is one line of the **model table**: `roles.<name>` in `~/.halo/config.json` names the model
that job runs on. Lineups, which used to hand bios to roles, are gone ([MOVING-from-3.5.md](MOVING-from-3.5.md)); what
connects agents is a map ([AGENTS.md](AGENTS.md), [CREW-sessions.md](CREW-sessions.md)).

## The 90-second version

- A session with no map set runs as a plain session always did: main on your model, and helpers it hands work to by
  name (`planner`, `researcher`, `coder`, `reviewer`, `media`, `writer`, `ops`), each on `auto` unless the model
  table names a model for it.
- `halo roles point <role> <model>` writes `roles.<role>` (as `halo config set roles.<role> <model>` does); the next
  session's helper of that name runs on it. Studio's Local section offers the same write ("Assign").
- `roles.enabled: false` turns the table off: one model for everything, the default model you picked.

## The names a session reads

The plain session's helpers above, plus `orchestrator`, `judge`, `tester`, `small` (summaries and drafts),
`compaction`, `subagent_default` (a sub-agent with no role at all) and the media roles `visual`, `eyes` and
`concierge`. A name nothing reads is refused when you assign it, in one line saying which name does that work.

## A role's value

A model reference (`or:vendor/model`, `ol:qwen3:8b@lan`, `dbx:endpoint` ...), or `{"model": "...", "effort": "..."}`.
Two words are picked at spawn instead of naming a model:

### Auto

`auto` picks a model for each task from your catalog: what the task needs (an image, audio, video or a PDF in it; a
plan or a review asks for reasoning; a long task asks for a long context), weighed against cost
(the `mid` band), from the best-at index `halo models analyze` builds. No candidate (or none with
credentials here) runs on the session's model, and the one-line reason says so.

### Measured

`measured` is the `auto` pick with one rule first: among the candidates, the model with the best measured first-time
success here at that kind of task (from 3 checked tasks, `halo models --measured`) wins
([OUTCOMES.md](OUTCOMES.md)).

## Where a spawn's model comes from

A call's own `model:`, then a `--role` override, then the agent file's `model:`, then the model table, then the
spawning session's model. The effort half follows the same order.

## Overrides for one session

- `--role NAME=MODEL[:EFFORT]` on the command line (repeatable; a bad value is a usage error, exit 2):

  ```sh
  halo -p --role researcher=or:deepseek/deepseek-v4.1-flash:low "summarize this repo"
  ```

- `Agent(role=...)` on one call resolves that call against the role's model.
- `/role <name> <model> [effort]` in a session sets one role for this session only.

## Local models in the table

Local's pages say which local model fits a role on each card and assign it (`roles.<role>`); the steward and the
scheduler read the table to know which models your sessions load ([STUDIO-local.md](STUDIO-local.md),
[MODELS-ollama.md](MODELS-ollama.md)).
