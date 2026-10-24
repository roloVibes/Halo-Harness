# Commands: packs

Read this when you list, inspect, install, enable, grant, update, roll back or remove a pack, or name where packs come from, on the command line (`halo pack`).

Part of [Commands](COMMANDS.md), which lists every part.

## `halo pack`

Halo 3.2.0.0. A pack is a folder of bios, lineups, skills, commands, hooks
and MCP servers with a `pack.yaml` at its root ([PACKS.md](PACKS.md); the
contract is [EXTENSION_API.md](EXTENSION_API.md)). Every verb takes `--cwd
DIR` (act as if run from DIR, so its `.halo/packs/` is the repo's) and
`--json` (one JSON object on stdout). Exit codes: 0 done, 1 could not (the
reason on stderr, one line each; for `doctor`: problems found), 2 usage. A
bare `halo pack` prints the verb list.

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
lineup with its members, tiers, workflows and acceptance, each permission it
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
  doc-review--review: doc-review--writer (main), doc-review--reviewer (reviewer); 2 tiers; workflows review; acceptance.test: python -m pytest -q; acceptance.review: true
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
does not start, its hooks do not load. Grants add up across calls.

#### `--grant`

`--grant NAME`, repeatable: grant one permission the pack requests
(`mcp:<server>`, `hooks`, `bash`, `network`, `home-write`). A name it does
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
are manifest problems (the first group).

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
`sources`: `{"sources"}`, the others `{"ok", "lines"}`).
