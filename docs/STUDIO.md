# Halo Studio

`halo studio` opens your lineups and agent bios as an editable graph in the
browser. It is the visual front door to the same files the wizard and the
CLI edit: a lineup is `~/.halo/teams/<name>.yaml` (or `.halo/teams/` in a
project), a bio is `~/.halo/agents/<name>.yaml`, and Studio reads and writes
them through the exact functions `halo teams` and `halo agents` use. Nothing
is a second source of truth.

```sh
halo studio                 # starts a local server, opens the browser in the mode you used last
halo studio --mode roles    # straight into Roles (lineups and bios), --mode org, --mode design
halo studio --no-open       # prints the URL only (SSH, a headless box)
halo studio --port 8765     # a fixed port instead of a free one
```

Inside the TUI, `/roles`, `/org` and `/design` open Studio straight into that
mode from the live session; `/studio [roles|org|design]` is the long form and
`/studio url` prints the URL without opening a browser. A model running in a
Halo session knows this too: the system prompt names Studio, its three modes
and the command, so "open the GUI for roles" runs `halo studio --mode roles`.

## What you see

- **The rail (left):** every lineup you can reach (shipped, user, project; the
  active one marked), and every agent bio. Drag a bio onto the canvas to add
  an assignment to the open lineup.
- **The canvas:** one card per assignment -- the agent name, its role and
  alias, the model that resolves for it with price and context from the
  catalog, its tool count, a scope badge and a status dot (green valid, amber
  a warning, red a problem; hover reads the text). Edges are **delegation**
  from `main` (labelled with the routing keys that reach a member), **reports
  to** lines from the org section (dashed) and **pipeline** stage order
  (dotted). Pan by dragging, zoom with the wheel, `Shift`-drag to marquee-
  select, `A` lays the graph out again, `F` fits it. Positions are remembered
  per lineup under `~/.halo/studio/layouts/`.
- **The inspector (right):** *Assignment* (agent, role, alias, instances,
  `use_for`, a per-assignment model override), *Agent* (the bio behind the
  card: every section as typed fields, with the "about N turns at this
  price" hint next to the budget), *Lineup* (description, about, and each
  top section -- delegation, routing, budget, escalation, context,
  permissions, org, pipeline, acceptance -- as a YAML body with its
  enforcement badge), *YAML* (the whole file as it will be written; edits go
  both ways).
- **The command palette:** `Ctrl`/`Cmd`+`K` lists every action and every
  lineup and bio; `?` replays the tour.
- **Run view:** overlays the newest session's sub-agents on the cards (which
  node is running, cost so far) and a timeline strip of them. Read-only.

## Org mode: the company in Paperclip

The **Roles | Org** toggle in the top bar (`R` / `O`) swaps the canvas to
your company in [Paperclip](PAPERCLIP.md). Agents are cards (title, role,
adapter, status, spend against budget), reporting lines are the edges, and
dragging a card onto another makes it report there (a confirm, then a
`PATCH` of the agent's `reportsTo`). The rail lists the agents and the
company's goals and projects; the inspector has **Agent** (title, role,
reports-to, budget; Wake, Pause / Resume, Terminate; the adapter it runs),
**Issues** (the agent's issues, or all of them; create one, which wakes
its assignee), **Paperclip** (the agent's own Paperclip page embedded, with
"open" for a full tab) and **Company** (stats, **Sync lineup -> company**,
**Pull reporting lines -> lineup**, "Open Paperclip").

Studio talks to Paperclip through its own server (`/api/pc/...`), which adds
the board token from `~/.halo/paperclip.json` server-side; the page never
holds it. When Paperclip is not installed the Org canvas explains it and
offers **Install Paperclip** with the install log streamed into the page
(Node 24+ required); when it is installed but not running it says how to
start it.

![Org mode: the halo-dev-cycle lineup as a Paperclip company](media/studio-org.png)

## Design mode: prototypes, pages and decks on your own apps

The third button in the top bar, `Roles | Org | Design` (keys `R` / `O` / `D`,
or `?mode=design`; the choice is remembered). It is the page for `halo design`
projects under `~/.halo/design/<slug>/`.

