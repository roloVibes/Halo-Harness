# Brief D5: Halo Design, the "plus more" polish (3.0.1.0)

Worktree: the Halo-D worktree (branch `track-d`; the lead tells you its path). You draft; the
lead verifies, runs the battery and commits. Do NOT commit, do NOT push, do NOT touch
`~/.claude.json`, `~/.claude/settings.json`, the real `~/.halo`, `CHANGELOG.md` or `README.md`
(the lead writes those).

## House rules (plans/WORKER-RULES.md, non-negotiable)

- Every production file you write stays under 250 lines. Split instead of growing. A file that
  is already over the cap (`studio/api.py`, `studio/model.py`) may only gain one-line hooks.
- Tests run as `python -m tests.test_X` from the repo root (never pytest) with
  `PYTHONPATH=<worktree> BRIDGE_TEST_HOME=<a fresh scratch dir under <scratchpad>>
  BRIDGE_TEST_NO_BACKGROUND_NET=1 PYTHONIOENCODING=utf-8`.
- No safety / refusal / "for your protection" wording anywhere. No new runtime Python deps.
  No CDN, no fetched fonts (CSP `default-src 'self'`).
- Bash heredocs mangle backslashes on this host: write files with the Write tool.
- Never read `~/.claude/.credentials.json`. Never write provider keys anywhere.
- Subprocess stdout on Windows: `encoding="utf-8"`. No machine paths (account names) in any
  file you write: the privacy scan fails the build on them.

## What exists (read first)

D3 landed: `halo_harness/studio/design_api.py`, `design_api_io.py`, `design_api_turns.py`,
`design_files.py`, `static/design.js`, `design-canvas.js`, `design-panel.js`,
`design-panel2.js`, `design.css`, `tests/test_studio_design.py` (the `_Studio` server, the
fake runner set through `design_api.RUNNER`), `tools/design_demo.py`,
`tools/capture_studio.py --mode design`, `docs/STUDIO.md` "Design mode", `docs/DESIGN.md`.
The design engine: `halo_harness/design/{store,session,crafts,crafts_probe,sync,export,
controls,cli}.py`, `halo_harness/capabilities.py`. The tour: `static/palette.js` (`tour`,
`STEPS`). Read `plans/briefs/D3-studio-design.md` for the contract you are extending.

## Deliverables

### 1. Variants: "Explore N directions"

- Palette command and a button beside **Run turn** ("3 directions"). It wraps the prompt:
  "Make N directions of: <prompt>. Each is its own artboard named <base>-a, <base>-b, <base>-c
  (same kind), clearly different in layout, type and colour, all keeping the design system."
  One turn (one live turn per project stays). After it ends the canvas tiles the new artboards
  side by side and selects the first. `POST design/<slug>/run` gains an optional
  `{"variants": N, "base": "<artboard id>"}` that builds that prompt server-side so the CLI
  can use it too: `halo design run <slug> "<prompt>" --variants 3 --base hero`
  (`design/cli.py`).

### 2. Critique: a second model reviews an artboard

