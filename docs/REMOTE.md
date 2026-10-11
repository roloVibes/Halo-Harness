# Remote control

Halo 2.0.9 adds remote control of a running session. This page covers the
part that exists today: the per-session **control socket** and the **sessions
registry**. The Signal bridge that sits on top of it (pairing a phone, relaying
prompts and permission cards) is built in later 2.0.9 rounds and gets its own
sections here as it lands.

## What the control socket is

With `remote.enabled` set, every interactive `halo` session and every
`halo -p` run (including `--bg` runs, which re-run the same invocation)
opens one local socket and lists itself in the registry. A program that can
reach that socket can do what the keyboard does: send a prompt (or steer the
turn in flight), interrupt, switch mode / model / effort, run a slash
command, answer a permission card, a question, a plan review or an approval
gate, read the status, read the tail of the conversation, and watch the
session's events as they happen. It is the same set of calls the TUI itself
makes on the `Controller`; the socket never injects raw commands into the
agent loop.

Off by default. Turn it on with:

```sh
halo config set remote.enabled true
```

It takes effect for sessions started afterwards. In the TUI, `/remote` says
whether this session's socket is on (and where) and how many live sessions
the registry holds.

## Where it listens

| Platform | Endpoint | Auth |
|---|---|---|
| Linux / macOS | Unix socket `~/.halo/run/<session_id>.ctl`, mode 0600, directory 0700 | the file mode |
| Windows | loopback TCP `127.0.0.1:<port>` (OS-assigned) | a random 16-byte hex token; the first line of a connection must be `{"token": "..."}` within 5 seconds or the connection is closed |

Nothing ever listens on a non-loopback address. The token is never logged or
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
| `status` | | the status payload (phase, model, context, cost, `permission_mode`, effort), plus `session_id`, `cwd`, `title`, `busy`, `kind` (`tui` or `print`), `pid`, and `pending` (the ids of unanswered permission / question / plan / approval cards) |
| `submit`, `steer` | `text` | `{steered}`; while a turn runs the text steers it, otherwise it starts the next turn. In `halo -p` the next turn is queued only for `--input-format stream-json` runs |
| `interrupt` | | `{interrupted}` |
| `answer` | `kind` = `permission`, `request_id`, `action` (`allow` / `deny`), optional `scope` (`once` / `session` / `always`), `message`, `rule` | `{resolved}`. `session` / `always` learn the card's suggested rule (or `rule`), as the TUI's buttons do |
| `answer` | `kind` = `question`, `request_id`, `answer` | `{resolved}` |
| `answer` | `kind` = `plan`, `approved`, optional `feedback`, `mode_after` | `{resolved}` |
| `answer` | `kind` = `approval`, `request_id`, `action` (`accept` / `edit` / `stop`), optional `instruction` | `{resolved}` |
| `mode` | `mode` | `{mode}` |
| `model` | `ref` | `{model}`; an unresolvable ref is `ok: false` with the resolver's sentence |
| `effort` | `level` | `{effort, message}` |
| `slash` | `name` and `args`, or `line` (`"/cost"`) | `{output}` |
| `tail` | `n` (default 20, at most 200) | `{markdown}`: the last n user / assistant messages |
| `subscribe` | optional `kinds` (a list; default all) | `{subscribed: true}`; event frames follow on this connection |
| `unsubscribe` | | `{subscribed: false}` |

An `answer` for a card that is no longer waiting is `ok: false`. A request
that is not valid JSON gets `{"id": null, "ok": false, "error": "invalid JSON"}`
and the connection stays open.

Several clients may connect at once; a subscription belongs to its
connection. Commands that arrive over the socket show up in the TUI transcript
as a `(remote) ...` note, never as a message typed by you.

## The event feed

After `subscribe`, a connection receives the session's events (the kinds in
`halo_harness/events.py`, payloads untouched) as they are produced, with two
changes: consecutive `text_delta`s are merged into one `text_chunk` frame
(`{"event": "text_chunk", "data": {"text": ...}}`) every 2 seconds or 1800
bytes, flushed early whenever another event arrives so order is kept, and
`thinking_delta` is not sent. The feed is a copy taken where the session emits
events; the TUI's own queue is untouched.

Each subscriber has a queue of 256 frames. A client that stops reading is
dropped (its connection is closed) when the queue fills; the session and the
other clients carry on.

## The sessions registry

`~/.halo/run/sessions.json` lists the live sessions that opened a control
socket:

```json
{"version": 1, "sessions": [
  {"session_id": "...", "cwd": "...", "pid": 1234, "endpoint": "unix:<state dir>/run/<session_id>.ctl",
   "token_env": null, "started": 1791699000.0, "title": "Fix the flaky test", "mode": "default", "kind": "tui"}
]}
```

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

## Config keys

| Key | Default | Meaning |
|---|---|---|
| `remote.enabled` | `false` | open a control socket and registry entry for each session |
