# Halo 2.0.10 review, round 5 (fix pass 3): remote control 1-5, subprocesses 21-23, supply chain 26-27, then the SWEEP

Repo: `<repo>` (branch master; start from HEAD after round 4 `3725d23`,
clean). Read `plans/WORKER-RULES.md` FIRST and follow every rule in it
(test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies.

Source of truth: `docs/harness/SECURITY-REVIEW-2.0.10.md` sections A, E
and G (read each finding in full). Standing contract (plans/HANDOFF.md):
no new gates, no safety or refusal language; these are correctness and
hardening fixes of what the docs already promise. docs/REMOTE.md is the
remote-control threat model; keep its six layers true.

## Findings to fix (each at the source, each pinned in `tests/test_security_round5.py`, split 5b/5c at the 250-line cap)

Remote control (`halo_harness/remote/`):
- **1** `phrase_to_secret` accepts an empty phrase or any word count ->
  it raises `ValueError` unless exactly 32 known words; `pair_uri`
  parsing likewise validates length and hex.
- **2** the signing secret is sent inside the Signal chat -> the phrase
  and link are shown ONLY in the TUI/CLI (as round 4's dialog already
  does); the chat reply after pairing says "Paired. Your signing phrase is
  on the Halo screen." and nothing else; the per-peer `signed` default
  and the docs follow.
- **3** the phone permission card truncates the command and hides what
  `3` persists -> the card shows the full command (chunked if needed)
  and labels `3` with the exact rule that will be written.
- **4** a peer with no secret verifies against an empty HMAC key -> a
  peer with `signed: true` and no secret REFUSES every command with a
  notice to re-pair; `signed: false` is the only unsigned path.
- **5** rate limit runs before the signature check; unbounded audit,
  contact table and control-socket slots -> signature check first, then
  rate limit; audit.jsonl rotates at 5 MB (keep one previous file);
  pending contact requests capped (32, oldest dropped); subscriber slots
  per control socket capped (16).

Subprocesses (`remote/signal_install.py`, `agent/cc_runtime.py`, `remote/cli_*`):
- **21** signal-cli archive installed without a pinned digest; gpg success
  means "any key in the keyring"; the install fails open -> pin the
  SHA-256 of the 0.14.9 assets per OS in `signal_install.py` (the worker
  fetches the real digests ONCE from the release page/`.sha256` files
  and records their URLs in the docstring; if a digest cannot be fetched
  here, leave a clearly named placeholder constant and make setup refuse
  until it is filled -- say so); verify the digest before unpacking;
  gpg, when used, must verify against the pinned signal-cli release key
  fingerprint (document it; do not download keys silently); the tar
  extraction rejects device members, absolute paths and `..`.
- **22** the `cc:` route trusts `--tools ""` and never checks it -> read
  back the tool list from the first `system.init` (the capabilities the
  2.0.5 control channel already captures) and refuse to continue with a
  notice if the child advertises tools it was told not to have.
- **23** the registration-lock PIN and SMS code travel on argv -> pass
  them via stdin or a temp file 0600 where signal-cli supports it (check
  `register`/`verify`/`setPin` in the JSON-RPC surface from
  SIGNAL-RESEARCH section 1; the JSON-RPC path takes them as params, not
  argv -- prefer it), never in `ps` output.

Supply chain (`scripts/install-halo.sh|.ps1`, `pyproject.toml`, CI):
- **26** the install one-liner runs a mutable master with no checksum or
  tag -> the scripts install the latest TAG by default (`--ref` to
  override), and README's one-liner pins the script to a tag URL; the
  script prints the tag and commit it installs.
- **27** dependencies unpinned and unaudited -> `requirements.lock` with
  hashes regenerated (uv or pip-compile, stdlib-free; document the
  command), the installer uses it, CI gains a `pip-audit` step (fails on
  known CVEs, with an allowlist file for accepted ones) -- edit
  `.github/workflows/suites.yml` for both jobs.

If a finding is wrong against the current code, mark it REJECTED with
evidence.

## Then the SWEEP

`plans/briefs/2.0.10-review/SWEEP.md` (<= 120 lines): every finding 1-27
with status (fixed in round N / rejected: reason / left: reason), the
residual risks copied from the review doc with any change, and the
three contract lines restated.

## Deliverables

1. The fixes, pinned, old-code checks noted.
2. CHANGELOG `[2.0.10] - unreleased` "### Security review fix pass, round
   3 (remote control, subprocesses, supply chain)".
3. Review doc "Fixed in round 5" lines; SWEEP.md; docs/REMOTE.md updated
   for 2, 3, 4 (pairing text, card text, signed semantics) and 21 (what
   setup verifies); README one-liner; docs/COMMANDS.md for `--ref`.

## Verification before hand-back

The new modules, every `tests/test_remote_*` suite, `tests.test_cc_session`,
`tests.test_cc_models`, the install-script tests (`ls tests | grep -i install`),
every touched module's tests, `python test_bridge.py`, `python -m tests.test_invariants`,
`python -m tests.test_privacy_scan`, `python -m tests.test_docs_links`,
`python -m tests.test_docs_commands`, `python -m halo_harness audit privacy`,
and `python -m pyflakes halo_harness/ bridge.py | grep "undefined name"`
printing nothing. `python test_tui.py` only if `tui/` changed. Hand back
ONCE, under 60 lines, then end your run: RESULT LINES (one per finding
1-5, 21-23, 26-27), FILES TOUCHED, WHAT YOU FOUND (incl. whether the
signal-cli digests were fetched or left as placeholders). No commit, no
push.
