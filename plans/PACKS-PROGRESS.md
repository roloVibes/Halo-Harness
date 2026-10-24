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

- R3 (2026-10-21, branch v320/R3-studio from f5dfac1): Studio contributions.
  - `contributes.studio` is typed (schemas/pack_yaml.py `studio()`, the JSON
    twin's `$defs.studio` / `$defs.panel`): `sections`, `panels` (with a core
    `section`), `palette`, `config_form`, `events`, `attention`; a panel is
    `{id, title, kind, source, w, h, help, columns, links}`, kinds markdown,
    table, form, links, events, bundle. Meaning in `packs/studio_rules.py`
    (manifest lines `pack.yaml line N: contributes.studio.<key> ...`).
  - `studio-script` joins the permissions; a bundle panel needs it
    (`manifest.needed`, enable's request lines, doctor).
  - The registry the shell reads: `packs/studio_registry.py` (`GET
    /api/pack/registry`): only running packs, ids `<id>--<name>`, routes
    resolved, `config_form` adds a Settings panel (kind form) and a palette
    line, a bundle's `script: granted | not granted` and grant line.
  - `studio/packs_studio_api.py` (`pack` in `_PREFIXES`): registry, `file/`
    (markdown, JSON, a granted bundle; the shell's CSP; `?t=` for an
    import(), routed from server.py do_GET), `data/`, `config` GET/POST.
  - `pack_changed` frames: `studio/packs_studio_live.py` (`notify` from
    `grants.changed` and install; a 2 s watch for another process's change).
  - Attention: `fleet/pack_attention.py` (rows `pack:<id>:<kind>` from
    `.data/<id>/attention/<row>.json`; A/R/S write `answers/<row>.json`, O
    opens the pack's section); `attention.build(packs=)`, `fleet_answer` branch.
  - The shell: `routes/packs/` (store, registry, panels, kinds, PackForm,
    PackEvents with PackBundle, events, nav, types); `sections()` /
    `useSections()` in routes/index.tsx (the six unchanged, packs after
    Orchestra on Alt+7..9, a "packs" divider in the tab strip, a PACKS group in
    the rail); the palette's "pack <id>" groups; the Workspace adds a panel
    that arrives; Live, Activity and Attention render the pack's kinds.
  - Fixtures: doc-review gains `contributes.studio` (+ studio/notes.md,
    studio/checks.json); studio-bundle (studio/hello.js); failure fixtures
    studio-bad-kind, studio-outside, studio-no-script.

- R4 (2026-10-23, branch v320/R4-fleet from acd7eb2): Fleet capabilities from packs.
  - `contributes.fleet` is typed (schemas/pack_yaml.py `fleet()`, FLEET_KEYS /
    CAPABILITY_KEYS / REQUIRES_KEYS / HARDWARE_KEYS; the JSON twin's
    `$defs.fleet` / `$defs.capability`): `capabilities: [{name, description,
    requires: {tools, runtimes, platform, hardware: {gpu, ram_gb}, models,
    grants, locality}, capacity: {parallel}}]`, `inspector: [{label, source}]`,
    `mission: {metadata}`. Meaning in `packs/fleet_rules.py` (manifest lines
    `pack.yaml line N: contributes.fleet.<key> ...`): a name not in the
    top-level `capabilities:`, an unknown `requires` key (with the closest), a
    grant not requested, locality (repo, repo:<name>, shared, pack-data),
    platform/runtime words, capacity 1..64, a path in a description, a
    token-shaped value or an env reference ($VAR, ${VAR}, %VAR%) anywhere under
    contributes.fleet, an inspector source outside the pack or not md/txt/json,
    a metadata value that is a mapping.
  - `packs/fleet_registry.py`: per running pack, each capability checked on
    this host (`checks` -> `available`, `why`): tools (`has` or PATH), runtimes,
    platform, GPU / RAM, models (a bio_models tag, or a ref / family), grants,
    locality; `section` is the catalog's `packs` section
    (`capabilities_sources.packs`, one gather line; scrub runs over it);
    `refusal(needs)` the worker's line; `mission_metadata` / `pack_mission` a
    pack lineup's metadata; `host_catalog` (the cached catalog or a light view)
    for inspect and doctor.
  - Catalog views: `capabilities_view.pack_caps` / `pack_word` (summary and chips
    "+N pack caps", a spec-sheet `packs` row only when there are some);
    `capabilities_who` kind `pack` (one not available here at half, with why);
    `packs_studio_live.publish` marks the catalog stale on every `pack_changed`
    (grants.changed already did for this process's own changes).
  - Missions: `mission_assign.has` (kind `pack`, only where available; why
    "pack <id>: <name>"), `unique_lines`, `assign` -> `pack_needs: [{need,
    pack}]`; `mission_plan.pack_line` in each harness's block and the prompt's
    needs rule; `mission_dispatch.fields` sends `needs`; `mission_worker.check`
    keeps them and `pack_check` refuses in `accept` / `start_local`, and
    `control.run` checks a `run_task` before the owner is asked ("this harness
    does not run pack doc-review with bash"); `mission_api.create` carries the
    pack lineup's `metadata` (body `lineup`, else config `team`); MISSION.md has
    a Metadata line.
  - `halo pack inspect`: a "contributes:" block (Studio's sections, panels,
    palette, settings form, event lines, attention rows; the fleet
    capabilities with available / why, inspector lines, metadata;
    `packs/contrib_views.py`), `--json` `contributes: {studio, fleet}`;
    `halo pack doctor`: a `fleet-capability` row per capability not available
    here (the grant command when a grant is what is missing).
  - Studio (`routes/fleet/PackCaps.tsx`): the Capabilities card's "packs" line,
    the plan's needs cell ("docs.review · pack doc-review on <harness>"), the
    selected part's pack inspector lines (read through R3's file route; a pack
    only on another harness shows its labels), the same in the Agent panel for
    a part's agent of the open mission, the mission's metadata in its head.
  - Fixtures: doc-review gains `contributes.fleet` (docs.review: models
    [tools], grants [bash], parallel 2; inspector fleet/checklist.md; metadata
    review/style); fleet-secret (token + $HOME), fleet-unknown-name,
    fleet-needs-gpu (valid; not available without a GPU).

- R5 (2026-10-23, branch v320/R5-workflows from c6003a0): workflows and artifacts.
  - The workflow file `<pack>/workflows/<name>.yaml` (its name in
    `contributes.workflows`): shape `schemas/workflow_yaml.py` (TOP_KEYS,
    STAGE_KEYS, WHEN/GIVE/TAKE/INPUT/OUTPUT/PREREQ keys) + the JSON twin
    `packs/schema/workflow.schema.json`; meaning `packs/workflow_rules.py`
    (inputs, outputs, prerequisites, the file vs contributes.workflows) and
    `packs/workflow_stages.py` (ids, `role_bio`, needs, after/takes, the cycle,
    for_each, when, gives, retries/timeout/budget, gate, verify, after_event),
    one manifest line each `workflows/<name>.yaml line N: <key> ...`.
  - `packs/typed.py`: artifact schemas (`artifacts/<schema>.json`,
    `contributes.artifacts` names) and event schemas (`events/<kind>.json`, a
    `contributes.events` entry is a kind or `{kind, schema, description}`):
    `check` (shape + `required`), `x-halo-view` table | markdown | keyvalue.
  - The compile (`halo_harness/workflows/`): spec (find `<pack>/<name>` of a
    running pack), inputs (typed inputs, prerequisites, capability needs),
    conditions (`when`), compile (stages -> jobs, Goal fields, handoffs),
    bounds (goal.workflow, the bound rows), pinned (the lead refines briefs of
    the pinned jobs; a reviewed plan keeps the stage set), runtime (a lane's
    stage text, run-time `when` -> skipped, budget stop, after_event,
    timeout_s), gate (`widen`: artifacts vs schema, evidence in the record,
    stage tests, per-stage retries), outputs (copy to `<run>/artifacts/`, the
    report's `workflow` + `artifacts`), cli (`halo workflow list|show|check|run`,
    `halo orchestra new --workflow`), goal (`--as goal`: the run queued for the
    supervisor; `cli_add` for `halo goal add --workflow`).
  - Orchestra hooks, each a no-op without `goal.workflow`: `Goal.workflow`;
    `split_goal` -> `split_pinned`; `plan.check` -> `plan_rules` +
    `plan_problems(claim_free=)`; `workers.run_lane` -> `runtime.stage`
    (prompt + `early`); `adapters.spawn_worker` reads `lane.timeout_s`;
    `quality_gate` -> `widen`, `GateResult.notes` (run.py's respawn text);
    `lanes.step_state` (a skipped lane's step); `write_report` -> `outputs.part`,
    `format_report` the artifact and not-enforced lines; the record check's
    detail counts the workflow rows.
  - Events: `ext.publish_event` refuses a pack that does not run here (one
    line, ValueError), checks a declared kind's data (a mismatch goes out with
    `problems`), keeps every event (`packs/events_log.py`,
    `~/.halo/packs/.data/<id>/events.jsonl`); a bio's trigger `{on: event,
    name: <pack>:<kind>}` / `{event: ...}` fires once (`packs/event_triggers.py`,
    TeamScheduler polls each tick); a stage's `after_event` waits.
  - Memory: `ext.memory.write(namespace, text, provenance)` + `<name>._meta.json`
    (`packs/memory_meta.py`: source, run, stage, written, retention keep |
    days:<n> | run, shared); recall's filter reads a namespace plus what is
    shared with its pack; `retention: run` goes when the run ends (from the
    report), `halo recall prune`; `halo recall --namespace --provenance`.
  - Studio: a panel kind `artifact` (`{kind: artifact, schema, source: latest |
    <json> | data:<path>}`, studio_rules + registry `view`/`file`), `GET
    pack/<id>/artifact/<schema>` and `GET orchestra/<run>/artifact/<name>`
    (`studio/workflow_api.py`); `routes/packs/ArtifactView.tsx` (table,
    markdown, keyvalue; PackArtifact), PackEvents shows a kind's data under its
    line (registry events `view`) and a frame's `problems`; Orchestra's Report
    panel an "Artifacts (N)" tab (`routes/orchestra/Artifacts.tsx`).
  - `halo pack inspect`'s contributes block lists the workflows, artifact
    schemas and event schemas (`contributes.typed` in `--json`).
  - Fixtures: doc-review gains workflows/review.yaml (read per file, judge with
    gate human, write with a run-time when and evidence), artifacts/review-report.json,
    events/review.done.json, a "Last review report" artifact panel; wf-cycle,
    wf-unknown-role, wf-no-giver, wf-input-type; tests/fixtures/workflows/report-bad.json.

## Open dependencies

- R2 confirmed the `<id>--<name>` names (Decisions); the ROADMAP's R2 line
  still says `<pack>/<name>` -- the coordinator fixes it.
- The supervisor's goal queue (3.1.8.0 R1, `halo goal add --lineup`) and
  Studio's Orchestra goal form do not read the lineup's acceptance yet:
  after the merge each calls `packs.lineup_run.goal_defaults` (one line).
- 3.1.9.0 R1's enriched capability rows: `bio_models.TAGS` / `row_tags` is the
  one place to add their tags.
- The registry cache keys on pack.yaml and state.json, not on a pack's bio
  files: an edit inside an installed pack's agents/ shows its manifest lines
  after the next install/update/enable (installs go through the journal).
- R3 (done): a pack's Studio rows and answers are files in its data folder
  (no new ext name); a push channel to the pack's code (an answer as a frame)
  is R5's typed events. The supervisor's `goal_*` rows (3.1.8.0 R1) are not on
  this branch: after the merge they sit beside `pack:<id>:<kind>` in
  `fleet_answer.act`, each its own branch.
- R3: a pack section you were on comes back after a reload only once the
  registry loads (the first paint is the saved core section or Roles).
- R4 (done): `capacity.parallel` is advertised and shown to the planner; the
  hub does not hold a part back when a harness already runs that many (the
  worker refuses only for a pack that does not run or a grant that is
  missing). A refused part fails like an offline harness's: the hub does not
  re-plan it onto another harness (the supervisor's replanning, 3.1.8.0 R2,
  may). `fleet.capabilities.hide` does not hide a pack capability.
- R4: a pack's inspector lines are read through R3's file route, so Studio
  shows a file only for a pack that runs on its own harness; a part on a
  member shows the labels and "runs on <member>". The Agent panel shows them
  for a part's agent when that mission is open in the Mission panel.
- R4: a mission's metadata comes from the lineup named in the request
  (`lineup`) or the active one (config `team`); Studio's Mission form and
  `halo fleet mission new` send no `lineup` yet (one field each).
- R5 (done): the supervisor (3.1.8.0 R1/R2) is on master, not on this
  branch. `halo workflow run --as goal` and `workflows/goal.py` are written
  against master's `supervise.queue` / `runner.ensure_run` (a merge preview,
  master + this branch file by file, ran the resume test green). After the
  merge `halo goal add` gains `--workflow` + `--input` (two add_argument lines
  and `if args.workflow: return workflow_goal.cli_add(state_dir, args)` in
  supervise/goal_cli.py), and `workflows` can join test_invariants'
  `_MAP_PACKAGES` (master's line holds `supervise`).
- R5: the replanner (3.1.8.0 R2) may add or replace lanes in split.json; a
  workflow run's stage map is keyed by job id, so a replan of a workflow run
  should keep its stage set (or be off for it): not handled here.
- R5: `gate: human` is the plan review before any stage starts, not a hold
  before that one stage; the workflow's own `budget_usd` is the goal's budget
  (the forecast, and the supervisor's stop under `--as goal`), not enforced as
  a stop in a plain Orchestra run. A stage's `needs` are checked on this
  harness at compile time (an Orchestra run is local).
- R5: the evidence is read into the gate's record check; 3.1.8.0 R3's judge
  reading the evidence instead of the summary is the next widening.
- R5: Studio has no workflow picker (Orchestra's new-run form, the Pack
  Manager): runs start from the CLI. R6's Pack Manager is the place.
- R5: a lineup's `workflows:` stays a list of names (R2): a workflow runs by
  its `<pack>/<name>`; the compiled goal's `lineup` is the pack lineup that
  names it.
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

- R3 new modules: test_packs_studio_contract 6, test_packs_studio_api 6,
  test_packs_studio_ui 8 (Chrome, full tier) -- 20 tests, all green.
- R3 kept green, module by module: 79 plain modules (R1's and R2's lists,
  test_fleet_panels_api/_more/_extras, test_fleet_mission_api, test_studio_team)
  938 tests, 937 passed, 1 skipped, 1 failed under load (test_agents_schedule's
  1 s schedule; alone twice 7/7); 14 Chrome modules (test_packs_studio_ui,
  test_packs_roles_studio, test_studio_ui 53, test_studio_start, _roles_model,
  _roles_glow, _roles_tiers, _modes, _model_select, _session, _session_live,
  _session_links, _session_cost_map, _session_steer) 87 tests: one source pin
  failed (test_studio_modes read `Digit[1-6]` in keys.ts; now `Digit[1-9]`),
  re-run 12/12.
- R3 full runs (2026-10-21, Windows build host): `tests/run_all.py --fast`
  4883 tests / 495 modules, 4870 passed, 2 failed, 11 skipped, both real-home
  guards ok; the two were test_studio_section_order's source pins (keys.ts
  and Palette.tsx read `SECTIONS`, now `sections()`), updated, the module
  re-run 6/6. `test_bridge.py` 101/101. Studio UI: `npx tsc --noEmit` clean,
  two builds identical (studio.js sha256 a8f09cdf..., studio.css a9594654...,
  index.html unchanged), `tests.test_studio_dist` 6/6 last.
  Not run: test_tui.py, the full tier as a whole, Kali/WSL.

- R4 new modules: test_packs_fleet_contract 4, test_packs_fleet_catalog 4,
  test_packs_fleet_missions 5 (one over two homes, the HubRig),
  test_packs_fleet_ui 2 (Chrome, full tier) -- 15 tests, all green.
- R4 kept green, module by module: 41 modules (R1-R3's packs modules,
  test_fleet_capabilities / _hub, test_fleet_mission / _api / _files /
  _handoffs / _merge / _run, test_fleet_panels_api / _extras / _more,
  test_fleet_control, test_fleet_hub_control, test_fleet_cli, test_docs_*,
  test_invariants, test_studio_edit_target, test_studio_team,
  test_audit_privacy, test_privacy_scan, test_line_endings, test_glossary): one
  module failed, test_packs_cli (two doctor pins listed the extended fixture's
  checks exactly: + fleet-capability; the clean-doctor catalog row gains
  tools), updated, re-run 4/4. Chrome: test_packs_fleet_ui 2,
  test_packs_studio_ui 8, test_packs_roles_studio 5, test_studio_ui 53,
  test_studio_start 2, test_studio_modes 12 -- 82/82.
- R4 full runs (2026-10-23, Windows build host): `tests/run_all.py --fast`
  4896 tests / 498 modules, 4885 passed, 0 failed, 11 skipped, both real-home
  guards ok; `test_bridge.py` 101/101. Studio UI: `npm ci`, `npx tsc
  --noEmit` clean, two builds identical (studio.js sha256 3db6ea04...,
  studio.css 41b2f982..., index.html unchanged), `tests.test_studio_dist` 6/6
  last. Not run: test_tui.py, the full tier as a whole, Kali/WSL.

- R5 new modules: test_workflow_schema 5, test_workflow_compile 6,
  test_workflow_run 7 (the `--as goal` supervisor test skips on this branch),
  test_pack_events 4, test_pack_memory_provenance 4, test_workflow_ui 3
  (Chrome, full tier) -- 29 tests, 28 passed, 1 skipped.
- R5 kept green, module by module: R1-R4's packs modules, test_ext_api,
  test_orchestra_* (18), test_studio_orchestra_api / _plan,
  test_agents_schedule, test_recall_fleet, test_round_embeddings_local,
  test_docs_*, test_invariants, test_line_endings, test_privacy_scan,
  test_audit_privacy, test_glossary, test_studio_edit_target,
  test_doctor_config, test_config_where, test_completion_cli. Pins updated:
  test_ext_api (`memory` in SURFACE; review.done data matches its schema),
  test_packs_studio_contract (the report panel, the event view),
  test_packs_studio_ui (a disabled pack's event is refused), test_docs_commands
  (`halo workflow`). Chrome 85/85 (test_workflow_ui, test_packs_studio_ui,
  test_packs_fleet_ui, test_packs_roles_studio, test_studio_ui 53,
  test_studio_start, test_studio_modes).
- R5 merge preview (scratch: master + this branch file by file): master's
  test_supervise_* (11 modules, 57 tests), the orchestra run / gate / plan
  modules, test_agents_schedule and the R5 modules (the supervisor test
  included) green; every file merges cleanly but the built bundles.
- R5 full runs (2026-10-23, Windows build host): `tests/run_all.py --fast`
  4922 tests / 503 modules, 4910 passed, 0 failed, 12 skipped, both real-home
  guards ok; `test_bridge.py` 101/101. Studio UI: `npm ci`, `npx tsc
  --noEmit` clean, two builds identical (studio.js sha256 2ce5048c...,
  studio.css bec944aa..., index.html unchanged), `tests.test_studio_dist` 6/6
  last. Not run: test_tui.py, the full tier as a whole, Kali/WSL.

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

- R3: every Studio contribution is data Studio's components draw; the one
  script a pack may run in the page is a `bundle` panel, behind the explicit
  `studio-script` grant (like `bash`); no filter or wording beyond the grant line.
- R3: the bundle loads through `import()`, which sends no header, so the file
  route takes the token in `?t=` as `/api/events` does; it serves only a
  declared bundle source, and only while `studio-script` is granted.
- R3: a pack's attention row is a JSON file its code writes with
  `write_private` (`attention/<row>.json`); the answer is a file beside it
  (`answers/<row>.json`): no new ext API name.
- R3: `config_form: true` is the Settings panel of the pack's first section,
  so it needs a section and a `config.schema` (manifest lines otherwise).
- R4: a pack capability is one of the catalog's needs, matched by the same
  `mission_assign.has` (kind `pack`), and only where it is available: an
  unavailable one is listed (with why) but never meets a need.
- R4: the worker's check is the explicit grant rule it already applies (the
  pack runs here, the capability's grants are granted); a part is refused with
  one line, which is the part's result. It runs before a member's owner is
  asked. A need no pack here declares is not this check's (it was the hub's
  catalog's), except a `pack:` need.
- R4: the manifest refuses a token-shaped value and an environment reference
  anywhere under `contributes.fleet`, and a path in a capability's
  description; any other path is cut by the catalog's scrub (the brief's
  description path is a manifest line, so the scrub test puts its paths in
  `requires.tools` and `mission.metadata`).
- R4: `requires.models` takes a bio_models tag or a model ref / family (the
  brief's "ref or tag"); unlike a bio's `models.preference`, a provider-pinned
  ref is allowed here: it names what the host must have, not what to run.

- R5: a workflow COMPILES to an Orchestra goal (goal.json `workflow` holds the
  pinned plan); every runtime hook is a no-op for a goal without it, so a
  repo with no pack and no workflow runs exactly as before.
- R5: the pinned split still asks the lead once, for briefs only; an answer
  that changes the stage set is asked again once, then the workflow's own
  briefs run (the stages are fully specified; the refinement is optional).
- R5: a stage that edits no file of the repo claims nothing (`claim_free` in
  the plan check); its lane commits nothing and merges trivially.
- R5: one job per stage, one per file for `for_each` (`{input, match}`): the
  brief's "parallel per file".
- R5: an artifact give is saved as `<name>.json` in `lanes/<n>/artifacts/`;
  the gate's mismatch is a return with one line per problem, the stage's
  `retries` its cap; the evidence rows join `record` (`evidence:<item>`,
  `artifact:<name>`), so `record_equals_disk` fails on a missing one.
- R5: a run-time `when` false marks the lane `skipped` (no worker runs, its
  step reads skipped, it merges with nothing) instead of a new lane state.
- R5: a disabled pack's event is a ValueError naming it (ext's existing
  refusal form), never a silent drop; a mismatching event goes out with its
  problems. The events log in the pack's data folder is what subscriptions
  read, so a trigger fires from any process.
- R5: `_meta.json` is a sidecar per entry (`<name>._meta.json`), so parallel
  stages never share a file; a note without one is the user's, kept.

## Next task

- R6: The Pack Manager in Studio and the reference pack (plans/ROADMAP.md
  3.2.0.0 R6, Phases 9-10): discover, capabilities, dependencies, requested
  permissions, enable and disable, model and tool settings, templates,
  presets, compatibility warnings, health, update, uninstall (trusted local
  and configured sources only); the "Documentation Review" pack (a reviewer
  and a writer bio, the review workflow, a Studio review panel, the typed
  review-report artifact, a Fleet capability requirement) that installs, runs
  (`halo workflow run`), renders (its artifact panel) and uninstalls without a
  core change. R5's doc-review fixture is its seed; a workflow picker belongs
  in the Pack Manager.
