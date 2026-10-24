"""halo_harness.packs -- capability packs (Halo 3.2.0.0 R1, docs/PACKS.md).

A pack is a folder: a Claude-plugin layout (`.claude-plugin/`, `agents/`,
`skills/`, `commands/`, `hooks/`, `.mcp.json`) plus `pack.yaml` at its root,
and Halo bios and lineups under `agents/*.yaml` and `teams/*.yaml`. It lives
under `~/.halo/packs/<id>/` or `<repo>/.halo/packs/<id>/`. One module per
responsibility:

    names.py      ids, qualified names (`<id>--<name>`), source labels
    semver.py     versions and version ranges
    manifest.py   pack.yaml: read and validate
    discover.py   the packs on disk, nearest first
    state.py      <state>/packs/state.json: installed, enabled, granted
    settings.py   config.json `packs.settings.<id>` against the pack's schema
    resolve.py    requires -> order; API and Halo version ranges
    conflicts.py  two packs (or a pack and you) offering one name
    registry.py   the active packs: discovered, enabled and resolved
    grants.py     what a pack requests, what is granted, enable/disable
    contribute.py what an active pack adds (plugin roots, bio/lineup folders)
    journal.py    <state>/packs/journal.jsonl and the journaled file writes
    fetch.py      a pack source: a folder or a git url
    sources.py    where a bare id is looked for: packs.sources, then the shipped packs (3.2.0.0 R6)
    manager.py    what Studio's Pack Manager shows (3.2.0.0 R6)
    install.py    install (update's door)
    update.py     update: the migration notes first, staged and swapped, the old kept as <id>.previous (3.2.0.0 R7)
    rollback.py   `halo pack rollback`: <id>.previous back, settings and ownership restored (3.2.0.0 R7)
    migrate.py    `migrations` between two versions; the `settings` renames, journaled (3.2.0.0 R7)
    deprecations.py  doctor rows: an ext name announced for removal, a grant an update asked for (3.2.0.0 R7)
    interpreter.py   `${halo_python}` and PYTHONPATH for a pack's hook and MCP server (3.2.0.0 R7)
    remove.py     remove (your own work stays)
    doctor.py     every problem, one line each
    cli.py        `halo pack ...`
    cli_views.py  the text `halo pack list` / `inspect` print

A pack imports `halo_harness.ext` only (docs/EXTENSION_API.md).
"""
