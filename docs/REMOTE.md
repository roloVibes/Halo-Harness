# Remote control

Read this when you control a running session from another process, or wire a transport (a phone, a chat) to Halo.

Halo 2.0.9 adds remote control of a running session. This page covers the
per-session **control socket**, the **sessions registry** and the **event
feed** every other door uses, then the **transports** built on them (3.3.13.0:
the Signal bridge is the shipped signal pack), the TUI's `/remote` and status
chip, the command line, `halo doctor` and the config keys.

Contents: [the control socket](#what-the-control-socket-is) | [the event feed](#the-event-feed) |
[the sessions registry](#the-sessions-registry) | [transports](#transports) | [the glance from a phone](#the-glance-from-a-phone) |
[the TUI](#in-the-tui-remote-and-the-status-chip) | [command line](#command-line-reference) |
[doctor](#doctor) | [config keys](#config-keys)

## What the control socket is

Every interactive `halo` session and every `halo -p` run (including `--bg`
runs, which re-run the same invocation, and Orchestra
workers), opens one local socket and lists itself in
the registry. A program that can
reach that socket can do what the keyboard does: send a prompt (or steer the
turn in flight), interrupt, switch mode / model / effort, run a slash
command, answer a permission card, a question, a plan review or an approval
gate, read the status, read the tail of the conversation, and watch the
session's events as they happen. It is the same set of calls the TUI itself
makes on the `Controller`; the socket never injects raw commands into the
agent loop.

**Two switches since 3.0.5.0.** `control.enabled` (default `true`)
opens the control socket and the registry entry for every session, so
Studio and `halo remote` can see it; `remote.enabled` (default `true` since
3.3.13.0) is every transport's switch -- a pack's bridge, the signal pack's
for one, answers and the core's notes go out only while it is on
([Transports](#transports)). Before 3.0.5.0 `remote.enabled` opened the
socket too; until 3.3.13.0 it was the Signal bridge's alone, default false.

```sh
halo config set control.enabled false    # no session opens a control socket
halo config set remote.enabled false   # no transport answers, no note is written (see Transports)
```

Both take effect for sessions started afterwards. **A private session**
registers nothing and opens no socket: start it with `halo --private`
(it sets `HALO_PRIVATE` for its own process, so the Orchestra
workers it starts are private too), turn it on and off in the TUI with
`/private on` / `/private off` (the status bar shows a `private` chip), or
make every session private with `control.private: true`. In the TUI, `/remote`
says whether this session's socket is on (and where) and how many live
sessions the registry holds.

## Where it listens

| Platform | Endpoint | Auth |
|---|---|---|
| Linux / macOS | Unix socket `~/.halo/run/<session_id>.ctl`, mode 0600, directory 0700 | the file mode |
| Windows | loopback TCP `127.0.0.1:<port>` (OS-assigned) | a random 16-byte hex token; the first line of a connection must be `{"token": "..."}` within 5 seconds or the connection is closed. Connections still in that handshake sit in a separate pool of 16 (the oldest is closed for a new one) and only authenticated ones count against the 32 slots; at most 16 connections hold an event feed |

Nothing ever listens on a non-loopback address (`halo host serve` is a separate
listener on its own port that speaks only its own signed protocol: [HOST.md](HOST.md)). The token is never logged or
printed by `halo remote sessions`; on Windows it is stored in the registry
entry (a 0600 file in your own state directory).

An endpoint is written as `unix:<path>` or `tcp:127.0.0.1:<port>`.

## The wire

One JSON object per line, both ways.

```
request   {"id": 1, "cmd": "submit", "text": "run the tests"}
response  {"id": 1, "ok": true,  "result": {"steered": false}}
          {"id": 1, "ok": false, "error": "empty prompt"}
event     {"event": "permission_request", "data": {...}, "turn": 3, "agent_id": null, "ts": 1791699334.1}
```

| `cmd` | Fields | Result |
|---|---|---|
| `ping` | | `{pong, session_id}` |
| `status` | | the status payload (phase, model, context, cost, `permission_mode`, effort), plus `session_id`, `cwd`, `title`, `busy`, `kind` (`tui`, `print` or 3.3.11.0 R2 `headless`), `pid`, `accepts_turns` (a print-mode run started with `--input-format stream-json`, or a headless session: a `submit` runs or queues a turn; absent on a TUI session), `pending` (the ids of unanswered permission / question / plan / approval cards) and, on a headless session, `parked` (`[{id, kind, since}]`, the asks it waits on, oldest first) |
| `submit`, `steer` | `text`; optional `origin` (`{via, by}`), `when_busy` (`steer` / `refuse` / `queue`, `submit` only), `receipt` | `{steered}`; while a turn runs the text steers it (`when_busy: steer`, the default: the Signal bridge's call is unchanged), otherwise it starts the next turn. 3.3.11.0 R1: `refuse` answers `{busy: true, line}` and takes nothing; `queue` answers `{queued: true}` and the session holds that ONE turn until the running one ends (a second: `{busy, held: true, line}`). In `halo -p` the next turn is queued only for `--input-format stream-json` runs |
| `interrupt` | | `{interrupted}` |
| `answer` | `kind` = `permission`, `request_id`, `action` (`allow` / `deny`), optional `scope` (`once` / `session` / `always`), `message`, `rule` | `{resolved}`. With `allow`, `session` / `always` learn the card's suggested rule (or `rule`), as the TUI's buttons do; a `deny` learns nothing whatever its `scope` |
| `answer` | `kind` = `question`, `request_id`, `answer` | `{resolved}` |
| `answer` | `kind` = `plan`, `approved`, optional `feedback`, `mode_after` | `{resolved}` |
| `answer` | `kind` = `approval`, `request_id`, `action` (`accept` / `edit` / `stop`), optional `instruction` | `{resolved}` |
| `mode` | `mode` | `{mode}` |
| `model` | `ref` | `{model}`; an unresolvable ref is `ok: false` with the resolver's sentence |
| `effort` | `level` | `{effort, message}` |
| `slash` | `name` and `args`, or `line` (`"/cost"`) | `{output}` |
| `tail` | `n` (default 20, at most 200) | `{markdown}`: the last n user / assistant messages |
| `receipts` | | `{receipts: [...]}`: the session's receipts ladder (3.3.11.0 R1, below) |
| `subscribe` | optional `kinds` (a list; default all) | `{subscribed: true}`; event frames follow on this connection |
| `unsubscribe` | | `{subscribed: false}` |
| `note` | `name` = `remote.attached`, `peer` (an id prefix), `attached` (true or false) | `{attached: <count>}`; a transport's bridge (the signal pack's) announcing that a phone attached or detached (drives the status chip). A connection that closes takes its phones with it |

An `answer` for a card that is no longer waiting is `ok: false`. A request
that is not valid JSON gets `{"id": null, "ok": false, "error": "invalid JSON"}`
and the connection stays open.

Several clients may connect at once; a subscription belongs to its
connection. Commands that arrive over the socket show up in the TUI transcript
as a `(remote) ...` note, never as a message typed by you; a `submit` with
`origin: {via: "studio"}` says `(from Studio) prompt: ...` instead (3.3.11.0 R1), and its turn's `user_message`
frame carries `via`, `by` and `receipt`.

### Receipts (3.3.11.0 R1)

Every prompt, steer and answer Studio sends a live session (Session's Prompt panel, `POST
/api/sessions/<sid>/command` with `cmd` submit / steer / answer) gets an id and a ladder, kept append-only in
`~/.halo/sessions/<project>/<session id>/receipts.jsonl` (one writer, `remote/receipts.py`; every change is a new full
row `{id, client_id, kind: prompt|steer|answer, sha256, at, sent_at, state, reason?, turn?, seq?}`, the text itself
never, and the last row per id wins):

| State | When |
|---|---|
| `sent` | Studio stored it, before the socket call. A retry with the same `client_id` (the idempotency key) returns the stored row and sends nothing: one turn, never two |
| `delivered` | the session's handle took the text (an answer: before its card resolves) |
| `read` | the message is in the model's input: the loop wrote the user node the request is derived from, and that node carries `receipt` (the turn's first node, or a steer's at the safe point that applies it); the row names the node's `seq` and the turn. The transcript is the evidence, never a timer. An answer has no `read` (its outcome is the tool result the turn goes on with) |
| `replied` | the main session's `turn_done` for that turn (an answer: the turn it answered) |
| `failed` | with a `reason`: `busy` (`when_busy: refuse` while a turn ran), `held` (a second `queue`), `expired` (sent or delivered and unread after 24 hours: a lazy TTL applied when a send or a read touches the file), or the socket's error |

When the session ends (its handle detaches: `/exit`, a `shutdown`, the process ending) a `delivered` row still unread
goes back to `sent` with the reason, and a held queued turn is dropped with one line in the transcript. `GET
/api/sessions/<sid>/receipts` (Studio, the TTL applied) and the socket's `receipts` read the same rows; Studio's
`slash` and `tail` reach the socket's own commands through the same route (`GET /api/sessions/<sid>/slash` lists the
commands). Federation extends the ladder across halos.

## Agent-level commands (3.0.5.0)

The commands above address the whole session. These address one agent:
the main agent (`agent_id` `main`, or the session id), any sub-agent at any
depth (its 8-character id), or a background Bash job (`job:<id>`). They are
what Studio's Agents -> Live and `halo remote agents | steer | stop` send; the
semantics are in [SUBAGENTS.md](SUBAGENTS.md#the-live-agent-tree-and-what-studio-can-do-to-an-agent).

| `cmd` | Fields | Result |
|---|---|---|
| `agents` | | `{agents: [row, ...]}`: the session's live agent tree, parents before children. A row is `{agent_id, parent, name, role, bio, lineup, model, kind, task, since, state, turns, cost_usd, current, last_text, transcript}`; `kind` is `main`, `subagent`, `member` (a team member), `background` or `job`; `state` is `queued`, `running`, `waiting`, `paused`, `done`, `failed` or `stopped`; `current` is the tool in flight with one line of its arguments, or `thinking` |
| `agent_tail` | `agent_id`, `n` (default 100, at most 500), optional `kinds` (a list) | `{agent_id, events: [entry, ...]}`: the last n entries of that agent's own transcript (for `main`, the session's). An entry is `{kind, ...}` with `kind` one of `user`, `text`, `thinking`, `tool_call`, `spawn`, `tool_result`, `handback`, `control`, `note`, `ask`, `error`, `done` |
| `agent_steer` | `agent_id`, `text`, optional `mode` (`nudge`, the default, or `redirect`) | `{agent_id, mode, delivered}`: `inbox` (the agent reads it before its next model call), or for `main` `steer` / `turn` (today's `steer`); a finished agent answers `ok: false` |
| `agent_stop` | `agent_id`, optional `reason` | `{agent_id, stopping: [ids]}`: that agent and its subtree end at their next tool boundary. `main` is the turn-level `interrupt` (`{agent_id, interrupted}`); a `job:` id kills the job (`{agent_id, stopped, message}`) |
| `pause` | optional `agent_id` | `{paused}`: that agent and its subtree (or, with no `agent_id`, every agent of the session) hold at their next tool boundary |
| `resume` | optional `agent_id` | `{resumed, was_paused}` |
| `shutdown` | optional `reason` | `{shutdown: true}`: every agent ends at its next tool boundary, then the session closes: the TUI shows `shut down from Studio by <by>: <reason>` and exits, `halo -p` reads no further turn and returns |
| `agent_follow` | `agent_id`, `on` (default true) | `{agent_id, following: [ids]}`: while on, that agent's entries are also published as `agent_event` frames |

Every one takes `by` (the caller's name: Studio sends `harness.name`, `halo
remote` sends it too) and `via` (default `Studio`). The commands that act
on an agent are recorded in that agent's own transcript as a `meta` node
(`{"control": {"cmd", "by", "via", "agent_id", ...}}`; `"fleet"` before 3.5.0.0, still read); a steer, stop or pause
also leaves one line in the parent's transcript (`"<agent> steered from
Studio by <by>: <first 80 characters>"`) and in the TUI. Old clients see
the same wire: nothing in the earlier commands changed.

## The event feed

After `subscribe`, a connection receives the session's events (the kinds in
`halo_harness/events.py`, payloads untouched) as they are produced, with two
changes: consecutive `text_delta`s are merged into one `text_chunk` frame
(`{"event": "text_chunk", "data": {"text": ...}}`) every 2 seconds or 1800
bytes, flushed early whenever another event arrives so order is kept, and
`thinking_delta` is not sent. The feed is a copy taken where the session emits
events; the TUI's own queue is untouched. (3.3.9.0 R3: a subscriber that
names `text_delta` in its `kinds` gets each delta raw as it streams -- the
voice door and Studio's Talk do, so the first sentence speaks without waiting
for a chunk; no other subscriber sees one.)

**Agent and registry frames (3.0.5.0).** Every frame also carries `session_id` and
`harness` (the harness id). Three kinds join the feed: `agent_state` (a row
of the agent tree changed: data is the row; state, tool, turns or task at
once, text and cost alone at most once a second per agent), `agent_event`
(an entry of an agent someone follows with `agent_follow`) and `registry` (this
session's registry entry (3.5.0.0: named `fleet` before), public fields only, with `action` `register`,
`update` or `unregister`). The first frame of every new subscription is the
session's `registry` frame with `action: hello`. The `subagent_*` frames are
unchanged.

Each subscriber has a queue of 256 frames. A client that stops reading is
dropped (its connection is closed) when the queue fills; the session and the
other clients carry on.

## The sessions registry

`~/.halo/run/sessions.json` lists the live sessions that opened a control
socket:

```json
{"version": 1, "sessions": [
  {"session_id": "...", "cwd": "...", "pid": 1234, "endpoint": "unix:<state dir>/run/<session_id>.ctl",
   "token_env": null, "started": 1791699000.0, "title": "Fix the flaky test", "mode": "default", "kind": "tui",
   "harness": {"id": "5f0c...", "name": "you@laptop", "host": "laptop", "user": "you", "version": "3.0.5.0", "os": "linux"},
   "project": {"root": "/srv/app", "repo": "app", "branch": "main", "dirty": false}, "parent": null}
]}
```

Since 3.0.5.0: `kind` is `tui`, `print` or `orchestra-worker`
(3.3.11.0 R2: or `headless`, below); `harness.id` is a stable per-home id kept in `~/.halo/harness-id` and
`harness.name` is `harness.name` (default `user@host`); `project` is read from
git a moment after the session starts (None fields outside a repo);
`parent` is the session that started this one (an Orchestra worker names
the session that ran the Orchestra, through `HALO_SESSION_PARENT`). An entry
written by an older Halo, without these keys, still loads.

It is written atomically (temp file and replace, under a best-effort lock),
the title follows the session's auto-title or `/rename`, and `mode` follows
mode changes. Entries whose process is gone or whose endpoint refuses a
connection are dropped the next time anything lists the registry, and a
session removes its own entry when it quits (every quit path, including the
Ctrl+C card, plus a process-exit hook for a crash).

```sh
halo remote sessions
```

lists the live sessions (id prefix, pid, kind, mode, age, cwd, endpoint,
title). `halo_harness.remote.client.ControlClient` is a small stdlib client
for scripts and tests.

### A session without a terminal (3.3.11.0 R2)

`halo --headless --session-for studio` ([COMMANDS-main.md](COMMANDS-main.md#--headless---session-for-who)) runs a
whole session whose control socket is its ONLY door: `halo_harness/headless_session.py` builds the controller the
TUI builds (`tui/bootstrap.build_controller`) and starts it without the Textual app; this process drains the
controller's events in the TUI's place, so the feed and the session log are the TUI's own. Its registry row says
`kind: headless` and `parent: studio:<pid>` (the starter's `HALO_SESSION_PARENT` wins over `--session-for`), and Agents
-> Live, the Map, Session and `halo studio --session` list it as a session of this harness.

* **Asks park.** A permission, a question, a plan or an approval waits on the handle until an `answer` comes through
  the socket; `status` lists each under `parked` with the time it was first seen. Studio's Prompt panel answers it with
  the card's buttons; the Attention card is `parked: true`, and while no Studio page is open (Studio's feed
  serves no page) its line ends "-- waiting on you in Studio".
* **It ends** on `/quit` (or `/exit`) through `slash`, on `shutdown` (Studio's **End session**: the turn ends at its
  next tool boundary), on SIGTERM, or when its worker ends; its registry row goes with it. A quit here stops only what
  this process started (a background run, a schedule fire), never the Studio above it.
* **Studio starts it** (`POST /api/sessions/new {model, cwd}`, `studio/sessions_new_api.py`): the child is detached
  the way `studio/launch.py` detaches Studio (no console; its own process group on Windows, its own session on POSIX),
  so closing the tab or stopping Studio never ends it; its output goes to `~/.halo/run/headless/<session id>.log`. The
  session id is chosen by Studio (`--session-id`), so the page opens Session on it before it registers. The children
  are kept in `~/.halo/studio-sessions.json` (`{version, sessions: [{session_id, pid, cwd, model, started, log}]}`,
  private, written under the file lock; a row whose pid is gone is dropped the next read), and `GET
  /api/sessions/started` lists the ones still running with `live` (registered now), so a restarted Studio finds them.

## Transports

Halo 3.3.13.0 R3. A **transport** carries a session somewhere else -- a phone, a chat -- and is a pack: the core
never knows which one. The Signal bridge, Halo's own until 3.3.13.0, is the shipped **signal pack**
(`halo pack install signal`; its README is the whole guide: setting up, pairing in one message, signing, the chat
commands, the threat model, live verification). `halo remote signal ...` now prints one line that points there.

What the core gives every transport, through the extension API's transport seam (`halo_harness.ext.remote`,
[EXTENSION_API.md](EXTENSION_API.md#transports)):

- **the sessions**: the registry's live rows and a client of each one's control socket (this page, above);
- **a session started for it**: a text with no session open starts one (`halo --headless --session-for remote`,
  [a session without a terminal](#a-session-without-a-terminal-33110-r2)). A transport runs as a pack service
  without Halo's provider keys, so it asks the supervisor, which holds them: `remote/session_start.py` writes the
  request under `~/.halo/remote/session-requests/`, `halo supervise` answers it within half a second, and the
  requester waits for the session's registry row (a transport run by hand starts it itself);
- **the notes** (`remote/notify.py`): one seam for what may reach the owner unprompted. The core writes a note only
  while a transport listens (`listen(name)`, a heartbeat at least once a minute, `~/.halo/remote/listeners/`); each
  is one line of `~/.halo/remote/notify.jsonl` (0600, the newest 200, none older than ten minutes) with a `kind`:

  | Kind | Written by |
  |---|---|
  | `asks` | Studio's live watcher: each new row of the attention queue (a card, a waiting agent, a cap, a conflict, the supervisor's parked decisions), as the card's text with the harness name (`live/push.py`); its `session` field lets a transport skip the session it is attached to |
  | `supervisor` | a goal of `halo supervise` that ends, parks, fails or stops (`supervise/queue.set_state`) |
  | `steward` | the Ollama steward's note that asks for attention, read from its journal by the supervisor's tick (`remote/notify_sources.py`) |
  | `turn_done`, `errors` | kept for transports (the signal pack reads them from the attached session's own feed) |

  The transport decides per phone or chat what to pass on (the signal pack's `/notify`);
- **the cards' text** (`remote/cards.py`: permission, question, plan, approval, and the reply parsers), a voice
  note's transcript through the local speech server ([VOICE.md](VOICE.md)), a QR drawing, the live lines (`live_lines`);
- **the switch**: `remote.enabled` (default true since 3.3.13.0): with it false no transport answers and no note
  is written; `control.enabled` still governs the control sockets;
- **a service the supervisor runs** for the transport's own process ([SUPERVISE.md](SUPERVISE.md#pack-services)).

`halo remote transports` lists the transports listening and the switch.

**What moved.** `halo remote signal setup | register | link | run | pair | peers | unpair | reverify | status | off
| on` -> `/signal`, `/signal link`, `/signal register`, `/signal pair`, `/signal phones`, `/signal unpair <n>`,
`/signal reverify <n>`, `/signal off | on`, and Setup -> Signal; `halo remote signal run --daemon` -> the pack's
service under `halo supervise` (`halo supervise --service` for logon); the TUI's `/remote` dialog -> `/signal` and
the Setup pages; `~/.halo/remote/{signal.json, signal-cli/, peers.json, pending.json, audit.jsonl, registration-pin}`
-> the pack's data folder, moved once by its service; the `remote.signal.enabled`, `remote.rate_per_minute`,
`remote.verbosity`, `remote.stale_window_s` and `remote.pair_code_ttl_s` keys -> the pack's settings
(`packs.settings.signal.on | rate_per_minute | verbosity | stale_window_s | pair_ttl_s`; `halo config get|set` of an
old key says its new home). Halo no longer downloads signal-cli: the pack's `requires:` names it with its install
line for each OS.

## The glance from a phone

Studio's glance (3.4.1.0 R4, [STUDIO-live.md](STUDIO-live.md#the-glance)) is one phone-width page of the loopback Studio.
Nothing new listens for it: Studio answers 127.0.0.1 alone (its peer and its Host header), `halo host`
speaks only its own signed protocol, and the control socket above is loopback. The one door from a phone is the one
Studio already prints for another machine -- an SSH forward of its port:

1. On the machine that runs Studio, an SSH server (OpenSSH; on Windows the optional OpenSSH Server) answers on port 22.
2. In an SSH app on the phone, connect to `<you>@<this machine's LAN address>` and forward the phone's local port `<P>`
   to `127.0.0.1:<P>` (the port `halo studio` printed).
3. On the phone, open `http://127.0.0.1:<P>/?mode=glance#t=<token>` -- or scan the code Studio's **Open the glance**
   draws when an SSH server answers here.

The phone's browser then talks to its own 127.0.0.1, so Studio's Host check, the token and the owner proof hold exactly
as on this machine, and the page is a secure context (the owner proof and the browser's notification need one). With no
SSH server answering, **Open the glance** and `halo studio --mode glance` say plainly that the page is this-machine-only.

## In the TUI: `/remote` and the status chip

`/remote` prints the control socket's status in the transcript: this session's socket (or why it has none), the
registry's live sessions, `remote.enabled`, the transports listening, and every pack service the supervisor runs
with its state line. `/remote signal ...` says where the Signal bridge went.

**The status chip.** While a phone is attached to *this* session the status bar shows `⇄ remote 1` (`<> remote 1`
where the terminal has no truecolor), with the number of attached phones. A transport announces an attach or detach
with the control socket's `note` command (below); one that dies takes its phones with it, because the session forgets
a connection's phones when it closes. With no phone attached the chip names the transport that listens (`⇄ signal`),
or the pack service that should run and does not (`⇄ signal/bridge off`), read every fifteen seconds. Text from a
phone appears in the transcript tagged with where it came from.

## Command line reference

Exit codes: 0 done, 1 could not do it (the reason is on stderr), 2 usage.

| Verb | Does |
|---|---|
| `halo remote sessions` | live sessions that opened a control socket |
| `halo remote agents <session>` | that session's agent tree: id, name, state, cost, model, what it is doing (3.0.5.0; `<session>` is an id or a unique prefix) |
| `halo remote steer <session> --agent <id> [--redirect] <text>` | a note that agent reads before its next model call; `--redirect` replaces the rest of its task |
| `halo remote stop <session> --agent <id> [--reason <text>]` | stop that agent and its subtree at the next tool boundary (`--agent main` interrupts the turn) |
| `halo remote transports [--json]` | 3.3.13.0: the transports listening here and `remote.enabled` |
| `halo remote signal ...` | one line: the Signal bridge is the signal pack |

**The control socket's `note` command.** `{"cmd": "note", "name": "remote.attached", "peer": "<id prefix>",
"attached": true}` tells the session a phone attached or detached (`{"ok": true, "result": {"attached": <count>}}`).
The `status` payload carries `remote_attached`, the count. Any other note name is an error.

## Doctor

`halo doctor` (and `/doctor`, `halo doctor --json`) has these rows, in the `[OK]` / `[WARN]` vocabulary:

| id | Checks |
|---|---|
| `remote` | the control sockets (`control.enabled`), `remote.enabled`, the transports listening and the live sessions in the registry |
| `service_<pack>_<name>` | each pack service the supervisor knows: running is OK; an autostart service that is not is a WARN with its line (the signal pack's bridge says what it needs: signal-cli, an account, the supervisor) and `-> fix: halo supervise services` |

`halo pack doctor` names a pack's missing requirement (signal-cli for the signal pack) with its install line. Doctor
writes nothing.

## Config keys

| Key | Default | Meaning |
|---|---|---|
| `control.enabled` | `true` | open a control socket and registry entry for each session (3.0.5.0) |
| `harness.name` | `user@host` | this harness's name in the registry and on the commands it sends |
| `control.private` | `false` | every session starts private, as with `halo --private` |
| `host.allow_control` | `ask` | on a machine that runs `halo host`, the cap on every peer's grant: `none`, `ask` (each request queued for the owner) or `all` |
| `remote.enabled` | `true` | every transport's switch (3.3.13.0; it was the Signal bridge's, default false): false and no pack's bridge answers and no note is written |

The Signal bridge's keys are the signal pack's settings since 3.3.13.0 (`packs.settings.signal.*`, its README).
