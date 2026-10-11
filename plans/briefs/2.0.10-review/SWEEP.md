# 2.0.10 security review: final sweep (after round 5)

Every numbered finding 1-27 of `docs/harness/SECURITY-REVIEW-2.0.10.md`
walked against the tree at the end of round 5. Status key: fixed in round N
(pinned by the named test file), rejected (reason), left (reason).

Standing contract (plans/HANDOFF.md), restated:

1. Deny rules hold in every mode.
2. Auto mode with no rules stays allow (an explicit allow rule keeps
   matching exactly as before).
3. No new gates, no classifier-shaped suggestions, no safety or refusal
   language: these are correctness and hardening fixes of what the docs
   already promise.

## Summary

- Fixed: 26 of 27 (round 3: 6-10, 17-20; round 4: 12-16, 24-25; round 5:
  1-5, 21-23, 26-27).
- Rejected: 11 (contract, allow side).
- Left: none whole. Parts of 5 (expiry of pending requests), 26 (signed tags
  for the script itself) and 27 (actions pinned by commit) are left, listed
  under their rows.

## A. Remote control

| # | Status |
|---|--------|
| 1 | fixed in round 5: `phrase_to_secret` needs exactly 32 words; `secret_from_hex` / `parse_pair_uri` exactly 64 hex (`test_security_round5` f1) |
| 2 | fixed in round 5: the chat says only "Paired. Your signing phrase is on the Halo screen."; phrase, link and QR are shown on the computer only (f2) |
| 3 | fixed in round 5: the phone card shows the whole command and `3` names the rule it saves (f3) |
| 4 | fixed in round 5: `signed: true` with no usable secret refuses everything with a re-pair notice; `signed: false` is the only unsigned path (f4) |
| 5 | fixed in round 5: signature before rate limit with a separate bad-message counter, audit rotation at 5 MB, pending requests capped at 32, handler exceptions audited, control-socket feed cap 16 and a separate pre-auth pool (f5). Left: expiring pending requests after a day (the cap bounds the table instead) |

## B. Trust boundaries

| # | Status |
|---|--------|
| 6 | fixed in round 3: `.mcp.json` approval keys are trust-gated; `-p` approves project servers only in a trusted folder (`test_security_round3`) |
| 7 | fixed in round 3: `statusLine` and the other command-naming keys are trust-gated. `permissions.defaultMode` in an untrusted layer is unchanged (outside the finding) |
| 8 | fixed in round 3: https or loopback endpoints only; the token endpoint is pinned at login and used for refresh |
| 9 | fixed in round 3: server names with `__` become disabled placeholders; `suggest_rule` keeps the whole tool name |
| 10 | fixed in round 3: https only; a host from a project file is named and retyped before a token is stored |

## C. Permission engine

| # | Status |
|---|--------|
| 11 | rejected (contract): an explicit allow rule keeps matching exactly as before; no heuristic about dangerous commands is added. The deny side of the same shape is finding 12 |
| 12 | fixed in round 4: deny/ask rules hold through compound keywords, more wrappers, `-c` payloads, `find -exec` and PowerShell forms (`test_security_round4`) |
| 13 | fixed in round 4: tool-global options no longer hide the verb from deny/ask prefix rules |
| 14 | fixed in round 4: a malformed deny/ask rule is named at load, in `/permissions` and in `halo doctor` (`test_security_round4b`) |
| 15 | fixed in round 4: Read deny/ask rules reach `cat ~/...`, the Bash readers, and Grep/Glob over a directory |
| 16 | fixed in round 4: a rule is matched as written and with its symlinks resolved; Windows trailing dots and spaces are judged as the OS opens the file |

## D. Credentials

