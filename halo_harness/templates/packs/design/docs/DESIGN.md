# Design

Read this when you make designs, pages, decks or logos with the design pack on your own apps.

Halo 3.0.1.0 made it, as Halo Design; since Halo 3.3.13.0 it is the **design pack**: Halo ships it and you turn it on
(`halo pack install design`, `halo pack enable design --grant-all`). Designs, prototypes, pages, decks, logos, photo
work, motion and video, made by a model you choose, on the creative apps already on your machine. It is a section of
Halo Studio (the first pack section, `Alt+0`, while the pack is on), `/design` in a session, and the pack's own routes
(`/api/packs/design/design/...`). Nothing leaves your machine except the model calls you already make with Halo.

## The model

A **project** is a folder in the pack's data folder, `~/.halo/packs/.data/design/projects/<slug>/` (before the pack it
was `~/.halo/design/<slug>/`; the pack moves that folder once and says so in one line):

| path | what |
|---|---|
| `design.json` | name, created, the project's model, the artboard list |
| `artboards/<id>/` | an artboard's CURRENT files |
| `artboards/<id>/v<n>/` | a snapshot after each turn that changed it (versions) |
| `comments.json` | pinned comments: artboard, x/y as percentages, text, resolved |
| `assets/` | uploads, captures and exports from the craft apps |
| `system.json` | the design system: tokens by group, components, where they came from |
| `history.jsonl` | one line per turn: prompt, model, cost, the versions it made |

An **artboard** is one of two things:

- a **web prototype, page or deck**: `index.html`, self-contained (inline CSS and JS, no CDN), reading the design
  tokens as CSS variables on `:root`;
- a **craft render**: `render.png`, `render.svg`, `render.pdf` or `render.mp4` saved by the app's own export tool, plus
  `source.json` naming the app, the saved document, the kind and a title.

Either may carry `controls.json`, the knobs a person moves without a model call:

```json
[{"name": "Spacing", "kind": "range", "target": "css:--space", "min": 0, "max": 64, "step": 1, "value": 16},
 {"name": "Accent", "kind": "color", "target": "css:--accent", "value": "#89b4fa"}]
```

A `css:` target rewrites that variable in `index.html` in place and versions the artboard. A `craft:<tool>:<param>`
target is queued for the next turn.

## A design turn

The Thread panel's Send (the pack's `POST <slug>/run {prompt}`) is one headless Halo turn (`halo -p`, through
`ext.host.halo_command()`) in the project folder, on the project's model (else the pack's setting `model`, else the
session's), with the file tools and every registered craft app allowed as tools, and the Design skill appended to the
system prompt. The skill carries the artboard contract above, the recipe per craft app, the design system's tokens and
components, the open comments and the artboards already there. When the turn ends every changed artboard gets a new
version and the turn is logged with its cost. A turn's cap is the request's `budget`, else the pack's `budget_usd`.

