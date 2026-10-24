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
| [Agents and teams](#agents-and-teams) | stable | bios and lineups under `<id>--<name>`; R2: capabilities, needs, namespace, workflows, acceptance |
| [Skills, commands, hooks and MCP](#skills-commands-hooks-and-mcp) | stable | the Claude-plugin layout, namespaced |
| [Permissions and grants](#permissions-and-grants) | stable | requested in pack.yaml, granted by you |
| [Studio contributions](#studio-contributions) | stable | `contributes.studio` (3.2.0.0 R3): sections, panels, palette, the settings form, event lines, attention rows; a bundle only with `studio-script` |
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
  studio: {sections: [...], panels: [...], palette: [...], config_form: true, events: {...}, attention: {...}}   # 3.2.0.0 R3, below
  fleet: {}                     # planned (R4)
  artifacts: []                 # planned (R5)
  events: [review.done]         # the kinds the pack publishes
  workflows: [review]           # the workflow names its lineups may use (3.2.0.0 R2; R5 runs them)
config:
  schema: {properties: {style: {type: string, enum: [short, long]}}, additionalProperties: false}
  defaults: {style: short}
permissions: ["mcp:lint", hooks]    # mcp:<server>, hooks, bash, network, home-write, studio-script
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

Status: **stable** (`contributes.agents` and `contributes.teams`; the schema
deltas below are stable since 3.2.0.0 R2). `agents/*.yaml` (bios) and
`teams/*.yaml` (lineups) are
read in place by the pack tier of `agent_search_dirs` / `team_search_dirs`:
after the project and home folders, before the shipped templates; the source
label is `pack:<id>`, the name `<id>--<name>`, and `_pack` and `_name` are
attached. Inside the pack, a lineup's `agent:` and a file's `extends:` may
name the pack's own bios and lineups bare; Halo qualifies them. A pack file
is never written: Studio answers 409 and offers a duplicate in your scope,
which wins (and `halo pack doctor` names the shadow). A project pack's lineup
loses `permissions.mode` and allow rules. `agents/*.md` are Claude-plugin agents.

The bio and lineup schemas are the user's ([AGENTS.md](AGENTS.md),
[ROLES.md](ROLES.md)); a pack's files add or narrow these (checked with the
manifest, `halo_harness/packs/bio_rules.py`, one line per problem naming the
file and line):

| Where | Key | Meaning |
|---|---|---|
| bio | `models.capabilities: [tag, ...]` | resolved at load to the best catalog model with every tag (`long-context`, `vision`, `audio`, `video`, `files`, `image-out`, `tools`, `local`; `halo_harness/packs/bio_models.py`); none: the user's `default` model and a doctor row. A bio of the user's may say it too. |
| bio | `models.preference` | a bare family name only (`claude-sonnet`): the family the pick prefers. A route prefix (`or:` ...), a `vendor/model` path, a Databricks name, or `models.provider`, is a manifest problem. |
| bio | `context.memory.namespace` | default the pack's id; the folder `~/.halo/packs/.data/<id>/memory/<namespace>/`; recall (`recall.search(namespace=...)`) reads it apart from the user's and every other pack's. |
| bio | `tools.needs: [need, ...]` | `bash`, `network`, `home-write`, `hooks`, `mcp:<server>`, each requested in `permissions`; an ungranted need loads the bio and gets a doctor row naming `halo pack enable <id> --grant <need>`. |
| lineup | `workflows: [name, ...]` | names from the manifest's `contributes.workflows` (names, or `workflows/<name>.yaml` whose stem is the name; R5 runs them). |
| lineup | `acceptance.test`, `acceptance.review` | the Orchestra goal's `test` and `plan: review` a run with this lineup starts with (`halo orchestra new --lineup`); `prompt` / `expect` stay the doctor's smoke prompt. |
| both | `from_pack: <id>@<version>` | written by Studio's Clone on the copy in the user's folder; changes nothing at run time. |

The manifest gains `contributes.workflows` (a list of names). Clone and
Customize copy a pack's bio or lineup into the user's folder as `<name>`
(`halo_harness/packs/clone.py`); a file of the user's, or a shipped one,
with that name is written only after the user's confirm.

## Skills, commands, hooks and MCP

Status: **stable**. An enabled pack's root joins the session's plugin roots
(`headless.build_session`), so the plugin layout loads unchanged: skills
`<id>:<skill>`, commands `<id>:<command>`, plugin agents, `hooks/hooks.json`
(with `${CLAUDE_PLUGIN_ROOT}`), MCP servers `plugin_<id>_<server>`. Nothing is
copied into `~/.claude`. Hooks load only with the `hooks` grant; an MCP
server starts only with its `mcp:<server>` grant (and `network` for a url).

## Permissions and grants

Status: **stable**. A pack requests `permissions:` in pack.yaml: `mcp:<server>`,
`hooks`, `bash`, `network`, `home-write`, `studio-script` (3.2.0.0 R3: a Studio bundle panel). You grant them with `halo pack
enable <id> --grant NAME` (or `--grant-all`); grants add up and live in
state.json; `disable` clears them. A contribution whose permission is not
granted does not run, and `halo pack doctor` says so. `bash` and `network`
are recorded for a pack's own code to check with `is_granted`; `home-write`
lets `write_private` / `write_yaml` write outside the pack's data folder.

## Studio contributions

Status: **stable** (3.2.0.0 R3). A pack adds to Studio by declaring it under
`contributes.studio`; Studio's own components draw every part from that data,
and nothing of the pack runs unless it asks for `studio-script` and you grant
it. The shell reads one registry the server builds from the packs that run
here (`GET /api/pack/registry`, `halo_harness/packs/studio_registry.py`) and
reads it again on every `pack_changed` frame, so nothing shows for a disabled
pack and a pack you enable shows without a reload. No core file is patched;
the auth, local-first and privacy model is Studio's own (loopback, the launch
token, the shell's CSP).

| Key | Shape | What Studio does with it |
|---|---|---|
| `sections` | `[{id, title, blurb, help, panels: [<panel>]}]` | a section of its own after Orchestra (Alt+7, Alt+8, Alt+9 in order; the tab strip and the rail show them after a thin "packs" divider); its panels fill the 24 columns left to right |
| `panels` | `[{section: <core section>, ...<panel>}]` | a panel in Session, Team, Roles, Fleet, Design or Orchestra, under that section's own, as a strip |
| `palette` | `[{id, label, action}]` | a command palette line in the group "pack <id>"; `action` is `route:<section>[/<panel>]`, `url:<address>` or `config` |
| `config_form` | `true` or `false` | a Settings panel (kind `form`) at the end of the pack's first section, and a palette line "Settings: <name>" |
| `events` | `{<kind>: {label, line}}` | a `pack_event` of that kind (one of `contributes.events`) renders as `label` + `line`, `{field}` read from the frame's data, in Session's Live column, Fleet's Activity and the pack's `events` panels; a kind no running pack declares keeps the generic line (the pack, the kind, the data in short) |
| `attention` | `{<kind>: {label, keys: {a, r, s, o}}}` | a row of the attention queue, kind `pack:<id>:<kind>`, with the pack's label and its answers |

A `<panel>` is `{id, title, kind, source, w, h, help, columns, links}`:

| `kind` | Reads | Draws |
|---|---|---|
| `markdown` | `source`: a `.md`, `.markdown` or `.txt` file in the pack's folder | Studio's markdown (never HTML, never a remote image) |
| `table` | `source`: a `.json` file in the pack's folder, or `data:<path>` in its data folder; a list of rows (or `{rows: [...]}`) | a table; the columns are `columns`, else the first row's keys |
| `form` | the pack's `config.schema` (`properties`, each with `type`, `enum`, `description`) | one field per key; Save checks the values against the schema and writes `packs.settings.<id>` (`GET/POST /api/pack/<id>/config`) |
| `links` | `links: [{label, route}]` or `[{label, url}]` | a route into Studio (a core section, or the pack's own section and panel), or an http(s) or mailto address in a new tab |
| `events` | the pack's own `pack_event` frames | a live list, newest last, each with its `line` |
| `bundle` | `source`: an ES module (`.js`, `.mjs`) in the pack's folder | `mount(el, api)`, loaded only when `studio-script` is granted; until then one line naming `halo pack enable <id> --grant studio-script` |

Ids (a section, a panel, a palette line) are names without `--` (letters,
digits, `-` and `_`), unique in the pack; Studio qualifies them
`<id>--<name>` (a pack's section is `doc-review--docs`) and keeps the titles
as written. `w` is 4..24 columns (default 12), `h` 8..200 rows of 8 px
(default 24). `help` is the panel's `?` popover and the Inspector's lines (one
per line); the title bar's source line says "from pack <id>". A bad
contribution is a manifest problem naming the key and its line, so the pack
does not install or run:

```
pack.yaml line 12: contributes.studio.sections[0].panels[0].kind 'chart' is not one of markdown, table, form, links, events, bundle
```

The problems checked: an unknown kind, a `source` outside the pack's folder
(or a file that is not there), a bundle without `studio-script` in
`permissions`, a route to nothing, an `events` kind not in
`contributes.events`, `config_form` without a `config.schema` or without a
section, a panel under `panels:` naming a section that is not a core one, an
id used twice or holding `--`.

The doc-review fixture's (`tests/fixtures/packs/doc-review/pack.yaml`):

```yaml
contributes:
  events: [review.done]
  studio:
    sections:
      - id: docs
        title: Docs review
        blurb: The review notes, the checks and the links
        panels:
          - {id: notes, title: Review notes, kind: markdown, source: studio/notes.md, w: 12, h: 30}
          - {id: checks, title: Checks, kind: table, source: studio/checks.json, columns: [check, state, note], w: 12, h: 30}
          - id: links
            title: Links
            kind: links
            w: 24
            h: 16
            links:
              - {label: Roles (the review lineup), route: roles}
              - {label: The checks, route: docs/checks}
              - {label: How packs work, url: "https://github.com/roloVibes/Halo-Harness/blob/master/docs/PACKS.md"}
    panels:
      - {id: reviews, section: session, title: Reviews, kind: events, w: 10, h: 24}
    palette:
      - {id: open-checks, label: Open the review checks, action: "route:docs/checks"}
    config_form: true
    events:
      review.done: {label: REVIEW, line: "{file}: {findings} findings"}
    attention:
      review.ask: {label: review, keys: {a: accept, r: redo, s: skip, o: open}}
```

`tests/fixtures/packs/studio-bundle/` is the bundle example: one section, one
`bundle` panel (`studio/hello.js`, twenty lines that write "hello from
<id>"), `permissions: [studio-script]`.

**The routes** (`halo_harness/studio/packs_studio_api.py`, behind the token
guard of every Studio route; a pack that does not run here answers 404):

- `GET /api/pack/registry`: `{version: 1, core: [the six], packs: [{id, name,
  version, scope, script: granted | not granted | none, grant, sections,
  panels, palette, config_form, events, attention}]}`, ids qualified, routes
  resolved to `{section, panel?}`, each panel with `about` ("from pack <id>"),
  `collapsed` (true in a core section) and `file` (the api path of its
  source; a bundle's only once granted).
- `GET /api/pack/<id>/file/<path>`: a markdown or JSON file inside the pack's
  folder, or its bundle module (a bundle panel's `source`, only with
  `studio-script` granted, else 403 naming the grant), under the shell's CSP.
  An `import()` sends no header, so this route also takes the token in `?t=`,
  as `/api/events` does. `..`, an absolute path or another file type is 404.
- `GET /api/pack/<id>/data/<path>`: a markdown or JSON file in the pack's data
  folder (`~/.halo/packs/.data/<id>/`, where `write_private` writes).
- `GET /api/pack/<id>/config` and `POST /api/pack/<id>/config {values: {key:
  value}}`: the form's fields and values; a value that does not fit the
  schema answers 422 and nothing is written.

**A bundle** is a module that exports `mount(el, api)`: `el` is the panel's
body, `api` is `{pack, panel, get(path), config()}` (`get` reads a file of
the pack as text, `config` its settings); what `mount` returns, when it is a
function, runs when the panel goes away. It runs in the page like the
shell's own script, so it is the one Studio contribution that takes your
explicit grant (`halo pack enable <id> --grant studio-script`), as `bash` and
`hooks` do.

**Attention rows** come from the pack's code: it writes one JSON file per row
in its data folder with the stable surface,
`write_private("<id>", "attention/<row>.json", json.dumps({"kind": "review.ask", "what": "...", "detail": "..."}))`.
The row shows while the pack runs and its kind is declared; A, R or S answers
it through the queue's answer route: Studio writes `answers/<row>.json`
(`{row, kind, key, answer, text, by, ts}`) beside it and removes the row
file, for the pack's code to read; O opens the pack's first section.

**`pack_changed`** (`{"event": "pack_changed", "data": {"why"}}`) goes out on
`/api/events` after `halo pack enable`, `disable`, `install`, `update` and
`remove` in Studio's own process, and within two seconds of the same change
made from another terminal (Studio watches the packs folders, each pack.yaml
and state.json).

## Fleet capabilities

Status: **planned** (R4). Proposed `contributes.fleet`: `{capabilities:
[{name, requires: {tools, runtimes, platform, hardware}}]}` merged into the
fleet capabilities catalog; a capability never carries a credential, a
private path or an environment value.

## Workflow contracts

Status: **planned** (R5). Proposed: a declarative workflow file on top of
the Orchestra (stages, typed inputs and outputs, gates, budgets, checks),
listed under `contributes.workflows`, runnable on any compatible model.
Since R2 `contributes.workflows` is read for its names (a lineup's
`workflows:` is checked against them); nothing runs a workflow yet.

## Events and artifacts

Status: **planned**; `publish_event` itself is stable. A frame is `{"session_id":
"pack:<id>", "event": "pack_event", "pack": "<id>", "data": {"pack", "kind",
"data"}, "ts"}`; `kind` is one of `contributes.events`. Since 3.2.0.0 R3 a kind's line in Studio is
`contributes.studio.events.<kind>` (`{label, line}`, [Studio contributions](#studio-contributions)). Proposed for R5:
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
