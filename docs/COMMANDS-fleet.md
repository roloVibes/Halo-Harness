# Commands: remote control and the fleet

Read this when you control sessions remotely or run a fleet and its missions.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo remote`

Halo 2.0.9. Remote control of a running session, and the Signal bridge that
lets a phone drive one. The full description (the control socket and its wire,
the threat model, setup per OS, pairing, signing, the chat commands, a live
checklist) is in [REMOTE.md](REMOTE.md). Every `signal` verb takes `--json`
(one JSON object on stdout); exit codes are 0 done, 1 could not do it (the
reason on stderr), 2 usage. A bare `halo remote signal` prints the verb list.

### `halo remote sessions`

Lists the live sessions that opened a control socket (every session does
unless config `fleet.enabled` is false or it is private; before 3.0.5.0 this
was config `remote.enabled`): session id prefix, pid, kind (`tui`, `print`,
`paperclip`, `orchestra-worker` or `flow`),
permission mode, age, working directory, endpoint and title. Entries whose
process is gone or whose endpoint refuses a connection are pruned first. It
prints nothing secret (the Windows loopback token is never shown). With none
live it says so and exits 0; any other `halo remote` argument prints the
usage line and exits 2.

```sh
halo remote sessions
```

### `halo remote agents | steer | stop`

Halo 3.0.5.0 (Fleet). One live session's agents from a terminal, over its
control socket. `<session>` is a session id or a unique prefix of one;
every verb takes `--json`; exit 1 when the session is unknown, unreachable
or refuses the command (the reason on stderr).

- `halo remote agents <session>`: the agent tree, one line per agent
  indented under its parent: id, name, state, cost so far, model, what it
  is doing.
- `halo remote steer <session> --agent <id> [--redirect] <text>`: a note
  that agent reads before its next model call; `--redirect` replaces the
  rest of its task (`--agent main` steers the main agent).
- `halo remote stop <session> --agent <id> [--reason <text>]`: stop that
  agent and every agent under it at the next tool boundary; its parent gets
  the stopped hand-back and carries on (`--agent main` interrupts the turn).

```sh
halo remote agents 3f2a
halo remote steer 3f2a --agent 9c41d2e0 "skip the docs, fix the test first"
halo remote stop 3f2a --agent 9c41d2e0 --reason "wrong folder"
```

Each command goes out with `by` = `fleet.name` and `via` = `halo remote`,
recorded in the agent's transcript. See [SUBAGENTS.md](SUBAGENTS.md).

### `halo remote signal setup`

Asks for the identity model (`--model dedicated`, the default and the
recommended one, or `--model linked`), then finds signal-cli 0.14.9 (an
earlier `setup`, or on `PATH`) or offers to download it into
`~/.halo/remote/signal-cli/dist/`. The download needs a yes (`--yes`);
`--no-download` only looks; `--binary PATH` uses a signal-cli you already have;
`--jvm` forces the JVM build (JRE 25) even on Linux x86-64, for a proxied host.
Linux x86-64 gets the native build, every other OS the JVM build; the `.asc` is
checked with `gpg` when present. Writes `~/.halo/remote/signal.json` and sets
`remote.signal.enabled`. Never installs system-wide.

### `halo remote signal register`

`halo remote signal register +15555550123` registers the dedicated number: it
prints the captcha page when Signal asks for one; pass the token with
`--captcha`; `--voice` asks for a call (only after an SMS was requested); `--code`
completes the registration; `--pin` supplies the registration-lock PIN of a
number that already has one. A Signal rate limit prints `retryAfterSeconds`.
The registration-lock PIN reaches signal-cli through its JSON-RPC stdin (`setPin`,
and `verify` when signal-cli offers it), never on the command line; only when
signal-cli has no such method for `verify --pin` does `--pin` go on argv, and then
the command says so. After `--code` a registration-lock PIN is set and kept in
`~/.halo/remote/registration-pin` (0600).

### `halo remote signal link`

Links signal-cli as a device of your own Signal account: prints the
`sgnl://linkdevice` URI and draws it as a QR code (half-blocks; `--ascii` for
`#`), waits for the scan (`--timeout` seconds, default 180), and stores the
account with the `linked` identity model. `--name` sets the device name.

### `halo remote signal run`

Runs the bridge in the foreground. `--daemon` writes the service-manager file
for this OS (a systemd user unit, a launchd plist or a Task Scheduler XML)
under `~/.halo/remote/` and prints the one command that enables it; it never
enables it. `--os` writes the file for another OS. Does nothing while
`remote.signal.enabled` is false.

### `halo remote signal pair`

Lists the contact requests (number, ACI prefix, safety number) and clears the
bridge's notices (a changed safety number, a rate limit). `--approve N` (a
number from the list, or an ACI prefix) issues the six-digit code and, waiting
up to `--wait` seconds (default 600), prints the 32-word signing phrase and the
`halo-remote://` link as text and a QR code once the phone has sent the code.
This screen (and the `/remote` dialog) is the only place the phrase is shown: the
chat reply to the phone is just "Paired. Your signing phrase is on the Halo screen."

