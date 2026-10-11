# Halo 2.0.9 Signal remote control, round 4: the CLI, the TUI `/remote` dialog and status chip, doctor, docs

Repo: `<repo>` (branch master; start from HEAD after round 3 `069f38d`,
clean). Read `plans/WORKER-RULES.md` FIRST and follow every rule in it
(test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies.

Design: `plans/2.0.8-signal-brief.md` section 3 (TUI side, CLI) and
section 1 (setup: dedicated number first, linked device as the
documented alternative), as adjusted by `docs/harness/SIGNAL-RESEARCH.md`
sections 2 (registration, captcha, linking), 5 (per-OS operation, proxy,
egress hosts) and 8 (flags, version pin, registration lock). Rounds 2-3
built everything below the surface; read `halo_harness/remote/__init__.py`
and the function surface in `docs/REMOTE.md`, then `remote/cli.py`
(`halo remote sessions` from round 2), `remote/signal_config.py`,
`remote/pairing.py` (`pending`, `approve`, `reverify`, `unpair`, `peers`,
`set_signed`, `notices`), `remote/signing.py` (`pair_uri`,
`secret_to_phrase`), `remote/bridge.py` (`run_bridge`), `remote/runtime.py`
(`status_line`), `halo_harness/doctor.py` (the `_check_*` pattern and
`--json` from 2.0.7.1 round 9), `tui/dialogs/mcp_status.py` and
`tui/dialogs/subscription_notice.py` (dialog patterns), the status bar's
`statusbar.py` and the HUD slots (a chip must also be a HUD slot).

## Deliverables

1. **CLI `halo remote signal ...`** in `remote/cli.py` (+ `remote/cli_signal.py`
   if needed): `setup` (asks dedicated-number vs linked-device; locates or
   downloads signal-cli 0.14.9 to `~/.halo/remote/signal-cli/` for this OS
   per research section 1 -- Linux x86-64 native tarball, otherwise the JVM
   build and a JRE 25 check; verifies the `.asc` with `gpg` when present;
   writes `~/.halo/remote/signal.json`; never installs system-wide; the
   download itself is behind an explicit confirmation and is mocked in
   tests), `register <number>` (captcha flow: prints the captcha URL,
   accepts the token, `--voice` fallback only after an SMS attempt,
   `-5` rate limit surfaced with `retryAfterSeconds`, sets a registration
   lock PIN stored 0600), `link` (prints the `sgnl://linkdevice` URI as text
   and as a terminal QR -- write a small stdlib QR encoder for alphanumeric/
   byte mode, version <= 10, EC level L, rendered with half-block glyphs;
   pin it against a known vector), `run [--daemon]` (`run_bridge` in the
   foreground; `--daemon` writes a systemd user unit on Linux, a launchd
   plist on macOS, a Task Scheduler XML on Windows, under `~/.halo/remote/`,
   and prints the one enable command -- never enables it itself), `pair`
   (lists pending contact requests with safety numbers, approves one by
   index, prints the 6-digit code and, once the peer is paired, the
   32-word phrase + the `halo-remote://` link as text and QR), `peers`,
   `unpair <aci-prefix>`, `reverify <aci-prefix>`, `status` (bridge pid /
   signal-cli version / account / peers / last audit ts), `off` (the kill
   switch: stops a running bridge via a stop file the bridge polls, and
   sets `remote.signal.enabled=false`). Every subcommand has `--json`.
   `remote` joins `completion_cli` subcommands with its verbs.
2. **TUI `/remote` dialog** (`tui/dialogs/remote_status.py`): bridge
   state (off / starting / connected / rate-limited / stopped), the
   control-socket line from round 2, the peers table (ACI prefix, number
   if any, paired_at, signed, blocked), the pending contact requests with
   an Approve button that runs `pairing.approve` and shows the code large,
   the phrase + link after pairing (shown once, with "I wrote it down"
   to dismiss), per-peer `signed` toggle, Unpair, Reverify, and the kill
   switch (`Off`); chords only, Esc closes. `/remote pair|off|status` as
   argument forms do the same without the dialog. Notices from
   `pairing.notices()` (changed safety number, rate limit, captcha) are
   surfaced as TUI notifications and cleared.
3. **Status chip + HUD slot**: a `remote` slot (`⇄ remote` / ASCII `<>
   remote`, with the attached peer count) in the default status bar while a
   peer is attached to THIS session, driven by a `remote_attached` field
   the bridge sets through the control socket (`status` already carries
   session_id; add a `remote.attached` notification the bridge sends on
   attach/detach via a new `note` cmd on the socket -- the one protocol
   addition this round, documented). The three game skins get the slot in
   their tickers. Commands from Signal keep the `(remote)` tag from round 2.
4. **doctor**: `_check_remote()` -- `remote.enabled`, the registry count,
   signal-cli present + version vs the 0.14.9 pin (warn at 90 days from
   its release date), JRE when the JVM build is used, `~/.halo/remote/`
   permissions, egress hosts to allow (the seven `*.signal.org` names) when
   a proxy is configured; `--json` shape consistent with 2.0.7.1 round 9.
   `halo preflight` untouched.
5. **Docs + release prep**: `docs/REMOTE.md` completed -- threat model
   (the six layers, what each stops, what it does not), the two identity
   models with the exact setup per OS (Kali/Linux native, Windows JVM +
   `--tcp`, macOS JVM), the proxied-VM recipe (`JAVA_TOOL_OPTIONS`), the
   full chat-command list, the pairing walkthrough with screenshots of the
   dialog (`scripts/screenshots.py` scene `remote-dialog`), the daemon
   install per OS, and "Live verification" (the checklist the owner runs
   with a real number: pair from the phone, `/sessions`, attach, prompt,
   streamed reply, answer a permission card by number, `/stop`, unpair, a
   second phone must be ignored) with the research doc's unresolved live
   checks listed as "confirm on first live run". `docs/COMMANDS.md`,
   `docs/SLASH-COMMANDS.md`, `docs/CONFIG.md` (`remote.signal.*`),
   HANDBOOK a short "Remote control from Signal" section pointing at
   REMOTE.md, README one feature bullet + a row in the feature grid,
   CHANGELOG `[2.0.9] - unreleased` "### Remote control: CLI, `/remote`,
   doctor".

## Hard constraints

No safety or refusal language anywhere (authentication is described as
authentication). No real phone numbers, names, account ids or secrets;
tests use obviously fake values; the privacy scan must stay green. No
new dependency (the QR encoder is stdlib and original; the Reed-Solomon
tables are computed, not copied). Never block the UI thread (the dialog
calls pairing on a worker and renders results on the UI thread; the
bridge is never started inside the TUI process -- `/remote` tells the
user to run `halo remote signal run` and shows its state). Every file
write <= 250 lines. The download in `setup` is mocked in every test;
no test touches the network.

## Verification before hand-back

The new test modules (`tests/test_remote_cli_signal.py`, `test_remote_qr.py`,
`test_remote_dialog.py`, `test_remote_doctor.py`, `test_remote_chip.py`),
all twelve existing remote suites, `tests.test_doctor*` (find them),
`tests.test_completion_cli`, `tests.test_hud_engine`, `tests.test_hud_mario`,
`tests.test_hud_metroid`, `tests.test_screenshots`, every touched module's
tests, `python test_bridge.py`, `python test_tui.py` once (keep NEW
snapshots; revert churn on existing ones and say which),
`python -m tests.test_invariants`, `python -m tests.test_privacy_scan`,
`python -m tests.test_docs_links`, `python -m tests.test_docs_commands`,
`python -m tests.test_docs_slash_commands`, `python -m tests.test_docs_hygiene`,
`python -m halo_harness audit privacy`, and `python -m pyflakes halo_harness/
bridge.py | grep "undefined name"` printing nothing. Hand back ONCE, under
60 lines, then end your run: RESULT LINES (1-5), FILES TOUCHED, WHAT YOU
FOUND (what the owner must do by hand for the live check, step by step;
anything left open and why). No commit, no push.
