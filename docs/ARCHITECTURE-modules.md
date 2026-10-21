# Architecture: the module map

Read this when you look for the module behind a Studio, fleet, Orchestra or team feature.

Part of [Architecture](ARCHITECTURE.md), which lists every part.

## Module map: Studio, fleet, Orchestra, team, supervise

One responsibility per module, named for it (3.1.0.0 R2 re-cut every module
named by line count: no `*_more.py`, `*2.py`, `*_extra*.py` or `*_rest.py`
is left in `halo_harness/`, and `tests/test_invariants.py` keeps it so).
Every module of these packages is listed here; the same test checks
this list against the tree.

**Studio** (`halo_harness/studio/`):

- the server and the shell: `studio/server.py` (the loopback server, the
  token, the CSP), `studio/api.py` (the JSON routes and their dispatch),
  `studio/raw_body.py` (a route that answers with bytes), `studio/launch.py`
  (start, find and stop Studio's own process), `studio/model.py` (what Studio
  shows, built from the wizard's and the CLI's functions)
- the live feed: `studio/events.py` (the registry watcher), `studio/events_sse.py`
  (`GET /api/events`), `studio/feed_kinds.py` (the frame kinds it asks for)
- Roles and models: `studio/roles_api.py`, `studio/roles_findings.py`,
  `studio/models_api.py`; the coach:
  `studio/coach_api.py`, `studio/coach_probe_job.py` (3.1.6.0: the probe on
  a thread, its step lines on the feed); the live sessions: `studio/sessions_api.py`; the
  config checks behind Roles' Problems panel: `studio/doctor_config_api.py`
  (`GET /api/doctor/config`, the rows of `halo doctor --config`)
- one editor (3.1.1.0): `studio/edit_target.py` (what `halo studio --edit`
  names: bio, lineup, team, and its URL), `studio/edit_open.py` (open Studio
  on it, or focus the Studio already running), `studio/focus_api.py`
  (`POST /api/focus`, the `focus` frame), `studio/field_help_api.py`
  (`GET /api/field-help`, `halo_harness/field_help.py`'s lines for the bio
  form and the lineup inspector)
- the model catalog (3.1.4.0 R4): `studio/catalog_env.py` (the env a session
  resolves providers with: the env file, the shell, the settings.json `env`
  chain), `studio/models_refresh.py` (Refresh: every provider at once,
  time-boxed, one outcome line each, kept with its time),
  `studio/models_fallback.py` (`GET /api/models/fallback`: the refs in use and
  the shipped OpenRouter list, not verified), `studio/models_resolve.py`
  (`GET /api/models/resolve`: what a role runs on)
- the Session dashboard (3.1.4.0): `studio/session_open.py` (a section
  target: Session on a session or any section, for `/studio` and `halo studio
  --session`; this harness's live sessions; the served page's
  `data-live-session` mark)
- Design: `studio/design_api.py` (the routes, a turn, comments, knobs, the
  direct edit), `studio/design_artboards_api.py` (one artboard: versions,
  restore, contrast, rename, delete), `studio/design_assets_api.py` (the
  assets folder), `studio/design_critique_api.py` (variants and the critique),
  `studio/design_system_api.py` (the design system and its sync),
  `studio/design_export_api.py` (exports and the handoff),
  `studio/design_request.py` (the lookups every route shares),
  `studio/design_turns.py` (the live turns), `studio/design_api_edit.py` (the
  text picker script), `studio/design_files.py` (the raw artboard files)
- Media: `studio/media_api.py`, `studio/media_render.py`
- Orchestra: `studio/orchestra_api.py`, `studio/orchestra_plan_api.py`,
  `studio/orchestra_model.py`, `studio/orchestra_live.py`
