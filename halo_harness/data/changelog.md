# What changed (the newest version entries of CHANGELOG.md, shipped with the package; `halo whatsnew` reads it)

## [3.6.0.19] - 2026-11-24

Local models: the session you really get. A session on a local model is now sent the window Halo names, with the
tool block of the window its first request is sent at (where the two can still part is in the Known limits). A new
conversation is not compacted before it has an answer (on one real model that compaction threw the first question
away). `halo local prompt` measures the session you get, and with Copilot set up main keeps the Builder. This
release was checked with real sessions on a real Ollama, which also showed what it does not fix yet:
read the Known limits.

### Fixed

- **A session on a model whose larger window runs partly on the CPU stays at the window Halo names.** When another
  program left the model loaded at a window that spills to the CPU, a session of more turns said "reloaded at 16k,
  the largest known to fit the card" and then sent the larger window on every turn: nothing was reloaded and the
  model ran partly on the CPU for the whole session. Now every call of that session is sent the window the line
  names, the model is loaded there once, and the session compacts within it: its compaction calls are held at that
  window too, and a conversation larger than it is summarised from a transcript cut to fit ("the conversation (N
  tokens) is larger than <model>'s window (16,384): it summarises a transcript cut to fit"). A `halo -p` run already
  did this since 3.6.0.12; a session did not.
- **A new conversation is not compacted before it has an answer.** On a model whose window Halo puts below Halo's
  own first request, a new session said "this will be cut: compacting first", summarised a conversation that had
  no history, and the summary replaced the question you had just typed: asked later what the first question was,
  the model named the second one. Now a request with no earlier answer is not compacted before it is sent, and
  nothing is asked. When it cannot fit the window you read "prompt N tokens · window W · usable U · ...: sending
  anyway (the tail is kept)", and before it, when the system prompt, the memory and the tools alone are already
  more than the window holds, the line that says so ("... alone are N tokens, more than this W window holds ...").
  It goes out as "send anyway" sends it, and a reply that is then cut at the window stands as the answer (before,
  that started a compaction too). The same holds for a helper's first request and for a `halo -p` run. From the
  second turn on nothing changes.
