# Fleet

Halo 3.0.5.0 "Fleet" puts every harness, every session and every agent in
one live picture in Studio: what each one is doing, what it is thinking,
what it wrote, and the controls to steer, pause or stop any of them. This
page grows with the release. **3.0.5.0 R1 (this round) is what one session
exposes**; the hub and the join (`halo fleet serve | pair | join`), Studio's
Fleet section (the map, the agent inspector, Live Roles) and the fleet
panels (people, attention, activity, costs, health) come in rounds R2 to R4.

## What a session exposes (R1)

- **A control socket, on by default.** Config `fleet.enabled` (default
  `true`) opens the session's loopback control socket and lists it in
  `~/.halo/run/sessions.json` for every kind of session: the TUI, `halo -p`
  (and `--bg`), `halo paperclip-run` heartbeats, Orchestra worker children
  and a flow's org run. Nothing listens beyond loopback (a 0600 Unix socket
  on Linux and macOS, loopback TCP plus a random token on Windows; see
  [REMOTE.md](REMOTE.md)). `remote.enabled` is now only the Signal phone
  bridge's switch.
- **A private switch.** `halo --private`, `/private on` in the TUI or
  `fleet.private: true`: the session registers nothing and opens no socket,
  so Studio, `halo remote` and the fleet never see it; the status bar shows
  a `private` chip. `/private off` lists it again.
- **Who and where.** The registry entry carries `harness` (`{id, name,
  host, user, version, os}`: `id` is a stable per-home id in
  `~/.halo/fleet-id`, `name` is `fleet.name`, default `user@host`),
  `project` (`{root, repo, branch, dirty}`, from git), `kind` (`tui`,
  `print`, `paperclip`, `orchestra-worker`, `flow`) and `parent` (the
  session that started it, for an Orchestra worker).
- **The agent tree.** The main agent and every sub-agent at every depth
  (Agent/Task calls, count/batch jobs, org positions and team members,
  background sub-agents), plus background Bash jobs, each with its parent,
  name, role, bio, lineup, model, kind, task, state, turns, cost, the tool
  in flight and the last text it wrote. `agents` over the socket, `halo
  remote agents <session>`, `/agents live` in the TUI.
- **Agent-level control.** `agent_tail` (an agent's own transcript),
  `agent_steer` (a note that agent reads before its next model call:
  `nudge` or `redirect`), `agent_stop` (that agent and its subtree, at the
  next tool boundary), `pause` / `resume` (one agent or the whole session),
  `shutdown` (the session ends after the current tool call) and
  `agent_follow` (stream one agent's entries live). Wire shapes in
  [REMOTE.md](REMOTE.md#agent-level-commands-3050-fleet); what the agents and
  their parents see in [SUBAGENTS.md](SUBAGENTS.md#the-live-agent-tree-and-what-studio-can-do-to-an-agent).
- **Feed frames.** `agent_state` on every change of a row, `agent_event` for
  followed agents, `fleet` when the session joins, changes or leaves the
  registry (and as the first frame of every new subscription); every frame
  carries `session_id` and `harness`.
- **Studio.** `GET /api/sessions` rows carry the new fields and an agent
  count (the rail shows it); `GET /api/sessions/<sid>/agents`, `GET
  /api/sessions/<sid>/agents/<aid>/tail`, `POST
  /api/sessions/<sid>/agents/<aid>/command` and the session commands
  `shutdown`, `pause`, `resume` (see [STUDIO.md](STUDIO.md)).

## The rules every control follows

- Code decides: stop and pause are flags the agent loop checks before every
  tool call and before every model call; nothing is ever asked of a model.
- A steer is a user-role note. It never widens a permission, answers a card,
  changes an Orchestra claim or skips a gate; the owner's permission engine
  runs for every agent as before, and `by` is only a label.
- Every command names its origin (`by`, `via`) in the agent's own
  transcript, and the parent's transcript gets one line.

## Config keys

| Key | Default | Meaning |
|---|---|---|
| `fleet.enabled` | `true` | every session opens its control socket and registers |
| `fleet.name` | `user@host` | this harness's name in the registry and on every command it sends |
| `fleet.private` | `false` | every session starts private (as with `--private`) |
