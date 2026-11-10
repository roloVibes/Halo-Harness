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
  a thread, its step lines on the feed); the live sessions: `studio/sessions_api.py` (3.3.11.0 R1: the Prompt panel's
  sends with their receipts, its slash list and the receipts' rows: `studio/sessions_prompt_api.py`; the session's
  side: `remote/prompt_queue.py`, `remote/receipts.py`, `remote/receipt_seams.py`; 3.3.11.0 R2: a session with no terminal,
  started and listed by `studio/sessions_new_api.py`, run by `headless_session.py`); the
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
- a pack's own routes (3.3.13.0 R2, extension API 1.2): `studio/packs_routes.py` (imports a pack's routes module
  through its folder as `halo_packs.<id>`, answers `/api/packs/<id>/<prefix>/...`, its body limit, the doctor row),
  `studio/modes.py` (the words `--mode` and `/studio` take: a core section or `<pack>--<section>`),
  `packs/studio_view_rules.py` (a section's `view` and the `routes` block), `ext/host.py` (the Halo services a
  pack's routes call: the models a task ranks, the media models, the MCP servers and a probe of one, a fetch, the
  `halo` command, the ComfyUI client), `ext/testing_studio.py` (`testing.studio`: a live Studio in a scratch home
  with the pack linked and granted) and `packs/test_run_studio.py` (`halo pack test`'s views, routes ping and the
  pack's own tests); Design's routes are the design pack's `server/` since then (halo_harness/templates/packs/design/);
  3.3.14.0 R1: `studio/owner_proof.py` (what the launch token derives: the owner proof the shell's own page sends on
  the writes that change grants, packs, Setup, Settings and sessions, and a pack's GET-only key for what its page
  embeds; docs/STUDIO-shell.md "The owner's page and a pack's key")
- Media: `studio/media_api.py`
- Orchestra: `studio/orchestra_api.py`, `studio/orchestra_plan_api.py`,
  `studio/orchestra_model.py`, `studio/orchestra_live.py`
- the supervisor's morning line (3.1.8.0 R1): `studio/supervise_api.py`
  (`GET /api/supervise/summary`, the Session landing's "N done, M waiting, $X")
- Agents (3.3.16.0 R1: Team, Roles and Orchestra in one section): `studio/agents_door.py` (the old section words as
  doors to Agents' Cast, Runs and Live, and the line each prints once)
- Team: `studio/team_api.py` (3.3.16.0 R1: the board's routes answer 410; the gate answer the Fleet attention row
  uses stays), `studio/team_live.py`,
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
  `fleet/hub_capabilities.py`, `fleet/hub_mission.py`, `fleet/hub_hosts.py` (3.3.7.0 R1: the halo hosts members
  announce)
- the relay of a joined harness: `fleet/relay.py`, `fleet/relay_hub.py`,
  `fleet/relay_runtime.py`, `fleet/relay_stream.py`, `fleet/control.py`,
  `fleet/local_view.py`, `fleet/agent_tokens.py` (each agent row's own tokens,
  from its transcript), `fleet/think.py` (3.3.16.2: every agent's thoughts as
  `thinking_chunk` frames), `fleet/talk.py` (3.3.16.2: one agent's words to
  another as `agent_talk` frames)
- the CLI: `fleet/cli.py` (the dispatcher, serve, pair), `fleet/cli_join.py`
  (join, leave, status), `fleet/cli_members.py` (members, kick),
  `fleet/cli_panels.py` (record, digest), `fleet/cli_caps.py` (capabilities,
  who), `fleet/cli_mission.py` (missions), `fleet/table.py`,
  `fleet/table_live.py`
- the panels: `fleet/attention.py`, `fleet/team_attention.py`,
  `fleet/supervise_attention.py` (3.1.8.0 R1: the supervisor's parked decisions),
  `fleet/pack_attention.py` (a pack's own rows, 3.2.0.0 R3),
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
  `fleet/mission_stage_run.py` (3.1.2.0 R2: a part of kind orchestra, a delegated team stage's run),
  `fleet/mission_hold.py` (3.2.1.0 R3: a pack capability's `capacity.parallel` held, a part refused for a
  pack reason re-planned once)
- recall across the fleet (3.1.2.0 R3): `fleet/hub_recall.py` (the hub fans a
  recall query out and merges the hits; 3.1.6.0 its `local/coach-library`
  route forwards a library fetch to one member), and the scripted two-machine check
  `fleet/live_check.py` with its `--fake` seams `fleet/live_check_fakes.py`
  (`tools/live_fleet_check.py` is the CLI; `halo_harness/recall_fleet.py` and
  `halo_harness/recall_cli.py` are the member's side and `halo recall`)

**Orchestra** (`halo_harness/orchestra/`, its CLI beside the package):

- the run: `orchestra/goal.py`, `orchestra/workflow.py`, `orchestra/index.py`,
  `orchestra/split.py`, `orchestra/plan.py`, `orchestra/plan_check.py`,
  `orchestra/workers.py`, `orchestra/worker_stop.py`, `orchestra/worker_result.py`, `orchestra/lanes.py`,
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
goal`); 3.3.13.0 R3, the packs' services: `supervise/services.py` (start, restart
by the rule, stop, each tick), `supervise/services_rows.py` (the state file, the
rows other processes read, Start / Stop, the enable lines, the Pack Manager's
block) and `supervise/services_cli.py` (`halo supervise services | service`, the
session-request lane); 3.3.13.1: `supervise/single.py` (one supervisor per state
folder: the lock on `supervise/supervisor.lock`, held for its life); 3.3.14.0 R2:
`supervise/procgroup.py` (a service and its children as one group: a new
session on POSIX, a Job object on Windows; the stop signals the group).

**A pack's services and the transport seam** (Halo 3.3.13.0 R3; docs/EXTENSION_API.md "Services", "Transports"):
`packs/manifest_services.py` (`contributes.services`: the entries, the health and log shapes, the `services` grant,
the meaning lines), `packs/test_run_services.py` (`halo pack test`'s services check), `packs/test_run_own.py` (`halo
pack test` runs the pack's `tests/test_*.py`) and `ext/remote.py` (what a transport pack imports: the sessions, a
session started for it, the cards, the notes, a transcript, the QR text, its service's row); the core's side is
`remote/notify.py`, `remote/notify_sources.py`, `remote/session_start.py`, `remote/status.py` and
`commands/pack_run.py` (a pack command with `run:`). The shipped signal pack is
`halo_harness/templates/packs/signal/` (its own code under `halo_signal/`).
R2 (replanning while it runs): `supervise/drift.py` (when a run drifts), `supervise/replan.py` (the pause, its gate, the spawn hook),
`supervise/replan_ask.py` (the lead asked in the goal's thread), `supervise/replan_prompt.py` (the replan prompt),
`supervise/replan_plan.py` (the answer checked), `supervise/replan_moves.py` (the moves and the diff),
`supervise/replan_apply.py` (the plan written into the run), `supervise/replan_rows.py` (the owner's answer).

**Outcomes** (`halo_harness/outcomes/`, Halo 3.1.8.0 R3, docs/OUTCOMES.md):
verified outcomes and measured routing -- `outcomes/transcript.py` (a
transcript's tool calls with their results; a session's log file),
`outcomes/kinds.py` (the task kinds and what a test run looks like),
`outcomes/evidence.py` (`gather` -> Evidence, evidence.json),
`outcomes/lines.py` (the evidence lines a person and the judge read),
`outcomes/lane.py` (a lane's evidence, the gate's once-only send-back, the
judge's block), `outcomes/session.py` (a sub-agent's evidence and outcome
at its end), `outcomes/records.py` (outcomes.jsonl), `outcomes/measured.py`
(success per model and kind), `outcomes/routing.py` (`models.preference:
measured`), `outcomes/cli.py` (`halo outcomes`, `halo models --measured`);
3.1.9.0 R3 (Auto learns): `outcomes/learn.py` (the learned numbers over the
window, the pick's weight, dropped for a kind, `relearn` for
`models_auto.pick`) and `outcomes/learn_cli.py` (`halo outcomes learned`,
`halo outcomes forget`).

**Knowledge** (`halo_harness/knowledge/`, Halo 3.1.8.0 R4, docs/KNOWLEDGE.md
and docs/RECALL.md): findings and decisions that outlive a session --
`knowledge/store.py` (the files: write, read, list, supersede, forget, the
ids, `_meta.json`), `knowledge/frontmatter.py` (an entry's front matter, its
one-line fields, the confidence rule), `knowledge/search.py` (through recall,
else a word match), `knowledge/cite.py` (the snapshot and its cite line, the
worker's brief block, the ids a text names, "reused by"),
`knowledge/writers.py` (the judge, the gate, the coach's Apply, the
supervisor's answers), `knowledge/sources.py` (recall's finding / decision /
note sources: the entries and `recall.sources`), `knowledge/share.py` (the
`knowledge` fleet command and `halo knowledge fetch`) and `knowledge/cli.py`
(`halo knowledge`); the agents' tools are `tools/knowledge.py`.

**Measured, watched and shared** (Halo 3.3.8.0 R4, docs/POOL.md "Measured", docs/MODELS-bundles.md): the pool's
speed card -- `local_pool/bench.py` (the 3.3.6.0 battery against the running pool, the cost line in seconds),
`local_pool/speed.py` (the card, the single-node baseline, measured or extrapolated, the penalty line); the steward's
pool findings -- `ollama_steward/rules_pool.py` (pool-degraded, pool-rtt, pool-spill), `ollama_steward/verify_timing.py`
(the server log's `timing` rates folded into the fix loop's before / after); the off-hours re-bench --
`host/refresh_pool.py` (the plan's pool row, every member idle, the run); bundles that claim more --
`packs/manifest_bundle_claims.py` (reservations with a host, the schedule, the priority, the floor),
`local_sched/bundle_parts.py` (the verdict across the parts), `local_sched/preempt.py` (the lower claim gives way,
told), `local_sched/reserve_parts.py` (claiming the pool and another host); fleet-wide placement --
`local_sched/place_advice.py` (the candidates, the scores and the loading tax, the adviser's placement kind, the
re-check on a far card's change); Studio -- `studio/pool_watch_api.py` (the Pool page's Bench and Findings),
`ui/src/routes/local/PoolWatch.tsx`, `poolwatchstore.ts`.

**The speech servers** (Halo 3.3.9.0 R1, docs/VOICE.md): the speech catalog -- `voice/catalog.py` (seven models,
their engine, repo, files and footprints; `VOICE_GB` for the bundles), `voice/install.py` (present on disk, the hub
download cut to the engine's files, remove); the server -- `voice/server.py` (bind, load, serve), `voice/server_routes.py`
(OpenAI's audio routes), `voice/engines.py` (the engine seam: faster-whisper, kokoro-onnx, the extra's install line),
`voice/engine_fake.py` (HALO_VOICE_ENGINE=fake), `voice/log_lines.py` (the log lines, written and read from one
place), `voice/launch.py` (`halo local serve --stt | --tts`: the subprocess, the registry row, the `stt` / `tts`
entry), `voice/device.py` (auto, cpu, cuda, said); the steward -- `ollama_steward/server_log_voice.py` (the lines as
events), `ollama_steward/rules_voice.py` (stt-slow, tts-slow, voice-cpu, voice-load-failed); the fit --
`local_sched/bundle_voice.py` (a speech need through the catalog and the disk); `voice_cli.py` (`halo voice`) and
`doctor_voice.py` (`halo doctor --voice`).

**The voice loop** (Halo 3.3.9.0 R2, docs/VOICE.md "The loop"): `voice/audio.py` (the devices, `Audio.open`, a WAV as
frames) and `voice/audio_fake.py` (HALO_VOICE_AUDIO=fake), `voice/vad.py` (Silero through onnxruntime, the level gate),
`voice/loop.py` (the microphone, the VAD's start and end, the utterance to STT, `controller.submit`, barge-in,
push-to-talk), `voice/speak.py` (the event-sink tap, the sentences to TTS, playback, the cut), `voice/aggregate.py`
(the sentence aggregator), `voice/client.py` (the two calls to the speech servers), `voice/latency.py` (the latency
card, `turns.jsonl`, `halo voice stats`), `voice/ensure.py` (the servers the loop starts, the bundle's picks),
`voice/session.py` (`/voice on | off | ptt | status`, one loop per session); `voice_loop_cli.py` (`halo voice`, `on`,
`off`, `devices`, `stats`, `--input-file`); the TUI -- `tui/slash_voice.py`, `tui/voice_view.py` (the `voice` events:
the mic chip, the partial transcript, the echo, the latency line); the steward -- `ollama_steward/rules_voice_loop.py`
(voice-slow).

**Through the host, Studio, the glasses** (Halo 3.3.9.0 R3, docs/VOICE.md "Through the host", docs/VOICE-glasses.md):
`voice/turn.py` (one voice turn through a session's control socket: the audio read and resampled to 16 kHz, the
sessions of a home, the stt call, `submit`, the reply's sentences to the tts server, the trailer -- the voice door's and
Talk's one core), `voice/remote.py` (`voice.stt_server: stt@pc`: the paired host found, its speech servers through its
signed `voice/stt` / `voice/tts` routes, the link's round trip, the door's frames for `halo voice client`),
`host/ops_voice.py` (the host's `POST voice/turn | stt | tts` and `GET me`'s voice block), `voice_client_cli.py`
(`halo voice client`), `studio/voice_api.py` and `studio/voice_act_api.py` (Local -> Voice: the view; the servers,
download, loop and Talk's job with its `talk` frames), `doctor_voice.py`'s CPU pair.

**Local engines** (Halo 3.3.13.0, docs/MODELS-engines.md; the 3.3.9.1-3.3.9.3 runtimes folded): one
OpenAI-compatible adapter and one descriptor table -- `engines/descriptors.py` (THE table: per engine its port, routes,
detection, program, install lines, where it runs, managed start, log patterns with sentences, fixes, fit figures,
tuning flags, `verified: False`), `engines/models.py` (the models each engine names: the Library's download targets
and the fit's sizes), `engines/adapter.py` (the program, the auto-detect by owned_by or /health, the
`huggingface.local_servers` entry, Halo's key, the stop, the first request's wait), `engines/launch.py` (`halo local
serve --runtime <id>`: the descriptor's start, a supervised engine's plan and settle), `engines/launch_env.py`
(3.3.14.0 R2: a managed server child's environment without Halo's keys, a program from a PATH folder only, the `--lan`
key check, the key file), `ollama_steward/body_lines.py` (3.3.14.0 R2: a request body's line in a server log is no
server event, for every classifier and the host's peer view), `engines/steward.py` (the
descriptor-driven log reader, the queue read, the one rule over the events), `engines/fit.py` (the `vram` and
`paged-moe` rules), `engines/doctor.py` (`halo doctor --local`'s line per engine found), `engines/peer.py` (the host's
`engines` offer, a peer's `hf:local/<model>@<host>`, an engine server as a placement option) and `engines/bench.py`
(`halo local bench --host <id>` through the OpenAI-compatible route).

**Policy hooks and modes** (Halo 3.3.10.0; docs/EXTENSION_API.md "Policy hooks"; the session's gate is
`agent/policy_gate.py`, docs/ARCHITECTURE-permissions.md):
`packs/manifest_policy.py` (`contributes.policy` and `contributes.modes`: the entries, their meaning lines, the
command with `${halo_python}` and `${CLAUDE_PLUGIN_ROOT}` put in), `packs/mode_state.py` (the pack's `mode.json`:
read, set_mode, arm, disarm, the `mode` event), `packs/policy_proc.py` (one policy's long-lived process: JSON lines,
the budget, a late answer dropped), `packs/policy.py` (the armed policies, `ask` -> `Verdict`, the `when` filter,
`on_error`, the `policy` rows, `winner`), `packs/policy_redact.py` (`redact: [env names]` out of the input and the
result), `packs/policy_after.py` (R2: the post-call verdict, pass / redact / drop, the original's sha256),
`packs/policy_audit.py` (R2: the verdicts read back: `halo pack policy log`, status counts and processes, the Pack
Manager's block, a mission's armed ids), `packs/policy_views.py` (inspect's block, `halo pack policy status`, the
doctor's mode.json rows) and `packs/cli_policy.py` (`halo pack mode`, `halo pack policy`).

**A pack's Setup blocks** (Halo 3.3.11.0 R3; docs/EXTENSION_API.md "Setup blocks"): `packs/manifest_setup.py`
(`contributes.setup`: the entries, the form's fields, the `pack:<id>:<block>` keys, the meaning lines),
`packs/setup_state.py` (the pack's `setup.json`: done / skipped per block, the `setup:` lines `halo pack enable` ends
with, the doctor's info row, `halo setup <pack>`'s door), `studio/setup_packs_api.py` (`GET setup/packs`, `GET|POST
setup/packs/<id>/<block>`, the state's `packs`) and `start/checks_pack.py` (a pack's check as a row of the checks job).

**A pack's palettes** (Halo 3.3.12.0 R2; docs/EXTENSION_API.md "Themes"): `packs/manifest_themes.py`
(`contributes.themes`: the entries, the `<pack-id>/<id>` names, the meaning lines and the contrast lines),
`themes/packs.py` (the enabled packs' palettes, read live on the packs registry's snapshot, and their rows for `GET
settings/themes`), `themes/restore.py` (the pack's `theme.json`: the value a pack palette replaced, written back by
`halo pack disable` / `remove`; the gone-palette line) and `themes/studio_css.py` (the CSS variables Studio draws a
palette in, run by `scripts/themes_css.py` for the ten and by the server for a pack's).

**Workflow squares** (Halo 3.3.16.0 R3; docs/WORKFLOWS-squares.md): `workflows/contract.py` (a square's contract read
from the workflow file and its meaning lines), `workflows/registry.py` (the four places a square comes from, yours >
project > shipped for a bare name and a pack's by `<pack>/<name>`; the enabled sets per lineup), `workflows/router.py`
(the gaps, the pick, the why line, the depth and the cap), `workflows/square_run.py` (a square's run by its engine and
the `gives` check), `workflows/receipts.py` (the receipt node, the Live tree's square, the cost, an Orchestra run's
squares), `workflows/squares_cli.py` (`halo workflows`, the TUI's `/workflows`), `tools/workflow.py` (the `Workflow`
tool) and `studio/workflows_api.py` (Agents -> Workflows: the board's rows, enable / disable, the YAML, a square's
budget and limits). Halo 3.3.16.3 "Blocks": `workflows/when.py` (a block's when: the rule, its label and sentence, the
CLI's `--when`), `workflows/when_store.py` (where the rules live: a lineup's `workflows:` items, config
`workflows.when` on the auto lineup), `workflows/when_route.py` (always, then words, before the needs pick),
`workflows/when_tool.py` (the Workflow tool's words for each rule), `workflows/squares_when_cli.py` (`halo workflows
enable --when`, `halo workflows when`), `workflows/blocks.py` and `workflows/blocks_tier.py` (the block templates:
load, check, add a square of yours or a tier), `workflows/members.py` (who is inside a square; a shipped one copied to
yours first), `workflows/blocks_show.py` (a lineup's blocks in lines: `halo blocks`, `halo teams show`), `blocks_cli.py`
(`halo blocks list | add | show`) and `studio/blocks_api.py` (the composing routes: when, members, swap, templates).

The map goes on in [Architecture: the module map, part two](ARCHITECTURE-modules-two.md): the Ollama
steward, packs, the extension API, isolation, the guided first run, Setup and Settings.
