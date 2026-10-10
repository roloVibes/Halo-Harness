# Halo 2.0.7 fix pass, round 10: review findings 84-92 (telemetry, stats, shared state)

Repo: `<repo>` (branch master; start from HEAD after round 9, clean). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test environment:
`BRIDGE_TEST_HOME=<fresh scratch dir>`, `BRIDGE_TEST_NO_BACKGROUND_NET=1`,
`OLLAMA_HOST=http://127.0.0.1:1`). `plans/CYCLE.md` "Budget discipline"
applies. The owner's review is `<review file>` (outside the repo; read the
numbered findings, never copy its text into the repo). Standing contract
from `plans/HANDOFF.md`: deny rules hold in every mode, auto mode with no
rules stays allow, classifier-shaped suggestions are rejected.

## Findings to fix (each at the source, each pinned in `tests/test_review2_round10.py`)

- **84** sub-agent costs land on the parent row; **85** stats cache
  schema; **86** replay kinds; **87** background PID reuse on macOS;
  **88** recall temp file and cross-project prune; **89** U+2028/U+2029
  line splits; **90** gym `nodigest`; **91** background `-p` stdin;
  **92** shared-state file locks (`launch_state.py`, `update.py`,
  `history.py`).

Then the last sweep: run the whole review file against the tree once more
and list every finding still open with a one-line reason (fixed in an
earlier round, rejected by the standing contract, or genuinely left).

## Verification before hand-back

The new module, every touched module's tests, `python test_bridge.py`,
`python tests/run_all.py` once, `python tests/test_privacy_scan.py`,
`python tests/test_invariants.py`, `python -m halo_harness audit privacy`,
all green; no network in tests. Hard constraints: no safety or refusal
language, no real paths or names, no new dependency. Hand back RESULT LINES
(one per finding), FILES TOUCHED, WHAT YOU FOUND (including the final
open-findings list). No commit, no push.
