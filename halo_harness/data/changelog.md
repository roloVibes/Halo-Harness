# What changed (the newest version entries of CHANGELOG.md, shipped with the package; `halo whatsnew` reads it)

## [3.6.0.12] - 2026-11-22

`!command` runs from Studio too. A line that starts with `!` runs that command in the session at once, from the
terminal app and now from Studio's Prompt box, through one path: it shows once in both, Esc or Stop ends it, and
closing Halo ends everything. A one-shot (`halo -p`) on a local model is sent the window Halo says it sends and the
tools of that window. And Studio reads the project of the session it shows. The limits that remain are at the end of
this section.

### Added

- **A `!command` typed in Studio's Prompt box runs in the session, as in the terminal.** A one-line `!command` runs
  that command at once: no model turn, no receipt marks, and the model sees its output on the next turn, as before. An
  image chip in the box stays for the next prompt, as in the terminal. It works while a turn is running too: a `!`
  line is never a steer and is never queued. Your line shows once, and under it one answer line: `ran` and the
  command's output; `asks first: answer below` when the session's rules ask first (the ask is the panel's own card,
  Allow there runs the command, and the terminal's card reads "Answered in Studio: Allow"); `denied: {reason}` when a
  rule refuses it (the line stays in the box); or `still running: Stop is on its row; its output shows in the Feed`
  when it has not ended after 3.5 seconds. Before, Studio sent such a line to the model as a prompt.
- **Stop on a `!` command that still runs.** In the Prompt panel the row of a `!` command that has not ended carries a
  Stop button. It ends the `!` commands running at that moment, and a running turn with them, as Esc does in the
  terminal. A `!` command started right after it is its own command and runs.
- **Esc ends a running `!` command in the terminal app.** Its card ends with `[command aborted]`, the words a stopped
  Bash call already shows. With a turn running, one Esc ends both. With no turn running and text in the prompt box,
  the first Esc clears the box, as before, and the next ends the command. Before, Esc did not reach a `!` command: it
  ran on to its end or to the Bash tool's time limit.
- **The Prompt panel's help and the docs say it:** "A line that starts with ! runs that command in the session at
  once, as in the terminal: no model turn; its output shows here and in the Feed." (docs/SLASH-COMMANDS-keys.md,
  docs/STUDIO-session.md).

### Changed

- **A `!` command is one thing in both views.** The terminal's Bash card and Studio's Feed row come from the same
  events of the session, so each view shows the command once, with its result, whichever side typed it. A session
  Studio started (no terminal) takes the same path.
- **A `!` command that asks first can be answered from either side.** The terminal's card and Studio's card are one
  decision: an Allow from Studio runs the command. Before, an answer from Studio closed the terminal's card and
  nothing ran.
- **Every interrupt sent to a session ends its running `!` commands too:** Session's Stop for a turn and an interrupt
  from a phone, not only the new Stop on a `!` row. A Stop pressed in Studio for a turn therefore also ends a long `!`
  command started in the terminal.
- **Closing Halo ends a running `!` command and answers every waiting `!` ask "no",** on every way out, in the
  terminal app and in a session Studio started: no thread and no process of it is left.
- **A one-shot on a local model is sent the tools of the window it asks.** `halo -p` on an Ollama model tries the
  windows 8,192, 16,384 and up in turn, each with the tool block a session of that window is sent, and asks the first
  that holds the request. A typical one-shot asks 16,384 and now sends the core tools first (13 tools, about 2,200
  tokens in the test home) where it sent all 28 (about 4,100); the others stay reachable through ToolSearch, and one
  line says so: "{n} tools not offered to {model} (window 16,384): the core tools first, the rest by ToolSearch". A
  very small one-shot (an empty folder, a one-line prompt) now fits 8,192. Later calls of the run keep the block they
  started with; when the run has to grow, the block grows with it. A session of more than one turn (the terminal app,
  Studio, `--input-format stream-json`), a helper's call and a cloud model are sent what they were sent before, byte
  for byte.
- **On Auto, a one-shot on a local model reads which helpers it can start,** the same two lines every other session
  reads. 3.6.0.10's notes said a one-shot keeps its one older line about delegating; that limit is gone. With the
  smaller tool block its first ask stays 16,384.
- **Studio hears the files of every open session's project.** An agent, workflow or map changed in the project of a
  session started in another folder reaches the open page at once. A folder is watched only while a session runs
  there.

### Fixed

- **A one-shot on a model that runs partly on the CPU is sent the window its line names.** When a local model is
  loaded at a window that spills to the CPU, Halo reloads it at the largest window known to fit the card and says
  "reloaded at 16k". For a one-shot whose prompt was more than half of that window, the line was printed and the
  larger, spilling window was sent all the same, so nothing was reloaded. Now the window the line names is the one
  sent, and a second line says how much room the reply has: "the prompt is more than half of it: the reply has {n}
  tokens". When the request does not fit the smaller window, the larger one is kept and the line says that instead:
  "{model} on {host} is loaded at a 32k window that runs partly on the CPU there now: kept there, the request does not
  fit 16k, the largest known to fit the card".
