# Halo 2.0.8 theme pack, round 2: the Metroid skin

Repo: `<repo>` (branch master; start from HEAD after round 1 `e29da72`,
clean). Read `plans/WORKER-RULES.md` FIRST and follow every rule in it
(test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies.

Design source: `plans/ROADMAP.md` section "ADDED 2026-10-04 (rolo): 2.0.7
becomes a theme pack: DOOM, Metroid, Mario", the Metroid bullet. Round 1
built the engine; this round is a SKIN DECLARATION on it. Read
`halo_harness/tui/hud.py` (HudSkin, Segment, Glyphs, SLOTS, the
`_BUILTIN_SKIN_MODULES` list, `PLACEHOLDER_ACCENTS`), `tui/hud_doom.py`
(the template), `tui/hud_render.py`, `tui/theme_games.py` (the `metroid`
palette already exists; refine it) and `tests/test_hud_engine.py` (the
width sweep every skin must pass) before writing anything.

## Deliverables

1. **`halo_harness/tui/hud_metroid.py`** registering `HudSkin("metroid",
   ...)`: added to `_BUILTIN_SKIN_MODULES`, `metroid` removed from
   `PLACEHOLDER_ACCENTS`. No StatusBar changes; if the engine needs a
   seam the DOOM skin did not, add it generically (data-driven) and pin it.
2. **The HUD, styled like the game's**: energy tanks + reserve as the
   context meter (filled/empty tank glyphs for the remaining-context
   percentage in tens, the exact number beside them), missile- and
   super-missile-style counters for turn count and tool count (the
   `new`/`throughput` and `tools` slots), the AREA NAME slot in place of
   the cwd (the cwd's last component rendered as the area label, the
   branch as its sub-label), cost/balance and providers in their own
   panels, the face slot carrying an original Samus-visor glyph set with
   the five phase states (idle, thinking, writing, error, needs-you).
   Everything today's status bar shows stays reachable (same cascade
   rule as DOOM; narrowest keeps phase, context, cost, cwd, mode).
3. **Area variants**: five palettes as selectable variants of the one
   `metroid` theme -- Crateria (blues/greys), Brinstar (greens/pinks),
   Norfair (reds/oranges), Maridia (teals), Tourian (greys). The variant
   is `theme_variant` in `~/.halo/config.json` (default `crateria`),
   settable by `/metroid <area>` (bare `/metroid` keeps the toggle
   contract from round 1 exactly) and `/theme metroid <area>`; the
   wizard Theme step offers the variant when `metroid` is picked. The
   active area's name shows in the HUD's area panel as a prefix glyph /
   accent, not as text that hides the cwd.
4. **Map-grid panels and visor input framing**: dialogs and cards under
   `metroid` get a map-grid border glyph set (original Unicode, ASCII
   fallback without truecolor); the input line gets a visor-shaped left/
   right frame (two glyphs, same fallback rule). Both driven by the skin
   declaration + `styles.tcss` classes toggled the way `hud-heavy` is.
5. **Tests + docs**: `tests/test_hud_metroid.py` (declaration shape, the
   width sweep via the shared helper, every face state, the tank meter at
   0/10/55/100 %, the five variants resolve to distinct palettes,
   `/metroid <area>` persists and the bare toggle is unchanged -- reuse
   `tests/test_theme_toggles.py`'s parametrised pins, do not duplicate
   them); snapshots `metroid-hud-face-{idle,thinking,writing,error,
   needs-you}.svg`, `metroid-hud-width-{wide,medium,narrow,compact}.svg`,
   `metroid-area-{crateria,brinstar,norfair,maridia,tourian}.svg` (the
   main screen per variant, wide) in `docs/harness/tui-snapshots/` pinned
   from `test_tui.py` the way round 1 did; `scripts/screenshots.py`
   scene `theme-metroid` -> `docs/screenshots/theme-metroid.svg`; README
   themes table: the Metroid row gets its render (Mario stays text-only);
   HANDBOOK Themes section: the Metroid HUD fields table + the variants;
   SLASH-COMMANDS `/metroid [area]`; CONFIG `theme_variant`; CHANGELOG
   `[2.0.8] - unreleased` "### Theme pack: Metroid".

## Hard constraints

Original Unicode/ASCII art only, inspired by the game; no ripped sprites,
sounds, logos, map data or copyrighted strings in the repo (it is
public); area names are plain words. Theme name stays exactly `metroid`.
No safety or refusal language; no real paths or names; no new dependency;
never block the UI thread; the bar must render in 80 columns and without
truecolor. Every file write <= 250 lines (split `hud_metroid.py` into
`hud_metroid.py` + `hud_metroid_areas.py` if needed).

## Verification before hand-back

`tests.test_hud_metroid`, `tests.test_hud_engine`, `tests.test_hud_engine_app`,
`tests.test_theme_toggles`, `tests.test_theme_toggles_app`, `tests.test_theme`,
every touched module's tests, `python test_bridge.py`, `python test_tui.py`
once (keep the NEW snapshots; revert unintended changes to existing ones
with `git checkout -- <file>` and say which), `python -m tests.test_invariants`,
`python -m tests.test_privacy_scan`, `python -m tests.test_docs_slash_commands`,
`python -m tests.test_docs_commands`, `python -m halo_harness audit privacy`,
and `python -m pyflakes halo_harness/ bridge.py | grep "undefined name"`
printing nothing. Hand back RESULT LINES (1-5), FILES TOUCHED, WHAT YOU
FOUND (any engine seam you had to add, for round 3). No commit, no push.