![Design mode: the Launch page project](media/studio-design.png)

**What you see.** The left rail lists projects (with a New project form that
opens its model picker on the design ranking, capability chips included), the
open project's artboards (id, kind, app, latest version) and its design system
(token groups with counts, plus a "Sync from..." box that takes a folder path
or a URL). The canvas is a dot-grid of frame cards: title row (title, kind,
app, `v<n>`), the frame itself (a sandboxed iframe for an HTML artboard, an
image for a `render.png` / `render.svg`, a link card for a PDF or MP4), a
device select (phone 390, tablet 820, desktop 1280 wide; the frame scales to
fit the card) and a version slider. Drag a card by its title row; positions
are kept in your browser per project. Pan with space-drag, the middle button
or a drag on the empty background; zoom with `Ctrl`+wheel; `F` fits.

**The panel** replaces the inspector tabs: Chat, Comments, Knobs, System,
Export.

- **Chat**: the prompt box (`Enter` sends, `Shift+Enter` adds a line), a model
  override and a budget, the turn's events as they stream (assistant text,
  compact tool cards, the result with its cost), the project's running cost and
  the history. One turn runs per project at a time; the page polls the turn
  every 500 ms.
- **Comments**: press `C` (the Comment tool) and click a frame to pin a note
  (the position is kept as a percentage of the frame). Open pins are grouped by
  artboard with Resolve; **Send comments** turns every open pin into one prompt
  ("Address these comments: ...") and runs a turn, then resolves them when it
  succeeds.
- **Knobs**: the artboard's `controls.json` as sliders, colour inputs and
  selects. A `css:--name` knob rewrites that variable in the page's `:root`
  block in place, with no model call, and makes a new version; a `craft:` knob
  is saved and applied by the next turn. Ask for knobs in a turn: "add knobs for
  spacing and the accent colour".
- **System**: the design system's tokens by group, editable, saved with Save
  tokens; sources and components below.
- **Export**: folder, HTML, PNG, SVG or PDF (optionally for one artboard) with
  the returned lines, and **Handoff bundle**, which shows the bundle's path
  with a Copy button.

**Direct text edits.** "Edit text" on an HTML card reloads the frame with
`?edit=1`: the page becomes editable, and `Ctrl+S` or leaving the text posts
the page back to Studio, which saves it as a new version ("direct edit"). The
helper script is wrapped in `<!--halo-edit-->` markers and never reaches the
saved file.

**Versions.** Every turn, knob move, direct edit and restore is a version.
The slider under a card swaps the frame to `v<n>/...`; at an older version,
**Restore this version** makes it the newest one.

**The raw file route and its sandbox.** Artboard files are served at
`GET /design-files/<slug>/<artboard>/<file>` (and `.../v<n>/<file>`), loopback
only and confined to that artboard's folder (`..` is a 404). They carry their
own `Content-Security-Policy: default-src 'self' 'unsafe-inline' data: blob:`
and `nosniff`, not Studio's, because a prototype has inline CSS and JS. The
page embeds them as `<iframe sandbox="allow-scripts">` without
`allow-same-origin`, so a prototype runs but cannot reach Studio's API or its
token.

**Plus more.**

- **Explore directions**: the **3 directions** button beside Run turn (or `V`)
  wraps the prompt as "Make 3 directions of: ..." with artboards named
  `<name>-a`, `-b`, `-c` (the name box beside the button, the selected artboard
  by default). It is one turn; afterwards the canvas tiles the new artboards
  side by side and selects the first. `POST design/<slug>/run` takes
  `{"variants": N, "base": "<id>"}`, and the CLI takes `--variants N --base ID`.
- **Critique**: **Critique <artboard>** (or `K`) starts a read-only turn (Read
  and Glob, no MCP servers) where a second model, the project's or the one picked,
  reviews the artboard. Its notes land as comment pins with a `critique` badge and
  a `[high]` / `[medium]` / `[low]` prefix; Send comments includes them.
  `POST design/<slug>/critique {artboard, model?}`.
