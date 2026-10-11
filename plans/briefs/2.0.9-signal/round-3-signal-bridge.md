# Halo 2.0.9 Signal remote control, round 3: signal-cli transport, the bridge, pairing, signing, rendering

Repo: `<repo>` (branch master; start from HEAD after round 2 `797e053`,
clean). Read `plans/WORKER-RULES.md` FIRST and follow every rule in it
(test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies.

Design: `plans/2.0.8-signal-brief.md` sections 1-3 (transport, the six
security layers, the bridge and chat commands) AS ADJUSTED by
`docs/harness/SIGNAL-RESEARCH.md` section 8 (every bullet there is a
decision for this round; section 8 wins over the brief) with the JSON
shapes, limits and error codes of its sections 1, 3 and 4. The session
side is round 2's control socket: read `halo_harness/remote/protocol.py`,
`remote/client.py` (`ControlClient`), `remote/registry.py` (`list_live`,
`entry_for`, `default_token_for`) and `docs/REMOTE.md`. No hardware or
network is used in this round: everything is tested against a fake
signal-cli JSON-RPC child.

## Deliverables

1. **`remote/signal_transport.py`**: the signal-cli client. Default
   transport = a spawned `signal-cli -a <account> --trust-new-identities
   never --scrub-log -d <remote dir>/signal-cli jsonRpc` child over
   stdio (newline JSON-RPC 2.0 both ways; notifications `receive`
   envelopes); optional `daemon --socket` (POSIX) / `daemon --tcp
   127.0.0.1:<port>` (Windows) client for the service-manager install.
   `send`, `sendTyping` (re-sent every 10 s while a turn runs, `stop`
   at turn_done), `sendReceipt type=read` after a command passes the
   checks, `listIdentities`, `trust`, `subscribeReceive` when
   `--receive-mode manual` is in use. Reconnect/respawn with backoff on
   exit or `-3`; the error-code map from section 8 (`-4` identity, `-5`
   rate limit + captcha token surfaced, `-1`, `-6`). The signal-cli
   binary path, account and flags come from `~/.halo/remote/signal.json`
   (written by round 4's setup; this round reads it and documents it).
   Attachments: inbound `text/x-signal-plain` from a paired peer becomes
   the prompt text, every other attachment is ignored, the downloaded
   file is deleted after reading; outbound long replies use a
   `data:text/plain;filename=reply.txt;base64,...` attachment (never a
   file on disk).
2. **`remote/pairing.py` + `~/.halo/remote/peers.json`** (0600, dir
   0700): peers keyed on the ACI (`sourceUuid`), storing
   `{aci, number|None, safety_number, paired_at, signing: {secret_hex|None,
   counter}, signed: bool}`. The contact-request flow of section 8
   (shape B): an unknown sender's envelope (incl. the `exception` /
   untrusted-identity notification) is NEVER answered; it becomes a
   pending contact request `{aci, number, safety_number (from
   listIdentities), first_seen}` exposed through `pairing.pending()` for
   round 4's `/remote` card and `halo remote signal pair`; `approve(aci)`
   calls `trust` with `verifiedSafetyNumber`, generates the one-time
   pairing code (6 digits, 10-minute expiry) and returns it for display;
   the phone's next message must be exactly that code (whitespace-
   trimmed) -> peer written, reply "Paired. Signing secret: <QR-able
   phrase>" ONCE (see 3). A changed safety number (receive-side
   `UntrustedIdentityException` notification, or `-4` on send) marks the
   peer `blocked_until_reverified` and surfaces a notice; `reverify(aci)`
   repeats the trust step. `unpair(aci)`. Rate limit per peer:
   `remote.rate_per_minute` (default 30); over it, drop and notify once.
3. **`remote/signing.py`**: after pairing, a 256-bit secret per peer
   (`secrets.token_bytes`), shown once as a 12-word phrase from a built-in
   wordlist (original list, 256 common English words -> 12 words of 8
   bits; no BIP39 copy) and a QR-able `halo-remote://pair?...` string
   (text only; QR rendering is round 4). Each signed command is
   `<text> #<counter>:<hmac8>` where `hmac8` = first 8 hex chars of
   `HMAC-SHA256(secret, f"{counter}|{text}")`; the bridge requires a
   strictly increasing counter and a 5-minute window on the envelope
   timestamp; replay (same or lower counter) is refused with a notice;
   `signed: false` on a peer disables the check (layers 1-2 remain). A
   signing helper CLI for the phone side is NOT in scope (the phone
   types `#n:hash` from any HMAC app); document the exact bytes so round
   4 can print worked examples.
