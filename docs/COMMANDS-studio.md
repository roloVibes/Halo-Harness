# Commands: Studio, design, media, Orchestra and teams

Read this when you open Studio or run designs, media, an Orchestra goal or a team from the command line.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo studio`

3.0.2.0: `halo studio --stop` ends a Studio running in the background (the
wizard's Open Studio buttons start one, detached); a second `halo studio`
while one runs reuses it (prints the URL, opens the browser) unless
`--port` asks for another. 3.2.2.0: the last halo session to quit ends the
Studio as well, and `halo update` stops it before installing. 3.4.1.1: only a
Studio a session started for itself; one you start on your own (`halo studio`)
is never stopped by a session's quit (the quit line
says "left running: Studio (started on its own; halo studio --stop)").


```sh
halo studio [--mode session|agents|local|packs|setup|settings|glance|<pack>--<section>] [--port N] [--no-open] [--cwd DIR]
halo studio --edit bio:<name> | lineup:<name>[:<block>] | team [--no-open]
halo studio --session [<id>] [--prompt] [--no-open]
```

### `--session`

3.1.4.0: `--session [<id>]` opens the **Session** section (`Alt+1`, this
session, live: the agent tree, activity, attention and agent inspector scoped to
this harness, and the session's Cost) on the session `<id>` names (a prefix
of a live session's id will do). Without `<id>` it is the newest live
session on this harness; with none live, Session opens on its Start view and
the command says so. The session rides in the URL as
`?mode=session&session=<id>`. Like `--edit`, a Studio already running for
this home is reused: every open page switches to Session on that session
(`POST /api/focus {mode, session}`); with no page open the browser opens the
URL, with no browser the URL is printed, and with none running one starts
(`halo studio --session <id>` in the background). `--no-open` only prints the
URL; `--edit` with `--session` is exit 2. The TUI's bare `/studio` runs the
same thing on the session you are in.

### `--prompt`

3.3.11.0 R1: with `--session [<id>]` (or alone: the newest live session) Studio opens Session on that session with
its **Prompt** panel up and the keyboard in its box, to type into the session as in the terminal
([Studio: the Prompt panel](STUDIO-session.md#the-prompt-panel-33110-r1)). It rides in the URL as
`?mode=session&session=<id>&prompt=1`, and a Studio already running gets it in the `focus` frame
(`POST /api/focus {mode: "session", session, prompt: true}`); in Studio itself `Alt+Enter` or the palette's
"Prompt: type into this session" does the same.

### `--edit`

3.1.1.0: Studio is the one editor of bios and lineups, and `--edit TARGET`
opens it on one: `bio:<name>` (Agents on Cast, the Bios panel on that bio's form),
`lineup:<name>` (Agents on Cast, that lineup open, the Inspector on its Lineup tab's summary; 3.3.16.0 R1b:
`lineup:<name>:<block>` opens that block's page, a block being `description`, `workers`, `schedule` or one of the
nine sections) or `team` (Agents on Live; 3.3.16.0 R1: the Team section went, 3.4.0.0 D: Runs too); 3.3.0.0 R4: `setup`, `setup:first` (what
`halo init` opens: `?mode=setup&first=1`) and `setup:<block>` (`halo setup
team`: `?mode=setup&block=team`), [STUDIO-setup.md](STUDIO-setup.md). The target rides in the URL as
`?mode=roles&edit=bio:<name>` (the token stays in the `#t=` fragment). When
a Studio already runs for this home, it is reused: every open Studio page
switches to the target and no tab opens (`POST /api/focus`, a `focus` frame
on the live feed); with no page open the browser opens the URL, and with no
browser the URL is printed. With none running, `halo studio --edit` starts
one as usual, on the target. `--no-open` only prints the URL. A target that
is not one of the three shapes: exit 2 with the reason. `halo agents edit`,
`halo teams edit`, the TUI's `/edit` and `e` in the terminal's bio and
lineup views run the same thing (see
[AGENTS.md](AGENTS.md#editing-bios-and-lineups-studio-is-the-editor-halo-3110)).

Halo 2.1.0, modes in 3.0.2.0: opens Halo Studio, the browser GUI, straight
into a section: 3.3.16.0 R1: `--mode agents` (Team, Roles and Orchestra in one: Cast, the lineups and agent bios as an
editable graph; Live, what runs now, a goal run included; 3.4.0.0 D: Runs, the run console, went), and `--mode roles`,
`orchestra` and `team` still open Agents on Cast, Live and Live, printing the new door once ("Roles is Agents -> Cast now (Alt+2 in Studio; halo studio --mode agents)");
3.2.0.0 R7: `--mode packs` (the Pack Manager; `?mode=packs` in the URL);
without `--mode` it opens in the mode you used last; 3.3.13.0 R2: `--mode <pack>--<section>` opens a running pack's
section (`--mode design--design`, the design pack's), and `--mode design` with that pack off says how to turn it on.
3.4.1.0 R4: `--mode glance` opens the glance (`?mode=glance`), one phone-width page of this Studio -- what runs now,
what waits on you as large buttons, the spend against its cap -- and says under the URL how a phone reaches it: through
an SSH app's forward of Studio's port when an SSH server answers here, else that the page is this-machine-only
([STUDIO-live.md](STUDIO-live.md#the-glance), [REMOTE.md](REMOTE.md#the-glance-from-a-phone)).
The TUI's `/roles` (Agents on Cast) and, with the design pack on, `/design` are the same doors from a live session. It Starts a loopback-only server on a free port (or
`--port`), prints its URL (the URL carries a per-launch token: open exactly
that) and opens the browser unless `--no-open`; `--cwd` is the project
directory for project-scope files (default: the current directory). Ctrl+C
stops it. Over SSH, forward the printed port and open the same URL. The
TUI's `/studio` serves the same page from the running session. See
[STUDIO.md](STUDIO.md).

## Design: a pack

Halo 3.3.13.0 R2: Design is the **design pack** Halo ships, and the `halo design` verbs are gone: each is a panel or a
route of the pack's Design section (`/api/packs/design/design/...`; `GET crafts?probe=1` is the old `doctor --probe`).
`halo design ...` prints one line saying so. Turn the pack on and open it:

```sh
halo pack install design
halo pack enable design --grant-all
halo studio --mode design--design             # or /design in a session (/design url prints the address)
```

Halo 3.0.1.0 made it, as Halo Design. A project is a folder of artboards (an
`index.html` prototype, or a craft app's render plus its source) with
versions, pinned comments, knobs (`controls.json`) and a design system
(`system.json`). `run` is one design turn: a headless Halo session in the
project folder, on the project's model, with the file tools and every
registered craft app (DesignCraft, VectorCraft, PhotoCraft, LightCraft,
EffectCraft, FilmCraft, PdfCraft, and ComfyUI after `halo media init`) as its tools; afterwards every changed
artboard gets a new version and the turn's cost is logged. `sync` reads CSS
custom properties, a Tailwind config, `tokens.json` files and component
names from a codebase, or a page's stylesheets from a URL. See [the design pack's
README](../halo_harness/templates/packs/design/README.md) and its docs/DESIGN.md.

## `halo media`

```sh
halo media init [--url U] [--install-workflows] [--yes]   register mcpServers.comfyui (user scope) and store comfy.url
halo media doctor [--url U] [--smoke] [--timeout S]       the server, model folders, saved workflows, the starters, the entry
halo media serve                                         the ComfyUI MCP server on stdio (what the entry runs)
halo media inspect <workflow> [--json] [--url U]         a workflow's nodes, titles, literal inputs and set keys
halo media models [image|video|audio] [--url U]          rescan the server and print the media-model inventory (as halo models --media)
halo media workflows [--url U]                           workflows saved in ComfyUI and the Halo starters
```

Halo 3.0.4.0: ComfyUI as the eighth craft app. `init` writes
`mcpServers.comfyui` (a stdio server, `python -m halo_harness.media.comfy_server`
with `COMFY_URL` in its env) through the same writer `halo mcp add` uses, and
`comfy.url` into `~/.halo/config.json`; `--install-workflows` saves the
starter workflows into ComfyUI's workflow browser, asking once when a starter
of the same name is already there (`--yes` overwrites). `doctor` exits 1 when
the server is unreachable or the smoke render fails; `--smoke` renders a
64x64 image through the text-to-image starter (`--timeout` seconds, default
900) and prints the output name and the elapsed time. The URL is `--url`,
else `COMFY_URL`, else `comfy.url`, else `http://127.0.0.1:8188`. Every
session then has the `mcp__comfyui__*` tools. See [COMFYUI.md](COMFYUI.md).

## `halo orchestra`

```sh
halo orchestra new [--what T --done-when T --stop-when T] [--workers N] [--test CMD] [--file F ...] [--lineup L] [--goal FILE] [--repo DIR]
halo orchestra status [RUN] [--repo DIR]           the goal, the workflow's steps, live claims, the last events
halo orchestra claims [RUN] [--repo DIR]           every live claim: key, holder, state, expiry
halo orchestra log [RUN] [--since N] [--repo DIR]  the timed run log
halo orchestra runs [--repo DIR]                   every run of this repo, oldest first
halo orchestra run [RUN] [--model REF] [--dry-run] [--force] [--repo DIR]   split, workers, merge, tests, gate, report
halo orchestra lanes [RUN] [--repo DIR]            every worker lane: state, pieces sent back, cost, holder
halo orchestra report [RUN] [--repo DIR]           the run's report and its checks
halo orchestra stop [RUN] [--reason T] [--repo DIR]  ask a running run to stop at its next step
halo orchestra run [RUN] --review [--repo DIR]     3.0.9.0: pause after the split until the plan is approved
halo orchestra plan [RUN] [--repo DIR]             the plan of a review run as a table (3.1.2.0: a Cost column and the
                                                   forecast's total against the goal's budget_usd), its problems
halo orchestra approve [RUN] [--file F] [--repo DIR]  check the plan (F, else Studio's draft, else the split); the run takes it
halo orchestra reject [RUN] --reason T [--repo DIR]  the waiting run stops with the reason
halo orchestra coach [RUN] [--model] [--apply ID [--yes]] [--json] [--repo DIR]   3.0.9.0: the coach's card (halo coach)
```

Halo 3.0.3.0: the Orchestra, several agents editing the same files without
losing a change. `new` writes `<repo>/.halo/orchestra/<run-id>/` with
`goal.json` (WHAT YOU WANT / DONE WHEN / STOP WHEN, asked on a terminal when
not given as flags), `workflow.json` (the designed graph) and an empty
`events.jsonl`. Inside a run (`HALO_ORCHESTRA_RUN`) Write and Edit on the
goal's files go through claims, and the `OrchestraClaim`/`OrchestraRelease`/
`OrchestraClaims`/`OrchestraNote` tools appear. RUN is a run id, a unique
prefix, or a folder; the latest run when omitted. See [ORCHESTRA.md](ORCHESTRA.md).

`run` drives the whole pipeline: the lead splits the goal into jobs (one
model call, checked by code), each job gets a git worktree and a worker
(`halo -p` in that worktree, the run and lane in its environment), the
worker branches merge into `orchestra/<run-id>` one at a time (a conflict
goes to a fresh judge, its answer applied by code and checked by the
tests), the gate runs the tests and sends a failing piece back up to
`return_cap` times, and `report.json` lists the checks. One line per step
prints as it happens, then the report; exit 0 finished, 1 stopped.
`--dry-run` prints the lead's split only. `--model REF` sets the model for
every part (default: each role's model). `/orchestra` shows the same run in
the TUI.

Halo 3.0.7.0: before the split (and before `--dry-run`), the run-start
preflight checks the run's lineup (the goal's `lineup`, else the active
team): a model id its provider's catalog does not know, an assignment
naming a missing bio, a bio whose `tools.allow` is an empty list, a `tiers`
problem. It prints every problem with its fix and exits 2; `--force` runs
anyway. `halo doctor --roles` prints the same list for the active lineup.

## `halo work`

```
halo work [RUN] [--json]     the units of any run of any kind, as one table
```

Halo 3.1.2.0: an Orchestra lane and a supervisor goal
are both a *unit* of work (one model underneath, see
[WORK.md](WORK.md)). `halo work` prints the units of any run -- an Orchestra
run or a goal -- as one table: the kind, the
unit, its state, its cost, its attempts, its gate and its base. `RUN` is a
run folder, a run id or an id prefix; with no `RUN`, the latest run of this
repo. `--json` prints the rows. Read only; no model is called.

## `halo coach`

**The coach pack's verb since 3.4.0.0** (`halo pack install coach`, then `halo pack enable coach --grant-all`;
with the pack off it is one line that says so). Its settings are `packs.settings.coach.<key>` (Settings -> From
packs), no longer the core keys `coach.*` / `improve.*`; [the pack's README](../halo_harness/templates/packs/coach/README.md).


```
halo coach [RUN] [--json] [--repo DIR]           the post-run coach's card for a run of any kind
halo coach [RUN] --model [--refresh]             the run's lead explains each card in one paragraph
halo coach [RUN] --apply ID [--yes] [--json]     write the change card ID names, after the confirm card and y/N
halo coach [RUN] --probe [--k N] [--yes] [--json]  3.1.6.0: try two candidate overlays first, then one card
halo coach --undo [APPLY_ID] [--json]            put back the file of an apply (default: the last one not undone)
halo coach library [list] [--json]               3.1.6.0: the improvement library: one entry per Apply
halo coach library show ENTRY [--json]           an entry's EXPERIENCE.md and the files it keeps
halo coach library forget ENTRY [--yes]          delete an entry's folder (after y/N)
```

Halo 3.1.3.0: the coach's loop in one command (see [ORCHESTRA.md, "The
coach"](ORCHESTRA.md#the-coach)). `RUN` is a run folder, a run id or an id
prefix of an Orchestra run; with no `RUN`, the latest run, as `halo work` finds it. The card
lists each suggestion with its id, its why lines, what Apply writes, its
**applied** / **undone** state and, once asked, the lead's paragraph.

- `--model` asks the run's lead (its lineup's lead role and model) for one
  paragraph per card, kept in `<run>/coach.ask.json`; a second `--model`
  reads them back with no call, `--refresh` asks again. A model error is
  one line on that card; the command still exits 0.
- `--apply ID` prints the confirm card -- the file, whether Apply creates
  it, the before -> after diff -- and asks `Apply this change? [y/N]`;
  `--yes` skips the question. With `--json` and no `--yes` it prints
  `{preview, applied: null}` and writes nothing. The change goes through the
  writer Studio's editor uses (a bio, a lineup, the run's plan draft) and is
  recorded in `~/.halo/coach/applied.jsonl`.
- `--undo [APPLY_ID]` restores the file's text from before the apply when
  the file still holds what the apply wrote; otherwise it exits 1 with the
  reason and writes nothing.
- `--probe [--k N]` (3.1.6.0, an Orchestra run with its report) prints the
  cost line first ("probe: 2 runs, up to $X") and asks `Run the probe?
  [y/N]` (`--yes` skips; `--json` without `--yes` prints the estimate and
  runs nothing). It then runs the goal again under the lead's candidate
  overlays (k pairs; `coach.probe.k`, each run capped at the run's cost x
  `coach.probe.budget_factor`), prints each step, the contrast table and the
  pick; the probe's card then leads the run's card (`--apply probe-<ts>`
  writes it, `--undo` puts every file back). See [ORCHESTRA.md, "Probes"](ORCHESTRA.md#probes).
- `--json` prints the result; every suggestion carries `paragraph` (null
  until asked), `paragraph_error` and `applied`; 3.1.6.0 the result carries
  `library` and `library_line`, each suggestion `library_hits`.
- `library` (3.1.6.0, caught before the run: no run is named `library`):
  every Apply leaves an entry in `~/.halo/coach/library/<entry>/`
  ([ORCHESTRA.md, "The library"](ORCHESTRA.md#the-library)). `list` (the
  default) prints one line per entry -- id, when, project, lineup, source
  (`apply` or `probe`), the title, `(undone)` and `(from <harness>)` when they
  apply; with no entry it says how one is born. `show ENTRY` prints its
  EXPERIENCE.md and the files it keeps; `forget ENTRY` asks `[y/N]` (`--yes`
  skips) and deletes the folder. Exit codes: 0 done, 1 no such entry or
  nothing deleted, 2 usage.

The kind verb `halo orchestra coach` takes the same `--model`, `--refresh`,
`--apply`, `--yes` and `--json`. Exit codes: 0 done, 1 no such run, a change
that cannot be made or a refused undo, 2 usage. `/coach` in the TUI runs the
same command.

## `halo team` (left in 3.4.0.0)

The team file (`.halo/team.yaml`) and `halo team` left the core in 3.4.0.0; `halo team` answers one line
saying so. A lineup's tiers and blocks (Agents -> Cast, `halo teams`) and a run's lanes with their owns lines
(a goal run on Agents -> Live, `halo orchestra`) do its job.

## `/tasks` (Ctrl+T)

Halo 2.0.2 round 3: a full-height panel listing every running, queued,
background and finished sub-agent of this session (position/role, model,
status, elapsed, tool count, cost, and its place in the tree),
plus a second tab for the shared task board (`TaskCreate`/`TaskUpdate`/
`TaskList`). Enter opens a live transcript viewer of the highlighted
agent's own log; `Tab` switches tabs; Ctrl+T or Esc closes it. The Agent
tool's own `count`/`batch` parameters spawn several sub-agents in one
call (capped at `agents.max_concurrent`, excess ones queue); see
[SUBAGENTS.md](SUBAGENTS.md) for the full picture.

## `halo completion`

```sh
halo completion bash
halo completion zsh
halo completion powershell
```

Halo 2.0.2: prints a shell-completion script for the `halo` command
itself -- every top-level subcommand, every known role name
([ROLES.md](ROLES.md)), and every model ref already cached under
`~/.halo` (`models.json`/`dbx-endpoints.json` -- read as plain files, no
network call of its own). `eval "$(halo completion bash)"` (or `zsh`) in
your shell's rc file, or dot-source the `powershell` form from your
`$PROFILE`.
