# Prompt for the Claude Code session on Halo-Harness

Copy the block below into the session after dropping this folder at `docs/design/studio-instrument/` in the repo.

---

Apply the Studio look proposal in `docs/design/studio-instrument/`. Read `PROPOSAL.md` first, then `docs/STUDIO-redesign-brief.md`, `docs/STUDIO-shell.md` and `docs/STUDIO-sections.md`. The mock-ups are in `docs/design/studio-instrument/mockups/` (HTML is the source of truth for sizes and CSS; PNGs are for comparison).

Do it as one round with tests, in this order, one commit per step:

1. **Palette.** Add `instrument` to `halo_harness/themes/palettes.py` from the table in PROPOSAL.md §1, dark posture. Run the generator so `halo_harness/studio/ui/src/styles/tokens.css` and the terminal pick it up. Make `instrument` the Studio default (replace `holo` only if the maintainer says so; otherwise add it and switch the default). The per-palette contrast test must pass with no exceptions.
2. **Derived variables.** Rewrite the derived block of `tokens.css` to PROPOSAL.md §2 (glass, glow, grid, soft tints, radii, shadow, spacing, type, motion). Keep every variable name other components already reference; add new ones rather than renaming. The no-colour-literal test over `styles/*.css` and `lib/ui/*` must still pass.
3. **Shell.** Restyle `shell/Rail` (52 px icon rail, collapsible to 176 px with labels, per-browser persistence, attention badge), `Header`, `StatusBar`, `Inspector`, `Palette`, `ThemeMenu`, `Swatch` per §3. Rail order becomes Session, Team, Roles, Fleet, Local, Orchestra, Packs, Design, Setup, Settings with two dividers. Do not change the `Alt+1..0` bindings or any `data-testid`.
4. **Components.** Restyle `lib/ui/*` per §3: Button, Kbd, Field, Surface (panel frame with corner ticks and the three faces), HudStrip/HudCell, Tabs, Menu, Dialog (with the DOES / COSTS / WRITES block), Toasts, Empty, ErrorState, Skeleton, FitMeter, WindowedRows.
5. **Map nodes and edges.** Session Map, Roles Live and Fleet Tree nodes and edges per §3 "Map node" and "Edges": top rule in the state colour, moving dash toward a working child, 10 s fade on done, failed stays until clicked, white outline for selected and linked hover. Show the resolved model id without the provider prefix on nodes and Live tags; keep the full id in the inspector.
6. **Motion.** Implement §5 exactly. Nothing animates on section load. `prefers-reduced-motion` switches every animation to an instant state swap.
7. **Checks.** Compare each section against its PNG at 1440×900 and 1280×800, and Session at 390 wide. Add or update the shell-rule tests the brief names (nothing pops on load, rail is sections only, inspector opens only on selection, Focus hides everything but the page). Rebuild the dist.

Constraints from the brief: no webfont from the network (the mock-ups load Inter and JetBrains Mono from Google Fonts for preview only; the shipped stack is the system fallbacks), no image assets for chrome, WCAG AA on every text/surface pair, no motion while nothing changes.

When a mock-up and the brief disagree, the brief wins; tell me where that happened. When something in PROPOSAL.md needs an eighteenth token or a new generator variable, say so and stop before adding it.
