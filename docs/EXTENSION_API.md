# The extension API

Read this when you write a pack, or change what Halo promises a pack: the manifest, the lifecycle, what a pack may import and what each part's status is.

Halo 3.2.0.0 (written in R1, final in R7: every part was `stable`); 3.3.10.0 R1 added
[Policy hooks](#policy-hooks) as the first `draft` part, and R2 made it `stable` (a session enforces each verdict).
A pack is a folder Halo installs, enables and removes (see
[PACKS.md](PACKS.md) for using one); this page is the contract a pack is
written against. The extension API version is `API_VERSION = "1.1"` (1.0 until 3.3.10.0; a 1.0 pack keeps
everything, [Changes in 1.x](#changes-in-1x); 3.3.11.0 added [Setup blocks](#setup-blocks) to it)
(`halo_harness.ext.API_VERSION`, also exported as `HALO_API_VERSION`). The
machine-readable manifest schema is
`halo_harness/packs/schema/pack.schema.json`; the reference pack is
`halo_harness/templates/packs/doc-review/` (3.2.0.0 R6, shipped with Halo).

**Start here** (3.3.12.0 R4): to write a pack, start from the pack kit, not a blank folder. `halo pack new <id> --kinds
...` writes a pack that installs, passes `halo pack test` and that `halo pack doctor` finds nothing wrong with; `halo
pack test .` checks every part against fakes; `halo pack install . --link` makes the installed pack your folder. The
guide, for a person and for a Halo session (`halo --team pack-author`), is [PACK-AUTHORING.md](PACK-AUTHORING.md).

## Status of each part

| Part | Status | What the status means here |
|---|---|---|
| [The stable surface](#the-stable-surface-halo_harnessext) | stable | names and meanings hold for every 1.x |
| [The manifest](#the-manifest-packyaml) | stable | format 1, read by API 1.x |
| [The lifecycle](#the-lifecycle) | stable | `halo pack` verbs, state.json, the journal |
| [Agents and teams](#agents-and-teams) | stable | bios and lineups under `<id>--<name>`; R2: capabilities, needs, namespace, workflows, acceptance |
| [Skills, commands, hooks and MCP](#skills-commands-hooks-and-mcp) | stable | the Claude-plugin layout, namespaced |
| [Permissions and grants](#permissions-and-grants) | stable | requested in pack.yaml, granted by you |
| [Studio contributions](#studio-contributions) | stable | `contributes.studio` (3.2.0.0 R3): sections, panels, palette, the settings form, event lines, attention rows; a bundle only with `studio-script` (3.3.10.0 R3: its `api` publishes, listens, routes and asks for attention) |
| [Fleet capabilities](#fleet-capabilities) | stable | `contributes.fleet` (3.2.0.0 R4): worker capabilities in the catalog, available or not and why; mission needs, the worker's own check, inspector lines, mission metadata |
| [Workflow contracts](#workflow-contracts) | stable | `workflows/<name>.yaml` (3.2.0.0 R5): compiled to an Orchestra goal, its hand-offs and a pinned plan; `halo workflow` |
| [Events and artifacts](#events-and-artifacts) | stable | typed events (3.2.0.0 R5: schemas, the events log, subscriptions), typed artifacts with viewers, memory with provenance |
| [Compatibility and migration](#compatibility-and-migration) | stable | the version policy (`ext.compatible`, `ext.deprecations`), `migrations` shown before an update and applied, `halo pack rollback` (3.2.0.0 R7) |
| [Bundles](#bundles) | stable | `bundle:` (3.3.7.0 R5): a capability bundle, a pack with a resource claim -- needs, reservation, routing, latency budget; the verdict before anything downloads |
| [Setup blocks](#setup-blocks) | stable | `contributes.setup` (3.3.11.0 R3, API 1.1): a pack's own pages in Studio's Setup -- a form over its `config.schema` keys, a check through Setup's checks job, a note -- shown while the pack is enabled, their state in `setup.json`; `halo pack enable` and `halo doctor` say what waits, `halo setup <pack>` opens it |
| [Requirements](#requirements) | stable | `requires:` tool entries (3.3.12.0 R4, API 1.1): the open-source tools a pack wraps, each with its install line per OS, license and why; Halo never installs one -- the doctor names a missing one, `halo pack test` skips what it gates |
| [Policy hooks](#policy-hooks) | stable | `contributes.policy` and `contributes.modes` (3.3.10.0, API 1.1): a pack's runtime mode (mode.json), a policy hook whose verdict decides a tool call before it runs (deny > ask > allow) and, with `after: true`, its result after (pass, redact, drop); every verdict in the audit; the dry run |
| [The reference example](#the-reference-example) | stable | the Documentation Review pack Halo ships (3.2.0.0 R6): every part of the API in one pack a third party can copy |

`stable`: a 1.x Halo keeps it. `removed <version>`: gone in that version,
announced a minor version before it ([Changes in 1.x](#changes-in-1x)).
Since 3.2.0.0 every part is `stable` and none is removed; a later part may
start as `draft` (usable, may change in a minor API version with a migration
note) or `planned` (the shape proposed, nothing reads it yet). Policy hooks
was the first `draft` part (3.3.10.0 R1) and is `stable` from 3.3.10.0 R2; no part is `draft` now.

## The stable surface (`halo_harness.ext`)

Status: **stable**. A pack's code imports `halo_harness.ext` and nothing
else of Halo (`tests/test_ext_api.py` walks every fixture and shipped pack's Python to
check it). The modules under `halo_harness/ext/` are the implementation; the
names in `__all__` are the contract.

- `API_VERSION`, `HALO_API_VERSION`: `"1.1"` (3.3.10.0 R1; `"1.0"` before).
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
- `set_mode(pack_id, mode_id, on=True, note="")` / `current_mode(pack_id)`: API 1.1 (3.3.10.0 R1, part of the
  stable [Policy hooks](#policy-hooks) since R2): turn one of the pack's `contributes.modes` on or off in its `mode.json`
  (`[]` when written, else one line; on arms the policies that name it) and read the mode that is on (None for none).
- `testing`: API 1.1 (3.3.12.0 R4, stable): a pack's tests. `testing.run(folder, kinds=None, timeout_s=10)` makes every
  check `halo pack test` makes in a scratch home of its own (never a model call, never the network) and answers a
  `Report` (`add(file, what, ok, fix)` for the pack's own checks, `ok`, `exit_code`, `text()`, `as_json()`);
  `testing.manifest(folder)` reads pack.yaml; `testing.ask_policy(folder, policy, tool, input)` asks one of the
  pack's policies about one call. A pack's `tests/pack_test.py` (written by `halo pack new`) is the example.
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
requires: [{pack: base-docs, version: "1.2"}]   # version: a minimum, or {min, max}; 3.3.12.0 R4: a tool too, below
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
  policy: [{id: fence, run: [...], when: {tools: [...], modes: [...]}, impact, on_error, redact, after}]   # 3.3.10.0, Policy hooks below
  modes: [{id: fenced, label: Fenced, theme: midnight}]   # 3.3.10.0: the pack's runtime modes
  setup: [{id: prefs, title: Review preferences, kind: form, fields: [style], after: model}]   # 3.3.11.0, Setup blocks below
config:
  schema: {properties: {style: {type: string, enum: [short, long]}}, additionalProperties: false}
  defaults: {style: short}
permissions: ["mcp:lint", hooks]    # mcp:<server>, hooks, bash, network, home-write, studio-script
migrations:
  - {from: 0.9.0, to: 1.0.0, note: the reviewer bio is now doc-review--reviewer}
  # 3.2.0.0 R7: settings renames packs.settings.<id> keys as the update runs
  # - {from: 1.1.0, to: 1.3.0, note: settings key `lint.level` is now `lint.strictness`, settings: {lint.level: lint.strictness}}
bundle: {needs: {...}, reservation: {...}, routing: {...}, latency_budget_ms: 1500}   # 3.3.7.0 R5, Bundles below
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
| `bundle` | `source`: an ES module (`.js`, `.mjs`) in the pack's folder | `mount(el, api)`, loaded only when `studio-script` is granted; until then one line naming `halo pack enable <id> --grant studio-script`. 3.3.10.0 R3: `api` acts too (publish, on, getData, mode, attention, route: [the bundle panel's `api`](#the-bundle-panels-api) below) |
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

`tests/fixtures/packs/studio-bundle/` is the bundle example: one section with a
`bundle` panel (`studio/hello.js`: "hello from <id>", and since 3.3.10.0 R3 one
button per `api` call, each with its result line) and an `events` panel, one
event kind (`hello.said`), one attention row kind (`hello.ask`), one mode
(`loud`), `permissions: [studio-script]`.

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
- 3.3.10.0 R3, behind a bundle panel's `api` (`halo_harness/studio/packs_studio_bundle_api.py`; each 403 naming
  the grant until `studio-script` is granted): `POST /api/pack/<id>/publish {kind, data}`, `POST
  /api/pack/<id>/attention {row, kind, what, detail}` and `GET /api/pack/<id>/mode`; the table below.

**A bundle** is a module that exports `mount(el, api)`: `el` is the panel's
body, `api` is the bundle panel's `api` below; what `mount` returns, when it
is a function, runs when the panel goes away (and every `on` the panel made
stops then). It runs in the page like the shell's own script, so it is the
one Studio contribution that takes your explicit grant (`halo pack enable
<id> --grant studio-script`), as `bash` and `hooks` do.

### The bundle panel's `api`

3.3.10.0 R3 (`halo_harness/studio/ui/src/routes/packs/bundleApi.ts`; the routes:
`halo_harness/studio/packs_studio_bundle_api.py`). Every call is the pack's own (its files, its data folder,
its declared event kinds and attention rows, its mode) and rides the `studio-script` grant: the module loads only
once it is granted, and each route behind a call answers 403 naming `halo pack enable <id> --grant studio-script`
without it. A call the server refuses rejects its promise with an `Error` whose message is the server's line.

| Call | Takes | Returns | Through |
|---|---|---|---|
| `pack`, `panel` | | the pack's id, the panel's id | |
| `get(path)` | a file of the pack (markdown, JSON) | `Promise<string>` | `GET pack/<id>/file/<path>` |
| `config()` | | `Promise<{fields, values, problems, ...}>` | `GET pack/<id>/config` |
| `publish(kind, data)` | one of the pack's `contributes.events` kinds, its data | `Promise<{ok, kind, published, problems?}>`: `problems` when the data does not fit the kind's schema (published all the same) | `POST pack/<id>/publish`: `ext.events.publish_event`'s own check and its events log; a kind the pack does not declare, or a name that is not one, is 422 with the line; past the rate, 429 |
| `on(kind, cb)` | one of the pack's kinds, a callback | `off()`: the function that stops it | the pack's own `pack_event` frames as they arrive on the live feed; `cb({kind, data, ts, problems?})` |
| `getData(path)` | a file of the pack's data folder (markdown, JSON) | `Promise<string>`, read-only | `GET pack/<id>/data/<path>` (any write method is 405) |
| `mode()` | | `Promise<{pack, mode, label, since, by, armed, modes}>` | `GET pack/<id>/mode`: the pack's `mode.json` ([Policy hooks](#policy-hooks)) |
| `attention({row, kind, what, detail?})` | a row name, one of the pack's `attention` kinds, its line | `Promise<{ok, row, kind, file}>` | `POST pack/<id>/attention`: writes `attention/<row>.json` in the pack's data folder, the row the attention queue shows at once (the pack named, its keys; answered through the answers contract above); the same rate |
| `route(section, panel?)` | a core section, or one of the pack's own sections (its id, or qualified), and maybe a panel | `true`, or `false` when it names neither | the shell's own section switch and panel focus, as a `links` route |

**The rate.** `publish` and `attention` share one rate per pack: **20 writes in any 10 seconds** (a sliding window,
per Studio server); the 21st is 429 `{error, rate: {limit: 20, window_s: 10}, retry_after}` and nothing is
written. A panel publishes on a click or a change of its own state, a few a second at most; the rate keeps a loop in
a bundle from filling the feed (Studio keeps the last 300 frames) or the pack's events log.

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

## Bundles

Status: **stable** (3.3.7.0 R5). A **capability bundle** -- not the `bundle` kind of a Studio panel above, which is a
script module -- is a pack with one more block, `bundle:`, a resource claim on the local models
([MODELS-bundles.md](MODELS-bundles.md)). It is read by `halo_harness.packs.manifest_bundle` (shape:
`schemas/pack_yaml.bundle`; the JSON twin `packs/schema/bundle.schema.json`, also `$defs.bundle` of
`pack.schema.json`); every bad value is one line naming the key.

```yaml
bundle:
  needs:                          # each role the bundle needs, the models that can fill it, best first
    chat: {any_of: [lfm3:1.7b, qwen3-coder:30b-gpu], window: 8192}
    stt:  {any_of: [faster-whisper:large-v3-turbo, faster-whisper:small.en], device: cpu-or-gpu}
    tts:  {any_of: [kokoro-82m], device: cpu}
  reservation: {model: lfm3:1.7b, vram_gb: 1.2, keep_alive: -1, priority: high}
  routing: {task_work: coder-or-cloud, never_evict: reserved}
  latency_budget_ms: 1500
```

| Key | Takes | Meaning |
|---|---|---|
| `needs.<role>.any_of` | a list of model names (required) | the models that can fill the role, best first; an Ollama tag, or a speech model (`faster-whisper:*`, `kokoro-*`, `parakeet-*`, `qwen3-tts:*`: runtime `voice`) |
| `needs.<role>.window` | tokens, 512 or more | the window it runs at (8,192 when left out) |
| `needs.<role>.device` | `gpu` (default), `cpu`, `cpu-or-gpu` | where it runs; the CPU costs no VRAM; `cpu-or-gpu` speech runs on the CPU |
| `needs.<role>.vision`, `.tools` | true / false | the model must see / call tools (its battery profile, else its catalog row) |
| `needs.<role>.runtime` | `ollama`, `voice` | read from the name when left out |
| `reservation.model` | a model a need lists, or a needs role | what the bundle holds while it is on; a role means whichever of its `any_of` the verdict picks |
| `reservation.vram_gb` | GB | its memory; the weights plus the KV at its window when left out |
| `reservation.keep_alive` | `-1` (default) or a duration | written on the reserved model's profile while the bundle is on |
| `reservation.priority` | `high`, `normal` (default), `low` | the claim's priority, said on the Hosts card |
| `reservation.window` | tokens | the window it is held at (the need's by default) |
| `routing.task_work` | `coder-or-cloud` (default), `coder`, `cloud`, `local` | where task work goes while it is on: `coder` makes the coder fitting beside the reservation part of the verdict |
| `routing.never_evict` | `reserved` (default), `none` | nothing Halo does evicts the reserved model |
| `routing.escalation` | `on` (default), `off` | `off`: no cloud rung for any session while the bundle is on (offline-only) |
| `latency_budget_ms` | ms | said beside the verdict's expected latency |
| `reservations` | a list of reservations | 3.3.8.0 R4: several claims, one per host; each takes the `reservation` keys plus `host` and `min_free_gb` |
| `reservations[].host` | a paired host's name, an `ollama.hosts` name, or `pool` | where that reservation is held (the default host when left out) |
| `reservations[].min_free_gb`, `min_free_gb` | GB, 0 or more | the GB that card keeps free for tasks beside the claim (the bundle's for every reservation) |
| `schedule.hours` | `HH:MM-HH:MM` | 3.3.8.0 R4: the hours the claims are held, the host's local clock (it may wrap midnight); outside them the bundle claims nothing |
| `priority` | `high`, `normal` (default), `low` | 3.3.8.0 R4: every reservation's default; when two claims collide the lower one is pre-empted and told in one line |

A bundle requests no permission: turning it on grants nothing. Halo ships ten (`halo_harness/templates/bundles/`);
`halo pack verdict | on | off <bundle>` and `halo pack list --bundles` are its verbs
([COMMANDS-packs.md](COMMANDS-packs.md#bundles)).

## Policy hooks

Status: **stable** (3.3.10.0 R1 the contract, R2 the enforcement; extension API 1.1). A pack declares a policy,
arms it through its runtime mode, and every session asks it about each matching tool call **before the call runs**:
its verdict decides the call, enforced by the harness, independently of the model, which cannot argue past it. A
policy that declares `after: true` is asked once more **after the call ran**, with the result. Every verdict is in
the audit. **With no pack armed, nothing changes**: `policy.armed()` is empty (a home with no packs folder costs two
`stat` calls), no process starts, and the loop makes exactly the calls it made before (pinned by a call-count test).
`halo pack policy test` runs a verdict without a session.

**The manifest block** (`halo_harness/packs/manifest_policy.py`; `$defs.policy` and `$defs.mode` of
`pack.schema.json`). A policy rides on the `hooks` permission: the pack requests it, you grant it.

```yaml
contributes:
  policy:
    - id: fence                     # a name, unique in the pack
      run: ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/policy/fence.py"]   # a command in the pack folder
      when: {tools: [Write, Edit], modes: [fenced]}
      impact: high                  # low | medium (default) | high: what the pack says its verdicts weigh; shown
      on_error: deny                # allow (default) | deny
      redact: [MY_SERVICE_TOKEN]    # environment variable names, never their values
      after: false                  # true: asked again after the call, with its result (the post-call verdict)
  modes:
    - {id: fenced, label: Fenced, theme: midnight}   # theme: accepted and ignored until 3.3.12.0
permissions: [hooks]
```

| Key | Takes | Meaning |
|---|---|---|
| `id` | a name (letters, digits, `-`, `_`; no `--`) | the policy, unique in the pack |
| `run` | a list (exec form, no shell), or one string split like a shell line | `${halo_python}` with a pack file after it, or a pack file itself; `${halo_python}` is Halo's own Python and `${CLAUDE_PLUGIN_ROOT}` the pack's folder, put in as `hooks/hooks.json`'s exec form does; a path outside the pack, or a file that is not there, is a manifest problem |
| `when.tools` | tool names, `mcp__<server>__<tool>`, `connector__<slug>`, or `*` | the calls the policy is asked about; left out, every tool. A call it does not name never reaches the process. A name is any tool Halo has when the manifest is read (the core tools, and every tool class loaded then, `manifest_policy.tool_names()`) |
| `when.modes` | ids of `contributes.modes` | the policy answers only while one of these modes is on; left out, whatever the mode |
| `impact` | `low`, `medium`, `high` | shown in `halo pack inspect` and `halo pack policy status`; no verdict reads it |
| `on_error` | `allow`, `deny` | the verdict when the answer is late, malformed or missing (`allow` when left out: the zero-change rule) |
| `redact` | environment variable names | each one's value is replaced by `[redacted:<NAME>]` in the tool input before the request leaves Halo |
| `after` | `true`, `false` | `true`: the policy is asked again after the call ran, with its result (the post-call verdict, below) |
| `modes[].id`, `label`, `theme` | a name; a line; a theme name | a runtime mode of the pack; the label is what a person reads; the theme is read from 3.3.12.0 |

Each bad value is one line naming the entry, and the pack does not install or run:

```
pack.yaml: contributes.policy[0].run: '/etc/fence.py' is outside the pack folder (a command in the pack: ${CLAUDE_PLUGIN_ROOT}/<path>)
pack.yaml: contributes.policy[0].when.tools: 'Wirte' is not a tool Halo has (closest: Write); a tool name, mcp__<server>__<tool> or *
pack.yaml: contributes.policy[0].when.modes: 'audit' is not one of contributes.modes (fenced)
```

**The mode file.** `~/.halo/packs/.data/<id>/mode.json`, in the pack's data folder beside its events log:

```json
{"mode": "fenced", "since": "2026-11-02T12:00:00Z", "by": "cli", "armed": ["fence"], "note": ""}
```

It is the one record of what a pack has on at run time (the lifecycle's enabled / disabled record is `state.json`;
this is not it), written only by `halo_harness/packs/mode_state.py`, privately and atomically. The doors are `halo
pack mode <pack> <mode> on | off`, `halo pack policy arm <pack> <policy>` / `disarm <pack> [<policy>]`, and from
the pack's own commands and hooks `ext.set_mode(pack_id, mode_id, on=True)` / `ext.current_mode(pack_id)`; never a
write by hand. Turning a mode on arms each policy whose `when.modes` names it (and turning another mode on in its
place disarms the old one's); turning it off disarms them; `arm` and `disarm` name one policy. A mode or a policy
the manifest does not declare is one line naming the entry, and nothing is written:

```
policy-fence declares no mode 'audit' (contributes.modes: fenced)
policy-fence declares no policy 'gate' (contributes.policy: fence)
```

Every change is the pack's typed event `mode` in its events log (`{change, mode, armed, by}`), which a bio's trigger
and a workflow's `after_event` can wait on like any pack event. There is no new watcher: Studio's files watcher
(3.2.2.0 R6) watches lineups, bios, config and layouts only, so the policy catalog stats `mode.json` at the moment
a verdict is needed, and a mode switched in another terminal counts at the next verdict.

A policy **answers** when the pack runs here (enabled for its folder, no problem), `hooks` is granted, `mode.json`
arms it, and its `when.modes` takes the mode that is on (`halo_harness.packs.policy.armed`).

**The protocol.** `run` starts once, as a long-lived process: when a session starts with the policy armed, when it
is armed in a process that runs sessions, or else the first time it is asked; it stops when it is disarmed or the
session ends -- a Windows spawn is 100-300 ms and a
session makes thousands of calls, so a verdict costs a round trip, not a spawn. It runs in the pack's folder with
the environment every hook gets (the provider keys Halo holds taken out, `CLAUDE_PLUGIN_ROOT`, `PYTHONPATH` for
`halo_harness.ext`, and `HALO_PACK_ID`, `HALO_POLICY_ID`), and speaks JSON lines: one request per line on its stdin,
one answer per line on its stdout, flushed.

```
request  {"id": "r7", "tool": "Write", "input": {"file_path": "/tmp/x", "content": "..."}, "cwd": "/work/repo",
          "session": "20261102-120000-ab12", "agent": "", "mode": "fenced", "permission_mode": "default",
          "config": {}, "policy": "fence"}
answer   {"id": "r7", "verdict": "deny", "reason": "outside the project", "rule": "outside-project", "scope": "session"}
```

| Field | Meaning |
|---|---|
| `id` | the request's; the answer carries it back |
| `tool`, `input` | the call: the tool's name and its input (after `redact`) |
| `cwd`, `session` | the session's folder and id (`dry-run` for `halo pack policy test`) |
| `agent` | the sub-agent's id, `worker:<lane>` for an Orchestra worker, `""` for the main agent: delegated calls are asked too |
| `policy` | the policy's id (each policy has a process of its own) |
| `mode`, `permission_mode` | the pack's mode now, and the session's permission mode |
| `config` | the pack's own settings (`packs.settings.<id>` over `config.defaults`) |
| `verdict` | `allow`, `deny` or `ask` -- `permissions.Decision`'s words |
| `reason`, `rule` | the pack's own line, and which of its rules fired; the line a person sees is this `reason` |
| `scope` | `session` (the default), `machine` or `fleet`: how far the verdict reaches (Federation R6 reuses the shape) |

The answer must come **within the budget**, `packs.policy.budget_ms` (2000 when unset). A late answer, a line that
is not a JSON object, a verdict or scope outside the words above, or the process ending (or not starting) is the
policy's `on_error`, always with a logged line and the reason saying what happened: `deny -- fence: on_error deny
(no answer within 2000 ms)`. A late answer that arrives afterwards is read and dropped (its id is an earlier
request's), so it never answers the next request; a process that ended is started again for the next one. A fence
pack says `on_error: deny`, which is fail-closed: while its process is slow or broken, every call it guards is
denied, so its author keeps the answer well inside the budget.

**What an armed hook sees.** An armed hook sees every matching tool input, a Write's content included. `when.tools`
is how a pack limits what it reads, and `redact: [env names]` takes declared secrets out of the input before it
leaves Halo. Every verdict and every error is a `policy` row in the pack's events log (`{policy, tool, verdict,
reason, rule, scope, ms, session, agent, error?}`); the tool input itself is never written there.

**Several packs.** With more than one policy armed, each is asked and **the winner** is the verdict that counts:
deny over ask over allow (after the call: drop over redact over pass; `policy.winner`). Every pack's verdict is
logged, the winning one named (`winner: true`, `of: <how many>`).

**The dry run.** `halo pack policy test <pack> <policy> <tool> '<json input>'` arms nothing: it starts the policy's
process for this one request, prints the verdict and its time, and stops it.

```
$ halo pack policy test policy-fence fence Write '{"file_path": "/tmp/x"}'
deny -- fence: outside the project (12 ms)
  rule: outside-project; scope: session
```

The first answer of a process includes the interpreter's start (about 40-50 ms for Python on Windows, less on
Linux); a long-lived process's later answers are a few milliseconds.

**The enforcement** (3.3.10.0 R2, `halo_harness/agent/policy_gate.py`). In the loop's `_resolve_tool_call`, the armed
policies are asked before `permission_engine.decide`, and asked again wherever the engine decides again: after a
PreToolUse or PermissionRequest hook rewrote the input (a rewrite never routes around a fence). The winner decides:

- **deny**: the call does not run. It is refused through the same refused-tool path as one of your own deny rules,
  and the line the model and you read is the pack's, the pack and the rule named:
  `policy: deny -- fence: outside the project (pack policy-fence, rule outside-project)`. The session's
  `permission_denials` entry carries `pack`, `policy` and `rule`.
- **ask**: the call goes to the approval flow with that line as its reason (`policy: ask -- fence: ... (pack ...,
  rule ...)`), so the card says which pack asks and why. A permission mode cycle while the card is up never answers
  it, a PreToolUse hook's allow never lifts it, and your own deny rule still wins over it; with no one to ask (print
  mode, a background sub-agent) it is refused like any ask there.
- **allow**: the engine decides as before: your rules, the mode, the hooks.

Sub-agent calls and Orchestra worker calls resolve through the same method (a worker is a session of its own, its
`agent` is `worker:<lane>`), so the model cannot step around a fence by delegating. The plan specials
(`EnterPlanMode`, `ExitPlanMode`) are gated only by a pack's deny, like your deny rules: their own bodies handle the
confirmation. A fleet mission records the armed policies of the harness that made it (`policies` in `mission.json`,
and each part's dispatch carries them); Federation R6 enforces them on the far side.

**The post-call verdict.** A policy that declares `after: true` is asked once more after a call it names has run,
on the same process, within the same budget, with the same `on_error` (allow reads as pass, deny as drop) and the
same logging (`halo_harness/packs/policy_after.py`):

```
request  {...the pre-call fields..., "after": true, "result": "<the tool's result as text>", "ms": 41}
answer   {"id": "r9", "verdict": "pass" | "redact" | "drop", "reason": "...", "rule": "...", "result": "..."}
```

`pass` keeps the result. `redact` replaces it with the answer's `result` (a string): the model and the transcript
see the redacted one, and the audit row keeps `sha256:<hex>` of the original and the rule. `drop` replaces it with
the pack's line (`policy after: drop -- <policy>: <reason> (pack ..., rule ...)`). With several, each policy sees
the result as the one before it left it, and a drop ends the round. `redact: [env names]` takes the named secrets
out of the result too before it leaves Halo.

**The audit.** Every verdict, before and after, is a `policy` row in the pack's events log (`{policy, tool, verdict,
reason, rule, scope, ms, session, agent, at: before | after, winner, of?, error?, sha256?}`; never the input) and
is on the call itself: the transcript's tool row and the `tool_use_ready` / `tool_result` events carry `policy:
{line, verdicts}` (no new event kind; a call no policy was asked about carries no such field), the TUI's tool line
and the Session feed's tool row draw the line (`policy: deny -- fence: outside the project`), and the Pack Manager's
row shows the armed policies and the last verdict. `halo pack policy log [<pack>] [--since 1h]` prints them, and
`halo pack policy status` shows each policy's process (a `policy_proc` row when it starts and stops) and its verdict
counts.

**When the pack catalog cannot be read** (3.3.10.0 R3). `policy.armed()` keeps the last list it read in the process.
When a later read fails (the packs folder or `state.json` unreadable), the gate uses that list, so an armed `on_error:
deny` fence still denies, and logs the failure once per call naming what answers (`policy: the armed policies could
not be read: <why>; the last ones read here answer: policy-fence/fence`). In a process that never read an armed
policy the list is empty and the failure changes nothing: the zero-change promise holds.

`tests/fixtures/packs/policy-fence/` is the example: the `fence` policy (`policy/fence.py`, plain Python, nothing of
Halo imported) denies a Write or Edit whose path is outside the project folder and allows the rest, `on_error:
deny`, armed by its one mode, `fenced`. The first real consumer is the **concord** pack Halo ships
(`halo_harness/templates/packs/concord/`, [PACKS.md](PACKS.md#the-concord-pack)): its `claimed-files` policy runs
`concord check <path>` and denies a Write or Edit to a file another Concord task claims, `on_error: allow`.

## Setup blocks

Status: **stable** (3.3.11.0 R3, API 1.1). A pack adds its own pages to Studio's Setup section
([STUDIO-setup.md](STUDIO-setup.md#a-packs-blocks)) by listing them under `contributes.setup`; Setup's own parts draw
each one, and nothing of the pack's runs to draw it. `halo_harness/packs/manifest_setup.py` checks the list at install,
one line per problem (an unknown kind, a field `config.schema` does not have, a `run` outside the pack or missing, a
check without its four lines, a missing `text` file, an `after` that is not a core step, a key of another kind), and
the install is refused.

```yaml
contributes:
  setup:
    - {id: prefs, title: Review preferences, kind: form, fields: [style, depth], after: model}
    - id: reach
      title: Reach the review service
      kind: check
      run: ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/setup/reach.py"]
      what: asks the pack's script whether the review service answers
      cost: free
      time: seconds
      writes: nothing
    - {id: about, title: Before you start, kind: note, text: setup/about.md}
```

| Key | What it is |
|---|---|
| `id` | lower-case letters, digits, `-` and `_`; the step's id is `pack:<pack id>:<id>` |
| `title` | the step's name in Setup's rail and Summary |
| `kind` | `form`, `check` or `note` |
| `after` | optional: a core step (`providers`, `local`, `model`, `permissions`, `theme`, `team`, `linux`, `check`) the block is drawn right behind, the pack's name on it; left out, the block follows the core steps under the pack's name, before the Summary |
| `help` | optional: the page's one line (the pack's `description` when left out) |
| `fields` | form: the `config.schema` keys it shows, in the schema's order (left out: every key); Save checks them against the schema and writes `packs.settings.<id>`, nothing else |
| `run` | check: a command in the pack folder with the substitutions hooks use (`${halo_python}`, `${CLAUDE_PLUGIN_ROOT}`), exec form; exit 0 is green, its output the row's lines |
| `what`, `cost`, `time`, `writes` | check, all four required: the line the row shows before it runs (an offered action says what it does first); the row is off until you tick it |
| `text` | note: a markdown file in the pack, drawn as the page |

**The state** is `~/.halo/packs/.data/<id>/setup.json` (`packs/setup_state.py`), `{"blocks": {<id>: {state, at,
by}}}`: a form is `done` once saved from Setup, a check once it ran green through the checks job, a note once
marked read, and any block may be `skipped`; a block not in the file is waiting. Each change is the pack's `setup`
event in its events log. **The doors**: the blocks show only while the pack is enabled; `halo pack enable <id>` (and
`halo pack on`) end with one line per block waiting, `setup: <id> -- <title> (halo setup <id>)`; `halo setup <id>`
opens Setup on the first block waiting (`?mode=setup&block=pack:<id>:<block>`, or the lines where no browser opens);
`halo doctor`, `halo pack doctor` and the Pack Manager list a pack setup still waiting as an `info` row
("setup-waiting", exit 0; the Manager's row says "setup waiting"). **Nothing private**: a block's answers carry the
pack's own manifest lines, its own settings for the form's keys and its own note file, never an environment value, a
key, the provider state or another pack's settings; the check runs with the environment a pack hook gets (Halo's
provider keys taken out, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PROJECT_DIR`, `HALO_PACK_ID`, `HALO_SETUP_BLOCK` put in). With
no pack contributing `setup`, Setup is as it was. `tests/fixtures/packs/setup-blocks/` is the example: one of each kind.

## Requirements

Status: **stable** (3.3.12.0 R4, API 1.1). A pack that wraps an open-source tool declares it in `requires:`, the list
that also names the packs it depends on: a pack is `{pack, version}`, a tool is an entry with a `kind`
(`halo_harness/packs/manifest_requires.py`; the JSON twin is `requires` in `pack.schema.json`).

```yaml
requires:
  - kind: command                  # command (a program on PATH) | python (a module) | npm (a package) | git (a repo)
    name: rg
    version: ">=13"                # optional: >=x, <=x, ==x or x (a minimum)
    install:                       # the line the owner runs, one for each OS
      windows: winget install BurntSushi.ripgrep.MSVC
      linux: sudo apt install ripgrep
      mac: brew install ripgrep
    url: https://github.com/BurntSushi/ripgrep
    license: MIT OR Unlicense
    why: searches the project's files for the pack's search command
    used_by: ["mcp:rg", hooks/rg_todos.py]   # optional: the parts of the pack it gates
```

**Halo never installs a requirement.** What it does with the entry:

| Where | What it says |
|---|---|
| `halo pack doctor` | one warns row per tool not found here, `missing-requirement`: `<id>: needs rg (command): rg is not on PATH; without it mcp:rg, hooks/rg_todos.py does not run -> install it: <the line for this OS>` |
| `halo pack test` | the parts `used_by` names are skipped with one line each (and so is any hook or MCP server whose program is not on PATH); the requirement itself is a skip line with the install line |
| the Pack Manager | the pack's row says "needs rg" (its health lines carry the doctor's row) |
| the README `halo pack new` writes | an "Install" section, one line per tool and OS |

A `command` is found on PATH and a `python` module by import; an `npm` package is looked for as a program of its name
and a `git` repo is not checked. Each bad value is one line naming the entry (a kind outside the four, a name, a
version that is not a range, an install line missing for an OS, the url, license or why left out), and the pack does
not install. How to choose and wrap a tool is [PACK-AUTHORING.md](PACK-AUTHORING.md#wrapping-an-open-source-tool).

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
pack doc-review needs extension API 1.2 to 1.9; this Halo has 1.1
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

Each minor version lists here the names it adds (the name, what it does, the
version) and the names it deprecates (the name, the version it goes away in,
what to use instead), one line each (`ext.compat.CHANGES` holds the same).

- **1.1** (Halo 3.3.10.0): adds `set_mode` and `current_mode` (a pack's runtime mode) and the manifest's
  `contributes.policy` and `contributes.modes` ([Policy hooks](#policy-hooks): draft in R1, stable from R2, which
  enforces each verdict and adds the post-call verdict, `after: true` -> pass | redact | drop), and (R3) the bundle
  panel's `api` calls `publish`, `on`, `getData`, `mode`, `attention` and `route`, and (Halo 3.3.11.0) the manifest's
  `contributes.setup` ([Setup blocks](#setup-blocks), stable), and (Halo 3.3.12.0 R4) `testing` (a pack's tests, what
  `halo pack test` runs) and the `requires:` tool entries ([Requirements](#requirements)), both stable; deprecates nothing. A 1.0 pack keeps everything: `{min: "1.0"}` and `{min: "1.0", max: "1.9"}` take 1.1, and a pack
  without `policy` and `modes` reads and runs exactly as before. (A pack that says `max: "1.0"` asked for 1.0 only
  and gets the one compatibility line.)
- **1.0** (Halo 3.2.0.0): the first version.

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

Status: **stable** (3.2.0.0 R6). Halo ships two packs: **Documentation
Review** and (3.3.10.0 R3) **Concord**, the second reference example, the one
that shows a policy hook and a mode on a real tool ([PACKS.md](PACKS.md#the-concord-pack)).
Documentation Review, at `halo_harness/templates/packs/doc-review/`, is the reference a
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