### `halo remote signal peers`, `unpair`, `reverify`

`peers` lists the paired phones (never their secrets). `unpair <aci-prefix>`
removes one with its secret. `reverify <aci-prefix>` trusts a blocked phone's
new safety number (the running bridge finishes the step).

### `halo remote signal status`, `off`, `on`

`status` shows the bridge (state and pid), the signal-cli version against the
pin, the account, the phones and the last command's time. `off` is the kill
switch: it asks a running bridge to exit (a stop file it polls) and sets
`remote.signal.enabled` to false; `on` sets it back.

## `halo fleet`

Halo 3.0.5.0 (Fleet, round R2). One machine runs a hub; other harnesses join
it with a six-word code; each joined harness shares what it chooses
(`fleet.share`) and accepts control only as its owner allows
(`fleet.allow_control`). The full description (share and control levels, the
owner's card, TLS and HMAC, what never leaves a machine) is in
[FLEET.md](FLEET.md). Every verb but the table takes `--json` (one JSON
object on stdout); exit codes are 0 done, 1 could not do it (the reason on
stderr), 2 usage.

```sh
halo fleet [--once] [--json]
halo fleet serve [--port N] [--bind ADDR] [--name NAME] [--no-tls] [--json]
halo fleet pair [--ttl 10m] [--ascii] [--json]
halo fleet join <host:port|url> --code "<six words>" [--share status|events|full]
                [--allow-control none|ask|all] [--fingerprint HEX] [--json]
halo fleet leave [hub] [--json]
halo fleet status [--json]
halo fleet members [--json]
halo fleet kick <name> [--json]
halo fleet record <sid> [--agent <aid>] [--out PATH] [--json]
halo fleet digest [--since 2h|45m|1d|<unix seconds>|<ISO time>] [--json]
halo fleet capabilities [name] [--refresh] [--tools] [--json]
halo fleet who "<query>" [--json]
halo fleet mission new "<goal>" [--prefer a,b] [--budget N] [--constraints "..."] [--test CMD] [--no-repo] [--json]
halo fleet mission plan|edit|approve|run|status|stop|report|open <id> ... [--json]
```

### `halo fleet` (the live table)

Every harness, session and agent this machine sees, one row per agent
(harness, session, agent indented under its parent, state, what it is doing,
cost), redrawn every 2 s: Up/Down select, `s` steer, `k` stop (asks y/N),
`p` pause or resume, `r` refresh, `q` quit. It reads Studio's `GET
/api/fleet` when Studio runs, else the hub this machine serves, else this
harness alone. `--once` prints the table once (also what a pipe gets);
`--json` prints the view. `/fleet` in the TUI is the same table.

### `halo fleet serve`

Starts the hub. With a Studio running it starts inside Studio's process (and
stops with it); otherwise it runs here until Ctrl+C. `--port` (default
`fleet.hub.port`, 7430; `0` picks a free one), `--bind` (default `0.0.0.0`),
`--name` (default `fleet.name`), `--no-tls` (HMAC-signed plain HTTP even
when the `cryptography` package would allow TLS). Offline mode refuses it.

### `halo fleet pair`

A one-time code for this machine's hub: six words, good for one harness,
`--ttl` long (default `10m`; `90s`, `1h`), printed with the exact `halo
fleet join` line, a QR code (`--ascii` draws it with `#`) and the
certificate fingerprint.

### `halo fleet join`

Joins a hub (`host:port`, or `http(s)://host:port`) with `--code` and stores
it in `~/.halo/fleet.json`. `--share` and `--allow-control` set this hub's
own levels (default: the config keys); `--fingerprint` insists on the hub's
certificate (otherwise the one the hub vouches for in its code-checked reply
is pinned). A wrong, spent or expired code is refused.

### `halo fleet leave`, `status`

`leave [hub]` tells the hub and forgets it (every hub when none is named).
`status` shows this harness, each joined hub (does it answer, does it see
this harness online and with how many sessions, its share and control
levels) and the hub this machine serves (members, online, an open code).

### `halo fleet members`, `kick`

On the hub's machine: `members` lists the paired harnesses (name, id, host,
version, share, control, online, when paired); `kick <name>` (or an id
prefix) removes one: its key stops working and its links close within a
second.

```sh
halo fleet pair --ttl 15m
halo fleet join hub-machine:7430 --code "acorn badge cobalt dancer ember frost"
halo fleet status
halo fleet kick bob@laptop
```

### `halo fleet record`

Round R4. Writes a session of this harness as a flight recording: one
self-contained HTML file (inline CSS and JS, the session as a JSON block, no
network at all) with a lane per agent (bars by state, a tick per tool call),
the cost curve, a scrub bar with Play / Pause and a speed, and each agent's
Thinking, Working and Output as they were at the cursor. It reads the
session's transcripts on disk (`~/.halo/sessions`), so a finished session
records as well as a live one; a unique prefix of the session id is enough.
`--agent <aid>` keeps that agent and its sub-agents; `--out PATH` writes
there instead of `~/.halo/recordings/<sid>[-<aid>].html`. A member's session
is recorded from Studio's Fleet section (`POST /api/fleet/<harness>/<sid>/recording`).

