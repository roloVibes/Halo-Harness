# Halo 2.0.10 review, round 6: the front page redo with real graphics

Repo: `<repo>` (branch master; start from HEAD after round 5 `6edd212`,
clean). Read `plans/WORKER-RULES.md` FIRST and follow every rule in it
(test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies.

Design: `plans/2.0.9-review-privacy-brief.md` section D (rolo: "the
screenshots kinda suck"). What exists: `scripts/screenshots.py` (Textual
pilots over fixture data -> SVG under `docs/screenshots/`, pinned by
`tests/test_screenshots.py`), the README's current gallery and themes
table, `docs/harness/tui-snapshots/`, the mock upstream the TUI tests
use (`tests/helpers/`), the HUD skins, `/review`, `/remote`, `/tasks`,
the pending-card dock, the model picker with its columns. Headless
Chrome is on this host (`"C:/Program Files/Google/Chrome/Application/
chrome.exe" --headless=new --screenshot=<png> --window-size=W,H
file:///<svg>` renders an SVG to a crisp PNG; use `--force-device-scale-
factor=2` for 2x). No new Python dependency: PNG rendering goes through
Chrome when present and is skipped (SVG kept) when not.

## Deliverables

1. **`tools/capture_screens.py`** + `tools/captures.json`: one
   deterministic capture list (name, scene, size 120x40, theme, 2x) ->
   SVG via the existing pilot scenes (extend `scripts/screenshots.py`'s
   scene functions; share code, do not duplicate) -> PNG via headless
   Chrome into `docs/media/<name>.png` (SVG beside it). Scenes, all
   from mock servers (never a real key, path or hostname): (a) a turn
   with the phase line counting then the summary (claude-dark); (b) the
   pending-card dock with two queued asks; (c) the model picker with the
   data/region/speed columns; (d) `/tasks` with a running org tree;
   (e) `/mcp` with a failure reason and a connector; (f) the DOOM HUD;
   (g) the Metroid HUD (Norfair); (h) the Mario HUD; (i) `/review` cards
   with a confirmed finding; (j) the `/remote` dialog with a pending
   contact request; (k) a steer landing mid-turn. For (a) and (k) also
   an animated SVG (SMIL `<animate>`/`<set>` over the frames, 3-4
   frames, looping) at `docs/media/<name>.anim.svg` -- hand-assembled
   from the per-frame exports, no GIF library.
2. **Hand-drawn SVG diagrams** under `docs/media/diagrams/` (original,
   simple, dark-and-light safe, <= 60 KB each): how a session runs (the
   loop, tools, the event stream, the TUI); the routes (`or:`, `dbx:`,
   `local:`, `cc:`, `cx:`, `oai:` -> one session); roles and
   organizations (a lineup, an org tree, the tasks panel); the
   connectors bridge (a non-Claude model reaching Claude Docs); the
   remote-control path (phone -> Signal -> signal-cli -> bridge ->
   control socket -> session). A short hero banner SVG with the wordmark
   from the launch screen.
3. **README rewrite of the top half**: the hero banner; a one-paragraph
   pitch; install in three lines (the tagged one-liners); then "What
   makes Halo stand out" as short stories with the image beside each:
   auto mode that never interrupts; steering a running turn; watching a
   model think; the dock that cannot hide; one session across providers;
   roles and organizations running the same flow that built Halo;
   connectors reaching Claude Docs from a non-Claude model; `halo
   bugreport`; `/review`; remote control from Signal; the game HUDs. A
   comparison table against running the same models through other
   harnesses on the points that matter (config reuse, steering,
   liveness, permissions model, MCP, sessions, remote control) -- state
   facts about Halo, and for others only what their public docs say, no
   names of people. Keep every existing README section the tests pin
   (`tests/test_quickstart_docs.py`, `test_docs_links.py`,
   `test_docs_hygiene.py`, `test_hooks_lifecycle.py`, the themes table,
   the install block); the rest of the README moves below the stories.
4. **Checks**: `tests/test_front_page_media.py` -- every image the README
   references exists, is under 1 MB, and (for PNGs) came from
   `captures.json` (name match); `tools/capture_screens.py --check`
   re-renders the SVGs and compares them to the committed ones (byte-
   identical, the way `test_screenshots.py` does) and is wired into
   `tests/test_screenshots.py` or its own test; PNGs are NOT compared
   byte-wise (Chrome builds differ) -- only their existence and size.
   `docs/harness/tui-snapshots` untouched. `scripts/screenshots.py` keeps
   working for the existing gallery (its test stays green).
5. **Docs + CHANGELOG**: `docs/MEDIA.md` (how to regenerate: the two
   commands, the Chrome requirement, what is deterministic and what is
   not); CHANGELOG `[2.0.10] - unreleased` "### Front page: real captures,
   diagrams, the stories"; HANDBOOK links the diagrams where they fit
   (one line each).

## Hard constraints

No real keys, paths, hostnames, usernames or phone numbers in any
capture or diagram (mock data only; the privacy scan runs over SVGs
too). No new Python dependency; Chrome is optional tooling. Original
art only. No safety or refusal language. Every file write <= 250 lines
(the README rewrite goes in two or three Write/Edit passes; SVGs under
250 lines each or generated by the script).

## Verification before hand-back

`tests.test_front_page_media`, `tests.test_screenshots`, `tests.test_quickstart_docs`,
`tests.test_docs_links`, `tests.test_docs_hygiene`, `tests.test_hooks_lifecycle`,
`tests.test_privacy_scan`, `python -m halo_harness audit privacy`, `python
test_tui.py` once if any TUI scene helper changed shared code (revert
snapshot churn and say which), `python -m pyflakes halo_harness/ bridge.py
tools/ scripts/ | grep "undefined name"` printing nothing. Hand back
ONCE, under 60 lines, then end your run: RESULT LINES (1-5), FILES
TOUCHED (with the count and total size of docs/media/), WHAT YOU FOUND
(which captures needed a fixture change; whether Chrome rendered every
PNG; anything left open). No commit, no push.
