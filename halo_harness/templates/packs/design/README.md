# Design (design)

Prototypes, pages, decks and logos made by your own craft apps and models, on artboards in Studio: projects, a thread
of design turns, versions, comments, knobs, a design system, exports and the handoff. The Design section, as a pack
since Halo 3.3.13.0.

A Halo pack Halo ships. `HALO-PACK.md` is how to work on it; this page is how to use it. What Design does is
[docs/DESIGN.md](docs/DESIGN.md); the Studio section, panel by panel, and the pack's routes are
[docs/STUDIO-design.md](docs/STUDIO-design.md).

## Use it

```
halo pack install design
halo pack enable design --grant-all
```

Then the Design row in Studio's rail (`Alt+0` while it is the first pack section), `/design` in a session (`/design url`
prints the address), or `halo studio --mode design--design`. Projects live in the pack's data folder,
`~/.halo/packs/.data/design/projects/<slug>/`; a `~/.halo/design` from before the pack is moved there once, with one
line saying so. `halo pack disable design` takes the section away (its projects stay).

What it brings:

- Studio section `design` -- Design: the page drawn by `studio/design.js` (Projects, Design system, Assets, Artboards,
  Thread, Render, Settings)
- its routes under `/api/packs/design/design/` (`server/routes.py`)
- `/design` -- open the Design section
- a palette line: Design: open the Design section (and, while the page is up, every Design command)

## Install

It drives these apps when they are there (each is optional: without them prototypes and SVG are written by hand).
Halo never installs them; install each once and register its MCP server:

- **designcraft-cli** (NOASSERTION, https://getartcraft.com/apps/designcraft): pages, one-pagers, decks and posters
- **vectorcraft-cli** (NOASSERTION, https://getartcraft.com/apps/vectorcraft): logos, icons, illustrations and diagrams
- **photocraft-cli** (NOASSERTION, https://getartcraft.com/apps/photocraft): photo compositing, retouching and raster mockups
- **lightcraft-cli** (NOASSERTION, https://getartcraft.com/apps/lightcraft): developing and exporting photos
- **effectcraft-cli** (NOASSERTION, https://getartcraft.com/apps/effectcraft): motion graphics, animated logos and title cards
- **filmcraft-cli** (NOASSERTION, https://getartcraft.com/apps/filmcraft): video cuts, trailers and product clips
- **pdfcraft-cli** (NOASSERTION, https://getartcraft.com/apps/pdfcraft): assembling, annotating and checking PDFs

Each: the installer or build from its page, then `halo mcp add -s user <app> <app>-cli mcp`. ComfyUI comes through
`halo media init` (Halo's docs/COMFYUI.md). `halo pack doctor` names a missing one with its install line.

## Settings

`model` (the model a new project starts with; empty: the session's default) and `budget_usd` (what one design turn may
spend, US dollars; 0: no cap of the pack's own): the Design page's Settings strip, the Pack Manager's Settings, or
`halo config set packs.settings.design.model <ref>`.

## Permissions

Each one runs nothing until you grant it (`halo pack enable design --grant <name>`):

- `studio-script`: its Studio script (a bundle panel, a section's page) runs in the page
- `studio-routes`: runs this pack's Python inside Studio's server

## Files

- `pack.yaml`: the manifest: id, version, the extension API range, what it contributes, what it requests
- `commands/design.md`: the entry command /design: it opens the Design section (`studio: design`)
- `studio/design.js`: the section's page, ONE ES module built from `studio/src/` by the Studio UI's `npm run build`
  (`vite.pack.config.ts`); React and the shell's parts come from Studio (`api.lib`), never bundled
- `studio/src/`: the page's sources (TypeScript + React; `@halo/<part>` is a part of `api.lib`)
- `server/routes.py`: the pack's own Studio routes; `server/*.py` the modules they reach (the projects on disk, a turn,
  the craft apps, exports, the design system, contrast, critique, the raw files, a ComfyUI render)
- `docs/DESIGN.md`, `docs/STUDIO-design.md`: what Design does; the section and the routes
- `tests/pack_test.py`: `halo pack test`'s checks and the pack's own; `tests/test_*.py` the pack's own test modules
  (`halo pack test design` runs each); `tests/seed.py` a demo project; `tests/capture_design.py` the Studio capture
- `HALO-PACK.md`, `CHANGELOG.md`, `README.md`

## Develop it

`halo pack test design` (or `halo pack test .` in this folder) checks every part in a scratch home and runs the pack's
own tests; after a change to `studio/src/`, `npm run build` in Halo's `halo_harness/studio/ui` rebuilds `studio/design.js`
(built twice, identical). HALO-PACK.md has the loop and the rules.
