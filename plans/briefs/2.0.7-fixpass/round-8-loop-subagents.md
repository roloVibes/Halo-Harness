# Halo 2.0.7 fix pass, round 8: review findings 49-53 (loop scheduling), 54-58/60-62/64 (sub-agents and roles)

Repo: `<repo>` (branch master; start from HEAD after round 7, clean). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test environment:
`BRIDGE_TEST_HOME=<fresh scratch dir>`, `BRIDGE_TEST_NO_BACKGROUND_NET=1`,
`OLLAMA_HOST=http://127.0.0.1:1`). `plans/CYCLE.md` "Budget discipline"
applies. The owner's review is `<review file>` (outside the repo; read the
numbered findings, never copy its text into the repo). Standing contract
from `plans/HANDOFF.md`: deny rules hold in every mode, auto mode with no
rules stays allow, classifier-shaped suggestions are rejected.

## Findings to fix (each at the source, each pinned in `tests/test_review2_round8.py`)

Loop scheduling (`agent/loop.py` ~7174-7343):
- **49** the read-only batch runs after an Agent call instead of alongside.
- **50** the 30 s read-only cap ignores the model's own timeout.
- **51** text typed during `/compact` is lost.
- **52** `tool_choice=required` overflow sentinel raises AttributeError.
- **53** Esc-queued batch and waiter-slot leaks.

Sub-agents and roles (`agent/subagent.py`, `teams_yaml.py`, `roles.py`):
- **54** concurrent-resume TOCTOU; **55** cc: Stop hook continuation
  unread; **56** task_id resume drops role, model and effort; **57** team
  `max_parallel` overridden; **58** role table never recomputed; **60**
  team role names rejected; **61** `tools: Agent(X)` unenforced; **62**
  export uses snake_case keys; **64** worktree leak on a failed model
  resolve.

## Verification before hand-back

The new module, every touched module's tests (incl. `tests/test_loop_retries.py`,
`tests/test_agents_teams.py`, the subagent suites), `python test_bridge.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python -m halo_harness audit privacy`, all green; no network in tests.
Hard constraints: no safety or refusal language, no real paths or names,
no new dependency, never block the UI thread. Hand back RESULT LINES (one
per finding: DONE / PARTIAL / REJECTED with the reason and the pinning
test), FILES TOUCHED, WHAT YOU FOUND. No commit, no push.
