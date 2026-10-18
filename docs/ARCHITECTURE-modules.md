# Architecture: the module map

Read this when you look for the module behind a Studio, fleet, Orchestra or team feature.

Part of [Architecture](ARCHITECTURE.md), which lists every part.

## Module map: Studio, fleet, Orchestra, team

One responsibility per module, named for it (3.1.0.0 R2 re-cut every module
named by line count: no `*_more.py`, `*2.py`, `*_extra*.py` or `*_rest.py`
is left in `halo_harness/`, and `tests/test_invariants.py` keeps it so).
Every module of these four packages is listed here; the same test checks
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
  `studio/models_api.py`; Org mode: `studio/paperclip_api.py`; the coach:
  `studio/coach_api.py`; the live sessions: `studio/sessions_api.py`; the
  config checks behind Roles' Problems panel: `studio/doctor_config_api.py`
  (`GET /api/doctor/config`, the rows of `halo doctor --config`)
- one editor (3.1.1.0): `studio/edit_target.py` (what `halo studio --edit`
  names: bio, lineup, team, and its URL), `studio/edit_open.py` (open Studio
  on it, or focus the Studio already running), `studio/focus_api.py`
  (`POST /api/focus`, the `focus` frame), `studio/field_help_api.py`
  (`GET /api/field-help`, `halo_harness/field_help.py`'s lines for the bio
  form and the lineup inspector)
- Design: `studio/design_api.py` (the routes, a turn, comments, knobs, the
  direct edit), `studio/design_artboards_api.py` (one artboard: versions,
  restore, contrast, rename, delete), `studio/design_assets_api.py` (the
  assets folder), `studio/design_critique_api.py` (variants and the critique),
  `studio/design_system_api.py` (the design system and its sync),
  `studio/design_export_api.py` (exports and the handoff),
  `studio/design_request.py` (the lookups every route shares),
  `studio/design_turns.py` (the live turns), `studio/design_api_edit.py` (the
  text picker script), `studio/design_files.py` (the raw artboard files)
- Flow: `studio/flow_api.py` (the routes), `studio/flow_api_edit.py` (the flow
  file's one write route), `studio/flow_request.py` (body parsing),
  `studio/flow_assets_api.py` (the assets upload), `studio/flow_model.py`
  (what the routes read), `studio/flow_runs.py` (the one live run)
- Media: `studio/media_api.py`, `studio/media_render.py`
- Orchestra: `studio/orchestra_api.py`, `studio/orchestra_plan_api.py`,
  `studio/orchestra_model.py`, `studio/orchestra_live.py`
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

**Fleet** (`halo_harness/fleet/`):

- who and where: `fleet/identity.py`, `fleet/store.py`, `fleet/protocol.py`,
  `fleet/tls.py`, `fleet/pair_kex.py`, `fleet/pairing.py`
- the hub: `fleet/hub.py`, `fleet/hub_http.py`, `fleet/hub_join.py`,
  `fleet/hub_links.py`, `fleet/hub_state.py`, `fleet/hub_commands.py`,
  `fleet/hub_capabilities.py`, `fleet/hub_mission.py`
- the relay of a joined harness: `fleet/relay.py`, `fleet/relay_hub.py`,
  `fleet/relay_runtime.py`, `fleet/relay_stream.py`, `fleet/control.py`,
  `fleet/local_view.py`
- the CLI: `fleet/cli.py` (the dispatcher, serve, pair), `fleet/cli_join.py`
  (join, leave, status), `fleet/cli_members.py` (members, kick),
  `fleet/cli_panels.py` (record, digest), `fleet/cli_caps.py` (capabilities,
  who), `fleet/cli_mission.py` (missions), `fleet/table.py`,
  `fleet/table_live.py`
- the panels: `fleet/attention.py`, `fleet/team_attention.py`,
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
  `fleet/mission_stage_run.py` (3.1.2.0 R2: a part of kind orchestra | flow, a delegated team stage's run)

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
- the coach: `orchestra/coach.py` (the card, the cache), the rules once over
  the unit model (`orchestra/coach_rules.py`), one thin evidence loader per
  run kind (`orchestra/coach_orchestra_rules.py`, `orchestra/coach_flow_rules.py`,
  `orchestra/coach_mission_rules.py`, `orchestra/coach_team_rules.py`),
  `orchestra/coach_lane_facts.py` (an Orchestra run's lanes as facts),
  `orchestra/coach_prices.py` (the model catalog and its prices)
- the CLI: `orchestra_cli.py` (the parser, the dispatch, `new`),
  `orchestra_cli_views.py` (status, claims, log, runs, lanes, report),
  `orchestra_cli_run.py` (run, stop), `orchestra_cli_plan.py` (plan, approve,
  reject), `coach_cli.py` (the coach verbs)

**The unit of work** (`halo_harness/work/`, Halo 3.1.2.0 R1, docs/WORK.md):
the shared model a lane, a mission part, a team stage and a flow step all
are -- `work/unit.py` (the `Unit`), `work/states.py` (the one state machine
and the four alias tables), `work/claims.py`, `work/handoff.py`,
`work/gate.py`, `work/ledger.py` (the `LedgerLine`), `work/report.py` (the
`UnitRow`), `work/store.py` (`UnitStore`), and one adapter per kind
(`work/adapters/lane.py`, `work/adapters/part.py`, `work/adapters/stage.py`,
`work/adapters/step.py`), the only place that knows each engine's files;
`work/forecast.py` (3.1.2.0 R2: a unit's forecast line, its price and the
total against a budget).
`halo_harness/work_cli.py` is `halo work` (the units of any run as a table).

**Team** (`halo_harness/team/`): `team/spec.py` (the team file),
`team/validate.py` and `team/validate_stages.py` (`validate_team`),
`team/resolve.py` (tiers, block files and a stage's goal, shared by the
runner and the validator), `team/blocks.py`, `team/board.py`,
`team/stages.py`, `team/triggers.py`, `team/run.py`, `team/run_stage.py`,
`team/parallel.py` (3.1.2.0 R2: a stage's members at once), `team/remote_stage.py`
(3.1.2.0 R2: an orchestra or flow stage on a fleet member), `team/budget.py`
(3.1.2.0 R2: the budget line), `team/guard.py`, `team/delegate.py`,
`team/adapters.py`, `team/cli.py`, `team/cli_run.py`.

- The first ten minutes (3.1.1.0): `studio/start_api.py` (Start here: `/api/start`),
  `studio/start_job.py` (the one `halo start` Studio runs, its `start` frames),
  `studio/glossary_api.py` (`GET /api/glossary`, docs/GLOSSARY.md); the guided run
  itself is `halo_harness/start/` (engine, steps, the sample repo, the fake model calls)
