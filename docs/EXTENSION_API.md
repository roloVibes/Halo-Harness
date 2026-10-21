# The extension API

Read this when you write a pack, or change what Halo promises a pack: the manifest, the lifecycle, what a pack may import and what each part's status is.

Halo 3.2.0.0 R1. A pack is a folder Halo installs, enables and removes (see
[PACKS.md](PACKS.md) for using one); this page is the contract a pack is
written against. The extension API version is `API_VERSION = "1.0"`
(`halo_harness.ext.API_VERSION`, also exported as `HALO_API_VERSION`). The
machine-readable manifest schema is
`halo_harness/packs/schema/pack.schema.json`; the reference fixture is
`tests/fixtures/packs/doc-review/`.

## Status of each part

| Part | Status | What the status means here |
|---|---|---|
| [The stable surface](#the-stable-surface-halo_harnessext) | stable | names and meanings hold for every 1.x |
| [The manifest](#the-manifest-packyaml) | stable | format 1, read by API 1.x |
| [The lifecycle](#the-lifecycle) | stable | `halo pack` verbs, state.json, the journal |
| [Agents and teams](#agents-and-teams) | stable | bios and lineups under `<id>--<name>` |
| [Skills, commands, hooks and MCP](#skills-commands-hooks-and-mcp) | stable | the Claude-plugin layout, namespaced |
| [Permissions and grants](#permissions-and-grants) | stable | requested in pack.yaml, granted by you |
| [Studio contributions](#studio-contributions) | planned | shape proposed; R3 builds it |
| [Fleet capabilities](#fleet-capabilities) | planned | shape proposed; R4 builds it |
| [Workflow contracts](#workflow-contracts) | planned | shape proposed; R5 builds it |
| [Events and artifacts](#events-and-artifacts) | planned | typed schemas proposed; `publish_event` is stable |
| [Compatibility and migration](#compatibility-and-migration) | planned | the policy below is the proposal R7 makes final |
| [The reference example](#the-reference-example) | planned | the fixture today; the Documentation Review pack in R6 |

`stable`: a 1.x Halo keeps it. `draft`: usable, may change in a minor API
version with a migration note. `planned`: the shape is proposed here and
nothing reads it yet (a manifest may carry it; Halo stores it and does not act).

## The stable surface (`halo_harness.ext`)

Status: **stable**. A pack's code imports `halo_harness.ext` and nothing
else of Halo (`tests/test_ext_api.py` walks every fixture pack's Python to
check it). The modules under `halo_harness/ext/` are the implementation; the
names in `__all__` are the contract.

- `API_VERSION`, `HALO_API_VERSION`: `"1.0"`.
- `read_yaml(path)`: a dict, `{}` for an empty file, None when missing or not a mapping.
- `write_yaml(pack_id, path, data)`: `[]` when written, else one line; lands where `write_private` would.
- `check_schema(doc, schema)`: one finding per shape problem, `{check, key, text, closest}`.
- `get_config(pack_id, key=None, default=None)` / `set_config(pack_id, key, value)`: the pack's own settings,
  `packs.settings.<id>` over the manifest's `config.defaults`, checked against `config.schema` before writing.
- `write_private(pack_id, path, text)`: a 0600 file, written atomically. A relative path lands in the pack's
  data folder `~/.halo/packs/.data/<id>/`; a path outside it needs the `home-write` grant.
- `pack_dir(pack_id)`: the pack's own folder (Halo never writes there). `data_dir(pack_id)`: its data folder.
- `publish_event(pack_id, kind, data=None)`: a frame on Studio's live feed (below), True when a Studio took it.
- `is_granted(pack_id, permission)`: whether you granted it (False while the pack is disabled).
- `Unit`: the unit of work (`halo_harness.work.unit.Unit`, docs/WORK.md).
- `is_valid_pack_id`, `is_valid_name`, `qualified_name(pack_id, name)`, `split_name(name)`: the name rules.

## The manifest (`pack.yaml`)

Status: **stable**, manifest format 1 (read by extension API 1.x). At the
pack's root, read through Halo's YAML reader and checked by
`halo_harness.packs.manifest.validate_manifest`: an unknown key is one line
naming the closest known key; every bad value is one line.

```yaml
id: doc-review                  # required: ^[a-z][a-z0-9-]*$, no "--", no trailing "-"; the folder's name
name: Documentation review      # required
version: 1.0.0                  # required: semver
description: A reviewer and a writer bio, a review lineup, ...
author: Halo fixtures           # a string, or {name, email, url}
license: MIT
halo_api: {min: "1.0", max: "1.9"}   # required min: the extension API versions it works with
halo: {min: "3.1"}              # optional: the Halo versions it works with
capabilities: [docs.review]     # names (lower-case, digits, . _ -)
requires: [{pack: base-docs, version: "1.2"}]   # version: a minimum, or {min, max}
contributes:
  agents: [agents/reviewer.yaml, agents/writer.yaml, agents/helper.md]
  teams: [teams/review.yaml]
  skills: skills                # the plugin layout's places, exactly
  commands: commands
  hooks: hooks/hooks.json
  mcp: [{name: lint, description: checks links}]   # each a server in .mcp.json
  studio: {}                    # planned (R3)
  fleet: {}                     # planned (R4)
  artifacts: []                 # planned (R5)
  events: [review.done]         # the kinds the pack publishes
config:
  schema: {properties: {style: {type: string, enum: [short, long]}}, additionalProperties: false}
  defaults: {style: short}
permissions: ["mcp:lint", hooks]    # mcp:<server>, hooks, bash, network, home-write
migrations:
  - {from: 0.9.0, to: 1.0.0, note: the reviewer bio is now doc-review--reviewer}
```

Version ranges compare release numbers of any length (missing parts are 0);
`max` is inclusive at its own precision (`max: "1.9"` takes 1.9.4). A pack
folder is a Claude-plugin layout (`.claude-plugin/plugin.json`, `agents/`,
`skills/`, `commands/`, `hooks/hooks.json`, `.mcp.json`) plus `pack.yaml`
and Halo's `agents/*.yaml` and `teams/*.yaml`; `plugin.json`'s `name`, when
set, is the pack's id. A contribution needs its permission requested (an MCP
server `mcp:<server>`, a url server `network` too, a hooks file `hooks`).

## The lifecycle

Status: **stable**. `halo pack list | inspect | install | enable | disable |
update | remove | doctor` ([COMMANDS-packs.md](COMMANDS-packs.md)).

- **Discovery**: `<repo>/.halo/packs/<id>/` (project, the untrusted layer) then
  `~/.halo/packs/<id>/` (user); a same-id pack in the repo is the one used.
  A folder whose name starts with `.` is Halo's own (`.data`, `.backup`, `.staging-*`).
- **Install** validates everything before writing anything: the manifest, the
  `halo_api` and `halo` ranges; a folder already at `<packs>/<id>/` is never
  overwritten. Every file is written through the journal
  `~/.halo/packs/journal.jsonl` (`{ts, op, op_id, pack, path, existed, before,
  after}`, content hashes); a failed copy rolls back. A git url is cloned
  fresh; offline mode answers "offline mode: not connecting to <host>".
- **State** is `~/.halo/packs/state.json`, written privately:
  `{"version": 1, "installed": {"<id>": {version, source, installed, enabled, granted, scope, root}}}`.
  A pack is enabled only for the folder its record names.
- **Resolution**: an enabled pack runs when its manifest validates, the API
  and Halo versions are in range and every `requires` entry is installed,
  enabled, in range and running; a cycle is one line. Dependencies run first.
- **Disable**: nothing of the pack contributes; its files stay; grants clear.
- **Update** replaces the pack's own unchanged files from its source, keeps a
  file you changed and prints the `migrations` notes between the versions.
- **Remove** deletes only the pack's own files (the journal's, unchanged);
  your bios, lineups, memory folders and settings stay and are listed.

## Agents and teams

Status: **stable**. `agents/*.yaml` (bios) and `teams/*.yaml` (lineups) are
read in place by the pack tier of `agent_search_dirs` / `team_search_dirs`:
after the project and home folders, before the shipped templates; the source
label is `pack:<id>`, the name `<id>--<name>`, and `_pack` and `_name` are
attached. Inside the pack, a lineup's `agent:` and a file's `extends:` may
name the pack's own bios and lineups bare; Halo qualifies them. A pack file
is never written: Studio answers 409 and offers a duplicate in your scope,
which wins (and `halo pack doctor` names the shadow). A project pack's lineup
loses `permissions.mode` and allow rules. `agents/*.md` are Claude-plugin agents.

## Skills, commands, hooks and MCP

Status: **stable**. An enabled pack's root joins the session's plugin roots
(`headless.build_session`), so the plugin layout loads unchanged: skills
`<id>:<skill>`, commands `<id>:<command>`, plugin agents, `hooks/hooks.json`
(with `${CLAUDE_PLUGIN_ROOT}`), MCP servers `plugin_<id>_<server>`. Nothing is
copied into `~/.claude`. Hooks load only with the `hooks` grant; an MCP
server starts only with its `mcp:<server>` grant (and `network` for a url).

## Permissions and grants

Status: **stable**. A pack requests `permissions:` in pack.yaml: `mcp:<server>`,
`hooks`, `bash`, `network`, `home-write`. You grant them with `halo pack
enable <id> --grant NAME` (or `--grant-all`); grants add up and live in
state.json; `disable` clears them. A contribution whose permission is not
granted does not run, and `halo pack doctor` says so. `bash` and `network`
are recorded for a pack's own code to check with `is_granted`; `home-write`
lets `write_private` / `write_yaml` write outside the pack's data folder.

## Studio contributions

Status: **planned** (R3). Proposed `contributes.studio`: `{sections: [{id,
title, bundle}], panels: [{section, id, title, bundle}], palette: [{id,
label, route}]}`; a bundle is a file under the pack loaded by the Studio
server under `/pack/<id>/` (same origin, Studio's CSP), with a typed data
contract; nothing shows for a disabled pack.

## Fleet capabilities

Status: **planned** (R4). Proposed `contributes.fleet`: `{capabilities:
[{name, requires: {tools, runtimes, platform, hardware}}]}` merged into the
fleet capabilities catalog; a capability never carries a credential, a
private path or an environment value.

## Workflow contracts

Status: **planned** (R5). Proposed: a declarative workflow file on top of
the Orchestra (stages, typed inputs and outputs, gates, budgets, checks),
listed under `contributes.workflows`, runnable on any compatible model.

## Events and artifacts

Status: **planned**; `publish_event` itself is stable. A frame is `{"session_id":
"pack:<id>", "event": "pack_event", "pack": "<id>", "data": {"pack", "kind",
"data"}, "ts"}`; `kind` is one of `contributes.events`. Proposed for R5:
typed event schemas (`contributes.events: [{kind, schema}]`) and artifact
schemas with viewers (`contributes.artifacts: [{kind, schema, viewer}]`).

## Compatibility and migration

Status: **planned** (R7 makes it final). Proposed policy: the API version is
`major.minor`; a minor version adds names and keeps every 1.x name's meaning;
a major version may remove one, announced a minor version ahead. A pack
states `halo_api: {min, max}`; a Halo outside the range does not run it and
says so. A pack's own breaking change is listed under `migrations` and
printed by `halo pack update`. A renamed pack is a new pack.

## The reference example

Status: **planned** (R6: the Documentation Review pack). Today:
`tests/fixtures/packs/doc-review/`, every contribution kind of this round.
