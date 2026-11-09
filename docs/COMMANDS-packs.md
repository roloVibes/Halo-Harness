# Commands: packs

Read this when you list, inspect, install, enable, grant, update, roll back or remove a pack, or name where packs come from, on the command line (`halo pack`).

Part of [Commands](COMMANDS.md), which lists every part.

## `halo pack`

Halo 3.2.0.0. A pack is a folder of bios, lineups, skills, commands, hooks
and MCP servers with a `pack.yaml` at its root ([PACKS.md](PACKS.md); the
contract is [EXTENSION_API.md](EXTENSION_API.md)). Every verb takes `--cwd
DIR` (act as if run from DIR, so its `.halo/packs/` is the repo's) and
`--json` (one JSON object on stdout). Exit codes: 0 done, 1 could not (the
reason on stderr, one line each; for `doctor`: a blocks or warns row; info rows alone exit 0), 2 usage. A
bare `halo pack` prints the verb list. 3.3.7.0 R5: `verdict`, `on`, `off` and
`list --bundles` are the bundle verbs ([Bundles](#bundles) below). 3.3.10.0 R1:
`mode` and `policy` ([Modes and policy hooks](#modes-and-policy-hooks) below). 3.3.12.0 R4: `new`, `test`, `unlink`
and `install --link` are the pack kit's ([COMMANDS-packs-kit.md](COMMANDS-packs-kit.md)).

### `halo pack list`

One line per pack here: id, version, state (`enabled`, `enabled, not
running`, `disabled`, `not installed (found in place)`), scope (`project` or
`user`), source and what it offers (bios, lineups, agents, skills,
commands, MCP servers, hook events). `--json` prints `{"packs": [...]}`.

```sh
halo pack list --json
```

#### `--available`

3.2.0.0 R6: also what you could install by id: each pack in a `packs.sources`
folder or url, then in the packs Halo ships, that is not installed here (one
per id, the first place first). `--json` adds `"available"`.

```sh
$ halo pack list --available
No packs here. A pack lives in ~/.halo/packs/<id>/ or .halo/packs/<id>/ (halo pack install <path|git url>).
available (halo pack install <id>):
  doc-review  1.0.0     Documentation Review  from .../halo_harness/templates/packs
```

### `halo pack inspect`

`halo pack inspect <id|path>`: the manifest (name, version, the extension
API and Halo versions it works with, what it requires), every name it
offers, each bio with the model it resolves to (and why: its
`models.capabilities`, or your default model when no catalog model has
them), the grants it needs (granted or not) and its memory namespace, each
lineup with its members, tiers and acceptance (3.3.10.0 R3: then one line per
workflow it runs, resolved: `workflow <pack>/<name> -- <title>: <description>`,
the title being the workflow's `name:`; a name no pack here knows stays as
written with "(not found)"; `--json`: `workflow_lines: [{ref, found, line}]`),
each permission it
requests with what needs it and whether it is granted, its settings
(defaults with yours on top) and its problems. 3.2.0.0 R4: a "contributes:"
block lists what it adds to Studio (sections and their panels, panels in a
core section, palette lines, the settings form, event lines, attention rows)
and to the fleet (each capability, available here or not and why, against
this harness's cached capabilities catalog; its inspector lines and mission
metadata). A path inspects a pack folder before you install it. `--json`
adds `bios`, `lineups` and `contributes: {studio, fleet}`.

```sh
$ halo pack inspect doc-review
...
bios:
  doc-review--reviewer: runs on ol:long-1 (the best catalog model with long-context)
    needs: bash (not granted)
    memory namespace: doc-review/reviews
lineups:
  doc-review--review: doc-review--writer (main), doc-review--reviewer (reviewer); 2 tiers; acceptance.test: python -m pytest -q; acceptance.review: true
    workflow doc-review/review -- review: Review the Markdown files under a folder and write one review report.
contributes:
  Studio section docs (Docs review): notes (markdown), checks (table), links (links)
  Studio panel in session: reviews (events)
  palette: Open the review checks
  the settings form (its first section's Settings panel)
  event lines: review.done
  attention rows: review.ask
  fleet capability docs.review: available here (tools: or:anthropic/claude-sonnet-4.6; bash granted); 2 at once
    Reviews a repo's documents for dead links, heading order and style
  mission inspector line: Review checklist (fleet/checklist.md)
  mission metadata: review=docs, style=short
```

### `halo pack install`

`halo pack install <path|git url|id>` copies the pack into `~/.halo/packs/<id>/`;
`--project` copies it into this repo's `.halo/packs/<id>/` instead. A bare id
is looked for in each `packs.sources` entry in order, then in the packs Halo
ships (3.2.0.0 R6: the Documentation Review reference pack), so `halo pack
install doc-review` installs the shipped one unless a source of yours holds a
pack with that id ([PACKS.md](PACKS.md#the-reference-pack)).
Everything is checked before a file is written (the manifest, the API and
Halo versions); a folder already there is left as it is. Files go through
the journal (`~/.halo/packs/journal.jsonl`); a copy that fails part way is
rolled back. A git url is cloned fresh (`git clone --depth 1`); in offline
mode the one line is "offline mode: not connecting to <host>". The pack is
installed disabled.

#### `--project`

Install into the repo's `.halo/packs/` (the untrusted layer: its lineups
lose `permissions.mode` and allow rules).

### `halo pack enable`

`halo pack enable <id>` turns the pack on and prints what it requests. A
contribution whose permission is not granted does not run: its MCP server
does not start, its hooks do not load. Grants add up across calls. 3.3.11.0 R3:
it ends with one line per [Setup block](EXTENSION_API.md#setup-blocks) of the
pack neither done nor skipped, `setup: <id> -- <title> (halo setup <id>)`
(`halo pack on <bundle>` prints the same lines).

#### `--grant`

`--grant NAME`, repeatable: grant one permission the pack requests
(`mcp:<server>`, `hooks`, `bash`, `network`, `home-write`, `studio-script`, `services`). A name it does
not request is one line and exit 1.

#### `--grant-all`

Grant every permission the pack requests.

```sh
halo pack enable doc-review --grant mcp:lint --grant hooks
```

### `halo pack grant`

3.2.0.0 R6: `halo pack grant <id> NAME [NAME ...]` gives an enabled pack more
of what it requests (the same as `enable --grant`) and prints what it
requests, granted or not. A disabled pack's grants are given as you enable
it: the one line names `halo pack enable <id> --grant NAME`. Studio's Grant
toggle (the Pack Manager's Details panel) runs this.

#### `--off`

Take the grants back: the contributions that need them stop running, each
named with the command that grants it again.

```sh
$ halo pack grant doc-review hooks --off
took back hooks from doc-review
```

### `halo pack disable`

`halo pack disable <id>`: nothing of the pack contributes from then on; its
files stay; its grants clear (the next `enable` states them again).

### `halo pack update`

`halo pack update <id>` reads the pack's recorded source again (a folder, or
a fresh clone of its url) and makes install's checks on it (a new version
that fails one is refused with its lines, and `<id> <version> stays as it
is`). 3.2.0.0 R7: it prints the `migrations` notes between the installed and
the new version first (`doc-review 1.1.0 -> 1.3.0: <note>`), stages the new
version beside the pack (each file the pack wrote that you have not changed
replaced; a file you changed or added carried over and listed) and swaps it
in by two renames, keeping the old version as `<id>.previous/`; then it
renames the `packs.settings.<id>` keys the notes declare (one line each). A
copy or rename error leaves the old version in place, in one line. From the
same source with nothing new: `<id> <version> is up to date`.

3.2.1.0 R4: in a terminal (stdin and stdout both one) it asks before the
swap: it prints the dry run's lines (the notes, the files that change, the
settings it renames, your files it keeps), then `Apply? [y/N]`. `y` makes the
update and prints its own lines; `n`, Enter or the end of input print `<id>
<version> stays as it is` and exit 1, nothing changed. A run that is not in a
terminal (a pipe, a script, CI), `--json` and `--dry-run` never ask. The Pack
Manager's Update confirm in Studio is the same look.

#### `--dry-run`

Print the notes and what the update would do (the files that change, one
line each: `  <file> (changed|new|dropped)`, the settings it renames, your
files it keeps), ending `dry run: nothing is changed (halo pack update <id>
makes these changes)`; change nothing.

#### `--yes`

3.2.1.0 R4: do not ask before the swap in a terminal; the update runs as
it does where nothing asks.

### `halo pack rollback`

3.2.0.0 R7: `halo pack rollback <id>` swaps `<id>.previous/` (the version
the last update replaced) back in: your files changed since the update stay,
the settings that update renamed move back, the grants and the enabled state
stay, and the version rolled back from is deleted (`halo pack update <id>`
brings it back). One version back only: `<id>.previous` is the one version
kept, the next update replaces it, and there is no version history on disk
(3.2.1.0 R4 writes it down as the rule). With none kept: `<id> has no earlier
version to go back to: an update keeps the version it replaces as
<id>.previous until the next update`.

### `halo pack remove`

`halo pack remove <id>` deletes the pack's own files only, its `<id>.previous/`
(3.2.0.0 R7) and drops its record. Your bios and lineups named `<id>--*`, your lineups naming its bios,
their memory folders (`~/.halo/teams/<id>--*/`), your `packs.settings.<id>`
and a `team:` naming its lineup stay, each listed.

#### `--keep-config`

Keep the pack's record (disabled, with its grants), so installing it again
starts with the same grants; a kept `<id>.previous/` stays with it, and
`halo pack rollback <id>` installs that version again.

### `halo pack sources`

3.2.0.0 R6: where a bare id is looked for, in order, with the packs each
place holds (`(installed)` beside the ones here): the folders and git urls of
`packs.sources` in `~/.halo/config.json`, then the packs Halo ships. A git url
is not fetched to list it. `halo pack sources add <folder|git url>` appends
one (a folder must be there), `halo pack sources remove <folder|git url>`
takes one out (the packs installed from it stay). `--json` prints
`{"sources": [...]}`. Studio's Pack Manager (Sources panel) runs the same.

```sh
$ halo pack sources add ~/packs
added ~/packs to packs.sources (it holds my-checks)
```

### `halo pack doctor`

Every problem, one line each: a manifest that does not validate, an API or
Halo version outside a pack's range, a missing, disabled or out-of-range
required pack, a requires cycle, a contribution whose permission is not
granted, settings outside the pack's schema, a capability set no model in
your catalog has (one row per set, naming the bios that fall back to your
default model), a bio's need you have not granted (one row per need, with
`halo pack enable <id> --grant <need>`), a fleet capability not available
here (one row each, with why, and the grant command when a grant is what is
missing; 3.2.0.0 R4), a name two packs (or a pack and you) offer, a pack shadowed by a same-id repo pack, a state record whose
folder is gone, a bio or lineup file pack.yaml does not list, and what the
privacy scan finds in the pack's files. `halo doctor --config` lists the
same lines under its packs group. A bio naming one provider, a stray
workflow name, a tag Halo does not know and a need pack.yaml does not request
are manifest problems (the first group). 3.3.10.0 R3: an enabled pack's
`.mcp.json` server whose command is not on PATH (a program its owner installs,
like the concord pack's `concord-mcp`) is one warns row, `not-on-path`.

**Severities and the exit code** (3.3.10.0 R3). Each row is `blocks` (printed
`[ERROR]`: the pack contributes nothing until it is fixed), `warns` (`[WARN]`:
a part of it does not run) or `info` (`[INFO]`: a note, never a problem; today
one kind: a fleet capability hidden on purpose with `fleet.capabilities.hide`).
Info rows print last (dimmed on a terminal) and the RESULT line counts them
apart (`RESULT: 0 problem(s) (0 error(s), 0 warning(s)), 1 note(s).`); the
exit code is 1 when any blocks or warns row is there and 0 when every row is
info. 3.3.11.0 R3: an enabled pack's Setup block still waiting is the second
kind, one row per pack, `setup-waiting` (`[INFO] <id>: setup waiting: 2 blocks
not done yet (...) -> halo setup <id>`); `halo doctor` prints the same as an
`[INFO] Pack setup:` line, and the Pack Manager's row says "setup waiting".
`--json` keeps its shape (`{"problems": [...]}`, each row with its
`severity`) and the same exit rule; `halo doctor --config` tags the row
`[INFO]` and does not count it as a finding. The Pack Manager counts info rows
apart from the doctor lines ("1 note").

### `halo setup <pack>`

3.3.11.0 R3: `halo setup <id>` (an enabled pack's id) opens Studio's Setup on the
pack's first [Setup block](EXTENSION_API.md#setup-blocks) still waiting
(`?mode=setup&block=pack:<id>:<block>`; every block done: its first), with the
one line `halo setup team` prints. With no terminal, `--terminal`, or a box where
no browser opens, it prints a line per block with its state (`done`, `skipped`,
`waiting`) and `halo studio --edit setup:pack:<id>:<block>`, exit 0. A disabled
pack, or one with no blocks, is one line and exit 1; a word that is no pack's id
is the usage line and exit 2.

## Bundles

A bundle is a pack with a resource claim (3.3.7.0 R5; [MODELS-bundles.md](MODELS-bundles.md)). Its verbs:

```sh
halo pack list --bundles [--host pc] [--json]   # every bundle here and shipped: [x] on / [ ] off, its state, its verdict
halo pack verdict meta-glasses [--host pc] [--json]
halo pack on meta-glasses [--host pc]           # only a ready bundle: installed, enabled, its reservation claimed
halo pack off meta-glasses                      # released, keep_alive put back, the pack disabled
```

`halo pack verdict <bundle>` prints the honest verdict before anything downloads -- `ready`, `downloads` or `wont`,
its line, the reservation's budget line, then each way out (`-`) and each warning (`!`), each a number, and for
downloads the pull and probe lines to run (nothing is pulled here):

    meta-glasses on pc: ready
      fits today -- 1.2 GB reserved leaves ~20.8 GB, the coder (18.9 GB) still fits beside it, barely; ...
      nothing reserved; 22.0 GB free for tasks
      ! GPU STT (faster-whisper:large-v3-turbo, 1.5 GB) would break that: the coder would no longer fit beside it
      - the coder's window 32 k -> 16 k frees 0.8 GB

`halo pack on <bundle>` turns a ready one on (any other state prints the verdict's line and its ways out, exit 1):
the bundle is installed from the shipped ones when it is not installed, enabled, its claim recorded (on the paired
halo host when one serves the card) and the reserved model's profile gets keep_alive -1, kept until `halo pack off`.
`halo pack off <bundle>` takes the claim back, reverts that change and disables the pack. `--host` names the Ollama
host to judge (the default one when left out).

3.3.8.0 R4: a bundle with several reservations prints one `+` line per other part, where it is held ("+ the pool for
reasoner: Qwen3-Next-80B-A3B Q4_K_M fits the pool ... [ready]"), then its `schedule:` line, its priority, and `!` the
notice of a pre-emption it suffered ("! pre-empted night-batch (low) on pc: focus (high) needs its 6.0 GB ..."). `on`
releases the lower claims it pre-empts first, one line each, then claims every part (the pool: a claim on host
`pool`, Warm still starts it; a paired host: its `claim` op), each row with the bundle's hours
([MODELS-bundles.md](MODELS-bundles.md#several-reservations-a-schedule-a-priority-3380-r4)).

## Modes and policy hooks

3.3.10.0 ([EXTENSION_API.md](EXTENSION_API.md#policy-hooks)): a pack that declares `contributes.modes` and
`contributes.policy` has a runtime mode and policy hooks, recorded in `~/.halo/packs/.data/<id>/mode.json`. Every
session asks the armed policies before each matching tool call (R2): a deny refuses it with the pack's line, an ask
goes to the approval card, an allow leaves it to your permissions as before. These verbs write the record, run a
verdict dry and read the verdicts back.

### `halo pack mode`

`halo pack mode <pack> <mode> on | off`: turn one of the pack's modes on (each policy whose `when.modes` names it is
armed; a mode that was on in its place goes off and its policies with it) or off (its policies disarmed). Every
change is the pack's `mode` event. A mode the pack does not declare is one line and nothing is written (exit 1):

```sh
halo pack mode policy-fence fenced on
policy-fence: mode fenced on (Fenced); armed: fence
it is not asked until the pack runs here: halo pack enable policy-fence --grant hooks
halo pack mode policy-fence audit on
halo pack: policy-fence declares no mode 'audit' (contributes.modes: fenced)
```

#### `--note`

`halo pack mode ... on --note TEXT`: a line kept in mode.json beside the mode (why it is on).

### `halo pack policy`

- `halo pack policy status`: every pack here that declares a policy or a mode, its mode, and each policy's state:
  `armed, asked now`, `not armed (halo pack policy arm <pack> <policy>)`, or `armed, not asked:` and why (the pack
  does not run here, hooks is not granted, its mode is not on); under it (3.3.10.0 R2) the policy's process
  (`running (pid N)` while a session keeps it, else `not running`) and its verdict counts. `--json`: `{"packs":
  [...]}`, each policy with `process` and `verdicts`.
- `halo pack policy arm <pack> <policy>` / `halo pack policy disarm <pack> [<policy>]`: arm one policy, or disarm
  one (every armed one without a name); the mode stays as it is.
- `halo pack policy test <pack> <policy> <tool> '<json input>'`: a verdict without a session. It arms nothing,
  starts the policy's process for this one request, prints the verdict with its time and stops the process; a tool
  `when.tools` does not name is not asked. Exit 0 for any verdict.
- `halo pack policy log [<pack>]` (3.3.10.0 R2): every verdict sessions got, before and after the call, oldest
  first, one line each: the time, the pack, the verdict and the pack's reason, then the tool, the time it took, the
  rule, the sub-agent or worker when it was one, `the winner` when several policies answered, the error when the
  policy did not, and the sha256 of a result it redacted or dropped. Without a pack: every pack that declares a
  policy. `--json`: `{"verdicts": [...]}`, the rows as the events log keeps them (never the tool input).

```sh
halo pack policy test policy-fence fence Write '{"file_path": "/tmp/x"}'
deny -- fence: outside the project (12 ms)
  rule: outside-project; scope: session
  a dry run: nothing was armed, no session asked
halo pack policy log policy-fence --since 1h
2026-11-03 12:00:01 policy-fence  deny -- fence: outside the project  (Write, 3 ms, rule outside-project)
```

#### `--budget-ms`

`halo pack policy test ... --budget-ms N`: how long to wait for the answer (default `packs.policy.budget_ms`, 2000);
a late answer is the policy's `on_error` verdict, said with what happened.

#### `--since`

`halo pack policy log ... --since WHEN`: only the verdicts after WHEN: `30m`, `2h`, `1d` (that long ago), epoch
seconds, or an ISO time (`2026-11-03T12:00`, local when it has no zone). Anything else is a usage line (exit 2).

## A pack in `halo agents list` and `halo teams list`

With a pack enabled, `halo agents list` and `halo teams list` print your
names (and the shipped ones) one per line as before, then one group per
pack: `pack <id>:` and its `<id>--<name>` names, indented. A name a file of
yours shadows says so: `  doc-review--reviewer  shadowed by
~/.halo/agents/doc-review--reviewer.yaml`. With no pack the output is
unchanged.

#### `--cwd`

Every verb: act as if run from DIR.

#### `--json`

Every verb: print one JSON object (`list`: `{"packs"}`, with `--available`
also `{"available"}`, `inspect`: the manifest view, `doctor`: `{"problems"}`,
`sources`: `{"sources"}`, the others `{"ok", "lines"}`;
`policy status`: `{"packs"}`, `policy test`: `{"ok", "lines", "verdict"}`).
