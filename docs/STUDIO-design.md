# Studio: Design mode

Read this when you make prototypes, pages or decks with Studio's Design section on your own creative apps.

Part of [Halo Studio](STUDIO.md), which lists every part.

## Design mode: prototypes, pages and decks on your own apps

Design (`Alt+5`, `halo studio --mode design`, `/design`) is a React section of
the shell since 3.0.7.0, over `halo design` projects under
`~/.halo/design/<slug>/`. With no project yet it is one **Start view**: what
Design mode is, the steps, and one button: name the first project and
**Create project** (a project made elsewhere shows up within 4 s).

![Design mode: the Launch page project](media/studio-design.png)

| Panel | What it is |
|---|---|
| **Projects** (`design-projects`) | Every project with its artboards and model; click one to open it; **New project** (a dialog: a name and, if you like, its model from the model select); 3.1.4.0: the open project's model on top, in the same select, saved at once (`PUT design/<slug>/model {model}`; its first option keeps the default model) |
| **Design system** (`design-system`, 3.0.7.0 R3b) | The project's token sheet (`system.json`): the tokens by group (colours, type, spacing, radii), a colour with its swatch, each value editable with **Save tokens**; the components and the sources; **Sync** from a folder path or a web page |
| **Assets** (`design-assets`) | The project's `assets/`: **Add files...** or drop files on the panel (uploaded as base64, 15 MB each); click a row to put its path in the message; **Download** saves it through `/design-files/<slug>/_assets/<name>` |
| **Artboards** (`design-artboards`) | The artboards as cards on a canvas: the frame (a prototype in `<iframe sandbox="allow-scripts">`, a render as an image, a video, else a link), its open comment pins (click one: its text and **Resolve**), the version slider with **Restore**, then **Knobs (N)**, **Critique**, **Contrast**, **Rename**, **Delete** (asks first) and **Download**; double-click a prototype's text to edit it; the toolbar has **Select / Comment**, the device select, zoom, Fit, **Export...** and **Handoff**; its settings face (the title bar's ... menu, Settings) holds the device and the knobs |
| **Thread** (`design-thread`) | The project's turns as one thread: what you asked, the model's reply as markdown, cost, tool calls, seconds and the versions it made; the running turn streams at the bottom with a chip per tool call; the **Send** box (`Enter` sends, `Shift+Enter` a new line) and **3 directions** beside it, while a turn runs **Cancel turn**; **Send comments (N)** when pins are open |

**Turns over the live feed.** Every step of a turn is a `design_turn` frame
on `/api/events` (`session_id: "design:<slug>"`, data `{slug, turn, state:
started|event|done, n, event, result}`; a tool call's input is cut to one
line). While the feed is not open the page polls `turn/<id>?since=N` every
500 ms instead (the classic page's way); both fill the same slots, so nothing
shows twice. One turn runs per project at a time. **Cancel turn** is `POST
design/<slug>/turn/<id>/cancel`: the turn's child is killed, the turn ends
with code 130 and `cancelled: true`, and what it wrote so far is kept as
versions. The history keeps each turn's reply text (8000 characters).

**A safe markdown subset.** The thread renders headings, paragraphs, lists,
block quotes, code blocks, inline code, bold, italic and links (only
`http(s)` and `mailto`, opened with `rel="noopener noreferrer"`). Nothing is
parsed as HTML and no image is fetched: an image shows as its alt text.

**Artboards.** Drag a card by its title; the places are saved on the server
(`PUT /api/layout/design:<slug>`, stored as `_design-<slug>.json`, 500 ms after
the last move). **Rename** is `POST design/<slug>/artboard/<id>/rename
{name}` (the title changes; the id, files and versions stay); **Delete** is
`DELETE design/<slug>/artboard/<id>` (its folder and versions go, its open
pins are resolved; refused while a turn runs). **Critique** starts a
read-only turn (Read and Glob, no MCP servers) whose notes land as pins with a
`critique` badge (`POST design/<slug>/critique {artboard, model?}`);
**Contrast** opens the text-on-background table with ratio and AA / AAA
verdicts (`GET design/<slug>/artboard/<id>/contrast`). **Export...** asks for
folder, HTML, PNG, SVG or PDF and one artboard or all, then shows what it
wrote; **Handoff** shows the bundle's path and the command that continues
from it.

**Versions.** Every turn, knob move, direct edit and restore is a version.
The slider swaps the frame to `v<n>/...`; at an older version **Restore**
makes it the newest one.

**Knobs.** An artboard's `controls.json` knobs are sliders, colour pickers
and selects in the Artboards panel's settings face (a card's **Knobs (N)**
opens it on that artboard; a select there picks another). A change is posted
150 ms after the last move (`POST design/<slug>/control {artboard, name,
value}`): a `css:` knob rewrites the variable in the page at once and is
saved as a version (the chip says `made v3`, the frame reloads), any other
knob is kept for the next turn (`saved for the next turn`).