- **Save as an agent on Live's card reads the session's own project.** The agent built from a made-up helper took what
  it may use from `main` of the folder Studio was started in. It now takes it from the project of the session the
  helper ran in, and never offers a name an agent of that project, or of Studio's own folder, already has. Save itself
  is unchanged: it writes a new agent of yours.
- **Session's workflow line reads the session's own map file.** "This session is running the workflow ... from ..."
  read the map by its name in Studio's folder, so a session in another project with a map of the same name could show
  the other project's workflow. It now reads the file the session runs on, the one the drawing under it reads.

### Known limits

- **A `!` line from the phone bridge or from voice is still a prompt to the model.** Only the terminal app and
  Studio's Prompt box run it as a command.
- **A `!` line with a second line is a prompt,** in Studio as in the terminal.
- **A `!` line that begins with a space is a prompt in Studio's Prompt box;** the terminal runs it as a command.
- **A `/` line with an image chip is still a prompt in Studio's Prompt box;** in the terminal it runs as a command and
  the image waits.
- **A refused `!` line from Studio shows its refusal twice in the Prompt panel:** the answer line `denied: {reason}`
  and the session's own error row, the one the terminal shows.
- **`halo -p "!ls"` sends the line to the model as a prompt, as before.** A one-shot has no `!` handling. A `!` line
  sent from Studio's Prompt box to a `halo -p` run that is still running is answered "a ! command needs a session in
  the terminal app or one Studio started".
- **Stop and Esc end a running turn together with the `!` command.** There is no way yet to end only the command while
  a turn runs.
- **Stop for a `!` command is on its row in the Prompt panel only.** The Feed shows the row, but the steer box's Stop
  there is for agents.
- **Whether a small local model works as well with the core tools as with all of them was not measured.** Every check
  of the one-shot change used the tests' stand-in for Ollama, never a real model.
- **A one-shot reloaded under a spill can print the reply's room twice,** once in the new second line and once in the
  line that was already there.
- **The two changes for a model that runs partly on the CPU apply to one-shots only.** A session of more turns still
  says "reloaded at 16k" and is raised past that window when its prompt is more than half of it.
- **Session's workflow line, when the map new sessions use is not the session's own map,** still reads that other map
  by its name in Studio's folder.
