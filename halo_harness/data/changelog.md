# What changed (the newest version entries of CHANGELOG.md, shipped with the package; `halo whatsnew` reads it)

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
  theme is `instrument`, as before. On 3.6: the same order, and `halo doctor --config` no longer says that Claude Code's setting beats the pick.

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

## [3.4.1.1] - 2026-11-12

What a third two-machine run found: a saved replay no longer carries your paths, another session's exit no longer stops
Studio, the glance says when Studio was restarted. Defects 38-66 of the 3.4.1.0 check (the PC and the Linux VM, the
fleet pack joined), each with its test; the fleet pack is 1.0.3 (`halo pack update fleet`).

### Fixed (wrong)

- 48: a session's quit stops only what that session started: a Studio started on its own (`halo studio`, above all
  with `--fleet`, members joined to its hub) is never stopped by another session's `/quit`; the quit line says "left
  running: Studio (started on its own; halo studio --stop)". A Studio a shell command opened (`halo replay open`,
  `halo init`) has no owner and stays too (children_stop.py, children.py, studio/launch.py).
- 56: a saved replay is safe to hand on: a path inside the project is written project-relative, any other under the
  home as `~/...` (every spelling: either separator, any case, Git Bash's `/c/...`, WSL's `/mnt/c/...`), and the user
  name and the machine name only where the owner typed them (the title, the lineup's names) or in a project path --
  applied when the file is written, to every field; Save's "not included" line says so; `halo audit privacy
  --replays` checks the replay folder (live/replay_private.py). The format is unchanged: an older file opens.
- 63: the glance on a Studio that was restarted (a new per-launch key, never kept or reused) says "Studio was restarted
  and has a new key: open the glance again from Studio (Session's ... menu -> Open the glance)" and stops asking; the
  same Studio back (a blip, the SSH forward re-made) is live again by itself as before.
- 50: a session's title is the owner's first words, in a session without a terminal as in the TUI (it was the prompt
  hook's JSON verdict, `{"ok": false, ...}`); such a stored title reads as the first words.
- 60: a goal run on the scrubber is drawn from its record's own times (`GET fleet/replay?run=`): each lane's states (it
  ends when it merged), its costs at each end, and "unknown at this moment" where the record cannot say, never $0.
- 42 (fleet): a need no card lists (the lead's `shell`) sends the lead's first answer back once; a harness the goal or
  the part names wins, and such a word is dropped there (said in the plan's notes); "1 part" in Attention.
- 51: a replay's WAITS rows count to the scrubber's moment, not to the present (and show on every box).
- 52: a permission card answered from Studio (a session without a terminal) reads "waiting on you" for its whole span.
- 57: `halo orchestra new` with no terminal on Windows (NUL answers isatty) says the no-terminal line, no traceback.
- 58: an Orchestra worker's brief says its own test runs are not the gate, and STOP WHEN's gate is the run's to count.
- 62: the report card's "In all ... waiting on you" is the sum of every listed wait (a card's own "after N s").
- 65: the glance's SPEND TODAY is the harness's today as the caps count it (`GET fleet/costs`), not a drawn session's.
- 66: a goal run's worker sessions count to their run's repo for the per-project cap, not to `worker-1`.

### Fixed (confusing)

- 40 (fleet): the plan's note reads this machine's permission mode and ask wait now, not a cached card.
- 43 (fleet): a files part's brief says to write its outputs with Write, never a shell redirect (which asks).
- 45: the update note no longer says "update available" for the same commit spelled 8 and 7 characters long.
- 46: the TUI's status bar calls the `default` mode `default`, as its cards, Studio and the mission note do.
- 49 (fleet): an away member the hub has not heard from since it restarted has an unknown today, never $0.0000.
- 54: Export a clip on a session already saved films that file instead of saving it again.

### Fixed (cosmetic)

- 38: `halo pack doctor` says the update command once, as the fix. 39: the firewall line counts the UDP twin of each
  Block rule. 41 (fleet): the status table keeps a command's `|`. 44: a spend under a cent keeps its figure
  (`$0.0004`, never `$0.000`). 47: a new file's diff reads `@@ -0,0 +1 @@` / `+8`. 53: Save writes the name its dialog
  showed. 55: no invalid escape sequence in Halo's source (`halo replay clip` printed a SyntaxWarning). 59: a goal run's
  lead is named by its model, never its role word `main`. 61: Compare says "A asked you 2 times; B 3 times." 64:
  Settings -> Studio has one Alerts control, saying what this browser will do.

### Also

- Every server a user restarts on the same port rebinds at once on Linux, as Studio does: `halo host serve`, the fleet
  hub, `halo voice serve` (tests/test_server_rebind.py). A pid is alive on Windows by its own exit code; a `tasklist`
  slower than its timeout is unknown, never dead (process_alive.py).
- The Python tests that run a UI `.ts` module (the cost agreement, the mode order, the model-name strip, the replay's
  time axis) run where node has no TypeScript support (Debian's v24, built without it) by transpiling with the UI's own
  `typescript` (tests/helpers/node_ts.py); with neither, the skip says what the box lacks.

## [3.4.1.0] - 2026-11-12

**Scrub a run back in time on the canvas, save it as one file, open it anywhere.** The living canvas, part 2 (the
owner, 2026-11-10: "the best real-time visualization and clarity of what is going on with multi-model multi-workflow
jobs"), section A of its plan: time on Agents -> Live, then a run's replay as one file and its clip.

### R1: the scrubber and the replay file

#### Added

- **The scrubber under Live's canvas** (`routes/agents/live/Scrubber.tsx`, `timeline.ts`; docs/REPLAY.md): the session's
  time axis with its phase bands (waiting on you, a tool, thinking, writing, idle) and one mark per spawn, hand-off,
  ask, failure and finish (hover: what it was). Dragging redraws the canvas as it was at that moment -- who existed, in
  which block, each state and what it ran, the plan's line labels, the sentence under the bar (an ask first), the cost
  so far -- under a "replay -- <time>" banner in muted colours; **Play** at 1x / 4x / 16x; **Now** (or Esc) returns.
  Over the session running now it shows the axis up to now and a drag rewinds it. It is the ONE replay control: a
  session, a goal run (coarse: each lane's start and end), a mission and a saved file play on it.
- **The replay file** (`live/replay_file.py`): **Save this run's replay** says what the file holds, costs and writes,
  then writes `<state>/replays/<session>-<stamp>.halo-replay` (JSON, `format: halo-replay`, `version: 1`: the agents,
  their states over time, the costs, the marks and bands, the lineup's blocks as they were), with no prompt, tool
  input or output, thought or path, every string through the export redactor. History lists saved files and **Open a
  file** takes one made on another machine; an older `GET fleet/replay` answer opens as version 1.
- **Export a clip** (`live/replay_clip.py`, `live/clip_chrome.py`): the range From .. To at the scrubber's speed,
  filmed on Live in headless Chrome and assembled by Pillow into one WebP (else GIF), 1200 px wide, 5 frames a second,
  at most 30 s (played faster to fit, said), under `<state>/replays/clips/`; it says the frames, length, width and
  path before it writes.
- `halo replay list | save <session> | open <file> | clip <file> [--from --to --speed]` (`replay_verbs.py`);
  `halo replay <session> --model <ref>` is unchanged. Studio routes `replays`, `replays/plan`, `replays/save`,
  `replays/import`, `replays/<id>`, `replays/<id>/clip`, `replays/clips/<name>` (`studio/replays_api.py`);
  `?mode=agents&view=live&replay=<id>[&at=<s>]` opens a saved file.
- `GET fleet/replay` answers `marks`, `bands` and `agent_costs` too (`live/timeline.py`); `live/history.py` rebuilds
  each question or plan review (its AskUserQuestion / ExitPlanMode call) and each permission card (the turn record's
  `permission_waits`) as a wait on you.
- From 3.4.1.0 a turn's record keeps a permission card's words (`debug_timeline.record_permission_wait(..., what)`), so
  its mark says what it asked; an older session's mark says "a permission card (answered allow after 6 s)".

#### Removed

- Cast's replay bar (`routes/roles/Replay.tsx`, `routes/fleet/replay.ts`, the Roles store's `replay`, `live.ts
  agentsAt`): its doors -- the agent inspector's Replay and history "replay", the Roles Live tab's "replay", the
  palette's "Agents: replay this session on Live" -- open the session on Live's scrubber. Its testids `replay-bar`,
  `replay-play`, `replay-scrub` and `replay-close` are the scrubber's.

#### Docs

- New docs/REPLAY.md; STUDIO-live.md "Time: the scrubber", STUDIO-agents.md, STUDIO.md, COMMANDS-sessions.md, the
  glossary's "replay", the docs map.

### R2: compare two runs, and a goal run saved as a replay file

#### Added

- **Compare two runs** (History on Agents -> Live; `routes/agents/live/Compare.tsx`, `compareStore.ts`; docs/REPLAY.md
  "Compare two runs"): every History row has a tick; two ticked -- any two of a session, a goal run and a saved replay
  file -- and **Compare** opens a page of the drawer, with Back (the ticks stay). "What differed" in three plain lines
  derived from the rows; the two runs over one time axis, each one's agents as lanes in their blocks in the phase
  colours; the rows -- how it ended, wall time, cost, tokens, the models (each one's share of cost and time), agents
  spawned, asks to you, failures, retries -- with the better figure named by a word in its cell (cheaper, faster, fewer,
  finished). One ticked: **Compare before / after**, split at its first steer (else halfway), **split at** moves it. No
  model call; nothing written. A ticked mission says it is compared from its report (the fleet pack's).
- Every figure is read from the run's own record (`live/replay_facts.py`): a session's transcripts, a goal run's report
  and lanes, a file's new `facts`; never a live counter. A cost Halo cannot price is "unknown" (the priced part with a
  "+", never $0) and the better cost is not marked on that row.
- `halo replay compare <a> <b> [--split T] [--json]` (a, b: a session id, a goal run id, a `.halo-replay` path or saved
  id); Studio's `GET replays/compare?a=&b=[&split=]` (`live/compare.py`, `live/compare_text.py`). The rows are plain
  data (`{key, label, a: {value, text}, b, better, word}`) another page can read.
- **A goal run saves and films like a session** (`live/replay_run.py`): Save this run's replay and Export a clip on the
  scrubber, `halo replay save <run-id>`, `replays/plan?run=` and `replays/save {run}`. Its file holds the lead and its
  lanes as agents, each lane's state changes from its record, the plan review as an ask, and its figures. The file
  format keeps version 1 (`kind: run`, `run_id` and `facts` are keys a version-1 reader ignores; an R1 file still opens
  and compares). The redaction test covers a goal run.

#### Fixed

- A session's replay counted a finished sub-agent's cost twice: its parent's transcript carries the sub-agent's
  rolled-up total and its own transcript its calls. `live/history.py` now skips the rolled-up line when it reads the
  sub-agent's own transcript (the scrubber's cost, the file's `cost_usd`).

#### Docs

- docs/REPLAY.md (Compare two runs, a goal run's file, the verb), STUDIO-live.md, STUDIO-agents.md,
  COMMANDS-sessions.md, ARCHITECTURE-modules.md, the glossary's "replay", the docs map.

### R3: the run report card, and Session says its permission mode

#### Added

- **The run report card** (`live/report_card.py`, `report_card_sections.py`, `report_card_text.py`; docs/REPLAY.md "The
  report card"): one card per finished session, goal run or saved `.halo-replay` file, rendered from its record --
  never hand-written, no model call, nothing written. R2's nine figures for that one run (the same cells Compare
  shows), then the story in about ten lines (who was asked what, what each handed back, each ask and failure, how it
  ended), where the time went (by phase, by block), where the money went (by model, by block), what failed and what
  happened next, what waited on you and for how long, which model did what, the files it wrote with their paths, and
  what this record cannot show, in words. A cost Halo cannot price is "unknown" or the priced part with a "+", never $0.
- Studio: each History row's own **Report** door (`ReportCard.tsx`): a session's or a file's card is a page of the
  drawer (Back, Replay, Copy Markdown); with nothing running, Live's empty state ends with a row for the session that
  ended last and its Report card (a row, never a pop-up). **One page per goal run**: the card is the first block of its
  report page in History; the cost / time / models lines of the report's facts moved into the card's figures, every
  door and testid kept. Missions are the fleet pack's: no card.
- `halo report <session|run|file> [--json]` (`report_cli.py`) prints the card's Markdown (`--json`: its data); Studio's
  `GET replays/report?ref=` answers the card and its Markdown. A file opened on another machine gives the same card.
- A replay's `facts` carry `artefacts` (each file an Edit / Write call wrote, by its path inside the project; one
  outside it by its name only; a goal run's: what merged and its workflow's saved outputs) and `answer` (the first line
  of main's last text). The file format stays version 1; an older file's card says what it cannot show.
- **Session's bar says the session's permission mode** (`session/ModeWord.tsx`): one small word (auto, default,
  acceptEdits, plan, bypassPermissions, dontAsk) with the mode's one-line meaning on hover, from the session's row; a
  status frame's `permission_mode` moves it, so Shift+Tab in the terminal changes the word.

#### Docs

- docs/REPLAY.md "The report card" (and what a replay file now names), STUDIO-live.md, STUDIO-agents.md,
  STUDIO-session.md "The mode word", COMMANDS-sessions.md, ARCHITECTURE-modules.md, the glossary's "report card" (+ twin),
  the docs map.

### R4: the glance, and the alert

#### Added

- **The glance** (`/?mode=glance`, `routes/glance/`; docs/STUDIO-live.md "The glance"): one phone-width page of this
  Studio, no rail and no panels -- the sentence of what is going on now (Live's own grammar over the session Live
  draws; what waits on you when there is no agent tree to read), what waits on you with its answers as large buttons
  that each say what they do (a text box first for an answer that needs words), the spend against its cap (today's, as
  the caps count it; "$x+" or "unknown" for what Halo cannot price, never $0; "no cap set"), the session's elapsed time
  and the last three events. It says **live**, that the feed is reconnecting, or **stale: last heard N s ago** after 15
  seconds without an answer, and reconnects by itself. Nothing opens on load; it calls no model.
- Where it opens: **Open the glance** in the palette (View) and in Session's "..." menu (ELSEWHERE), a dialog with this
  machine's address, Open it here (DOES / COSTS / WRITES first) and, for a phone, the steps and a code to scan when an
  SSH server answers here, else plainly that the page is this-machine-only (`GET glance/door`,
  `studio/glance_door.py`); `halo studio --mode glance` (a page word, not a section) prints the phone's line under the
  URL. No new listener, no new port: a phone reaches it only through an SSH forward of Studio's port, the door Studio
  already printed (docs/REMOTE.md "The glance from a phone").
- **The alert** (`studio.alerts`, Settings -> Studio -> Alerts, `lib/alerts.ts`; docs/STUDIO-live.md "The alert"):
  none (the default) or this browser's notification. Choosing the browser asks this browser for permission on that
  click, once, never on load; then one notification when something starts waiting on you (what waits, on which
  session; never one per feed event, never for what waited before the page opened), and a click on it opens the ask
  (Session's Attention on that row; on the glance, the row). The channels are one table: a second is one entry. Nothing
  for the Signal pack: the owner has not chosen a channel yet.

#### Changed

- **An answer from the attention queue needs the owner proof** (`studio/owner_proof.py`): `POST
  fleet/attention/answer` -- Attention's keys and the glance's buttons -- joined the owner routes, so the launch token
  alone (what a pack's page script could read) is a 403 "this needs the owner's own page" and the card still waits.
  Studio's own page always sent the proof; nothing changes for it.
- Studio's fleet store starts `lite` for the glance (the queue, not the capability catalogs or the missions).

#### Docs

- docs/STUDIO-live.md "The glance" and "The alert", docs/REMOTE.md "The glance from a phone", STUDIO-security.md,
  STUDIO-shell.md, EXTENSION_API.md (the owner routes), COMMANDS-studio.md (`--mode glance`), CONFIG.md
  (`studio.alerts`), ARCHITECTURE-modules.md, the glossary's "glance" (+ twin), the docs map.

### R5: 3.4.0.1 merged in, and what the second two-machine check found

The released 3.4.0.1 is merged into this line (History's rows keep both the tick boxes and Report doors of R2/R3 and
3.4.0.1's "N sessions inside"; Studio's start lines keep the glance's phone line and print at once). A second check of
3.4.0.1 on the PC and the Linux VM (numbering from the first check's 1-29):

#### Fixed

- **2** `halo pack inspect` lists what a pack adds to Halo under `offers:` (CLI verbs, slash commands, doctor rows,
  Studio server modules), as `pack list` counts them; "nothing" when it offers nothing.
- **12** `halo fleet status` on the machine serving the hub prints the firewall line too (and `serving.firewall`).
- **22 / 35** History: a goal run's lead and worker sessions fold under their run whatever folder Studio started in
  (each session's own record names its folder; a worker's is its run's worktree); a mission re-plan keeps every lead
  session (plan.json `lead_sessions` appends), so the first lead is not a row of its own.
- **30** An installed pack older than the one this Halo ships (installed from Halo's own shipped folder) is said in one
  line with `halo pack update <id>` by `halo pack list` (and `--json` `ships`), `halo pack inspect`, `halo pack
  doctor`, `halo doctor`, Studio's Packs ("1.0.2 available") and at the end of `halo update`. `halo pack install <id>`
  of an installed pack: the same version says "already installed: nothing to do" and exits 0; another version says so
  with the update command (exit 1). The fleet pack is 1.0.2.
- **31** The firewall line resolved only the venv launcher: uv's `cpython-3.12-...` is a junction to
  `cpython-3.12.13-...`, where Windows Firewall recorded the PC's two Block rules, so Halo said "no rule" and gave only
  the allow command. Both the launcher and the interpreter are resolved, a rule's program is compared as written and
  resolved; a Block rule is said first with the command that removes it, then the allow line.
- **32** A mission part on a harness in permission mode `default` failed even when it only wrote its own output. Its
  own outputs folder (`artifacts/<n>/` of the mission folder) needs no ask (checked against `..`, `\\?\` / `\\.\` /
  UNC spellings, NTFS streams and links out); any other call the mode asks about waits as a card in that machine's
  Attention (Studio, the TUI, the glance) instead of being refused, the hub shows the part "waiting on you (on
  <machine>): <what>", and nobody answering within `fleet.mission.ask_wait_min` (default 30) ends it "not done: nobody
  answered ...". The plan's note says so. Nothing else is allowed by Halo.
- **33** Live's sentence on the fleet scope counted a member's session twice ($0.015 for a $0.0075 session): the spend
  is the agents', not their session and machine boxes again.
- **34** report.md's cost per harness reads "(1 part, #2; 0 done, 1 not)", not "(parts 2; ...)".
- **36** Right after `halo fleet join`, before any session there, the plan and `halo fleet who` say "<member> joined
  but has not sent its card yet (it goes with the first halo session there)" instead of "nobody in the fleet has gpu".
- **37** A long hand-back reason is quoted whole when it fits, else cut at a word with "...".
- Costs: a failed call (a 429, a 5xx) spent nothing and no longer marks the harness's today unknown (`$x+`) while the
  report card called the same session whole; one finished session with a sub-agent tells one number in the report
  card, Compare, the replay, History, the harness's today and the caps. Per-project caps count finished sessions too
  (`cost_today_projects`, from each session's record by its project).
- Tests: tests/helpers/studio_ollama.py reads config.json again for a moment when Windows denies the read while the
  server replaces it (Windows run 43173639949).

#### Docs

- docs/FLEET.md (the recipe's step 1 on a used machine, a mission part in `default` mode, the firewall junction, `halo
  fleet status`, Caps), PACKS.md (installing an installed pack, an older shipped pack), CONFIG.md
  (`fleet.mission.ask_wait_min`), ARCHITECTURE-modules.md, plans/HANDOFF.md.

### R6: what the CI runners found

The candidate passed on the Windows PC and was red on both GitHub runners; each cause below, found and pinned.

#### Fixed

- **Export a clip without Pillow.** Saying what a clip will write (the dialog, `GET replays/<id>/clip`, `halo replay
  clip --dry-run`) no longer needs Pillow: the plan answers with its frames, width, path and cap, plus `pillow` /
  `needs`; without Pillow the dialog says in one line what to install and Export is off, the CLI prints the same line
  and the clip itself exits 2, before anything is written (only the encode needs Pillow, `replay_clip.encoder()`). The
  plan answered 422 where Pillow was missing. The dialog also keeps only the newest plan: the speed moving as the saved
  file opened and a From typed just after sent two asks, and the older answering last left a plan (and an Export) of a
  range the fields no longer said.
- **A hover card no longer opens by itself on load.** A box drawn under a pointer that has not moved (Cast's lineup
  opening under the "Open auto" button just clicked) got the browser's enter with no move, and its card opened; the
  rest now starts on the pointer's first move on the box (`lib/hover/useHover.ts`). Seen on Linux, where the fonts put
  a card under that pointer.
- **Studio serves again on its own port right after it stopped (Linux).** A connection it closed sits in TIME_WAIT on
  the port for a minute and the bind failed ("Address already in use"): Studio sets SO_REUSEADDR on POSIX, where it
  never lets two listeners share a port, and keeps SO_EXCLUSIVEADDRUSE on Windows.
- **A slow `tasklist` no longer deletes a live session (Windows).** The session registry's liveness check spawned
  `tasklist` with a 5 s timeout; one slower answer read a live session as dead and `list_live` pruned its row for good,
  so Studio lost the session (Session's mode word never moved again). It now asks the process itself
  (OpenProcess + GetExitCodeProcess), and this process's own rows at once.
- CI installs Pillow (`requirements-ci.in`, hash-locked in `requirements-ci.lock`), so both runners encode a clip; the
  no-Pillow path is tested on every box by hiding Pillow (`tests/helpers/no_pillow.py`).
- **Session's mode word follows the registry whatever order things land in.** GET fleet answered a snapshot from
  before the registry moved (its 1 s cache was dropped only by a session frame, and the mode can move before the
  session's feed reaches Studio): the registry file is part of the cache's key now (`peers/local_view.py`). On the page
  (`routes/fleet/modeOrder.ts`), a status frame older than one already applied never puts its mode back, and an answer
  asked before the newest status frame landed keeps that frame's mode; one asked after it wins.
- `tools/studio_modes_banner.py --check` asks for the same size and the same pixels within 16 levels on at most 0.1 %
  of them (`matches`): Pillow 13.0 draws the labels 42 pixels apart from 10.2 (4 levels at most), and the byte
  comparison called the banner stale on CI once CI had Pillow; another capture or another tile order is still stale.
- Tests: a node test that runs a `.ts` module skips on a node built without TypeScript (Debian's).
- Tests: a "nothing opens on load" check names the card that opened, where the pointer rests and the box under it; the
  mode word's driver says the page's word and the registry's rows when it times out; `tests/test_studio_rebind.py`,
  `tests/test_replay_clip_pillow.py`, `tests/test_studio_mode_order.py`, `tests/test_studio_modes_banner_check.py`; the
  registry's slow-`tasklist` pin; the report card's mode step holds the session's feed until the page has read its word.

#### Docs

- docs/REPLAY.md (a clip's plan needs no Pillow).

## [3.4.0.1] - 2026-11-12

What a real two-machine run found: a blocked part no longer counts as done, costs count finished sessions, the hub says
when the firewall is in the way. A tester ran 3.4.0.0 on the Windows PC and the Linux VM, paired through the fleet pack,
with a mission split across both, and wrote 29 defects; each line below names the one it fixes (the fleet pack is 1.0.1).

- 15: a mission part is `done` only when its work is: the brief asks the worker to end its hand-back with `Outcome: done`
  or `Outcome: blocked -- <why>`, and a part whose hand-back says it is blocked, or whose named outputs are not in the
  mission folder, ends `failed` with the reason (the worker decides before it writes `result.json`; the hub checks a
  member's `done` again). The mission ends "N of M part(s) did not finish: ..." (fleet/mission_outcome.py).
- 4: `halo recall --fleet` and `/recall --fleet` run with the fleet pack on (they asked the pack for a module that
  stayed in core); a pack module that does not import says its real error instead of "install the pack".
- 10, 17, 26: one source of truth for a session's cost, its record (live/session_cost.py): a harness's "today" counts
  its finished sessions too, on the hub's own machine and on a member (its announce carries its `cost_today`), so the
  fleet caps and Studio's machine boxes see mission and goal-run spend; a call Halo could not price stays unknown
  (`$x+`), never $0. History's session costs read the same.
- 21: a goal run whose split failed counts its lead's calls (split.json keeps them).
- 18: a mission part's hand-back pushed to the hub has its full local paths cut (home -> `~`, a path -> its last part).
- 1: `halo studio --no-open` with its output redirected writes its URL lines at once.
- 12: Halo never opens Windows Firewall, and now says when it is in the way: a hub (and `halo host serve`) on Windows
  reads the inbound rules (no elevation) and prints one line with the command an administrator runs (remove the
  `python.exe` Block rules Windows made from a declined prompt, then allow the port); `halo doctor`, Setup -> Machines
  and `halo fleet serve` say the same; a join that times out says "the hub did not answer on <host>:<port>: on Windows
  the firewall is the usual cause; on the hub run `halo doctor`" (peers/firewall.py; FLEET.md "Windows Firewall").
- 13: opening Studio loads and calls no model: the Ollama steward's job started with Studio or the hub reads the logs
  and runs the rules; its note and a new model's probe run only under `halo ollama steward --watch` or the new
  `ollama.steward.watch: true`.
- 14: a plan that needs what only an away member has names it ("X has gpu but is offline (no halo session open
  there): open one, then plan again"); `halo fleet join` says a member is online only while a halo session runs there.
- 16: each capability card carries the permission mode a mission part runs in; a part placed where calls that ask are
  refused gets a note in the plan with what lets them through.
- 27: `halo fleet leave` after a kick says "it had already removed this harness".
- 11: `halo fleet status` names a joined hub by the hub's name, not this harness's.
- 19: a capability card from an older read, or made by another Halo version, shows "(refreshing ...)" and is
  gathered again.
- 7: the fleet pack has a `halo doctor` row: whether it runs, the hub here (and the firewall in its way), each joined
  hub and whether it answers.
- 2: `halo pack install` / `list` count a pack's CLI verbs, slash commands, doctor rows and Studio server modules (the
  fleet pack "offered nothing"); an empty `halo pack list` points at `--available`.
- 3: with the fleet pack installed but off, its verbs say "the fleet pack is installed but off: halo pack enable fleet
  --grant-all" (not "install it").
- 5, 6: `halo studio --help` names the fleet pack for `--fleet` and `--mode fleet`; `halo pack --help` lists `cli:<verb>`
  among the grants.
- 8, 9: Studio's words name the Mission panel on Agents -> Live and Live's inspector, not the Runs view that went.
- 20: `halo orchestra new` with no `--file` says a run cannot split without the goal's files; such a run stops before
  the lead is asked.
- 22: History folds a goal run's and a mission's own sessions under their row ("3 sessions inside").
- 23, 24, 25: the Mission report counts parts per harness ("1 (#2)"), keeps its total whole, and says "nothing to
  merge (files parts only)".
- 28, 29: with the fleet pack off, Setup's line names no machines, and `?mode=fleet` / `halo studio --mode fleet` say
  the pack's line instead of pointing at Setup -> Machines.
- Tests: `test_studio_local_hf` (two servers: the driver's fallback click started a second one after a first start had
  answered; it now waits for Start's answer and checks one server started) and `test_bundle_reserve` (one route call
  timing out under load marked the host down for 30 s, so every read after it had no card; the readiness wait clears
  the mark its own probe set).

## [3.4.0.0] - 2026-11-11

**Halo is defined by its core, everything else ships as a pack, and Agents opens on the living canvas.** The core is what it was built around: the agent loop and its tools, permissions and
policy, the providers in use here (OpenRouter, Databricks, Anthropic, OpenAI-compatible, Ollama, Hugging Face and the
local servers), all the local-model work, lineups and blocks, Studio's Session, Agents, Local, Packs, Setup and
Settings, and the pack system. Experimental features that mask that core leave it, as packs where that is cheap and
as plain removals where nothing is left to pack; the measure is lines and files after versus before.

### A: Typesafe leaves the core

TypeSafe was a key-only placeholder: it stored `TYPESAFE_API_KEY`, had no `ts:` route, no adapter and no models, and
the usage audit found no call. With nothing to move, it is removed rather than packed.

#### Removed

- The `typesafe` provider: its entry in `PROVIDER_NAMES`, `LABELS` and `PREFIXES` and its `credentials_present` /
  `credentials_source` branches (`providers/enablement.py`); the "not probed (stores a key only)" reachability branch
  (`providers/reachability.py`); its `_model_count` and `halo providers setup typesafe` branches (`providers_cli.py`).
  Replaced by nothing: `halo providers`, `/providers`, `halo balances` / `/balances` and `halo doctor`'s enabled count
  list six providers.
- The TypeSafe tab of `halo init` and the init wizard (`init_providers.py`: `TAB_PROVIDERS`, `TAB_LABEL`, the
  `tab_credential_state` branch, `_TAB_KEY_ENV`; the tab help in `tui/dialogs/init_tabs.py` and `init_wizard.py`) and
  Studio Setup's TypeSafe card (`studio/setup_providers_state.py`: `KEY_FIELDS` and the `_secret` branch).
- `halo bugreport`'s TypeSafe line (`bugreport.py`).
- `TYPESAFE_API_KEY` from `redact.py`'s named list (the generic `*_API_KEY` rule still redacts it).
- Verbs: `halo providers enable | disable | setup typesafe` and `/providers enable | disable typesafe` (each now says
  the one line below). Keys: `TYPESAFE_API_KEY` (env file, shell, settings env block) and `providers.typesafe` in
  config.json, both ignored. Files: none was TypeSafe's own. halo_harness/ outside templates/: 2003 files and 328,429
  lines before, 2004 files and 328,465 lines after (99 lines out of 17 core files; 65 lines in for
  `providers/left_core.py`, the module that says what left).

#### Added

- `providers/left_core.py`: what left the core and the one line each leftover gets, never an error -- a `ts:` ref
  (a `--model`, `/model`, a remembered model, a lineup card or a Studio card: "no route: 'ts:...' (ts: typesafe
  (TypeSafe) left the core in 3.4.0.0: ...)"), a leftover `TYPESAFE_API_KEY` or `providers.typesafe` row (one
  `[WARN]` row in `halo doctor`, one line under `halo providers`), `halo providers enable typesafe` (the line, exit 1;
  `disable`, exit 0). The `cc:` / `cx:` line of 3.1.5.0 moved there with its words unchanged. A leftover key stays
  stripped from tool children (`providers/config.py`): it is a secret wherever it came from.
- `tests/test_providers_left_core.py` pins each leftover line and that nothing is said when nothing is left over.

#### Docs

- COMMANDS-providers.md, COMMANDS-health.md, SLASH-COMMANDS-providers.md, MODELS-references.md (the prefix table),
  STUDIO-setup.md, HANDBOOK.md, MODELS-openai-codex.md and the glossary's "provider" no longer list TypeSafe and say
  where a leftover is named; `docs/screenshots/balances.svg` is re-rendered by `scripts/screenshots.py` (six
  providers). MODELS-experiential.md keeps `or:typesafe/jev-router` (an OpenRouter model) and the
  research notes under docs/harness/ stay as history.

### B: the experiments leave the core

The owner (2026-11-10): "being able to define what halo harness is makes it stronger. All these experimental features
can be packs." This block is F4 and F7 of the Focus plan (plans/ROADMAP.md); what it moved and removed is below, each
with what replaces it. A leftover of a removed feature is ignored, never an error.

#### Removed

- **The team file and `halo team`** (3.0.8.0; removed, not packed: Team's board left Studio in 3.3.16.0 and nothing
  used the file). `halo team ...` now answers one line: the team file left in 3.4.0.0, a lineup's tiers and blocks
  (Agents -> Cast, `halo teams`) and a run's lanes with their owns lines (Agents -> Runs, `halo orchestra`) do its job.
  LINEUPS are untouched: `halo teams`, `teams_yaml.py`, `~/.halo/teams/*.yaml`, a lineup's tiers, routing, budget and
  pipeline, and `team_config.py` (the Databricks `team.json` preset, which is not the team file). Gone:
  - modules `halo_harness/team/` (spec, validate, validate_stages, resolve, blocks, board, stages, gate_actions,
    triggers, run, run_stage, parallel, remote_stage, budget, guard, delegate, adapters, cli, cli_run),
    `studio/team_api.py`, `studio/team_live.py`, `studio/team_budget_api.py`, `fleet/team_attention.py`,
    `work/adapters/stage.py`, `orchestra/coach_team_rules.py`, `templates/team/team.yaml` (the team template);
    kept by moving: `team/adapters.orchestra_run` -> `orchestra/to_report.py` (the supervisor's and a fleet mission
    part's), `team/delegate.FleetDelegate` -> `fleet/delegate.py` (the two-machine check's mission step; its
    `send_run` went with the team stage), `member_bio` -> `supervise/runner.main_bio`;
  - verbs `halo team init|validate|run|status|board|answer|stop|log|blocks|coach`; the routes `/api/team/*` (410
    since 3.3.16.0), `/api/team/coach`, `/api/work/team/*` and `/api/work/stage/*`;
  - the Attention kinds `team_gate` and `team_budget`; the work record's unit kind `stage` and run kind `team`
    (`halo work` reads lanes, mission parts and supervisor goals); the session's team claim guard (`HALO_TEAM_SCOPE`);
  - `halo config where`'s "Team file" group and `halo doctor --config`'s team-file rows; the schema kind `team`;
  - the two-machine check's `team` step (`tools/live_fleet_check.py`: who, mission, recall);
  - the glossary words team, member and stage (block now means the lineup's block on Agents -> Cast); completion's
    `team`; docs/TEAM.md (removed from docs/README.md and the README's table; every page that linked it says where its
    job went);
  - tests `test_team_blocks`, `test_team_budget`, `test_team_cli`, `test_team_delegate_runs`, `test_team_parallel`,
    `test_team_run`, `test_team_spec`, `test_studio_team`, `tests/helpers/team_rig.py`, `coach_seed.team_run`.
- **The guided first run left the core for the shipped `first-run` pack** (3.1.1.0; off unless enabled):
  - modules `halo_harness/start/` (engine, steps, steps_run, steps_setup, card, lineup, sample_repo, fake, fresh,
    screen, errors, auto_gate), `start_cli.py`, `studio/start_api.py`, `studio/start_job.py` -> the pack's
    `first_run/`, `cli/start.py`, `server/start_api.py`, `server/start_job.py` (+ `server/routes.py`);
    `tui/dialogs/start_panel.py` (the TUI's `/start` panel) removed: the pack's `/start` shows the card and how to run
    it; the core checks stay core as `halo_harness/checks/` (`start/checks.py` -> `checks/catalog.py`,
    `checks_run.py` -> `checks/run.py`, `checks_pack.py` -> `checks/pack.py`, `checks_steward.py` ->
    `checks/steward.py`, `provider.py` -> `checks/provider.py`), and the sample's knowledge tag stays core
    (`knowledge/rank.sample_root`);
  - `halo start` and `/start` are the pack's (`contributes.cli`, `.slash`); with the pack off each is one line: "the
    guided first run is a pack now: halo pack install first-run, then halo pack enable first-run --grant-all";
  - the core check `start` (Setup's Check row, `halo check --start`, the wizard Summary's row) -> the pack's Setup
    block `run` (`pack:first-run:run`); `halo check --start` says the one line; `halo init` no longer offers the run;
  - Studio's "Start here" overlay (`shell/StartHere.tsx`, `lib/start.ts`), Agents -> Runs' "Test this lineup"
    (`routes/agents/runs/TestLineup.tsx`), the Setup Check row's card and Summary's Run, the palette's "Start: the
    guided first run" and the route `/api/start` -> the pack's **First run** panel in the Agents section
    (`studio/first-run.js`) over its routes `/api/packs/first-run/start/...`;
  - `tools/capture_start.py` (`capture_studio.py --mode start`; what it kept is `tools/capture_fresh.py`); tests `test_start_cli`, `test_start_cli_errors`, `test_start_studio_api` (moved:
    `test_pack_first_run_cli`, `test_pack_first_run_errors`, `test_pack_first_run_routes`, run against the pack),
    `test_start_checks` (-> `test_checks_catalog`), `test_start_tui` (-> `test_explain_tui`, the panel's tests went),
    `test_studio_start`'s Start-here run, `test_studio_modes`'s `--mode start`, `test_studio_quiet`'s Start-here
    test, and `test_setup_state_no_probe`'s / `test_setup_api`'s card checks.

#### Added

- **The `first-run` pack** (`halo_harness/templates/packs/first-run/`): `halo start`, `/start`, the Setup check row and
  the First run panel; `halo pack test first-run` passes it.
- **Seams, draft for extension API 1.3** (docs/EXTENSION_API.md "CLI verbs, slash commands, doctor rows and settings
  rows", "Core access"): `contributes.cli: [{verb, module, help}]` (`main(argv) -> int`, grant `cli:<verb>`,
  `packs/contrib_cli.py`), `contributes.slash: [{name, module, help}]` (`run(args_text, facade) -> str`, grant
  `cli:<name>`, `packs/contrib_slash.py`), `contributes.doctor: [{id, module, help}]` (`rows(ctx) -> list`, grant
  `doctor`, `packs/contrib_doctor.py`), `contributes.settings: [{key, title, help, type, default}]`
  (`packs.settings.<id>.<key>`, no grant, `packs/contrib_settings.py`), their manifest rules (`packs/contrib_lines.py`)
  and `halo_harness.ext.core` (`core.module(name)`, `core.get(name, attr)` over `core.REACHABLE`); `halo_harness/left.py`
  (the one line a verb that left the core says).

#### Docs

- docs/TEAM.md removed; COMMANDS-init, HANDBOOK, STUDIO-shell, STUDIO-setup, STUDIO-agents, SLASH-COMMANDS-tui,
  TROUBLESHOOTING, PACKS ("The first-run pack"), EXTENSION_API, ARCHITECTURE-modules(-two), GLOSSARY, WORK, MISSIONS,
  ORCHESTRA, ROLES, AGENTS and README say what left and where it went.

### B2: the coach is a pack; the wizard is a console fallback

The coach (its cards, probes, the improvement library and `/improve`) is the shipped `coach` pack, off unless you
enable it; the supervisor, replanning and verified outcomes stay core. The terminal wizard's screens are gone: Setup is
Studio's, and `halo init --terminal` (or no browser) is a plain console setup of the essentials. The pack contributions
`contributes.doctor` and `contributes.settings` are wired in, and the extension API is 1.3.

#### Removed

- The coach's modules, moved into `halo_harness/templates/packs/coach/` (the pack replaces them): `orchestra/coach.py`,
  `coach_apply.py`, `coach_ask.py`, `coach_citations.py`, `coach_compare.py`, `coach_compose.py`, `coach_experience.py`,
  `coach_library.py`, `coach_library_share.py`, `coach_mission_rules.py`, `coach_orchestra_rules.py`, `coach_probe.py`,
  `coach_probe_card.py`, `coach_probe_prompt.py`, `coach_probe_schema.py`, `coach_record.py`, `coach_rules.py`,
  `probe_overlay.py`, `probe_runs.py` (-> engine/); `coach_cli.py`, `coach_library_cli.py`, `improve_cli.py` (-> cli/);
  `improve/` (`__init__`, `apply`, `config`, `dismissed`, `draft`, `evidence` -> improve/); `studio/coach_api.py`,
  `studio/coach_probe_job.py` (-> server/); `knowledge/writers.applied` (-> engine/knowledge_applied.py).
- `improve/hint.py` and the once-a-session `/improve` hint (agent/loop.py `_maybe_yield_improve_hint`): no pack seam
  for a session notification; the coach pack's doctor row says what `/improve` uses.
- The TUI's `/improve` card review (tui/slash.py `_handle_improve` and its workers, tui/widgets/cards.py
  `ImproveCard`): the pack's `/improve` prints what `halo improve` prints.
- CLI verbs and slash commands from the core: `halo coach`, `halo improve`, `/coach`, `/improve` (the pack's now; one
  line each with it off, halo_harness/left.py); `halo orchestra coach` and `halo fleet mission coach` hand over to the
  pack's verb.
- Config keys `coach.probe.k`, `coach.probe.budget_factor`, `coach.library.cite`, `improve.enabled`, `improve.hint`,
  `improve.model`, `improve.since_days`, `improve.max_candidates`, `improve.hint_threshold.repairs`,
  `.edit_failures`, `.loop_breaker`, and the config sections `coach` / `improve`: ignored with one line (`halo doctor
  --config`; `halo config set` names the pack's key). The pack's seven rows are `packs.settings.coach.<key>`.
- Settings rows: those eleven, and the group "Coach and improve" (-> Settings -> From packs while the pack is on).
- Doctor row `improve` (the `/improve` config line) (-> the coach pack's doctor row).
- The coach's lines in the core: the Orchestra report's `coach:` line (`orchestra/report.coach_line`), the mission
  report's, and `halo fleet digest`'s coach rows (its `coach` list stays, empty).
- Studio: the run report's Coach tab (`routes/orchestra/Coach.tsx`, `coachApply.ts`), the mission's Coach face
  (`routes/fleet/MissionCoach.tsx`), the bio form's coach note (`routes/roles/CoachNote.tsx`, `coachHint`), the plan
  canvas's coach staging (`plan/stage.ts stagePlan`), `lib/coach/` (CoachCards, ConfirmCard, LibraryFold, ProbeBar,
  actions, probe, store, types) and `styles/coach.css`; the routes `/api/orchestra/<run>/coach`,
  `/api/fleet/missions/<id>/coach`, `/api/coach/library/...` (-> the pack's Coach panel in Agents and
  `/api/packs/coach/coach/...`).
- The terminal wizard (Setup is Studio's; the console setup below replaces the terminal path):
  `tui/dialogs/init_wizard.py`, `init_tabs.py`, `team_step.py`, `team_step_actions.py`, `summary_checks.py`,
  `check_rows.py`, `step_rail.py`, `setup_mode.py`, `init_picker.py` (the arrow-key pickers), `ollama_found.py`,
  `ollama_calibrate_offer.py`; `wizard_ux.py` keeps only the footer caption `/agents` uses; init_cli's
  `_run_init_wizard_flow`, `_run_init_tabs`, `_launch_after_wizard`. `/agents` and `/teams` (their list and view
  screens) stay.
- `halo setup --terminal` and `/setup --terminal`'s screens (-> the console way, one line per page).
- Captures: `docs/media/studio-orchestra-coach.png` (tools/capture_orchestra.py `coach_capture`) and the TUI gallery's
  `team-step` scene (`docs/screenshots/team-step.svg`, scripts/screenshots.py, its tests/test_screenshots pin).
- Tests: tests/test_improve_hint.py; the Chrome coach checks (tests/helpers/studio_coach.py, studio_ui_coach.py,
  studio_coach_rig.py); test_h15_init_tabs, test_init_wizard_round7, test_ollama_discover_wizard,
  test_ollama_tune_wizard, test_round2b_wizard_roles_fixes, test_round2c_wizard_ux, test_round_wizard_deep_review,
  test_wizard_team_switch_sync; the wizard tests in test_review3_f2 (1), test_review3_t2 (3),
  test_agents_teams_forms (2), test_explain_tui (1), test_hotfix_101_fix_init_preserve (3), test_auto_lineup (1),
  test_setup_api (1), test_wizard_agents_bios (2), test_wizard_lineup (1), test_wizard_studio_doors (1); test_tui.py's
  20 wizard and init-picker pilots and 3 ImproveCard / `/improve` pilots.

#### Added

- The shipped `coach` pack (`halo pack install coach`, `halo pack enable coach --grant-all`): `halo coach`, `halo
  improve`, `/coach`, `/improve`, a Coach panel in Studio's Agents section (a finished run's cards, Ask, Apply after
  its confirm card, Undo, Probe), seven Settings rows under From packs, one doctor row; `halo pack test coach` passes.
- `contributes.settings` wired: an enabled pack's rows in Studio's Settings (group "From packs", shown only while a
  pack has rows) and in `halo config get` (the default while unset) / `set` (its type checked, one line, exit 2).
- `contributes.doctor` wired: an enabled, granted pack's rows last in `halo doctor` (`From packs, <id>: ...`).
- Doctor rows for both shipped packs: first-run (ready to rehearse your lineup, or the provider / lineup missing) and
  coach (what it keeps and uses, or the Studio grants its panel waits for).
- The console setup: `halo init --terminal` and the no-browser fallback ask a provider (numbered) and its key (by NAME
  in the env file), the default model (a short numbered list, or a typed ref), the permission mode and whether to run
  doctor, then name where the rest is (Studio's Setup, its address and port-forward line when one runs).
- `halo setup <page>` and `/setup <page>` for every Setup page (providers, local, model, permissions, theme, team,
  linux, check, machines); `--terminal` or no browser prints the console way (setup_cli.CONSOLE); `halo init --step
  <page>` is the same.
- halo_harness/legacy_roles.py: a role table from before lineups becomes the lineup `migrated` once, at an interactive
  session start and in `halo init`'s console setup (the wizard's lineup step did it until now).
- Extension API 1.3 (`ext.compat.CHANGES["1.3"]`): `contributes.cli`, `.slash`, `.doctor`, `.settings` and `ext.core`,
  all draft; the first-run and coach packs say `halo_api: {min: "1.3"}`.
- Tests: test_pack_coach, test_packs_contrib_wired (fixture pack tests/fixtures/packs/contrib-rows), test_init_console,
  tests/helpers/coach_pack.py (the moved coach tests run against the pack's modules); test_invariants'
  `invariant_k` (no core module imports a shipped pack).

#### Changed

- `orchestra/coach_prices.py` -> `orchestra/prices.py` (+ `money`, `row_line`) and `orchestra/coach_lane_facts.py` ->
  `orchestra/lane_facts.py`: the forecast, the outcomes records and the supervisor's replan prompt read them; they stay
  core. `outcomes/records.path` keeps `<state>/coach/outcomes.jsonl`.
- `ext.core.REACHABLE` adds the coach pack's door (the run folders, the writers, the probe's Orchestra runs, the fleet's
  mission folders, /improve's session; outcomes through `outcomes.records` only) and drops `orchestra.coach`.
- The guided first run's step 6 runs the coach pack's `halo coach <run> --json` while that pack is enabled, else one
  line that the coach is a pack.
- The fleet's `coach_library` command answers through the coach pack (`packs/contrib_cli.pack_call`), else one line.
- Studio's Coach panel writes a card's change after its own confirm card; it no longer opens the bio form or the plan
  canvas with the change staged.
- `halo init`'s console prompts read stdin with `--terminal` even without a terminal (scripts can drive it).

#### Docs

- EXTENSION_API (1.3, the four contributions draft with their exact shapes and grants, "Changes in 1.x"), PACKS ("The
  coach pack"), CONFIG (the From packs note; the coach rows out), COMMANDS-init (the console setup), COMMANDS-studio,
  COMMANDS-sessions, COMMANDS-health, COMMANDS-fleet, SLASH-COMMANDS(-tui, -keys), ORCHESTRA and STUDIO-orchestra (the
  coach is a pack), STUDIO-setup, WIZARD (a note: the screens left, the rules stay Studio's), GLOSSARY,
  ARCHITECTURE-modules, README (Features and Documentation name the coach pack; no wizard).

### C: Fleet leaves the core

The owner (2026-11-10): "Fleet doesn't really fit anymore ... it can be a pack." Halo's core is see, shape, mix, local,
start; several halos joined to one hub serve none of them directly, so the fleet is ONE shipped pack now, `fleet`, off
by default: `halo pack install fleet`, then `halo pack enable fleet --grant-all`, and it works as it did.

#### Removed from core (now in the shipped `fleet` pack: `halo pack enable fleet`)

- **Verbs**: `halo fleet` (the live table, `serve`, `pair`, `join`, `leave`, `status`, `members`, `kick`, `record`,
  `digest`, `capabilities`, `who`, `mission ...`) and `halo mission ...` (new: the same as `halo fleet mission ...`);
  `/fleet` (the table as text; the TUI's live table dialog is gone, `halo fleet` in a terminal is the live table) and
  `/mission`; `halo studio --fleet`; `halo recall --fleet`, `/recall --fleet` and `halo knowledge fetch` (they ask the
  fleet). With the pack off each says one line: what it is and `halo pack install fleet, then halo pack enable fleet
  --grant-all`.
- **Studio doors**: Agents -> Live's **this halo | fleet** switch and the fleet scope (the machines, their sessions and
  agents, a mission's parts), the palette's fleet lines (who can..., the machines' specs, missions, pair, kick, while
  you were away), Setup's **Machines** page (pairing, sharing, the people), the rail's "while you were away" dot, and
  the routes behind them (`fleet/hub`, `fleet/pair`, `fleet/settings`, `fleet/kick`, `fleet/commands/<id>`, a member's
  commands, `fleet/health`, `fleet/digest`, `fleet/capabilities`, `fleet/who`, `fleet/missions...`, `fleet/recall`).
  `GET fleet` says `fleet_pack: true | false`; the UI shows a Fleet door only on true.
- **Config keys** (Settings -> Fleet, shown only while the pack runs; `halo config set` still takes them):
  `fleet.share`, `fleet.allow_answers`, `fleet.share_captures`, `fleet.hub.port`, `fleet.tags`,
  `fleet.capabilities.hide`, `fleet.ollama.share`, `fleet.recall.share`, `fleet.recall.hide`, `fleet.shared_dir`,
  `fleet.mission.prefer`, `fleet.mission.max_parallel`, `fleet.mission.max_file_mb`.
- **Python**: the hub (hub*.py), the relay of a joined halo (relay_hub, relay_runtime), missions (mission*.py), the
  capability catalog and who (capabilities*.py but the host's hardware), control from a hub, delegate, digest, health,
  the table, the live check, the CLI (cli*.py), knowledge across the fleet (knowledge/share.py) and what packs bring to
  the catalog (packs/fleet_registry.py, fleet_share.py) are the pack's fleet/; Studio's pair, capabilities, mission and
  hub routes and its health + digest its server/.
- With the pack off a pack workflow's capability `requires` are not checked (the catalog that checks them is the
  pack's); a `contributes.fleet` pack shows no fleet rows in the Pack Manager.

#### Stays in the core (moved out of halo_harness/fleet/, which is gone)

- **halo_harness/peers/**: everything one machine needs to reach another's models, so `halo host serve`, the pool,
  Local -> Hosts and Ollama on the network work with the pack off: identity, fleet.json and the pair keys (store), the
  signed wire (protocol), TLS, pairing codes and the key exchange (pairing, pair_kex, hub_join), the relay client
  (relay, relay_stream), hosts (hub_hosts, hub_host_cmd), Ollama on the network (ollama_share*, control_models,
  control_pulls, control_probes), this harness's own sessions (local_view, agent_tokens), the host's hardware
  (capabilities_host), the capability cache (catalog.py, new) and `lan_address` / `FleetOffline` / `parse_ttl` (net.py,
  new).
- **halo_harness/live/**: this machine's sessions live: thinking and talk on the feed (think, talk), the attention
  queue and its sources, one session's timeline and flight recording (history, recording), the file-conflict edges, the
  spend caps, the decision journal, push to the phone and hand-offs. Session, Agents -> Live, the attention chip and the
  replay read `fleet/*` routes that the core still answers for this harness (studio/fleet_view_api.py, new: the core's
  half; the pack answers every `fleet/*` route while it runs).
- `halo_harness/recall_fleet.py` (Studio's recall box reads its local half), the work record's mission adapter
  (work/adapters/part.py reads mission.json itself), `fleet.enabled`, `fleet.name`, `fleet.private`,
  `fleet.allow_control` (the host's grants), `fleet.caps.*` and `fleet.attention.signal` (now under Settings -> Remote).

#### Migration

A halo that had a fleet (a joined hub in fleet.json, a hub's members, missions, or fleet keys only the pack reads in
config.json) gets the shipped pack installed and enabled on its first run after the update, with one line that says so
(packs/fleet_migrate.py; the marker `<state>/packs/.fleet-migrated` keeps it from asking again). Nothing is deleted.

#### Seams

No manifest key is new: the pack uses `contributes.cli` / `.slash` (3.4.0.0 B). The core reaches the pack only through
`halo_harness/packs/fleet_door.py` (`module(rel)`, `call(rel, attr, ...)`: None while the pack does not run here);
`halo_harness.ext.core` lists the core modules the pack drives and adds `core.version()`. Tests run the pack in every
scratch home with `PACKS_TEST_SHIPPED=fleet` (packs/registry.py, honoured only under BRIDGE_TEST_HOME;
tests/helpers/fleet_pack.py sets it and serves the moved modules under their old names).

#### Not done here

- Studio's fleet UI (routes/fleet/*, the Live fleet scope) is still compiled into the core bundle, gated on
  `fleet_pack`: a React section has no pack seam yet (a pack's Studio panel is plain DOM).
- Federation R1's contracts (branch v3318/R1-contracts, its work record included) are left unmerged.

#### With B2 (the coach pack)

- A pack never imports another pack. The coach pack reaches missions and the hub through the core door
  `packs.fleet_door` (in `ext.core.REACHABLE`): with the fleet pack off, `halo fleet mission coach` / `halo coach
  mission` say the fleet pack's one line, Studio's `fleet/missions/<id>/coach` finds no mission, and `halo coach
  library fetch` says the fleet's hub is the fleet pack's. The fleet pack reaches the coach through
  `packs.contrib_cli` (`dispatch` for `halo fleet mission coach`, `pack_call` for the `coach_library` command): with
  the coach pack off, one line naming the coach pack. `ext.core.REACHABLE` lists no `fleet.*` module (they are
  `peers.*`, `live.*` or the fleet pack's now).

### D: a goal run is a job on Live and in History (Orchestra's Runs view and Start screen go)

The owner (2026-11-10): "I always see unused older versions of orchestrations ... I'd love to see what is actually
happening." Orchestra's engine is core and unchanged (worktrees, merge, the test gate, the supervisor, outcomes,
replanning; the `code` block, `halo orchestra` and `halo supervise` run on it). What went is the separate place to look
at it: one place shows what runs now (Agents -> Live), one shows what ran (History, on Live's bar).

- **Agents has Cast, Live and Workflows** (`C`, `L`, `W`). `R` and every door that named Runs land on Live (once in a
  browser: "Runs is gone: a goal runs on Live (Run a goal on its bar); a finished run is in History"); a door that names
  a run (`?mode=agents&run=<id>`, an attention row's `o`, the palette) opens it on Live while it runs, else its report.
- **A running goal run is a job on Live**: its lead, its lanes in the run's block under it (a group box of kind `run`;
  with the plan under it on, the block "goal run: <goal>"), each lane a box with a row per fact -- state, model, cost,
  what it owns (its claims), its worktree -- and what it waits on: the merge and the gate are steps on the waiting path,
  the sentence under the bar covers the run. A click is Live's inspector, summary first (goal, owns, state, last output,
  cost), then one page each: Plan, Claims (Release, Steal), Diff, Test result, Log; Stop the run (one confirm), Review the
  plan, Steer its worker (the lane's worker in the inspector: Steer, Pause, Stop), Watch in Session. Hover = its card.
- **Run a goal** on Live's bar and in the palette opens the goal form as a panel beside the canvas (what you want, done
  when, the shared files, the gate's test, Review the plan first) that says what it will do, what it may cost and where
  it writes before Run; Run it across the fleet and a pack's workflow are in it. No screen of its own.
- **Review the plan first**: the lead waits on you on Live; Review the plan opens the plan review (the 3.0.9.0 canvas) as
  a Live panel, the canvas folded while it is open; Approve and run closes it.
- **History**: a goal run's row says how it ended, its wall time, its cost and its models (`GET orchestra/runs` rows
  carry `models`, `elapsed_s`, `ended`, `stop_reason`) and opens its report as a page of History -- the plan and its
  lanes, the outcomes, the gate, the merge, the artifacts, a dry run's jobs -- with Copy, Replay and Run it again.

#### Removed (each door and where its job went)

| Door | Its job now |
|---|---|
| Agents -> Runs (the view, `R`, `?view=runs`, `?mode=orchestra`, the palette's **Agents: Runs**) | Agents -> Live (`R` lands there) |
| Runs' Start screen (the goal form, the five steps, past runs, open the workspace anyway) | Live's **Run a goal** panel; past runs: History |
| the Goal panel (the open run's line: state, cost, stop, new run) | the run's lead on Live and its inspector (Stop the run) |
| the Workflow panel (the step graph, the gate diamond) | the run's block on Live, the lead's waits (the merge, the gate) |
| the Run grid panel (the counters, one tile per lane) | the lanes' boxes on Live; the lead's summary (lanes by state) |
| the Lanes panel (the timeline, the hand-off arcs, the owns line, a lane's claims) | each lane's box (OWNS row) and its inspector pages (Plan: after and takes; Claims) |
| the Live file panel (the goal file with each lane's bands) | a lane's **Diff** page (its units: base, then the lane's text) |
| the Report panel and its Artifacts tab | History's report page (the checks, the lanes, the gate, the merge, the artifacts; Copy) |
| the Log panel | a lane's or the lead's **Log** page |
| the Claims panel (Release, Steal) | the **Claims** page (Release, Steal while live) |
| the plan canvas taking the console's place | the **Plan** review panel on Live (from Review the plan) |
| the "+" menu's RUNS group (New run, the runs, the missions) | Run a goal; History; the Mission panel (`M`) |
| Runs' mission rows | a running mission on Live's fleet scope, a finished one in History; its panel on Live |
| the Mission panel on Runs | the Mission panel on Live (`M`, `?mode=fleet&mission=<id>`) |
| J / K over the lanes, F follow the Log | J / K hop Live's agents; a lane's Log page |
| the palette's Orchestra: new run / stop run / open run / focus lane | Agents: Run a goal / stop the run / lane N; History: run <id>; Agents: review the plan |
| compare two runs, retry | none was a Runs control: two reports side by side are two History pages; Run it again on a report is the retry (the goal filled in) |

- Files: `routes/orchestra/` Orchestra.tsx, Start.tsx, OrchRail.tsx, GoalPanel.tsx, WorkflowGraph.tsx, RunGrid.tsx,
  Lanes.tsx, LaneEdges.tsx, LiveFile.tsx, Log.tsx, Claims.tsx, Report.tsx, ReportTabs.tsx, commands.ts and the old
  FeedPanels.tsx (its FeedDot kept as FeedDot.tsx): 1,621 lines; `styles/orchestra-file.css` (143) and every dead rule
  of orchestra.css, orchestra-plan.css, start-view.css, agents.css; the eight panels' help text (help-orchestra.ts keeps
  the plan review's); SECTION_HELP's `orchestra` copy; the pictures `studio-orchestra.png`, `-start.png`, `-plan.png`
  (new: `studio-run-live.png`, `studio-run-report.png`); Runs' tests and drivers rewritten for Live and History.
- Docs: STUDIO-orchestra.md rewritten ("Studio: a goal run on Live and in History"), STUDIO-agents, ORCHESTRA "In
  Studio", the glossary (lane, plan), the README section and every doc that named Agents -> Runs.

#### Also in D

- **The capability checker is core again** (`halo_harness/packs/fleet_registry.py`, `peers/needs.py`,
  `peers/projects.py`, `packs/fleet_rules.hidden`): with the fleet pack off, a pack workflow's capability `requires`
  are checked and a pack declaring capabilities shows its rows (`halo pack inspect`, `halo pack doctor`); the fleet pack
  re-exports them through `ext.core` (REACHABLE + `packs.fleet_registry`, `peers.needs`, `peers.projects`).
- **`scripts/prepush.py`** removes every folder under `halo_harness/` and `tests/` that holds nothing but `__pycache__`
  before the tiers (one line each), and on Windows passes over WSL's `bash` for Git's (one line; no Git bash: the fix,
  exit 2) -- `scripts/prepush_tree.py`.
- `tests/helpers/run_all_support.py`'s cache list names the real modules (`peers.catalog`, the fleet pack's `health`).

### E: the README and the docs intro say what Halo is

- The README is the owner's wording ("Multi-agent. Multi-workflow. Fully visible."), five pillars (See, Shape, Mix,
  Local, Start) with one Studio picture each, Install, and "Everything else is a pack" with the shipped packs; the
  docs map, the HANDBOOK, STUDIO.md and harness/INSTALL.md open the same way, and pyproject and `halo --help` carry the
  short description.
- Pictures: the hero carries the tagline; Cast, Workflows, the model picker, Setup (no Machines step), Local, Packs,
  Settings (its General page: the Fleet page is the fleet pack's) and the six-section banner are re-rendered.

### The living canvas (built as 3.3.18.0, shipped here)

The owner, 2026-11-10: "i feel like agent canvas should be better. i always see like unused older version of
orchestrations that aren't even happening when I look at it. id love to see what is actually happening when i look at
that view." Agents -> Live now shows only what is happening, with the plan under it, what each agent waits on, one
sentence of what goes on, and zoom levels that change what is drawn (docs/STUDIO-live.md).

#### Changed

- **Agents opens on Live**: Alt+2, the rail, `?mode=agents`, `halo studio --mode agents` and a `focus` frame without a
  view land on Live -- what runs now, or one sentence ("Nothing is running. Start a session, or open the last one as a
  replay.") with **Open the plan (Cast)** and **Replay the last session**. Doors that name a view still win (`?view=cast`,
  C / R / L / W, `?mode=roles`, `--edit`). A fresh Studio with nothing saved opens there too (it opened on Cast's Start view).
- **Nothing past is drawn as present**: a finished agent stays ten seconds, a failed one until its **dismiss**, then leaves
  (its group and its session with it); a finish or a failure from before the page loaded is not drawn; Live picks the
  newest session with an agent at work; on the fleet the machines stay and an away member's rows do not count; a mission's
  parts show only while it runs or is planned. A stop counts as an end for the fade (`fleet/sync.ts`).
- **Cast is the plan**: its bar says "the lineup new sessions use: <name>" and, while agents run, "N live -- see Live";
  its cards no longer glow for a failure the page did not see, nor for an away member's last rows.
- **The rail's Agents badge** counts live agents on this harness and online members only.
- Live lays out once per change of the tree's shape and repaints between (a long session's frames never move a box).
- `GET fleet/history?role=main` dates a session by its transcript's first line (st_ctime was the last metadata change on Linux).

#### Added

- **History** on Live's bar (closed on load): past sessions, Orchestra runs and missions, newest first, each with what it
  was, when, how long, its cost and how it ended; a row opens a **replay** (muted, under a "replay -- ended <when>" banner,
  **Back to now**).
- **Plan under it** (Live's bar, `?plan=on|off`; on by default when the session's lineup has tiers or squares): the
  lineup's blocks as the map, each live agent inside its block, "not in the plan" with why; main's lines carry the plan's
  when, the dash only into a block at work.
- **What waits**: each live box says what it waits on (you, an agent, a tool, a model reply, nothing); the **waiting path**
  is a brighter hairline; **the one sentence** under the bar (`live-narration`) says what goes on now -- what waits on you
  first, the agents by block and what they do, what the session waits on, the models, the spend -- and a click centres the
  agent it waits on; a line's label shows the latest hand-off for eight seconds, its hover the last three, its click
  Conversations on that pair.
- **far | mid | near**: the zoom changes what is drawn (blocks only under 60%, boxes, boxes with their thought and tool
  output from 130%); Ctrl+wheel zooms around the pointer and keeps what is under it; Fit picks the level.
- Tests: `tests/test_studio_live_truth.py`, `tests/test_studio_live_plan.py` (Chrome); the density driver waits for what
  Live draws before it measures and measures the History drawer.

#### Docs

- `docs/STUDIO-live.md` (new part of STUDIO.md); STUDIO-agents.md and STUDIO-sections.md say Agents opens on Live; the
  Agents `?` help has the new steps; glossary: **replay**, **waiting path**.

### Docs: the README shows Studio

- "What it feels like" leads with Studio: `docs/media/studio-model-picker.png` (new, `capture_studio.py --mode picker`) and
  `docs/media/studio-auto.png` (new, `capture_steer.py --only auto`) replace the terminal model picker and auto-mode pictures;
  the steer animation and the phase-line picture left the README for one sentence each. The TUI captures stay in `docs/media`.

## [3.3.17.0] - 2026-11-10

**Copilot at work.** Halo signs in to your work's Microsoft 365 Copilot in the browser (or with a device code) and
talks to it as a provider with one model, `cp:work`, over the Work IQ API or Graph's preview Copilot Chat API. A
session or a lineup role can run on it as a consult role, any agent can ask it through the `copilot_ask` tool, and its
cost is said as "billed by your tenant", never as dollars (docs/PROVIDERS-copilot.md).

### R1: the door

#### Added

- **The settings** `copilot.tenant`, `copilot.client_id` (your own Entra app registration, a public client),
  `copilot.api` (`workiq` default | `graph-beta`), `copilot.web`, `copilot.timezone` and `copilot.scopes`: Settings ->
  Providers, docs/CONFIG.md (`providers/copilot_config.py`).
- **Sign-in** (`providers/copilot_auth.py`, `copilot_tokens.py`): the authorization-code flow with PKCE (S256) against
  the tenant's Entra endpoints, the redirect `http://localhost:<free port>` served once by a listener on 127.0.0.1
  (the state checked, one request, then it closes; a 5-minute wait, said in the terminal), Halo opens the browser and
  prints the URL; `--device` and any box with no browser (SSH, no DISPLAY, `HALO_NO_BROWSER`) use the device code.
  The refresh token goes to the env file as `HALO_SECRET_COPILOT_REFRESH`; access tokens stay in memory, refreshed
  60 s early; who signed in and until when is in `~/.halo/copilot/account.json` (no token).
- **The adapter** (`providers/copilot.py`, on `providers/http.py` only): Work IQ's JSON-RPC `SendMessage` with
  `A2A-Version: 1.0`, the `contextId` kept per conversation and the time zone in the metadata; Graph's
  `/beta/copilot/conversations` and `.../chat` with the text, `locationHint.timeZone`, `additionalContext`, the file
  URIs and web grounding. Both answer `{text, citations, sensitivity, conversation, api}`. Every failure is one line
  with its next step: not set up, not signed in, the sign-in expired, consent missing (the scopes named), no licence,
  billing not enabled, throttled after one `Retry-After` wait, offline mode.
- **`halo copilot signin [--device]`, `signout`, `status [--json]`, `ask "<prompt>" [--file URL]... [--no-web] [--api
  workiq|graph-beta] [--json]`** (docs/COMMANDS-copilot.md); `halo copilot` alone is `status`.
- **The mock** (`tests/helpers/mock_copilot.py`): Entra (authorize, token with PKCE, refresh, a revoked refresh, the
  device code), Work IQ's A2A endpoint and Graph's beta conversations, for every test here.

### R2: in the harness

#### Added

- **`cp:work`** (`model.py`'s prefix table, `providers/copilot_route.py`): a session or a role runs on the session's
  one Copilot conversation; the loop sends it no tools. Its catalog row (`providers/copilot_catalog.py`) says `takes:
  text, files, web`, `tools: no`, no context window and "Copilot Credits or your licence"; `halo models` lists it once
  you are signed in. Auto picks it for the need `work-data` ("research over your work data") when signed in, and
  never for a role that needs tool calls (`models_auto_work.py`).
- **The `copilot_ask` tool** (`tools/copilot_ask.py`, the `web` capability), registered once Copilot is set up: the
  answer with its citations as numbered lines, in the transcript like any tool result.
- **Cost**: a `cp:work` turn and a `copilot_ask` call add no dollars and mark the cost incomplete; `/cost`, `/status`
  and Studio's Cost panel say "Copilot: billed by your tenant (credits or licence)" (`providers/copilot_cost.py`).
- **Studio**: Setup -> Providers has a Copilot card (the status a row per fact, the tenant and app id, the door, Sign
  in / Sign out, the scopes to consent to as a copyable list, Register the app's steps); Sign in starts the browser
  flow on the machine Studio runs on ("finish in the browser tab that opened"), or shows the device code when there is no
  browser (`studio/setup_copilot_api.py`, `routes/setup/CopilotCard.tsx`).
- **`halo doctor`**: one Copilot row (not set up / signed in as ... until ... / token expired / consent missing /
  billing not enabled / no licence), each with its next step (`providers/copilot_doctor.py`).
- **Docs**: docs/PROVIDERS-copilot.md, docs/COMMANDS-copilot.md, the glossary's "consult role".

### On 3.3.16.1-3.3.16.3 (the round, merged onto master)

- **The prompt diet**: `copilot_ask` has its lean description (`tools/lean_descriptions.py`) and goes out right after
  what the lineup needs (`agent/prompt_diet.py` `AFTER_NEEDS`). Copilot not set up, the tool is not registered and the
  pinned first turns do not move; set up, a lean first turn grows by at most the tool's lean size
  (tests/test_prompt_budget_pins.py).
- **The shared ranking**: a model that states no tool calls is never ranked for code (`model_rank.ranks_for`), and
  `cp:work`'s missing dollar price never wins "cheapest"; Auto's `work-data` pick goes through `model_rank`'s one
  comparator (`models_auto_work.py`).
- **Studio**: a Cast hover on `cp:work` says it takes text, files, web; no tools, and "your tenant's credits or
  licence" as its price (the model row's `price_note`); a hover leaves out a context window nobody states. A square or
  a block template may name a bio on `cp:work`; its Costs line and block footer say "tenant credits" in place of the
  dollar band (all of it on Copilot) or after it (part of it) (`workflows/contract.py`, `SquareBlock.tsx`).
- **Live**: a `cp:work` role's turn shows as text rows with no THINK row (Copilot streams no thoughts and none is
  made up), its hand-back as a TALK row, a `copilot_ask` call as a tool row (tests/test_copilot_fit.py).

## [3.3.16.3] - 2026-11-10

The owner, 2026-11-10: "I still really want to see different blocks that you can almost like drag and drop in the agents
tab ... I wish I could see better groupings of these sub-agents ... here's this one task and here's the sub-agents in there".

### Added

- **Live in groups** (Agents -> Live and Session's Map): the sub-agents one step of a parent started together (one
  reply's Agent calls) are one box titled by their task -- the description they share, else the parent's own line
  before the calls, else the words the descriptions start with, never a model call -- and the parent's line goes into
  the box; a square's agents are one box titled `square <name>` with its DOES line; a tier's agents fall back to the
  tier's purpose; an agent started alone is not boxed. The bar counts working / waiting / done, the cost and the time,
  says Auto's pick in plain words ("3 readers on kimi-k3 for a pdf in the task"), folds to itself on the chevron (amber
  while one inside waits on you), and has a hover card. Ten agents are a grid of four to a row; boxes nest one level.
  `routes/agents/live/groups.ts`, `groupLayout.ts`, `GroupBox.tsx`; Session's timeline gains **by group**.
- Agent rows carry `spawn: {step, description, lead}` (`agent/agent_hooks.spawn_of`: the parent's id and reply count,
  the call's description, the parent's last line in that reply) and a square's row its `does`.
- **Blocks on Cast**: the lineup's enabled squares are blocks beside its tiers on one canvas, main's line into each;
  a square block opens to show the bios of its lineup on their models (folded: its TAKES / GIVES / COSTS lines; the
  chevron kept per lineup), its footer its limits and cost band. A click opens its summary in the inspector, with new
  **Purpose** and **Agents** pages (`PUT workflows/contract` takes `does`; a shipped square says how to copy it).
- `tiers[].purpose` in a lineup: the tier block's title line on Cast (its `...` menu edits it), Live's tier group,
  `halo teams show`'s tier line; the shipped auto lineup names both of its tiers.
- **The when** (part 2; the owner: "add this workflow in there when this situation happens"): a lineup's `workflows:`
  item may be `{ref, when: {needs, words, mode}}` beside plain refs (which keep their meaning): `needs` narrow what the
  square covers, `words` fire on what the task says, `mode` is `auto`, `named` (only by name), `always` (first, before
  main answers) or `off` (not connected). `workflows/router.py` reads it (always, then words, then the needs pick;
  `when_route.py`), the receipt's reason names the rule that fired (`handing the PDF to media: when main needs pdf`,
  its `rule` field), the Workflow tool's description says each rule; the auto lineup keeps its rules in config
  `workflows.when.<ref>` (a new keyed Settings row). `workflows/when.py`, `when_store.py`, `when_tool.py`.
- **The line carries it** on Cast: main's line into a square block has a short label (`needs pdf`, `says review,
  audit`, `always first`) with a hover card; a click on it, or the block's new **When** row in the inspector, opens the
  When page (four choices in plain words, what it writes, Save, Disconnect). A block with no line is dashed, its footer
  says "not connected: main never uses it", Problems lists it (NOT CONNECTED). Main's edge handle dragged onto a block,
  or the block's `⋯` menu (Connect to main, When, Disconnect, Take it off), draws the line.
- **The library on Cast, three kinds**: Workflows (yours / packs / shipped), Blocks you can start from, Agents (the
  bios), one search over all three; `+ Library` on Agents' bar on Cast too, beside the canvas, closed on load.
- **Block templates** under `halo_harness/templates/blocks/`: `thinking` (three reasoning agents), `media` (adds as
  `media-team`), `review-panel` (three reviewers), `local-workers` (a tier); every agent on `auto`, nothing names a
  provider. `workflows/blocks.py`, `blocks_tier.py`; `GET workflows/templates`, `POST workflows/templates/add | merge |
  remove`.
- **The four drags** with the real pointer, each asking first (WHAT / COSTS / WRITES) and saying what changed in one
  line: a workflow or a template from the library onto the canvas (wired to main by its covers); an agent (a bio, a
  tier card, another square's agent) into a block (a shipped square is copied to yours as `my-<name>` first and the
  board swaps to it, its rule kept: `workflows/members.py`, `PUT workflows/members`, `POST workflows/swap`); a square's
  agent out onto the canvas (the last cannot leave); a block by its title bar (its spot in the lineup's layout,
  `block:<ref>`). Undo / Redo walk each back in order with the lineup's own edits (`blocks/history.ts`). Keys: Tab
  reaches blocks and their agents, `M` then the arrows and Enter moves one, Delete asks in the inspector.
- CLI and TUI: `halo workflows enable <ref> --when needs=pdf,audio | words=review,audit | named | always | off | auto`,
  `halo workflows when <ref>`, a `when:` column in `halo workflows list` and `/workflows`; `halo blocks list | add
  <template> [--as <name>] | show <name>` (`blocks_cli.py`); `halo teams show` prints `block <ref> (square): when ...`.

### Changed

- Live's layout draws a group as one child of its parent (`liveLayout.ts` hands a tree with groups to
  `groupLayout.ts`; a tree without them is laid out as before). The glossary's **block** says the canvas meaning too;
  **group** is new.
- A lineup's `workflows:` list keeps its `{ref, when}` items through `halo workflows enable / disable` (edited in place,
  not rewritten as refs); `halo teams validate` checks each rule. The square inspector's summary has a **When** row; a
  square's hover card says its when in place of its covers on the board. W keeps its own board with the same library.
- **One order with 3.3.16.2's lineup roles**, explicit before implicit (`workflows/router.py` `route`, docs/WORKFLOWS-squares.md
  "The order"): a square named; then a square whose when fires (`always`, then `words`, then `needs`), ahead of a role;
  then a role of the lineup that covers the need ("to your media role"); then a plain ref's covers; then the line
  saying what would. An inherited `workflows.enabled` square is a plain ref, so on the auto lineup a PDF still goes to
  its media member unless the media square has a when. The Workflow tool is not offered when every square on is `off`;
  `halo doctor`'s squares line names a square's when; `halo workflows list` shows "on for <lineup>" / "off" and the when
  column. An edit to a lineup with no `workflows:` key (enable, disable, a when) starts from the set it inherits.

### Docs

- docs/STUDIO-blocks.md (a new part of STUDIO.md: "Blocks" and "Live in groups"; STUDIO-agents.md points to it), docs/ROLES.md and docs/AGENTS.md (`tiers[].purpose`),
  docs/WORKFLOWS-squares.md "A square as a block", the glossary, README's Agents part.
- Part 2: docs/STUDIO-blocks.md "Composing: the line, the library, the drags"; docs/WORKFLOWS-squares.md "When",
  "Block templates", "Who is inside a square"; docs/COMMANDS-workflows.md (`--when`, `when`, `halo blocks`); docs/AGENTS.md
  (`workflows[].when`); docs/CONFIG.md (`workflows.when.<square>`); the glossary's **when**; README's Workflows part;
  docs/media/studio-workflows.png re-rendered as the composed board.

## [3.3.16.2] - 2026-11-10

**Live: thinking you can see, agents talking.** The owner: "make watching a model think much better. In sessions
live tab, it's really amazing to get more visualization on what the models are really thinking. There should also be
a section that does this for model to model or agent to agent conversations. Maybe we can give that a label in the
live feed so we see models conversing with each other and that's its own label."

### Added

- **THINK rows** (`fleet/think.py`, `routes/shared/liveThink.ts`, `routes/session/LiveThink.tsx`): every agent's
  reasoning now reaches Studio as `thinking_chunk` frames from the session's agent tree (followed or not; before, the
  control socket dropped `thinking_delta` and only a followed agent's thinking showed, folded per chunk). One row per
  thought however many pieces it streams in: muted italic on a hairline `--think` rule, a caret while it grows, four
  lines with show all / show less, then `thought 4.2 s · 812 tokens` (the length when it streamed, the tokens when the
  provider reported `reasoning_tokens`). Native Anthropic thinking streams as it comes; the OpenAI-dialect reasoning
  (DeepSeek, Kimi, GLM, OpenRouter, Ollama's thinking models) lands in one piece at the end of the call. A model with
  no thinking shows no THINK row.
- **Thought, then act**: a THINK row's chip says what it led to (`then ran Edit basket.py`, `then answered`) and
  jumps there; the action row's `why?` opens that thought under the row.
- **The Thinking view**: a toggle beside Follow (off by default) narrows Live to the thoughts and what each led to,
  for everyone or the pinned agent. The kind pick gains think and talk.
- **TALK rows** (`fleet/talk.py`, `routes/shared/liveTalk.ts`, `routes/session/LiveTalk.tsx`): one agent's words to
  another as `agent_talk` frames, one shape `{id, from, to, text, why, re?, cut?}`: a parent's task to a child
  (`task`), the child's hand-back (`hand-back`, `re` the task), another agent's steer (`agent_steer` with
  `from_agent`), a Workflow square's hand-off and answer (`square`) and Studio's Hand to... another machine
  (`hand-over`). The row: the speaker's tag, an arrow, the listener's tag, the reason. A hand-back is one row: the
  agent's OUT block becomes the TALK row (an OUT after a TALK hand-back is not added). The map's edge between the
  two lights once from the speaker to the listener, with an arrow.
- **Conversations** (`session-conversations`, optional, the header's "+"): the pairs that have talked, newest first,
  and the chosen pair's thread, each message on its speaker's side with its reason and time, a reply under what it
  answers; a message's click scrolls Live to its row, "show in Live" narrows Live to the pair.
- The trace export (`halo session export`, Live's Export) writes a `thinking` row per thought and `talk:` rows for a
  sub-agent's task and hand-back (the hand-back in place of its last text, never both) and a square's receipt.

### Changed

- **The timeline shows the mix**: Live's timeline draws each lane by phase -- thinking, running a tool, writing,
  waiting on you, idle -- in the state tokens (the legend is in Live's `?` help); hovering a segment says the phase
  and its length, a click on a thinking segment scrolls the column to that thought.
- **`why?`**: on a row a thought led to, its first answer is that thought, inline under the row; "what the model saw"
  there is the turn's postmortem as before. The agent inspector's Thinking tab draws thoughts the way Live does,
  with what each led to.
- The kind pick's text no longer includes thinking (it has its own, think).

### Docs

- docs/STUDIO-sections.md (Session: THINK, TALK, the Thinking view, thought then act, the timeline's phases,
  Conversations), docs/FLEET.md (the two frames and their shapes, the KIND column), docs/STUDIO-session.md (the
  trace's new rows), the glossary (thought, agent talk), Live's and Conversations' `?` help, README "Watching a model
  think" and "Agents talking" with docs/media/studio-thinking.png re-rendered and docs/media/studio-talk.png new.

### From a session's own review (Kali, 2026-11-10)

The owner asked his session's own model (GLM 5.3 on Databricks, a custom lineup) what it thought of 3.3.16.0. It
named four things; each was checked against the code, all four were real.

- **A tie in the model pick went to the name.** `models_best_at.best_per_kind` ranked an equal score by the
  model's ref, so `...-opus-4-1` led over `...-opus-4-6`, an older model over its successor, and price and what
  was measured played no part (the roster, `halo models analyze`, `--best-for` and every pick behind them). Every
  pick now breaks a tie by one order (`halo_harness/model_rank.py`): the kind's score, the measured first-time
  success for the kind here (from 3 checked tasks), the newer version within a model family (`4.6` > `4.1`,
  `v4.1` > `v4`, `5.3` > `5`, a newer date suffix; read across `-`, `.` and `v`), the larger context, the lower
  price, the provider you have a key for, then the name; the cheapest per kind goes price first. The leader's
  line names the deciding term ("same score as X: newer", "...: measured 4/5 here", "...: cheaper") in the
  roster, `halo models analyze`, `halo models --best-for` and the Roles picker. The `auto` pick, `measured`, a
  pack bio's capability pick, the role presets' cheapest model, `halo gym propose` and the media ranking use the
  same order past their own rules. **The best-at index's schema is 2: every box rebuilds it once** on its first
  read after the update. Two test pins held the alphabetical accident (`tests/test_roster_dropped.py`:
  `ant:fable` led code over the same-scored, cheaper `ant:opus` by name alone) and were fixed.
- **Knowledge search answered with the sample's gate records.** A search for "halo harness update new features
  version" came back with 4 of 5 hits from the guided first run's sample repo: the gate's records carry its test
  command, whose python sits in the tool venv (`.../uv/tools/halo-harness/bin/python`), so "halo" and "harness"
  matched a path, there was no project scope, and equal scores went to the newest. Search now ranks by relevance
  first (paths, commands and shas are not words a record says; no shared content word, no hit), this project's
  records first at equal relevance and another project's marked, a routine passed gate under findings unless the
  query names its unit, re-runs collapsed to the newest with "x N", and each hit says why it is there.
  `halo start`'s sample records are tagged `sample` and never answer another project's search (an older one is
  recognized by its project being a sample folder); its card says so. New: `halo knowledge list --kind
  gate|finding|decision --project .|all|NAME`, `halo knowledge prune --kind ... --older-than 7d [--dry-run]
  [--yes]` (prints what it would remove and the count; only `--yes` removes), and a cap of
  `knowledge.gate_keep` (50, a Settings row) passed-gate records per project, applied when the gate writes one.
- **The Workflow tool sat on lineups that had no square.** A custom lineup with no `workflows:` key enabled no
  square, yet the tool was offered every turn and answered "no square is enabled for this lineup". A lineup
  with no `workflows:` key now inherits config `workflows.enabled` (default `media`) like the auto lineup
  (`workflows: []` is none, on purpose); the tool is offered only when a square is on for the lineup; a role of
  the lineup that covers the read (a `media` role, or a card whose bio's `models.needs` / kind covers pdf,
  vision, audio, video) takes the task the Agent tool's way, with the receipt "handing the PDF to your media
  role: the lineup covers it"; when nothing covers it the line says what would ("no role or square reads PDFs
  here: `halo workflows enable media`, or give a role a model that takes PDFs"). `halo doctor` says under the
  lineup which squares are on and from where; `halo workflows list` marks each "on for <lineup>" or "off".
- **No changelog on the box.** A `uv tool install` carries no CHANGELOG.md, so nobody there could see what a
  version changed. The package now ships the newest twelve dated entries (`halo_harness/data/changelog.md`,
  written by `scripts/release.py` when it dates a release); `halo whatsnew [<version>] [--since V] [--full]
  [--summary]` and the TUI's `/whatsnew` show the installed version's summary and each heading with its first
  line, and after `halo update` installs a newer version its last lines are that version's summary and "halo
  whatsnew for the rest".
