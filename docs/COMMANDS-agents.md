# Commands: agents, maps and review

Read this when you manage your agents and maps, or run a review, from the command line.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo agents`

(3.6.0.0 R5) Your agents: one file each in `~/.halo/crew/agents/` (agent/1), a trusted project's in
`.halo/crew/agents/`, and the starters Halo ships (read-only; copy one to make it yours). Studio's Agents -> 1 · Agents
is the full editor ([CREW-FORMATS.md](CREW-FORMATS.md)).

```sh
halo agents list                       # yours, this project's, then the starters; a file with a problem says it
halo agents show coder                 # its file, and the workflows and maps that use it
halo agents new my-coder --from coder  # one of yours: a copy (or, without --from, a blank one)
halo agents edit my-coder              # your $VISUAL / $EDITOR on your file; else Studio on it (a starter: how to copy it)
halo agents try my-coder "fix the retry in client.py"   # on a throwaway copy of this repo: its reply, what it used, cost
```

## `halo maps`

(3.6.0.0 R3; R5) Your maps: what main hands work to, and when ([CREW-sessions.md](CREW-sessions.md)). Every session
runs on a map: `--map <name>` for one run, else config `crew.map`, else the shipped `starter`. Editing one is Studio's
Map tab (Agents -> 3 · Map) or its builder box.

```sh
halo maps list            # every map (yours, this project's in a trusted folder, the starters); * marks the one in use
halo maps show ship-it    # main, each box, each line with its When in words, the cap, any problem
halo maps use ship-it     # new sessions run on it (config crew.map); a running session keeps its own
halo maps use --off       # back to the default (the starter map drawn, no rules of its own)
halo maps use --none      # One model for everything: no map, main does every job (roles off)
halo maps edit my-map     # your $VISUAL / $EDITOR on your file; else Studio's Map on it
```

`use` writes `crew.map` through the builder's undo store, so Studio's Undo puts it back. `halo --map <name>` runs one
session on a map without changing config; the old `--team <name>` prints one line and runs on the map in use.

## `halo teams`, `halo roles`

(3.6.0.0 R5) Lineups are gone. Each prints one line -- "lineups are gone: halo maps use <name> picks the map your
sessions run on" -- and exits 0. Your old files under `~/.halo/teams` and `~/.halo/agents` stay where they are, unread
(Halo says so once, and `halo doctor` while they are there). One verb stays for this release: `halo roles point <role>
<model>`, the role write the Ollama steward's and the adviser's lines offer ([COMMANDS-ollama.md](COMMANDS-ollama.md)).

## `halo review`

```sh
halo review [target ...] [--level {low,medium,high}] [--dimensions LIST] [--fix] [--no-verify]
            [--json] [--model REF] [--role NAME=MODEL[:EFFORT]] [--cwd DIR]
```

Halo 2.0.10: review a change with parallel dimension reviewers and a judge,
and print the ranked findings (the same thing `/review` does in the TUI).
`target` is nothing (this branch against its merge base with the default
branch, uncommitted changes included), a range `a..b`, a branch, a pull
request (`#123` or `123`, through `gh`), or one or more paths/globs reviewed
as they are. Exit code 0 whenever the review ran (findings never change it),
1 if every reviewer failed, 2 for usage errors and targets that cannot be
resolved. Progress lines go to stderr; the result goes to stdout. See
[REVIEW.md](REVIEW.md) for the pipeline, the JSON shape and the cost.

#### `--level {low,medium,high}`

How many findings each reviewer may report (3, 8, 20) and how speculative
it may be. Default `medium`.

#### `--dimensions LIST`

A comma-separated subset of `correctness`, `security`, `performance`,
`tests`, `docs-consistency`. Default: all five.

#### `--fix`

After verification, a `coder` sub-agent applies a minimal fix in the working
tree for each CONFIRMED finding (never committing) and the judge re-checks
it; each finding gets an `outcome` of `fixed`, `skipped` or
`no_change_needed`. Runs the session in `acceptEdits` mode. Not combinable
with `--no-verify`.

#### `--no-verify`

Skip the judge: findings stay PLAUSIBLE and none are dismissed.

#### `--json`

Print one JSON object `{target, findings, dismissed, reviewers, cost_usd,
elapsed_s}` with the ReportFindings field names instead of text.

#### `--model REF`, `--role NAME=MODEL[:EFFORT]`, `--cwd DIR`

`--model` is the model for roles with none of their own; `--role` (repeatable)
sets the `reviewer`, `judge` or `coder` role for this run; `--cwd` is the
repository or directory to review (default: the current directory).