| # | Status |
|---|--------|
| 17 | fixed in round 3: both redactors learned nested JSON, URL credentials, backslash and numeric values |
| 18 | fixed in round 3: a redirect that changes scheme, host or port keeps only plain transport headers |
| 19 | fixed in round 3: signal-cli and `${VAR}` expansion use the secret-stripping child env; `mcp list/get` drop url queries |
| 20 | fixed in round 3: secret files are written private and atomic; allow-rule writes keep the file mode; constant-time proxy token compare |

## E. Subprocesses

| # | Status |
|---|--------|
| 21 | fixed in round 5: pinned SHA-256 per asset checked before unpacking (digests fetched from the release API), gpg counts only for the pinned key, tar rejects device/FIFO/link/absolute/`..` members (`test_security_round5b` f21). Left: the release key fingerprint is empty, so the gpg result reads `digest-only` |
| 22 | fixed in round 5: a built-in tool in the first `system.init` ends the `cc:` turn and stops the child (f22) |
| 23 | fixed in round 5: `setPin` and (when offered) `verify --pin` go through JSON-RPC stdin. Left: signal-cli 0.14.9 has no JSON-RPC `verify`, so `verify --pin` on a locked number still uses argv for that one call, with a printed note (f23) |

## F. File tools and state

| # | Status |
|---|--------|
| 24 | fixed in round 4: new state directories are 0700, transcripts, shadow index, spilled results and `bridge.log` are 0600; an existing tree is tightened once (POSIX) (`test_security_round4c`) |
| 25 | fixed in round 4: session ids and tool-use ids are validated or turned into safe file stems |

## G. Supply chain

| # | Status |
|---|--------|
| 26 | fixed in round 5: scripts install the newest tag or `--ref`, print tag and commit, pin the uv bootstrap, constrain versions with `requirements.lock`; README one-liners use a tag URL (`test_security_round5c` f26). Left: signed tags / a checksum file for the script itself; a clone left on a detached tag cannot `git pull` (re-run the installer or use `--ref master`) |
| 27 | fixed in round 5: hashed `requirements.lock` (command in its header), hashed install and a `pip-audit` gate with an allowlist file in both CI jobs (f27). Left: pinning the GitHub actions by commit; `uv tool install` does not enforce lock hashes (tested), so the installers constrain versions only |

## Residual risks (copied from the review, with changes)

- A paired, signed phone (or anyone holding the secret) does everything the
  keyboard does; there is no content filter, by design.
- Bash and PowerShell rules are string matching: variable indirection
  (`x=rm; $x y`), `$IFS` splitting, interpreters (`python -c`), `find -exec`
  (round 4 covers the plain forms), aliases and unlisted wrappers escape any
  pattern.
- The signing MAC is 32 bits. Changed in round 5: the online bound is the
  bad-message counter (10 a minute per peer), not the command budget; there is
  still no lockout after bad MACs.
- Secrets at rest are plaintext files, 0600 where tightened: the env file,
  `peers.json` signing secrets, OAuth tokens, signal-cli's key store, the
  registration PIN. No OS keyring.
- Transcripts keep whatever tools returned, secrets included, until exported
  with `--sanitize`; `redact.py` is best-effort (round 3 widened it).
- Another process running as the user reaches every control socket and reads
  all of the above; the Windows loopback port is open to every local account
  (token only); the Unix socket has no peer-credential check beyond mode 0600.
- Project skills, commands and agents can grant themselves temporary allow
  rules through frontmatter, as in Claude Code; hooks, MCP servers and plugins
  from user scope run as the user, unconfined.
- WebFetch reaches loopback and private hosts on purpose; a WebFetch deny
  rule is the only control.
- A `--plugin-url` clone is loaded once cloned and never re-verified.
- Shadow snapshots follow symlinks and junctions; Write and Edit truncate in
  place rather than replacing atomically.
- New in round 5: the signal-cli digests are GitHub's own `digest` values, so
  they catch a swapped or corrupted download, not a compromised release; the
  release key fingerprint is not pinned yet; the lock's hashes are enforced in
  CI, not by `uv tool install`.
