# Fleet

Halo 3.0.5.0 "Fleet" puts every harness, every session and every agent in
one live picture: what each one is doing, what it is thinking, what it
wrote, and the controls to steer, pause or stop any of them. **R1** is what
one session exposes; **R2** (this page's second half) is the hub and the
join: one machine runs a hub, others join it with a six-word code, and each
joined harness shares what it chooses and accepts control only as its owner
allows. Studio's Fleet section (the map, the agent inspector, Live Roles) and
the fleet panels come in rounds R3 and R4.

## What a session exposes (R1)

- **A control socket, on by default.** `fleet.enabled` (default `true`)
  opens each session's loopback control socket and lists it in
  `~/.halo/run/sessions.json`: the TUI, `halo -p` (and `--bg`), Paperclip
  heartbeats, Orchestra workers and a flow's org run. It listens on loopback
  only (see [REMOTE.md](REMOTE.md)). `remote.enabled` is only the Signal
  phone bridge's switch.
- **A private switch.** `halo --private`, `/private on` or `fleet.private:
  true`: the session registers nothing and opens no socket, so Studio, `halo
  remote` and every hub never see it (a `private` chip in the status bar).
- **Who and where.** Each registry entry carries `harness` (`{id, name,
  host, user, version, os}`; `id` is a stable per-home id in
  `~/.halo/fleet-id`, `name` is `fleet.name`, default `user@host`), `project`
  (`{root, repo, branch, dirty}` from git), `kind` and `parent`.
- **The agent tree.** The main agent and every sub-agent at every depth plus
  background Bash jobs, each with parent, name, role, model, state, turns,
  cost, the tool in flight and its last text: `agents` over the socket, `halo
  remote agents <session>`, `/agents live`.
- **Agent-level control.** `agent_tail`, `agent_steer` (`nudge` or
  `redirect`), `agent_stop`, `pause` / `resume`, `shutdown`, `agent_follow`;
  wire shapes in [REMOTE.md](REMOTE.md#agent-level-commands-3050-fleet), what
  the agents see in [SUBAGENTS.md](SUBAGENTS.md#the-live-agent-tree-and-what-studio-can-do-to-an-agent).
- **Feed frames.** `agent_state`, `agent_event` (followed agents), `fleet`
  (a session joined, changed or left); every frame carries `session_id` and
  `harness`.

## The rules every control follows

- Code decides: stop and pause are flags the agent loop checks before every
  tool call and every model call; nothing is ever asked of a model.
- A steer is a user-role note. It never widens a permission, answers a card,
  changes an Orchestra claim or skips a gate; the owner's permission engine
  runs for every agent as before, and `by` is only a label.
- Every command names its origin (`by`, `via`) in the agent's transcript.
- A hub never gets a tool permission. Commands from a hub pass the owner's
  `fleet.allow_control` first, and then run exactly as a local one would.

## The hub and the join (R2)

### What a hub is

A hub is one harness that others join: it keeps the merged picture of every
member (their sessions and agent trees, live) and passes commands from its
Studio to a member's sessions. Start one with `halo studio --fleet` (the hub
runs inside Studio's process, and Studio's Fleet view shows the members), or
`halo fleet serve` (inside a Studio that already runs, else standalone in the
terminal until Ctrl+C). The hub is a member of its own hub: its own sessions
appear first, straight from the local registry. A harness may join several
hubs.

### Pairing a harness

1. On the hub: `halo fleet pair` prints a six-word code (good for one
   harness, ten minutes by default: `--ttl 30m`), the exact `halo fleet join`
   line, a QR code of the hub's address and certificate fingerprint, and the
   fingerprint itself.
2. On the joiner: `halo fleet join <host:port> --code "acorn badge ..."`
   (optionally `--share`, `--allow-control`, `--fingerprint`). The two sides
   agree on a pair key with a Diffie-Hellman exchange authenticated by the
   code, so someone listening on the LAN learns neither; the hub keeps only
   a hash of the code and spends it on the first join. Five wrong codes a
   minute from one address and that address waits.
3. Every session the joiner runs from then on (and every one running now,
   within a few seconds) is announced to the hub. `halo fleet status` shows
   whether each hub answers and sees this harness online.

### What each share level sends

`fleet.share` (default `events`; a hub entry's own `share` wins):

| Level | The hub gets |
|---|---|
| `status` | each session's row (title, kind, mode, project name and branch, state, model, cost) and its agent tree, kept live with `agent_state` frames; no text, and agent rows without their last text |
| `events` | that, plus every feed frame except the text and thinking streams (tool calls and results, cards, todos, turn starts and ends, sub-agent events) |
| `full` | everything, including the text stream, and the hub may read an agent's tail (`agent_tail`, `tail`) or follow one (`agent_follow`) |

The level is applied on the member before anything is sent, and again on
the hub. Full local paths never leave: a working directory or repo root
travels as its last component only.

### What control levels mean, and the card the owner sees

`fleet.allow_control` (default `ask`; a hub entry's own wins) gates
`agent_steer`, `agent_stop`, `pause`, `resume`, `shutdown`, `steer` and
`interrupt` from a hub:

- `none`: refused; the hub shows the reason ("control from a hub is off on
  bob@laptop (fleet.allow_control: none)").
- `ask`: a card in the owner's TUI, "alice@hub on hub-a wants to stop the
  main agent: wrong folder" [allow] [deny]. Allow runs it; deny, or no
  answer in 120 s, refuses it with the reason. The hub sees `asked` (202)
  until then, and the outcome as a `fleet` frame. A print-mode session has
  no one to ask, so under `ask` it denies.
- `all`: applied at once.

Applied or refused, the session's transcript records the command with `by`
(the person at the hub) and `via` ("hub <name>"). Permission, question, plan
and approval cards are never answerable from a hub unless `allow_control:
all` AND `fleet.allow_answers: true`, and then only once (a hub never learns
an allow rule); the fleet card itself is never answerable from a hub.

### Ports, TLS and HMAC

The hub listens on `fleet.hub.port` (7430; `--port`, `--bind`, default
`0.0.0.0`) and serves only the fleet protocol (`/fleet/v1/...`); Studio's
own API stays on loopback, unchanged. Every request from a member is signed
with the pair key (HMAC-SHA256 over the method, path, member id, time, a
nonce and the body's hash); the hub refuses one whose clock is two minutes
off or whose nonce it has seen. Every command the hub sends down is signed
too, numbered and timed, so a member runs only the hub's own. With the
`cryptography` package on the hub (`pip install "halo-harness[fleet]"`) the
port speaks TLS with a self-signed certificate made on first serve; the
joiner pins its fingerprint (the hub vouches for it inside the
code-authenticated join reply) and refuses any other. Without it, or with
`serve --no-tls`, the hub speaks HMAC-signed plain HTTP: tamper-proof, but
readable on the LAN. Offline mode (`--offline`, `/offline on`) refuses
`serve` and stops the relay.

### Leaving, kicking, offline

`halo fleet leave [hub]` tells the hub and forgets it (and its key); with no
name it leaves every hub. On the hub, `halo fleet members` lists the members
(name, id, host, version, share, control, online) and `halo fleet kick
<name>` removes one: its key stops working at once and a running hub closes
its links within a second; the member's relay marks that hub `kicked` in its
`~/.halo/fleet.json` and stops trying. A hub that is down never slows a
member: the relay runs on its own thread and retries with backoff (1 s,
doubling to a minute).

### What never leaves a machine

The control sockets, their tokens and endpoints; the pair keys (the
joiner's in `~/.halo/fleet/keys/`, 0600; the hub's in `members.json`, 0600);
private sessions; full local paths; permission rules and config; transcripts
on disk (a hub reads an agent's tail only under `full`, through the
session); and, under `status`, every word an agent writes.

### Files

| Where | What |
|---|---|
| joiner `~/.halo/fleet.json` | `{hubs: [{url, name, hub_id, key_ref, fingerprint, tls, share, allow_control, member_name, joined_at, state}]}` |
| joiner `~/.halo/fleet/keys/<ref>.key` | that hub's pair key |
| hub `~/.halo/fleet/hub/members.json`, `codes.json` | members with their keys; live codes as hashes |
| hub `~/.halo/fleet/hub/cert.pem`, `key.pem` | the TLS certificate (with `cryptography`) |
| hub `~/.halo/fleet/hub/serve.json` | while a hub runs: its port, fingerprint and a loopback admin token |

### The wire

One JSON document per message, `"v": 1`. Member to hub: `POST
/fleet/v1/join` (the pairing exchange), `announce` (this process's sessions
with their agent trees), `frames` (feed frames, batched), `reply` (a
command's `asked` / `done` / `refused` / `error`), `leave`, `GET ping`; hub
to member: `GET /fleet/v1/stream?link=<id>`, an SSE stream of `hello`,
`command` (`{cid, session_id, cmd, fields, by, hub}`) and `kicked` docs.
Each halo process with sessions runs one relay thread per joined hub.

### Studio: `GET /api/fleet` and the commands

- `GET /api/fleet` -> `{harnesses: [{id, name, host, user, version, os,
  share, allow_control, online, last_seen, cost_today, version_mismatch,
  local, sessions: [{...the session row, agents: [...]}]}], hub: {serving,
  name, port, bind, tls, fingerprint, url, members, online,
  pair_code_active}}`; this harness first (`local: true`).
  `version_mismatch` is true for a member on another Halo version (`halo
  update` on the older one).
- `POST /api/fleet/<harness>/<sid>/command` (`steer`, `interrupt`,
  `shutdown`, `pause`, `resume`, `answer`) and `POST
  /api/fleet/<harness>/<sid>/agents/<aid>/command` (`steer`, `stop`, `pause`,
  `resume`, `follow`, `tail`): this harness takes the direct path; a member
  answers 200, 202 (`asked`), 403 (refused, with its reason), 409 (not
  connected) or 504. `GET /api/fleet/commands/<id>` is one command's state;
  `POST /api/fleet/hub {action: start|stop}` starts or stops Studio's hub.
- The live feed: member frames carry `harness: <id>` with their
  `session_id` unchanged; `fleet` frames say join, leave, online, offline,
  sessions and command; the `sessions` frame carries this harness's id.

## The terminal: `halo fleet` and `/fleet`

`halo fleet` alone is a live table (refreshed every 2 s) of every harness,
session and agent: harness, session, agent (indented under its parent),
state, what it is doing, cost. Up/Down select, `s` steer, `k` stop (asks
y/N), `p` pause or resume, `r` refresh, `q` quit; `--once` prints it once,
`--json` the view. `/fleet` in the TUI is the same table as a dialog. Both
read Studio's `GET /api/fleet` when Studio runs, else the hub this machine
serves, else the local registry and sockets. Every flag is in
[COMMANDS.md](COMMANDS.md#halo-fleet).

## Config keys

| Key | Default | Meaning |
|---|---|---|
| `fleet.enabled` | `true` | every session opens its control socket and registers |
| `fleet.name` | `user@host` | this harness's name in the registry, on a hub and on every command it sends |
| `fleet.private` | `false` | every session starts private (as with `--private`) |
| `fleet.share` | `events` | what a joined harness sends: `status`, `events`, `full` |
| `fleet.allow_control` | `ask` | what a hub may do here: `none`, `ask`, `all` |
| `fleet.allow_answers` | `false` | with `all`, a hub may also answer cards (once only) |
| `fleet.hub.port` | `7430` | the hub's LAN port |