- **Every Known limit of 3.6.0.11 still holds,** but the first: a `!` line from Studio now runs.
- **Where it was checked.** On the Linux VM: all three suites (the module runner's four shards, the bridge suite and
  the terminal app's suite; on a copy with no git history: the few tests that need it run in CI) and the full real-use
  check, eighteen of eighteen steps; its prompt step now sends a `!` line from Studio to a real terminal session and
  sees it run once, with no model request. On the PC (Windows), one at a time: the plain modules of this release, the
  Prompt panel's browser module once, and the terminal app's `!` tests. The whole run on the VM found one test that
  calls the quit on a stand-in object that lacked the new end of `!` work; the stand-in has it now. A package checker
  found that Studio could not end a running `!` command; the Stop on the command's row was added after that and is
  checked over the session's socket and in a browser. The reviewer found that a `!` command started right after a Stop
  was ended with the one before; each command now has its own stop, and a test holds it. The modules changed after the
  whole run were run again on the VM and the PC. Stop was not tried by hand with a real terminal session beside
  Studio. No real Ollama and no real model was used for the one-shot changes. Browsers on macOS and Windows are CI's
  part.

## [3.6.0.11] - 2026-11-22

What you pick is what you get. A default model and a map picked in `halo init` or in Studio are what a new session
runs, and Studio says so where that cannot be; Session's steer box is closed until you ask for it; Session shows the
session you started last, names it, and counts its cost once; and Up in the prompt goes to the start of the prompt
before it walks history. The limits that remain are at the end of this section.

### Changed

- **Setup saves what you pick when you leave the page.** On the Map, Default model, Permissions and Theme pages a pick
  was saved only by the page's own button (Apply on the Map page, Save on the others). Next, Back, the step rail and
  Done saved nothing, so the Summary and the next session showed the older value. Now Next, Back, a click on the step
  rail, the Summary's Change, Done, and opening another section through Studio's own rail all save the picks still
  standing first. While a pick is not saved yet, the block's foot reads "1 changed · saved when you leave this page".
  The page's button still saves at once and Revert still drops the pick. A pick made while a save is on its way is
  saved by the same leave. A refused save keeps you on the page and the foot says why; at Done the Summary says it and
  nothing is started. When Setup is left through Studio's rail the other section opens all the same, and a refused
  save shows in the block's foot when you come back.
- **Session's steer box is closed until you ask for it.** The Feed's rows take the whole height. A Steer button in the
  Feed's header, beside Follow, opens the box at the bottom with the cursor in the field; a second click closes it. A
  row's "steer" and `s` on a row open it aimed at that row's agent. An x at the end of the box's top row, or Esc in
  the field, closes it. Text typed and not sent is still there the next time the box opens; a sent steer clears the
  text and leaves the box open for a follow-up. Pause and Stop for the Feed's agent are in the box, so they show while
  it is open. Screenshot opens the box too, so its picture shows under the field. Every page load starts with the box
  closed.
- **Session follows the newest session you start, and names the one it shows.** When Session chose its session by
  itself and you start `halo` in another folder, Session moves to the new one at its next read of the session list and
  says "Now typing into {folder} · {title}." for six seconds. It follows only a session a person talks to, the
  terminal app's or one Studio started: a one-shot `halo -p` and a worker another session started never take Session
  by themselves. If the session it chose by itself ends while another runs, it moves to the newest open one. A session
  you picked yourself never moves by itself: Change session, a `?session=` link, `/studio`, New session, or a click on
  a row, a tag or a Map agent of it. Nothing moves while the Prompt box, or the open steer box, holds text. The Feed's
  header has a new last row that names the session, with a Change session button; while other sessions are open, a
  chip "N other sessions running" beside it opens the same list.
- **The Feed shows the lines of that session only.** Before, the lines of every session of this harness were mixed in
  the Feed, while the steer box and the Prompt box sent to the picked one. The Feed's "N working" counts that
  session's agents.
- **Agents > Map says which map new sessions run.** The Map select at the top left only opens a map. When the open map
  is not the one new sessions run, the top line now says "New sessions do not run on {open}; they run on {the other}."
  with a button "Run new sessions on {open}", which does what the switch "New sessions run on this" does. On Auto the
  same line stands under Auto's first line. After a change is saved on a map new sessions do not run, the receipt ends
  with the same sentence.
- **Main's box on the Map names the model a new session on that map starts on, and why:** "{model} · your default
  model", "· your last /model", "· pinned in main's own file, outranks your default model", "· from HALO_MODEL", "·
  from routes.json", "· from your work environment" or "· Halo's built-in default". On Auto a model pinned in your own
  copy of main is not used, and the box says so on a second line. Which model wins is unchanged.
- **Up goes to the start of the prompt before it walks history, in the terminal app and in Studio's Prompt box.** Up
  moves one line up; on the first line it takes the cursor to the very start and keeps the text; pressed again at the
  start, it brings back the older prompt. Down is the mirror: one line down, to the very end, then the newer prompt.
  While a recalled prompt stands untouched, Up and Down keep walking. With nothing to recall, they leave the cursor
  where it is (in the terminal app it jumped to the end). Before, Up on the first line of a long prompt went to
  history, and the start was reached by holding Left.
- **The terminal's status bar no longer shows an OpenRouter key's lifetime spend.** For a key with no limit the bar
  read "OR $... used" beside the session's cost: everything that key ever spent, in every app, with nothing saying so.
  The bar now shows an OpenRouter figure only when it is a balance ("OR $12.40 left"). `/cost` and `/providers` still
  print the key's spend, with what it is.

### Fixed

- **The default model you pick is the one a new session starts on, and the one the check names.** A model switched to
  with `/model` is remembered, and that memory outranks the default model. A `/model` made in one folder also counted
  in every folder that had no choice of its own, so one switch, made anywhere, outranked the default everywhere, with
  no end. The check's line ("Default model: ...", in the terminal setup's Checks and on Setup's Check page) told the
  truth: a new session did start on the older model. Now saving a default model forgets the remembered `/model`
  choices, in every folder: in `halo init`, on Setup's Default model page, in Settings, with `halo config set model
  ...`, and when a lineup offer on a model's card is accepted. Resetting the default model (Settings' Reset to
  default) does the same, and so does picking the model that already is the default in the terminal setup.
- **A `/model` made after that is remembered as before** and outranks the default until a default is saved again.
  While that model's provider is set up, the check names both: "Default model: {the /model one} ... [from last-used
  model (/model); config.json's model is {the default}]"; when it is not, the check's warning names the remembered
  model only.
- **A map with a problem says that new sessions will not run it.** Setup saved such a map (one that names a workflow
  that does not exist, for example) and every new session quietly ran on Auto. Apply's answer now ends with "{map} has
  a problem: new sessions run on Auto until it is fixed" and the problems; the Summary row, the rail and the Map
  glance read "{map}: has a problem, new sessions run on Auto". On Agents > Map, saving a map with a problem shows the
  red "This map has a problem" lines at once; before, the save answered that there were none.
- **A finished helper's cost is counted once.** Session's status line, the head line and the sentence of Agents >
  Live, and the Map's boxes and top sentence counted a finished helper on its own row and again inside its parent's
  figure: a session of $0.0251 whose helper had finished read "Done · $0.04". They now give the Cost panel's total,
  which is the terminal's.
- **The Prompt panel shows the prompts typed before Studio attached** as your turns, so an answer no longer stands
  without its question.
- **When the session you watched has ended and another is running,** Cost and the Prompt box say "The session you
  watched ended; {folder} is running." with Change session, in place of "No session here yet".
- **Setup: a finished measure or network scan no longer turns back to "running" for a moment.** On a slow machine the
  log and the summary of "Measure the found models" could leave the page right after the measure ended and come back
  up to a second later: the answer to the click that started it arrived after the result and was taken as newer. The
  Check page already handled this; the Ollama block now does too.
- **The real-use check on Windows leaves as soon as its result is written.** Three times at a release gate it passed
  every step, printed its last line and was then stopped while Python was ending (the C runtime's abort, with no line
  of Python's own). What stops it is not known; nothing of the result depends on that ending, and an end before the
  last line is still named.

### Known limits

- **A line that starts with `!` typed in Studio's Prompt box is not run as a command.** In the terminal app `!command`
  runs the command at once, as before. From Studio the same line still goes to the model as a prompt. It is planned
  for the next release.
- **A model pinned in your own copy of main still outranks the default model on a map that is not Auto.** The Map now
  says so in main's box; which one should win has not been changed.
- **Main's box names a remembered `/model` without checking that its provider is still set up.** If it is not, a new
  session falls back with a notice while the box still names that model.
- **Main's box on the Map speaks for the folder Studio was started in.** With the `/model` memory kept per folder (the
  default), a session started in another folder can start on that folder's remembered `/model`.
- **Closing the browser tab while a pick stands in Setup saves nothing.**
- **An install that already shows the older model keeps showing it until a default is saved once more.** Halo cannot
  tell which of the two was chosen last on an existing install. Save the default again (Setup's Default model page, or
  `halo config set model <ref>`), or switch with `/model`.
- **The remembered effort is not forgotten** when a default model is saved.
- **A `config.json` edited by hand forgets nothing:** a remembered `/model` choice still outranks a `model` typed into
  the file.
- **Unchanged:** `HALO_MODEL` and `routes.json`'s `default` still outrank `config.json`'s `model`.
- **The steer box keeps one unsent text for the page,** not one per session: text typed while one session shows is
  there when the box opens on another.
- **Up in Studio's Prompt box on one long line that wraps goes straight to the start;** the terminal app first moves
  one screen line up.
- **On Auto the Map keeps one empty line above main's box** for the "New sessions do not run on ..." line, so nothing
  moves when the line comes or goes.
- **The steer foot of the agent drawer in Agents > Live is unchanged:** it is always there.
- **On a short window the open steer box leaves the Feed little room.** With six agents on the timeline and a window
  about 800 px high, less than one row of the Feed shows until the box is closed.
- **Every Known limit of 3.6.0.10 still holds.**
- **Where it was checked.** On the Linux VM: all three suites (the module runner's four shards, the bridge suite and
  the terminal app's suite; on a copy with no git history: the few tests that need it run in CI) and the full real-use
  check, eighteen of eighteen steps. On the PC (Windows), one at a time: the plain modules of this release and, once
  each, the browser modules it changed. The whole run on the VM found that the Feed's new Change session button sat 6
  px under Export where the rule is 8; it has 10 now. The run on the PC found the short-window limit above: a browser
  step that clicks a row's steer hit the timeline instead, because the steer box left open by the step before had
  squeezed the Feed; that step now starts with the box closed, as a person meets it. The follow rule (Session moves to
  the newest session) was checked with the test rig's sessions in a browser, not with two real terminal sessions side
  by side. Browsers on macOS and Windows are CI's part.

## [3.6.0.10] - 2026-11-21

Main knows what it can do. On Auto, main is told when to hand work out and which helpers this session can start, by
name, your own agents first; a local model as main is sent the Builder tool from a 32,768 window and may propose an
agent or a workflow by itself; and the Map tab shows the list main reads. The limits that remain are at the end of
this section.

### Changed

- **On Auto, a local model running as main is told when to hand work out and whom it can start**, in the terminal app
  and in a session started from Studio. In place of its one line about delegating on a big job it reads two: "- Hand
  work out instead of doing it all yourself: give each part of a job that can run on its own (a search or survey, a
  plan, a review, a test run, mechanical edits, a file your model cannot read) to a helper with the Agent tool;
  helpers on one job share one `task`; run independent parts in parallel; keep judgement and the final review
  yourself." and "- Helpers you can start now (`subagent_type`): planner (plan, outline); researcher (research,
  investigate); coder (implement, fix, refactor); reviewer (review, audit, judge); writer (summarize, draft, docs,
  changelog); media-reader (image, screenshot, video, audio, pdf, transcribe); ops (deploy, release, install, ci);
  Judge (pass or fail a result); Tester (run tests, report). With no `subagent_type` Halo picks a kind from your
  words." That is the list of a home with no agents of your own; yours come first. The two lines are made at the
  session's first request and stay the same for the whole session (an agent you save meanwhile is in your next
  session); they are made again only when main's model changes.
- **A local model as main is sent the Builder tool from a 32,768 window** (it was 65,536 and up), in the terminal app
  and in a session started from Studio. It can make or change agents and workflows as a cloud main does: it sends the
  call, the approval card shows, and nothing is written until you approve it. It reads short words for the tool, with
  every one of the Builder's tools and its arguments by name; a cloud model keeps the long words. At 8,192 and 16,384
  the tool does not fit and is only named among the tools main can call by name, as before.
- **On Auto, main may propose an agent or a workflow by itself.** There the Builder's own words read "Use it when the
  person asks for an agent, a workflow or a map change, or by yourself to propose an agent or a workflow for work that
  will come back." On a map of yours, with roles off, in an `--agent` session and in a session restricted to some
  kinds they read as before ("..., never on your own."). The choice is made once, when the session starts.
- **When a request sends the Workflow tool and you have workflows of your own**, main also reads "- The Workflow tool
  lists workflows you can run by `name`: run one when it fits the whole job."
- **With many agents the list gives way instead of growing.** The few words leave first (the built-in kinds', then
  other agents', then Auto's seven, yours last), then names from the end, ending "and {n} more (a wrong name lists
  them all)". No prompt bound was raised for anything in this release.
- **A cloud model on Auto knows the helpers too.** In a top session on Auto the Agent and Task tools' words end with
  the same list, set once at the start.
- **The Map tab's "Main can hand work to"** (Agents, 3 Map, on Auto) names exactly the kinds a new session tells main:
  in a home with no agents of your own, 9 names where it listed 15.
- **Unchanged, letter for letter:** what main reads about handing work out on a map of yours, with roles off, in an
  `--agent` session, in a session restricted to some kinds, as a sub-agent, and with a model that takes no tools.

### Fixed

- **The builder's tools answered some wrong calls with nothing, or with the wrong words** (in a session and in
  Studio's builder box alike). `workflow_make` with steps that are not a list of steps made a workflow with no steps
  and said nothing; `step_add` with an index that is not a number put the step at the end and said nothing;
  `workflow_change` with no `fields` (or `for` outside `fields`) said "nothing would change"; an unknown field is now
  named as not a workflow's. Each now says what it needs.
- **The cloud text said custom roles are off by default.** They are on. A cloud model now reads "With custom roles ON
  (the default) the model table (`roles.*`) picks a sub-agent's model (`role:`); with roles OFF it runs the session
  model unless the call passes `model:`."
- **A helper shared main's Agent, Task and Workflow tools**, and a helper's start set their state again. Each helper
  now has its own copies.
- **The measured prompt size counts what a real new session sends** (`halo local prompt`, `/status`, the model card in
  Studio). On a cloud model the first turn measures 55 tokens larger by this fix alone, because a line the session
  always sent is counted; the fix itself sends nothing more. The bounds now also measure a new session that carries
  the Builder tool.

### Known limits

- **A one-shot (`halo -p`) on a local model is as it was.** There main keeps its one line about delegating and is not
  sent the Builder tool. A one-shot's first window is sized by its prompt, and the new lines pushed a small one-shot
  on a local model from a 16,384 window to 32,768: the whole suite found that before the release, and a local
  one-shot's request is now letter for letter what it was in 3.6.0.9. (`halo -p --input-format stream-json` and a
  remote session take more turns: they read the new lines, as the terminal app does.)
- **At 8,192 and 16,384 the Builder tool does not fit**; main can still call it by name. With Copilot set up, its own
  tool ranks first, so the Builder may not be sent at 32,768 or 49,152 either (not measured).
- **`halo local prompt` measures a session without the Builder tool**, so the figure it shows is the Builder's short
  words (about 400 tokens) lower than what a top session on Auto sends from 32,768.
- **Nothing draws yet what main handed out.** A session now counts, for each of main's turns, the helpers it started
  and its own tool calls, and its status row says which kinds main was told; Live shows neither yet.
- **Whether a local model hands work out more, or uses the Builder well, with these words was not measured.** No model
  was called.
- **On a map of yours the measured prompt size can read a little high:** it counts the map's lines on the Agent and
  Task tools but not the map's narrowing of the tools.
- **Seen and not changed:** an agent file's line `tools: Read, Agent(planner, Judge)` is split at its comma and
  restricts nothing; and an agent of yours that has a file problem and is named like one of Auto's seven stops Auto's
  map from being made, so that session runs with none of the seven.
- **Every Known limit of 3.6.0.9 still holds.**
- **Where it was checked.** On the Linux VM: all three suites (the module runner's four shards, the bridge suite and
  the terminal app's suite; on a copy with no git history: the few tests that need it run in CI) and the full real-use
  check, eighteen of eighteen steps. On the PC (Windows), one at a time: the plain modules of this release and the
  tests of how a local model's window is sized. The first whole run on the VM found what the first limit above says:
  with the new lines a small one-shot on a local model asked a 32,768 window where it had asked 16,384, and seven
  tests of window sizing failed; a one-shot now keeps its one line and those tests pass unchanged. That run also
  showed that an older test left the governor's cooldown for a local host behind it, which failed another test once
  the suite's order moved; that test now cleans up after itself. Not run: any real model (every figure here is Halo's
  own measure of what it sends), macOS, Windows beyond the modules named (CI runs both at the release gate), and
  Studio's Map tab in a browser.

## [3.6.0.9] - 2026-11-21

What Studio shows now follows the files. When a session, the Builder's card or a hand changes a workflow, a map or an
agent, the workflow you have open, the map you have open and the drawings show it a moment later, with no reload. The
limits that remain are at the end of this section.

### Changed

- **The workflow you have open follows its file** (Agents, 2 Workflows). When the workflow that is open in the form
  changes on disk, the form shows the new steps and words a moment later. Before, the list beside it showed the new
  number of steps while the form kept the old ones, and Save would have written the old ones back over the change. If
  you have unsaved edits in the form, nothing you typed changes: the form says "{name} changed on disk while you had
  edits here. Save writes yours over it." with the button "Reload it (your edits go)". If the file is removed, the
  form stays and says "{name} was removed on disk. Save writes it again." A pack's workflow that is open read-only
  shows the pack's new steps when the pack changes. In the list, a workflow's "on the map" tag now follows a map
  changed while you look at it; before, it changed only when a workflow file changed or the list was read again.
- **The map you have open follows its files** (Agents, 3 Map). The map is drawn again when its file changes; a
  workflow box shows its workflow's new steps and an agent box its agent's new model when those files change. Before,
  a map written other than by the Builder's card, or a changed workflow or agent on one of its boxes, re-read only the
  list of maps: the open map stayed old until you switched maps or reloaded the page. A box you opened, an open When
  card and an Undo on offer stay as they are. While you drag a box or a line the redraw waits for the drop; a drag
  whose release never reaches the window (the window lost the focus) now ends as Escape ends it. A locked map is drawn
  again too.
- **The drawings follow a changed workflow** (Session's drawing; Agents, 4 Live draws with the same code). A workflow
  box's steps follow the workflow's file: after a plain write, and after a Builder card that changed only the
  workflow, with "new" on the new steps. Before, a plain write showed nothing, and a Builder card put "new" on the old
  steps. A step's model follows the agent's file, where the map has an agent box for that agent.
- **What was built is still said after a reload.** After a Builder card, Session's head ("Changed in this session at
  ...", "Just built: ..."), the ready lines on Auto and "new" on the boxes it wrote are there again when the page is
  loaded again in the same tab, for that session. Before, a reload showed the new steps and dropped every word about
  what had changed. Only that browser tab keeps them (at most the 20 newest sessions); nothing leaves the machine.
- **A workflow changed by a plain edit is said in words.** When a workflow on a box of the session's drawing changes
  on disk and no Builder card wrote it, Session's lines gain "The workflow {name} changed at {time}. A run already
  going keeps its steps; the next run takes the change." It is one line however many changed: "The workflows build and
  review changed, the last at {time}. ..." names the newest first, three at most, then how many more. The room for the
  line is held from the first draw, so nothing moves when it comes. On Auto the line is for a workflow the session has
  run or is running. A Builder card that wrote the workflow shows its own head and not this line as well.
- **The real-use check says how it ended itself** (for developers). `python scripts/realcheck.py --name-the-end` runs
  the check as a child and, when the check did not end by its own exit, prints one line with the true exit status and
  its kind; the check also turns on Python's own fault reporter. CI passes the switch.

### Fixed

- **A Builder card's write was read twice.** Studio's file watcher reports every write about a second and a half
  later, and the page then read again what the card had just brought. The page now compares the file's hash with what
  it holds and reads only what differs; a different write that lands right after is still read.
- **A local model server could keep running after the last Halo on its home was killed.** A session that is killed
  hard cannot take its row out of the list of sessions, and the watcher that stops the server took that row for a
  living session for as long as any program had its process number; Windows can give a dead number to another program
  soon after. The watcher now tells such a program from the session by when it began. That works on Windows and macOS;
  on Linux a row carries nothing to tell by, and the number is taken at its word, as before. On Windows the watcher
  also waited two seconds for the server to obey a soft stop that the system had refused outright, as it does for a
  console program, which a model server is. It now goes on to the hard stop at once: by its own waits the server now
  ends at most a little over one second after its last Halo, where it was up to a little over three.

### Known limits

- **Studio follows the files of its own folder.** A session started in a terminal in another project writes that
  project's workflows, maps and agents where Studio does not look: they are not listed and not followed.
- **A session whose model gets the short tool list is not sent the Builder tool** (a small context window: measured
  with the default tools at 49,152 and below; sent at 65,536). Such a session can change a workflow only by editing
  its file. Studio now shows that change; the card's head and the "new" marks come only with the Builder's card.
- **Agents, 4 Live has no test of its own for this.** It draws with the code Session's drawing uses, which is tested.
  Live has no head and no "changed" line of its own.
- **The line can still move the drawing once** in two cases: a session that was started before this release, and a
  workflow box added to the map after the session started (until its next hand-off).
- **One order is not tested:** the watcher's report of a Builder card's write reaching the page before the card's own.
  The card's session then still shows the card's head; another session with the same workflow on a box keeps the line.
- **On the Map, not checked during a redraw:** the picked box, and a Builder ghost waiting for Apply or Undo. When the
  open map's file is removed, the tab does nothing, as before.
- **Not understood: how the real-use check ended once at the gate of 3.6.0.8.** On CI's Windows runner both real-use
  jobs passed all 18 steps, and then their checker ended with status 127 and no line of its own. Git Bash reports 127
  for a crash-kind Windows status. The rerun and the release's own run were green. The switch above is there so that
  the next time names itself.
- **Every Known limit of 3.6.0.8 still holds.**
- **Where it was checked.** On the Linux VM: all three suites (the module runner's four shards, the bridge suite and
  the terminal app's suite; on a copy with no git history: the few tests that need it run in CI) and the full real-use
  check through its new parent, eighteen of eighteen steps. This release's browser tests ran there on a real headless
  Chrome: the open workflow's form, the open map (also with a drag in hand), Session's drawing, one read per change,
  the head after a reload, and the line for a changed workflow (also on Auto). On the PC (Windows), one at a time with
  a real headless Chrome: the three Studio modules that hold these browser tests (the Workflows tab, the Map tab and
  Session's drawing), and the plain and node modules the change touches. CI's first run on this release then failed
  once in the real-use check on its Windows runner: of 28 ways out, a hard kill of a session with a model server
  beside it left the server and its watcher running 5 s later. Reading the watcher found the two things under Fixed:
  the first explains why only a hard kill failed (only a hard kill leaves the session's row; the same case passed by
  Ctrl+C and by a closed terminal), and the second took 2 s off every way out. The run cannot be repeated on demand.
  Each has a test that was red before. The same run showed, on CI's Linux and macOS runners, that the Workflows list's
  "on the map" tag did not follow a changed map: its test had passed elsewhere only by its timing, and now tests the
  rule. Not checked by hand: macOS (CI's macOS runners ran the suites and the real-use check). Not run: Agents, 4
  Live, a real model asked to change a workflow, and a session started in another folder than Studio's.

## [3.6.0.8] - 2026-11-21

Halo runs and drives a browser by itself. Every session has a built-in Browser tool that uses a browser already on
the machine, with nothing to install and no other product in between; Studio shows each step in words and with a
picture of the page, and you can have a window you can watch. The limits that remain are at the end of this section.

### Added

- **A built-in Browser tool in every session.** Halo finds Google Chrome, Chromium, Microsoft Edge or Brave already on
  the machine (in that order, or the one `HALO_CHROME` names), starts it itself and drives it. Nothing is installed
  and nothing is downloaded. A session started from Studio has it too. With no browser on the machine the tool
  answers "No browser found: install Google Chrome, Chromium, Microsoft Edge or Brave, or set HALO_CHROME to a
  browser's path. Halo downloads none."
- **What it can do.** Open a page, read it, click, type, press a key, scroll, go back, run JavaScript in the page,
  take a screenshot, close. Every answer but screenshot's and close's gives the page's title, its address, its visible
  text and a numbered list of what can be pressed or typed into; a control is named by its number, its words, or
  `css:<selector>`.
- **Real pages.** When a click opens a new tab the browser goes on in it and the answer begins "A new tab opened; now
  on it." A page's alert, confirm or prompt box is answered at once and the answer begins "The page showed a box:
  '...' (accepted)." A page that never finishes loading is read as it stands after 15 s, and the answer says so. A
  download lands in the session's attachments folder when it is whole, and the answer says where.
- **You can see the page.** After every action that can change the page, its picture is kept in the session's
  attachments folder (the newest 20) and the answer names it. In Studio, a Browser step shows in Session's Live column
  and in Agents -> 4 · Live in plain words ("Browser open <address>", "Browser click <target>" ...), and a click on
  the step opens the picture of the page after it. The picture is not sent to the model; `screenshot` sends one.
- **A window you can watch.** Settings has a head "Browser" with two settings. **Window**: "shown opens the browser
  Halo drives as a window you can watch and sign in to; hidden runs it out of sight." (`halo config set
  browser.window shown`; the tool's `show: true` does it for one session). **Profile**: "kept remembers sign-ins
  between sessions in Halo's own folder (never your own browser's); clean starts empty every time."
- **Sign-ins stay.** By default the browser uses a profile of Halo's own, kept between sessions, so a sign-in you make
  once in the shown window is there next time. It is never your own browser's profile. One session uses it at a
  time; another session at the same moment starts clean and says so.
- **`halo doctor` has a row `browser`**: which browser Halo will use, or the line that says what to install.

### Changed

- **`--chrome` is no longer the way to a browser.** Its doc now says it uses another product's browser extension and
  works only while that product does; the built-in Browser tool needs neither. The tip that named it names the
  built-in tool.
- **`--playwright` runs a fixed version** (`@playwright/mcp@0.0.86`, never the latest), says once before it starts
  what the first start downloads (about 59 MB), and writes its page files in Halo's own folder, removed when the
  session ends, instead of the folder halo was started in.
- **Permissions for the tool.** Open, read, screenshot and close are decided as WebFetch is for the same address (a
  rule `Browser(domain:example.com)` works); click, type, key, scroll, back and js ask in the default mode and never
  in Auto.

### Fixed

- **Four `halo doctor` fix lines named headings that did not exist**, the Chrome row's among them ("see README.md
  (Browser)"). They name real ones now.

### Known limits

- **Nothing listens on the network.** The browser talks to Halo over a pipe on Linux, macOS and Windows. It is Halo's
  own child: it ends with the session on every way out, and `halo ps` lists it while it runs. The helpers the browser
  starts for itself (its crash handler; on macOS the updater it wakes) are ended with it on Linux and macOS: asked to
  end, and ended at most a second later if still there. What it may leave on the machine is Halo's kept profile only.
- **A sign-in survives every ordinary way out** (quitting the terminal app, ending a session from Studio, Studio
  stopping, the end of `halo -p`): Halo asks the browser to close and waits up to three seconds. A kill of Halo itself
  cannot do that: a sign-in made in its last seconds may then be lost. Quitting the terminal app with a browser open
  was not run for real on any system: only the order of its steps is tested. Studio stopping was driven inside the
  test's own process, not by a real `halo studio --stop`.
- **In Studio the picture's box can change its height once** when a browser shown as a window took the picture: the
  page is smaller than the 1280 by 800 the box starts with.
- **A download that cannot be moved into the session's folder is dropped without a line.**
- **A session whose model gets the short tool list** (a small context window) is offered the Browser tool by name
  only; it can still call it.
- **The window was never opened in a test**: only the way the browser is started for it is checked. macOS was run on
  CI's runners only (a headless Chrome there), never on a person's Mac. On Windows, Edge was run only as far as
  starting and answering over the pipe; Brave and Chromium were never run, and only finding them is tested.
- **Every Known limit of 3.6.0.7 still holds.**
- **Where it was checked.** On the Linux VM: all three suites (the module runner's four shards, the bridge suite and
  the terminal app's suite; on a copy with no git history: the few tests that need it run in CI) and the full real-use
  check, eighteen of eighteen steps. Its new step starts a real Halo that opens a real page in a real installed
  browser, presses a button, takes its pictures and closes; nothing of the browser is left after a normal end and
  after a hard one. The system's temp folder was listed before and after a session there and on the PC: nothing of the
  browser was added. On the PC (Windows), with a real headless Chrome, one at a time: the browser's own modules (among
  them a sign-in that is still there in the next session), the Studio module (a session started from Studio opens,
  presses and pictures a page; Live shows the steps and the picture), the changed plain modules and the node checks,
  and the two new real-use steps. Chrome and Edge both answered over the pipe on Windows. The whole suite found five
  things at the join, none in what the browser does (lists of main's tools and a recorded request that now hold the
  Browser tool, a rule about reading the home folder, a test helper's server, the browser module started `ps` through
  the standard starter): each is settled. CI then ran the browser's modules and the real-use step on its Windows and
  macOS runners, with the Chrome installed there, and its first run found two more things, both in how the browser
  ends: on Windows a start that came right after a hard end left that session's folder for a later start, and on macOS
  Chrome's crash handler and the updater it wakes ran on after the browser was closed. Each has a fix and a test that
  was red before, and this release's own CI run passed on both runners with them. Not run: a person's Mac, a browser
  shown as a window, Edge beyond starting and answering, Brave and Chromium at all, and quitting the terminal app with
  a browser open on any system.

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