### `halo fleet digest`

Round R4. What happened since `--since` (`2h`, `45m`, `1d`, unix seconds or
an ISO time; default `1d`), per harness, computed in code: sessions started
and ended, the cost, the decisions answered from Studio and who answered
them, the files touched, the errors and the hand-offs, and (3.1.3.0) one
coach line per run the post-run coach read ("coach    orchestra <run>: 3
suggestions, 1 applied, top: ..."; `coach` rows in `--json`, from
`~/.halo/coach/runs.json`). This harness is read from its own transcripts; members and decisions come from the hub's journal
(`~/.halo/fleet/journal.jsonl`, written while Studio's Fleet watcher runs).
`--json` prints the same object as `GET /api/fleet/digest`.

```sh
halo fleet record 82eb586a --agent 5848a1cc
halo fleet digest --since 8h
```

### `halo fleet capabilities`

Halo 3.0.6.0 round R6. What each harness can do, as a spec sheet: the
hardware (CPU, cores, RAM, GPU and VRAM, free disk), the models it is best
with and its local ones, its craft apps and ComfyUI models, every MCP server
with its tool count, its skills, command-line tools with their versions,
projects, providers, roles, integrations and tags, with the catalog's age and
hash. `name` picks one harness (its name or id; `local` is this one).
`--tools` lists every MCP tool with its description; `--refresh` gathers this
harness's catalog again (or, through Studio, asks the named member now);
`--json` prints `{ok, source, harnesses: [...]}`, each row with its whole
`catalog`. It reads Studio's `GET /api/fleet/capabilities` when Studio runs,
else the hub this machine serves, else this harness alone (`source`: studio,
hub, local). What a catalog holds and what never leaves the machine:
[FLEET.md](FLEET.md#capabilities-3060-r6).

### `halo fleet who`

Round R6. Which harness can do something, ranked in code: an exact name beats
a word of a name, which beats a word of a description, and a tag counts
double; each harness lists its best matches and why. Exit 1 when nothing
matches (or the query has no word); `--json` prints `{ok, source, q, words,
results}`. `/fleet who <query>` in the TUI prints the same, and `/fleet
capabilities [name]` the spec sheet.

```sh
halo fleet capabilities kali@lab --tools
halo fleet who gridcraft
halo fleet who "a 4090 for video"
```

### `halo fleet mission`

Halo 3.0.6.0 round R7. One goal across every harness: the hub's lead splits
it into parts by what each harness can do, each part runs on its harness
(the `run_task` fleet command, under that harness's `fleet.allow_control`),
repo parts merge one at a time, and a report says who did what and what it
cost. The folder, the plan contract, claims and the shared folder:
[MISSIONS.md](MISSIONS.md).

```sh
halo fleet mission new "<goal>" [--prefer a,b] [--budget N] [--constraints "..."] [--test CMD] [--no-repo] [--json]
halo fleet mission plan <id> [--again] [--json]
halo fleet mission edit <id> <part> (--harness NAME | --drop) [--json]
halo fleet mission approve <id> [--json]
halo fleet mission run <id> [--no-follow] [--force] [--json]
halo fleet mission status [id] [--json]
halo fleet mission stop <id> [--reason TEXT] [--json]
halo fleet mission report <id> [--json]
halo fleet mission open <id> [--json]
halo fleet mission coach <id> [--model] [--apply ID [--yes]] [--json]
```

`new` drafts the mission and plans it, then prints the plan table: each
part's harness (`(pinned)` when only it has what the part needs), its
state, why, its claims and what it waits for. `--prefer` names harnesses that
break a tie (default `fleet.mission.prefer`), `--budget` the mission's dollars,
`--constraints` what every part must respect, `--test` a command run on a
judged merge, `--no-repo` no repo parts even inside a git repo (the repo is
the folder you run it in). `plan` prints the plan (`--again`: the lead plans
it anew); `edit` gives a part to another harness (`--harness`) or drops it
(`--drop`), checked again in code; `approve` approves; `run` approves a
planned mission, runs it and follows it with a live table of the parts by
harness until it ends (exit 0 when done, 1 when it failed or stopped;
`--no-follow` returns at once; the run-start preflight checks this harness's
active lineup first and lists each problem with its fix, `--force` runs
anyway). `status` lists the missions, or one
mission's parts by harness with state and cost; `stop` stops every running
part (`--reason` goes in the report); `report` prints `report.md`; `open`
prints the mission folder; `coach` (3.0.9.0) prints the post-run coach's card
for a mission in this harness's missions folder (3.1.3.0: `--model` asks the
lead for a paragraph per card, see `halo coach`). `--json` prints the route's answer with `ok` and
`source`. They use the running Studio, else the hub this machine serves,
else this harness alone (then `run` follows in this process, which keeps the
mission running). `/mission [id]` in the TUI prints the status.

```sh
halo fleet mission new "Scan the lab subnet and build the findings workbook" --budget 2
halo fleet mission edit m-20261015-3fa2 3 --drop
halo fleet mission run m-20261015-3fa2
```
