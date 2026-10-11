# Halo 2.0.10 review, round 4 (fix pass 2): permission engine 12-16, file tools and state 24-25 (11 is REJECTED)

Repo: `<repo>` (branch master; start from HEAD after round 3 `8376d4a`,
clean). Read `plans/WORKER-RULES.md` FIRST and follow every rule in it
(test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies.

Source of truth: `docs/harness/SECURITY-REVIEW-2.0.10.md` sections C and
F (read each finding in full). THE STANDING CONTRACT DECIDES THIS ROUND
(plans/HANDOFF.md, pinned by `tests/test_review2_round4.py`): deny and ask
rules the user wrote must hold in every mode; auto mode with NO rules
stays allow; the ALLOW side is never tightened and no heuristic about
"dangerous" commands is added. The owner rejected "allow-match
substitution refusal" in 2.0.7 by name. Therefore:

- **11 is REJECTED** (an explicit allow matching `ls $(...)`): that is the
  allow side. Record it in the review doc as "Rejected by the standing
  contract (allow side); the deny side is covered by 12" and do not
  change allow matching.
- **12, 13, 15** are fixed on the DENY/ASK side only: a user's deny or ask
  rule must hold when the same command is reached through `if/then`,
  `for/do`, `while`, `!`, `exec`, a wrapper (`watch`, `flock`, `unshare`,
  `strace`, `nice`, `timeout`, `env`, `sudo` -- the review's list plus the
  obvious siblings), PowerShell's equivalents, tool-global options between
  the binary and the subcommand (`git -C x push`, `docker --context x
  run`, `kubectl -n x delete`, `npm --prefix x run`), and the Bash readers
  for Read/Grep/Glob path rules (`cat`, `head`, `tail`, `less`, `sed`,
  `awk`, `grep`, `cp`, `python -c open(...)` is OUT of scope) plus `~`
  expansion and directory-wide Grep/Glob. Matching a deny through these
  forms is correctness of the user's own rule; the allow decision for the
  same command stays exactly what it is today.
- **14** a malformed deny/ask rule is surfaced (doctor, `/permissions`, a
  one-line notice at load) instead of silently inert; it is never
  "fixed up" into a different rule.
- **16** a path rule whose own text contains a symlink matches after
  resolving both sides the same way.
- **24** `~/.halo`, sessions and shadow snapshots are created 0700/0600
  (POSIX; a no-op on Windows), existing trees are tightened once at
  launch with a single notice.
- **25** provider- and CLI-supplied ids (`tool_use_id`, `session_id`) are
  validated before use as file names (a conservative charset, no
  separators), rejected with a clear error otherwise.

## Deliverables

1. The fixes above at the source (`permissions.py` and its shell parsing
   helpers, `tools/read.py|grep.py|glob.py` path-rule plumbing, `shadow.py`,
   `agent/log.py`, `launch_state.py`, `config/paths.py`), each pinned in
   `tests/test_security_round4.py` (split 4b/4c at the 250-line cap);
   every pin fails on the old code (check with `git stash`, say which);
   `tests/test_review2_round4.py` and every existing permissions suite
   stay green UNCHANGED -- if one has to change, the fix is wrong.
2. CHANGELOG `[2.0.10] - unreleased` "### Security review fix pass, round
   2 (permission rules hold through compound commands; state-dir modes)".
3. The review doc: "Fixed in round 4: ..." under 12-16, 24, 25; the
   rejection note under 11.
4. docs: the permissions section of HANDBOOK (one paragraph: a deny or
   ask rule follows the command through compound forms and wrappers; the
   allow side is unchanged), docs/CONFIG.md if a key is added.

## Verification before hand-back

The new modules, `tests.test_review2_round4`, every permissions suite
(`ls tests | grep -i -E "permission|perm_|rules|deny|allow"`), the tool
suites (`ls tests | grep -i -E "tools_|test_read|test_grep|test_glob|shadow"`),
`tests.test_launch_state`, `tests.test_history`, `tests.test_review2_round10`
(the shared-state locks), every touched module's tests, `python test_bridge.py`,
`python -m tests.test_invariants`, `python -m tests.test_privacy_scan`,
`python -m tests.test_docs_links`, `python -m halo_harness audit privacy`,
and `python -m pyflakes halo_harness/ bridge.py | grep "undefined name"`
printing nothing. `python test_tui.py` only if `tui/` changed. Hand back
ONCE, under 60 lines, then end your run: RESULT LINES (one per finding
11-16, 24, 25: DONE / REJECTED with the pinning test and the old-code
check), FILES TOUCHED, WHAT YOU FOUND. No commit, no push.
