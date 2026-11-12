# What changed (the newest version entries of CHANGELOG.md, shipped with the package; `halo whatsnew` reads it)

## [3.4.0.1] - 2026-11-12

What a real two-machine run found: a blocked part no longer counts as done, costs count finished sessions, the hub says
when the firewall is in the way. A tester ran 3.4.0.0 on the Windows PC and the Kali VM, paired through the fleet pack,
with a mission split across both, and wrote 29 defects; each line below names the one it fixes (the fleet pack is 1.0.1).

- 15: a mission part is `done` only when its work is: the brief asks the worker to end its hand-back with `Outcome: done`
  or `Outcome: blocked -- <why>`, and a part whose hand-back says it is blocked, or whose named outputs are not in the
  mission folder, ends `failed` with the reason (the worker decides before it writes `result.json`; the hub checks a
  member's `done` again). The mission ends "N of M part(s) did not finish: ..." (fleet/mission_outcome.py).
- 4: `halo recall --fleet` and `/recall --fleet` run with the fleet pack on (they asked the pack for a module that
  stayed in core); a pack module that does not import says its real error instead of "install the pack".
- 10, 17, 26: one source of truth for a session's cost, its record (live/session_cost.py): a harness's "today" counts
  its finished sessions too, on the hub's own machine and on a member (its announce carries its `cost_today`), so the
  fleet caps and Studio's machine boxes see mission and goal-run spend; a call Halo could not price stays unknown
  (`$x+`), never $0. History's session costs read the same.
- 21: a goal run whose split failed counts its lead's calls (split.json keeps them).
- 18: a mission part's hand-back pushed to the hub has its full local paths cut (home -> `~`, a path -> its last part).
- 1: `halo studio --no-open` with its output redirected writes its URL lines at once.
- 12: Halo never opens Windows Firewall, and now says when it is in the way: a hub (and `halo host serve`) on Windows
  reads the inbound rules (no elevation) and prints one line with the command an administrator runs (remove the
  `python.exe` Block rules Windows made from a declined prompt, then allow the port); `halo doctor`, Setup -> Machines
  and `halo fleet serve` say the same; a join that times out says "the hub did not answer on <host>:<port>: on Windows
  the firewall is the usual cause; on the hub run `halo doctor`" (peers/firewall.py; FLEET.md "Windows Firewall").
- 13: opening Studio loads and calls no model: the Ollama steward's job started with Studio or the hub reads the logs
  and runs the rules; its note and a new model's probe run only under `halo ollama steward --watch` or the new
  `ollama.steward.watch: true`.
- 14: a plan that needs what only an away member has names it ("X has gpu but is offline (no halo session open
  there): open one, then plan again"); `halo fleet join` says a member is online only while a halo session runs there.
- 16: each capability card carries the permission mode a mission part runs in; a part placed where calls that ask are
  refused gets a note in the plan with what lets them through.
- 27: `halo fleet leave` after a kick says "it had already removed this harness".
- 11: `halo fleet status` names a joined hub by the hub's name, not this harness's.
- 19: a capability card from an older read, or made by another Halo version, shows "(refreshing ...)" and is
  gathered again.
- 7: the fleet pack has a `halo doctor` row: whether it runs, the hub here (and the firewall in its way), each joined
  hub and whether it answers.
- 2: `halo pack install` / `list` count a pack's CLI verbs, slash commands, doctor rows and Studio server modules (the
  fleet pack "offered nothing"); an empty `halo pack list` points at `--available`.
- 3: with the fleet pack installed but off, its verbs say "the fleet pack is installed but off: halo pack enable fleet
  --grant-all" (not "install it").
- 5, 6: `halo studio --help` names the fleet pack for `--fleet` and `--mode fleet`; `halo pack --help` lists `cli:<verb>`
  among the grants.
- 8, 9: Studio's words name the Mission panel on Agents -> Live and Live's inspector, not the Runs view that went.
- 20: `halo orchestra new` with no `--file` says a run cannot split without the goal's files; such a run stops before
  the lead is asked.
- 22: History folds a goal run's and a mission's own sessions under their row ("3 sessions inside").
- 23, 24, 25: the Mission report counts parts per harness ("1 (#2)"), keeps its total whole, and says "nothing to
  merge (files parts only)".
- 28, 29: with the fleet pack off, Setup's line names no machines, and `?mode=fleet` / `halo studio --mode fleet` say
  the pack's line instead of pointing at Setup -> Machines.
- Tests: `test_studio_local_hf` (two servers: the driver's fallback click started a second one after a first start had
  answered; it now waits for Start's answer and checks one server started) and `test_bundle_reserve` (one route call
  timing out under load marked the host down for 30 s, so every read after it had no card; the readiness wait clears
  the mark its own probe set).

## [3.4.0.0] - 2026-11-11

**Halo is defined by its core, everything else ships as a pack, and Agents opens on the living canvas.** The core is what it was built around: the agent loop and its tools, permissions and
policy, the providers in use here (OpenRouter, Databricks, Anthropic, OpenAI-compatible, Ollama, Hugging Face and the
local servers), all the local-model work, lineups and blocks, Studio's Session, Agents, Local, Packs, Setup and
Settings, and the pack system. Experimental features that mask that core leave it, as packs where that is cheap and
as plain removals where nothing is left to pack; the measure is lines and files after versus before.

### A: Typesafe leaves the core

TypeSafe was a key-only placeholder: it stored `TYPESAFE_API_KEY`, had no `ts:` route, no adapter and no models, and
the usage audit found no call. With nothing to move, it is removed rather than packed.

#### Removed

- The `typesafe` provider: its entry in `PROVIDER_NAMES`, `LABELS` and `PREFIXES` and its `credentials_present` /
  `credentials_source` branches (`providers/enablement.py`); the "not probed (stores a key only)" reachability branch
  (`providers/reachability.py`); its `_model_count` and `halo providers setup typesafe` branches (`providers_cli.py`).
  Replaced by nothing: `halo providers`, `/providers`, `halo balances` / `/balances` and `halo doctor`'s enabled count
  list six providers.
- The TypeSafe tab of `halo init` and the init wizard (`init_providers.py`: `TAB_PROVIDERS`, `TAB_LABEL`, the
  `tab_credential_state` branch, `_TAB_KEY_ENV`; the tab help in `tui/dialogs/init_tabs.py` and `init_wizard.py`) and
  Studio Setup's TypeSafe card (`studio/setup_providers_state.py`: `KEY_FIELDS` and the `_secret` branch).
- `halo bugreport`'s TypeSafe line (`bugreport.py`).
- `TYPESAFE_API_KEY` from `redact.py`'s named list (the generic `*_API_KEY` rule still redacts it).
- Verbs: `halo providers enable | disable | setup typesafe` and `/providers enable | disable typesafe` (each now says
  the one line below). Keys: `TYPESAFE_API_KEY` (env file, shell, settings env block) and `providers.typesafe` in
  config.json, both ignored. Files: none was TypeSafe's own. halo_harness/ outside templates/: 2003 files and 328,429
  lines before, 2004 files and 328,465 lines after (99 lines out of 17 core files; 65 lines in for
  `providers/left_core.py`, the module that says what left).

#### Added

- `providers/left_core.py`: what left the core and the one line each leftover gets, never an error -- a `ts:` ref
  (a `--model`, `/model`, a remembered model, a lineup card or a Studio card: "no route: 'ts:...' (ts: typesafe
  (TypeSafe) left the core in 3.4.0.0: ...)"), a leftover `TYPESAFE_API_KEY` or `providers.typesafe` row (one
  `[WARN]` row in `halo doctor`, one line under `halo providers`), `halo providers enable typesafe` (the line, exit 1;
  `disable`, exit 0). The `cc:` / `cx:` line of 3.1.5.0 moved there with its words unchanged. A leftover key stays
  stripped from tool children (`providers/config.py`): it is a secret wherever it came from.
- `tests/test_providers_left_core.py` pins each leftover line and that nothing is said when nothing is left over.

#### Docs

- COMMANDS-providers.md, COMMANDS-health.md, SLASH-COMMANDS-providers.md, MODELS-references.md (the prefix table),
  STUDIO-setup.md, HANDBOOK.md, MODELS-openai-codex.md and the glossary's "provider" no longer list TypeSafe and say
  where a leftover is named; `docs/screenshots/balances.svg` is re-rendered by `scripts/screenshots.py` (six
  providers). MODELS-experiential.md keeps `or:typesafe/jev-router` (an OpenRouter model) and the
  research notes under docs/harness/ stay as history.

### B: the experiments leave the core

The owner (2026-11-10): "being able to define what halo harness is makes it stronger. All these experimental features
can be packs." This block is F4 and F7 of the Focus plan (plans/ROADMAP.md); what it moved and removed is below, each
with what replaces it. A leftover of a removed feature is ignored, never an error.

#### Removed