The craft apps are the seven ArtCraft MCP servers and ComfyUI, each registered as an MCP server a session sees, so a
Halo session already has their tools (ComfyUI is registered by `halo media init`, see Halo's docs/COMFYUI.md). The
pack's `requires:` names the seven with their install lines; `halo pack doctor` says which are missing here:

| app | for | render step |
|---|---|---|
| DesignCraft | pages, one-pagers, decks, posters | `export_png`, PDF |
| VectorCraft | logos, icons, illustrations | `export` SVG / PNG |
| PhotoCraft | compositing, retouching, raster mockups | `doc_export` PNG |
| LightCraft | developing and batch-exporting photos | `export` |
| EffectCraft | motion graphics, animated titles | `render_frame` |
| FilmCraft | video cuts, trailers, product clips | `render_frame`, `render_preview` |
| PdfCraft | assembling, annotating, signing, checking PDFs | `page_render`, `doc_save` |
| ComfyUI | generated stills, image-to-video clips, upscales from local diffusion models | `comfy_run`, then `comfy_fetch` to `render.png` / `render.mp4` |

`GET crafts` (the pack's route) says which are registered; `GET crafts?probe=1` starts each one, counts its tools and
checks the render tool is there. An app that is not registered is simply left out of the skill: prototypes and SVG are
still written by hand.

### What the apps add, and what works without them

Design needs none of the apps. A turn attaches only the craft servers that are registered; with none, the model writes
`index.html` and SVG by hand, and every Studio feature (frames, knobs, comments, versions, variants, critique,
contrast, exports, the handoff) works on that. The apps change what a turn can *deliver* and how reliably:

- **Real documents, not approximations.** A model can write SVG; it cannot write a layered PSD, a print-ready PDF, a
  developed RAW or an MP4. Through the MCP it drives the engine that can, and the artboard's `source.json` names the
  saved document, which opens in that app afterwards.
- **Commands with undo instead of guessed markup.** Each app exposes its full command list as typed tools.
- **Inspection in the loop.** The apps return the document state, so the model checks its work mid-turn and fixes it.
- **The render is the app's own**, at the scale you asked, with selectable text in PDFs.
- **Local.** The servers run headless on your machine; only the model call leaves it.

## Which model

Any model Halo can reach, chosen per project (the New project dialog, the Projects panel's model select) or for every
new project (the pack's Settings panel: `model`). The model select ranks the catalog for the job (`ext.host.models
("design")`: vision, context, tool support, price, speed); `halo models --best-for design` says the same in a terminal.

## Refining

- **Thread**: the next prompt. The model sees the artboards it already made.
- **Comments**: pick **Comment** on the Artboards toolbar and click a spot on a frame: a comment box opens there and
  Enter pins it. Click a pin for its text and Resolve. "Send comments" turns the open pins into the next prompt and
  resolves them when the turn succeeds.
- **Knobs**: the sliders, colour pickers and selects from `controls.json`, in the Artboards panel's settings (a card's
  **Knobs** button opens them), live, no model call: a `css:` knob is applied at once and saved as a version, any other
  waits for the next turn.
- **Direct text edits**: double-click a text in an HTML artboard (select the card first): an editor opens on it; Enter
  saves the page as a new version, Esc cancels.
- **Device size**: prototypes at phone (390 x 844), tablet (820 x 1100) or desktop (1280 x 800) size.
- **Versions**: a slider per artboard; **Restore** brings one back.

## Design systems

The Design system panel's **Sync** (the pack's `POST <slug>/sync {source}`) writes `system.json` with provenance:

- a **codebase**: CSS custom properties (grouped into colors, typography, spacing, radii, shadows), a
  `tailwind.config.*` `theme.extend`, `tokens.json` / `*.tokens.json` (W3C design tokens), and component names from
  `components/`, `ui/`, `src/components/`, `app/components/`;
- a **URL**: the page's inline and linked stylesheets (fetched through Halo's one network door, `ext.host.fetch`);
- images and documents dropped into `assets/` are read by the model in a turn.

Syncing again merges. Nothing is guessed: a token not in a source is not written. The panel lists the tokens by group
(a colour with its swatch) and edits a value (**Save tokens**).

## Exports and the handoff

**Export...** writes a static site with an index page (every artboard, shareable as is), or copies the prototypes or
renders as HTML, PNG, SVG or PDF; a PDF of an HTML artboard is asked for in a turn ("export hero as a PDF through
PdfCraft"). **Handoff** writes a bundle: the artboards' current files, `system.json`, `assets/` and a `HANDOFF.md` that
a Halo or Claude Code session continues from (`halo --cwd <the bundle> "continue from HANDOFF.md"`).

## Plus more

- **Directions**: the **3 directions** button beside Send makes hero-a, hero-b, hero-c in one turn, clearly different
  in layout, type and colour, all keeping the design system (the `run` body's `variants` and `base`).
- **Critique**: a read-only turn (Read and Glob, no MCP servers, six turns) judges hierarchy, spacing, type scale,
  contrast, token use, copy and accessibility; each note becomes a comment pin marked `critique` with its severity.
- **Contrast**: WCAG ratios for every text-like colour token on every background-like token, read from the artboard's
  `:root` (the design system fills gaps). No model call.
- **Assets**: the project's `assets/` folder; drop files on the panel (15 MB each), put `Use assets/<name>` in the
  prompt, download each one.
- **Render**: a ComfyUI workflow into an artboard of the project (the Render panel, the pack's `POST render`).
- **Run view**: each history line records tool calls and seconds beside the cost.

## Studio

Open it with the rail's Design row, `Alt+0` while it is the first pack section, `/design` in a session (`/design url`
prints the address), or `halo studio --mode design--design`. [STUDIO-design.md](STUDIO-design.md) is the section,
panel by panel, and the pack's routes.
