# Packs (3.2.0.0) -- progress

The working record of the Packs program (plans/ROADMAP.md "3.2.0.0 'Packs'").
Kept current by every round: what is done, open dependencies, test results,
decisions, the next task.

## Done

- R1 (2026-10-21, branch v320/R1-packs):
  - docs/PACKS-inventory.md: the extension points a pack reuses, the risks.
  - The stable surface `halo_harness/ext/` (API_VERSION 1.0): read_yaml,
    write_yaml, check_schema, get_config, set_config, write_private, pack_dir,
    data_dir, publish_event, is_granted, Unit, the name rules.
  - docs/EXTENSION_API.md (a status per part), the JSON schema
    `halo_harness/packs/schema/pack.schema.json`, the fixture
    `tests/fixtures/packs/doc-review/`.
  - `halo_harness/packs/`: manifest (schema kind "pack"), discover, state,
    settings, resolve, conflicts, registry, offers, grants, contribute,
    journal, fetch, install, remove, doctor, cli, cli_views.
  - `halo pack list|inspect|install|enable|disable|update|remove|doctor`;
    config section `packs` (`packs.sources`, `packs.settings.<id>`); the packs
    group of `halo config where` and `halo doctor --config`.
  - Wired: every enabled pack's root joins the session's plugin roots; the
    pack tier in `agent_search_dirs` / `team_search_dirs` (`pack:<id>`,
    `<id>--<name>`, read in place); hooks and MCP servers only when granted;
    `read_only_source` replaces every "template" check (Python and Studio);
    Fleet's capabilities catalog gathers afresh after enable, disable,
    update and remove.
  - docs/PACKS.md, docs/COMMANDS-packs.md, CONFIG/AGENTS/ROLES rows, the
    module map (+ packs/, ext/ in `_MAP_PACKAGES`), field_help `PACK`.

## Open dependencies

- R2 (roles and lineups from packs) builds on the `<id>--<name>` names, the
  `_pack` / `_name` markers and `read_only_source`; the roadmap's R2 text
  says `<pack>/<name>` -- R1 used `<id>--<name>` per its brief (a `/` breaks
  the bio and lineup name rule and file names). R2 should confirm.
- R3 (Studio contributions): `contributes.studio` is accepted and stored,
  never read. The six sections stay hardcoded until R3.
- R4 (Fleet): `contributes.fleet` likewise; `capabilities` in pack.yaml are
  names only.
- R5: `contributes.artifacts`, typed event schemas; `publish_event` sends
  one `pack_event` frame kind today (not in feed_kinds.DEFAULT_KINDS, which
  lists the kinds asked of sessions).
- R7: the glossary gains "pack" (closed list in R1); the compatibility and
  migration policy is `planned` with the proposal in EXTENSION_API.md.
- A project pack's BIO keeps its `tools.permission_mode` and allow rules (the
  brief named lineups only; no trust filter exists for project bios either).

## Test results

- R1 new modules: test_packs_manifest 7, test_packs_resolve 5,
  test_packs_conflicts 3, test_packs_lifecycle 9, test_packs_contribute 5,
  test_packs_cli 4, test_ext_api 3 (36 tests, all green).
- Kept green: test_doctor_config, test_config_where, test_completion_cli,
  test_docs_*, test_invariants, test_agents_*, test_teams_*, test_mcp_*,
  test_skill_tool, test_studio_api, test_studio_edit_route,
  test_review3_s2, test_w5_plugin_full_load, test_offline_mode,
  test_audit_privacy, test_privacy_scan, test_line_endings, test_glossary.
- Full runs (2026-10-21, Windows build host): `tests/run_all.py --fast` 4854
  tests / 490 modules, 4842 passed, 1 failed (test_studio_edit_target pinned
  the field-help groups; "pack" added, the module re-run green), 11 skipped,
  both real-home guards ok; `test_bridge.py` 101/101; Studio UI: `npx tsc
  --noEmit` clean, two builds identical, `tests.test_studio_dist` 6/6 last.
  Not run: test_tui.py (per the brief), the full tier, Kali/WSL.

## Decisions

- Pack-qualified names are `<id>--<name>` (valid under the name rule); an id
  holds no `--` and does not end in `-`, so a qualified name splits one way.
- The pack tier sits after the project and home folders and before the
  shipped one: yours always wins, and doctor names the shadow.
- A pack is enabled for the folder its state record names (`root`), so a
  same-id pack in another repo stays off until enabled there.
- Ownership of a pack's files is the journal's content hash: update and
  remove touch only files that still hold what the pack wrote.
- Grants add up across `enable`; `disable` clears them; `remove
  --keep-config` keeps the record and grants for the next install.
- `packs.sources` lets `halo pack install <id>` find a pack by id.
- `home-write` gates `write_private` / `write_yaml` outside the pack's data
  folder `~/.halo/packs/.data/<id>/`; `bash` and `network` are recorded for a
  pack's own code (`is_granted`); a url MCP server needs `network` too.

## Next task

- R2: roles and lineups from packs (plans/ROADMAP.md 3.2.0.0 R2).
