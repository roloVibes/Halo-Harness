# Handoff: continuing Halo Harness from a cold session

This folder carries the whole plan so a new session (local or cloud) can
pick the work up without the conversation that produced it. Read this file
first, then `WORKER-RULES.md`, then the round you are starting.

## WHERE THINGS STAND -- 2026-10-09 ~01:30 CDT (authoritative, read this first)

**The vibes/review.md fix pass (the owner's own 92-finding whole-tree
review of 2.0.7, at `<review file>` (the owner keeps it outside the repo)) is five
rounds in, all pushed to master: `c858334` (R1 crash+providers), `2a05160`
(R5 credentials + R6 data loss + R7 MCP + R2 TUI crashes), `25a615a`
(R8 deny-rule integrity), `f2aaad4` (R9/R10 slice + pyflakes CI gate).**
~55 of 92 findings fixed. Test files: `tests/test_review2_round1..5.py`.
CRITICAL CONTRACT (standing order, encoded in test_review2_round4): deny
rules must hold in every mode; auto mode with NO rules must stay allow --
the review's classifier-shaped suggestions (env-var allowlists #3,
allow-match substitution refusal #4, blanket `<<<` rejection, #6's
heuristic pile) are REJECTED, never re-add them.

**REMAINING from the review, in rough priority order (read the review
file for each finding's detail):**
- 43-45 (MCP: HTTP/SSE + ws connectors carry creds/streams through
  `connectors.py`), 46 (TCP preflight ignores HTTP(S)_PROXY,
  `mcp/http_sse.py:243-287`), 47 (timed-out plugin clone cached valid
  forever + no `--` separator, `plugin_fetch.py:82-104`)
- 49-53 (loop scheduling: read-only batch runs after Agent call; the 30s
  read-only cap ignoring the model's own timeout; typed-during-/compact
  loss; `tool_choice=required` overflow sentinel AttributeError;
  Esc-queued batch + waiter-slot leaks, `loop.py:7174-7343`)
- 54-58/60-62/64 (sub-agents/roles: concurrent-resume TOCTOU; cc: Stop
  hook continuation unread; task_id resume drops role/model/effort;
  team max_parallel overridden; role table never recomputed; team role
  names rejected; tools:Agent(X) unenforced; export snake_case keys;
  worktree leak on failed model resolve, `subagent.py`)
- 33/38-40 (provider tail: escalation set_model half-switch; xp:
  count_tokens; proxy cred scopes; non-JSON 200 handling)
- 67-75 (TUI: xclip DEVNULL; slash drops image attachments; shadow
  snapshots on the UI thread; roles-editor ctrl+s; card race; recalled
  paste placeholder; image-chip delete; invalid YAML silently kept;
  auto-title/stream-json state resets)
- 76-78/80/82-83 (CLI/doctor: -p -c silent new session; providers setup
  argparse; doctor --json prints text first; PATH check reads own env;
  --fork + --no-session-persistence leak; -w before validation)
- 84-92 (telemetry/stats: sub-agent costs on the parent row; stats cache
  schema; replay kinds; bg PID-reuse on macOS; recall temp file +
  cross-project prune; U+2028/9 line splits; gym nodigest; bg -p stdin;
  shared-state file locks, `launch_state.py`/`update.py`/`history.py`)
- P2 tail: ollama `_get_json` HTTPException; http.py non-final-404
  connection leak + bad-route caching; oai_stream cache-write pricing;
  mcp/oauth single-request callback; mcp_cli one project-key form;
  gym_tool_tasks docstring
- The review's own #299 suggestion 1 (permission bypass test file) is
  DONE as test_review2_round4; suggestion 2 (pyflakes CI) DONE in
  .github/workflows/suites.yml.

**Known flakes (this box, not CI):** test_h5c_f07 under full battery;
test_agents_schedule's `every_1s` disarm timing check (passes on re-run);
test_privacy_scan's key-shaped-fragment check fails on clean HEAD too.

**Before any tag:** the full battery (test_bridge + tests/run_all +
test_tui) -- NOT yet run since these five rounds; the release itself
release.py needs CHANGELOG "unreleased" + a clean tree.

After the remaining findings: the 2.0.7.1 (or 2.0.8) release, then the
2.0.8 theme pack (DOOM/Metroid/Mario) per ROADMAP.md.

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-08 ~23:30 CDT (previous)

**v2.0.7 IS RELEASED** (tag `2c9af54`/v2.0.7, GitHub release published,
--no-install: the owner is refreshing installs himself). Everything in
2.0.7 shipped: rounds 0b (status notices), 0c (steer-through-tool-calls),
Pillar 1 (filter-aware routing), Pillar 2 (preflight + canaries), 0e
(concierge + media agent), local embeddings + /recall + the generic
`local:` route, the wizard deep review (roles surface), the copy-out fix
(selected-range copies + mechanism confirmation + the tmux/Kali OSC-52
fix), dead-model-id detection + surfaced 404 handbacks + balances
remaining-first, `halo local warm` + the single-GPU swap warning, the
external-review fix pass (13 findings), and paste reliability (bare
/paste reads the clipboard directly). Known-flake: test_h5c_f07 fails
only under full-battery load on THIS box (passes standalone, green on
every CI run). NEXT when resumed: 2.0.8 theme pack (DOOM/Metroid/Mario)
per ROADMAP.md.

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-08 04:45 CDT (previous)

**v2.0.6.1 IS RELEASED** (tag `5e025ad`, signed assets on GitHub, VM on it,
Windows installs it on the session-exit watcher -- the owner is restarting
RIGHT NOW to pick it up). 2.0.7 is open, unreleased, tree clean at `master`.

**2.0.7 running list (ROADMAP.md tail sections are the detail authority):**
- DONE 0a: steer text renders at submit, apply-time duplicate suppressed
  (`03d54e7`).
- DONE 0d: Ctrl+Alt+V pastes images when the terminal eats Ctrl+V (`3a5e4f2`).
- DESIGNED 0e: concierge role = glm-5.3-flash (vision=True, $0.50/M out vs
  main glm-5.3 vision=False $7.00/M -- measured live, see ROADMAP 2026-10-08
  section); ONE media agent (ffmpeg frames / whisper transcript / paste all
  converge on image-or-text), capability routing off ModelProfile.vision.
- NEXT **0b: notices stop impersonating the user.** `_apply_pending_job_notices`
  / `_apply_pending_agent_notices` (agent/loop.py ~6530) deliver background
  job/sub-agent completions as USER-role messages merged into the owner's next
  turn -- the model reads status interleaved with the human's question and
  answers the status first (rolo: "typing a question, getting a blob back of
  what's been done, then an answer is not a good flow"). Fix: deliver as
  clearly-marked system-framed status blocks placed AFTER the human's message,
  framed "answer the human first, fold status in only where relevant". Print
  mode keeps current behavior. Tests: tests/test_parallel_round.py,
  test_acceptance_round.py touch notice paths.
- THEN 0c: steer-through-tool-calls (forward steers into running sub-agents;
  children already share the parent's abort Event -- H6 scope B, subagent.py).
- THEN the cyber pillars (rolo 2026-10-07: "put those at the head", restrictor
  plates off, NO fleet): 1. filter-aware routing (Pillar 1.1-1.3), 2. preflight
  + canaries (Pillar 2). THEN 3. embeddings, 4. wizard deep review + concierge
  template (same surface), 5. copy-out fix, 6. dead-model-id detection,
  7. balances-remaining ($145 shown "used" but owner wants remaining via
  OpenRouter /credits total_credits-total_usage).

**Conventions that matter:** 250-line write cap, comment-dense house style,
every round = tests + changelog entry + commit + push, run suites via
`python -m tests.test_<name>` (NOT pytest), full gate scripts at
appDev/halo-harness-runners, Windows gates run ONE AT A TIME (bash.exe WFSO
fork failures under parallel load), release via scripts/release.py
(CHANGELOG section must say "unreleased" -- the script stamps the date; the
local install step needs --no-install while a session holds halo.exe).
Owner live-reports are gold: diagnose in THIS session's style (find the real
mechanism, fix at the choke point, pilot-verify, document in the changelog).

---

## Where things stand (2026-10-02)

Halo Harness 2.0.1 is seven parts in on `master`, every part verified on
Windows and a Kali Linux VM and pushed:

| Part | Commit | What landed |
|---|---|---|
| 1 | 1165cca | run from any directory, launch without the auth hang, one executable |
| 2 | ca60e27 | GLM on Databricks effort sets, effort as sent, steer-restart, TTFT telemetry |
| 3 | 914ca04 | visible thinking phase line, live status counters, rotating tips |
| 4 | e326d04 | Up-arrow recall fixed, copy and paste in the chat box |
| 5 | cc7c9a7 | pending-card dock, `halo bugreport`, per-turn timeline, remembered model and effort |
| 6 | 5df3502 | credential resolution consistency, lint clean, timeline complete, steadier tests |
| 7 | ef4351b | MCP explains itself, claude.ai connectors bridge, `mcp serve`, generic `mcp login` |
| docs | 94dcb3f | README redo, `docs/HANDBOOK.md` |

Everything else in `2.0.1-gap-list.md` and `2.0.1-w4-plan.md` is still
open. The remaining 2.0.1 rounds, in order:

1. **W4a** (`2.0.1-w4-plan.md`, section "W4a"): the 17 hook events, the 21
   flags plus the 7 declared not applicable, skills in sub-agents,
   sub-agent asks through the dock, `/rewind` for created files and Bash
   changes, the misc items.
2. **W5** (`2.0.1-gap-list.md`, section "W5: coverage gaps"), plus the two
   items carried at the end of `2.0.1-w4-plan.md` (Linux test determinism
   for `tests/test_cc_session.py`; connector cold start in print mode).
3. **Release** (`2.0.1-gap-list.md`, section "Release"): review, fix pass,
   CHANGELOG tidy, tag `v2.0.1`, push. The Kali live checks need a machine
   with a real `claude` login; a cloud session cannot do them, so leave a
   note in the PR for the owner to run them.

After 2.0.1: `ROADMAP.md` (see its RENUMBERED section) lists 2.0.2 through 2.0.9 with their briefs here; 2.0.2 is `2.0.2-brief.md` (roles v2, organizations, sub-agent scale, MCP repair, Qwen, terminal title).

## How to work from a cold session

- Base yourself on the current `master`. Work on a branch named
  `wip/<round>` (for example `wip/w4a`), commit there, push the branch and
  open a pull request; the owner verifies on Windows and the Kali VM and
  merges. Do not push to `master` directly from a cloud session.
- Commit as the repository owner's noreply identity and end every commit
  message with the line `Co-Authored-By: Claude <noreply@anthropic.com>`
  for the model that wrote it. Never add a session link line.
- Verification before a hand-back is the three hermetic suites from the
  repo root, all green, with both guard lines reading `ok`:
  `python test_bridge.py`, `python tests/run_all.py`, `python test_tui.py`.
  Install first with `pip install -e ".[dev]"` (or `uv pip install -e .`).
  The suites need no credentials and no network beyond PyPI.
- `WORKER-RULES.md` has the standing rules: writes of at most 250 lines, no
  safety or refusal wording anywhere, never read Claude Code's credentials
  file, never write `~/.claude.json` or `~/.claude/settings.json`, every
  test scopes its home, the Databricks host in the repo is always the
  placeholder `your-workspace.cloud.databricks.com`.
- Paths in the briefs that read `<repo>`, `plans/`, `<kali-vm>` or `~` were
  the owner's machine paths; in a cloud session the repo root is the
  checkout and `plans/` is this folder.

## Files here

| File | Purpose |
|---|---|
| `WORKER-RULES.md` | standing rules, verification recipe, hand-back format |
| `ROADMAP.md` | every version and which brief covers each; its RENUMBERED and REORDERED sections are the authority for the order |
| `2.0.1-gap-list.md` | the complete 2.0.1 list: W3 and W4 sections, MCP additions, W5 coverage, release steps |
| `2.0.1-glm.md`, `2.0.1-liveness-tips.md`, `2.0.1-w2c-history-clipboard.md`, `2.0.1-w3-plan.md` | rounds already shipped (reference) |
| `2.0.1-w4-plan.md` | W4a (open) and W4b (shipped), plus carried items |
| `2.0.2-brief.md` | 2.0.2: roles v2, organizations, sub-agent visibility and scale, MCP repair, Qwen tool calling, terminal title |
| `2.0.3-brief.md`, `2.0.3-jev.md`, `2.0.3-research.md` | now 2.0.4: picker columns, balances, enumeration, Codex and OpenAI, jev, learned rules, cc: v2, legacy env-file drop |
| `2.0.4-brief.md` | now 2.0.5: model gym, soak test and watchdog, CI, invariants |
| `2.0.5-ollama-brief.md` | now 2.0.3 (moved ahead 2026-10-03): local and LAN Ollama models |
| `2.0.8-signal-brief.md` | 2.0.8: remote control of sessions from Signal |
| `2.0.9-review-privacy-brief.md` | 2.0.9: deep code review feature and the privacy/secret audit of repo and history |

## RESUMED 2026-10-06 ~09:40 (owner bought API credits)

The partial work of the two stopped workers was in `git stash` as
`stash@{0}` "wip: round 4 Governor + 4b cc Linux steer, partial" -- **the
stash is GONE (dropped sometime before ~19:00 2026-10-06; round 4b was
re-shipped clean as 9ec1fdd, and round 4's Governor restarts from the
brief, not the stash)**. Order now: round 2b SHIPPED 9d8eb5a -> round 2c
SHIPPED 97d8c87 -> round 4b SHIPPED 9ec1fdd -> round 2d SHIPPED c23e5de
(the old name off the front pages + banner + the README gallery, 2026-10-06
~21:05) -> round 4 (Governor, restart clean from the brief) -> round 5 ->
review -> tag.

## STOPPED 2026-10-06 ~09:10 at the owner's request (token budget 99%)

Both in-flight workers were stopped mid-round. Their partial work (now in
the stash above) was, nothing committed after 98fe38b:
- Round 4 (Governor): `providers/governor.py`, `governor_state.py`,
  `gateway_routing.py`, `lanes.py` (new); edits to `providers/http.py`,
  `providers/stream.py`, `agent/loop.py`, `agent/subagent.py`, `roles.py`,
  `teams_yaml.py`, `tests/helpers/runner.py`; new `tests/test_governor*.py`,
  `test_lanes.py`, `test_gateway_routing.py`. Unknown how far along: run
  its tests, read its brief, and either finish with one worker ("the tree
  already contains ..., finish, do not restart") or `git stash` it and
  restart the round clean.
- Round 4b (cc: steer on Linux): any changes under `agent/cc_control.py`,
  `cc_runtime.py`, `cc_process.py`, `tests/helpers/fake_claude_cc.py`,
  `tests/test_cc_session.py`. Verify under WSL (command in the section
  below) and on Windows before committing. Until it lands, CI Linux stays
  red on three cc: tests; everything else was green on 84eb849.
Pick up with the section below, starting at "How to pick it back up".

## Resume point 2026-10-06 ~06:40 (read this first; written as the budget ran out)

### Where things stand

- Released and installed on both boxes: v2.0.3, v2.0.3.1, **v2.0.4
  (2026-10-06, release commit b081db8, tag v2.0.4)**. History rewritten
  2026-10-05 (all hashes changed; old-history backup beside the repo on the
  build host). v2.0.4 shipped on four green gates (owner's Linux VM suites,
  build-host live check, CI Linux, CI Windows); its code review is DEFERRED
  into the 2.0.5 review (budget), which covers `04ae6e4..<2.0.5 head>`.
- 2.0.5 control pack, briefs in `plans/briefs/2.0.5/`, order in STATUS.md:
  **round 1 `cc:` route v2 SHIPPED (38852a2)**; CI fix for a literal
  version pin (6d91bc8, see CYCLE.md); **round 2 wizard: agent bios and
  lineups SHIPPED (924bad0)**; **round 3 learned gateway rules + the legacy
  env-file drop SHIPPED (2886397)**; **round 4 the Governor IN FLIGHT** when
  this was written (one worker on the build host, started ~07:40; expected
  files: new `providers/governor.py`, `providers/governor_state.py`,
  `providers/gateway_routing.py`, edits to `providers/http.py`,
  `agent/loop.py` (retry ownership), `roles.py` / `teams_yaml.py` (lanes
  validator), the status bar, a `gov` CLI and `/gov`, `doctor.py`, new
  `docs/GOVERNOR.md`, tests under `tests/test_governor*.py`). **Round 4b
  IN FLIGHT in parallel** (an exception to one-worker-at-a-time, files
  disjoint): the round-1 `cc:` steer path fails on Linux only
  (`tests/test_cc_session.py`: steer not sent or logged after a 3 s
  control-response wait; the POSIX close test finds the bridge socket
  left behind); reproduced on the owner's Linux VM at 5e57931; fix worker
  owns only `agent/cc_control.py`, `cc_runtime.py`, `cc_process.py`,
  `tests/helpers/fake_claude_cc.py`, `tests/test_cc_session.py`; Linux
  reproduction runs under WSL against the live tree (WSL python has the
  dependencies). CI fixes already pushed as 84eb849 (changelog-entry
  tests anchor on the section header, catalog age never negative, the
  compose-time test separates a slow runner from a blocking check).
  Round 5 not started. Round 2 left one wiring for round 4:
  `teams_yaml.member_system_context_addition` (the lineup's `about:` text
  as "How this team works") is built and unit-tested but not yet called
  from the live sub-agent session builder.
- The repeatable cycle (brief -> one worker -> verify -> commit -> CI ->
  live check -> release script) is `plans/CYCLE.md`; every brief is under
  `plans/briefs/`, sanitized (`<repo>`, `<scratchpad>`, `<you>`,
  `<user@host>`, `<key>` stand for machine-specific values that live only
  in the orchestrator's own notes, never in this repo).

### How to pick it back up, step by step

1. `git status --short`. A dirty tree with the in-flight round's files
   above is that worker's work in progress, not damage. Run the brief's
   verification list (`python tests/test_<touched>.py` for each touched
   test module, `python test_bridge.py`, `python tests/test_privacy_scan.py`,
   `python tests/test_invariants.py`, `python tests/test_docs_commands.py`,
   `python tests/test_docs_slash_commands.py`, `python -m halo_harness audit
   privacy`, all with `BRIDGE_TEST_HOME=<fresh dir>`,
   `BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
   If green and the deliverables of the in-flight round's brief are
   present, commit it as one round commit (`feat(<area>): 2.0.5 round N --
   <title>`) and push. If not, start ONE worker with that brief plus the
   sentence "the tree already contains <files>; finish the deliverables
   from there, do not restart".
2. Check CI for the last pushes (`.github/workflows/suites.yml`, Linux +
   Windows): red means diagnose environment versus product first; the
   known shapes are in CYCLE.md and the 2.0.4 log in STATUS.md.
3. Rounds 3, 4, 5 in order, each: brief -> one worker -> verify (step 1's
   list) -> one commit -> push -> tick STATUS.md -> next. Round 4 (the
   Governor) is the largest; its brief points at the vendored kit and
   REVIEW.md. Round 5 depends on round 4.
4. Review covering 2.0.4 and 2.0.5 (`git diff 04ae6e4..HEAD`): one
   reviewer agent (Opus when the budget allows, Sonnet otherwise) with the
   WORKER-RULES hard constraints as its checklist; criticals and majors
   fixed in a fix-pass commit; minors listed for 2.0.6.
5. Pre-tag gates: CI green on the candidate; the three suites on the
   owner's Linux VM (the runner scripts live beside the repo on the build
   host, see the orchestrator's notes; they need the VM venv with pyyaml);
   ONE live check on real keys (the 2.0.4 live-check script pattern) that
   also runs the `cc:` real-binary interop check from
   `docs/harness/CC-CONTROL-CHANNEL.md` (steer cuts the reply, `/model
   cc:<alias>` without a restart, `/compact` shows a summary) and then
   widens `providers/cc_tested.json` `max` to the installed version.
6. Release: `python scripts/release.py 2.0.5 --remote <user@host>
   --identity <key>` (dry-run first); tick STATUS.md and this file; both
   installs print the version.
7. Then 2.0.6 hardening (ROADMAP "REORDERED 2026-10-05" + the carried
   items: `2.0.3-release-notes-for-fix-pass.md` minors, Try it / smoke runs
   and export-import bundles from the round-2 deferrals, lane warnings and
   the lineup cost estimate if round 5 did not land them), 2.0.7
   embeddings, 2.0.8 themes, 2.0.9 Signal, 2.0.10 review. 3.0.1.1 stays
   parked.

### Facts a resumer needs

- Installed claude on the build host is 2.1.291, above `cc_tested.json`'s
  max (2.1.284): widen only after step 5's interop check passes.
- By design, not bugs: `set_permission_mode` is implemented and tested but
  never invoked (the `cc:` child stays in bypass so Halo's rules govern);
  native `--resume` history for a mid-session switch into `cc:` is not
  done (it would mean writing Claude Code's own session files).
- The release bumps the version AFTER the suites run: no test may pin the
  version literal (invariant (g); the version check derives it from the
  newest dated CHANGELOG section). `## [2.0.5] - unreleased` is open at
  the top of the CHANGELOG; the release script dates it.
- The remote refresh runs ssh non-interactively: always pass `--identity`.
- Plans-only pushes do not run CI (paths-ignore); a push that mixes code
  and plans runs it at the head commit.
- The coding-flow lineup and its bios ship in the repo:
  `halo_harness/templates/teams/halo-dev-cycle.yaml` and
  `halo_harness/templates/agents/{orchestrator,implementer,verifier,
  reviewer,researcher,release-manager,watchdog}.yaml`; user copies go to
  `~/.halo/teams/` and `~/.halo/agents/` (project: `.halo/teams/`,
  `.halo/agents/`) and win over the shipped files.
- Budget: the owner's token allowance renews Friday 2026-10-09; until then
  CYCLE.md "Budget discipline" (no per-round VM runs, one live check per
  round at most, status posts only when asked, one worker at a time).