- the supervisor's morning line (3.1.8.0 R1): `studio/supervise_api.py`
  (`GET /api/supervise/summary`, the Session landing's "N done, M waiting, $X")
- Team: `studio/team_api.py`, `studio/team_init_api.py`, `studio/team_live.py`,
  `studio/team_budget_api.py` (3.1.2.0 R2: the answer to a stage held at its budget line)
- Fleet: `studio/fleet_api.py` (agent commands on a live session),
  `studio/fleet_hub_api.py` (the fleet routes and their dispatch),
  `studio/fleet_pair_api.py` (pair, settings, kick, history),
  `studio/fleet_panels_api.py` (the R4 panels), `studio/fleet_answer.py` (one
  key on an attention row), `studio/fleet_handoff_api.py` (an agent's
  hand-off), `studio/fleet_recording_api.py` (flight recordings, the replay),
  `studio/fleet_capabilities_api.py` (capabilities, who),
  `studio/fleet_mission_api.py` (missions), `studio/fleet_watch.py` (the
  watcher), `studio/fleet_watch_sources.py` (what it reads),
  `studio/fleet_feed.py` (its tap on the live feed), `studio/fleet_send.py`
  (a session command, this harness's or a member's)
- the one unit view (3.1.2.0): `studio/work_api.py`
  (`GET /api/work/<kind>/<run>`, the units of any run; docs/WORK.md)
- recall (3.1.2.0 R3): `studio/recall_api.py` (`GET /api/recall?q=&fleet=1`
  for the recall box, `GET /api/fleet/recall?q=` the hub's merged view)

**Fleet** (`halo_harness/fleet/`):

- who and where: `fleet/identity.py`, `fleet/store.py`, `fleet/protocol.py`,
  `fleet/tls.py`, `fleet/pair_kex.py`, `fleet/pairing.py`
- the hub: `fleet/hub.py`, `fleet/hub_http.py`, `fleet/hub_join.py`,
  `fleet/hub_links.py`, `fleet/hub_state.py`, `fleet/hub_commands.py`,
  `fleet/hub_capabilities.py`, `fleet/hub_mission.py`
- the relay of a joined harness: `fleet/relay.py`, `fleet/relay_hub.py`,
  `fleet/relay_runtime.py`, `fleet/relay_stream.py`, `fleet/control.py`,
  `fleet/local_view.py`, `fleet/agent_tokens.py` (each agent row's own tokens,
  from its transcript)
- the CLI: `fleet/cli.py` (the dispatcher, serve, pair), `fleet/cli_join.py`
  (join, leave, status), `fleet/cli_members.py` (members, kick),
  `fleet/cli_panels.py` (record, digest), `fleet/cli_caps.py` (capabilities,
  who), `fleet/cli_mission.py` (missions), `fleet/table.py`,
  `fleet/table_live.py`
- the panels: `fleet/attention.py`, `fleet/team_attention.py`,
  `fleet/supervise_attention.py` (3.1.8.0 R1: the supervisor's parked decisions),
  `fleet/caps.py`, `fleet/conflicts.py`, `fleet/digest.py`,
  `fleet/journal.py`, `fleet/health.py`, `fleet/push.py`, `fleet/handoff.py`,
  `fleet/history.py`, `fleet/recording.py`, `fleet/recording_page.py`
- capabilities: `fleet/capabilities.py`, `fleet/capabilities_host.py`,
  `fleet/capabilities_probe.py`, `fleet/capabilities_sources.py`,
  `fleet/capabilities_view.py`, `fleet/capabilities_who.py`
- missions: `fleet/mission.py`, `fleet/mission_api.py`,
  `fleet/mission_store.py`, `fleet/mission_doc.py`, `fleet/mission_plan.py`
  (the lead's split), `fleet/mission_plan_check.py` (its answer made into a
  checked plan), `fleet/mission_assign.py` (which harness takes which part),
  `fleet/mission_claims.py` (claims as paths), `fleet/mission_run.py`,
  `fleet/mission_dispatch.py`, `fleet/mission_worker.py`,
  `fleet/mission_worker_run.py`, `fleet/mission_worker_session.py`,
  `fleet/mission_guard.py`, `fleet/mission_files.py`,
  `fleet/mission_handoff.py`, `fleet/mission_merge.py`,
  `fleet/mission_report.py`, `fleet/mission_attention.py`,
  `fleet/mission_stage_run.py` (3.1.2.0 R2: a part of kind orchestra, a delegated team stage's run)
- recall across the fleet (3.1.2.0 R3): `fleet/hub_recall.py` (the hub fans a
  recall query out and merges the hits; 3.1.6.0 its `local/coach-library`
  route forwards a library fetch to one member), and the scripted two-machine check
  `fleet/live_check.py` with its `--fake` seams `fleet/live_check_fakes.py`
  (`tools/live_fleet_check.py` is the CLI; `halo_harness/recall_fleet.py` and
  `halo_harness/recall_cli.py` are the member's side and `halo recall`)

**Orchestra** (`halo_harness/orchestra/`, its CLI beside the package):

- the run: `orchestra/goal.py`, `orchestra/workflow.py`, `orchestra/index.py`,
  `orchestra/split.py`, `orchestra/plan.py`, `orchestra/plan_check.py`,
  `orchestra/workers.py`, `orchestra/worker_result.py`, `orchestra/lanes.py`,
  `orchestra/handoff_spec.py`, `orchestra/handoff.py`, `orchestra/handoff_run.py`,
  `orchestra/merge.py`, `orchestra/hunks.py`, `orchestra/gate.py`,
  `orchestra/report.py`, `orchestra/run.py`, `orchestra/adapters.py`,
  `orchestra/gitops.py`, `orchestra/stale.py` (3.1.2.0 R2: a downstream lane re-based
  before the merge), `orchestra/forecast.py` (3.1.2.0 R2: the plan's cost forecast)
- the shared files: `orchestra/claims.py`, `orchestra/guard.py`,
  `orchestra/events.py`, `orchestra/jsonl.py`, `orchestra/view.py`
- the coach: `orchestra/coach.py` (the card, the cache, the overlay), the
  rules once for every run kind (`orchestra/coach_rules.py`), one thin
  evidence loader per run kind (`orchestra/coach_orchestra_rules.py`,
  `orchestra/coach_mission_rules.py`,
  `orchestra/coach_team_rules.py`), `orchestra/coach_lane_facts.py` (an
  Orchestra run's lanes as facts), `orchestra/coach_prices.py` (the model
  catalog and its prices); 3.1.3.0 the loop: `orchestra/coach_ask.py` (the
  lead's paragraph per card), `orchestra/coach_apply.py` (Apply through the
  editors' writers, the confirm card), `orchestra/coach_record.py` (the
  applied record, Undo, the summary line, the runs the coach read); 3.1.6.0
  the probes: `orchestra/coach_probe.py` (the cost line, the lead's draft,
  the whole probe, probe.json), `orchestra/coach_probe_schema.py` (the
  candidate's strict shape and the run facts it is checked against),
  `orchestra/probe_runs.py` (a probe run's folder under the reference, its
  plan, the budget, the threads, the cleanup), `orchestra/probe_overlay.py`
  (the overlay in a lane worktree's project scope and on the worker's argv),
  `orchestra/coach_compare.py` (the deliverables, the anonymized judge, the
  contrast), `orchestra/coach_compose.py` (adopt, merge or keep, and the
  writes Apply makes), `orchestra/coach_probe_card.py` (the one card, its
  grouped Apply, the CLI's table), `orchestra/coach_probe_prompt.py` (the
  lead's draft prompt, with the library's lessons); 3.1.6.0 the improvement
  library: `orchestra/coach_library.py` (the entries in
  `~/.halo/coach/library/`: born on Apply, undone with Undo, forget),
  `orchestra/coach_experience.py` (what an entry says: EXPERIENCE.md, the
  project and its remote path, the overlay), `orchestra/coach_citations.py`
  (the citation rule, the card's line and `library_hits`, the probe's
  lessons), `orchestra/coach_library_share.py` (the fleet: a member's
  `coach_library` answer, `fetch`)
- the CLI: `orchestra_cli.py` (the parser, the dispatch, `new`),
  `orchestra_cli_views.py` (status, claims, log, runs, lanes, report),
  `orchestra_cli_run.py` (run, stop), `orchestra_cli_plan.py` (plan, approve,
  reject), `coach_cli.py` (`halo coach` and the coach verbs;
  `halo_harness/coach_library_cli.py` is `halo coach library`)

**The unit of work** (`halo_harness/work/`, Halo 3.1.2.0 R1, docs/WORK.md):
the shared model a lane, a mission part and a team stage all
are -- `work/unit.py` (the `Unit`), `work/states.py` (the one state machine
and the three alias tables), `work/claims.py`, `work/handoff.py`,
`work/gate.py`, `work/ledger.py` (the `LedgerLine`), `work/report.py` (the
`UnitRow`), `work/store.py` (`UnitStore`), and one adapter per kind
(`work/adapters/lane.py`, `work/adapters/part.py`, `work/adapters/stage.py`),
the only place that knows each engine's files;
`work/forecast.py` (3.1.2.0 R2: a unit's forecast line, its price and the
total against a budget).
`halo_harness/work_cli.py` is `halo work` (the units of any run as a table).

**Team** (`halo_harness/team/`): `team/spec.py` (the team file),
`team/validate.py` and `team/validate_stages.py` (`validate_team`),
`team/resolve.py` (tiers, block files and a stage's goal, shared by the
runner and the validator), `team/blocks.py`, `team/board.py`,
`team/stages.py`, `team/gate_actions.py` (accept / redo / stop and their
short forms), `team/triggers.py`, `team/run.py`, `team/run_stage.py`,
`team/parallel.py` (3.1.2.0 R2: a stage's members at once), `team/remote_stage.py`
(3.1.2.0 R2: an orchestra stage on a fleet member), `team/budget.py`
(3.1.2.0 R2: the budget line), `team/guard.py`, `team/delegate.py`,
`team/adapters.py`, `team/cli.py`, `team/cli_run.py`.

**Supervise** (`halo_harness/supervise/`, Halo 3.1.8.0 R1, docs/SUPERVISE.md):
the daemon that owns a goal queue and runs it without a TUI --
`supervise/settings.py` (the `supervise` config section), `supervise/queue.py`
(the goal store), `supervise/history.py` (the history log and the morning
summary), `supervise/pulse.py` (the pulse and the stop file),
`supervise/heartbeat.py` (an Orchestra run's cross-process runner heartbeat),
`supervise/budget.py` (a goal's and the queue's cap as a stop),
`supervise/runner.py` (the orchestra and job runners and their outcome),
`supervise/decisions.py` (the parked decisions), `supervise/asks.py` (a
supervised job's asks), `supervise/arm.py` (the lineups' schedules and
triggers, armed by the supervisor), `supervise/loop.py` (the tick),
`supervise/apply.py` (settling a goal and applying a decision),
`supervise/cli.py` (`halo supervise`) and `supervise/goal_cli.py` (`halo
goal`).

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
`where/pack_files.py` is the packs group of `halo config where`.

**The extension API** (`halo_harness/ext/`, API 1.0, docs/EXTENSION_API.md):
`ext/names.py` (the name rules), `ext/yamlio.py` (`read_yaml`, `write_yaml`),
`ext/schema.py` (`check_schema`), `ext/config.py` (`get_config`,
`set_config`), `ext/files.py` (`pack_dir`, `data_dir`, `write_private`),
`ext/events.py` (`publish_event`), `ext/grants.py` (`is_granted`); the
package's `__init__` is the contract.

- The first ten minutes (3.1.1.0): `studio/start_api.py` (Start here: `/api/start`),
  `studio/start_job.py` (the one `halo start` Studio runs, its `start` frames),
  `studio/glossary_api.py` (`GET /api/glossary`, docs/GLOSSARY.md); the guided run
  itself is `halo_harness/start/` (engine, steps, the sample repo, the fake model calls)
