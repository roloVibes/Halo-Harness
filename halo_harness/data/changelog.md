# What changed (the newest version entries of CHANGELOG.md, shipped with the package; `halo whatsnew` reads it)

## [3.6.0.23] - 2026-11-27

A closing release, Windows only. Every program Halo starts is inside Halo's Job from its first instant: the start
moment named in the Known limits of 3.6.0.22 is closed. Nothing changes on macOS or Linux.

### Fixed

- **Windows: a hard kill of Halo in the moment a program was being started could leave that program behind.** A
  program joined Halo's Job a moment after its start. Killed in that moment, Halo left a browser it runs itself
  suspended for good, any other program running on, and a tool server was never in a Job of Halo's at all. Now
  Halo makes itself a member of a Job of its own, first thing. Everything it starts is born inside: an ordinary
  program, the browser Halo runs, a tool server, a helper. Windows ends them with Halo at any instant.
- **A program can no longer slip out in that moment either.** The Job Halo sits in has to let a kept program
  leave (a background job, the updater, your browser). So a program born in it could let a child of its own leave
  before Halo had moved it into the strict Job; Git Bash programs do that whenever they may. An ordinary program
  is now started suspended and let run only once it is inside the strict Job.

### Changed

- **What is yours stays yours.** Your editor (from Roles, the crew editor, the terminal app, the /mcp dialog) is
  started so that it leaves Halo's Job: it never ends with Halo, not at a normal exit and not at a hard kill. Kept
  programs leave as before: by themselves, or from outside every Job where an outer Job lets nothing leave, or
  held by that outer Job with the one line that says so.
- On Windows Halo no longer falls back to opening your browser from inside its own process (it would close with
  Halo). Where no kept start can be made, the address stays printed for you to open.
- **For pack authors:** on Windows a program a pack starts by itself with Python's own `subprocess` is born in
  Halo's Job now and ends with Halo, also at a normal exit. A program that must outlive Halo is started through
  `closing.kept_kwargs`, the person's own program through `closing.start_persons`.

### Tests

- Proofs with the kill placed in the moment on purpose (the starter held right after a create): an ordinary child,
  the browser stand-in, a tool-server stand-in, inside a launcher-like Job and inside a strict outer Job: gone. A
  kept child and an editor: they OUTLIVE the starter, after a normal exit and after a hard kill. A grandchild that
  asks to leave as its first act: gone. A resume that fails: the child is ended and the caller told. A
  self-assignment that fails: the old path, one trace line.
- The independent check found a kept start that ended with Halo inside a strict outer Job when it could not be
  started from outside; repaired, with its test. The review asked whether the terminal app's editor still ended
  with Halo; run, it does not, and that shape is a test now.
- Real use on a Windows PC: a real `halo init` in a scratch home, inside a strict outer Job, with no outer Job,
  and through an installed launcher. Healthy starts asked the browser exactly once; hard kills at many moments
  left nothing.

### Known limits

- A tool server may start a program of its own that asks to leave before the server library's own Job holds the
  server (the library assigns that Job after the start). Halo's Job holds the server itself from its birth.
- A Ctrl+C in the few instructions between a create and Python's record of it leaves that one child suspended
  until Halo ends; it ends with Halo.
- Where Halo cannot join a Job of its own (an outer Job that refuses a nested one), it works as 3.6.0.22 did, and
  one trace line says so.
- Not tried before the push: a hosted machine's own outer Job, other installers' launchers, a real service, a real
  browser.
- Every other Known limit of 3.6.0.22 still holds.

## [3.6.0.22] - 2026-11-27

A closing release, Windows only. The hole a test caught while 3.6.0.21 was made is closed, and a second of the same
kind that was found while closing it. No new feature. Nothing changes on macOS or Linux.

### Fixed

