# Halo 2.0.5 round 4: team control (the lineup sections enforced, agent hooks, schedule and triggers)

Repo: `<repo>` (branch master; start from HEAD after round 3). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test
environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies: one worker, touched modules
plus `python test_bridge.py`, no full suites.

Specification: `plans/ROADMAP.md` sections "ADDED 2026-10-05 ~22:45 (rolo):
agent declaration files (YAML) behind roles and orgs" (the line "Deferred to
2.0.5 with the Governor: `hooks` (pre/post tool commands) and
`schedule`/`triggers`") and "ADDED 2026-10-06 ~00:40 (rolo): a team template
is a lineup of many assignments" (the line "gates enforced by the 2.0.5
Governor"); `docs/AGENTS.md` paragraph "Every OTHER top section, also
stored/validated/shown but not enforced by the live agent loop this round
(the Governor's own job, 2.0.5)". Round 3 shipped the Governor; this round
makes the stored sections real.

## Where the code is

`halo_harness/agents_yaml.py` (bio schema and loader), `teams_yaml.py`
(template schema: `TOP_SECTIONS`, `GATE_KINDS`, the shape validators),
`agents_cli.py`, `teams_cli.py`, `agents_doctor.py`, `agents_md_bridge.py`,
the shipped files under `halo_harness/templates/agents/` and
`templates/teams/` (incl. `halo-dev-cycle.yaml`), the sub-agent runner and
the delegation path in `agent/` (where `Agent`/sub-agent spawns resolve a
role to a model and tools), the Governor from round 3 (`providers/
governor.py`, priorities and budgets), `hooks` as Claude Code defines them
in the existing settings reader (Halo already runs the user's Claude Code
hooks; reuse that runner), the scheduler surface that exists for cron-like
jobs (if none, `bg_run.py` is the base), `docs/AGENTS.md`, `docs/TEAMS.md`
(or the teams section of AGENTS.md), `docs/CONFIG.md`.

## Deliverables

1. **Lineup sections enforced in the live loop.** When a session runs under
   a team (`team:` config key or `--team`): `delegation` (mode, `max_parallel`
   via the Governor's in-flight cap per team, `max_depth`, `handoff` shape,
   `forward_text`), `routing` (task kind -> role or alias, with `default`),
   `budget` (`max_budget_usd`, `max_total_turns`, `max_wall_time`,
   `agents_may_exceed`: when exhausted the team stops delegating and says so
   in one line; never a refusal, a stop with the reason), `escalation`
   (`triggers` tool_failures / context_overflow / budget_exhausted -> `to`
   model, `ask` true shows the existing escalation approval card, false
   switches and announces), `context` (files and skills loaded for every
   member; `memory.namespace` and `writers`), `permissions` (mode, rules,
   offline applied to every member on top of the bio's own), `org`
   (`reports_to` governs who receives a member's hand-back; `reporting`
   cadence and format drive the one-line reports), `pipeline` (stages run
   in order; a `required` gate must pass its stage's acceptance before the
   next stage starts, `optional` records and continues).
2. **Agent `hooks`**: `hooks: {pre_tool: [...], post_tool: [...], on_start:
   [...], on_finish: [...]}` in a bio, each entry `{command, match?,
   timeout?}` in Claude Code's hook shape, run by the existing hook runner
   with the agent's name in the environment (`HALO_AGENT`), output shown in
   the transcript as hook output is today; a template may add hooks per
   assignment (`overrides.hooks`).
3. **`schedule` and `triggers`**: `schedule: {cron: "<5 fields>", prompt:
   ..., model?: ...}` or `{every: 30m, ...}` on a bio starts the agent as a
   background job on that cadence while a session that loaded the team is
   alive (never a system service); `triggers: [{on: file_change, paths:
   [...]}, {on: event, name: <halo event>}, {on: message, from: <role>}]`
   start it on the event. `halo agents schedule list|run <name>` and
   `/agents schedule` show what is armed and the next fire time.
4. **Validation and doctor**: the loaders validate the new sections with one
   plain line per problem; `halo doctor --teams` exercises one `required`
   gate on the fixture lineup; `halo teams show` prints the enforcement
   state per section (enforced / stored only, with the reason).
5. **Docs and CHANGELOG**: docs/AGENTS.md (drop the "not enforced" paragraph,
   document each section's runtime behaviour, hooks, schedule, triggers),
   docs/CONFIG.md, docs/COMMANDS.md and docs/SLASH-COMMANDS.md entries,
   CHANGELOG `[2.0.5]` "### Team control".

## Tests (hermetic)

A fixture lineup with two bios and a fake model: routing sends an
`implement` task to the worker alias and a `review` task to the reviewer;
`max_parallel` holds the third spawn until one finishes; `max_depth`
refuses a nested delegation with the one-line notice; budget exhaustion
stops delegation with the reason; each escalation trigger switches (and
with `ask: true` shows the card); a `required` gate blocks the next stage
until its acceptance passes and an `optional` one records and continues;
hooks run with `HALO_AGENT` set and their output lands in the transcript;
a schedule with `every: 1s` fires twice in the test and stops when the
session closes; each trigger kind fires once; the validators' lines. No
network, no real model, nothing written outside the scratch home.

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere: a budget or gate
  stops with its reason, it never judges the request.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file; `halo audit privacy` exit 0; privacy scan and invariants
  green.
- No network in tests; never read the owner's key files.
- No new hard dependency (pyyaml is already in). House size conventions
  (`teams_runtime.py` and `agents_schedule.py` are the expected new
  modules; `teams_yaml.py` stays a schema module).
- Never block the UI thread: schedules and triggers run as background jobs
  through the existing job surface (`bg jobs` in the status bar).

## Verification before hand-back

Touched and new test modules, `python test_bridge.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python tests/test_docs_commands.py`, `python tests/test_docs_slash_commands.py`,
`python -m halo_harness audit privacy`, all green. Record
`stat -c %s ~/.halo/history.jsonl` and `ls ~/.halo/sessions | wc -l` at the
start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-5: DONE / PARTIAL / ALREADY COVERED with
evidence and the pinning test names), FILES TOUCHED, WHAT YOU FOUND (which
sections the loop already honoured, anything left open and why, the manual
check for the owner: `halo --team halo-dev-cycle` with one `required` gate
and one scheduled watchdog). No commit, no push.
