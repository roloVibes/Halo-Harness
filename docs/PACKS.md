# Packs

Read this when you add a pack of bios, lineups, skills, commands, hooks and MCP servers to Halo, or take one out again.

Halo 3.2.0.0. One harness, one Studio, and packs: folders someone else
maintains that add bios, lineups, skills, commands, hooks and MCP servers to
your Halo without changing Halo itself. A pack is installed disabled; you
enable it and grant what it asks for; disabling it changes nothing else;
removing it takes away its own files and never yours. The commands are in
[COMMANDS-packs.md](COMMANDS-packs.md); the contract a pack is written
against is [EXTENSION_API.md](EXTENSION_API.md).

## What a pack is

A folder named by the pack's id with a `pack.yaml` at its root. The rest is
a Claude-plugin layout plus Halo's own bio and lineup files:

```
doc-review/
  pack.yaml                 # id, name, version, the API versions it works with, what it offers, what it requests
  .claude-plugin/plugin.json
  agents/reviewer.yaml      # a Halo bio        -> doc-review--reviewer
  agents/helper.md          # a Claude-plugin agent
  teams/review.yaml         # a Halo lineup     -> doc-review--review
  skills/check-links/SKILL.md                   -> /doc-review:check-links
  commands/review.md                            -> /doc-review:review
  hooks/hooks.json          # loads once you grant hooks
  .mcp.json                 # servers start once you grant mcp:<server>  -> plugin_doc-review_lint
```

Every name a pack offers carries its id, so two packs never take the same
name and a pack never takes one of yours: bios and lineups are `<id>--<name>`
(`halo agents` and `halo teams` list them under the pack, Studio's Roles
shows them read-only), skills and commands `<id>:<name>`, MCP servers
`plugin_<id>_<server>`.

## Where packs live

- `~/.halo/packs/<id>/`: yours, for every repo (`halo pack install <path|git url>`).
- `<repo>/.halo/packs/<id>/`: this repo's (`--project`). A repo's pack is the
  untrusted layer: its lineups lose `permissions.mode` and allow rules, the
  way a repo's own lineup does in a folder you have not trusted. A repo's
  pack with the same id as one of yours is the one used (doctor says so).
- `~/.halo/packs/state.json`: which packs are installed, from where, enabled
  or not and what you granted (private, 0600). A pack is enabled for the
  folder you enabled it in, so a same-id pack in another repo stays off.
- `~/.halo/packs/journal.jsonl`: every file an install, update or remove
  wrote or deleted, with its hash: how Halo knows which files are the pack's.
- `~/.halo/packs/.data/<id>/`: the pack's own place to write.
- Settings: `~/.halo/config.json` under `packs.settings.<id>`, checked
  against the schema in the pack's `pack.yaml` (`halo config set
  packs.settings.doc-review.style long`).

## The lifecycle

1. `halo pack inspect ./doc-review` reads a pack folder before you install it:
   what it offers, what it requests, its problems.
2. `halo pack install ./doc-review` (or a git url) checks everything first,
   then copies every file through the journal. Nothing is overwritten: a
   folder already at `~/.halo/packs/doc-review/` is left as it is.
3. `halo pack enable doc-review --grant mcp:lint --grant hooks` turns it on.
4. `halo pack disable doc-review` turns it off: nothing of it runs, its
   files stay, its grants clear.
5. `halo pack update doc-review` brings in the new version from where it was
   installed from, prints the pack's migration notes, and keeps any file
   you changed.
6. `halo pack remove doc-review` removes it (below).

`halo pack doctor` (and the packs group of `halo doctor --config`) lists
every problem in one line each.

## Grants

A pack asks for what its contributions need: `mcp:<server>` for each MCP
server (and `network` for one reached by a url), `hooks` for its hooks,
`bash`, `network` and `home-write` for its own code. Nothing it asks for runs
until you grant it: an ungranted MCP server does not start, ungranted hooks
do not load, and doctor names each one with the command that grants it.
Grants add up across `enable` calls and live in state.json; `disable`
clears them.

## Remove keeps your work

`halo pack remove <id>` deletes only the files the pack's install or update
wrote and that still hold what was written. It keeps, and lists:

- a file in the pack's folder you changed or added (the folder stays with them);
- your bios and lineups named `<id>--*` (a duplicate you made in Studio);
- your lineups that name the pack's bios;
- the lineups' memory and layout folders (`~/.halo/teams/<id>--*/`);
- your settings under `packs.settings.<id>` and a `team:` naming its lineup.

`--keep-config` also keeps the pack's record and grants, so installing it
again later starts where you left off. A pack Halo found in place (a folder
you put there yourself) has no files of Halo's to remove: nothing in it is deleted.