- **Windows, inside a Job that lets nothing leave (a CI runner, a service, some terminals): a hard kill of Halo in
  the instant it started the helper that opens your browser left that helper behind,** a PowerShell that was
  suspended and did nothing, for good. Halo started the helper suspended, put it into its own Job and only then
  let it run; killed between those two steps, the helper was in no Job of Halo's and nobody was left to wake it or
  end it. Now the helper is started awake, and the first thing it does is wait for one word from Halo on a pipe of
  its own. Halo writes the word once the helper is in its Job. A Halo that is gone before that closes the pipe by
  being gone, and the helper leaves at once, having started nothing. It was there since 3.6.0.18 and named in
  3.6.0.21's Known limits. The same helper starts a program you asked to keep (a background job, for one)
  inside such a Job, so that start is covered too.
- **The same for the short probe** that asks whether a program may leave the Jobs Halo is in (once per process,
  before a browser or a kept program is started). It was a `cmd` created suspended and ended at once; a hard kill
  while it was up left a suspended `cmd.exe`. It now waits on a pipe of its own in the same way and ends when the
  pipe closes. It runs with `/d`, so no AutoRun command of yours runs inside it.

### Tests

- Halo is killed hard exactly between the helper's start and its adoption, and nothing is left. The kill is put
  there on purpose (the test holds the starter in that instant), never hoped for. A helper whose adoption fails is
  gone and has started nothing; a healthy start still starts the program exactly once. A hard kill while the probe
  is up leaves nothing; the probe passes `/d`. The two hard-kill tests are red on 3.6.0.21.
- Real use, on a Windows PC: a real `halo init` in a scratch home, inside a Job that lets nothing leave, with a
  stand-in for the browser. Killed hard in that exact instant, 3.6.0.21 left the helper both times of two; this
  release left nothing five times of five, and nothing at sixteen other instants from the address line to a second
  after it. The browser was asked once where the start had been let through, never twice, and not at all where
  the kill came first.
