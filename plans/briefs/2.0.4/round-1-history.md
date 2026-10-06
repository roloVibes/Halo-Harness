# Halo 2.0.4 round 1: `halo audit privacy` and the history-rewrite plan

Repo: <repo> (branch master; start
from HEAD = 4a788a3, round 0 tooling). Read `plans/WORKER-RULES.md` FIRST and
follow every rule in it (test environment: `BRIDGE_TEST_HOME=<fresh scratch
dir>` and `BRIDGE_TEST_NO_BACKGROUND_NET=1` only). The round is defined in
`plans/ROADMAP.md` under "2.0.4 ... round 1 history". This round delivers the
AUDIT COMMAND and a WRITTEN PLAN; the orchestrator executes the rewrite
itself afterwards (mirror backup, git filter-repo, force-push, clones reset).
You never rewrite history, never force-push, never run git filter-repo.

## Deliverable 1: `halo audit privacy [--history] [--json] [--since <rev>]`

A CLI subcommand (wire it the way `halo doctor`/`halo bugreport` are wired;
reuse `halo_harness/redact.py`'s token patterns and
`tests/test_privacy_scan.py`'s rules as the single source of truth: move the
shared rule set into a small production module, e.g.
`halo_harness/privacy_rules.py`, and make the test import it so the two can
never drift).

- Working-tree mode (default): scans every tracked file plus untracked,
  non-ignored files for: real user-profile paths (Windows `C:\Users\<name>`
  and `/home/<name>`, `/Users/<name>` forms), private-range and link-local
  IP literals, LAN hostnames and `.local` names, machine names, Windows
  `%SystemDrive%`/`%USERPROFILE%`-style stray cache files, key- and
  token-shaped strings (every pattern redact.py knows), e-mail addresses,
  and any path under the state dir. Reports one line per finding:
  `path:line: <kind>: <masked excerpt>`; exit 1 when anything is found, 0
  when clean. The allowlist (`tests/privacy_scan_allowlist.txt` and the
  documented placeholder ranges) applies here too.
- `--history`: the same scan over every commit reachable from HEAD (use
  `git log --all --name-only` to find paths that ever existed, and
  `git grep -I -n -E <pattern> <commit>` or `git log -p -S` on each rule;
  keep it reasonably fast: scan each distinct blob once, keyed by blob id).
  Reports `commit:path:line: <kind>: <masked excerpt>`, plus a summary of
  the DISTINCT PATHS to purge entirely (files that should never have been
  committed, e.g. cache files, state-dir leaks) versus LINES that need
  text replacement (a hostname inside a doc that otherwise stays).
- `--json`: machine-readable output with the same fields, for the plan.
- Excerpts are always masked (never print the key or the full path; show
  the kind and a short context with the secret replaced by `<redacted>`).
- Docs: docs/COMMANDS.md entry (`#### \`audit\``), docs/TROUBLESHOOTING.md
  or docs/PRIVACY.md (create a short PRIVACY.md if none exists) describing
  what Halo never writes to the repo and how to run the audit; CHANGELOG
  bullet under [2.0.4] "### History and privacy".

## Deliverable 2: `plans/2.0.4-history-rewrite-plan.md`

Run `halo audit privacy --history --json` against THIS repo and write the
plan from its output: (a) the exact list of paths to remove from every
commit (`git filter-repo --invert-paths --path <p> ...`), (b) the exact
text replacements (`git filter-repo --replace-text <file>` format: one
`literal==>replacement` per line, saved as `plans/2.0.4-history-replacements.txt`
but with the LITERALS themselves written as the masked kind, since the
plan file is committed to the public repo: the orchestrator fills the real
literals from the audit's JSON at execution time -- so write the JSON to
the scratchpad path the orchestrator gives in the spawn prompt, NOT into
the repo), (c) the tags that must be re-created (every `v*` tag, since
filter-repo rewrites them), (d) the two clones to reset (the build host's
working tree and the owner's Linux clone) with the exact commands, (e) a
verification step (`halo audit privacy --history` returns 0 after the
rewrite; the three suites still pass; `git fsck`), and (f) the
announcement text for the CHANGELOG ("history rewritten on <date>; re-clone
or `git fetch && git reset --hard origin/master`").

## Tests

- tests/test_audit_privacy.py: a scratch git repo (init under system temp)
  with planted findings of every kind in committed files AND in an earlier
  commit whose file was later deleted: working-tree mode finds the live
  ones and exits 1; `--history` finds the deleted-file leak and lists the
  path under "purge entirely"; `--json` round-trips; a clean repo exits 0;
  the allowlist suppresses a planted allow-listed fixture; excerpts never
  contain the planted secret. Stub nothing: these are real `git`
  invocations on a scratch repo (git is available on every platform the
  suites run on).
- tests/test_privacy_scan.py keeps passing and now imports the shared rule
  module.

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere. Describe behaviour.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file, INCLUDING the plan and the replacements file (masked
  kinds only); the real JSON goes to the scratchpad path from the spawn
  prompt.
- Never rewrite history, never force-push, never run git filter-repo, never
  touch `.git` of this repo beyond read-only git commands.
- No network in tests.
- Keep changes inside: the new modules, cli.py (subcommand wiring),
  halo_harness/redact.py (only if a pattern must move), tests/
  test_privacy_scan.py (import the shared rules), the new test module,
  docs, CHANGELOG, plans/2.0.4-history-rewrite-plan.md,
  plans/2.0.4-history-replacements.txt, plans/STATUS.md (round 1 [~]).

## Verification before hand-back

`python tests/test_audit_privacy.py`, `python tests/test_privacy_scan.py`,
`python tests/test_invariants.py`, `python tests/test_docs_commands.py`,
`python test_bridge.py`, all green; `halo audit privacy` (working tree) on
this repo returns 0; `halo audit privacy --history --json` written to the
scratchpad path. Record `stat -c %s ~/.halo/history.jsonl` and
`ls ~/.halo/sessions | wc -l` at the start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-2: DONE / PARTIAL with evidence and the
pinning test names), FILES TOUCHED, WHAT YOU FOUND (the history audit's
counts by kind, the number of distinct paths to purge, the number of text
replacements, anything surprising, anything left open and why). No commit,
no push.
