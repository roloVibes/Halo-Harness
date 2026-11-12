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
  `audio`, `video`, `files`, `image-out`, `tools`, `local`, and (3.2.1.0
  R1, from the catalog rows 3.1.9.0 enriched) `reasoning` (the row's
  reasoning kind is `native` or `openai`, not `none`), `open-weights` (the
  row says `open_weights: true`) and `audio-out` (`audio` among the row's
  output modalities). `local` is the row's own `local` when it states one
  (a Hugging Face router row is remote); only a row without the key is
  local by its provider (Ollama, Hugging Face).
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

One full example (the reference pack Halo ships, `halo_harness/templates/packs/doc-review/`):

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

- `workflows: [<name>, ...]`: the pack workflows the lineup runs. Each name
  is one pack.yaml declares under `contributes.workflows`; a stray one is a
  manifest problem naming the line. A workflow's compiled run uses the
  lineup that names it (its goal's `lineup`, [Workflows](#workflows)).
  3.2.1.0 R2: an item may also be written `<id>/<name>`, the way `halo
  workflow run` names it (`doc-review/review`); a bare name resolves inside
  its own pack, and another pack's `<pack>/<name>` is a manifest line ("a
  pack's lineup runs its own"). See [A lineup's workflows](#a-lineups-workflows).
- `acceptance` holds the smoke prompt `halo doctor --teams` runs (`prompt`,
  `expect`) and the Orchestra defaults a run on this lineup starts with:
  `test` (the command the gate runs) and `review: true` (pause after the split
  for the plan's review). `halo orchestra new --lineup doc-review--review`
  takes them when you give no `--test`; what you type wins. 3.2.1.0 R1: so do
  `halo goal add --lineup` ([SUPERVISE.md](SUPERVISE.md)) and Studio's
  Orchestra goal form (it says "test from the lineup: <command>").

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

### A pack's squares

Halo 3.3.16.0 R3. A pack's workflow is a **square** when its file says what it
`gives` at its root ([WORKFLOWS-squares.md](WORKFLOWS-squares.md)): the main
agent's `Workflow` tool can hand it a task once a lineup enables
`<pack>/<name>`. The contract is checked with the manifest, one line per bad
value naming the key and its line (`workflows/review.yaml line 9: covers
'pdfs' is not a need a square covers (...)`), and `halo pack test` adds a
`square <pack>/<name>` check for each: `gives` present, the `covers`,
`takes` and `gives` words known. A pack's square is read-only in Studio;
`halo workflows new <name> --from <pack>/<name>` copies it into yours.

### A lineup's workflows

A lineup's `workflows:` names workflows by `<pack>/<name>` (3.3.16.0 R3: or a bare
square name of yours, the project's or shipped; the list is the lineup's enabled
squares), the ref `halo
workflow run` takes (`<pack>--<name>` reads the same). The rule (3.2.1.0 R2,
`packs/lineup_run.py`):

- a bare name resolves inside its own pack: a pack's lineup's own, or the pack
  a clone of yours came from (`from_pack: doc-review@1.0.0`, which Studio's
  Clone writes);
- a lineup of yours may name any pack's workflow as `<pack>/<name>`; a ref no
  running pack holds is one `halo teams validate` line, in `halo workflow
  run`'s own words:

```
"workflows" 'other-pack/flow': pack other-pack is not installed here (halo pack list)
```

- the resolved lineup keeps `workflows` as written and carries
  `workflow_refs` beside it (`["doc-review/review"]`); `halo teams show`
  prints them, `workflows: doc-review/review (halo workflow run
  doc-review/review)`, and names a bare name of yours with no pack ("names no
  pack: a lineup of yours names <pack>/<name>").

## Yours first

A bio or lineup of yours (`~/.halo/agents/`, `~/.halo/teams/` or the repo's
`.halo/`) never loses to a pack's. The names cannot collide unless a file of
yours is named `<id>--<name>`: then yours is the one used everywhere (also as
the parent of a pack bio that `extends` it), `halo agents list` / `halo teams
list` print the pack's under its group as "shadowed by
~/.halo/agents/<id>--<name>.yaml", Studio's row says "shadows pack <id>", and
`halo pack doctor` names it.

Yours first holds for a pack you write too: start it with the pack kit (3.3.12.0 R4), not a copy of a shipped pack.
`halo pack new <id> --kinds ...` writes a pack that works, `halo pack test .` checks it against fakes, and `halo pack
install . --link` makes the installed pack your folder, so an edit shows at once ([PACK-AUTHORING.md](PACK-AUTHORING.md),
[COMMANDS-packs-kit.md](COMMANDS-packs-kit.md)).

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

- **Its own sections**, after the core sections: the icon rail shows them
  after a thin divider, each with the diamond (3.3.2.0), reached by a click or the palette
  (3.3.13.0 R2: the nine core sections hold `Alt+1` to `Alt+9`, Packs the sixth, Setup the seventh, Settings the
  eighth, Local the ninth, and the first pack section takes `Alt+0`). The doc-review pack's is **Docs review**: its notes (a
  markdown page of the pack), its checks (a table over a JSON file), links
  (into Studio, or a page in a new tab) and Settings.
- **Panels in a core section**, under that section's own, as strips: the
  pack's **Reviews** sits in Session. Each pack panel's **?** (or `?`, or the
  ... menu's Help) says "from pack <id>" first, then the pack's own help
  lines.
- **Palette lines** in their own group, "pack <id>": the pack's "Open the
  review checks" opens Docs review on the Checks panel.
- **Settings**: with `config_form: true`, a form of the pack's
  `config.schema` (a field per key, its description as the help line). Save
  checks the values and writes `packs.settings.<id>` in `~/.halo/config.json`,
  the same key `halo config set packs.settings.<id>.<key>` writes.
- **Its live lines**: what the pack publishes (`publish_event`) shows in
  Session's Live column, Agents' Activity and the pack's events panels with the
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

- **A page of its own** (3.3.13.0 R2, extension API 1.2): a section the pack draws whole with its own module (a
  `view`), on Studio's own React and parts; it runs only once you grant `studio-script`, like a bundle panel. The
  design pack's Design section is one.
- **Its own routes** (3.3.13.0 R2): the pack's Python answering `/api/packs/<id>/<prefix>/...` inside Studio's
  server, only once you grant `studio-routes` ("runs this pack's Python inside Studio's server"). A route that fails
  is one line and a `halo pack doctor` row; disabling the pack, or taking the grant back, unloads it.

  Since 3.3.10.0 R3 the script can act, not only draw: publish the pack's own events (at most 20 writes in 10
  seconds), listen for them, read its data folder and its mode, raise an attention row, and take you to a section
  ([the bundle panel's `api`](EXTENSION_API.md#the-bundle-panels-api)).

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
  shows the pack's inspector lines (its own markdown or JSON files): read
  through the pack's file route when the pack runs on Studio's own harness,
  and (3.2.1.0 R3) from the text the member's catalog carries (the file's
  first 8 KB, paths cut) when it runs on a member.
- **Capacity is held** (3.2.1.0 R3): the lead reads `docs.review (pack
  doc-review, 2 at a time)`, and the hub starts at most `capacity.parallel`
  parts holding that capability on one harness at once; the next one waits
  ("part 3 waits: bob@member runs 2/2 of pack doc-review: docs.review") and
  starts when one ends.
- **The worker checks again**: before the part runs, the harness that got it
  reads its own packs; if the pack is disabled there, or a grant is missing,
  the part is refused with one line, "this harness does not run pack
  doc-review with bash". (3.2.1.0 R3) The hub re-plans it once onto another
  harness that has the capability ("part 1 replanned: bob@member refused
  (...); alice@hub has pack doc-review: docs.review"); with none, the
  mission goes on as it does when a harness drops out.
- **Hidden**: `fleet.capabilities.hide` names a pack capability as it names
  a tool (`docs.review`, or `doc-review/docs.review` for this pack's only):
  the catalog leaves it out, so no part is planned onto it here; `halo pack
  doctor` counts the hidden ones and `halo pack inspect` marks them
  (3.2.1.0 R3).
- **Mission metadata**: a mission started with the pack's lineup (the active
  one, or `lineup:` in the request: `halo fleet mission new --lineup
  doc-review--review`, the Mission panel's Lineup select, 3.2.1.0 R1)
  carries the pack's `mission.metadata`, and the mission says the lineup.

What a pack advertises never holds a secret, an environment reference or a
path: the manifest refuses the first two (and a path in a description), and
the catalog cuts every other path to its last part before anything leaves
the machine. `halo pack inspect <id>` lists the capabilities with available /
why in its "contributes:" block (with the Studio contributions), and
`halo pack doctor` has a row for each one not available here (and one row
per pack saying how many `fleet.capabilities.hide` hides, 3.2.1.0 R3).

## Workflows

A pack may ship workflows, `workflows/<name>.yaml` named in
`contributes.workflows` ([WORKFLOWS.md](WORKFLOWS.md) is the guide,
[EXTENSION_API.md](EXTENSION_API.md#workflow-contracts) the contract). A
workflow names its prerequisites, typed inputs and outputs, and stages
(sequential with `after`, parallel without, one job per file with
`for_each`), each with its role (a bio of the pack), its conditions, gate,
retries, timeout, budget and checks. Halo compiles it to an Orchestra run:

```sh
halo workflow list                                        # the workflows of the packs that run here
halo workflow check doc-review/review --input docs=docs   # the jobs it compiles to, or every problem
halo workflow run doc-review/review --input docs=docs     # run it now (an Orchestra run)
```

The goal form (Live's Run a goal panel, 3.4.0.0 D; Orchestra's new-run form before) has a picker too (3.2.1.0 R2): with no workflow
filled in, "or run a pack's workflow" under the goal form lists the workflows
of the packs that run here, and a pick fills in the same form the Pack
Manager's Run <workflow> does ([STUDIO-orchestra.md](STUDIO-orchestra.md)).

What holds a workflow's run to its file (3.2.1.0 R2):

- **`gate: human` is the plan review before the run starts.** Any stage with
  it makes the whole compiled goal `plan: review` (`workflows/compile.py`):
  the run waits for `halo orchestra approve` (or Studio's plan) once, before
  any stage. A hold before one stage, after the run started, is not a thing
  yet ([plans/ROADMAP.md](../plans/ROADMAP.md) "After 3.2.1.0").
- **The workflow's own `budget_usd` is a stop**, in a plain Orchestra run as
  under `--as goal`: before each pass of any stage's worker the run's spend
  (the lead's split, every lane, the judge's conflicts, as the report counts
  it) is checked against it, and at it the run stops with `STOP: budget: the
  run spent <spent> of <cap> USD (the workflow's budget_usd)`. The report says
  the cap and the spend (`budget: the run spent 0.0400 of 2.0000 USD (the
  workflow's budget_usd, a stop)`). A workflow with no `budget_usd` of its own
  has no run-level stop; each stage's own `budget_usd` holds that stage.
- **The stage set is the file's.** The supervisor's replanner leaves a
  workflow run alone: it is never paused for a replan, and with
  `supervise.replan` set the goal says so once, "a workflow run keeps its
  stage set (its plan is pinned by doc-review/review)"
  ([SUPERVISE.md](SUPERVISE.md#replanning)).
- **The gate reads a stage's evidence.** Each `verify.evidence` item is a line
  under its lane in the gate's verdict and the report (`evidence report: 213
  bytes, sha256 3f9a1c0b7d2e`, or `evidence report: missing`), and the
  conflict judge reads the incoming lane's ([OUTCOMES.md](OUTCOMES.md#the-judge-reads-the-evidence)).

A typed output (`artifact:<schema>`) is checked against the pack's
`artifacts/<schema>.json` at the gate and drawn by its schema's view in the
pack's section (a panel of kind `artifact`) and in Orchestra's Report panel.
A pack's event kinds may carry a schema (`events/<kind>.json`): a
mismatching event goes out with its problems, a disabled pack's is refused,
and a bio's trigger or a stage's `after_event` can wait for one. Its memory
notes carry their provenance (`ext.memory.write`; recall reads a namespace
and what other packs share with it). A bad workflow file is one manifest
line naming the key and its line, so the pack does not run until it is
fixed; `halo pack inspect` lists the workflows, artifact schemas and event
schemas in its "contributes:" block.

## Where packs live

- `~/.halo/packs/<id>/`: yours, for every repo (`halo pack install <path|git url>`).
- `<repo>/.halo/packs/<id>/`: this repo's (`--project`). A repo's pack is the
  untrusted layer: its lineups lose `permissions.mode` and allow rules, the
  way a repo's own lineup does in a folder you have not trusted. A repo's
  pack with the same id as one of yours is the one used (doctor says so).
- `~/.halo/packs/state.json`: which packs are installed, from where, enabled
  or not and what you granted (private, 0600). What Halo reads of the packs
  is kept until a pack.yaml, a `*.yaml` / `*.md` in a pack's `agents/`,
  `teams/` or `workflows/`, or state.json changes (3.2.1.0 R1): an edit you
  make by hand inside an installed pack's bios shows at the next lookup
  (a bio that now names a provider takes the pack out, and `halo pack
  doctor` names the line). A pack is enabled for the
  folder you enabled it in, so a same-id pack in another repo stays off.
- `~/.halo/packs/journal.jsonl`: every file an install, update, rollback or
  remove wrote or deleted, with its hash: how Halo knows which files are the
  pack's; and each settings rename an update made (3.2.0.0 R7).
- `~/.halo/packs/<id>.previous/`: the version the last update replaced, for
  `halo pack rollback` (3.2.0.0 R7); never discovered as a pack.
- `~/.halo/packs/.data/<id>/`: the pack's own place to write (3.3.13.0: a pack service's health file and log
  live here; the signal pack keeps its account, phones and audit here).
- Settings: `~/.halo/config.json` under `packs.settings.<id>`, checked
  against the schema in the pack's `pack.yaml` (`halo config set
  packs.settings.doc-review.style long`).

## The lifecycle

1. `halo pack inspect ./doc-review` reads a pack folder before you install it:
   what it offers, what it requests, its problems.
2. `halo pack install ./doc-review` (or a git url) checks everything first,
   then copies every file through the journal. Nothing is overwritten: a
   folder already at `~/.halo/packs/doc-review/` is left as it is. Installing
   a pack that is installed already: the same version says "already
   installed: nothing to do" and exits 0; another version says so with
   `halo pack update <id>` and exits 1 (3.4.1.0). 3.4.1.2: a bare id (`halo pack install coach`, Studio's Install
   on a card) is the pack Halo ships by that id, else the first `packs.sources` entry holding it -- never a folder of
   the current directory (`./coach` names one); a source holding an id Halo ships does not shadow it (one line says
   so; `halo pack install <id> --from <source>` takes that source on purpose).
5a. A pack installed from the packs Halo ships (`halo pack install fleet`)
   does not move by itself when `halo update` brings a newer Halo: when this
   Halo ships a newer version, `halo pack list`, `halo pack inspect`, `halo
   pack doctor`, `halo doctor`, Studio's Packs ("1.0.2 available") and the
   end of `halo update` say it in one line with `halo pack update <id>`
   (3.4.1.0).
3. `halo pack enable doc-review --grant mcp:lint --grant hooks` turns it on.
4. `halo pack disable doc-review` turns it off: nothing of it runs, its
   files stay, its grants clear.
5. `halo pack update doc-review` brings in the new version from where it was
   installed from: its migration notes first, any file you changed kept, the
   old version kept for `halo pack rollback doc-review` (below).
6. `halo pack remove doc-review` removes it (below).

`halo pack doctor` (and the packs group of `halo doctor --config`) lists
every problem in one line each.

## Updating and rolling back

3.2.0.0 R7. Try an update first; nothing changes until you run it:

```
$ halo pack update doc-review --dry-run
doc-review 1.1.0 -> 1.3.0: settings key `lint.level` is now `lint.strictness`
would update doc-review 1.1.0 -> 1.3.0 (4 file(s) changed; 1.1.0 kept as doc-review.previous)
  agents/reviewer.yaml (changed)
  pack.yaml (changed)
  skills/check-links/SKILL.md (changed)
  studio/notes.md (changed)
would rename packs.settings.doc-review.lint.level to lint.strictness (your value 'high')
dry run: nothing is changed (halo pack update doc-review makes these changes)
```

3.2.1.0 R4: run in a terminal, `halo pack update doc-review` shows the same
lines (the notes, the files that change, the settings it renames, your files
it keeps) and asks before it changes anything:

```
$ halo pack update doc-review
doc-review 1.1.0 -> 1.3.0: settings key `lint.level` is now `lint.strictness`
would update doc-review 1.1.0 -> 1.3.0 (4 file(s) changed; 1.1.0 kept as doc-review.previous)
  ...
Apply? [y/N] y
updated doc-review 1.1.0 -> 1.3.0 (4 file(s) changed); 1.1.0 is kept as doc-review.previous (halo pack rollback doc-review)
```

`n`, Enter or the end of input leave the pack as it is (`doc-review 1.1.0
stays as it is`, exit 1). `--yes` skips the question; `--json`, `--dry-run`
and a run that is not in a terminal (a pipe, a script, CI) never ask, as
before. The look and the swap read the same fetched source, so what you are
shown is what goes in. The Pack Manager's Update confirm in Studio is the same
look: it shows these lines and Update runs the update.

Then (after `y`, with `--yes`, or at once where nothing asks) the update puts
the new version in place in one step: it is staged beside the pack (with every file
of yours from the pack's folder carried over) and swapped in by two renames,
so a copy error or a file in use leaves the old version exactly as it was
(`update of doc-review stopped: <why>; 1.1.0 stays as it was (nothing was
replaced)`). The old version is kept as `~/.halo/packs/doc-review.previous/`,
the `settings` renames the pack declares are made in your
`packs.settings.doc-review` (a key you already set under the new name wins),
and your grants stay. A permission the new version asks for that the old one
did not is listed (`halo pack grant doc-review network`) and stays a doctor
line until you grant it.

Changed your mind? `halo pack rollback doc-review` swaps `doc-review.previous`
back, moves the renamed settings back, keeps your grants (and a file you
changed since the update), and deletes the version rolled back from; `halo
pack update doc-review` brings it back again. Halo keeps one version back,
and that is the rule: `<id>.previous` is the one version kept, the next
update replaces it, and there is no version history on disk (to go back
further, install the version you want from its folder or url). `halo pack
remove doc-review` deletes it too; with `--keep-config` it stays beside the
record and `halo pack rollback doc-review` installs it again. In Studio,
"Roll back to <version>" appears once an update kept one
([STUDIO-packs.md](STUDIO-packs.md)). The procedure, step by step, is in
[EXTENSION_API.md](EXTENSION_API.md#updating-a-pack).

## When a pack cannot run

Each problem is one line, the same in `halo pack`, `halo pack doctor` and
Studio's Pack Manager (Details and the last action's lines). What each says
and what to do:

| What happened | The line | What to do |
|---|---|---|
| pack.yaml is not YAML | `bad-yaml: pack.yaml: it does not read as a YAML mapping (key: value)` | fix the file (`halo pack inspect <folder>` reads it again) |
| no id, or a bad one | `no-id: pack.yaml: id: required`; `Doc_Review: pack.yaml: id 'Doc_Review' is not a pack id: ...` | give it an id of lower-case letters, digits and single hyphens |
| any other manifest problem | `<id>: pack.yaml: <the key and what is wrong>` (an unknown key names the closest) | fix pack.yaml; the pack installs and runs once it validates |
| written for a newer extension API | `pack <id> needs extension API 1.3 to 1.9; this Halo has 1.2` | update Halo, or install an older version of the pack |
| written for an older extension API | `pack <id> needs extension API 0.5 to 0.9; this Halo has 1.2` | install a newer version of the pack (its author widens `halo_api`) |
| needs a newer Halo | `pack <id> needs Halo >= 9.0; this is 3.2.0.0` | update Halo |
| a required pack is missing | `<id> requires base-docs, which is not installed` | `halo pack install base-docs`, then enable it |
| a required pack is off or too old | `<id> requires base-docs, which is installed but not enabled (halo pack enable base-docs)`; `<id> requires base-docs 2.0 to 2.9; 1.4.0 is installed` | enable it, or update it |
| a requires cycle | `cycle-a is in a requires cycle: cycle-a -> cycle-b -> cycle-a` | the packs' authors break the cycle; disable one meanwhile |
| an install stopped half-way | `install of <id> stopped: <why>; every file it wrote is removed again` | fix the cause (the source moved, the disk is full) and install again |
| an update's new version is bad | `<id>: pack.yaml: ...` then `<id> 1.0.0 stays as it is` | nothing changed; wait for a fixed version, or `--dry-run` it later |
| an update stopped | `update of <id> stopped: <why>; 1.0.0 stays as it was (nothing was replaced)` | close what holds the pack's folder and update again |
| a bare id no source holds | `no pack <id> in the sources searched: <each source>, the packs Halo ships (halo pack sources add <folder\|git url>; a folder here is ./<id>)` | `halo pack sources add` the folder or url that holds it; a source that is gone says `(not a folder)` |
| the recorded source is gone | `<id>'s source <path> is not there any more; nothing is changed (...)` | install it again from where it is now |
| a new version needs a grant | `<id> 1.1.0 requests network, which 1.0.0 did not; it is not granted, so what needs it does not run` | `halo pack grant <id> network`, or `halo pack rollback <id>` |
| a grant not given | `<id>: MCP server lint does not run: mcp:lint is not granted` | `halo pack enable <id> --grant mcp:lint` |
| an API name going away | `<id>: <file> line N uses ext.<name>, deprecated since API 1.3; it goes away in API 2.0 (use ext.<other>)` | the pack's author moves to the new name before that version |
| nothing to roll back | `<id> has no earlier version to go back to: an update keeps the version it replaces as <id>.previous until the next update` | nothing kept: install the version you want from its folder |

The failure fixtures under `tests/fixtures/packs/` (`bad-yaml`, `no-id`,
`bad-id`, `api-too-new`, `api-too-old`, `halo-too-new`, `needs-base`,
`cycle-a`, `cycle-b`) produce these lines; `tests/test_packs_failures.py`
pins each one on the CLI and in Studio.

## A pack's own Python

3.2.0.0 R7. A pack's hook and MCP server name Halo's own interpreter as
`${halo_python}`; Halo expands it to the Python it runs in (`sys.executable`)
when it starts them, so the pack's code imports `halo_harness.ext` even
where the `python` on your PATH is another one (a `uv tool` install):

```json
{"mcpServers": {"lint": {"command": "${halo_python}", "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/lint_server.py"]}}}
{"hooks": {"PostToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "args": ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/hooks/note.py"]}]}]}}
```

Both hook forms work on Windows and Linux, in a pack's `hooks/hooks.json` and
in any Claude Code plugin's. In a hook's shell `command` (Git Bash runs it on
Windows, `/bin/sh` elsewhere) `${halo_python}` and `${CLAUDE_PLUGIN_ROOT}` go
in as that shell reads them (3.2.1.0 R4): forward slashes on Windows, quoted
when the path holds a space or another character the shell reads
(`${halo_python}` always), and escaped instead when you wrote the placeholder
inside your own `"..."` or `'...'`:

```
"command": "sh ${CLAUDE_PLUGIN_ROOT}/hooks/run.sh"
  Windows, the pack in D:\Tools\My Packs\lint  ->  sh 'D:/Tools/My Packs/lint'/hooks/run.sh
  Linux,   the pack in /opt/packs/lint          ->  sh /opt/packs/lint/hooks/run.sh
```

The exec form (`args`, no shell) gets both paths as they are and is the same
on every platform, so it stays the recommended one and the reference pack
uses it; `shell: "powershell"` gets the plugin root as it is too, and so does
the hook's `CLAUDE_PLUGIN_ROOT` environment variable. Every process started
from a pack's folder also gets `PYTHONPATH` with Halo's package root first, so a script run by
another Python finds `halo_harness.ext` as well. A plain Claude-plugin folder
(no pack.yaml) gets `${halo_python}` but not the PYTHONPATH.

## The Pack Manager

Studio's **Packs** section (`Alt+4`, 3.2.0.0 R6) runs the lifecycle above with
buttons, through the same code: each action runs the function `halo pack`
runs and shows the lines it prints, and every open Studio redraws on the
`pack_changed` it publishes ([STUDIO-packs.md](STUDIO-packs.md)).

- **Sources**: where a bare id is looked for: an id Halo ships is always the
  shipped pack (3.4.1.2); any other id, in order, the folders and git
  urls of `packs.sources` (Add source, Remove: `halo pack sources add|remove`). A pack not installed has Install (`--project`
  with "into this repo"). No marketplace: only what your config names and what
  Halo ships.
- **Installed**: every pack here, its state, the grants given of the ones it
  requests and the doctor's lines for it; Enable, Disable, Update (it shows
  the dry run's lines first, R7), Roll back to <version> (once an update kept
  one) and Remove (it asks first, naming `halo pack remove <id>` and `--keep-config`).
- **Details**: the extension API and Halo ranges beside this Halo's, each
  required pack and whether it is met, what keeps it from running here (in
  the doctor's words), each permission with a Grant toggle (an enabled pack:
  `halo pack grant <id> <name> [--off]` at once; a disabled one: picked for its
  Enable), what it contributes (`halo pack inspect`'s block) with links to its
  section, its lineup in Roles and its workflows, and its health.
- **Settings**: the pack's settings form, for a disabled pack too.
- **Templates**: its lineups and bios with Preview, Clone, Customize and Apply
  (Roles' own actions), and Run <workflow>: Orchestra's new-run form filled
  in with the workflow and its inputs; Run compiles it as `halo workflow run` does.
  Orchestra's Start view offers the same workflows in its own picker (3.2.1.0 R2).
- **Bundles** (3.3.7.0 R5, under Installed): every bundle here and the nine Halo ships, each a tick with its
  verdict line, its ways out and the one download button; [Bundles](#bundles) below.

## Bundles

A **bundle** (3.3.7.0 R5) is a pack with a resource claim: one more block in `pack.yaml`, `bundle:`, says what local
models it needs, the one it reserves while it is on, where the rest of the work goes and its latency budget (the
contract: [EXTENSION_API.md](EXTENSION_API.md#bundles)). Before anything downloads, its verdict says whether it is
ready, needs downloads (each tag with its size and fit, one button) or won't work (with the ways out, each a number);
only a ready bundle turns on, and while it is on nothing Halo does evicts the reserved model and its GB count in
every budget line. Halo ships nine in `halo_harness/templates/bundles/`: meta-glasses (voice), bulk-worker,
verifier, compactor, embeddings, translation, vision, offline-only and coder-first. Turning a shipped one on installs
it like any pack (into `~/.halo/packs/<id>/`), enables it (a bundle requests no permission) and claims its
reservation; off releases it and disables the pack. `halo pack verdict | on | off <bundle>`, `halo pack list
--bundles` ([COMMANDS-packs.md](COMMANDS-packs.md#bundles)); the arithmetic, the reservation and the routing are in
[MODELS-bundles.md](MODELS-bundles.md).

## Setup blocks

3.3.11.0 R3. A pack can add its own pages to Studio's Setup (`contributes.setup`,
[EXTENSION_API.md](EXTENSION_API.md#setup-blocks)): a form for its settings, a
check it runs, a note to read. They show while the pack is enabled, so a pack you
install after `halo init` says so when you turn it on: `halo pack enable <id>`
ends with a `setup: <id> -- <title> (halo setup <id>)` line per block still
waiting, `halo setup <id>` opens the first one in Studio, and `halo doctor` and
`halo pack doctor` keep an info row until each is done or skipped. A form writes
the pack's own settings only; a check runs with what a pack hook gets (never
Halo's provider keys); nothing of another pack is shown to it.

## Themes

3.3.12.0 R2. A pack can ship palettes of its own (`contributes.themes`,
[EXTENSION_API.md](EXTENSION_API.md#themes)). While the pack is enabled each
one is a theme like the ten Halo has, named `<pack-id>/<id>`
(`pack-theme/nightshade`, also `-daltonized` and `-ansi`): `/theme` lists it
under the pack's name, `/theme pack-theme/nightshade` draws the terminal in it
at once, and Studio's header menu and Settings -> Themes show it in a group
under the pack's id. Halo keeps the theme you had before you chose it; `halo
pack disable` or `halo pack remove` puts that one back and says so in one line
(`theme: pack-theme/linen was pack-theme's palette and the pack is disabled;
restored claude-dark`). Every pack palette meets the same contrast floors as
the ten; one that does not is refused at install with the pair and its ratio.

## Modes and policy hooks

A pack may declare **modes** and **policy hooks** (3.3.10.0; the contract:
[EXTENSION_API.md](EXTENSION_API.md#policy-hooks)). A policy hook is a command in the pack that Halo starts once and
asks about each tool call it names (`when.tools`), one JSON line in and one verdict out -- `allow`, `deny` or `ask`
with the pack's own reason -- within `packs.policy.budget_ms` (2000 ms); a mode is a switch that arms the policies
that name it. Both are recorded in the pack's `mode.json`, which `halo pack mode <pack> <mode> on | off` and `halo
pack policy arm | disarm` write, and `halo pack policy status` reads; `halo pack policy test` runs a verdict without a
session ([COMMANDS-packs.md](COMMANDS-packs.md#modes-and-policy-hooks)). A policy needs the `hooks` grant, and an
armed hook sees every matching tool input, a Write's content included, so read its `when.tools` and `redact` before
you grant it. A session asks the armed policies before each call they name (3.3.10.0 R2), sub-agents and
Orchestra workers included: a `deny` refuses the call with the pack's own line, which the model and you read
(`policy: deny -- fence: outside the project (pack policy-fence, rule outside-project)`); an `ask` shows the approval
card with that line; an `allow` leaves the call to your permissions as before. A policy with `after: true` also
sees the result and may pass it, redact it (the model sees the pack's version; the audit keeps the original's
sha256) or drop it. Every verdict is on the call's tool line (the TUI, Studio's Session feed, the transcript), on
the pack's row in the Pack Manager, and in `halo pack policy log`. With no pack armed nothing changes; a pack
without policies and modes is untouched.

## The reference pack

Halo ships six packs: **Documentation Review**, below, **Concord** ([The concord pack](#the-concord-pack)), **Signal**
([The signal pack](#the-signal-pack)), **Design** ([The design pack](#the-design-pack)) and (3.4.0.0) **First run**
([The first-run pack](#the-first-run-pack)) and **Coach** ([The coach pack](#the-coach-pack)).
**Documentation Review** (`doc-review`,
`halo_harness/templates/packs/doc-review/`): a reviewer and a writer bio, the
review lineup, the review workflow (read each Markdown file, judge the
findings, write one typed `review-report`), a Studio section with the last
review report, the `docs.review` fleet capability, and a skill, a command, a
hook and a lint MCP server. `halo pack list --available` shows it; `halo pack
install doc-review` installs it (3.4.1.2: a bare id Halo ships is always the
shipped pack; a pack of yours with that id installs with `--from <source>` or
by its folder, `./doc-review`); `halo pack enable doc-review --grant bash` turns it on; `halo workflow
run doc-review/review --input docs=docs` runs its review. Its `README.md` is
the guide to making your own pack from it: every file in one line, the API
version, installing from a folder or a git url, checking it with `halo pack
doctor`. `tests/test_reference_pack.py` installs it in a fresh home, runs its
workflow, finds it in Studio, Roles and the fleet catalog, removes it and
finds nothing of it left.

## The first-run pack

**First run** (`first-run`, `halo_harness/templates/packs/first-run/`, 3.4.0.0) is the guided first run, out of Halo's
core: `halo start` (one real Orchestra run that rehearses your lineup on a sample repo, its card first) and `/start`,
a row on Setup's Check page and a **First run** panel in Studio's Agents section (where "Start here" and "Test this
lineup" went), and one `halo doctor` row (ready, or what is missing first). `halo pack install first-run`, `halo pack
enable first-run --grant-all` (`cli:start` for the verb and the slash command, `doctor` for its row, `studio-script`
and `studio-routes` for the panel). With it off, `halo start` and `/start` say in one line that it is a pack now. It is
the example of the 3.4.0.0 draft parts ([CLI verbs, slash commands, doctor rows and settings
rows](EXTENSION_API.md#cli-verbs-slash-commands-doctor-rows-and-settings-rows), [core
access](EXTENSION_API.md#core-access)); [its README](../halo_harness/templates/packs/first-run/README.md) has the rest.

## The coach pack

**Coach** (`coach`, `halo_harness/templates/packs/coach/`, 3.4.0.0) is the post-run coach, out of Halo's core: `halo
coach` (a finished run's cards, Ask, Apply after one confirm, Undo, probes, the improvement library) and `halo improve`
(memory and rule candidates from recent sessions), `/coach` and `/improve`, a **Coach** panel in Studio's Agents section
(where the run report's Coach tab and the mission's Coach face went), seven rows in Settings under **From packs**
(`packs.settings.coach.<key>`) and one `halo doctor` row. `halo orchestra coach` and `halo fleet mission coach` hand over
to its verb. `halo pack install coach`, `halo pack enable coach --grant-all` (`cli:coach`, `cli:improve`, `doctor`,
`studio-script`, `studio-routes`). With it off each verb says in one line that the coach is a pack now, and the old keys
`coach.*` and `improve.*` are ignored. The supervisor, replanning and verified outcomes stay in the core; [its
README](../halo_harness/templates/packs/coach/README.md) has the rest.

## The design pack

**Design** (`design`, `halo_harness/templates/packs/design/`, 3.3.13.0 R2) is Studio's Design section, out of Halo's
core: projects of artboards made by a Halo turn with your ArtCraft apps as its tools, versions, comments, knobs, a
design system, exports and the handoff, and a ComfyUI render into a project. It ships with Halo and stays off until you
turn it on: `halo pack install design`, `halo pack enable design --grant-all` (`studio-script` for its page,
`studio-routes` for its routes), then the Design row of Studio's rail (`Alt+0` while it is the first pack section) or
`/design`. Its projects live in its data folder (`~/.halo/packs/.data/design/projects/`); a `~/.halo/design` from
before the pack is moved there once, with one line saying so. Disabling it takes the section away and leaves the
projects. [Its README](../halo_harness/templates/packs/design/README.md) has the rest; it is the example of every
extension API 1.2 part ([a section's view](EXTENSION_API.md#a-sections-view), [`api.lib`](EXTENSION_API.md#apilib),
[a pack's own routes](EXTENSION_API.md#a-packs-own-routes), [the host services](EXTENSION_API.md#the-host-services)).

## The concord pack

**Concord** (`concord`, `halo_harness/templates/packs/concord/`, 3.3.10.0 R3) lets a Halo session take part in a
repository's [Concord](https://github.com/Get-Concord-AI/concord-mcp) workspace: the shared record of who works on
what (tasks with the files they claim, hand-offs, messages between Claude Code, Codex, Cursor or Gemini sessions in
the same repo). It ships with Halo and stays off until you turn it on, and it is the first real consumer of the
policy hook. Concord's telemetry to getconcord.ai is on by default upstream; this pack turns it off
(`CONCORD_TELEMETRY_DISABLED=1` on the MCP server, every hook command and the policy's check).

- **Install Concord yourself**, once per machine: `npm install -g @concord-ai/concord-mcp` (Halo never downloads
  or installs it). In the repo, Concord's own `concord setup --no-mcp --no-adapters` creates its `.concord/` folder.
  Until `concord-mcp` is on PATH, `halo pack doctor` says so in one `not-on-path` row.
- **Turn it on**: `halo pack install concord`, `halo pack enable concord --grant hooks --grant mcp:concord`.
- **What it adds**: the `concord` MCP server (your `concord-mcp`, `CONCORD_REPO_ROOT` set to the project folder
  through `${CLAUDE_PROJECT_DIR}`, which Halo fills in for a pack's `.mcp.json`); Concord's Claude Code hook commands
  for UserPromptSubmit, PostToolUse, Stop and SessionEnd (message delivery and read receipts); the `coordinating`
  mode and its `claimed-files` policy: `halo pack mode concord coordinating on`, and a Write or Edit to a file an
  active Concord task claims is denied with the pack's line (`policy: deny -- claimed-files: concord: src/auth.py is
  claimed by task t-42 (pack concord, rule claimed)`). The policy runs `concord check <path>` (exit 1 = an overlap);
  a box without Concord blocks nothing (`on_error: allow`, and no `concord` on PATH is an allow).
- **Identity**: Concord tells agents apart by an id; Claude Code hands it a session id and Halo does not, so set
  `CONCORD_AGENT_ID` before starting halo, and `CONCORD_TASK=<your task id>` so your own claim is not counted
  against your own writes.
- **The live check** (the pack's `README.md` has it in full): a Halo session and a Codex session in one repo trading
  a prompt and a reply through Concord, and a Write to a file the Codex task claims getting the pack's line.

`tests/test_pack_concord.py` checks the manifest, the server's environment, the hooks and the policy against a fake
`concord` (never the real one).

## The signal pack

**Signal** (`signal`, `halo_harness/templates/packs/signal/`, 3.3.13.0 R3) is Halo on your phone through Signal, as a
conversation; until 3.3.13.0 it was the core's `halo remote signal` bridge. It ships with Halo and stays off until you
turn it on, and it is the first pack with a service and a command that runs a program.

- **Install signal-cli yourself** (GPL-3.0; Halo never installs it): the pack's `requires:` has the line for each OS,
  and Setup -> Signal's first block checks it.
- **Turn it on**: `halo pack install signal`, `halo pack enable signal --grant-all` (`services`), `halo setup signal`
  (link this computer to your Signal, or register a number; pair the phone), `halo supervise`.
- **What it adds**: the bridge as a service (`contributes.services`: `halo supervise` keeps it running, the Pack
  Manager's row has Start / Stop); `/signal` (a `run:` command: status, pair, phones, sign, home, off, on, url, test,
  link, register -- no model call); its Setup blocks; its settings (`packs.settings.signal.*`, the old `remote.*`
  keys' new home).
- **The conversation**: pairing in one six-word text; a text with no session starts one in the phone's home folder;
  the answer paragraph by paragraph; cards answered with a number, a letter or a thumbs up; pictures, PDFs and voice
  notes in, `/file` and `/shot` out; `/notify` for the attention queue's, the supervisor's and the steward's notes.
- **The live check** and the threat model are in the pack's `README.md`.

`tests/test_pack_signal.py` installs it in a scratch home and drives a whole conversation over real control sockets
through a stub transport; the pack's own tests (`halo pack test signal`) drive its parts through fakes (never the real
signal-cli, never a Signal message).

## Grants

A pack asks for what its contributions need: `mcp:<server>` for each MCP
server (and `network` for one reached by a url), `hooks` for its hooks,
`bash`, `network` and `home-write` for its own code and its bios' `tools.needs`, `hooks` for a policy hook
(3.3.10.0 R1), and `services` for a program the supervisor keeps running (3.3.13.0 R3). Nothing it asks for runs
until you grant it: an ungranted MCP server does not start, ungranted hooks
do not load, and doctor names each one with the command that grants it.
Grants add up across `enable` calls and live in state.json; `disable`
clears them.

What each grant gives is one line (`halo pack inspect`, the Pack Manager, `halo_harness/packs/grants.py`), said as it
is (3.4.1.2): `studio-script` runs the pack's code INSIDE Studio's page with Studio's own power -- it can do what you
can do in Studio, including starting sessions that run commands; `doctor`, `cli:<verb>` and `studio-routes` run the
pack's Python inside halo with your rights and Halo's keys; `services` and `hooks` run its programs with your rights
(they can read what you can, Halo's key file included). For a pack Halo does not ship, those grants need an explicit
yes: `--grant NAME` names it; `--grant-all` prints each line and asks once in a terminal (refused without one unless
`--yes`); the Pack Manager shows the lines and grants on Grant. Once any of them is given, `bash`, `network` and
`home-write` fence nothing: the pack's code runs as you. A real fence for a page's script (a sandboxed frame) is the
"Pack trust" item of the roadmap.

## Remove keeps your work

`halo pack remove <id>` deletes only the files the pack's install or update
wrote and that still hold what was written. It keeps, and lists:

- a file in the pack's folder you changed or added (the folder stays with them);
- your bios and lineups named `<id>--*` (a duplicate you made in Studio);
- your lineups that name the pack's bios;
- the lineups' memory and layout folders (`~/.halo/teams/<id>--*/`);
- your settings under `packs.settings.<id>` and a `team:` naming its lineup.

`--keep-config` also keeps the pack's record and grants, so installing it
again later starts where you left off. The version the last update kept
(`<id>.previous/`) is deleted with the pack; with `--keep-config` it stays
beside the record, and `halo pack rollback <id>` installs it again. A pack Halo found in place (a folder
you put there yourself) has no files of Halo's to remove: nothing in it is deleted.