- Healthy starts are as fast as before.
- The helper's script is checked as text: the wait for the word is its first act, and it never asks PowerShell
  for its piped input (PowerShell would then read Halo's word itself).

### Known limits

- **Windows: a child joins its Job a brief moment after it is started, not at its start.** The moment is the time
  Halo takes to put it in: usually far under a second, longer on a busy machine. A hard kill of Halo in exactly
  that moment leaves that child, and anything it started in that moment, outside the Job. A server that reads from
  Halo ends when its pipe closes, a tool's command runs to its own end, and Halo's own children watch for Halo and
  close within two seconds; but a browser that Halo runs itself is started suspended and would stay so until you
  end it. Found while closing the hole above; it has been so since Halo first used a Job (3.6.0.0), and nothing
  has been seen left this way. Closing it means starting every child inside the Job from its first instruction,
  which changes the base of how Halo starts programs: it is the next release's first job.
- Not tried: a PowerShell in Constrained Language mode. If the helper's read of the word is refused there, the
  helper does not wait for it and goes on to the start. The program's own starter still refuses to run it once
  Halo is gone, so nothing outlives Halo; but the helper would not have "started nothing".
- The new tests have not run on a hosted Windows machine before the push; the hosted run follows it.
- Every Known limit of 3.6.0.21 still holds, except its first (closed here).

## [3.6.0.21] - 2026-11-25

Left-overs, and checks that tell the truth. No new feature. The small faults the last two reviews named are
closed, and five checks that went red on a slow test machine while the product was right now measure what they
mean to measure.

### Fixed

- **A load Halo saw, or a window it measured, counts only under the server it was seen under.** 3.6.0.20 lets a
  measured window, and a window a session saw sit wholly on the card, raise a memory estimate that is too low. Both
  were trusted after an Ollama upgrade or a change of the settings that change the size of the same window (the
  cache type, how many requests the server takes at once, `OLLAMA_GPU_OVERHEAD`), so the first session after such
  a change could ask for a window that no longer fits. Each record now keeps the server's version and the settings
  Halo can see, and is used only when they are today's. (For a server on another machine Halo sees its version
  only; `OLLAMA_GPU_OVERHEAD` is read from Halo's own environment.) A measurement made before this release keeps
  its window. A window that 3.6.0.20 only saw sit on the card, without a measurement, no longer raises the estimate
  after the update; `halo local measure <model>` settles it.
- **A local session keeps what you paste.** A lean request leaves out the list of the other tool servers' tools
  (3.6.0.20); it also dropped any message of yours that happened to begin with that list's first words. Only the
  list itself, exactly as Halo writes it, is left out now.
- **The line that tells a local model how to reach a server's tool is true.** It said every such tool can be called
  by its name; only a tool named `mcp__...` can. It now reads `- ToolSearch "<words>" finds a server's tool; a tool
  named mcp__... can also be called by its name.`
- **No "Exception ignored in atexit callback" after a forced end.** Once Halo's closing procedure has run, nothing
  new is started (3.6.0.18). When it ran first on another thread (a hard end after the grace, a closed console),
  a pack's exit hook or a stop that tried to start a program printed a traceback on the way out. The start is
  still refused; the refusal is now taken quietly. With `HALO_CLOSE_TRACE` on, one trace line names what was
  refused.
- **The wait between two changes of the model pool never counts a change as lying in the future.** A change stamped
  a moment after the clock's reading (the stamp is rounded) read "-0 min ago" and added that moment to the
  ten-minute wait. It is now zero seconds ago.

### Changed

- What a local model is sent: the one ToolSearch line above, and a pasted message that begins like the tools list
  stays in the request. Nothing else; a session on a large-window model is sent what 3.6.0.20 sent, byte for byte.

### Tests

Each of the first four went red on a hosted test machine in the last three releases although the product was
right; each was made wrong on purpose once to see the new check still fail, and then run ten times.

- A browser test of Studio's Live view counts the redraws a scroll causes. It counted while the page's own clock
  and live feed kept running, so a tick could land in one of its two counts (red about one run in three on macOS).
  The page's clock and feed are held still while it counts; a redraw the scroll itself causes is still counted.
- The real-use step that builds an agent and reads its "ready" card waited 15 and 30 seconds for a turn and then
  blamed the card's words. It waits the checker's own budget for a turn, and a turn that is still running is said
  as that.
- Budgets of CPU time (an idle Studio page: 5 % of one core; Studio's two start checks: 5 CPU-seconds each) are
  now set against the speed of the machine they run on, measured in the same run with a fixed piece of work (never
  under the budget, at most four times it); the line says the factor when it is not 1.
- A redraw test counted a read that Studio's file watcher makes after the redraw. It now sends the Builder's
  message before the file is written, so the page must draw from that message alone, and counts only reads
  before the redraw.
- New, not one of the four: a session on a large-window model WITH other tool servers is driven through the same
  path a real turn takes and compared with what it must be sent (3.6.0.20 proved this for one function only).
- Two more, from this release's own first run on the hosted machines (each read, neither the product's doing in a
  way a person would meet). The real-use check gave `halo init` ten seconds to reach the browser; on a hosted
  Windows machine, where that start goes through a helper, they ran out once: it has forty-five, and the wait
  ends as soon as the browser is asked. And a test that sets the wait between two changes of the model pool to
  zero was still told to wait ("-0 min ago"): see Fixed.
- And one from the run on the version's own commit: the test that proves `halo local prompt` starts nothing
  compared the NUMBER of threads before and after, and failed when a thread an earlier test had left ended in
  between. It now looks for a new thread.

### Known limits

- **Windows, inside a Job that lets nothing leave (a CI runner, a service): a hard kill of Halo in the instant it
  starts the helper that opens your browser can leave that helper behind,** a PowerShell that is suspended and does
  nothing. A test caught it once on a hosted Windows machine while this release was made. It has been there
  since 3.6.0.18, and no other way out is affected (Ctrl+C, a closed terminal, a quit). The next release closes it.
- When the notice of a file write reaches Studio before the Builder's own message about it (a slow machine), the
  newly built box is drawn without its "new" tag. Seen while fixing the redraw test; not fixed here.
- A browser page's own errors still do not fail a test: only one in five of the test drivers collects them. On the
  one full pass made for this release no page error was seen.
- A tool server whose name contains two underscores in a row is listed under a cut name in a local model's lines.
- The hosted Windows and macOS test machines were not available for the checks above before the push; the ten
  runs of each were made on Linux.
- Every Known limit of 3.6.0.20 still holds.

## [3.6.0.20] - 2026-11-24

Local models, measured right. Halo's memory estimate was about eighteen times too high for one family of models
and gave such a model a 4k window where 65,536 fits; it now counts what the server really keeps, and a measurement
or a load Halo has seen can raise an estimate that is too low. A local session no longer carries the names of every
tool of your other tool servers: on one real setup with many servers its first request went from about 14,600
tokens to about 6,300. `halo local prompt` counts those servers, and `/status` describes the session it is typed in. All
of it was checked with real sessions on a real Ollama.

### Fixed

- **The memory estimate of a latent-attention model.** A model that keeps one small latent row a layer in its cache
  (its `/api/show` names `key_length_mla` and `value_length_mla`) was estimated as if every head kept its full key
  and value: about eighteen times too much. (An older file of the same family names neither; the server runs it
  with every head's full cache, and it keeps the estimate it had.) A 30B model of that kind was held at 4k, where
  it sits wholly on its card at 65,536. The estimate now counts what the server keeps. Checked against five real
  loads of one model: it is never below a real load. A new session on that model now starts at 65,536 with one
  load and one tool list; 3.6.0.19 started it at 4k, cut its first request and reloaded on the second turn.
- **A reading of the card no longer counts a load twice.** Halo keeps a reading of the card's free memory for a
  minute and adds back what its own loaded models hold; right after a load that counted the model twice, and the
  second request of a session asked for a window four times the first (a reload, and with the estimate now right,
  a window that would spill). Each reading now adds back only what was loaded when it was taken.
- **A measurement, or a load Halo saw wholly on the card, raises an estimate that is too low.** After `halo local
  measure <model>` a new session starts at the measured window (the lines call it "learned cap") while the card has
  the room it had at the measurement. A window a session saw sit wholly on the card ("seen to fit") does the same
  for later sessions while the card has that load's room. With less room on the card than then, the estimate
  stands, as before. `halo ollama`, `/ollama` and Studio's Models list print the window a session is sent, with the
  source word `calibrated` or `seen`. Before, the smaller of the estimate and the measurement always won, so a
  measurement could never help a model the estimate misjudged.
- **A session's tool list never changes in the middle of it.** The list is the one of the window the first request
  is sent at (3.6.0.19), but it was kept only when that window differed from the one Halo first resolved; when the
  resolved window moved later (the card got busier), the list changed between two turns. It is always kept now.
  So a session that started at a small window keeps that window's list also when its window grows later (a
  profile, a measurement, a freed card); a new session, or a switch of the model, gets the larger one.
- **With a window of your own (a profile), the first turn loads the model once.** It loaded twice ("loading ...",
  then "loading ... again at a 32k window").
- **The line for a first request that is over its window says why the window is that small.** After "the system
  prompt, the memory and the tools alone are N tokens, more than this W window holds with the reply's R:" you now
  read, when the window is Halo's own estimate and nothing was measured, "that window is Halo's memory estimate for
  <model> on <host>; `halo local measure <model>` measures what the card holds"; for a profile, "the profile of
  <model> on <host> sets that window (`halo ollama profile`)"; for the host's `max_ctx`, "the host's max_ctx sets
  that window"; otherwise, as before, "a bigger-window model holds them".
- **A first request is not compacted after it was sent either.** 3.6.0.19 stopped the compaction before the send.
  Now, when Halo judged a first request to fit and the server then cut it: a reply cut at the window stands ("<host>
  cut the reply at the window (...): nothing earlier to compact, the reply stands as it is"); a prompt the server
  trimmed is sent once more at a larger window when the call may get one, and otherwise stands ("<host> read X of Y
  tokens of the first request (its window is W): nothing earlier to compact, the answer stands"); a first request
  Ollama refuses outright at a window that cannot grow ends with one line ("<host> refused the first request (N
  tokens) and its window cannot grow: nothing earlier to compact"). Before, each started a compaction of a
  conversation with no answer in it, then more calls, then an error. From the second turn on nothing changes.
- **A local session no longer carries the names of every tool of your other tool servers.** Every session logs a
  list of the tools it can load on demand, and that list rode in every request, outside every budget: with sixteen
  servers of sixty tools about 9,400 tokens, more than half of a 16,384 window. A lean request (a local model, any
  model with a window under 65,536, their helpers, the smaller request Halo makes after a model's answer failed,
  and any session with the lean prompt switched on) now leaves the list out; each server's line says how many
  tools it has, ``- `<server>` (60 tools): <what it is for>``, and one line says that ToolSearch finds a server's
  tool. ToolSearch searches the tools itself and never needed the list. A session on a large-window model is sent
  what it was sent before, byte for byte (only that smaller request after a failed answer is lean).
- **A server's line in a local model's system text is its first sentence,** 160 characters at most. One server's
  whole first line of more than 900 characters rode in every request.
- **`halo local prompt` counts the other tool servers.** It reads the servers a session in this folder has and
  their tools from Halo's own cache of their tool lists, and starts nothing. It prints "other tool servers: N, M
  tools (from Halo's cache of their tool lists; none was started)", and for a server Halo has no cache of yet "not
  counted: the tools of N other tool servers (<names>); a session's /status counts them". On the real setup above
  it said 6,410 tokens where the server then read 6,265.
- **`/status` describes the session it is typed in:** its own first request, with its own tools and servers. It
  described a new default session.
- **The release tool** no longer prints false "driver retried once" warnings (it read the workflow's own script in
  the log), and says so when a job never ran because no runner took it.

### Changed

What a model is sent changes in these cases only; a session on a model with a large window (65,536 and up) is sent
byte for byte what 3.6.0.19 sent (the request bodies were compared across both), except the smaller request Halo
makes after a failed answer, which is lean.

- A latent-attention model: a larger window, and the tool list of that window.
- A lean request: no list of the other servers' tool names; the servers' lines with their counts, each its first
  sentence; one ToolSearch line. A helper's own system text gets those lines too when its request held the list.
- A first request the server cut, trimmed or refused: no compaction request follows.
- A session whose resolved window moves after its first request: the first request's tool list on every later one.
- After `halo local measure`, or after a load seen wholly on the card: the observed window when it is larger than
  the estimate and the card has the room.

### Tests

- The three waits that follow a click in one browser test of Studio's Live view have a slow runner's budget (one
  of them ran out on a hosted Windows runner and five tests went red from that one read).
- The stand-in Ollama of the tests can answer "exceeds the available context size", so the rule that a session
  held at a window is never re-sent past it has its own test now (3.6.0.19 shipped it without one).
- Four tests that pinned "compacted and re-sent" for a first request are rewritten to the new truth and renamed to
  what they assert; the compaction of a LATER request after the send has a new end-to-end test.

### Known limits

- The estimate errs on the safe side: for the model it was checked against it is 0.3 to 2.4 GB above the real
  load, so a model can still get a smaller window than its card would hold. `halo local measure <model>` settles
  it; the session after it starts at the measured window, which can fill the card almost to the top. A window of
  your own is `halo ollama profile set <host> <model> num_ctx <N>`.
- Model families with a sliding attention window are still estimated too high (not checked against a real load).
- A session on a large-window model still sends the names of all tools of your other servers in every request, as
  before: with many servers that is thousands of tokens. Its sentence "calling them directly will fail" is not
  true on Halo (such a tool is loaded when it is called).
- `halo local prompt` counts a server only when Halo has a cache of its tools made with the server's settings as
  they are now (a session makes it). Studio's model card and `halo doctor` describe a new session without the
  other servers.
- A reading of the card that another view took first (Studio's panel) and that an estimate uses only after a load
  can still count that load twice.
- A first request can still be compacted on two rare paths: an overflow in the middle of a stream on a dialect
  other than Ollama's, and a compaction left pending by a switch of the model.
- A first request that cannot fit its window is sent at once, without the card that offers a bigger-window model.
- The real sessions were run on Windows with one Ollama and one card; the same paths run with a stand-in server in
  the tests on Windows, macOS and Linux.
- Every Known limit of 3.6.0.19 still holds, except the ones this release closes: the estimate of a
  latent-attention model, a measurement that could not win over it, the tool list that changed on a later turn,
  the other servers' tool names in a local session, and the first request compacted after the send.

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