- **Contrast**: the Knobs tab ends with a table of text-on-background pairs with
  ratio and AA / AAA verdicts (failing pairs first, red / amber / green dots),
  refreshed after every knob move. `GET design/<slug>/artboard/<id>/contrast`.
- **Assets**: the rail's Assets list (name, size, thumbnail) with a drop zone.
  Drop files from the desktop onto the rail or the canvas to upload them; the
  Chat box gets "Use assets/<name> ...". An image dropped on a frame card adds
  "Place assets/<name> on <artboard>". Click an asset to insert its path.
  `GET` / `POST design/<slug>/assets`, 15 MB at most.
- **Run view**: History shows "12 tool calls · 48 s · $0.03" per turn.

![The Knobs tab with Spacing at 48 and the Contrast table](media/studio-design-knob.png)

| Key | Action (Design mode) |
|---|---|
| `D` / `R` / `O` | switch mode |
| `N` | new project |
| `Enter` in the Chat box | run the turn |
| `C` | toggle the comment tool (`Esc` returns to select) |
| `V` | explore 3 directions of the Chat prompt |
| `K` | critique the selected artboard |
| `X` | check contrast (opens Knobs) |
| `S` | send comments |
| `Y` | sync the design system |
| `U` | add assets |
| `E` / `H` | export folder / handoff bundle |
| `F` | fit the canvas |
| `Ctrl`+wheel, space-drag | zoom, pan |
| `Ctrl`/`Cmd`+`K` | the palette lists every Design command with its key |

Shortcuts are inactive while you type in a box. The tour (`?`) shows five Design
steps when the page is in Design mode.

## Validate, save, apply

**Validate** runs `teams_yaml.validate_team_template` (the CLI's own checks)
and redraws the graph. **Save** validates, then writes the YAML to your user
scope (or the project, with the scope toggle in the top bar). A shipped
lineup or bio is never edited in place: saving it writes a copy under the
same name into your scope, which then shadows the shipped one -- exactly
what the wizard's Duplicate does. **Apply** shows the role table it will
write and, on confirm, does what `halo teams use <name>` does: `roles.*`
and `team:` in `~/.halo/config.json`, with custom roles switched on.

Errors are the validator's own lines, shown under the field they name and
in the Lineup tab; a save that fails leaves the file untouched.

## Security model

- The server binds `127.0.0.1` only and refuses any request from a non-
  loopback peer.
- Every API call carries a per-launch token (the `#t=` fragment in the URL
  `halo studio` prints; the page keeps it in session storage and sends it as
  a bearer header). A request without it is a 401.
- A request carrying an `Origin` header that is not this server's own is a
  403, so a page on another site cannot drive Studio even with the port.
- No CDN, no fonts fetched, no analytics: the page is a handful of static
  files served from the package, under a strict content-security policy.
- Writes go only to `~/.halo` (and a project's `.halo/` when you choose that
  scope); shipped files under the package are never written or deleted.

## Over SSH

On a box you reach over SSH (the usual Kali case), run `halo studio
--no-open` there, then on your machine:

```sh
ssh -L 48761:127.0.0.1:48761 <host>
```

using the port Studio printed, and open the printed URL (token included)
in your own browser.

## Shortcuts

| Key | Action |
|---|---|
| `Ctrl`/`Cmd`+`K` | command palette |
| `Ctrl`/`Cmd`+`S` | save |
| `Ctrl`/`Cmd`+`Enter` | validate |
| `Ctrl`/`Cmd`+`N` | new lineup |
| `A` / `F` | auto-layout / fit |
| `Del` | remove the selected assignment |
| `[` / `]` | hide the rail / the inspector |
| `?` | the tour |

## Files

`halo_harness/studio/server.py` (the server, the guard, the command),
`api.py` (the routes), `design_api.py` / `design_api_io.py` / `design_api_turns.py` / `design_files.py` (Design mode), `model.py` (the graph, the catalog rows, the session
reader), `static/` (the page). Tests: `tests/test_studio_api.py`,
`tests/test_studio_model.py`.
