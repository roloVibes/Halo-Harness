# The extension API

Read this when you write a pack, or change what Halo promises a pack: the manifest, the lifecycle, what a pack may import and what each part's status is.

Halo 3.2.0.0 (written in R1, final in R7: every part was `stable`); 3.3.10.0 R1 added
[Policy hooks](#policy-hooks) as the first `draft` part, and R2 made it `stable` (a session enforces each verdict).
A pack is a folder Halo installs, enables and removes (see [PACKS.md](PACKS.md) for using one); this page is the
contract a pack is written against. The extension API version is `API_VERSION = "1.5"` (1.0 until 3.3.10.0, 1.1 until 3.3.13.0, 1.2
until 3.4.0.0, 1.3 until 3.5.0.0, 1.4 until 3.6.0.0; a 1.0, 1.1 or 1.2 pack keeps everything, [Changes in 1.x](#changes-in-1x); 3.3.11.0 added [Setup
blocks](#setup-blocks) to 1.1, 3.3.12.0 [Themes](#themes); 3.3.13.0 made it 1.2 with [Services](#services) and
[Transports](#transports) (R3) and [a section's view](#a-sections-view), [`api.lib`](#apilib), [a pack's own
routes](#a-packs-own-routes) and [the host services](#the-host-services) (R2), the seams the signal and design packs are
built on; 3.4.0.0 made it 1.3 with the four `draft` contributions a pack's [CLI verbs, slash commands, doctor rows and
settings rows](#cli-verbs-slash-commands-doctor-rows-and-settings-rows) and [core access](#core-access), the seams the
first-run and coach packs are built on; 3.5.0.0 made it 1.4: [Pack capabilities](#pack-capabilities) under
`contributes.capabilities`; 3.6.0.0 made it 1.5: a Studio panel's `role`, `side` and `content_w`, the stage)
(`halo_harness.ext.API_VERSION`, also exported as `HALO_API_VERSION`). The machine-readable manifest schema is
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
| [Studio contributions](#studio-contributions) | stable | `contributes.studio` (3.2.0.0 R3): sections, panels, palette, the settings form, event lines, attention rows; a bundle only with `studio-script` (3.3.10.0 R3: its `api` publishes, listens, routes and asks for attention); 3.3.13.0 R2, API 1.2: a section drawn whole by one bundle (`view`), `api.lib` (the shell's React and parts), the pack's own API routes (`routes`, the `studio-routes` grant) |
| [The host services](#the-host-services) | stable | `ext.host` (3.3.13.0 R2, API 1.2): what Halo does for a pack's code -- its state folder, models for a task, the registered MCP servers and a probe, the tool env, a URL fetch through Halo's one network door, Halo as a child process, ComfyUI |
| [Pack capabilities](#pack-capabilities) | stable | `contributes.capabilities` (3.2.0.0 R4; API 1.4 this name): the pack's capabilities, available here or not and why, what a workflow's prerequisite checks, inspector lines |
| [Workflow contracts](#workflow-contracts) | stable | `workflows/<name>.yaml` (3.2.0.0 R5): compiled to an Orchestra goal, its hand-offs and a pinned plan; `halo workflow` |
| [Events and artifacts](#events-and-artifacts) | stable | typed events (3.2.0.0 R5: schemas, the events log, subscriptions), typed artifacts with viewers, memory with provenance |
| [Compatibility and migration](#compatibility-and-migration) | stable | the version policy (`ext.compatible`, `ext.deprecations`), `migrations` shown before an update and applied, `halo pack rollback` (3.2.0.0 R7) |
| [Bundles](#bundles) | stable | `bundle:` (3.3.7.0 R5): a capability bundle, a pack with a resource claim -- needs, reservation, routing, latency budget; the verdict before anything downloads |
| [Setup blocks](#setup-blocks) | stable | `contributes.setup` (3.3.11.0 R3, API 1.1): a pack's own pages in Studio's Setup -- a form over its `config.schema` keys, a check through Setup's checks job, a note -- shown while the pack is enabled, their state in `setup.json`; `halo pack enable` and `halo doctor` say what waits, `halo setup <pack>` opens it |
| [Themes](#themes) | stable | `contributes.themes` (3.3.12.0 R2, API 1.1): a pack's own palettes, registered as `<pack-id>/<id>` while the pack is enabled and drawn by the terminal and Studio like the ten (the `-daltonized` / `-ansi` modifiers, the WCAG AA pins); the theme saved before is restored when the pack is disabled or removed |
| [Requirements](#requirements) | stable | `requires:` tool entries (3.3.12.0 R4, API 1.1): the open-source tools a pack wraps, each with its install line per OS, license and why; Halo never installs one -- the doctor names a missing one, `halo pack test` skips what it gates |
| [Policy hooks](#policy-hooks) | stable | `contributes.policy` and `contributes.modes` (3.3.10.0, API 1.1): a pack's runtime mode (mode.json), a policy hook whose verdict decides a tool call before it runs (deny > ask > allow) and, with `after: true`, its result after (pass, redact, drop); every verdict in the audit; the dry run |
| [Services](#services) | stable | `contributes.services` (3.3.13.0 R3, API 1.2): a pack's program the supervisor keeps running while the pack is enabled and granted `services` -- autostart, a restart rule, a health file, a log; `halo supervise services`, the Pack Manager's Start / Stop |
| [Transports](#transports) | stable | `ext.remote` (3.3.13.0 R3, API 1.2): what a pack that carries Halo to a phone or a chat uses -- the live sessions and their control sockets, a session started for it, the cards' text, the core's notes, a voice note's transcript; the shipped signal pack is one |
| [CLI verbs, slash commands, doctor rows and settings rows](#cli-verbs-slash-commands-doctor-rows-and-settings-rows) | draft | four parts, each `draft` (3.4.0.0, API 1.3): `contributes.cli` (a pack's own `halo <verb>`, grant `cli:<verb>`), `contributes.slash` (its `/<name>`, the same grant), `contributes.doctor` (its rows in `halo doctor` under "From packs", grant `doctor`), `contributes.settings` (its rows in Studio's Settings under "From packs" and in `halo config get/set`, no grant) |
| [Core access](#core-access) | draft | `ext.core` (3.4.0.0, API 1.3): the core modules the first-run and coach packs drive, by name, over `core.REACHABLE` |
| [The reference example](#the-reference-example) | stable | the Documentation Review pack Halo ships (3.2.0.0 R6): every part of the API in one pack a third party can copy |

`stable`: a 1.x Halo keeps it. `removed <version>`: gone in that version,
announced a minor version before it ([Changes in 1.x](#changes-in-1x)).
Since 3.2.0.0 every part is `stable` and none is removed; a later part may
start as `draft` (usable, may change in a minor API version with a migration
note) or `planned` (the shape proposed, nothing reads it yet). Policy hooks
was the first `draft` part (3.3.10.0 R1) and is `stable` from 3.3.10.0 R2; 3.4.0.0's (API 1.3: the four contributions and core access) are `draft` now
([CLI verbs, slash commands, doctor rows and settings rows](#cli-verbs-slash-commands-doctor-rows-and-settings-rows), [core access](#core-access)).

## The stable surface (`halo_harness.ext`)

Status: **stable**. A pack's code imports `halo_harness.ext` and nothing
else of Halo (`tests/test_ext_api.py` walks every fixture and shipped pack's Python to
check it). The modules under `halo_harness/ext/` are the implementation; the
names in `__all__` are the contract.

- `API_VERSION`, `HALO_API_VERSION`: `"1.5"` (3.6.0.0; `"1.4"` from 3.5.0.0, `"1.3"` from 3.4.0.0, `"1.2"` from 3.3.13.0, `"1.1"` from 3.3.10.0 R1, `"1.0"` before).
- `api_version()`, `compatible(range)`, `deprecations()`: 3.2.0.0 R7, the version policy
  ([Compatibility and migration](#compatibility-and-migration)): this API's version, whether a `halo_api`
  range takes it, the names announced for removal (`[{name, since, removed_in, use}]`, none in 1.0).
- `read_yaml(path)`: a dict, `{}` for an empty file, None when missing or not a mapping.
- `write_yaml(pack_id, path, data)`: `[]` when written, else one line; lands where `write_private` would.
- `check_schema(doc, schema)`: one finding per shape problem, `{check, key, text, closest}`.
- `halo_harness.ext.subprocess_safe` (3.4.1.2): a pack's `subprocess` (`from halo_harness.ext import subprocess_safe as
  subprocess`): a bare program name runs from a PATH folder, never the current folder.
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
  API 1.2 (3.3.13.0 R2): `testing.scratch_home()` points the test's own process at a fresh home (call it first);
  `with testing.studio(folder) as s:` a live Studio in that home with the pack linked and every grant it requests
  (`s.route(rest)`, `s.call(method, path, body)` as the owner's page, `s.raw(path)` as an iframe asks: the pack's key
  in `?k=` (3.3.14.0 R1), `s.module(rel)`, `s.listen()`
  for the live feed); `testing.pack_module(folder, rel)` imports one of the pack's modules as Studio's routes do (the
  same module object, so a fake a test sets is the one the routes use). `halo pack test` also runs each of the pack's
  own `tests/test_*.py` (`python -m tests.<name>` from the pack's folder, a fresh home each, exit 0 passes).
- `remote`: API 1.2 (3.3.13.0 R3, stable): the transport seam ([Transports](#transports)) -- `sessions()`,
  `connect(session_id)`, `start_session(cwd, model, by)`, `cards`, `KINDS` / `notify` / `listen` / `notes`,
  `transcribe(path)`, `qr_text(data)`, `words()`, `service(pack, name)`, `service_ask(pack, name, verb)`,
  `logon_lines()`, `live_lines()`, `capture_studio()`, `enabled()`, `offline()`, `default_model()`.
- `host`: API 1.2 (3.3.13.0 R2, stable): [the host services](#the-host-services), what Halo does for a pack's code.
- `core`: API 1.3 (3.4.0.0 B, draft): [core access](#core-access) -- `core.module(name)`, `core.get(name, attr)` over
  `core.REACHABLE`, the Orchestra engine and the lineups for the shipped packs that left the core.
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
  capabilities: {capabilities: [...], inspector: [...]}   # 3.2.0.0 R4 (API 1.4: this name), below
  artifacts: [review-report]    # 3.2.0.0 R5: artifact schemas, artifacts/<name>.json
  events: [review.done]         # the kinds the pack publishes; a kind or {kind, schema} (R5: events/<kind>.json)
  workflows: [review]           # workflow names (R2), each workflows/<name>.yaml (R5)
  policy: [{id: fence, run: [...], when: {tools: [...], modes: [...]}, impact, on_error, redact, after}]   # 3.3.10.0, Policy hooks below
  modes: [{id: fenced, label: Fenced, theme: midnight}]   # 3.3.10.0: the pack's runtime modes
  setup: [{id: prefs, title: Review preferences, kind: form, fields: [style], after: model}]   # 3.3.11.0, Setup blocks below
  themes: [{id: nightshade, label: Violet night, posture: dark, palette: {bg: "#0d0b14", ...}}]   # 3.3.12.0, Themes below
  services: [{name: bridge, run: [...], autostart: true, restart: on-failure, health: {file: health.json}, log: service.log}]   # 3.3.13.0, Services below
  cli: [{verb: review, module: cli/review.py, help: ...}]   # 3.4.0.0 B (draft): also slash, doctor, settings -- below
config:
  schema: {properties: {style: {type: string, enum: [short, long]}}, additionalProperties: false}
  defaults: {style: short}
permissions: ["mcp:lint", hooks]    # mcp:<server>, hooks, bash, network, home-write, studio-script, studio-routes, services; 3.4.0.0 B: cli:<verb>, doctor
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

**A command that runs a program** (3.3.13.0 R3, API 1.2): a pack's `commands/<name>.md` whose frontmatter says
`run: ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/<file>", ...]` is a command the session runs itself, with no model
call: the words after `/<pack>:<name>` (or the entry command `/<pack>`) go to the program as its arguments, and its
output is the answer in the transcript (`halo_harness/commands/pack_run.py`; the environment a hook gets, stopped
after 120 s). The body is what the command says when the program cannot start. The signal pack's `/signal` is one.
3.3.14.0 R1: such a command needs the `bash` grant (the pack requests it; the Pack Manager row and `halo pack enable`
name it as "command <name> (run:)"); until it is granted the command keeps its prompt form and `halo pack doctor`
says what is missing. `HALO_PACK_ID` is the pack's id from its record, also for a linked pack in a folder of another
name.

A skill's `SKILL.md` body follows the same rule for its own variables
(3.2.1.0 R5): in a `` !`sh ${CLAUDE_SKILL_DIR}/scripts/x.sh` `` span the
skill's folder goes in as the span's shell reads it, and the rest of the
body gets it as it is. A skill or command body does not get
`${CLAUDE_PLUGIN_ROOT}`; a skill names its own files by `${CLAUDE_SKILL_DIR}`
([SLASH-COMMANDS-tui.md](SLASH-COMMANDS-tui.md)).

## Permissions and grants

Status: **stable**. A pack requests `permissions:` in pack.yaml: `mcp:<server>`,
`hooks`, `bash` (3.3.14.0 R1: also what a `run:` command needs), `network`, `home-write`, `studio-script` (3.2.0.0 R3: a
Studio bundle panel; 3.3.13.0 R2: or a section's view; 3.4.1.2: "runs this pack's code INSIDE Studio's page with
Studio's own power: it can do what you can do in Studio, including starting sessions that run commands",
[`api.lib`](#apilib)), `studio-routes` (3.3.13.0 R2, API 1.2; 3.4.1.2: "runs this pack's Python inside halo (Studio's
server) with your rights, Halo's keys and Studio's token; turning it off takes effect at Studio's restart for work
already started", [a pack's own routes](#a-packs-own-routes)), `services` (3.3.13.0 R3: "runs a program of this pack in
the background while the supervisor runs, with your rights: it can read what you can, Halo's key file included"),
`doctor` and `cli:<verb>` (3.4.0.0 B; 3.4.1.2: "runs this pack's Python inside halo on every halo doctor" / "for halo
<verb> and /<verb>", "with your rights and Halo's keys"); `hooks` says "its hooks run as commands with your rights".
`halo_harness/packs/grants.py` WHAT is the one table; no grant has a blank line. You grant them with `halo pack
enable <id> --grant NAME` (or `--grant-all`); grants add up and live in
state.json; `disable` clears them. 3.4.1.2: a pack Halo does not ship gets one of these grants that runs its code
(`studio-script`, `studio-routes`, `doctor`, `services`, `hooks`, `cli:<verb>`) only on an explicit yes: naming it
(`--grant NAME`) is that yes; `--grant-all` prints each line and asks once in a terminal (no terminal: refused unless
`--yes`); Studio's Pack Manager shows the lines in a dialog and grants on Grant. Once any of them is given, `bash`,
`network` and `home-write` fence nothing: they are notes a pack's own code reads, and that code runs with your rights. A contribution whose permission is not
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
| `sections` | `[{id, title, blurb, help, panels: [<panel>], view?}]` | a section of its own after the core sections (3.2.0.0 R6: after the core sections; 3.3.3.0 R2: after Settings, reached by a click or the palette; 3.3.13.0 R2: after Local, and the first pack section takes the tenth key, `Alt+0`; the icon rail shows them after a thin divider, each with the diamond, 3.3.2.0); its panels fill the 24 columns left to right, or (3.3.13.0 R2, API 1.2) `view: {bundle: <module>}` draws its whole page ([a section's view](#a-sections-view)) |
| `panels` | `[{section: <core section>, ...<panel>}]` | a panel in Session, Team, Roles or Orchestra: a closed drawer beside that section's main thing, its button in the view bar (3.6.0.0; a strip before) |
| `routes` | `{module: <file>.py, prefix: <word>}` | 3.3.13.0 R2 (API 1.2): the pack's own API routes, `/api/packs/<id>/<prefix>/...`, answered by the module's `handle` ([a pack's own routes](#a-packs-own-routes)); needs `studio-routes` |
| `palette` | `[{id, label, action}]` | a command palette line in the group "pack <id>"; `action` is `route:<section>[/<panel>]`, `url:<address>` or `config` |
| `config_form` | `true` or `false` | a Settings panel (kind `form`) at the end of the pack's first section, and a palette line "Settings: <name>" |
| `events` | `{<kind>: {label, line}}` | a `pack_event` of that kind (one of `contributes.events`) renders as `label` + `line`, `{field}` read from the frame's data, in Session's Live column, Agents' Activity and the pack's `events` panels; a kind no running pack declares keeps the generic line (the pack, the kind, the data in short) |
| `attention` | `{<kind>: {label, keys: {a, r, s, o}}}` | a row of the attention queue, kind `pack:<id>:<kind>`, with the pack's label and its answers |

A `<panel>` is `{id, title, kind, source, schema, w, h, role, side, content_w, help, columns, links}`; API 1.5 (3.6.0.0, Studio's stage): `role` `main` | `drawer` (the default: beside the main thing, its button in the view bar) | `tab` (in the main thing's place), `side` `left` | `right`, `content_w` 360-560 px; a 1.0-1.4 panel's `w` columns map to a right drawer `w` x 60 px wide, a pack section's first panel its main thing:

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
id used twice or holding `--`; 3.3.13.0 R2: a view's bundle that is not a `.js` / `.mjs` file of the pack or without
`studio-script` requested, a section with a view that also lists panels, a routes module that is not a `.py` file of
the pack, a prefix that is not a word, routes without `studio-routes` requested.

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

- `GET /api/pack/registry`: `{version: 1, core: [the five a pack's panel may join], packs: [{id, name,
  version, scope, script: granted | not granted | none, grant, routes, sections,
  panels, palette, config_form, events, attention}]}`, ids qualified, routes
  resolved to `{section, panel?}`, each panel with `about` ("from pack <id>"),
  `collapsed` (true in a core section) and `file` (the api path of its
  source; a bundle's only once granted); 3.3.13.0 R2: a section with a view carries `view: {source, script, grant,
  file?}` (`file` only once granted), and `routes` is `{prefix, api, granted}` or null; 3.3.14.0 R1: `key`, the pack's
  key for what its page embeds (`?k=`).
- `GET /api/pack/<id>/file/<path>`: a markdown or JSON file inside the pack's
  folder, or its bundle module (a bundle panel's `source`, only with
  `studio-script` granted, else 403 naming the grant), under the shell's CSP.
  An `import()` sends no header, so this route also takes the pack's key in `?k=` (3.3.14.0 R1: the registry's `key`,
  a GET-only key Studio derives for this pack, never the launch token). `..`, an absolute path or another file type is
  404.
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
`halo_harness/studio/packs_studio_bundle_api.py`). The calls below reach the pack's own files, data folder, declared
event kinds and attention rows and mode, and its `lib`'s client the pack's own routes ([`api.lib`](#apilib) says the
scope); each rides the `studio-script` grant: the module loads only
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
| `lib` | | 3.3.13.0 R2 (API 1.2): [`api.lib`](#apilib), the shell's React and parts | |
| `routes` | | 3.3.13.0 R2: the path of the pack's own routes under `/api/` (`packs/<id>/<prefix>`), `""` without them | |
| `section` | | 3.3.13.0 R2: the section the module draws in (a view's own, or the panel's) | |

3.3.13.0 R2: `on(kind, cb)` also hears the pack's `pack_live` frames, what its routes publish with `ctx.publish` (live
only: not kept in the events log, not drawn in Session's Live column or Agents' Activity).

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

### A section's view

3.3.13.0 R2, API 1.2 (`halo_harness/packs/studio_view_rules.py`; the shell: `routes/packs/PackView.tsx`). A section
whose page is one module of the pack, not a grid of panels: `sections: [{id, title, blurb, help, view: {bundle:
studio/page.js}}]`. Studio imports the module once you grant `studio-script` (until then the page is one line naming
`halo pack enable <id> --grant studio-script`) and calls `mount(el, api)` with the section's whole page as `el` and the
[bundle `api`](#the-bundle-panels-api) (`api.section` its id, `api.lib`, `api.routes`); what `mount` returns runs when
the section goes away. The section takes a key like any pack section (the first pack section `Alt+0`), opens with
`?mode=<id>--<section>`, `halo studio --mode <id>--<section>` and `/studio <id>--<section>`, and has no "+" menu: the
page is the room (a page that wants panels draws `api.lib.workspace.Workspace` itself). Its `help` is the section's
"How this works": the first line what it is, each other line a step, `Step: what it does`. A section with a view lists
no panels. The design pack's Design section is one (`halo_harness/templates/packs/design/`).

A command can open it: a pack command whose frontmatter says `studio: <section id>` (one of the pack's own sections) is
not a prompt -- `/<command>` opens Studio there and `/<command> url` prints the address, as `/studio <id>--<section>`
does (`halo_harness/commands/pack_studio.py`; the design pack's `/design`).

### api.lib

3.3.13.0 R2, API 1.2 (`halo_harness/studio/ui/src/packlib/`). What a bundle shares with the shell instead of bundling a
copy, so a pack's page draws like the shell and there is one React. It follows the shell's major version (`lib.version`,
`"3"`): a minor Studio only adds to it.

| Part | What it is |
|---|---|
| `React`, `ReactDOM`, `jsxRuntime` | the shell's own React 19 (`ReactDOM` is `react-dom/client` with `createPortal`, `flushSync`) |
| `ui` | the `lib/ui` primitives: `Button`, `Dialog`, `Toasts`, `Tabs`, `Field`, `Kbd`, `Empty`, `Skeleton`, `ErrorState`, `Surface`, `HudStrip`, `HudCell`, `Icon`, `Menu`, `WindowedRows`, `FitMeter`, `TextBox` (3.3.15.0 R3), `Panel` |
| `api`, `fetchJson(path, init?)`, `authUrl(path)` | 3.3.14.0 R1: a JSON client scoped to this pack (`api.get/post/put/del`, `call`, `ApiError`; `fetchJson` for a path under `/api/`), below; `authUrl` the address of one of the pack's own routes or files with its key in `?k=`, for what sends no header (an iframe, an image, a video, a link) |
| `events` | the live feed the shell is connected to: `on(kind, fn)` (returns the stop), `state()`, `onState(fn)` |
| `store` | `createStore`, `useStore`, `writeLocal`, `studio` (the shell's state), `toast(text, tone)`, `goSection(id)` |
| `theme` | `tokens()` (the palette's colour variables as they are now), `current()`, `onChange(fn)`; `css(text)` (also `lib.css`) adds a stylesheet of the pack's own as a constructed sheet, so the shell's CSP holds, and returns the function that removes it |
| `workspace` | `Workspace` (the panel grid: `<Workspace section={api.section} specs={...} />`; its panels open in the shell's Inspector, `studio.update(() => ({ inspector: { section, panel } }))`), `showPanel`, `hidePanel`, `focusPanel`, `patchPanel`, `layoutStore`, `settle`, `useStateMotion` |
| `widgets` | `Markdown` (the safe subset), `ModelSelect`, `PackForm` (a pack's settings form), `Metric`, `useHelpGroup`, `useResolved` |
| `util` | `same`, `changed`, `equal`, `reuse` (structural sharing for polled JSON), `nudgeApart` |
| `kbd(combo, run)` | a key on the page (`Mod+Enter`; the section keys and Mod+K stay the shell's); returns the stop |
| `commands(fn)` | palette lines while the page is up (`fn` returns `[{id, label, hint?, run}]`, read each time the palette opens, grouped "pack <id>"); returns the stop |

**The client's scope** (3.3.14.0 R1; `halo_harness/studio/ui/src/packlib/scoped.ts`). `api.lib`'s client is the pack's,
not the shell's: it sends Studio's token and never the owner's proof (below), and it reaches any method on the pack's
own routes (`packs/<id>/...`); GET on its own `pack/<id>/file|data|config|mode|artifact/...` and POST on its own
`pack/<id>/publish|attention`; PUT on its own canvas layouts (`layout/<id>:<name>`); and GET on the read-only routes a
page draws from (`pack/registry`, `state`, `session`, `tools`, `models...`, `layout/<name>`, `media/status|models|
workflows...`, `glossary`, `field-help`). Anything else rejects with an `Error` naming that rule, and no request is
made. 3.4.1.2: Studio answers EVERY write (any method but GET) only for a request carrying the owner's proof,
`X-Halo-Owner`, which only the shell's own page holds, except a running pack's own routes (the `packs/<id>/...`,
`pack/<id>/publish|attention` and `layout/<id>:<name>` writes above, the id taken from the path); anything else gets
403 "this needs the owner's own page" ([STUDIO-shell.md](STUDIO-shell.md#the-owners-page-and-a-packs-key)).
**What the scope is not:** the client is the scope a well-behaved page keeps to, and the server enforces what it can,
but a bundle runs in Studio's own page: it can read the token, draw over the shell and press its buttons, so
`studio-script` is said plainly as Studio's own power (above). A real fence -- a sandboxed frame with a message broker
-- is the "Pack trust" item of plans/ROADMAP.md. The extension API stays 1.2.

The same parts (without `commands`) are `globalThis.__haloStudioLib`, because a module built against them takes React
at import time (hooks imported at the top, a `memo()` or a store made at module level). 3.3.14.0 R1: Studio imports
pack modules one at a time, and while one is evaluated the global is that pack's own lib (its scoped client); between
imports its client is scoped to no pack (the read-only GETs). The design pack builds that way:
`halo_harness/studio/ui/vite.pack.config.ts` maps `react`, `react/jsx-runtime`, `react-dom/client` and `@halo/<part>`
to the matching part (`vite.shared.ts` `shellLib`), and tsconfig's paths type `@halo/<part>` against the shell's own
modules. A plain ES module reads `api.lib` in `mount`, as the kit's example does.

### A pack's own routes

3.3.13.0 R2, API 1.2 (`halo_harness/studio/packs_routes.py`). `contributes.studio.routes: {module: server/routes.py,
prefix: design}`, granted `studio-routes` ("runs this pack's Python inside halo (Studio's server) with your rights,
Halo's keys and Studio's token; turning it off takes effect at Studio's restart for work already started"): Studio imports the module
through the pack's own folder (the package `halo_packs.<id>`, so a relative import reaches the pack's other modules;
`${CLAUDE_PLUGIN_ROOT}` semantics: nothing is copied) and answers `/api/packs/<id>/<prefix>/<path>`, behind the token
like every route, with

```python
def handle(ctx, method, path, body, query):   # path: what follows the prefix
    return 200, {"ok": True}                  # (status, a dict or a list): JSON
    # or (status, bytes | str, content_type[, headers]): a file
```

`ctx` carries `pack_id`, `prefix`, `pack_root`, `data_dir` (the pack's data folder), `state_dir` (Halo's), `cwd`
(Studio's project), `publish(kind, data)` (a `pack_live` frame on the live feed, which the pack's bundle hears with
`api.on(kind)`; nothing keeps it) and `bridge` (Studio's live-feed bridge). The module is imported once and again when
its file changes or its install record does (3.3.14.0 R1: `halo pack update` and `rollback` load it afresh, all of its
modules); a pack disabled, removed or no longer granted is unloaded (its next request answers 404 or 403 naming the
grant), and only a pack this Studio loaded is: an id a URL makes up, or a registry read that fails for a moment,
unloads nothing. The module runs in Studio's own process, so a thread or a child it started keeps going after the
unload: a module-level `unload()`, when the module defines one, runs then to stop them (3.3.14.0 R1); anything it
leaves running stops with Studio. A module that does not import, a `handle` that raises or answers out of shape: 500 with one line,
kept in the pack's data folder (`.studio-routes.json`) as `halo pack doctor`'s `studio-routes` row until it imports
clean again. The request body limit is the server's 4 MB unless the module says `MAX_BODY = <bytes>` (at most 64 MB;
per pack and prefix, never global: the design pack's is 22 MB for a 15 MB asset). A GET also takes the pack's key in
`?k=` (an iframe or an image sends no header; 3.3.14.0 R1: `api.lib.authUrl` adds it, the launch token is not taken
from the URL), and a file answer keeps the route's own `Content-Security-Policy` (and a `Content-Disposition`); a file
answer with no CSP of its own gets `sandbox; default-src 'none'` (3.3.14.0 R1), and every other header of the answer
is Studio's.

`halo pack test` imports the module the same way and asks `handle(ctx, "GET", "ping", {}, {})`: it must answer in
shape with a status below 500. `halo pack new --kinds studio` writes a working example of each part (a page-view
section with `api.lib`, a routes module with `ping` and a `note` POST).

## The host services

Status: **stable** (3.3.13.0 R2, API 1.2; `halo_harness/ext/host.py`). What Halo does for a pack's own code that the
pack cannot do with `halo_harness.ext` alone; `from halo_harness.ext import host`. Each goes through Halo's own code,
so it follows the owner's config, the offline switch and the network door the way Halo's features do.

| Call | What it does |
|---|---|
| `host.state_dir()` | Halo's state folder (`~/.halo`, or a test's scratch home) |
| `host.models(task="", cwd=None, limit=12)` | model rows for a picker, the best for `task` first (`design`, `code`, `vision`, ...) |
| `host.media_models(kind="all")` | ComfyUI's models from the cached inventory, by what each makes |
| `host.mcp_servers(cwd=None)` | `{name: entry}` of every MCP server a session in `cwd` sees (project scope wins) |
| `host.mcp_probe(name, entry, cwd=None, env=None)` | start that server through Halo's MCP handshake, list its tools, stop it: `{state, tools, error, elapsed}` |
| `host.child_env(env=None)` | the environment Halo gives a tool's process (its provider keys left out) |
| `host.fetch(url, timeout_s=20, limit=2_000_000)` | a page's text through Halo's one network door (offline mode refuses it with its line) |
| `host.halo_command()` | `[python, "-m", "halo_harness"]`: Halo as a child process (`halo -p` for a turn of the pack's own) |
| `host.comfy()` | the ComfyUI Halo is pointed at (`halo media`): `queue(workflow, sets, source="", cwd=None)` -> `{prompt_id, source, label}`, `wait`, `outputs`, `view`, `url` |
| `host.HostError` | what a host call raises: its message and `status` |

## Pack capabilities

Status: **stable** (3.2.0.0 R4; API 1.4, 3.5.0.0: its manifest key is `contributes.capabilities` -- its name before,
`contributes.fleet`, is still read the same, its `mission` key ignored). A pack declares the capabilities it brings
under `contributes.capabilities`; each is checked on this host: available or not, and why. A pack workflow that needs
one runs only while the pack runs here with the grants the capability requires, `halo pack inspect` lists them with
available / why, and `halo pack doctor` has a row per capability not available here.

| Key | Shape | What Halo does with it |
|---|---|---|
| `capabilities` | `[{name, description, requires, capacity}]` | one entry each: `{name, description, available, why, checks, requires, capacity}` |
| `capabilities[].name` | one of the top-level `capabilities:` | what a workflow's prerequisite names (`docs.review`, or `pack:docs.review`) |
| `capabilities[].description` | a sentence | what `halo pack inspect` prints under it; no path in it |
| `capabilities[].requires.tools` | `[name]` | a CLI on PATH, an MCP server or tool, a craft app here |
| `capabilities[].requires.runtimes` | `[word]` | `python`, `node`, `java` ... found here (a version when known) |
| `capabilities[].requires.platform` | `[word]` | this host's OS or distro is one of them (`linux`, `windows`, `darwin`, `kali` ...) |
| `capabilities[].requires.hardware` | `{gpu: true \| false \| <a word of its name>, ram_gb: n}` | a GPU (or one whose name has the word, `4090`), at least that much RAM |
| `capabilities[].requires.models` | `[tag or model]` | a catalog model with the tag (`long-context`, `vision`, `audio`, `video`, `files`, `image-out`, `tools`, `local`, `reasoning`, `open-weights`, `audio-out`), or one by its ref or family |
| `capabilities[].requires.grants` | `[permission]` | each one of the pack's `permissions`, granted here |
| `capabilities[].requires.locality` | `[repo \| repo:<name> \| pack-data]` | the data is on this host: a repo checkout (that repo), files in the pack's data folder |
| `capabilities[].capacity` | `{parallel: 1..64}` | how many uses of it this harness takes at once |
| `inspector` | `[{label, source}]` | an inspector line: a markdown or JSON file of the pack, shown with the capability |

A capability is **available** when every `requires` holds on this host;
`why` names what holds (`tools: or:anthropic/claude-sonnet-4.6; bash
granted`) or what is missing (`no GPU here`, `bash not granted (halo pack
enable doc-review --grant bash)`). Only the packs that run here are listed;
a disabled pack adds nothing.

**What a capability never carries.** A value under `contributes.capabilities` that looks like a secret (a token shape
the privacy scan knows, a Bearer value) or an environment reference (`$VAR`, `${VAR}`, `%VAR%`) is a manifest problem,
and so is a path in a `description`: one line each naming the key and its line, and the pack does not install or run:

```
pack.yaml line 12: contributes.capabilities.capabilities[0].description: a token-shaped value; an advertisement leaves this machine, so it never holds a secret or an environment value
pack.yaml line 14: contributes.capabilities.capabilities[0].requires.tools[0]: an environment reference ($HOME); an advertisement leaves this machine, so it never holds a secret or an environment value
```

A capability name the top-level `capabilities:` does not list, a `requires` key outside the table above (with the
closest one), a grant the pack does not request, an unknown locality, a capacity outside 1..64 and an inspector source
outside the pack or of another type are one line each too.

The doc-review reference pack's (`halo_harness/templates/packs/doc-review/pack.yaml`):

```yaml
capabilities: [docs.review]
permissions: ["mcp:lint", hooks, bash]
contributes:
  capabilities:
    capabilities:
      - name: docs.review
        description: Reviews a repo's documents for dead links, heading order and style
        requires:
          models: [tools]
          grants: [bash]
        capacity: {parallel: 2}
    inspector:
      - {label: Review checklist, source: capabilities/checklist.md}
```

`tests/fixtures/packs/caps-needs-gpu/` is one not available on a host without a GPU (`why: no GPU here`);
`caps-secret/` and `caps-unknown-name/` are the failure fixtures.

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
| `prerequisites` | `{tools, grants, capabilities, files}` | checked before the run: a CLI on PATH, a grant you gave the pack, a capability available here (its `contributes.capabilities` requires), a file in the repo |
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
| `scope` | `session` (the default) or `machine`: how far the verdict reaches |

The answer must come **within the budget**, `packs.policy.budget_ms` (2000 when unset). A late answer, a line that
is not a JSON object, a verdict or scope outside the words above, or the process ending (or not starting) is the
policy's `on_error`, always with a logged line and the reason saying what happened: `deny -- fence: on_error deny
(no answer within 2000 ms)`. A late answer that arrives afterwards is read and dropped (its id is an earlier
request's), so it never answers the next request; a process that ended is started again for the next one. Writing
the request has the same budget (3.3.14.0): a process that stops reading its input is ended at the budget, the call
says `policy did not answer in <n>s` (its `on_error` applies), and the next call starts it again. A fence
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
confirmation.

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
out of the result too before it leaves Halo. The call's live output (the `tool_progress` frames the TUI, Studio and
every control-socket client, a phone included, show) goes through the same verdict (3.3.14.0): `pass` streams it as
it was, `redact` sends the redacted text, `drop` sends none.

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

## Themes

Status: **stable** (3.3.12.0 R2, API 1.1). A pack ships palettes of its own under `contributes.themes`; while the pack
is enabled each one is a theme exactly like the ten Halo has (`halo_harness/themes`, [CONFIG.md](CONFIG.md) `theme`):
`/theme`, `halo config set theme`, Setup's Theme page, Studio's header menu and Settings -> Themes list it under the
pack's id, and the terminal and Studio draw it. `halo_harness/packs/manifest_themes.py` checks the list at install, one
line per problem, and the install is refused: an id that is not `^[a-z][a-z0-9-]*$`, a core palette's id, an id that
ends in a modifier (`-daltonized`, `-ansi`), an id used twice, a label left out, a posture other than `dark` or
`light`, a missing or an extra token, a value that is not `#rrggbb`, and every pinned pair under its WCAG AA floor
(below), the palette's own and its `-daltonized` variant's, each with its ratio.

```yaml
contributes:
  themes:
    - id: nightshade
      label: Violet night, a green second accent
      posture: dark                 # dark | light
      palette: {bg: "#0d0b14", bg2: "#120f1c", surface: "#171325", ...}   # every token below, each "#rrggbb"
```

**The tokens** (`halo_harness/themes/palettes.py` `TOKENS`; a palette names every one):

| Token | What it colours |
|---|---|
| `bg` | the page behind everything |
| `bg2` | the second band: Studio's canvas, the terminal's surface |
| `surface` | a panel's or a card's face (Studio) |
| `surface2` | a raised face: hover, inputs, the terminal's panels |
| `border` | an opaque edge (the terminal's borders) |
| `line` | the tint Studio's lines and grid are drawn in (dark: with alpha; light: as is) |
| `text` | body text |
| `muted` | secondary text: hints, labels |
| `faint` | decoration: dim text, the strong line on a light page |
| `accent` | this is live / do this |
| `accent2` | the second accent |
| `accent_ink` | text on an accent fill (a primary button) |
| `ok` | done, healthy |
| `warn` | needs you |
| `bad` | failed |
| `user` | the user's lines in the terminal |
| `tool` | a tool call in the terminal |

**The contrast rule** is the one the ten meet (`themes/registry.py` `PAIRS`, WCAG AA): `text` reads 4.5:1 on `bg`,
`bg2`, `surface` and `surface2`; `accent_ink` 4.5:1 on `accent` (a primary button's label); `muted`, `accent`,
`accent2`, `ok`, `warn`, `bad`, `user` and `tool` 3:1 on `bg`, `bg2` and `surface`. `faint` is decoration and not
pinned. The `-daltonized` variant is derived as for the ten (the accent pair, the status pair and the user / tool
lines moved to blue and orange, never red against green) and must meet the same floors.

**The name** is `<pack-id>/<id>` (`pack-theme/nightshade`): never a core id, visibly a pack's; with a modifier,
`pack-theme/nightshade-daltonized` or `-ansi`. It is what `theme` in `~/.halo/config.json` holds and what Studio's
`data-theme` attribute says. **Live, no watcher**: the registry reads the enabled packs' manifests at call time
(`halo_harness/themes/packs.py`, cached on the packs registry's own signature), so `halo pack enable` makes the
palettes valid at once and `disable` / `remove` takes them away; `theme.VALID_THEMES` is a live view of that set.
**Studio**: `GET settings/themes` lists a pack palette after the ten with `pack`, `pack_name`, its tokens and the CSS
variables it is drawn in (`halo_harness/themes/studio_css.py`, the derivation `scripts/themes_css.py` runs for the
ten at build time); the page sets those variables on `<html>` while the palette is drawn, and the served page carries
them as one inline rule for the first frame (allowed by its hash in the page's style-src), so a reload never shows
`holo` first. A pack palette never touches the built stylesheet.

**The restore rule.** Choosing a pack palette through any door (`/theme`, `halo config set theme`, Setup, the header
menu, Settings -> Themes: all go through `theme.persist_theme`) keeps the value saved before it in
`~/.halo/packs/.data/<id>/theme.json` (`halo_harness/themes/restore.py`); moving to another palette of the same pack
keeps that first value; a core palette, or the key unset, clears the record. When the pack is disabled or removed while
its palette is the saved `theme`, the value before it is written back (or the key unset when there was none) and the
command says so in one line, `theme: pack-theme/linen was pack-theme's palette and the pack is disabled; restored
claude-dark`; Studio follows at once, a running terminal on `/theme` or its next launch. A saved `theme` naming a
pack palette whose pack is not enabled reads like a removed game theme: one line at startup and in `halo doctor
--config`, the default drawn, never a crash. With no pack contributing `themes`, everything is as it was (the ten, the
generated CSS). `tests/fixtures/packs/pack-theme/` is the example: `nightshade` (dark) and `linen` (light).

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

## Services

Status: **stable** (3.3.13.0 R3, API 1.2). A pack that must keep a program running -- a bridge to a phone, a watcher,
a small server -- lists it under `contributes.services`; the supervisor (`halo supervise`,
[SUPERVISE.md](SUPERVISE.md#pack-services)) runs it while the pack is enabled and granted `services`.
`halo_harness/packs/manifest_services.py` checks the list at install, one line per problem naming the entry (a name
that is not one, a `run` outside the pack, a restart rule that is not one of the three, a health with both or neither
of file and url, a url that is not on this machine, a log outside the data folder), and the install is refused.

```yaml
contributes:
  services:
    - name: bridge                               # lower-case letters, digits, - and _; the service is <pack>/<name>
      description: answers the paired phones     # one line: what it does while it runs
      run: ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/bin/signal.py", "service"]   # exec form, a file of the pack
      autostart: true                            # halo supervise starts it (false: only Start starts it)
      restart: on-failure                        # on-failure (an exit other than 0) | always | never
      health: {file: health.json, max_age_s: 90} # a file in the data folder it rewrites
      log: service.log                           # its stdout and stderr, in the data folder
permissions: [services]
```

| What | How |
|---|---|
| **start** | each tick (5 s) of `halo supervise`, an autostart service of a pack that is enabled and granted `services` and is not running starts, in the pack's folder, with the environment a hook gets (Halo's provider keys left out) plus `HALO_SERVICE` (`<pack>/<name>`), `HALO_SERVICE_HEALTH` (the health file's path), `HALO_SERVICE_STOP` (the file whose existence asks it to end) and `HALO_SUPERVISOR=1` |
| **restart** | after an exit other than 0 (`on-failure`) or any exit (`always`), it starts again after 5 s, doubling to 300 s; ten minutes up puts the wait back to 5 s |
| **stop** | Stop (the Pack Manager's row, `halo supervise service stop <pack>/<name>`), the grant taken back, the pack disabled, or the supervisor's own way out: the stop file first, then after 5 s the process ended; 3.3.14.0: a service runs in its own process group (a Job object on Windows), so ending it ends the programs it started too (signal-cli's JVM with the bridge) |
| **state** | `<state>/supervise/services.json`, read by `halo supervise services` and `status`, the Pack Manager's row ("running since 09:12" / "stopped: <line>"), `halo doctor` (one row per service), the TUI's remote chip and `ext.remote.service(pack, name)` |
| **health** | a file younger than `max_age_s` (120 when left out) is `ok`; its JSON's `line` (or `state`) is the row's line. A `{url: ...}` health is accepted and not checked in this version: the row reads `unknown` (3.3.14.0, REVIEW #26) || **the enable line** | `halo pack enable <id>` says, per service, where it starts and whether the supervisor runs now |
| **halo pack test** | checks that each service's command resolves and its health and log have a shape the supervisor reads; it does not start it |

A service needs the session a person would have: it asks for one through [Transports](#transports)'s
`start_session`, which the supervisor starts with the keys it holds, so the pack's program never holds one.

## Transports

Status: **stable** (3.3.13.0 R3, API 1.2). A transport carries a session somewhere else -- a phone, a chat -- and is
a pack; the core never knows which one. `halo_harness.ext.remote` is what it uses
([REMOTE.md](REMOTE.md#transports) has the core's side):

| Name | What it does |
|---|---|
| `sessions()` / `connect(session_id, timeout=10)` | the live sessions (newest first, never a token) and a client of one's control socket: `.call(cmd, **fields)`, `.next_event(timeout)`, `.close()` -- the wire is [REMOTE.md](REMOTE.md#the-wire) |
| `start_session(cwd, model="", by="", timeout_s=45)` | a session with no terminal for the transport; `(row, "")` or `(None, the line)` |
| `default_model()`, `enabled()`, `offline()` | config `model`; `remote.enabled` (every transport's switch); Halo's offline mode |
| `cards` | the plain-text cards (`permission_messages`, `question_card`, `plan_card`, `approval_card`, `status_text`, `one_line`) and the reply parsers (`parse_permission_reply`, `parse_question_reply`, `normalize_questions`) |
| `KINDS`, `listen(name)`, `notes(cursor, kinds=None)`, `notify(kind, text, source="", session="")` | the core's notes: say you listen (once a minute), read the ones after your cursor; kinds `turn_done`, `asks`, `errors`, `supervisor`, `steward` |
| `transcribe(path)` | a voice note's text through the local speech server that runs ([VOICE.md](VOICE.md)); `(text, "")` or `(None, the line)` |
| `qr_text(data)`, `words()` | a QR code in half-block text; the 256 words of the signing and pairing phrases |
| `service(pack, name)`, `service_ask(pack, name, "start" \| "stop")`, `logon_lines()` | its own service's row, a Start / Stop, how to start the supervisor at logon |
| `live_lines()` (`fleet_lines()` its name before 1.4, still answering), `capture_studio(session_id="")` | this harness's sessions and what waits; a capture of the Studio window when it is open here |

The shipped **signal pack** (`halo_harness/templates/packs/signal/`) is the example: its service runs the bridge,
its `/signal` command runs its program, its Setup blocks walk signal-cli, the account, pairing and the service, and
its tests drive a whole conversation through fakes.

## CLI verbs, slash commands, doctor rows and settings rows

Status: **draft**, each of the four parts (Halo 3.4.0.0, API 1.3; usable, may change in a minor API version with a
migration note). What a pack that left Halo's core (the first-run and coach packs) needs to keep its verbs: a top-level
`halo <verb>`, a `/<name>` slash command, rows in `halo doctor` and rows in Studio's Settings. Each has one loader
module under `halo_harness/packs/` (`contrib_cli.py`, `contrib_slash.py`, `contrib_doctor.py`, `contrib_settings.py`;
`contrib_lines.py` hands their rules to the manifest check). The manifest shapes, exactly (the coach pack's, trimmed):

```yaml
contributes:
  cli:      [{verb: coach, module: cli/coach.py, help: "the post-run coach's card"}]    # main(argv) -> int
  slash:    [{name: coach, module: cli/slash.py, help: "the post-run coach's card"}]    # run(args_text, facade) -> str
  doctor:   [{id: coach, module: doctor.py, help: "what the coach keeps and uses"}]     # rows(ctx) -> list
  settings: [{key: probe.k, title: Probe pairs, type: integer, default: 1, help: "..."}]  # packs.settings.coach.probe.k
permissions: ["cli:coach", doctor]
```

Keys: `cli` takes `verb` (lower-case letters, digits and `-`), `module` (a `.py` file of the pack), `help` (one line);
`slash` takes `name`, `module`, `help`; `doctor` takes `id`, `module`, `help`; `settings` takes `key` (lower-case words
joined by `.`), `title` (required), `help`, `type` (`string`, `integer`, `number` or `boolean`) and `default` (of that
type). Any other key is a problem.

| Key | What Halo does with it | Grant |
|---|---|---|
| `cli` | `halo <verb> ...` imports the module through the pack's folder (the package `halo_packs.<id>`, as Studio imports a pack's routes) and calls `main(argv)` with the words after the verb; its return is the exit code. A core verb always wins; a verb that left the core (`halo_harness/left.py`: `team`, `start`) says its one line when no enabled pack answers it | `cli:<verb>` ("its verb runs") |
| `slash` | `/<name> ...` runs `run(args_text, facade)` and shows what it returns, where no core command took the name; a word that left the core is a one-line command with its pack off | `cli:<name>` (the same grant as the verb of that name) |
| `doctor` | `halo doctor` adds `rows(ctx)`'s rows last, each `From packs, <id>: <text>`: a string is an `[OK]` line, `{ok, text, fix}` an `[OK]` or a `[WARN]` with its `-> fix:`; `ctx` carries `pack_id`, `cwd`, `state_dir`, `data_dir`. Only while the pack is enabled; without the grant, one `[WARN]` row naming it. A module that raises is one `[WARN]` row naming it, never the doctor's failure | `doctor` |
| `settings` | rows of Studio's Settings and `halo settings` in the group **From packs** (each row's title names its pack), each `packs.settings.<id>.<key>` in config.json (where `ext.get_config` reads); `halo config get` says the row's default while it is unset and `halo config set` checks its type (one line, exit 2). With the pack off the rows are gone and a value left in config.json is ignored | none (no code runs) |

A pack's Python runs with your rights, so every key that runs it takes a grant you give (`halo pack enable <id>
--grant cli:<verb>`, or `--grant-all`), as `studio-routes` and `services` do. One line per problem names the entry
(`contributes.cli[0].module: 'cli/x.py' is not in the pack`); a verb or a name used twice, an unknown key, a module
outside the pack or not a `.py` file, a settings `type` that is not `string`, `integer`, `number` or `boolean` are
problems.

## Core access

Status: **draft** (Halo 3.4.0.0, API 1.3). `halo_harness.ext.core` is the one door the shipped packs that left the
core in 3.4.0.0 (first-run, coach) use to reach the Orchestra engine, the lineups, the checks, the run folders and the
writers they always drove (the coach reads verified outcomes through `outcomes.records` only):
`core.module(name)` is `halo_harness.<name>` and `core.get(name, attr)` one name of it, for a `name` in
`core.REACHABLE` (any other raises ValueError naming the rule). These are Halo's own modules as they are in the Halo
the pack ships with: they follow Halo's version, not the extension API's, so a third-party pack does not build on them.

`core.version()` is this Halo's version. A shipped pack never imports another pack: the first-run pack reaches the
coach through `core.get("packs.contrib_cli", "dispatch" | "pack_call")` (the coach pack's verb or module while it is
enabled, else the one line naming the coach pack).

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
pack doc-review needs extension API 1.6 to 1.9; this Halo has 1.5
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

- **1.5** (Halo 3.6.0.0): a Studio panel's `role`, `side`, `content_w` ([Studio contributions](#studio-contributions)); a 1.0-1.4 panel's `w` / `h` still work (`w` columns -> a right drawer `w` x 60 px wide); nothing deprecated; a pack that names a role states `{min: "1.5"}`.
- **1.4** (Halo 3.5.0.0): the manifest's capabilities block is `contributes.capabilities`; its name before,
  `contributes.fleet`, is still read the same (its `mission` key is ignored, the locality `shared` is gone);
  `ext.remote.live_lines` (the old name `fleet_lines` still answers). A pack that names a capability states
  `{min: "1.4"}` to use the new key; the shipped doc-review pack does.
- **1.3** (Halo 3.4.0.0): adds the manifest's `contributes.cli`, `contributes.slash`, `contributes.doctor` and
  `contributes.settings` with the grants `cli:<verb>` and `doctor` ([CLI verbs, slash commands, doctor rows and settings
  rows](#cli-verbs-slash-commands-doctor-rows-and-settings-rows)) and `core` ([core access](#core-access)); all draft;
  deprecates nothing. A 1.0, 1.1 or 1.2 pack keeps everything (`{min: "1.0", max: "1.9"}` and `{min: "1.2"}` take 1.3);
  the shipped first-run and coach packs say `{min: "1.3"}`.
- **1.2** (Halo 3.3.13.0 R2): adds `host` ([the host services](#the-host-services)), the manifest's
  `contributes.studio.sections[].view` ([a section's view](#a-sections-view)) and `contributes.studio.routes` with the
  `studio-routes` grant ([a pack's own routes](#a-packs-own-routes)), the bundle `api`'s `lib`, `routes` and `section`
  ([`api.lib`](#apilib)) and its `on` hearing `pack_live`, a command's `studio:` frontmatter, and `testing.scratch_home`,
  `testing.studio`, `testing.pack_module` and the pack's own `tests/test_*.py` in `halo pack test`; all stable;
  deprecates nothing. A 1.0 or 1.1 pack keeps everything (`{min: "1.0"}` and `{min: "1.1", max: "1.9"}` take 1.2).
- **1.1** (Halo 3.3.10.0): adds `set_mode` and `current_mode` (a pack's runtime mode) and the manifest's
  `contributes.policy` and `contributes.modes` ([Policy hooks](#policy-hooks): draft in R1, stable from R2, which
  enforces each verdict and adds the post-call verdict, `after: true` -> pass | redact | drop), and (R3) the bundle
  panel's `api` calls `publish`, `on`, `getData`, `mode`, `attention` and `route`, and (Halo 3.3.11.0) the manifest's
  `contributes.setup` ([Setup blocks](#setup-blocks), stable), (Halo 3.3.12.0 R2) the manifest's `contributes.themes`
  ([Themes](#themes), stable), and (3.3.12.0 R4) `testing` (a pack's tests, what `halo pack test` runs) and the
  `requires:` tool entries ([Requirements](#requirements)), both stable; deprecates nothing. A 1.0 pack keeps everything: `{min: "1.0"}` and `{min: "1.0", max: "1.9"}` take 1.1, and a pack
  without `policy` and `modes` reads and runs exactly as before. (A pack that says `max: "1.0"` asked for 1.0 only
  and gets the one compatibility line.)
- **1.2** (Halo 3.3.13.0 R3): adds `remote` (the transport seam, [Transports](#transports)), the manifest's
  `contributes.services` and the grant `services` ([Services](#services)), a pack command's `run:` frontmatter (a
  program of the pack, no model call), and `halo pack test` running the pack's own `tests/test_*.py`; all stable;
  deprecates nothing. A 1.0 or 1.1 pack keeps everything: `{min: "1.0", max: "1.9"}` and `{min: "1.1"}` take 1.2.
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

Status: **stable** (3.2.0.0 R6). Halo ships three packs: **Documentation
Review**, (3.3.10.0 R3) **Concord**, the second reference example, the one
that shows a policy hook and a mode on a real tool ([PACKS.md](PACKS.md#the-concord-pack)), and (3.3.13.0 R2) **Design**,
the Design section out of the core: the example of [a section's view](#a-sections-view), [`api.lib`](#apilib),
[a pack's own routes](#a-packs-own-routes) and [the host services](#the-host-services)
([its README](../halo_harness/templates/packs/design/README.md)).
Documentation Review, at `halo_harness/templates/packs/doc-review/`, is the reference a
third party copies, and the regression test of this whole page
(`tests/test_reference_pack.py` installs it in a fresh home, runs its
workflow, finds it in Studio and Roles with its capability, removes it and
finds nothing of it left; every packs test reads it too). What it shows:

| Part of the API | In the pack |
|---|---|
| The manifest | `pack.yaml`: `halo_api: {min: "1.4", max: "1.9"}`, `halo` (the Halo it ships in: `{min: "3.2"}` from the 3.2.0.0 release), settings schema and defaults, permissions, one migration note |
| Agents and teams | `agents/reviewer.yaml` (by capability, a memory namespace, a need), `agents/writer.yaml` (extends it, a family preference), `teams/review.yaml` (two tiers, acceptance, its workflow) |
| Skills, commands, hooks and MCP | `skills/check-links/`, `commands/review.md`, `agents/helper.md`, `hooks/` (a PostToolUse hook publishing review.done), `.mcp.json` + `mcp/lint_server.py` (a stdio MCP server: check_links, check_headings); both started with `${halo_python}`, Halo's own Python (3.2.0.0 R7) |
| Studio contributions | a section (markdown, table, links, the artifact panel, Settings), a Session panel, a palette line, event lines, an attention row kind |
| Pack capabilities | `docs.review` (a model with tools, the bash grant, two at once), an inspector line |
| Workflow contracts | `workflows/review.yaml`: read each Markdown file, judge (`gate: human`), write the report |
| Events and artifacts | `artifacts/review-report.json` (`x-halo-view: table`), `events/review.done.json` |

Its `README.md` is the third-party guide: every file in one line, the API
version, how to install from a folder or a git url (or by id from a
`packs.sources` folder: `halo pack sources add`), how to check a pack with
`halo pack inspect` and `halo pack doctor`. `halo pack install doc-review`
finds it: the shipped folder is the last entry of the sources search, after
`packs.sources`. The failure fixtures stay under `tests/fixtures/packs/`
(`wf-cycle/`, `wf-unknown-role/`, `wf-no-giver/`, `wf-input-type/`, the
studio and capability ones) with `tests/fixtures/workflows/report-bad.json`, an
artifact off its schema. 3.2.0.0 R7 adds one per lifecycle failure
(`tests/test_packs_failures.py`): `bad-yaml/`, `no-id/`, `bad-id/`,
`api-too-new/`, `api-too-old/`, `halo-too-new/`, `needs-base/` (a missing
dependency) and `cycle-a/` with `cycle-b/`; docs/PACKS.md "When a pack cannot
run" lists the line each one gets.
