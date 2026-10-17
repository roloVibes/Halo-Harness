# Halo Design

Halo 3.0.1.0. Designs, prototypes, pages, decks, logos, photo work, motion and
video, made by a model you choose, on the creative apps already on your machine.
It is the Design section of Halo Studio (`Alt+4`) and a command family
(`halo design`). Nothing leaves your machine except the model calls you already
make with Halo.

## The model

A **project** is a folder under `~/.halo/design/<slug>/`:

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

- a **web prototype, page or deck**: `index.html`, self-contained (inline CSS and
  JS, no CDN), reading the design tokens as CSS variables on `:root`;
- a **craft render**: `render.png`, `render.svg`, `render.pdf` or `render.mp4`
  saved by the app's own export tool, plus `source.json` naming the app, the saved
  document, the kind and a title.

Either may carry `controls.json`, the knobs a person moves without a model call:

```json
[{"name": "Spacing", "kind": "range", "target": "css:--space", "min": 0, "max": 64, "step": 1, "value": 16},
 {"name": "Accent", "kind": "color", "target": "css:--accent", "value": "#89b4fa"}]
```

A `css:` target rewrites that variable in `index.html` in place and versions the
artboard. A `craft:<tool>:<param>` target is queued for the next turn.

## A design turn

`halo design run <slug> "<prompt>"` (or the Thread panel in Studio) is one headless
Halo turn (`halo -p`) in the project folder, on the project's model, with the file
tools and every registered craft app allowed as tools, and the Design skill
appended to the system prompt. The skill carries the artboard contract above, the
recipe per craft app, the design system's tokens and components, the open comments
and the artboards already there. When the turn ends every changed artboard gets a
new version and the turn is logged with its cost.

The craft apps are the seven ArtCraft MCP servers and ComfyUI, each registered
in Claude Code's user config, so a Halo session already has their tools
(ComfyUI is registered by `halo media init`, see [COMFYUI.md](COMFYUI.md)):

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

`halo design doctor` says which are registered; `--probe` spawns each one, counts
its tools and checks the render tool is there (exit 1 when one is down). An app
that is not registered is simply left out of the skill: prototypes and SVG are
still written by hand.

### What the apps add, and what works without them

Design needs none of the apps. A turn attaches only the craft servers that are
registered in `~/.claude.json`; with none, the model writes `index.html` and SVG
by hand, and every Studio feature (frames, knobs, comments, versions, variants,
critique, contrast, exports, the handoff) works on that. The apps change what a
turn can *deliver* and how reliably:

- **Real documents, not approximations.** A model can write SVG; it cannot write
  a layered PSD, a print-ready PDF, a developed RAW or an MP4. Through the MCP it
  drives the engine that can, and the artboard's `source.json` names the saved
  document, which opens in that app afterwards.
- **Commands with undo instead of guessed markup.** Each app exposes its full
  command list as typed tools; the model lists them, executes, and can undo.
- **Inspection in the loop.** The apps return the document state (items, bounds,
  overset text, layer trees), so the model checks its work mid-turn and fixes
  it, the way it reads a file after editing code.
- **The render is the app's own.** `render.png`, `render.svg` or `render.pdf` is
  what the app exported, at the scale you asked, with selectable text in PDFs.
- **Local.** The servers run headless on your machine; only the model call
  leaves it.

| App | What Design gets from it |
|---|---|
| DesignCraft | pages, one-pagers, posters and decks laid out in frames, rendered to PNG and PDF |
| VectorCraft | logos, icons and illustrations as true vector paths, exported SVG and PNG |
| PhotoCraft | compositing, retouching and raster mockups, exported PNG |
| LightCraft | RAW photos developed and batch-exported into the project's assets |
| EffectCraft | motion graphics and animated titles, rendered frames |
| FilmCraft | video cuts and product clips, preview renders |
| PdfCraft | assembled, signed, form-filled and accessibility-checked PDFs |
| ComfyUI | images and short clips generated on your own GPU (Qwen Image, Wan 2.2), fetched into the artboard with a `source.json` naming the workflow, prompt id and `set` values |

Installed on this machine but not used by Design: DeckCraft (PowerPoint-class,
PPTX in and out), WordCraft (Word-class, DOCX, Markdown, PDF), GridCraft
(Excel-class, XLSX, charts), CADCraft and SoundCraft. The first three are the
natural next additions (decks with PPTX export, documents with DOCX, spreadsheets
as input); the last two do not belong on a design canvas.

## Which model

Any model Halo can reach, chosen per project (`--model` on `new` or `run`, or the
picker in Studio). `halo models --best-for design` ranks the catalog for the job
(vision, context, tool support, price, speed) with a one-line reason each; `visual`,
`image`, `audio` and `video` are the other rankings. See
[MODELS.md](MODELS.md) "Which model for what".

## Refining

