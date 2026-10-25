# Studio: Team and Roles

Read this when you edit a team board or a lineup on the Roles canvas.

Part of [Halo Studio](STUDIO.md), which lists every part.

## Team: people, blocks and stages on one board

`Alt+2` (or `?mode=team`, `halo studio --mode team`, `/studio team`) is the
project's team file ([TEAM.md](TEAM.md)) as one board, live: who works on
the repo that holds Studio's folder, where their work lands, in which order,
and every gate that waits on you. Nothing in it calls a model by itself: Run
starts a stage the way `halo team run` does, on a runner thread of Studio's
own (with the block watchers armed), and every move comes back as a `team`
frame on the live feed.

![Team: launch mid-run, draft done, review held at its gate with the gate card open, the notes block held by a hand edit (amber), the change feed under the board](media/studio-team.png)

**The Start view.** While the repo has no team file the section is one Start
view instead of three empty panels: what a team is in three sentences (next
to a lineup, an Orchestra run and a mission), the six steps below,
and one button, **Make my first team** (`POST /api/team/init`: the shipped
template in `<repo>/.halo/team.yaml` and a starter `docs/BRIEF.md`, the same
code as `halo team init`; a 409 when a file exists). A file that does not
load, or has problems, shows the **Problems** list there instead, with
**Validate**. "open the board anyway" (or `?view=workspace`) goes straight to
the panels.

Three panels: the Board at 0,0 (18 columns, 78 rows: a small team's whole
board without scrolling; it scales down to 75% before it scrolls), the
Inspector the whole right-hand column (its gate card and change list are
long), the Change feed under the board. Each has its about line and `?`.

| Panel | What it shows |
|---|---|
| **Board** (`team-board`) | The **run bar**: the team, the run id, its state (not started, open, done, stopped), its cost, the runner dot (live: Studio drives the run now), **Run next** (`POST team/run` with no stage: the first pending manual stage), **Stop** (asks for a reason on a card) and **Validate** (the file's problems and every member's lineup preflight in a dialog), and (3.0.9.0) **Coach** once the run is done or stopped (the post-run coach's cards in a dialog). Under it the board: one labelled column per **member** (`team-member`: name, lineup and role, a harness chip when it runs on a fleet member, a live chip per stage it works in right now); one box per **stage** (`team-stage`) in the columns of its members (an Orchestra stage spans the team), coloured by state: pending grey, ready a cyan outline, running a cyan pulse, gated amber with its gate diamond filled, done green, failed red, skipped dim; each box has its kind, the line that matters (waiting, error, summary or trigger), its members and lead, its cost; the **blocks** (`team-block`) in the band underneath as document, folder or git nodes with their path, claims mode, last change and a claim badge (how many hold a part; amber while someone writes). **Edges** (`team-edge`): `stage_done:` triggers down the right-hand gutter (lit once the stage they wait on is done), reads dashed and writes solid between a stage and its blocks (lit while the stage runs), `block_change:` triggers dotted amber from a block to its stage. A click selects a member, a stage or a block and the Inspector opens on it. Compact face: members, stages, running, at a gate. |
| **Inspector** (`team-inspector`) | Three faces by the selection. **Stage**: its board row (state, kind, members, lead, gate, trigger with its settle window, reads, writes, cost, time), its summary, error and `waiting` (a delegated member: asked or running on its harness), **Run** (`POST team/run {stage}`: a problem in the file or a blocking preflight finding is listed right there, the preflight with **Run anyway** = `force`), and while it waits at its gate the **gate card**: the gate's text, the stage's summary, the acceptance's ok and note, **Accept**, **Redo** with your instruction, **Stop** (`POST team/answer`). **Block**: path, kind, claims mode, the ledger, every holder with its key, state and expiry, and its change lines newest first (`GET team/blocks/<id>/changes`, **More** pages back with `next`). **Member**: lineup (a link that opens Roles on that lineup), role, harness and the stages it is in. With nothing selected the stage at a gate shows first. Compact face: the selection and how many stages wait at a gate. |
| **Change feed** (`team-feed`) | Every line of the run's `events.jsonl`, newest last: the time since the run started, the kind, the stage, the text. A chip row hides or shows **state**, **trigger**, **gate**, **claim** and **change** lines (report and note lines always show); a click on a line selects its stage; at the bottom it follows the live run. Compact face: the line count and the last line. |

**Live.** The section reads `GET /api/team` once, then `GET team/board`,
`GET team/blocks` and `GET team/events?since=0`. Each `team` frame (`action`
stage, gate, claim or change) moves its stage's box at once (a stage frame
carries the board row) and opens the gate card (a gate frame carries
gate.json), and asks for the catch-up 150 ms later (the board, the blocks'
holders and the new event lines from `next`), so a line is never counted
twice. While the live feed is down and a run is open it polls every 2.5 s.

