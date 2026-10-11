# Halo 2.0.8 theme pack, round 3: the Mario skin

Repo: `<repo>` (branch master; start from HEAD after round 2 `4f39d27`,
clean). Read `plans/WORKER-RULES.md` FIRST and follow every rule in it
(test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies.

Design source: `plans/ROADMAP.md` section "ADDED 2026-10-04 (rolo): 2.0.7
becomes a theme pack: DOOM, Metroid, Mario", the Mario bullet. Rounds 1
and 2 built the engine and two skins; this round is the third SKIN
DECLARATION. Read `halo_harness/tui/hud.py` (HudSkin incl. the round 2
seams: meter_cells, variants, panel_border, input_frame, the `turns` and
`area` slots; `_BUILTIN_SKIN_MODULES`, `PLACEHOLDER_ACCENTS`),
`tui/hud_doom.py` and `tui/hud_metroid.py` (templates), `tui/hud_render.py`,
`tui/theme_games.py` (the `mario` palette exists; refine it),
`tests/helpers/hud_skin_checks.py` (the shared checks every skin runs) and
`tests/test_hud_metroid.py` before writing anything.

## Deliverables

1. **`halo_harness/tui/hud_mario.py`** registering `HudSkin("mario", ...)`:
   added to `_BUILTIN_SKIN_MODULES`, `mario` removed from
   `PLACEHOLDER_ACCENTS` (which then becomes empty -- keep the mechanism,
   it is the placeholder path for any future theme). No StatusBar changes
   unless a generic seam is missing; if so add it data-driven and pin it.
2. **The HUD, styled like the game's top bar**: a coins panel for cost
   (coin glyph + the cost, the balance beside it), a timer-style clock
   for the phase clock (`elapsed` slot, counting UP while a turn runs,
   idle shows the last turn's time), a WORLD/LEVEL slot for the cwd
   (`area` slot: the cwd's last component as the "world" label and the
   branch as the "level"), a score-style panel for tokens (tokens
   remaining as the score), lives-style counters for turns (`turns`) and
   tools (`tools`), the face slot carrying an original five-state ASCII
   face (idle, thinking, writing, error, needs-you). Everything today's
   status bar shows stays reachable (same cascade rule: narrowest keeps
   phase, context, cost, cwd, mode); 80 columns keeps coins, timer and
   world.
3. **Two palettes as variants** of the one `mario` theme: `bros` (Super
   Mario Bros: sky blue, brick red, pipe green, coin gold) and `world`
   (Super Mario World: brighter sky, question-block orange, cape-feather
   yellow, pipe green). Default `bros`. Set by `/mario <variant>` and
   `/theme mario <variant>`, the wizard Theme step offers them when
   `mario` is picked, `halo config set theme_variant` validates, bare
   `/mario` keeps the round 1 toggle contract exactly. Reuse
   `theme.GAME_VARIANTS` / `theme_toggle.set_game_variant` from round 2.
4. **Brick and pipe motifs + 1-up/coin cues**: cards and dialogs under
   `mario` get a brick-pattern border (a glyph set via `panel_border`,
   ASCII fallback) and the input line a pipe-shaped frame via
   `input_frame`; when a sub-agent finishes or a background job completes,
   the status bar flashes a short original "1-UP"/coin cue in the face
   slot for ~2 s (engine seam: `HudSkin.cues` = {event: frames}, a timer
   driven by the StatusBar, no-op for skins without cues; the TUI's
   existing agent/job completion event is the trigger -- find it in
   `tui/dispatch.py`). No sounds, ever.
5. **Tests + docs**: `tests/test_hud_mario.py` (the shared checks, every
   face state, the coin/timer/world fields in a real bar, the two
   variants resolve to distinct palettes, `/mario <variant>` persists and
   the bare toggle is unchanged, the 1-up cue shows and clears, cues are
   a no-op for DOOM/Metroid); snapshots `mario-hud-face-{idle,thinking,
   writing,error,needs-you}.svg`, `mario-hud-width-{wide,medium,narrow,
   compact}.svg`, `mario-variant-{bros,world}.svg`, `mario-cue-1up.svg`,
   `mario-card-permission.svg` pinned from `test_tui.py` as round 2 did;
   `scripts/screenshots.py` scene `theme-mario` -> `docs/screenshots/
   theme-mario.svg`; README themes table: the Mario row gets its render
   (the table is then complete: three renders); HANDBOOK Themes: the Mario
   HUD fields table, the variants, the cues; SLASH-COMMANDS `/mario
   [variant]`; CONFIG (`theme_variant` now lists mario's values);
   CHANGELOG `[2.0.8] - unreleased` "### Theme pack: Mario".

## Hard constraints

Original Unicode/ASCII art only, inspired by the games; no ripped sprites,
sounds, logos or copyrighted strings in the repo (it is public); variant
names are plain words. Theme name stays exactly `mario`. No safety or
refusal language; no real paths or names; no new dependency; never block
the UI thread (the cue timer is a Textual timer, not a sleep); the bar
must render in 80 columns and without truecolor. Every file write <= 250
lines (split `hud_mario.py` + `hud_mario_cues.py` if needed).

## Verification before hand-back

`tests.test_hud_mario`, `tests.test_hud_metroid`, `tests.test_hud_engine`,
`tests.test_hud_engine_app`, `tests.test_theme_toggles`,
`tests.test_theme_toggles_app`, `tests.test_theme`, every touched module's
tests, `python test_bridge.py`, `python test_tui.py` once (keep the NEW
snapshots; revert unintended changes to existing ones with `git checkout
-- <file>` and say which), `python -m tests.test_invariants`,
`python -m tests.test_privacy_scan`, `python -m tests.test_docs_slash_commands`,
`python -m tests.test_docs_commands`, `python -m halo_harness audit privacy`,
and `python -m pyflakes halo_harness/ bridge.py | grep "undefined name"`
printing nothing. Hand back RESULT LINES (1-5), FILES TOUCHED, WHAT YOU
FOUND (any engine seam added; anything left open and why). No commit, no
push.
