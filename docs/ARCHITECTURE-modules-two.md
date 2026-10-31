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
`ollama_steward/ledger_prompt.py` (3.3.5.0 R4: the prompt budget's fields -- the composition, the prefix,
the preflight's decision, `warming`, `cache_reused_pct`),
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
- Studio's Local section (3.3.5.0 R1, docs/STUDIO-local.md): `ollama_steward/resources.py` (the sampler: one sample a
  second per host this machine serves while the tab or the steward job holds it on, the 5-minute STORE, the watch
  lease), `ollama_steward/resources_readers.py` (nvidia-smi, rocm-smi, a Mac's ioreg and sysctl, the compute processes),
  `ollama_steward/resources_system.py` (RAM and CPU per OS: /proc, GlobalMemoryStatusEx / GetSystemTimes, memory_pressure
  and ps), `ollama_steward/resources_share.py` (the recent file, a member's samples on its ledger push and the hub's
  side, the member that serves a host, the planner's `others_for`), `ollama_steward/ledger_tap.py` (every ledger line and
  server event published: a listener in Studio's process, else a POST to the Studio running for the home),
  `ollama_steward/ledger_bytes.py` (`bytes_in` / `bytes_out`), `providers/ollama_load.py` (Load / Unload: a generate with
  no prompt and a keep-alive), `fleet/control_models.py` (`ollama_load` / `ollama_unload` from a hub, under
  `fleet.allow_control`), `fleet/ollama_share_take.py` (the member's side of the push's answer, out of
  `fleet/ollama_share.py`), `studio/local_api.py` (the `local/` routes), `studio/local_hosts_view.py` (every host as a
  card and its controls), `studio/local_models_view.py` (every model per host, its card, its meter, the intent scores),
  `studio/local_traffic.py` (the ledger as rows, the per-host minute buckets, the tap's `traffic` frames),
  `studio/local_warm.py` (3.3.5.0 R4: a model row's "warm" / "cold (~N s to load)" and "cache reused N %"),
  `studio/local_catalog.py` (one catalog per host keyed by `/api/tags`' signature), `studio/local_door.py`
  (`LocalTarget` = `local`, `local:<page>`, `?mode=local&page=hosts`), `local_tab_cli.py` (`halo local` opens it,
  `halo local hosts | models | resources` print) and `ui/src/routes/local/` (the page rail, the seven pages, the
  strips, the traffic view, the host cards, the model rows).
- Local -> Library (3.3.5.0 R2, docs/STUDIO-local.md "Library"): `models_library/` -- `ollama_library.py`
  (ollama.com/library and a model's tags page, parsed from HTML; `ShapeChanged` when the markup moves),
  `ollama_registry.py` (the registry's manifest and config blob), `hf_hub.py` (the hub's search, a repo's files, its
  config.json as a shape; the token for a gated repo), `snapshot.py` (`snapshot_ollama.json`, the shipped catalog),
  `cache.py` (`<state>/cache/models-library.json` and the one fetch through `providers/http.urlopen_tls`), `shapes.py`
  (a family's shape before it is installed), `row_builders.py` (LibraryRow from each listing), `rows.py`
  (`card_for_row`, `fit_for_row`), `browse.py` (the query) -- with `studio/models_library_api.py` (the `local/library`
  routes), `models_browse_cli.py` (`halo models browse`), `tools/library_snapshot.py` (takes the snapshot) and
  `ui/src/routes/local/Library*.tsx` + `libstore.ts`.
- Ollama, controlled (3.3.5.0 R3, docs/STUDIO-local.md "Jobs"): `providers/ollama_control.py` (pull streamed with a
  cancel, delete, show and its facts, copy, rename, `/api/ps`), `providers/ollama_guard.py` (under the test flag no
  catalog reader reads the made-up default host, and no control call leaves for anything but a loopback fake),
  `studio/local_pull_job.py` (one pull job per host and name, its `pull` frames, `current()`, the caches dropped after
  a success), `studio/local_control_api.py` (the `local/` pull / delete / show / copy / rename / twin / loaded / uses
  routes), `studio/local_uses.py` (`uses_of`: what names a model), `fleet/control_models.py` (`ollama_pull`,
  `ollama_delete`, `ollama_copy`, `ollama_twin` from a hub) with `fleet/control_pulls.py` (a member's jobs on its
  ledger push), `models_control_cli.py` (`halo models pull | rm | load | unload | copy | rename | twin | loaded`) and
  `ui/src/routes/local/` `jobs.ts`, `Pulls.tsx`, `LibraryPull.tsx`, `ctl.ts`, `ModelCards.tsx`, `LoadedNow.tsx`.
- Hugging Face local, controlled (3.3.5.0 R5, docs/STUDIO-local.md "Hugging Face"): `providers/hf_download.py` (a repo or
  a file into a model folder through the hub cache's layout: the licence line first, `Range` resume from a `.part`,
  the sha256 / git blob id check, the token for a gated repo), `providers/local_server.py` + `local_server_cmd.py` (a
  managed `llama-server` / `mlx_lm.server`: the fit planner's flags and their sources, the log, `/health` until ready,
  the registry row, stop, tail, status, the exit sweep), `studio/local_download_job.py` (the pull jobs' store with kind
  `download`), `studio/local_hf_view.py` (the folders and what is on disk, with the card, the fit and who serves it),
  `studio/local_hf_api.py` + `studio/local_server_api.py` (the `local/hf/*`, `local/download*`, `local/server*` routes),
  `local_hf_cli.py` + `local_hf_serve_cli.py` (`halo local download | ls | rm | serve | stop | servers | log`) and
  `ui/src/routes/local/` `HfPage.tsx`, `HfRow.tsx`, `HfCards.tsx`, `hfstore.ts`.
- The battery (3.3.6.0 R1, docs/MODELS-cards.md "The profile"): `providers/battery_probes.py` (the six probes and how
  each answer is read), `providers/capability_battery.py` (`run`: the requests, the fit, the profile kept in
  `providers/ollama_capability.py`'s cache by digest + Ollama version + probe set), `providers/battery_profile.py` (the
  derived labels), `providers/placement.py` + `placement_apply.py` (the rules, the gates, the reserve, the pivot
  schedule), `providers/model_card_blocks.py` (the card's four blocks), `providers/ollama_twin_verify.py` (a fitted twin
  verified), `agent/local_failure.py` + `ollama_steward/failure_lines.py` (the failure lines),
  `ollama_steward/probe_new.py` (the steward's job probes a new model), `studio/local_probe_job.py` +
  `studio/local_probe_api.py` (the probe jobs and routes), `studio/local_twin_verify.py` (raw tag vs twin, the verify
  thread), `fleet/control_probes.py` (a member's profiles on its ledger push), `models_probe_cli.py`
  (`halo models probe`), `doctor_local_roles.py` and `ui/src/routes/local/` `probes.ts`, `ProbeBits.tsx`,
  `ui/src/routes/shared/ModelCardBlocks.tsx`.
- The search (3.3.6.0 R2, docs/STUDIO-local.md "The search", docs/MODELS-cards.md "the three truths"):
  `models_library/truths.py` + `truth_rules.py` (declared / expected / verified per capability and fit fact),
  `search.py` (the gates, the ranking, the verdicts), `search_filters.py` (fit, supply, licence, platform, the
  architectures per Ollama version), `search_cost.py` (the cost preview), `search_query.py` (the search as browse.py
  runs it, the resource strip), `presets.py` + `presets_save.py` (the nine presets, the sentence parser, Save as role
  template, the role offer), `role_gaps.py` (a lineup's gaps), `ollama_steward/fingerprints.py` (the crash
  fingerprints, `halo ollama crashes`), `studio/local_verify_job.py` (Download and verify: the pull, the battery, the
  offer), `studio/local_search_api.py` (the presets, template, verify, assign and crashes routes),
  `doctor_local_ids.py` (dead role ids, Ollama version drift) and `ui/src/routes/local/` `SearchBar.tsx`,
  `SearchFilters.tsx`, `LibraryRowBits.tsx`, `VerifyList.tsx`, `verify.ts`.
- Logs and diagnostics (3.3.6.0 R3, docs/MODELS-ollama-logs.md, docs/STUDIO-local.md "Logs"):
  `ollama_steward/server_log_remote.py` (another machine's log over its `ssh:` entry: the read command, base64 bytes,
  the per-host state, rotation, the journal, Windows), `ollama_steward/log_tail.py` (the bounded tail of any host,
  `halo ollama log`'s reader, the steward job's remote reads), `ollama_steward/log_status.py` (live, stale, quiet,
  unreadable, on that machine, missing; the ladder; the line groups), `ollama_steward/fingerprint_facts.py` (the load
  block: `load-result` events, the load a crash died in, `crashes --why`), `ollama_steward/rules_crash.py` (a crash
  that repeats proposes the fix), `ollama_steward/cli_logs.py` (`halo ollama log`, `events`, `crashes`),
  `agent/ollama_log_recovery.py` (the log read after each call drives the recovery, the preflight's evidence),
  `providers/fit_evidence.py` (the fit badge's evidence), `fleet/control_probes.py` `read_events` / `take_events` (a
  member's server events on its ledger push), `studio/local_logs_api.py` (the Logs routes) and `ui/src/routes/local/`
  `LogsPage.tsx`, `LogTail.tsx`, `LogModelRows.tsx`, `logstore.ts`, `ui/src/routes/shared/FitEvidence.tsx`.
- Measured cards and the dialect record (3.3.6.0 R4, docs/MODELS-cards.md "Measured", "The dialect record", "The KV
  dial"; docs/MODELS-ollama-logs.md "The degradation ladder", "The model shelf"): `providers/battery_multitool.py` (the
  battery's multi-tool probe: tool-call accuracy), `providers/measured.py` (the measured facts, each with its source,
  date and n), `providers/model_card_measured.py` (the card's Measured, dialect and KV-dial blocks),
  `providers/dialect.py` (the record, your edits), `providers/dialect_refine.py` (the ledger's rules per the apply
  modes), `providers/dialect_apply.py` (the record applied: the body, fences, the repair loop's bound, the loop guard,
  the tool budget), `providers/kv_dial.py` (the windows per KV type, the crash note), `models_library/shelf.py` (last
  use, Retire, the shelf, Re-pull), `agent/postmortem.py` (Why this answer?), `agent/degrade.py` (the degradation
  ladder), `models_card_facts_cli.py` (`halo models measured | dialect`), `models_shelf_cli.py` (`halo models retire |
  shelf`), `studio/local_card_api.py` (the measured and dialect routes), `studio/local_shelf_api.py` (the shelf
  routes), `studio/postmortem_api.py` (`GET sessions/<sid>/postmortem`) and `ui/src/routes/shared/DialectBlock.tsx`,
  `ui/src/routes/local/ShelfBits.tsx`, `ui/src/routes/session/Why.tsx`, `ui/src/styles/model-measured.css`.