- `POST design/<slug>/critique` `{artboard, model?}`: a turn with ONLY `Read,Glob` as tools and
  no MCP servers (`session.run_turn(..., tools_override="Read,Glob", entries={})` -- add that
  keyword to `run_turn`, default None keeps today's behaviour), the project's model unless
  `model` is given, `max_turns` 6, and a critique skill (`design/critique.py::critique_prompt`):
  read the artboard (index.html, or render.png/.svg through Read) and system.json, judge
  hierarchy, spacing rhythm, type scale, contrast, consistency with the tokens, copy, and
  accessibility, then reply with ONE fenced ```json block: a list of
  `{"x": <0-100>, "y": <0-100>, "text": "<one sentence, what and why>", "severity": "high|medium|low"}`
  (at most 8). The server parses the first fenced json list from the result text and adds each
  as a comment pin with `"source": "critique"` and the severity in the text prefix
  (`[high] ...`); the response is `{turn, pins}` once done (run it through the same thread +
  polling as a turn; the Chat shows it as a turn whose events are the critique). Comments tab
  shows critique pins with a distinct badge; "Send comments" includes them.
- CLI: `halo design critique <slug> <artboard> [--model M]` prints the pins.
- Tests: with the fake runner emitting a `result` whose text has a fenced json list of 2 pins,
  the pins land in comments.json with the source and severities; a result with no json block
  adds no pins and the response says so in one plain sentence.

### 3. Contrast check (pure Python, no model)

- `design/contrast.py`: parse `:root { --x: <value>; }` colour tokens from an artboard's
  `index.html` (hex 3/6/8, `rgb()`/`rgba()`), and `system.json` colour tokens as a fallback;
  WCAG 2.x relative luminance and contrast ratio; pair every token whose name suggests text/
  foreground/accent/primary with every token whose name suggests background/surface/bg (name
  heuristics in one small table), report `{fg, bg, ratio, aa, aaa, aa_large}`; also a direct
  `ratio(a, b)`. `GET design/<slug>/artboard/<id>/contrast` -> `{pairs: [...], note}`. Knobs tab
  gets a **Contrast** section (a small table, failing pairs first, red/amber/green dots) that
  refreshes after a knob moves. Tests: known pairs (#000/#fff = 21, #777/#fff ~ 4.48 fails AA
  normal text), rgb parsing, the name heuristics, the route.

### 4. Assets

- `GET design/<slug>/assets` lists `assets/` (name, size, kind by extension, a data URL
  thumbnail for images under 400 KB); `POST design/<slug>/assets` `{name, data_base64}` writes
  it (name sanitised to a basename, no path separators, 15 MB cap -> 413). Rail gains an
  **Assets** list with a drop zone (drag files from the desktop onto the rail or the canvas:
  upload, then the Chat box gets "Use assets/<name> ..." appended), click an asset to insert
  its path into the prompt. Dropping an image onto a frame card appends "Place assets/<name>
  on <artboard>" to the prompt instead. Tests: upload, list, a path-traversal name is
  sanitised, the cap.

### 5. Run view with cost, and shortcuts

- `design/session.py::run_turn` logs `elapsed` seconds and `tool_calls` (count of
  `tool_use` blocks seen) in the history line; `halo design show` prints them per turn and
  Studio's History list shows "12 tool calls · 48 s · $0.03". Keep `session.py` under 250.
- Palette: every Design command has a shortcut shown in the palette (e.g. `N` new project,
  `Enter` in the box runs, `C` toggles the comment tool, `V` variants, `K` critique, `E`
  export, `F` fit) -- none may collide with the global `R/O/D/?/Ctrl+K` ones; shortcuts are
  inactive while typing in an input.
- The tour (`palette.js` `STEPS`): when the page is in Design mode, the steps are the Design
  ones (projects and artboards, the frame cards and pins, knobs and contrast, chat/variants/
  critique, export and handoff) -- five steps, plain words.

### 6. Captures and docs

- `tools/capture_studio.py --mode design-knob --out docs/media/studio-design-knob.png`: the
  demo project with the Knobs tab open and the Spacing knob moved to 48 (the frame reloaded),
  so the picture shows the knob and the changed spacing; commit the PNG. Add `"studio-design-
  knob"` to the two allow-lists in `tests/test_front_page_media.py` (grep `studio-org`).
- `docs/STUDIO.md` Design section: variants, critique, contrast, assets, the shortcuts, the
  run view line. `docs/DESIGN.md`: a "Plus more" section with the same, two lines each, and
  `critique`/`--variants` in the command list. `docs/COMMANDS.md`: the two new verbs/flags in
  the `halo design` block (the docs test checks every flag is mentioned).

### 7. Tests to run and make green

`python -m tests.test_studio_design`, `test_design_store`, `test_design_session`,
`test_design_crafts`, `test_studio_api`, `test_studio_model`, `test_studio_org`,
`test_studio_ui`, `test_docs_commands`, `test_front_page_media`, `test_privacy_scan`,
`test_invariants`, `test_offline_mode`; `node --check` on every JS file you touch; `python -m
pyflakes halo_harness/studio halo_harness/design tests/test_studio_design*.py`. New tests may
go in `tests/test_studio_design_more.py` and `tests/test_design_contrast.py`.

## Report back

Every file added or changed with its line count, the exact per-module test results, and what
you left out and why. Nothing else.