**Direct text edits.** A prototype's current version is framed with
`?edit=pick`: a small picker in the sandboxed frame posts `halo-design-pick`
to Studio on a double-click (the text, its element path from `<body>`, the
text node, its box). Studio opens its own inline editor on the card at that
text; **Enter** or Save reads the page's source, changes that one text node
(found by its path, else by its text when that is unique) and posts the page
to `POST design/<slug>/text-edit {artboard, html}`, saved as a new version
with the note `direct edit`; **Esc** or Cancel drops it. A text the page's
own script draws is not in its source: Studio says so, and a turn changes it.
A card's frame takes the pointer once the card is selected (click its
title).

**Comments.** Pick **Comment** in the toolbar and click a frame: a small
comment box opens at that point; **Enter** pins it (`POST design/<slug>/comment
{artboard, text, x, y}`, x and y in percent of the frame, on the newest
version). Pins are numbered per artboard; click one for its text and
**Resolve** (`POST design/<slug>/comments/resolve {ids}`). **Esc** or Select
puts the tool down. **Send comments (N)** in the Thread turns the open pins
into one turn and resolves them when it succeeds.

**The design system.** The Design system panel lists the token sheet; edit a
value and **Save tokens** (`PUT design/<slug>/system`, the whole sheet with
its components and sources kept). **Sync** reads tokens from a codebase
folder or a web page (`POST design/<slug>/sync {source}`) and merges them;
a dialog says how many tokens there are, by group, and where they came from.

