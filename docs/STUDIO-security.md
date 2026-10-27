# Studio: saving, security, SSH and shortcuts

Read this when you save and apply from Studio, run it over SSH, check what it lets a page do, or want every shortcut.

Part of [Halo Studio](STUDIO.md), which lists every part.

## Validate, save, apply

Every edit is validated as you make it (`teams_yaml.validate_team_template`,
the CLI's own checks, plus the preflight: the Problems panel). **Save** validates, then writes the YAML to your user
scope (or the project, with the user / project toggle in Lineups). A shipped
lineup or bio is never edited in place: saving it writes a copy under the
same name into your scope, which then shadows the shipped one -- exactly
what the wizard's Duplicate does. **Apply** shows the role table it will
write and, on confirm, does what `halo teams use <name>` does: `roles.*`
and `team:` in `~/.halo/config.json`, with custom roles switched on.

Errors are the validator's own lines, listed in the Inspector and in
Problems; a save that fails leaves the file untouched.

## Security model

- The server binds `127.0.0.1` only and refuses any request from a non-
  loopback peer.
- Every API call carries a per-launch token (the `#t=` fragment in the URL
  `halo studio` prints; the page keeps it in session storage and sends it as
  a bearer header). A request without it is a 401.
- A request carrying an `Origin` header that is not this server's own is a
  403, so a page on another site cannot drive Studio even with the port.
- **One exception to the bearer header: `/api/events`.** A browser's
  `EventSource` cannot send headers, so the live feed takes the same
  per-launch token in the query (`?t=`), compared in constant time; a
  missing or wrong token is a 403, and the loopback, Host and Origin checks
  are the same as for every other call. The token never leaves the machine
  and the response is `Cache-Control: no-store`.
- **The sessions routes (3.0.4.0).** `GET /api/sessions` lists the live
  sessions in `~/.halo/run/sessions.json`: `[{session_id, title, cwd, mode,
  kind, started, pid, status: idle|busy|waiting|unknown, busy, pending,
  model, status_age_s}]`. The status comes from each session's control
  socket (1 s timeouts, asked side by side, cached 2 s; the request waits
  at most 1.5 s). The endpoint and token are never returned. `POST
  /api/sessions/<sid>/command {cmd: answer|interrupt|steer|submit, kind?,
  request_id?, action?, instruction?, text?}` forwards one control-protocol
  request ([REMOTE.md](REMOTE.md)) to that session over its socket, using
  the token from the registry. That lets Studio answer a permission,
  question, plan or approval card in a running TUI session, steer it,
  send it a prompt or interrupt it. The answers: `{ok, result}`, 404 for a
  session not in the registry, 422 for another `cmd`, and 502 with the
  socket's own error text (for example "no pending approval request"). It
  sits behind the same bearer-token guard as every other route, so only the
  page `halo studio` opened can use it.
- **The agent routes (3.0.5.0 Fleet, `studio/fleet_api.py`).** The session
  rows also carry `harness`, `project`, `parent` and `agents` (how many
  sub-agents are working right now; the Fleet tree shows it), and a private
  session is never listed. `GET /api/sessions/<sid>/agents` is the
  session's agent tree, `GET /api/sessions/<sid>/agents/<aid>/tail?n=&kinds=`
  one agent's last entries, `POST /api/sessions/<sid>/agents/<aid>/command
  {cmd: steer|stop|pause|resume|follow, text?, mode?, reason?, on?}` acts
  on one agent, and `POST /api/sessions/<sid>/command` also takes `shutdown`
  (`reason`), `pause` and `resume` (optional `agent_id`). Studio sends `by`
  = `fleet.name` and `via` = `Studio`. The live feed passes `agent_state`,
  `agent_event` and `fleet` frames with each frame's `harness`. Shapes and
  rules: [REMOTE.md](REMOTE.md#agent-level-commands-3050-fleet),
  [SUBAGENTS.md](SUBAGENTS.md), [FLEET.md](FLEET.md).
- **The fleet routes (3.0.5.0 R2, `studio/fleet_hub_api.py`).** `halo studio
  --fleet` (or `halo fleet serve` while Studio runs) starts the fleet hub
  inside Studio's process, on its own LAN port that serves only the fleet
  protocol; this API stays on loopback. `GET /api/fleet` is every harness
  (this one first, then each member of the hub) with its sessions and agent
  trees; `POST /api/fleet/<harness>/<sid>/command` and `POST
  /api/fleet/<harness>/<sid>/agents/<aid>/command` act on this harness
  directly and on a member through the hub, as that member's owner allows
  (200, 202 `asked`, 403 refused with the reason); `GET
  /api/fleet/commands/<id>` and `POST /api/fleet/hub {action: start|stop}`.
  Member frames reach the live feed with their `harness`. See
  [FLEET.md](FLEET.md#studio-get-apifleet-and-the-commands).
- No CDN, no fonts fetched, no analytics: the page is a handful of static
  files served from the package, under a strict content-security policy.
  The shell (`static/dist/`) gets `default-src 'self'; connect-src 'self'`
  with no inline styles or scripts (a checkout without a build answers `/`
  with one line saying how to build the UI). The built bundle contains no
  `http://` or `https://` URL at all (a CI test checks).
- Writes go only to `~/.halo` (and a project's `.halo/` when you choose that
  scope); shipped files under the package are never written or deleted.

## Over SSH

On a box you reach over SSH (the usual Kali case), run `halo studio
--no-open` there, then on your machine:

```sh
ssh -L 48761:127.0.0.1:48761 <host>
```

using the port Studio printed, and open the printed URL (token included)
in your own browser.

## Shortcuts

The shell's keys: `Alt+1`..`Alt+8` sections (`Alt+1`: Session, the first row since 3.1.6.0; `Alt+7`: Packs; and Setup `Alt+8`; 3.3.2.0: the rail prints no key, the palette's Go to shows them), `Ctrl`/`Cmd`+`K` the palette,
`?` the focused panel's help (again, or away from a panel: How this works),
`Alt`+arrows / `Alt+Shift`+arrows move / resize the focused panel, `Esc`
closes. `F` (3.3.2.0) is Focus: the rail, the inspector and the status bar
hide, `F` again brings them back; where a section's own `F` follows or fits
(below), `Shift+F`. The rail's chevron (its foot) expands or collapses it. Roles (3.0.7.0 R2): on the canvas `A` lays out, `F` fits, `+` / `-`
zoom, the arrows nudge the selected card, `Del` removes it (asks first);
`Ctrl+Z` / `Ctrl+Shift+Z` undo / redo a lineup edit, `Ctrl`/`Cmd`+`S`
saves. The hop keys (3.0.5.0, [Fleet](STUDIO-fleet.md#keys-hop-around)): `J` / `K` the
next / previous live agent (Fleet map, Roles cards, Orchestra lanes), `F`
follow, `Space` pin the mini stream, `Esc` unpin, `P` pause or resume, `K`
in the Agent panel stop (asks first). Session's Live column (3.3.0.0 R6,
[steering and exporting](STUDIO-session.md#keys)): `Tab` / `Shift+Tab` in the
Steer field cycle its target among the live agents, `Escape` leaves the field
and follows again, `s` on a focused row makes it the target.

## Files

`halo_harness/studio/server.py` (the server, the guard, the command),
`events.py` (the live feed: the registry watcher and `/api/events`),
`ui/` (the React shell's sources; see docs/DEVELOPMENT.md "Studio UI"),
`static/dist/` (its committed build; the only page since 3.0.7.0 R2),
`api.py` (the routes), `roles_api.py` (`GET gym`, `GET models/best-for`, `POST models/analyze`), `roles_findings.py`
(the Problems panel's findings), `doctor_config_api.py` (`GET doctor/config`, the panel's Config group), `models_api.py` (the catalog status, Refresh, the probe), `media_api.py` / `media_render.py` (the ComfyUI
routes and a render's background thread), `sessions_api.py` (the live sessions and
their commands), `design_api.py` (the routes) with `design_artboards_api.py` / `design_assets_api.py` / `design_critique_api.py` / `design_system_api.py` / `design_export_api.py` / `design_request.py` / `design_turns.py` / `design_api_edit.py` / `design_files.py` (Design mode), `model.py` (the graph, the catalog rows, the session
reader). Tests: `tests/test_studio_api.py`,
`tests/test_studio_model.py`, `tests/test_studio_dist.py` (the build and
its routes), `tests/test_studio_live.py` (the live feed),
`tests/test_studio_media_sessions.py` (the 3.0.4.0 Media and sessions routes),
`tests/test_studio_ui.py` (headless Chrome over the shell; the Orchestra Start
view and grid through `--mode orchestra --dom` (tools/capture_orchestra.py),
and clicks and keys through `tests/helpers/studio_clarity.py` over the
DevTools protocol, `tests/helpers/cdp.py`). The Media
panels are `ui/src/routes/media/`; the Orchestra
Start view `ui/src/routes/orchestra/Start.tsx`; the help copy
`ui/src/routes/sectionHelp.ts`, `help.ts`, `help-orchestra.ts` and
`help-design.ts`. Design (3.0.7.0 R3) is
`ui/src/routes/design/` (`store.ts`, `sync.ts`: the turns over the live
feed, `actions.ts`, `Projects.tsx`, `Thread.tsx` + `ThreadParts.tsx`,
`Artboards.tsx` + `ArtboardCard.tsx`, `Assets.tsx`, `Start.tsx`,
`Dialogs.tsx`, `commands.ts`), the safe markdown `ui/src/lib/markdown.tsx`,
`styles/shared.css`, `design.css` and `design-thread.css`; tests
`tests/test_studio_design_live.py` and the Chrome checks in
`tests/helpers/studio_design.py`. Roles (3.0.7.0 R2) is
`ui/src/routes/roles/` (the store `store.ts`, `sync.ts`, the edits and the
undo history `actions.ts`, `bioActions.ts`, the canvas `Canvas.tsx` +
`CanvasParts.tsx` + `CanvasBar.tsx` + `layout.ts`, Live Roles `live.ts` +
`LiveTab.tsx`, `Replay.tsx`, the Inspector `Inspector.tsx` + `Assignment.tsx`
+ `LineupTab.tsx` + `SectionForm.tsx` + `sections.ts` + `controls.tsx`,
`Problems.tsx` + `ConfigProblems.tsx`, `Lineups.tsx`, `Bios.tsx` + `BioForm.tsx` +
`ModelPicker.tsx`, `Models.tsx`, `Start.tsx`, `Dialogs.tsx`, `keys.ts`,
`commands.ts`), `styles/roles.css` and `roles-panels.css`, the help
`routes/help-roles.ts`; tests: the DOM counts in `tests/test_studio_modes.py`
(`tools/capture_studio.py --mode roles --dom`, tools/capture_roles.py) and the
Chrome clicks in `tests/helpers/studio_roles.py`. Fleet (3.0.5.0) is
`ui/src/routes/fleet/` (the store and the feed: `store.ts`, `sync.ts`,
`streams.ts`; the panels `Map.tsx` + `MapNode.tsx` + `layout.ts`,
`Agent.tsx` + `StreamViews.tsx` + `Steer.tsx`; `FleetRail.tsx`, `Start.tsx` +
`Pair.tsx`, `Pip.tsx`, `hop.ts`, `frames.ts`, `commands.ts`, `Dialogs.tsx`),
`styles/fleet.css` and `fleet-agent.css`, the help `routes/help-fleet.ts`;
Live Roles is `frames.ts` (the live rows into the Roles store), `hop.ts`
and `replay.ts` with the Roles section's `live.ts`, `LiveTab.tsx` and
`Replay.tsx`; the
routes `fleet_hub_api.py` (R2), `fleet_pair_api.py` and `fleet_api.py`
(`get_history`), R4's `fleet_panels_api.py`, `fleet_handoff_api.py` and `fleet_recording_api.py`
over the watcher `fleet_watch.py` (what it reads: `fleet_watch_sources.py`; its feed tap:
`fleet_feed.py`; a session command: `fleet_send.py`). 3.0.6.0 R6 adds `Capabilities.tsx` + `Who.tsx` + `caps.ts` +
`MapChips.tsx`, `styles/fleet-caps.css` and `fleet_capabilities_api.py`
(tests: `tests/test_fleet_capabilities*.py`, the `caps` Chrome scenario in
`tests/helpers/studio_fleet_caps.py`). 3.0.6.0 R8 adds the Mission panel:
`Mission.tsx` + `MissionStart.tsx` + `MissionPlan.tsx` + `MissionRun.tsx` +
`MissionReport.tsx` + `MissionDialogs.tsx`, the map overlay `MapMission.tsx`,
the store `mstore.ts`, the loader `mload.ts`, the palette `mcommands.ts`,
`styles/fleet-mission.css` + `fleet-mission2.css` over R7's
`fleet_mission_api.py` (the `mission` Chrome scenario in
`tests/helpers/studio_fleet_mission.py`, its fakes in
`tests/helpers/studio_fleet_mseed.py`). Tests: `tests/test_fleet_studio_routes.py` and the Fleet
tests in `tests/test_studio_ui.py` (`tests/helpers/studio_fleet.py` over
`tests/helpers/studio_fleet_rig.py`); captures `tools/capture_studio.py
--mode fleet` (tools/capture_fleet.py).
