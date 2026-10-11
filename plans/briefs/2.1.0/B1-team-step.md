# 2.1.0 round B1 -- the Team step is back, and it explains itself

Read `plans/WORKER-RULES.md` first. Work ONLY in this checkout
(`<home>\Halo-B`, branch `track-b`). Do not commit or push.

## Why

The owner (2026-10-11): "we need a massive revamp of agents and agent roles,
it has to be the clearest and smoothest part of this set up. I don't see it
in the wizard set up anymore. Really, we need this to be clear how it works
and allow users to easily change and apply templates for agent assignments
thru wizard or command line."

Verified root cause: a fresh `halo init` pushes `SetupModeStep`
(`tui/dialogs/init_wizard.py:1669`) with Quick preselected
(`tui/dialogs/setup_mode.py:58`); Quick runs only `providers, default_model,
summary` (`setup_mode.py:27 QUICK_STEP_KEYS`); the Summary step then applies
the `standard` lineup and calls `set_roles_enabled(False)`
(`init_wizard.py:1556-1587`); and a later `halo init --step team` opens with
the switch off, which shows one sentence and hides both panes
(`team_step.py:284-292`). So a new user never sees agents at all.

The concept model does NOT change (docs/AGENTS.md: a bio is what an agent IS,
a lineup assigns bios to roles, a role is a slot the loop fills). The
resolve/validate/apply functions in `agents_yaml.py` / `teams_yaml.py` stay
the single source of truth. This round changes how people SEE and PICK.

## Deliverables

1. **Quick setup includes the Team step.** `setup_mode.py`:
   `QUICK_STEP_KEYS = ("providers", "default_model", "team", "summary")`.
   The Quick/Full chooser's copy names it: Quick = "a provider key, your
   default model, and which lineup of agents runs your work". Update the
   module docstring and any test that pins the Quick key list.

2. **A new Team step** (`tui/dialogs/team_step.py`, 446 lines today -- keep
   every file under the house 250-line write cap by splitting: put the
   explainer text and the preview tree into a NEW `tui/dialogs/team_preview.py`,
   and keep `team_step.py` as the screen). The screen, top to bottom:
   - A plain-words header (one or two sentences, Textual `Static`):
     "Halo runs one model for everything unless you pick a lineup. A lineup
     gives each job (planning, coding, reviewing, research) its own agent and
     model."
   - A **lineup list** (left; an `OptionList` or the existing list widget
     `lineup_editor.team_rows()` feeds): the FIRST row is always
     **"One model for everything"** (applies the shipped `standard` lineup and
     sets roles off -- exactly what Summary does silently today); then every
     reachable lineup (shipped, user, project) with its one-line description
     and a scope badge. The active one is marked.
   - A **live preview pane** (right at >= 100 columns, below otherwise) for
     the highlighted lineup: a tree `role -> agent -> model` with the model's
     price/context when the catalog knows them (`teams_yaml.resolve_role_table`
     + `lineup_editor.resolved_assignment_line`), the lineup's `about:` text
     when it has one, any `lineup_editor.lineup_warnings` lines, and one
     "Roughly $X per turn at these prices" line when every model has a price
     (`team_preview.cost_hint(table)`; print "price unknown for <model>"
     otherwise -- never a blank that reads as free). For "One model for
     everything" the preview is the sentence `team_step.py:166-168` prints
     today, with the default model named.
   - Buttons: **Use this lineup** (apply + `team:` via
     `teams_yaml.apply_team_template`, also patches the live session's role
     table as `_commit_lineup` does today), **Customize...** (opens the
     existing `LineupEditor` on the highlighted lineup; a shipped lineup is
     duplicated into user scope first, as the Duplicate action does today),
     **New lineup** (the existing new flow). The Agents pane (bios list) stays
     reachable through a **Agents...** button that pushes the existing
     `AgentsListScreen` -- it is no longer a pane of this step.
   - The "Custom roles: off / on" `Switch` is REMOVED as the primary control;
     picking "One model for everything" is the off state. `roles.enabled` is
     always written explicitly by this step (reconciles `roles.py:204`
     defaulting True with the docs' "a fresh install runs with roles off").
   - A plain Next applies whichever row is highlighted (keep the
     highlight-is-selection rule from docs/WIZARD.md rule 1); Enter on a row
     opens its editor (rule 2).
   - Keys: Esc, Ctrl+Left/Right as today; Ctrl+N new lineup; Ctrl+E customize.

3. **The Summary step** (`init_wizard.py:1556-1587`) no longer applies
   `standard`/flips roles off on its own; it prints the lineup the Team step
   applied by name with its resolved roles (one line per role), or "One model
   for everything: <model>".

4. **`team_preview.py` is reusable**: `preview_lines(name, *, cwd=None,
   state_dir=None, width=80) -> list[str]` (plain text, no markup) and
   `cost_hint(table) -> str`, so B2's `halo teams preview` and `/teams` can
   print the same tree. Unit-test them directly.

5. **Tests.** Update: `tests/test_round2c_wizard_ux.py:246,272`,
   `tests/test_wizard_lineup.py:375`, `tests/test_wizard_agents_bios.py:149,232`,
   `tests/test_agents_teams_forms.py:292,306`, `tests/test_round_wizard_deep_
   review.py:96`, `test_tui.py:9907-10137` (init wizard and lineup) and any
   Quick-setup pin. Add `tests/test_team_preview.py` (the tree for every
   shipped lineup, the cost hint with and without prices, the warnings line).
   Add a pilot test: a fresh wizard with Quick selected reaches the Team step;
   highlighting `balanced` and pressing Next writes `team: balanced` and
   `roles.enabled: true`; highlighting the first row writes `team: standard`
   and `roles.enabled: false`.

6. **Docs.** `docs/WIZARD.md` (the step list and the Team step section),
   `docs/ROLES.md` and `docs/AGENTS.md` each get a NEW top section "The
   90-second version" (bio -> lineup -> role -> session, in plain words, with
   the three ways to pick: wizard, CLI, Studio -- Studio is "coming in 2.1.0"
   for now) BEFORE the field reference; nothing below is removed. Fix the
   drift: AGENTS.md says the panes sit side by side at 120 columns (gone) and
   lists four shipped lineups when six ship (`balanced, code-review,
   halo-dev-cycle, local-first, quality, standard`). Also a diagram
   `docs/media/diagrams/agents-model.svg` (hand-drawn, under 60 KB, explicit
   width/height, the style of the five existing diagrams there) and
   CHANGELOG `## [2.1.0] - unreleased` with a B1 entry.

## Constraints

- No new dependencies. No safety/refusal wording anywhere.
- Every file write <= 250 lines; split modules rather than grow them.
- Tests: `python -m tests.test_X` style, scoped home. Run the modules you
  touched plus `python test_bridge.py` and `python test_tui.py` before
  hand-back (test_tui rewrites docs/harness/tui-snapshots; `git checkout --
  docs/harness/tui-snapshots` afterwards). A pre-existing failure to ignore:
  `test_tui.py::test_bare_effort_card_selection_persists_like_the_plain_text_path`
  ("nothing persisted yet") fails on master before this round.
- The 80x24 rule: every control must be reachable at 80x24 (stacked layout).

## Hand-back

RESULT LINES per deliverable (DONE / PARTIAL with evidence and test names),
FILES TOUCHED, WHAT YOU FOUND. No commit, no push.
