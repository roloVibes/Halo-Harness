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

The bio and lineup names are `<id>--<name>`, not `<pack>/<name>` (3.2.0.0
R2 decision): a `/` breaks the bio and lineup name rule
(`^[A-Za-z0-9][A-Za-z0-9_-]*$`), so a slash name could not be a file name, a
route target, a memory folder or a `tools.mcp_servers` entry. An id holds no
`--` and does not end in `-`, so `doc-review--reviewer` splits one way only.

## A pack's bios

A pack's `agents/<name>.yaml` is a bio in the same schema as yours
([AGENTS.md](AGENTS.md)): the sections `models`, `tools`, `context`,
`limits`, `output`, `environment`, `acceptance` are read as written. What a
pack's bio says that yours usually does not:

- `models.capabilities: [<tag>, ...]`: what the model must do, never which
  provider runs it. At load the bio runs on the best model in your catalog
  carrying every tag (a model of the family `models.preference` names
  first, then the higher price tier, then the larger window); when none
  does, it runs on your `default` model and `halo pack doctor`, `halo pack
  inspect` and the card in Studio say "no model in the catalog has
  <tags>". The tags: `long-context` (200k tokens or more), `vision`,
  `audio`, `video`, `files`, `image-out`, `tools`, `local`.
- No provider: `models.provider`, or a `models.preference` /
  `models.fallback` with a route prefix (`or:`, `ant:`, `dbx:` ...), a
  `vendor/model` path or a Databricks endpoint name, is a manifest problem
  naming the file and its line (`halo pack install` refuses the pack). A bare
  family name (`claude-sonnet`) may stay in `models.preference`.
- `context.memory.namespace` (the field your bios have too; default: the
  pack's id) is the pack bio's own memory: the folder
  `~/.halo/packs/.data/<id>/memory/<namespace>/`. Recall keys every note by
  its file, so a pack bio's recall reads that folder only, never yours or
  another pack's, and your own recall leaves every pack's folder out. A team
  member running the bio is told the folder.
- `tools.needs: [bash, network, home-write, mcp:<server>, hooks]`: the grants
  the bio uses. Each one is in pack.yaml's `permissions` (else a manifest
  problem). A need you have not granted does not stop the bio: it loads, and
  `halo pack doctor` (and the card in Studio) names
  `halo pack enable <id> --grant <need>`.
- `tools.permission_mode` and allow rules are read as written, as a project
  bio's are: permissions stay the rules you set and the grants you give.

One full example (the fixture `tests/fixtures/packs/doc-review/`):

```yaml
# agents/reviewer.yaml -> the bio doc-review--reviewer
name: reviewer
description: Reads a document and lists what is unclear, wrong or missing, one finding per line.
kind: reviewer
models:
  capabilities: [long-context]   # the best catalog model with a 200k+ window; else your default
  effort: high
tools:
  allow: [Read, Grep, Glob, Bash]
  deny: [Edit, Write]
  needs: [bash]                  # pack.yaml requests bash; halo pack enable doc-review --grant bash
context:
  memory: {namespace: reviews}   # ~/.halo/packs/.data/doc-review/memory/reviews/
output:
  handoff: summary
```

