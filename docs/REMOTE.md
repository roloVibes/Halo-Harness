# Remote control

Halo 2.0.9 adds remote control of a running session. This page covers the
per-session **control socket**, the **sessions registry**, and the **Signal
bridge** that sits on top of them (pairing a phone, relaying prompts and
permission cards). The `halo remote signal` commands and the TUI `/remote`
dialog that set the bridge up arrive in the last 2.0.9 round.

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

## The Signal bridge

The bridge is a daemon (`halo_harness.remote.bridge`) that sits between
Signal and the control sockets above. It runs `signal-cli` as a child process
(`signal-cli -a ACCOUNT --trust-new-identities never --scrub-log -d
~/.halo/remote/signal-cli jsonRpc ...`, newline JSON-RPC over stdio: no port,
no socket file), reads what the paired phone sends, and drives the attached
session with it. It relays the session's answers, permission cards,
questions and plan reviews back to the phone. The CLI that sets it up
(`halo remote signal ...`) and the TUI `/remote` dialog arrive in the next
2.0.9 round; this page documents the behaviour they drive.

Two things are fixed by how signal-cli works. Messages are end-to-end
encrypted between the phone and the Halo number; a stranger's first message
cannot be decrypted under `--trust-new-identities never`, which is what makes
the contact-request pairing below possible. The bridge answers nobody it has
not paired.

### signal.json

`~/.halo/remote/signal.json` holds the signal-cli settings (written by the
setup command; every key is optional except `account`):

