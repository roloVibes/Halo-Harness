# HALO-PACK.md: working on the Signal pack

You are working in the folder of a Halo pack. Read this page first, then follow its loop for every change. The full
guide is Halo's `docs/PACK-AUTHORING.md`; the contract is `docs/EXTENSION_API.md` (the transport seam this pack uses
is its "Transports" section, the service it runs "Services").

## What this pack is

`signal` (pack.yaml: `id`), "Signal": Halo on your phone through Signal, as a conversation. What it brings:

- **the service** `signal/bridge` (`contributes.services`): `bin/signal.py service`, kept running by `halo supervise`,
  its health in the data folder's `health.json`;
- **the entry command** `/signal` (`commands/signal.md`, `run:` -- the pack's program, no model call): `bin/signal.py
  ctl <verb>`;
- **Setup blocks** (`contributes.setup`): Signal on this box, the account (link / a number), a test message, pairing,
  the phones, the conversation's settings, the service -- each check is `bin/signal.py setup <block>`;
- **the requirement** signal-cli (`requires:`, GPL-3.0; never installed by Halo) and **settings** (`config`).

## The code

`halo_signal/` imports `halo_harness.ext` and nothing else of Halo; the core's sessions, cards, notes, speech and QR
drawing come through `ext.remote`. The loop is `bridge.py` (one thread); an envelope goes through `inbound.py`
(who, signed, rate, receipt) to `routing.py` (a card's answer, a chat command in `chat.py`, a prompt); the attached
session is `session.py` (attach, start one, the feed thread) and its events `feed.py` (the answer through `relay.py`
paragraph by paragraph, the cards, the closing line); `notes.py` carries the core's notes per phone; `media.py`
files both ways; `pairing.py` + `pairing_trust.py` who may talk; `phones.py` each phone's session, home and notes;
`transport.py` + `calls.py` + `link.py` + `errors.py` + `typing_keeper.py` the signal-cli JSON-RPC client; `ctl.py`,
`ctl_account.py`, `setup.py`, `service.py`, `main.py` the program's verbs.

## The loop

1. Edit the files. Keep each code file at 250 lines or fewer.
2. `halo pack test .` -- every check in a scratch home, then the pack's own `tests/test_*.py` (one check each). They
   use fakes only: `tests/support.py` (a stub transport, a fake clock), `tests/fake_session.py` (sessions as the
   bridge sees them), `tests/fake_signal_cli.py` and `tests/fake_signal_admin.py` (signal-cli stand-ins). Never run
   the real signal-cli in a test and never send a Signal message. `python -m tests.<module>` runs one.
3. `halo pack install . --link --project`, `halo pack enable signal --grant-all`, `halo supervise` -- try it.
4. `halo pack doctor` -- nothing about this pack left.

## The rules

- No message text at rest: the audit line is a hash; a phone's file waits in `inbox/` and goes after a day.
- A secret (a signing secret, the registration PIN) is shown on the computer once and never sent in the chat; a PIN
  travels to signal-cli on stdin, never in argv.
- The service holds no provider key (the supervisor leaves them out); a session for a phone is started by the
  supervisor through `ext.remote.start_session`.
- Offers say what they do: every Setup check has its what / cost / time / writes lines.