`agents/writer.yaml` says `extends: reviewer` (the pack's own reviewer) and
`models.preference: claude-sonnet`: it inherits the tags and prefers a
Sonnet with them.

## A pack's lineups

A pack's `teams/<name>.yaml` is a lineup in the same schema as yours
([ROLES.md](ROLES.md)): `delegation`, `routing`, `budget`, `escalation`,
`context`, `permissions`, `pipeline`, `tiers` as written. Members name the
pack's bios by their short names (`agent: writer`); Halo qualifies them.
Two keys more:

- `workflows: [<name>, ...]`: the pack workflows the lineup runs (3.2.0.0 R5
  runs them). Each name is one pack.yaml declares under
  `contributes.workflows`; a stray one is a manifest problem naming the line.
- `acceptance` holds the smoke prompt `halo doctor --teams` runs (`prompt`,
  `expect`) and the Orchestra defaults a run on this lineup starts with:
  `test` (the command the gate runs) and `review: true` (pause after the split
  for the plan's review). `halo orchestra new --lineup doc-review--review`
  takes them when you give no `--test`; what you type wins.

```yaml
# teams/review.yaml -> the lineup doc-review--review
agents:
  - {agent: writer, role: main}
  - {agent: reviewer, role: reviewer}
tiers:
  - {name: lead, members: [main]}
  - {name: checks, members: [reviewer]}
acceptance: {review: true, test: python -m pytest -q}
workflows: [review]
```

## Yours first

A bio or lineup of yours (`~/.halo/agents/`, `~/.halo/teams/` or the repo's
`.halo/`) never loses to a pack's. The names cannot collide unless a file of
yours is named `<id>--<name>`: then yours is the one used everywhere (also as
the parent of a pack bio that `extends` it), `halo agents list` / `halo teams
list` print the pack's under its group as "shadowed by
~/.halo/agents/<id>--<name>.yaml", Studio's row says "shadows pack <id>", and
`halo pack doctor` names it.

## In Studio's Roles

The Lineups and Bios panels group by where each one lives: **yours**,
**project**, one **pack <id>** box per pack that runs here, **shipped**,
each a labeled box, an empty one collapsed. A disabled pack has no box. A
pack's row offers:

- **Preview**: the lineup on the canvas (or the bio in the form), read-only;
  the Inspector says "from pack <id>, read-only".
- **Clone**: a copy in your scope named `<name>` (the `<id>--` dropped),
  with a `from_pack: <id>@<version>` line; a lineup's members stay the
  pack's bios. When a file of yours has that name, or Halo ships one
  (`reviewer`), Studio asks first: replace it, or pick another name. Nothing
  of yours is written without that answer.
- **Customize**: Clone, then the copy opened to edit.
- **Apply** (lineups): the Apply dialog, naming the pack and the lineup it
  replaces as the one new sessions use. It writes `~/.halo/config.json` only.

## In Studio

A pack may add to Studio what its `pack.yaml` declares under
`contributes.studio` ([EXTENSION_API.md](EXTENSION_API.md#studio-contributions)
has the shape); Studio draws all of it with its own components, and all of it
goes the moment you disable the pack (no reload):

- **Its own sections**, after Orchestra: the tab strip and the rail show them
  after a thin "packs" divider, on Alt+7, Alt+8 and Alt+9 (the six sections
  keep Alt+1..6). The doc-review fixture's is **Docs review**: its notes (a
  markdown page of the pack), its checks (a table over a JSON file), links
  (into Studio, or a page in a new tab) and Settings.
- **Panels in a core section**, under that section's own, as strips: the
  fixture's **Reviews** sits in Session. Each pack panel's title bar says
  "from pack <id>", and `?` (or the ... menu's Help) shows the pack's own help
  lines.
- **Palette lines** in their own group, "pack <id>": the fixture's "Open the
  review checks" opens Docs review on the Checks panel.
- **Settings**: with `config_form: true`, a form of the pack's
  `config.schema` (a field per key, its description as the help line). Save
  checks the values and writes `packs.settings.<id>` in `~/.halo/config.json`,
  the same key `halo config set packs.settings.<id>.<key>` writes.
- **Its live lines**: what the pack publishes (`publish_event`) shows in
  Session's Live column, Fleet's Activity and the pack's events panels with the
  pack's label and line, `REVIEW  README.md: 3 findings`.
- **Its attention rows**: a row the pack raises shows in Attention with the
  pack's label and keys (`review`, A accept, R redo, S skip, O open) and is
  answered there like any row.
- **A bundle**: a panel the pack draws with its own script. It runs only once
  you grant `studio-script`; until then the panel is one line naming the
  command:

```
This panel is studio-bundle's own script (studio/hello.js). It runs once you grant it:
halo pack enable studio-bundle --grant studio-script
```

## In the fleet

A pack may bring worker capabilities to your fleet: what its `pack.yaml`
declares under `contributes.fleet`
([EXTENSION_API.md](EXTENSION_API.md#fleet-capabilities) has the shape). Each
capability is a name from the pack's `capabilities:` with what it requires of
a host (tools, runtimes, the platform, a GPU or RAM, a model by tag, the
grants it needs, where its data must be). Once the pack runs here:

- **The catalog** lists each one, available here or not and why: `halo fleet
  capabilities` has a `packs` row, Studio's Capabilities card a "packs" line
  (`docs.review · pack doc-review · 2 at once · available: tools: <model>;
  bash granted`), the map's chips count them (`+1 pack cap`).
- **Who can**: `halo fleet who docs review` (and Studio's Who box) finds the
  harness whose pack has it; one listed as not available there counts half
  and says why.
- **Missions**: the lead sees each harness's pack capabilities and which one
  only one harness has; a part that names one in `needs` goes only to a
  harness where it is available (its pack runs with the grants), and the
  plan says "docs.review · pack doc-review on <harness>". Selected, the part
  shows the pack's inspector lines (its own markdown or JSON files).
- **The worker checks again**: before the part runs, the harness that got it
  reads its own packs; if the pack is disabled there, or a grant is missing,
  the part is refused with one line, "this harness does not run pack
  doc-review with bash", and the mission goes on as it does when a harness
  drops out.
- **Mission metadata**: a mission started with the pack's lineup (the active
  one, or `lineup:` in the request) carries the pack's `mission.metadata`.

What a pack advertises never holds a secret, an environment reference or a
path: the manifest refuses the first two (and a path in a description), and
the catalog cuts every other path to its last part before anything leaves
the machine. `halo pack inspect <id>` lists the capabilities with available /
why in its "contributes:" block (with the Studio contributions), and
`halo pack doctor` has a row for each one not available here.

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
`bash`, `network` and `home-write` for its own code and its bios' `tools.needs`. Nothing it asks for runs
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