- **One window in every line, and the tool block of that window.** The tool block of a session is the block of the
  window its first request is sent at, and it stays that for the session. Three cases said one window and sent
  another: a model held at a smaller window because the larger one spills (the line beside "reloaded at 16k" said
  "(window 65,536)" and the session carried that window's 28 tools); a model Halo has not
  measured, whose first request is raised over the default (the line said "(window 8,192)", 16,384 was sent); and a
  model another program left loaded at a larger window that Halo holds (65,536 was sent with the 16,384 block and
  "(window 16,384)"). Each now reads "N tools not offered to <model> (window W)" with the window the first request
  is sent at.
- **"the largest known to fit the card" is said only of a window that is known.** With nothing measured, a model
  loaded at a spilling window was "reloaded at 8k, the largest known to fit the card": the 8k was a default, never
  measured and never sent. Now that line is said only when the window comes from a spill Halo saw or from a
  measurement; otherwise you read the load line, "loading <model> on <host> again at a 16k window", which names the
  window that is sent.
- **The reply's room is said once.** A reload under a spill printed it on two lines.
- **`halo local prompt` measures the session you get.** It measured a session without the Builder tool, so from a
  32,768 window on its figure was about 400 tokens lower than what a session someone answers really sends. It now
  uses the same rule a session uses for the Builder, and so do `/status` (with the Builder when the session has
  it), Studio's model card ("Halo's first turn: N tokens") and `halo doctor`. Nothing a model is sent changes by
  this.
- **With Copilot set up, main keeps the Builder.** `copilot_ask` took the last room of the 4,500-token tool budget,
  so at a 32,768 or 49,152 window the Builder was left out and main never read the words that let it propose a
  helper or a workflow. `copilot_ask` now rides on top of that budget (150 tokens) and is not counted in the tool
  count either: both are sent, and every other tool is in or out exactly as in a home without Copilot. So with
  Copilot set up, another tool ranked after it that did not fit before (a pack's, another server's) can be sent
  now too.
- **macOS: the closing procedure's look for left-over programs no longer lists its own `ps`,** a process that is
  gone a moment later, and one byte that is no UTF-8 in any program's command line no longer makes the whole look
  answer "nothing".

### Added

- **`halo gym handout <model> --diet`.** Does a local model do as well with fewer tools? It runs the gym's fixed
  four-part job three times with every tool the model's own window takes and three times with the 16,384 block
  (13 tools, the rest by name), both with today's words and at the same window, and ends with one line: "Verdict:
  the 16,384 block does as well (finished A of N, with every tool B; parts handed out C of P, with every tool D)."
  or "Verdict: the 16,384 block does worse: it finishes A of N (with every tool B)." A model whose own window takes
  no more tools than that block prints "not measured" and saves no card. Free and local; about two minutes per
  model on a GPU. On the first real model it read "does as well (finished 3 of 3, with every tool 2 ...)". See
  [COMMANDS-gym-handout.md](docs/COMMANDS-gym-handout.md).

### Changed

What a model is sent changes in these cases only. A session on a model with a large window (65,536 and up: the
cloud models Halo ships with), and a local session or `halo -p` run on a measured model with no spill whose
requests fit, are sent byte for byte what 3.6.0.18 sent (the request bodies were compared across both).

- A session held at a window because the larger one spills: that window on every call (also its compaction's), and
  the tool block of that window from the first request on (at 16,384: 13 tools instead of 28, the others by name).
- A session whose first request is sent another window than Halo resolved (raised over a default, or a larger
  loaded window that is held): the tool block of the window sent.
- A first request that cannot fit its window (a session's, a `halo -p` run's, a helper's): sent as "send anyway"
  sends it, where a compaction ran before.
- With Copilot set up, at windows over 16,384 and under 65,536 (a local model or a small-window cloud one):
  `copilot_ask` no longer takes room from the others, so the tools ranked after it that now fit are sent too, the
  Builder's definition (about 400 tokens) first.

### Tests

- The real-use step `made-at-once` asked two turns in one session with the same words and waited for the same
  answer; the terminal draws the first answer again when the second prompt is sent, so the second wait could be
  true before main had asked anything (red once on macOS in 3.6.0.18's CI). The second turn has its own words.
- The two real-halo tests of a quit with a stuck read now time the stuck quit against a healthy quit on the same
  machine: it may take twice the healthy one plus the product's own bound and three seconds (on one Windows machine:
  0.3 s healthy, 2.1 s stuck). Before, they asked only "gone within 15 s".
- The prompt pins measure the session with the Builder (32,768: 8,263 -> 8,666 tokens on Windows); no bound moved.

### Known limits

- **A model Halo has not measured can be held at a window that is far too small.** Halo's memory estimate counts
  about thirty times too much for one family of models (latent attention). Seen on a real 30B model: the estimate
  says 4k, while the model sits wholly on its card at 65,536. A new session on it then reads "... more than this
  4,096 window holds ...: a bigger-window model holds them" (for this model untrue: it is the estimate that is
  small) and "sending anyway", is sent at 4k, and from the second turn runs at a larger window with a reload and
  another tool block, which can change once more on a later turn (the estimate moves while the model is loaded).
  Measuring does not help yet: `halo local measure <model>` found a far larger window safe for that model and the
  next session still started at 4k, because the smaller of the estimate and the measurement wins. What does help
  today is a window of your own for that model: `halo ollama profile set <host> <model> num_ctx 32768`; a new
  session then starts at 32,768 with one window in every line (checked on the real model). The estimate itself is
  the next release's first job.
- The names of the tools of your other MCP servers are in every request of a local session, and `halo local
  prompt` does not count them. With many servers that is thousands of tokens.
- A spill found only after a session's first call (nothing loaded at the start, the first load spills): the window
  steps down turn by turn and the tool block stays the first window's; the reload lines name each window as it is
  sent, the "tools not offered" line still names the first.
- When another program later reloads the model at a larger window that fits, the session keeps its tool block and
  is sent the larger window, with no new line.
- A first request that cannot fit its window is sent at once: the card that offers a bigger-window model is not
  shown for it (the line says a bigger-window model holds it; `/model` switches).
- The tool steps of a FIRST turn can still be compacted when their output does not fit, and so can a first
  request that Halo judged to fit and that the server then cuts.
- A session held at a window is now held there too when Ollama answers "prompt exceeds num_ctx" (it compacts
  instead of being re-sent at a larger window). That one path was changed after the review and has no test of
  its own yet.
- A reload with nothing known says only "loading <model> on <host> again at a Wk window", not why.
- The real sessions were run on Windows with one Ollama and one card; the same code paths run with a stand-in
  server in the tests on Windows, macOS and Linux. The macOS fix above was not run by hand on a Mac.
- Every Known limit of 3.6.0.18 still holds.

## [3.6.0.18] - 2026-11-24

A Ctrl+C always reaches Halo, and the last ways a quit could leave something behind are closed. On Windows a Ctrl+C
typed in the first moments of a terminal session could do nothing: a program Halo itself had started took the key.
That is found and repaired, and it was Halo's fault, not the keyboard's. A quit while Halo is still opening your
browser no longer opens it after Halo has gone, Ctrl+Q ends a session whose screen is stuck, a Ctrl+C during
`/update`'s hand-off ends Halo, and once Halo's closing procedure has run nothing new starts behind it.

### Fixed

- **A Ctrl+C in a session's first moments is no longer lost (Windows).** When a session starts, Halo asks `claude
  auth status` who is signed in. That program shared the terminal's keyboard with Halo, so it could take a key you
  typed. And when its `.cmd` wrapper ended, Windows switched the console back to turning Ctrl+C into a signal for
  0.1 to 0.3 seconds, longer on a busy PC; Halo swallowed that signal, so a Ctrl+C typed then did nothing. Now no
  program Halo starts for itself gets the keyboard while the terminal app is up (see Changed), and when the console
  does turn a Ctrl+C into a signal Halo treats it as the key: the first press stops the turn, the second opens the
  quit card. This is the limit 3.6.0.17 named ("on one loaded Windows machine the real-use check's Ctrl+C step fails
  in about half its runs"): the keys were lost by Halo, not by the checker.
- **A quit while Halo is still opening your browser no longer opens it after Halo has gone (Windows).** Inside a
  Job that lets nothing leave (a CI runner, a service) Halo starts a browser or a kept program through a small
  helper. When you quit in the first seconds of `halo init`, `/studio` or a sign-in, that helper stayed behind and
  opened the browser seconds after Halo had left. Now the helper that makes the start is held in Halo's own Job
  and ends with it on every way out (Ctrl+C, a closed terminal, a hard kill). The start's last step, a tiny runner
  outside every Job, starts the program only while the Halo that asked is still running and its closing procedure
  has not marked the start; otherwise it starts nothing and removes its files. A kept program whose start was
  under way when Halo closed either does not start, or, when it answers within the quit's wait, is named in
  "halo: left running on purpose" as before.
- **A second Ctrl+C while `halo init` waits for its browser prints no traceback.**
- **A Ctrl+C during `/update`'s hand-off to the updater ends Halo.** It prints "halo: interrupted while starting
  the update. `halo --version` shows what is installed; `halo update` starts it again." and leaves with 130.
  Before, Halo left without its bound there: a background check stuck on the network kept it alive, and the Ctrl+C
  printed a traceback.
- **A Ctrl+C that ends the terminal app from outside leaves with one line and 130.** The line is print mode's
  "halo: interrupted", on Windows, macOS and Linux, stuck check or not. Before, a traceback and Python's own exit
  code.
- **Ctrl+Q ends a session whose screen is stuck.** Ctrl+Q is the key for a session that no longer answers. On a
  screen that had stopped taking events its own thread waited for that screen without limit and no end was armed at
  all. Now the end is armed at the press, before anything that can wait: when the app does not close, Halo ends
  itself about ten seconds after the press, through its closing procedure, so everything it started ends with it.
  A session that does close leaves as before.
- **A late background worker of Halo's own no longer holds the quit.** A call that arrived as the app closed
  could start one more of Halo's internal workers (a refresh, a check), and the process stayed alive until that
  worker ended: without limit on Python 3.10 and 3.11, up to 300 seconds on 3.12 and later. Such a worker is now
  never run. Your own background commands are not what this is about.
- **Once Halo's closing procedure has run, nothing new starts behind it.** A background worker that answers late
  and then tries to start a program through Halo's own process layer is refused, on Windows, macOS and Linux. What
  you asked Halo to keep (the updater's hand-off, a `--keep` server) still starts, and so does what the closing
  procedure itself needs.
- **A program whose start was under way at the instant Halo closed is still ended (Linux and macOS).** When Halo's
  end is forced because a background check is stuck, it looks once more right before it leaves and ends what it
  finds, with the usual "halo: ended ..." line. Before, such a program outlived Halo.
- **Quitting while one of Halo's own short checks runs prints no false line (Linux and macOS).** The status line's
  command, `claude auth status`, `claude mcp list` and the git branch look are ended silently. Before, a quit could
  print "halo: ended sh (pid N), sleep (pid N), left running by a tool command; ..." for a check nobody started and
  nobody can keep. A tool command's leftover still gets that line.
- **The OpenRouter balance refresh asks nothing more once a quit has begun.** Before, its second request could
  still go out, with your key, after you had quit.
- **A kept start that begins after Halo's closing procedure has run is taken back at once (Windows).** No helper
  runs and no file holding the environment is written.

### Changed

- **While the terminal app is up, a program Halo starts gets no keyboard input.** Its input is the null device: a
  tool's command that asks a question on its input reads "end of input" at once, where before it shared the
  keyboard with Halo and could take the keys you typed. Your editor is the one exception: while Ctrl+E, `/editor`,
  `/improve`'s edit or the `/mcp` dialog's editor is open, the editor has the keyboard, and only the editor.
  `halo -p` and Halo's other commands are unchanged.
- **Ctrl+Q has one end.** Its last resort no longer leaves by a raw exit that skipped the closing procedure. On a
  stuck screen the end comes about ten seconds after the press (before: never on a wedged screen, 2.5 seconds
  after the app was asked to close otherwise).
- **The real-use check's closing step keeps the checker's own notes in a file of their own**
  (`close-trace-checker.txt` beside Halo's `close-trace.txt`), so no line is lost when both write at once.

### Known limits

- **One Ctrl+C can still be swallowed in a window of milliseconds (Windows).** Halo puts the console's setting back
  twice a second. When that happens between the console turning a Ctrl+C into a signal and Halo reading the
  setting, that one press counts as a program's signal and does nothing. Press again.
- **The keyboard rule is the terminal app's.** `halo init` and the other commands start their programs as before,
  sharing the terminal's input; that was not looked at.
- **A quit in the instants between the runner's last check and its start still lets that one program start
  (Windows).** It is then your browser, or a kept program: named when it answers within the quit's wait, else
  listed by `halo ps` as kept without a line at the quit. The same holds for a start made between the quit and
  the closing procedure.
- **After a hard kill of Halo during such a start, a file with the start's environment (your keys included) can
  stay in your own temp folder** until the next such start removes folders older than ten minutes.
- **A kept program can go unnamed** when a quit reads the list in the few instructions between its start and its
  entry in the list, or when its starter is a caller that keeps a program without Halo's own kept start.
- **Ctrl+Q on a stuck screen does not print the quit's usual lines** (what was stopped, what was left running on
  purpose): the terminal is still the app's then. On Linux and macOS a "halo: ended ..." line of the last look can
  still appear. Halo's end there was proven with a stand-in screen that never answers, not with a really wedged
  terminal.
- **The last look for a start under way runs only on the forced end (Linux and macOS),** which is where a worker
  can still answer late. The refusal covers what Halo starts through its own process layer: a program a library
  starts by itself is not refused, and a thread that itself runs the closing procedure may still start one.
- **When the closing procedure ran first on another thread (a forced end, a closed console window), a stop the
  main thread still tries is refused too.** The closing procedure has done the stops by then; an exit hook of a
  pack that starts a program there can print "Exception ignored in atexit callback".
- **A Ctrl+C typed during a real `/update` hand-off, and a Ctrl+C escaping the app in a real terminal, were not
  produced by hand.** Both are driven by tests that run the real code in a child process.
- **The Windows repairs were driven in a pseudoconsole, not in a real console window.** The kept-start repair's
  real-use run (a real `halo init` inside a Job that lets nothing leave) was the PC's only; CI's Windows runners
  run its tests. Nothing was run on macOS by hand: CI's macOS legs run the tests and the real-use check's
  `closing` step.
- **Every Known limit of 3.6.0.17 still holds, except these three:** the lost Ctrl+C on a loaded Windows machine,
  the Ctrl+C during `/update`'s hand-off, and the false "left running by a tool command" line for a check of
  Halo's own.
- **Where it was checked.** On the Linux VM: all three suites (the module runner's four shards, the bridge
  suite and the terminal app's suite; on a copy with no git history: the few tests that need it run in CI), and on
  the final code the terminal app's suite again, the browser modules of the Prompt box, the Feed, the steer box,
  Session's drawing and the card, the closing and update modules, and the full real-use check, twenty of twenty
  steps; named alone, its `closing` step (all 28 ways out left nothing) and its `update` step passed three more
  times each. On the PC (Windows), one at a time: every node-backed module, the closing modules three times each
  and once more after the review's repairs, every update module, the terminal app's quit, Ctrl+Q and editor tests,
  and the real-use check's `closing` step eleven times while this release was built, the last three on the final
  code: eleven passes, on the machine where it failed in about half its runs before. One reviewer read the whole
  release: nothing that must be fixed; six sentences of these notes were corrected, five small things repaired
  (among them: a Ctrl+C typed in your editor no longer makes Halo change the console's setting under the editor,
  and Ctrl+Q's last resort ends a real Halo only) and three tests tightened. Nothing was run on macOS by hand.

## [3.6.0.17] - 2026-11-23

Closed means gone, also while the network hangs; and the prompt, one to one. A terminal Halo you quit no longer stays
alive behind a background check that waits on a network that does not answer. Session's Prompt box in Studio now does
with a line what the terminal's prompt does: a `!command` or `/command` typed after a space runs as a command, a
`/command` runs with an image waiting under the box, a refused `!command` shows once and the box empties, and Up and
Down move through a long wrapped line a screen line at a time. A running `!command` can be stopped from its row in the
Feed, and the Agent panel names a running tool as its box does. 3.6.0.16 was not published on its own: its release run
found the closing fault repaired here, so this is the first release that holds what both sections say.

### Changed

- **A `!command` or `/command` typed after a space or a blank line runs as a command in Studio's Prompt box.** As in
  the terminal, the line runs in the session with no model turn. Before, Studio sent it to the model as a prompt. A
  text of two lines that both have words and a `!` inside a line are prompts, as before.
- **A `/command` typed while an image is under the box runs as a command.** The image waits under the box for the next
  prompt, as the terminal keeps it. Before, the line went to the model with the image.
- **After a refused `!command` the Prompt box is empty, as the terminal's is.** Up brings the line back. Before,
  Studio kept the line in the box.
- **Up and Down on one long prompt that wraps in the box move a screen line at a time first.** Then Up goes to the
  start and Down to the end, and then through the prompts you sent, as in the terminal. Before, Up on a wrapped line
  went straight to the start.
- **`s` on a row of the Feed pins that agent, exactly as the row's "steer ▸" does.** One act, one result; Esc on a row
  shows everyone again. Before, `s` aimed the steer box without the pin.
- **The Agent panel's glance line and a pinned agent's small floating panel name a running tool as its box does.** An
  MCP tool reads as its name alone (`mcp__srv__slow_tool`, not `mcp__srv__slow_tool {"seconds": 30}`), and a built-in
  reads "Bash ls -la" (before, "Bash: ls -la"). A waiting, paused, queued or finished agent reads as before, and the
  whole input stays in the tool row's detail.

### Added

- **A running `!command` has its own Stop on its row in the Feed.** The same "Stop" its row in the Prompt panel has,
  with the same hover: "Stop: ends this command now, and a running turn with it (Esc in the terminal does the same)".
  A click on it does not open the row, a model's tool rows and a session of another machine's Halo have none, and when
  the command ends the Stop goes while the elapsed time keeps its place at the row's end.

### Fixed

- **A Halo you quit is gone, also while the network hangs.** A terminal session starts a few checks in the background
  when it opens: who is signed in, the model catalog, your balances, whether an update is out. When you quit while one
  of them waited on a network that did not answer, the Halo process stayed alive until that wait gave up by itself:
  seconds for most, minutes for the catalog (30 seconds a provider), and the update check's `git` and git's https
  helper stayed with it. 3.6.0.16's release run saw exactly that on Windows: five seconds after Ctrl+C a `python.exe`,
  a `git.exe` and a `git-remote-https.exe` were still running. Now a quit waits for them at most two seconds, all of
  them together. Halo then saves the session and prints its last lines as before, and when a check is still stuck it
  is gone half a second after the last line, whatever that check waits for: 2.7 seconds from the quit to gone,
  measured on Windows and on Linux, against 0.2 to 0.4 seconds with nothing stuck. Every way out of the terminal has
  this bound: Ctrl+C and its confirm, `/quit`, an error that ends the app, and `/update`'s restart, where it starts
  only after the hand-off to the updater has returned, never during it. A quit where nothing is stuck leaves as it
  did: the same lines, the same exit code, the same saved session.
- **The update check's git ends with Halo.** The check's `git ls-remote` runs in a group of its own and is ended with
  everything it started, the https helper included, the moment Halo leaves, and at its five-second limit while Halo
  runs. Before, the limit ended git alone and then waited on the helper, which held git's output open. A check that a
  quit cut short is not remembered as "no network": the next launch asks again. A catalog refresh asks no further
  provider once Halo is leaving.
- **A thing you asked Halo to leave running is named in every quit.** "halo: left running on purpose: ..." is printed
  also when a background check is stuck; the lines of a stuck quit are those of any other quit.
- **On Windows a command ended at its time limit no longer holds Halo.** After Halo ended a command that ran over its
  limit, it waited without limit for the command's output to close, and a helper the command had started could hold it
  open. Halo now waits at most one second for the rest of the output.
- **A `!command` refused by a rule of yours shows once in the Prompt panel.** `!<cmd>` over `denied: <reason>`, not
  twice. A `!command` refused in the terminal still shows the session's own line in the panel, and Live's journal
  still records every refusal.
- **The Feed's steer box keeps its unsent text for each session.** Moving Session to another session shows that
  session's own text (empty when it has none), so a text written for one session is never sent to another. Before, one
  text stood for the whole page.

### Known limits

- **A background check that is stuck is left behind, not ended.** Its thread is abandoned when the process leaves half
  a second after the quit's last line; what it was reading is not saved. A check of Halo's own that runs a program
  longer than the two-second wait (the launch's `claude auth status` on a quit in its first seconds) has that program
  ended by the closing procedure, which on Linux and macOS names it "left running by a tool command". Print mode,
  Studio's server and `halo local serve` are as they were: this bound is the terminal app's.
- **A Ctrl+C during `/update`'s hand-off to the updater leaves without the bound,** as 3.6.0.16 did. When an error
  ends the app, Halo's last lines now print before the error's traceback.
- **The closing repairs were not run by hand on macOS.** CI's macOS legs run their tests and the real-use check's
  `closing` step.
- **On one loaded Windows machine the real-use check's Ctrl+C step fails in about half its runs** (seen while this
  release was built): the Ctrl+C keys the checker sends do not all reach Halo, so no quit is asked. It passes on Linux
  and on CI's Windows runners. Whether the checker's key sending or Halo's console input loses them is not yet known;
  it is the next thing looked at.
- **A `!command` line from the phone bridge or from voice is still a prompt.** Letting a remote surface run a command
  is the owner's decision.
- **Stop ends every running `!command` and a running turn with it;** there is no "end only this command". A click on a
  row whose command has just ended, before the page has its result, ends whatever turn runs then.
- **A prompt pasted with a space before a path now takes the command door, as in the terminal.** ` /tmp/notes.txt
  explain this` answers "Unknown command: /tmp/notes.txt (try /help)" and the line stays in the box. A line of only
  spaces and a `!` shows an error row and keeps the line, where the terminal empties its box without a word.
- **The steer box's image chip is still one for the page:** only its text is kept per session.
- **The timeline shows a running `!command` only while a turn runs, with no Stop, and Agents -> Live does not show it
  at all.** The Feed and the Prompt panel are the two places that name it, and both have its Stop.
- **On a very narrow Feed, where a tool row's first line wraps, the row can wrap differently when the Stop goes.** The
  result's line arrives under the row at the same moment.
- **The one row for a refused `!command` is proven in the panel's own rule, not in a browser:** the browser check
  holds the one row and the emptied box, but its page does not draw the session's own error line, so it could not show
  two rows either way.
- **A click on the Feed's Stop was not shown ending a real `!command` in a real session.** The check holds that the
  click reaches the session's door; the same Stop on the Prompt panel's row is shown ending a real command.
- **Up and Down on a wrapped line were driven in Chrome on Linux and once on Windows;** each browser makes its own
  move inside the text, and macOS is CI's part.
- **Every Known limit of 3.6.0.16 still holds, except this one:** the Agent panel's glance line and a pinned agent's
  small floating panel no longer write an MCP tool's raw arguments.
- **Where it was checked.** On the Linux VM, on the final code: all three suites (the module runner's four shards, the
  bridge suite and the terminal app's suite; on a copy with no git history: the few tests that need it run in CI), the
  browser modules of the Prompt box, the Feed, the steer box, Session's drawing and the card, the closing and update
  modules, and the full real-use check, twenty of twenty steps; named alone, its `closing` step (all 28 ways out left
  nothing) and its `update` step passed three more times each. On the PC (Windows), one at a time, on the final code:
  every node-backed module, this release's four browser modules, the closing modules (the ones that start a real Halo
  three times), every update module and the terminal app's quit tests. The real-use check's `closing` step was not
  used as a gate on the PC: see the limit above. Three reviewers read this release: one the Prompt box and the Feed
  (nothing that must be fixed; two sentences of these notes were corrected), one the first closing repair (nothing
  that must be fixed; it named what still held a quit, which became the second), and one the quit's bound, who found
  that a healthy quit on Linux and macOS could end a short program of one of Halo's own checks and print a false
  "halo: ended" line; that was repaired and its test fails on the code before. Browsers on macOS are CI's part, and
  nothing was run on macOS by hand.

## [3.6.0.16] - 2026-11-23

Small repairs after 3.6.0.15. Main is now told about an agent you save, delete or undo only when the names it can
start change, so a model you pick on one of Auto's boxes no longer reads to main as "a new helper". On a map of your
own a box names a running tool without its raw arguments. Nothing under Session's drawing moves while you point at it,
and choosing a row on a group's card never moves the rows. The real-use check runs its `live-scene` step in every run
now, on Windows, macOS and Linux.

### Changed

- **Main is told about a saved agent only when the names it can start change.** A new name is told as before: "[Halo]
  A new helper you can start now: {name} ({words}).", and a delete as before: "[Halo] Taken back: {name} can no longer
  be started in this session.". Main is no longer told anything when only what stands behind a name it can already
  start changes: your own agent taking the place of one the session started with (a model you pick on one of Auto's
  boxes saves such an agent), a project's save over an agent of yours, an edit, and the Undo or the delete that puts
  the start back. Before, the first two read "A new helper you can start now" and were listed under "Added in this
  session", and their undo read "[Halo] Taken back: {name} starts as it did when this session began.". That line is
  now told only when an Undo brings back an agent main had been told it can no longer start. No word of any line
  changed, and a session in which nothing is saved, deleted or undone sends exactly what 3.6.0.15 sent.
- **The real-use check runs `live-scene` in every run (for developers).** `python scripts/realcheck.py` runs all
  twenty steps; 3.6.0.14 and 3.6.0.15 ran `live-scene` only with `--only live-scene`. CI runs it on Windows, macOS and
  Linux. The step now fails, with a line of its own, when the page has no drawer head to read; before, it passed
  without checking the head.
- **The release tool asks GitHub again when one read fails (for developers).** While `scripts/release.py` waits for
  the suites, a `gh` read that fails on the network is asked again after its pause, and three failures in a row stop
  it with the last reason. Before, one failed read ended the tool while the run was still going.

### Fixed

- **An agent the session started with, deleted and then saved again, is told to main as startable again.** Main had
  read "[Halo] Taken back: {name} can no longer be started in this session." and was told nothing when you saved the
  agent again, so it kept believing it could not start it. It is now told "[Halo] A new helper you can start now:
  {name} ({words})." once. The name is not listed under "Added in this session": main could start it when the session
  began.
- **On a map of your own a box names a tool without its raw arguments.** A helper that ran an MCP tool read
  `mcp__srv__slow_tool {"seconds": 30}` in its box; it now reads `mcp__srv__slow_tool`, as Session's status line and
  the wait link do. A built-in reads in its short form, as before.
- **The wait link under Session's drawing holds still while you point at the drawing.** While the pointer rests on
  Session's drawing, or a card is open, the slot under the drawing keeps the height it had: the link's words change in
  place, and a link that needs another row takes it when the pointer leaves. Before, a long tool name gave the link a
  second row and the drawing got shorter under the pointer.
- **The whole status line is the hover of the status words only.** While the status line in the head of Session's
  drawing is held short, only the status words show the whole line as their hover; pointing at the rest of the head
  (the truth lines, the link to Agents -> Live) no longer shows it.
- **Choosing a row on a group's card never moves the rows.** The "MODEL of {name}" row is as tall as its longest
  member's name needs from the moment the card opens: choosing a helper with a long name and then one with a short
  name moves neither "Change" nor any row, and no name is cut. A single helper's card and main's are unchanged.
- **After a failed read the MODEL block's rows keep the answer's height.** After "Could not read this helper's agent:
  {error}", then Close, Change and a read that works, the rows hold the answer's height and not the error row's, so a
  pick's shorter line moves nothing under them.
- **Pause and Resume pressed at nearly the same moment leave the helper's row true.** Two presses that crossed could
  leave the row saying the opposite of what was set, and the button then offered the wrong press.
- **A helper's own deny on MCP tools, and what a helper's helper does to its parent's tools, are held by tests (for
  developers).** Nothing changed in what a helper can use: the test of the deny now fails when the helper's own filter
  is taken out, and the docs of the read say truly that a helper's helper, when it searches, may grow its parent
  helper's own list of tools it may ask for; nothing is loaded and main's tools never change.

### Known limits

- **The Agent panel's glance line and a pinned agent's small floating panel still write an MCP tool's raw arguments.**
  They show the helper's line as it is.
- **Two presses of Pause and Resume that cross leave the row true, but their two updates can reach an open page in
  either order.** The page then shows the older one until that helper's next update.
- **While you point at the drawing, a wait link that arrives or grows shows only as many rows as the slot had.** Its
  whole text is its hover, and it takes its rows when the pointer leaves. The line that says more lies below was not
  checked for a text that needs a second row.
- **With Windows' font the long wait link of the browser check fits the rows the slot has,** so on Windows that check
  proves only that nothing moves; that the slot holds back a row is proven on Linux.
- **`live-scene` had run by hand on Linux and Windows only.** CI is the first to run it on macOS and on its own
  Windows runners.
- **Driven in a browser on Linux only.** The box's words, the wait link, the head's hover and the group card's rows
  were driven in headless Chrome on Linux against a page whose session rows are stood in, not in a real session with a
  real MCP tool; browsers on Windows and macOS are CI's part, and nothing was run on macOS by hand.
- **What main is told was not read in a real model's session.** It is held by the session's own tests and by a real
  session with Studio's real server taking a save and a delete; no model was asked what it understood.
- **Every Known limit of 3.6.0.15 still holds, except these:** `live-scene` is in a plain run of the real-use check;
  on a map of your own a box's line names a tool without its raw arguments; and the wait link under Session's drawing
  holds while the pointer rests.
- **Where it was checked.** On the Linux VM: all three suites (the module runner's four shards, the bridge suite and
  the terminal app's suite; on a copy with no git history: the few tests that need it run in CI), then, on the final
  code, the browser modules of Session's drawing, of the card, of Live and of Auto's groups (the card's three times),
  and the full real-use check, twenty of twenty steps with `live-scene` among them; named alone, `live-scene` passed
  twice more. On the PC (Windows), one at a time: every node-backed module, the card's two browser modules, the plain
  modules of this release, and `live-scene` once. One reviewer read the whole diff and found nothing that must be
  fixed; one sentence of these notes was wrong and is corrected. Browsers on macOS are CI's part, and nothing was run
  on macOS by hand.

## [3.6.0.15] - 2026-11-23

The box acts, and what you make can be used at once. An agent you save in Agents, one the Builder makes in a session,
or one a model pick in a helper's box makes can be started by main in the session that is running on Auto, from main's
next step, with no restart, and main is told so once. A click on a helper's box or on main's now opens a MODEL block:
pick one of your models and it saves or makes your agent (for main it runs /model), with Undo and a way to open that
agent in Agents. On Auto the helper groups in Agents -> Live stand wider and closer to main, a wide group lays three
helpers a row, and a group whose helpers are all done folds to its head. What last release's real-use step found is
repaired: a helper can use an MCP server's tools, a helper that ends at once shows its time, no box moves when a
group's counts line changes, and a cost above zero never reads as zero.

### Added

- **An agent you save in Agents can be started in the session that is running now.** A save (a new agent, an edit or a
  delete) reaches every Halo session running on Auto (one of yours reaches every session; a project's, the sessions in
  that project), and the session takes it before main's next model call; a helper already running keeps what it
  started with. A session that is not on Auto (a map of your own) takes nothing and loses nothing: a delete leaves the
  agent it started with in place there. Main is told once, before its next step: "[Halo] A new helper you can start
  now: {name} ({words})."; when you delete it or undo it, "[Halo] Taken back: {name} can no longer be started in this
  session." (or "[Halo] Taken back: {name} starts as it did when this session began." when your save had replaced an
  agent the session started with). An edit of an agent the session started with is not told, nothing is told twice,
  and after /clear or a compaction what main can no longer have read is told once more. A session that cannot run the
  agent as it is (it runs on a map of yours, the agent asks for a tool its main does not have or a mode above its own,
  a built-in has that name, or the session holds that name from a source that wins, such as the project's own agent
  file or `--agents`) leaves it for your next session. A session that does not answer is that session's alone: the
  others still take the save. A session in which nothing is added or taken back sends exactly what 3.6.0.14 sent.
- **What the Builder makes in a session is ready in it at once.** Main can call an agent the applied card made in the
  same turn, and the card's result ends with "Ready in this session now: the agent {x} (subagent_type `{x}`)." (with a
  workflow, the workflow is named first in the same line). An agent the session cannot run says why: "Saved for your
  next session: the agent {name} (it asks for {tool}, which this session's main does not have).", "(it asks for a mode
  above this session's)." or "(a built-in has that name).". A card that removes an agent, or an undo of a card, takes
  it back and main is told at its next step. The terminal's folded card and Studio's lines over Session's drawing say
  the same words.
- **Main's hover says what was added.** On Auto, main's hover ends with "Added in this session: {names}" once agents
  were added since the session started; "Told it can start: {names}" stays what main read at the start.
- **A MODEL block in a helper's box and in main's, closed until you ask (Agents -> Live and Session's drawing).** A
  click on a helper's box (a member of a group on Auto) or on main's box opens its card with one row first in its
  body: "MODEL" and a button "Change". A press opens the block in place and only then reads the helper's agent
  ("Reading this helper's agent..." until it answers); the button then reads "Close", which folds the block again and
  keeps what it showed. Open, it holds one line that says what a pick does for this kind of helper, and the picker of
  your own models, labelled "Model" (picked, never typed; for a helper its first row is "Auto: Halo picks the model
  per task"; main's has no Auto row). A card opened anew starts closed, and a card whose block was never opened asks
  nothing for it. A group's card has the block of the row you chose: its row reads "MODEL of {name}", and choosing
  another row closes it and asks nothing, so a helper of a folded group can still be given a model. When the read
  fails: "Could not read this helper's agent: {error}", with no picker; Close, then Change, asks again.
- **The block says what a pick does before you pick.** One of your agents: "Picking a model saves it in your agent
  {name}: its next start uses it, in this session too, unless main names a model itself."; one that ships with Halo:
  "{name} ships with Halo and Auto picks its model per task. Picking a model saves your own {name} on that model:
  ..."; a built-in: "{X} is built into Halo and has no file. Picking a model makes {name}, an agent of yours built
  from {X}, on that model: ..."; one main made up: "Main made this helper up for its task. Picking a model makes
  {name}, an agent of yours built from it, on that model: ..."; a general helper Auto sent to one of its cards first
  reads "A general helper that Auto sent to its {card} card for the word "{word}"." and its pick saves your own agent
  of that card; main: "Picking a model runs /model in this session.". A pack's agent ("{name} comes with the pack {P};
  Halo does not change it here.") and a Claude Code agent file ("{name} is a Claude Code agent file; Halo reads it and
  does not change it.") have no picker, and neither has a helper whose own agent you deleted after it started ("Your
  agent {name} is gone: it was deleted after this helper started."). A session that cannot take agents at once reads
  the "from your next session" form of each line. Under it, for a helper: "This helper keeps {model} until it ends."
  ("It ran on {model}." once it ended).
- **A pick saves or makes your agent, and Undo takes it back.** The answer's line takes the place of the rows: "Saved:
  {name} runs on {model} from its next start, in this session too, unless main names a model itself." (or "Saved:
  {name} runs on {model} from your next session."), "Made {name}, an agent of yours on {model}: main can start it now,
  unless it names a model itself." (or "... main can start it from your next session."), and a refusal "Not saved:
  {error}.". A built-in's pick makes an agent named like it (`judge` for Judge; `judge-2` while you already have a
  `judge`). Then [Undo]: "Put back: {name} runs on {old} again." or "Taken back: {name} is gone." (main is told it is
  taken back); "Not undone: {name} was changed since." when the file changed after the pick; a put-back the form
  refuses reads "Not undone: {error}.", and a delete it refuses reads the form's own line ("{name} is used by {list}:
  take it out there first"). [Edit in Agents] opens your agent in the Agents form; [Make it an agent] (a helper that
  ships with Halo, a routed, a built-in or a made-up one) does what the box's "Save as an agent" does, then goes to
  Agents. Open, the block holds still: its row of buttons and Undo's room are there from its first draw (main's pick
  has no Undo).
- **Main's model from its box.** A pick in main's MODEL block runs /model in that session: "Switched main to {model}
  now, as /model in its terminal, and saved for your next launch." when a terminal ran it, "Switched main to {model}
  for this session; not saved for your next launch." when none did; either is written only once the session reads back
  the pick (for up to 3 s), else "Not switched: {why}.". While main is in a turn nothing is sent: "Not switched: main
  is in a turn: pick again when it ends."
- **On Auto a general hand-off starts your agent once you own one named like the card's.** With an agent of your own
  named like the agent of one of Auto's cards (your own `coder`, say), main's general hand-offs that Auto sends to
  that card start yours: your instructions, your model (unless main names a model in the call), drawn in Agents ->
  Live as your saved agent. It runs exactly as if main had named your agent. With only the one that ships with Halo, a
  call that names a type, a fanned-out call, a helper's own hand-off or a session on a map of yours, everything is as
  before. An agent you save during the session counts at once.
- **Auto's helper groups fold when they are done (Agents -> Live and Session's drawing).** A group whose helpers have
  all finished as done folds to its head 10 s after the last one ended: only the head is drawn, with its all-done
  line; its hover still lists every member, and a click opens its card, which lists every member as a row (choose one
  to pause, stop or steer it, to read what it said and why it got its model, or to set its model); the groups below
  move up. A group that finished before you opened the page is drawn folded from the start. A group with a failed or
  stopped helper stays open, and so does one with anything running, queued, paused or waiting. Nothing folds while the
  pointer is on the drawing or a card is open: it folds when the pointer leaves or the card closes. When a new helper
  joins a folded group, the group opens again once the drawing is free, its earlier helpers at the heights they had,
  and rings once.
- **What a program can now ask and read (for developers).** The control socket takes `agent_put` and `agent_gone`;
  Studio serves `GET crew/agent-model`, `POST crew/agent-model` and `POST crew/agent-model/undo`; a terminal's answer
  to a `slash` command carries `terminal: true`; a session's row carries `use_now` and `kinds_added`, a helper's row
  `ended`, `pause_set` and, under `spawn`, `source` and `routed`.
- **The real-use check has a step for a pick that acts at once (for developers).** `python scripts/realcheck.py --only
  made-at-once`: in a real Studio and a real terminal session on Auto, it presses "Change" in the built-in Judge's box
  and picks a model in its MODEL block, which makes `judge`; main is told and starts it on that model in the same
  session; Undo takes it back and main is told; an agent saved in Agents' form reaches the running session; nothing is
  left behind. It runs in every plain run, so in CI's real-use legs on three systems.

### Changed

- **In Agents -> Live on Auto the groups stand closer to main and as wide as the view allows.** The lane between main
  and the groups is 96 px (it was 212) and the group column is min(760, view / zoom - 392) px, at least 352 (it was
  248); from a view of 744 px the drawing does not scroll sideways. A new width waits like every re-flow: nothing
  moves while the pointer is on the drawing or a card is open. A group lays its helpers three a row when each would be
  at least 200 px wide, else two or one as before (in practice only this column gets three; Session's drawer stays at
  one or two). Agents -> Map and a map of yours are laid out as before.
- **An agent that ships with Halo is read in the Agents form, with Copy.** Opened by name, it shows "{name} ships with
  Halo: read it here; Copy makes it yours to change.", every field and the model picker off (More still unfolds), no
  Save, no Discard changes, no Delete; Copy and Try it stay. Copy opens "my-{name}", not saved: "A copy of {name}, not
  saved yet: it is yours to change, then Save." (it was "{name}-copy"). A pack's agent is read the same way, with its
  band "From the pack {pack}: read-only here. Copy makes it yours." and no Save at all (it was drawn turned off).
- **"Save as an agent" and "Make it an agent" fill the form from the helper as it is.** One that ships with Halo gives
  its own file; a general helper Auto routed gives its card's agent; a built-in gives its description, its
  instructions, its tools and its mode; any other keeps the made-up agent as before. The form says "Built from
  {helper} on {model}, not saved yet: read it, change what you like, then Save."
- **`halo local prompt` counts what a first request really sends.** "Halo's own first turn: ..." now holds the
  permission mode line every turn starts with and, for a local main on Auto, the reminder after the task, each as its
  own row ("mode line", "reminder") before the tool rows; `--json` carries them as `turn_start`. `/status`, `halo
  doctor`'s default-model row, Studio's model card and the Ollama steward's fit floor read the same measure.
  `docs/MODELS-prompt-diet.md` names the two rows.
- **The gym's card says when a host gives no digest.** For a host that gives none (a gateway that speaks the OpenAI
  dialect, say), `halo gym handout` after a run and `halo gym show` print, under the card's line and before the
  verdict: "no digest from this host: a later build of this model overwrites this card". The card keeps its file name;
  nothing more is asked of the host (`docs/COMMANDS-gym-handout.md`).
- **Last said names whose words it shows:** "Last said by {name} at {t}: {text}", "Last said by {name}: {text}", "Last
  thought by {name} at {t}: {text}", "Last thought by {name}: {text}", with the name as the row shows it, read at the
  click and kept when another row is chosen (still one read, at the click); "Nothing said yet." is unchanged.
- **The real-use step `live-scene` is repaired and passes by hand (for developers).** It reads the order the page drew
  the groups in, waits for the writer's group to fold, rests the pointer on the drawing and reads that it is there,
  takes a cost as the page now writes it, gives the chart's work out only after the terminal said its MCP server
  connected, and proves the chart's helper was given the MCP tool at once and that the tool ran. It still runs only
  when named (`--only live-scene`); `--list` says why.
- **The real-use step `auto-groups` reads a folded group's helpers from the group's card (for developers).** A group
  that has folded shows no helper to hover, so the step opens the group's card, chooses each row and reads why that
  helper got its model there.
- **The docs say what this release built.** `docs/STUDIO-live.md` (the MODEL block, Last said by, Resume),
  `docs/STUDIO-groups.md` (the fold, Auto's column, three a row, the counts line's rows, the cost form),
  `docs/CREW-sessions.md` (usable at once), `docs/STUDIO-agents.md` (an agent that ships with Halo is read there),
  `docs/SUBAGENTS.md` and `docs/COMMANDS-mcp.md` (a helper's MCP tools), `docs/DEVELOPMENT.md` (the real-use steps).

### Fixed

- **A helper can use an MCP server's tools.** A helper main hands work to may use every tool main may use when the
  helper starts, an MCP server's tools included: it finds one with ToolSearch, or has it at once when the tool or its
  server is set to `alwaysLoad`. Before, ToolSearch answered "(not found: ...)" and a call got "Unknown tool" unless
  main had loaded that tool first. An agent file's `tools:` still narrows a helper, a deny rule or `--disallowedTools`
  holds for a helper as for main, and a tool main loads later does not reach a helper already running. A helper that
  started before a server connected finds that server's tools with ToolSearch from then on. In a session with an MCP
  server a helper's first request now carries ToolSearch, the deferred-tools reminder and its `alwaysLoad` tools; a
  session with none sends what it sent before.
- **An MCP server that connects after a terminal session started now counts, for main too.** In the terminal app
  servers connect after the first paint; one with no tools cache yet (a fresh home) connected and said "mcp: {n}
  server(s) connected" while its tools never entered the session. They now enter when it connects, through the same
  rules as at the start, and its `alwaysLoad` tools are loaded at once. A lazy server that a helper starts reaches
  main too, and the other way round.
- **Session's drawer head holds still under a resting pointer.** While the pointer rests on Session's drawing, or a
  card is open, the drawer's head keeps its height: its status line changes in place and takes another row only when
  the pointer leaves or the card closes (the whole line is in the head's hover meanwhile). Before, a longer line grew
  the head and moved every box under it by a row.
- **The status line names a running tool without its raw arguments.** A tool whose arguments have no short form (an
  MCP tool) is named alone in Session's status line and in the wait link under the drawing, as a box's NOW line names
  it; before, its arguments were written out as JSON. A built-in's short form reads as before.
- **`/mcp reconnect` keeps the session's deny rules.** A reconnected server's tools pass the same rules as at the
  start; before, a denied tool of that server could be found with ToolSearch after a reconnect.
- **A helper that ends at once shows its time.** In Agents -> Live and Session's drawing a helper that ends inside its
  first second, or before the page saw it run, now always reads "done in {span}" ("stopped after {span}", "failed
  after {span}"); before, it sometimes kept an empty line and its group's all-done line counted from its start. An
  ended run is rounded to the nearest second, the same in the helper's box, in its group's all-done line and in its
  hover (0 s only for a run under half a second), and its all-done group folds 10 s after the real end.
- **No box moves when a part joins a group's counts line.** The counts line keeps, from the group's first draw, the
  room its longest form takes at the group's width, so a helper starting to wait on you, one ending or a cost arriving
  never pushes the boxes under it down (Session's drawer at its narrowest included, with the pointer resting or not).
  When the group's width changes, the room is taken anew.
- **A cost above zero never reads as zero.** A group's cost, its all-done line and the hovers of a group and of its
  members write amounts as the boxes' heads do (four decimals under $1, two from $1), and an amount above zero under
  $0.00005 reads "<$0.0001" there, on the box heads, in Session's Cost panel, in the hub's today figures and on the
  report card. Before, a group of helpers that cost under half a cent read "$0.00".
- **Pause says what a press does.** While a pause you set is in place (from your press until a Resume), Pause reads
  "Resume" and a press takes the pause back, also before the helper holds (a helper that waits on you holds only at
  the call after your answer); before, it read "Pause" and a second press paused again. The card, a box's head in the
  feed, Agents' detail and its palette command and Session's steer row all read the same fact; the words, and the
  toast "Paused: it holds at its next tool or model call", do not change. A helper that has ended reads "Pause" again.

### Known limits

- **A model pick for main while main is in a turn is refused:** "Not switched: main is in a turn: pick again when it
  ends."
- **A model set in a helper's box counts from that helper's next start.** A helper already running keeps its model
  ("This helper keeps {model} until it ends."), and a model main names in its own call still wins.
- **A save in Agents' form does not say on the page whether a running session took it.** Main is told when one does; a
  session on a map of yours, or one that cannot run the agent, leaves it for your next session without a word on the
  page. A save asks each running session in turn and waits up to 5 s for one that does not answer.
- **A helper that calls an MCP tool before its server has connected gets "Unknown tool"** and is told to call
  ToolSearch, which then finds it; the tool is not pushed into a helper that is already running.
- **On a map of your own a box's line still writes an MCP tool's raw arguments,** and with a very long tool name the
  wait link under Session's drawing can take another row while the pointer rests (the head and the boxes hold).
- **A helper whose `tools:` names only `mcp__<server>__*` (and not ToolSearch) cannot reach a lazy MCP server that
  nobody has started yet,** as a main started with `--tools` that leaves ToolSearch out cannot.
- **`halo local prompt`'s composition line counts the mode line and the reminder under "history",** not under
  "system"; its total holds them.
- **With its MODEL block open a helper's card is tall.** In a 1440 x 900 window an open block can make the card take
  the drawing's whole height, so no other box in that column can be clicked until the block or the card is closed.
  Closed, as it opens, the card is one row taller than in 3.6.0.14.
- **Driven in a browser on Linux only.** The MODEL block of every kind of helper, a pick, Undo, Edit in Agents and
  Make it an agent are driven in headless Chrome on Linux against a page whose session rows are stood in; a pick that
  counts at once in a real session on Auto is driven by the real-use step `made-at-once` (by hand on Linux; CI is the
  first to run it on Windows and macOS). A routed hand-off starting your agent is proven in the session's own tests,
  not in a real page, and a pick for main with a real terminal attached is held by tests of the terminal's side.
- **Main's "Added in this session" line** was checked in its rule and on the session's row, not hovered in a browser
  after a real save.
- **The fold's 10 s is timed to the second by its rule, not in a browser,** where the check waits 11 s of the page's
  own clock.
- **The terminal app was not driven by hand with a model for the MCP repairs:** the late connect is proven through the
  terminal's own builder with test servers, and a helper's MCP call through a real `halo -p` with a test server.
- **Two suspected faults were not faults.** A helper of a fan-out names its tool on its box as a lone helper does, and
  a pointer that already rests on Session's drawing holds it (also when the drawing is drawn under it, or the drawer
  is narrowed by its keys or closed and opened again). Both were tried in a real session and in headless Chrome on
  Linux; pointer events may differ in other browsers.
- **Run by hand on Windows and Linux only.** The browser checks ran in headless Chrome on Linux; browsers on Windows
  and macOS are CI's part, and nothing was run on macOS by hand.
- **Every Known limit of 3.6.0.14 still holds, except these:** the card has a model block now; `halo local prompt`
  counts the mode line and the reminder; and of what the `live-scene` step found, the counts line's second row, the
  helper given no MCP tool, the helper with no "done in" and the "$0.00" are repaired, and the fan-out helper's
  "waiting for a model reply" did not show in a check built to catch it.
- **Two more of 3.6.0.14's limits end with the repairs above:** Pause on a helper that waits on you, and Last said not
  naming whose words it shows.
- **A pick for main compares the model the session reports with your pick,** with a terminal attached or not. If the
  session spells that model another way, a switch that worked reads "Not switched: ...".
- **`live-scene` is not in a plain run of the real-use check yet.** The product faults it found are repaired and it
  passed three times in a row on Linux, once more on Linux's macOS path, and twice on Windows; it has not run on macOS
  or on CI's runners, so CI does not run it.
- **Where it was checked.** On the Linux VM: all three suites (the module runner's four shards, the bridge suite and
  the terminal app's suite; on a copy with no git history: the few tests that need it run in CI), then the modules
  changed after that run once more, the browser modules of the drawing, of the card and of the Agents form, and the
  full real-use check, nineteen of nineteen steps (`live-scene` is left out of a plain run; named, it passed three
  times in a row, once more on Linux's macOS identity path, and once on the final tree). On the PC (Windows), one at a
  time: every node-backed module and the plain modules of this release, and `live-scene` twice. One reviewer read the
  whole diff; its one must (a delete in Agents reached a session that is not on Auto) is fixed, with a test. Browsers
  on macOS and Windows are CI's part, and nothing was run on macOS by hand.

## [3.6.0.14] - 2026-11-22

The box opens in place, and the hand-out measure run for real. On the drawing of a running session a click on a box
now opens that box's card at the box, with a head that holds still, one row of actions and one body that scrolls.
`halo gym handout` was run on real local models for the first time: it showed that 3.6.0.10's words alone made no
local model hand work out, so a local main on Auto is now also reminded at each task, and the command now reaches a
host that needs a key, says what it does while it runs and says whether a model passes.

### Added

- **A click on a box opens its card at the box (Agents -> Live).** A helper, a group, main, a workflow's block or a
  line's label: the card is 440 wide with its top-left at the box's top-left (its top-right when it would pass the
  view's right edge), lifted to stay inside the view. It unfolds from the box's own rectangle in 160 ms and folds back
  into it in 120 ms; with reduced motion it comes and goes at once. One card at a time: a click on another box opens
  that box's card, a click on the same box closes it.
- **In Session's map the card sits at its box:** 6 px under it, the drawer less 16 wide (6 px over it when there is no
  room below; else the drawer's lower corner, as before). It opens and closes at once there.
- **The card holds still: a head, one row of actions, one body.** The head: the title and its x, the state line, "Why
  this model: ..." and a NOW line for the chosen agent ("Grep · 4 s", "waiting for you · 12 s") in two rows held from
  the start. On a helper's card the state line changes with the helper's box ("queued", "waiting on you", "stopped":
  the same words the box shows) in rows held for its longest state. The actions: Pause or Resume and Stop for the
  chosen agent, "Open the map at {sender}" when there is one, "Open in Agents -> Live", and the steer box under them
  (three lines at most; a longer steer scrolls inside it). The body alone scrolls: the asks that were there at the
  click, a row per live agent (a click on its words aims Pause, Stop and the steer box at it; an ended one reads
  "ended at {t}"), what the card's agent said last, on main's card "Told it can start: {every name}", then asks that
  arrive later.
- **Last said.** Under its rows the card shows what its agent said last: "Last said at 14:02:11: ..." (the time as
  your locale writes it, with its seconds) (for a helper that answered and ended: its answer), else "Last thought at
  ...: ...", else "Nothing said yet."; "Could not read what it said: ..." on an error. It is read once, at the click,
  for the agent chosen then (a group's first row, else the helper, else main): the card opens when that read answers
  or after one second, and an answer that comes later is added to the body. A card closed before the answer stops the
  read quietly.
- **Ways to close the card, in both drawings:** Escape (outside a text field), its x, a click anywhere outside it, a
  wheel over the drawing or a zoom. A wheel over the card scrolls its body. Escape in the Stop confirm closes the
  confirm only. The Stop confirm and the slot under the drawing do not close it by a press; the slot's own press still
  closes it first, then scrolls. Leaving the section by its key closes it too.
- **On Auto a local main is reminded at every task to hand work out.** After your task, on the line under the
  permission mode, a main that runs on a local model (`ol:`, `hf:local/`, `hf:mlx/`) and was told its helpers also
  reads: "If this job has parts that can run on their own, hand each one to a helper with the Agent tool before you
  work on it yourself (one call per part; `subagent_type` names the helper). A small job you do yourself." About 60
  tokens a task by Halo's own count. A turn that background results open, not a task of yours, does not carry it. A
  main on a cloud model, a main on a map of your own and every helper read exactly what they read before.
- **`halo gym handout` says whether a model passes.** Under each model's line, and under each hand-out card in `halo
  gym show` (cards saved by 3.6.0.13 too): "Verdict: passes. Today's words make it hand out {d} more of 4 parts.", or
  "Verdict: does not pass." followed by a sentence for each rule that fails ("Today's words do not make it hand out
  more ({a} of 4 parts, before {b}).", "It names a helper right in {r} of {n} calls (it needs 9 in 10).", "It finishes
  fewer trials with today's words ({f} of {n}, before {g})."), or "Verdict: none. {k} of {m} trials got no answer: run
  it again."
- **`halo gym handout` prints one line per trial as it ends:** "  now 2 of 3: 2 of 4 parts in 2 calls · own steps 1 ·
  finished · 41 s". A trial ends "finished", "not finished in 10 requests", "stopped by an error after {n} requests"
  or with "no answer". Each trial and the card keep their seconds.
- **The real-use check has a step for the drawing of a running session (for developers).** `python
  scripts/realcheck.py --only live-scene`: a real Studio and a real terminal session on Auto in one scratch home,
  seven helpers of a scripted model, headless Chrome on Agents -> Live and on Session's map at its narrowest. It
  reports each alone: the helpers' NOW words, the heads and main's turn line, the slot, nothing moving under a resting
  pointer, a long tool's held form, the rings, the box opening in place, reduced motion, nothing left behind. It runs
  only when named: today it fails on faults it found in the product (Known limits), so a plain run and CI leave it
  out; `--list` marks it.

### Changed

- **The gym's time line is the measured one:** "About 2 minutes per model with three trials when the model runs on a
  GPU (five real runs took 9 minutes together); a model that runs on the CPU takes much longer." It said 20 to 40
  minutes, unmeasured.
- **The gym's "now" is today's whole first request:** for a local main it carries the reminder line; "before" has
  neither the helpers words nor the reminder.
- **The gym's means count the trials that got an answer.** A trial whose first request got no reply is left out of
  them and named on the errors line.
- **One pair of Pause and Stop on the card,** for the chosen agent, where every row had its own pair. A row's hover
  reads "Pause, stop or steer this one with the buttons and the field above".
- **In a window too low for the head, the actions and a sliver of the body, the whole card scrolls,** so Send can be
  reached.
- **The real-use check's idle minute has Agents -> Live open (for developers).** `idle-cpu` now starts a session on
  Auto that hands one piece of work out, opens Agents -> Live on it, opens the helper's box in place and closes it,
  then measures 60 s: Halo's processes together under 5% of one core, and the page's interval timers counted at five
  moments: Live adds two, the box adds none and leaves none. When no browser opens it now fails (it measured without
  the page before); with `--browser none` it is a counted SKIP. Its budget is 240 s on Windows and 180 s elsewhere;
  CI's real-use check has 60 minutes (it had 56).
- **The docs say what the drawing of a running session shows.** `docs/STUDIO-groups.md`: each helper's state word and
  NOW line, the held height, main's turn line and hover, the heads' counts, the slot's forms and tail, the rings,
  nothing moving under the pointer. `docs/STUDIO-live.md`: "The box opens in place". A test holds every quoted line to
  the words the product makes.

### Fixed

- **`halo gym`, `halo gym handout` and `halo gym propose` reach a host that needs a key.** They did not load the keys
  file, so a host whose key is kept by name (`api_key_env`) was asked without it and refused every request.
- **The gym speaks to a gateway in front of Ollama in its own dialect.** A host entry with `dialect: "openai"` was
  sent Ollama's own API and refused; the hand-out gym and the battery now speak to it as a session does, with the
  entry's key. Through a gateway the gym asks nothing of Ollama's own API and cannot unload the model; the card's
  errors line says so: "unload: {host} is a gateway that speaks the OpenAI dialect: the gym cannot unload {model}
  through it; it stays loaded until that host's keep-alive ends."
- **A run that no host answered is not a measurement.** It printed a row of zeros, saved a card and exited 0. It now
  prints "{ref}: not measured: {the cause}" (each cause once), saves no card and exits 1 when no model ran; when the
  first trial of both arms gets no answer the run stops there.
- **The model listing no longer asks a gateway for Ollama's `/api/ps`.** The answer was always a refusal.

### Known limits

- **What the first real runs measured (local models on one machine with a GPU).** With 3.6.0.10's words alone no model
  handed out more than before. With the reminder, five trials each way: one 27B model went from 0 to 2.2 of 4 parts
  and passes; a 12B model went from 0 to 0.8 and now finishes every run (it finished none before), which is short of
  the one part more that passing needs; a second 27B model and a 30B coder model handed out nothing with any wording
  tried (a stronger line in the system text, a nudge after three steps done alone, thinking on). In ten trials a job
  with one small part was never handed out with the reminder. The samples are small: `halo gym handout <model>` tells
  you which kind your model is.
- **Through a gateway the hand-out gym was run for real once** (three trials: it reached the host with its key,
  measured, and left the model loaded as its errors line says). The battery (`halo gym`) through a gateway was driven
  by tests only, and its repair round there by no test.
- **`halo prompt` does not count the permission mode line or the reminder.** Its measure of a first request never held
  that line.
- **Last said is the words of the agent chosen at the click.** Choosing another row aims Pause, Stop and the steer box
  at that agent, but Last said stays the first one's and does not name whose words they are.
- **The card has no model block yet.** Picking a model and "Make it an agent" from the card are the next release.
- **"6 px under its box" in Session's map is proven on numbers, not in a browser:** the browser scene has no room
  below its box, so there the card sits over it.
- **Leaving Session by its key with a card open in its map** runs the same code as in Agents -> Live, where it is
  tested; no browser test drives it from Session.
- **Found by the new `live-scene` step, not fixed in this release.** (1) In Session's map at its narrowest a group's
  counts line takes a second row when a part joins it (a helper asks, one ends, a cost appears) and every box under it
  drops 17 px, also under a resting pointer (so since 3.6.0.13, with or without a card; an open card stays where it
  opened). (2) A helper is not given an MCP server's tool: in the step a general-purpose helper that called one got
  "Unknown tool", also with the server set to `alwaysLoad`. A helper gets the tools main's list holds; why the
  server's tools were not in it is read in the code (a session in a terminal builds its list before its MCP servers
  connect), not proven in a run. (3) Pause on a helper that waits on you stays "Pause": nothing shows whether it was
  taken. (4) A helper that ends at once sometimes shows no "done in {span}" (one run in two). (5) A group whose
  helpers cost under half a cent reads "$0.00". (6) Seen once: a helper of a fan-out that ran a command read "waiting
  for a model reply". Two of the step's scenes also depend on the order four helpers start in.
- **No talk between agents is drawn,** and only Auto draws NOW, TURN and the rings: both as in 3.6.0.13.
- **Every Known limit of 3.6.0.13 still holds, except three:** the gym has now been run on real models, it prints a
  verdict, and the open box is no longer the old step-in card.
- **Where it was checked.** On the Linux VM: all three suites (the module runner's four shards, the bridge suite and
  the terminal app's suite; on a copy with no git history: the few tests that need it run in CI), then the modules
  changed after that run once more, the browser modules of the drawing and of the card, and the full real-use check,
  eighteen of eighteen steps (`live-scene` is left out of a plain run and fails when named, as said above). On the PC
  (Windows), one at a time: the plain modules of this release, and the real-use check's `idle-cpu` step alone (0.7 to
  3.9% of one core in four runs; a fifth failed before its fix, when a line typed a tenth of a second after the
  session's status line showed was not taken). `halo gym handout` was run for real on five local models on one
  machine's own Ollama, and once through a gateway that needs a key. One reviewer read the whole diff. Browsers on
  macOS and Windows are CI's part.

## [3.6.0.13] - 2026-11-22

Live you can read, and a measure. On the drawing of a running session (Agents -> Live and Session's map, on Auto)
every helper's box now says in words what it does at this moment, a box keeps its height, main's box says what this
turn did, a group's head counts what is true, the slot at the foot names the group that waits on you when it is out of
sight, and a box rings once when something happens to it. A new command, `halo gym handout`, measures on a local model
whether main hands work out more with the words 3.6.0.10 gave it. It was never run on a real model: the limits are at
the end of this section.

### Added

- **NOW: every helper's box says what it does now.** A line under its state line, the first that applies: "waiting for
  you · {s}"; "paused"; "queued · {s}"; "stopped after {span}", "done in {span}", "failed after {span}"; "{tool} ·
  {s}" while a tool runs (the tool's own name, as the Feed shows it); "thinking · {s}"; "writing · {s}"; else "waiting
  for a model reply · {s}". A thought is drawn in the thinking colour, waiting for you in amber. When Studio does not
  know since when, the words stand alone, with no separator at their end; a tool Studio knows only from the agent's
  row reads its name alone; and when Studio never saw a helper end, the line stays blank (the state line already says
  how it ended). On Auto main's box draws the same line where its tool clock was, while main works or waits.
- **A queued helper reads "queued" and a stopped one "stopped".** Before, a queued helper read as working and a
  stopped one as done. Both have a calm edge: they are not working and not done.
- **A helper's hover adds "Now: ..." with the whole words.** For a queued helper: "Now: queued · {s}: it starts when a
  running helper ends."
- **Main's box on Auto says what this turn did:** "This turn: started {h} helpers · used {t} tools itself", under NOW.
  A part that is zero is left out; the line is blank before the first turn and stays until your next message. Main's
  hover reads "main · {model}", "This session: started {H} helpers · used {T} tools itself" and "Told it can start:
  {names}" (twelve names, then " and {n} more"); before the session's first request it reads as before.
- **A group's head counts from the true state:** "{w} working" (running or paused), "{q} queued", "{v} waiting on you"
  (amber), "{d} done", "{k} stopped", "{f} failed"; a part that is zero is left out.
- **The slot at the drawing's foot names the group that waits on you when it is out of sight:** "↓ {name} · waits on
  you" when it lies below and "↑ {name} · waits on you" above (a press brings the group's head to the top, or the
  helper that asks when the head alone would leave it out of view), and "{name} · waits on you · under the open box"
  when the open card covers it (a press closes the card). With nobody waiting out of sight it names a working group
  below, as before. Its tail now reads " · and {n} more groups below" (" · and 1 more group below" at one); before it
  read " and {n} more below".
- **A box rings once when something happens to it.** A helper that starts waiting on you (amber) or fails (red) gets a
  ring that shakes for a third of a second; a helper that ends done (green) and a group main hands work to (the
  group's colour) get a ring that fades. Nothing rings on the first draw, out of view, under the pointer or under the
  open card; a box rings at most once in 4 seconds, at most four at once, the top-most first; with reduced motion set
  nothing rings. Main's box never rings.
- **`halo gym handout <model> [<model> ...] [--trials N]`: does main hand work out more on your local model?** It runs
  one fixed four-part job in a scratch copy of a small project with each local model you name as main: N times
  (default 3) with the words main had before 3.6.0.10 and N times with today's, taking turns. No session runs and no
  helper is started: the gym answers every tool call itself inside the copy, and each part handed out gets a fixed
  answer. It prints four facts before its first request (what it does, that it is free, how long it may take, what it
  writes), then one line per model: "{model}: hands out {a} of 4 parts in {c} calls (before {b}) · bundled {u} · names
  right {r} of {n} · own steps {o} (before {p}) · finished {f} of 3 (before {g}) · 3 trials" (the two 3s follow
  `--trials N`; a mean of one call reads "in 1 call"). A ref that is not a local model prints "{ref}: the gym runs
  local models only." and sends nothing. A local model whose host is not found prints "{ref}: not measured: {the
  cause}" and gets no card. When no model ran the command exits 1. A model that is sent the same words in both arms
  prints "{model}: not measured: this model is sent the same words before and today (it takes no tools, or today's
  words do not fit its window), so there is nothing to compare." and gets no card. An Ollama model is unloaded at the
  end (when it could not be, the card's errors line says so) and the copy is removed. The paths and patterns the model
  names are held inside the copy: one that leaves it is refused before the system is asked anything about it.
- **The cards of `halo gym handout` and `halo gym show`.** One card per model and host under
  `~/.halo/gym-handout/<host>/`, apart from the battery's cards (nothing that reads the battery's results reads them).
  `halo gym show` prints the battery as before, then "Main hands work out (halo gym handout):" with each card's line;
  with only handout cards it prints those and exits 0. The new docs part is docs/COMMANDS-gym-handout.md.

### Changed

- **A box keeps its height.** A helper's NOW holds two rows from the first draw and its state line the room of its
  longest words, so a helper's box does not grow when it starts waiting or its words change; main's TURN line holds
  its rows too. Words that need more (a long tool name) grow the box once, while the drawing is not held, and the box
  keeps that height. While the pointer rests on the drawing, and for later words that need more than the box has, NOW
  reads "a tool · {s}" and the whole words are in the hover (for main: in the line's own tooltip). A helper's box is
  taller than before.
- **Session's slot keeps the room of its longest words from the first draw:** four of its lines at the default drawer
  width.
- **A press on the slot while a card is open closes the card first, then scrolls.** Before, it scrolled with the card
  open.
- **A group's head reads "{v} waiting on you" where it read "{v} waiting",** and a group with a stopped helper no
  longer reads as all done: only helpers that ended done count.
- **Studio's row of a session carries the agents the session had at its start,** which main's hover on Auto reads.

### Fixed

- **While the pointer rests on the drawing, a helper that joins a group no longer changes the group's box.** The group
  keeps the members it was laid out with until the pointer leaves; then the new helper is drawn, and its group rings.

### Known limits

- **`halo gym handout` was never run on a real model.** Every check used the tests' stand-in for Ollama on this
  machine's loopback. Its time line says so itself: "About 20 to 40 minutes per model with three trials (not measured
  yet: the first run sets this line)." Whether main hands out more on your model is what the first real run will say.
- **The command prints counts, not a verdict.** The bar the design sets (today's words hand out at least one part more
  than before, a helper is named right in at least 90 % of the calls that name one, and no fewer trials finish) is in
  the docs, not in the output.
- **The `hf:local/` and `hf:mlx/` routes of the command are built and no test drives them.** Nothing is unloaded on
  them: a server Halo starts for an `hf:mlx/` model is handled as the battery's (`halo gym`) is. A `local:` ref is
  refused with the same line as a cloud ref, as the battery does.
- **A trial has no time limit of its own.** It ends after 10 requests, but a model that sends a search pattern that
  never ends holds it until Ctrl+C.
- **No talk between agents is drawn.** No agent sends a message to another agent yet, so there is nothing true to
  draw.
- **"The open box" is today's step-in card.** The box that opens in place is a later release.
- **While the pointer rests on the drawing, a group's head counts leave out a helper that has just joined,** until the
  pointer leaves.
- **The slot's answer is worked out again on a scroll, a change of the view's height, a new layout and when the card
  opens or closes.** A window resized with the card open can keep "under the open box" until one of those.
- **The slot judges "out of sight" up and down only.** A helper that waits on you and is out of view sideways (the
  drawing zoomed in) is not named.
- **A workflow's group that is drawn as its steps has no helper boxes:** a helper of it that waits on you is not named
  by the slot and does not ring.
- **Only Auto draws NOW, TURN and the rings.** A map of your own draws its boxes as before.
- **Every Known limit of 3.6.0.12 still holds.**
- **Where it was checked.** On the Linux VM: all three suites (the module runner's four shards, the bridge suite and
  the terminal app's suite; on a copy with no git history: the few tests that need it run in CI), then the modules
  changed after that run once more, and the full real-use check, eighteen of eighteen steps. On the PC (Windows), one
  at a time: the plain modules of this release and the two browser modules of the drawing, once each. The whole run on
  the VM found one stylesheet imported in the wrong order; it is fixed. The reviewer found that a network path named
  by the model under test was looked up before it was refused; it is now refused first, and a test holds it. The
  package checks found that the first group of a session did not ring; it rings now. `halo gym handout` was never run
  against a real Ollama or a real model: every check used the tests' stand-in. Browsers on macOS are CI's part.

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
