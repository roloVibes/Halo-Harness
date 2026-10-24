# Studio: the Pack Manager

Read this when you install, grant, enable, set up, update or remove packs from Studio's Packs section.

Part of [Halo Studio](STUDIO.md), which lists every part.

## Packs: the Pack Manager (3.2.0.0 R6)

Packs (`Alt+7`) is Studio's seventh core section, appended after the six,
which keep their keys. It is the place to find a pack, read what it brings and
asks for, and run its whole lifecycle -- install, grant, enable, settings,
templates, update, remove -- without a terminal. Every button runs the same
function `halo pack` runs ([COMMANDS-packs.md](COMMANDS-packs.md)) and the
lines it answers are the ones the terminal prints; an error is the
command's own line. Each change publishes `pack_changed` on the live feed, so
this page, every other open Studio and the section tabs redraw at once, and a
`halo pack` run in a terminal shows here within two seconds.

Packs come only from places you trust: the folders and git urls of
`packs.sources` in `~/.halo/config.json` and the packs Halo ships (the
Documentation Review reference pack). There is no marketplace.

### The panels

- **Installed**: one row per pack here (installed, or a folder Halo found in
  place): its id, name and version, its state (`enabled`, `disabled`,
  `enabled, not running`), how many of the permissions it requests are
  granted (`1/3 granted`), how many lines `halo pack doctor` has for it, and
  under the row the first thing that keeps it from running here. Its
  actions: **Enable** (with the grants picked in Details: `Enable (1 grant)`,
  the button's tooltip is the command), **Disable**, **Update**, **Roll back
  to <version>** and **Remove**. Update asks first (3.2.0.0 R7): its confirm
  shows what `halo pack update <id> --dry-run` prints -- the migration notes,
  the files that change, the settings it renames, your files it keeps -- and
  Update runs it; a refused update shows its lines instead. It is the same
  look `halo pack update <id>` prints in a terminal before it asks
  `Apply? [y/N]` (3.2.1.0 R4). Roll back (shown
  once an update kept the version before) runs `halo pack rollback <id>`.
  Remove asks first: what goes (the pack's own files), what stays
  (yours, each listed after), a "keep its record and grants" box
  (`--keep-config`) and the command it runs. Under the rows, the lines the
  last action printed.
- **Sources**: each place a bare id is looked for, in order -- your
  `packs.sources` entries (Remove takes one out), then the packs Halo ships
  -- with the packs each holds. A pack not installed has **Install**
  ("into this repo" installs into the repo's `.halo/packs/`); a click on its
  name shows it in Details before you install it. **Add source** takes a
  folder of packs, a pack's folder or a git url. A git url is cloned only
  when you install from it.
- **Details**: the selected pack, as `halo pack inspect` reads it: its
  description, author and license; the extension API and Halo ranges beside
  this Halo's; each pack it requires and whether that is met; **what keeps
  it from running here** in the doctor's words (an API or Halo range, a
  dependency missing or off, a fleet capability not available, with why);
  each permission it requests and what needs it, with a **Grant** toggle; what
  it contributes (the block `halo pack inspect` prints: its Studio section and
  panels, palette lines, settings form, event lines, attention rows, fleet
  capabilities, workflows, artifact and event schemas) with links that open
  its section, its lineup in Roles and each workflow's Run; and its health,
  the doctor's rows with their fixes.
- **Settings**: the pack's own form (R3's, one field per key of its
  `config.schema`). Save checks the values against the schema, then writes
  `packs.settings.<id>`. It works for a disabled pack too, so you can set a
  pack up before you enable it.
- **Templates**: what the pack lets you start from. Its lineups and bios
  with Roles' own actions: **Preview** (opens it in Roles, read-only),
  **Clone** (a copy in your files, with `from_pack`), **Customize** (Clone,
  then your copy opened) and **Apply** (a lineup becomes the one new
  sessions use; it asks first). Its workflows with **Run <name>**: Orchestra's
  Start view opens with the workflow's form filled in -- its ref, its stages,
  one field per input at its default -- and Run compiles it exactly as
  `halo workflow run` does (a missing input shows the compile's lines under
  the form). A pack's templates are read in place while it runs, so a
  disabled pack shows "Enable it first". Orchestra's own Start view lists the
  same workflows under its goal form, **or run a pack's workflow** (3.2.1.0 R2,
  [STUDIO-orchestra.md](STUDIO-orchestra.md)).

### The Grant toggle

On an enabled pack a toggle grants (or takes back) that permission at once:
`halo pack grant <id> <name>` (`--off`). On a disabled pack the toggles pick
what its Enable grants, so you decide before anything runs; a pack not
installed yet has them greyed. Grants are only ever what you choose,
shown as the pack requested them.

### A pack's own sections

A pack you enable may add its own sections after Packs, on `Alt+8` and
`Alt+9` in order (later ones have no key), behind a thin "packs" divider in
the tab strip and a PACKS group in the rail; and panels in the core
sections, palette lines and feed lines ([PACKS.md](PACKS.md#in-studio)).
They go the moment you disable it.

**After a reload (3.2.1.0 R1)** the pack section you were on is the first
paint, not the core section it used to fall back to while the packs
registry loaded. The served page names the running packs' own sections up
front (`<html data-pack-sections="[{id, pack, title}, ...]">`,
`studio/session_open.py` `boot_html`, only when a pack with sections runs),
so the section saved for this browser (`halo.studio.section`, an id with
`--`) opens at once with its tab, its title and one line, "loading the
pack's section", until `GET pack/registry` brings its panels. A pack that
is gone by then (disabled, removed) takes you to the first tab, as before;
`?mode=` still wins.

### The routes

The section reads and acts through `/api/pack/...`
(`halo_harness/studio/packs_manager_api.py`, the data in
`halo_harness/packs/manager.py`), with Studio's token and origin guard:

| Route | Runs |
|---|---|
| `GET pack/manager` | every pack here (its `halo pack list` row, `halo pack inspect` payload, health, compatibility lines, workflows), the sources with their packs, the doctor's rows of no pack |
| `POST pack/install {source \| id, project}` | `halo pack install <source\|id> [--project]` |
| `POST pack/sources {add \| remove}` | `halo pack sources add\|remove <folder\|git url>` |
| `POST pack/<id>/enable {grants, grant_all}` | `halo pack enable <id> --grant ... \| --grant-all` |
| `POST pack/<id>/grant {need, on}` | `halo pack grant <id> <need> [--off]` |
| `POST pack/<id>/disable` | `halo pack disable <id>` |
| `POST pack/<id>/update {dry_run}` | `halo pack update <id> [--dry-run]` (3.2.0.0 R7: Update's confirm asks with `dry_run` first) |
| `POST pack/<id>/rollback` | `halo pack rollback <id>` (3.2.0.0 R7) |
| `POST pack/<id>/remove {keep_config}` | `halo pack remove <id> [--keep-config]` |
| `GET\|POST pack/<id>/settings` | the settings form of any pack installed here |
| `POST orchestra/run {workflow, inputs}` | `halo workflow run <pack>/<name> --input k=v ...` (Run <workflow>) |

A "no pack ..." line answers 404, every other refusal 422, each with the
command's lines in `problems`.

### The reference pack in Studio

On a fresh home Sources shows **Documentation Review** under "shipped with
Halo". Install it, toggle `bash` in Details, Enable: its **Docs review**
section appears after Packs, its review lineup under Roles, and Templates
offers Run review ([PACKS.md](PACKS.md#the-reference-pack)).