| Key | Default | Meaning |
|---|---|---|
| `binary` | `signal-cli` | path of signal-cli, or a list of argv words that start it |
| `account` | | the account signal-cli runs as (a number, or an ACI for a numberless linked account) |
| `identity_model` | `dedicated` | `dedicated` (a number of its own) or `linked` (a secondary device of your account, driven through Note to Self) |
| `own_aci` | | the account's own ACI; required for `linked` |
| `transport` | `stdio` | `stdio` (spawn `signal-cli jsonRpc`), `socket` (client of `daemon --socket`, POSIX) or `tcp` (client of `daemon --tcp 127.0.0.1:PORT`) |
| `socket`, `tcp` | | the daemon endpoint for those two transports |
| `receive_mode` | `manual` | `manual` (the bridge calls `subscribeReceive`, so messages wait on Signal's server while it is down), `on-start` or `on-connection` |
| `data_dir` | `~/.halo/remote/signal-cli` | signal-cli's `-d` directory |
| `extra_args` | `[]` | more global flags, placed before the subcommand |

If signal-cli exits, or answers a request with a network error (`-3`), the
bridge respawns or reconnects it with a growing delay (1, 2, 4, 8, 15, 30 s).
Other signal-cli errors are told apart by their JSON-RPC code, never by their
text: `-4` an untrusted or changed key (the peer is blocked, below), `-5` a
server rate limit (sending pauses for `retryAfterSeconds` and the captcha
token is shown to you as a notice), `-1` a user error, `-6` a rejected captcha.

### How pairing works

Pairing is a contact request that you approve on the computer, followed by a
one-time code typed on the phone. Nobody is answered before it finishes.

1. On the phone, open a chat with the Halo number and send any message
   (for example `hi`). Nothing comes back; that is expected.
2. On the computer, the bridge shows a contact request: the sender's ACI
   (and number, when Signal gave one) and the safety number signal-cli holds
   for that key. Compare the safety number with the one on your phone
   (Signal: the chat's name, then View safety number).
3. Approve the request on the computer. The bridge then tells signal-cli to
   trust that key with exactly that safety number, and shows you a six-digit
   code that is good for ten minutes.
4. On the phone, send that code as the next message, nothing else. The
   bridge replies once with `Paired.`, the 32-word signing phrase and a
   `halo-remote://pair?...` link (see Signing). The phone is now stored in
   `peers.json` under its ACI.

Chatter before the code is ignored. Three wrong six-digit codes, or ten
minutes, drop the request, and a new message starts a new one. In `linked`
mode the "phone" is your own account writing to Note to Self; the trust step
is skipped and only that conversation is read.

If a paired phone's safety number changes (a new phone, a reinstall), signal-cli reports an untrusted
identity. The bridge marks the peer blocked, tells you, and ignores its
messages until you confirm the new safety number with `reverify`. A peer is
removed with `unpair` (from the computer, or `/remote unpair` from the
phone). Each peer may send `remote.rate_per_minute` commands a minute
(default 30); over that, commands are dropped and the phone is told once.

### Signing

After pairing, every command carries a signature that only your phone can
make. The bridge creates a random 256-bit secret per peer and shows it once,
as a link and as 32 words (one of 256 words per byte; `phrase_to_secret`
reverses it). A command is the text, a space, and `#<counter>:<mac>`:

```
/status #1:9ef2aa6c
```

* `mac` is the first 8 lowercase hex characters of `HMAC-SHA256(key = the 32
  secret bytes, data = UTF-8 of "<counter>|<text>")`. `<counter>` is a
  decimal number with no leading zeros and `<text>` is the command exactly as
  typed, without the trailer or the space before it.
* The counter must be strictly greater than the last accepted one (gaps are
  fine), and the message's own timestamp must be within 5 minutes
  (`remote.stale_window_s`) of the computer's clock. A repeat or a lower
  counter is refused with a notice; a refused command does not use up its
  counter.
* Any HMAC tool on the phone can compute it. Worked example (a test vector,
  never a real secret): with the secret bytes `00 01 02 ... 1f`
  (hex `000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f`),
  `/status` with counter 1 signs as `/status #1:9ef2aa6c`, and
  `run the tests` with counter 7 as `run the tests #7:e3173adf`.
* `signed: false` on a peer in `peers.json` turns the check off for that
  peer, leaving the pairing and the Signal encryption in place.

### Chat commands

Plain text is a prompt (or a steer while a turn is running). The first
command attaches the most recently started live session.

| Message | What it does |
|---|---|
| `/sessions` | numbered live sessions (title, folder, phase); `*` marks the attached one |
| `/attach <n>` | attach session number n |
| `/status` | model, mode, effort, context, cost, cards waiting on you |
| `/stop` | interrupt the running turn |
| `/mode <name>`, `/model <ref>`, `/effort <level>` | switch them in the attached session |
| `/quiet`, `/loud` | relay only cards, errors and the closing line / also the session's text |
| `/tail <n>` | the last n messages of the conversation |
| `/remote pair`, `/remote unpair`, `/remote status` | add another phone (instructions), remove this phone, show this pairing |
| any other `/x` | run as a Halo slash command in the session |

While a card is open: permission `1` allow once, `2` allow for the session,
`3` always allow, `4` deny (`4 <reason>` tells the model why); a question is
answered with its letter (`b`, or `a,c`) or by typing the answer; a plan
review with `approve` or `feedback <notes>`; an approval gate with `accept`,
`edit <instruction>` or `stop`. Replies are plain text: Markdown is flattened,
code keeps its lines and is marked monospace, a message holds at most 1800
bytes (long output is split on spaces), and an answer longer than four
messages arrives as one short message plus `reply.txt`. A running turn shows
Signal's typing indicator, and each finished turn ends with a `Done.` line
carrying the cost. A long prompt typed on the phone arrives as an attachment;
the bridge reads it, then deletes the downloaded file.

### What is stored where

All under `~/.halo/remote/` (directory 0700, files 0600):

| File | Holds |
|---|---|
| `signal.json` | the signal-cli settings above |
| `signal-cli/` | signal-cli's own data (keys, account database) |
| `peers.json` | per paired phone: ACI, number, safety number, paired time, signing secret and counter, `signed`, blocked state |
| `pending.json` | open contact requests (the pairing code only as a salted hash), queued trust steps, notices for the computer |
| `audit.jsonl` | one line per command: time, the first 8 characters of the ACI, `sha256("<aci>\|<counter>\|<text>")` truncated to 16 hex, kind and outcome |

No message text, reply or attachment is written by the bridge, logged, or
kept: the audit hash cannot be reversed, `signal-cli` runs with `--scrub-log`
and its stderr is discarded, replies leave as a `data:` URI attachment rather
than a file, and a downloaded attachment is deleted as soon as it is read.

## Config keys

| Key | Default | Meaning |
|---|---|---|
| `remote.enabled` | `false` | open a control socket and registry entry for each session |
| `remote.rate_per_minute` | `30` | commands per minute per paired phone; over it the bridge drops them and tells the phone once |
| `remote.verbosity` | `loud` | what a newly attached phone is sent: `loud` (the session's text, cards, errors) or `quiet` (cards, errors, the closing line); `/quiet` and `/loud` change it per phone |
| `remote.stale_window_s` | `300` | a signed command whose message timestamp is further than this from the computer's clock is refused |
| `remote.pair_code_ttl_s` | `600` | how long the one-time pairing code stays valid |
