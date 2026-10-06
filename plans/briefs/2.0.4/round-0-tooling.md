# Halo 2.0.4 round 0: tooling (CI for the three suites, a release script, invariants)

Repo: <repo> (branch master; start
from HEAD, after the v2.0.3.1 tag). Read `plans/WORKER-RULES.md` FIRST and
follow every rule in it (test environment: export `BRIDGE_TEST_HOME=<fresh
scratch dir>` and `BRIDGE_TEST_NO_BACKGROUND_NET=1` only). The round is
defined in `plans/ROADMAP.md` under "2.0.4 = tooling, history, provider
pack: round 0 tooling"; read that bullet and every line in ROADMAP.md that
mentions "invariant" (grep it) before starting. 2.0.4's version string
becomes "2.0.4" only at its release; this round does NOT bump the version.

## Deliverable 1: GitHub Actions workflow `.github/workflows/suites.yml`

- Triggers: every push to master and every pull request.
- Two jobs, `linux` (ubuntu-latest) and `windows` (windows-latest), each a
  matrix over nothing (one Python: 3.12), each running the three suites in
  order with hard timeouts, the same way the orchestrator runs them by hand
  (see scratchpad-free equivalents in docs: `python test_bridge.py`,
  `python tests/run_all.py`, `python test_tui.py`), with
  `BRIDGE_TEST_HOME` set to a fresh temp dir inside the runner workspace and
  `BRIDGE_TEST_NO_BACKGROUND_NET=1`; `PYTHONPATH` the checkout.
- Install: `pip install -e .[dev]` if a dev extra exists, else `pip install
  -e .` plus whatever test-only packages the suites import (find them by
  running the suites on this box with a fresh venv if needed; `mcp>=2.2,<3`
  is required for the MCP suites, Textual for the TUI suite). No secrets,
  no provider keys, nothing from the owner's machine; tests are hermetic.
- The TUI suite on the Windows runner may need `PYTHONUTF8=1` and a
  `COLUMNS`/`LINES` env (check test_tui's own needs); set them in the job.
- A job-level `timeout-minutes` (Linux 45, Windows 60) and `concurrency`
  cancelling superseded runs of the same ref.
- Upload the three RESULT lines as the job summary (`$GITHUB_STEP_SUMMARY`)
  so a phone can read pass/fail without opening logs; on failure upload the
  full logs as an artifact.
- Do NOT run the privacy scan differently: it is part of run_all already.
- Document in docs/CONTRIBUTING.md (create if missing, short) what the
  workflow runs and that the manual three-platform run is now the exception.

## Deliverable 2: release script `scripts/release.py` (+ `halo release`? no: a repo script, not a user command)

- `python scripts/release.py <version> [--date YYYY-MM-DD] [--remote
  user@host ...] [--no-install] [--dry-run]`:
  1. refuses when the tree is dirty under halo_harness/, tests/, docs/;
  2. sets `halo_harness/__init__.py::__version__` to <version> (or verifies
     it already is);
  3. requires `## [<version>] - unreleased` in CHANGELOG.md and sets the
     date;
  4. commits "release: Halo Harness <version>" (message body from the
     CHANGELOG section's first bullets), creates the annotated tag
     `v<version>` with message "Halo Harness <version>", pushes master and
     the tag;
  5. refreshes the local install with `uv tool install --reinstall
     git+https://github.com/roloVibes/Halo-Harness@v<version>` unless a
     halo session is running (detect by process list on Windows/POSIX;
     print the command instead), and for each `--remote user@host` runs
     over ssh: `cd ~/Halo-Harness && git fetch --tags && git checkout
     v<version> && uv tool install --reinstall . && halo --version`;
  6. prints a one-screen summary.
  `--dry-run` prints every step without executing. No hostnames, addresses
  or user names in the script or docs (`tests/test_privacy_scan.py`
  enforces it); remotes come only from the command line.
- Test: tests/test_release_script.py drives the script with `--dry-run` on a
  scratch git repo (init a temp repo with a CHANGELOG and __init__) and
  asserts the step list, the refusal on a dirty tree, the refusal when the
  CHANGELOG section is missing, and the version write; nothing executes git
  push or uv for real (stub subprocess.run for the non-dry-run path test).

## Deliverable 3: invariants

- Collect every "invariant" line from ROADMAP.md's old hardening list plus
  these standing rules, and make each one a test in
  tests/test_invariants.py (one @test per invariant, each explaining what it
  protects):
  a. no safety/refusal/"for safety"/"dangerous command" language in
     halo_harness/, docs/, tests/ (reuse whatever scan exists; if none, a
     word list with an allowlist file);
  b. every raw network-opening call goes through providers/http.py's choke
     point (tests/test_offline_mode.py already has this invariant: move or
     reference it, do not duplicate);
  c. no file under halo_harness/ writes to the real home when
     BRIDGE_TEST_HOME is set (grep for `Path.home()` outside config/paths.py
     and whitelist the known, reasoned exceptions);
  d. every slash command in the builtins registry has a heading in
     docs/SLASH-COMMANDS.md and every CLI flag in cli.py has a `####`
     entry in docs/COMMANDS.md (tests/test_docs_slash_commands.py covers
     part of this; extend rather than duplicate);
  e. the privacy scan passes (already in run_all; reference it);
  f. no test module exports BRIDGE_STATE_DIR for its whole run (grep tests/
     for `os.environ["BRIDGE_STATE_DIR"]` at module level; allowlist the
     ones that set it inside a single test with a restore).
- Wire tests/test_invariants.py into tests/run_all.py the way other modules
  are discovered (check how run_all finds modules; probably by glob).

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere. Describe behaviour.
- No real paths, LAN addresses, hostnames, usernames, machine names or keys
  in any repo file.
- No network in tests. The workflow file is the only place that installs
  from the network, and it installs only public packages.
- Keep changes inside: .github/workflows/, scripts/, tests/test_release_
  script.py, tests/test_invariants.py, docs/CONTRIBUTING.md, docs/COMMANDS.md
  (only if a flag entry is missing), CHANGELOG.md (`## [2.0.4] - unreleased`
  section above [2.0.3.1] with a "Tooling" subsection), plans/STATUS.md
  (tick round 0).

## Verification before hand-back

`python tests/test_release_script.py`, `python tests/test_invariants.py`,
`python test_bridge.py`, `python tests/test_privacy_scan.py`, all green;
`python -c "import yaml; yaml.safe_load(open('.github/workflows/suites.yml'))"`
(install pyyaml in a scratch venv if needed, never into the repo deps) to
prove the workflow parses. Record `stat -c %s ~/.halo/history.jsonl` and
`ls ~/.halo/sessions | wc -l` at the start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-3: DONE / PARTIAL with evidence and the
pinning test names), FILES TOUCHED, WHAT YOU FOUND (anything beyond the
brief, anything left open and why, and which invariants from ROADMAP you
could not turn into a test and why). No commit, no push.
