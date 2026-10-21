# Commands: packs

Read this when you list, inspect, install, enable, update or remove a pack from the command line (`halo pack`).

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

### `halo pack inspect`

`halo pack inspect <id|path>`: the manifest (name, version, the extension
API and Halo versions it works with, what it requires), every name it
offers, each permission it requests with what needs it and whether it is
granted, its settings (defaults with yours on top) and its problems. A path
inspects a pack folder before you install it.

### `halo pack install`

`halo pack install <path|git url>` copies the pack into `~/.halo/packs/<id>/`;
`--project` copies it into this repo's `.halo/packs/<id>/` instead.
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

### `halo pack disable`

`halo pack disable <id>`: nothing of the pack contributes from then on; its
files stay; its grants clear (the next `enable` states them again).

### `halo pack update`

`halo pack update <id>` reads the pack's recorded source again (a folder, or
a fresh clone of its url) and, through the journal, replaces each file the
pack wrote that you have not changed; a file you changed or added stays and
is listed. The `migrations` notes between the installed and the new version
are printed.

### `halo pack remove`

`halo pack remove <id>` deletes the pack's own files only and drops its
record. Your bios and lineups named `<id>--*`, your lineups naming its bios,
their memory folders (`~/.halo/teams/<id>--*/`), your `packs.settings.<id>`
and a `team:` naming its lineup stay, each listed.

#### `--keep-config`

Keep the pack's record (disabled, with its grants), so installing it again
starts with the same grants.

### `halo pack doctor`

Every problem, one line each: a manifest that does not validate, an API or
Halo version outside a pack's range, a missing, disabled or out-of-range
required pack, a requires cycle, a contribution whose permission is not
granted, settings outside the pack's schema, a name two packs (or a pack and
you) offer, a pack shadowed by a same-id repo pack, a state record whose
folder is gone, a bio or lineup file pack.yaml does not list, and what the
privacy scan finds in the pack's files. `halo doctor --config` lists the
same lines under its packs group.

#### `--cwd`

Every verb: act as if run from DIR.

#### `--json`

Every verb: print one JSON object (`list`: `{"packs"}`, `inspect`: the
manifest view, `doctor`: `{"problems"}`, the others `{"ok", "lines"}`).
