# What changed (the newest version entries of CHANGELOG.md, shipped with the package; `halo whatsnew` reads it)

## [3.6.0.7] - 2026-11-21

Copying out of a session works. In the terminal app the words you drag over are the words you get, the moment you let
go. In Studio a drag across Live rows copies the rows' own words, without the clock, labels, tags or buttons, and
every reply has a Copy button, as does every code block of a Live text row and of the Prompt feed. The limits that
remain are at the end of this section.

### Added

- **In the terminal app a drag copies the moment you let go.** No key is needed: the line "Copied the selection (N
  characters)" shows, and the usual second line says which program took it. So pressing the terminal's own copy key
  out of habit (it has nothing to copy while Halo owns the mouse) leaves the dragged words on the clipboard, and a
  paste gives them. Every new drag copies again. A plain click copies nothing and says nothing.
- **In Studio every reply has a Copy button**, in Session's Live column and in the Prompt panel's feed, and so does
  every code block of a Live text row and of the Prompt feed. It shows when the row is hovered or the button has the
  keyboard. It reads "Copy"; a press puts the text as the agent wrote it on the clipboard (a code block's button: the
  code only, its indentation and line breaks kept) and reads "Copied" for two seconds in the same place. When the
  browser refuses the clipboard it reads "Select and copy it yourself" and selects the text, so Ctrl+C copies it.
  Nothing moves when a button shows or its word changes.

### Changed

- **Ctrl+C says what it copied.** With a selection: "Copied the selection (N characters)"; it copies the same words
  again and never opens "Quit Halo?". With nothing selected: "Copied the last reply (N characters)"; a second press
  within three seconds still asks "Quit Halo?".
- **Code blocks in a reply are drawn as blocks in Live's text rows and in the Prompt feed**, in a fixed-width face
  with a rule at their left, their fence lines kept as written.
- **F1 help has a row "Drag"**: "Drag over text to copy it; Ctrl+C copies the selection again, or the last reply when
  nothing is selected."

### Fixed

- **A drag over part of an answer copied the whole last answer.** In the terminal app, a drag over a few words of any
  answer but the last, or of a code block, then Ctrl+C, gave the last answer; a drag over one word of a one-line row
  gave the whole line. The words you drag over are now the words you get. A drag over a whole answer still copies its
  source text.
- **A click on a tool's card took the keyboard.** What you typed next went to the card: "/copy" after such a click
  opened the card's pager and copied the card. It now goes to the chat box. Tab still reaches a card, and its keys
  work once the keyboard is there.
- **In Studio's Live column a drag across rows carried everything on the rows.** The paste held the clock, the kind
  label, the agent's tag, "why?" and the Steer box's words. It now holds the rows' own words, one row a line.
- **Selecting text in a Live row changed who you were steering.** A drag that selects words now leaves the steer
  target where it was; a plain click on a row still chooses it.

### Known limits

- **A tool's output has no Copy button.** In Live a click on a tool row that shows "▸" opens the result under the row,
  up to its first 4,000 characters, and it can be selected there; the Prompt feed shows its one-line preview only.
- **In Live an agent's "DONE · ITS LAST WORDS" and "HANDS BACK" rows draw their code blocks as plain text**, with no
  Copy of their own; the row's Copy copies the whole text.
- **The Copy button shows on hover or keyboard focus**, so not on a touch screen.
- **A drag in the terminal app does not set the Linux middle-click selection**; it sets the clipboard.
- **A drag that starts on the blank cell before a word copies that leading space**: it copies what is highlighted.
- **The once-a-session hint still says to hold Shift to select with the terminal itself**, which is not the key in
  every terminal (iTerm2 uses Option).
- **When the browser refuses the clipboard on a "DONE · ITS LAST WORDS" row**, the text selected for you is the
  shortened one the row shows, not the whole.
