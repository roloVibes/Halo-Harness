# Studio: a brief for a new look

Read this when you design a new look for Halo Studio, or hand the job to a design session: what Studio is made of, what a look must be expressed as, and what must not change.

Part of [Halo Studio](STUDIO.md), which lists every part.

This page is for a design session (a person, or Claude in a design session) asked to propose a new look for Halo Studio.
It says what Studio is made of, what a look must be expressed as so the harness can adopt it, and what must not change.
Read it with `docs/STUDIO-shell.md` ("Look" and the shell's rules), `docs/STUDIO-sections.md` (every section, one
paragraph each) and the captures under `docs/media/` (`hero.png`, `auto-mode.png`, `model-picker.png`, `pending-dock.png`,
`mcp-connectors.png`). The source is `halo_harness/studio/ui/src/`.

## What Studio is

A browser console for a running agent harness. One window, an icon rail of sections on the left, a header, a status bar,
and a page of panels per section. Nine sections: **Session** (this session live: the Map, Live, Cost, Agent, Activity,
Attention, Prompt), **Team** (the lineup plan), **Roles** (the lineup canvas with a Plan | Live switch -- Live is the real
agent tree), **Design**, **Orchestra** (a goal, a plan, parallel
workers, a merge, a report), **Packs** (the Pack Manager), **Setup** (pages that end in a running halo), **Settings** (every
config key from one catalog, the Themes page), **Local** (GPU and VRAM live, hosts, models, the library with a fit badge,
Hugging Face, benchmarks, the steward). The audience is one person running agents on their own hardware who wants to see
and steer every agent. Density is a feature; chrome has to earn its pixels.

## The visual direction the owner set

A Minority Report / Jarvis operations console: glass surfaces, HUD corner brackets, a cyan accent with amber as the
second accent, monospace for data and sans for prose, quiet motion that tells you something changed and then stops. "Next
level AND easy to understand": a newcomer must know what a panel is for without the help, and the help (`?`) carries the
reference text, never the panel. Rules that came from use: nothing pops up when a section loads; the rail is sections
only; the inspector opens on selection and otherwise stays out of the way; Focus (Shift+F) hides everything but the
page; one thing per section by default (more panels through the header's "+" menu); a page with several blocks is paged or
tabbed, never one long scroll; every offered action says what it does, what it costs and what it writes before it runs;
failures are one line and a path.

## What a look is, mechanically

A look is a **palette** plus **component CSS**. A palette is exactly these seventeen tokens, each a `#rrggbb` value, with a
posture (dark or light): `bg`, `bg2`, `surface`, `surface2`, `border`, `line`, `text`, `muted`, `faint`, `accent`,
`accent2`, `accent_ink`, `ok`, `warn`, `bad`, `user`, `tool`. Eleven palettes ship (`halo_harness/themes/palettes.py`;
`instrument` is the Studio default and the brand look since 3.3.15.0, `holo` before; `paper` the light default), the terminal draws from the same tokens, and Studio's
CSS variables are generated from them into `halo_harness/studio/ui/src/styles/tokens.css`. Every other colour in Studio is
a CSS variable derived from those (glass, glow, grid, soft variants), defined once in `tokens.css`; component files may
not carry a colour literal (a test enforces it). Text on surfaces meets WCAG AA (4.5:1 body, 3:1 large), enforced per
palette. Fonts: the stack is `JetBrains Mono`-class for data and `Inter`-class for prose, system fallbacks; no webfont is
loaded from the network.

The components a look restyles live in `halo_harness/studio/ui/src/lib/ui/` (Button, Dialog, Empty, ErrorState, Field,
FitMeter, HudStrip and HudCell, Icon, Kbd, Menu, Skeleton, Surface, Tabs, Toasts, WindowedRows) and the shell in
`halo_harness/studio/ui/src/shell/` (Header, Rail and RailSections, Inspector, Palette (the command palette), StatusBar,
StartHere, SectionHelp, ThemeMenu, Swatch). Panels share one frame: a title row, a glance face (one line of state) and a
detail face, a strip variant at the foot of a page, and a collapsed state. Layout is a grid the user can rearrange; the
defaults per section are code, the user's changes are saved per browser.

## What a proposal should contain

1. A **palette** for the new look in the seventeen tokens (dark posture; a light twin is welcome), with the contrast
   ratios of text on each surface.
2. The **derived variables**: glass, glow, grid, soft tints, border radii, the shadow scale, the spacing scale, the type
   scale (sizes for title, body, data, caption), the motion rules (durations, easing, what moves and what never does).
3. **Component specs** for the list above: states (rest, hover, focus, active, disabled, selected, busy), the panel
   frame in its three faces, the inspector, the rail with its selected and attention states, the header, the status
   bar, the toast, the dialog, the palette, the Kbd chip, the fit meter, the HUD strip.
4. **Section mock-ups** for at least Session, Roles (Live), Local and Packs at 1440 x 900 and 1280 x 800, plus a phone
   width for Session: what the one-thing-per-section default looks like, what Focus looks like, what the "+" menu adds.
5. **Motion**: a short description or a prototype of the three or four animations that carry meaning (an agent starting
   and ending on the tree, a receipt ladder climbing, the fit meter filling, a toast arriving) and the rule for everything
   else (none).
6. The **why**: one page on what the new look says about the product that the current one does not.

## What must not change

- Section and panel names, keyboard shortcuts (Alt+1..0, Shift+F, the palette's key), the `data-testid` attributes and
  the information on each panel: the look restyles, it does not rearrange features. A proposal to add or remove a panel
  is welcome as a separate note, not folded into the look.
- The token vocabulary (seventeen names) and the rule that colours live only in `tokens.css`. A look that needs an
  eighteenth token says so explicitly; the harness can add one with a generator change.
- Readability at 1280 px wide and on a phone for Session; WCAG AA; no webfont from the network; no image assets for
  chrome (SVG inline is fine); no motion that runs while nothing changes.
- The quiet-shell rules above.

## How a proposal lands

The palette becomes one more entry in `palettes.py` (or replaces `holo`'s values if it is the new brand); the derived
variables and component CSS become one round of work on `tokens.css`, `styles/*.css` and `lib/ui/*`; the generator keeps
the terminal in step. Hand the proposal back as a folder of mock-ups (PNG or HTML), the palette table, and the component
spec; the maintainer turns it into a round with tests that pin the contrast, the dist and the shell's rules.

## What shipped

3.3.15.0 L1 applied the first proposal made from this brief, "Instrument" ([design/studio-instrument/](design/studio-instrument/PROPOSAL.md)):
the `instrument` palette as Studio's dark default, the derived variables, the shell and `lib/ui` restyled, map nodes and
edges, and the four-animation motion rule ([STUDIO-shell.md](STUDIO-shell.md), "Visual language" and "Motion"). The rail
order the proposal suggested was not taken.