**Attention and the status bar.** A stage held at a required gate is a
**team gate** row in Fleet's Attention queue (`kind: team_gate`,
fleet/team_attention.py): `A` accepts, `R` redoes with your text, `S` stops
the run, `O` opens the Team section on that stage with its gate card. The
status bar's **TEAM** cell (with a team file) counts the stages running now
and the ones at a gate, in every section.

### How this works: Team

1. **The team file**: `<repo>/.halo/team.yaml` (else
   `~/.halo/teams/<project>.team.yaml`): the brief every agent reads first,
   the members, the blocks and the stages. Make my first team writes it from
   the template; Validate checks it and runs the lineup preflight.
2. **The blocks**: each keeps a ledger: who holds which part (a section, a
   file) and one change line per write. While a stage runs its members write
   only inside its write blocks; a part another member holds comes back
   naming the holder.
3. **The stages**: each reads and writes blocks and starts on a trigger:
   manual (Run), `stage_done:<stage>` (the edges down the right) or
   `block_change:<block>` (after a quiet settle window).
4. **Run**: Run next (or Run on a stage in the Inspector) starts it: its box
   pulses cyan, its members' columns show who is at work, the blocks it
   writes count their holders and the feed fills.
5. **The gate**: a stage with a required gate stops at amber; the
   Inspector's gate card (and a Fleet Attention row) has its summary and the
   acceptance. Accept, Redo with an instruction, or Stop the run.
6. **The next stage**: Accept marks it done: the `stage_done` edges light
   and the stages waiting on it start; a block that changes and settles
   starts its `block_change` stage. Stop ends the run; every stage not done
   is skipped.

