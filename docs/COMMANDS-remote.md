# Commands: remote control

Read this when you control sessions remotely.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo remote`

Halo 2.0.9. Remote control of a running session. The full description (the
control socket and its wire, the event feed, the registry, the transports) is in
[REMOTE.md](REMOTE.md); exit codes are 0 done, 1 could not do it (the reason on
stderr), 2 usage. 3.3.13.0 R3: the Signal bridge that lets a phone drive a
session is the signal pack (`halo pack install signal`, then `/signal`; its
README); `halo remote signal ...` prints one line that says so.

### `halo remote sessions`

Lists the live sessions that opened a control socket (every session does
unless config `control.enabled` is false or it is private; before 3.0.5.0 this
was config `remote.enabled`): session id prefix, pid, kind (`tui`, `print`
or `orchestra-worker`),
permission mode, age, working directory, endpoint and title. Entries whose
process is gone or whose endpoint refuses a connection are pruned first. It
prints nothing secret (the Windows loopback token is never shown). With none
live it says so and exits 0; any other `halo remote` argument prints the
usage line and exits 2.

```sh
halo remote sessions
```

### `halo remote agents | steer | stop`

Halo 3.0.5.0. One live session's agents from a terminal, over its
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

Each command goes out with `by` = `harness.name` and `via` = `halo remote`,
recorded in the agent's transcript. See [SUBAGENTS.md](SUBAGENTS.md).

### `halo remote transports`

Halo 3.3.13.0 R3. The transports listening here (a pack's bridge -- the signal
pack's says `signal` while its service runs) and `remote.enabled`, every
transport's switch; `--json` for the same as one object. See
[REMOTE.md](REMOTE.md#transports).
