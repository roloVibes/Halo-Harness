# Halo 2.0.5 round 2c: the wizard interaction model (smooth, not clunky)

Repo: `<repo>` (branch master; start from HEAD after round 2b; a git stash
holds other rounds' partial work and is NOT yours). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test environment:
`BRIDGE_TEST_HOME=<fresh scratch dir>`, `BRIDGE_TEST_NO_BACKGROUND_NET=1`,
`OLLAMA_HOST=http://127.0.0.1:1`). `plans/CYCLE.md` "Budget discipline"
applies: one worker, touched modules plus `python test_bridge.py` and
`python test_tui.py`, no other suites.

Specification: `plans/ROADMAP.md` section "ADDED 2026-10-06 ~10:05 (rolo):
2.0.5 round 2c 'wizard interaction model'" (read it in full; the owner's
words and the ten rules are there). Round 2b already applied rules 1, 2
and 7 to the screens it touched; this round applies all ten everywhere.

## Where the code is

`halo_harness/tui/dialogs/init_wizard.py` (`ALL_STEP_KEYS`, `StepScreen`,
every `*Step`, `SummaryStep`, `STEP_FACTORIES`), `tui/dialogs/agents_step.py`,
`agent_bio_editor.py`, `lineup_editor.py`, `roles_editor.py`,
`org_editor.py`, `model_picker.py`, the wizard's CSS, `init_cli.py`
(`--step`), `docs/HANDBOOK.md` wizard section, `docs/AGENTS.md`,
`docs/ROLES.md`, `docs/ORGS.md`, the TUI snapshot tests under
`docs/harness/tui-snapshots` (regenerate only the wizard ones, and only
after the pilots pass; `git checkout -- docs/harness/tui-snapshots` for
anything you did not mean to change).

## Deliverables

1. **`docs/WIZARD.md`**: the ten rules on one page, with the chord table
   and a two-line description of each step; linked from HANDBOOK and
   COMMANDS (`halo init`).
2. **Rules 1, 2, 7 on every screen** (not only the round-2b ones): one
   shared mixin or helper in the wizard package that step screens and list
   screens use for "highlight is selection", "Enter acts", "focus the
   content on open".
3. **Rule 3, autocomplete in model fields**: a dropdown under the field
   (a small `OptionList` or the house completion widget) filtered by what
   is typed from the enumerated rows, Enter picks, Escape closes; used by
   the bio editor, the roles editor, the org editor and the lineup grid;
   Ctrl+P keeps opening the full picker.
4. **Rule 4, the step rail** at the top of every step, with done ticks and
   Ctrl+Left / Ctrl+Right for Back and Next; `halo init --step` unchanged.
5. **Rule 5, quick setup**: the first screen offers "Quick setup" (keys,
   default model, done: activates `standard`, roles off) and "Full setup"
   (every step); quick is the default and the Summary says what it chose.
6. **Rules 6, 8, 9, 10**: the one-sentence header per step, two levels
   deep at most with the toast on save and inline errors, the uniform
   footer, the Summary with "Change" jumps.
7. Docs updated (HANDBOOK walkthrough rewritten around quick/full setup;
   AGENTS, ROLES, ORGS where keys changed), CHANGELOG `[2.0.5]` "### Wizard
   interaction model".

## Tests (hermetic)

One pilot per rule per screen kind at 80x24 and 120x40 with a fixture
catalog: highlight-is-selection on the default model and theme steps;
Enter opens a bio and a lineup from their lists and uses a lineup; focus on
open; autocomplete filters and picks in all four field sites; the rail
shows the current step and Ctrl+Right advances; quick setup ends on a
Summary with `standard` active and roles off; full setup walks every step;
the toast after a save; Escape never loses data; Summary "Change" jumps.
No network, no real model.

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file; `halo audit privacy` exit 0; privacy scan and invariants
  green.
- No network in tests; never read the owner's key files; the real `~/.halo`
  is never touched by tests.
- No new hard dependency. `init_wizard.py` grows by registration lines
  only: the mixin, the rail, the autocomplete widget and the quick/full
  chooser are new modules under `tui/dialogs/`.
- Never block the UI thread; chords or function keys only in any screen
  with a text input.

## Verification before hand-back

Touched and new test modules, `python test_bridge.py`, `python test_tui.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python tests/test_docs_commands.py`, `python tests/test_docs_slash_commands.py`,
`python -m halo_harness audit privacy`, all green. Record
`stat -c %s ~/.halo/history.jsonl` and `ls ~/.halo/sessions | wc -l` at the
start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-7: DONE / PARTIAL with evidence and the
pinning test names), FILES TOUCHED, WHAT YOU FOUND (which screens broke the
rules and how, anything left open and why, the manual check for the owner:
`halo init` quick setup end to end, then `halo init --step agents` and
Enter on a bio). No commit, no push.