**Keys.** `Alt+2` opens Team; `Tab` moves between the stage and block boxes
and `Enter` selects one; `?` and the panel keys work as everywhere.
**Palette** (`Ctrl`/`Cmd`+`K`): **Team: run next stage**, **Team:
validate**, **Team: stop** (asks for a reason), **Team: open file** (the
team file's path in a dialog with **Copy**), and **Team: open stage
<id>** for every stage.

**Files.** `ui/src/routes/team/` (`Team.tsx` the panels, `Start.tsx` the
Start view, `store.ts` + `sync.ts` the store and its feed, `actions.ts`,
`layout.ts` the board's geometry, `Board.tsx` + `BoardParts.tsx` +
`RunBar.tsx`, `Inspector.tsx` + `InspectorStage.tsx` + `InspectorBlock.tsx`,
`Feed.tsx`, `Dialogs.tsx`, `commands.ts`), `routes/help-team.ts`,
`styles/team.css` + `team-panels.css`; the routes are
`studio/team_api.py` and `team_init_api.py`, the runner thread
`team_live.py`, the Attention rows `fleet/team_attention.py`. Pictures:
`python tools/capture_studio.py --mode team` (tools/capture_team.py).

## What you see (Roles)

**Roles follows the disk (3.2.2.0).** When a lineup's file changes (your
session's model edited it, `halo teams apply`, another Studio saved it) the
canvas and the Inspector show the new version within two seconds; a bio
saved from the terminal updates the Bios panel, the bio form and the cards'
model pills; a moved layout file moves the cards (unless a move of yours is
still being saved); `config.json` moves the **active** mark and the default
model. An unsaved draft is never overwritten: the lineup's edits (the
Inspector's fields, its YAML, a card moved between tiers) or the bio form's
keep what you typed, and a line over the Inspector or the bio form says
"<name> changed on disk" with **Reload** (the file's version, your edits
dropped) and **Keep mine** (Save writes yours over the file). A lineup or bio
deleted on disk leaves the list; the open one closes with "<name> was
deleted on disk. Pick another ... from the list", or, with unsaved edits,
stays open with **Keep mine** (Save puts it back) and **Close it**.

Roles (`Alt+3`, 3.0.7.0 R2) is six panels; until you have a lineup of your
own (only the shipped ones, none active) it is one **Start view** instead:
what a lineup is, the steps, and **Make my first lineup** (a copy of a
shipped one, opened on the canvas); "open the panels anyway" (or
`?view=workspace`) goes straight to the panels.

**The default lineup (3.1.9.0).** While no `team:` is set, new sessions run
the shipped `auto` lineup ([ROLES.md](ROLES.md#the-auto-lineup-halo-3190)):
the Start view says so ("In use now: auto (the default)") with **Open auto**
beside Make my first lineup; once the panels show, it opens on the canvas,
the toolbar's chip reads **active (default)**, the Lineups glance **ACTIVE ·
auto (default)** and the status bar `active: auto (default)`. Its pool's
cards read **auto** on their model pill ("picked when it spawns, for its
task" on hover). While a member runs, its card's pill names the model it was
picked for, with "auto: <model> -- <reason>" on hover; the Inspector's **Live**
tab prints the same line under the agent's head (`roles-live-reason`), and
the Session section's Live column writes the spawn as "main spawned coder on
<model>: <reason>". A lineup with no `auto` card shows nothing new. Apply
another lineup to replace it. 3.1.8.0 R3: a card whose bio says `measured`
reads **measured** on its pill ("picked when it spawns, by what succeeded
here at its kind, else as auto" on hover); once its pick used the numbers,
the reason on hover and in the Live tab ends "(measured 4/5 code)", and the
model picker's best-at line says "measured: code 4/5"
([OUTCOMES.md](OUTCOMES.md)). 3.1.9.0 R3 ([Auto learns](ROLES.md#auto-learns-halo-3190)):
when what was learned moved an `auto` pick, the pill's hover, the Live tab
line and the spawn line end "(learned: code 1/4 on <model>, so <picked>
instead)" (and "(code 5/5 here)" when the numbers confirmed it).

| Panel | What it holds |
|---|---|
| **Lineups** (`roles-lineups`) | every lineup (shipped, user, project; the active one marked, the open one highlighted); **New** and **Duplicate** ask for a name on a card, **Delete** asks first (a shipped lineup stays), **Apply** asks first, showing the role table it writes; **user / project** says where New, Save and Delete write |
| **Canvas** (`roles-graph`, the drawn canvas `roles-canvas`) | the open lineup: one card per assignment, in one labelled column box per tier; the edges; the toolbar (scope, unsaved, Add tier, Undo, Redo, Save, Apply, Lay out, Fit, zoom); the replay bar along its bottom |
| **Inspector** (`roles-inspector`) | **Assignment** (the selected card's bio, role, alias, instances, the words that route a task to it, a model override, what resolves for it; Edit bio, Duplicate, Remove; with no card: the lineup's description, about and extends), **Lineup** (every top section as a small form with a **YAML** toggle and its enforcement badge), **Live** (the agents on the card now, or its last runs) |
| **Problems** (`roles-problems`) | everything wrong with the lineup as it stands in the editor, saved or not, in **Blocks** and **Warns**, each with its fix; a click selects its card; **Config** lists what `halo doctor --config` finds in the files behind the lineup |
| **Bios** (`roles-bios`) | every bio (drag one onto the canvas to add a card); a click opens the **bio form** (`bio-form`): models first (3.1.4.0: the preferred model in the **model select**, the **model picker table** folded under **more...**, fallback, effort up to xhigh and max, thinking, the context budget); description, kind, tags, extends; tools (allow and deny from the real registry, `GET /api/tools`, MCP servers, permission mode, the rules); context (files, skills, the memory namespace, prompt notes); limits; output; environment (own worktree, offline); acceptance; the schedule (cron or every, its prompt and model) and the triggers (file change, event, message); a **YAML** toggle for the whole bio (hooks and any key without a field); **Save bio** (with **Save to project scope**), New, Duplicate, Delete |
| **Models** (`roles-models`) | the catalog: its row count, each provider (enabled, key, models cached), why it is empty when it is (every provider looked at and why it lists nothing), **Refresh** (`POST /api/models/refresh`: every provider at once, each time-boxed, one line each: `ok, N models` or the reason, and "refreshed <when>"), **Analyze** (3.1.9.0, `POST /api/models/analyze`, what `halo models analyze` does: rebuilds what each model is good at and shows how many models per kind and each kind's strongest, the cheapest beside it when it differs), and **Test a model** by any ref |

- **A card** shows the agent, its role and alias, the **instances stack** (a slot with `instances: 3` is
  three stacked cards and `×3`), the **model pill** with the price in / out
  per 1M tokens and the context from the catalog, the **gym score** when
  `halo gym` measured that model on this machine (`GET /api/gym`), and a
  **warnings badge** with the count of its problems (hover reads them). Its
  band is its role's colour, kept clear of the state colours amber, green and red
  so the glow reads (tier 0 is cyan). Since 3.2.2.0 the card carries no
  scope badge: the bio's scope (shipped, user, project, a pack) is in the
  Lineups and Bios lists and in the Inspector's Assignment header (a
  shipped bio is read-only, Duplicate it in Bios for your copy).
- **The tier boxes.** One labelled column box per tier from the lineup's
  `tiers:` (tier 0 on the left, holding the main agent alone; the implicit
  last tier dashed; a lineup without tiers is one box, `all`). The strip
  says `Tier N · name`, the count, `max_parallel` and whether it is
  implicit; a click on it collapses the box to its strip (the cards hide)
  or expands it. Drag a card into another box: the alias moves to that
  tier's `members` and the lineup saves at once (`PUT /api/lineup/<name>`;
  a shipped lineup saves as your copy). The main agent cannot leave tier 0
  and nothing else may join it: that drop snaps back with a toast naming
  the rule. Positions and each box's collapsed state go to `PUT
  /api/layout/<name>` (`{nodes, tiers}`) 500 ms after the last move; a
  layout saved before the boxes existed is laid out once.
- **A drop makes room (3.2.2.0).** The card you drop keeps its spot; every
  card it lands on steps aside inside its own tier box (sideways first,
  then it takes the dropped card's old spot, then down; the box grows
  around it), live while you drag, so no card ever covers another. A drop
  into another tier's box is the tier move above and lands beside the card
  it hits, never on it. A collapsed tier is not a drop target: hold a card
  over its strip for a moment (600 ms) and the tier opens; drop it there
  while it is still collapsed and the card stays where it was ("tier
  <name> is collapsed; it stays where it was"). The selected card and the
  one you dropped last are drawn on top of the others, and the canvas
  grows with a drag so the card never scrolls out of view. A card's id is
  its alias (else its role, else its agent) plus an ordinal only among the
  cards with that same name (`reviewer#0`, `reviewer#1`), so removing a
  card keeps every other card's id and its saved spot; a layout saved with
  the older index ids (`worker#2`) reads with today's ids when its cards
  are the lineup's.
- **Tiers on the canvas (3.1.6.0).** **Add tier** on the toolbar opens a
  name field; Enter adds the tier as a new, empty box after the last one
  ("Drag cards here" in its brackets; with no tiers declared yet it first
  puts the main card alone in tier 0, `top`), and the boxes lay themselves
  out in columns again when they would overlap. Drag cards in; double-click
  a box's name to rename it in place (Enter keeps it, Escape drops it). The
  palette's **Roles: add tier** opens the same field. The box head's `...`
  opens its own menu, in the Fleet map's vocabulary:

  | Item | What it does |
  |---|---|
  | **Rename** | the name in the head becomes a field |
  | **Model...** | the model select bound to `tiers[i].model`; its first option, "the session's", clears it |
  | **Trigger...** | starts on (none, schedule, file_change, event, message), its one field (every or cron, paths, the event, from) and the prompt the tier's lead starts on; none clears it |
  | **Max parallel...** | how many of the tier's members run at once (blank: no cap) |
  | **Delete** | removes the tier; its cards fall to the implicit last tier (off for tier 0) |

  Each is one edit and a save (Ctrl+Z undoes it). A tier that names a
  model or a trigger shows a second head row: the **model pill** and the
  **trigger chip** (`⚡ every 30m`, `⚡ on file src/`); a click on either
  opens that form. A card in that tier whose bio says `default` runs on
  the tier's model: its pill shows it and its title says where the model
  comes from (this card's own, its bio's, its tier's, the session's); the
  Inspector's MODEL strip names the tier as what the card inherits. The
  rules (the model order, the trigger and what its lead may spawn) are in
  [ROLES.md](ROLES.md#tiers-halo-3070).
- **The edges**: **delegation** from main (cyan) and **pipeline** stage
  order (amber, dotted, `then <stage>`). 3.1.6.0: each label sits along its
  edge, offset by its place among the edges leaving the same card, so a
  one-tier fan reads as a tree; the selected card's labels are placed
  first and full strength, the others dimmed, and a label that would still
  overlap another is left off: no two labels ever overlap.
- **One editor (3.1.1.0).** Studio is where bios and lineups are edited:
  every field the terminal's read-only bio and lineup views show is in the
  bio form and the Inspector (the field-by-field table is in
  [AGENTS.md](AGENTS.md#editing-bios-and-lineups-studio-is-the-editor-halo-3110)),
  and each carries the same one plain line the terminal shows, from
  `GET /api/field-help` (`halo_harness/field_help.py`; the bundle carries no
  copy). `halo studio --edit bio:<name>` / `lineup:<name>` opens this section
  on that bio's form or that lineup's Lineup tab (see
  [STUDIO-shell.md](STUDIO-shell.md#opening-studio-on-a-bio-a-lineup-or-the-team-halo-studio---edit)).
- **Where the model is chosen (3.1.4.0).** The Inspector's **MODEL** strip,
  above its tabs, says what the selected card runs on (or the main card's,
  with none selected) and holds the **model select** for that card's own
  model (it saves at once; its first option keeps the bio's own), with
  **change the bio's model** beside it; the card's model pill (or Enter on a
  selected card) jumps there. The same select is the Assignment tab's Model
  override and the bio form's first field: the catalog grouped by provider,
  then the refs your config, bios and lineups already name and, while
  OpenRouter has no live list, Halo's shipped list (both marked "not
  verified"), **more...** for the whole table and **Test** for the probe.
- **The catalog resolves providers as a session does (3.1.4.0):** the env
  file, the shell and the settings.json `env` chain
  (`studio/catalog_env.py`), so a Databricks or OpenRouter key kept in
  settings.json lists its models here too; with no live list the select
  says why, per provider, and offers Refresh (`studio/models_refresh.py`,
  each provider asked at once and given 6 s).
- **The model picker table** (in the bio form): every catalog row with its
  price in / out, context, **best at** (3.1.9.0: the kinds it is good at as
  chips -- visual, audio, video, image, design, pdf, code, research, bulk,
  fast, local -- and its one honest line under them, the whole line on
  hover; `GET /api/models` rows carry `best_at {line, kinds}`, `GET
  /api/models/best-for` the kinds; see
  [MODELS-references.md](MODELS-references.md#what-each-model-is-good-at-halo-3190))
  and gym score; 3.1.9.0 R3: under the line, a **learned** chip per task
  kind this Halo measured the model at (`code 4/5`: first-time passes of
  the checked tasks in the last 30 days; muted while under 3 tasks, struck
  through when the model is dropped for that kind, the numbers and the
  auto pick's weight on hover; `GET /api/models` rows carry `learned`), and
  a **learned for** select that narrows the chips to one kind and strikes
  the rows of the models dropped for it
  ([ROLES.md](ROLES.md#auto-learns-halo-3190)); sort by name, price, context or best (the most kinds
  first), search across all of it, the line's words included; the table
  scrolls sideways in a narrow panel; a click picks the row; a ref the catalog lacks can be typed below. **Test this model**
  (`POST /api/models/test {ref}`) sends one short request and shows `ok in
  N ms`, or the error, right under it, never a dialog.
- **Problems** come from `POST /api/validate` 250 ms after every edit (and
  from `GET /api/lineup/<name>` on open): `findings` merges the validator's
  lines (blocks: Save answers 422 for these), the run-start preflight on
  the edited mapping (a model id its catalog does not know, a dead fallback,
  a bio with `tools.allow: []`, aliases in no tier), three tiers or more
  without the `delegation.max_depth` to reach the bottom one, and each
  card's own warnings (`studio/roles_findings.py`). The **Config** group
  comes from `GET /api/doctor/config?lineup=<name>` when the lineup opens and
  after each save: the `halo doctor --config` findings about its own file,
  the lineups it extends, config.json's `team:` naming it, and a team
  file naming it (`studio/doctor_config_api.py`).
- **Undo and redo.** Every edit (a field, a drop, a removed card, a YAML
  apply) joins a history of 50; `Ctrl+Z` undoes, `Ctrl+Shift+Z` (or
  `Ctrl+Y`) redoes; inside a text box the box keeps its own undo. A save
  that answers 422 lists the validator's lines in the Inspector and keeps
  your edit.
- **The palette's Roles group**: Roles: new lineup, Roles: apply lineup,
  Roles: new bio, Roles: test model (the open bio's model, or the selected
  card's), Roles: save lineup, Roles: undo / redo, and every lineup and bio
  by name.
- **No browser dialogs**: names, confirmations (delete, apply, remove a card,
  leave unsaved edits) and results are cards and toasts inside Studio.
