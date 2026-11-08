"""halo_harness.themes -- one palette set for the terminal and Studio (Halo 3.3.12.0 R1).

`palettes.py` holds the ten palettes as data in one token vocabulary; `registry.py` answers which names are valid,
what each draws in (the `-daltonized` / `-ansi` modifiers applied) and the WCAG contrast of every pinned pair.
`halo_harness/theme.py` reads its `VALID_THEMES` from here; `tui/theme.py` maps the tokens to Textual's variables;
`scripts/themes_css.py` writes Studio's `[data-theme]` blocks into `studio/ui/src/styles/tokens.css`.
R2: `packs.py` reads the enabled packs' own palettes (`<pack-id>/<id>`) live, `restore.py` keeps the theme a pack
palette replaced and writes it back when the pack goes, `studio_css.py` derives Studio's variables from the tokens.
"""
