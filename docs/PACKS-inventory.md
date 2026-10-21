# Packs: the inventory of extension points

Read this when you change how a pack plugs into Halo: the extension points a pack reuses and the places that assumed nothing outside Halo adds files.

A survey taken for 3.2.0.0 R1 (see [PACKS.md](PACKS.md) for packs themselves and
[EXTENSION_API.md](EXTENSION_API.md) for the contract). Line numbers drift; the
names do not.

## The extension points a pack reuses

- **The plugin-root channel.** `headless.build_session` resolves `--plugin-dir` /
  `--plugin-url` once and hands the same list to skills and commands
  (`commands.registry.Registry.discover`), agents from `agents/*.md`
  (`config.agents_md.discover_agents(plugin_roots=)`), hooks
  (`build_hook_runner(extra_plugin_roots=)` -> `hooks.load_plugin_hooks`), MCP
  (`mcp_setup.build_manager(extra_plugin_roots=)` ->
  `config.plugins.discover_plugin_mcp_servers`) and the Skill tool
  (`Session.plugin_roots`, children through `agent/subagent.py`). The TUI goes
  through `build_session` too. Names are namespaced already: skills and
  commands `<plugin>:<name>`, MCP servers `plugin_<plugin>_<server>`; the
  plugin name is `.claude-plugin/plugin.json`'s `name` or the folder name. An
  enabled pack's root joins this list, so its plugin layout loads unchanged.
- **The bio and lineup folders.** `agents_yaml.agent_search_dirs` and
  `teams_yaml.team_search_dirs`: project `.halo/`, home `~/.halo/`, shipped
  `templates/` (label "template"); nearest wins by name. A pack tier sits
  after the home and before the shipped folder, read in place, label
  `pack:<id>`, names `<id>--<name>`.
- **Prior art.** `teams_bundle.py` (validate before writing, skip collisions,
  "shadows shipped", rollback) and `orchestra/coach_record.py` (`{existed,
  before, after}` rows) shape the install journal; YAML through
  `agents_yaml._read_yaml_file` / `_write_yaml_file`; shapes through
  `schemas.check`; private files through `privateio.write_private_atomic`;
  settings through `theme.get_config_value` / `set_config_value`; the
  `halo config where` groups (`config_where.GROUPS`) and `halo doctor --config`
  (`doctor_config.config_findings`); `field_help.py`; `privacy_scan` over a
  pack's text files.

## Compatibility risks (each one handled or named)

- **The "template" marker.** About fifteen places read the source label
  "template" as "read-only, never write". `packs.names.read_only_source` now
  answers for "template" and every "pack:<id>" (Python and Studio).
- **Copy-once lineups.** `ensure_builtin_team_templates` copies shipped
  lineups once and they go stale; a pack's files are read in place instead.
- **The name rule** `^[A-Za-z0-9][A-Za-z0-9_-]*$`: `<id>--<name>` fits it, so
  a pack name works in routes, memory folders and `tools.mcp_servers`.
- **Strict top-level schemas.** `config.json` reports an unknown top-level
  key; `packs` joins `schemas.config_json._SECTIONS` (one free mapping).
- **Closed sets.** The feed kinds (`studio/feed_kinds.py`, `KNOWN_KINDS` in
  the UI), the CLI dispatch and `completion_cli.SUBCOMMANDS`, the work kinds
  (`work/states.KINDS`: lane, part, stage) and the glossary are closed lists;
  a pack adds to none of them in R1 (`publish_event` uses one frame kind,
  `pack_event`).
- **Six hardcoded Studio sections** (`ui/src/routes/index.tsx` `SECTIONS`):
  Studio contributions stay `planned` (R3).
- **Same-origin pack UI.** Studio's CSP is `default-src 'self'`; a pack's UI
  must be served by the Studio server under the pack's id (R3).
- **`~/.claude` is never written.** A pack's skills, commands, hooks and MCP
  servers are read from its own folder; nothing is copied into `~/.claude`.
- **Pack renames.** A new id is a new pack: names qualified with the old id
  (`old--bio` in a user lineup) stop resolving; doctor names them.
- **Untrusted folders.** A project pack (`<repo>/.halo/packs/`) is the
  untrusted layer: its lineups lose `permissions.mode` and allow rules the same
  way a project lineup does in an untrusted folder.