- **Every Known limit of 3.6.0.6 still holds.**
- **Where it was checked.** On the Linux VM: the whole test suite, its browser modules included (on a copy with no git
  history: the few tests that need it run in CI), and the full real-use check, seventeen of seventeen steps. Its new
  step starts a real Halo in a terminal, drags over words of the first answer with the terminal's own mouse sequences
  and reads what reached a stand-in clipboard program: those words on release, on a second drag and on Ctrl+C, then
  the last answer when nothing is selected. A real drag in a real terminal window there (a private display) put the
  dragged words on the real clipboard. The whole suite found the Copy button 6 px from "why?" where two controls are
  never closer than 8; it stands 8 px away now. On the PC (Windows): the changed plain modules and the node checks;
  the same real-use step in a real pseudoconsole, with a second clipboard program lying in the project folder that
  must never be started (it was not); and, in a headless Chrome, the copy module (three of its six tests failed until
  the test compared line ends alike: Windows' clipboard hands text back with its own; then six of six) and the module
  of the room rules. The release gate's first run then showed, in the terminal app's own suite on all three systems,
  that a reply selected as a whole widget (not by a drag) had been left out of the copy; it is copied again, and that
  suite passes on the Linux VM. Not run: macOS locally (CI runs it at the release gate), Firefox and Safari, Wayland,
  a copy over SSH into an outer terminal, the plain Windows console host, and a drag over a reply that is still being
  written.

## [3.6.0.6] - 2026-11-21

A workflow can be run for real from Studio, from every view that shows one: yours, this project's and an enabled
pack's. A Studio tab that can only look says so and says why, and one press makes it yours, in Firefox too. A pack's
workflows and agents are named as the pack's. The limits that remain are at the end of this section.

### Added

- **Run it: a workflow runs for real from Studio.** Wherever Studio shows a workflow that a session runs by name (an
  enabled pack's, yours, this project's) there is a **Run it**: in Agents -> 2 · Workflows beside **Try it** (Try it
  is unchanged); in the Map's **Run a goal** drawer, under a head "Workflows"; in Packs -> Pack Manager under the
  pack; in a pack's own section, in a row Studio draws above the pack's page; on the card of a workflow's box on the
  Map; and in the palette as **Run a workflow** (picked before the workflows are read, its list says "Reading the
  workflows..." and fills when they come). A press opens one form in place: the workflow's name, a box for the task,
  the line "Starts a new session in {folder} that runs this workflow's steps on your models. It can change files
  there. Cost and time depend on the models its steps use.", **Run** and **Cancel**. Run answers in the same place
  with "Started: session {id}." and **Watch it in Live**, which opens Agents -> 4 · Live on that session when you
  press it and shows the run as a group. Nothing under the form moves.
- **How it runs.** Run starts a new session in Studio's folder that runs the workflow by its name, step by step,
  through the same code as the Workflow tool. No model is asked to start it. The session is Studio's own and ends with
  Studio. In a terminal the same is `halo --headless --run-workflow <name> --workflow-task="<task>"`.
- **A tab that can only look says so, and one press makes it yours.** A Studio tab that a link or a script opened may
  look but not change things (that rule is as before). It now says so in one line at the top, from its first draw,
  with a button, **Make this tab yours**, that reloads the tab so that it can change things. The line gives the
  reason: "because a link or a script opened it", "Studio could not tell this reload from a link", or "because Studio
  was started again since it was opened". When a press is refused in such a tab, one toast carries the same line and
  the same button, whatever view you pressed in. The status bar's VIEW ONLY and the glance say the same.

### Changed

- **A pack's workflows and agents are named as the pack's.** They carry the tag "pack {id}" in Agents ->
  2 · Workflows (in a group of their own, "From packs"), in the Agents list, in a step's agent picker and in the
  Map's "Agents and workflows" list. They are read-only like the ones that ship with Halo: the form says so, Save is
  off, there is no Delete, and **Copy** makes one yours.
- **The refusal's words.** A write from a page that may only look is answered with "this page can look but not change
  things: only a Studio tab you opened yourself may. In Studio, press Make this tab yours (it reloads the tab), or run
  `halo studio`."
- **A workflow's form no longer jumps a moment after it opens.** Its "What it costs and writes" lines are read before
  the form is first drawn, so **Try it** and the rows under it stay where they are.

### Fixed

- **A tab that looked yours and could change nothing.** When Studio was started again and its new address was entered
  over an open Studio tab, the tab read as before, showed no VIEW ONLY, and every launch was refused. It now shows the
  line with its reason and the button, and one press makes it work.
- **A pack's workflow looked like yours.** It was listed under Yours with no tag, the Map's list called a pack's items
  "ships with Halo", and the form offered Save, which wrote a file of yours under the pack's name, and Delete, which
  failed.
- **A group could stay undrawn in Live until the pointer moved.** When Live (in Agents, and Session's Live drawer)
  opened with the pointer over the drawing and nothing drawn yet, the first group appeared only once the pointer left
  the drawing.

### Known limits

- **A workflow that ships with Halo has no Run it**: Copy makes it yours, and yours has one. A workflow with a problem
  has Run it off, and its hover says the first problem.
- **On the Map, an opened workflow box with the Run it form can be taller than the drawing's room.** In a low window
  the **Run** button is then below the drawing's edge: scroll the drawing to reach it. (Seen on Windows in a window
  800 px high.)
- **Live draws a second, small group ("Task 2") beside a run's own group**, for the run's own record. The Workflow
  tool's runs do the same.
- **A plain reload (F5, Ctrl+R) makes a tab yours in Chrome, not in Firefox.** Edge sends what Chrome sends and was
  not run. In Firefox use the button (pressed in a real Firefox, in Studio), or Ctrl+Shift+R, or enter the address
  again (both measured in a real Firefox on a stand-in page judged by Studio's own rule, not in Studio). Safari was
  not measured.
- **The Agents list tags a pack's agents but keeps them under Yours**; only the Workflows list has the group
  "From packs".
- **Every Known limit of 3.6.0.5 still holds.**
- **Where it was checked.** On the Linux VM, with a browser: the whole test suite, its browser modules included (on a
  copy with no git history: the few tests that need it run in CI; one YAML test also failed there, only because that
  machine's Halo had been installed without the dependency lock and so with a newer YAML library than the lock names),
  and the full real-use check, sixteen of sixteen steps. Make this tab yours was pressed in a real Firefox there (a
  hidden display, a throwaway profile): a tab a program opened, a tab the glance's link opened, the press, and Ctrl+R.
  On the PC (Windows), in a headless Chrome, one at a time: the three browser modules this release adds to (the tab
  that can only look, a pack's workflows in the lists, Run it in every view), and the plain and node checks of the
  join. The Run it module failed there in four runs of seven until the test scrolled the Map's drawing as a person
  does (the Known limit above); after that it passed three of three, and twice on the VM. The release gate's first run
  then showed two more things: on macOS the palette's list of workflows stayed empty when Run a workflow was picked
  before the workflows had been read (fixed: the list is read again when they come; the test now holds Studio's
  answers back to make that moment, red without the fix on the PC), and an older test of the Run a goal drawer
  expected the pack picker to be the last thing in the form's box of fields, which the new Workflows list under it
  ended. Not run: macOS locally (CI runs it at the release gate), Firefox on Windows or macOS, Safari, and a look-only
  tab across a real restart of Studio by a person (the test starts a second Studio under the open tab).

## [3.6.0.5] - 2026-11-20

The default is called Auto everywhere you read it, and the word "starter" leaves what Halo shows you. On Auto, the Live
drawings show each piece of work main hands out as a named, coloured group, and after a build Halo says what is ready in
this session now. The Attention chip left the Agents section: Session's Attention button counts what waits. A map of
your own is drawn as before. The limits that remain are at the end of this section.

### Added

- **On Auto, each piece of work is a named, coloured group.** In Session's Live drawer and in Agents -> 4 · Live, a
  session on Auto shows main alone until main starts a helper. Then each piece of work main hands out is one box in a
  colour of its own: four colours that repeat (the fifth group takes the first again), never a state's colour. A new
  group comes under the last one and nothing already drawn moves; main's box keeps the room of its usual fullest state
  from the first draw (a longer line, such as a long command, grows it once, and it then holds), so the groups under it
  stand still. In Session the drawing fills its drawer from the first draw; a group that does not fit whole is cut by
  the drawer's edge and reached by scrolling. Helpers on the same piece of work share one box, also when main hands out
  more of it in a later reply; a helper started by a helper sits in its parent's box; each run of a saved workflow is a
  box of its own, named "workflow {W}", with its steps, so two runs of one workflow are two boxes. A group's name is the
  few words main gave the work, else the words its helpers share, else "Task {n}", and the Timeline's **by group** and
  the glance page use the same name. A session recorded before this release groups its helpers by the reply that started
  them.
- **A group's head says how its work goes, and every helper says why it got its model.** The head reads, for example,
  "3 agents · 3 working · $0.04" (a part that is zero is left out; "1 failed" is red), and "3 agents · all done · $0.09
  · 2 min" once every helper is done; under it, a line says which models were picked and why. Inside, each helper reads
  "{who}: {description}" over "{model} · {state}", its left edge in its state's colour; a helper started by a helper
  adds "started by {who}: {task}"; up to eight are shown, then "+{n} more". **Save as an agent** shows only on a helper
  that is no saved agent. Hover a helper for "Why this model: ..." ("Why this model: named by main or by your settings"
  when there is no reason); click it for its card with the same line. Hover the head for "Started by main at {t}", one
  line per helper and the cost; click it for a card with Pause and Stop for each helper still working and **Open in
  Agents -> Live**. Hover main for its model and "Can hand work to: {names}", the agents this session started with.
- **Main's line into a group shows the work.** It lights while a helper of that group works, then stays as a trace that
  is heavier the more helpers the group had. A line into a group carries no label: the group's head names it.
- **Work that starts out of sight is named.** On Auto, when a helper starts working in a group wholly below what you
  see, the slot at the foot of the drawing reads "↓ {name} · working" (or "↓ {name} · working and {n} more below").
  Press it and the group's head comes to the top of Session's Live drawer (in Agents -> 4 · Live, into view). The slot's
  room is there from the first draw, so nothing above it moves when a name appears. On a map of your own Session's slot
  is as before and Agents -> 4 · Live has no slot.
- **The doors land on the group.** A group card's **Open in Agents -> Live** opens Agents -> 4 · Live on that session
  with the group's head at the top and its border pulsing for two seconds (with reduced motion: a still outline for
  the same two seconds). An attention alert's **Open**, or a row's **O**, for a question a helper of a session on Auto
  asks opens that helper's group, selected, with the helper's card open and the question's choices in it. Main's own
  questions land on main as before.
- **After a build on Auto, Halo says what is ready in this session now.** When a Builder card is applied in a session on
  Auto, its result (what main reads, and the terminal's card) ends with lines worked out from what the session really
  has: "Ready in this session now: the workflow review.", "Saved for your next session: the agent checker (this
  session's list of agents was fixed when it started; ...)", "Saved for your next session: the agent checker (this
  session keeps the checker it started with).", "Saved for your next session: the workflow review (this session started
  with no workflow, so it has no Workflow tool).", or "Not run under its name: the workflow review (this project has its
  own workflow review, which runs first)." The line about a session with no Workflow tool is given only when that is the
  reason: when the session's own rules leave the tool out (a deny rule, a tool list), no line is shown for that
  workflow. The terminal's Builder card shows them right under its header, also while folded. In Studio the head over
  Session's Live drawing says "Just built: the workflow review. Ready in this session now, by name." (or that it waits
  for your next session, or that this project's own workflow of that name runs under that name), with **Open in
  Workflows** and the same lines under it; a build of agents only gets the lines alone. Nothing is made usable that was
  not usable before. On a map of your own, after an undo, or when you leave every line, there is no such line.
- **A docs page, "Studio: Auto's groups"**, says what the boxes, the slot and the doors are; the Studio index links it.

### Changed

- **The default is Auto, and `auto`, `starter` and no map set are one map.** It ships as `auto`, with the same seven
  boxes and lines as before. `--map starter`, `crew.map: starter`, a goal's `lineup: starter` and `halo maps use
  starter` all run on Auto, as a plain session; `halo maps use auto`, `halo maps use starter` and `halo maps use --off`
  take `crew.map` out of config.
- **The terminal says Auto.** `/status` reads "Map: Auto (the default: main picks who works on each task, and a model
  for each one)"; `halo doctor` "Map: Auto (the default: main picks who works on each task); halo maps use <name>
  changes it, halo maps list shows them"; `halo setup map --terminal` "map: Auto (the default)"; `halo init`'s summary
  "Lineup: Auto (the default)". `halo maps list` starts with a row for `auto` (`default`, "main picks who works on each
  task") and ends "in use: Auto (the default)". `halo maps use --off` says "New sessions run on Auto (the default); no
  map of yours is set." A map with a problem: "halo: the map {X} has a problem, so this session runs on Auto (the
  default):". An old `team: auto` says "... lineups are gone; Auto is the default, so team: auto needs nothing. Clear
  the old key with halo config set team null."
- **What comes with Halo says "ships with Halo".** `halo maps show`, `halo agents show` and `halo workflows show`, the
  rows of Setup -> Map, the Map's switcher and the Builder name a map, agent or workflow that comes with Halo "(ships
  with Halo)", and the scope column of `halo maps list`, `halo agents list` and `halo workflows list` reads `shipped`.
  Studio's Agents and Workflows lists head them "Ships with Halo · Copy makes it yours". The refusals say it too, for
  example "coder ships with Halo (read-only): halo agents copy coder makes yours (my-coder)", and the Builder's copy row
  reads "Copy the map ship-it (ships with Halo) as yours (the changes below go into your copy)". Every agent, workflow
  and map file that ships with Halo starts "# Ships with Halo (3.6.0.0): read-only; ...".
- **Agents -> 3 · Map on Auto shows main alone and one line**: "Auto has no plan to edit: main picks who works on each
  task as it goes, and Live draws each task as a named group. Main can hand work to: {names}." with **Watch it in Live**
  (it opens Agents -> 4 · Live on the newest session on Auto) and "· + New map makes a map of your own." With no session
  on Auto, "Nothing runs on Auto right now." stands where the button was. Auto has no box to edit, no switch, no Lock
  and no Add; Run a goal stays. The bar's slot says "New sessions run on Auto (the default)." while no map is set. Over
  a session on Auto Studio says "This session runs on Auto (the default), as it started at {t}. Main picks who works on
  each task; each task shows as a named, coloured group." Old sessions, logs and links that name starter open and read
  as Auto (the default).
- **The map lists put Auto first.** The Map's switcher lists "Auto (the default)", then your maps, then "{name} (this
  project's)", then "{name} (ships with Halo)", then **+ New map**; no row says "· in use". Setup -> Map lists "Auto
  (the default)" first with "Main picks who works on each task; each one's model is picked for its task, and the reason
  is shown.", and One model for everything last; with Auto picked its preview reads "PREVIEW · Auto (the default)" with
  no **Edit on the Map**. Setup's strip and the Map glance say "Auto (the default)", and a theme set to follow the
  system reads "Follow the system" in Setup (the config value `auto` is unchanged).
- **Turning your map's "New sessions run on this" off** says "New sessions run on Auto (the default); a running session
  keeps its own."
- **An old map of yours named `starter` or `auto` is kept and listed, and no longer runs.** On 3.6.0.4 a map of yours
  named starter was what new sessions ran on; now a session with no map set, with `--map starter` or with `crew.map`
  naming starter or auto runs the shipped Auto. Halo never renames, moves or deletes your file. It is listed among your
  maps as "starter · your copy from before" (in `halo maps list` under its own name, never in use). In Setup -> Map its
  row has one button, **Copy as my-map**, and pressing its name opens your file read-only on Agents -> 3 · Map; there
  the bar shows its name and the same button, with no switch and no Lock. The copy holds your boxes and lines, is named
  my-map (my-map-2, my-map-3 ... when taken) and opens on the Map; turn on its **New sessions run on this** to run it
  again. In the terminal, `halo maps show starter` and `halo maps copy starter` read the shipped Auto, not your file.
- **A new map can never be named `auto` or `starter`.** Studio's **+ New map**, `halo maps copy --as`, the Builder and
  Studio's map API answer "{name} is a name of the default (Auto); give your map another name." and write nothing.
- **The Builder no longer copies the default as a map of yours.** With no map named (outside a session with no map
  set, or in Studio's builder box with Auto open on the Map), a map change used to offer to copy the default as your own
  map named starter. Now it writes nothing and answers "Name the map: Auto (the default) stays as it is, where main
  chooses who works. Pass a new name in args.map to make a map that routes."
- **Asking the Builder to use the map "starter" or "Auto" says what happens.** When Auto is already in use it answers
  "New sessions run on Auto (the default) already." and shows no card. When a map of yours is set, the card has one row,
  "New sessions run on Auto (the default); a running session keeps its own.", and applying it takes `crew.map` out of
  your config.
- **Asking for a workflow on Auto makes no map.** In a session on Auto, "build me a review workflow: a coder then a
  checker" gives one card that makes the agents not saved yet and the workflow, with no map row and no "New sessions run
  on it" row, headed "Your review workflow: the workflow review (coder, then checker)." In a session on a map of your
  own the card is as before.
- **Main is asked to name the piece of work each helper belongs to**, in 2 to 6 words, on the Agent and the Task tool,
  and to give helpers on the same work the same words: these become the group's name. A call that leaves them out still
  runs exactly as on 3.6.0.4, also when a local model's reply is repaired.
- **`halo explain auto`** (and Studio's Glossary) says "Auto: the default. Main picks who works on each task, and a
  model for each one; Live draws each task as a named, coloured group." The docs and the README say Auto (the default)
  and "ships with Halo" throughout.
- **Session's Attention button counts what waits on you.** It reads "Attention 2" while two decisions wait, the number
  and the button in the amber the Agents chip had, and just "Attention" while none does. Its room for two digits is
  there from the first draw, so nothing in Session's bar moves when the number comes, changes or goes; a count of 100 or
  more shows the true number, and the button widens for it. While its drawer is open the button keeps its pressed look
  and only the number is amber. A decision that belongs to no session (a conflict whose holder is in no session) is
  listed and counted in Session's Attention too.
- **The doors that opened Agents' Attention open Session's Attention drawer.** The palette's two lines read "Session:
  Attention" and "Session: answer next" (the oldest row picked), in the palette's Session group, with no key hint. A
  pack's attention row with no section of its own opens there on **O**. A note sent to your phone or chat through a
  pack's bridge, for a decision Halo has no card of its own for (a file conflict, for example), now ends "(answer it in
  Studio: Session, Attention)".

### Removed

- **The word "starter" from what Halo shows you.** Studio's pages, the terminal's lines, `halo` commands' output and
  help, Studio's API answers and what a session on Auto is told were cleared of it, and checks now scan for it. It stays
  only in the name of your own old file ("starter · your copy from before"), in a refusal that repeats a name you typed,
  and in the notes of earlier releases (`halo whatsnew`). `halo media`'s ComfyUI starter workflows keep their own word.
- **The glossary's "starter" entry.** `halo explain auto` is the default's entry now.
- **The Attention chip in Agents.** No "Attention · n" chip on any Agents tab (1 · Agents, 2 · Workflows, 3 · Map, 4 ·
  Live), no Attention panel over the tab, no A key in Agents, and no Attention step or A key in Agents' section help.
  Decisions wait in Session's Attention. An ask's alert, clicked while you are in Agents, still lands on 4 · Live on the
  asking box's card (on Auto, on its group).

### Fixed

- **Turning off a map that was not in use said new sessions run on no map.** Through Studio's map API, turning off a
  map while another map of yours was set changed nothing, yet the answer read "New sessions run on no map (as before
  maps)." It now reads "{name} was not in use; new sessions still run on {set}."
- **A running workflow was named by its raw input.** While main ran a workflow, its box in the Live drawings and its
  card in Agents -> 4 · Live read `Workflow {"name": "review", "task": "..."}`: several lines, so the box grew and
  everything under it moved at the moment the workflow started. A workflow is now named by its name (`Workflow review`),
  or by its task when it has no name.

### Known limits

- **Every Known limit of 3.6.0.4 still holds**, except renaming "starter" to Auto with agents drawn in named groups,
  which this release does for Auto.
- **A map of your own draws no groups.** Its boxes, lines and workflow blocks draw exactly as on 3.6.0.4, with no group
  colours. Groups on a map of your own are not in this release.
- **At a small window (1280 x 800) a group can be only partly in view in Session's Live drawing.** The drawing fills its
  drawer, but a group of three helpers is taller than the room left under main, and after a build the head and its lines
  take more of it. What does not fit is reached by scrolling; the line at the foot names a working group that is not
  wholly in view ("↓ {name} · working"), and one press on it brings that group's head to the top.
- **With no live session, the count on Session's Attention button is not visible until Session is opened.** Session
  then shows its Start view; **Open anyway** shows the bar and the count. The glance and the alert still show a decision
  that waits.
- **In Agents' Feed, an ask card's keys can open Session's Attention out of sight.** A key pressed while Studio is
  still reading the card's answers (its hover then says "Studio is reading its answers: this opens Attention"), or R on
  a question, opens Session's drawer, not something in Agents. Answer it there: Session's Attention lists it.
- **On a map of your own, main's box still changes height with what main does**, and the boxes under it move with it, as
  on 3.6.0.4. On Auto it keeps the room of its usual fullest state.
- **On Auto a helper inside a group cannot be reached with the keyboard.** The keyboard reaches a group and its card,
  not a single helper in it; a click opens a helper's card. On 3.6.0.4 every helper box was a tab stop.
- **Main is not yet told which kinds of helper it can start, and nothing measures how often it hands work out.** The
  agents it can hand work to are shown to you: this session's on main's hover, a new session's on Auto's Map tab.
- **A theme from a pack takes the group colours of the shipped palette of its kind**: a light one the shipped light
  palette's four, a dark one the default palette's four, not colours of its own.
- **A group name in unusually wide letters can make Session's slot one line taller.** The slot's room is sized for a
  long name of ordinary letters; the text is never cut.
- **On Auto, a workflow built in a session that an older Halo started gets no head and no lines in Studio**, because
  that session's build carries no answer about what is ready. Studio no longer says "It is on no map, so no session runs
  it yet", which is false on Auto. A session started by this release gets the lines.
- **Where it was checked.** On the Linux VM, with a browser: the whole test suite, its browser modules included (on a
  copy with no git history: the few tests that need it run in CI), and the full real-use check, sixteen of sixteen
  steps passed, among them the two new ones that drive a real terminal session and a real Studio through Auto's groups
  and through a build on Auto with its true lines, with nothing of the run left running. On the PC (Windows), without
  a browser: the Python and node checks of each change, and, before the Attention change, the real-use check with its
  five browser steps skipped by name (11 passed). With a browser on Windows, one real-use step was run on the PC, the
  build on Auto: the release gate's first Windows run had failed in it (a workflow's start grew main's box; see
  Fixed), and it passed on the PC after the fix. The release gate's hosted Windows and macOS runs also showed that
  with reduced motion (those machines have it on) the group's two-second cue lasted one frame; it is a still outline
  now, and the groups' browser test presses once with reduced motion on every system (run on the PC, with and without
  the fix). macOS was not run locally: CI runs it, and the other browser steps on Windows, at the release gate. How
  the four group colours look to a person was judged by no check; the checks measure only that they stay apart from
  the state colours and from each other, also for colour-blind eyes.

## [3.6.0.4] - 2026-11-18

A small release with one fix at its heart: a running terminal session could vanish from Studio for good after one
failed connect to it, while the terminal went on working. Now one failed connect no longer removes it. Beside it are
three small fixes found while flaky tests were looked into, and steadier tools for people who build Halo. Nothing else
changed in how a session runs. The limits that remain are at the end of this section.

### Fixed

- **A running session could vanish from Studio for good.** One failed connect to a terminal session (a heavily loaded
  machine, or a terminal paused with Ctrl+Z or a debugger while Studio read its list) took the session off the list
  every Halo reads. Session and Agents' Live drawing lost it, the Prompt panel showed it ended and its box went
  read-only, and `halo remote sessions` stopped showing it, while the terminal went on working. Only `/clear` brought
  it back. Now a refused connect keeps the session listed and only notes when connects began to fail; one connect that
  gets through clears that. It leaves the list only when its process has ended, its socket file is gone, or connects
  to it have failed for 30 seconds in a row. `halo ps` and `halo doctor` count such a session the same way.
- **A session whose row was removed puts it back.** If a session left the list anyway (paused long enough, or removed
  by an older Halo), it writes its row back at its next status event, without `/clear` (it looks at most once a
  second, so an event within a second of its last look is passed over). Status events come at the start and end of
  every turn, on a mode or model change, and when a background result arrives. A session that has ended never writes
  its row back.
- **A session refused connects once a few were waiting (9 on Linux).** Its control socket now holds a much longer
  queue (129 waiting connects on Linux), so a burst of reads while the session is slow to accept waits instead of
  failing.
- **Stopping a session with no terminal could say it failed.** When Studio's Stop or another caller sent `shutdown`,
  the session could close its socket before its answer was written, and on a loaded machine the caller read "control
  socket closed" for a stop that had worked. The session now begins to end once its answer has gone out, or two
  seconds after the command when the answer is not out by then (a caller that has stopped reading, or a machine so
  loaded that the answer waits that long); only then can the caller still read "control socket closed". It still ends
  if the caller has gone. The terminal's `/exit` sent from Studio gets the same two-second bound.
- **The terminal app logged "worker git-branch raised" as it closed.** A background worker whose call into the app was
  cancelled because the app was closing was logged as an error, and could show a red notice. Such a call now ends the
  worker quietly, for every worker, but only while the app is closing. The same errors while the app runs, and any
  other error while it closes, are logged and shown as before.
- **Studio's palette missed an agent that arrived while it was open.** Opened with Ctrl+K (Cmd+K on a Mac) right
  after a page load and typed into before the session list was read, it did not show "Agents: follow agent <name>"
  until you typed again. The line now shows as soon as the agent arrives.

### Changed, and you may notice

- **The palette's list follows the live agents while it is open.** Its "Agents: follow agent <name>" lines are worked
  out again whenever the live agents change, not only when it opens and on each key, so a line can appear or go while
  you look at it, the way the Settings lines that load late already did.

### Known limits

- **Every Known limit of 3.6.0.3 still holds.** The cut titles in the Map drawer that 3.6.0.3 put on the list for the
  next release are not in this one.
- **An idle session whose row was removed comes back at its next turn, not before.** It puts its row back only at a
  status event, and an idle session that nobody types into sends none.
- **A paused or hung session leaves the list late, not at once.** While its process is alive but does not answer, it
  stays listed until its queue of waiting connects is full, and then for 30 seconds more. On Linux, with one process
  reading the list each second, that was about two and a half minutes. A command sent to it meanwhile fails as it did
  before. A session whose process has ended still leaves at once.
- **Two refused connects more than 30 s apart, with nothing reading the list in between, still remove the row once.**
  The session puts it back at its next status event.
- **A Halo older than 3.6.0.4 running beside this one still uses the old rule**: one refused connect removes the
  session's row, and it can leave an old mark that makes a new Halo remove the row at its first refused connect. A
  session running 3.6.0.4 puts its row back at its next status event; a session running an older Halo does not.
- **Where it was checked.** On Linux, real separate processes were run on 3.6.0.3 and on this release: a session with
  no terminal, a second process reading the list each second, and a third filling the session's queue of connects
  while it was paused. On 3.6.0.3 a paused session left the list about nine seconds into its pause and never came
  back, not even after its next turn. On this release a session paused for 45 seconds stayed listed; with its queue
  filled it stayed listed for 30 seconds, then left, and came back at its next turn. A session that ended or was
  killed left at the next read on both. Nothing was run on macOS or Windows; a real Ctrl+Z in a terminal and a really
  loaded machine were not run; the lost answer to a shutdown did not show on either version on a quiet machine.
- **Session's Live drawing can still stop under its last whole row and leave empty room below it** when its boxes are
  tall, as they are mid-run. This release does not change it.

### For people who build Halo

- **The release tool no longer crashes on Windows when it resumes a release.** Picking up a release it had started
  (for example after a red CI gate), `scripts/release.py` read the candidate's CHANGELOG through git in the Windows
  code page and died with "AttributeError: 'NoneType' object has no attribute 'strip'". Every text it and
  `scripts/release_gate.py` read from git, gh, curl or `git credential fill` is now read as UTF-8; a byte that is not
  UTF-8 becomes a replacement mark, never a crash. Nothing it writes or prints changed.
- **The test driver ends its own Chrome's helpers before its close returns.** It waits up to 10 s until no process
  with its own throwaway profile folder is left, then ends any still there by pid after matching its start time: never
  by name, never another Chrome. A Windows runner no longer marks a browser module red because the test's own Chrome
  was still closing its crash handler or a utility process. The leftover check in `tests/run_all.py` is as strict as
  before. `scripts/realcheck` opens its browser through the same driver and gets the same close. A browser test's
  close can take up to 10 s longer while its Chrome's helpers are slow to go, as they are on Windows.
- **The test that proves lazy MCP servers connect in parallel counts overlap, not seconds**: 3 connects in flight at
  once when parallel, 1 when one after another. A slow runner can no longer turn it red.
- **The run-parts driver's timeouts name the registry**: the file's row ids, the row's `unreachable_since` and one
  timed probe.
- **New and changed tests**: `test_remote_registry` (one failed probe keeps the row; 30 s of failures, or a missing
  socket file, removes it; `halo ps` and `halo doctor` count a live session), `test_remote_control_socket`,
  `test_session_registry` (a session puts its row back; an ended one never does), `test_headless_session`,
  `test_review3_z2`, `test_review3_d1`, `test_chrome_close` (new; no browser), `test_release_script`,
  `test_mcp_lazy_cache`, and the browser tests `test_studio_prompt` (one refused connect keeps the box editable) and
  `test_studio_agents_live` (the palette lists an agent that arrives while it is open).

## [3.6.0.3] - 2026-11-18

Replays and History leave Halo. Both things called a replay are gone, in Studio and in the terminal: the playback of a
past session or goal run on the Map, and `halo replay`'s re-run of a turn on another model. History leaves Agents ->
3 · Map with them. What you keep: the session export (one Markdown file of a session, from three places), a goal
run's report on a page of its own, `halo report`, Record and `halo bugreport`; your old saved files stay where they
are. Nothing else changed in how a session runs. The limits that remain are at the end of this section.

### Removed

- **Replays, both of them.** The playback of 3.4.1.0 (a past session or goal run played on the Map with a scrubber)
  and `halo replay <session> --model` (one turn sent again to another model, with the difference shown). With them
  went `.halo-replay` files, Studio's Save, **Export a clip** and **Compare** (two runs side by side), every
  `halo replay` verb (`list`, `save`, `open`, `clip`, `compare`), `halo audit privacy --replays`, and `halo report`
  of a saved file.
- **`halo replay` says one line and stops.** With or without words after it, it prints this on stderr and exits 2; it
  never becomes a prompt and writes no session log: "halo replay (playing a session back, re-running a turn on another
  model) left Halo in 3.6.0.3. To keep a session as a file: halo session export <id>". `halo audit privacy --replays`
  says the same line, and so does `halo report` given a `file:` ref, a name ending in `.halo-replay`, any existing
  file, or an id found only among the old saved files. `halo replay` is no longer in `halo --help` or in the
  completions; `report` stays.
- **History left Agents -> 3 · Map**: the strip under the map ("Replay it on the map", "Report card", "Back to now"),
  the drawer's History page with its lists and ticks, **Open a file**, a past session's report card in Studio, and
  "Replay the last session" on the top line. The Map's drawer button reads **Run a goal** (it read History).
- **No Replay door is left in Studio**: not on Session's Agent panel, not on a LAST SESSIONS row, not in the palette
  ("Agents: replay this session on the Map"), not on a goal run's report page.
- **Two things have nothing in their place.** Compare: the nearest thing is two `halo report` cards side by side.
  The re-run of a turn on another model: comparing models is still on the list, as its own piece of work.
- **The word "replay" left the glossary** (`halo explain replay` finds nothing), and the docs page docs/REPLAY.md
  and its picture docs/media/studio-map-replay.png are gone. Its rules of the redaction, with their documented
  limit, are in docs/PRIVACY.md ("One redaction for everything that leaves"); its report card is in
  docs/COMMANDS-sessions.md, under `halo report`.

### Changed, and you may notice

- **The session export is the way to keep a session.** It is one Markdown file you read without Halo: every prompt,
  every reply and every tool call, keys masked, your home read as `~`. Its three doors give the same bytes:
  - Studio: Session -> Feed -> **Export** (hover: "Save this session export as one Markdown file:
    halo-trace-<id>-<date>.md");
  - in the terminal's session, `/export` (with no name it writes beside the session's log, in
    `~/.halo/sessions/<project-slug>/`);
  - `halo session export <id>`.
  The file's name stays `halo-trace-<id>-<yyyy-mm-dd-hhmm>.md` and its first line is unchanged. Its header no longer
  says "· lineup: not recorded" (an old log's recorded lineup still shows).
- **Each row of LAST SESSIONS ON THIS HARNESS** (Session's Agent panel with no agent picked, the last 8 sessions)
  offers **export** where it offered replay: it saves that session's export, the same file as the Export button, and
  a toast says what was saved or why not. Each row keeps **record**.
- **The words say "session export".** `halo --help` reads "the session export: a session as one Markdown file" for
  `halo session` and "the raw session log, JSON lines, for a script" for `halo export`; `halo export --help` adds that
  keys are masked only with `--sanitize`. A failed download in Studio says "The session export did not download: ...".
  A headless `/export` says "A single -p turn has no session to export here." and names `halo session export <id>`.
- **A finished goal run's report is its own page in the Map's drawer, titled Goal run.** Every way to it lands there:
  the run's `&run=<id>` link, Attention's `o` on a run, the palette's "Goal run <id>" line (now in the Agents group)
  and a dry run. A running goal run's page has the same title. When the run ends while its page is open, the page stays
  and offers **Open its report** where **Stop the run** was; a run gone from Studio reads "Run <id> is not going any
  more." with the same button. The report page has **Back**, **Copy** and **Run it again**; Back returns to the run's
  page when **Open its report** sent you, and otherwise closes the drawer.
- **The report card on that page shows every step**, and says "from the record · no model call"; the old "...and N
  more steps (Replay shows every one)" is gone. `halo report` keeps ten steps and ends "...and N more steps."
  (`--json`: `story` and `story_more`), as before. `halo report` takes a session id first, then a goal run id; its
  head always says it was rendered from the session's (or the goal run's) own record.
- **Agents -> 3 · Map draws the plan and what runs now, never the past.** There is no "Replaying ... Back to now"
  line, no replay rows, no replay colours and no dashed "removed since" boxes; "{n} new, not connected yet" and the
  plan start at the row's left edge. The Map's drawer holds Run a goal's form, a goal run's page while it runs and its
  report when it ends. Opening the drawer with **Run a goal** (or the palette's Show panel line) opens the form; a
  drawer already open when the page loads shows "Run a goal: several agents, one goal, one set of files." with a **Run
  a goal** button. Agents -> 4 · Live is still the live drawing.
- **An old replay link** (`?mode=agents&replay=<id>`, with any `at=` or `view=`) opens Agents -> 3 · Map as it is
  now; `replay=` and `at=` leave the address, which names the Map, so a reload opens the Map again.
- **`halo doctor` names your old files and leaves them.** While `<state>/replays/` exists it shows one line, for
  example "[WARN] Halo no longer opens replays; 3 saved files are in ~/.halo/replays/ (clips counted) -> fix: delete
  the folder when you like". Nothing is moved or deleted; with no folder there is no row.
- **Record stays**, and its hover reads "this session as one HTML page you can open anywhere" (on the button, on a
  LAST SESSIONS row's **record** link and on the palette's "Agents: record <name>"). Its page, its Play and its scrub
  bar are as before.
- **Other words.** A failed agent's Dismiss reads "Seen: <name> failed; this hides it here". Agents' help item
  "History and goal runs" is now "Goal runs, and keeping a session". The goal form's sentences say the report becomes a
  page of its own in the drawer. `/studio orchestra`, the first-run pack's Run a goal step and Session's help name no
  History. When no Chrome is found: "this needs Chrome and none was found: install Chrome or set HALO_CHROME".
- **docs/PRIVACY.md says two more facts about the redaction**: what a text cut short keeps of your account or machine
  name (one or two letters, or more of a name with a dash, dot or underscore once the cut is past its first part), and
  what each thing that leaves does with a path in another account's home.

### Fixed

- **Record's page could carry a key.** Record now passes the session through the session export's redaction before it
  writes: key-shaped tokens are masked, a path inside the project is relative, any other path under your home reads
  `~/...`, and your user and machine names are taken out (a path in another account's home is the exception: see Known
  limits). The project's folder name stays, as before. If the redaction fails, no page is written and Studio's toast
  says so: "the redactor could not clean this session; nothing was written".
- **In the Map's drawer the Run a goal form's buttons covered a field.** At 1280 x 800 the model picker sat 4 px above
  Run, partly under the button row's fade (at 1440 x 900 the "who plays the parts" line touched it). The fields now
  scroll in a box of their own, and Run, Dry run and Clear the form sit in a row under it: no field slides under the
  buttons, and Run is still in view without scrolling. A pack workflow's form in the same drawer has the same box and
  row.
- **The Run a goal form cut a label** ("SHARED FILES (COMMA ...") at 1280 x 800 and narrower. A label too long for its
  box now wraps to a second line.
- **A dry run's report did not show**: the form closed and nothing opened. A dry run now opens its Goal run page.
- **Studio's goal-run sentences sent you to History** for a run's report, and the Map's drawer button read History
  over the goal form. Both now name the Goal run page and Run a goal.

### Known limits

- **Every Known limit of 3.6.0.2 still holds**, except the two this release ends: "A saved replay file does not play
  in Studio" (replays are gone) and "History is still on Agents -> 3 · Map" (it has left). Two of them said "the next
  release": switching a running session to another map, and renaming "starter" to Auto with agents drawn in named
  groups. Neither is in this release. Auto with named groups is planned for a later one; switching a running session's
  map comes only if Halo can do it safely. The limits there about Studio's Export a clip form leave with it. Two
  limits of the redaction still hold for the session export, the report card and Record's page (both in
  docs/PRIVACY.md): an account named by a common word, and an excerpt cut short inside your account or machine name
  keeps one or two letters before its `...`, or more of a name with a dash, dot or underscore once the cut is past its
  first part (`on gpu-b...` for a machine named `gpu-box`).
- **Compare and the re-run of a turn on another model have nothing in their place.** Comparing models is still on the
  list.
- **The rows' export link covers the sessions that list shows, the last 8.** Export an older one from the terminal:
  `halo session export <id>`.
- **`halo export --sanitize` and Record's page do not mask another account's home path** (a path under some other
  user's home on this machine): the export as before, Record like it. The session export takes that account's name
  out, but writes the path as `~/...`, which reads like your own home.
- **Each tool result in the session export is cut at 40 lines**, then "... (N more lines)", as before.
- **A `.halo-replay` file made by 3.4.1.0 to 3.6.0.2 no longer opens anywhere**: Studio, `halo report` and every
  `halo replay` verb are gone or refuse it. The file stays on disk until you delete it.
- **The Map drawer's head cuts its own title** at 1280 x 800 when opened with Run a goal ("RUN A ..."; 3.6.0.2 cut
  "HIST..." the same way), and the goal form's head line ("several agents, one goal, one set ...") is cut at every
  size. At 1024 px wide and under, the view bar's title is drawn over the MAP button. A text should never be cut: this
  is on the list for the next release.
- **Where it was checked.** The exports, `halo report`, Record's masking, the retired command and the doctor's line
  were run for real on Linux only. No automated check presses a LAST SESSIONS row's export link; its route and its
  saving are each tested.

### For people who build Halo

- **Three things that stay left modules named after replays**, with no change of behaviour: the redaction's paths
  and names are `halo_harness/privacy_scrub.py` (was `live/replay_private.py`); the report card's data is
  `halo_harness/live/card_data.py`, beside `live/card_run.py`, `live/card_facts.py` and `live/card_timeline.py` (were
  `live/replay_run.py`, `live/replay_facts.py`, `live/timeline.py`); finding Chrome is `halo_harness/browser_find.py`
  (realcheck's `--browser` and the suite's Chrome driver use it).
- **Deleted**: `halo_harness/replay.py`, `replay_cli.py`, `replay_verbs.py`, `studio/replays_api.py`, and
  `live/replay_clip.py`, `clip_pipe.py`, `clip_chrome.py`, `replay_guard.py`, `replay_file.py`, `replay_cut.py`,
  `compare.py`, `compare_text.py`; in Studio's source `History.tsx`, `Compare.tsx`, `ReplaySave.tsx`, `Scrubber.tsx`,
  `historyStore.ts`, `compareStore.ts` and `replay.ts`.
- **Routes.** The report card is `GET live/report?ref=session:<id>` (or `run:<id>`) in `studio/live_report_api.py`:
  422 without a ref, 404 when it names nothing, 404 with the retired line for an old saved file. `replays/*` and
  `live/replay` answer 404. No pack or extension API ever exposed replays.
- **The retired verb's shape**: one row in `cli_commands.py`, `_c("replay", "", RECORDS, "left Halo in 3.6.0.3 (halo
  session export)", kind="retired")`, and one line, `cli_commands.REPLAY_LEFT`; `cli.py` prints it to stderr and
  returns 2 before anything else reads the words. `audit_cli.py` (`--replays`), `report_card.OldFile` (`halo report`)
  and `live/report` say the same line.
- **`tests/test_removed_replays.py` keeps them gone.** It greps Studio's UI source, every string constant of Halo's
  Python (by an ast scan; docstrings and comments left out), README.md, docs/ and both glossaries for `replay`,
  `scrubber`, `halo-replay`, `History`, `Compare`, `Back to now`, `What happened` and `clip`. Each skip excuses only
  the words its regex matches, and a skip that excuses nothing fails. It also checks the one line and exit 2, that
  `replay` is in neither help nor completions, the 404 routes, that the old modules are gone and nothing names them,
  and that the doctor names the old folder and never deletes it.
- **New and changed tests**: `test_privacy_scrub` (was `test_replay_private`), `test_card_data`,
  `test_browser_find`, `test_goal_run_report_page`, `test_history_leaves_the_map`, `test_replays_leave_studio`,
  `test_live_recording_redaction`. The tests of the old playback, its clips and Compare are deleted.
- **Two browser checks are steadier.** The long-title pick test holds both headers' words equal in any font, and the
  run-parts driver waits on its facts in order and names the one it stopped at.

## [3.6.0.2] - 2026-11-17

"Session map": what a session really does is drawn on the map it really follows, and what main builds for you in a
session shows in Studio at once, with one true sentence about which map the session runs on and which map new
sessions will use. Agents gets a fourth tab, Live, for the run, and the Map tab is the plan. A card in the
terminal no longer takes a key you meant for the box, and Studio's prompt and the terminal's prompt now behave much
more alike. The limits that remain are at the end of this section.

### Added

#### Session's Live drawing

- **The drawing shows the session you chose.** Session's left drawer draws the session picked in Session, the same
  one Cost, Prompt and the Feed speak of, not "the first session on a map". With nothing picked it takes the newest
  open session and keeps it: another session getting a turn moves nothing. The pick changes only when you pick
  another (an agent of another session, a link, `/studio`).
- **Top to bottom, at full size.** Main sits alone on the first row, its boxes two to a row below (one to a row in a
  drawer narrower than 400 px), a new rank on a new row; nothing scrolls sideways. It opens at 100 %; Ctrl + wheel
  (Cmd on a Mac), a pinch or the **- / % / + / Fit** buttons zoom from 75 % to 200 %. A box shows its name, then
  "kind · state", then what it does now; a long name wraps and the box grows. Lines leave the bottom of a box and
  enter the top of the next, and never pass under a box. A box no line from main reaches is placed below the others.
- **Nothing is cut and nothing jumps.** At rest no box is cut by the drawer's edge: a slot at the bottom says
  "↓ 2 more below" and a press scrolls one row. While the pointer is on the drawing, boxes that arrive or grow wait
  until it leaves (touch: a lifted finger or 2 s still); words change in place. After you scroll, the first box you see
  keeps its place.
- **The wait link stays whole.** When the session waits, its wait ("waiting on: coder -> Bash pytest -q", "waiting on
  you: ...") sits beside "↓ n more below", which keeps its width and its one line. The link's words are whole and wrap
  on lines kept for it from the first draw, so a usual wait coming or going moves nothing; a longer one takes its room
  once, when it first shows, and nothing moves when it goes. A press on it brings the box that is waited on into view
  and opens its card.
- **One true sentence over the drawing**, never amber, never flipping when a turn ends: "This session runs on shop,
  as it started at 2:26 PM. New sessions will too." When new sessions run on another map: "This session keeps running
  on starter (the default), as it started. Start a new session to run on review-flow." with a **New session** button
  (it opens the New session form; the form starts the session), then when each was switched on. While a workflow of
  that map runs, "This session is running the workflow W from review-flow." comes first; when the session's map file
  changed, "shop changed at ...; this session takes it at its next hand-off." A session with no map, one that ended,
  one Studio started that has no message yet, and no session at all each get their own plain sentence; the Start view
  says "No session is open here. New sessions will run on review-flow." and, after a build, "Your last session built
  the map review-flow at ... . New sessions run on it." The block keeps its height, so the drawing does not move.
- **A plain status line under it**: "tester working on the workflow W, step 3 of 6 · waiting for a model reply ·
  $2.42", "Waiting for you · $0.40", "Done · $1.10", with "· 1 hand-off outside the map" when work went where the map
  has no line. Main waiting on what it started is not "working"; the words "delegating", "in main's helpers" and "on 2
  models" are gone from this line. It keeps room for its longest sentence from the first draw.
- **What main builds shows at once.** When a Builder card is applied in a session while the drawer is closed, the Live
  button in the view bar shows a small "new"; nothing opens, nothing pops up, no button moves. In the drawer, "Running:
  starter (the default) | Just built: review-flow" appears once the session built another map (on a second line when
  the names are long); each half is a button, only Running is lit. The just-built map is shown by itself once, when
  the build lands, unless your pointer is on the drawing or a card is open. A head says what was built: "Just built:
  the workflow solo. It is on no map, so no session runs it yet." with **Open in Workflows**, "Changed in this session
  at 8:02 PM; this session takes it at its next hand-off.", or "Just built in this session at 8:02 PM. This session
  does not run on it." Boxes a build wrote carry "new 8:02 PM" until the session ends. The drawing comes from what the
  build sent; nothing waits on the network, and a map whose file is gone reads "This map was removed at 8:02 PM."
- **A running workflow is drawn as itself**: a block "workflow W · step 3 of 6" with a row per step ("3 test · tester
  · {model} · working"; done, working, next, failed), as the box it runs from or on a full-width row under the box that
  called it. Other agents are named rows in the box that holds them: a saved agent reads "{agent} · {model} · {state}";
  one made up for its task reads "made up: {the first 40 characters of the task} · {state}" and is the only row with
  a **Save as an agent** button. After three rows, "+2 under it" is a button that opens the rest in 4 · Live's Feed.
- **Lines that light.** Every hand-off lights the line it travels for as long as it is in flight, then leaves a
  quieter trace (heavier for more hand-offs; the newest is marked). Hover a trace: "Carried 3 hand-offs; last at 5:51
  PM: ...". A line nothing travelled never lights. On a map of yours, work no line brought is dashed in its own colour,
  "off-map" ("Not on the map: main started this itself"); on the default map main picks every hand-off and nothing is
  counted. When an agent talks to an agent in another box, the line between them pulses for 4 seconds.
- **A clock on every box at work**: a working box (and a working row) says the tool it is in and for how long,
  "Bash · 12 s"; a waiting one says what it waits for, in the status line's words, and for how long, "waiting for
  you · 12 s". It ticks in place without moving anything, and runs only while the drawing is on screen.
- **Step in from where you look.** Click a box, a step row, a block's head or a line (a 12 px band): a card opens in a
  fixed corner of the drawer with that agent's words, Pause (Resume), Stop and a steer field (type and Enter). A box
  with several live agents gets a row each. Escape, × or a second click closes it. Stop asks first and looks the agent
  up again when you confirm: if it already ended, nothing is sent and the card says "ended at 7:04 PM". Things not
  running show their state only. Every card offers "Open in Agents -> Live"; an off-map line's card also offers "Open
  the map at main". J and K step to the next and previous box with the focus in a drawing; Enter on a box opens its
  card. Hovering a box shows a summary: name, agent or workflow, model, state, "Starts when: ... (from ...)", children.

#### Agents: four tabs

- **`1 · Agents | 2 · Workflows | 3 · Map | 4 · Live`**, keys 1 to 4 (L opens Live, C the Map, W Workflows). The
  running dot sits on 4 · Live.
- **4 · Live is the run**: the session Session chose (newest open one otherwise), its sentence and status line, and
  the map it really follows drawn left to right like the Map, lit by what runs (workflow blocks, named rows, made-up
  rows, lit lines with traces, off-map work dashed; a label shows a hand-off's task for a few seconds). It is
  read-only and never amber, and it draws the session's own map whatever 3 · Map has open. With two or more sessions
  open, a **Which session** picker lists "{title} · {map}", this machine's first; another machine's session reads
  "... Its drawing is in that machine's Studio." Clicking a box, row, line or label opens the same step-in card. The
  wait link sits left of the zoom buttons.
- **A session with no map is drawn too**, in 4 · Live as in Session's drawer: main's box (and any workflow the run
  itself started) under "This session runs with no map, as it started at 2:26 PM: main does the work and starts its
  own agents." Nothing is fetched for it.
- **Agents opens on Live** while a session you have talked to is open here, otherwise on the tab used last. The tab is
  decided once and never moves by itself; a reload waits up to 1.5 s for the session list ("Reading the sessions.").
  A link, a key or a tab click always wins.
- **3 · Map is the plan.** A running session is one quiet line in a row that is always there: "fix-login runs on
  this map now. [Watch it in Live]", or that it runs on another map as it started, or that it is running a workflow
  from this map (that box is marked "running now in {session}"). The picker says "· running in {session}" and "· new
  sessions". A map built in a session while you are elsewhere opens next time you open 3 · Map; while you are on the
  Map, the row says "{map} was just built in {session} at {time}. [Open it]". The map you have open, changed by a
  build, is re-read in place, keeping your card, your pick and your zoom. The top line shows a goal run's whole goal,
  wrapped beside its **Open** button, on a line of its own that is there from the first draw, so a goal run starting
  does not push the drawing down.
- **2 · Workflows** says at its top: "Workflows are fixed lists of steps. A session runs a map, and a box on a map can
  run a workflow: see Map." A workflow main just built opens by itself the next time you come to the tab (never under
  you, never over an unsaved edit; the list marks it "new" until you open it). The list, the form of a workflow on no
  map and the line after Save say how to use one: "To put a workflow on a map: in 3 · Map, drag it from Agents and
  workflows onto a box, and that box hands work to it."

#### The Feed

- **The Feed lives on 4 · Live**, behind a **Feed** button on its bar: what the session's agents say and do, line by
  line, with Show, Steer, Stop and Pause / Resume / Dismiss. A click on a box in Live sets the Feed to that box. An
  agent's "open" from outside Session (the palette's "follow agent", a double-click) lands on Live's Feed for that
  agent. In Session the same panel is now called the Feed. Its list of the helpers a helper started shows each one's
  whole task.
- **The Map keeps its own drawer** for Run a goal, a goal run's pages and History. Pressing Replay (History's button,
  "Replay the last session" or the palette's replay) opens History at once on that replay's rows: its starts,
  hand-offs, asks, failures and finishes up to the scrubber, oldest first, each row whole. "Back to now" stays in
  sight.

#### Attention's Open and the other doors

- **An ask's Open lands on the run's drawing.** O on an Attention row (over Agents, Session's Attention drawer, the
  Feed's ask) or a click on the browser's alert opens 4 · Live when you are in Agents, otherwise Session with that
  session chosen, its Live drawer open and Attention open on that row (also when Attention is not in your saved
  layout). The asking agent's box is selected and its card is open with the ask's own answers ("allow once", "deny",
  "stop"), Pause, Stop and Steer; for a session with no map that is main's box. If the session ended meanwhile, one
  line says "This session ended at {time}. Nothing waits on you there now." If Studio has not read that session yet,
  it reads the sessions once and then lands; if that read fails, "Studio could not read the sessions just now. Try
  Open again." An ask from an agent on no box opens the Feed on it: "{agent} is not on the map: its question is in
  the Feed." An ask from another machine's session opens Session's Attention on its row.
- **A door never leads nowhere.** A door that switches section and opens a panel (Run a goal, a goal run's Open, an
  agent's open, Steer from outside Session, a pack's link) opens it on the section's first visit too; a panel that is
  gone says "That panel is not on this page any more: there is nothing to open."

#### One prompt in Studio and the terminal

- **A prompt or steer sent from Studio shows once in the terminal**, as its `❯` row, and brings the transcript down to
  it. Your turns in Studio's feed carry no "from Studio" badge. A steer is one row with "↳ steering the running turn…"
  under it; a turn stopped from anywhere shows "Interrupted." in Studio. A slash line typed in the terminal now gets
  its own `❯ /<line>` row too.
- **A slash line typed in Studio runs in the terminal as if typed there**: `/model <name>` switches the model,
  `/status`, `/help` and the rest print in the terminal and come back to Studio. A command that opens a window in the
  terminal (bare `/model`, `/resume`, `/rewind`, `/permissions` and the like) says "/<name> opens a window in the
  terminal: type it there."; `/paste`, `/images` and `/screenshot` say "/<name> works on the terminal's own box: type
  it there." A busy terminal runs nothing: "The terminal is busy: nothing was run. Press Enter to try again." A command
  still running after 3.5 s answers Studio with what it printed so far and "Still running in the terminal: the rest of
  its output will show there." `/exit` from Studio answers first, then ends the terminal's Halo. Enter on a bare
  `/model` in Studio opens Studio's own model picker.
- **Answers read the same everywhere**: "Answered in Studio: Allow", "Answered in the terminal: ...", "Answered
  remotely: ...", from one table. A question card answered in the terminal closes in Studio.
- **Studio's Prompt box keeps what you type after Enter.** When the session answers, only the text that was sent is
  taken out, and only if you did not touch it; a refused or failed send leaves the box alone. After a send of only an
  image, what you typed after Enter stays exactly, spaces and line breaks too.
- **The Prompt panel names the session it types into**: "<folder> · <title> · started 09:05 · in a terminal", with
  the date for a session from another day, "no messages yet" for one with no message, and an amber "no terminal" chip
  for a session Studio started. The row is two lines high and never cuts the title. **Change session** lists every
  open session. A switch from elsewhere says "Now typing into <folder> · <title>." for 6 seconds. After `/clear`, a
  fork or `/resume` in the terminal, the box follows: "Same terminal, new conversation: <folder>." If the session ends
  with text in the box, it is kept, read-only, with **Copy** (it reads "Copied." for 2 seconds). When a prompt sent
  from Studio seemed to do nothing in your terminal, it had gone to another open session: the header now says which.
- `/studio` in a private session says "This session is private: Studio cannot see it or type into it."

#### The terminal's cards

- **A long card fits the terminal**: its area grows to half the window instead of stopping at 12 lines, and when you
  resize the window a card that waits keeps the prompt box, the status line and its answers in view.
- **A waiting card says so.** A card waits when it shows while the box holds text, within 1.5 s of a key into the box,
  or while a dialog is open; with an empty, idle box it takes the keyboard as before. Above the box: "⏸ Permission
  waits while you type · Tab goes to it · Enter sends your text" (shorter in a narrow terminal). The box reads "Tab: go
  to the waiting card · Enter: send a message", and the status tag "permission needed · Tab goes to it". On a question
  card Tab goes to its first unanswered question; a click on the wait line also turns to the card.
- **Your draft is set aside, not wiped**, when a card asks for words (a deny reason, "Other...", plan feedback, an
  approval edit): "Your text is set aside; it comes back after this answer." It comes back exactly, pastes and image
  chips included. If the ask was already answered elsewhere, your words are kept, not sent: "Kept, not sent: that ask
  was already answered. Edit the text to send it." When a card also waits, both lines show above the box, the kept
  line on top.
- **A paste never answers a card.** It goes into the box and the card waits.
- **A card answered in Studio stays until you close it**: its line reads "✓ Answered in Studio: <label> · Enter closes
  it" ("· closes when you send" while the box holds text); your Enter, or a key on the card, closes it and sends it
  nothing, so words typed for one ask can never answer the next.
- **`/effort`, `/rewind` and `!cmd` no longer refuse while a card is shown.** The waiting card comes back, still
  waiting, when the new card closes.

#### The agent knows its own map

- **After the map new sessions use is switched while a session runs**, the agent's next turn starts with one short
  note naming the map this session runs on and the one new sessions will use, and that nothing needs restarting.
  The note tells it to answer from it when asked which map or workflow it uses, instead of searching the disk or
  suggesting a restart.
- **`/clear` says the map stays**: "This session still runs on shop."
- **Halo records when the map new sessions use was switched**, whichever way Halo switched it (the Builder, Studio,
  Setup, `halo maps use`, `halo config set|unset crew.map`, roles on or off); after a hand edit of `crew.map` the time
  is left out, never a wrong one. A session started on a map while no map is set for new sessions and "One
  model for everything" is on says "New sessions will run with no map." everywhere.
- **The Builder's map view, asked from a session, now starts** "THIS SESSION runs on starter (the default), as it
  started at 14:02. NEW SESSIONS run on review-flow (switched on at 14:05)."

#### The Builder

- **"Build me a review workflow: a coder then a reviewer" is one card** that makes the workflow, a new map with a box
  running it, and a ticked line "New sessions run on review-flow. This session keeps running on starter (the default),
  as it started. Start a new session to run on review-flow." (in the terminal it adds how to start one, below). When
  the new map would let agents do more, that line is its own question, unticked, No first.
- **In a session on a map of your own, a change with no map named goes to the map this session runs on**, not to the
  map new sessions use; each line ends "-- this session takes it at its next hand-off".
- **Editing a map new sessions do not use asks**, unticked: "New sessions do not run on ship-it; they run on shop. Run
  new sessions on it instead?"
- **A switch checked again at Apply**: when the map's file changed since the card was shown and now lets agents do
  more, or cannot be checked, the switch is left out and the result says why; the rest is written. Studio's builder
  box shows these "Left out: ..." lines too.

### Changed, and you may notice

- **Typing text and pressing Enter in the terminal's box no longer answers a card.** The old "type and press Enter to
  deny / keep planning / answer Other" is gone: with a card shown, Enter sends the box as with no card, and the card
  stays. To give a typed reason, go to the card and press its own key for it (a deny reason, "Other..."): what was in
  the box is set aside and comes back after. Tab no longer answers the lane offer or `/effort`. The permission
  placeholder reads "1-4 answers the request above".
- **Agents has four tabs; the run is on Live and the Map is the plan.** 3.6.0.1's lit Map, its amber "another map"
  line and its "What they think and say" drawer are gone; the Map has no feed. Agents opens on Live while a session
  you talked to is open.
- **An ask's Open lands on the run's drawing.** From inside Agents it stays in Agents, on 4 · Live (3.6.0.1 always went
  to Session). An ask from another machine's session opens Session's Attention on its row (3.6.0.1 opened its agent on
  Agents -> Map); its drawing is in that machine's Studio.
- **A session with no map draws main alone on Live**: main's box, and any workflow the run itself started, under
  "This session runs with no map, as it started at ...".
- **Session's drawing opens at full size** (100 %), with "↓ n more below" under its last whole row; 3.6.0.1 opened it
  fitted, panning from main. **Fit** still fits it.
- **A box on Session's drawing no longer shows its own cost** (3.6.0.1's lit Map did): it is in the box's card, and the
  session's total is in the status line.
- **Replies of the remote protocol no longer carry the sender's name.** `fleet.message` answers `{delivered, via}`
  (3.6.0.1: `{delivered, by}`), a `by` a client sends is not read, and a control record has none. A script that read
  `by` gets a changed reply.
- **The Builder's line about a map switch, in the terminal,** ends "In the terminal: quit, then run halo; /clear keeps
  starter (the default)." (with the map this session runs on).
- **New words.** Session's left drawer is **Live** and its line-by-line panel is **Feed** (hover says "(was Map)" /
  "(was Live)" this release), and Session's help speaks of Live and the Feed. The Map's switch "My sessions use this"
  reads "New sessions run on this". On the boxes of the run drawings the words "helper" and "made up for this task"
  are gone. Local -> Logs' re-read box reads "Follow". The drawer's link reads "Open in Agents -> Live".
- **The terminal shows less noise from Studio**: the grey "(from Studio) prompt / steer", "(remote) prompt / steer",
  "(remote) /<name>", "(remote) permission ..." and Studio's "(remote) interrupt" lines are gone, and so are the "no
  longer waiting" toasts. An answer given in Studio reads "Answered in Studio", not "Answered remotely".
- **In a session on the default map (starter), asking the Builder to change "the map" without naming one writes
  nothing**: main is told to name the map. The Builder's result no longer ends "Studio follows the files.".
- **`halo replay open` opens the Map** (History is there), and says "History on Agents -> Map lists it."
- **Studio's requests give up after 30 s** ("Studio server unreachable: no answer in 30 s"), except those that wait on
  a model, another machine, a download, a run starting or a pack.
- **The Map's bar on the default map with no map set** says "New sessions run on starter (the default)." in place of a
  switch that did nothing. With roles off, when new sessions run on no map, it says "New sessions will run with no
  map." beside the switch **New sessions run on this**, which is off; pressing it turns roles back on.

### Fixed

- **A card in the terminal could answer a key you meant for your sentence.** In earlier releases a card that asks you
  something (a permission, a question, a plan) took the keyboard while you were typing, and cards answer to single
  keys, so a letter of your sentence could answer a card you had not read; it could allow something for the whole
  session. Now, while you type, the box keeps the keyboard and the card waits, with a line above the box that says so.
  Tab turns to the card and Tab comes back to the box. A card answers to no key in its first 0.6 seconds on screen (a
  double tap of `1` answers one card, and an Enter in that moment sends nothing). Words already in the box are never a
  card's answer.
- **Session's drawing no longer says "No session is running here" each time a turn ends**, and no longer draws "the
  first session on a map" instead of the one you chose.
- **Agents no longer flips back and forth**: a busy session within 1.5 s of opening Agents moved it to the Map.
- **A workflow's step agents were drawn as made-up helpers**, and a saved agent with no line on the default map was
  "made up for the task". Each step now says its workflow, its step and its agent.
- **No user or host name in logs.** Nothing Studio sends writes the machine's user or host name into the session log,
  the feed, receipts, agent records or what the model reads; the lines say "from Studio" (or `halo remote`). A
  hand-off made from Studio writes "by Studio" into its brief, and names the Halo it went to by the name a person set
  there, else "another harness, in the folder <folder>" ("~" for a home folder), never by a user and host name.
- **Studio's Prompt box was emptied whole when the answer to a send arrived**, losing what you typed after Enter.
- **Studio's map list said "starter" both when you chose it and when nothing was set**; it now says which.
- **Words were cut**: the 44-character cut of "what it does now" is gone on Session's drawing and on the Map, and so is
  the 80-character cut of a goal run's goal on the Map's top line. A replay's rows in History and the Feed's list of
  helpers show their whole text, and the wait link on both run drawings no longer cuts a tool's words at 36
  characters or a question at 48.
- **2 · Workflows no longer says the Map tab "comes in the next version".**
- **A Studio-started session with no message yet** is never picked over another open session, and sorts last.
- **`/exit` sent from Studio to a terminal that is already closing** no longer prints a traceback over the terminal.
- **The Builder's result no longer calls a file "new"** that the card changed, when its path was spelled another way
  (a link such as macOS /var to /private/var, or a Windows drive letter in another case or with other slashes).
- **The box a session waits on (on you, a tool or a model reply) was not outlined on the run drawings.** It is now, on
  Session's Live and on 4 · Live.
- **`halo bugreport` could cut a settings path under your home folder** when the home folder's own path ran 40 or more
  letters, digits and slashes with no dot, dash or underscore (a macOS temp folder can). The path is now shown as
  `~/...`; a secret beside it is still cut.

### Known limits

- **A session keeps running on the map it started on until a new session.** Switching a running session to another
  map comes in the next release.
- **The default map is still called "starter"**; the next release renames it Auto and draws agents in named groups.
- **An ask answered in Studio leaves its card in the terminal until you press Enter in the box or a key on the card.**
  The card says how it was answered, and it gets nothing from that key; the Enter still sends the box's own text.
- **In Studio's Prompt box, if after Enter you select everything and retype a text that begins like the one just sent,
  its first characters can be removed when the answer arrives** (for example a word starting with `y` typed over a sent
  `y`). It never loses more than 3.6.0.1, which emptied the whole box.
- **Studio and the terminal still keep separate Up-arrow histories**, Studio's unsent text is one text for the whole
  page, and Studio's Prompt feed does not show turns from before a page reload. Studio does not show the text you are
  typing in the terminal, and a slash line typed in the terminal is not shown in Studio.
- **While a turn runs, Studio offers Queue it or Steer** where the terminal steers.
- **A burst of keys that is not a paste** (a tool that types for you, or a terminal without paste support) reaching a
  card that already has the keyboard and has been on screen for more than 0.6 seconds can still answer it.
- **A title longer than two lines makes Studio's Prompt header taller.**
- **A made-up agent's row shows the first 40 characters of its task.**
- **Something main builds before Studio follows the session may not be marked as just built.** Studio picks up a
  terminal session within about two seconds of its start (or of Studio's own start); what the session sends before
  that does not reach the page. What was built is saved and listed all the same.
- **On Windows (and wherever the font runs wider) the sentence over Session's drawing can take one more line when the
  map new sessions use is switched**, which moves the controls under it once, also while the pointer is on the drawer.
- **A saved replay file does not play in Studio, and has not since 3.6.0.0.** `halo replay open` still checks the file
  and keeps it, but Studio lands on Agents -> 3 · Map without it, and the file's row in History shows a scrubber over
  a drawing that does not change. `halo replay clip` gives up after 40 seconds and writes no file; Studio's Export a
  clip, which films the same way, writes no file either. A session of this machine still replays on the Map from
  History. Found while this release was checked; the fix is in the next release.
- **History is still on Agents -> 3 · Map.** It leaves the Agents tab in the next release.
- **Windows: a worker container whose Halo is ended hard (Task Manager) keeps running until the next `halo` start**,
  which removes it and says so; Windows has no reaper. Its `docker run` client ends with Halo at once. Any `halo`
  command is such a start (`halo ps` too); without Halo, `docker ps --filter label=halo.owner` lists it and
  `docker rm -f <name>` removes it.
- **macOS: a program a tool command detaches with an Apple system binary** (`ssh -fN host`, `ssh -f -M`, a
  `daemon()` fork of a program under /usr/bin) can still outlive Halo, and `halo ps` does not list it: macOS shows no
  environment for its own binaries. Start such a program with `HALO_OWNER=kept-<name>` if you mean to keep it, or end
  it by hand; docs/PROCESSES.md ("What Halo cannot end on macOS").
- **macOS: a program Apple ships can outlive Halo.** Found on a real Mac with System Integrity Protection on,
  present in 3.6.0.0 too and not fixed here: macOS hides the environment of a program it ships (`sleep`, `ssh`,
  `tail`, a shell), and Halo finds strays by a marker there. Measured: such a program that a tool command leaves in
  the background outlives a Halo stopped with Ctrl+C or a closed terminal (a hard kill ended it); one that Halo
  starts itself, as a pack can, outlives a Halo ended with `kill` and a hard kill too. A background job left by a
  tool command that finished normally can outlive every way out; that and the other ways out were not measured.
  The real-use check (`scripts/realcheck.py`) cannot see them either, so its PASS on a Mac does not cover them, and
  docs/PROCESSES.md does not describe this yet. After Halo has gone, however it ended, look with `ps -ax` and end
  yours by pid (`kill <pid>`).
- **Still as in 3.6.0.1** (each is written out in its Known limits below): `halo ps --json` does not list containers
  and `halo stop` does not stop one; on Windows the MCP HTTP client waits about 2 seconds for an MCP server on this
  computer that is not running, and a model server named `localhost` that listens on ::1 only is reached after half a
  second per connection; on Linux a record written by 3.6.0.0, or a local model server's, needs `halo ps --forget
  <pid>`; Windows `/update` can ask to be run again in one rare case; with the container engine stopped a start can
  wait up to 3 seconds once every 10 minutes; an Orchestra lane with `isolation: user` did not get the container
  lane's changes; the container lane ran against a real Docker on Linux only; on Windows a container engine reached
  through a `.cmd` or `.bat` shim whose daemon hangs can hold a start or a close longer; some 3.5 words remain
  ("Lineup:" in `halo init`'s summary and other places); Studio's Export a clip form names no browser problem until
  the export starts; a shared replay keeps a common-word account name outside home folders and logins, and an
  excerpt cut one or two letters into a name keeps those letters; a listen address `[::]` is saved as `127.0.0.1`;
  the terminal setup's last line does not mention maps; the Builder's map-switch question looks only at the folder
  you have open and at a folder outside any project; a click on the browser's alert brings Studio forward only when
  the browser allows it; `halo local stop` on a model server Halo cannot prove does not name `halo ps --forget`;
  `/update` and `halo update --keep-running` name no way to stop an unproven pack, shell or schedule process; on
  Windows and macOS a clock that steps back more than 2 seconds at the wrong moment drops a record; on macOS a stuck
  `ps` can stall one tool call for tens of seconds.
- **Where it was checked.** The browser-driven checks of this release run in the automated runs on Linux, Windows and
  macOS.

### For people who build Halo

- **`scripts/realcheck.py` has two new steps**: `session-map` (main builds a review workflow from chat; the card, the
  "new" word, the drawing and Agents' tabs are checked in a browser) and `prompt` (`--only prompt`, about 10 s: a real
  `halo` in a terminal and a Studio; a prompt shows once, `/model` switches, an answer reads "Answered in Studio:
  Allow", no user or host name in the log or on screen). In CI the realcheck step has 45 minutes and its job 50.
- **A browser check presses each control the design names** on Session's Live drawer and Agents' four tabs and fails
  when a press changes nothing.
- **A plain session sends the model exactly the bytes it sent before**, checked against a recording made before these
  changes.
- **CI's `studio-ui` job runs the TypeScript halves of the tests** with `HALO_NODE_TS_REQUIRED=1`: a half that cannot
  run fails there instead of being skipped.
- **A `halo` a test starts runs with the real card times** (1.5 s and 0.6 s) unless that test turns them off for it;
  the test runner's switch reaches only its own process.

## [3.6.0.1] - 2026-11-16

Fixes for what using 3.6.0.0 turned up on Windows, macOS and Linux; what you already do works as before. The few
new things come with the fixes: `halo ps --forget <pid>`, worker containers in the `halo ps` list, and a question
from the Builder before a map switch or a line from main that lets your sessions do more. "Open" on an ask in
Studio now takes you to it, and one button is gone from Studio's header. The limits that remain are at the
end of this section.

### Studio

- **The three-lines button beside the theme button is gone, with the density setting behind it.** It switched
  between "comfortable" and "compact", and compact only made the spacing and the text a few pixels smaller, so
  pressing it looked like nothing happened and the button seemed broken. The button, the palette's "Density: compact"
  and "Density: comfortable" commands and the compact sizes are removed: Studio has one size, the one it already used
  by default. If you had picked compact, Studio opens at the normal size; there is nothing to do. Nothing else in the
  header moved.
- **"Open" on something that waits on you takes you to it.** When an alert said a session was waiting on you and you
  clicked it, or pressed **O** on an Attention row, Studio could look like it did nothing: from Session it only
  opened the Agent side panel (which closed Attention), from Agents it stayed on the Map, and the alert's click
  opened Attention but left Session on whichever session it showed. Now every open of an ask (the browser alert's
  click, **O** on an Attention row in Session or in Agents, **O** on the ask card in the Live column) does the same
  from any section: Studio goes to **Session**, selects the session that asks, points the Live column at the agent
  that asks and opens **Attention** on that row, so A / R / S answer it there. If that session ended a moment
  before, one line says "That session has ended; its ask is gone."; if Studio could not read the sessions just
  then, "Studio could not read the sessions just now. Try Open again." It is never silent. Rows that are not a
  session's ask keep their places (the Ollama steward's note opens Local -> Hosts, a spend cap Agents -> Map), and
  an ask from another harness on your network still opens its agent on Agents -> Map.

### Windows and local model servers

- **Windows: Session no longer waits seconds for a local model server that is not running.** Windows takes about
  2 seconds to report a closed port on this computer, and Halo asked more than once while reading the model lists,
  so with Ollama stopped Session took several seconds to appear, and the terminal's start, `halo -p` and
  `halo doctor` waited too. On Windows a connection to this computer (127.x.x.x, ::1, `localhost`) now gets at most
  half a second per address; a server that runs answers in milliseconds. A model request that gets no answer in that
  half second tries once more with its full time, so a server that runs but is busy for a moment (several agents
  starting at once) still connects; against a stopped server such a request says so about half a second later than
  in 3.6.0.0 (about a second for `localhost`). A quick check, such as the version probe, gets the one short try.
  Measured on Windows with Ollama stopped: reading Session's model lists 2.6 s before, 1.3 s after. A remote host
  and an https connection keep their normal limit, and Linux and macOS, which report a closed port at once, behave
  exactly as in 3.6.0.0.
- **When nothing runs on that port, the message says so**: "nothing is listening there (connection refused); is the
  model server running there? (Ollama: `ollama serve`)", not advice to check the machine's network, DNS or VPN.
  On Windows, when a server takes no connection even in a request's full time, the message says the connect "timed
  out after N s connecting on this computer (the server took no connection in that time: too busy, or hung)".
- **Windows: an Ollama set up as `http://localhost:11434` is found again.** Windows tries ::1 first for `localhost`,
  and Ollama listens on 127.0.0.1 only, so Halo's quick check gave up and showed the host as "(unreachable)" while it
  ran. For `localhost` Halo now tries 127.0.0.1 first and ::1 second (only when every address the name gives is on
  this computer; a remote name is never reordered), so each connection is made at once.
- **A listen address typed into Studio's Setup works.** `0.0.0.0:11434` (or `[::]:11434`) is the address Ollama
  listens on, not one to connect to, and Windows refuses it. Setup now saves `http://127.0.0.1:11434`, as the
  terminal setup already did, and says so in one line under the card. On Windows a host 3.6.0.0 saved as `0.0.0.0`
  works without saving it again. On Linux and macOS, where such an address always connected, a saved one is read as
  in 3.6.0.0, so the context windows and speeds Halo learned under it are kept.

### Permissions

- **The Builder asks before a map switch that lets your sessions do more.** Asking the Builder for "my sessions use
  the map X" compared only the agents in the map's boxes and workflow steps, never the map's main agent, so a switch
  to a map whose main is `careful: own` put every next session in auto mode with no question, and "Apply them"
  applied it. That row now compares main by the same rule a session uses to pick its mode and its tools. The map you
  pick is used in every folder, so the row is judged twice, for the folder you have open and for a session outside
  any project, and more in either one counts. When the new map gives main more (a less careful start mode, or a tool
  such as Run commands), the row starts unticked with its own question, No first, and "Apply them" leaves it out;
  its text says what widens and where, for example "new sessions start in auto mode, as its main says (until now
  default)" or "new sessions outside this project start in acceptEdits mode, as its main says (until now default)".
  A switch to a map as careful or more, with no more tools, is a plain row as before. In a folder you have not
  trusted, the mode it starts from ignores the project's own `defaultMode`, as a session does.
- **A line from main on the map you use asks first when it gives main more.** A new line, or a line whose When
  widens from "only when I ask", that gives main the Agent or Task tool, or lets main hand work on its own to an
  agent that may do more than main and its agents, is now such a row too (unticked, its own question), like the
  same change made by a map switch. A line on a map you do not use, or to an agent that does no more, stays plain.
- **Studio's "My sessions use this" and `halo maps use` say when the start mode changes.** You press these yourself,
  so they still ask nothing, but when the switch changes the mode new sessions start in, the receipt says so. Studio:
  "New sessions run on X; a running session keeps its own; they start in auto mode (until now default)".
  `halo maps use` adds the same words to its first line, or, when the map's own main raises your mode, prints main's
  line instead ("the map X's main runs in auto ...; your own mode was default"), so it is said once. Both also say
  when the mode outside this project changes ("...; outside this project they start in acceptEdits mode (until now
  default)"); a change that is the same in both places is said once. When the mode does not change, the receipt is
  as before. `halo maps use` now reads your settings' default mode as well as config `permission_mode`, in the
  order a session reads them.

### `halo ps` and `halo update`

- **A record Halo cannot prove no longer blocks `/update` on Windows or lists another program as Halo's.** Halo
  keeps a list of the processes it starts. A record whose start time could not be read when it was written stayed as
  long as any program held that process number, so `halo ps` showed that program as Halo's and `/update` on Windows
  refused every time. Halo now drops such a record by itself once the number provably belongs to a program started
  after the record was written (Windows and macOS always; Linux for records written by 3.6.0.1 or later). Nothing is
  signalled on the way. Halo also stops writing such records: a process that already exited is not recorded, and a
  start time that cannot be read at once is read again.
- **New: `halo ps --forget <pid>`.** For a record Halo still cannot decide on, look at the pid in Task Manager or
  `ps`; if it is another program, `halo ps --forget <pid>` removes the record and signals nothing. A record whose
  process runs and is proven Halo's own is refused, with `halo stop <pid>` named instead. A forgotten process is no
  longer ended when Halo closes (`halo ps --forget` says so), and `halo stop <pid>` names `halo ps --forget <pid>`
  when it answers "still running" for a record it cannot prove.
- **`/update` and `halo update` never tell you to `taskkill` or `kill` a process Halo cannot prove is its own.** The
  Windows `/update` refusal still refuses while such a process may run, and now names `halo ps --forget <pid>` for a
  record of Halo's list, or the Halo command that stops that kind (for example `halo studio --stop`) where there is
  one. `halo update --keep-running` gives such a record the same words instead of "stop it with: taskkill /PID N"
  (or `kill N`); a record with a known start time keeps its stop command. On Windows, when processes still hold the
  install's files at the end, `halo update` names each one (a Studio it cannot prove is its own as "Studio (pid N,
  not proven to be Halo's own)"), tells you to close them yourself and run `halo update` again, and no longer sends
  a plain run back to "run it without --force": that hint follows only a run that used `--force`, and promises only
  that a plain run stops each one it can prove is Halo's own.
- **`halo update` says plainly what it will not stop.** When a Studio or the supervisor opened the halo you update
  from and Halo cannot confirm it is still the same process, the first line now says the updater does not stop it and
  you close it yourself; before, it said "the updater stops it once this halo has exited" and then did not. On
  Windows the install waits until it is closed; on macOS and Linux the install goes on while it runs. One that Halo
  did confirm is stopped by the updater, as before.
- **`halo update` and `/update` look twice before trusting a start time.** The other Halo processes the scan finds,
  a Studio or supervisor that opened this halo, and the supervisor named in its pulse file are kept only while their
  pid still runs the same command, so a pid that exited and went to another program in that moment is dropped and
  the updater cannot take that program's start time as proof and end it. When the second look cannot be read, nothing
  that still runs is dropped: it is named and never ended by its number.
- **`halo ps` lists the worker containers Halo has recorded**, one line each: `container`, the name, the engine,
  since when, and its state: "its Halo is running: removed when it closes", "its Halo has gone: removed at the next
  start, or now with: docker rm -f <name>", "its Halo could not be checked: kept while it may run; if it has ended:
  docker rm -f <name>", or, when the engine did not remove it, when a start tries again and the command that
  removes it now. The listing makes no engine call; like every `halo` start, `halo ps` first runs the start
  clean-up, which may call the engine once for a container whose Halo is provably gone.

### Closing

- **A worker container no longer outlives the Halo that started it.** An Orchestra lane with `isolation: container`
  now names its container (`halo-<owner>-<lane>-<6 hex>`, where `<owner>` is the id of the Halo that started it),
  labels it `halo.owner=<owner>` and records it under `~/.halo/containers/` while it runs;
  `docker ps --filter label=halo.owner` lists the ones running. `docker rm -f` (or `podman rm -f`) removes it when
  that Halo closes, after a hard kill of that Halo (macOS and Linux: the reaper does it), or at the next `halo` start,
  with one line:
  "halo: removed a worker container left from <when> (<name>)". Before, nothing knew the container, and its worker
  kept running, and spending, until it ended. A lane that runs past its time now has its container removed too, not
  only the `docker run` client. The start sweep removes only containers recorded in this home whose Halo is provably
  gone (its process has ended, or its start time was read and belongs to another program), never one found only by
  its label; a Halo whose start time cannot be read for a moment (a busy Mac while a large model loads) keeps its
  container. With no record a start makes no engine call.
- **A stopped Docker does not slow every start.** When a container is left to remove and the engine does not answer,
  a start tries once for at most 3 seconds and the starts of the next 10 minutes leave it alone. A close in a lane's
  first moments keeps the record unless `rm -f` really removed the container (Docker 23 and newer answer "No such
  container" with success for one it has not created yet; that is not counted as removed), so one the engine creates
  a moment later is still removed at the next start, and `halo ps` lists it until then. A container is said removed
  only when the engine answered so: when the engine program recorded for it is missing, the record stays, a start
  10 minutes later tries again, and `halo ps` says the engine did not remove it.
- **Windows: what Halo runs and waits for ends with Halo, also when Halo is ended from Task Manager.** A pack's check,
  a git clone and a container lane's `docker run` client now join Halo's Job object, as the other programs it starts
  always did. The editor Halo opens for you and anything you asked to keep are never tied to Halo.
- **macOS: a Halo that starts no program starts no reaper.** Every Halo on a Mac, even `halo ps` or a `halo stop`
  with nothing to stop, started the closing reaper at once and scanned every process on the machine when it closed,
  because Halo's own `ps` read of a start time counted as starting a program. The reaper now starts with the first
  real program Halo starts, as on Linux. `halo doctor` (and so the installer's last check) still starts one for a
  moment: it runs your login shell once to read your PATH, and what your profile starts must end with Halo.

### The terminal setup and typed numbers

- **Numbered picks take only 0-9.** A superscript digit (²) typed at a numbered pick of `halo init --terminal`
  (provider, permission mode, default model, "Which Ollama?", the model list) stopped the setup with a Python error,
  and a full-width (２) or Arabic-Indic (٢) digit was quietly read as 2. Now only 0-9 count; anything else is no
  answer, and the setup asks again or says "no server picked" / "no model picked". The same holds wherever you type a
  number: `halo stop <pid>`, `halo ps --forget <pid>`, `/intro <n>`, `/why <turn>`, `turn N` in the terminal UI,
  `halo review #N`, `halo local` by port, a pool member's `host:port`, `--keep-alive`, a cron step in an agent
  file, the accessible mode's numbered answers, Studio's pool, voice and settings number fields and its
  live-agents list (an answer that says what is wrong, not a server error), and the Signal pack's phone pick
  (Signal pack 1.0.2).
- **A very long number is no number.** A paste of thousands of digits at a numbered pick stopped the setup with a
  Python error, and Studio's number queries failed the same way. Now a number of more than 18 digits (leading zeros
  do not count) is read like any other answer that is not a number: the setup asks again and Studio refuses it.
- **The setup's last line names no lineup**: "The rest (local models, theme, Linux fixes, checks, machines) is in
  Studio's Setup ...".

### `halo replay` and the privacy audit

- **Replays and exports keep ordinary words when your account has a common name.** With an account named `user`,
  `admin`, `test`, `home`, `runner`, `ubuntu` and the like, `halo replay`, `halo export`, the bug report, the session
  trace and the report card rewrote ordinary text: "the user asked" became "the <user> asked", `tests/test_a.py`
  became `tests/<user>_a.py` and `ubuntu-latest` became `<user>-latest`. Such a name is now replaced in a home
  folder (the Linux, macOS and Windows home folders in either slash, Git Bash, WSL, `~name`, a `${HOME:-...}`
  default, whatever character ends the name) and in a login: `name@machine`, `machine\name` for this computer's
  own name, a share `\\machine\name`, the account of `ssh -l`, `sudo -u`, `docker -u`, `psql -U`, `mysql -u`,
  `runas` and `net use /user:`, of `su`, `chown`, `id`, `passwd`, `groups`, `finger`, `useradd` and kin at the
  start of a command, and keys such as `user=` or `owner=`. Everywhere else it stays; docs/REPLAY.md has the
  rule, and Known limits says what that leaves. Any other account or machine name is replaced as a whole word: a
  digit, `_`, `.`, `@` or a quote beside it still counts as a boundary, but it is never replaced inside a longer
  word. A machine name that is a common word (`localhost`, `desktop`, `laptop` and the like) is no longer
  replaced at all.
- **`halo audit privacy --replays` uses the same rules**, so it no longer reports `<user>` as a leaked user name,
  and in a replay that was not scrubbed it reports a common-word account name in a home folder or a login (the
  places above), and any other account or machine name wherever it stands as a word.
- **`halo replay clip` and Studio's Export a clip with a `HALO_CHROME` that names no browser** now stop with
  "HALO_CHROME names a browser that does not exist: <value> (fix or unset it)" instead of filming in your installed
  Chrome. A bare command name (`HALO_CHROME=chromium`) still resolves through PATH.

### Docs and help

- **The how-to pages send you only to commands that exist** (the dated research notes under docs/harness and
  docs/design are left as written, and some still name old commands). Lines that named `halo teams ...`, `halo team`,
  `halo workflow ...`, `halo blocks`, a bare `halo roles` or `halo --config` now name the 3.6 command
  (`halo maps use|list|edit`, `halo workflows`, `halo orchestra new --workflow ... --input ...` then
  `halo orchestra run`, `halo goal add --workflow`, `halo config get roles`) or say the command is gone.
  docs/README.md, WIZARD.md, PACKS.md, ISOLATION.md and MODELS-ollama-steward-sched.md now teach agent, workflow, map;
  a section that still describes a 3.5 lineup or bio file, or a 1.x pack's format, says so under its heading.
- **Help texts and the model's own instructions describe 3.6.** `halo studio --help` says "your agents, workflows
  and maps" and that the old `--mode` words (roles, orchestra, team) open Agents on its Map. `halo isolation check`'s
  help says what it reads: lineups and bios of the older 3.5 format (agent files do not declare isolation yet). The
  system prompt no longer sends the model to lineups, bios, the Cast canvas or Fleet.

### For people who build Halo

- **The test runner fails a module that leaves a process running.** After each module `tests/run_all.py` looks for
  processes the module started that still run and counts a failure, so one leak no longer piles up on your machine
  or upsets the modules after it. It ends, by pid and once its start time matches again, only what the run provably
  started (a child of the run, or a process with the run's own marker; on Windows also a process the WMI host
  started that names a folder of the run), and prints
  `[LEFTOVER] <module>: pid <pid> <command line> -- ended by pid`. A process found only because its command line
  names a folder of the run, such as a `tail -f` you started yourself, is named "NOT ENDED" and keeps running. A
  line shows the program and its arguments only, cut to 200 characters, never an environment (on a Mac they are read
  again without the environment). Before it calls a process left behind, the check waits out Halo's own closing
  time and a margin (8 seconds), and only while something is still there, so a Halo closing normally on a slow
  machine is not counted. Nothing that ran before the module began is touched, and nothing is ended by name. The
  test-side leaks it found are fixed (the kept-marker test's sleeper on the macOS path, the quick-exit test's
  reaper, the Bash tool test's `sleep 5 &`, the reference pack's lint MCP server, the clipboard test's stand-in
  daemon, and a pack's policy program, which a test home now ends when it closes), and the closing tests' sleeper
  helper ends itself after 15 minutes.
- **The tests never write into your real Claude configuration.** With `CLAUDE_CONFIG_DIR` (or `GOVERNOR_STATE_DIR`)
  set in your shell, a test could write a `.claude.json`, settings, agents or skills into your own Claude Code folder.
  The test rig removes both variables when a test module loads, `run_all` removes them again before each module, and
  `run_all` checks `.claude.json`, `settings.json` and `.config.json` in that folder after every module: a module that
  creates or removes one fails with a `[REAL CLAUDE CONFIG]` line.
- **`scripts/realcheck.py --browser <path or command>|none`** (or `REALCHECK_BROWSER`): `none` turns the two browser
  steps (`studio`, `idle-cpu`) into a counted, named SKIP and starts no Studio or browser for them; a path or a
  command name picks the browser, and one that names nothing fails those steps. With no switch nothing changes: an
  installed Chrome, headless, with a throw-away profile. The tests' Chrome drivers stop on a `HALO_CHROME` that names
  nothing, the same as `halo replay clip`.
- **Windows: the two outer-Job tests of `tests.test_kept_outlives_starter` pass with a Python whose site-packages
  holds old backports** (Anaconda, for one). The test put site-packages ahead of the standard library; it now sets
  `PYTHONPATH` to the repo only, and inside a virtualenv adds the venv's site-packages after the standard library.
  Halo was never at fault.

### Known limits

- **Windows: a worker container whose Halo is ended hard (Task Manager) keeps running until the next `halo` start**,
  which removes it and says so; Windows has no reaper. Its `docker run` client ends with Halo at once. Any `halo`
  command is such a start (`halo ps` too); without Halo, `docker ps --filter label=halo.owner` lists it and
  `docker rm -f <name>` removes it.
- **macOS: a program a tool command detaches with an Apple system binary** (`ssh -fN host`, `ssh -f -M`, a
  `daemon()` fork of a program under /usr/bin) can still outlive Halo, and `halo ps` does not list it: macOS shows no
  environment for its own binaries. Start such a program with `HALO_OWNER=kept-<name>` if you mean to keep it, or end
  it by hand; docs/PROCESSES.md ("What Halo cannot end on macOS").
- **macOS: a program Apple ships can outlive Halo.** Found on a real Mac with System Integrity Protection on,
  present in 3.6.0.0 too and not fixed here: macOS hides the environment of a program it ships (`sleep`, `ssh`,
  `tail`, a shell), and Halo finds strays by a marker there. Measured: such a program that a tool command leaves in
  the background outlives a Halo stopped with Ctrl+C or a closed terminal (a hard kill ended it); one that Halo
  starts itself, as a pack can, outlives a Halo ended with `kill` and a hard kill too. A background job left by a
  tool command that finished normally can outlive every way out; that and the other ways out were not measured.
  The real-use check (`scripts/realcheck.py`) cannot see them either, so its PASS on a Mac does not cover them, and
  docs/PROCESSES.md does not describe this yet. After Halo has gone, however it ended, look with `ps -ax` and end
  yours by pid (`kill <pid>`).
- **`halo ps --json` does not list containers**, and `halo stop` does not stop one; `docker rm -f <name>` does. With
  no process of Halo running, `halo ps` prints "no process of Halo is running for this home" above its container
  lines.
- **Windows: the MCP HTTP client still waits about 2 seconds** for an MCP server on this computer that is not
  running; the half-second bound covers model servers only.
- **Windows: a model server named `localhost` that listens on ::1 only** is reached after half a second per new
  connection.
- **Linux: a record written by 3.6.0.0, and a local model server's record, carry no boot-clock time**, so Halo cannot
  drop it by itself when its pid goes to another program; `halo ps --forget <pid>` removes it. On Linux a pid reused
  within about 2 seconds of its record being written is not caught either.
- **Windows: `/update` can ask you to run it again in one rare case**: when, between its two looks, the only other
  Halo ends and another program takes its pid, that pid is named as one that may still run.
- **With the container engine stopped, a `halo` start after a container was left waits up to 3 seconds, at most
  once every 10 minutes for as long as the engine stays stopped**, and a close that removes some of several
  containers but not all leaves every record to the next start.
- **An Orchestra lane with `isolation: user` did not get the container lane's changes**: past its time only its `sudo`
  client is ended; the worker keeps running, and spending, until the Halo that started it is gone, and then ends
  itself.
- **The container lane was run against a real Docker on Linux only** (a normal way out, a hard kill, a hard kill
  with no reaper left, a lane past its time: the container and its record were gone each time); on Windows and
  macOS and with podman it was tested with a stand-in engine, and podman's own message for a missing container was
  not checked against a real podman. The last fixes to it (a Halo provably gone, "No such container" with success,
  a missing engine program) came after that run and were tested with a stand-in engine that answers as Docker 23
  does.
- **Windows: a container engine reached through a `.cmd` or `.bat` shim whose daemon hangs** can hold a start or a
  close longer than its 3 seconds; Docker Desktop's `docker.exe` and `podman.exe` are single programs and are not
  affected.
- **Some 3.5 words remain**: `halo init`'s Summary after Done still prints "Lineup: <name>" (so do the lineup default
  line and the terminal UI's team preview), Studio's Orchestra workflow form still says `halo workflow run`,
  `halo isolation check` still lists 3.5 lineup and bio files, the first-run pack still rehearses a 3.5 lineup, and
  the lineup and bio prose of other docs pages (ORCHESTRA.md, GLOSSARY.md, STUDIO-sections.md, COMMANDS-init.md,
  OUTCOMES.md, PACK-AUTHORING.md and others) waits for a later release; only their command lines were fixed.
  docs/ISOLATION.md repeats its notice about the 3.5 files several times.
- **Studio's Export a clip form still says "No Chrome found on this machine: install Chrome or set HALO_CHROME"**
  when `HALO_CHROME` names nothing; starting the export gives the exact line.
- **A shared replay keeps a common-word account name outside home folders and logins.** For an account named
  `admin`, `user`, `dev` and the like, the word stays in an `ls -l` owner column, a process list, an `/etc/passwd`
  line, an ssh config `User` line, a role value, a path or web route word, prose, a domain account `CORP\name`,
  the account of a command that is not on the list in docs/REPLAY.md (`crontab -u`, `getent passwd`, `net user`)
  and of a listed command behind a wrapper (`nohup su name`, `timeout 5 id name`). 3.6.0.0 replaced the word in
  all of these, and in ordinary text with them. A machine named with a common word (`localhost`, `desktop`,
  `laptop` ...) stays everywhere; 3.6.0.0 replaced it. Search the replay for the word before you share it if you
  want it gone. A name that is not a common word is removed wherever it stands as a word.
- **A replay excerpt cut one or two letters into your account or machine name keeps those letters** before its
  `...`; a cut of three letters or more is removed.
- **A listen address `[::]` typed into either setup is saved as `127.0.0.1`** (on Windows a saved one is also read
  so), so a server that listens on IPv6 only, which Ollama does not, is not reached there; save
  `http://[::1]:<port>` for it.
- **The terminal setup's last line does not mention maps**: pick one with `halo setup map` or on the Map page of
  Studio's Setup.
- **The Builder's map-switch question looks at the folder you have open and at a folder outside any project**, not
  at each of your other trusted projects: one whose own settings or agents give main more can change with no
  question.
- **A click on the browser's alert brings Studio's window forward only when the browser allows it**; Studio is on
  the ask when you get to it.
- **`halo local stop` on a model server Halo cannot prove** says its record is kept and `halo ps` lists it, without
  naming `halo ps --forget <pid>`, which removes the record.
- **`/update` on Windows and `halo update --keep-running` on every system, for a record they cannot prove of a pack,
  shell or schedule process**, name `halo ps --forget <pid>` but no way to stop it if it is Halo's; end it where it
  runs.
- **Windows and macOS: when the clock steps back more than 2 seconds** just as Halo records a process whose start
  time it could not read, the record is dropped and Halo does not end that process when it closes. It takes both at
  once, so it is rare.
- **macOS: when `ps` itself is stuck** (a very heavy load), recording a process can wait out several of its
  5-second limits, so one tool call can stall for tens of seconds (3.6.0.0: about 10 seconds).
- **Checked on a real Mac only in part.** An earlier build of this release ran the real-use check and the closing
  tests on a real Mac, which found the macOS limit above; the macOS changes (the reaper, the records' start times,
  the test runner's look) were otherwise checked by the automated runs on macOS and on Linux taking the macOS path.
  Studio's header and "Open" on an ask were checked in a browser on Linux only; the update and `/update` changes
  were driven with stand-in process lists, not by a real update.
- **For people who build Halo:** on Windows a kept program Halo starts through WMI is found by the leftover check
  only when a scratch folder is in its command line, and a program a Bash command leaves running with `cmd &` is not
  seen by the check; on a Mac the check is blind to the programs of the macOS limit above, as the real-use check is.

## [3.6.0.0] - 2026-11-16

Agents are agents, workflows and maps now: lineups, bios and squares are no longer read, and `--team` only says so
(what to use instead: docs/MOVING-from-3.5.md). Studio closes with the command that started it, everything Halo starts
ends with it unless you asked it to keep running, `halo update` installs through a separate updater, and the Ollama
steward's background job is off until you turn it on. The rounds that built this are below the fixes; the limits
that remain are at the end of this section.

### Coming from 3.5.0.1

- **Windows: leave 3.5.0.1 with `/update` in a session, not `halo update` in a shell.** 3.5.0.1's own `halo update`
  reinstalls from inside the running halo, which holds the files it replaces, so it can leave the install half
  replaced, and nothing in 3.6.0.0 can change that old updater. `/update` in a 3.5.0.1 session hands the install to a
  script that runs after that halo has exited. Or close every Halo window, run `halo studio --stop`, and run the
  repair line:
  `uv tool install --reinstall --constraints https://raw.githubusercontent.com/roloVibes/Halo-Harness/v3.6.0.0/requirements.lock "git+https://github.com/roloVibes/Halo-Harness@v3.6.0.0"`.
- **With the LAN host turned on (`halo host install`), any system: run `halo host stop` first.** 3.5.0.1's updater
  does not see the host its unit starts: on Windows the host holds the files, on macOS and Linux it keeps running the
  old code. The unit starts it again at your next login (or run `halo host serve`).
- **The Windows installer waits for you.** `install-halo.ps1` (also the way to repair a 3.5.0.1 install) names each
  halo still running from the environment it would replace, by pid, says to close Halo, run `halo studio --stop`
  (and `halo host stop`) and run it again, and installs nothing until then. `-DryRun` says it would stop.

### Closing: nothing Halo started is left behind

- **A shell command ends with Halo.** What a Bash tool command started (`sleep`, `make`, `git`, a dev server) ends on
  every way out: Ctrl+C, a closed terminal, a normal exit and a hard kill, also when the command ran in the
  background. While it runs `halo ps` lists it as a "shell command".
- **Quitting is quick and has one time limit.** A background shell job and everything it started stop the moment you
  confirm the quit; the whole way out (waiting for a running turn, stopping what the session started, the final
  clean-up) shares one limit of about 4 seconds, and what the session started is stopped together, not one after
  another.
- **`halo ps` lists what runs.** It now shows the sessions on this home (listed, never stopped: `halo stop --all`,
  `--orphans` and a session's pid leave it alone; it ends from its own terminal), `halo --bg` runs (`halo stop bg`
  and `halo stop --all` stop them) and the updater while it runs. The Studio row has an age.
- **What a tool command left running is named.** On Linux and macOS a daemon a tool command started (a tmux server,
  an ssh ControlMaster, a dev server) still ends with Halo, now with one line: "halo: ended tmux (pid N), left running
  by a tool command; ...". To keep one past Halo, start it with `HALO_OWNER=kept-<name>`, for example
  `HALO_OWNER=kept-tmux tmux new-session -d -s work`.
- **The editor Halo opens for you is yours.** Ctrl+E (`/editor`), `/mcp`'s edit and `halo agents|workflows|maps edit`
  start your `$VISUAL` / `$EDITOR` without Halo's marker, so a GUI editor that stays open (`code --wait`, `gedit`) is
  no longer ended, unsaved buffers and all, when the session quits. The tmux server `halo --tmux` starts stays too.
- **A program Halo runs and waits for ends with it.** An Orchestra worker's `sudo` / `docker` wrapper, a pack's check
  or a git clone survived a hard kill of the Halo that ran it; it is now covered by the closing procedure. A worker
  run with `isolation: user` ends itself when the lead is gone.
- **Halo never ends a process it cannot prove is its own.** `halo host stop`, `halo host steward off`,
  `halo host rpc off`, `halo pool stop`, `halo local stop`, a quit, `halo studio --stop` and the updater signal a pid
  only when the start time written down for it matches the process that has that pid now (after a reboot a pid can
  belong to another program, and that program was ended). A record that does not match is cleared and said ("...
  signalled nothing"); a model server that still runs but cannot be proven keeps its record, and the command names
  its pid and `halo ps` and fails. The updater says "pid N was not stopped: its start time cannot be read ..." and
  never replaces files under a halo that may still run.
- **`halo studio` names the sessions it ends.** A session started from Studio's New session closes with that Studio;
  Ctrl+C on `halo studio` asks each one to finish at a safe point and prints one line naming them, with the
  `halo --resume <id>` that reopens each.
- **`HALO_CLOSE_TRACE=<file>`** (new, off when unset): one line per step of the way out (the keys read, the quit card
  and its answer, each background job stopped, the closing procedure), and the stack of every thread when a close
  still runs 4 seconds after it started.

### Updating and installing

- **Installing on Python 3.10 works again.** The dependency lock pinned a package that needs Python 3.11, so the
  installers, the README's one-line install and `halo update` stopped with "No solution found" on a stock Ubuntu
  22.04 (and its WSL image).
- **`halo update` works on a pipx or pip install.** pip refused the hash-locked dependency file, so every update of
  such an install was rolled back; pip and pipx now get the same versions without hashes, taken from the release
  being installed. uv installs are unchanged.
- **The lines Halo prints to add voice, MLX, replay clips or TLS work.** They named `halo-harness[voice]` and
  friends, which no package index has; each line is now built for your install (your installer, release or clone,
  and the extras you have), as `halo doctor --voice` prints it. `halo update` keeps the extras a uv or pipx install
  was made with.
- **`halo update --check` on a build ahead of the line it follows says so:** "this build ... is ahead of ...: the
  offer is older, nothing to apply", exit 0, nothing installed. `/update` and the once-a-day note agree.
- **`halo update` sees every halo it has to stop.** On Windows a single process anywhere with a letter such as an
  umlaut in its command line emptied the list; on Python 3.10 Studio, the supervisor, Studio's sessions and
  background runs were not counted; the LAN host (in every form Halo writes it) and a model server's watcher were not
  counted either. They are named and stopped now; the host is shown as "LAN host" and stopped through its own stop
  file, which its service does not restart in the middle of the install.
- **Windows: `halo update` works on a Python from the Microsoft Store.** It stopped with "no Python outside halo's own
  environment was found to run the updater" on a machine without `uv` and the `py` launcher.
- **`install-halo.sh` installs on the Python it names.** It reported the Python it chose (yours, or `HALO_PYTHON`)
  but let uv pick another; both install lines now pass `--python`. It looks at the same names `halo` does
  (`python3`, `python`, `python3.14` down to `python3.10`), so a stock Mac with Homebrew's `python3.13` is found, and
  with no Python 3.10 or newer it lets uv bring Python 3.12 instead of stopping.
- **`/update` ends only what it can prove is Halo's own.** The updater that runs after Halo exits ends a pid only while
  its start time equals the one Halo recorded for it (`halo update` records a Studio that opened it as it finds it).
  A process with no recorded start time is named with the command that ends it; on Windows the update then stops
  before anything is installed ("end it and run /update again"), on macOS and Linux it goes on and leaves it running.
  The fallback scripts, used where no Python outside Halo's own is found, check the start time before each kill too.

### Local models and Ollama

- **A model server that is not running is not called a network problem.** A refused connection now reads "... nothing
  is listening there (connection refused); is the model server running there? (Ollama: `ollama serve`)", with the
  port; a public host gets "is the server running, and is the port right?". Setup's "Add host & test" shows the same.
- **`halo local serve` downloads the llama.cpp build for your CPU.** An Intel Mac got the Apple Silicon build and an
  arm64 Linux or Windows machine the x64 one; now an Intel Mac gets x64, an Apple Silicon Mac (also under Rosetta)
  the Metal build, arm64 the arm64 CUDA or Vulkan build. On Windows a CUDA download brings its CUDA runtime. With no
  build for your CPU, one line says how to install llama.cpp yourself.
- **Local MLX servers and the first-run pack's Setup check never import code from your project folder** (they now
  start Python the safe way, as every other Halo child does).
- **The model picker shows what is there.** One Refresh shows a model you just pulled; a pull, delete, copy or rename,
  a load or unload in Local, and a change made from another machine refresh the list; after a long idle the first
  read builds a fresh list instead of showing an old one.
- **`OLLAMA_HOST=0.0.0.0:11434` works for this computer's Ollama.** It is the value Halo's Ollama panel suggests for
  serving the network, an address Ollama listens on but a client cannot reach on Windows, so the terminal setup's
  "this computer" row said "did not answer". The setup, a session with no Ollama host set and server discovery now
  connect to 127.0.0.1 on that port and show and save that address (`[::]` too).
- **Local's server list shows a running server whose start time cannot be read right now** (a slow `ps` on a Mac
  while a large model loads); it hides one only when the start time read now contradicts the record.

### Setup and the first run

- **Local models only, from start to finish.** `halo init --provider ollama` sets up an Ollama server with no key
  (`--model <name>` or `ol:<name>@<host>` picks the model; without one and no terminal it names the server's models
  and writes nothing). `halo init --terminal` (also the setup over SSH) has an `ollama` row: pick a server, see its
  models, pick the default. Beside a key provider use `--model ol:<name>`; the last "Default model" pick lists the
  Ollama models next to the key providers'.
- **Setup's Done never starts a halo that cannot run.** With no provider, or an Ollama host and no model, the Summary
  says what is missing and offers the page that fixes it; the step rail ticks Providers and Default model only when a
  session could use them.
- **Setup decides Done for a local-server model from your configuration, without connecting** (each load of Setup
  probed local ports for about a second). A model Halo has served, or one a configured local server serves, is ready
  while its server is stopped (starting halo starts it or says why); an MLX model is ready on Apple silicon only; a
  model no server serves gets "the server for ... is not running and none is set up for it: start it on the Local
  page (Serve), or pick another model".
- **A `routes.json` that holds a list, a string or a number no longer breaks Done.** Setup showed Done as ready and
  pressing it gave an error; such a file now reads as having no routes (one line in Halo's log), so the Summary and
  Done agree. `halo doctor` already flags it.
- **A first run with nothing set up says what to do**, not a bare "OpenRouter not configured": `halo -p` and the
  first screen of a session name the variable to set or `halo init`; with no default model they say so and how to set
  one; a Copilot (`cp:work`) session not signed in says `halo copilot signin`.
- **Ctrl+C stops `halo init`** at any prompt: "halo init: stopped; nothing more was written.", exit 130 (it was taken
  as "no key" or the default answer, and printed a traceback at the provider list).
- **A key pasted with its name or quotes is stored as the key** (`OPENROUTER_API_KEY="sk-or-..."` was stored whole and
  every call failed with HTTP 401), in `halo init` and in Setup's provider pages.
- **`halo init --provider <name> --replace-key`** asks for the key (or Databricks token) again; a refused live test
  after setup names it.
- **`halo init` sees Done** when the clock jumped back during Setup (a VM restored from a snapshot, a laptop waking),
  and its summary after Done reads your provider and model from your home, not "not set".
- **`halo init`, `halo setup` and `halo studio --edit` wait up to 45 s for Studio** (was 15 s) on a slow first start,
  and stop a Studio they give up on instead of leaving it running.
- **`halo init --no-launch` says what it does**: it serves Setup from your terminal and Ctrl+C there closes Studio.
- **Windows: the window Setup's Done opens takes your typing** when you finished Setup from `halo studio`.
- **macOS: Done tells the truth when Terminal cannot open** (macOS refused Studio control of Terminal in Privacy &
  Security > Automation): it says so with macOS's reason and that you can run `halo` yourself.
- **The terminal setup stops when its input ends.** Ctrl+D, a closed terminal or a pipe that ends used to be read
  as "the default" at every question, so `halo init --terminal` walked on and wrote a provider, a model and a
  permission mode nobody chose. It now stops with one line and writes nothing more, as Ctrl+C does. A default is
  taken only for Enter; a letter that is no answer is asked again, and `q` at the provider list stops the setup.

### Studio

- **Studio and every server Halo starts listen at once.** They asked the network for the name of the address they
  had just bound before listening; where that is slow (VPN, managed DNS) `halo studio` was silent for the wait and
  `halo init` fell back to the terminal setup. `halo mcp login` cancelled in the browser wait prints no traceback.
- **A config.json with one typo is no longer wiped.** `halo maps use`, Setup's Map page and Studio's map switch
  rewrote a file that did not parse with only the map in it; they now refuse with the line and column and leave the
  file as it was. `halo config get` (exit 2), `halo doctor`, Setup and a starting session say the file is not in
  effect, instead of reading it as empty.
- **The model picker never picks a model you cannot see**: a row the mouse wheel scrolls away loses its highlight.
- **A prompt typed into the Prompt panel shows its answer**, also a new session's first one and one typed the moment
  the session is ready.
- **The Packs page draws in a fraction of a second on Windows** (it waited about 7 s).
- **Local > Voice > Talk** says "recording" only once the microphone gives sound ("Opening..." until then), and a
  second press while it opens no longer opens a second microphone.
- **Setup > Check** keeps its result line after Run instead of flipping back to "running...".
- **`/status` and `/config` name the theme you picked in Halo**, not one left in Claude Code's settings.

### Sessions, settings and messages

- **A mistyped command does not start a session.** `halo docter` prints "halo: no command 'docter' -- did you mean
  `halo doctor`? (to send it as a prompt: halo -- "docter")" and exits 2; only a word one slip from a command is
  caught.
- **`halo config set` refuses what nothing would read**: a misspelled key (with "did you mean"), a value outside a
  setting's choices, a model that does not parse; exit 2, nothing saved. **`halo config unset <key>`** is new
  (Studio's Themes page and the docs named it).
- **Flags that name a missing file or bad JSON stop the run**: `--settings`, `--mcp-config`, `--agents` and `--cwd`,
  with one line and exit 2. A bad saved model says where it came from ("from config.json's model").
- **A session that cannot be saved says so** ("this session's log could not be written ...; it cannot be resumed"),
  and `--continue` / `--resume` skip the empty file a full disk leaves.
- **A Halo folder that cannot be used gives one line**, not a traceback: "halo: cannot use <folder> (<reason>) --
  check the owner and permissions of <folder>", exit 2 (with the `sudo chown` fix on Linux and macOS). `halo doctor`'s
  first row says whether that folder can be read and written, and a check that cannot read its file is one row.
- **A home on a filesystem without file locks no longer stalls** (a one-word `halo -p` took about a minute and a
  half).
- **A pack, agent, workflow or map file nested more than 100 levels deep** is refused as unreadable YAML; it ended
  `halo pack list` and Studio with no message.
- **`halo --tmux` runs the session with this shell's environment** (keys, `HALO_OFFLINE`, `HALO_PRIVATE`) even when a
  tmux server already runs.

### Trust and permissions

- **Your deny and ask rules for one agent hold on a map.** A chain's hop, a routed hand-off and a helper main makes
  up are decided as `Agent(<name>)`; a deny refuses the hop in one line naming the rule.
- **A map no longer raises the permission mode you set.** A map's main only narrows your mode (plan stays plan); only
  a map and main agent that are both yours may raise it, said in one line.
- **A trust record for a symlink no longer follows the link** (Linux, macOS): pointing `~/current` at a fresh clone no
  longer makes that clone trusted. Each lookup checks only the folder you are in.
- **A `~/.claude.json` record keyed with backslashes** no longer counts for a Linux or macOS folder.
- **Windows: a file in your project named like a tool is never run in its place** (`rg.cmd`, `gh.cmd`, `halo.bat`
  in a cloned repository ran on the first Grep): programs are looked up on PATH only.
- **Windows: a hook written for sh is never run by PowerShell.** With no Git Bash, a `PreToolUse` hook blocks the call
  and says why; a hook on another event is skipped as failed. `"shell": "powershell"` hooks run as before.
- **Linux: the browser Halo starts no longer shows your Studio key** to other accounts: it gets a one-time link (a
  Studio from an older version still running does not understand it: restart it).

### Windows

- **No blank terminal windows** from `halo local serve`, `halo --bg`, `halo host serve`, `halo supervise --daemon`
  or the duty steward, and closing the launching terminal still does not end them.
- **Quitting a session no longer hangs 5 to 30 seconds** on a machine with few cores.
- **Ctrl+Break in a full-screen session leaves the terminal as it found it.**
- **TaskStop, Esc or a timeout ends everything a shell command started at once**, not only `bash.exe`.
- **A thing you asked to keep survives a terminal that holds its programs in a Job object**, also a `halo update` run
  from another Halo's Bash tool; when it cannot, one line says so.
- **Git Bash is found wherever Git for Windows is installed** (per user, another drive, scoop, only on PATH).
- **The PowerShell tool and PowerShell hooks keep non-English text**, and a command may start with `using namespace`.
- **Sessions in a deep project folder are saved again** with long paths off: Halo's own session folders use a
  shorter name when the full one would not fit.
- **A folder typed in another letter case is the same folder** (sessions, memory, trust); a junction or subst drive
  keeps memory and sessions together, and `claudeMdExcludes` patterns written through one work.
- **Halo opens pages in the browser `BROWSER` names**, also inside a Job object; `halo init` prints the Studio
  address at once there.
- **Quitting a session that owns a Studio is quick on an installed Halo**, and the page hears goodbye.
- **A quit in the first seconds no longer opens a browser on a stopped Studio** when the program that started Halo
  holds it in a Job object (some terminals, CI runners): a browser start not yet begun is dropped, one on its way out
  of the Job is taken back, and the quit does not wait for either.
- **`halo doctor` passes on a machine without Claude Code** (all systems), and names your Windows release.

### macOS

- **A time-zone change no longer makes Halo lose its own processes**; a record a 3.5 Halo wrote still matches.
- **Far fewer `ps` processes**: a liveness check reads the kernel's record instead.
- **A served local model is stopped with the home's last Halo even when one `ps` is slow.**
- **A hard kill of a nested Halo** (a sub-agent, an Orchestra worker, a tmux pane) ends exactly what that Halo
  started.
- **`halo host install` and `halo supervise --service` print a line that survives a restart** (the plist is copied
  into `~/Library/LaunchAgents/`).
- **No bell over ssh or sudo**, and none when you copy in Apple Terminal (Halo uses `pbcopy` there).
- **A program named in `BROWSER` is used alone**, in its own session; the Chrome that films a clip never asks the
  login keychain.
- **The terminal setup no longer runs its Linux step on a Mac** (it offered to download a static `rg` and to add a
  PATH line to `~/.profile`, a file zsh does not read). That step is for Linux only; Windows never gets it either.

### Linux

- **`nohup halo ... &` survives the hangup.**
- **Halo never opens a text browser on your terminal, and never a browser over SSH**, without a display or with
  `HALO_NO_BROWSER` set: the address is printed. A text browser you name in `BROWSER` is still used.

### Words and docs

- **Every `halo ...` command Halo tells you to run exists** (a test checks every printed line); `halo gym propose
  --apply` writes the role table again; `halo roles` and `/roles` say where the model table is.
- **`halo explain` knows agent, workflow, map and starter**; bio, tier and block say they are 3.5 words.
- **SECURITY.md says what listens on your network** (`halo host serve`, `halo host rpc on`,
  `halo local serve --lan`) instead of the gone fleet hub.
- **MOVING-from-3.5.md covers the rest**, and no page says a Studio outlives the command that started it.
- **docs/PROCESSES.md says what Halo cannot end on macOS** (a system program a tool command detached, the moment
  before a shell command's entry is written) and what to do: start it with `HALO_OWNER=kept-<name>` to keep it, or
  end it by hand.

### R0a

Studio has room: one main thing per view, drawers and tabs instead of tiles, no sideways scrollbars, nothing smaller
than 12 px. The owner, 2026-11-12: "I agree the panel is cramped. We need to fix that for all of studio parts."

- **The stage.** The 24-column grid of tiles is gone (`lib/workspace/grid.ts`, `quiet.ts`, `room.ts`, the strips,
  Arrange, floating panels, moving a panel). Each view has one main thing (Session's Live, Agents' Canvas, Packs'
  Installed) with at least 60 % of the stage; every other panel is a named button in the view bar (one 44 px row:
  `ViewBar.tsx`, a live word beside a name where it has one) and opens as a drawer beside the main thing, full
  height, pushing it, as wide as its content says (360-560 px), or as a tab in its place (`Stage.tsx`,
  `lib/workspace/rules.ts`). Under 1440 px one drawer at a time, at 1440 and up one per side; under 1100 it floats
  over the main thing; under 760 the rail is a menu (`useBreakpoint()`). A drawer's inner edge, or `Alt+Left` /
  `Alt+Right` on it, makes it wider or narrower. A panel says how it opens: `role` (main / drawer / tab), `side`,
  `contentW` (`lib/workspace/types.ts`).
- **What is kept** (`persist.ts`, v3): the drawers open, a width you set, the tab shown, per view; opening a drawer is
  not a "custom layout" (the badge and "layout yours" went). A view whose default changes says so once ("Use the new
  one" / "Keep mine"); an arrangement saved by the old grid is dropped with one line.
- **The header.** The "+" menu went (every panel is a button in the view bar; the palette's "Show panel: <name>"
  opens one); the "..." holds Reset layout and How panels open; Arrange went.
- **One type scale and one spacing scale.** 12 (data, captions), 13 (body), 15 (titles), 18 (a page title): every
  sheet's 9.5-11.5 px became 12 (the sizes measured before: 10.5 px in 3,113 text runs, 11 px in 2,585, 11.5 px in
  1,626); spacing 4 / 8 / 12 / 16 / 24 (`tokens.css`). Buttons are 28 px tall at the least (32 by default); Live's
  agent tags and Settings' switches too. `tests/test_studio_type_scale.py` greps the sheets for a size under 12 px.
- **Cramped is a test that fails.** `tests/test_studio_room.py` (driver `tests/helpers/studio_room.py`, over the
  Session rig and a long-names seed) measures rules R1-R10 on Session, Agents, Packs, Local, Setup and Settings at
  1280, 1500 and 1920, each drawer opened in turn, then the breakpoints and what is kept.
- **Packs** (extension API 1.5): a Studio panel may say `role`, `side` and `content_w`; a 1.0-1.4 panel's grid `w`
  maps to a right drawer `w` x 60 px wide, a pack section's first panel is its main thing. The pack kit's Studio
  template declares its panels the new way.
- **The boot hop, looked into.** The Session driver's about:blank hop hid a page that stayed blank 1 in 12 runs on
  CI. About 700 direct Studio -> Studio navigations here (the second while the first still loads, under
  `HALO_STUDIO_SLOW_MS=400`) never left a blank page apart from the ones a rebuild of the dist emptied mid-run. As a
  defence, each served page now names its script with its own query (`./studio.js?b=<nonce>`,
  `studio/shell_assets.py`), so no page can take another page's script load; the room driver opens every view
  straight from the one before.

### R0a, finished

- **Installing a pack never shows it half there.** `halo pack install` writes `pack.yaml` last, and a folder under a
  packs folder with no `pack.yaml` is not a pack (`packs/discover.py`): a list read while the copy runs -- Studio's
  2 s watch, the lineups watcher, `halo pack list` in another terminal -- used to show the half-copied pack as "not
  installed (found in place)" with no API range ("any"), which is what turned `tests.test_packs_manager_ui` red on
  Linux CI and in the local gate. `halo pack doctor` names such a folder once ("a leftover folder, not a pack").
- **`halo pack remove` leaves no half pack.** The bytecode Python wrote for the modules Halo installed
  (`__pycache__/<module>.<tag>.pyc`) goes with them, so the folder goes too and `halo pack list` is clean; a file of
  yours is kept and named, and a `__pycache__` holding anything else stays whole (`packs/remove.py`).
- **A drawing fits its box when the box changes** (`lib/canvasNav.ts`, one rule for Live, Session's Map, Cast and the
  design pack's artboards): its box getting wider or narrower (a drawer opened, closed or dragged, a breakpoint) fits it again unless you
  zoomed or panned it by hand since it was last fitted; Fit makes it automatic again. Session's Map never fits below
  12 px text: it opens on the picked (else the main) agent and pans, the line under it says so; its drawer is 560 px.
- **Session's Live has room.** Every control is 28 px tall at the least and 8 px from its neighbours: the agent tags
  (a broken rule had left them at 22 px), the "steer" button beside a tag instead of over its name, "why?", "by
  group", the "N new rows" pill (under the lines now, never over one), the Agent and Attention drawers' buttons; the
  timeline's lanes are 28 px rows. Packs, Local, Setup and Settings keep 8 px between neighbours as well.
- **Halo's own secret files stay out of tool output** (`tools/halo_secrets.py`, through the tool registry): the
  secret values in the Studio info file (token, owner salt), the provider key file, MCP OAuth tokens and the host
  steward's key read as `[hidden]` in what Read, Grep, Bash, BashOutput and PowerShell show, with one line saying so.
  Nothing is refused: the file still reads. `halo config set tools.show_halo_secrets true` shows the values.
- **Tests.** `tests/test_studio_room.py` asserts R7 on Session (no control under 28 px, no overlap, 8 px apart on
  every view but Agents), R5's names (never cut in a box 24 characters wide) and R8's drawings (each one fits its new
  box, or keeps its lead node whole past the 12 px floor; a zoom by hand survives a drawer). New:
  `tests/test_packs_leftovers.py`, `tests/test_tools_halo_secrets.py`. `tests.test_packs_manager_ui` passes
  `HALO_STUDIO_SLOW_MS` to its driver (the driver environment dropped it) and waits for the row state it asserts.

### R1

Make an agent in Studio, or describe it and let the builder make it. The owner, 2026-11-12: "We need a much better way
to build custom agents, their model, what they do ... each of these sections needs a prompt box".

- **Agents -> 1 · Agents** (`Alt+2`; Live while a session runs; `1`): the list on the left (yours and this project's, tagged `new` and `not
  used yet`, then ten starters to copy) and the agent's form: name, what it does, the instructions it gets, the model
  (the shared picker, Auto first), what it may use (a switch per kind of tool, each saying what it can and cannot do),
  how careful, Try it, More, and Save / Discard changes / Copy / Delete (asked on the page). Nothing is written until
  Save. (Cast, Live and the old Workflows board stayed in the same switch until R5a removed them.)
- **The builder**, a box docked under the form: say what you want; it answers with a **preview**, one line per change
  with a tick. A line that lets an agent do more (change files, run commands, the web, a skill, a connected tool, a
  less careful mode, a higher money cap) is amber and never ticked for you. **Apply** writes the ticked lines, **Undo**
  puts the files back as they were. It works on your agents' files only. **Write it for me** fills its box. Its
  model and its daily cap (default $1.00) are in Settings -> Studio; the line beside the box shows today's spend.
- **Try it** runs the agent once, as the form holds it, as a real agent on a throwaway copy of the project (a git
  worktree, removed after), its careful mode honoured; the cost is said before, Stop ends it, the result shows in the
  tab, and a run that ends while you look elsewhere is an Attention row.
- **An agent you make is one a session can use**: the Agent tool spawns it by name.
- **The formats** (docs/CREW-FORMATS.md): `agent/1`, `workflow/1`, `map/1`, one YAML file each in `~/.halo/crew/`
  (or a trusted project's `.halo/crew/`), checked line by line (a map whose lines make a circle is named as one);
  the starters re-made in them (`halo_harness/templates/crew/`: 10 agents, the code / plan / review / research /
  media workflows, the maps `starter` and `ship-it`). The old lineups, bios and squares were left alone in this
  round; R5a and R5d retire them.
- **Routes** (docs/STUDIO-builder.md): `GET crew/agents`, `GET/POST/PUT/DELETE crew/agent/<name>`, `GET crew/workflows`,
  `GET crew/maps`, `GET crew/estimate`, `POST crew/try`, `GET crew/try/<id>`, `POST crew/try/<id>/stop|seen`,
  `GET builder`, `POST builder/ask|apply|undo`; every write owner-only. Config: `studio.builder.model`,
  `studio.builder.cap_usd`. Code: `halo_harness/crew/`, `studio/crew_api.py`, `studio/builder_api.py`,
  `live/crew_attention.py`, `studio/ui/src/routes/crew/`.
- **Tests:** `test_crew_formats`, `test_builder_flows`, `test_builder_injection`, `test_crew_try`, `test_studio_crew`
  (Chrome); `test_studio_room` measures the new tab at 1280 / 1500 / 1920.

### R2

Make a workflow -- your agents in steps, in order -- try it, save it, or describe it and let the builder draft it. The
owner, 2026-11-12: "We should do the same kind of thing for work flows, we can group created agents in work flows".

- **Agents -> 2 · Workflows** (the `2` key; the old Workflows board stayed as Board until R5a). The list on the left
  (yours and this project's, tagged `on the map` / `not on the map` -- nothing is on a map until the Map tab, and a line says so -- then the five starters to copy) and the
  form: name and where it is used; what it is for, with **Write it for me**; **the steps, in order** (a row per step:
  its name, up / down, take it out, its agents as chips that work at the same time, Gets, Hands on, When it runs,
  Repeat until at most N times; **+ Add a step** picks one of your agents or makes one -- the agent form opens filled
  in and Save comes back with the step added); what it costs and writes (a band per run from the catalog prices,
  "unknown until the first run" where Auto picks); Try it; Save / Discard / Copy / Delete asked on the page.
- **The steps, drawn** beside the form: a box per step, an arrow between, a loop mark for a repeat; it draws itself,
  zooms the house way and fits again when its box changes width (unless you zoomed it by hand).
- **The builder on this tab**: "make a review workflow: my-reviewer, then tester, repeat until the tests pass, at most 3
  times" gives one preview -- the workflow, a line per step, and a proposal card (**make it**) for an agent you do not
  have -- drawn as ghost steps in the form and the drawing; one Apply, one Undo, across agents and workflows. A line
  that lets an agent do more is never ticked for you; a workflow line widens nothing by itself.
- **Try it on a workflow**: the band said first; every step runs once on a throwaway copy of the project; each step's
  result, the agents that ran, their time and cost, each repeat's check appear as it runs; Stop; an Attention row when
  you are elsewhere.
- **A session runs a saved workflow**: the Workflow tool takes a crew workflow by name; its name wins over a square of
  the same name, and the receipt line says it ran on the step runner.
- **The step runner** (`halo_harness/crew/runner.py`, `runner_text.py`, `runner_when.py`, `runner_session.py`): each
  step's agents spawned as children through `agent/subagent.py` with the specs `crew/spec.py` builds, side by side;
  the hand-on text (each agent's reply under its name) is the next step's input with its Gets; When it runs uses the
  router's words (`workflows/when.py`, `workflows/router.py`); Repeat until is one yes/no call by the step's last agent
  after each round, at most `max` rounds (default 3, never more than 10); every call checks the workflow's own
  `max_usd` (new, optional, in `workflow/1`) and the session's cap; a step naming a missing or broken agent stops the
  run before any model call. Live draws the workflow's node, its children and the hand-off as for any sub-agent.
- **The builder's new tools** (`crew/tools_flow.py`, `crew/tools_try.py`, `crew/changes_steps.py`): `workflow_make`,
  `workflow_change`, `workflow_copy`, `workflow_remove`, `step_add`, `step_change`, `step_move`, `step_remove`,
  `try_agent`, `try_workflow` (these two start the Try it run and write nothing).
- **Routes** (docs/STUDIO-workflows.md): `GET crew/workflows`, `GET/POST/PUT/DELETE crew/workflow/<name>` (with `cost`,
  `writes`, `missing`, `maps`), `POST crew/workflow-cost`, `POST crew/try {kind: workflow}`, `POST builder/ask {tab:
  workflows}`; every write owner-only. Try it for a workflow: `crew/trial_flow.py`, `crew/try_flow.py`; the Workflow
  tool: `crew/flow_door.py`, `tools/workflow.py`, `workflows/offer.py`.
- **Tests:** `test_step_runner`, `test_builder_workflows`, `test_crew_flow_api`, `test_studio_flows` (Chrome);
  `test_builder_injection` grows a workflow-text case; `test_studio_room` measures the new tab at 1280 / 1500 / 1920.
- **Fixed (Windows), Try it:** a page polling a running Try it record no longer gets a 404 while the record is
  being written (`crew/trial.py` reads again; the reader half of R1's "a record's write waits for a reader").

### R3

Connect your agents and workflows on a map, and let your sessions run on it. The owner, 2026-11-12: "I think live is
where we can drag and drop workflows and agents and connect them together and make a big mapping connecting workflows
and agents".

- **Agents -> 3 · Map** (the `3` key): the switch reads 1 · Agents | 2 · Workflows | 3 · Map (since R5a).
  main at the left, a box per agent or workflow, one kind of line ("hands work to") with its **When** in words in a
  label lane between the columns, never over a box; hovering a box lifts its lines and dims the rest; a box grows with
  its text. Zoom the house way; Fit never under 75 %, past that the map pans from main; a hand zoom survives the drawer.
- **Add**: "Agents and workflows", a slim list in a drawer that pushes the map, a grip and **Add** on every row, Enter
  adds. While you drag a row the drop places light up and say what a drop does ("drop: main hands work to it" on a box,
  "drop: add, connect later" on the strip). **Not connected yet**, the strip under the map, holds what nothing hands
  work to; what you or the builder just made is tagged `new`.
- **Connect**: a dot on every box -- drag it to another box, or click it (Enter) for a list. The **When card** opens at
  the line: always / when the task needs (a PDF, an image, audio, video, code, a review) / when the task says (words) /
  only when I ask / main decides per task. A line's label opens its card again, or takes the line out. Chains work
  (main -> plan -> code -> reviewer); a line that would make a circle is refused in one sentence, on the page and by
  the route. A workflow box opens in place to its steps and a link to the Workflows tab.
- **Every change saves at once** with a receipt line and **Undo** (the builder's own undo store, byte for byte). A
  starter map is saved as yours on its first change.
- **More than one map**: the switcher ("this project's" first, yours, the starters, **+ New map**) with ONE switch, **My
  sessions use this** (config `crew.map`); **Lock** (off by default) stops every change.
- **The builder on this tab**: "send anything touching auth to my-reviewer after the code workflow" is one preview, a
  box line and a line line with its When in words, drawn on the map as a dashed ghost box and a dashed line; Apply,
  Undo. "what is my map?", "show me my workflows", "why did reviewer run?" are answered from `studio_show` with no
  change lines.
- **Sessions run on the map you switched on** (or `halo --map <name>` for one run; each session row carries `map`): main
  takes its model, instructions and tools from the map's main, whose careful mode may narrow your permission mode but
  never raise it (only a map and main agent that are both yours may, said in one line); the Agent tool spawns
  exactly the agents main has a line to, the Workflow tool runs exactly its workflows; a When routes a hand-off that names no target the
  way the router does; when a target finishes, the runtime follows its box's chain lines itself (an `always` line, a
  `needs` / `says` / `ask` line checked against the task and its files), never a model call; each receipt names the
  line that fired ("map ship-it · line plan -> code (always) · code"). `caps.session_usd` is the session's money cap
  (main and every hand-off): reached, hand-offs stop with one plain line. A changed map applies at the next hand-off
  and says so once; a map with a problem does not start a session half-configured: its lines on stderr, the session
  runs as with no map. With no map in use a session runs exactly as before.
- **In a session**, "make me a reviewer agent and hand reviews to it" goes through the same tools: the `Builder` tool
  (not in print mode) shows one approval card -- the plain lines in one question, each widening line its own question
  with No first -- in the terminal and in Studio's ask card; only what the person picks is written; Studio follows.
- **`halo maps list / show / use [--off]`**.
- **The compile** (`halo_harness/crew/compile.py`): a map + the files it names -> main's session config, the hand-off
  table (`{line, box, kind, name, when}` per line from main, and per box for chains), the agent specs (`crew/spec.py`,
  each with its own name as its role, so an `auto` agent is picked by `models_auto` with its `needs`; agent/1's `needs`
  may now name `tools`). `crew/map_control.py` holds it where a lineup was; `crew/map_run.py` makes main's hand-offs
  and follows the chains; `crew/map_when.py` reads a When with the router's words; `crew/map_session.py` is the session
  builder's part. Parity: a map that mirrors the auto lineup gives the same main tools, model and mode and, for the
  same tasks, the same model picks and permission modes; a child's tools are its `uses` (agent/1).
- **The builder's new tools** (`crew/tools_map.py`, `crew/tools_show.py`, `crew/changes_map.py`): `map_box_add`,
  `map_box_remove`, `map_line_add`, `map_line_change`, `map_line_remove`, `map_use` (says when the new map's agents
  may do more, amber and unticked) and the read-only `studio_show`; `crew/session_tool.py` + `tools/builder_tool.py`
  offer them to main.
- **Routes** (docs/STUDIO-map.md): `GET crew/maps`, `GET / PUT / DELETE crew/map/<name>`, `POST crew/map/<name>/use`,
  `POST builder/ask {tab: map}`; every write owner-only, each with its undo id.
- **Docs:** [STUDIO-map.md](docs/STUDIO-map.md), [CREW-sessions.md](docs/CREW-sessions.md); STUDIO-builder.md and
  CREW-FORMATS.md grow; `--map` and `halo maps` in COMMANDS; `crew.map` in CONFIG.md.
- **Tests:** `test_crew_compile` (the parity table), `test_map_chains`, `test_builder_map`, `test_builder_session_parity`,
  `test_crew_map_api`, `test_studio_map` (Chrome); `test_studio_room` measures the Map at 1280 / 1500 / 1920.
- **Tests, steadier on Windows:** the shared rigs keep one connection per thread instead of a local port per call
  (`tests/helpers/kept_http.py`; a session poll spent ~400 ports a module, held two minutes each in TIME_WAIT), and a
  connect that finds no free local port is tried again for a short, bounded time.

### R4

The map you built is the picture that runs. The owner: "this never looks right compared to what the other views are
for active workflows. It's never matching what is going on", and "I think we should be able to see the active line up
in canvas". One drawing now: while a session runs on a map, the same map lights up.

- **Agents -> 3 · Map, lit**: the tab shows a dot while a session runs on a map. The top line says "A session is
  running on this map (started 14:02)", then one sentence of what goes on (who works, who waits on what or on you, the
  models, the dollars so far: Live's own sentence) and exactly when an edit takes effect (a line, a When or a new box
  at the next hand-off; an agent's own change the next time it starts; main's model and instructions with the next
  session). Edits stay allowed.
- **Each box** says its state (working, waiting on you, done, failed, not used yet), what it does now and its cost, a
  row per fact; hover for its summary, click for its words in the drawer. **A hand-off moves along the line you drew**
  (the line the runtime's receipt named): the line lights, a dot travels it, its label shows the task for a few
  seconds, then its When again; a chain is seen box to box; with reduced motion the line lights and nothing travels. A
  background hand-off says on its line that its chain is not followed.
- **An opened workflow box** lights its steps as the step runner reports them: the step running, its agents, a
  repeat's round and its checks.
- **Helpers the session made up** (a task no line's When claimed: main makes a helper for it, on main's own tools and
  mode) show beside the box that started them, dashed, "made up for this task", with **Save as an agent**: the Agents
  form opens with an agent built from it, nothing written until you Save.
- **What they think and say**, a drawer that pushes the map: THINK, SAY, TALK, tool and ask rows, newest at the bottom,
  following as Session's Live does, filtered by the box you clicked or everyone; **Steer** and **Stop** (asked first) to
  that box's agent; an ask's answers as buttons (and its box says "waiting on you").
- **Another map running**: the top line says so in amber with **Show the running map**; several sessions: a small
  picker, one lit at a time. **A session that did not start on a map** is offered, not drawn over your map; shown, it is
  main and its helpers, "This session did not start on a map", no invented lines. An agent that matches no box is never
  dropped: it waits under Not connected yet, tagged "not on this map" and why. A box landing under Not connected yet is
  said in the top line with a link to it; a Builder card the session waits on draws its ghosts with "answer it in the
  session".
- **History under the map**: a picker of finished runs, newest first; **Replay it on the map** lights the map the run
  ran on, in quiet colours, as Live's scrubber moves it; a box the run used that the map no longer has shows dashed,
  "removed since"; **Report card** from the picker row.
- **Session's Map panel** shows the same lit map, compact and read-only, with a link to the Map tab, while a session
  runs on a map (a session not on a map keeps the tree until every session runs on one).
- **How it is built**: a session on a map sends `map_hop` (a line's hand-off start / end, a chain's line not taken),
  `map_step` (a workflow box's step runner) and `map_card` frames and keeps the first two in its log
  (`halo_harness/crew/map_events.py`); every spawn a hand-off makes carries its box on its row (`crew`). Studio's
  overlay (`routes/crew/map/overlay.ts`) is one pure function from one session's rows and frames to each box's state,
  the pulses, the opened steps, the helpers and where they hang, and the rows that match nothing; a replay feeds the
  recorded events through the same function. `runner_session.run_workflow` takes an `emit`; `GET live/replay` adds the
  map and its events; **`POST crew/from-live {session, agent_id}`** (owner-only, writes nothing) builds the unsaved
  agent body. No new listener, no model call for the picture.
- **Docs:** [STUDIO-map.md](docs/STUDIO-map.md) "While a session runs" and "History", [CREW-sessions.md](docs/CREW-sessions.md)
  (made-up helpers, the frames), STUDIO-session.md's Map panel; pictures by `tools/capture_map_live.py`.
- **Tests:** `test_map_overlay` (the overlay in node: states, a pulse on the named line, a chain, steps and a repeat, a
  helper and its parent, an ask, a row that matches nothing, replay equals live), `test_studio_map_live` (Chrome, as a
  first-time user: each point above, the room at 1280 / 1500 / 1920, a zoom while frames arrive), `test_map_chains`
  (the frames and the log, a made-up helper), `test_crew_map_api` (from-live, the replay's map).

### Fixed along the way

- **Every command and every Studio read took seconds with a large pack enabled** (the owner: "halo init on my mac
  almost freezes", Setup stuck on "reading setup"; measured on that machine: `halo pack list` 12.6 s, `halo
  --version` 0.1 s). When Halo checked a pack it read every agent file of the pack again for every stage of every
  workflow: 48 agents and 58 stages were about 2,500 YAML parses per build of the pack list. A YAML file is now
  parsed once per change (`agents_yaml._read_yaml_file`: its time, size, file id and change time; a file changed in
  the last three seconds is never kept; each caller gets its own copy). Also released as 3.5.0.1.
- **The theme picked in Halo wins.** The theme chosen in Setup, in Settings or with `/theme` now comes before a
  `theme` left in Claude Code's settings files (before, that setting came first). A `--theme` flag and the
  `HALO_THEME` variable still come first; with nothing picked the theme is `instrument`. Also in 3.5.0.1.

- **A paired host was not found in the first minute after a start.** `peers/ollama_share.own_addresses()` treated
  "nothing cached yet" as a fresh entry while the machine had been up for under a minute and raised an error, which
  the code that looks up a paired halo host read as "not paired": a host service started at logon, or anything
  that ran within a minute of boot, judged a network Ollama host as local and unknown. It now asks whether there is
  an entry before it asks how old it is.

### R4b

The lit Map takes over what the old Live view still did, and Session's two views get room. The owner first: "in the
studio sessions, map/live I am unable to adjust the sizes of the 2 views, i wanted to see the map more and shrink live
view. Actually I cannot just see the map ... the 2 views should be viewed singly too".

- **The line in the middle moves, and far.** A drawer that holds a drawing (`drawing` on its spec: Session's Map) drags
  until the main thing is 360 px wide (`MAIN_MIN`, a drawer's least), so the Map can be the bigger view; before, the
  Map was held to 560 px and to the drawers' 40 % of the stage, so at 1280 and 1500 it opened at its widest and a drag
  wider did nothing. A floating drawer (under 1100 px) drags too; a drag that loses its pointer (an iframe, a window
  switch) ends like a release. `Alt+Left` / `Alt+Right` go as far. The width is kept per view. While the line moves no
  drawing re-fits; one nobody zoomed fits once when the drag ends (`lib/canvasNav.ts holdFits`).
- **Either view alone.** **Only this** in every drawer's and the main thing's title line (`Alt+Up`; **Show both** /
  `Alt+Down` comes back): a drawer takes the whole stage while the main thing stays open, hidden, and keeps following;
  the main thing alone puts its drawers aside. The view bar says "Map only", "Live only" or "Map and Live", kept per
  view (`solo` in the layout record).
- **On the Map, what Live did:** the clicked box's facts in the drawer's head (model and why, may use, tokens, cost,
  how long) with **Pause / Resume** and **Dismiss**; the seconds on what a box does now, the box the session waits on
  outlined, the sentence's wait a link to it; a TALK between two boxes as a short dashed pulse with its first words
  (no line added; reduced motion marks the boxes); "+N under it" on a helper that started helpers, listed in the
  drawer; "plan: 3 of 7 done" from main's todo plan; a goal run going named in the top line with **Open** (its pages in
  the drawer), **Run a goal** on the Map's bar, Live's whole History (goal runs, saved files, Compare) from History
  under the map; a replay's rows in the drawer up to the scrubber; another machine's session listed in the picker;
  `J` / `K` between working boxes; **Replay the last session** when nothing runs; a hover summary card on a lit box.
  Not carried over: Hand to another machine, levels, the plan as blocks, a drawn second level of helpers, a goal run's
  lanes drawn on the canvas ([STUDIO-map.md](docs/STUDIO-map.md#what-live-did-on-the-map-3600-r4b)).
- **Moved, not copied:** the Live files the new code used (`narrate`, `useWaits`, `waits`, `replay`, `timeline`,
  `Scrubber`, `ReplaySave`, `ReportCard`, `cardData`, `now`, `roles/liveModel`) now live in `routes/crew/live/`, and the
  goal-run pages reused here (`GoalDrawer`, `GoalSays`, `RunInspector`, `RunPages`, `RunReport`, `Owns`, `goalStore`,
  `runWaits`) in `routes/crew/run/`, Live's `History` and `Compare` in `routes/crew/live/`; the old Live view imports
  them from there.
- **Docs:** STUDIO-shell.md (the rule), STUDIO-session.md, STUDIO-map.md.
- **Tests:** `test_studio_room` drags the line with real pointer events at 1280 / 1500 / 1920 and measures Session in
  all three arrangements (`tests/helpers/studio_room_split.py`); `test_studio_map_takeover` (Chrome) drives every point
  above, an ask's answer pressed in the drawer resolving the session's waiting card, and two sessions in the picker.

### R5a

Every session runs on a map, and the old lineups, bios, squares and the old canvas leave Studio and the terminal. The
owner: "I do not care if it completely removes previously saved things, this is much better". (This round's first
half: the switch, the views, the verbs and the dialogs. The modules underneath go next.)

Removed (and what replaces each):

- **Agents' Cast, Live and Board views**, with their panels (Lineups, Bios, the Inspector, Problems, Models), the
  blocks library and the board of squares, their routes (`lineups`, `lineup/*`, `bios`, `bio/*`, `state`, `session`,
  `tools`, `validate`, `yaml`, `roles/packs`, `roles/clone`, `workflows/*`), stores, CSS and drivers. Agents is three
  tabs: **1 · Agents | 2 · Workflows | 3 · Map** (keys 1 2 3; for this release C and L open the Map, W Workflows). An
  old address lands on a tab: `view=cast|live|orchestra|runs`, `mode=roles|team|orchestra` on the Map,
  `view=flows` on Workflows, `mode=fleet` on the Map with "Fleet left Halo in 3.5" once.
- **Live's node menu**: Take over is a button in the Map's drawer beside Pause (the same dialog and route); Pin is
  dropped (the drawer's filter by box does its job); Record is the scrubber's "Save this run's replay", on the Map.
  Live's History, its goal-run pages and Run a goal are the Map's drawer; a session row replays on the map it ran on.
- **Session's Map panel's tree**: the panel draws the session as its map (a session not on a map: main and the
  helpers it started), and zooms and pans the house way.
- **`halo teams`, `halo roles`, `halo blocks`, `halo workflow`, `/teams`, `/roles`**: each prints one line ("lineups
  are gone: halo maps use <name> ..."; "starters: halo workflows new <name> --from <starter>"; "use halo workflows")
  and exits 0. `halo roles point` stays for this release (the steward's and the adviser's lines offer it, and it
  reaches a session with no map).
- **The TUI's lineup editor and view, roles editor, bio editor, teams list and agents list.** `/map` shows the map
  the session runs on, read-only, with "open Studio to change it".
- **`--team <name>`**: it prints one line and the session runs on the map in use; `--map <name>` picks one.
- **The Orchestra goal form's LINEUP field**, and a pack's lineups and bios in the Pack Manager's Templates (one line
  says they are no longer read).

Changed:

- **A session with no map runs as it did on 3.5, and the Map draws it.** With no `crew.map` set (and roles on), the
  session draws the shipped `starter` map (main and planner, researcher, coder, reviewer, writer, media-reader and
  ops) so the Map tab shows what it does, but the starter sets no rules: every agent the session finds can be
  spawned (the built-ins such as Explore, your `.claude/agents`, a project's, a pack's, `--agents`), and yours wins
  over a starter agent of the same name; no money cap; sub-agents delegate two levels deep, four at a time; each
  sub-agent's model is picked as before (the same needs and routing words); the coder edits your own files (no
  worktree); `halo roles point <role> <model>` and `/role` reach the agent of that role; the Workflow tool is there;
  nothing is added to the system prompt and the Agent and Workflow tools say what they said. These values are read
  from one shipped file (R5b, below). A test compares the default session with values
  recorded on 3.5. A map you pick or write keeps its rules: main held to its lines, its cap, its instructions, main's
  `careful` narrowing your mode. A map with a problem says its lines and the session runs on the default. The step
  runner's, a chain's and `/review`'s own spawns are not held to a map.
- **One model for everything is still there**: `roles.enabled: false` with no map set means no map at all, as on 3.5
  (one model, no hand-offs). Setup's Map step lists it first; `halo maps use --none` sets it, `halo maps use --off`
  (or picking `starter`) goes back to the default, and picking a map turns roles back on.
- **The old files: one line, once.** When `~/.halo/teams`, `~/.halo/workflows`, `~/.halo/agents` (or this project's)
  hold files you wrote or changed, Halo says once that they are no longer read and where the new ones live: in the
  terminal at the first start, as an Attention row until set aside, and in `halo doctor` while they are there. The
  lineups and bios Halo itself copied there, unchanged, are not counted. A `team:` still set in config is named in
  the same line, with what to do. Nothing is deleted, converted or rewritten.
- **`halo agents`** (list / show / new [--from] / edit / try) and **`halo workflows`** (list / show / new [--from] /
  edit / try / run) work on the agents and workflows of `~/.halo/crew/`; **`halo maps edit`** joins `list / show /
  use`. `--edit agent:<n> | workflow:<n> | map:<n>` (the TUI's `/edit` too); the old `bio:` / `lineup:` / `team`
  say the old files' line and open the tab that replaced them.
- **Setup's Team step is Map**: pick the map new sessions run on (`starter` is the default); Apply writes `crew.map`.
  `halo setup map` opens it (`team` and `roles` still do), and `halo setup map --terminal` names the `halo maps`
  commands and the map in use.
- `halo agents edit` / `halo workflows edit` / `halo maps edit`: an editor that does not start is one plain line and
  exit 1, and an editor path with spaces works; `halo agents try` / `halo workflows try` stop waiting after an hour,
  on Ctrl+C or when the run's record is gone, and say why.
- A pack's panel declared for Agents (or roles, orchestra, team) joins the Map's workspace; the palette's Show panel
  lines follow the tab on screen.
- Fixes found on the way: a session on a map logged its `map_start` before the system node, so every print-mode
  session on a map failed "session log has no 'system' node"; the status strip made the page 8 px wider than a
  390 px window when a cell's text grew (it scrolls inside itself now); Reset layout counted the builder's dock as an
  open drawer; a panel's Settings never opened the inspector on an Agents tab (the column looked for the tab's
  workspace among the sections), nor kept it across a reload; History's Compare put its Apply past a narrow drawer's
  edge; a goal run's Replay from its report drew no scrubber on the Map; a goal run waiting on you had no line on a
  Map with no session running (the line says "A goal run is going" with Open now, whatever runs); Agents opened
  straight on Workflows drew nothing (its part had no height once the old bar went); Session's lit map says "more than
  fits" when it pans past the readable size, as the Map does.
- The README's Shape and Mix pictures are the Map and 1 · Agents now (`studio-map.png`, `studio-agents-tab.png`);
  the Cast pictures (`studio-workflows.png`, `studio-model-picker.png`, `studio-roles*.png`, the Roles GIF) and their
  capture tools went; the Agents tile of the modes banner, the goal run pictures and the tabs' own pictures are
  re-shot.

### R5b

The rest of Halo asks the map, not the lineup. Local scheduling, warm sets, placement, the steward, doctor, Studio's
model lookup and its file watcher, the run engine's lanes and the outcomes read the map in use and the agent files; a
session with no map reads one shipped file for what a 3.5 plain session did; packs move to extension API 2.0. (The
old lineup and bio modules still ship for the two shipped packs that drive them, first-run and coach, and are not on
any session's path; they go when those packs are re-made.)

Removed (and what replaces each):

- **Schedules and triggers of lineups** (`/agents schedule`, the supervisor's armed lineups): a map has none; `/agents
  schedule` says so in one line.
- **`halo doctor --teams`**: one line pointing at `halo doctor --agents`, which now checks your agent files (their
  problems, and each agent's own `more.check` on one call) and the map in use.
- **A lineup's acceptance as an Orchestra goal's default test** (`halo orchestra new --lineup`, Studio's run form, the
  supervisor's queue): nothing is taken; a goal's `lineup` field names the map its job's session runs on (`--map`).
- **A session's tools narrowed by its lineup's or its `--agent` bio's `tools.capabilities`**: a session reads no lineup
  or bio (a map agent's tools are its `uses`); an Orchestra lane keeps its run's list, isolation and secrets (the run
  engine's lanes still name bios while the first-run and coach packs ship them).
- The lineup graph and bio views of `studio/model.py`.

Changed:

- **A session with no map** keeps every 3.5 answer (tools, spawns, depth 2 / 4 parallel, the model picks and the
  routing words, no cap, `halo roles point` reaching the agent) from one shipped file,
  `templates/crew/plain/session.yaml` (what was the `auto` lineup and its seven bios), read from the package only. An
  `--agent` session and a session built directly hold the same answers; roles off ("One model for everything") holds
  none. `tests/test_crew_compile.py` pins it on the values recorded on 3.5.
- **Local models follow the map**: `halo local warm` / `halo local place` take a map (the one in use when none is
  named), the swap preview and the steward's rules read its agents' models ("this map swaps 2x on one card"), and
  Local's Delete names the agent files that use a model ("the model of agent `x`"). For a plain home, a home on a map
  of yours and the cold `halo local place`, every one of these answers what 3.5 answered (tests/test_crew_readers.py).
- **Local's adviser** reads what a new session's agents run on: on a plain session your `roles.<name>` over its cards
  (and the roles Halo itself reads, such as `roles.small` or `roles.judge`), on a map its agents. It had gone quiet: it
  asked a lineup no session reads any more. A role no session runs (`roles.verify`) is no lane, and a home that still
  says `team: balanced` gets the same answers as one that does not.
- **The lane offer** ("keep it as the coder lane under a model that can") keeps a plain session and points
  `roles.coder` at the model, main moving to the orchestrator: "fix" and "implement" go to that coder, two hand-offs
  deep, every spawn as before -- what 3.5's lane lineup did. A map you had put in use is taken out of use, with the
  command that brings it back. The same answer says which coder model it replaced ("(was ...)") and, when roles were
  off, each role of yours that runs again. `halo config set model` names the two commands and writes nothing.
- **Local's "Assign <role> to <model>"** writes `roles.<role>` and nothing else; **"Save as role template"** writes the
  agent `local-<preset>` on the model you picked (with no model it says so in one line). Neither writes a lineup,
  copies Halo's lineups into `~/.halo/teams` or names a retired command any more. A Verifier row now offers the
  `reviewer` card (what a plain session hands review work to), and a new session's reviewer runs on the model. A role
  no session reads is never reported as assigned: `verify` says to assign `reviewer`, Security says to save the agent
  `local-security` and hand it work by name, anything else says so in one line, and nothing is written. Studio shows
  these refusal lines (it showed "Unprocessable Entity").
- **`/status`** says the map the session runs on; **`/workflows`** lists what the Workflow tool lists: the workflows it
  runs by name (yours, the project's, an enabled pack's) and the squares it enables. A pack's workflow runs by name too,
  but never under the name of a square or of your own workflow: a bare `review` stays the review square, and a bare name
  that reaches a pack's workflow says its full `<pack>--<name>`. `halo workflows list` says the set is the session's
  (config `workflows.enabled`), and `halo roles` names the map in use or the plain session's cards, not a `team:`
  lineup nothing reads.
- **Studio's file watcher** watches `~/.halo/crew/` (agents, workflows, maps) and, in a trusted folder only, the
  project's `.halo/crew/`, so an agent, workflow or map written in a terminal shows at once in the three tabs, and the
  model lookup's cache is cleared on a change.
- **Orchestra stops a goal whose map does not exist** before it starts (one line naming the maps here), as 3.5 stopped
  a goal whose lineup did not resolve.
- **Old files**: every version of every lineup, bio and square Halo ever copied into a home is known as Halo's own
  (`crew/old_stock.txt`, written from git history by `scripts/old_stock.py`), so a long-time user's untouched copies
  are never named as theirs.
- **Extension API 2.0** (`halo_harness.ext.API_VERSION`): a pack ships `crew/agents`, `crew/workflows` and
  `crew/maps`, read in place as `<pack>--<name>` (sessions spawn its agents, `halo maps use` takes its maps, the
  Workflow tool runs its workflows). A 1.x pack still installs and runs: its bios are read as agents, its lineups as
  maps (Halo's own bio names such as `default-model` and `auto-coder` read as the starters that do that job, `extends:`
  followed, its `delegation` as the map's depth and parallel caps) and its plain workflows as workflows; a bio allowed
  WebFetch alone gets WebFetch alone (`uses: [fetch]`); a bio's `acceptance:` is its agent's check, so the hand-back
  check and `halo doctor --agents` run it as before; a lineup card's own `models.preference` is not carried (a map box
  has no model of its own) and the pack's line says so; a workflow that is not plain still runs on the run engine
  (`halo orchestra new --workflow`). `halo pack list` counts the agents, maps and workflows a pack gives, says "made for
  extension API 1.x; read by this Halo's 2.0 as 1.x" on its line, and with `halo pack doctor` says in one line what is
  not carried (a lineup naming an agent nobody has is named with why). A 3.5 name typed bare (`--map hunt`, `halo maps
  use hunt`, `--agent scout`) reads the one enabled pack's `<pack>--hunt` with a line naming it, but only when no file
  of yours, the project's or Halo's starters has that name (`--agent reviewer` is the starter reviewer even with
  doc-review enabled); `--team hunt` and a
  config `team: hunt` name the exact command. `ext.compatible` now tells the truth for a capped range;
  `ext.reads_as_1x` says a 1.x pack loads anyway. The doc-review pack ships its crew in 2.0 files.
  docs/EXTENSION_API.md "A pack's crew"; docs/MOVING-from-3.5.md.

### R5d

Most of what is left of lineups, bios, blocks and the squares' lineup half is deleted. A session behaves exactly as
before (its first request is the same, byte for byte); what went had no reader left. The lineup and bio readers that
the two shipped packs first-run and coach still drive stay until those packs are re-made on agents and maps.

Removed (and what to do instead):

- **The squares' lineup half**: a lineup's `workflows:` list and per-square rules are not read, and `halo workflows
  enable | disable | when` (already unreachable) is deleted. A session's squares are config `workflows.enabled` and
  `workflows.when.<square>`; set them with `halo config set` or Studio's Settings. The Workflow tool's lines now name
  that key, not the gone verb.
- **The role table turned into a lineup** at session start and in `halo init`'s console setup: nothing is migrated
  any more; `roles.*` is the model table sessions read as it is.
- **`halo config where`'s lineup and bio rows, and `halo doctor --config`'s lineup and bio checks** (and Studio's
  `GET doctor/config?lineup=`): those files are not read, so they are not checked; the old-files line still names
  them once.
- **The block templates** (`templates/blocks`, `halo blocks add`): start a workflow from a starter,
  `halo workflows new <name> --from <starter>`.
- **The /model picker's Agents source** lists your agent files (`~/.halo/crew/agents`, the project's, the starters,
  an enabled pack's) instead of bios; its "New bio..." row is gone.
- Modules with no reader left: lineup schedules and triggers, the lineup runtime, team bundles, the lineup answer,
  the lineup choice, the Roles problems panel, the pack bio and lineup rows for Cast, a pack's Clone, the block
  templates and the squares CLI.

Added: **your own copy to edit** (`own_copy`): `halo agents | workflows | maps copy <name> [--as <new>]` writes a
starter's (or a pack's, or the project's) file to `~/.halo/crew/<kind>s/my-<name>.yaml` and never over a file of yours;
`edit` on a starter names it. Studio's button for it comes in the next round. A workflow's `own_copy: true` field still
changes nothing (it does not move a workflow onto the run engine yet). A copy carries `from: <where> <name>` (a pack's
map: `from: pack <pack>--<name>`); once that pack is disabled, `halo maps list` and `halo doctor` say in one line that
the copied map names an agent that is gone. A copy a trusted project's own file of that name would shadow is refused
in one line naming `--as`.

Fixed after review: the /model picker's Agents source listed nothing (it asked for the wrong kind and hid the error;
only a missing or unreadable file now reads as "no agents"), and picking an agent there sets that agent's model (one
with no model of its own leaves the session's alone and says so). `halo config set` stores a list for every key the
Settings catalog types a list (`media,review`, one name, or a JSON list), so `halo config set workflows.enabled
media,review` turns both squares on; the reader takes a hand-written comma string too, and `halo doctor --config`
says in one line when a list-typed key holds one plain value. `halo config where` (and `/config where`) lists the
agent, workflow and map folders where the lineup and bio folders were: the project's, yours, the starters and each
enabled pack's (read-only), with which file wins a name two of them hold. The scheduler leftovers in the session loop and the
`templates/blocks` package data are gone. The map's caps (`max_parallel`) and its agents as `Agent(role=...)` names
keep their tests (tests/test_review2_round8c.py). The terminal's help text no longer sends anyone to
`halo workflow run`, `halo teams` or `halo workflows enable`; a few docs pages and Studio's Orchestra workflow form
still name them (see Known limits).

Docs: AGENTS.md and ROLES.md rewritten short for agents and the model table; WORKFLOWS-squares.md says config holds
the squares; MOVING-from-3.5.md lists what R5d removed and what is not moved yet, and the README links it.

### R8

A model on another machine answers as fast as that machine can. A one-word answer from a model on another machine
took 33-39 s through Halo on first use (0.2 s straight from Ollama): Halo measured the model's window before the turn
(three reloads, one past the host's cap), asked for the cap as the window, and estimated tokens 4.5x too high.

- **A turn never waits for a measurement.** No call loads a model to measure it any more (the first-use
  auto-calibration is gone). At the end of each turn one `/api/ps` read (a second at most, never one per tool step)
  says whether the model sits wholly on the card at the window used; Halo keeps that (`window_truth` in
  `ollama-fit.json`, agent/ollama_window_truth.py). A read that fails or is not Ollama's answer is unknown, never
  "not loaded": no "loading" line, nothing kept, and the window last used stays. The ladder of loads runs only when
  you ask: `halo local measure`, or Measure on a host's card in Studio's Local section.
- **The window a turn asks for** is the window the model is already loaded at on that server when it holds the
  request -- the prompt with a 15 % margin for the estimate plus the reply's full room at that window -- and is not
  on the CPU (nobody's model is reloaded, another machine's load included; what the card holds right now decides, and a
  window that runs partly on the CPU is reloaded once under it, with a line saying why). Otherwise a `halo -p` run asks for what its request needs on the
  ladder 8,192 / 16,384 / 32,768 / 65,536, and a session that takes more turns (the TUI, Studio, `--input-format
  stream-json`) asks for the largest window it may use, so a session is one load; a session that has to grow goes
  straight to that largest window. Helper calls (the small model, compaction, titles, hooks) stay on the ladder, and
  every session of one process (sub-agents too) shares the window last asked of a model, so two calls starting
  together never reload it back and forth. Never above the host's `max_ctx`, a measured cap or a window seen spilling. A
  steward profile's window still wins. The traffic ledger's `window_source` says which: `loaded`, `request size`,
  `last used`, `steward profile`, ... Auto-compaction's share is of the most the window can be.
- **A prompt the window cut is sent again.** Ollama cuts a prompt longer than the window and answers anyway (one long
  message to half the window, `num_ctx / 2 + 2`; a chat by dropping whole messages from the front). A count at that
  half, one reaching into the room kept for the reply, one smaller than the last call's while the conversation only
  grew, or one under 70 % of the estimate now marks the call trimmed and sends it once more at the largest window,
  with one line; such a count never sets the ratio. The reply's room is never squeezed by a loaded window. The
  `/api/ps` read before a call waits 3 s at most (it was 10) and says in one line when it gave up.
- **The estimate is honest.** The ledger's `estimate_tokens` is the prompt's (it carried the reply's room, 16,384
  on a first call); the real `prompt_eval_count` of a call that loaded the model (nothing cached), or one at or above
  the raw estimate, sets this model's ratio, which the next estimate starts from when chars / 3.5 is more than 15 %
  off.
- **Halo does not unload or shorten what it did not load on request.** No request carries a `keep_alive` nobody set
  (the capability battery and probe sent "5m", which overrode a server that keeps models for ever).
- **A measurement, when asked for,** never steps above the host's `max_ctx` (`halo ollama discover --calibrate` and
  Setup's "Measure the found models" too), gives the cold first load a load's own time (one load, never "does not
  fit"), keeps the safe window it measured when a later step is slow, and runs once per model digest and server
  version (`--again` repeats it). One measurement per server runs at a time, across every Halo process (a second is
  refused with a line), and it leaves the server as it found it: the model back at the window it had, or unloaded
  when it was not loaded (when the server's answer afterwards is unreadable, only that model, and the line says the
  others were not checked); the report says which.
- **The wait says what it is**: "loading <model> on <host> (16.6 GB)" before a call that loads the model, then how
  long it took -- in the TUI's status line and transcript, Studio's Live row, and a `system`/`status` line in
  `--output-format stream-json`.
- **Control from this machine with nothing but Ollama on the other one**: `halo local ps | warm | unload | pull |
  measure` (`--host`, `--json`, exit codes 0 / 1 / 2 / 3), through Ollama's own API; a server that answers with
  something that is not Ollama's answer (a sign-in page, a 401, a redirect) gets one line naming what came back and
  exit 1, never "nothing is loaded"; `halo --help` names `local` and
  `host`, `halo local --help` the verbs. Studio's host cards control an `ollama.hosts` entry no halo host serves
  through Ollama's API (Warm, Unload, Measure, Refresh, each saying what it does and costs). `halo local warm MODEL`
  loads at the window a turn will use and leaves the keep-alive to the server unless `--keep`.

### R10

When Halo closes, everything it started closes. A Studio that `halo init` started was found still running fourteen
hours later with no parent, and the next `halo init` used it. Now no process Halo started is alive five seconds after
the Halo that started it is gone -- a normal exit, Ctrl+C, SIGTERM, a closed terminal or a hard kill -- unless you
asked for it to keep running, and Halo names it on the way out with the command that stops it. (What this does not
reach yet is under Known limits.)

- **One closing procedure, on every way out** (halo_harness/closing.py): what this Halo started, newest first, is
  asked to stop the way it stops itself (Studio's stop route, a model server's stop), then signalled as a group or a
  tree, then ended hard, all inside one deadline of about 4 s for the whole way out. Nothing is printed when all is
  well; one line for each thing left running on purpose.
- **A hard kill still takes the children down.** On Windows every child Halo starts is in a Job object of Halo's,
  which the system ends with Halo (a shell command's programs cannot break away from theirs). Every Halo child (the
  Studio server first) watches the Halo that started it and closes within two seconds of it going. On Linux and
  macOS a tiny reaper waits for Halo and ends what it started when it dies without a word. Every child carries
  `HALO_OWNER=<id>` in its environment (an editor Halo opens for you does not: it is yours), so a stray is findable.
- **There is no detached Studio.** A Studio belongs to the launch that started it (`halo init` hands it to the
  session it starts in the same terminal). A launch never adopts a leftover; a Studio whose owner is alive (another
  terminal's session, your own `halo studio`) is used as it is, named in one line, and left to its owner. `halo
  setup`, `halo studio --edit` and `halo replay open` stay in the foreground while a Studio they started serves
  (Ctrl+C ends both). A page whose Studio has gone says "Studio has stopped" and stops asking.
- **What may keep running, because you asked:** `halo --bg`, `halo host serve`, `halo supervise --daemon`, a model
  server started with `--keep` (also `halo local serve --pool <model> --keep`, which `halo pool stop` stops), the
  rpc-server of `halo host rpc on` (`halo host rpc off`), the Signal pack's `/signal link` helper while it waits for
  the phone, and the updater -- each in the ledger, listed by `halo ps` and named on the way out; and the editor Halo
  opens for you. Nothing else: the host's duty steward is the host's child and ends with it.
- **The sweep at start:** a halo launch first stops what an earlier Halo left behind with no living owner (one line:
  "stopped a Studio server left from <when>").
- **Halo's own Python never imports from your project folder.** Halo started its helpers as `python -m
  halo_harness`, which put the current folder first: from a folder holding a `halo_harness/` checkout "Studio did not
  start", and a project's `json.py` would have run. Every helper now starts with `-P` (Python 3.11+) or a small
  bootstrap that drops that entry (3.10). "Studio did not start" says why: the exit code and the last line.
### R16

- **`halo -p` runs the Workflow tool in the default mode.** It hands work to sub-agents, so it now stands where the
  Agent tool does in every mode and entry point (what each sub-agent then does is still decided by its own
  permissions); it used to need a prompt nobody can answer in `-p`. TaskCreate / TaskUpdate (the session's task
  board) and SendUserMessage join the tools that never ask. The table of every tool by mode is pinned by a test.
  A deny or ask rule written for `Agent` (bare, `Task`, or `Agent(<type>)`) decides a Workflow call the same way, a
  bare `Agent` deny or `--disallowedTools Agent` takes Workflow out of the tool list, and an agent that may not
  delegate gets no Workflow. In plan mode a workflow that runs on the Orchestra (a run folder, worktrees, paid lanes,
  its test) is refused in one line, before anything is written or started.
- **`halo --help` names every command** (it named 26 of 53), grouped with the everyday ones first, each with its
  purpose, from the one list cli.py runs commands from (halo_harness/cli_commands.py). `halo recall --help`,
  `halo audit --help` and `halo preflight --help` now print their usage and exit 0.
- **`halo --version` prints one line**, `halo <version> (<commit>, <branch>)`, and no banner.
### R13

The three things that blocked the release: an update that could break the install, a steward that ran whether
you wanted it or not, and a release script that pushed to a main line that no longer takes a direct push.

- **Once 3.6 is installed, `halo update` cannot leave a half install** (the way up from 3.5.0.1 is at the top of
  this section). On Windows a `halo update` run from inside the tool environment it was replacing died halfway and
  left that environment without the package. The install now runs in a small standalone updater
  (`halo_harness/update_runner.py`, standard library only) that halo copies to `~/.halo/run/`, outside the
  environment, and starts with a Python that is not that environment's: on Linux and macOS in the same terminal
  (halo hands over to it), on Windows in the background once halo has exited, with a window that shows it. It waits
  for the old halo to be gone, stops what `halo update` already stopped before, installs, and checks that `halo --version` answers
  the new version. When the install or that check fails it puts back what was there -- the exact commit that was
  installed and a lock of the packages it had -- and says in one line what happened and the one command to run by
  hand. On Windows a halo that still holds the files (`--force`) is named and nothing is installed. The outcome is
  kept, and the next `halo update` says it once. `/update` in a session uses the same updater.
- **An older release is called older.** `halo update --check` compares versions, not commit counts on two lines
  that do not lead to each other: on a main-line build ahead of the last release it says "the newest release,
  3.5.0.1, is OLDER than this build; `halo update` would move you back", and a plain `halo update` asks for `--to`
  or `--channel main` instead of moving back. `/update` and the once-a-day startup note say the same. The release's
  checksum check stays on (`--no-verify` is the only way round it) and its refusal is one line.
- **The Ollama steward is off unless you turn it on.** Its background job (a log read every 2 s, a sampler every
  second, a tick every 5 s) kept a laptop near one full CPU core. `ollama.steward.job` now defaults to off -- a
  fresh install and a config that never set it both mean off; `true` stays on -- and off, nothing of it starts:
  no thread, no timer, no sampler. One switch turns it on and off at once, no restart: Settings -> Ollama (which
  says what it does and what it costs) or `halo config set ollama.steward.job true|false`. Off, its readers say
  "the steward is off" in one line: Local -> Steward, the status lines, `halo doctor --local`'s server-log rows;
  the TUI starts no poll of its notes.
- **A release goes through a candidate branch.** `scripts/release.py <version>` makes the version commit on
  `rc/<version>`, pushes it, waits for that branch's suites run on the exact sha, and only when every required job
  concluded success (Linux x4, Windows x4, macOS x4, studio-ui, and every system's real-use check jobs, checkout
  and installed: nineteen, all required by default and none allowed to fail in CI; an emergency alone leaves macOS
  or the real-use check out, with `--emergency-skip-macos-gate` / `--emergency-skip-realcheck-gate`, and the run
  names every leg it left out) fast-forwards master, tags and
  publishes the release with its tar.gz and `checksums.txt`. A red run stops it naming the failing jobs, with nothing tagged. "driver retried once" lines in
  the run's log are printed as warnings. `--skip-windows` is gone. It starts only from origin/master as GitHub has it,
  and a plain re-run after a red gate or a refused push resumes from `rc/<version>` (no second commit); a failed git
  step says what is done and what is left, never a traceback.
- **The updater cannot be stopped halfway.** The installer runs in its own process group and its output streams as
  it comes; a Ctrl+C or a closed terminal during the install still gets the old version put back, and the outcome
  is always written. On Windows the updater runs in a console of its own with no window, and its window only shows
  it (it stays open on any outcome but a success). A Studio that opened the halo being updated is stopped by the updater, never waited
  on; nothing is stopped before the updater is known to start; `halo update --check` writes nothing.
- **Tests:** `test_update_runner` (the real updater against a scratch tool environment: an installer that fails
  halfway, a wrong version, a failed restore, a halo that does not exit, held files), `test_update_cli`,
  `test_update_detached`, `test_steward_off` (a Studio and a session with no steward thread and under 2 % of a core
  over 20 s idle; the switch on and off), `test_release_ci_gate` and `test_release_script` over a fake `gh`.
### R14

Studio's first minute costs a second of CPU, not a minute. The owner ran `halo init` from his home folder: the page
kept spinning while Studio sat at 110% of a core for about a minute. Reproduced in a scratch home of the same shape (the
project is the home, two big packs at project scope, two Ollama hosts, a megabyte of `~/.claude.json`, past
transcripts, a 30,000-file tree) with the Setup page's own requests and `halo init`'s wait beside them: 47 CPU-seconds
in the first minute on Windows, 8.8 on Linux, never idle; Setup's first answer after 6.3 s on Windows.

- **`halo init` no longer reads the whole Setup page once a second.** While it waited for Setup's Done it fetched
  `setup/state` (every provider, model row, map and check) every second -- most of that minute. It now asks `GET
  setup/done-at` (only the Done time) and reads `setup/state` once, after Done, for the Summary's lines.
- **Each local model's "what fits" is worked out in a few steps, not hundreds.** The largest window that fits is
  found by halving the list of windows (every part of a load grows with the window, so the answer is the same), and
  the model's facts are looked up once per estimate; the estimate also reuses the host's one `/api/ps` read instead of
  one read per model.
- **One build for every request at once.** The pack list, an Ollama host's model catalog, the local models view and
  the GPU reading are each built by one request while the others wait for its answer; the local models view behind
  the model picker is kept 20 s and then answered at once while it is read again in the background (it waited 5.6 s
  on Windows for every `GET /api/models`); past 40 s the next read waits for a fresh look instead of showing a list
  that may name models that are gone. Each Ollama host and each local server port is asked side by side.
- **A pack's bios are read once per workflow check, not once per stage** (a pack of 58 bios and 48 stages read them
  7,500 times per build), with libyaml's parser where PyYAML has it.
- **Files are parsed once per change**: `~/.claude.json` for "is this folder trusted" (the file watcher parsed it
  every 1.5 s) and `config.json` for every setting read (a model row read it several times), each kept by the file's
  time, size and id, and read afresh when written in the last three seconds.
- **Setup's first answer waits at most a second for the machine's detection** (Ollama hosts, local server ports,
  the GPU); the page reads again while it is still detecting.
- **`halo studio --timings`** and **`halo init --timings`** print the wall and CPU time of each start phase, of the
  first 40 requests and of the process at 5, 10, 30 and 60 s; `GET /api/studio/timings` answers the same.

After, same home and requests: 1.2 CPU-seconds in the first minute on Windows (0.7 to idle, at 1.8 s), 0.7 on
Linux (0.5 to idle, at 0.5 s); Setup's first answer after 1.7 s on Windows, 0.5 s on Linux (1.2 s before); idle with
the page open under 1% of a core.
`tests/test_studio_first_minute.py` holds a real server to it: at most 5 CPU-seconds from launch to idle, the
address within 2 CPU-seconds, Setup's first read within 2, under 2% of a core idle, and a 50,000-file project tree
costing no more at start.
### R12

Halo works on a Mac. Nobody had run the suite on one until this week: 123 tests failed on an Apple silicon Mac, 141 on
the macOS CI runners, and his Mac beeped when a session started.

- **No beep in Apple Terminal.** A session's start-up bytes, captured on the Mac with Apple Terminal's settings, held
  `ESC ] 22 ; default BEL` (Textual's mouse-pointer shape: Apple Terminal has no such sequence, so its closing BEL
  rang the bell), a `CSI ? 2048 $ p` query Apple Terminal prints a stray `p` for, and Halo's BEL-closed window title.
  In Apple Terminal (`TERM_PROGRAM=Apple_Terminal`) none of the three is sent now (`term_profile.py`); every other
  local terminal gets what it got (over ssh or sudo the pointer shape and the mode query go only to kitty, foot,
  Ghostty and WezTerm). `tests/test_start_bytes.py` starts a real session on a pseudo-terminal and finds no BEL.
- **A session's control socket always opens.** macOS keeps 104 bytes for a socket path and its temp folder alone is
  `/var/folders/xx/.../T/`; a deep home or project gave a session no control socket, so Studio could not see it. A
  path too long now puts the socket in a short private folder (`$XDG_RUNTIME_DIR/halo` or `/tmp/halo-<uid>`, by a
  hash) with `run/<id>.ctl` naming it; one that still cannot fit is one plain line (in the transcript, and for a
  session with no terminal), never a silent nothing.
- **A folder reached through a symlink is the same folder.** On macOS `/var` and `/tmp` are links into `/private`;
  sessions, memory, `~/.claude.json` project entries and `claudeMdExcludes` patterns were kept under one spelling and
  looked up under the other ("no sessions found for this directory"). One helper, `config.paths.folder_key`, spells
  a folder for every store and lookup (the folder you are in resolved through its links on Linux and macOS, while a
  stored `~/.claude.json` key is compared as written; on Windows as the disk spells it, never through a junction).
- **The launcher and the installer find a new enough Python.** `bin/halo` takes the first of `HALO_PYTHON`,
  `python3`, `python`, `python3.14` ... `python3.10` that is 3.10 or newer (a Mac's `/usr/bin/python3` is 3.9), and
  says in one line which it looked at when none is; `install-halo.sh` honours `HALO_PYTHON` and lists each python it
  looked at with its version.
- **A steer reaches every silent sub-agent on a Mac.** Cutting a call that had not answered yet closed its socket's
  descriptor under the thread still reading it; on macOS the number went at once to the next call's connection, and
  of two sub-agents cut together one never sent its call again. On Linux and macOS the cut now only shuts the socket
  down (that wakes the reader); Windows keeps its close.
- **An ended session is ended on a Mac.** A session that had exited but was not yet reaped still answered "alive" on
  macOS (no `/proc` to say it is a zombie), so Studio waited on it; the kernel's record of the process now says so
  there (`ps` when that record cannot be read).
- **Tests ask the platform.** The MLX checks ask whether this is Apple silicon instead of assuming it is not; tests
  that compared a typed temp path with the resolved one compare the folder; a test that needs 127.0.0.2 works where
  only 127.0.0.1 exists (macOS).

### Known limits

- **macOS was checked by the automated test runs only.** The closing procedure, the Terminal and Apple Terminal
  handling, the launchd lines, the installer script and the `ps` and time-zone handling were not run by hand on a
  real Mac for this release.
- **macOS: a program a tool command detaches from its shell** (`cmd &`, then the shell exits) **that is an Apple
  system binary cannot be found at close** (macOS hides its environment from Halo), so it keeps running. Linux ends
  it. A shell command's own entry in `halo ps` also appears a few milliseconds after it starts; a hard kill of Halo
  inside that moment leaves it out. docs/PROCESSES.md ("What Halo cannot end on macOS") says what to do.
- **A quit can take up to about a second longer than its 4-second deadline** in the worst case.
- **Windows: `halo stop <pid>` on a session's shell from another terminal ends `bash.exe` only**; the programs it
  started end when the Halo that started them exits.
- **`halo update` treats any program named `halo` / `halo.exe`, and any `python -m halo_harness` of another install
  or home, as a halo to stop.** For a halo found that way, and for a Studio that opened this halo, the start time it
  goes by is read just after the process list is taken, so a pid reused in that moment is not caught; from then on a
  pid is ended only while its start time still equals that one.
- **Windows: `/update` refuses while Halo's records hold a process with no start time**, and when that pid now
  belongs to another program the refusal does not go away by itself (rare: Halo records a start time when it starts
  a process). If Task Manager shows that pid is not a Halo program, close the session and run `halo update` in a
  terminal: it signals nothing it cannot prove and removes that record.
- **The way up from 3.5.0.1** (the block at the top) is covered by an automated job on each system, not by a run by
  hand on a real install.
- **An Orchestra lane with `isolation: container`** is not given Halo's owner variables, and a lane past its time or
  a lead killed hard leaves its container running.
- **Windows with long paths off:** a sub-agent started by a sub-agent goes one folder deeper than the shortened
  session folder allows for, and a home folder longer than about 130 characters still cannot hold every file.
- **The `ps` look is kept for 1.5 s on macOS**, so a read-only listing in a long-lived process (`halo bg list`) can
  name a reused pid as the old process for that long; every path that signals reads afresh.
- **`halo studio --timings`' CPU figures do not count child processes.**
- **The line for a model server that does not answer can show twice in `halo -p` output.**
- **Some docs still describe lineups and `halo teams`**: WIZARD.md, PACKS.md, MODELS-ollama-steward-sched.md;
  `halo studio --help` still says "lineups and agent bios"; Studio's Orchestra workflow form says `halo workflow
  run`; the first-run pack still rehearses a 3.5 lineup (MOVING-from-3.5.md, "Not yet moved").

## [3.5.0.1] - 2026-11-14

A hotfix on the 3.5 line: Halo with a large pack enabled was slow to do anything, and the theme picked in Setup did
not apply. 3.6.0.0 was built beside this release, not on it, but it carries both fixes (its "Fixed along the way"), so
on 3.6 both are in place. To move from 3.5.0.1 to 3.6, read "Coming from 3.5.0.1" under 3.6.0.0.

- **Every command and every Studio read took seconds with a large pack enabled** (Setup stuck on "reading setup").
  When Halo checked a pack it read every agent file of the pack again for every stage of every workflow: a pack with
  48 agents and 58 workflow stages was about 2,500 YAML parses each time the pack list was built, which every command
  and Studio's Setup page do. A YAML file is now parsed once per change of the file (its time, size, file id and
  change time; a file changed in the last three seconds is always read again, so a same-size rewrite is never
  answered from the old copy; each caller gets its own copy). Measured with that pack in a clean home:
  `halo pack list` 7.7 s before, 0.7 s after. On 3.6: the same rule, checked by 200 same-size rewrites read back at
  once.
- **The theme picked in Halo wins.** The theme chosen in Setup, in Settings or with `/theme` now comes before a
  `theme` left in Claude Code's settings files; before, that older setting beat the pick, so Setup saved the theme and
  nothing changed. A `--theme` flag and the `HALO_THEME` variable still come first. With nothing picked anywhere the
  theme is `instrument`, as before, and `halo doctor --config` no longer says that Claude Code's setting beats the
  pick. On 3.6: the same order and the same `halo doctor --config` line.

## [3.5.0.0] - 2026-11-13

Fleet is no longer part of Halo Harness: the pack, its missions, its hub and its pages are removed; Halo is one
machine's agents and your local models. Everything about this machine's sessions stays (the registry, the control
socket, Session, Agents -> Live, History, Attention, the glance, the scrubber and the replay, steer / pause / stop),
and so does everything about local models on other machines (Ollama on the network, `halo host serve` and the host
door, the pool, the steward, capability checks). Fleet's code was saved as a standalone pack folder outside this
repository; it is not published.

### What was removed

| Thing | Lines |
|---|---|
| the shipped `fleet` pack (`halo_harness/templates/packs/fleet/`: the hub, pairing, members, missions, its CLI, Studio routes, tests, docs, UI bundle; 74 files) | 9,668 |
| core glue (`packs/fleet_door.py`, `packs/fleet_migrate.py`, `work/adapters/part.py`, the coach pack's mission coach and library share, `tools/capture_fleet.py`, `tools/live_fleet_check.py`; 10 files) and the fleet parts of other core modules | 2,693 removed (1,161 added) |
| Studio's fleet UI (Mission panel and dialogs, the mission store, Capabilities, Who, People, Pair, Health, Digest, Recall, the machine nodes and summary, mission parts, Setup -> Machines, the fleet scope on Live, three stylesheets; 30 files) | 3,732 removed (326 added) |
| fleet, mission, hub, pair and member tests (49 files) and the fleet parts of mixed modules | 10,076 removed (1,595 added) |
| docs: FLEET.md, MISSIONS.md, COMMANDS-fleet.md, STUDIO-fleet.md, four pictures; the fleet parts of every other doc | 2,676 removed (654 added) |

Studio's bundle: `studio.js` 1,430,286 -> 1,332,425 bytes, `studio.css` 273,323 -> 258,852 bytes.

### What was renamed (old -> new)

- Studio routes: `fleet`, `fleet/<harness>/<sid>/command`, `.../agents/<aid>/command|handoff`, `fleet/history`,
  `fleet/attention[/answer]`, `fleet/costs`, `fleet/caps`, `fleet/conflicts`, `fleet/<h>/<sid>/recording`,
  `fleet/recordings/<name>`, `fleet/replay` -> `live/...` (`studio/live_api.py`; another harness is a 404).
- Feed frames: a session's `fleet` frame -> `registry`; Studio's watcher's `fleet` frame -> `live`; a transcript's
  `fleet` / `fleet_note` meta -> `control` / `control_note` (the old ones are still read).
- Modules: `studio/fleet_view_api` -> `live_api`, `fleet_api` -> `live_agents_api`, `fleet_panels_api` ->
  `live_panels_api`, `fleet_handoff_api` -> `live_handoff_api`, `fleet_recording_api` -> `live_recording_api`,
  `fleet_answer` / `fleet_feed` / `fleet_send` / `fleet_watch` / `fleet_watch_sources` -> `live_*`;
  `remote/fleet_identity` -> `session_identity`, `fleet_frames` -> `agent_frames`, `cli_fleet` -> `cli_agents`;
  `packs/fleet_registry` -> `capability_check`, `fleet_rules` -> `capability_rules`; `recall_fleet` -> `recall_box`.
- Config keys (an old config still loads: the old key is read once and migrated in memory): `fleet.enabled` ->
  `control.enabled`, `fleet.private` -> `control.private`, `fleet.name` -> `harness.name`, `fleet.allow_control` ->
  `host.allow_control`, `fleet.caps.per_harness_usd_per_day` / `per_project_usd_per_day` -> `caps.*`,
  `fleet.attention.signal` -> `attention.signal`, `fleet.ollama.share` -> `ollama.share`. Every other `fleet.*` key
  is ignored and `halo doctor` says once "fleet.* settings are no longer used: Fleet is a separate pack now", naming
  them. `HALO_FLEET_PARENT` -> `HALO_SESSION_PARENT`, `HALO_FLEET_PRIVATE` -> `HALO_PRIVATE`, `~/.halo/fleet-id` ->
  `~/.halo/harness-id` (renamed once).
- Extension API 1.4: a pack's `contributes.fleet` is `contributes.capabilities` (the old name is still read, its
  `mission` key ignored, the locality `shared` gone); `ext.remote.fleet_lines` -> `live_lines` (the old name still
  answers). The shipped coach (1.0.1: no mission coach, no library fetch), first-run (1.0.1: step 7 ends on Local) and
  signal (1.0.1: `/fleet` is `/live`) packs follow; the doc-review pack declares `contributes.capabilities`.
- The `halo-harness[fleet]` extra is `[tls]` (the old name stays, for `halo host serve`'s TLS).

### What a user who used Fleet sees

`halo fleet ...` and `halo mission ...` (and `/fleet`, `/mission`, `halo recall --fleet`) answer one line and exit 2:
"Fleet is not part of Halo Harness any more (it left in 3.5.0.0); it is a separate pack." `halo studio --fleet`,
`--mode fleet` and `?mode=fleet` are gone; Agents -> Live draws this machine's sessions only, Setup has no Machines
step, Settings no Fleet page, the palette no fleet lines. A home with fleet state keeps its files (`~/.halo/fleet.json`,
`<state>/fleet/`) untouched; the pairing with a `halo host` (another machine's models) keeps working, its records
still live in those files.

## [3.4.1.3] - 2026-11-13

Every model field in Studio is a picker of the models you have: you never type a model reference from memory. Every drawing in Studio zooms the same way: Ctrl or Cmd + wheel, or a pinch. Finished background work shows up, and the agent picks it up, without you sending a message.

### Pick, don't type

- One model picker everywhere (`studio/ui/src/routes/shared/picker/`): the models of the providers set up here, grouped by provider with each provider's state in one line, searchable (ref, name, provider, best-at, takes, `cheap`, `free`, `local`, a window like `200k`), one line per row with what the model takes, keys (type to filter, Up / Down, Enter, Esc). Agents -> Models' **Test a model** (it was a bare text box), a bio's preferred model, fallback and schedule model, a lineup card's and a tier's model, the escalation's Switch to, the goal and workflow forms, the plan review, Setup's default model, Settings' model rows (`model`, `compactionModel`, both steward models, every role's model, `embeddings.model` with the Ollama models only), Session's New session, the Prompt panel's `/model `, and the design and signal packs' `model` settings all open it.
- A saved model the catalog lacks shows as it is, marked "not in your catalog", and stays selectable; with no model at all the picker says why in one line with Refresh or Setup.
- The last row of the picker, always: "use a reference that is not listed", checked as you type against the session's own parser (`GET /api/models/check`); a wrong prefix says which prefixes exist.
- A field that needs a capability (a bio's `models.needs`) lists the models that state it first and dims the others.
- Agents -> Models fits its panel: no sideways scroll; long lines wrap or end in an ellipsis with the whole on hover.
- A static check (`tests/test_studio_model_pickers.py`) fails when a new text field in Studio is labelled as a model field without going through the picker.

### Zoom and pan, the same on every drawing

- One module (`studio/ui/src/lib/canvasNav.ts`) for Agents -> Live (and its replay), Session's Map, Agents -> Cast and the design pack's artboards: Ctrl + wheel (Cmd on a Mac) zooms around the pointer, a trackpad pinch zooms smoothly, a wheel notch is one step; the page's own zoom stays put over a drawing; a plain wheel scrolls, Shift + wheel pans sideways; `+`, `-` and `0` on a focused drawing; drag the background to pan, double-click it to fit; the zoom is kept for the visit.
- Session's Map opens fitted to its panel but never smaller than its text reads: a bigger tree opens on the main agent with "more than shows: Fit shows all", and has its own - / % / + / Fit buttons; a resize no longer throws your zoom away.
- The plan review and the Workflows board keep scrolling only: both are in the Agents section the next release replaces.

### Finished background work, without a prompt

- A background sub-agent or Bash job that finishes while the session is idle shows at once, with no model call: one transcript line and the status bar in the terminal (`◼ background work finished: ...`), the session's row in Studio's Attention (Agents -> Live's chip, the glance, and the browser alert when `studio.alerts` is `browser`), the line in Session's feed (`agent/bg_pickup.py`).
- Then the main agent takes a turn by itself to read the results and report or carry on (`↻ Halo picks up the finished background work`): finishes within 3 s are one turn; never while the input box holds text or an ask is open; the turn carries no message of yours, only the finished work under the status-notice frame (not a message from the human), and is logged as such.
- `background.self_turns` (default 3) caps such turns in a row with no message from you; the session's spend cap stops them too; either says so in one line.
- `background.when_done` (Settings -> Steer and turn): `continue` (the default), `tell` (shown only; your next message reads it) or `wait` (the behaviour before). A finish during a running turn, `-p` and the other headless runs are unchanged.

### Also

- **A path cut in half is still private.** A task is shortened to 200 characters before a replay is saved; when the
  cut landed inside a home or project path, the stub that was left was kept as it was. It is now rewritten like the
  whole path (`~...`, `....`), as a cut-off name already was.
- **Dependencies:** `opentelemetry-api` 1.45.2 (CVE-2026-126360 in 1.45.1, found by the audit gate).

## [3.4.1.2] - 2026-11-12

A security pass: what a pack's page script can do is now said plainly and fenced on the server, an untrusted folder can
no longer replace a shipped pack or workflow or import your Claude files, and a fleet hub can no longer plant settings on
a member. The 2026-11-12 security review's findings, each with its test.

### Studio, packs, supply chain

- SERVERS-1, SERVERS-2: every change Studio makes needs the owner's own page. Any write without the owner proof is
  refused, except a running pack's own routes, whichever route a write takes (typing into a session or answering its
  cards included); the handlers that type into a session, start one, write or apply a bio or lineup, or shut Studio
  down check it again themselves. A test lists every write route and fails on a new one until it is classified.
- SERVERS-4, PACKS-2: a page a script opens (now also cut off from its opener), a frame, a link or a browser that
  sends no Fetch Metadata gets Studio without the owner's salt (your own reload keeps it): it can look but not change things, and its status bar (the glance: under its answers) says
  how to open Studio yourself. The shell makes the proof once at boot, keeps it where no other script on the page can
  reach it, and loads no pack's page before. `halo studio --stop` and `--edit` keep working (the salt is
  in the private studio.json beside the token).
- SERVERS-2, PACKS-6: every grant says what it gives, none is blank: `studio-script` runs the pack's code inside
  Studio's page with Studio's own power, including starting sessions that run commands; `doctor`, `cli:<verb>` and
  `studio-routes` run its Python inside halo with your rights and Halo's keys; `services` and `hooks` run its programs
  with your rights. A pack Halo does not ship gets one of those only on an explicit yes: `--grant NAME`, or
  `--grant-all` after its lines and one question (`--yes` without a terminal); the Pack Manager asks in a dialog.
- PACKS-1: a bare pack id (`halo pack install coach`, `halo pack test coach`, Studio's Install) is always the
  pack Halo ships by that id, never a folder of the current directory; a `packs.sources` entry holding a shipped id
  does not shadow it (one line says so; `halo pack install <id> --from <source>` takes it on purpose); the core's door
  to a shipped pack opens its Python only when it is the shipped one (or a fork granted `studio-routes`).
- SERVERS-5, PACKS-8: Export a clip films through a throwaway Studio of its own that answers only the replay page's
  reads; on Linux and macOS its Chrome speaks DevTools over pipes and opens no port. The running Studio's key never
  enters the filming browser.
- SERVERS-7: the speech servers answer only programs on this machine at their own address: another Host name or any
  browser Origin is refused; on Windows their port is exclusive, as Studio's.
- SERVERS-8: a host's engine offer hands a paired peer only the engine's own key, never the value of another variable an
  entry names.
- PACKS-9: the CI workflow passes a dispatch's sha to its shell as data, never as script.
- PACKS-10: `halo update` installs nothing when it cannot fetch the dependency lock and says how to install without it
  on purpose; the installers fetch and check the lock first and stop the same way.
- The design for the real fence of a pack's page (a sandboxed frame and a message broker) is written in the roadmap's
  "Pack trust" item.

### Engine, fleet files, replay privacy

- **ENGINE-1.** A cloned repo's own workflows, lineups and bios (`.halo/workflows/`, `.halo/teams/`, `.halo/agents/`)
  are read only in a folder you trusted, and a project workflow or lineup never takes a shipped or pack name (the
  shipped `media` square stays the shipped one); `halo workflows list` and `halo config where` say which project
  file is not used and why. A square the `Workflow` tool runs on the Orchestra engine starts its lanes in your
  session's own permission mode and under its rules, and a test command a project file wrote (a stage's
  `verify.test`, a lineup's `acceptance.test`) is decided as a Bash call -- your deny and ask rules, pack policies
  and hooks -- before it runs. The same gate now keeps an untrusted repo from replacing the bio the default lineup's
  main session runs, whose hooks ran at session start.
- **ENGINE-2.** In a folder you have not trusted, CLAUDE.md imports come only from inside it; under the Claude config
  folder only `*.md` files are ever imported (never credentials, settings, other projects' transcripts or history),
  every import passes your Read deny rules, and each refusal is said once when the session starts.
- **ENGINE-3.** Changing the permission mode (Shift+Tab, `/permissions`) no longer answers a card a pack, a hook or an
  untrusted skill raised; an untrusted skill's commands run only on your own allow on its card.
- **ENGINE-4.** Read and Edit deny rules now also cover `tee`, `cp`, `mv`, `install`, `ln`, `rm`, `unlink`, `shred`,
  `truncate`, `dd`, `curl -o`, `wget -O` and `rsync` in Bash, and `Tee-Object`, `Rename-Item`, `Format-Hex`, `Import-Clixml`, `Export-Clixml`,
  `Export-Csv`, piped readers, `${C:\path}` and the .NET stream readers and writers in PowerShell.
- **ENGINE-5.** Switching the main session's permission mode reaches its running and background sub-agents at once;
  a sub-agent is never left above its parent's mode.
- **ENGINE-6.** A mission part's own-outputs-folder rule lifts only the mode's ask; an ask rule of yours stays an ask.
- **PACKS-3.** A fleet member writes only the mission files its part may read and never a configuration-like path
  (`.claude/`, `.mcp.json`, `.git`, a root CLAUDE.md or AGENTS.md), whatever a hub lists, and a mission folder (or a
  repo part's worktree) is never a trusted folder. Fleet pack 1.0.4.
- **PACKS-4.** On Windows, Halo never runs a program by its bare name from the current folder: every launch resolves
  the program over the PATH folders first, and `NoDefaultCurrentDirectoryInExePath` is set before anything starts.
- **PACKS-5, SERVERS-6.** Replays, `halo export --sanitize`, `/export --sanitize`, `halo session export`, the report
  card and `halo bugreport` share one redaction: more key shapes (Groq, xAI, Perplexity, JWTs, tokens in URLs such as
  Studio's launch link, random 30-character tokens, your secret environment values), and your home path, user name
  and machine name in every spelling -- inside URLs and `user@host`, relative and `..` paths, 8.3 short names,
  percent-encoded or full-width text, agent ids, the plan and keys.
- **PACKS-7.** A hostile `.halo-replay` file cannot crash an import or the CLI (deep nesting is refused), carries no
  terminal escape sequences into `halo replay` or `halo report`, and never replaces a replay you saved.

### Privacy

- **The pre-push gate checks names again.** `scripts/prepush.py` runs `halo audit privacy` in a scratch home, so it
  never saw your private term list and every machine- and owner-name check was off in the gate. It now hands the list
  over by file name (`HALO_PRIVACY_TERMS_FILE`, never on a command line), and when there is no list it says so in one
  line ("name checks OFF"); CI, which has no list by design, says the same in its log.
- **`halo audit privacy` reads more.** Every run starts with whether the name checks are on. The name terms now cover
  the whole tree (plans, notes, reports, tools, scripts, the shipped packs, SVG text), not five folders; a finding
  names a term by its number (`term #3`), never the term; files that are not text are counted as "not checked".
  `--history` reads every ref the clone has (branches, tags, remotes), and `--since REV` leaves out what REV reaches.
  An escaped Windows profile path (`C:\\Users\\<name>` in a string) and `/home/<a real default account>/...` are found
  even when the name is a usual placeholder, unless the whole path is on the allowlist.
- **`halo audit privacy --commits`** (new) reads every commit's author and committer address and its message: an
  address that is not a GitHub noreply one is reported masked, with how many commits carry it, and a private term in a
  message by its number. They fail the audit only on a commit that is not yet on `origin/master`; older ones are
  counted (fixing them is a history rewrite). The pre-push gate runs it.
- **Personal material out of the tree.** Machine and device names, the owner's home setup, other projects, local
  folder paths and a user name in examples are replaced with neutral ones used the same way everywhere (`tower`,
  `sagan`, `laptop`, `linux-vm`, the user `you`; docs/DEVELOPMENT.md "Names to use in examples and tests"); the test
  fixture's memory text is now an invented one.
- **Release tarballs leave out the working notes.** `plans/`, `research_notes/` and `reports/` are `export-ignore`, so
  the release asset (`git archive` of the tag) no longer carries them; they stay in the repository.
- **Supported versions.** SECURITY.md says the newest release is the supported one and that versions before 3.4.1.2
  have known, fixed security problems (`halo update`). The review pages keep an open item's id, title and severity,
  without the detail of how it works, until it is fixed.