- **The team file and `halo team`** (3.0.8.0; removed, not packed: Team's board left Studio in 3.3.16.0 and nothing
  used the file). `halo team ...` now answers one line: the team file left in 3.4.0.0, a lineup's tiers and blocks
  (Agents -> Cast, `halo teams`) and a run's lanes with their owns lines (Agents -> Runs, `halo orchestra`) do its job.
  LINEUPS are untouched: `halo teams`, `teams_yaml.py`, `~/.halo/teams/*.yaml`, a lineup's tiers, routing, budget and
  pipeline, and `team_config.py` (the Databricks `team.json` preset, which is not the team file). Gone:
  - modules `halo_harness/team/` (spec, validate, validate_stages, resolve, blocks, board, stages, gate_actions,
    triggers, run, run_stage, parallel, remote_stage, budget, guard, delegate, adapters, cli, cli_run),
    `studio/team_api.py`, `studio/team_live.py`, `studio/team_budget_api.py`, `fleet/team_attention.py`,
    `work/adapters/stage.py`, `orchestra/coach_team_rules.py`, `templates/team/team.yaml` (the team template);
    kept by moving: `team/adapters.orchestra_run` -> `orchestra/to_report.py` (the supervisor's and a fleet mission
    part's), `team/delegate.FleetDelegate` -> `fleet/delegate.py` (the two-machine check's mission step; its
    `send_run` went with the team stage), `member_bio` -> `supervise/runner.main_bio`;
  - verbs `halo team init|validate|run|status|board|answer|stop|log|blocks|coach`; the routes `/api/team/*` (410
    since 3.3.16.0), `/api/team/coach`, `/api/work/team/*` and `/api/work/stage/*`;
  - the Attention kinds `team_gate` and `team_budget`; the work record's unit kind `stage` and run kind `team`
    (`halo work` reads lanes, mission parts and supervisor goals); the session's team claim guard (`HALO_TEAM_SCOPE`);
  - `halo config where`'s "Team file" group and `halo doctor --config`'s team-file rows; the schema kind `team`;
  - the two-machine check's `team` step (`tools/live_fleet_check.py`: who, mission, recall);
  - the glossary words team, member and stage (block now means the lineup's block on Agents -> Cast); completion's
    `team`; docs/TEAM.md (removed from docs/README.md and the README's table; every page that linked it says where its
    job went);
  - tests `test_team_blocks`, `test_team_budget`, `test_team_cli`, `test_team_delegate_runs`, `test_team_parallel`,
    `test_team_run`, `test_team_spec`, `test_studio_team`, `tests/helpers/team_rig.py`, `coach_seed.team_run`.
- **The guided first run left the core for the shipped `first-run` pack** (3.1.1.0; off unless enabled):
  - modules `halo_harness/start/` (engine, steps, steps_run, steps_setup, card, lineup, sample_repo, fake, fresh,
    screen, errors, auto_gate), `start_cli.py`, `studio/start_api.py`, `studio/start_job.py` -> the pack's
    `first_run/`, `cli/start.py`, `server/start_api.py`, `server/start_job.py` (+ `server/routes.py`);
    `tui/dialogs/start_panel.py` (the TUI's `/start` panel) removed: the pack's `/start` shows the card and how to run
    it; the core checks stay core as `halo_harness/checks/` (`start/checks.py` -> `checks/catalog.py`,
    `checks_run.py` -> `checks/run.py`, `checks_pack.py` -> `checks/pack.py`, `checks_steward.py` ->
    `checks/steward.py`, `provider.py` -> `checks/provider.py`), and the sample's knowledge tag stays core
    (`knowledge/rank.sample_root`);
  - `halo start` and `/start` are the pack's (`contributes.cli`, `.slash`); with the pack off each is one line: "the
    guided first run is a pack now: halo pack install first-run, then halo pack enable first-run --grant-all";
  - the core check `start` (Setup's Check row, `halo check --start`, the wizard Summary's row) -> the pack's Setup
    block `run` (`pack:first-run:run`); `halo check --start` says the one line; `halo init` no longer offers the run;
  - Studio's "Start here" overlay (`shell/StartHere.tsx`, `lib/start.ts`), Agents -> Runs' "Test this lineup"
    (`routes/agents/runs/TestLineup.tsx`), the Setup Check row's card and Summary's Run, the palette's "Start: the
    guided first run" and the route `/api/start` -> the pack's **First run** panel in the Agents section
    (`studio/first-run.js`) over its routes `/api/packs/first-run/start/...`;
  - `tools/capture_start.py` (`capture_studio.py --mode start`; what it kept is `tools/capture_fresh.py`); tests `test_start_cli`, `test_start_cli_errors`, `test_start_studio_api` (moved:
    `test_pack_first_run_cli`, `test_pack_first_run_errors`, `test_pack_first_run_routes`, run against the pack),
    `test_start_checks` (-> `test_checks_catalog`), `test_start_tui` (-> `test_explain_tui`, the panel's tests went),
    `test_studio_start`'s Start-here run, `test_studio_modes`'s `--mode start`, `test_studio_quiet`'s Start-here
    test, and `test_setup_state_no_probe`'s / `test_setup_api`'s card checks.

#### Added

- **The `first-run` pack** (`halo_harness/templates/packs/first-run/`): `halo start`, `/start`, the Setup check row and
  the First run panel; `halo pack test first-run` passes it.
- **Seams, draft for extension API 1.3** (docs/EXTENSION_API.md "CLI verbs, slash commands, doctor rows and settings
  rows", "Core access"): `contributes.cli: [{verb, module, help}]` (`main(argv) -> int`, grant `cli:<verb>`,
  `packs/contrib_cli.py`), `contributes.slash: [{name, module, help}]` (`run(args_text, facade) -> str`, grant
  `cli:<name>`, `packs/contrib_slash.py`), `contributes.doctor: [{id, module, help}]` (`rows(ctx) -> list`, grant
  `doctor`, `packs/contrib_doctor.py`), `contributes.settings: [{key, title, help, type, default}]`
  (`packs.settings.<id>.<key>`, no grant, `packs/contrib_settings.py`), their manifest rules (`packs/contrib_lines.py`)
  and `halo_harness.ext.core` (`core.module(name)`, `core.get(name, attr)` over `core.REACHABLE`); `halo_harness/left.py`
  (the one line a verb that left the core says).

#### Docs

- docs/TEAM.md removed; COMMANDS-init, HANDBOOK, STUDIO-shell, STUDIO-setup, STUDIO-agents, SLASH-COMMANDS-tui,
  TROUBLESHOOTING, PACKS ("The first-run pack"), EXTENSION_API, ARCHITECTURE-modules(-two), GLOSSARY, WORK, MISSIONS,
  ORCHESTRA, ROLES, AGENTS and README say what left and where it went.

### B2: the coach is a pack; the wizard is a console fallback

The coach (its cards, probes, the improvement library and `/improve`) is the shipped `coach` pack, off unless you
enable it; the supervisor, replanning and verified outcomes stay core. The terminal wizard's screens are gone: Setup is
Studio's, and `halo init --terminal` (or no browser) is a plain console setup of the essentials. The pack contributions
`contributes.doctor` and `contributes.settings` are wired in, and the extension API is 1.3.

#### Removed

- The coach's modules, moved into `halo_harness/templates/packs/coach/` (the pack replaces them): `orchestra/coach.py`,
  `coach_apply.py`, `coach_ask.py`, `coach_citations.py`, `coach_compare.py`, `coach_compose.py`, `coach_experience.py`,
  `coach_library.py`, `coach_library_share.py`, `coach_mission_rules.py`, `coach_orchestra_rules.py`, `coach_probe.py`,
  `coach_probe_card.py`, `coach_probe_prompt.py`, `coach_probe_schema.py`, `coach_record.py`, `coach_rules.py`,
  `probe_overlay.py`, `probe_runs.py` (-> engine/); `coach_cli.py`, `coach_library_cli.py`, `improve_cli.py` (-> cli/);
  `improve/` (`__init__`, `apply`, `config`, `dismissed`, `draft`, `evidence` -> improve/); `studio/coach_api.py`,
  `studio/coach_probe_job.py` (-> server/); `knowledge/writers.applied` (-> engine/knowledge_applied.py).
- `improve/hint.py` and the once-a-session `/improve` hint (agent/loop.py `_maybe_yield_improve_hint`): no pack seam
  for a session notification; the coach pack's doctor row says what `/improve` uses.
- The TUI's `/improve` card review (tui/slash.py `_handle_improve` and its workers, tui/widgets/cards.py
  `ImproveCard`): the pack's `/improve` prints what `halo improve` prints.
- CLI verbs and slash commands from the core: `halo coach`, `halo improve`, `/coach`, `/improve` (the pack's now; one
  line each with it off, halo_harness/left.py); `halo orchestra coach` and `halo fleet mission coach` hand over to the
  pack's verb.
- Config keys `coach.probe.k`, `coach.probe.budget_factor`, `coach.library.cite`, `improve.enabled`, `improve.hint`,
  `improve.model`, `improve.since_days`, `improve.max_candidates`, `improve.hint_threshold.repairs`,
  `.edit_failures`, `.loop_breaker`, and the config sections `coach` / `improve`: ignored with one line (`halo doctor
  --config`; `halo config set` names the pack's key). The pack's seven rows are `packs.settings.coach.<key>`.
- Settings rows: those eleven, and the group "Coach and improve" (-> Settings -> From packs while the pack is on).
- Doctor row `improve` (the `/improve` config line) (-> the coach pack's doctor row).
- The coach's lines in the core: the Orchestra report's `coach:` line (`orchestra/report.coach_line`), the mission
  report's, and `halo fleet digest`'s coach rows (its `coach` list stays, empty).
- Studio: the run report's Coach tab (`routes/orchestra/Coach.tsx`, `coachApply.ts`), the mission's Coach face
  (`routes/fleet/MissionCoach.tsx`), the bio form's coach note (`routes/roles/CoachNote.tsx`, `coachHint`), the plan
  canvas's coach staging (`plan/stage.ts stagePlan`), `lib/coach/` (CoachCards, ConfirmCard, LibraryFold, ProbeBar,
  actions, probe, store, types) and `styles/coach.css`; the routes `/api/orchestra/<run>/coach`,
  `/api/fleet/missions/<id>/coach`, `/api/coach/library/...` (-> the pack's Coach panel in Agents and
  `/api/packs/coach/coach/...`).
- The terminal wizard (Setup is Studio's; the console setup below replaces the terminal path):
  `tui/dialogs/init_wizard.py`, `init_tabs.py`, `team_step.py`, `team_step_actions.py`, `summary_checks.py`,
  `check_rows.py`, `step_rail.py`, `setup_mode.py`, `init_picker.py` (the arrow-key pickers), `ollama_found.py`,
  `ollama_calibrate_offer.py`; `wizard_ux.py` keeps only the footer caption `/agents` uses; init_cli's
  `_run_init_wizard_flow`, `_run_init_tabs`, `_launch_after_wizard`. `/agents` and `/teams` (their list and view
  screens) stay.
- `halo setup --terminal` and `/setup --terminal`'s screens (-> the console way, one line per page).
- Captures: `docs/media/studio-orchestra-coach.png` (tools/capture_orchestra.py `coach_capture`) and the TUI gallery's
  `team-step` scene (`docs/screenshots/team-step.svg`, scripts/screenshots.py, its tests/test_screenshots pin).
- Tests: tests/test_improve_hint.py; the Chrome coach checks (tests/helpers/studio_coach.py, studio_ui_coach.py,
  studio_coach_rig.py); test_h15_init_tabs, test_init_wizard_round7, test_ollama_discover_wizard,
  test_ollama_tune_wizard, test_round2b_wizard_roles_fixes, test_round2c_wizard_ux, test_round_wizard_deep_review,
  test_wizard_team_switch_sync; the wizard tests in test_review3_f2 (1), test_review3_t2 (3),
  test_agents_teams_forms (2), test_explain_tui (1), test_hotfix_101_fix_init_preserve (3), test_auto_lineup (1),
  test_setup_api (1), test_wizard_agents_bios (2), test_wizard_lineup (1), test_wizard_studio_doors (1); test_tui.py's
  20 wizard and init-picker pilots and 3 ImproveCard / `/improve` pilots.

#### Added

- The shipped `coach` pack (`halo pack install coach`, `halo pack enable coach --grant-all`): `halo coach`, `halo
  improve`, `/coach`, `/improve`, a Coach panel in Studio's Agents section (a finished run's cards, Ask, Apply after
  its confirm card, Undo, Probe), seven Settings rows under From packs, one doctor row; `halo pack test coach` passes.
- `contributes.settings` wired: an enabled pack's rows in Studio's Settings (group "From packs", shown only while a
  pack has rows) and in `halo config get` (the default while unset) / `set` (its type checked, one line, exit 2).
- `contributes.doctor` wired: an enabled, granted pack's rows last in `halo doctor` (`From packs, <id>: ...`).
- Doctor rows for both shipped packs: first-run (ready to rehearse your lineup, or the provider / lineup missing) and
  coach (what it keeps and uses, or the Studio grants its panel waits for).
- The console setup: `halo init --terminal` and the no-browser fallback ask a provider (numbered) and its key (by NAME
  in the env file), the default model (a short numbered list, or a typed ref), the permission mode and whether to run
  doctor, then name where the rest is (Studio's Setup, its address and port-forward line when one runs).
- `halo setup <page>` and `/setup <page>` for every Setup page (providers, local, model, permissions, theme, team,
  linux, check, machines); `--terminal` or no browser prints the console way (setup_cli.CONSOLE); `halo init --step
  <page>` is the same.
- halo_harness/legacy_roles.py: a role table from before lineups becomes the lineup `migrated` once, at an interactive
  session start and in `halo init`'s console setup (the wizard's lineup step did it until now).
- Extension API 1.3 (`ext.compat.CHANGES["1.3"]`): `contributes.cli`, `.slash`, `.doctor`, `.settings` and `ext.core`,
  all draft; the first-run and coach packs say `halo_api: {min: "1.3"}`.
- Tests: test_pack_coach, test_packs_contrib_wired (fixture pack tests/fixtures/packs/contrib-rows), test_init_console,
  tests/helpers/coach_pack.py (the moved coach tests run against the pack's modules); test_invariants'
  `invariant_k` (no core module imports a shipped pack).

#### Changed

- `orchestra/coach_prices.py` -> `orchestra/prices.py` (+ `money`, `row_line`) and `orchestra/coach_lane_facts.py` ->
  `orchestra/lane_facts.py`: the forecast, the outcomes records and the supervisor's replan prompt read them; they stay
  core. `outcomes/records.path` keeps `<state>/coach/outcomes.jsonl`.
- `ext.core.REACHABLE` adds the coach pack's door (the run folders, the writers, the probe's Orchestra runs, the fleet's
  mission folders, /improve's session; outcomes through `outcomes.records` only) and drops `orchestra.coach`.
- The guided first run's step 6 runs the coach pack's `halo coach <run> --json` while that pack is enabled, else one
  line that the coach is a pack.
- The fleet's `coach_library` command answers through the coach pack (`packs/contrib_cli.pack_call`), else one line.
- Studio's Coach panel writes a card's change after its own confirm card; it no longer opens the bio form or the plan
  canvas with the change staged.
- `halo init`'s console prompts read stdin with `--terminal` even without a terminal (scripts can drive it).

#### Docs

- EXTENSION_API (1.3, the four contributions draft with their exact shapes and grants, "Changes in 1.x"), PACKS ("The
  coach pack"), CONFIG (the From packs note; the coach rows out), COMMANDS-init (the console setup), COMMANDS-studio,
  COMMANDS-sessions, COMMANDS-health, COMMANDS-fleet, SLASH-COMMANDS(-tui, -keys), ORCHESTRA and STUDIO-orchestra (the
  coach is a pack), STUDIO-setup, WIZARD (a note: the screens left, the rules stay Studio's), GLOSSARY,
  ARCHITECTURE-modules, README (Features and Documentation name the coach pack; no wizard).

### C: Fleet leaves the core

The owner (2026-11-10): "Fleet doesn't really fit anymore ... it can be a pack." Halo's core is see, shape, mix, local,
start; several halos joined to one hub serve none of them directly, so the fleet is ONE shipped pack now, `fleet`, off
by default: `halo pack install fleet`, then `halo pack enable fleet --grant-all`, and it works as it did.

#### Removed from core (now in the shipped `fleet` pack: `halo pack enable fleet`)

- **Verbs**: `halo fleet` (the live table, `serve`, `pair`, `join`, `leave`, `status`, `members`, `kick`, `record`,
  `digest`, `capabilities`, `who`, `mission ...`) and `halo mission ...` (new: the same as `halo fleet mission ...`);
  `/fleet` (the table as text; the TUI's live table dialog is gone, `halo fleet` in a terminal is the live table) and
  `/mission`; `halo studio --fleet`; `halo recall --fleet`, `/recall --fleet` and `halo knowledge fetch` (they ask the
  fleet). With the pack off each says one line: what it is and `halo pack install fleet, then halo pack enable fleet
  --grant-all`.
- **Studio doors**: Agents -> Live's **this halo | fleet** switch and the fleet scope (the machines, their sessions and
  agents, a mission's parts), the palette's fleet lines (who can..., the machines' specs, missions, pair, kick, while
  you were away), Setup's **Machines** page (pairing, sharing, the people), the rail's "while you were away" dot, and
  the routes behind them (`fleet/hub`, `fleet/pair`, `fleet/settings`, `fleet/kick`, `fleet/commands/<id>`, a member's
  commands, `fleet/health`, `fleet/digest`, `fleet/capabilities`, `fleet/who`, `fleet/missions...`, `fleet/recall`).
  `GET fleet` says `fleet_pack: true | false`; the UI shows a Fleet door only on true.
- **Config keys** (Settings -> Fleet, shown only while the pack runs; `halo config set` still takes them):
  `fleet.share`, `fleet.allow_answers`, `fleet.share_captures`, `fleet.hub.port`, `fleet.tags`,
  `fleet.capabilities.hide`, `fleet.ollama.share`, `fleet.recall.share`, `fleet.recall.hide`, `fleet.shared_dir`,
  `fleet.mission.prefer`, `fleet.mission.max_parallel`, `fleet.mission.max_file_mb`.
- **Python**: the hub (hub*.py), the relay of a joined halo (relay_hub, relay_runtime), missions (mission*.py), the
  capability catalog and who (capabilities*.py but the host's hardware), control from a hub, delegate, digest, health,
  the table, the live check, the CLI (cli*.py), knowledge across the fleet (knowledge/share.py) and what packs bring to
  the catalog (packs/fleet_registry.py, fleet_share.py) are the pack's fleet/; Studio's pair, capabilities, mission and
  hub routes and its health + digest its server/.
- With the pack off a pack workflow's capability `requires` are not checked (the catalog that checks them is the
  pack's); a `contributes.fleet` pack shows no fleet rows in the Pack Manager.

#### Stays in the core (moved out of halo_harness/fleet/, which is gone)

- **halo_harness/peers/**: everything one machine needs to reach another's models, so `halo host serve`, the pool,
  Local -> Hosts and Ollama on the network work with the pack off: identity, fleet.json and the pair keys (store), the
  signed wire (protocol), TLS, pairing codes and the key exchange (pairing, pair_kex, hub_join), the relay client
  (relay, relay_stream), hosts (hub_hosts, hub_host_cmd), Ollama on the network (ollama_share*, control_models,
  control_pulls, control_probes), this harness's own sessions (local_view, agent_tokens), the host's hardware
  (capabilities_host), the capability cache (catalog.py, new) and `lan_address` / `FleetOffline` / `parse_ttl` (net.py,
  new).
- **halo_harness/live/**: this machine's sessions live: thinking and talk on the feed (think, talk), the attention
  queue and its sources, one session's timeline and flight recording (history, recording), the file-conflict edges, the
  spend caps, the decision journal, push to the phone and hand-offs. Session, Agents -> Live, the attention chip and the
  replay read `fleet/*` routes that the core still answers for this harness (studio/fleet_view_api.py, new: the core's
  half; the pack answers every `fleet/*` route while it runs).
- `halo_harness/recall_fleet.py` (Studio's recall box reads its local half), the work record's mission adapter
  (work/adapters/part.py reads mission.json itself), `fleet.enabled`, `fleet.name`, `fleet.private`,
  `fleet.allow_control` (the host's grants), `fleet.caps.*` and `fleet.attention.signal` (now under Settings -> Remote).

#### Migration

A halo that had a fleet (a joined hub in fleet.json, a hub's members, missions, or fleet keys only the pack reads in
config.json) gets the shipped pack installed and enabled on its first run after the update, with one line that says so
(packs/fleet_migrate.py; the marker `<state>/packs/.fleet-migrated` keeps it from asking again). Nothing is deleted.

#### Seams

No manifest key is new: the pack uses `contributes.cli` / `.slash` (3.4.0.0 B). The core reaches the pack only through
`halo_harness/packs/fleet_door.py` (`module(rel)`, `call(rel, attr, ...)`: None while the pack does not run here);
`halo_harness.ext.core` lists the core modules the pack drives and adds `core.version()`. Tests run the pack in every
scratch home with `PACKS_TEST_SHIPPED=fleet` (packs/registry.py, honoured only under BRIDGE_TEST_HOME;
tests/helpers/fleet_pack.py sets it and serves the moved modules under their old names).

#### Not done here

- Studio's fleet UI (routes/fleet/*, the Live fleet scope) is still compiled into the core bundle, gated on
  `fleet_pack`: a React section has no pack seam yet (a pack's Studio panel is plain DOM).
- Federation R1's contracts (branch v3318/R1-contracts, its work record included) are left unmerged.

#### With B2 (the coach pack)

- A pack never imports another pack. The coach pack reaches missions and the hub through the core door
  `packs.fleet_door` (in `ext.core.REACHABLE`): with the fleet pack off, `halo fleet mission coach` / `halo coach
  mission` say the fleet pack's one line, Studio's `fleet/missions/<id>/coach` finds no mission, and `halo coach
  library fetch` says the fleet's hub is the fleet pack's. The fleet pack reaches the coach through
  `packs.contrib_cli` (`dispatch` for `halo fleet mission coach`, `pack_call` for the `coach_library` command): with
  the coach pack off, one line naming the coach pack. `ext.core.REACHABLE` lists no `fleet.*` module (they are
  `peers.*`, `live.*` or the fleet pack's now).

### D: a goal run is a job on Live and in History (Orchestra's Runs view and Start screen go)

The owner (2026-11-10): "I always see unused older versions of orchestrations ... I'd love to see what is actually
happening." Orchestra's engine is core and unchanged (worktrees, merge, the test gate, the supervisor, outcomes,
replanning; the `code` block, `halo orchestra` and `halo supervise` run on it). What went is the separate place to look
at it: one place shows what runs now (Agents -> Live), one shows what ran (History, on Live's bar).

- **Agents has Cast, Live and Workflows** (`C`, `L`, `W`). `R` and every door that named Runs land on Live (once in a
  browser: "Runs is gone: a goal runs on Live (Run a goal on its bar); a finished run is in History"); a door that names
  a run (`?mode=agents&run=<id>`, an attention row's `o`, the palette) opens it on Live while it runs, else its report.
- **A running goal run is a job on Live**: its lead, its lanes in the run's block under it (a group box of kind `run`;
  with the plan under it on, the block "goal run: <goal>"), each lane a box with a row per fact -- state, model, cost,
  what it owns (its claims), its worktree -- and what it waits on: the merge and the gate are steps on the waiting path,
  the sentence under the bar covers the run. A click is Live's inspector, summary first (goal, owns, state, last output,
  cost), then one page each: Plan, Claims (Release, Steal), Diff, Test result, Log; Stop the run (one confirm), Review the
  plan, Steer its worker (the lane's worker in the inspector: Steer, Pause, Stop), Watch in Session. Hover = its card.
- **Run a goal** on Live's bar and in the palette opens the goal form as a panel beside the canvas (what you want, done
  when, the shared files, the gate's test, Review the plan first) that says what it will do, what it may cost and where
  it writes before Run; Run it across the fleet and a pack's workflow are in it. No screen of its own.
- **Review the plan first**: the lead waits on you on Live; Review the plan opens the plan review (the 3.0.9.0 canvas) as
  a Live panel, the canvas folded while it is open; Approve and run closes it.
- **History**: a goal run's row says how it ended, its wall time, its cost and its models (`GET orchestra/runs` rows
  carry `models`, `elapsed_s`, `ended`, `stop_reason`) and opens its report as a page of History -- the plan and its
  lanes, the outcomes, the gate, the merge, the artifacts, a dry run's jobs -- with Copy, Replay and Run it again.

#### Removed (each door and where its job went)

| Door | Its job now |
|---|---|
| Agents -> Runs (the view, `R`, `?view=runs`, `?mode=orchestra`, the palette's **Agents: Runs**) | Agents -> Live (`R` lands there) |
| Runs' Start screen (the goal form, the five steps, past runs, open the workspace anyway) | Live's **Run a goal** panel; past runs: History |
| the Goal panel (the open run's line: state, cost, stop, new run) | the run's lead on Live and its inspector (Stop the run) |
| the Workflow panel (the step graph, the gate diamond) | the run's block on Live, the lead's waits (the merge, the gate) |
| the Run grid panel (the counters, one tile per lane) | the lanes' boxes on Live; the lead's summary (lanes by state) |
| the Lanes panel (the timeline, the hand-off arcs, the owns line, a lane's claims) | each lane's box (OWNS row) and its inspector pages (Plan: after and takes; Claims) |
| the Live file panel (the goal file with each lane's bands) | a lane's **Diff** page (its units: base, then the lane's text) |
| the Report panel and its Artifacts tab | History's report page (the checks, the lanes, the gate, the merge, the artifacts; Copy) |
| the Log panel | a lane's or the lead's **Log** page |
| the Claims panel (Release, Steal) | the **Claims** page (Release, Steal while live) |
| the plan canvas taking the console's place | the **Plan** review panel on Live (from Review the plan) |
| the "+" menu's RUNS group (New run, the runs, the missions) | Run a goal; History; the Mission panel (`M`) |
| Runs' mission rows | a running mission on Live's fleet scope, a finished one in History; its panel on Live |
| the Mission panel on Runs | the Mission panel on Live (`M`, `?mode=fleet&mission=<id>`) |
| J / K over the lanes, F follow the Log | J / K hop Live's agents; a lane's Log page |
| the palette's Orchestra: new run / stop run / open run / focus lane | Agents: Run a goal / stop the run / lane N; History: run <id>; Agents: review the plan |
| compare two runs, retry | none was a Runs control: two reports side by side are two History pages; Run it again on a report is the retry (the goal filled in) |

- Files: `routes/orchestra/` Orchestra.tsx, Start.tsx, OrchRail.tsx, GoalPanel.tsx, WorkflowGraph.tsx, RunGrid.tsx,
  Lanes.tsx, LaneEdges.tsx, LiveFile.tsx, Log.tsx, Claims.tsx, Report.tsx, ReportTabs.tsx, commands.ts and the old
  FeedPanels.tsx (its FeedDot kept as FeedDot.tsx): 1,621 lines; `styles/orchestra-file.css` (143) and every dead rule
  of orchestra.css, orchestra-plan.css, start-view.css, agents.css; the eight panels' help text (help-orchestra.ts keeps
  the plan review's); SECTION_HELP's `orchestra` copy; the pictures `studio-orchestra.png`, `-start.png`, `-plan.png`
  (new: `studio-run-live.png`, `studio-run-report.png`); Runs' tests and drivers rewritten for Live and History.
- Docs: STUDIO-orchestra.md rewritten ("Studio: a goal run on Live and in History"), STUDIO-agents, ORCHESTRA "In
  Studio", the glossary (lane, plan), the README section and every doc that named Agents -> Runs.

#### Also in D

- **The capability checker is core again** (`halo_harness/packs/fleet_registry.py`, `peers/needs.py`,
  `peers/projects.py`, `packs/fleet_rules.hidden`): with the fleet pack off, a pack workflow's capability `requires`
  are checked and a pack declaring capabilities shows its rows (`halo pack inspect`, `halo pack doctor`); the fleet pack
  re-exports them through `ext.core` (REACHABLE + `packs.fleet_registry`, `peers.needs`, `peers.projects`).
- **`scripts/prepush.py`** removes every folder under `halo_harness/` and `tests/` that holds nothing but `__pycache__`
  before the tiers (one line each), and on Windows passes over WSL's `bash` for Git's (one line; no Git bash: the fix,
  exit 2) -- `scripts/prepush_tree.py`.
- `tests/helpers/run_all_support.py`'s cache list names the real modules (`peers.catalog`, the fleet pack's `health`).

### E: the README and the docs intro say what Halo is

- The README is the owner's wording ("Multi-agent. Multi-workflow. Fully visible."), five pillars (See, Shape, Mix,
  Local, Start) with one Studio picture each, Install, and "Everything else is a pack" with the shipped packs; the
  docs map, the HANDBOOK, STUDIO.md and harness/INSTALL.md open the same way, and pyproject and `halo --help` carry the
  short description.
- Pictures: the hero carries the tagline; Cast, Workflows, the model picker, Setup (no Machines step), Local, Packs,
  Settings (its General page: the Fleet page is the fleet pack's) and the six-section banner are re-rendered.

### The living canvas (built as 3.3.18.0, shipped here)

The owner, 2026-11-10: "i feel like agent canvas should be better. i always see like unused older version of
orchestrations that aren't even happening when I look at it. id love to see what is actually happening when i look at
that view." Agents -> Live now shows only what is happening, with the plan under it, what each agent waits on, one
sentence of what goes on, and zoom levels that change what is drawn (docs/STUDIO-live.md).

#### Changed

- **Agents opens on Live**: Alt+2, the rail, `?mode=agents`, `halo studio --mode agents` and a `focus` frame without a
  view land on Live -- what runs now, or one sentence ("Nothing is running. Start a session, or open the last one as a
  replay.") with **Open the plan (Cast)** and **Replay the last session**. Doors that name a view still win (`?view=cast`,
  C / R / L / W, `?mode=roles`, `--edit`). A fresh Studio with nothing saved opens there too (it opened on Cast's Start view).
- **Nothing past is drawn as present**: a finished agent stays ten seconds, a failed one until its **dismiss**, then leaves
  (its group and its session with it); a finish or a failure from before the page loaded is not drawn; Live picks the
  newest session with an agent at work; on the fleet the machines stay and an away member's rows do not count; a mission's
  parts show only while it runs or is planned. A stop counts as an end for the fade (`fleet/sync.ts`).
- **Cast is the plan**: its bar says "the lineup new sessions use: <name>" and, while agents run, "N live -- see Live";
  its cards no longer glow for a failure the page did not see, nor for an away member's last rows.
- **The rail's Agents badge** counts live agents on this harness and online members only.
- Live lays out once per change of the tree's shape and repaints between (a long session's frames never move a box).
- `GET fleet/history?role=main` dates a session by its transcript's first line (st_ctime was the last metadata change on Linux).

#### Added

- **History** on Live's bar (closed on load): past sessions, Orchestra runs and missions, newest first, each with what it
  was, when, how long, its cost and how it ended; a row opens a **replay** (muted, under a "replay -- ended <when>" banner,
  **Back to now**).
- **Plan under it** (Live's bar, `?plan=on|off`; on by default when the session's lineup has tiers or squares): the
  lineup's blocks as the map, each live agent inside its block, "not in the plan" with why; main's lines carry the plan's
  when, the dash only into a block at work.
- **What waits**: each live box says what it waits on (you, an agent, a tool, a model reply, nothing); the **waiting path**
  is a brighter hairline; **the one sentence** under the bar (`live-narration`) says what goes on now -- what waits on you
  first, the agents by block and what they do, what the session waits on, the models, the spend -- and a click centres the
  agent it waits on; a line's label shows the latest hand-off for eight seconds, its hover the last three, its click
  Conversations on that pair.
- **far | mid | near**: the zoom changes what is drawn (blocks only under 60%, boxes, boxes with their thought and tool
  output from 130%); Ctrl+wheel zooms around the pointer and keeps what is under it; Fit picks the level.
- Tests: `tests/test_studio_live_truth.py`, `tests/test_studio_live_plan.py` (Chrome); the density driver waits for what
  Live draws before it measures and measures the History drawer.

#### Docs

- `docs/STUDIO-live.md` (new part of STUDIO.md); STUDIO-agents.md and STUDIO-sections.md say Agents opens on Live; the
  Agents `?` help has the new steps; glossary: **replay**, **waiting path**.

### Docs: the README shows Studio

- "What it feels like" leads with Studio: `docs/media/studio-model-picker.png` (new, `capture_studio.py --mode picker`) and
  `docs/media/studio-auto.png` (new, `capture_steer.py --only auto`) replace the terminal model picker and auto-mode pictures;
  the steer animation and the phase-line picture left the README for one sentence each. The TUI captures stay in `docs/media`.

## [3.3.17.0] - 2026-11-10

**Copilot at work.** Halo signs in to your work's Microsoft 365 Copilot in the browser (or with a device code) and
talks to it as a provider with one model, `cp:work`, over the Work IQ API or Graph's preview Copilot Chat API. A
session or a lineup role can run on it as a consult role, any agent can ask it through the `copilot_ask` tool, and its
cost is said as "billed by your tenant", never as dollars (docs/PROVIDERS-copilot.md).

### R1: the door

#### Added

- **The settings** `copilot.tenant`, `copilot.client_id` (your own Entra app registration, a public client),
  `copilot.api` (`workiq` default | `graph-beta`), `copilot.web`, `copilot.timezone` and `copilot.scopes`: Settings ->
  Providers, docs/CONFIG.md (`providers/copilot_config.py`).
- **Sign-in** (`providers/copilot_auth.py`, `copilot_tokens.py`): the authorization-code flow with PKCE (S256) against
  the tenant's Entra endpoints, the redirect `http://localhost:<free port>` served once by a listener on 127.0.0.1
  (the state checked, one request, then it closes; a 5-minute wait, said in the terminal), Halo opens the browser and
  prints the URL; `--device` and any box with no browser (SSH, no DISPLAY, `HALO_NO_BROWSER`) use the device code.
  The refresh token goes to the env file as `HALO_SECRET_COPILOT_REFRESH`; access tokens stay in memory, refreshed
  60 s early; who signed in and until when is in `~/.halo/copilot/account.json` (no token).
- **The adapter** (`providers/copilot.py`, on `providers/http.py` only): Work IQ's JSON-RPC `SendMessage` with
  `A2A-Version: 1.0`, the `contextId` kept per conversation and the time zone in the metadata; Graph's
  `/beta/copilot/conversations` and `.../chat` with the text, `locationHint.timeZone`, `additionalContext`, the file
  URIs and web grounding. Both answer `{text, citations, sensitivity, conversation, api}`. Every failure is one line
  with its next step: not set up, not signed in, the sign-in expired, consent missing (the scopes named), no licence,
  billing not enabled, throttled after one `Retry-After` wait, offline mode.
- **`halo copilot signin [--device]`, `signout`, `status [--json]`, `ask "<prompt>" [--file URL]... [--no-web] [--api
  workiq|graph-beta] [--json]`** (docs/COMMANDS-copilot.md); `halo copilot` alone is `status`.
- **The mock** (`tests/helpers/mock_copilot.py`): Entra (authorize, token with PKCE, refresh, a revoked refresh, the
  device code), Work IQ's A2A endpoint and Graph's beta conversations, for every test here.

### R2: in the harness

#### Added

- **`cp:work`** (`model.py`'s prefix table, `providers/copilot_route.py`): a session or a role runs on the session's
  one Copilot conversation; the loop sends it no tools. Its catalog row (`providers/copilot_catalog.py`) says `takes:
  text, files, web`, `tools: no`, no context window and "Copilot Credits or your licence"; `halo models` lists it once
  you are signed in. Auto picks it for the need `work-data` ("research over your work data") when signed in, and
  never for a role that needs tool calls (`models_auto_work.py`).
- **The `copilot_ask` tool** (`tools/copilot_ask.py`, the `web` capability), registered once Copilot is set up: the
  answer with its citations as numbered lines, in the transcript like any tool result.
- **Cost**: a `cp:work` turn and a `copilot_ask` call add no dollars and mark the cost incomplete; `/cost`, `/status`
  and Studio's Cost panel say "Copilot: billed by your tenant (credits or licence)" (`providers/copilot_cost.py`).
- **Studio**: Setup -> Providers has a Copilot card (the status a row per fact, the tenant and app id, the door, Sign
  in / Sign out, the scopes to consent to as a copyable list, Register the app's steps); Sign in starts the browser
  flow on the machine Studio runs on ("finish in the browser tab that opened"), or shows the device code when there is no
  browser (`studio/setup_copilot_api.py`, `routes/setup/CopilotCard.tsx`).
- **`halo doctor`**: one Copilot row (not set up / signed in as ... until ... / token expired / consent missing /
  billing not enabled / no licence), each with its next step (`providers/copilot_doctor.py`).
- **Docs**: docs/PROVIDERS-copilot.md, docs/COMMANDS-copilot.md, the glossary's "consult role".

### On 3.3.16.1-3.3.16.3 (the round, merged onto master)

- **The prompt diet**: `copilot_ask` has its lean description (`tools/lean_descriptions.py`) and goes out right after
  what the lineup needs (`agent/prompt_diet.py` `AFTER_NEEDS`). Copilot not set up, the tool is not registered and the
  pinned first turns do not move; set up, a lean first turn grows by at most the tool's lean size
  (tests/test_prompt_budget_pins.py).
- **The shared ranking**: a model that states no tool calls is never ranked for code (`model_rank.ranks_for`), and
  `cp:work`'s missing dollar price never wins "cheapest"; Auto's `work-data` pick goes through `model_rank`'s one
  comparator (`models_auto_work.py`).
- **Studio**: a Cast hover on `cp:work` says it takes text, files, web; no tools, and "your tenant's credits or
  licence" as its price (the model row's `price_note`); a hover leaves out a context window nobody states. A square or
  a block template may name a bio on `cp:work`; its Costs line and block footer say "tenant credits" in place of the
  dollar band (all of it on Copilot) or after it (part of it) (`workflows/contract.py`, `SquareBlock.tsx`).
- **Live**: a `cp:work` role's turn shows as text rows with no THINK row (Copilot streams no thoughts and none is
  made up), its hand-back as a TALK row, a `copilot_ask` call as a tool row (tests/test_copilot_fit.py).

## [3.3.16.3] - 2026-11-10

The owner, 2026-11-10: "I still really want to see different blocks that you can almost like drag and drop in the agents
tab ... I wish I could see better groupings of these sub-agents ... here's this one task and here's the sub-agents in there".

### Added

- **Live in groups** (Agents -> Live and Session's Map): the sub-agents one step of a parent started together (one
  reply's Agent calls) are one box titled by their task -- the description they share, else the parent's own line
  before the calls, else the words the descriptions start with, never a model call -- and the parent's line goes into
  the box; a square's agents are one box titled `square <name>` with its DOES line; a tier's agents fall back to the
  tier's purpose; an agent started alone is not boxed. The bar counts working / waiting / done, the cost and the time,
  says Auto's pick in plain words ("3 readers on kimi-k3 for a pdf in the task"), folds to itself on the chevron (amber
  while one inside waits on you), and has a hover card. Ten agents are a grid of four to a row; boxes nest one level.
  `routes/agents/live/groups.ts`, `groupLayout.ts`, `GroupBox.tsx`; Session's timeline gains **by group**.
- Agent rows carry `spawn: {step, description, lead}` (`agent/agent_hooks.spawn_of`: the parent's id and reply count,
  the call's description, the parent's last line in that reply) and a square's row its `does`.
- **Blocks on Cast**: the lineup's enabled squares are blocks beside its tiers on one canvas, main's line into each;
  a square block opens to show the bios of its lineup on their models (folded: its TAKES / GIVES / COSTS lines; the
  chevron kept per lineup), its footer its limits and cost band. A click opens its summary in the inspector, with new
  **Purpose** and **Agents** pages (`PUT workflows/contract` takes `does`; a shipped square says how to copy it).
- `tiers[].purpose` in a lineup: the tier block's title line on Cast (its `...` menu edits it), Live's tier group,
  `halo teams show`'s tier line; the shipped auto lineup names both of its tiers.
- **The when** (part 2; the owner: "add this workflow in there when this situation happens"): a lineup's `workflows:`
  item may be `{ref, when: {needs, words, mode}}` beside plain refs (which keep their meaning): `needs` narrow what the
  square covers, `words` fire on what the task says, `mode` is `auto`, `named` (only by name), `always` (first, before
  main answers) or `off` (not connected). `workflows/router.py` reads it (always, then words, then the needs pick;
  `when_route.py`), the receipt's reason names the rule that fired (`handing the PDF to media: when main needs pdf`,
  its `rule` field), the Workflow tool's description says each rule; the auto lineup keeps its rules in config
  `workflows.when.<ref>` (a new keyed Settings row). `workflows/when.py`, `when_store.py`, `when_tool.py`.
- **The line carries it** on Cast: main's line into a square block has a short label (`needs pdf`, `says review,
  audit`, `always first`) with a hover card; a click on it, or the block's new **When** row in the inspector, opens the
  When page (four choices in plain words, what it writes, Save, Disconnect). A block with no line is dashed, its footer
  says "not connected: main never uses it", Problems lists it (NOT CONNECTED). Main's edge handle dragged onto a block,
  or the block's `⋯` menu (Connect to main, When, Disconnect, Take it off), draws the line.
- **The library on Cast, three kinds**: Workflows (yours / packs / shipped), Blocks you can start from, Agents (the
  bios), one search over all three; `+ Library` on Agents' bar on Cast too, beside the canvas, closed on load.
- **Block templates** under `halo_harness/templates/blocks/`: `thinking` (three reasoning agents), `media` (adds as
  `media-team`), `review-panel` (three reviewers), `local-workers` (a tier); every agent on `auto`, nothing names a
  provider. `workflows/blocks.py`, `blocks_tier.py`; `GET workflows/templates`, `POST workflows/templates/add | merge |
  remove`.
- **The four drags** with the real pointer, each asking first (WHAT / COSTS / WRITES) and saying what changed in one
  line: a workflow or a template from the library onto the canvas (wired to main by its covers); an agent (a bio, a
  tier card, another square's agent) into a block (a shipped square is copied to yours as `my-<name>` first and the
  board swaps to it, its rule kept: `workflows/members.py`, `PUT workflows/members`, `POST workflows/swap`); a square's
  agent out onto the canvas (the last cannot leave); a block by its title bar (its spot in the lineup's layout,
  `block:<ref>`). Undo / Redo walk each back in order with the lineup's own edits (`blocks/history.ts`). Keys: Tab
  reaches blocks and their agents, `M` then the arrows and Enter moves one, Delete asks in the inspector.
- CLI and TUI: `halo workflows enable <ref> --when needs=pdf,audio | words=review,audit | named | always | off | auto`,
  `halo workflows when <ref>`, a `when:` column in `halo workflows list` and `/workflows`; `halo blocks list | add
  <template> [--as <name>] | show <name>` (`blocks_cli.py`); `halo teams show` prints `block <ref> (square): when ...`.

### Changed

- Live's layout draws a group as one child of its parent (`liveLayout.ts` hands a tree with groups to
  `groupLayout.ts`; a tree without them is laid out as before). The glossary's **block** says the canvas meaning too;
  **group** is new.
- A lineup's `workflows:` list keeps its `{ref, when}` items through `halo workflows enable / disable` (edited in place,
  not rewritten as refs); `halo teams validate` checks each rule. The square inspector's summary has a **When** row; a
  square's hover card says its when in place of its covers on the board. W keeps its own board with the same library.
- **One order with 3.3.16.2's lineup roles**, explicit before implicit (`workflows/router.py` `route`, docs/WORKFLOWS-squares.md
  "The order"): a square named; then a square whose when fires (`always`, then `words`, then `needs`), ahead of a role;
  then a role of the lineup that covers the need ("to your media role"); then a plain ref's covers; then the line
  saying what would. An inherited `workflows.enabled` square is a plain ref, so on the auto lineup a PDF still goes to
  its media member unless the media square has a when. The Workflow tool is not offered when every square on is `off`;
  `halo doctor`'s squares line names a square's when; `halo workflows list` shows "on for <lineup>" / "off" and the when
  column. An edit to a lineup with no `workflows:` key (enable, disable, a when) starts from the set it inherits.

### Docs

- docs/STUDIO-blocks.md (a new part of STUDIO.md: "Blocks" and "Live in groups"; STUDIO-agents.md points to it), docs/ROLES.md and docs/AGENTS.md (`tiers[].purpose`),
  docs/WORKFLOWS-squares.md "A square as a block", the glossary, README's Agents part.
- Part 2: docs/STUDIO-blocks.md "Composing: the line, the library, the drags"; docs/WORKFLOWS-squares.md "When",
  "Block templates", "Who is inside a square"; docs/COMMANDS-workflows.md (`--when`, `when`, `halo blocks`); docs/AGENTS.md
  (`workflows[].when`); docs/CONFIG.md (`workflows.when.<square>`); the glossary's **when**; README's Workflows part;
  docs/media/studio-workflows.png re-rendered as the composed board.

## [3.3.16.2] - 2026-11-10

**Live: thinking you can see, agents talking.** The owner: "make watching a model think much better. In sessions
live tab, it's really amazing to get more visualization on what the models are really thinking. There should also be
a section that does this for model to model or agent to agent conversations. Maybe we can give that a label in the
live feed so we see models conversing with each other and that's its own label."

### Added

- **THINK rows** (`fleet/think.py`, `routes/shared/liveThink.ts`, `routes/session/LiveThink.tsx`): every agent's
  reasoning now reaches Studio as `thinking_chunk` frames from the session's agent tree (followed or not; before, the
  control socket dropped `thinking_delta` and only a followed agent's thinking showed, folded per chunk). One row per
  thought however many pieces it streams in: muted italic on a hairline `--think` rule, a caret while it grows, four
  lines with show all / show less, then `thought 4.2 s · 812 tokens` (the length when it streamed, the tokens when the
  provider reported `reasoning_tokens`). Native Anthropic thinking streams as it comes; the OpenAI-dialect reasoning
  (DeepSeek, Kimi, GLM, OpenRouter, Ollama's thinking models) lands in one piece at the end of the call. A model with
  no thinking shows no THINK row.
- **Thought, then act**: a THINK row's chip says what it led to (`then ran Edit basket.py`, `then answered`) and
  jumps there; the action row's `why?` opens that thought under the row.
- **The Thinking view**: a toggle beside Follow (off by default) narrows Live to the thoughts and what each led to,
  for everyone or the pinned agent. The kind pick gains think and talk.
- **TALK rows** (`fleet/talk.py`, `routes/shared/liveTalk.ts`, `routes/session/LiveTalk.tsx`): one agent's words to
  another as `agent_talk` frames, one shape `{id, from, to, text, why, re?, cut?}`: a parent's task to a child
  (`task`), the child's hand-back (`hand-back`, `re` the task), another agent's steer (`agent_steer` with
  `from_agent`), a Workflow square's hand-off and answer (`square`) and Studio's Hand to... another machine
  (`hand-over`). The row: the speaker's tag, an arrow, the listener's tag, the reason. A hand-back is one row: the
  agent's OUT block becomes the TALK row (an OUT after a TALK hand-back is not added). The map's edge between the
  two lights once from the speaker to the listener, with an arrow.
- **Conversations** (`session-conversations`, optional, the header's "+"): the pairs that have talked, newest first,
  and the chosen pair's thread, each message on its speaker's side with its reason and time, a reply under what it
  answers; a message's click scrolls Live to its row, "show in Live" narrows Live to the pair.
- The trace export (`halo session export`, Live's Export) writes a `thinking` row per thought and `talk:` rows for a
  sub-agent's task and hand-back (the hand-back in place of its last text, never both) and a square's receipt.

### Changed

- **The timeline shows the mix**: Live's timeline draws each lane by phase -- thinking, running a tool, writing,
  waiting on you, idle -- in the state tokens (the legend is in Live's `?` help); hovering a segment says the phase
  and its length, a click on a thinking segment scrolls the column to that thought.
- **`why?`**: on a row a thought led to, its first answer is that thought, inline under the row; "what the model saw"
  there is the turn's postmortem as before. The agent inspector's Thinking tab draws thoughts the way Live does,
  with what each led to.
- The kind pick's text no longer includes thinking (it has its own, think).

### Docs

- docs/STUDIO-sections.md (Session: THINK, TALK, the Thinking view, thought then act, the timeline's phases,
  Conversations), docs/FLEET.md (the two frames and their shapes, the KIND column), docs/STUDIO-session.md (the
  trace's new rows), the glossary (thought, agent talk), Live's and Conversations' `?` help, README "Watching a model
  think" and "Agents talking" with docs/media/studio-thinking.png re-rendered and docs/media/studio-talk.png new.

### From a session's own review (Kali, 2026-11-10)

The owner asked his session's own model (GLM 5.3 on Databricks, a custom lineup) what it thought of 3.3.16.0. It
named four things; each was checked against the code, all four were real.

- **A tie in the model pick went to the name.** `models_best_at.best_per_kind` ranked an equal score by the
  model's ref, so `...-opus-4-1` led over `...-opus-4-6`, an older model over its successor, and price and what
  was measured played no part (the roster, `halo models analyze`, `--best-for` and every pick behind them). Every
  pick now breaks a tie by one order (`halo_harness/model_rank.py`): the kind's score, the measured first-time
  success for the kind here (from 3 checked tasks), the newer version within a model family (`4.6` > `4.1`,
  `v4.1` > `v4`, `5.3` > `5`, a newer date suffix; read across `-`, `.` and `v`), the larger context, the lower
  price, the provider you have a key for, then the name; the cheapest per kind goes price first. The leader's
  line names the deciding term ("same score as X: newer", "...: measured 4/5 here", "...: cheaper") in the
  roster, `halo models analyze`, `halo models --best-for` and the Roles picker. The `auto` pick, `measured`, a
  pack bio's capability pick, the role presets' cheapest model, `halo gym propose` and the media ranking use the
  same order past their own rules. **The best-at index's schema is 2: every box rebuilds it once** on its first
  read after the update. Two test pins held the alphabetical accident (`tests/test_roster_dropped.py`:
  `ant:fable` led code over the same-scored, cheaper `ant:opus` by name alone) and were fixed.
- **Knowledge search answered with the sample's gate records.** A search for "halo harness update new features
  version" came back with 4 of 5 hits from the guided first run's sample repo: the gate's records carry its test
  command, whose python sits in the tool venv (`.../uv/tools/halo-harness/bin/python`), so "halo" and "harness"
  matched a path, there was no project scope, and equal scores went to the newest. Search now ranks by relevance
  first (paths, commands and shas are not words a record says; no shared content word, no hit), this project's
  records first at equal relevance and another project's marked, a routine passed gate under findings unless the
  query names its unit, re-runs collapsed to the newest with "x N", and each hit says why it is there.
  `halo start`'s sample records are tagged `sample` and never answer another project's search (an older one is
  recognized by its project being a sample folder); its card says so. New: `halo knowledge list --kind
  gate|finding|decision --project .|all|NAME`, `halo knowledge prune --kind ... --older-than 7d [--dry-run]
  [--yes]` (prints what it would remove and the count; only `--yes` removes), and a cap of
  `knowledge.gate_keep` (50, a Settings row) passed-gate records per project, applied when the gate writes one.
- **The Workflow tool sat on lineups that had no square.** A custom lineup with no `workflows:` key enabled no
  square, yet the tool was offered every turn and answered "no square is enabled for this lineup". A lineup
  with no `workflows:` key now inherits config `workflows.enabled` (default `media`) like the auto lineup
  (`workflows: []` is none, on purpose); the tool is offered only when a square is on for the lineup; a role of
  the lineup that covers the read (a `media` role, or a card whose bio's `models.needs` / kind covers pdf,
  vision, audio, video) takes the task the Agent tool's way, with the receipt "handing the PDF to your media
  role: the lineup covers it"; when nothing covers it the line says what would ("no role or square reads PDFs
  here: `halo workflows enable media`, or give a role a model that takes PDFs"). `halo doctor` says under the
  lineup which squares are on and from where; `halo workflows list` marks each "on for <lineup>" or "off".
- **No changelog on the box.** A `uv tool install` carries no CHANGELOG.md, so nobody there could see what a
  version changed. The package now ships the newest twelve dated entries (`halo_harness/data/changelog.md`,
  written by `scripts/release.py` when it dates a release); `halo whatsnew [<version>] [--since V] [--full]
  [--summary]` and the TUI's `/whatsnew` show the installed version's summary and each heading with its first
  line, and after `halo update` installs a newer version its last lines are that version's summary and "halo
  whatsnew for the rest".

## [3.3.16.1] - 2026-11-10

**The local prompt diet.** A first turn to an unknown remote Ollama model was 16,970 tokens of Halo's own prompt
plus a 16,384 reply's room, past its 32,768 window, so the window doubled to 65,536 and the model reloaded; it is
now 7,778 + 8,192 = 15,970 and goes out at 32,768 (16,384: 6,232 + 4,096 at 16,384; 49,152: 7,776 + 12,288; a 200k
cloud model unchanged, byte for byte). Measured with `halo local prompt`, pinned by `tests/test_prompt_budget_pins.py`
on Windows and Linux ([MODELS-prompt-diet.md](docs/MODELS-prompt-diet.md)).

### Changed

- **The reply's room follows the window** (`agent/reply_room.py`): a call to the session's own Ollama model asks for
  at most a quarter of the window it gets, never under the window class's floor and never more than it asked; a
  steward profile's `num_predict` and your own `max_tokens` keep their rule. A session's first call starts where
  Halo's own prompt is half the window at most, and no later call drops under the window last asked of the model (no
  reload). The turn says it once per session. `agent/loop.py`'s `_build_ollama_body_for_ref` calls it (no lines added).
- **Tools, lean** (`agent/prompt_diet.py`, `tools/lean_descriptions.py`): on the lean profile an alias goes on the
  wire once (`Task` as `Agent`; a call named `Task` still runs), a Windows session offers one shell (`prompt.shell`),
  every built-in tool goes out with a short description, and the block is held to 2,200 tokens up to a 16,384 window
  and 4,500 under 65,536, filled core first, then the lineup's needs (`Workflow` only when a square covers what the
  model lacks), the built-ins, the rest. What is left out stays callable by name and through ToolSearch; the system
  line naming it says so. The unknown-remote case: 29 tools, ~9,300 tokens -> 25 tools, 3,747.
- **The system text, lean** (`agent/prompt_lean_system.py`): the wire copy keeps the instructions (native tool
  calls, CLAUDE.md, read before edit, verify, plan mode, memory, hooks, delegation) and drops the per-tool list and
  the reference prose: ~4,150 tokens of Halo's own text -> ~580; the lean system message, memory included, 3,792.
- **The estimate is the wire's** (`providers/ollama_wire_estimate.py`): the window is picked from the estimate of
  the Ollama-shaped body that is sent, not the Anthropic-shaped request (0.5 % apart); the strict `num_ctx >= floor`
  check in `tests/test_ollama_trim_recovery.py` is back.
- The steward's fit plan never shrinks a window under Halo's own measured first turn plus a reply (`fit.floor_window`,
  8,192 when unmeasured); the steward's guide budget is 2,200 tokens (the new row).

### Added

- `halo local prompt [<ref>] [--window N] [--platform P] [--json]` (`agent/prompt_measure.py`): what a model's first
  turn costs before you use it -- the composition, the reply's room, the window, a row per tool (offered or left out
  and why). `/status` and `halo doctor`'s default-model row say "Halo's own first turn: N tokens of W (P %)" on a
  local model; Studio's model card has the row "Halo's first turn: N tokens (P % of the window)".
- The steward rule `prompt-heavy`: Halo's own part of the newest call over half its window, with one next step (the
  lean profile on, a bigger window, or the core tools).
- Config `prompt.shell` (`auto` | `bash` | `powershell`, Settings -> Models).
- Tests: `test_prompt_diet`, `test_prompt_budget_pins`, `test_prompt_measure`.

### Docs

- New [MODELS-prompt-diet.md](docs/MODELS-prompt-diet.md) (the before and after, the reply's room, aliases once, one
  shell, lean descriptions and system text, the budget test, `halo local prompt`); MODELS-prompt-budget.md gains "The
  diet"; COMMANDS-local.md `halo local prompt`; CONFIG.md `prompt.shell`; the steward's symptoms table `prompt-heavy`.

### Docs: the README and the pictures

- **Update, and the certificate line.** README gets a `## Update` section (`halo update`, `/update`, and the one-line
  repair for an install older than 3.3.16.0 that stops at `invalid peer certificate: UnknownIssuer`); docs/INSTALL.md's
  Update section and a docs/TROUBLESHOOTING.md entry titled by the error say the same.
- **The README as 3.3.16.0 is.** Agents' four views, `### Live on the fleet`, a `### Workflows: saved orchestrations as
  squares` part (the square, the router, the five shipped, `halo workflows`, the board), the Features and Documentation
  rows; its pins in tests/test_quickstart_docs.py follow.
- **Every Studio picture re-rendered** from the 3.3.16.0 build (the stills, both GIFs, the modes banner, `hero.png`,
  `social-preview.png`), and a new one: `docs/media/studio-workflows.png` from `tools/capture_workflows.py`
  (`tools/capture_studio.py --mode workflows`).
- **What it feels like, in the current look.** The README's terminal pictures were rendered in `claude-dark`; they are
  `instrument` now (the default since 3.3.15.0: `tools/captures.json`, `scripts/capture_scenes.py`). "Steering a running
  turn" and "Watching a model think" lead with Studio stills, `studio-steer.png` and `studio-thinking.png`
  (`tools/capture_steer.py`), then the terminal picture.

### Added: hover says what a box is

The owner, 2026-11-10: "hovering over gives a solid summary, if we click one we get that other panel with all the
detail about the selected box."

- Every box in Agents has a hover card: a Cast card, a Live agent, a session, a machine, a run's lead and lanes, a
  mission part, a workflow square on the board and in the library. Rest the pointer on it about 350 ms, or Tab to it
  (the arrows on the board), and one card shows beside it, inside the window, never over the box.
- A card is a title, one sentence of what the box is, at most eight rows of facts the page already has (a fact not
  known is left out), a NOW block while the box works, and a line saying what a click does
  ([STUDIO-agents.md](docs/STUDIO-agents.md#hover-and-click-33161) has each kind's rows).
- A click still opens the inspector and hides the card; so do Esc, a scroll, a press and the box's "..." menu. One card
  at a time, no buttons on it, no request on hover.
- A box with a card drops its plain tooltip; a button or chip inside it keeps its own. A workflow square's contract
  opens in the inspector on a click now, not on hover. Cast cards take the keyboard (Tab, then Enter selects).
- `studio.hover_cards` (Settings -> Studio, a new page; on by default) turns the cards off and the tooltips back on.
- Fixed on the way: the Workflows board drew 0 px wide while the library was closed (it fell into the library's
  column), so its squares could not be hovered or clicked until the library opened.

## [3.3.16.0] - 2026-11-10

**Agents: one section for your agents.** The owner, 2026-11-09: "what does teams even give us? ... roles and
orchestration are almost the same ... all rolled into the new agents". Team, Roles and Orchestra are one Studio
section, Agents (`Alt+2`), with three views on one switch -- Cast (the lineup and its bios: Roles as it was), Runs (a
goal for the lineup: Orchestra as it was, plus who owns what and Test this lineup) and Live (the session's agents as a
tree, a live Orchestra run's lanes under its lead). R2 folds the Fleet section into Agents -> Live, Setup ->
Machines and Local, so the shell has six core sections; every old door (and `?mode=fleet`) (`?mode=roles`,
`orchestra`, `team`, `--mode`, `--edit`, `/roles`, `/studio`) still lands on the right view and says the new one.
R1b (the inspector says one thing at a time, the density pass), R2 (the Fleet fold) and R3 (Workflows) follow.

### R1: Agents, one section

#### Changed

- **One section, three views** (`routes/agents/`). `SECTIONS` is Session `Alt+1`, Agents `Alt+2`, Fleet `Alt+3`,
  Packs `Alt+4`, Setup `Alt+5`, Settings `Alt+6`, Local `Alt+7`; the packs' own sections take `Alt+8`, `Alt+9` and
  `Alt+0` (`FIRST_KEY = 8`). Agents' bar starts with **Cast | Runs | Live** (`?mode=agents&view=cast|runs|live`; `C`,
  `R`, `L` outside a text field; the palette's "Agents: Cast / Runs / Live") and it opens on Cast with nothing else
  open. Cast and Live draw Roles' workspace, Runs Orchestra's, each keeping its layout, panel ids and every
  `data-testid`; the header's `+` and `...` menus, the palette's panel rows and the status bar follow the view.
- **The doors.** `?mode=roles` lands on Cast (`&view=live` on Live), `?mode=orchestra` and `?mode=team` on Runs, the
  latter with "Team's board is gone; a run's plan shows who owns what" the first time in a browser; a saved section,
  a `focus` frame, an attention row's `o` and a pack's route that name an old word land the same way
  (`ui/src/lib/agentsDoor.ts`). `STUDIO_MODES` is the seven sections plus `roles`, `orchestra` and `team`;
  `halo studio --mode roles|orchestra|team`, `/studio <word>` and the TUI's bare `/roles` open Agents and print the
  new door once (`studio/agents_door.py`). `halo studio --edit bio:|lineup:` opens `?mode=agents&view=cast&edit=...`,
  `--edit team` `?mode=agents&view=runs&edit=team`.
- **Who owns what** (Runs). Each lane says what it owns -- the claim ledger's keys for that lane -- on its plan card
  (`plan-owns`) and its row in Lanes (`lane-owns`); a focused lane lists its claims with holder and state
  (`lane-claims`), and the plan inspector shows the same rows as CLAIM LEDGER, read from `GET orchestra/<run>`'s
  `claims` (no new field).
- **Test this lineup** on Runs' bar: the guided first run on the active lineup (`POST start`), its card first; on Auto
  it is disabled with the Auto line beside it.
- **Live draws a run.** While an Orchestra run of Studio's repo is live, Live draws its lead and each lane under it,
  the lane's number in its colour and its worktree badge (the lane's branch); a click opens Runs on that lane.
- The Fleet attention rows of an Orchestra gate, a supervisor decision and a team stage open Agents on Runs (`o`:
  "open Agents: Runs"); a team stage held at its budget line answers Raise with where the team file is.
- Words that named the old sections follow: CLI help (`halo studio --mode agents`), the system prompt, the guided
  first run's card, Auto line and next steps (Agents: Cast, Agents: Runs, Fleet), the coach's error lines, Setup's
  **Edit in Agents**, the Session Map's **Open in Agents Live**, the Start views' Next footer (Cast -> Runs -> Fleet).

#### Removed

- **The Team section** (`routes/team/*`, `help-team.ts`, `styles/team*.css`, the status bar's TEAM cell, the Team
  Chrome drivers and `tools/capture_team.py`, `docs/media/studio-team.png`). Every `/api/team/...` route the board
  used answers 410: "Team's board moved into Agents -> Runs (a run's plan shows who owns what); halo team runs the
  team file" (`studio/team_init_api.py` deleted). `halo team` stays, `GET team/coach` stays, and a team stage at its
  gate is still a row of Fleet's Attention.

#### Docs

- New [docs/STUDIO-agents.md](docs/STUDIO-agents.md): the three views, the doors, what Team's board became, the owns
  line, Test this lineup, Live's run lanes and Cast. STUDIO-orchestra.md is "Agents -> Runs"; STUDIO-team-roles.md
  points to the new doc, keeping its anchors. STUDIO-sections.md has one Agents entry (Roles, Orchestra and Team folded
  in with "moved" lines), STUDIO-shell.md, STUDIO.md, README (seven sections, the banner and its captures re-rendered),
  TEAM.md ("the board moved to Agents -> Runs; `halo team` stays"), COMMANDS-studio.md, the glossary and every doc's
  `Alt+N` follow.

### R1b: the inspector says one thing at a time; the density pass

The owner's photo of Cast's Lineup tab (2026-11-09: "so so busy ... I can barely read ... idk what all of those
functions and settings even are") and his standing rule ("small blocks that make it hard to use ... make studio
cleaner and clearer").

#### Changed

- **The inspector opens on a summary.** With a lineup open, the Lineup tab (and the Assignment tab with no card) is six
  plain-words lines -- what the lineup does, the main model with its price and band, who is on it, where workers run,
  spend, "9 sections: 3 set, 6 at Halo's default" -- then one Edit row per block (Description and how it works, Where
  workers run, Schedule and warm set, the nine sections), each with its state in mono or "not set = Halo does: ...".
  No form, no YAML box, no help paragraph is on it.
- **One block per page.** Edit opens that block alone: Back (or Esc) to the summary, the title, the enforcement badge,
  the YAML toggle and a `?` with that block's field lines only; one sentence of what it does; "not set = Halo does
  ..." when it is unset; then its form. A selected card opens on its own summary (role, bio, the model with its takes
  tags, price and context, instances, the words that route to it) with Edit rows for its Slot and its Model override
  and Edit bio. Every testid stays (`roles-block-<name>` is the row that opens the page).
- **The density pass.** No control bar under 36 px, no row that is a target under 40 px, 12 px inside every panel
  body and between panels, one thing open per section on load: Settings' and Local's page-rail rows were 33 px (now
  `--row-h`, 40), and Session's Live and Prompt panels set their body's padding to 0 (the exemption went; the
  primitive's 12 px applies). Every core section kept one panel open on load.
- The Studio captures that still drew the nine-icon rail are re-rendered (Session, its Live column and GIF, Roles
  Live, Fleet x5, Packs, Setup, Settings, Local, Design, Agents, Roles, the modes banner, the hero and the social
  preview).

#### Added

- `LINEUP_DEFAULTS` in `halo_harness/field_help.py`: what Halo does when a lineup leaves each section (and
  `isolation`) out, read from the code that applies it; `GET /api/field-help` serves it as `lineup_defaults`, and the
  terminal's lineup view prints "(not set = Halo does: ...)" under each unset section.
- `halo studio --edit lineup:<name>:<block>` opens one block's page (`description`, `workers`, `schedule` or a section).
- The primitives mark themselves for the density rules (`data-density="bar|row|body"`), the tokens `--ctl-h` (36)
  and `--row-h` (40), and `tests/test_studio_density.py` (headless Chrome over every core section, each workspace
  panel opened in turn; the first offender fails with its section, testid and height); `tests/test_lineup_defaults.py`.

#### Docs

- STUDIO-agents.md (the summary, Edit, one block per page, the defaults line), STUDIO-shell.md (the density rules),
  ROLES.md (a lineup section not set: what Halo does), AGENTS.md, COMMANDS-studio.md (`--edit lineup:<n>:<block>`),
  MEDIA.md (the seven-tile banner).

### R2: the Fleet fold

A machine's agents are in Agents, its pairing in Setup, its models in Local; the Fleet section is gone. Six core
sections: Session `Alt+1`, Agents `Alt+2`, Local `Alt+3`, Packs `Alt+4`, Setup `Alt+5`, Settings `Alt+6`; the packs'
own sections start on `Alt+7` (`FIRST_KEY = 7`).

#### Changed

- **Live spans the fleet.** Agents -> Live has a scope switch, **this halo | fleet** (`live-scope`; `F`, Shift+F, on
  the canvas; `f` still fits): on fleet the canvas is machine > session > agent, one box per machine (Halo version and
  capability chips), its sessions as cards (git, mission and conflict chips, `...` menu) and their agents as the tree,
  a mission's parts in their machines' boxes (drag a part into another box to reassign it; claims and hand-on edges,
  conflict edges, lit spawn edges). The Session Map is the same canvas as a thumbnail (`routes/agents/live/`).
- **The inspector follows the pick, summary first** (`LiveInspector`): nothing picked is the fleet's glance (while you
  were away, machines, agents working, what waits on you, today's spend against the cap, the balances, the caps
  reached with Lift, one row per machine); a machine is its summary (who, health, spend today, Message) with Edit rows
  for Specs and who can... (the spec card, the recall box), Spend caps (`POST fleet/caps`, and a link to Settings ->
  Fleet) and Sharing and control (Setup -> Machines), one block a page with Back; an agent is the one agent inspector
  (the same component in Session's Agent strip, Cast's Live tab and Live); a mission part its card with its owns line.
- **The Attention chip** in Agents' bar (`agents-attention`, amber with a count, `A` toggles it, the palette's "Agents:
  Attention") opens the queue over the page (`fleet-attention` kept); **Activity** is an optional panel of Live, closed
  on load (the header's **+**, the palette).
- **Missions are runs**: Runs' **+** menu and Start view list the missions as rows (goal, state, parts, where they run)
  and offer **Run it across the fleet** when more than one harness is here; `M` and `?mode=fleet&mission=<id>` open the
  Mission panel in Runs; a part's row and card say what it owns.
- **Setup -> Machines** (the step before the Summary, `?block=machines`): the pair card, the share / control rows, the
  hubs joined and the People table with **Forget**; Fleet's Start view is its lead while only this harness is here;
  the Summary has a Machines line; the Start views' Next footer is Cast -> Runs -> Machines.
- **Local takes the Ollama panel**: Hosts gains the steward block (host picker, the models table, the traffic timeline,
  the fit plan with Apply and Copy), Steward gains Run now, the hub's note and the changes with Undo; the
  `ollama_steward` attention row's `o` opens Local -> Hosts on its host ("open Local"), a spend cap's opens the
  machine's spend ("open the spend"), a conflict's opens Live ("open Live").
- `?mode=fleet`, `halo studio --mode fleet` and `/studio fleet` land on Agents -> Live with the fleet scope and say
  once "Fleet is Agents -> Live now, the fleet scope on", with where machines, models and missions went
  (`studio/agents_door.py`); `STUDIO_SECTIONS` is the six, `STUDIO_MODES` keeps `fleet` as a door. The rail's agent
  count and "while you were away" dot sit on Agents; the status bar's FLEET cell went. Palette rows say "Agents: ...",
  "Setup: pair a machine", "Setup: forget <machine>", "Local: the Ollama steward".

#### Removed

- **The Fleet section**: `routes/fleet/Fleet.tsx`, `Start.tsx`, `Map.tsx`, `MapNode.tsx`, `MapChips.tsx`,
  `MapMission.tsx`, `MapSteer.tsx`, `MapTreeNode.tsx`, `FleetTree.tsx`, `layout.ts`, `Ollama.tsx`, the pair dialog,
  FleetSettings' member list (the People table has them), the People / Health / Costs / Capabilities panel faces,
  **By project** (each session card keeps its git chips), `help-fleet.ts`'s panel entries but Attention, Activity and
  Mission, `tests/helpers/studio_tree.py`, and `docs/media/studio-fleet-ollama.png`. Fleet's Ollama pieces moved to
  `routes/local/` (`ostore.ts`, `StewardBits.tsx`, `HostPlan.tsx`, `HostTraffic.tsx`, `HostSteward.tsx`).

#### Docs

- docs/STUDIO-fleet.md is "Fleet in Agents, Setup and Local" (where each Fleet panel went, Live on the fleet, every
  "How this works" anchor kept, Setup -> Machines); STUDIO-agents.md (Live's scope, the inspector by pick, the
  Attention chip, missions in Runs), STUDIO-sections.md (six entries; Fleet folded into Agents with a "moved" line),
  STUDIO-shell.md, STUDIO-setup.md (the Machines page), STUDIO-local.md and MODELS-ollama-steward.md (the steward
  block), FLEET.md's Studio part, MISSIONS.md, README (six sections, the banner and the fleet picture re-rendered),
  COMMANDS-studio.md, the glossary and every doc's `Alt+N` follow.

### The map's boxes say everything they hold

The owner, from Session's Map on Kali (2026-11-10): "information gets stomped on, it's ok if the boxes elongate to fit
the words, just don't squish them. Also no need for tui in the boxes."

- An agent's box on Live and on Session's Map (`routes/roles/LiveNode.tsx`, `styles/nodes.css`) is 268 x 124 px
  (240 x 110 compact; 228 x 92 and 180 x 70 before), and each thing it says has its own row: the name whole (the full
  name in the tooltip when even that is cut), the role under it in the second accent colour (`roles-live-role`), the
  model on the left of a row whose right side is the cost and the time (the model gives way, the cost never does),
  then two lines of what it does now (`roles-live-now`) or the running tool. Nothing is cut by a character count
  before the box is full; the badge and the menu never shrink.
- A session's box (`routes/agents/live/SessionNode.tsx`) shows its title on two lines before it is cut, the project
  and branch beside its cost, and the kind chip only for a session that is not the terminal's (`headless`, a mission
  part); "tui" is no longer printed. A file another session edits too is its own line ("! also edited elsewhere:
  basket.py") in place of a clipped chip.
- The role leads an agent's box when it has one ("reviewer", "writer"), and the agent's own name is the muted line
  under it (the owner: "do role first in the boxes"); a box with no role is titled by its name as before.
- A node's "..." menu measures itself and opens upward when there is no room under the node: with eight items its
  last one, Open in Session, sat below the window on a node low on the canvas, and a click there did nothing
  (`routes/agents/live/NodeMenu.tsx`).
- Live's auto-fit runs before the tree is painted, so a tree is never shown for a frame at the zoom of the scope you
  just left, and a zoom pressed in that frame is no longer undone (`routes/roles/LiveMap.tsx`).
- A panel added from the header "+" or a palette door while its section is still laying out is added when the layout
  is there, however long that takes; it was dropped after one 120 ms retry, which a slow machine lost
  (`lib/workspace/persist.ts` `whenLaidOut`, `shell/commands.ts`, `routes/agents/fleetDoor.ts`).
- A failed agent's edge stays red while that agent is selected: the selection colour no longer covers a state colour
  (`styles/nodes.css`).
- docs/media: the Live, Session and mission captures, the modes banner and the hero re-rendered.

### Fixed on the way: a mission's report is there when its state says done; the Benchmarks page's stale mark

- **A Fleet mission's `report.md` and `report.json` are written before its final state lands on disk**
  (`fleet/mission_run.py` `_end` writes the report inside the state's update; `mission_report.write` takes the
  document the caller holds). Before, the state said done a moment before the files existed, and a reader that
  saw done could find no report (the hosted Linux runner did, on 0ec52632).
- **The Benchmarks page's stale mark no longer depends on who loaded first.** `GET local/benches` read the host's
  Ollama version only from in-process caches (the hosts strip's card, a provider call's cache); a page answered
  before those were filled showed no "measured on 0.40.5" and never re-read. `local_bench_runs._now_version` now
  probes `/api/version` once per host per process when no card holds it (the test flag's rule kept: loopback
  fakes only). The seeded fake `box` answers `/api/version` with the version its card says.
- **An update answer that came from the cache says so** (`update_note.py`). When the live check fails (offline, a
  short outage, a rate limit) `latest_available` answers from `~/.halo/update-check.json`; that answer printed like a
  live one, so a box behind a dead router read "available (stable): v3.3.14.0" and `halo update` said "already up to
  date" while v3.3.15.0 existed (the owner, 2026-11-10). `halo update --check`, `halo update` and `/update` now add
  "(from the cache, checked 6 h ago; the live check failed: network unavailable -- run `halo update --check` again
  when you are online)".
- **`halo update` survives a network uv's own TLS does not trust** (`update_install.py`; the owner's Kali, 2026-11-10:
  uv stopped at "invalid peer certificate: UnknownIssuer" on the `requirements.lock` URL while git, which trusts the
  box's CA store, had cloned fine, and halo stayed on 3.3.14.0). The lock is now fetched by halo itself (the same TLS
  policy as every other request: the system's store and any configured CA bundle) into a local file; when that fetch
  fails the pin is dropped for this run with one line; a certificate failure in the installer itself is run once more
  on the system's certificate store, and a second failure says what to check (`env | grep -i proxy`, an intercepting
  proxy's CA). The store is asked for through the environment (`UV_SYSTEM_CERTS=1`, and `UV_NATIVE_TLS=1` for a uv
  before 0.11), not the `--native-tls` flag, which uv 0.11 renamed and says it will remove: one retry that works on
  every uv, printed as a line to paste. `scripts/install-halo.sh` and `install-halo.ps1` do the same when their
  `uv tool install` fails, so a box whose old `halo update` cannot get past the certificate is repaired by running
  the installer again. The "after" line reads the version under the banner, not the banner.

### R3: Workflows, squares and the router

The owner, 2026-11-09 evening: "have that whole entire workflow in like a square ... your main kind of orchestration
agent can just now point to the different workflow squares ... I might be using a model that has no visualization,
can't read PDFs, but it knows that there's a workflow that has other models that can process that information". A
square is a workflow with a contract; the main agent hands a task to one through one tool, the router.

#### Added
- **A square's contract** in the workflow file (`workflows/contract.py`, the schema and its JSON twin): `does`
  (`description` stays its alias), `takes`, `gives` (required for a square; checked when it returns), `covers`,
  `lineup`, `engine` (`session` | `orchestra` | `mission`, run as orchestra while only this harness is here), `budget`
  (`band`, `cap_usd`) and `limits` (`depth` default 1, `turns`, `wall_s`). One meaning line per bad value; a hand-off
  written at the root says it belongs on a stage. A workflow without `gives` lists and runs as before and is never
  picked.
- **The registry** (`workflows/registry.py`): squares from yours (`~/.halo/workflows/`), the project's
  (`.halo/workflows/`), the running packs' (`<pack>/<name>`) and the shipped ones; a bare name resolves yours >
  project > shipped; `spec.find` reads it. Enabled per lineup: a lineup's `workflows:` list, or on the auto lineup the
  new config key `workflows.enabled` (Settings -> Agents and roles; default: `media`).
- **Five shipped squares** (`templates/workflows/`): `media` (pdf, vision, audio, video on an `auto` lead), `plan`,
  `review`, `research` (session) and `code` (orchestra: build, then review), each with `limits.depth: 1` and a check.
- **The `Workflow` tool** (`tools/workflow.py`, `workflows/router.py`, `workflows/square_run.py`): `Workflow(need |
  name, task, files)` on the main agent and every bio allowed `Agent`. The gaps are the task's needs minus what the
  model takes (the `/model` takes column), plus the asks; the enabled square covering the most gaps, nearest the
  session's band, takes it, and one line says why ("handing the PDF to media: your model takes text only"); no square
  is one line and the model goes on. A session square runs one agent through the Agent tool's path (the parent's
  permission engine and rules); an orchestra square compiles and runs, bounded by `limits.wall_s`. Depth and the cap
  (the square's or the session's remaining, the smaller) are enforced in the tool; a session square is stopped past
  its cap, wall time or turns.
- **Receipts** (`workflows/receipts.py`): each hand-off is a `receipt` node in the transcript (the files' names, never
  their content), a node on Agents -> Live under the agent that called it (the agent row's new `square` field, the
  square's name in mono and its engine's colour, its cost beside the session's), a `squares` line on the Session's
  Cost panel, and a `squares:` line of an Orchestra run's report, in order.
- **Agents -> Workflows**, the fourth view (`W`, `?mode=agents&view=workflows`, the palette's **Agents: Workflows**;
  `routes/agents/workflows/`, `styles/workflows.css`, `studio/workflows_api.py`): the board of enabled squares (240 x
  140 cards on the 12 px grid: DOES / TAKES / GIVES / COSTS and a limits chip), the library (yours, packs, shipped,
  a search box, `/`), a drop's confirm card (what / cost / time / writes), the `x`, the summary-first inspector with
  Enable, Budget, Limits and YAML pages, the still edges with one moving dash toward the square at work.
- **`halo workflows list | show | enable | disable | test | new`** (`workflows/squares_cli.py`; `check` and `run`
  reach `halo workflow`'s), the TUI's **`/workflows`**, and a `square` check per pack square in `halo pack test`.

#### Changed
- `halo workflow` keeps its verbs; `spec.find` takes a bare name (yours, the project's, shipped). A lineup of yours
  may name a bare square in `workflows:`.
- A bio allowed `Agent` or `Task` is allowed `Workflow` too (`config/agents_md.py`).

#### Docs
- New docs/WORKFLOWS-squares.md (the contract, the registry, the router, receipts); WORKFLOWS.md "A square";
  COMMANDS-workflows.md `halo workflows`; STUDIO-agents.md the fourth view and the board's rules; SLASH-COMMANDS-tui.md
  `/workflows`; PACKS.md "A pack's squares"; AGENTS.md the `Workflow` tool; CONFIG.md `workflows.enabled`; the
  glossary's "square" and "router" (and a sentence on "receipt"); the module map.

## [3.3.15.0] - 2026-11-09

**Studio wears the Instrument look.** A design session answered `docs/STUDIO-redesign-brief.md` with "Instrument"
(`docs/design/studio-instrument/`: the proposal, the mock-ups, the prompt it was written to be applied with), and this
version applies it as its first round (the second, R2, makes every model list say what a model takes): an eleventh palette, `instrument`, that Studio draws on a dark system; solid surfaces,
1 px hairlines, corner ticks on every panel, cyan for work and selection, amber for what waits on you, mono for data
and sans for prose; four animations that carry meaning and nothing else that moves. It restyles only: no section or
panel is renamed, no shortcut, route, `?mode=` word or `data-testid` changes, and the rail keeps its nine core
sections in their order with the packs' after them.

### Fixed on the way: an Orchestra worker's "STOP: none" is no stop

- **A worker that says the stop condition did not apply no longer kills its lane** (rolo, Kali, during the guided
  first run; finding f-20261109-9f7492). `stop_line` read any reply line starting with `STOP:` as a real stop, so
  "STOP: none -- my unit is written" or "STOP: not applicable" failed the lane and every lane that depended on it, and
  the retry path never retries a stop. A reason that only says it did not apply (none, n/a, no, not applicable, does
  not apply, nothing, not needed) is skipped (`orchestra/worker_stop.py`); a bare `STOP:` still means the worker
  stopped; the worker prompt now says to write no STOP line at all when STOP WHEN does not apply.

### L1: Instrument, the look

#### Changed

- **The palette.** `instrument` joins the registry (`halo_harness/themes/palettes.py`, PROPOSAL.md section 1: the
  seventeen tokens exactly, dark; every text token over 4.5:1 on bg, surface and surface-2, the lowest faint on
  surface-2 at 4.9; accent_ink on accent 10.5). Studio's "follow the system" draws it on a dark system (`:root`
  alone, `data-theme="auto"` and the server's first paint did holo); `holo` stays in the theme menu and on Settings ->
  Themes, `paper` stays the light default, the terminal's default is unchanged and `/theme` lists eleven. holo's
  label says it was Studio's look before this version.
- **The derived variables** (PROPOSAL.md section 2; `halo_harness/themes/studio_css.py`, the same rule for a pack's
  palette at run time). Surfaces are solid (`--surface-glass` is the surface, `--blur` 0), the resting `--glow` is
  no shadow and `--glow-strong` a 1 px accent ring, Studio's hairlines come from the opaque `border` token (`--line`,
  the new `--border`; a light palette's `line` is its `border`, so a light page draws as before) with `--line-soft`
  for row rules and `--line-strong` the border lifted toward the text, `--grid-line` is the dot of the static dot grid
  (`--grid`, on map canvases only), one shadow level (`--shadow-1`), soft fills at 6-8 % on a dark page, and `--user`
  / `--tool`. The static block of `styles/tokens.css` adds the scales: radii (`--r-panel` 6 ... `--r-badge` 2),
  spacing (`--s-1`..`--s-6`: 4 8 12 16 20 28), type (`--t-title`, `--t-body` 13 px prose, `--t-data` 12 px mono,
  `--t-caption`, `--t-node-name`), motion (`--dur-fast` 160, `--dur-base` 240, `--dur-slow` 600 ms, zero under
  reduced motion) and the chrome sizes; comfortable density is 13 px text and a 40 px title row, compact 12 px and 32.
  Every old variable name stays.
- **The shell** (PROPOSAL.md section 3). The rail is 52 px of icons (176 px with titles on its chevron, kept per
  browser as before), the selected section the accent with a 2 px bar at the left edge, its badges squares; the header
  48 px with the section's name in mono caps, a `/` and its line, the command palette's door a 300 px field; the status
  bar 26 px in 11 px mono; the inspector a 344 px column; the palette 560 px with 36 px rows. The rail is still
  sections only, nothing opens on a section load, the inspector opens on a selection, Focus hides all but the page.
- **The kit** (`lib/ui`). Buttons 30 px in mono (on = the accent, primary the accent fill), Kbd 16 px, a Field's text
  input carries a leading `›`, Tabs are 36 px mono caps with a 1 px underline and no sliding, Menu and Dialog the one
  shadow level, every panel frame (`.glass`) four corner ticks with the selected panel's in the text colour, Toasts
  300 px in mono, Empty one line and a button, ErrorState one line in red, Skeleton still blocks after 300 ms, the
  FitMeter an 8 px track. **A confirmation shows DOES / COSTS / WRITES** (`lib/ui/DialogCost.tsx`, `Dialog`'s new
  `cost`): three mono lines before the buttons, the pack kit's offered-action rule made visible -- a pack's remove and
  update, Roles' Apply, delete a lineup, a bio or a card, leave unsaved edits, clone over a name, stop a mission, take
  over, hand to, kick, stop a team run, delete a local model.
- **Map nodes and edges** (Session Map, Roles Live, the Fleet Tree; `styles/nodes.css`). A node is surface-2 with a
  hairline and a 2 px rule across the top in its state colour (working cyan, waiting amber three pulses then steady,
  done green fading to rest over 10 s, failed red until you click it), a state square, a 1 px outline 3 px out when it
  is selected or a Live line for it is hovered; an edge is 1.5 px, a working child's carries a 4/8 dash moving toward
  it, a failed one is dotted. Nodes, Roles Live's nodes, Live's tags and the Fleet Tree show the resolved model without
  its provider prefix (`lib/modelName.ts`: `or:qwen/qwen3-coder` -> `qwen3-coder`); the Inspector, the Agent panel and
  the tooltips keep the full id.
- **Motion** (PROPOSAL.md section 5, `styles/motion.css`). Four animations: an agent starting (its node fades in, its
  edge draws from the parent) and ending, a receipt ladder climbing (the Prompt panel's four marks, 160 ms apart), the
  fit meter filling once, a toast arriving (16 px rise and fade, a 180 ms fade out; it holds 4 s, an error stays until
  its ✕). Each plays only for a thing that appears after its page drew (`lib/motion/born.ts`), never on a section
  load; the working state square blinks at 1.4 s. Everything else is still: no breathing, no flowing light, no sweep,
  no fade or rise when a section, a panel, a menu, a dialog or a row appears. Under `prefers-reduced-motion` every one
  is an instant state swap and a working edge is solid accent.

#### Docs

- docs/STUDIO-shell.md: the Instrument look (the rail's widths, the panel frame's ticks and faces, the Dialog's three
  lines, the motion rule), the eleven palettes; docs/CONFIG.md `theme` and docs/GLOSSARY.md: eleven palettes,
  `instrument` the dark default; docs/STUDIO-sections.md and docs/STUDIO-setup.md where a line counted palettes or
  described chrome that changed; docs/STUDIO-redesign-brief.md: what shipped.

### R2: the picker says what a model takes

The owner: "When you use forward slash model, show what the models capabilities are like visual, audio, pdf, etc. Is
there a way to see this info via studio?" The facts were in every catalog row and the honest line in the best-at
cache; now every place a model is picked says them.

#### Changed
- The terminal `/model` picker's rows carry a `takes=` column right after the ref (`halo_harness/model_takes.py`):
  what the model reads (`text` always, then `vision`, `audio`, `video`, `pdf`), `image` when it makes images, `tools`
  and `think` when stated or measured, `?` when the catalog states no inputs. The header line explains it. The prices
  follow it, so a narrow terminal keeps ref, takes and price and ellipsizes ctx and speed.
- The picker's subtitle shows the highlighted model's honest line ("vision+pdf in, tools, reasoning, long context
  (1M), premium; no audio") and the footer again when nothing is highlighted (`tui/dialogs/model_picker_takes.py`).
- `/model <ref>`'s confirmation ends with the takes words; `halo models` prints a `takes` column for the OpenRouter
  and Databricks tables; `halo models show <ref>` prints `takes:` and `best at:` (`--json`: `takes`, `best_at_line`).
- Studio: one tag group (`routes/shared/ModelTakes.tsx`, `data-testid="model-takes"`, the honest line its title)
  wherever a model is picked -- under the model select (Orchestra's goal and workflow forms, Roles' Assignment, MODEL
  strip, tier menu, bio form), beside Session's new-session select, Settings' model rows, and as the TAKES column of
  Roles' picker table and Setup's default model. `GET models`, the Setup rows and `GET sessions/new` carry `takes` (and
  the new-session rows the line); no new route.
- Studio, the owner's note on the picker's chips ("funky": ovals stretched to the row, rows several lines tall): a row
  is one line with fixed columns (MODEL, IN / OUT, CTX, TAKES, GYM); the tags are 18 px square-cornered mono words in
  a fixed order (vision, audio, video, pdf, image, tools, think; at most six, then `+n`; `text in` or `?` muted); the
  ranked "best at" kinds are no longer chips in the row: they stay the "best" sort and, with the honest line, the
  effort word and the card's chips, sit on one detail line under the list for the highlighted row
  (`styles/model-takes.css`).

#### Docs
- SLASH-COMMANDS-session.md (`/model`: the column, the line, the confirmation), COMMANDS-providers.md (`halo models`'
  takes column, `halo models show`'s lines), STUDIO-sections.md (the chips wherever a model is picked).

### R3: text boxes fit their text

The owner, with a photo of the Session Prompt panel: "These chat prompt boxes or all boxes that have text in them need
to be bigger ... I can't ever see the example text fully because the chat window is so small." The composer was one
line tall under a mostly empty panel, its two-line placeholder cut mid-word; the same one-line boxes held paragraphs in
Roles' Lineup tab, Orchestra's goal form, Fleet's Steer and Mission start and the Settings editors.

#### Changed
- One text box, `lib/ui/TextBox.tsx` (styles/textbox.css): three lines tall at the least, it grows with its text up to
  `maxRows` lines (12 by default) and then scrolls, with no resize handle and the Field look (the hairline, the accent
  border on focus; prose 13 px for text, mono 12 px for data). It grows by `field-sizing: content` where the browser
  has it and by its measured height on each change elsewhere. `Field` offers it as `multiline`; `lib/ui` (and a
  pack's `api.lib.ui`) exports it. It is now the only `<textarea` in Studio's source: the Prompt composer, Fleet's
  Steer box, Mission start's goal, the Take over brief and the Message box, Orchestra's three goal boxes and the plan's
  reject reason, Roles' Description and How the pieces work together (Description was a one-line field), Prompt
  notes, Rules (mono), the schedule's Prompt, the bio and section YAML (the bio's up to 24 lines), Settings' JSON and
  list editors, and Local -> Steward's question box (it was a one-line field; Enter asks, Shift+Enter a new line).
- The Prompt panel: the box takes the panel's free height while the conversation is short (`fill`: a hidden mirror of
  the text sizes it, the panel's rows are the header, the feed at what it holds, the foot with the rest); a
  conversation taller than the panel scrolls on its own and the box is three lines again, growing with the draft.
- Placeholders fit: at most two lines in a three-line box, the rest in the panel's `?`. The composer's is "Type a turn,
  or / for a command" (Enter, Shift+Enter and the history are in its `?`, with how the box grows); the goal's WHAT
  YOU WANT example, Mission start's goal, Live's Steer line for a finished agent ("pin a live agent to steer"), the
  steward's question (its examples moved to the page's `?`), the no-session line and a Settings list's default (shown
  only when short; the row's default line has it) are shorter.
- Read text is text: the field hints of Roles' Assignment and Lineup tabs sit in the tab's `?` (`routes/roles/TabHelp.tsx`,
  one label and line per field, each section's fields included; the label keeps its line as a tooltip), and a
  lineup's description in the Lineups list wraps to its full height instead of ending in an ellipsis.
- Panels breathe (the owner, with a photo of Fleet: the strips were "squished and too small ... the bottom is too
  short and not enough padding"): a strip was 5 grid rows, a 28 px panel under a 40 px title bar; it is 7 rows now
  (`STRIP_ROWS`, `lib/workspace/types.ts`), a 44 px strip 12 px from the next and 18 px from the workspace's edges,
  its bar centred over its whole height with 12 px at its sides. A title bar is 36 px at the least (compact
  density's 32 grows), a panel body pads 12 px at the least in either density (the plan canvas, the Roles canvas and
  the design board's 10 px too). The quiet layout gives the strips their full height and the page above them the
  rest. Orchestra's Goal panel is 10 rows taller for its three-line goal boxes, so every field and Run still fit.
- `tests/test_studio_textboxes.py` (full tier; driver `tests/helpers/studio_textboxes.py`): on the Prompt panel,
  Orchestra's goal form and Roles' Lineup tab every box is three lines empty, grows with four, stops at twelve and
  scrolls, and its placeholder fits; the composer fills the panel over a short feed and is its own size under a long
  one; TextBox is the only `<textarea`; on Fleet and Session with every panel collapsed each strip is >= 40 px, 12 px
  apart, its bar centred, and an open panel's bar is >= 36 px with its body padded >= 12 px
  (`tests/helpers/studio_strips.py`).

#### Docs
- STUDIO-shell.md (the text box rule beside the Field spec, the strip's and the body's sizes), STUDIO-sections.md (the Prompt panel's box, the Lineup and
  Assignment tabs' `?`), EXTENSION_API.md (`TextBox` in `api.lib.ui`).

### R4: instrument is the default, until you change it

The owner: "instrument theme should be the default theme for halo unless a user changes it." L1 drew instrument only on
a dark system with `theme` unset; now unset means instrument everywhere, and "Follow the system" is a choice you save.

#### Changed
- `theme` unset is `instrument` for every surface: Studio on a dark AND a light system (`:root` and the page with no
  attribute, the server's first paint, `main.tsx`'s fallback), and the terminal (`theme.DEFAULT_THEME`, `instrument-ansi`
  on a terminal without truecolor; `claude-dark` before). `halo config get theme` with it unset prints
  `(unset: instrument)`. The registry names it (`palettes.DEFAULT`) and `GET settings/themes` sends it (`default`).
- `theme: auto` is a value the key takes ("follow the system": instrument on a dark system, paper on a light one); the
  header's and Settings -> Themes' **Follow the system** write it (they cleared the key before) and are marked current
  only while it is saved; with the key unset the mark sits on instrument. `/theme auto`, `halo config set theme auto`,
  the config schema and the Settings row take it; a terminal draws the default for it. `halo config unset theme` is the
  way back to the default. Setup's Theme block says "Nothing saved yet: halo and Studio draw instrument".
- The TUI snapshots under `docs/harness/tui-snapshots/` are drawn in instrument now (re-rendered by `test_tui.py`).

#### Docs
- CONFIG.md `theme` (unset = instrument; `auto` follows the system), STUDIO-shell.md and STUDIO-sections.md (the theme
  menu and the Themes page), GLOSSARY.md and its packaged twin (palette, posture).

### R5: the guided first run belongs to custom lineups

The owner: "If I have a model selected for auto, then it just tests that 1 model a bunch of times and not really has
value ... If the user is on auto then that shouldn't happen." On the Auto lineup (or none) every part is one model
picked per task, so the guided first run would rehearse one model five times.

#### Changed
- `halo start` on the Auto lineup (or none) prints "Your lineup is Auto: the guided first run would rehearse one model
  five times. Build a lineup or a workflow in Roles (Agents from 3.3.16.0) and test it there.", offers `halo gym
  --quick`, writes nothing and exits 0 (`--json`: `{ok, ran: false, reason: "auto_lineup"}`); `--lineup <name>` or an
  active custom lineup runs as before (`halo_harness/start/auto_gate.py`).
- The same rule everywhere the start is offered: `halo init`'s wizard Summary and console offer (`--yes` included), `halo
  check` (`--all` and `--explain` leave it out, `--start` prints the line), the TUI's `/start`, Setup -> Check (no row;
  `start_auto` in `GET setup/state`) and Setup's Summary, and Studio's Start here (no Run button; `auto` in `GET start`;
  `POST start` and a Check with `start` answer 422 `auto_lineup`). The card and its costs are unchanged for a custom
  lineup.

#### Docs
- COMMANDS-init.md and HANDBOOK.md (where the test lives now: `halo start` for a custom lineup; Agents -> Runs adds "Test
  this lineup / workflow" in 3.3.16.0), WIZARD.md and STUDIO-setup.md (the row on Auto).

### R6: init ends with both running

The owner, on Kali: "during init the halo harness cli closes ... the terminal part never launched just the gui." The
wait counted a busy Studio as gone (ten failed GETs while a check or the guided first run held it up), so `halo init`
ended, and Setup's Done had no terminal to start halo in and said nothing.

#### Changed
- `halo init` on a terminal stays until Setup is done, then becomes the session: its line is "Setup is open in your
  browser: <url>. This terminal starts halo when you press Done there (Ctrl+C: stop here; `halo` later starts it).";
  failed GETs while Studio's port still answers no longer count toward "Studio closed" (only a silent port does); on
  Done it prints the Summary's lines and "Setup is done: halo starts here, paired with Studio at <url>", then starts
  halo in this terminal (the same home, so the session shows in Studio's Session section). Ctrl+C prints the stop line
  and exits 0.
- While it waits, init keeps `~/.halo/setup-wait.json` (its pid; `studio/init_waiting.py`), and Studio's Done answers
  who starts halo (`starts`, `line`): "halo is starting in your terminal" while an init waits; with none waiting it
  opens a terminal running halo (`studio/halo_terminal.py`: a console on Windows, Terminal on macOS, `$TERMINAL` then
  qterminal, xfce4-terminal, gnome-terminal, ... with a display on Linux) or says "no terminal found to start halo in;
  run `halo` yourself" in an error toast -- never silent. The Summary's Done note says which (`init_waiting` in
  `GET setup/state`).
- The console flow (`--yes`, no TTY), `--no-launch` and a terminal wizard that starts nothing end on one line: "Start
  halo with `halo`; `halo studio` opens Studio beside it, and the two pair on their own".

#### Docs
- COMMANDS-init.md, WIZARD.md and STUDIO-setup.md: the terminal waits, both come up, and what Done says.

### R7: the guided first run runs the lineup you picked

The owner, on Kali: "The whole init guided first run doesn't even use the orchestration you picked from earlier in
init. It keeps mentioning my-halo-dev-cycle." `halo start` copied the shipped `halo-dev-cycle` to `my-halo-dev-cycle`
and ran the Orchestra sample on that copy whatever the Team step applied, and every surface named the copy.

#### Fixed
- `halo start` (and Setup's Check row, Studio's Start here, the TUI's `/start`) rehearses the active lineup (`team` in
  config.json), or the one `--lineup <name>` names, read as it is: nothing is copied, `my-halo-dev-cycle` is never
  written (one left by an earlier run stays where it is), and `start.steps.DEFAULT_LINEUP` is gone
  (`halo_harness/start/lineup.py` `pick` / `parts`).
- A name with no lineup behind it is one line and exit 1: "no lineup named X; `halo teams` lists them" (`--json`:
  `reason: "no_lineup"`; Studio's `POST start`: 422). On the Auto lineup the line is now "Your lineup is Auto: pick or
  build a lineup in Roles first, then `halo start` rehearses it." (`--explain` too).
- The lineup's own cards play the parts: the lead is its `main` card (the lead's model on a real run), and each of the
  sample's lanes goes to a card that writes code (a `coder`, `implementer` or `subagent` role or alias, or a card used
  for implement or fix), in turn, as many as its `instances`; each job of the plan takes that card's bio (and the model
  it pins), and the workers run under the lineup (`--team`). Fewer lane slots run the sample in that many lanes, one
  line says so; a lineup with no such card says so and exits 1 before writing anything (`reason: "no_coder"`, 422 in
  Studio).
- The lineup step, the plan, the run, the report and the summary name the lineup and its cards; the card names the
  lineup it rehearses, its lead and lane cards, the distinct models it will call with their prices, and an estimate
  priced lane by lane (`start/card.py`); its "writes" line and the Setup Check row's read "a sample repo under
  ~/.halo/start/<date>/ (your lineup is not touched)". The gym row's candidates come from the same lineup.

#### Docs
- COMMANDS-init.md, HANDBOOK.md, GLOSSARY.md ("lineup", "guided first run"), STUDIO-shell.md, STUDIO-setup.md and
  WIZARD.md: the run rehearses your lineup; no copy anywhere.

## [3.3.14.0] - 2026-11-09

**The review's fix pass: the token and the grants, then children and keys.** The November code and security review
(plans/REVIEW-2026-11.md) found the doors that skip Halo's own machinery; 3.3.13.1 closed the three highs, and this
version closes the mediums, with the simple lows beside them: first what a pack's page can reach through Studio's
token and how a pack's grants and code are loaded (R1), then the children a service or an engine leaves and the keys
they inherit (R2). The extension API stays 1.2: the client `api.lib` hands a pack's page is now scoped to that pack,
which is what `api.lib` was always meant to be.

### R1: the token and the grants

#### Changed

- **A pack's page cannot grant itself more** (REVIEW #4: STUDIO-5, PACKS-2, PERMS-3). The writes that change what runs
  here -- a pack's grant, enable, disable, install, sources, update, rollback, remove, service, settings and config,
  the bundles, Setup, Settings and every write under `sessions/` (a new session, a command, a prompt) -- answer 403
  "this needs the owner's own page" unless the request carries `X-Halo-Owner`, an HMAC of a per-launch salt keyed by
  the launch token (`studio/owner_proof.py`). The served page carries the salt as `data-owner-salt` (a navigation
  only); the shell's first module (`ui/src/lib/owner.ts`) reads it and removes it before any pack module loads and
  keeps it in its own closure; only the shell's own client (`lib/api.ts` `call`) sends the header. `api.lib`'s
  `api`, `fetchJson` and `authUrl` are a client scoped to the pack (`ui/src/packlib/scoped.ts`): its own routes, its
  own `pack/<id>/` files and calls, its own canvas layouts and the read-only routes a page draws from; anything else
  rejects with an Error naming that rule. Pack modules are imported one at a time with `__haloStudioLib` set to that
  pack's lib while each evaluates (`routes/packs/importPack.ts`), so `@halo/api` is the pack's own client too.
  `studio-script`'s grant line: "its Studio script runs in the page with a client scoped to this pack's own routes";
  EXTENSION_API.md's `api.lib` section states the scope ("The client's scope").
- **The launch token leaves pack URLs** (#5: STUDIO-1, PACKS-3). What a page embeds where no header goes (an
  iframe, an image, a video, a module import) carries the pack's own key, `?k=<HMAC("pack-raw:" + id)>`, accepted
  only on a GET of that pack's `/api/packs/<id>/...` and `/api/pack/<id>/file/...`; `?t=` is no longer taken there.
  `GET pack/registry` names each pack's `key`; the design pack's frames and assets go through `authUrl` as before and
  now carry the key; its files.py docstring says what the frame can and cannot reach.
- **`studio-routes` says what it is** (#34: PERMS-9): "runs this pack's Python inside Studio's server, with Halo's
  keys and Studio's token; turning it off takes effect at Studio's restart for work already started", in the grant
  line and EXTENSION_API.md; unloading a pack's routes calls the routes module's own `unload()` when it defines one.
- **A `run:` command needs the `bash` grant** (#9: PACKS-4, PERMS-10). `packs/manifest.needed` adds `("bash",
  "command <name> (run:)")`, so the Pack Manager row and `halo pack enable` name it; until it is granted the command
  keeps its prompt form and `halo pack doctor` says what is missing (and when the pack does not request `bash`, that
  its pack.yaml needs it). `HALO_PACK_ID` is the pack's id from its record (`make_run` takes it), also for a pack linked
  from a folder of another name.

#### Fixed

- **Every non-media type is sandboxed; a raw pack body gets a CSP** (#6: STUDIO-3, PACKS-6). The design pack's
  `_files/` adds `sandbox allow-scripts` to every response that is not an image (SVG is not), a video, an audio file,
  a PDF or a font, so `.xhtml`, `.xml`, `.xsl`, `.svgz` and an unknown type get an opaque origin; a pack route's raw
  answer with no CSP of its own gets `sandbox; default-src 'none'`.
- **Only a loaded pack is unloaded, never on a failed read** (#7: STUDIO-4). `packs_routes.find` unloads only an id it
  loaded (a URL's `<id>.server` drops nothing); `packs/contribute._active` answers the last good read when a registry
  read raises (said once), so a pack folder mid-update unloads nobody's routes; a pack package gone from
  `sys.modules` is one fresh import.
- **The routes cache follows the install record** (#8: PACKS-5). The cache is keyed on the record's version, install
  time and last update as well as the file's time, and `halo pack update` / `rollback` drop the pack's routes
  (`grants.changed(unload=)` -> `notify_studio`), so an update that changes only a sibling module answers at once.
- **The shell is not framed by another page** (#32: STUDIO-2): `frame-ancestors 'self'` in the shell's CSP and
  `X-Frame-Options: SAMEORIGIN` on `/` and `index.html`.
- **The access log keeps no token** (#33: STUDIO-6): with `HALO_STUDIO_LOG` set, request lines say `t=...` and `k=...`.
- **The render route checks its project** (#38: PACKS-11): the design pack's `POST render` takes only a project slug,
  so `../x` answers 404.

### R2: children and keys

#### Changed

- **An untrusted project's bio or lineup does not pick your keys or the host** (REVIEW #10: PERMS-4). A bio or lineup
  that came with the project (`.halo/agents`, `.halo/teams`, a project-scope pack), read in a folder Halo does not trust
  yet, loses `secrets`, `environment.secrets`, `environment.pass_to_tools` and its isolation's `image`, `mounts`,
  `user`, `group` and `env`; the lane's opt-in lines say what was not applied and why (`isolation/spec.py`
  `untrusted_split`). Your own `~/.halo` files keep them; trusted, the project's do too.
- **An `after` policy covers the live output** (#11: PERMS-5). A call's `tool_progress` frames go through the same
  verdict as its result, taken once per call (`agent/policy_gate.progress`): pass streams them as they were, redact
  sends the redacted text, drop sends none -- to the TUI, Studio and every control-socket client, a phone included.
- **Read / Edit deny rules gate PowerShell** (#13: PERMS-7). `Get-Content` / `cat` / `gc` / `type`, `Select-String`,
  `Import-Csv`, `Set-Content`, `Add-Content`, `Out-File`, `Clear-Content`, `New-Item`, `Remove-Item`, `Copy-Item` /
  `Move-Item`, `>` / `>>` and `[IO.File]::*` on a denied path are denied the way Bash's readers and redirects are,
  through script blocks, `powershell -Command` / `cmd /c` payloads and `cd` (`halo_harness/permissions_ps.py`); a Read
  ask rule asks for the readers.
- **Every managed server gets a tool child's environment** (#22: LOCAL-2). An engine, llama-server, mlx_lm and the
  speech servers start with Halo's provider keys and the env file's keys left out (`providers.config.tool_child_env`
  through `engines/launch_env.child_env`); an engine adds back only its own key.
- **`--lan` is announced only when the engine checks the key** (#24: LOCAL-4). After the start, one request without
  the key goes to the engine's loopback port; a 401 / 403 is "every address, behind Halo's key (it refused a request
  without the key)", anything else stops it and starts it again on 127.0.0.1, the line saying the engine does not check
  Halo's key and the registry row carrying `lan_off`.
- **A FreeToken server's long wait is the first request's only** (#45: LOCAL-11): `engines/adapter.widen` gives the
  30-minute wait once per url and server.

#### Fixed

- **Stopping a slow service ends its children** (#17: CORE-3, REMOTE-6, PERMS-13, PACKS-10). A pack service runs in
  its own process group -- a new session on POSIX, `CREATE_NEW_PROCESS_GROUP` and a Job object with
  KILL_ON_JOB_CLOSE on Windows (`supervise/procgroup.py`) -- and a stop signals the group (SIGTERM, then SIGKILL after
  the wait; the Job ended on Windows), so signal-cli's JVM ends with its bridge; a service that ended on its own takes
  what it left running with it.
- **A Start / Stop written during a tick is not lost** (#25: CORE-7, PERMS-11, PACKS-8). The tick removes only the
  asks it read from `services-want.json`, under the file's lock, which `want()` takes too.
- **Engine rows carry `proc_start`** (#21: LOCAL-1). `halo local serve --runtime <engine>` records the process's start
  time; "already running", `halo local stop` and the exit sweep compare pid and start, so a reused pid is never
  signalled.
- **The steward skips request text in a log** (#23: LOCAL-3). A prompt line (Ollama's `prompt="..."`, a `"content":`
  / `"messages":` body, a pretty-printed request) is no server event in any classifier or line reader
  (`ollama_steward/body_lines.py`, the rule the host already used for a peer's log view); the server's read state
  counts them (`body_lines_skipped`). A tool result saying "CUDA out of memory" raises no finding, fingerprint or
  reply-cut proposal.
- **The policy pipe has a deadline** (#12: PERMS-6). Writing a request has the policy's budget; a process that stops
  reading is ended there, the call says "policy did not answer in <n>s" and its `on_error` applies, and the next call
  starts it again.
- **A Hugging Face download stays in its model folder** (#14: PERMS-8). A file name or commit with a drive (`C:evil`),
  any `:`, a backslash, a leading `/` or a `..` part answers one line and writes nothing; the target must resolve
  inside the folder; the `.part` file is named from the hub's hash only when it is hex (`providers/hf_paths.py`).
- **A phone's files land after the checks** (#20: REMOTE-3). The signal pack takes a message's files into `inbox/`
  only after the sender, signature and rate checks; a refused message's files are deleted from signal-cli's folder; a
  file sent with a `/command` is deleted and the phone told once; a running bridge clears `inbox/` files past a day
  every hour.
- **Small ones beside them:** a converted voice note leaves no temp folder (#29: REMOTE-4, PACKS-7); a sub-agent never
  keeps a Skill's temporary grant (#36: PERMS-15); `halo local log <id>` and Studio's log route read only a registry
  row's log, 404 otherwise (#39: LOCAL-5); a host's engine offer is reached on the paired host's address, an offer
  whose runtime is no engine id skipped and said once (#40: LOCAL-6); a peer row with a port that is not 1-65535 is
  dropped before placement and at the join (#41: LOCAL-7); a server's rotation set is its own files only, so
  llama-6000 never reads llama-60001 (#42: LOCAL-8); a program only the current folder holds is not run (#43:
  LOCAL-9); the runtime fetch's zip comment says what guards it and its downloaded archives are removed (#35:
  PERMS-14).

#### Docs

- #26 `health: {url}` is out of the services docs and the manifest comment; EXTENSION_API.md says a url health is
  accepted and not checked in this version. #27 SUPERVISE.md: the Windows at-logon task does not carry
  `JAVA_TOOL_OPTIONS` (set it for your user) and a systemd value is written as given (quote it yourself). #37
  COMMANDS-packs-kit.md: `halo pack test` runs a pack's own tests with your home and the network unless they set a
  scratch home (the template's do).

## [3.3.13.1] - 2026-11-09

**The steward hotfix and the review's first cut.** The usage audit of the owner's own logs (plans/ROADMAP.md, the
Focus plan's F1) found the Ollama steward tuning itself in a loop: each cut reply proposed twice the reply reserve in
force, auto mode applied it, its own ten-minute notes were the calls it tuned, and the profiles ended at 2^160; and a
host entry held its key as a value in config.json. This hotfix bounds the reserve, keeps the steward's own calls out of
what it reads, keeps it quiet when nothing changed, gives a way to reset a profile, and moves a key value out of
config.json. With it come the review's (plans/REVIEW-2026-11.md) three high findings and four of its medium ones:
the skill of a cloned repo, the Windows path spellings, a pack's symlinks, the supervisor's backoff and its one
instance, and the signal pack's off switches and reactions. The rest of the review is 3.3.14.0's.

### The steward hotfix

#### Fixed
- **The reply reserve is bounded** (`ollama_steward/rules_reply_bound.py`, `rules_reply.py`): `reply-cut` and
  `cut-resent` take the target from the measured cut (twice the cut reply, at least 4,096, in 1,024 steps), never from
  the profile's current value; never above the model's own context (its trained context from the catalog, else the
  measured cap) minus the prompt, nor above half the window in use; at most one num_predict proposal per model per hour,
  whatever the session; never twice for one cut (the cut is named in the finding's evidence). Where the rule before
  this would have doubled again, a `reserve-loop` finding says so and what held it. A profile's window or reserve over
  2^21 is never written, and a reserve over the profile's window is held to it (`profiles.clean`).
- **The steward's own calls are not its traffic** (`agent.live_call`, `ledger_call.py`, `ledger.read_calls`,
  `job_state.last_call_at`): its note and chat calls are tagged `by: "steward"` in the ledger; the rules, the "calls
  flow" timer and every reader of the traffic skip them (`read_calls(own=True)` shows them).
- **Quiet when idle** (`ollama_steward/agent_quiet.py`, `agent.due`): a note (one model call) only when a finding, a
  server or a profile changed since the last note, or a server event fired; each note keeps that signature.

#### Added
- `halo ollama steward profiles [reset [<model>]] [--host H] [--json]` (`ollama_steward/profiles_reset.py`), and a
  Reset button on the model's profile in Local -> Models (`POST ollama/steward/profiles-reset`): the tuned fields
  dropped, each named with its value (an absurd one by its size), the measured dialect record kept, every change in
  force on that profile marked reverted so no rollback or session end puts a value back.
- **A host key value moves to the env file** (`providers/ollama_key_migrate.py`): an `ollama.hosts[].api_key` that holds
  a key (not an env-var name) is moved the first time the hosts are read: the value to the env file as
  `HALO_SECRET_OLLAMA_<NAME>`, config.json keeps that name as `api_key_env`, one line on stderr names the host and the
  variable (never the value). `halo doctor --config` has a `key-value` row while a value is still there.
  The migration writes nothing while the test flag is set without a scratch home, and the doctor tests that ran
  `run_checks()` bare now run it against a scratch home (`tests/test_doctor_mcp_config_cli.py`): a test run never
  reads or writes the owner's own config.json or env file.

### The review, round 1

#### Fixed
- **#1 (PERMS-1) A cloned repo's skill no longer grants itself Bash** (`tools/skill_gate.py`, `tools/skill.py`,
  `agent/policy_gate.py`, `commands/registry.py`, `commands/skills.py`): a project or plugin skill in a folder that is
  not trusted gets no `allowed-tools` grant; its pre-run `` !`cmd` `` commands decide the Skill call (a deny rule on
  one denies the call, naming the command; an ask is the ordinary card naming the commands, and your yes runs them
  once); `/<skill>` typed works the same, without the card; one line says the grant was dropped. Every skill's pre-run commands now go through the
  armed pack policies before the permission engine.
- **#2 (PERMS-2) Windows path spellings meet the deny rules** (`permissions_paths.py`, `permissions._abs_posix`):
  `\\?\C:\...`, `\\?\UNC\localhost\C$\...` and `\\localhost\C$\...` (also `127.0.0.1` and this machine's name) are
  judged as `C:\...`; any other `\\`-rooted path for Read, Edit, Write, Grep or Glob is asked while a deny or ask path
  rule covers that tool.
- **#3 (PACKS-1) A pack ships its own files only** (`packs/fetch.stray_file`, `packs/install.copied_checks`,
  `packs/update.py`): install and update stop at a source holding a symbolic link or a file that resolves outside its
  folder, one line naming it, nothing written; update copies with `follow_symlinks=False`. `halo pack install --link`
  (your own folder, read in place) is unchanged.
- **#15 (CORE-1) A service failing a thousand times in a row no longer stops the supervisor**
  (`supervise/services.py`, `loop.py`): the backoff exponent is capped (5 s doubling to 300 s, as documented) and a
  fault in the services tick never skips the steward's notes and the pulse.
- **#16 (CORE-2) One supervisor per state folder** (`supervise/single.py`, `supervise/cli.py`): `halo supervise` holds
  an exclusive lock on `supervise/supervisor.lock` for its life, taken before the pulse is read; a second start (or
  `--daemon`) exits 1 naming the holder's pid.
- **#19 (REMOTE-2) The off switches stop a running bridge** (`remote/notify.py`, the signal pack's `bridge.py`,
  `service.py`): `notify()` writes nothing while `remote.enabled` is false; the bridge reads `remote.enabled` and the
  pack's `on` again every 5 s and ends (exit 0, one line, health `off`) when either is off.
- **#18 (REMOTE-1) A reaction answers only a card** (the signal pack's `answers.py`, `outbox.py`, `bridge.py`,
  `inbound.py`, `session.py`): each card message's sent timestamp is kept for its phone, and a thumbs-up (or a heart or
  a check) answers the open card only when its `targetSentTimestamp` is one of them; on any other message it does
  nothing.

## [3.3.13.0] - 2026-11-08

**The fold.** The three runtime rounds of 3.3.9.1-3.3.9.3 (FreeToken, Strata, TensorFold) were not what the owner meant:
"I wanted just new info that could be helpful for us ... the intent was to research and add helpful parts", and an
outside review found three sibling packages for engines almost nobody runs odd. This version opens by folding them into
ONE generic OpenAI-compatible local-engine adapter whose per-engine knowledge is a short descriptor table, keeping the
two ideas that generalised -- the paged mixture-of-experts fit (RAM and the disk link, not VRAM) and the steward
reading a non-Ollama server's log through a per-engine descriptor -- and dropping the engine-specific packages, the
TensorFold release fetcher and the three docs pages. llama-server and mlx_lm, the two engines the owner runs, are
untouched, and so is a user with none of the three.

**The Focus plan's first cuts.** The core gets smaller: what is optional becomes a pack Halo ships and the owner turns
on, the core keeping only the seam it plugs into.

### R1: one local-engine adapter -- FreeToken, Strata and TensorFold fold into a descriptor table

#### Added
- `halo_harness/engines/`: `descriptors.py` -- THE table, one entry per engine (`freetoken`, `strata`, `tensorfold`;
  adding one is an entry, never a round): id (the old runtime word), label, url, the source it was read from, default
  port, base path, health and queue routes, detection (owned_by, or /health keys asked only for rows of the engine's
  shape), program and `--version` pattern, the owner's install line per OS (Halo never installs an engine), where it
  runs, the managed start (and a supervised engine's plan, status and stop), the log patterns with the steward's
  sentence each, the fixes, the fit rule and figures, the tuning flags, and `verified: False` until an owner's live run;
  `models.py` (the models each engine names: 16 FreeToken checkpoints, 24 Strata sets, 24 TensorFold models with their
  stated sizes, one row shape); `adapter.py` (the program from `huggingface.engine_bins.<id>` or PATH, the auto-detect,
  the entry `engine: <id>`, Halo's key, the stop, the first request's wait); `launch.py` (`halo local serve --runtime
  <id>` from the descriptor, the plan check before a supervised start, the settle after it); `steward.py` (one log
  reader driven by the descriptor's patterns, the /health or /metrics queue read, one rule over the events);
  `fit.py` (the two generic rules, `vram` and `paged-moe`); `doctor.py` (one `halo doctor --local` line per engine
  found on PATH, configured or running); `peer.py` (the host's `engines: {<id>: offer}`, a peer's
  `hf:local/<model>@<host>`, an engine server as a placement option with its loading tax); `bench.py` (`halo local
  bench --host <id>` through the OpenAI-compatible route, the card kept under the model's own id too).
- Steward kinds and findings `engine-loading`, `engine-slots`, `engine-waiting`, `engine-backend-fallback`,
  `engine-disk-bound` (one rule, the descriptor's sentence and fix line, never applied); an engine's `loaded` line is a
  `load-result`, its errors `other-error`; knowledge/local-servers.md's "Other local engines" section with the five rows.
- `huggingface.engine_bins` (a map of engine id to its program); glossary "local engine" and "paged MoE".
- docs/MODELS-engines.md ("Other local engines"): the table rendered, the install lines, what Halo does and does not
  do, `verified: false` said plainly, how to add an engine.
- Tests: `tests/test_engines_descriptors.py`, `test_engines_adapter.py`, `test_engines_steward.py`,
  `test_engines_fit.py`, `test_engines_doctor_host.py`, over one fake engine (`tests/helpers/fake_engine.py`,
  `engine_home.py`, `engine_lines.py`) on free loopback ports; the old fit modules' 31 verdicts reproduced.

#### Changed
- Every seam that branched per engine reads the table: `ollama_steward/server_context_hf.py`, `server_rules_hf.py`
  (SAYS from the descriptors), `servers_hf.py` (the runtime words), `server_log_hf.py` (the queue read, the roster's
  model), `tune_lines_hf.py` (the descriptor's `tune`), `rules.py`; `providers/huggingface_local_probe.py` (detection,
  the default probe ports from the table), `providers/huggingface.py` (a peer's engine), `providers/local_server.py`
  (the stop, the supervised alive), `providers/stream.py` (the first request's wait); `local_hf_serve_cli.py`
  (`--runtime` choices from the table), `local_hf_cli.py`, `local_bench_cli.py`, `local_sched/place.py` (the host flag
  `engine`), `place_advice.py` (`engine_tax`), `models_library/browse.py`, `rows.py`, `search_filters.py`,
  `host/routes_view.py` (`engines` in the catalog), `host/state.py`, `doctor_local_ids.py`,
  `settings_catalog_rows_b.py`, `glossary.py`.
- A `local_servers` entry that says `runtime: freetoken | strata | tensorfold` keeps working (the ids are the old
  words); an entry Halo wrote before (`freetoken: true` ...) is still Halo's; the old `huggingface.<id>_bin` words are
  still read and `halo doctor --local` names the new one.
- MODELS.md, MODELS-steward-servers.md, LOCAL-MODELS.md, COMMANDS-local-servers.md, CONFIG.md, MAC.md, DEVELOPMENT.md,
  GLOSSARY.md, ARCHITECTURE-modules.md and docs/README.md point at docs/MODELS-engines.md and lose their per-engine
  paragraphs.

#### Removed
- `halo_harness/freetoken/` (bench, bench_cli, catalog, launch, link, peer, requirements, route, shape, waits),
  `halo_harness/strata/` (bench, catalog, control, detect, launch, peer, requirements, route) and
  `halo_harness/tensorfold/` (catalog, peer, requirements, route, source) -> `halo_harness/engines/`.
- `providers/local_runtime_tensorfold.py` -> `engines/launch.py`; `providers/local_runtime_fetch_tf.py` (the TensorFold
  release fetcher) -> nothing: Halo never downloads an engine; the install line says where the archive is.
- `local_sched/fit_ft.py`, `fit_st.py`, `fit_tf.py` -> `engines/fit.py`; `doctor_freetoken.py`, `doctor_strata.py`,
  `doctor_tensorfold.py` -> `engines/doctor.py`.
- `ollama_steward/server_log_ft.py`, `server_log_strata.py`, `server_log_tensorfold.py`, `server_stats_tensorfold.py`
  -> `engines/steward.py`; `rules_ft.py`, `rules_strata.py`, `rules_tensorfold.py` and their findings `ft-expert-thrash`,
  `ft-pinned-cap`, `ft-kernel-jit`, `strata-disk-bound`, `strata-slots`, `strata-download`, `tf-waiting`,
  `tf-backend-fallback`, `tf-load` -> `engine-disk-bound`, `engine-backend-fallback`, `engine-loading`,
  `engine-slots`, `engine-waiting`; the event kinds `expert-cache`, `pin-cap`, `kernel-jit`, `ram-tight`, `download`,
  `capacity`, `queue`, `load-start` -> the five `engine-*` kinds.
- Verbs and flags: `halo local bench --bw [--model DIR]` (`ft bench bw`, the measured host link) -> nothing (the fit
  says the table's link figure); `halo local serve --runtime strata --plan` and `--model-path` -> the plan check runs
  on every supervised start; `halo local serve --runtime tensorfold --yes` fetching the archive -> nothing;
  `halo local runtime remove tensorfold-<tag>` (no archive is fetched any more).
- Config words: `huggingface.freetoken_bin`, `huggingface.strata_bin`, `huggingface.tensorfold_bin` ->
  `huggingface.engine_bins.<id>` (the old words still read); the entry markers `freetoken: true`, `strata: true`,
  `tensorfold: true` -> `engine: <id>` (the old ones still recognised); the host catalog's `freetoken`, `strata`,
  `tensorfold` keys -> `engines: {<id>: offer}` (a peer still reads an older host's keys).
- Glossary: "expert cache", "offload", "expert set", "streams" -> "local engine", "paged MoE".
- Docs: docs/MODELS-freetoken.md, MODELS-strata.md, MODELS-tensorfold.md -> docs/MODELS-engines.md.
- Tests: `tests/test_doctor_{freetoken,strata,tensorfold}.py`, `test_{freetoken,strata,tensorfold}_fit.py`,
  `test_host_{freetoken,strata,tensorfold}.py`, `test_local_serve_{freetoken,strata,tensorfold}.py`,
  `test_server_log_{ft,strata,tensorfold}.py`, `test_local_runtime_fetch_tensorfold.py` and the helpers
  `fake_ft_server.py`, `fake_strata.py`, `fake_tensorfold_server.py`, `{ft,st,tf}_home.py`, `{ft,st,tf}_lines.py` ->
  the five `tests/test_engines_*.py` and `tests/helpers/fake_engine.py`, `engine_home.py`, `engine_lines.py`.

### R2: Design out -- the Design section is the shipped design pack; the core keeps the seam

#### Added
- Extension API 1.2 (`halo_harness.ext.API_VERSION`): `contributes.studio.sections[].view: {bundle}` -- a pack section
  drawn whole by one ES module of the pack, `mount(el, api)` on the section's page, behind `studio-script`
  (`packs/studio_view_rules.py`, `ui/src/routes/packs/PackView.tsx`); the first pack section takes the tenth key, `Alt+0`.
- `api.lib` on the bundle api (`ui/src/packlib/`): the shell's own React, ReactDOM, jsx runtime, the `lib/ui`
  primitives, the JSON client with the token (`fetchJson`, `authUrl`), the live feed, the store helpers, the theme
  (`tokens()`, `css(text)` as a constructed stylesheet), the panel workspace, the composite widgets (`Markdown`,
  `ModelSelect`, `PackForm`, ...), `kbd` and palette `commands`; it follows the shell's major version. The same object
  is `globalThis.__haloStudioLib` for a module built with `vite.pack.config.ts` (`vite.shared.ts` `shellLib`: React
  and `@halo/<part>` taken from the shell, never bundled). The bundle api also gains `routes` and `section`, and `on`
  hears the pack's `pack_live` frames.
- `contributes.studio.routes: {module, prefix}` and the `studio-routes` grant ("runs this pack's Python inside Studio's
  server"): `studio/packs_routes.py` imports the module through the pack's folder (`halo_packs.<id>`) and answers
  `/api/packs/<id>/<prefix>/...` with `handle(ctx, method, path, body, query)`; `ctx.publish(kind, data)` is a live-only
  `pack_live` frame; a GET also takes the token in `?t=`; a file answer keeps its own `Content-Security-Policy`; the
  module's `MAX_BODY` raises the 4 MB body limit for its prefix; a failure is a 500 with one line and a `halo pack doctor`
  row (`studio-routes`); disable, remove or a grant taken back unloads it.
- `ext.host` (`ext/host.py`): what Halo does for a pack's code (`state_dir`, `models(task)`, `media_models`,
  `mcp_servers`, `mcp_probe`, `child_env`, `fetch`, `halo_command`, `comfy()`, `HostError`); `testing.scratch_home`,
  `testing.studio` (a live Studio with the pack linked and granted) and `testing.pack_module`.
- `halo pack test` checks a view (the module exports `mount`), the routes (`GET ping` in shape) and runs the pack's own
  `tests/test_*.py` (`packs/test_run_studio.py`); `halo pack new --kinds studio` writes a page view with `api.lib` and a
  routes module with `ping` and `note` (`templates/pack-kit/kinds/studio/`).
- A command's `studio: <section>` frontmatter: the pack command opens its section (`commands/pack_studio.py`);
  `/studio <pack>--<section>`, `halo studio --mode <pack>--<section>` and `?mode=<pack>--<section>` open a pack's section
  (`studio/modes.py`, `ui/src/lib/sectionStart.ts`).
- The **design pack** (`halo_harness/templates/packs/design/`, off until enabled): `pack.yaml` (the Design section as a
  view of `studio/design.js`, routes `server/routes.py` under prefix `design`, `/design`, a palette line, the settings
  `model` and `budget_usd`, `requires:` for the seven ArtCraft CLIs), `server/` (the Design Python, ext-only), `studio/src/`
  (the Design page's sources, the Render and Settings panels), `studio/design.js` (built), `docs/DESIGN.md`,
  `docs/STUDIO-design.md`, README, HALO-PACK.md, CHANGELOG, and `tests/` (nine test modules: the eight Design modules
  that left the core and `test_review_pins.py`, the 3.0.2.0 review's artboard-route pins from test_review3_c/_c2; a
  runner, a rig on `testing.studio`, a fake craft app, the demo seed, the Studio capture, `pack_test.py`).
- Core tests `tests/test_pack_design.py` (fast: install, enable, the section and its key, `/design`, the old words, a
  route and the seam's failures, `halo pack test design`) and `tests/test_pack_design_ui.py` (full: the Design page in
  headless Chrome); `tests/helpers/design_pack.py`; `docs/STUDIO-local-media.md`.
- The Pack Manager and `halo pack inspect` say what each grant lets a pack do (`packs/grants.py` WHAT).

#### Changed
- Nine core sections: Session `Alt+1`, Team `Alt+2`, Roles `Alt+3`, Fleet `Alt+4`, Orchestra `Alt+5`, Packs `Alt+6`,
  Setup `Alt+7`, Settings `Alt+8`, Local `Alt+9`; the first pack section `Alt+0`. The modes banner is nine tiles.
- The Media panels (status, models, workflows) are Local's optional panels (its "+" menu), floating over its page;
  the palette's Media lines open them there. A paged section with optional panels shows its "+" menu.
- A pack panel may join Session, Team, Roles, Fleet or Orchestra (the registry's `core` is five).
- Layout names take `<pack id>:<name>` (the design pack keeps `design:<slug>`).
- Design's projects move from `~/.halo/design` to the pack's data folder (`~/.halo/packs/.data/design/projects/`), once,
  with one line saying so; Design's turn steps are the pack's `pack_live` frames of kind `turn`, a render's kind
  `render`; the raw artboard files are the pack's `_files/` route.
- Fleet's craft-app words and `halo media`'s comfyui lookup read their own tables (the Design crafts table went to the pack).
- The Inspector opens the panels a pack's page draws with `api.lib.workspace` (a view section's `sectionDef` reads the
  specs its Workspace registered), so the design pack's Knobs open its Artboards settings as before.
- The Chrome drivers' `press` waits until the control takes a press (not `disabled`): the Pack Manager's buttons stay
  disabled until its own reload, after the `pack_changed` frame already redrew the row.

#### Removed
- `halo_harness/design/` (store, session, sync, crafts, crafts_probe, critique, export, contrast, assets, controls,
  jsonio, cli) and `halo_harness/studio/design_*.py` (api, api_edit, artboards_api, assets_api, critique_api,
  export_api, files, request, system_api, turns) and `studio/media_render.py`: the design pack's `server/` now.
- `halo design ...`: one line pointing at `halo pack enable design` and `/design` (exit 2).
- The `/design` builtin: the pack's entry command takes the name; with the pack off, `/design` says how to turn it on.
- `halo studio --mode design`: `--mode design--design` with the pack on; the old word says how to turn the pack on.
- `/api/design/...`, `/design-files/...` and the 22 MB special case in `studio/server.py` (the routes seam's
  `MAX_BODY`), `POST media/render` and `GET media/renders/<id>` (the pack's `render` / `renders/<id>`), the
  `design_turn` and `media_render` feed kinds.
- `ui/src/routes/design/` (21 modules), `routes/help-design.ts`, `styles/design.css`, `styles/design-thread.css`,
  `routes/media/MediaRender.tsx`, the Design dialogs in App, the Design palette group, Design in the Start story.
- `tools/capture_studio.py --mode design`, `tools/capture_design.py` and `tools/design_demo.py` (the pack's
  `tests/capture_design.py` and `tests/seed.py`); the banner's Design tile.
- `tests/test_design_{contrast,crafts,session,store}.py` and `tests/test_studio_design{,_live,_more,_rest}.py` (the
  pack's `tests/`; `_more` and `_rest` named for what they hold, `test_design_turns_assets.py` and
  `test_design_page_routes.py`), test_review3_c's items 35 and 112 and test_review3_c2's item 7 (the pack's
  `test_review_pins.py`), test_studio_ui's Design checks (`tests/test_pack_design_ui.py`), test_media_comfy_cli's crafts check.
- `docs/DESIGN.md` and `docs/STUDIO-design.md` (the pack's `docs/`; the docs map and STUDIO.md point at its README;
  the Media panels' part is `docs/STUDIO-local-media.md`).

### R3: the Signal pack -- the bridge leaves the core and becomes a conversation

The owner: "it is just like a note that is sent to the user via signal. it needs to be a full back and forth
communication option". Why it felt like a note, from the code: the bridge was a foreground process nothing started;
pairing took four steps on two devices and every later plain text was refused unsigned; a text with no live session
got two error lines and was dropped; the answer came as timer-cut chunks followed by "Done."; the state showed only in
the TUI. Now the bridge is the shipped **signal pack**, run by the supervisor as a pack service, and a conversation.

#### Added
- **Pack services** (extension API 1.2, stable): `contributes.services: [{name, description, run, autostart, restart,
  health: {file | url, max_age_s}, log}]` (`packs/manifest_services.py`, `schemas/pack_yaml.py`, `pack.schema.json`),
  the grant `services` ("runs a program of this pack in the background while the supervisor runs"). `halo supervise`
  starts an enabled, granted pack's autostart services, restarts them by the rule (5 s doubling to 300 s), stops them
  on its way out (`supervise/services.py`, `services_rows.py`, `services_cli.py`); `halo supervise services`,
  `halo supervise service start|stop <pack>/<name>`, its lines in `halo supervise status`; `halo pack enable` says
  where each service starts; the Pack Manager's row shows "service running since 09:12" / "stopped: <line>" with
  Start / Stop (`POST pack/<id>/service`); `halo doctor` has one row per service; `halo pack test` checks a service's
  command and health shape (`packs/test_run_services.py`).
- **The transport seam** (`halo_harness.ext.remote`, API 1.2, stable): the live sessions and their control sockets,
  `start_session` (the supervisor starts it: `remote/session_start.py`, a 0.5 s lane in `halo supervise`), the cards'
  text, the core's notes (`remote/notify.py`: `asks` from the fleet's attention queue, `supervisor` when a goal ends,
  `steward` from the steward's attention notes via `remote/notify_sources.py`; written only while a transport
  listens), `transcribe` (a voice note through the local speech server), `qr_text`, `words`, `service`,
  `service_ask`, `logon_lines`, `fleet_lines`, `capture_studio`, `offline`. `halo remote transports`.
- **A pack command that runs a program** (`run:` in a pack command's frontmatter, `commands/pack_run.py`): kind core,
  no model call, the words as its arguments.
- **`halo pack test` runs a pack's own `tests/test_*.py`** (`packs/test_run_own.py`), one check per module; a Setup
  check whose file a missing requirement gates is a skip line; `halo pack test <id>` finds a pack Halo ships.
- **The signal pack** (`halo_harness/templates/packs/signal/`, off until enabled): the bridge as the service
  `signal/bridge`; `/signal` (status, pair, phones, unpair, reverify, sign, home, off, on, url, test, link, register,
  notices); Setup blocks (Signal on this box, link, a number of its own, a test message, pair a phone, phones, the
  conversation's settings, the service); `requires: signal-cli` (GPL-3.0) with the install line per OS; its README
  (threat model, pairing, signing, chat commands, live verification), HALO-PACK.md, CHANGELOG.md and 13 test modules (with their fakes).
  The conversation: pairing in one six-word text (a QR too), signing optional per phone; a text with no session starts
  one in the phone's home folder (`/cd`, `/new`) and says so first; the session kept across restarts (phones.json);
  the answer paragraph by paragraph, a code block whole, `reply.txt` past four messages, a closing line only after
  tool work, a status line after 20 s of silence; a text that is not a card's answer is held ("... or `send`");
  thumbs up / down answer a card; pictures, PDFs and voice notes in, `/file` and `/shot` out; `/cost`, `/fleet`,
  `/notify on|off <kind>`; one goodbye line when the supervisor stops.
- `tests/test_pack_signal.py` (the shipped pack in a scratch home, a whole conversation over real control sockets
  through the stub transport, the service under the supervisor against the fake signal-cli),
  `tests/test_supervise_services.py` (+ the `service-pack` fixture), `tests/test_remote_notify.py`,
  `tests/test_remote_cards.py`; glossary: `pack service`, `transport`.

#### Changed
- Extension API 1.1 -> 1.2 (`ext.API_VERSION`, `ext.compat.CHANGES["1.2"]`); the `api-too-new` fixture asks for 1.3.
- `remote.enabled` defaults to **true** and is every transport's switch (it was the Signal bridge's, default false).
- `remote/bridge_cards.py` -> `remote/cards.py` (core: the attention queue, the supervisor's asks and every transport
  draw the same text); `remote/daemon_units.py` -> `logon_units.py` (the supervisor's and the host's "at logon"
  files; `JAVA_TOOL_OPTIONS` carried into the supervisor's); the pulse liveness rule -> `remote/proc_ident.pulse_alive`.
- `fleet/push.py`: the attention queue's cards are `asks` notes on the transport seam (no `~/.halo/remote/fleet-push/`);
  the Fleet catalog's `integrations` lists the transports listening.
- `/remote` prints the control socket's status (socket, registry, `remote.enabled`, transports, pack services); the
  remote chip names the transport listening or its stopped service when no phone is attached; `remote/doctor_check.py`
  is the control line plus one row per pack service; `remote/cli_common.py` keeps only the shared CLI helpers;
  `remote/pairing_files.py` keeps only the locked JSON helpers.
- Docs: REMOTE.md (the control socket, the feed, the registry, a new "Transports"; the Signal sections went to the
  pack's README), EXTENSION_API.md ("Services", "Transports", 1.2), SUPERVISE.md ("Pack services"), PACKS.md ("The
  signal pack"), CONFIG.md, COMMANDS-fleet.md, COMMANDS-supervise.md, COMMANDS-packs-kit.md, PACK-AUTHORING.md,
  STUDIO-packs.md, SLASH-COMMANDS-providers.md, HANDBOOK.md, FLEET.md, SECURITY.md, GLOSSARY.md.

#### Removed
- From the core, to the signal pack: `remote/bridge.py`, `bridge_commands.py`, `bridge_session.py`,
  `bridge_outbox.py`, `bridge_state.py`, `signal_calls.py`, `signal_config.py`, `signal_errors.py`,
  `signal_link.py`, `signal_transport.py`, `signal_typing.py`, `pairing.py`, `signing.py`, `audit.py`,
  `ratelimit.py`, `render.py`, `cli_setup.py`, `cli_pair.py`, `cli_link.py`, `cli_run.py`, `dialog_model.py`, and
  the TUI's `tui/dialogs/remote_status.py` and `remote_digits.py` (the `/remote` dialog).
- `halo remote signal setup | register | link | run [--daemon] | pair | peers | unpair | reverify | status | off |
  on`: `halo remote signal ...` prints one line pointing at the pack (`/signal`, Setup -> Signal).
- `remote/signal_install.py`: the pinned, digest-checked signal-cli download (Halo never installs a requirement; the
  pack's `requires:` says how).
- Config keys `remote.signal.enabled`, `remote.rate_per_minute`, `remote.verbosity`, `remote.stale_window_s`,
  `remote.pair_code_ttl_s` -> `packs.settings.signal.on | rate_per_minute | verbosity | stale_window_s | pair_ttl_s`
  (`halo config get|set` of an old key says the new home; Settings -> Remote keeps only `remote.enabled`).
- `~/.halo/remote/{signal.json, signal-cli/, peers.json, pending.json, audit.jsonl, registration-pin, register.json}`
  -> the pack's data folder (moved once by its service; `bridge.json`, `stop`, `fleet-push/` dropped).
- Tests moved into the pack: `test_remote_signal_transport`, `test_remote_signal_io`, `test_remote_signing`,
  `test_remote_render` (its card test stays as `test_remote_cards`), `test_remote_bridge`, `test_remote_bridge_auth`,
  `test_remote_pairing`, `test_remote_peers`, `test_remote_cli_install`, `test_remote_cli_run`,
  `test_remote_cli_signal`, `test_remote_dialog`, `test_remote_dialog_text`, `test_review3_d2`, `test_review3_d2b`,
  `test_review3_d2c`, `test_security_round5b` and the helpers `bridge_rig`, `cli_rig`, `signal_transport_rig`,
  `fake_signal_cli`, `fake_signal_admin`; their Signal pins are the pack's `test_transport_pins` and
  `test_bridge_pins`, the downloader's went with it.

## [3.3.12.0] - 2026-11-08

**Themes and parity.** One theming system, not two. Until now the terminal had two palettes and Studio a dark/light switch
per browser, and the two knew nothing of each other. R1 makes a palette registry of ten -- claude-dark, claude-light, holo,
paper, midnight, ember, forest, slate, dusk, dawn -- in one token vocabulary that both renderers draw from, chosen by one
`theme` key: `/theme`, `halo config set theme`, the header menu and a new Settings -> Themes page all move the same value,
Studio's palette blocks are generated from the registry so a colour lives in one place, and the daltonized variants now mean
something. Next in this version: a pack's own themes (R2), a pack mode's theme with toggle-and-restore (R3, issue #5), the
table panel's detail view and the parity audit (R4).

### R1: one palette set -- ten palettes, one `theme` key, the terminal and Studio in step

#### Added
- The palette registry (`halo_harness/themes/`): ten palettes as data in one token vocabulary (`palettes.py`: bg, bg2, surface, surface2, border, line, text, muted, faint, accent, accent2, accent_ink, ok, warn, bad, user, tool) -- `claude-dark`, `claude-light`, `holo` (Studio's glass, cyan and amber), `paper`, `midnight`, `ember`, `forest`, `slate`, `dusk`, `dawn`, each `{id, label, posture, tokens}`; `registry.py` answers the valid names (the ten x `-daltonized` / `-ansi`), the tokens a name draws in, its posture, and the WCAG contrast of every pinned pair (body text 4.5:1 on every face, a large or UI colour 3:1, a primary button's label 4.5:1); `cli.py` holds the words `/theme` and the refusals say.
- `-daltonized` now means something: the accent pair, the status pair and the terminal's user / tool lines become blue and orange (the Okabe-Ito hues), moved in lightness per palette until they read on its backgrounds -- never red against green.
- Studio from the same source: `scripts/themes_css.py` writes one `:root[data-theme="<name>"]` rule per palette (its id and `-ansi`), one override per `-daltonized` name and the "follow the system" rules between two marker comments of `styles/tokens.css`; the glass, lines, glows, soft fills and scrim derive from the tokens by posture. `--check` reports drift.
- `GET settings/themes` (the ten with their tokens and daltonized tokens, the vocabulary, the modifiers, the saved `theme`); the served index.html carries `data-theme` = the saved theme or `auto` (`studio/theme_boot.py`), so the first paint is in the right palette.
- The header's theme menu (`shell/ThemeMenu.tsx`): Follow the system and the ten, each with a swatch row (surface, text, accent, accent-2, ok, warn, bad), the current one checked, a door to Settings -> Themes; the palette's "Theme: <id>" per palette and "Theme: follow the system".
- Settings -> Themes (`?mode=settings&page=themes`, `halo settings themes`, after General on the rail): the ten rows with their swatches in the colours the API sends, posture and label, the current one marked; Follow the system; pointing at a row previews it on the page, Esc or moving away reverts, a click saves; Daltonized and ANSI as toggles.
- `/theme` with no argument lists the ten with their posture and one-line label, the current one marked; `halo settings themes --terminal` prints the same.
- Glossary: "palette" and "posture". Tests: `tests/test_theme_registry.py` (the ten, the postures, every modifier, daltonized blue / orange, the contrast pins over all thirty names, `resolve_theme` and the removed-theme notice unchanged, `halo config set theme`, the doctor), `tests/test_themes_css_drift.py`, `tests/test_studio_theme_api.py`, the Chrome `tests/test_studio_themes.py` (TIER full), and the TUI pilot `test_slash_theme_lists_the_ten_palettes_and_sets_one`.

#### Changed
- One key for both: `theme` in `~/.halo/config.json` names the palette for the terminal and Studio; the header menu, the palette, Settings -> Themes, Setup's Theme page, `/theme` and `halo config set theme` all write it (Studio through `POST settings/set` / `settings/unset`). Unset, the terminal keeps its truecolor-aware default (`claude-dark` / `claude-dark-ansi`) and Studio follows the system (`holo` dark, `paper` light). Studio's per-browser dark / light switch is gone: a saved `halo.studio.theme` is read once, written to the key when the key is unset (`dark` -> `holo`, `light` -> `claude-light`), then dropped. Studio follows a change made in a terminal at once (`files_changed`); the terminal has no config watch, so a change made in Studio reaches it on `/theme` or its next launch.
- `theme.VALID_THEMES`, the config schema's `theme` enum and the Settings row's choices come from the registry (30 names), never a literal list; an unknown name is one line naming the ten (`/theme`, `halo config set theme`, the settings route, Setup).
- `tui/theme.py variables_for` maps the registry's tokens to Textual's variables; `claude-dark` draws exactly as before; `claude-light`'s ok, warn and tool are a shade darker (`#3b9428`, `#b67418`, `#e45401`) so each reads 3:1 on the page. `holo` is Studio's dark of before, value for value; Studio's light of before is `claude-light` (its `--surface-2` is now the terminal's panel colour, `#dce0e8`).
- Setup's Theme page shows the ten palettes (the modifiers live on Settings -> Themes) and says the key is the terminal's and Studio's; the Settings row is titled "Theme".
- The Chrome drivers start headless Chrome on a dark system (`--blink-settings=preferredColorScheme=0`), so an unset theme draws holo on every runner as before.

### R2: a pack's own themes -- `contributes.themes` registers into the palette registry

#### Added
- `contributes.themes` in `pack.yaml` (`packs/manifest_themes.py`, `schemas/pack_yaml.py`, `pack.schema.json` `$defs.theme`, extension API 1.1, stable): `[{id, label, posture: dark | light, palette: {every token: "#rrggbb"}}]`, checked at install with one line per bad value -- an id that is not `[a-z][a-z0-9-]*`, a core palette's id, an id ending in a modifier, an id used twice, a label left out, a posture outside the two, a missing or an extra token, a value that is not `#rrggbb`, and every pinned pair under its WCAG AA floor (the palette's own and its `-daltonized` variant's) with its ratio.
- A pack palette is a theme like the ten while its pack is enabled, named `<pack-id>/<id>` (`pack-theme/nightshade`) with the `-daltonized` and `-ansi` modifiers derived the same way: `/theme` lists it under the pack's name and draws the terminal in it at once, `halo config set theme`, Setup and the settings route take it, and `halo doctor --config` knows it.
- Studio: `GET settings/themes` lists the enabled packs' palettes after the ten with `pack`, `pack_name`, their tokens and the CSS variables they are drawn in; the header's theme menu, Settings -> Themes and the palette show them in a group under the pack's id with the same swatches, hover preview and Daltonized toggle; `lib/theme.ts` sets a pack palette's variables on `<html>` while it is drawn (the generated `tokens.css` blocks stay the ten's); the served page inlines a saved pack palette's variables as one `<style id="halo-pack-theme">` rule the CSP allows by its sha256, so the first frame is already in it.
- The restore record: choosing a pack palette through any door keeps the theme saved before it in `~/.halo/packs/.data/<id>/theme.json` (`themes/restore.py`); `halo pack disable` and `halo pack remove` (and the Pack Manager's buttons) write it back while the pack's palette is the saved `theme`, or unset the key when there was none, and say so in one line (`theme: pack-theme/linen was pack-theme's palette and the pack is disabled; restored claude-dark`).
- The fixture pack `tests/fixtures/packs/pack-theme/` (`nightshade` dark, `linen` light, AA-clean); EXTENSION_API.md "Themes" (the shape, the tokens, the contrast rule, the naming, the restore rule), the status row and `ext.compat.CHANGES["1.1"]`; glossary "pack palette". Tests: `tests/test_pack_themes_manifest.py`, `tests/test_pack_themes_lifecycle.py`, the pack cases of `tests/test_theme_registry.py` and `tests/test_studio_theme_api.py`, and the Chrome pack step of `tests/test_studio_themes.py` (the menu and the page under "pack-theme", the computed accent, the first paint with the page's scripts off, the restore on disable).

#### Changed
- The registry is live: `themes/registry.py` reads the enabled packs' palettes at call time (`themes/packs.py`, cached on the packs registry's own snapshot, so no watcher) and gains `register` / `unregister`, `pack_ids`, `all_ids`; `theme.VALID_THEMES` is now a live view (`registry.LiveNames`) instead of a frozenset built at import, and the Settings row's choices are the same view; `ids()` is still the ten.
- `theme.persist_theme` is the one door every writer of `theme` goes through (`halo config set theme`, the settings route and Setup's route used to write the key directly), so the restore record is kept whichever door chose the palette; unsetting the key clears it.
- A saved `theme` naming a pack palette whose pack is not enabled reads like a removed game theme: one line at the terminal's start and in `halo doctor --config` (a `warns` row, no longer an unknown value), the default drawn, Studio following the system.
- Studio's palette derivation (`studio_vars`, `accent_vars`) moved from `scripts/themes_css.py` to `halo_harness/themes/studio_css.py` so the server can run it; the script imports it and `tokens.css` is byte for byte as before.

### R4: the pack kit -- `halo pack new`, `halo pack test`, an editable install, the authoring guide

#### Added
- `halo pack new <id> [--kinds ...] [--all] [--dir] [--name] [--description] [--author] [--github | --no-github] [--license SPDX]` (`packs/cli_new.py`, `packs/scaffold/`, the templates in `halo_harness/templates/pack-kit/`): a pack folder that `halo pack inspect` reads clean, that installs and enables with every grant, that `halo pack doctor` finds nothing wrong with and that `halo pack test` passes. One working example per kind: `agents` (two bios with every section a bio has: a local model asked for by `models.capabilities: [local, tools]` with the owner's default model as the cloud fallback, the tools allow-list, a skill, the memory namespace, the system prompt, the "Pick me to ..." line Auto reads), `teams` (two roles, two tiers, acceptance), `skills` (two), `commands`, `hooks` (a PostToolUse hook appending to the data folder), `mcp` (a stdio server with one tool), `events` and `artifacts` (a schema and a sample each), `workflows` (two stages, both roles, ending in the artifact), `studio` (a markdown panel, a table over `data:rows.json`, a bundle panel using the `api`), `bundle` (a `bundle:` block), `fleet`, `policy` (a guard that denies a write under `.git/` while its mode is on), `modes`, `setup` (a form, a check, a note), `themes` (a full AA-clean palette; written once this Halo reads `contributes.themes`, R2) and `integration` (ripgrep wrapped: `requires:`, a command, an MCP server, a hook). Always: `pack.yaml`, `.claude-plugin/plugin.json`, the entry command `commands/<id>.md`, a README written from the manifest, `HALO-PACK.md` (the contract, the loop, the rules a Halo session follows in the folder), `CHANGELOG.md`, `tests/pack_test.py`; with `--github` (the default) `LICENSE`, `.gitignore` and `.github/workflows/pack-test.yml` (`halo pack test .` on Ubuntu and Windows against Halo installed at this release's tag).
- `halo pack test <folder | id> [--kinds] [--timeout] [--verbose] [--json]` (`packs/cli_test.py`, `packs/test_run.py`, `test_run_parts.py`, `test_run_proc.py`, `test_run_mcp.py`): in a scratch home and project of its own, never a model call, never the network -- the manifest, an install with every grant and the doctor on that copy, each bio and lineup loads, each skill and command parses, the entry command runs in a fake session and lists the pack's parts, each hook runs once with a sample event of its matcher, each MCP server answers `initialize` and `tools/list` and stops (a silent one is the timeout line), each event and artifact schema takes its sample, each workflow compiles, each Studio panel's source is there and a bundle module exports `mount`, each policy answers in shape, each mode turns on and off, each Setup check runs green, each theme's contrast pins, the bundle block against a fake card, each requirement. One line per failure (`<file>: <what> -- <fix>`), a skip line for what needs the network, a model or a program not here, `RESULT: N checks, N passed, N failed`, exit 0 / 1.
- `halo_harness.ext.testing` (stable, API 1.1): `run(folder)` (the same checks; `Report.add` for a pack's own), `manifest(folder)`, `ask_policy(folder, policy, tool, input)`.
- `halo pack install <folder> --link [--project]` (`packs/link.py`): the installed pack is the folder itself, read in place through `<id>.link` (journal op `link`); an edit shows at the next read; `halo pack unlink` (= `remove`) takes the link away and leaves the folder (journal op `unlink`); update and rollback say there is nothing to do.
- `requires:` tool entries (`packs/manifest_requires.py`, extension API 1.1 "Requirements", stable): `{kind: command | python | npm | git, name, version, install: {windows, linux, mac}, url, license, why, used_by}` beside the `{pack, version}` entries; one line per bad value. Halo never installs one: `halo pack doctor`'s `missing-requirement` warns row with the install line for this OS, `halo pack test` skips what it gates, the Pack Manager's row carries `needs` ("needs rg").
- The entry command: a pack's `commands/<id>.md` is also `/<id>` (when no other command has the name), beside `/<id>:<id>`.
- The shipped `pack-author` lineup (`templates/teams/pack-author.yaml`) with the `pack-author` (the one-page contract and the loop), `pack-researcher` (finds and evaluates open-source tools to wrap, writes the evaluation into the README) and `pack-reviewer` bios: `halo --team pack-author` in a kit folder.
- docs/PACK-AUTHORING.md (start, the kinds, expansion packs, the loop, testing, Studio, the fleet, themes, wrapping an open-source tool, local-first packs, publishing, the checklist), docs/COMMANDS-packs-kit.md; glossary `pack kit`, `requirement`, `entry command`. Tests: `tests/test_pack_new.py`, `tests/test_pack_test.py`, `tests/test_pack_link.py`, `tests/test_pack_author_team.py`.

#### Changed
- docs/EXTENSION_API.md opens with "Start here" (the kit); the status table gains Requirements; `ext.testing` joins the stable surface and `ext.compat.CHANGES["1.1"]` lists it and the tool entries. PACKS.md "Yours first" points at the kit; COMMANDS.md's parts table gains the kit's page.
- Eight lineups ship (`pack-author` joins); `halo pack inspect` shows a tool requirement as `<name> <version> (<kind>)`.
- `halo pack doctor` adds the `missing-requirement` row for a running pack; a pack without tool entries is untouched, and every existing pack and fixture reads and runs as before.
