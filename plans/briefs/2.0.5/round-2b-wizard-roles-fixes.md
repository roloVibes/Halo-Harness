# Halo 2.0.5 round 2b: wizard and roles fixes (owner bug reports on round 2)

Repo: `<repo>` (branch master; start from HEAD = the round-3 tree plus the
CI fixes; the tree is clean, a stash holds other rounds' partial work and
is NOT yours). Read `plans/WORKER-RULES.md` FIRST and follow every rule in
it (test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies: one worker, touched modules
plus `python test_bridge.py` and `python test_tui.py`, no other suites.

Specification: `plans/ROADMAP.md` section "ADDED 2026-10-06 ~09:30 (rolo,
after using round 2 on his box): 2.0.5 round 2b" (read it in full; the
owner's words and the review's weak spots are quoted there; its six
numbered items are the deliverables below). Background: the round-2 brief
`plans/briefs/2.0.5/round-2-wizard-agents.md` and `docs/AGENTS.md`.

## Where the code is

`halo_harness/tui/dialogs/init_wizard.py` (`RolesStep`, "Roles and lineup",
the Lineup and Legacy panes), `tui/dialogs/agents_step.py`,
`tui/dialogs/agent_bio_editor.py` (a `Horizontal` of `#bio-form-pane` 62%
and `#bio-preview-pane` 38% at 92% height; `.bio-field-row { height: 3 }`;
the picker only behind Ctrl+P / Ctrl+F via `_open_picker`; `self.models`
is whatever the caller passed), `tui/dialogs/lineup_editor.py`,
`tui/dialogs/model_picker.py`, `roles.py` and `roles_cli.py` (`roles.enabled`
in config.json, `halo roles`, `halo roles template load|list`),
`teams_yaml.py` / `teams_cli.py` (`team:`, `halo teams use`), the shipped
`templates/teams/*.yaml`, `providers/model_enumeration.py`
(`build_model_rows`, what the Providers step runs), `config/` (how
`default_model` is stored), `scripts/release.py` + `tests/test_release_script.py`,
`README.md` (the version badge), `docs/ROLES.md`, `docs/AGENTS.md`,
`docs/COMMANDS.md`, `docs/SLASH-COMMANDS.md`, `docs/HANDBOOK.md`.

## Deliverables

1. **Roles on/off is one switch.** A toggle at the top of the wizard's
   "Roles and lineup" step labelled "Roles: on / off" (off hides both panes
   and shows one sentence: every role uses the default model); `halo roles
   on` / `halo roles off`; `/roles on|off`; `halo roles` prints the state as
   its first line ("roles: on (lineup <name>)" / "roles: off (standard:
   every role uses the default model)"); `halo roles template load <name>`
   sets `roles.enabled: true` and prints that it did; docs name `halo teams
   use <name>` as the way to point at a lineup without copying mappings.
2. **The `standard` lineup** ships in `templates/teams/standard.yaml`: every
   role assigned to the bio `default-model`, a shipped bio whose
   `models.preference` is the reference `default`, resolved at run time to
   the session's default model (document the reference in docs/AGENTS.md;
   `resolve_agent_bio` or the role resolver substitutes it); "Roles: off"
   activates `standard`; a config with no `team:` and `roles.enabled`
   false behaves identically; `halo teams show standard` explains it in
   one sentence.
3. **Bio editor layout.** The form pane and the preview pane each scroll
   independently; the preview never covers or pushes out the form's rows;
   the first rows (name, description, kind, the model fields) are visible
   on open at 80x24; every field can be focused by Tab and is visible when
   focused; the footer stays visible. Pin with pilots at 80x24 and 120x40.
4. **Bio editor model picking.** A "Pick..." button beside the preferred
   field and beside the fallback field (Ctrl+P / Ctrl+F stay and the footer
   names them); the picker is fed by the merged enumeration the Providers
   step produced (passed through the step, and if it has not run yet,
   run `build_model_rows` with the progress line the roles step uses);
   the bio-needs filter never yields an empty list silently: when it
   would, show all rows with one line saying why; the picked model lands in
   the field and the preview immediately; the same for the lineup editor's
   slots. Find why the owner saw no models at all (the step not passing the
   rows, the filter hiding everything, or the enumeration not reused) and
   fix the cause, not the symptom.
5. **Bug sweep.** Drive the whole flow in pilots at both sizes: Providers
   (fixture keys) -> enumeration -> Agents (new bio, pick model, save, edit,
   duplicate, delete) -> Roles and lineup (toggle on/off, new lineup, fill
   one slot from Models and one from Agents, draft about, save, activate)
   -> Orgs -> Summary. Fix everything that breaks or misleads (focus
   traps, unreachable buttons, stale previews, wrong defaults, errors on
   Back); one line per fix in the hand-back.
6. **Packaging.** `scripts/release.py`: update the README version badge to
   the released version (one regex over the badge URL and alt text) and
   publish a GitHub release for the tag whose notes are the CHANGELOG
   section (use the `gh` CLI when it is on PATH, else the REST API with a
   token obtained from `git credential fill`, never printed); `--no-github-release`
   skips it; the dry run prints the step. `tests/test_release_script.py`
   pins the badge rewrite and the release call through the fake runner;
   `tests/test_invariants.py` or `test_quickstart_docs.py` pins the README
   badge to `__version__`. Fix the current badge in README.md to 2.0.4.

## Tests (hermetic)

Textual pilots for items 1, 3, 4, 5 at 80x24 and 120x40 with a fixture
catalog and fixture bios; `halo roles on|off`, `/roles on|off`, the first
line of `halo roles`, `template load` flipping the flag; the `standard`
lineup resolving every role to the configured default model and following
a change of the default; the picker fed from a fixture enumeration with
the empty-filter fallback line; the release script's badge and GitHub
release steps through the fake runner. No network, no real model.

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file; `halo audit privacy` exit 0; privacy scan and invariants
  green.
- No network in tests; never read the owner's key files; the real `~/.halo`
  is never touched by tests.
- No new hard dependency. House size conventions: `init_wizard.py` grows
  by registration lines only; new code goes in the step and editor modules.
- Never block the UI thread; picker keys are chords or function keys.
- Do not touch the stash or any file outside the areas above.

## Verification before hand-back

Touched and new test modules, `python test_bridge.py`, `python test_tui.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python tests/test_docs_commands.py`, `python tests/test_docs_slash_commands.py`,
`python tests/test_release_script.py`, `python -m halo_harness audit privacy`,
all green. Record `stat -c %s ~/.halo/history.jsonl` and
`ls ~/.halo/sessions | wc -l` at the start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-6: DONE / PARTIAL with evidence and the
pinning test names), FILES TOUCHED, WHAT YOU FOUND (the root cause of "no
models in the bio editor", every sweep fix as one line, anything left open
and why, the manual check for the owner: `halo init`, Agents, New, Pick...,
Save, Roles and lineup toggle off then on, `halo roles`). No commit, no push.
