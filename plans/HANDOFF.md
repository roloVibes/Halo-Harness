# Handoff: continuing Halo Harness from a cold session

This folder carries the whole plan so a new session (local or cloud) can
pick the work up without the conversation that produced it. Read this file
first, then `WORKER-RULES.md`, then the round you are starting.

## WHERE THINGS STAND -- 2026-10-15 ~04:10 CDT (authoritative, read this first)

**3.0.5.0 "FLEET" IS RELEASED** (tag v3.0.5.0 at 2b0a9f7 on master, GitHub
release published, local install `halo 3.0.5.0`), cut on CI run 38688763766
read as `conclusion == success` for sha 0af8fde. Between the merge and the
tag, four test-only fixes: `test_review3_d1` item28 follows R1's `_actives`
list; the HubRig reads B's relay to ITS hub and starts `relay_runtime` from
nothing (a leaked session's watcher re-created a relay for a dead hub and the
kick test read that one: full suite only, Windows); `test_review_run`'s
parallel check trusts the gate's peak with the clock as a sanity cap;
`test_review_tui` reads "both rows listed, one running" from one snapshot
(mock reviewers 3 s). Worktree `hh-fleet/R4-panels` removed; the `fleet/*`
branches are merged and may be deleted. The owner's LIVE CHECK is still to
do (below). Pre-release history of the round follows.

**3.0.5.0 "FLEET" WAS CODE-COMPLETE ON MASTER 2026-10-14 ~21:45 CDT.** Every
round landed: R1 agent control (dbf1a13), R2 hub/pairing/join/relay
(7ece693), R3 the Studio Fleet section + Live Roles + hop keys (a82c607),
R4a the panels backend (782738e: the fleet watcher, attention queue + answer
route, caps, health, conflicts, hand-offs, recordings, replay, digest,
`halo fleet record|digest`, docs/FLEET.md "The panels"), R4b the panels UI
(33ee699: People/Costs/Health/Attention/Map/Activity/Agent, the conflict
edge, Take over / Hand to / Record / Replay, the canvas replay scrub, the
"While you were away" card, 6 new Chrome scenarios, studio-fleet-panels.png).
Merged as 3ef546f; CHANGELOG `## [3.0.5.0] - unreleased` holds R1-R4.
Branch `fleet/R4-panels` and worktree `<home>/hh-fleet/R4-panels` can go
after the tag. Release steps left: local three-suite gate (test_bridge,
tests/run_all, test_tui), CI `conclusion == success` for the exact sha,
`python scripts/release.py 3.0.5.0`, refresh the install (`uv pip install
--python <tool venv python> --reinstall-package halo-harness <clone>`),
`halo --version` = 3.0.5.0, memory. Then the owner's LIVE CHECK: this host
`halo studio --fleet` + `halo fleet pair`, the Kali VM `halo update` then
`halo fleet join <host>:7430 --code "..."`, an Orchestra run on one and a
flow on the other in one Fleet map, a steer from Studio reaching a worker
on the VM.

**NEXT: 3.0.6.0 "Fleet Missions"** (owner's ask 2026-10-14 ~21:00; plan
`~/.claude/plans/fleet-missions-3060.md`): R6 Capabilities (every harness
announces its MCP servers + tools, skills, roles, models, craft apps,
hardware, CLIs, tags; `GET /api/fleet/capabilities`, `/who?q=`, `halo fleet
capabilities|who`, a Studio Capabilities panel + chips), R7 Missions backend
(one goal split by the hub's lead over the capability catalog into parts
pinned to harnesses with reasons and exclusive claims; the mission folder
served over the signed fleet protocol or a real `fleet.shared_dir`; gated
`run_task` dispatch to `mission-worker` sessions; Orchestra merge + judge;
`halo fleet mission ...`), R8 the Missions Studio panel (DAG over the map,
drag to reassign) + docs + release. The former 3.0.6.0 list (tiers, Roles/
Org/Design ports, legacy removal) slides to 3.0.7.0; Team to 3.0.8.0.
Known small: `health` for the local harness probes providers (skipped under
`BRIDGE_TEST_NO_BACKGROUND_NET`); Hand to... "Open" copies a markdown path
(no open-file route); Costs cap save, Health Refresh, Kick confirm, hand_to
POST and the Activity filters are not driven in Chrome (API tests cover the
backend); `server.py` is 340 lines and `remote/bridge.py` 320 (over the cap
before this release).

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-14 ~19:00 CDT (authoritative, read this first)

**3.0.4.0 IS RELEASED AND INSTALLED** (see the previous snapshot below).
**3.0.5.0 "FLEET" IS IN FLIGHT, PAUSED FOR A MACHINE RESTART.** The owner's
plan is `~/.claude/plans/fleet-view-3050.md` (approved 2026-10-14 ~16:30:
"all of it and your suggestions"). Every brief, every round hand-back and
the CHANGELOG fragments are in `<home>/hh-fleet/briefs/` (OUTSIDE the repo
on purpose: the privacy scan rejects real home paths anywhere under the
tree, tracked or not; never copy them in).

Rounds (one Opus worker each, worktree per round off the previous round's
branch, I verify by rerunning the suites and looking at the pictures, then
commit; every branch is pushed to origin):
- **R1 agent control -- DONE** `fleet/R1-agent-control` dbf1a13: sockets on
  by default (`fleet.enabled`; `remote.enabled` only gates Signal), harness
  identity + project in the registry, the per-session agent tree, commands
  `agents` / `agent_tail` / `agent_steer` (nudge|redirect) / `agent_stop` /
  `pause` / `resume` / `shutdown` / `agent_follow`, frames `agent_state` /
  `agent_event` / `fleet`, Studio agent routes, `--private`.
