# Halo 2.0.7 fix pass, round 9: review findings 67-75 (TUI), 76-78/80/82-83 (CLI and doctor)

Repo: `<repo>` (branch master; start from HEAD after round 8, clean). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test environment:
`BRIDGE_TEST_HOME=<fresh scratch dir>`, `BRIDGE_TEST_NO_BACKGROUND_NET=1`,
`OLLAMA_HOST=http://127.0.0.1:1`). `plans/CYCLE.md` "Budget discipline"
applies. The owner's review is `<review file>` (outside the repo; read the
numbered findings, never copy its text into the repo). Standing contract
from `plans/HANDOFF.md`: deny rules hold in every mode, auto mode with no
rules stays allow, classifier-shaped suggestions are rejected.

## Findings to fix (each at the source, each pinned in `tests/test_review2_round9.py` or `test_tui.py`)

TUI:
- **67** xclip run with DEVNULL hides its errors; **68** a slash command
  drops image attachments; **69** shadow snapshots taken on the UI thread;
  **70** roles-editor Ctrl+S; **71** the card race; **72** recalled paste
  placeholder; **73** image-chip delete; **74** invalid YAML silently kept;
  **75** auto-title and stream-json state resets.

CLI and doctor:
- **76** `-p -c` silently starts a new session; **77** `providers setup`
  argparse; **78** `doctor --json` prints text first; **80** the PATH check
  reads the harness's own environment; **82** `--fork` with
  `--no-session-persistence` leaks; **83** `-w` applied before validation.

## Verification before hand-back

The new module, every touched module's tests, `python test_bridge.py`,
`python test_tui.py` once (then `git checkout -- docs/harness/tui-snapshots`
unless a change was intentional), `python tests/test_privacy_scan.py`,
`python tests/test_invariants.py`, `python tests/test_docs_commands.py`,
`python -m halo_harness audit privacy`, all green; no network in tests.
Hard constraints: no safety or refusal language, no real paths or names,
no new dependency, never block the UI thread, picker keys are chords.
Hand back RESULT LINES (one per finding: DONE / PARTIAL / REJECTED with
the reason and the pinning test), FILES TOUCHED, WHAT YOU FOUND. No commit,
no push.
