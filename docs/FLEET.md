# Fleet

Read this when you connect several harnesses into one fleet and watch or steer them from one place.

Halo 3.0.5.0 "Fleet" puts every harness, every session and every agent in
one live picture: what each one is doing, what it is thinking, what it
wrote, and the controls to steer, pause or stop any of them. **R1** is what
one session exposes; **R2** (this page's second half) is the hub and the
join: one machine runs a hub, others join it with a six-word code, and each
joined harness shares what it chooses and accepts control only as its owner
allows. **R3** is Studio's Fleet section (the map, the agent inspector,
the Fleet rail in every section, the hop keys, Live Roles: see
[In Studio](#in-studio) below); **R4** is the panels behind it (attention, caps,
conflicts, health, hand-offs, flight recordings, the replay and the digest: see
[The panels](#the-panels-r4)). Halo 3.0.6.0 adds **R6**, what every harness
can do and who can do something ([Capabilities](#capabilities-3060-r6)), and **R7**,
missions: one goal split into parts across every harness ([Missions](#missions-3060-r7)).

## What a session exposes (R1)

- **A control socket, on by default.** `fleet.enabled` (default `true`)
  opens each session's loopback control socket and lists it in
  `~/.halo/run/sessions.json`: the TUI, `halo -p` (and `--bg`), Orchestra
  workers and mission workers. It listens on loopback
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
session); and, under `status`, every word an agent writes. A capability
catalog (3.0.6.0 R6) carries names, never a path, a server command or a key
([Capabilities](#what-never-leaves-the-machine)).

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

## In Studio

`halo studio --mode fleet` (or `Alt+4`, `/studio fleet`) opens the **Fleet**
section; the full guide is [STUDIO-fleet.md](STUDIO-fleet.md#fleet-every-harness-every-agent).

- **The map.** One box per harness (this one first), a card per session, its
  agents as a tree under it with their state, what each one does now, its
  model and cost; **By project** puts everyone on the same repo in one box.
  The outlines move with the state: flowing while an agent works, amber while
  it waits on you, one green sweep when it finishes, a red flash when it
  fails; the edge from a parent lights for a few seconds when it spawns a
  child.
- **The agent inspector.** Click an agent: its header, what it was asked,
  and three streams, **Thinking** (its text as it types it), **Working** (one
  row per tool call with its result and the diff it writes) and **Output**
  (its hand-back); **Steer** (a nudge before its next step, or a redirect),
  Pause / Resume, Stop (asks first), Follow, Pin. Studio follows the agent
  you open (`agent_follow`) and reads its backlog once (`agent_tail`, through
  the hub for a member); every command goes to
  `POST /api/fleet/<harness>/<sid>/agents/<aid>/command`, so a member's
  `fleet.allow_control` applies exactly as it does for the CLI.
- **The Fleet rail** in every section: the same tree in short, with the live
  and need-you counts; a session that waits on you keeps its inline answer.
- **Hop around.** `J` / `K` the next / previous live agent (also on the Roles
  canvas and the Orchestra lanes), `F` follow, `Space` pin a mini
  stream that stays on screen in every section, `Esc` unpin, `P` pause or
  resume, `K` inside the Agent panel stop (asks first).
- **Live Roles.** On the Roles canvas the cards whose agents work
  glow in their band colour, by what each agent does right now (typing, a
  tool call, waiting on you, done, failed), with a count badge and a cost
  ticker; the Inspector's **Live** tab shows that agent's streams with Steer,
  Pause and Stop, or, when nobody runs the card, its last runs.
- **The Start view.** With only this harness and nothing running: what Fleet
  is, a pair code with its QR and the `halo fleet join` line, the share and
  control settings, the hubs this harness joined and this hub's members.

The routes R3 adds (the same loopback + token guard as every Studio route):

| Route | What |
|---|---|
| `POST /api/fleet/pair {ttl?}` | a one-time code for this machine's hub: `{code, expires, ttl, url, fingerprint, hub_running, join, qr, matrix}` (`matrix` is the QR as rows of 0/1) |
| `GET /api/fleet/settings` | `{name, share, allow_control, levels, hubs, members, hub}` (never a key) |
| `POST /api/fleet/settings {share?, allow_control?}` | writes `fleet.share` / `fleet.allow_control`; a bad value is a 422, a config.json that does not parse a 409 and is left alone |
| `POST /api/fleet/kick {harness}` | removes a member from this hub (its pair key with it) |
| `GET /api/fleet/history?role=&bio=&n=` | the last runs under a role or bio on this harness (from each sub-agent's `<sid>/subagents/agent-<id>.meta.json`, which records its role and lineup since 3.0.5.0, with the task and the cost from its transcript; `role=main` lists the sessions) |

## The panels (R4)

Round R4 adds the panels that watch the whole fleet at once: **People**,
**Attention**, **Activity** (the merged log and a timeline strip),
**Costs**, **Health**, project rooms with conflict warnings on the map,
hand-offs, flight recordings, the canvas replay and the digest. The Studio
side is in [STUDIO-fleet.md](STUDIO-fleet.md#fleet-every-harness-every-agent); this
section is what runs behind it. Everything here is computed in code from
what the hub already sees; nothing calls a model.

While Studio runs the hub (or the first time a panel asks), a **fleet
watcher** looks at the fleet every 3 s. It keeps the open cards' details
(from the sessions' `permission_request`, `question`, `plan_review` and
`approval_request` frames), who edits which file (from each agent's `current`
step, `Edit: <path>`), applies the caps, builds the attention queue, sends its
count as a `fleet` frame (`action: attention, count`) and writes the hub's
journal, `~/.halo/fleet/journal.jsonl` (0600; past 4 MB it rolls to
`journal.1.jsonl`): sessions that start and end, member cost snapshots, files
touched, errors, decisions and who made them, hand-offs, caps, rows set aside.

| Route | What |
|---|---|
| `POST /api/fleet/<harness>/<sid>/command {cmd: note, text}` | People's **Message**: a line the owner reads in that session's transcript and TUI, never the model (`fleet.message`); a member applies it unless its `fleet.allow_control` is `none` |
| `GET /api/fleet/attention` | `{rows, count, at}`: the attention queue, oldest first |
| `POST /api/fleet/attention/answer {id, key, text?}` | one key on one row (below): `{ok, id, kind, key, answer, result}` plus `open`, `set_aside`, `lifted` / `resumed` where they apply |
| `GET /api/fleet/costs` | `{fleet, harnesses, projects, sessions, caps, keys, reached, lifted, balances}` |
| `GET /api/fleet/caps`, `POST /api/fleet/caps {<key>: dollars}` | the caps; `0` or `null` clears one; a negative or non-number is a 422 |
| `GET /api/fleet/health[?refresh=1]` | `{harnesses: [...], cache_s}`: each harness's health, cached 60 s |
| `GET /api/fleet/conflicts` | `{conflicts, rooms, touches}` |
| `GET /api/fleet/digest?since=` | the digest (`2h`, `45m`, `1d`, unix seconds or milliseconds, an ISO time; default `1d`) |
| `POST /api/fleet/<harness>/<sid>/agents/<aid>/handoff {mode, brief?, to?}` | Take over or Hand to (below) |
| `POST /api/fleet/<harness>/<sid>/recording[?agent=]` | writes a flight recording: `{ok, path, name, url, bytes, agents, states}` |
| `GET /api/fleet/recordings/<name>` | that recording's HTML (`text/html`, as an attachment, its own CSP) |
| `GET /api/fleet/replay?session=<sid>[&harness=]` | `{harness, session_id, title, started, ended, cost_usd, agents, states, costs}` |

### Attention

One queue of every decision a person has to make, on any harness: a
session's open **permission**, **question**, **plan** and **approval** cards;
a hub asking to run a command here (**fleet_ask**); an agent **waiting** with
no card of its own listed; an agent (or a session) **paused** until someone
resumes it; an Orchestra run its gate
stopped, with the report's stop reason (**orchestra_gate**); a command this
hub sent that waits on a member's owner (**control_ask**, from the hub's open
commands); a spend **cap** reached; two agents editing one file
(**conflict**). Each row has who (harness, session, agent), what, a detail,
since when, the keys that kind takes and where to open it:

| Key | Does |
|---|---|
| `a` | allow once (permission), approve (plan), accept (approval), allow (fleet ask), resume (paused), lift for today (cap), set aside (orchestra gate, control ask, conflict) |
| `r` | deny with a reason (permission), answer (question), send back with feedback (plan), edit with an instruction (approval) |
| `s` | answer the card negatively, then stop the agent (an approval's own `stop`) |
| `o` | nothing is sent: the answer says which section and panel to open |

An answer goes through the route that already handles it:
`/api/fleet/<harness>/<sid>/command {cmd: answer}` for a card (a member
answers only under `fleet.allow_control: all` and `fleet.allow_answers:
true`, scope once), `/api/fleet/<harness>/<sid>/agents/<aid>/command` for a
stop or a resume. Each decision
is journaled with `by` (`fleet.name`), so the digest says who decided what.

When the Signal bridge is enabled (`remote.enabled`), running and paired, a
new row also goes to the phone as the card the bridge already sends,
prefixed with the harness name (see [REMOTE.md](REMOTE.md#the-signal-bridge));
`fleet.attention.signal: false` keeps the queue in Studio only.

### Caps

`fleet.caps.per_harness_usd_per_day`, `fleet.caps.per_project_usd_per_day`
and `fleet.caps.fleet_usd_per_day` (dollars; unset or `0` is no cap) are
read on the hub. Today's spend is every session started today, at the cost
its control socket reports (the same rule as a harness's `cost_today`). When
a cap is reached, the hub pauses the live sessions in its scope (the `pause`
command with reason `cap`: every agent holds at its next tool boundary, so
nothing new is spawned) and raises a `cap` row; `a` on it resumes them and
holds that cap off for the rest of the day. `GET /api/fleet/costs` adds the
balances the balances workers last fetched (`halo balances`), read-only.

### Conflicts

Project rooms: in the map's **By project** grouping each card shows its
branch, dirty / ahead / behind (against its upstream) and its worktree. The
hub keeps which file each agent edits (from `Edit:` / `Write:` steps, a path
made relative to its repo, so `~/shop/basket.py` on one machine and
`C:\src\shop\basket.py` on another are the same `shop/basket.py`) for 15 minutes, plus
the Orchestra claims of this machine's runs and the ones members' Orchestra
workers announce. Two agents of different sessions (on any harnesses) on one
file of one repo are a conflict: a warning edge on the map and a `conflict`
row ("<a> and <b> are both editing <file>"). Two agents of the same session
never are.

### Health

Per harness: the Halo and Python versions, the OS, each provider configured
or not (credentials only, never a key) and, when configured, reachable (a
connect-phase probe, no request sent), free disk, the live control sockets
and whether Studio runs; `status` is `ok`, `warn` or `bad`. A member answers
the fleet protocol's read-only `doctor` command (with `status`, through one
of its live sessions; it answers even under `fleet.allow_control: none`).
Each harness's answer is cached 60 s; `?refresh=1` asks again. Nothing is
written.

### Hand-offs

On an agent: **Take over** (`mode: take_over, brief`) is a redirect steer
with your brief, recorded as a hand-off (`handoff: take_over`) in the agent's
transcript and as "taken over" in its parent's. **Hand to...** (`mode:
hand_to, to: <harness id or name>`) turns the agent's task, its last
hand-back and the files it touched into one brief,
`<repo>/.halo/handoffs/<id>.md` (the state directory's
`handoffs/` when the repo is not on this machine). Then the agent is stopped.
A hand-off never widens a permission: the steer is a note the agent reads,
the file is text.

### Recordings

A flight recording is one self-contained HTML file: inline CSS and JS, the
session as a JSON block (with `<`, `>` and `/` escaped, so nothing an agent
wrote becomes markup or a link), no network at all. It shows the session,
its harness, start, length and cost; Play / Pause with a speed; a scrub bar;
one lane per agent with bars by state and a tick per tool call; the cost
curve; and the selected agent's Thinking, Working and Output as they were at
the cursor (Space plays, Left / Right step, 1 2 3 pick the stream). Studio
writes it with `POST /api/fleet/<harness>/<sid>/recording[?agent=]` (a
member's session from its agents' tails through the hub, which needs its
share `full`; this harness's from its transcripts, finished sessions too) to
`~/.halo/recordings/<sid>[-<aid>].html`; `halo fleet record <sid>` does the
same in the terminal ([COMMANDS-fleet.md](COMMANDS-fleet.md#halo-fleet-record)).

### Replay

`GET /api/fleet/replay?session=<sid>` is a finished session's `agent_state`
history: each agent (with its role, bio and lineup, which the Roles canvas
matches cards on) and every change of what it did (`typing`, `tool` with the
tool's name, `waiting`, `done`, `failed`) in time order, plus the cost
curve. The Roles canvas plays it back on its cards.

### Digest

"While you were away", computed in code: per harness, the sessions started
and ended, the cost, the decisions answered and by whom, the files touched,
the errors and the hand-offs since a moment, and (3.1.3.0) one coach line per
run the post-run coach read ("coach    orchestra <run>: N suggestions, M
applied, top: ..."). This harness is read from its own transcripts and its
`~/.halo/coach/runs.json`; members, decisions and hand-offs from the journal.
`GET /api/fleet/digest?since=` and `halo fleet digest [--since 2h]`
([COMMANDS-fleet.md](COMMANDS-fleet.md#halo-fleet-digest)).

## Capabilities (3.0.6.0 R6)

Every harness says what it can do, so you (and, from 3.0.6.0 R7, a fleet
mission) can see which one is best for a part of the job: which MCP servers
and tools it has, its skills, models, craft apps, GPU, command-line tools and
the tags its owner gave it. Everything is computed in code on each harness;
no model is called to build or rank it.

### What a catalog holds

`fleet/capabilities.py` gathers one catalog per harness:

```
{harness: {id, name, host, os, version}, at, hash, tags: [..],
 mcp: [{name, transport, tools: [{name, desc}] | null, note?}],
 skills: [name], roles: [{role, bio, lineup}], providers: [{name, id, ok}],
 models: [{id, provider, best_for: [visual|audio|video|image|design], local?}],
 craft_apps: [name], media: {comfyui, models: [{name, kind}]},
 hardware: {os, distro, release, cpu, cores, ram_gb, gpu: [{name, vram_gb}], disk_free_gb},
 clis: {git, gh, python, uv, node, npm, docker, ffmpeg, rg, claude, codex, ollama, go, cargo,
        java, kubectl, terraform, nmap: version | "installed" | null},
 projects: [{name, repo, branch}], integrations: {signal}}
```

- **MCP tools** come from each server's tool cache (`~/.halo/mcp/tools-cache/`,
  the files lazy MCP start writes). A server with no cache is connected once
  and its cache written; each probe has its own thread and the gather waits
  at most 8 s for all of them, so a server that does not answer is listed
  with `tools: null` and a note, and its list arrives with the next gather.
  claude.ai connectors are listed from their discovery cache.
- **Models** are the catalog's best few per job (`halo models --best-for`)
  and every local model; **roles** are the active lineup and your own.
- **Craft apps** are the registered ArtCraft servers (and ComfyUI); **media**
  is ComfyUI's last model scan.
- **Projects** are the repos of the live sessions, the working directory and
  recent history: a folder name, the repo name and the branch.
- The **hash** covers everything but the time and the free disk, so it moves
  only when what the harness can do moves.

The catalog is cached at `~/.halo/fleet/capabilities.json` and gathered
afresh when it is older than an hour, after `halo mcp add` / `remove`, and
on `halo fleet capabilities --refresh` (or Studio's Refresh).

**Packs** (3.2.0.0 R4). A `packs` section lists what the packs that run here
bring to the fleet (`contributes.fleet`, [PACKS.md](PACKS.md#in-the-fleet)):
`[{id, name, version, capabilities: [{name, description, available, why,
checks, requires, capacity}], inspector: [{label, source}], metadata}]`, each
capability checked on this host against the rest of the catalog (tools,
runtimes, platform, GPU and RAM, models by tag, the pack's grants, where the
data is). The summary and the chips count the available ones (`+1 pack
cap`), `who` ranks them (one not available here at half, with why), and the
catalog is gathered afresh on every pack change. A disabled pack adds
nothing; with no pack the section is empty and nothing else changes.

### What never leaves the machine

No full local path: projects are folder names and repo names, and every
string in the catalog has its absolute paths cut to their last component
before it is cached or sent. No server command, argument, URL, header or
environment value: an MCP server is its name, its transport and its tools.
No key: a provider is its name and whether it is enabled here.

`fleet.capabilities.hide` (a list of names) keeps things off the catalog:
an MCP server (and its tools), one tool (`write_range` or
`gridcraft/write_range`), a skill or a craft app. `fleet.tags` (a list) are
your own words for this harness (`gpu`, `studio`, `night-shift`); they show
first on its chips and count double when someone asks who can do something.

```sh
halo config set fleet.tags '["gpu", "studio"]'
halo config set fleet.capabilities.hide '["private-notes", "gridcraft/delete_sheet"]'
```

### How it reaches the hub

A joined harness's announce carries `capabilities_summary` (one line: counts
and tags) and `capabilities_hash`. When the hash is one the hub has no
catalog for, the hub asks for the whole catalog once, with the read-only
`capabilities` fleet command (`READ_CMDS`, answered at any share level from
the cache), through one of that harness's live sessions; a failed ask is
retried after a minute, never on every announce. A catalog that arrives with
a new hash raises a `fleet` frame `{action: "capabilities", harness, name,
hash}`. The hub's own harness is in the list too, from its own cache.

### Who can do this?

`halo fleet who "<query>"`, `/fleet who <query>` and Studio's "Who can..."
box rank every harness for what you typed. The query is cut into words (case
and filler words such as "who", "can", "make" ignored); each item of each
catalog (an MCP server or tool, a skill, a tag, a model, a craft app, a CLI,
the GPU, CPU, OS or RAM) scores:

| Match | Points |
|---|---|
| its whole name is the query, or one query word | 10 |
| a query word is a word of its name | 4 per word |
| a query word is in its description | 1 per word |
| the item is a tag | double |

A harness's score is the sum of its five best items; each result lists them
with why they matched. `who gridcraft` puts the harness that has gridcraft
first; `who 4090` the one with that GPU.

### Routes and the command line

| Route | Answer |
|---|---|
| `GET /api/fleet/capabilities[?harness=<id\|name\|local>&refresh=1]` | `{harnesses: [{harness, name, local, online, hash, summary, chips, at, received, catalog, note?}], at, stale_s}`; `refresh=1` gathers this harness again or asks the named member now |
| `GET /api/fleet/who?q=<words>` | `{q, words, results: [{harness, name, local, score, matched, matches: [{kind, name, why, score}]}]}`; 422 with no word |

`halo fleet capabilities [name] [--refresh] [--tools] [--json]` prints a spec
sheet per harness (hardware, models, craft apps, MCP servers with tool counts,
every tool with `--tools`, skills, CLIs, projects, providers, roles,
integrations, tags); `halo fleet who "<query>" [--json]` the ranking. Both read
Studio when it runs, else the hub this machine serves, else this harness
alone ([COMMANDS-fleet.md](COMMANDS-fleet.md#halo-fleet-capabilities)).

## Missions (3.0.6.0 R7)

A mission is one goal done by the whole fleet: the hub's lead splits it into
parts with the capability catalog in its prompt, each part is pinned to the
harness that has what it needs (or flagged unassignable), parts claim the
files they edit and two that would overlap run one after the other, each
part runs on its harness as the `run_task` fleet command (under that
harness's `fleet.allow_control`, like a steer) in a `mission-worker` session
whose edits outside its claims are refused, the mission folder is shared
over the signed protocol (`mission_files`) or a real mount
(`fleet.shared_dir`), and the repo parts merge one at a time with a judge.
`halo fleet mission new "<goal>"`, `GET /api/fleet/missions`, `/mission`;
in Studio, Fleet's Mission panel plans, draws, approves, runs and reports it (3.0.6.0 R8).
The whole story, the folder, the plan contract and a worked example:
[MISSIONS.md](MISSIONS.md).

## Recall across the fleet (3.1.2.0 R3)

The recall index is per machine: each box's `halo recall` searches its own
auto-memory and session logs. `halo recall --fleet <query>` (and `/recall
--fleet <query>` in the TUI and `halo -p`) asks the hub this machine runs,
or the first hub it joined, which sends the read-only `recall` fleet command
`{query, k}` to every online member at once. Each member answers **from its
own index** -- the index never leaves the box, only the hits: `{score,
title, kind, excerpt (<= 300 chars), harness}`. The hub merges them by score
with this machine's own hits and the CLI prints one table (score, harness,
title, excerpt), with a line for every harness that did not answer and why.
A member logs each ask in its own journal (`recall_asked`: what was asked,
by whom, how many hits). `GET /api/recall?q=&fleet=1` (Studio's recall box
with its Fleet switch) and `GET /api/fleet/recall?q=` (the hub's merged
view) are the routes. Two config keys on a member:

- `fleet.recall.share` (default `true`): `false` keeps the box out -- it
  answers no recall and the merged view shows it as `not_shared`.
- `fleet.recall.hide` (default `[]`): memory kinds never answered, the same
  shape as `fleet.capabilities.hide` -- `session`, `memory`, `coach_library`
  (3.1.6.0), or a memory topic's own `type` (`user`, `feedback`, `project`,
  `reference`).

**The coach's library across the fleet (3.1.6.0).** Every Apply of a coach
card leaves an entry in the box's improvement library
([ORCHESTRA.md, "The library"](ORCHESTRA.md#the-library)), and recall
indexes each entry's EXPERIENCE.md as a third kind, `coach_library`: a
member answers such a hit with the entry's Lessons as its excerpt, so
`halo recall --fleet` shows what another box learned for a goal like yours
(`[lib]` in the local `halo recall`). To take one, `halo coach library fetch
<harness> <entry>` asks the hub this machine runs (the admin route
`local/coach-library {harness, entry}`), which sends the read-only
`coach_library {entry}` fleet command to one live session of that member.
The member answers the entry's entry.json, EXPERIENCE.md, overlay.json and
files/ -- at most 256 KB in all, else it refuses with the size -- under the
same `fleet.recall.share` switch (and `fleet.recall.hide: [coach_library]`
keeps it out), and logs a `library_asked` line (`{entry, by, hub, bytes}`) in
its own journal. The entry is written here under the same id with `from:
<harness>`; a fetch never writes over an entry already here. The coach then
cites it for runs of the same project (the same remote path) like any entry
of this box.

## The two-machine check (3.1.2.0 R3)

`tools/live_fleet_check.py` runs the whole delegation path against a real
second machine with **one command on each box**. On this host:

    python tools/live_fleet_check.py hub [--fake] [--json] [--keep]

starts Studio with the fleet hub, prints a pairing code and the exact join
line, waits for the other box, then drives four steps and prints PASS / FAIL
with an evidence line for each: **who** (`fleet who nmap` names the member,
`who gridcraft` this host), **mission** (a one-part files mission pinned to
the member writes one file and its hand-back lands here), **team** (a team
with a delegated agent stage whose gate is answered here), **recall** (`recall --fleet` with a
query only the member's index answers). On the other box, with the code the
hub printed:

    python tools/live_fleet_check.py member <host>:<port> --code "acorn ..." [--fake]

joins the hub and stays live while the hub drives. PASS looks like four
`[PASS]` lines and `OK: 4/4 step(s) passed`; the script exits non-zero if
any step failed. `--json` writes `live-fleet-check.json` (one object per
step: `name`, `ok`, `evidence`, `seconds`) to paste back. `--fake` runs it
with no model call on either box (give it on both); the real configured
model otherwise. `--keep` leaves the hub up after the check.

## The terminal: `halo fleet` and `/fleet`

`halo fleet` alone is a live table (refreshed every 2 s) of every harness,
session and agent: harness, session, agent (indented under its parent),
state, what it is doing, cost. Up/Down select, `s` steer, `k` stop (asks
y/N), `p` pause or resume, `r` refresh, `q` quit; `--once` prints it once,
`--json` the view. `/fleet` in the TUI is the same table as a dialog. Both
read Studio's `GET /api/fleet` when Studio runs, else the hub this machine
serves, else the local registry and sockets. `halo fleet record <sid>`
writes a flight recording and `halo fleet digest [--since]` prints the
digest (both R4, from this harness's own files); `halo fleet capabilities
[name]` prints each harness's spec sheet and `halo fleet who "<query>"` (and
`/fleet who <query>` in the TUI) ranks the fleet for it (R6). Every flag is in
[COMMANDS-fleet.md](COMMANDS-fleet.md#halo-fleet).

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
| `fleet.caps.per_harness_usd_per_day` | unset | R4, on the hub: a harness's spend today that pauses its sessions (`0` or unset: no cap) |
| `fleet.caps.per_project_usd_per_day` | unset | the same for every session on one repo, any harness |
| `fleet.caps.fleet_usd_per_day` | unset | the same for every session the hub sees |
| `fleet.attention.signal` | `true` | new attention rows go to the paired phone when the Signal bridge runs; `false` keeps them in Studio |
| `fleet.tags` | `[]` | 3.0.6.0 R6: your own words for this harness; first on its chips, double weight in `who` |
| `fleet.capabilities.hide` | `[]` | MCP servers, tools (`tool` or `server/tool`), skills or craft apps its capability catalog never lists |
| `fleet.recall.share` | `true` | 3.1.2.0 R3: `false` keeps this box out of recall across the fleet (it answers none) |
| `fleet.recall.hide` | `[]` | 3.1.2.0 R3: memory kinds its recall never answers (`session`, `memory`, `coach_library` since 3.1.6.0, or a topic's `type`) |
| `fleet.shared_dir` | unset | 3.0.6.0 R7: a folder every machine sees; missions live there and nothing is mirrored ([MISSIONS.md](MISSIONS.md)) |
| `fleet.mission.prefer` | `[]` | harness names, in order, that break a tie when several can take a part |
| `fleet.mission.max_parallel` | harnesses | how many mission parts run at once (default: the number of harnesses) |
| `fleet.mission.max_file_mb` | `25` | the largest file a mission folder takes over the fleet protocol |