- **R2 hub and join -- DONE** `fleet/R2-hub-join` 7ece693: `halo_harness/
  fleet/` (hub on a LAN port, HMAC-signed, TLS optional, six-word pairing
  with a code-authenticated DH exchange, relay with share status|events|
  full and control none|ask|all), `GET /api/fleet`, proxied command routes,
  `halo fleet` live table, `/fleet`.
- **R3 Studio Fleet + Live Roles -- DONE** `fleet/R3-studio-fleet` a82c607:
  the Fleet section (Alt+6: map, agent inspector with Thinking/Working/
  Output + Steer, the Fleet rail everywhere, Start view with pair code),
  hop keys J/K/F/Space/P + the mini stream, Live Roles (cards glow, the
  Live tab). Pictures docs/media/studio-fleet.png, studio-roles-live.png.
- **R4 panels + the owner's extras -- IN PROGRESS, INTERRUPTED** worktree
  `<home>/hh-fleet/R4-panels`, branch `fleet/R4-panels`, brief
  `hh-fleet/briefs/fleet-R4-panels-brief.md` (people, attention queue +
  Signal push, activity timeline, costs + caps, health, conflict warnings,
  hand-offs, flight recordings, canvas replay, digest; code only, no model
  calls). The worker had written the backend modules `halo_harness/fleet/
  attention.py, caps.py, conflicts.py, digest.py, handoff.py, health.py,
  history.py, journal.py, push.py, recording.py, recording_page.py` and
  edited control/local_view/protocol/relay_hub, remote agent_control/
  bridge/fleet_identity/protocol, studio fleet_hub_api/sessions_api when
  the restart came; NO UI panels, tests, docs or dist yet unless the
  worker's final hand-back (if it arrived) says otherwise -- its hand-back,
  when present, is `hh-fleet/briefs/fleet-R4-handback.md`. The worktree
  state is committed as a WIP commit on the branch ("WIP fleet R4"); a
  resuming worker should `git log -1`, read the brief + hand-backs, verify
  each module against the brief, then finish items 1-12.
- **R5 release -- NOT STARTED**: merge `fleet/R4-panels` into master,
  insert `hh-fleet/briefs/CHANGELOG-3.0.5.0-draft.md` (R1-R3 bullets; add
  R4's) above the 3.0.4.0 section, gates (`python test_bridge.py`,
  `python tests/run_all.py`, root `python test_tui.py` then `git checkout --
  docs/harness/tui-snapshots`), push, CI `conclusion == success` for the
  exact sha (Windows run_all budget is 65 min), `python scripts/release.py
  3.0.5.0 --no-install`, `uv pip install --python <uv tool venv python>
  --reinstall-package halo-harness <clone>`, `halo --version`, this file,
  memory. Then the LIVE CHECK the owner must do: this host runs `halo studio
  --fleet` (expect the Windows firewall prompt), the Kali VM runs `halo
  update` then `halo fleet join <host>:7430 --code "<six words>"`, a session
  on each, both visible in one Fleet map, a steer from Studio reaching a
  worker on the VM.

Rules learned this cycle: briefs and hand-backs live outside the tree
(privacy scan); never run two headless Chromes at once (one-shot
`--dump-dom` returns empty); a closed loopback port takes ~2 s to refuse on
Windows; patch CRLF files EOL-aware; `git worktree remove` can hit
"Permission denied" right after a test run (retry, then `rm -rf` the stray
dir); the status cron jobs are session-only (re-create per session: every
15 min, every 30 min from 4 to 10 AM).

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-14 ~15:30 CDT (authoritative, read this first)

