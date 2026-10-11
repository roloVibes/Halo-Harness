# Brief D3: Studio Design mode (Halo 3.0.1.0)

Worktree: `C:\Users\rolo\Halo-D` (branch `track-d`). You draft; the owner's lead verifies,
runs the battery and commits. Do NOT commit, do NOT push, do NOT touch `~/.claude.json`,
`~/.claude/settings.json` or anything under `~/.halo` of the real user.

## House rules (plans/WORKER-RULES.md, non-negotiable)

- Every file you write stays under 250 lines. Split instead of growing.
- Tests run as `python -m tests.test_X` from the repo root (never pytest) with
  `PYTHONPATH=C:/Users/rolo/Halo-D BRIDGE_TEST_HOME=<a fresh scratch dir>
  BRIDGE_TEST_NO_BACKGROUND_NET=1 PYTHONIOENCODING=utf-8`. Scratch dirs go under
  `C:\Users\rolo\AppData\Local\Temp\claude\C--Users-rolo\475585f4-0b6d-4b08-a371-1b8d5350c499\scratchpad\`.
- No safety / refusal / "for your protection" wording anywhere. No new runtime Python deps.
  No CDN, no fetched fonts in the page (CSP is `default-src 'self'`).
- Bash heredocs mangle backslashes on this host: write files with the Write tool.
- Never read `~/.claude/.credentials.json`. Never write provider keys anywhere.
- Subprocess stdout on Windows: `encoding="utf-8"`.

## What exists (read these first)

- `halo_harness/design/store.py` (Project: create/open/list, artboards, discover_artboards,
  snapshot/restore, comments, controls, system, history), `design/session.py`
  (`run_turn(project, prompt, *, model, on_event, max_budget_usd, registered, runner)`:
  the `runner(cmd, cwd, env, on_line) -> code` hook replaces the subprocess in tests),
  `design/crafts.py`, `design/sync.py` (`scan_codebase`, `capture_url`, `write_system`),
  `design/export.py` (`export_project`, `handoff_bundle`), `design/cli.py`,
  `tests/test_design_store.py`, `tests/test_design_session.py` (the fake runner pattern).
- `halo_harness/capabilities.py` (`best_for(rows, "design")`) and `studio/model.py`
  (how the model picker rows are built with capability chips).
- Studio: `studio/server.py` (`_api` dispatches `/api/...` to `studio/api.py::dispatch`,
  `_static` serves `studio/static/`, loopback + token + Origin guard in `_guard`),
  `studio/api.py` (`Request`, `ROUTES`, the `pc/` branch at the top of `dispatch` is the
  pattern for a mode's own module), `studio/paperclip_api.py` (`dispatch_pc`), the page:
  `static/index.html` (the `.mode-toggle` Roles|Org buttons), `static/app.js`
  (`app.setMode`, `localStorage halo-studio-mode`, the `?mode=` query), `static/org.js`
  (how a mode enters/leaves, redraws the rail, swaps the inspector tabs), `static/api.js`,
  `static/inspector.js` (the `h/esc/field/input/select/textarea/problems` helpers),
  `static/palette.js`, `static/studio.css` (the `--bg/--panel/--accent...` variables, the
  light theme under `:root[data-theme="light"]`).
- Tests: `tests/test_studio_org.py` (the in-process `_Studio` server + `call()` helper),
  `tests/test_studio_ui.py` (headless Chrome smoke, skipped without Chrome),
  `tools/capture_studio.py` (seeded home -> docs/media/studio.png).

## Deliverables

### 1. `halo_harness/studio/design_api.py` (+ `design_api_turns.py` if needed for the cap)

`dispatch_design(req)` wired from `studio/api.py::dispatch` exactly like `pc/`
(`if req.path == "design" or req.path.startswith("design/")`). Routes (all JSON, all behind
the existing guard):

- `GET design/projects` -> `{projects: Project.list()}`; `POST design/projects` `{name, model}`
  -> 201 `{slug}`; `GET design/models` -> the design ranking (`capabilities.best_for` over
  the catalog rows `studio/model.py` already builds; top 12 with reasons).
- `GET design/<slug>` -> `{meta, artboards, comments, system, history, live_turn}`.
- `POST design/<slug>/run` `{prompt, model?, budget?}` -> `{turn}`; one live turn per project
  (409 with a plain sentence otherwise). The turn runs in a thread: `session.run_turn(...,
  on_event=<append to the turn's event list>, runner=RUNNER)` where `RUNNER` is a module
  global (None in production; tests set it to a fake). `GET design/<slug>/turn/<id>?since=N`
  -> `{events: events[N:], done, result}` (the page polls every 500 ms while live; no SSE).
- `POST design/<slug>/comment` `{artboard, text, x, y, path}`; `POST design/<slug>/comments/resolve`
  `{ids}`; `POST design/<slug>/control` `{artboard, name, value}` -> applies the knob
  IN PLACE without a model call: for a `css:--name` target rewrite that variable's value
  in `index.html`'s `:root { ... }` block (helper `apply_css_control(html, var, value) -> html`
  in `halo_harness/design/controls.py`, tested), then `project.snapshot(note="knob <name>")`;
  for a `craft:` target return 202 `{queued: true}` and leave it to the next turn.