- **Thread**: the next prompt. The model sees the artboards it already made.
- **Comments**: `halo design comment <slug> <artboard> "text" --at 40,12`, or in Studio
  pick **Comment** on the Artboards toolbar and click a spot on a frame: a comment box opens
  there and Enter pins it. Click a pin for its text and Resolve. "Send comments" turns the
  open pins into the next prompt and resolves them when the turn succeeds.
- **Knobs**: the sliders, colour pickers and selects from `controls.json`, in the Artboards
  panel's settings (a card's **Knobs** button opens them), live, no model call: a `css:` knob
  is applied at once and saved as a version, any other waits for the next turn. Ask for knobs
  in a turn ("add knobs for spacing and the accent colour").
- **Direct text edits**: double-click a text in an HTML artboard in Studio (select the card
  first): an editor opens on it; Enter saves the page as a new version, Esc cancels. A text
  the page's own script draws is changed with a turn instead.
- **Device size**: Studio draws prototypes at phone (390 x 844), tablet (820 x 1100) or
  desktop (1280 x 800) size; the select is on the Artboards toolbar and in its settings.
- **Versions**: `halo design show` lists them; `halo design restore <slug> <artboard> <n>`
  brings one back; Studio has a slider per artboard.

## Design systems

`halo design sync <slug> [PATH|URL]` writes `system.json` with provenance:

- a **codebase**: CSS custom properties (grouped into colors, typography, spacing,
  radii, shadows), a `tailwind.config.*` `theme.extend`, `tokens.json` /
  `*.tokens.json` (W3C design tokens), and component names from `components/`,
  `ui/`, `src/components/`, `app/components/`;
- a **URL**: the page's inline and linked stylesheets;
- images and documents dropped into `assets/` are read by the model in a turn.

Syncing again merges. Nothing is guessed: a token not in a source is not written.
In Studio the **Design system** panel lists the tokens by group (a colour with its swatch),
edits a value (**Save tokens**) and has **Sync** for a folder path or a web page, with a
dialog that says what it found.

## Exports and the handoff

`halo design export <slug> --as folder` writes a static site with an index page
(every artboard, shareable as is); `--as html|png|svg|pdf` copies the prototypes or
renders; a PDF of an HTML artboard is asked for in a turn ("export hero as a PDF
through PdfCraft"). `halo design handoff <slug>` writes a bundle: the artboards'
current files, `system.json`, `assets/` and a `HANDOFF.md` that a Halo or Claude
Code session continues from:

```sh
halo --cwd ~/.halo/design/launch-page/exports/<stamp>-handoff "continue from HANDOFF.md"
```

## Plus more

- **Directions**: `halo design run <slug> "<prompt>" --variants 3 --base hero` makes
  hero-a, hero-b, hero-c in one turn, clearly different in layout, type and colour,
  all keeping the design system. The **3 directions** button beside Send in Studio's Thread
  does the same (the `run` body's `variants` and `base`; the box beside it names them, the
  selected artboard by default) and lays the new artboards out in one row.
- **Critique**: `halo design critique <slug> <artboard>` runs a read-only turn (Read
  and Glob, no MCP servers, six turns) on the project's model or `--model`. It
  judges hierarchy, spacing, type scale, contrast, token use, copy and accessibility,
  and each note becomes a comment pin marked `critique` with its severity.
- **Contrast**: WCAG ratios for every text-like colour token on every background-like
  token, read from the artboard's `:root` (the design system fills gaps). No model
  call; Studio's **Contrast** button on an artboard shows the table.
- **Assets**: files in the project's `assets/` folder. Studio's Assets panel lists them,
  takes drops from the desktop (15 MB each), puts `Use assets/<name>` in the prompt and
  downloads each one.
- **Run view**: each history line records tool calls and seconds beside the cost;
  `halo design show` prints the last five and Studio's Thread shows
  "12 tool calls · 48 s · $0.03" under each turn, with the model's reply.

## Studio's Design mode

Press `Alt+4` in Studio, type `/design` in the TUI, or run `halo studio --mode design`.
Since 3.0.7.0 it is a React section: Projects, the Design system (tokens, Save tokens,
Sync), Assets, Artboards (frames: HTML in a sandboxed frame that cannot reach Studio's
API, at phone, tablet or desktop size; renders as images; double-click a text to edit it;
the Comment tool and numbered pins with Resolve; a version slider with Restore, Knobs,
Critique, Contrast, Rename, Delete, Download; Export and Handoff) and the Thread (the
turns as markdown, streamed over the live feed, with Cancel turn and 3 directions).
See [STUDIO.md](STUDIO.md).

## The command family

```sh
halo design new <name> [--model M]
halo design list
halo design show <slug>
halo design run <slug> "<prompt>" [--model M] [--budget USD] [--variants N] [--base ID]
halo design critique <slug> <artboard> [--model M]
halo design sync <slug> [PATH|URL]
halo design comment <slug> <artboard> "<text>" [--at X,Y]
halo design restore <slug> <artboard> <version>
halo design export <slug> [--as html|pdf|png|svg|folder] [--out DIR] [--artboard ID]
halo design handoff <slug> [--out DIR]
halo design doctor [--probe]
```
