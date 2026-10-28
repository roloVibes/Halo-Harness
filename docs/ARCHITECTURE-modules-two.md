# Architecture: the module map, part two

Read this when you look for the module behind the Ollama steward, packs, the extension API, isolation, Setup or Settings.

Part of [Architecture](ARCHITECTURE.md), which lists every part. Part one, [the module map](ARCHITECTURE-modules.md),
holds Studio, fleet, Orchestra, the unit of work, team, supervise, outcomes and knowledge.

## Module map, part two: the steward, packs, isolation, Setup, Settings

**The Ollama steward** (`halo_harness/ollama_steward/`, Halo 3.3.4.0 R1,
docs/MODELS-ollama-steward.md): the knowledge (`ollama_steward/
knowledge/*.md`, every claim tagged to `SOURCES.md`) and the hardware card
-- `ollama_steward/hardware_sources.py` (the parsers: the log's startup
block, `nvidia-smi` CSV, `system_profiler`, `/api/ps`),
`ollama_steward/hardware_readers.py` (the read-only readers: the log or
journald, the API, the GPU tools, over ssh for a remote host),
`ollama_steward/hardware.py` (the card and its lines) and
`ollama_steward/cli.py` (`halo ollama hardware`, `traffic`, `events`). R2,
every call leaves a record: `ollama_steward/ledger.py` (the ledger line,
`traffic.jsonl` written under a lock and rotated, read back, a calibration
load's line), `ollama_steward/ledger_call.py` (the observer
`agent/loop.py`'s `_stream` wraps every local-server call in),
`ollama_steward/ledger_switch.py` (3.3.5.0 R0: the line's `switched_from` and `fitted`),
`ollama_steward/traffic.py` (the rollups per host and model),
`ollama_steward/server_rules.py` (one server-log line to an event),
`ollama_steward/server_context.py` (the rules that need the lines around a
line and a clock), `ollama_steward/server_events.py` (`events.jsonl`, the
quiet period, the `/api/ps` deltas) and `ollama_steward/server_log.py` (the
read-only tail, journald, the watch loop); `fleet/ollama_share.py` sends a
member's ledger lines to its hub and appends them there. R3: `ollama_steward/rules.py` (gather, the finding), the rules in
`ollama_steward/rules_window.py`, `ollama_steward/rules_reply.py`, `ollama_steward/rules_host.py`, `ollama_steward/fit.py` (the planner),
`ollama_steward/profiles.py` (`ollama.profiles`), `ollama_steward/steward.py` (modes, journal, undo), `ollama_steward/cli_steward.py`;
`providers/ollama_fit_parts.py` (the corrected memory arithmetic), `agent/ollama_window_steward.py` (compaction before the call).
R4: `ollama_steward/job.py` (the one job per state dir: the tail, the timer, the frames), `ollama_steward/job_state.py` (its lock and status), `ollama_steward/notes.py` (the note lines, the hub's note on a member), `ollama_steward/agent.py` + `ollama_steward/agent_prompt.py` + `ollama_steward/agent_proposals.py` (the model, what it reads, its checked proposals), `ollama_steward/explain.py` (`halo ollama explain`); `tui/steward_notice.py` (the status bar and transcript line), `fleet/steward_attention.py` (the attention row).
R5: `studio/ollama_steward_api.py` (the `ollama/` routes: the steward, the hosts, the timeline, apply / dismiss / undo / run), `studio/ollama_hosts_view.py` (per host the card through a 60 s cache, the rollups, the models, the findings and the fit plan; the Hugging Face local servers' rows), `ollama_steward/steward_rollback.py` (the rollback judge, out of `steward.py`, which gained the profile lock and Dismiss), `commands/ollama_slash.py` (`/ollama`) and `ui/src/routes/fleet/Ollama*.tsx` + `ostore.ts` (the Ollama panel), `ui/src/routes/settings/OllamaBlock.tsx`, `ui/src/routes/setup/StewardLine.tsx`.
3.3.5.0 R0b (the model card): `providers/model_card.py` (`card_of`: what a model is and its sources),
`providers/model_card_purpose.py` (the family rules as code), `providers/model_card_words.py` (the `how` lines, the
chips), `providers/fit_meter.py` (fits / tight / spill / no), `agent/main_model_check.py` (the main-model line and the
coder-lane lineup), `agent/model_card_switch.py` (the card and the check in a `/model` switch), `model_card_cli.py`
(`halo models show`, `--cards`), `studio/model_card_api.py` (`models/card`, `models/lane`, `models/effort`,
`models/think`), `ollama_steward/rules_card.py` (`called-wrong`), `tui/widgets/lane_offer.py` +
`tui/lane_offer_flow.py` (the one-key offer), `ui/src/lib/ui/FitMeter.tsx`, `ui/src/routes/shared/ModelCard.tsx`,
`ui/src/routes/session/EffortMenu.tsx`.

**Packs** (`halo_harness/packs/`, Halo 3.2.0.0 R1, docs/PACKS.md): the
names (`packs/names.py`: ids, `<id>--<name>`, the `pack:<id>` label and
`read_only_source`), `packs/semver.py` (versions and ranges),
`packs/manifest.py` (pack.yaml: read and validate; its shape is
`schemas/pack_yaml.py`, its JSON twin `packs/schema/pack.schema.json`),
`packs/discover.py` (the packs on disk, nearest first), `packs/state.py`
(state.json), `packs/settings.py` (`packs.settings.<id>` against the pack's
schema), `packs/resolve.py` (requires, the API and Halo ranges, cycles),
`packs/registry.py` (the active packs, cached), `packs/conflicts.py` (one name
offered twice), `packs/offers.py` (the names a pack offers, by kind),
`packs/grants.py` (requests, grants, enable and disable),
`packs/contribute.py` (the plugin roots, the bio and lineup tier, the hook and
MCP grant filters), `packs/journal.py` (the journal and its journaled writes),
`packs/fetch.py` (a folder or a git url), `packs/install.py` (install and
update), `packs/remove.py` (remove; your work stays), `packs/doctor.py`
(every problem), `packs/cli.py` and `packs/cli_views.py` (`halo pack`);
`where/pack_files.py` is the packs group of `halo config where`. 3.2.0.0 R2,
a pack's bios and lineups: `packs/bio_models.py` (`models.capabilities` to the
best catalog model), `packs/bio_rules.py` (what a pack's bio and lineup may not
say, with the manifest), `packs/memory.py` (a pack bio's memory namespace,
recall's filter), `packs/lineup_run.py` (`workflows`, `acceptance.test` /
`review` as the Orchestra defaults), `packs/roles.py` (the bios and lineups
`halo pack inspect` / `doctor` and the list groups read), `packs/clone.py`
(Clone into your folder); `studio/packs_roles_api.py` is Studio's
`roles/packs` and `roles/clone`. 3.2.0.0 R3, Studio contributions:
`packs/studio_rules.py` and `packs/studio_keys.py` (what `contributes.studio` may say, with the manifest: the
panels, then the other keys),
`packs/studio_registry.py` (the registry the shell reads: ids qualified, routes
resolved, grant state); `studio/packs_studio_api.py` (`/api/pack/...`: the
registry, a pack's files and bundle, its settings form) and
`studio/packs_studio_live.py` (the `pack_changed` frame; 3.2.2.0 R6: `studio/files_live.py`, the
`files_changed` frame for the lineup, bio, config and layout files). 3.2.0.0 R4, Fleet
capabilities: `packs/fleet_rules.py` (what `contributes.fleet` may say, with
the manifest: names, requires, no path in a description, no secret or
environment reference anywhere), `packs/fleet_registry.py` (each running
pack's capabilities, available here or not and why: the catalog's `packs`
section; the worker's refusal line; a pack lineup's mission metadata) and
`packs/contrib_views.py` (`halo pack inspect`'s contributes block, the doctor's
fleet-capability rows) and (3.2.1.0 R3) `packs/fleet_share.py` (an inspector
line's text for the catalog, `fleet.capabilities.hide` for a pack capability,
the pack refusal lines the hub re-plans on). 3.2.0.0 R5, workflows and artifacts (docs/WORKFLOWS.md):
`packs/workflow_rules.py` and `packs/workflow_stages.py` (what a workflow file
may say, with the manifest; its shape is `schemas/workflow_yaml.py`, its JSON
twin `packs/schema/workflow.schema.json`), `packs/typed.py` (artifact and
event schemas, their check and view hint), `packs/events_log.py` (each pack's
kept events, the running check), `packs/event_triggers.py` (a bio's trigger on
`<pack>:<kind>`), `packs/memory_meta.py` (a memory entry's provenance, sharing
and retention), `studio/workflow_api.py` (a run's artifact and an artifact
panel's latest); the compile itself is `halo_harness/workflows/`:
`workflows/spec.py` (a pack's workflow, found by its reference), `workflows/inputs.py`
(the typed inputs and their check), `workflows/conditions.py` (a stage's `when`),
`workflows/compile.py` (a workflow and its inputs compiled to a Goal, its hand-offs
and a pinned plan), `workflows/bounds.py` (the compiled block in goal.json),
`workflows/pinned.py` (the lead's split of a workflow run, the stage set pinned),
`workflows/runtime.py` (a lane's stage each time its worker starts),
`workflows/gate.py` (the quality gate widened with typed outputs and evidence),
`workflows/outputs.py` (a run's outputs and its part of the report),
`workflows/cli.py` (`halo workflow`) and `workflows/goal.py` (a workflow run as a
goal of the supervisor, `halo goal add --workflow`). 3.2.0.0 R6, the Pack Manager
and the reference pack: `packs/sources.py` (where a bare id is looked for:
`packs.sources`, then the packs Halo ships under `templates/packs/`; `halo pack
sources`, `list --available`), `packs/manager.py` (what Studio's Packs section
shows: each pack's list row, inspect payload, health, compatibility lines and
workflows, the sources) and `studio/packs_manager_api.py` (its routes, each
running the function `halo pack` runs). 3.2.0.0 R7, compatibility and the
lifecycle hardened: `packs/update.py` (`halo pack update [--dry-run]`: the
migration notes first, the new version staged and swapped in by two renames,
the old kept as `<id>.previous`; 3.2.1.0 R4: the files that change one line
each, and `confirm`, the question `packs/cli.py` asks in a terminal unless
`--yes`), `packs/rollback.py` (`halo pack rollback`),
`packs/migrate.py` (a pack's `migrations` between two versions, the `settings`
renames applied and journaled), `packs/deprecations.py` (the doctor's rows for
an extension API name announced for removal and a grant an update asked for)
and `packs/interpreter.py` (`${halo_python}` and PYTHONPATH for a pack's hook
and MCP server; 3.2.1.0 R4: `${CLAUDE_PLUGIN_ROOT}` in any plugin hook's shell
`command`, filled for the quotes it sits in, forward slashes on Windows).

**The extension API** (`halo_harness/ext/`, API 1.0, docs/EXTENSION_API.md):
`ext/names.py` (the name rules), `ext/yamlio.py` (`read_yaml`, `write_yaml`),
`ext/schema.py` (`check_schema`), `ext/config.py` (`get_config`,
`set_config`), `ext/files.py` (`pack_dir`, `data_dir`, `write_private`),
`ext/events.py` (`publish_event`), `ext/grants.py` (`is_granted`),
`ext/memory.py` (`memory.write`, 3.2.0.0 R5), `ext/compat.py` (the version policy: `api_version`,
`compatible`, `deprecations`, 3.2.0.0 R7); the package's `__init__` is the contract.

**Isolation** (`halo_harness/isolation/`, Halo 3.1.8.0 R5, docs/ISOLATION.md):
`isolation/spec.py` (the `isolation` / `secrets` declarations, their
checks, what a lane runs with), `isolation/lane.py` (`prepare`: the opt-ins
applied where a worker starts), `isolation/container.py` (the `docker run`
argv, the image, the build), `isolation/seed.py` (the scoped state dir),
`isolation/scoped_user.py` (the `sudo -n -u` argv and the share step),
`isolation/secrets.py` (the broker reads, the strip names, `halo secrets`),
`isolation/capabilities.py` (the one table, which list wins, the narrowing),
`isolation/lines.py` (the report lines), `isolation/declared.py` (what your
lineups and bios declare), `isolation/doctor_rows.py` (the two doctor rows),
`isolation/cli.py` (`halo isolation`), `isolation/tools_view.py` (`/tools`);
`isolation/brokers/` holds one file per broker (`onepassword.py`, `env.py`)
and `isolation/Dockerfile` the worker image.

- The guided first run (3.1.1.0; 3.2.2.0 R2: `start/card.py` the card it opens on, `start/checks.py` +
  `start/checks_run.py` the five checks behind the wizard's Summary, `check_cli.py` (`halo check`),
  `tui/dialogs/summary_checks.py` + `check_rows.py` the Summary's rows): `studio/start_api.py` (Start here: `/api/start`),
  `studio/start_job.py` (the one `halo start` Studio runs, its `start` frames),
  `studio/glossary_api.py` (`GET /api/glossary`, docs/GLOSSARY.md); the guided run
  itself is `halo_harness/start/` (engine, steps, the sample repo, the fake model calls)
- Setup's Ollama finders (3.3.0.0 R5): `studio/setup_discover_api.py` (`setup/ollama/find`, `scan`, `add`,
  `measure`: `providers/ollama_discover.py` and the calibration from the page) and
  `studio/setup_discover_jobs.py` (the scan and measure background jobs, their `setup` frames, the rows found)
- Studio's Setup section (3.3.0.0 R1): `studio/setup_api.py` (its routes: `GET setup/state`,
  `POST setup/config` for model / permission_mode / theme, `POST setup/team`, the Team preview),
  `studio/setup_state.py` (what the state holds, read from the places the wizard reads) and
  `lineup_choice.py` (the Team step's three writes, called by the wizard and by Setup alike);
  R2: `studio/setup_providers_api.py` (the Providers and Local models routes, each calling the
  wizard's writer) and `studio/setup_providers_state.py` (the provider cards' masked state, the
  Ollama hosts, the Hugging Face entries, the model folders, the runtime, the detection lines).
  R3: `studio/setup_check_api.py` (the Check and Linux fixes routes), `studio/setup_check_job.py`
  (the Check job: `start/checks.py` run in order on a thread, `setup` frames, the guided first run
  through `start_job`), `studio/setup_check_state.py` (the checks, the card, the last check, the
  Linux fixes, the fresh-home flag) and `providers/local_models_cached.py` (the local model rows
  from what is cached, never a probe: `build_local_view(cached=True)` for a page read).
  R4: `studio/setup_door.py` (the doors: `SetupTarget` = `setup`, `setup:first`, `setup:<block>` as an
  edit target, `?mode=setup&first=1` / `&block=team`; the no-browser rule; `open_setup` starting or
  reusing Studio; `cli_door`, the one line `halo init`, `halo setup` and `halo start` print before the
  terminal wizard runs as the fallback) and `ui/src/routes/setup/door.ts` (the page's side).
  3.3.3.0 R1: `studio/setup_done.py` (the Summary's Done: `POST setup/done`, `setup-done.json`,
  `setup_done_at` the one reader), `init_wait.py` (`halo init` waiting for it, then bare halo through
  `cli.launch_bare`) and `ui/src/routes/setup/done.ts` (the page leaving Setup for Session).
- Studio's Settings section (3.3.3.0 R2): `settings_catalog.py` (every `~/.halo/config.json` key as one row:
  key, group, title, kind, default, choices, help, effect, secret; the rows in `settings_catalog_rows_{a,b,c}.py`;
  `cli_line`, `match` for a keyed row's entry), `studio/settings_api.py` (`GET settings/catalog`,
  `GET settings/values`, `POST settings/set`, `POST settings/unset`, through `theme.set_config_value`),
  `studio/settings_values.py` (each row's masked value against its default, a keyed row's entries, a posted value
  coerced and checked by kind and choices), `studio/settings_door.py` (`SettingsTarget` = `settings`,
  `settings:<group>` as an edit target, `?mode=settings&group=fleet`), `settings_cli.py` (`halo settings`) and
  `ui/src/routes/settings/` (the group rail, one page per group, a row per key, one field per kind).