- `POST design/<slug>/text-edit` `{artboard, html}` -> writes `index.html` (direct text edits
  from a contenteditable frame), snapshot note "direct edit".
- `GET design/<slug>/artboard/<id>/versions` -> `[{version, created, note}]`;
  `POST design/<slug>/artboard/<id>/restore` `{version}`.
- `POST design/<slug>/sync` `{source}` (a path or a URL; the URL path uses
  `capture_url` whose default fetch goes through `providers.http.urlopen_tls`; in tests pass
  a path only). `POST design/<slug>/export` `{as, artboard?}` -> `{lines}`;
  `POST design/<slug>/handoff` -> `{path}`.
- Errors: unknown slug 404 `{error}`; validation 422 `{error, problems: [...]}`.

### 2. The raw artboard file route in `studio/server.py`

Artboard files cannot go through `_api` (JSON) and must not inherit Studio's CSP (a
prototype has inline CSS/JS). Add `GET /design-files/<slug>/<artboard>/<file>` in
`do_GET` before `_static`: loopback only (like `_static`), path confined to
`design_root(state_dir)/<slug>/artboards/<artboard>/` (resolve + parents check, 404
otherwise; also serve `v<n>/<file>` for the version slider), mime by extension, headers
`Content-Security-Policy: default-src 'self' 'unsafe-inline' data: blob:` and
`X-Content-Type-Options: nosniff`. The page embeds it as
`<iframe sandbox="allow-scripts" src="/design-files/...">` (no `allow-same-origin`, so the
prototype cannot reach Studio's API or token). Keep server.py under 250 lines: move the
helper into `studio/design_files.py` if needed.

### 3. The page: `static/design.js` + `static/design-panel.js` + `static/design.css`

- A third button in `.mode-toggle`: `Roles | Org | Design` (keys R / O / D; `?mode=design`;
  remembered like the others). `app.setMode("design")` enters `window.designMode.enter(app)`
  and leaving restores the Roles state exactly as the Org branch does.
- **Rail:** Projects (list + "New project" with name and a model select opened on the design
  ranking with the capability chips), Artboards of the open project (id, kind, app badge,
  latest version), Design system summary (token groups with counts; a "Sync from..." input
  taking a path or URL).
- **Canvas:** while in Design mode the SVG canvas is hidden and a DOM layer `#design-canvas`
  (pan with space-drag or middle button, zoom with Ctrl+wheel, fit button) shows each
  artboard as a frame card: title row (title · kind · app · v<n>), the frame (an
  `<iframe sandbox="allow-scripts">` for an HTML artboard, `<img>` for `render.png/svg`, a
  link card for pdf/mp4), a device-frame select per card (phone 390, tablet 820, desktop
  1280 wide; the iframe scales to fit the card), a comment overlay: clicking the frame with
  the comment tool pins a comment (x,y as % of the frame) and opens the text box; pins are
  numbered dots; a version slider under the card (range over versions, swapping the frame's
  src to `v<n>/...`; the current version is the right end; a "Restore this version" button
  when not at the end). Layout: cards left-to-right with wrap, draggable positions kept in
  `localStorage` per project (nothing else persisted client-side).
- **Panel (right, replaces the inspector tabs in this mode):** tabs
  `Chat | Comments | Knobs | System | Export`.
  Chat: the prompt box (Enter sends, Shift+Enter newline), a model override select, the
  turn's streaming events as cards (assistant text as prose, `tool_use` as a compact card
  with the tool name and the first 80 chars of input, `result` with cost), a running cost
  line for the project (sum of history), and the history list (prompt, cost, versions).
  Comments: open pins grouped by artboard with Resolve, and **Send comments** which turns
  every open pin into one prompt ("Address these comments: ...") and runs a turn, then
  resolves them on success. Knobs: the selected artboard's `controls.json` as sliders /
  colour inputs / selects, debounced 150 ms to `POST control`, the frame reloads after
  the response; a hint when an artboard has none ("ask for knobs in a turn: 'add knobs for
  spacing and the accent colour'"). System: the tokens by group (editable values, saved
  with a Save button via a `PUT design/<slug>/system` route you add), sources, components.
  Export: buttons for folder / html / png / svg / pdf (+ artboard filter) showing the
  returned lines, and **Handoff bundle** showing the path with a copy button.
