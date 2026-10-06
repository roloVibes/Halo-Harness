# Halo 2.0.5 round 2d: the old name is gone; a README worth looking at

Repo: `<repo>` (branch master; start from HEAD after round 2c; a git stash
holds another round's partial work and is NOT yours). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test environment:
`BRIDGE_TEST_HOME=<fresh scratch dir>`, `BRIDGE_TEST_NO_BACKGROUND_NET=1`,
`OLLAMA_HOST=http://127.0.0.1:1`). `plans/CYCLE.md` "Budget discipline"
applies: one worker, touched modules plus `python test_bridge.py` and
`python test_tui.py` once at the end (the banner and the screenshot script touch the TUI),
no other suites.

Specification: `plans/ROADMAP.md` section "ADDED 2026-10-06 ~12:45 (rolo):
2.0.5 round 2d" (read it in full; the owner's words, the measured footprint
and the three items are there). The previous project name is the
hyphenated and underscored forms of the owner's first name followed by
"claude"; `git grep -i "rolo.claude"` lists every occurrence. Never write
that name into any new text, including this round's tests: the invariant
you add must express the pattern without spelling the name (build it from
parts or read it from a one-line constant in the invariant test only).

## Deliverables

1. **The name is off the front pages** (the owner narrowed this on
   2026-10-06 ~12:50: "just don't mention it directly on the first pages of
   the repo, whatever if it's in the change logs"). Scope: `README.md`,
   `docs/INSTALL.md`, `docs/harness/INSTALL.md`, `docs/HANDBOOK.md`,
   `docs/COMMANDS.md`, the `description` in `pyproject.toml`, and the text
   the installers print (`scripts/install-halo.sh`, `install-halo.ps1`).
   Where a legacy behaviour has to be described (the state-dir migration,
   the environment aliases), say "the previous name" or "pre-2.0 installs".
   Leave the compatibility code, its tests, the CHANGELOG and `plans/`
   exactly as they are; do not touch `BRIDGE_*` names.
   - Invariant: `tests/test_invariants.py` gains "(h) the previous project
     name appears on none of the front pages" (that file list,
     case-insensitive, both separators), expressed without spelling the
     name (build the pattern from parts).
2. **The README.** Rewrite `README.md` around: an ASCII-art banner (a
   figlet-style "HALO" wordmark in a fenced block, kept under 80 columns),
   one paragraph of what Halo is, "What it looks like" (the gallery below),
   a feature grid (two columns, one line each: routes, agent bios and
   lineups, the wizard, MCP deep dive, learned rules, balances and picker
   columns, privacy audit, CI and release script), install in three lines,
   a themes section with the current theme render and a note that the
   theme pack (DOOM, Metroid, Mario) adds one render each, links to the
   docs. The same banner prints on `halo --version` (multi-line) and
   becomes the first entry of the intro line pool.
3. **The gallery**: `scripts/screenshots.py` drives the TUI with Textual
   pilots over fixture data (fixture catalog, a fake model that streams a
   short reply and one tool call, fixture bios and the `halo-dev-cycle`
   lineup, a fake MCP server) and saves one SVG per scene under
   `docs/screenshots/`: `launch.svg` (first paint with the intro line),
   `turn.svg` (a reply streaming with a tool card and the phase line),
   `picker.svg` (the model picker with price, context and speed columns),
   `team-step.svg` (the wizard's Team step, custom roles on), `mcp.svg`
   (the `/mcp` dialog with one failing server and the deep-dive action),
   `permission.svg` (the permission card), `balances.svg` (the status bar
   with the balances chip and `/balances`). Size 120x36. The script is
   deterministic (fixed seed, fixed time, no network, no real keys) so a
   rerun produces byte-identical files, and `tests/test_screenshots.py`
   runs it into a scratch dir and checks every scene exists and is
   non-trivial (size and a marker string); the committed SVGs are the
   script's output, nothing hand-edited. Each README caption is one
   sentence.
4. Docs and CHANGELOG: docs/HANDBOOK.md and docs/COMMANDS.md mention the
   banner on `--version` and the screenshot script; CHANGELOG `[2.0.5]`
   "### The old name is gone" and "### README and screenshots".

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file; `halo audit privacy` exit 0; privacy scan and invariants
  green. The SVGs render fixture data only (placeholder model ids, no real
  balances, no real paths in the status bar: use a cwd like `~/project`).
- No network in tests; never read the owner's key files; the real `~/.halo`
  is never touched by tests or by the screenshot script.
- No new hard dependency. House size conventions.
- Never remove `BRIDGE_*` names; never touch the git stash or `.git`.

## Verification before hand-back

Touched and new test modules, `python test_bridge.py`,
`python tests/run_all.py` once, `python test_tui.py` once, `python
tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python tests/test_docs_commands.py`, `python tests/test_docs_slash_commands.py`,
`python -m halo_harness audit privacy`, a case-insensitive grep for the
pattern over the front-page file list returning nothing, all green. Record `stat -c %s ~/.halo/history.jsonl`
and `ls ~/.halo/sessions | wc -l` at the start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-4: DONE / PARTIAL with evidence and the
pinning test names), FILES TOUCHED (grouped: code, tests, docs, plans,
screenshots), WHAT YOU FOUND (what the removed compatibility actually did,
anything left open and why, the manual check for the owner: open the README
on GitHub, run `halo --version`, run `python scripts/screenshots.py` and
diff). No commit, no push.
