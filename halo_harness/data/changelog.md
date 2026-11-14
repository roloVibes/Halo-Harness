# What changed (the newest version entries of CHANGELOG.md, shipped with the package; `halo whatsnew` reads it)

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

## [3.3.16.1] - 2026-11-10

**The local prompt diet.** A first turn to an unknown remote Ollama model was 16,970 tokens of Halo's own prompt
plus a 16,384 reply's room, past its 32,768 window, so the window doubled to 65,536 and the model reloaded; it is
now 7,778 + 8,192 = 15,970 and goes out at 32,768 (16,384: 6,232 + 4,096 at 16,384; 49,152: 7,776 + 12,288; a 200k
cloud model unchanged, byte for byte). Measured with `halo local prompt`, pinned by `tests/test_prompt_budget_pins.py`
on Windows and Linux ([MODELS-prompt-diet.md](docs/MODELS-prompt-diet.md)).

### Changed

- **The reply's room follows the window** (`agent/reply_room.py`): a call to the session's own Ollama model asks for
  at most a quarter of the window it gets, never under the window class's floor and never more than it asked; a
  steward profile's `num_predict` and your own `max_tokens` keep their rule. A session's first call starts where
  Halo's own prompt is half the window at most, and no later call drops under the window last asked of the model (no
  reload). The turn says it once per session. `agent/loop.py`'s `_build_ollama_body_for_ref` calls it (no lines added).
- **Tools, lean** (`agent/prompt_diet.py`, `tools/lean_descriptions.py`): on the lean profile an alias goes on the
  wire once (`Task` as `Agent`; a call named `Task` still runs), a Windows session offers one shell (`prompt.shell`),
  every built-in tool goes out with a short description, and the block is held to 2,200 tokens up to a 16,384 window
  and 4,500 under 65,536, filled core first, then the lineup's needs (`Workflow` only when a square covers what the
  model lacks), the built-ins, the rest. What is left out stays callable by name and through ToolSearch; the system
  line naming it says so. The unknown-remote case: 29 tools, ~9,300 tokens -> 25 tools, 3,747.
- **The system text, lean** (`agent/prompt_lean_system.py`): the wire copy keeps the instructions (native tool
  calls, CLAUDE.md, read before edit, verify, plan mode, memory, hooks, delegation) and drops the per-tool list and
  the reference prose: ~4,150 tokens of Halo's own text -> ~580; the lean system message, memory included, 3,792.
- **The estimate is the wire's** (`providers/ollama_wire_estimate.py`): the window is picked from the estimate of
  the Ollama-shaped body that is sent, not the Anthropic-shaped request (0.5 % apart); the strict `num_ctx >= floor`
  check in `tests/test_ollama_trim_recovery.py` is back.
- The steward's fit plan never shrinks a window under Halo's own measured first turn plus a reply (`fit.floor_window`,
  8,192 when unmeasured); the steward's guide budget is 2,200 tokens (the new row).

### Added

- `halo local prompt [<ref>] [--window N] [--platform P] [--json]` (`agent/prompt_measure.py`): what a model's first
  turn costs before you use it -- the composition, the reply's room, the window, a row per tool (offered or left out
  and why). `/status` and `halo doctor`'s default-model row say "Halo's own first turn: N tokens of W (P %)" on a
  local model; Studio's model card has the row "Halo's first turn: N tokens (P % of the window)".
- The steward rule `prompt-heavy`: Halo's own part of the newest call over half its window, with one next step (the
  lean profile on, a bigger window, or the core tools).
- Config `prompt.shell` (`auto` | `bash` | `powershell`, Settings -> Models).
- Tests: `test_prompt_diet`, `test_prompt_budget_pins`, `test_prompt_measure`.

### Docs

- New [MODELS-prompt-diet.md](docs/MODELS-prompt-diet.md) (the before and after, the reply's room, aliases once, one
  shell, lean descriptions and system text, the budget test, `halo local prompt`); MODELS-prompt-budget.md gains "The
  diet"; COMMANDS-local.md `halo local prompt`; CONFIG.md `prompt.shell`; the steward's symptoms table `prompt-heavy`.

### Docs: the README and the pictures

- **Update, and the certificate line.** README gets a `## Update` section (`halo update`, `/update`, and the one-line
  repair for an install older than 3.3.16.0 that stops at `invalid peer certificate: UnknownIssuer`); docs/INSTALL.md's
  Update section and a docs/TROUBLESHOOTING.md entry titled by the error say the same.