**3 directions.** The Thread's **3 directions** sends the message box's text
through the same turn path as Send, with `variants: 3` and `base` (the box
beside it, the selected artboard's id by default) in the `run` body; the
server writes the prompt ("Make 3 directions of: ... named <base>-a,
<base>-b, <base>-c"), so it is not a prefix the page adds. When the turn ends
the new artboards are laid out in one row under the others (their places
saved like a drag) and the first is selected.

**Device size.** The Artboards toolbar's device select draws every prototype
at **Phone 390** (390 x 844), **Tablet 820** (820 x 1100) or **Desktop 1280**
(1280 x 800, the default), scaled to the card. The same select is in the
panel's settings face, and the choice is kept as the panel's setting in the
browser (`halo.studio.design.panel.design-artboards`).

**The raw file route and its sandbox.** Artboard files are served at
`GET /design-files/<slug>/<artboard>/<file>` (and `.../v<n>/<file>`), the
project's assets at `/design-files/<slug>/_assets/<name>`, loopback only and
confined to that folder (`..` is a 404). They carry their own
`Content-Security-Policy: default-src 'self' 'unsafe-inline' data: blob:`
and `nosniff`, not Studio's, because a prototype has inline CSS and JS. HTML
and SVG responses add `; sandbox allow-scripts` to that policy, so the
document gets an opaque origin even when it is framed without a sandbox
attribute or opened on its own; renders (PNG, PDF, MP4) keep the plain policy.
The page embeds them as `<iframe sandbox="allow-scripts">` without
`allow-same-origin`, so a prototype runs but cannot reach Studio's API or its
token. An artboard folder that is a symlink is never served.

The palette's Design group: **Design: new project**, **Design: send** (the
message box's text; with an empty box it moves the focus there), **Design:
cancel turn** (while one runs), **Design: 3 directions**, **Design: pin a
comment** (the Comment tool), **Design: preview at Phone 390 / Tablet 820 /
Desktop 1280**, **Design: export**, **Design: handoff bundle**, **Design:
send comments**, and every project by name.

![The Design section: a hero prototype and a logo mark as artboards](media/studio-design.png)

## Media: the ComfyUI panels

The palette (**Media: status**, **scan**, **models**, **quick render**)
pops the ComfyUI panels out over the Design canvas (from another section it
goes to Design first), and the Inspector's **Remove from Design** takes one
away again.

| Panel | What it shows |
|---|---|
| **Media status** | a dot that ticks green on every check (every 15 s while a Media panel is open), the ComfyUI version, the GPU's VRAM bar, the model count and the cache's age, **Scan** (reads the server's model folders and saved workflows into the cache) |
| **Media models** | tabs image / video / audio / upscale; each row is a file with its family, precision and size (and a note: a 4-step LoRA, the high- or low-noise expert); encoders, LoRAs and VAEs of the same families sit under **supporting files** |
| **Workflows** | Halo's starters and the workflows saved on the server; click one for the inputs a render can set (`*` marks a named input) |
| **Render** | the workflow, its named inputs (prompt, negative, size, seed, steps) and every node input under a disclosure, the design project and the artboard; **Render** queues it (`202`), the `media_render` frames show its progress, and the result shows inline (it is also an artboard in Design; a render over an existing artboard is its next version) |

While ComfyUI does not answer, the group is one card instead of four
panels: where Studio looked, the error, and the fix (start ComfyUI, then
`halo media init --url <its address>` or `COMFY_URL`, then **Check
again**). The models tab is remembered in your browser
(`halo.studio.media.tab`).

## Media routes (3.0.4.0)

The JSON routes behind the Media panels. Every one sits behind the
same loopback, Host, Origin and bearer-token guard as the rest of `/api/`.
Renders go to ComfyUI at `COMFY_URL`, the config's `comfy.url`, or
`http://127.0.0.1:8188` ([COMFYUI.md](COMFYUI.md)).

| Route | Answer |
|---|---|
| `GET media/status` | `{url, reachable, version, python, pytorch, gpus, registered, cache: {scanned, age_s, rows, workflows}, checked, age_s, checking}` |
| `GET media/models?kind=image-gen\|video-gen\|audio-gen\|upscale\|all` | `{kind, rows, scanned, url}` from the cached inventory |
| `POST media/scan` | `{rows, workflows, scanned, url}`: reads the server into the cache |
| `GET media/workflows` | `{workflows: [{name, source: starter\|saved}], reachable, url}` (the cache's names when the server is down) |
| `GET media/workflows/<name>/inputs?source=starter\|saved` | `{workflow, source, label, nodes}`: each node's settable inputs |
| `POST media/render {workflow, set, project, artboard}` | `202 {prompt_id, project, artboard, workflow, source}`; the render goes on in the background |
| `GET media/renders/<prompt id>` | the render's last state |

A render publishes `media_render` frames
(`session_id: "media:<prompt id>"`, data `{prompt_id, state:
queued|progress|done|error, text, project, artboard, workflow, artboards?,
error?}`) and saves each output as an artboard of the design project. A
render over an existing artboard becomes that artboard's next version.
`media/status` refreshes in the background every 15 s and never holds a
request for more than 2 s. An artboard's `url` is a `/design-files/` path.
A `.mp4` is served as `video/mp4` with no sandbox directive.
