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
- R2 (2026-10-21, branch v320/R2-roles from 69b156a): roles and lineups from packs.
  - A pack bio's `models.capabilities: [tag, ...]` resolves at load to the
    best catalog model with every tag (`packs/bio_models.py`: `TAGS`, `pick`,
    `apply` from `agents_yaml.resolve_agent_bio`; Studio's catalog rows, 60 s
    cache keyed by the home and its catalog files' mtimes); a family name in
    `models.preference` is preferred; none: the user's `default` model and a
    Problems/doctor row. A user bio may ask by tag too (a clone keeps it); a
    full ref there pins it. Card source "capabilities" (`teams_yaml.member_model`).
  - What a pack's files may not say (`packs/bio_rules.py`, manifest lines
    naming file and line): a provider (`models.provider`, a prefixed or
    vendor/model preference/fallback), an unknown tag, a bad
    `context.memory.namespace`, a `tools.needs` not requested, a lineup
    `workflows` name not in `contributes.workflows` (new manifest key).
  - `context.memory.namespace` (default the id) -> `~/.halo/packs/.data/<id>/memory/<ns>/`
    (`packs/memory.py`); recall indexes those notes in its one store and
    `recall.search(namespace=...)` filters by path (None = yours, every pack
    folder left out); a team member on a pack bio gets the folder in its
    prompt and extra dirs (`agent/subagent.py`).
  - `tools.needs`: an ungranted need loads the bio; doctor row `bio-need`
    with `halo pack enable <id> --grant <need>`; a card warning in Studio.
  - Lineup `acceptance.test` / `acceptance.review` = the Orchestra goal's
    `test` / `plan: review` (`packs/lineup_run.py`; `halo orchestra new
    --lineup` takes them, `--test` wins); `workflows` carried through resolve.
  - `halo pack inspect` (bios with model, needs, namespace; lineups with
    members, tiers, workflows, acceptance; `--json` `bios`/`lineups`),
    `halo pack doctor` (`bio-model` per capability set, `bio-need` per need),
    `halo agents list` / `halo teams list` (a `pack <id>:` group; a shadowed
    name says "shadowed by ~/.halo/..."; unchanged with no pack), `halo agents`
    (the shadow line in the pack group) -- `packs/roles.py`.
  - Studio Roles: Lineups and Bios grouped (yours, project, pack <id>,
    shipped; labeled boxes, empty collapsed; `GET state` / `roles/packs` list
    the packs that run); pack rows Preview (read-only canvas / bio form,
    "from pack <id>, read-only"), Clone (`POST roles/clone`, `packs/clone.py`:
    `<name>` + `from_pack: <id>@<version>`, 409 + confirm when yours or a
    shipped one has the name), Customize, Apply (dialog names the pack and the
    lineup it replaces; writes config.json only). Canvas edits and Save are
    refused on a pack lineup; New/Duplicate answer 409 instead of writing
    over a file of yours.
  - Fixtures: doc-review extended (reviewer: capabilities, namespace, needs
    bash; writer: family claude-sonnet; review: two tiers, acceptance, workflows;
    pack.yaml: bash, contributes.workflows); provider-pinned, stray-workflow,
    rare-caps, user-files/doc-review--reviewer.yaml.

## Open dependencies

- R2 confirmed the `<id>--<name>` names (Decisions); the ROADMAP's R2 line
  still says `<pack>/<name>` -- the coordinator fixes it.
- R5 runs `workflows`: R2 reads only the names (`contributes.workflows`:
  names, or `workflows/<name>.yaml` whose stem is the name). A cloned
  lineup keeps `workflows:` as plain names; R5 decides how a user lineup
  names a pack's workflow.
- The supervisor's goal queue (3.1.8.0 R1, `halo goal add --lineup`) and
  Studio's Orchestra goal form do not read the lineup's acceptance yet:
  after the merge each calls `packs.lineup_run.goal_defaults` (one line).
- 3.1.9.0 R1's enriched capability rows: `bio_models.TAGS` / `row_tags` is the
  one place to add their tags.
- The registry cache keys on pack.yaml and state.json, not on a pack's bio
  files: an edit inside an installed pack's agents/ shows its manifest lines
  after the next install/update/enable (installs go through the journal).
- R3 (Studio contributions): `contributes.studio` is accepted and stored,
  never read. The six sections stay hardcoded until R3.
- R4 (Fleet): `contributes.fleet` likewise; `capabilities` in pack.yaml are
  names only.
- R5: `contributes.artifacts`, typed event schemas; `publish_event` sends
  one `pack_event` frame kind today (not in feed_kinds.DEFAULT_KINDS, which
  lists the kinds asked of sessions).
- R7: the glossary gains "pack" (closed list in R1); the compatibility and
  migration policy is `planned` with the proposal in EXTENSION_API.md.
- A project pack's BIO keeps its `tools.permission_mode` and allow rules
  (decided in R2: kept, see Decisions).

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

- R2 new modules: test_packs_roles 7, test_packs_roles_api 6, test_packs_roles_cli 4,
  test_packs_roles_studio 5 (Chrome, full tier) -- 22 tests, all green. R1's
  test_packs_cli and test_packs_lifecycle follow the extended fixture
  (`bash` requested, the two bio doctor rows).
- R2 kept green, module by module (49 modules, 444 tests): R1's list above plus
  test_agents_teams_forms, test_external_review_fixes, test_recall_fleet,
  test_roles*, test_round_wizard_deep_review, test_teams_runtime,
  test_teams_tiers_runtime; Chrome Roles modules: test_studio_ui 53,
  test_studio_roles_model 5, _glow 6, _tiers 7, test_studio_start 2,
  test_studio_modes 12, test_studio_model_select 3.
- R2 full runs (2026-10-21, Windows build host): `tests/run_all.py --fast`
  4871 tests / 493 modules, 4860 passed, 0 failed, 11 skipped, both real-home
  guards ok (run with stdin closed: from a background shell an open stdin
  holds test_h15_init_tabs at the init wizard's prompt); `test_bridge.py`
  101/101; Studio UI: `npx tsc --noEmit` clean, two builds identical
  (studio.js sha256 1a976e3c...), `tests.test_studio_dist` 6/6 last.
  Not run: test_tui.py, the full tier as a whole, Kali/WSL.

## Decisions

- Pack-qualified names are `<id>--<name>` (valid under the name rule); an id
  holds no `--` and does not end in `-`, so a qualified name splits one way.
  R2 confirmed it against the roadmap's `<pack>/<name>`: a `/` breaks the
  bio and lineup name rule, file names, route targets and memory folders
  (docs/PACKS.md says so).
- R2: "budgets, delegation rules, acceptance checks" are the existing bio and
  lineup sections, read from a pack's files unchanged; no parallel keys. The
  memory namespace is the bios' existing `context.memory.namespace` (the
  brief's `memory.namespace`), the family preference the existing
  `models.preference` (the brief's `models.prefer`).
- R2: a project pack's bio keeps `tools.permission_mode` and allow rules;
  permissions stay the user's rules and grants, no filter.
- R2: a pack bio naming a provider is a manifest problem, so the whole pack
  does not install or run (not only the bio): the rule is static and the
  author's to fix.
- R2: Clone asks before a name Halo ships too (`reviewer`): the copy would
  take the shipped bio's place in every lineup naming it.
- R2: a file of yours named `<id>--<name>` wins everywhere, also as the
  `extends` parent of the pack's other bios.
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

- R3: Studio contributions (plans/ROADMAP.md 3.2.0.0 R3): `contributes.studio`
  read, one controlled bundle mechanism, nothing shown for a disabled pack.
