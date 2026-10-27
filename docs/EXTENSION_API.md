# The extension API

Read this when you write a pack, or change what Halo promises a pack: the manifest, the lifecycle, what a pack may import and what each part's status is.

Halo 3.2.0.0 (written in R1, final in R7: every part below is `stable`). A pack is a folder Halo installs, enables and removes (see
[PACKS.md](PACKS.md) for using one); this page is the contract a pack is
written against. The extension API version is `API_VERSION = "1.0"`
(`halo_harness.ext.API_VERSION`, also exported as `HALO_API_VERSION`). The
machine-readable manifest schema is
`halo_harness/packs/schema/pack.schema.json`; the reference pack is
`halo_harness/templates/packs/doc-review/` (3.2.0.0 R6, shipped with Halo).

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
| [Fleet capabilities](#fleet-capabilities) | stable | `contributes.fleet` (3.2.0.0 R4): worker capabilities in the catalog, available or not and why; mission needs, the worker's own check, inspector lines, mission metadata |
| [Workflow contracts](#workflow-contracts) | stable | `workflows/<name>.yaml` (3.2.0.0 R5): compiled to an Orchestra goal, its hand-offs and a pinned plan; `halo workflow` |
| [Events and artifacts](#events-and-artifacts) | stable | typed events (3.2.0.0 R5: schemas, the events log, subscriptions), typed artifacts with viewers, memory with provenance |
| [Compatibility and migration](#compatibility-and-migration) | stable | the version policy (`ext.compatible`, `ext.deprecations`), `migrations` shown before an update and applied, `halo pack rollback` (3.2.0.0 R7) |
| [The reference example](#the-reference-example) | stable | the Documentation Review pack Halo ships (3.2.0.0 R6): every part of the API in one pack a third party can copy |

`stable`: a 1.x Halo keeps it. `removed <version>`: gone in that version,
announced a minor version before it ([Changes in 1.x](#changes-in-1x)).
Since 3.2.0.0 every part is `stable` and none is removed; a later part may
start as `draft` (usable, may change in a minor API version with a migration
note) or `planned` (the shape proposed, nothing reads it yet).

## The stable surface (`halo_harness.ext`)

Status: **stable**. A pack's code imports `halo_harness.ext` and nothing
else of Halo (`tests/test_ext_api.py` walks every fixture and shipped pack's Python to
check it). The modules under `halo_harness/ext/` are the implementation; the
names in `__all__` are the contract.

- `API_VERSION`, `HALO_API_VERSION`: `"1.0"`.
- `api_version()`, `compatible(range)`, `deprecations()`: 3.2.0.0 R7, the version policy
  ([Compatibility and migration](#compatibility-and-migration)): this API's version, whether a `halo_api`
  range takes it, the names announced for removal (`[{name, since, removed_in, use}]`, none in 1.0).
- `read_yaml(path)`: a dict, `{}` for an empty file, None when missing or not a mapping.
- `write_yaml(pack_id, path, data)`: `[]` when written, else one line; lands where `write_private` would.
- `check_schema(doc, schema)`: one finding per shape problem, `{check, key, text, closest}`.
- `get_config(pack_id, key=None, default=None)` / `set_config(pack_id, key, value)`: the pack's own settings,
  `packs.settings.<id>` over the manifest's `config.defaults`, checked against `config.schema` before writing.
- `write_private(pack_id, path, text)`: a 0600 file, written atomically. A relative path lands in the pack's
  data folder `~/.halo/packs/.data/<id>/`; a path outside it needs the `home-write` grant.
- `pack_dir(pack_id)`: the pack's own folder (Halo never writes there). `data_dir(pack_id)`: its data folder.
- `publish_event(pack_id, kind, data=None)`: a frame on Studio's live feed (below), True when a Studio took it;
  3.2.0.0 R5: a declared kind's data is checked against its schema (a mismatch goes out with `problems`), the
  event is kept in the pack's events log, and a pack that does not run here is refused with one line (ValueError).
- `memory.write(namespace, text, provenance=None)`: 3.2.0.0 R5, a note in the pack's memory namespace with its
  `_meta.json` (source, run, stage, written, retention, shared; [Events and artifacts](#events-and-artifacts)).
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
name: Documentation Review      # required
version: 1.0.0                  # required: semver
description: Reviews a repo's Markdown documents with ...
author: Halo Harness            # a string, or {name, email, url}
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
  fleet: {capabilities: [...], inspector: [...], mission: {metadata: {...}}}   # 3.2.0.0 R4, below
  artifacts: [review-report]    # 3.2.0.0 R5: artifact schemas, artifacts/<name>.json
  events: [review.done]         # the kinds the pack publishes; a kind or {kind, schema} (R5: events/<kind>.json)
  workflows: [review]           # workflow names (R2), each workflows/<name>.yaml (R5)
config:
  schema: {properties: {style: {type: string, enum: [short, long]}}, additionalProperties: false}
  defaults: {style: short}
permissions: ["mcp:lint", hooks]    # mcp:<server>, hooks, bash, network, home-write, studio-script
migrations:
  - {from: 0.9.0, to: 1.0.0, note: the reviewer bio is now doc-review--reviewer}
  # 3.2.0.0 R7: settings renames packs.settings.<id> keys as the update runs
  # - {from: 1.1.0, to: 1.3.0, note: settings key `lint.level` is now `lint.strictness`, settings: {lint.level: lint.strictness}}
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
  A folder whose name starts with `.` is Halo's own (`.data`, `.backup`, `.staging-*`), and so is
  `<id>.previous` (the version the last update replaced, 3.2.0.0 R7).
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
- **Update** (3.2.0.0 R7) says the `migrations` notes between the versions first, stages the
  new version beside the pack (your changed and added files carried over), swaps it in by two
  renames and keeps the old one as `<id>.previous`; `--dry-run` says it all and changes nothing
  ([Updating a pack](#updating-a-pack)).
- **Rollback** (3.2.0.0 R7) swaps `<id>.previous` back ([Rolling back](#rolling-back)).
- **Remove** deletes only the pack's own files (the journal's, unchanged) and `<id>.previous`;
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
| bio | `models.capabilities: [tag, ...]` | resolved at load to the best catalog model with every tag (`long-context`, `vision`, `audio`, `video`, `files`, `image-out`, `tools`, `local`, and since 3.2.1.0 `reasoning`, `open-weights`, `audio-out`; `halo_harness/packs/bio_models.py`); none: the user's `default` model and a doctor row. A bio of the user's may say it too. |
| bio | `models.preference` | a bare family name only (`claude-sonnet`): the family the pick prefers. A route prefix (`or:` ...), a `vendor/model` path, a Databricks name, or `models.provider`, is a manifest problem. |
| bio | `context.memory.namespace` | default the pack's id; the folder `~/.halo/packs/.data/<id>/memory/<namespace>/`; recall (`recall.search(namespace=...)`) reads it apart from the user's and every other pack's. |
| bio | `tools.needs: [need, ...]` | `bash`, `network`, `home-write`, `hooks`, `mcp:<server>`, each requested in `permissions`; an ungranted need loads the bio and gets a doctor row naming `halo pack enable <id> --grant <need>`. |
| lineup | `workflows: [name, ...]` | names from the manifest's `contributes.workflows` (names, or `workflows/<name>.yaml` whose stem is the name; R5 runs them). 3.2.1.0 R2: an item may be `<id>/<name>` (the pack's own; another pack's is a manifest line); the resolved lineup carries `workflow_refs` (`["<id>/<name>", ...]`) beside the names ([PACKS.md](PACKS.md#a-lineups-workflows)). |
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

A `command` hook has two forms, and both work on Windows and Linux:

| Form | Entry | `${CLAUDE_PLUGIN_ROOT}` and `${halo_python}` |
|---|---|---|
| exec (recommended) | `{"type": "command", "args": ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/hooks/note.py"]}` | the paths as they are; no shell reads them |
| shell | `{"type": "command", "command": "sh ${CLAUDE_PLUGIN_ROOT}/hooks/run.sh"}` | as the hook's shell reads them (3.2.1.0 R4): forward slashes on Windows (Git Bash), quoted when a path holds a space or another character the shell reads, escaped inside your own `"..."` or `'...'`; `shell: "powershell"` gets the plugin root as it is |

Every other field of the entry, and the hook's `CLAUDE_PLUGIN_ROOT`
environment variable, get the path as it is
([PACKS.md](PACKS.md#a-packs-own-python)).

A skill's `SKILL.md` body follows the same rule for its own variables
(3.2.1.0 R5): in a `` !`sh ${CLAUDE_SKILL_DIR}/scripts/x.sh` `` span the
skill's folder goes in as the span's shell reads it, and the rest of the
body gets it as it is. A skill or command body does not get
`${CLAUDE_PLUGIN_ROOT}`; a skill names its own files by `${CLAUDE_SKILL_DIR}`
([SLASH-COMMANDS-tui.md](SLASH-COMMANDS-tui.md)).

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
| `sections` | `[{id, title, blurb, help, panels: [<panel>]}]` | a section of its own after the core sections (3.2.0.0 R6: after the core sections; 3.3.3.0 R2: after Settings, no key of their own, reached by a click or the palette; the icon rail shows them after a thin divider, each with the diamond, 3.3.2.0); its panels fill the 24 columns left to right |
| `panels` | `[{section: <core section>, ...<panel>}]` | a panel in Session, Team, Roles, Fleet, Design or Orchestra, under that section's own, as a strip |
| `palette` | `[{id, label, action}]` | a command palette line in the group "pack <id>"; `action` is `route:<section>[/<panel>]`, `url:<address>` or `config` |
| `config_form` | `true` or `false` | a Settings panel (kind `form`) at the end of the pack's first section, and a palette line "Settings: <name>" |
| `events` | `{<kind>: {label, line}}` | a `pack_event` of that kind (one of `contributes.events`) renders as `label` + `line`, `{field}` read from the frame's data, in Session's Live column, Fleet's Activity and the pack's `events` panels; a kind no running pack declares keeps the generic line (the pack, the kind, the data in short) |
| `attention` | `{<kind>: {label, keys: {a, r, s, o}}}` | a row of the attention queue, kind `pack:<id>:<kind>`, with the pack's label and its answers |

A `<panel>` is `{id, title, kind, source, schema, w, h, help, columns, links}`:

| `kind` | Reads | Draws |
|---|---|---|
| `markdown` | `source`: a `.md`, `.markdown` or `.txt` file in the pack's folder | Studio's markdown (never HTML, never a remote image) |
| `table` | `source`: a `.json` file in the pack's folder, or `data:<path>` in its data folder; a list of rows (or `{rows: [...]}`) | a table; the columns are `columns`, else the first row's keys |
| `form` | the pack's `config.schema` (`properties`, each with `type`, `enum`, `description`) | one field per key; Save checks the values against the schema and writes `packs.settings.<id>` (`GET/POST /api/pack/<id>/config`) |
| `links` | `links: [{label, route}]` or `[{label, url}]` | a route into Studio (a core section, or the pack's own section and panel), or an http(s) or mailto address in a new tab |
| `events` | the pack's own `pack_event` frames | a live list, newest last, each with its `line` |
| `bundle` | `source`: an ES module (`.js`, `.mjs`) in the pack's folder | `mount(el, api)`, loaded only when `studio-script` is granted; until then one line naming `halo pack enable <id> --grant studio-script` |
| `artifact` | `schema`: one of `contributes.artifacts`; `source`: `latest` (the default: the newest finished run of Studio's repo with an artifact of that schema, `GET /api/pack/<id>/artifact/<schema>`), a `.json` file in the pack's folder or `data:<path>` | 3.2.0.0 R5: the document drawn by its schema's `x-halo-view`: `table`, `markdown` or `keyvalue` (the default) |

Ids (a section, a panel, a palette line) are names without `--` (letters,
digits, `-` and `_`), unique in the pack; Studio qualifies them
`<id>--<name>` (a pack's section is `doc-review--docs`) and keeps the titles
as written. `w` is 4..24 columns (default 12), `h` 8..200 rows of 8 px
(default 24). `help` is the panel's `?` popover and the Inspector's lines (one
per line); its source line, "from pack <id>", is the first line of that `?` (3.3.2.0: the title line carries no about line). A bad
contribution is a manifest problem naming the key and its line, so the pack
does not install or run:

```
pack.yaml line 12: contributes.studio.sections[0].panels[0].kind 'chart' is not one of markdown, table, form, links, events, bundle, artifact
```

The problems checked: an unknown kind, a `source` outside the pack's folder
(or a file that is not there), a bundle without `studio-script` in
`permissions`, a route to nothing, an `events` kind not in
`contributes.events`, `config_form` without a `config.schema` or without a
section, a panel under `panels:` naming a section that is not a core one, an
id used twice or holding `--`.

The doc-review reference pack's (`halo_harness/templates/packs/doc-review/pack.yaml`):

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

Status: **stable** (3.2.0.0 R4). A pack declares the worker capabilities it
brings under `contributes.fleet`; each becomes an entry in this harness's
capabilities catalog (docs/FLEET.md "Capabilities"), checked on this host:
available or not, and why. `halo fleet who` finds them, a mission's planner
sees them in each harness's block, and a part may name one in `needs`; the
hub sends such a part only to a harness whose pack runs with the grants the
capability requires, and the worker checks that again before the part runs.
Nothing changes for a fleet with no pack.

| Key | Shape | What Halo does with it |
|---|---|---|
| `capabilities` | `[{name, description, requires, capacity}]` | one catalog entry each (`packs` section): `{name, description, available, why, checks, requires, capacity}` |
| `capabilities[].name` | one of the top-level `capabilities:` | what a part's `needs` names (`docs.review`, or `pack:docs.review`) |
| `capabilities[].description` | a sentence | `halo fleet who` ranks by it; no path in it |
| `capabilities[].requires.tools` | `[name]` | a CLI on PATH, an MCP server or tool, a craft app here |
| `capabilities[].requires.runtimes` | `[word]` | `python`, `node`, `java` ... found here (a version when known) |
| `capabilities[].requires.platform` | `[word]` | this host's OS or distro is one of them (`linux`, `windows`, `darwin`, `kali` ...) |
| `capabilities[].requires.hardware` | `{gpu: true \| false \| <a word of its name>, ram_gb: n}` | a GPU (or one whose name has the word, `4090`), at least that much RAM |
| `capabilities[].requires.models` | `[tag or model]` | a catalog model with the tag (`long-context`, `vision`, `audio`, `video`, `files`, `image-out`, `tools`, `local`, `reasoning`, `open-weights`, `audio-out`), or one by its ref or family |
| `capabilities[].requires.grants` | `[permission]` | each one of the pack's `permissions`, granted here |
| `capabilities[].requires.locality` | `[repo \| repo:<name> \| shared \| pack-data]` | the data is on this host: a repo checkout (that repo), the fleet's shared folder, files in the pack's data folder |
| `capabilities[].capacity` | `{parallel: 1..64}` | how many parts with it this harness takes at once: shown to the planner, and (3.2.1.0 R3) held by the hub, the next part `waiting` until one ends |
| `inspector` | `[{label, source}]` | a mission inspector line: a markdown or JSON file of the pack, shown with a part that needs the pack (Studio's Mission plan, the part's agent); 3.2.1.0 R3: the catalog carries the file's first 8 KB as `text` (paths cut), so a hub's Studio shows it for a member |
| `mission.metadata` | `{key: value}` | what a mission started with this pack's lineup carries (`metadata: {pack, lineup, ...}`, in MISSION.md and the Mission panel's head) |

A capability is **available** when every `requires` holds on this host;
`why` names what holds (`tools: or:anthropic/claude-sonnet-4.6; bash
granted`) or what is missing (`no GPU here`, `bash not granted (halo pack
enable doc-review --grant bash)`). Only the packs that run here are listed;
a disabled pack adds nothing. The catalog is gathered afresh on every pack
change (`halo pack enable | disable | update | remove`, and Studio's
`pack_changed` for a change made in another terminal).

**What an advertisement never carries.** The catalog leaves this machine, so
a value under `contributes.fleet` that looks like a secret (a token shape the
privacy scan knows, a Bearer value) or an environment reference (`$VAR`,
`${VAR}`, `%VAR%`) is a manifest problem, and so is a path in a
`description`: one line each naming the key and its line, and the pack does
not install or run:

```
pack.yaml line 12: contributes.fleet.capabilities[0].description: a token-shaped value; an advertisement leaves this machine, so it never holds a secret or an environment value
pack.yaml line 14: contributes.fleet.capabilities[0].requires.tools[0]: an environment reference ($HOME); an advertisement leaves this machine, so it never holds a secret or an environment value
```

Any other path (a tool given by its full path, a metadata value) is cut to
its last component by the catalog's scrub before it is cached or announced,
like every string in the catalog. A capability name the top-level
`capabilities:` does not list, a `requires` key outside the table above (with
the closest one), a grant the pack does not request, an unknown locality, a
capacity outside 1..64, an inspector source outside the pack or of another
type, and a metadata value that is a mapping are one line each too.

**The worker's own check.** A part's `needs` travel with it (`run_task`).
Before it runs (and on a member before its owner is asked), the worker reads
its own packs again: a need that is a pack capability runs only while that
pack runs here with the grants the capability requires, else the part is
refused with one line, which becomes the part's result:

```
this harness does not run pack doc-review with bash
```

It is the same explicit grant rule the harness applies to its own sessions:
a part gains nothing because another machine's catalog said it could run.

The doc-review reference pack's (`halo_harness/templates/packs/doc-review/pack.yaml`):

```yaml
capabilities: [docs.review]
permissions: ["mcp:lint", hooks, bash]
contributes:
  fleet:
    capabilities:
      - name: docs.review
        description: Reviews a repo's documents for dead links, heading order and style
        requires:
          models: [tools]
          grants: [bash]
        capacity: {parallel: 2}
    inspector:
      - {label: Review checklist, source: fleet/checklist.md}
    mission:
      metadata: {review: docs, style: short}
```

and its catalog entry on a harness that granted bash and has a model that
calls tools (`packs` section, as the hub receives it):

```json
{"id": "doc-review", "name": "Documentation review", "version": "1.0.0", "scope": "user",
 "capabilities": [{"name": "docs.review", "description": "Reviews a repo's documents for dead links, heading order and style",
                   "available": true, "why": "tools: or:anthropic/claude-sonnet-4.6; bash granted",
                   "checks": [{"key": "models", "ok": true, "line": "tools: or:anthropic/claude-sonnet-4.6"},
                              {"key": "grants", "ok": true, "line": "bash granted"}],
                   "requires": {"models": ["tools"], "grants": ["bash"]}, "capacity": {"parallel": 2}}],
 "inspector": [{"label": "Review checklist", "source": "fleet/checklist.md"}],
 "metadata": {"review": "docs", "style": "short"}}
```

`tests/fixtures/packs/fleet-needs-gpu/` is one not available on a host
without a GPU (`why: no GPU here`); `fleet-secret/` and `fleet-unknown-name/`
are the failure fixtures.

## Workflow contracts

Status: **stable** (3.2.0.0 R5; [WORKFLOWS.md](WORKFLOWS.md) is the guide). A
workflow is `<pack>/workflows/<name>.yaml`, its name in
`contributes.workflows`. Its shape is `halo_harness/schemas/workflow_yaml.py`
(the JSON twin `halo_harness/packs/schema/workflow.schema.json`), its meaning
`halo_harness/packs/workflow_rules.py` and `workflow_stages.py`: a bad file
is one manifest problem naming the key and its line, so the pack does not
install or run. The file COMPILES to an Orchestra goal, its hand-offs and a
pinned plan (`halo_harness/workflows/compile.py`); the Orchestra pipeline
runs it, there is no second engine.

| Key | Shape | What it becomes |
|---|---|---|
| `name`, `description` | the file's stem; a sentence | the goal's WHAT YOU WANT |
| `prerequisites` | `{tools, grants, capabilities, files}` | checked before the run: a CLI on PATH, a grant you gave the pack, a capability available here (its `contributes.fleet` requires), a file in the repo |
| `inputs` | `{<name>: {type: text \| path \| json \| artifact:<schema>, required, default, description}}` | `--input k=v`; a path is relative to the repo and there; an artifact input is a JSON file checked against the pack's schema |
| `outputs` | `{<name>: {type: artifact:<schema> \| files \| summary, from: <stage>, description}}` | the run's typed results, checked at the gate, copied to `<run>/artifacts/<name>/`, in the report |
| `stages` | `[<stage>]`, in order | one job per stage (one per file for `for_each`), `job-1..N` |
| `done_when`, `stop_when` | sentences | the goal's DONE WHEN and STOP WHEN |
| `budget_usd` | dollars | the goal's `budget_usd` (the forecast's; the supervisor's stop under `--as goal`) |
| `checkpoint` | `true` / `false` | the run resumes at its first unfinished step (`halo orchestra run <run>`, the supervisor's resume) |

A `<stage>`:

| Key | Shape | What it becomes |
|---|---|---|
| `id`, `title`, `brief` | a name; a line; what its worker does (`{item}`, `{<input>}` are filled in) | the job's title and the brief in its worker's prompt (the lead may refine the brief, never the stage set) |
| `role` | a bio of the pack (name, `<id>--<name>` or kind) or a bio Halo ships | the job's `bio` (the worker runs `--agent` it) |
| `needs` | capabilities the pack declares | checked available here before the run |
| `after` | stage ids | the job's `after` (sequential); none: it runs at once, in parallel |
| `for_each` | a path input, or `{input, match}` | one job per file under it (`match` a glob, default `*`) |
| `when` | `{input: <name>}` or `{output: <stage>.<give>}`, `key`, and one of `exists`, `equals`, `not-empty` | an input's: resolved at compile time; an upstream output's: when the lane starts. False: the stage is skipped with a `state` line |
| `gives` | `[{name, kind: files \| summary \| artifact, paths}]` | the job's `handoff.gives` (an artifact is saved as `<name>.json`; a `files` give's paths are its claims) |
| `takes` | `[{from: <stage>, take: all \| summary \| <a give>}]` | the job's `handoff.needs`, one per job of that stage |
| `retries` | 0 or more | the stage's own return cap at the gate (the goal's `return_cap` is the largest) |
| `timeout_s` | seconds | the worker's time limit |
| `budget_usd` | dollars | checked before each pass of the stage's worker: at it the run stops (`budget: stage <id> spent ...`) |
| `gate` | `human` or `auto` | `human`: the goal is `plan: review`, the run waits for the plan's approval before any stage (the plan review before the run starts; a hold before one stage is not a thing yet) |
| `verify` | `{test: <command>, evidence: [<output, give or repo path>]}` | the test joins the goal's `test` (and runs alone to find the stage that fails); the evidence joins the gate's record check |
| `after_event` | `<pack>:<kind>` | the lane waits for that pack event before its worker starts |

What runs each bound, and what is only recorded (`report.json` `workflow.bounds`,
"not enforced yet" in the CLI report): every stage bound above is held, and
(3.2.1.0 R2) so is the workflow's `budget_usd`, the goal's: before each pass
of any stage's worker the run's spend is checked against it and at it the run
stops, in a plain Orchestra run as under `--as goal`. The supervisor's
replanner never changes a workflow run's stage set (it is not paused for a
replan), and the gate's verdict carries each `verify.evidence` item as a line
under its lane (`evidence <item>: <bytes> bytes, sha256 <12>` or `missing`),
which the conflict judge reads too.

```
workflows/flow.yaml line 6: stages.audit.role 'auditor' is not a bio of the pack (by name or kind) nor a bio Halo ships
```

The commands: `halo workflow list | show | check | run` ([COMMANDS-workflows.md](COMMANDS-workflows.md)),
`halo orchestra new --workflow <pack>/<name> --input k=v`, and (with the supervisor) `halo workflow run ... --as goal`.

## Events and artifacts

Status: **stable** (3.2.0.0 R5; `publish_event` since R1). Three typed kinds
of data a pack has: its events, its artifacts and its memory.

**Events.** A frame is `{"session_id": "pack:<id>", "event": "pack_event",
"pack": "<id>", "data": {"pack", "kind", "data", "problems"?}, "ts"}`; a
`contributes.events` entry is a kind or `{kind, schema, description}`, and a
kind's schema is `events/<kind>.json` when the pack ships one.
`publish_event` checks a declared kind's data against it: a mismatch is
published all the same with `problems: [...]` (Studio shows them under the
line), never dropped; an undeclared kind goes out with Studio's generic
line. A pack that does not run here (disabled, not installed) is refused
with one line (ValueError) and nothing is kept. Every accepted event is
appended to `~/.halo/packs/.data/<id>/events.jsonl` (`packs/events_log.py`),
which the SUBSCRIPTIONS read from any process:

- a bio's trigger `{on: event, name: <pack>:<kind>}` (short: `{event: <pack>:<kind>}`) starts it once when the
  pack publishes that kind (agents_schedule.py, the bio trigger mechanism; packs/event_triggers.py);
- a workflow stage's `after_event: <pack>:<kind>` holds its lane until the event comes.

Studio draws a kind's line from `contributes.studio.events` and, when the
kind's schema has an `x-halo-view`, its data under the line.

**Artifacts.** An artifact schema is `artifacts/<schema>.json`, listed under
`contributes.artifacts` (by name or path). A schema is JSON schema's
`type`, `properties`, `additionalProperties`, `items`, `enum` and
`required`, plus `x-halo-view`:

| `x-halo-view` | Studio draws |
|---|---|
| `table` | the document's first list of objects as rows (the columns: its items' properties), its other keys above |
| `markdown` | the document's `markdown`, `text` or first text value, through Studio's markdown |
| `keyvalue` | each key and its value (the default) |

A workflow output of type `artifact:<schema>` is saved by its stage as
`lanes/<n>/artifacts/<name>.json` (files beside it in `lanes/<n>/artifacts/<name>/`),
checked against the schema at the gate (a mismatch is a return with one line
per problem: `report: findings[0].line is a whole number, got the string 'four'`),
copied to `<run>/artifacts/<name>/` when the run finishes, and listed in
report.json's `artifacts` (`{name, type, schema, view, stage, lane, state, path, ok, problems}`).
Its viewer is a Studio panel of kind `artifact` (`{kind: artifact, schema,
source: latest}`, [Studio contributions](#studio-contributions)) and the
Report panel's Artifacts tab of Orchestra's run view (`GET /api/orchestra/<run>/artifact/<name>`).

**Memory with provenance.** A pack's namespace folder (`context.memory.namespace`,
`~/.halo/packs/.data/<id>/memory/<ns>/`, since R2) holds each note `<name>.md`
with `<name>._meta.json`:

```json
{"source": "workflow run", "run": "20261023-101500-a1b2", "stage": "judge", "written": "2026-10-23T10:16:02Z",
 "retention": "keep", "shared": ["release-notes"]}
```

`ext.memory.write(namespace, text, provenance)` writes both (a stage's worker
gets `source`, `run` and `stage` from the environment); `source` is workflow
run | bio | user, `retention` keep | `days:<n>` | run, `shared` the packs that
may read it. Recall honours it: a namespace reads its own entries plus the
ones another pack shares with its pack; `retention: run` entries go when
their run ends, `days:<n>` ones with `halo recall prune`; `halo recall
--namespace <pack>/<ns> --provenance` lists them with their meta.

## Compatibility and migration

Status: **stable** (3.2.0.0 R7). The policy, as `halo_harness/ext/compat.py`
and `halo_harness/packs/resolve.py` apply it:

- **The API version is `MAJOR.MINOR`** (`API_VERSION`, `ext.api_version()`).
  A minor version only adds names: every name in `__all__` keeps its meaning
  for every later minor of its major. A major version may remove a name, and
  only one `ext.deprecations()` has listed, with the version it goes away in,
  for at least one minor version before it.
- **A pack states `halo_api: {min, max}`.** `min` is required (the API it was
  written for); `max` is inclusive at its own precision (`max: "1.9"` takes
  1.9.4). Without `max` a pack runs on its `min`'s major only: `{min: "1.0"}`
  runs on every 1.x and not on 2.0. `ext.compatible(range)` answers it.
  `halo: {min, max}` is matched against Halo's own version the same way,
  without the major rule.
- **A Halo outside a range does not run the pack, and says so in one line**:
  at install (nothing is written), at load (the pack contributes nothing), in
  `halo pack doctor` and in the Pack Manager's Details, in these words:

```
pack doc-review needs extension API 1.2 to 1.9; this Halo has 1.0
pack x needs Halo >= 3.3; this is 3.2.0.0
```

  A range with no `max` reads `1.0 or a later 1.x`.
- **A name announced for removal** that a pack's Python uses is a `halo pack
  doctor` row (and a health line in the Pack Manager) naming the file, the
  line and the version it goes away in, for example `doc-review:
  mcp/lint_server.py line 15 uses ext.get_config, deprecated since API 1.3; it
  goes away in API 2.0 (use ext.settings)`. Nothing is deprecated in 1.0.
- **A pack's own breaking change** is a `migrations` entry, `{from, to, note,
  settings?}`: `halo pack update` prints every entry between the installed
  version and the new one before it replaces anything, and applies the
  `settings` renames ([Updating a pack](#updating-a-pack)).
- **A renamed pack is a new pack.** A new id installs beside the old one and
  nothing carries over: the record, the grants, `packs.settings.<id>` and the
  journal are per id. `halo pack remove <old id>` takes the old one away.

### Changes in 1.x

None yet: 1.0 is the first version. Each minor version lists here the names
it adds (the name, what it does, the version) and the names it deprecates
(the name, the version it goes away in, what to use instead), one line each.

### Updating a pack

1. `halo pack update <id> --dry-run` prints the migration notes between the
   installed version and its source's (`<id> <from> -> <to>: <note>`, oldest
   first), what the update would do (the files that change, one line each,
   the settings it renames, your files it keeps) and changes nothing. The
   Pack Manager's Update shows the same lines in its confirm before it runs.
2. `halo pack update <id>` makes the checks install makes on the source (the
   manifest, both ranges, the same id): a new version that fails one is
   refused with its lines and `<id> <version> stays as it is`. In a terminal
   (3.2.1.0 R4) it then prints step 1's lines and asks `Apply? [y/N]`; `n`,
   Enter or the end of input stop here with `<id> <version> stays as it is`
   (exit 1). `--yes`, `--json` and a run with no terminal do not ask, and
   print the notes first. Then the new version is staged in `<packs>/.staging-<hex>/<id>/`
   (the new files, and every file of yours in the pack's folder carried over)
   and swapped in by two renames: `<id>/` becomes `<id>.previous/` (replacing
   the one kept before) and the staged folder becomes `<id>/`. A copy or
   rename error leaves the old version where it was, in one line:
   `update of <id> stopped: <error>; <version> stays as it was (nothing was replaced)`.
3. The journal records the new version's files as the pack's; the `settings`
   renames are made in `packs.settings.<id>` and journaled (`op: migrate`);
   state.json gets the new version and `previous: {version, op_id,
   requested}`. A permission the new version requests that the old one did
   not and you have not granted is one line, and a doctor row until you grant
   it (`halo pack grant <id> <name>`).

The entry shape, with a rename:

```yaml
migrations:
  - {from: 1.1.0, to: 1.3.0, note: settings key `lint.level` is now `lint.strictness`, settings: {lint.level: lint.strictness}}
```

`settings` maps an old key to a new one under `packs.settings.<id>` (a dotted
key reaches into a mapping); a new key you have set already wins and the old
one stays, said in one line. It is the only change Halo makes itself; every
other change is the note's to say.

### Rolling back

1. `halo pack rollback <id>` (the Pack Manager's "Roll back to <version>"):
   a file of yours changed or added in the pack's folder since the update is
   copied into `<id>.previous/` first, so it stays; `<id>/` moves aside,
   `<id>.previous/` becomes `<id>/` (two renames, the first undone when the
   second fails) and the version rolled back from is deleted (`halo pack
   update <id>` installs it again).
2. The journal's ownership goes back to what it was before that update, the
   settings it renamed move back (from the journal's `migrate` rows), and the
   record gets the old version and keeps its grants and its enabled state.
3. One version back only, and that is the rule: `<id>.previous` is the one
   version kept, the next update replaces it, and there is no version
   history on disk (3.2.1.0 R4). With none kept the answer is one line: `<id> has no earlier version to go back
   to: an update keeps the version it replaces as <id>.previous until the next update`.
4. `halo pack remove <id>` deletes `<id>.previous` too. `--keep-config`
   keeps it beside the record, and `halo pack rollback <id>` then installs
   that version again (disabled, with its grants); a fresh `halo pack
   install` removes a kept one.

## The reference example

Status: **stable** (3.2.0.0 R6). Halo ships one pack, **Documentation
Review**, at `halo_harness/templates/packs/doc-review/`: the reference a
third party copies, and the regression test of this whole page
(`tests/test_reference_pack.py` installs it in a fresh home, runs its
workflow, finds it in Studio, Roles and the fleet catalog, removes it and
finds nothing of it left; every packs test reads it too). What it shows:

| Part of the API | In the pack |
|---|---|
| The manifest | `pack.yaml`: `halo_api: {min: "1.0", max: "1.9"}`, `halo` (the Halo it ships in: `{min: "3.2"}` from the 3.2.0.0 release), settings schema and defaults, permissions, one migration note |
| Agents and teams | `agents/reviewer.yaml` (by capability, a memory namespace, a need), `agents/writer.yaml` (extends it, a family preference), `teams/review.yaml` (two tiers, acceptance, its workflow) |
| Skills, commands, hooks and MCP | `skills/check-links/`, `commands/review.md`, `agents/helper.md`, `hooks/` (a PostToolUse hook publishing review.done), `.mcp.json` + `mcp/lint_server.py` (a stdio MCP server: check_links, check_headings); both started with `${halo_python}`, Halo's own Python (3.2.0.0 R7) |
| Studio contributions | a section (markdown, table, links, the artifact panel, Settings), a Session panel, a palette line, event lines, an attention row kind |
| Fleet capabilities | `docs.review` (a model with tools, the bash grant, two at once), an inspector line, mission metadata |
| Workflow contracts | `workflows/review.yaml`: read each Markdown file, judge (`gate: human`), write the report |
| Events and artifacts | `artifacts/review-report.json` (`x-halo-view: table`), `events/review.done.json` |

Its `README.md` is the third-party guide: every file in one line, the API
version, how to install from a folder or a git url (or by id from a
`packs.sources` folder: `halo pack sources add`), how to check a pack with
`halo pack inspect` and `halo pack doctor`. `halo pack install doc-review`
finds it: the shipped folder is the last entry of the sources search, after
`packs.sources`. The failure fixtures stay under `tests/fixtures/packs/`
(`wf-cycle/`, `wf-unknown-role/`, `wf-no-giver/`, `wf-input-type/`, the
studio and fleet ones) with `tests/fixtures/workflows/report-bad.json`, an
artifact off its schema. 3.2.0.0 R7 adds one per lifecycle failure
(`tests/test_packs_failures.py`): `bad-yaml/`, `no-id/`, `bad-id/`,
`api-too-new/`, `api-too-old/`, `halo-too-new/`, `needs-base/` (a missing
dependency) and `cycle-a/` with `cycle-b/`; docs/PACKS.md "When a pack cannot
run" lists the line each one gets.
