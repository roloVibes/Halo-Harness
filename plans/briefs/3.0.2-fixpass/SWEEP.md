# 3.0.1.0 review fix pass: sweep (2026-10-13)

The owner's 15-reviewer cloud review of 3.0.1.0 (161 confirmed findings,
reviewed at master `4e4b85d`; the owner's edited copy, kept outside the repo,
removed item 6 and trimmed items 1, 2, 16 and 25 under the standing contract)
was worked as fifteen parallel rounds, one worktree and one worker each, and
merged onto `integrate` in this order: P, M, G3, G2, F, L, S, D1, D2, E, C,
B, T, G1, A. Every item is pinned in `tests/test_review3_<round>*.py`.

Standing contract (plans/HANDOFF.md): deny/ask rules hold in every mode; auto
and bypassPermissions with no rules stay allow; allow-side matching unchanged;
no classifier-shaped or network-reach restrictions.

## Status by round

| Round | Items | Status |
|---|---|---|
| A permissions | 1, 2, 3, 16, 17, 19, 20, 21, 91, 92, 93 | all DONE; `test_review3_a_probe.py` runs ~100 commands in all six modes |
| B trust | 4, 5, 18, 40, 65, 66, 139 | all DONE |
| C studio/tools | 7, 22, 23, 24, 34-38, 94, 95, 109-113 | DONE; **25 REJECTED** (does not hold: the http fallback is already cached under the http URL; pinned) |
| D1 remote core | 26-30, 96-100 | all DONE |
| D2 signal | 31-33, 101-108 | all DONE |
| E session/data | 13, 15, 41, 72, 75, 80, 86, 87, 161 | all DONE |
| F install/update | 14, 81-85, 150-155 | DONE; **81 PARTIAL** (stable channel retargets to the newest tag and checks the release's checksums asset; a uv git build has no local source to hash-compare, docs say so) |
| G1 providers wire | 9, 55-58, 126-132 | all DONE (132 docs + comment) |
| G2 local/catalog | 59-64, 133-138 | all DONE (60: served-id check not required, mlx_lm lists the Hub cache) |
| G3 MCP/commands | 10, 67-71, 140-143 | all DONE |
| L agent loop | 8, 45-48, 119-122 | all DONE (8: fired jobs get os.environ + session tool_env + marker, keys kept) |
| S sub-agents/teams | 49-54, 123-125 | all DONE |
| T TUI (+162) | 11, 12, 73, 74, 76-79, 144-149, 162 | all DONE; 162 = every level keeps the plain status bar (pinned), skin default plain |
| P design/Paperclip | 39, 42, 43, 44, 114-118 | all DONE |
| M data/misc | 88, 89, 90, 156-160 | all DONE |
| (removed) | 6 | not applied (owner's contract) |

Totals: 158 DONE, 1 PARTIAL, 1 REJECTED, 1 removed, 1 owner item DONE.

## Left open by the workers (small, outside the items)

- design/session.py still passes the design prompt as argv `-p` (same
  E2BIG class as item 42).
- `Session.clear()` leaves a live `_cx_state` (needs `codex_runtime.close_cx`).
- signal_install.verify_signature runs `gpg` with the full environment.
- About 40 `run_worker(thread=True)` calls on screens/widgets under
  tui/dialogs still use exit_on_error=True (only the items' ones changed).
- Org layout files are named `pc:<id>.json`; a colon makes an NTFS
  alternate stream on Windows.
- tools/ingest_model_table.py would drop the new
  `anthropic_model_capabilities` section (and two older ones) on a rerun.
- The model picker ignores `assign_role`'s refusal (closes silently).
- `tests/test_cli_flags.py::test_version_flag_short_and_long` fails on the
  Windows build host on untouched master (cp1252 subprocess decode).
- scene_band.py docstring says six rows; `scene.ROWS` is eight.

## Process notes

- Workers never commit; the orchestrator committed each branch and merged.
- Never `git stash` in the worktree farm: the stash stack is shared, and two
  workers swapped trees mid-run (recovered from saved patches, nothing lost).
- Hand-resolved merges: D1/D2 (bridge.py on_notice, bridge_session.py card
  tags + card=True, signal_transport._subscribe = retry ladder + interrupt),
  E/C (design/jsonio.py combined: strict reads, lock, atomic write), G1/G2
  (learned_params: `_allowed_values` + structured-value guard).