4. **`remote/bridge.py`**: the daemon loop (`run_bridge(config, transport,
   registry, clock)` with injectable pieces). State: attached session per
   peer (default: the most recently started live session), verbosity
   (`/quiet` = only cards, errors and turn_done; `/loud` = coalesced
   text_chunks too). Inbound routing: plain text -> `submit`/`steer`;
   `/sessions` (numbered list from `registry.list_live()` with title,
   cwd tail, phase), `/attach <n>`, `/status`, `/stop` -> interrupt,
   `/mode <name>`, `/model <ref>`, `/effort <level>`, `/quiet`, `/loud`,
   `/tail <n>`, `/remote pair|unpair|status`, numbered replies while a
   permission card is open (`1` allow once, `2` session, `3` always, `4`
   deny, `4 <reason>`), lettered replies while a question is open,
   `approve`/`feedback <text>` while a plan review is open, any other
   `/x` -> `slash`. Outbound rendering (`remote/render.py`): Markdown
   flattened to plain text (headings as upper-case lines, lists with
   `-`, code fences kept verbatim with the optional MONOSPACE `textStyle`
   span from section 8), chunked at <= 1800 UTF-8 bytes on whitespace;
   more than 4 chunks -> one message + text attachment; streaming
   coalesced to one message per `text_chunk` frame; cards rendered as
   numbered/lettered choices with the tool name and the one-line reason;
   `turn_done` closes with the cost line from `status`. Audit: one
   hashed line per command (`sha256(aci|counter|text)[:16]`, kind,
   outcome, ts) to `~/.halo/remote/audit.jsonl`; NO message content is
   ever logged or stored by the bridge (pin it).
5. **Tests + docs**: `tests/helpers/fake_signal_cli.py` (a Python script
   the transport spawns in place of signal-cli: speaks JSON-RPC 2.0 over
   stdio, replays scripted `receive` notifications built from the
   section 3 shapes, records every request, can inject `-3`/`-4`/`-5`
   errors and an untrusted-identity notification on demand);
   `tests/test_remote_signal_transport.py` (spawn, send, typing cadence,
   receipt after checks only, reconnect with backoff, error map,
   attachment in/out rules incl. the download being deleted);
   `tests/test_remote_pairing.py` (unknown sender never answered; contact
   request pending; approve -> trust called with the safety number ->
   code; wrong code x3 -> request dropped; expiry; peer written 0600;
   changed safety number blocks until reverify; unpair; rate limit);
   `tests/test_remote_signing.py` (phrase round-trip, HMAC vector with
   fixed secret/counter/text documented in docs, replay refused, window
   refused, signed:false bypass); `tests/test_remote_bridge.py` (every
   chat command against a fake control socket from round 2's helpers,
   permission card answered from the phone by number, question by
   letter, plan by approve, quiet/loud, chunking at the byte limit and
   the attachment fallback, no message content in any file under the
   scratch home -- grep the whole BRIDGE_TEST_HOME for a sentinel
   phrase). Docs: `docs/REMOTE.md` gains "How pairing works" (the
   contact-request flow with the exact phone-side steps), "Signing",
   "Chat commands" and "What is stored where"; `docs/CONFIG.md` the
   `remote.*` keys this round reads; CHANGELOG `[2.0.9] - unreleased`
   "### Remote control: the Signal bridge". Round 4 owns the CLI
   (`halo remote signal setup|register|link|run|pair|...`), the TUI
   `/remote` dialog and the status chip; this round exposes functions
   for them, nothing more.

## Hard constraints

No safety or refusal language anywhere: a paired, verified owner can do
everything the keyboard can; the pairing and signing layers are
authentication, described as such. No real phone numbers, names,
account ids or secrets in the tree (tests use obviously fake ACIs such
as `00000000-0000-4000-8000-000000000001`); the privacy scan must stay
green. No new dependency (stdlib `hmac`, `hashlib`, `secrets`, `base64`,
`json`, `subprocess`, `threading`). Never block the UI thread (the
bridge is its own process in round 4; here it is a function with
injected transport and clock). Every file write <= 250 lines (split
`bridge.py` into `bridge.py` + `bridge_commands.py` + `render.py`).

## Verification before hand-back

The new test modules, the four round 2 remote suites, every touched
module's tests, `python test_bridge.py`, `python -m tests.test_invariants`,
`python -m tests.test_privacy_scan`, `python -m tests.test_docs_links`,
`python -m tests.test_docs_commands`, `python -m halo_harness audit privacy`,
and `python -m pyflakes halo_harness/ bridge.py | grep "undefined name"`
printing nothing. (test_tui only if `tui/` was touched -- it should not
be.) Hand back ONCE, under 60 lines, then end your run: RESULT LINES
(1-5), FILES TOUCHED, WHAT YOU FOUND (the function surface round 4's CLI
and `/remote` dialog call, in about ten lines; the unresolved live
checks that need the real signal-cli; anything left open and why). No
commit, no push.