- **The README as 3.3.16.0 is.** Agents' four views, `### Live on the fleet`, a `### Workflows: saved orchestrations as
  squares` part (the square, the router, the five shipped, `halo workflows`, the board), the Features and Documentation
  rows; its pins in tests/test_quickstart_docs.py follow.
- **Every Studio picture re-rendered** from the 3.3.16.0 build (the stills, both GIFs, the modes banner, `hero.png`,
  `social-preview.png`), and a new one: `docs/media/studio-workflows.png` from `tools/capture_workflows.py`
  (`tools/capture_studio.py --mode workflows`).
- **What it feels like, in the current look.** The README's terminal pictures were rendered in `claude-dark`; they are
  `instrument` now (the default since 3.3.15.0: `tools/captures.json`, `scripts/capture_scenes.py`). "Steering a running
  turn" and "Watching a model think" lead with Studio stills, `studio-steer.png` and `studio-thinking.png`
  (`tools/capture_steer.py`), then the terminal picture.

### Added: hover says what a box is

The owner, 2026-11-10: "hovering over gives a solid summary, if we click one we get that other panel with all the
detail about the selected box."

- Every box in Agents has a hover card: a Cast card, a Live agent, a session, a machine, a run's lead and lanes, a
  mission part, a workflow square on the board and in the library. Rest the pointer on it about 350 ms, or Tab to it
  (the arrows on the board), and one card shows beside it, inside the window, never over the box.
- A card is a title, one sentence of what the box is, at most eight rows of facts the page already has (a fact not
  known is left out), a NOW block while the box works, and a line saying what a click does
  ([STUDIO-agents.md](docs/STUDIO-agents.md#hover-and-click-33161) has each kind's rows).
- A click still opens the inspector and hides the card; so do Esc, a scroll, a press and the box's "..." menu. One card
  at a time, no buttons on it, no request on hover.
- A box with a card drops its plain tooltip; a button or chip inside it keeps its own. A workflow square's contract
  opens in the inspector on a click now, not on hover. Cast cards take the keyboard (Tab, then Enter selects).
- `studio.hover_cards` (Settings -> Studio, a new page; on by default) turns the cards off and the tooltips back on.
- Fixed on the way: the Workflows board drew 0 px wide while the library was closed (it fell into the library's
  column), so its squares could not be hovered or clicked until the library opened.

## [3.3.16.0] - 2026-11-10

**Agents: one section for your agents.** The owner, 2026-11-09: "what does teams even give us? ... roles and
orchestration are almost the same ... all rolled into the new agents". Team, Roles and Orchestra are one Studio
section, Agents (`Alt+2`), with three views on one switch -- Cast (the lineup and its bios: Roles as it was), Runs (a
goal for the lineup: Orchestra as it was, plus who owns what and Test this lineup) and Live (the session's agents as a
tree, a live Orchestra run's lanes under its lead). R2 folds the Fleet section into Agents -> Live, Setup ->
Machines and Local, so the shell has six core sections; every old door (and `?mode=fleet`) (`?mode=roles`,
`orchestra`, `team`, `--mode`, `--edit`, `/roles`, `/studio`) still lands on the right view and says the new one.
R1b (the inspector says one thing at a time, the density pass), R2 (the Fleet fold) and R3 (Workflows) follow.

### R1: Agents, one section

#### Changed

- **One section, three views** (`routes/agents/`). `SECTIONS` is Session `Alt+1`, Agents `Alt+2`, Fleet `Alt+3`,
  Packs `Alt+4`, Setup `Alt+5`, Settings `Alt+6`, Local `Alt+7`; the packs' own sections take `Alt+8`, `Alt+9` and
  `Alt+0` (`FIRST_KEY = 8`). Agents' bar starts with **Cast | Runs | Live** (`?mode=agents&view=cast|runs|live`; `C`,
  `R`, `L` outside a text field; the palette's "Agents: Cast / Runs / Live") and it opens on Cast with nothing else
  open. Cast and Live draw Roles' workspace, Runs Orchestra's, each keeping its layout, panel ids and every
  `data-testid`; the header's `+` and `...` menus, the palette's panel rows and the status bar follow the view.
- **The doors.** `?mode=roles` lands on Cast (`&view=live` on Live), `?mode=orchestra` and `?mode=team` on Runs, the
  latter with "Team's board is gone; a run's plan shows who owns what" the first time in a browser; a saved section,
  a `focus` frame, an attention row's `o` and a pack's route that name an old word land the same way
  (`ui/src/lib/agentsDoor.ts`). `STUDIO_MODES` is the seven sections plus `roles`, `orchestra` and `team`;
  `halo studio --mode roles|orchestra|team`, `/studio <word>` and the TUI's bare `/roles` open Agents and print the
  new door once (`studio/agents_door.py`). `halo studio --edit bio:|lineup:` opens `?mode=agents&view=cast&edit=...`,
  `--edit team` `?mode=agents&view=runs&edit=team`.
- **Who owns what** (Runs). Each lane says what it owns -- the claim ledger's keys for that lane -- on its plan card
  (`plan-owns`) and its row in Lanes (`lane-owns`); a focused lane lists its claims with holder and state
  (`lane-claims`), and the plan inspector shows the same rows as CLAIM LEDGER, read from `GET orchestra/<run>`'s
  `claims` (no new field).
- **Test this lineup** on Runs' bar: the guided first run on the active lineup (`POST start`), its card first; on Auto
  it is disabled with the Auto line beside it.
- **Live draws a run.** While an Orchestra run of Studio's repo is live, Live draws its lead and each lane under it,
  the lane's number in its colour and its worktree badge (the lane's branch); a click opens Runs on that lane.
- The Fleet attention rows of an Orchestra gate, a supervisor decision and a team stage open Agents on Runs (`o`:
  "open Agents: Runs"); a team stage held at its budget line answers Raise with where the team file is.
- Words that named the old sections follow: CLI help (`halo studio --mode agents`), the system prompt, the guided
  first run's card, Auto line and next steps (Agents: Cast, Agents: Runs, Fleet), the coach's error lines, Setup's
  **Edit in Agents**, the Session Map's **Open in Agents Live**, the Start views' Next footer (Cast -> Runs -> Fleet).

#### Removed

- **The Team section** (`routes/team/*`, `help-team.ts`, `styles/team*.css`, the status bar's TEAM cell, the Team
  Chrome drivers and `tools/capture_team.py`, `docs/media/studio-team.png`). Every `/api/team/...` route the board
  used answers 410: "Team's board moved into Agents -> Runs (a run's plan shows who owns what); halo team runs the
  team file" (`studio/team_init_api.py` deleted). `halo team` stays, `GET team/coach` stays, and a team stage at its
  gate is still a row of Fleet's Attention.

#### Docs

- New [docs/STUDIO-agents.md](docs/STUDIO-agents.md): the three views, the doors, what Team's board became, the owns
  line, Test this lineup, Live's run lanes and Cast. STUDIO-orchestra.md is "Agents -> Runs"; STUDIO-team-roles.md
  points to the new doc, keeping its anchors. STUDIO-sections.md has one Agents entry (Roles, Orchestra and Team folded
  in with "moved" lines), STUDIO-shell.md, STUDIO.md, README (seven sections, the banner and its captures re-rendered),
  TEAM.md ("the board moved to Agents -> Runs; `halo team` stays"), COMMANDS-studio.md, the glossary and every doc's
  `Alt+N` follow.

### R1b: the inspector says one thing at a time; the density pass

The owner's photo of Cast's Lineup tab (2026-11-09: "so so busy ... I can barely read ... idk what all of those
functions and settings even are") and his standing rule ("small blocks that make it hard to use ... make studio
cleaner and clearer").

#### Changed

- **The inspector opens on a summary.** With a lineup open, the Lineup tab (and the Assignment tab with no card) is six
  plain-words lines -- what the lineup does, the main model with its price and band, who is on it, where workers run,
  spend, "9 sections: 3 set, 6 at Halo's default" -- then one Edit row per block (Description and how it works, Where
  workers run, Schedule and warm set, the nine sections), each with its state in mono or "not set = Halo does: ...".
  No form, no YAML box, no help paragraph is on it.
- **One block per page.** Edit opens that block alone: Back (or Esc) to the summary, the title, the enforcement badge,
  the YAML toggle and a `?` with that block's field lines only; one sentence of what it does; "not set = Halo does
  ..." when it is unset; then its form. A selected card opens on its own summary (role, bio, the model with its takes
  tags, price and context, instances, the words that route to it) with Edit rows for its Slot and its Model override
  and Edit bio. Every testid stays (`roles-block-<name>` is the row that opens the page).
- **The density pass.** No control bar under 36 px, no row that is a target under 40 px, 12 px inside every panel
  body and between panels, one thing open per section on load: Settings' and Local's page-rail rows were 33 px (now
  `--row-h`, 40), and Session's Live and Prompt panels set their body's padding to 0 (the exemption went; the
  primitive's 12 px applies). Every core section kept one panel open on load.
- The Studio captures that still drew the nine-icon rail are re-rendered (Session, its Live column and GIF, Roles
  Live, Fleet x5, Packs, Setup, Settings, Local, Design, Agents, Roles, the modes banner, the hero and the social
  preview).

#### Added

- `LINEUP_DEFAULTS` in `halo_harness/field_help.py`: what Halo does when a lineup leaves each section (and
  `isolation`) out, read from the code that applies it; `GET /api/field-help` serves it as `lineup_defaults`, and the
  terminal's lineup view prints "(not set = Halo does: ...)" under each unset section.
- `halo studio --edit lineup:<name>:<block>` opens one block's page (`description`, `workers`, `schedule` or a section).
- The primitives mark themselves for the density rules (`data-density="bar|row|body"`), the tokens `--ctl-h` (36)
  and `--row-h` (40), and `tests/test_studio_density.py` (headless Chrome over every core section, each workspace
  panel opened in turn; the first offender fails with its section, testid and height); `tests/test_lineup_defaults.py`.

#### Docs

- STUDIO-agents.md (the summary, Edit, one block per page, the defaults line), STUDIO-shell.md (the density rules),
  ROLES.md (a lineup section not set: what Halo does), AGENTS.md, COMMANDS-studio.md (`--edit lineup:<n>:<block>`),
  MEDIA.md (the seven-tile banner).

### R2: the Fleet fold

A machine's agents are in Agents, its pairing in Setup, its models in Local; the Fleet section is gone. Six core
sections: Session `Alt+1`, Agents `Alt+2`, Local `Alt+3`, Packs `Alt+4`, Setup `Alt+5`, Settings `Alt+6`; the packs'
own sections start on `Alt+7` (`FIRST_KEY = 7`).

#### Changed

- **Live spans the fleet.** Agents -> Live has a scope switch, **this halo | fleet** (`live-scope`; `F`, Shift+F, on
  the canvas; `f` still fits): on fleet the canvas is machine > session > agent, one box per machine (Halo version and
  capability chips), its sessions as cards (git, mission and conflict chips, `...` menu) and their agents as the tree,
  a mission's parts in their machines' boxes (drag a part into another box to reassign it; claims and hand-on edges,
  conflict edges, lit spawn edges). The Session Map is the same canvas as a thumbnail (`routes/agents/live/`).
- **The inspector follows the pick, summary first** (`LiveInspector`): nothing picked is the fleet's glance (while you
  were away, machines, agents working, what waits on you, today's spend against the cap, the balances, the caps
  reached with Lift, one row per machine); a machine is its summary (who, health, spend today, Message) with Edit rows
  for Specs and who can... (the spec card, the recall box), Spend caps (`POST fleet/caps`, and a link to Settings ->
  Fleet) and Sharing and control (Setup -> Machines), one block a page with Back; an agent is the one agent inspector
  (the same component in Session's Agent strip, Cast's Live tab and Live); a mission part its card with its owns line.
- **The Attention chip** in Agents' bar (`agents-attention`, amber with a count, `A` toggles it, the palette's "Agents:
  Attention") opens the queue over the page (`fleet-attention` kept); **Activity** is an optional panel of Live, closed
  on load (the header's **+**, the palette).
- **Missions are runs**: Runs' **+** menu and Start view list the missions as rows (goal, state, parts, where they run)
  and offer **Run it across the fleet** when more than one harness is here; `M` and `?mode=fleet&mission=<id>` open the
  Mission panel in Runs; a part's row and card say what it owns.
- **Setup -> Machines** (the step before the Summary, `?block=machines`): the pair card, the share / control rows, the
  hubs joined and the People table with **Forget**; Fleet's Start view is its lead while only this harness is here;
  the Summary has a Machines line; the Start views' Next footer is Cast -> Runs -> Machines.
- **Local takes the Ollama panel**: Hosts gains the steward block (host picker, the models table, the traffic timeline,
  the fit plan with Apply and Copy), Steward gains Run now, the hub's note and the changes with Undo; the
  `ollama_steward` attention row's `o` opens Local -> Hosts on its host ("open Local"), a spend cap's opens the
  machine's spend ("open the spend"), a conflict's opens Live ("open Live").
- `?mode=fleet`, `halo studio --mode fleet` and `/studio fleet` land on Agents -> Live with the fleet scope and say
  once "Fleet is Agents -> Live now, the fleet scope on", with where machines, models and missions went
  (`studio/agents_door.py`); `STUDIO_SECTIONS` is the six, `STUDIO_MODES` keeps `fleet` as a door. The rail's agent
  count and "while you were away" dot sit on Agents; the status bar's FLEET cell went. Palette rows say "Agents: ...",
  "Setup: pair a machine", "Setup: forget <machine>", "Local: the Ollama steward".

#### Removed

- **The Fleet section**: `routes/fleet/Fleet.tsx`, `Start.tsx`, `Map.tsx`, `MapNode.tsx`, `MapChips.tsx`,
  `MapMission.tsx`, `MapSteer.tsx`, `MapTreeNode.tsx`, `FleetTree.tsx`, `layout.ts`, `Ollama.tsx`, the pair dialog,
  FleetSettings' member list (the People table has them), the People / Health / Costs / Capabilities panel faces,
  **By project** (each session card keeps its git chips), `help-fleet.ts`'s panel entries but Attention, Activity and
  Mission, `tests/helpers/studio_tree.py`, and `docs/media/studio-fleet-ollama.png`. Fleet's Ollama pieces moved to
  `routes/local/` (`ostore.ts`, `StewardBits.tsx`, `HostPlan.tsx`, `HostTraffic.tsx`, `HostSteward.tsx`).

#### Docs

- docs/STUDIO-fleet.md is "Fleet in Agents, Setup and Local" (where each Fleet panel went, Live on the fleet, every
  "How this works" anchor kept, Setup -> Machines); STUDIO-agents.md (Live's scope, the inspector by pick, the
  Attention chip, missions in Runs), STUDIO-sections.md (six entries; Fleet folded into Agents with a "moved" line),
  STUDIO-shell.md, STUDIO-setup.md (the Machines page), STUDIO-local.md and MODELS-ollama-steward.md (the steward
  block), FLEET.md's Studio part, MISSIONS.md, README (six sections, the banner and the fleet picture re-rendered),
  COMMANDS-studio.md, the glossary and every doc's `Alt+N` follow.

### The map's boxes say everything they hold

The owner, from Session's Map on Kali (2026-11-10): "information gets stomped on, it's ok if the boxes elongate to fit
the words, just don't squish them. Also no need for tui in the boxes."

- An agent's box on Live and on Session's Map (`routes/roles/LiveNode.tsx`, `styles/nodes.css`) is 268 x 124 px
  (240 x 110 compact; 228 x 92 and 180 x 70 before), and each thing it says has its own row: the name whole (the full
  name in the tooltip when even that is cut), the role under it in the second accent colour (`roles-live-role`), the
  model on the left of a row whose right side is the cost and the time (the model gives way, the cost never does),
  then two lines of what it does now (`roles-live-now`) or the running tool. Nothing is cut by a character count
  before the box is full; the badge and the menu never shrink.
- A session's box (`routes/agents/live/SessionNode.tsx`) shows its title on two lines before it is cut, the project
  and branch beside its cost, and the kind chip only for a session that is not the terminal's (`headless`, a mission
  part); "tui" is no longer printed. A file another session edits too is its own line ("! also edited elsewhere:
  basket.py") in place of a clipped chip.
- The role leads an agent's box when it has one ("reviewer", "writer"), and the agent's own name is the muted line
  under it (the owner: "do role first in the boxes"); a box with no role is titled by its name as before.
- A node's "..." menu measures itself and opens upward when there is no room under the node: with eight items its
  last one, Open in Session, sat below the window on a node low on the canvas, and a click there did nothing
  (`routes/agents/live/NodeMenu.tsx`).
- Live's auto-fit runs before the tree is painted, so a tree is never shown for a frame at the zoom of the scope you
  just left, and a zoom pressed in that frame is no longer undone (`routes/roles/LiveMap.tsx`).
- A panel added from the header "+" or a palette door while its section is still laying out is added when the layout
  is there, however long that takes; it was dropped after one 120 ms retry, which a slow machine lost
  (`lib/workspace/persist.ts` `whenLaidOut`, `shell/commands.ts`, `routes/agents/fleetDoor.ts`).
- A failed agent's edge stays red while that agent is selected: the selection colour no longer covers a state colour
  (`styles/nodes.css`).
- docs/media: the Live, Session and mission captures, the modes banner and the hero re-rendered.

### Fixed on the way: a mission's report is there when its state says done; the Benchmarks page's stale mark

- **A Fleet mission's `report.md` and `report.json` are written before its final state lands on disk**
  (`fleet/mission_run.py` `_end` writes the report inside the state's update; `mission_report.write` takes the
  document the caller holds). Before, the state said done a moment before the files existed, and a reader that
  saw done could find no report (the hosted Linux runner did, on 0ec52632).
- **The Benchmarks page's stale mark no longer depends on who loaded first.** `GET local/benches` read the host's
  Ollama version only from in-process caches (the hosts strip's card, a provider call's cache); a page answered
  before those were filled showed no "measured on 0.40.5" and never re-read. `local_bench_runs._now_version` now
  probes `/api/version` once per host per process when no card holds it (the test flag's rule kept: loopback
  fakes only). The seeded fake `box` answers `/api/version` with the version its card says.
- **An update answer that came from the cache says so** (`update_note.py`). When the live check fails (offline, a
  short outage, a rate limit) `latest_available` answers from `~/.halo/update-check.json`; that answer printed like a
  live one, so a box behind a dead router read "available (stable): v3.3.14.0" and `halo update` said "already up to
  date" while v3.3.15.0 existed (the owner, 2026-11-10). `halo update --check`, `halo update` and `/update` now add
  "(from the cache, checked 6 h ago; the live check failed: network unavailable -- run `halo update --check` again
  when you are online)".
- **`halo update` survives a network uv's own TLS does not trust** (`update_install.py`; the owner's Kali, 2026-11-10:
  uv stopped at "invalid peer certificate: UnknownIssuer" on the `requirements.lock` URL while git, which trusts the
  box's CA store, had cloned fine, and halo stayed on 3.3.14.0). The lock is now fetched by halo itself (the same TLS
  policy as every other request: the system's store and any configured CA bundle) into a local file; when that fetch
  fails the pin is dropped for this run with one line; a certificate failure in the installer itself is run once more
  on the system's certificate store, and a second failure says what to check (`env | grep -i proxy`, an intercepting
  proxy's CA). The store is asked for through the environment (`UV_SYSTEM_CERTS=1`, and `UV_NATIVE_TLS=1` for a uv
  before 0.11), not the `--native-tls` flag, which uv 0.11 renamed and says it will remove: one retry that works on
  every uv, printed as a line to paste. `scripts/install-halo.sh` and `install-halo.ps1` do the same when their
  `uv tool install` fails, so a box whose old `halo update` cannot get past the certificate is repaired by running
  the installer again. The "after" line reads the version under the banner, not the banner.

### R3: Workflows, squares and the router

The owner, 2026-11-09 evening: "have that whole entire workflow in like a square ... your main kind of orchestration
agent can just now point to the different workflow squares ... I might be using a model that has no visualization,
can't read PDFs, but it knows that there's a workflow that has other models that can process that information". A
square is a workflow with a contract; the main agent hands a task to one through one tool, the router.

#### Added
- **A square's contract** in the workflow file (`workflows/contract.py`, the schema and its JSON twin): `does`
  (`description` stays its alias), `takes`, `gives` (required for a square; checked when it returns), `covers`,
  `lineup`, `engine` (`session` | `orchestra` | `mission`, run as orchestra while only this harness is here), `budget`
  (`band`, `cap_usd`) and `limits` (`depth` default 1, `turns`, `wall_s`). One meaning line per bad value; a hand-off
  written at the root says it belongs on a stage. A workflow without `gives` lists and runs as before and is never
  picked.
- **The registry** (`workflows/registry.py`): squares from yours (`~/.halo/workflows/`), the project's
  (`.halo/workflows/`), the running packs' (`<pack>/<name>`) and the shipped ones; a bare name resolves yours >
  project > shipped; `spec.find` reads it. Enabled per lineup: a lineup's `workflows:` list, or on the auto lineup the
  new config key `workflows.enabled` (Settings -> Agents and roles; default: `media`).
- **Five shipped squares** (`templates/workflows/`): `media` (pdf, vision, audio, video on an `auto` lead), `plan`,
  `review`, `research` (session) and `code` (orchestra: build, then review), each with `limits.depth: 1` and a check.
- **The `Workflow` tool** (`tools/workflow.py`, `workflows/router.py`, `workflows/square_run.py`): `Workflow(need |
  name, task, files)` on the main agent and every bio allowed `Agent`. The gaps are the task's needs minus what the
  model takes (the `/model` takes column), plus the asks; the enabled square covering the most gaps, nearest the
  session's band, takes it, and one line says why ("handing the PDF to media: your model takes text only"); no square
  is one line and the model goes on. A session square runs one agent through the Agent tool's path (the parent's
  permission engine and rules); an orchestra square compiles and runs, bounded by `limits.wall_s`. Depth and the cap
  (the square's or the session's remaining, the smaller) are enforced in the tool; a session square is stopped past
  its cap, wall time or turns.
- **Receipts** (`workflows/receipts.py`): each hand-off is a `receipt` node in the transcript (the files' names, never
  their content), a node on Agents -> Live under the agent that called it (the agent row's new `square` field, the
  square's name in mono and its engine's colour, its cost beside the session's), a `squares` line on the Session's
  Cost panel, and a `squares:` line of an Orchestra run's report, in order.
- **Agents -> Workflows**, the fourth view (`W`, `?mode=agents&view=workflows`, the palette's **Agents: Workflows**;
  `routes/agents/workflows/`, `styles/workflows.css`, `studio/workflows_api.py`): the board of enabled squares (240 x
  140 cards on the 12 px grid: DOES / TAKES / GIVES / COSTS and a limits chip), the library (yours, packs, shipped,
  a search box, `/`), a drop's confirm card (what / cost / time / writes), the `x`, the summary-first inspector with
  Enable, Budget, Limits and YAML pages, the still edges with one moving dash toward the square at work.
- **`halo workflows list | show | enable | disable | test | new`** (`workflows/squares_cli.py`; `check` and `run`
  reach `halo workflow`'s), the TUI's **`/workflows`**, and a `square` check per pack square in `halo pack test`.

#### Changed
- `halo workflow` keeps its verbs; `spec.find` takes a bare name (yours, the project's, shipped). A lineup of yours
  may name a bare square in `workflows:`.
- A bio allowed `Agent` or `Task` is allowed `Workflow` too (`config/agents_md.py`).

#### Docs
- New docs/WORKFLOWS-squares.md (the contract, the registry, the router, receipts); WORKFLOWS.md "A square";
  COMMANDS-workflows.md `halo workflows`; STUDIO-agents.md the fourth view and the board's rules; SLASH-COMMANDS-tui.md
  `/workflows`; PACKS.md "A pack's squares"; AGENTS.md the `Workflow` tool; CONFIG.md `workflows.enabled`; the
  glossary's "square" and "router" (and a sentence on "receipt"); the module map.

## [3.3.15.0] - 2026-11-09

**Studio wears the Instrument look.** A design session answered `docs/STUDIO-redesign-brief.md` with "Instrument"
(`docs/design/studio-instrument/`: the proposal, the mock-ups, the prompt it was written to be applied with), and this
version applies it as its first round (the second, R2, makes every model list say what a model takes): an eleventh palette, `instrument`, that Studio draws on a dark system; solid surfaces,
1 px hairlines, corner ticks on every panel, cyan for work and selection, amber for what waits on you, mono for data
and sans for prose; four animations that carry meaning and nothing else that moves. It restyles only: no section or
panel is renamed, no shortcut, route, `?mode=` word or `data-testid` changes, and the rail keeps its nine core
sections in their order with the packs' after them.

### Fixed on the way: an Orchestra worker's "STOP: none" is no stop

- **A worker that says the stop condition did not apply no longer kills its lane** (rolo, Kali, during the guided
  first run; finding f-20261109-9f7492). `stop_line` read any reply line starting with `STOP:` as a real stop, so
  "STOP: none -- my unit is written" or "STOP: not applicable" failed the lane and every lane that depended on it, and
  the retry path never retries a stop. A reason that only says it did not apply (none, n/a, no, not applicable, does
  not apply, nothing, not needed) is skipped (`orchestra/worker_stop.py`); a bare `STOP:` still means the worker
  stopped; the worker prompt now says to write no STOP line at all when STOP WHEN does not apply.

### L1: Instrument, the look

#### Changed

- **The palette.** `instrument` joins the registry (`halo_harness/themes/palettes.py`, PROPOSAL.md section 1: the
  seventeen tokens exactly, dark; every text token over 4.5:1 on bg, surface and surface-2, the lowest faint on
  surface-2 at 4.9; accent_ink on accent 10.5). Studio's "follow the system" draws it on a dark system (`:root`
  alone, `data-theme="auto"` and the server's first paint did holo); `holo` stays in the theme menu and on Settings ->
  Themes, `paper` stays the light default, the terminal's default is unchanged and `/theme` lists eleven. holo's
  label says it was Studio's look before this version.
- **The derived variables** (PROPOSAL.md section 2; `halo_harness/themes/studio_css.py`, the same rule for a pack's
  palette at run time). Surfaces are solid (`--surface-glass` is the surface, `--blur` 0), the resting `--glow` is
  no shadow and `--glow-strong` a 1 px accent ring, Studio's hairlines come from the opaque `border` token (`--line`,
  the new `--border`; a light palette's `line` is its `border`, so a light page draws as before) with `--line-soft`
  for row rules and `--line-strong` the border lifted toward the text, `--grid-line` is the dot of the static dot grid
  (`--grid`, on map canvases only), one shadow level (`--shadow-1`), soft fills at 6-8 % on a dark page, and `--user`
  / `--tool`. The static block of `styles/tokens.css` adds the scales: radii (`--r-panel` 6 ... `--r-badge` 2),
  spacing (`--s-1`..`--s-6`: 4 8 12 16 20 28), type (`--t-title`, `--t-body` 13 px prose, `--t-data` 12 px mono,
  `--t-caption`, `--t-node-name`), motion (`--dur-fast` 160, `--dur-base` 240, `--dur-slow` 600 ms, zero under
  reduced motion) and the chrome sizes; comfortable density is 13 px text and a 40 px title row, compact 12 px and 32.
  Every old variable name stays.
- **The shell** (PROPOSAL.md section 3). The rail is 52 px of icons (176 px with titles on its chevron, kept per
  browser as before), the selected section the accent with a 2 px bar at the left edge, its badges squares; the header
  48 px with the section's name in mono caps, a `/` and its line, the command palette's door a 300 px field; the status
  bar 26 px in 11 px mono; the inspector a 344 px column; the palette 560 px with 36 px rows. The rail is still
  sections only, nothing opens on a section load, the inspector opens on a selection, Focus hides all but the page.
- **The kit** (`lib/ui`). Buttons 30 px in mono (on = the accent, primary the accent fill), Kbd 16 px, a Field's text
  input carries a leading `›`, Tabs are 36 px mono caps with a 1 px underline and no sliding, Menu and Dialog the one
  shadow level, every panel frame (`.glass`) four corner ticks with the selected panel's in the text colour, Toasts
  300 px in mono, Empty one line and a button, ErrorState one line in red, Skeleton still blocks after 300 ms, the
  FitMeter an 8 px track. **A confirmation shows DOES / COSTS / WRITES** (`lib/ui/DialogCost.tsx`, `Dialog`'s new
  `cost`): three mono lines before the buttons, the pack kit's offered-action rule made visible -- a pack's remove and
  update, Roles' Apply, delete a lineup, a bio or a card, leave unsaved edits, clone over a name, stop a mission, take
  over, hand to, kick, stop a team run, delete a local model.
- **Map nodes and edges** (Session Map, Roles Live, the Fleet Tree; `styles/nodes.css`). A node is surface-2 with a
  hairline and a 2 px rule across the top in its state colour (working cyan, waiting amber three pulses then steady,
  done green fading to rest over 10 s, failed red until you click it), a state square, a 1 px outline 3 px out when it
  is selected or a Live line for it is hovered; an edge is 1.5 px, a working child's carries a 4/8 dash moving toward
  it, a failed one is dotted. Nodes, Roles Live's nodes, Live's tags and the Fleet Tree show the resolved model without
  its provider prefix (`lib/modelName.ts`: `or:qwen/qwen3-coder` -> `qwen3-coder`); the Inspector, the Agent panel and
  the tooltips keep the full id.
- **Motion** (PROPOSAL.md section 5, `styles/motion.css`). Four animations: an agent starting (its node fades in, its
  edge draws from the parent) and ending, a receipt ladder climbing (the Prompt panel's four marks, 160 ms apart), the
  fit meter filling once, a toast arriving (16 px rise and fade, a 180 ms fade out; it holds 4 s, an error stays until
  its ✕). Each plays only for a thing that appears after its page drew (`lib/motion/born.ts`), never on a section
  load; the working state square blinks at 1.4 s. Everything else is still: no breathing, no flowing light, no sweep,
  no fade or rise when a section, a panel, a menu, a dialog or a row appears. Under `prefers-reduced-motion` every one
  is an instant state swap and a working edge is solid accent.

#### Docs

- docs/STUDIO-shell.md: the Instrument look (the rail's widths, the panel frame's ticks and faces, the Dialog's three
  lines, the motion rule), the eleven palettes; docs/CONFIG.md `theme` and docs/GLOSSARY.md: eleven palettes,
  `instrument` the dark default; docs/STUDIO-sections.md and docs/STUDIO-setup.md where a line counted palettes or
  described chrome that changed; docs/STUDIO-redesign-brief.md: what shipped.

### R2: the picker says what a model takes

The owner: "When you use forward slash model, show what the models capabilities are like visual, audio, pdf, etc. Is
there a way to see this info via studio?" The facts were in every catalog row and the honest line in the best-at
cache; now every place a model is picked says them.

#### Changed
- The terminal `/model` picker's rows carry a `takes=` column right after the ref (`halo_harness/model_takes.py`):
  what the model reads (`text` always, then `vision`, `audio`, `video`, `pdf`), `image` when it makes images, `tools`
  and `think` when stated or measured, `?` when the catalog states no inputs. The header line explains it. The prices
  follow it, so a narrow terminal keeps ref, takes and price and ellipsizes ctx and speed.
- The picker's subtitle shows the highlighted model's honest line ("vision+pdf in, tools, reasoning, long context
  (1M), premium; no audio") and the footer again when nothing is highlighted (`tui/dialogs/model_picker_takes.py`).
- `/model <ref>`'s confirmation ends with the takes words; `halo models` prints a `takes` column for the OpenRouter
  and Databricks tables; `halo models show <ref>` prints `takes:` and `best at:` (`--json`: `takes`, `best_at_line`).
- Studio: one tag group (`routes/shared/ModelTakes.tsx`, `data-testid="model-takes"`, the honest line its title)
  wherever a model is picked -- under the model select (Orchestra's goal and workflow forms, Roles' Assignment, MODEL
  strip, tier menu, bio form), beside Session's new-session select, Settings' model rows, and as the TAKES column of
  Roles' picker table and Setup's default model. `GET models`, the Setup rows and `GET sessions/new` carry `takes` (and
  the new-session rows the line); no new route.
- Studio, the owner's note on the picker's chips ("funky": ovals stretched to the row, rows several lines tall): a row
  is one line with fixed columns (MODEL, IN / OUT, CTX, TAKES, GYM); the tags are 18 px square-cornered mono words in
  a fixed order (vision, audio, video, pdf, image, tools, think; at most six, then `+n`; `text in` or `?` muted); the
  ranked "best at" kinds are no longer chips in the row: they stay the "best" sort and, with the honest line, the
  effort word and the card's chips, sit on one detail line under the list for the highlighted row
  (`styles/model-takes.css`).

#### Docs
- SLASH-COMMANDS-session.md (`/model`: the column, the line, the confirmation), COMMANDS-providers.md (`halo models`'
  takes column, `halo models show`'s lines), STUDIO-sections.md (the chips wherever a model is picked).

### R3: text boxes fit their text

The owner, with a photo of the Session Prompt panel: "These chat prompt boxes or all boxes that have text in them need
to be bigger ... I can't ever see the example text fully because the chat window is so small." The composer was one
line tall under a mostly empty panel, its two-line placeholder cut mid-word; the same one-line boxes held paragraphs in
Roles' Lineup tab, Orchestra's goal form, Fleet's Steer and Mission start and the Settings editors.

#### Changed
- One text box, `lib/ui/TextBox.tsx` (styles/textbox.css): three lines tall at the least, it grows with its text up to
  `maxRows` lines (12 by default) and then scrolls, with no resize handle and the Field look (the hairline, the accent
  border on focus; prose 13 px for text, mono 12 px for data). It grows by `field-sizing: content` where the browser
  has it and by its measured height on each change elsewhere. `Field` offers it as `multiline`; `lib/ui` (and a
  pack's `api.lib.ui`) exports it. It is now the only `<textarea` in Studio's source: the Prompt composer, Fleet's
  Steer box, Mission start's goal, the Take over brief and the Message box, Orchestra's three goal boxes and the plan's
  reject reason, Roles' Description and How the pieces work together (Description was a one-line field), Prompt
  notes, Rules (mono), the schedule's Prompt, the bio and section YAML (the bio's up to 24 lines), Settings' JSON and
  list editors, and Local -> Steward's question box (it was a one-line field; Enter asks, Shift+Enter a new line).
- The Prompt panel: the box takes the panel's free height while the conversation is short (`fill`: a hidden mirror of
  the text sizes it, the panel's rows are the header, the feed at what it holds, the foot with the rest); a
  conversation taller than the panel scrolls on its own and the box is three lines again, growing with the draft.
- Placeholders fit: at most two lines in a three-line box, the rest in the panel's `?`. The composer's is "Type a turn,
  or / for a command" (Enter, Shift+Enter and the history are in its `?`, with how the box grows); the goal's WHAT
  YOU WANT example, Mission start's goal, Live's Steer line for a finished agent ("pin a live agent to steer"), the
  steward's question (its examples moved to the page's `?`), the no-session line and a Settings list's default (shown
  only when short; the row's default line has it) are shorter.
- Read text is text: the field hints of Roles' Assignment and Lineup tabs sit in the tab's `?` (`routes/roles/TabHelp.tsx`,
  one label and line per field, each section's fields included; the label keeps its line as a tooltip), and a
  lineup's description in the Lineups list wraps to its full height instead of ending in an ellipsis.
- Panels breathe (the owner, with a photo of Fleet: the strips were "squished and too small ... the bottom is too
  short and not enough padding"): a strip was 5 grid rows, a 28 px panel under a 40 px title bar; it is 7 rows now
  (`STRIP_ROWS`, `lib/workspace/types.ts`), a 44 px strip 12 px from the next and 18 px from the workspace's edges,
  its bar centred over its whole height with 12 px at its sides. A title bar is 36 px at the least (compact
  density's 32 grows), a panel body pads 12 px at the least in either density (the plan canvas, the Roles canvas and
  the design board's 10 px too). The quiet layout gives the strips their full height and the page above them the
  rest. Orchestra's Goal panel is 10 rows taller for its three-line goal boxes, so every field and Run still fit.
- `tests/test_studio_textboxes.py` (full tier; driver `tests/helpers/studio_textboxes.py`): on the Prompt panel,
  Orchestra's goal form and Roles' Lineup tab every box is three lines empty, grows with four, stops at twelve and
  scrolls, and its placeholder fits; the composer fills the panel over a short feed and is its own size under a long
  one; TextBox is the only `<textarea`; on Fleet and Session with every panel collapsed each strip is >= 40 px, 12 px
  apart, its bar centred, and an open panel's bar is >= 36 px with its body padded >= 12 px
  (`tests/helpers/studio_strips.py`).

#### Docs
- STUDIO-shell.md (the text box rule beside the Field spec, the strip's and the body's sizes), STUDIO-sections.md (the Prompt panel's box, the Lineup and
  Assignment tabs' `?`), EXTENSION_API.md (`TextBox` in `api.lib.ui`).

### R4: instrument is the default, until you change it

The owner: "instrument theme should be the default theme for halo unless a user changes it." L1 drew instrument only on
a dark system with `theme` unset; now unset means instrument everywhere, and "Follow the system" is a choice you save.

#### Changed
- `theme` unset is `instrument` for every surface: Studio on a dark AND a light system (`:root` and the page with no
  attribute, the server's first paint, `main.tsx`'s fallback), and the terminal (`theme.DEFAULT_THEME`, `instrument-ansi`
  on a terminal without truecolor; `claude-dark` before). `halo config get theme` with it unset prints
  `(unset: instrument)`. The registry names it (`palettes.DEFAULT`) and `GET settings/themes` sends it (`default`).
- `theme: auto` is a value the key takes ("follow the system": instrument on a dark system, paper on a light one); the
  header's and Settings -> Themes' **Follow the system** write it (they cleared the key before) and are marked current
  only while it is saved; with the key unset the mark sits on instrument. `/theme auto`, `halo config set theme auto`,
  the config schema and the Settings row take it; a terminal draws the default for it. `halo config unset theme` is the
  way back to the default. Setup's Theme block says "Nothing saved yet: halo and Studio draw instrument".
- The TUI snapshots under `docs/harness/tui-snapshots/` are drawn in instrument now (re-rendered by `test_tui.py`).

#### Docs
- CONFIG.md `theme` (unset = instrument; `auto` follows the system), STUDIO-shell.md and STUDIO-sections.md (the theme
  menu and the Themes page), GLOSSARY.md and its packaged twin (palette, posture).

### R5: the guided first run belongs to custom lineups

The owner: "If I have a model selected for auto, then it just tests that 1 model a bunch of times and not really has
value ... If the user is on auto then that shouldn't happen." On the Auto lineup (or none) every part is one model
picked per task, so the guided first run would rehearse one model five times.

#### Changed
- `halo start` on the Auto lineup (or none) prints "Your lineup is Auto: the guided first run would rehearse one model
  five times. Build a lineup or a workflow in Roles (Agents from 3.3.16.0) and test it there.", offers `halo gym
  --quick`, writes nothing and exits 0 (`--json`: `{ok, ran: false, reason: "auto_lineup"}`); `--lineup <name>` or an
  active custom lineup runs as before (`halo_harness/start/auto_gate.py`).
- The same rule everywhere the start is offered: `halo init`'s wizard Summary and console offer (`--yes` included), `halo
  check` (`--all` and `--explain` leave it out, `--start` prints the line), the TUI's `/start`, Setup -> Check (no row;
  `start_auto` in `GET setup/state`) and Setup's Summary, and Studio's Start here (no Run button; `auto` in `GET start`;
  `POST start` and a Check with `start` answer 422 `auto_lineup`). The card and its costs are unchanged for a custom
  lineup.

#### Docs
- COMMANDS-init.md and HANDBOOK.md (where the test lives now: `halo start` for a custom lineup; Agents -> Runs adds "Test
  this lineup / workflow" in 3.3.16.0), WIZARD.md and STUDIO-setup.md (the row on Auto).

### R6: init ends with both running

The owner, on Kali: "during init the halo harness cli closes ... the terminal part never launched just the gui." The
wait counted a busy Studio as gone (ten failed GETs while a check or the guided first run held it up), so `halo init`
ended, and Setup's Done had no terminal to start halo in and said nothing.

#### Changed
- `halo init` on a terminal stays until Setup is done, then becomes the session: its line is "Setup is open in your
  browser: <url>. This terminal starts halo when you press Done there (Ctrl+C: stop here; `halo` later starts it).";
  failed GETs while Studio's port still answers no longer count toward "Studio closed" (only a silent port does); on
  Done it prints the Summary's lines and "Setup is done: halo starts here, paired with Studio at <url>", then starts
  halo in this terminal (the same home, so the session shows in Studio's Session section). Ctrl+C prints the stop line
  and exits 0.
- While it waits, init keeps `~/.halo/setup-wait.json` (its pid; `studio/init_waiting.py`), and Studio's Done answers
  who starts halo (`starts`, `line`): "halo is starting in your terminal" while an init waits; with none waiting it
  opens a terminal running halo (`studio/halo_terminal.py`: a console on Windows, Terminal on macOS, `$TERMINAL` then
  qterminal, xfce4-terminal, gnome-terminal, ... with a display on Linux) or says "no terminal found to start halo in;
  run `halo` yourself" in an error toast -- never silent. The Summary's Done note says which (`init_waiting` in
  `GET setup/state`).
- The console flow (`--yes`, no TTY), `--no-launch` and a terminal wizard that starts nothing end on one line: "Start
  halo with `halo`; `halo studio` opens Studio beside it, and the two pair on their own".

#### Docs
- COMMANDS-init.md, WIZARD.md and STUDIO-setup.md: the terminal waits, both come up, and what Done says.

### R7: the guided first run runs the lineup you picked

The owner, on Kali: "The whole init guided first run doesn't even use the orchestration you picked from earlier in
init. It keeps mentioning my-halo-dev-cycle." `halo start` copied the shipped `halo-dev-cycle` to `my-halo-dev-cycle`
and ran the Orchestra sample on that copy whatever the Team step applied, and every surface named the copy.

#### Fixed
- `halo start` (and Setup's Check row, Studio's Start here, the TUI's `/start`) rehearses the active lineup (`team` in
  config.json), or the one `--lineup <name>` names, read as it is: nothing is copied, `my-halo-dev-cycle` is never
  written (one left by an earlier run stays where it is), and `start.steps.DEFAULT_LINEUP` is gone
  (`halo_harness/start/lineup.py` `pick` / `parts`).
- A name with no lineup behind it is one line and exit 1: "no lineup named X; `halo teams` lists them" (`--json`:
  `reason: "no_lineup"`; Studio's `POST start`: 422). On the Auto lineup the line is now "Your lineup is Auto: pick or
  build a lineup in Roles first, then `halo start` rehearses it." (`--explain` too).
- The lineup's own cards play the parts: the lead is its `main` card (the lead's model on a real run), and each of the
  sample's lanes goes to a card that writes code (a `coder`, `implementer` or `subagent` role or alias, or a card used
  for implement or fix), in turn, as many as its `instances`; each job of the plan takes that card's bio (and the model
  it pins), and the workers run under the lineup (`--team`). Fewer lane slots run the sample in that many lanes, one
  line says so; a lineup with no such card says so and exits 1 before writing anything (`reason: "no_coder"`, 422 in
  Studio).
- The lineup step, the plan, the run, the report and the summary name the lineup and its cards; the card names the
  lineup it rehearses, its lead and lane cards, the distinct models it will call with their prices, and an estimate
  priced lane by lane (`start/card.py`); its "writes" line and the Setup Check row's read "a sample repo under
  ~/.halo/start/<date>/ (your lineup is not touched)". The gym row's candidates come from the same lineup.

#### Docs
- COMMANDS-init.md, HANDBOOK.md, GLOSSARY.md ("lineup", "guided first run"), STUDIO-shell.md, STUDIO-setup.md and
  WIZARD.md: the run rehearses your lineup; no copy anywhere.
