# Halo 2.0.9 Signal remote control, round 2: the per-session control socket + sessions registry

Repo: `<repo>` (branch master; start from HEAD after round 1 `0df8bac`,
clean). Read `plans/WORKER-RULES.md` FIRST and follow every rule in it
(test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies.

Design: `plans/2.0.8-signal-brief.md` section 3 ("Session control
surface"), AS ADJUSTED by `docs/harness/SIGNAL-RESEARCH.md` section 9
(the verified Controller method table 9.1, the Command/Event kinds 9.2-9.3,
the tee requirement 9.4, the cc: run-dir pattern 9.5, the lifted inputs
9.6). Section 9 supersedes the brief wherever they differ. Read both
before coding, then `halo_harness/controller.py`, `halo_harness/events.py`,
`halo_harness/ccbridge/server.py` (the Windows loopback+token pattern and
the POSIX socket pattern to copy), `halo_harness/headless.py`
(`run_print_mode`, the stream-json stdin queue) and `halo_harness/tui/app.py`
(`_drain`, `resolve_permission_decision`).

## Deliverables

1. **`halo_harness/remote/__init__.py` + `remote/handle.py`**: a small
   `SessionHandle` protocol (submit, interrupt, set_mode, set_model,
   set_effort, answer_permission/question/plan/approval, run_slash,
   status, tail, subscribe/unsubscribe) with TWO implementations:
   `ControllerHandle` (wraps `Controller`, every method per table 9.1,
   including the "session"/"always" permission answers via
   `add_permission_rule` exactly as the TUI does) and `PrintModeHandle`
   (wraps the print-mode session: submit feeds the stream-json input
   queue, answers go to the same waiters the sinks use). Event feed: a
   tee inserted where `Controller.start()` hands `self.events.put` to
   `session.run` (and the print-mode equivalent) so the TUI's single
   consumer loses nothing; subscribers get coalesced events only
   (`text_delta` buffered into one `text_chunk` per 2 s or 1800 bytes;
   every other kind in 9.3 forwarded as-is with its payload).
2. **`remote/control_socket.py`**: the server. POSIX: Unix socket
   `~/.halo/run/<session_id>.ctl`, 0600, run dir 0700. Windows: loopback
   TCP on an OS-assigned port with a random 16-byte hex token; first line
   must be `{"token": ...}` within 5 s (copy `ccbridge/server.py`). Wire:
   newline JSON `{"id", "cmd", ...}` -> `{"id", "ok": true, "result"}` or
   `{"id", "ok": false, "error"}`; `cmd` set exactly: `status`, `submit`,
   `steer` (alias of submit), `interrupt`, `answer` (`{"kind":
   "permission"|"question"|"plan"|"approval", "id", ...}`), `model`,
   `effort`, `mode`, `slash`, `tail` (`{"n"}` last n messages rendered as
   Markdown), `subscribe`, `unsubscribe`, `ping`. Multiple clients;
   subscriptions are per connection; a slow subscriber is dropped after a
   bounded queue (256 events) fills, never blocking the session. Nothing
   listens on a non-loopback address; the token is never logged.
3. **`remote/registry.py`**: `~/.halo/run/sessions.json`, written
   atomically (temp + replace, the `filelock.py` best-effort lock from
   2.0.7.1), entries `{session_id, cwd, pid, endpoint, token_env|None,
   started, title, mode}`; `register`, `unregister`, `list_live` (drops
   entries whose pid is gone or whose endpoint refuses a connect probe,
   same sweep idea as the cc: `*.sock` cleanup), `endpoint_for(session_id)`.
   Title refreshes when the session's auto-title lands (hook the existing
   title event/update path).
4. **Wiring, behind config `remote.enabled` (default false this round)**:
   the TUI opens the socket at start and closes it on quit (including the
   Ctrl+C quit card path and the crash/atexit path from 2.0.7 round 7c);
   print mode (`halo -p`, incl. `--bg`) does the same; `/remote` in the
   TUI shows "control socket: on <endpoint>" or "off" plus the registry
   count this round (the full `/remote` dialog is round 4). `halo remote
   sessions` (new CLI stub under `remote/cli.py`) lists `list_live()`; it is
   the only CLI surface this round. Commands arriving over the socket
   appear in the transcript tagged `(remote)` via the existing
   `system_note`/`notification` path, never as a user bubble.
5. **Tests + docs**: `tests/test_remote_control_socket.py` (fake client:
   every `cmd` round-trips against a mock session; token required on
   Windows and a bad token is dropped; the feed delivers a
   `permission_request` and `answer` resolves it; the TUI's own queue
   still receives every event -- a tee test; a slow subscriber is dropped
   without stalling; the socket file/endpoint disappears on quit),
   `tests/test_remote_registry.py` (atomic write, dead-pid sweep, probe
   sweep, title refresh), a print-mode test driving `halo -p` with
   `remote.enabled` true and talking to its socket (POSIX-only skip is
   acceptable for the Unix-socket half; the Windows half must run on
   this host). docs: `docs/REMOTE.md` started (what the control socket
   is, the wire, the registry, the config key; the Signal parts come in
   rounds 3-4), docs/CONFIG.md (`remote.enabled`), docs/COMMANDS.md
   (`halo remote sessions`), docs/SLASH-COMMANDS.md (`/remote`, this
   round's one-line form), CHANGELOG `## [2.0.9] - unreleased` "### Remote
   control: the session control socket".

## Hard constraints

No safety or refusal language anywhere (an authenticated local client
can do everything the keyboard can). No real paths or names; no new
dependency (stdlib `socket`, `json`, `threading`, `secrets`); never block
the UI thread (the server runs on its own daemon thread; Controller
calls are already thread-safe per 9.1, verify `run_slash` and `tail`
are too or marshal them); every file write <= 250 lines (split
`control_socket.py` into server + protocol modules if needed). The
`cc:` bridge's `*.sock` files and sweep are untouched.

## Verification before hand-back

The new test modules, `tests.test_round_0b_status_notices`,
`tests.test_cc_session` (the run-dir sweep must still pass),
`tests.test_cli_flags`, `tests.test_ctrl_c_copy_quit`, `tests.test_console_mode`,
every touched module's tests, `python test_bridge.py`, `python test_tui.py`
once (revert snapshot churn with `git checkout -- <file>` and say which),
`python -m tests.test_invariants`, `python -m tests.test_privacy_scan`,
`python -m tests.test_docs_commands`, `python -m tests.test_docs_slash_commands`,
`python -m halo_harness audit privacy`, and `python -m pyflakes
halo_harness/ bridge.py | grep "undefined name"` printing nothing. Hand
back ONCE, under 60 lines, then end your run: RESULT LINES (1-5), FILES
TOUCHED, WHAT YOU FOUND (the exact `SessionHandle` surface round 3's
bridge will call, in ten lines; anything left open and why). No commit,
no push.