- **Direct text edits:** an "Edit text" toggle on an HTML artboard card reloads the frame
  with `?edit=1`; the raw file route, when `edit=1`, injects a tiny script at the end of
  the body that sets `document.body.contentEditable = true` and posts
  `{type: "halo-design-edit", html: document.documentElement.outerHTML}` to the parent on
  Ctrl+S / blur (postMessage; the parent checks `event.source === frame.contentWindow`
  and saves through `POST text-edit`). Note the injected script must strip itself from the
  posted HTML (wrap it in a marker comment and remove it before saving).
- **Palette:** Design actions registered in `palette.js`'s list when in Design mode: New
  project, Run a turn, Send comments, Sync design system, Export folder, Handoff, Fit canvas.
- **Look:** the Studio variables, cards with the same radius/border, a dot-grid canvas
  background, the comment pins in `--accent`, the device frame as a thin rounded border,
  150 ms transitions, keyboard focus rings, ARIA labels on the frame cards and pins. Light
  theme must look right too.
- **Empty states:** no project -> a centred card "Design, on your own apps" with a one-line
  description and the New project form; a project with no artboards -> a prompt
  suggestion list (three example prompts as buttons that fill the box).

### 4. Tests: `tests/test_studio_design.py`

Over the in-process server (copy `_Studio` from test_studio_org.py), scoped home, with
`design_api.RUNNER` set to a fake runner (copy the one in test_design_session.py) that
writes an `artboards/hero/index.html` containing `:root{--space:16px}` and a
`controls.json`: projects create/list/get; run -> poll `turn` until done -> the events
arrived in order and the artboard has v1; comment + resolve; control applies to the html
(`--space:24px` present, v2 exists); text-edit saves v3; versions list and restore;
`PUT system`; export folder returns a path that exists; handoff returns a path with
HANDOFF.md; the raw file route serves `index.html` with the sandbox CSP header, serves
`v1/index.html`, 404s on `..` and on an unknown slug, 403s from a non-loopback peer is
not testable so skip; the guard: a wrong token gets 401 on `design/projects`; a second
`run` while one is live gets 409 (use a runner that blocks on a threading.Event). Add
`halo_harness/design/controls.py` unit checks (replaces an existing value, adds the
variable when missing, leaves other declarations alone, handles `--x : 1px` spacing).

Then run and make green: `python -m tests.test_studio_design`, `test_studio_api`,
`test_studio_model`, `test_studio_org`, `test_studio_ui`, `test_design_store`,
`test_design_session`, `test_docs_commands`, `test_invariants`, `test_offline_mode`,
`test_privacy_audit` (if present; else `python -m halo_harness audit privacy`), and
`python -m pyflakes halo_harness/studio halo_harness/design tests/test_studio_design.py`.

### 5. Capture and docs

- `tools/capture_studio.py --mode design --out docs/media/studio-design.png`: seed a demo
  project in the scratch home (`tools/design_demo.py`: project "Launch page" with an HTML
  hero artboard that uses `--space` and `--accent` tokens and ships `controls.json` with
  two knobs, plus a VectorCraft-style artboard whose `render.svg` you draw by hand (a simple
  logo mark, original), two open comments, a system.json with a few tokens, and two history
  lines), open the page with `?mode=design`, wait for the frames, screenshot at 1440x900.
  Also a `--dom` check like the existing one. Commit the PNG (the lead verifies it).
- `docs/STUDIO.md`: a "Design mode" section (what you see, the shortcuts, the knobs, the
  comment flow, direct edits, versions, exports, the handoff, the raw file route and its
  sandbox). `docs/COMMANDS.md` already documents `halo design`.
- `CHANGELOG.md` under `## [3.0.1.0] - unreleased`: bullets for Studio Design mode.

## Report back

A list of every file added or changed with its line count, the exact test results (pass /
fail counts per module, and the failing names with one line each if any), what you left
out and why. No prose beyond that.
