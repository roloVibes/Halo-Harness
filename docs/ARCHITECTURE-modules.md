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
  `studio/models_api.py` (the coach's routes left with the coach pack in 3.4.0.0); the live sessions: `studio/sessions_api.py` (3.3.11.0 R1: the Prompt panel's
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
- Team: its routes left with the team file in 3.4.0.0
- Fleet, this machine's half (3.4.0.0 C: the rest is the fleet pack's server/): `studio/fleet_api.py` (agent
  commands on a live session), `studio/fleet_view_api.py` (the `fleet/*` routes the core answers, and the door to the
  pack's when it runs), `studio/fleet_panels_api.py` (attention, costs, caps, conflicts), `studio/fleet_answer.py`
  (one key on an attention row), `studio/fleet_handoff_api.py` (an agent's hand-off),
  `studio/fleet_recording_api.py` (flight recordings, the replay), `studio/fleet_watch.py` (the watcher),
  `studio/fleet_watch_sources.py` (what it reads), `studio/fleet_feed.py` (its tap on the live feed),
  `studio/fleet_send.py` (a session command, this harness's or a member's)
- the one unit view (3.1.2.0): `studio/work_api.py`
  (`GET /api/work/<kind>/<run>`, the units of any run; docs/WORK.md)
- recall (3.1.2.0 R3): `studio/recall_api.py` (`GET /api/recall?q=&fleet=1`
  for the recall box, `GET /api/fleet/recall?q=` the hub's merged view)

**Peers** (`halo_harness/peers/`, 3.4.0.0 C: one machine reaching another, out of the old fleet/):

- who and where: `peers/identity.py`, `peers/store.py`, `peers/protocol.py`, `peers/tls.py`, `peers/pair_kex.py`,
  `peers/pairing.py`, `peers/hub_join.py` (the join exchange a hub and `halo host` share), `peers/net.py`
  (`lan_address`, `FleetOffline`, `parse_ttl`)
- the relay client: `peers/relay.py`, `peers/relay_stream.py`
- hosts: `peers/hub_hosts.py` (3.3.7.0 R1: the halo hosts members announce), `peers/hub_host_cmd.py` (a Studio
  command to a host)
- Ollama on the network: `peers/ollama_share.py`, `peers/ollama_share_cards.py`, `peers/ollama_share_take.py`,
  `peers/control_models.py`, `peers/control_pulls.py`, `peers/control_probes.py`
- this harness: `peers/local_view.py`, `peers/agent_tokens.py` (each agent row's own tokens, from its transcript),
  `peers/capabilities_host.py` (the hardware), `peers/catalog.py` (the capability catalog's cache), `peers/needs.py`
  (3.4.0.0 D: whether a catalog meets a need), `peers/projects.py` (3.4.0.0 D: the repos this harness works in),
  `peers/firewall.py` (3.4.0.1: whether Windows Firewall lets other machines reach a port Halo listens on, read-only)

**Live** (`halo_harness/live/`, 3.4.0.0 C: this machine's sessions live, out of the old fleet/):

- `live/think.py` (3.3.16.2: every agent's thoughts as `thinking_chunk` frames), `live/talk.py` (one agent's words to
  another as `agent_talk` frames)
- the attention queue: `live/attention.py`, `live/supervise_attention.py` (3.1.8.0 R1: the supervisor's parked
  decisions), `live/pack_attention.py` (a pack's own rows, 3.2.0.0 R3), `live/steward_attention.py`
- `live/caps.py`, `live/conflicts.py`, `live/journal.py`, `live/push.py`, `live/handoff.py`, `live/history.py`,
  `live/recording.py`, `live/recording_page.py`
- `live/session_cost.py` (3.4.0.1: a session's spend from its record, and today's), `live/history_owner.py` (3.4.0.1:
  which past sessions are a goal run's or a mission's own)

**The fleet pack** (`halo_harness/templates/packs/fleet/`, 3.4.0.0 C): the hub (fleet/hub*.py), the relay of a joined
harness (relay_hub, relay_runtime, control), the CLI (cli*.py, table*.py), the capability catalog and who
(capabilities*.py), missions (mission*.py), health, the digest, delegate, recall and knowledge across the fleet
(hub_recall, knowledge_share), what packs bring to the catalog (fleet_registry, fleet_share), the two-machine check
(live_check*), its Studio routes (server/: fleet_hub_api, fleet_pair_api, fleet_health_api, fleet_capabilities_api,
fleet_mission_api) and its verbs (cli/). The core reaches it only through `packs/fleet_door.py`; `packs/fleet_migrate.py`
turns it on once for a halo that had a fleet. (`tools/live_fleet_check.py` is the check's CLI;
`halo_harness/recall_fleet.py` and `halo_harness/recall_cli.py` are the member's side and `halo recall`.)

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
- what the forecast, the outcomes and the supervisor read of a run: `orchestra/lane_facts.py` (an Orchestra run's
  lanes as facts) and `orchestra/prices.py` (the model catalog and its prices, a cost and a probe's contrast row in
  words); both were the coach's (`coach_lane_facts.py`, `coach_prices.py`) until 3.4.0.0, when the coach, its probes
  and the improvement library became the coach pack (`halo_harness/templates/packs/coach/`: engine/, cli/, improve/,
  server/, studio/coach.js; its README lists the modules)
- the CLI: `orchestra_cli.py` (the parser, the dispatch, `new`),
  `orchestra_cli_views.py` (status, claims, log, runs, lanes, report),
  `orchestra_cli_run.py` (run, stop), `orchestra_cli_plan.py` (plan, approve,
  reject); `halo orchestra coach` hands over to the coach pack's `halo coach` (3.4.0.0)

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

**Team** (`halo_harness/team/`): left in 3.4.0.0 with the team file. `orchestra/to_report.py` keeps its
`orchestra_run` (the supervisor's and a fleet mission part's), the fleet pack's `fleet/delegate.py` its `FleetDelegate` (the
two-machine check's mission step).

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
one-line fields, the confidence rule), `knowledge/search.py` (relevance first,
the project's scope, gates under findings, re-runs collapsed, each hit's why;
3.3.16.2), `knowledge/rank.py` (a record's content words, its project, the
sample's records, a routine gate, the re-run key), `knowledge/curate.py` (list
filters, prune by age, the passed-gate cap `knowledge.gate_keep`),
`knowledge/curate_cli.py` (`halo knowledge list` and `prune`), `knowledge/cite.py` (the snapshot and its cite line, the
worker's brief block, the ids a text names, "reused by"),
`knowledge/writers.py` (the judge, the gate, the coach's Apply, the
supervisor's answers), `knowledge/sources.py` (recall's finding / decision /
note sources: the entries and `recall.sources`), the fleet pack's `fleet/knowledge_share.py` (the
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
setup/packs/<id>/<block>`, the state's `packs`) and `checks/pack.py` (a pack's check as a row of the checks job).

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
budget and limits). 3.3.16.2: `workflows/offer.py` (the `Workflow` tool leaves the session's list when no square is on
for its lineup), `workflows/lineup_roles.py` (a lineup role that covers the reads takes the task before a square; the
"nothing reads it" line) and `workflows/doctor_rows.py` (`halo doctor`'s squares line, `halo workflows list`'s
header). Halo 3.3.16.3 "Blocks": `workflows/when.py` (a block's when: the rule, its label and sentence, the CLI's
`--when`), `workflows/when_store.py` (where the rules live: a lineup's `workflows:` items, config `workflows.when` on
the auto lineup), `workflows/when_route.py` (always, then words, then needs: an explicit when comes before a covering
role, a plain ref after it), `workflows/when_tool.py` (the Workflow tool's words for each rule), `workflows/squares_when_cli.py` (`halo workflows
enable --when`, `halo workflows when`), `workflows/blocks.py` and `workflows/blocks_tier.py` (the block templates:
load, check, add a square of yours or a tier), `workflows/members.py` (who is inside a square; a shipped one copied to
yours first), `workflows/blocks_show.py` (a lineup's blocks in lines: `halo blocks`, `halo teams show`), `blocks_cli.py`
(`halo blocks list | add | show`) and `studio/blocks_api.py` (the composing routes: when, members, swap, templates).

The map goes on in [Architecture: the module map, part two](ARCHITECTURE-modules-two.md): the Ollama
steward, packs, the extension API, isolation, the guided first run, Setup and Settings.
