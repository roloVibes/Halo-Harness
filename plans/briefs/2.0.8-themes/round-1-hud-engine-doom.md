# Halo 2.0.8 theme pack, round 1: the game-HUD status-bar engine + DOOM + the toggle contract

Repo: `<repo>` (branch master; start from HEAD after the v2.0.7.1 tag,
clean). Read `plans/WORKER-RULES.md` FIRST and follow every rule in it
(test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies.

Source of the design: `plans/ROADMAP.md` section "ADDED 2026-10-04 (rolo):
2.0.7 becomes a theme pack: DOOM, Metroid, Mario" and `plans/2.0.2-brief.md`
section G (+ "G addendum: /doom is a toggle"). Read both before coding.
This round builds the shared engine and the first skin (DOOM); rounds 2
and 3 add Metroid and Mario as skins on the same engine, so every seam
you add must be data-driven (a skin is a declaration, not a fork of the
status bar).

## What exists

- `halo_harness/theme.py`: the theme NAME registry (`VALID_THEMES`,
  precedence, `persist_theme`, `set_config_value`/`get_config_value` on
  `~/.halo/config.json`). Pure data, no Textual.
- `halo_harness/tui/theme.py`: `variables_for(name)` -> the Textual CSS
  variables for a theme name; `tui/styles.tcss` the stylesheet;
  `App.apply_theme(name)` in `tui/app.py`.
- `halo_harness/tui/widgets/statusbar.py` (`StatusBar`): one widget with
  setters for every field (phase word + clock, tool name, received chars,
  context pct, cost, balances, mode, pending permission, needs-you count,
  agents running, background activity, offline, saved usd, governor
  state, effort, new count, cwd + branch, spinner) and `_refresh_display`
  which lays them out with a width cascade.
- `/theme` in `tui/slash.py` (`_handle_theme`), the wizard Theme step in
  `tui/dialogs/init_wizard.py`, snapshot tests under
  `docs/harness/tui-snapshots/` driven by `test_tui.py`, `tests/test_theme.py`.

## Deliverables

1. **Theme names.** `doom`, `metroid`, `mario` join `VALID_THEMES` (no
   -daltonized/-ansi variants for the three; they are their own look).
   `tests/test_theme.py`'s valid-name pin is updated. All three appear in
   the wizard Theme step and in `/theme` completion with one-line
   descriptions. Only `doom` renders fully this round; `metroid` and
   `mario` resolve to a placeholder skin that is the default layout with
   their palette's accent colour, clearly marked in a code comment as
   "filled by round 2/3" -- nothing user-visible may say "not implemented".
2. **The game-HUD engine** (new `halo_harness/tui/hud.py`): a `HudSkin`
   declaration = ordered segments, each `(slot, label, glyphs, width_min)`,
   where a slot names one of the StatusBar's existing fields (tokens
   remaining / context pct / tools loaded / cost or balance / providers /
   phase face / cwd / branch / mode / needs-you / agents / effort ...), plus
   a `face` table mapping phase -> original ASCII face strings, plus
   border/panel glyph sets. `StatusBar._refresh_display` renders through
   the active skin when the theme has one (`skin_for(theme_name)`), and
   through today's layout otherwise. The width cascade still applies:
   segments drop in a declared priority order as the terminal narrows,
   and every field Halo's status bar shows today stays reachable (the
   narrowest cascade keeps phase, context pct, cost, cwd, mode).
3. **DOOM skin.** Palette from the brief (dark greys, blood reds, rust
   browns, muted greens, amber text), heavier borders on panels and
   dialogs, the bottom-HUD status bar: segmented panels in the order
   ammo -> health -> arms -> face -> armor -> keys, carrying tokens
   remaining -> context remaining percent -> tools loaded -> the face ->
   cost or balance -> providers; cwd/branch/mode/effort/needs-you/agents
   fold into the remaining segments as the skin declares. The face is an
   ORIGINAL ASCII "guy" (5 states: idle, thinking, writing, error,
   needs-you) -- draw your own, nothing copied from the game. Snapshot
   tests for every face state and for the width cascade (narrow, medium,
   wide).
4. **The toggle contract, pinned once for all three.** `/doom`, `/metroid`,
   `/mario` each: if that theme is not active, remember the active theme
   as `theme_toggle_previous` in `~/.halo/config.json` and apply the game
   theme (persisted as `theme`); if it IS active, restore
   `theme_toggle_previous` (default `claude-dark` when missing) and clear
   it. Switching from one game theme straight to another keeps the
   original non-game previous (so `/doom` then `/metroid` then `/metroid`
   returns to what was active before `/doom`). `/theme <name>` remains
   the explicit form and also records the previous when moving onto a
   game theme. The state survives a relaunch through config.json.
   One parametrised test covers all three names.
5. **Docs**: docs/HANDBOOK.md themes section (the three names, the
   toggles, the HUD fields table for DOOM), docs/SLASH-COMMANDS.md (three
   entries), docs/CONFIG.md (`theme_toggle_previous`), CHANGELOG
   `## [2.0.8] - unreleased` with "### Theme pack: the game-HUD engine and
   DOOM". `scripts/screenshots.py` gains a `theme-doom` scene (the main
   screen under the DOOM theme) rendered to `docs/screenshots/`; the README
   themes section gets the DOOM render and placeholders rows for Metroid
   and Mario that rounds 2/3 replace (no broken image links: omit the
   image until it exists).

## Hard constraints

Original Unicode/ASCII art only, inspired by the games; no ripped sprites,
sounds, logos or copyrighted strings in the repo (it is public). Theme
names stay exactly `doom`, `metroid`, `mario`. No safety or refusal
language; no real paths or names; no new dependency; never block the UI
thread; the status bar must still render in an 80-column terminal and in
`-ansi`-class terminals (fall back to ASCII box glyphs when
`supports_truecolor` is false). Every file write <= 250 lines (split
hud.py into hud.py + hud_doom.py if needed).

## Verification before hand-back

New modules' tests (`tests/test_hud_engine.py`, `tests/test_theme_toggles.py`,
snapshot pins in `test_tui.py`), `tests.test_theme`, every touched
module's tests, `python test_bridge.py`, `python test_tui.py` once
(commit the NEW snapshots; revert any unintended change to existing ones
and say so), `python -m tests.test_invariants`,
`python -m tests.test_privacy_scan`, `python -m tests.test_docs_slash_commands`,
`python -m tests.test_docs_commands`, `python -m halo_harness audit privacy`,
and `python -m pyflakes halo_harness/ bridge.py | grep "undefined name"`
printing nothing. Hand back RESULT LINES (1-5), FILES TOUCHED, WHAT YOU
FOUND (the skin declaration shape rounds 2/3 must follow, in ten lines).
No commit, no push.
