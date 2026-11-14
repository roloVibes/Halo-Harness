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
- **The agent routes (3.0.5.0, `studio/live_agents_api.py`).** The session
  rows also carry `harness`, `project`, `parent` and `agents` (how many
  sub-agents are working right now), and a private
  session is never listed. `GET /api/sessions/<sid>/agents` is the
  session's agent tree, `GET /api/sessions/<sid>/agents/<aid>/tail?n=&kinds=`
  one agent's last entries, `POST /api/sessions/<sid>/agents/<aid>/command
  {cmd: steer|stop|pause|resume|follow, text?, mode?, reason?, on?}` acts
  on one agent, and `POST /api/sessions/<sid>/command` also takes `shutdown`
  (`reason`), `pause` and `resume` (optional `agent_id`). Studio sends `by`
  = `harness.name` and `via` = `Studio`. The live feed passes `agent_state`,
  `agent_event` and `registry` frames with each frame's `harness`. Shapes and
  rules: [REMOTE.md](REMOTE.md#agent-level-commands-3050),
  [SUBAGENTS.md](SUBAGENTS.md).
- **The live routes (`studio/live_api.py`).** `GET /api/live` is this harness with its sessions and agent trees;
  `POST /api/live/<harness>/<sid>/command` and `POST /api/live/<harness>/<sid>/agents/<aid>/command` act on this
  harness's sessions (`local` or its id; another id is a 404). See
  [STUDIO-live-panels.md](STUDIO-live-panels.md#where-it-reads-and-writes).
- **The owner's page and a pack's key (3.3.14.0 R1, `studio/owner_proof.py`).** A pack's page runs in the shell's
  own page, so the writes that change what runs here (a pack's grant, enable, install, update, rollback, remove,
  service, settings; the bundles; Setup; Settings; a session started or typed into; 3.4.1.0 R4: an attention row
  answered, from Attention or the glance, `POST live/attention/answer`) also need `X-Halo-Owner`, a proof only the
  shell's own page holds; without it they are a 403, "this needs the owner's own page". What a pack's
  page embeds (an iframe, an image, a module) carries that pack's GET-only key in `?k=`, never the token
  ([the owner's page and a pack's key](STUDIO-shell.md#the-owners-page-and-a-packs-key)). No other page frames the
  shell (`frame-ancestors 'self'`, `X-Frame-Options: SAMEORIGIN`), and `HALO_STUDIO_LOG` writes `t=...` and `k=...`.
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
in your own browser. A phone does the same with an SSH app to reach the glance (3.4.1.0 R4,
[REMOTE.md](REMOTE.md#the-glance-from-a-phone)).

## Shortcuts

The shell's keys: `Alt+1`..`Alt+6` sections (`Alt+1`: Session, the first row since 3.1.6.0; `Alt+2`: Agents, 3.3.16.0; `Alt+3`: Local, 3.3.16.0 R2; then the pack's own sections on `Alt+7` to `Alt+0`; 3.3.2.0: the rail prints no key, the palette's Go to shows them), `Ctrl`/`Cmd`+`K` the palette,
`?` the focused panel's help (again, or away from a panel: How this works),
`Alt`+arrows / `Alt+Shift`+arrows move / resize the focused panel, `Esc`
closes. `F` (3.3.2.0) is Focus: the rail, the inspector and the status bar
hide, `F` again brings them back; where a section's own `F` follows or fits
(below), `Shift+F`. The rail's chevron (its foot) expands or collapses it. Roles (3.0.7.0 R2): on the canvas `A` lays out, `F` fits, `+` / `-`
zoom, the arrows nudge the selected card, `Del` removes it (asks first);
`Ctrl+Z` / `Ctrl+Shift+Z` undo / redo a lineup edit, `Ctrl`/`Cmd`+`S`
saves. The hop keys (3.0.5.0, [Keys](STUDIO-live-panels.md#keys-hop-around)): `J` / `K` the
next / previous live agent (Live, Cast cards), `f`
follow, `Space` pin the mini stream, `Esc` unpin, `P` pause or resume, `K`
in Session's Agent strip stop (asks first). Session's Live column (3.3.0.0 R6,
[steering and exporting](STUDIO-session.md#keys)): `Tab` / `Shift+Tab` in the
Steer field cycle its target among the live agents, `Escape` leaves the field
and follows again, `s` on a focused row makes it the target.

## Files

`halo_harness/studio/server.py` (the server, the guard, the command), `owner_proof.py` (the owner proof and a pack's
key, 3.3.14.0 R1; tests: `tests/test_studio_owner_proof.py`),
`events.py` (the live feed: the registry watcher and `/api/events`),
`ui/` (the React shell's sources; see docs/DEVELOPMENT.md "Studio UI"),
`static/dist/` (its committed build; the only page since 3.0.7.0 R2),
`api.py` (the routes), `roles_api.py` (`GET gym`, `GET models/best-for`, `POST models/analyze`), `roles_findings.py`
(the Problems panel's findings), `doctor_config_api.py` (`GET doctor/config`, the panel's Config group), `models_api.py` (the catalog status, Refresh, the probe), `media_api.py` (the ComfyUI
routes), `sessions_api.py` (the live sessions and
their commands), `packs_routes.py` (3.3.13.0 R2: a pack's own routes; Design's are the design pack's `server/`), `model.py` (the graph, the catalog rows, the session
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
`ui/src/routes/sectionHelp.ts`, `help.ts` and `help-orchestra.ts`. Design (3.0.7.0 R3) is the design pack's since
3.3.13.0 R2: its page's sources are `halo_harness/templates/packs/design/studio/src/`, built into its
`studio/design.js` by `vite.pack.config.ts` on the shell's own React and parts (`ui/src/packlib/`, the bundle api's
`lib`); the safe markdown is `ui/src/lib/markdown.tsx`; tests the pack's own `tests/` and the Chrome checks in
`tests/helpers/studio_design.py` (`tests/test_pack_design_ui.py`). Roles (3.0.7.0 R2) is
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
Chrome clicks in `tests/helpers/studio_roles.py`. The live pieces (3.0.5.0) are
`ui/src/routes/fleet/` (the folder keeps its name: the store and the feed, `store.ts`, `sync.ts`, `streams.ts`;
`Agent.tsx` + `StreamViews.tsx` + `Steer.tsx`; `Pip.tsx`, `hop.ts`, `frames.ts`, `commands.ts`, `Dialogs.tsx`),
`styles/fleet.css` and `fleet-agent.css`, the help `routes/help-live.ts`;
Live Roles is `frames.ts` (the live rows into the Roles store), `hop.ts`
and `replay.ts` with the Roles section's `live.ts`, `LiveTab.tsx` and
`Replay.tsx`; the routes `live_api.py` and `live_agents_api.py`
(`get_history`), R4's `live_panels_api.py`, `live_handoff_api.py` and `live_recording_api.py`
over the watcher `live_watch.py` (what it reads: `live_watch_sources.py`; its feed tap:
`live_feed.py`; a session command: `live_send.py`). Tests: `tests/test_studio_live_routes.py` and the live
tests in `tests/test_studio_ui.py` (`tests/helpers/studio_live.py` over
`tests/helpers/studio_session_rig.py`).