**3.0.4.0 "Media and Flow" IS RELEASED** (tag v3.0.4.0 at 3c3a3fc on master, GitHub
release published, local install `halo 3.0.4.0`), cut on CI run 38617371390 read
as `conclusion == success` for sha 93f7839. It carries R1 Media core (ComfyUI as
the eighth craft app), R2 the media-model inventory, R3 the flow engine, R4
Postiz, R5 the Studio flow/media/sessions routes, R6 the Studio Flow section and
Media panels, and R6b "Studio clarity" from the owner's live review (one header:
legacy pages embedded; panels focus on click and open on their full face with an
about line and a `?` help; a Start view per section instead of a grid of empty
panels; "How this works" per section with a first-visit welcome; labelled group
boxes on the Roles/Org canvases). Two late fixes before the cut: the model
dropdowns explain an empty catalog and offer Refresh (`GET /api/models/status`,
`POST /api/models/refresh`; the owner's Kali VM showed "(none)" with no reason),
and the ComfyUI client joined `_ALLOWED_RAW_NETWORK_CALLERS` (the user's own
render server, like the MCP probes). CI: the Windows run_all step budget is now
65 min (the 470-module suite timed out at 45 with four modules left; nothing
failed), Linux 50.

**Standing owner direction for every Studio round** (memory `feedback-studio-
clarity`): no nested chrome, panels usable without an activate step, a Start
view when nothing has run, explanations on every panel and section, visual
group containers on the canvases, clarity over flourish inside the holo look.

**NEXT: 3.0.5.0** per the owner's plan `~/.claude/plans/ok-ther-gui-parts-snappy-
hejlsberg.md`: tiers, Home, the Roles rebuild (port the legacy Roles/Org/Design
pages into the React shell -- the embedded mode is a bridge, not the end state),
Org/Design ports; 3.0.6.0+ the Team tab. Open and small: the rail still lists the
hidden Media panels while ComfyUI is down; the embedded Org page briefly draws the
Roles lineup before switching; the React Flow intake's model select has no
empty-catalog notice yet (the legacy pickers do). No worktrees remain
(`git worktree list` = master only); branches `flow/*` and `track-d` are merged
and may be deleted.

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-14 ~01:00 CDT (authoritative, read this first)

**3.0.2.0, 3.0.2.1, 3.0.2.2 AND 3.0.3.0 ARE RELEASED** (tags on master; the
local install reports `halo 3.0.3.0`). 3.0.2.x = the whole 3.0.1.0 review fix
pass (160 findings + the follow-up round Z; `plans/briefs/3.0.2-fixpass/
SWEEP.md`). 3.0.3.0 = the Orchestra (goal -> lead split -> workers in
worktrees with claims -> merge one at a time -> fresh judge -> gate loop ->
report; `halo orchestra`, docs/ORCHESTRA.md) and the React + Vite Studio shell
(committed bundle, `/legacy/` pages, movable workspace, motion vocabulary, SSE
feed, the Orchestra run console; docs/STUDIO.md). Every release was cut on a
green CI run read as a value (never on a watcher's exit code).

**IN FLIGHT: 3.0.4.0 "Media and Flow"** (plan: the owner's
`~/.claude/plans/ok-ther-gui-parts-snappy-hejlsberg.md`; briefs in the
session scratchpad under `flow/`): R1 Media core (ComfyUI as the eighth craft
app: `halo media init|doctor|serve|inspect|models|workflows`, the comfyui MCP
server, starter workflows, docs/COMFYUI.md) and R2 the media-model inventory
(`halo models --media`, `--best-for image-gen|video-gen|audio-gen|upscale`,
never in the LLM pickers) are DONE on branches `flow/R1-media-core` and
`flow/R2-media-inventory`; R3 the flow engine (`halo_harness/flows/`, the
social-post template, the marketing org, the human confirm gate, dry-run
post stubs) is running in worktree `<home>/hh-flow/R3-flow-engine`; then R4
Postiz (CLI, `POSTIZ_API_KEY`, dry-run by default), R5 Studio server routes
(flow/media APIs + the sessions answer route), R6 the Flow and Media
sections on the shell, R7 release. 3.0.5.0 = tiers, Home, the Roles rebuild,
Org/Design ports; 3.0.6.0+ = the Team tab. Rules learned: never `git stash` in
the worktree farm (shared stack); gate `release.py` on `gh run view <id>
--json conclusion` == success for the suites run of the exact sha; keep the
main checkout clean while a release is pending (a local `test_tui.py` run
rewrites docs/harness/tui-snapshots until it ends).

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-13 evening CDT

**THE 3.0.1.0 REVIEW FIX PASS IS INTEGRATED, HEADING FOR 3.0.2.0.** The
owner's 15-reviewer cloud review of 3.0.1.0 (161 confirmed findings; the
owner's edited copy removed item 6 and trimmed 1/2/16/25 under the standing
contract) was worked as fifteen parallel worktrees under `<home>/hh-fix/`
(branches `fix/A-permissions`, `B-trust`, `C-studio-tools`, `D1-remote-core`,
`D2-signal`, `E-session-data`, `F-install-update`, `G1-providers-wire`,
`G2-local-catalog`, `G3-mcp-commands`, `L-agent-loop`, `S-subagents-teams`,
`T-tui`, `P-design-paperclip`, `M-data-misc`), one Opus/Sonnet worker each,
then merged in sequence onto branch `integrate` (hand-resolved: D1/D2 in
bridge.py, bridge_session.py, signal_transport.py; E/C in design/jsonio.py
and store.py; G1/G2 in learned_params.py). Status: 158 DONE, 1 PARTIAL
(81: the stable channel cannot hash-compare a uv git build), 1 REJECTED
(25: does not hold, pinned), plus owner item 162 (every game level keeps the
full plain status bar, pinned across every theme and variant; the skin
default is now plain). `plans/briefs/3.0.2-fixpass/SWEEP.md` has the
per-item table. CHANGELOG `## [3.0.2.0] - unreleased` carries the section.
Pre-existing on this Windows host: `tests/test_cli_flags.py::
test_version_flag_short_and_long` fails on untouched master (cp1252
subprocess decode); baseline run_all on master = 4668 passed / 1 failed /
14 skipped. Remaining: full three-suite gate on `integrate`, fast-forward
master, push, CI, `release.py 3.0.2.0`, refresh the install (`uv pip install
--python <tool venv python> --reinstall-package halo-harness <clone>`),
remove the hh-fix worktrees. Lesson: never `git stash` in a shared-stash
worktree farm (two workers swapped trees; recovered from saved patches).

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-12 ~00:15 CDT

**EVERYTHING THROUGH 3.0.1.0 IS RELEASED.** Tags on master: v2.0.11
(`8ee57be`, the front page), v2.1.0 (`e045330`, Team step + `halo
studio`), v2.2.0 (`904d3c1`, Org mode on Paperclip), **v3.0.1.0
(`7659258`, Halo Design)**. GitHub releases published for each with their
artifacts. The local uv tool install reports `halo 3.0.1.0`. The Paperclip
company "Halo Harness" (seven halo-dev-cycle agents) runs the installed
`halo paperclip-run`. PR #3 (track-d) is merged by fast-forward; the
temporary `branches: [master, track-d]` workflow trigger was reverted
before the merge. Branch worktrees Halo-B/C/D can be removed (`git
worktree remove`) once the owner is done with them.

**3.0.1.0 in one paragraph:** `halo models --best-for design|visual|
audio|video|image` ranks the catalog from its own modality/price/context
facts; `halo design new|list|show|run|sync|comment|restore|export|
handoff|critique|doctor` works a project under `~/.halo/design/<slug>/`
(artboards with versions, pins, knobs, system.json, history) where a turn
is `halo -p` in the project folder with the seven ArtCraft MCP servers as
its ONLY MCP servers (strict `--mcp-config` per run) and the Design skill
appended; Studio's third mode `Roles | Org | Design` shows the artboards
as frames (sandboxed iframes / renders via `/design-files/...` with its
own CSP), chat with streamed turns, comment pins, knobs that rewrite
`:root` with no model call, direct text edits, a version slider,
variants, a critique pass, a WCAG contrast table, an assets drop zone,
exports and the handoff bundle. docs/DESIGN.md, docs/STUDIO.md "Design
mode", docs/MODELS.md "Which model for what".

**Live acceptance on this host:** `halo design run` on
`or:anthropic/claude-haiku-5.5` built an HTML hero with two knobs and a
VectorCraft logo mark (SVG+PNG) for $0.029 (project `halo-launch-page`);
knob -> v2 through the Studio API; `halo design doctor --probe` found all
seven craft apps up with their render tools.

**KNOWN / OWNER ACTIONS:** the Paperclip `review` agent shows a stale
"Process exited with code 1" from an earlier duplicate heartbeat (clears
on its next run); `studio/api.py` (267) and `studio/model.py` (282) sit
over the 250-line cap from before; known flakes:
`test_tui.py::test_bare_effort_card_selection_persists_like_the_plain_
text_path`, `tests/test_wizard_agents_bios.py::test_bio_editor_opens_
with_a_sentence_and_per_field_help`; GitHub's API applies a secondary
rate limit when two `gh run watch` loops poll at once (watch one run at
a time); owner still uploads docs/media/social-preview.png (Settings ->
Social preview) and does the live Signal check (docs/REMOTE.md). Nothing
is queued after 3.0.1.0: the roadmap through Track D is complete.

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-11 ~22:40 CDT (authoritative, read this first)

**v2.0.11 and v2.1.0 ARE RELEASED** (tags at `8ee57be` and `e045330`; local
install refreshed to 2.1.0 with the `uv pip install --python <tool venv
python> --reinstall-package halo-harness <clone>` recipe, since `uv tool
install --reinstall` fails while a `halo.exe` session runs).

**2.2.0 "Org mode" IS ON MASTER WAITING ON CI** (merge `3848dbd`; one CI fix
`7f7832b`: the Studio install endpoint started a real `npx` install on Linux
CI because the fake Paperclip was reachable but nothing was under
`~/.paperclip`; it now refuses whenever an instance is reachable). Gate the
release on `gh run view <id> --json conclusion` == success (never on the
watch command's exit), then `python scripts/release.py 2.2.0 --no-install`
(CHANGELOG has `## [2.2.0] - unreleased`), refresh the install, then
`halo paperclip sync halo-dev-cycle --company "Halo Harness"` so the live
Paperclip agents point at the installed `halo` (they still name a deleted
scratch runner).

**3.0.1.0 "Halo Design" IS IN FLIGHT ON `track-d`** (worktree <home>/Halo-D,
branched from track-c; the 2.2.0 CI fix is cherry-picked there as
`87309c2`). Done and committed: D1 capabilities (`halo models
--capabilities|--best-for KIND`, `halo_harness/capabilities.py`, Studio
chips); D2 `halo_harness/design/` (store, session, sync, export, cli; `halo
design new|list|show|run|sync|comment|restore|export|handoff|doctor`); D4
`design/crafts_probe.py` + `halo design doctor --probe` (all seven craft
apps up with their render tools on the build host); D3 Studio Design mode
(worker, verified: `studio/design_api*.py`, `design_files.py`, the raw
artboard route with its own sandbox CSP, `static/design*.js|css`,
`tests/test_studio_design.py` 9/9 incl. headless Chrome, `tools/
design_demo.py`, `capture_studio.py --mode design`, docs/media/
studio-design.png); docs/DESIGN.md, docs/STUDIO.md Design section,
COMMANDS.md sections, README story + rows, CHANGELOG `## [3.0.1.0] -
unreleased` (D1-D4 bullets). A design turn hands the model ONLY the craft
MCP servers (a strict `--mcp-config` written per run; `--tools` filters
built-ins only). **Live acceptance passed**: `halo design run` on
`or:anthropic/claude-haiku-5.5` made an HTML hero with two knobs and a
VectorCraft logo mark (SVG+PNG) for $0.029; export folder, handoff, the
Studio Design API (knob -> v2, raw route, ranking) all checked against the
real project `~/.halo/design/halo-launch-page`.

**IN FLIGHT: D5 polish** (worker from `plans/briefs/D5-design-polish.md`:
variants, critique pins, contrast check, assets, run-view cost line,
shortcuts, Design tour steps, docs/media/studio-design-knob.png, docs).
Then D6: CHANGELOG D5 bullets, the CI trio on track-d (push the branch,
watch the run), merge to master AFTER 2.2.0 is tagged, `release.py 3.0.1.0
--no-install`, refresh the install, memory, this handoff.

**KNOWN:** `studio/api.py` (267) and `studio/model.py` (282) sit over the
250-line cap from before; `test_tui.py::test_bare_effort_card_selection_
persists_like_the_plain_text_path` and `tests/test_wizard_agents_bios.py::
test_bio_editor_opens_with_a_sentence_and_per_field_help` are known
flakes; the three shields badges render blank through GitHub's camo
briefly after a push; owner still uploads docs/media/social-preview.png.

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-11 ~16:30 CDT (authoritative, read this first)

**v2.0.11 IS RELEASED** (tag v2.0.11 at `8ee57be`, GitHub release
published; the local uv tool install is refreshed to 2.0.11 -- note: `uv
tool install --reinstall` fails while a `halo.exe` session is running
(Scripts dir locked); `uv pip install --python <tool venv python>
--reinstall-package halo-harness <clone>` refreshes the package without
touching Scripts). The owner still uploads docs/media/social-preview.png
in GitHub Settings -> Social preview.

**2.1.0 IS MERGED INTO MASTER AND WAITING ON CI** (branch `track-b`,
worktree <home>/Halo-B, merged after this handoff): B1 the Team
step back in Quick setup with the lineup preview (`tui/dialogs/
team_preview.py`), B2 the CLI (`halo teams` overview/apply/preview/diff,
`halo agents` overview, `halo roles` sources, `/teams` overview), B3
`halo studio` (halo_harness/studio/, docs/STUDIO.md, three test
modules, docs/media/studio.png), B4 README/docs. NEXT: CI green on both
platforms -> `python scripts/release.py 2.1.0 --no-install` (CHANGELOG
has `## [2.1.0] - unreleased`) -> refresh the install -> handoff.

**2.2.0 "Org mode" IS CODE-COMPLETE ON `track-c`** (worktree C:/Users/
rolo/Halo-C, branched from track-b, master merged in): C1-C3
halo_harness/paperclip/ (client, `halo paperclip-run` adapter, `halo
paperclip status|install|open|link|sync|pull|org`), C4 Studio's Roles |
Org toggle over Paperclip (proxy `/api/pc/...`, org canvas, re-parent,
issues, embedded pages, install from the page), C5 docs/PAPERCLIP.md,
ORGS.md note, the wizard Orgs step pointer, README story,
docs/media/studio-org.png. Verified live against Paperclip 2026.1005.0
installed on this host (`~/.paperclip`, http://127.0.0.1:3100, company
"Halo Harness" with the halo-dev-cycle agents; a heartbeat ran the
adapter end to end). NEXT after 2.1.0 ships: merge master into track-c,
CI, `release.py 2.2.0`. Plan: ~/.claude/plans/awesome-job-on-getting-
robust-stardust.md (Track C at the end).

**KNOWN:** the CI steer-capture flake is fixed (two layout passes in
`scripts/screenshots.py::_export`); `tests/test_wizard_agents_bios.py::
test_bio_editor_opens_with_a_sentence_and_per_field_help` flaked once on
the Windows CI runner (focus timing) -- watch it; Paperclip auto-wakes an
assignee on assignment, so `agent heartbeat:invoke` right after assigning
makes a duplicate run that 403s on the comment; `cc:`/`cx:` bios fail a
heartbeat until `halo subscriptions accept` ran on the machine.

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-11 ~13:45 CDT (authoritative, read this first)

**2.0.11 "the front page" is code-complete and pushed** (`f4859ee` on
master; CHANGELOG `## [2.0.11] - unreleased`), the plan is
`~/.claude/plans/awesome-job-on-getting-robust-stardust.md` (two tracks:
A = 2.0.11 front page, B = 2.1.0 agents revamp + `halo studio`). Rounds:
A1 `62deb5e` every generated SVG carries width/height (GitHub's file
view showed every capture at ~180 px: viewBox-only SVGs have no
intrinsic size); A2 `46b5e13` the block-art HALO wordmark under a halo
ring (`banner.py` BANNER_ART + ASCII fallback), the intro reveals it row
by row in a gradient, the pool is the art + NIN line + Red Dragon line
only, `tools/hero_svg.py` draws hero.svg and social-preview.svg; A3
`b9568f8` the level band (`tui/scene.py` engine, `scene_mario/metroid/
doom.py` original 8-bit art, `widgets/scene_band.py`, `/level`,
`theme_scene`), three animated level captures; A4 `f4859ee` the README
as a product page, the GitHub description/topics set, docs/media/
social-preview.png.

**NEXT (in order):** 1. CI run 38163490762 green on Linux + Windows ->
`git checkout -- docs/harness/tui-snapshots` (test_tui churns them) ->
`python scripts/release.py 2.0.11 --no-install` -> refresh installs
(`halo update` / the installers). 2. Owner uploads
docs/media/social-preview.png in GitHub Settings -> Social preview (no
API). 3. Track B (2.1.0): B1 the Team step back in Quick setup, B2 the
CLI (`halo teams apply/preview/diff`, `use` writes roles too), B3 `halo
studio`, B4 docs, B5 release -- the plan file has every detail.

**KNOWN / FOUND THIS SESSION:** `test_tui.py::test_bare_effort_card_
selection_persists_like_the_plain_text_path` fails locally on master
("nothing persisted yet") BEFORE this session's changes -- check whether
CI sees it; the 2.0.10 release run's Windows job failed on
`test_committed_capture_svgs_are_a_fresh_renders_output` (the steer
capture flipped 1 in 3 on a scrollbar that appears one layout pass late;
`scripts/screenshots.py::_export` now settles two passes and four
consecutive checks agreed). Three shields badges (release, platform,
MIT) showed blank through GitHub's image proxy right after the push
while shields served them directly -- re-check; swap to static badges
if it persists. Status crons: session-only, every 15 min (30 min 4-10 AM).

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-11 ~22:15 CDT (authoritative, read this first)

**v2.0.10 IS RELEASED** (tag v2.0.10 at `d49f60d`, GitHub release
published, `--no-install`: the owner refreshes installs himself). CI
green on Linux and Windows at `f375925`. Four releases this session:
2.0.7.1 (review fix pass), 2.0.8 (theme pack), 2.0.9 (Signal remote
control), 2.0.10 (/review feature, the security review with 26/27
findings fixed + SECURITY.md, the front page redo). The roadmap through
2.0.10 is COMPLETE; 3.0.1.1 (serverless collaboration) is PARKED by the
owner -- do not start it unless he re-opens it.

**OWNER ACTIONS PENDING**
1. The live Signal check (dedicated number + Kali VM): docs/REMOTE.md
   "Live verification" + "Confirm on the first live run". Findings ->
   a 2.0.10.1 fix pass (update tests/helpers/fake_signal_cli.py to the
   real shapes). Also unverified live: signal-cli `setPin` over jsonRpc
   stdin; the gpg release-key fingerprint is empty (digest-only setup).
2. Refresh his installs (`halo update` on a clone checked out on a tag
   needs `--ref`; the installers now install the newest tag).
3. Two behaviour changes from the security pass to know: `${VAR}` in a
   project .mcp.json no longer expands provider tokens (warning), and
   the install one-liners pin a tag.

**IF RESUMED WITHOUT NEW ORDERS**: nothing is queued. Candidates the
sweep/residuals name (all small): SHA-pin the GitHub actions; Tab
completion for `/metroid <area>` and `/mario <variant>`; expire pending
contact requests after a day; `halo -c` in the TUI with no prior
session still starts fresh silently; wizard roles toggles do not
refresh a live role table. Status crons are session-only.

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-11 ~18:10 CDT (previous)

**2.0.10 is five rounds in, all pushed**: 1 `f88a012` (/review + halo
review, live-accepted with glm-5.3-flash), 2 `7b6b78c` (the security
review: docs/harness/SECURITY-REVIEW-2.0.10.md, 27 findings / 7 high, +
SECURITY.md), 3 `8376d4a` (fix pass 1: trust 6-10, credentials 17-20),
4 `3725d23` (fix pass 2: deny/ask rules hold through compound forms
12-16, state-dir modes 24-25; 11 REJECTED by the standing contract),
5 `9c78ff8` (fix pass 3: remote 1-5, subprocesses 21-23, supply chain
26-27) + `6edd212` (release.py rewrites the installer tag URLs).
`plans/briefs/2.0.10-review/SWEEP.md`: 26 fixed, 1 rejected, 0 open;
residual risks listed there (uv tool install ignores lock hashes; CI
actions not SHA-pinned; signal-cli setPin stdin path unverified live;
gpg release-key fingerprint left empty -> digest-only).

**IN FLIGHT: round 6, the front-page redo** (`round-6-front-page.md`:
tools/capture_screens.py + captures.json -> docs/media/ PNGs via
headless Chrome + SMIL-animated SVGs, hand-drawn diagrams, README top
half rewritten as stories + a comparison table, tests/test_front_page_
media.py, docs/MEDIA.md). THEN: CI green on both platforms (watch the
new pip-audit / --require-hashes steps in suites.yml -- first run after
round 5) -> `python scripts/release.py 2.0.10 --no-install` -> handoff +
memory. Behaviour changes worth telling the owner: `${VAR}` in a project
.mcp.json no longer expands provider tokens (warning instead); the
installers now install the newest tag (`--ref master` for the old
behaviour); `halo update` on a tag-checked-out clone needs `--ref`.

**OWNER ACTIONS PENDING**: the live Signal check (docs/REMOTE.md "Live
verification") -> 2.0.9.1/2.0.10.1 fix pass; after 2.0.10 the roadmap
has 3.0.1.1 PARKED by the owner (do not start it).

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-11 ~10:20 CDT (previous)

**v2.0.9 IS RELEASED** (tag v2.0.9 at `b691a0d`, GitHub release
published, `--no-install`: the owner refreshes installs himself). CI was
green on Linux and Windows at `5252e14`. Three releases this session:
2.0.7.1 (review fix pass), 2.0.8 (theme pack), 2.0.9 (Signal remote
control, rounds 1-4; code-complete, hermetically tested against a fake
signal-cli).

**OWNER ACTION PENDING: the live Signal check** -- a dedicated Signal
number on the Kali VM, following docs/REMOTE.md "Live verification"
(setup -> register -> run -> pair from the phone -> /sessions, attach,
prompt, permission card by number, /stop, unpair, second phone ignored)
and noting the items under "Confirm on the first live run". Findings
from that run become the 2.0.9.1 fix pass (brief it from the owner's
notes; the fake signal-cli in tests/helpers/fake_signal_cli.py must be
updated to whatever real shapes differ).

**NEXT on the roadmap: 2.0.10 review/security** (ROADMAP tail: a whole-
tree review -- the owner's own review file pattern from 2.0.7 worked:
numbered findings outside the repo, briefs point workers at it, one
round per area, pins per finding, SWEEP.md at the end).

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-11 ~09:00 CDT (previous)

**2.0.9 Signal remote control is CODE-COMPLETE, tag pending CI.** Rounds
pushed: 1 `0df8bac` (SIGNAL-RESEARCH.md refreshed to signal-cli 0.14.9,
nine questions answered, section 8 design adjustments incl. the
contact-request pairing flow, section 9 verified controller surface),
2 `797e053` (per-session control socket, SessionHandle for TUI + print
mode, sessions registry, `remote.enabled` default false), 3 `069f38d`
(signal-cli stdio transport, pairing, HMAC signing with a 32-word
phrase, bridge + rendering, fake signal-cli tests), 4 (the commit after
`68803d3`: `halo remote signal ...` CLI with an original QR encoder, the
/remote dialog, the `⇄ remote` chip + HUD slot, doctor checks, REMOTE.md
complete). Briefs: `plans/briefs/2.0.9-signal/round-{1,2,3,4}-*.md`.
CHANGELOG already carries `## [2.0.9] - unreleased` with four sections.

**REMAINING for the tag**: CI green on both platforms for round 4 ->
`python scripts/release.py 2.0.9 --no-install` -> handoff + memory.
**THE LIVE CHECK IS THE OWNER'S** (needs a dedicated Signal number and
the Kali VM): docs/REMOTE.md "Live verification" is the step list, and
"Confirm on the first live run" lists what only a real signal-cli can
settle (trust accepting plain digits, redelivery after trust, manual
receive-mode queueing, param shapes, attachment paths, .bat spawn on
Windows, --scrub-log). Expect a 2.0.9.1 fix pass after that run.

**THEN 2.0.10 review/security** (ROADMAP tail).

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-11 ~04:05 CDT (previous)

**v2.0.8 IS RELEASED** (tag v2.0.8 at `1d001be`, GitHub release
published, `--no-install`: the owner refreshes installs himself). The
theme pack shipped complete: DOOM, Metroid (five areas), Mario (two
palettes) on the shared game-HUD engine, the toggle contract, docs and
the README gallery. CI green on Linux and Windows at `86da95b` (the two
CI-only reds after round 3: cue calls now guard a missing status bar;
`release.py` re-renders docs/screenshots/ into the release commit so the
launch banner never drifts again). Pack follow-ups left open (small, not
blocking): Tab completion of `/metroid <area>` and `/mario <variant>`;
the ASCII fallback strips coin/heart/star glyphs instead of substituting.

**NEXT = 2.0.9 Signal** (`plans/2.0.8-signal-brief.md`; the owner's
order is a RESEARCH round first, then implementation rounds), then
2.0.10 review/security. Status crons are session-only; re-create.

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-11 ~01:45 CDT (previous)

**2.0.8 theme pack: all three skins are IN and pushed**: round 1
`e29da72` (names, `tui/hud.py` engine, DOOM, the toggle contract), round
2 `4f39d27` (Metroid: tanks/missile/super/area, five area variants,
map-grid cards, visor input frame), round 3 `69c330c` (Mario: score/
power/coins/world/time/turns, bros+world palettes, brick cards + pipe
frame, 1-UP/coin cues on sub-agent/job completion), plus `de279d6`
(Windows Terminal = truecolor via WT_SESSION). Each skin was verified
LIVE on this host (`/doom`, `/metroid norfair`, `/mario`, and each
toggle-again restore). README themes table is complete (three renders
under docs/screenshots/). CHANGELOG already carries `## [2.0.8] -
unreleased` with the three sections. Full test_tui is green at 291
tests; test_bridge 101/101.

**REMAINING for the 2.0.8 tag**: CI green on both platforms for
`69c330c` (watch was running at the pause) -> `python scripts/release.py
2.0.8 --no-install` (owner refreshes installs himself) -> handoff +
memory. Known cosmetic drift: docs/screenshots/launch.svg still shows
"halo 2.0.7" (regenerate with scripts/screenshots.py after a bump if
wanted). Left open from the pack (small follow-ups, not blocking): Tab
completion of `/metroid <area>` and `/mario <variant>` arguments; the
ASCII fallback strips the coin/heart/star glyphs instead of substituting.

**THEN 2.0.9 Signal** (`plans/2.0.8-signal-brief.md`, research round
first), then 2.0.10 review/security.

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-10 ~23:15 CDT (previous)

**v2.0.7.1 IS RELEASED** (tag v2.0.7.1 at `f2a70fb`, GitHub release
published, `--no-install`: the owner refreshes installs himself; the Kali
VM was unreachable all evening so its battery is CI's Linux job). The
vibes/review.md fix pass is COMPLETE: rounds 8 (`e793810`), 9 (`e774fe4`),
10 + sweep (`1efed92`), the three CI-only reds after round 9 (`63c57c1`:
POSIX project-key match, SIGHUP test under the consent gate, h9 timing
bound). `plans/briefs/2.0.7-fixpass/SWEEP.md`: 89/92 fixed, 3 rejected
(3, 4 by the standing contract; 18 does not hold), none open. CI green on
Linux and Windows at `63c57c1`. run_all on this host: 4298 tests / 335
modules green (takes ~55 min here; give workers a long timeout).

**IN FLIGHT: 2.0.8 theme pack, round 1** (`plans/briefs/2.0.8-themes/
round-1-hud-engine-doom.md`: theme names doom/metroid/mario registered,
`tui/hud.py` skin engine on the status bar, the DOOM skin with the 5-state
ASCII face + width cascade snapshots, the `/doom` `/metroid` `/mario`
toggle contract pinned once, docs + `theme-doom` screenshot scene).
THEN round 2 Metroid (Super Metroid areas as variants, HUD energy/missile
counters, map-grid panels, visor input framing), round 3 Mario (SMB/SMW
palettes, coins=cost, timer clock, world-level cwd, brick/pipe borders,
1-up/coin cues on finished tasks), round 4 README renders per theme +
CHANGELOG + full battery + `release.py 2.0.8`. Then 2.0.9 Signal
(`plans/2.0.8-signal-brief.md`, research round first).

Left open from the fix pass (not blocking): TUI `halo -c` with no prior
session still starts fresh silently (finding 76 was print-mode only);
init-wizard roles toggles do not refresh a live role table (58). Status
crons are session-only; re-create on resume.

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-10 ~18:45 CDT (previous)

Resumed on the Windows build host. Shipped and pushed today: `c1b6542`
(pyflakes gate: round 7 used `Optional` in providers/http.py without the
import; CI on 7b was red for that alone, Windows job green) and `e8a0d6a`
round 7c (Ctrl+C copies; second press within 3 s opens the "Quit Halo?"
card; `tui/console_mode.py` keeps the Windows console from killing the
session -- verified LIVE in Windows Terminal on this host: single press ->
toast, double -> card, Enter -> clean exit to the shell prompt). The
owner's second clone under his home folder was behind origin and carried
a duplicate of e521b24; it is now reset to origin/master (branch
`backup-c9ea633` keeps the old tip).

**IN FLIGHT: round 8** (`round-8-loop-subagents.md`, findings 49-53 +
54-64), one worker. Then round 9 -> round 10 + final sweep -> full battery
both platforms -> `scripts/release.py 2.0.7.1` -> 2.0.8 themes -> 2.0.9
Signal, exactly as the 00:45 snapshot below orders it. Status crons
(:00/:15/:30/:45, 4-10 AM every 30 min) are session-only; re-create.

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-10 00:45 CDT (previous)

**Owner paused the session ("finish what you're doing, save a handoff").**

Shipped tonight, all pushed: round 6 `ebe2ce8` (the nine CI-red tests), round 7 `4b207cd` (findings 43-47, 33, 38-40, P2 tail), the union-type repair fix `e521b24` (cherry-picked from the owner's second clone; its CHANGELOG line is still PENDING: add under `[unreleased]`: "fix: tool-arg schema validation no longer crashes on union types (`type` as a list), needed by MCP servers using string|null schemas"). CI: round 6 green on both platforms; the run on `e521b24` was in progress.

**Round 7b SHIPPED after the pause note was written (see the commit list)**; the paragraph below is kept as history. **Nothing is in flight; the tree is clean. Resume at round 7c.** Known on this build host only: `tests/test_governor_review.py` hangs standalone (CI runs it fine); `test_agents_schedule every_1s` and `test_cli_flags playwright` flake under load. Round 7b's design notes: the live sub-agent spawn path and a standalone bio naming `cc:`/`cx:` refuse clearly with the acceptance message rather than silently swapping to the default model (the lineup preview layer does the graceful fallback) -- revisit only if the owner wants the live path to fall back too.

**IN FLIGHT at the time of the pause note: round 7b, the subscription consent gate** (brief `plans/briefs/2.0.7-fixpass/round-7b-subscription-consent.md`, rolo's 23:10 decision: `cc:`/`cx:` off until the user types `I accept`). A worker had written the new modules and edited these files (its hand-back had not arrived): CHANGELOG.md README.md docs/COMMANDS.md docs/HANDBOOK.md docs/MODELS.md docs/SLASH-COMMANDS.md halo_harness/cli.py halo_harness/commands/builtins.py halo_harness/doctor.py halo_harness/init_providers.py halo_harness/model.py halo_harness/providers/model_enumeration.py halo_harness/providers_cli.py halo_harness/teams_yaml.py halo_harness/tui/dialogs/init_wizard.py halo_harness/tui/slash.py test_tui.py tests/test_agents_teams.py tests/test_cc_models.py tests/test_cc_session.py tests/test_codex_session.py tests/test_codex_settings_merge.py tests/test_dbx_tui_surface.py tests/test_edit_hint.py tests/test_h15_provider_enablement.py tests/test_launch_state.py tests/test_set_model_creds.py tests/test_w3b_timeline_completeness.py halo_harness/subscription_consent.py halo_harness/subscriptions_cli.py halo_harness/tui/dialogs/subscription_notice.py tests/test_subscription_consent.py tests/test_subscription_consent_cli.py tests/test_subscription_consent_tui.py. To finish: run `tests/test_subscription_consent*.py`, every touched module's tests, `test_bridge.py`, `test_tui.py`, invariants, privacy scan, docs tests, `audit privacy`; if green, commit as one round commit (add the pending CHANGELOG line above in the same commit); if not, start ONE worker with the brief plus "the tree already contains these files; finish from there".

**Then, in order:** round 7c (`round-7c-ctrl-c.md`: Ctrl+C copies, second press asks, Windows console never kills the session; rolo 23:45) -> round 8 (`round-8-loop-subagents.md`) -> round 9 (`round-9-tui-cli.md`) -> round 10 (`round-10-telemetry.md` + final sweep) -> full battery (test_bridge + tests/run_all + test_tui, both platforms) -> `scripts/release.py 2.0.7.1 --remote <user@host> --identity <key>` -> 2.0.8 themes (ROADMAP "2.0.7 becomes a theme pack": DOOM/Metroid/Mario on one game-HUD status-bar engine, slash toggles, snapshots, README renders) -> 2.0.9 Signal (`plans/2.0.8-signal-brief.md`, research round first).

Standing facts: the owner's review file lives outside the repo (`<review file>`); briefs point workers at it as the source of truth (round 7 found my paraphrase of 43-45 wrong). Status posts on :00/:30 and one watchdog per worker are session-only crons; re-create them when resuming. The owner's second clone under his home folder is NOT a source: pull before using it.

--- previous snapshot below ---

## WHERE THINGS STAND -- 2026-10-09 ~01:30 CDT (authoritative, read this first)

**Update 2026-10-09 22:50 (the next session, resumed):** round 6 of the fix pass SHIPPED as `ebe2ce8` (the nine tests red on CI after rounds 1-5: five product bugs, four stale pins; CI should be green on both platforms). Rounds 7-10 are briefed under `plans/briefs/2.0.7-fixpass/` (7: MCP 43-47 + provider tail + P2 tail, SHIPPED 4b207cd; 7b: the subscription consent gate (rolo 23:10, cc:/cx: off until accepted), IN FLIGHT from 23:40; 8: loop 49-53 + sub-agents 54-64; 9: TUI 67-75 + CLI 76-83; 10: telemetry 84-92 + final sweep), then the full battery and the 2.0.7.1 tag, then 2.0.8 themes and 2.0.9 Signal (the owner's order, 2026-10-09).

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
