# Halo 2.0.5 round 2: wizard: agent bios and lineups

Repo: `<repo>` (branch master; start from HEAD after round 1). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test
environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies: one worker, touched modules
plus `python test_bridge.py`, no full suites.

Specification: `plans/ROADMAP.md` section "ADDED 2026-10-06 ~04:35 (rolo):
2.0.5 round 'wizard: agent bios and lineups'" (read it in full; the owner's
words are quoted there and the five numbered items are the deliverables).
Background: the sections "ADDED 2026-10-05 ~22:45: agent declaration files
(YAML)", "ADDED 2026-10-06 ~00:25: agent BIOS and team TEMPLATES are two
layers" and "ADDED 2026-10-06 ~00:40: a team template is a lineup of many
assignments" define the two file kinds this round puts behind forms.

## Where the code is

`halo_harness/tui/dialogs/init_wizard.py` (1671 lines: `ALL_STEP_KEYS`,
`StepScreen`, `ProvidersStep` with the enumeration after the keys step,
`RolesStep` (~line 1128, it edits a LEGACY role template through
`roles.load_role_template` and `RolesEditor`), `OrgsStep`, `SummaryStep`,
`STEP_FACTORIES`), `tui/dialogs/roles_editor.py` (the role table editor with
the pick list, autocomplete, the template picker at its top and the Auto
tab; its save migrates a legacy table into `~/.halo/agents/*.yaml`),
`tui/dialogs/org_editor.py`, `halo_harness/agents_yaml.py` (`BIO_SECTIONS`,
`KNOWN_KINDS`, `agent_search_dirs`, `list_agent_bios`, `load_agent_bio_raw`,
`resolve_agent_bio`, `validate_agent_bio`, `save_agent_bio`,
`new_agent_bio_from_template`), `teams_yaml.py` (`TOP_SECTIONS`,
`GATE_KINDS`, `ASSIGNMENT_OVERRIDE_KEYS`, the validators, the role-table
and org projections), `agents_cli.py` and `teams_cli.py` (`new` writes a
starter, `edit` opens `$EDITOR`), `providers/model_enumeration.py`
(`build_model_rows`, the rows the pick list shows), the shipped
`templates/agents/*.yaml` and `templates/teams/*.yaml`, `docs/AGENTS.md`,
`docs/ROLES.md`, the wizard section of `docs/HANDBOOK.md`.

## Deliverables

1. **Agents step** (`"agents"` in `ALL_STEP_KEYS`, after `"default_model"`
   and before `"roles"`; `halo init --step agents` reaches it directly like
   the other keys): a list of every bio from `list_agent_bios` with its
   scope (project / user / shipped), description and preferred model;
   actions new, new from..., edit, duplicate, delete, import (a shipped bio
   is duplicated into user scope, never edited in place). The **bio
   editor** is one form over
   the common sections: identity (name with `is_valid_agent_name`,
   description, tags, kind from `KNOWN_KINDS`, extends from the known
   bios), `models` (preference and fallback each open the SAME pick list
   widget the roles editor uses, fed by the enumeration already done in
   the Providers step; effort, thinking, context_budget), `tools` (allow
   and deny from the harness's tool names, mcp_servers from the configured
   MCP servers, permission_mode, rules as free lines), `context` (files,
   skills, memory namespace), `limits` (max_iterations, timeout,
   max_budget_usd, concurrency), `output` (handoff, report_to),
   `environment` (worktree, offline), `acceptance` (prompt, expect). Save
   runs `validate_agent_bio` and `save_agent_bio` (user scope by default,
   project scope by a toggle); problems print one plain line each and keep
   the form open; keys the file already has outside the form survive a
   round trip untouched. Folded in (rolo 2026-10-06 ~04:50, "fold them in"):
   - **New from...** opens the form prefilled from any existing bio with
     `extends:` set to it; inherited values show greyed with a per-field
     override toggle, and only the overridden keys are written to the child
     file (`resolve_agent_bio` is the merged view; the raw file stays
     minimal).
   - **Problems inline**: a preview pane on the right shows the YAML that
     would be written (for a child, only the override keys); the validator
     runs on every change and its lines appear beside the field they name,
     not only on save.
   - **A picker that knows the bio**: the pick list is filtered by the
     bio's needs (tool-capable rows when `tools.allow` is non-empty, local
     rows only when `environment.offline` is on, a context window of at
     least the bio's `context_budget` share) with a one-chord toggle to
     show every row; a Suggest chord fills preference and fallback the way
     the roles editor's Auto tab does (presets, then gym data when present).
   - **Rules you can read**: each `tools.rules` line is syntax-checked and
     rendered as a plain sentence beside it ("Bash may not run git push");
     `limits.max_budget_usd` shows "about N turns at this model's price"
     from the row's price; `timeout` accepts the house duration words
     (`20m`, `2h`).
   - **Import from Claude Code**: an Import action lists the
     `.claude/agents/*.md` files `agents_md_bridge` already finds and
     converts the chosen ones into user-scope bios, one result line each.
2. **Two sources for a role slot.** The pick list used by the roles editor,
   the org editor and the new lineup editor gains a source switch
   (Models / Agents, one key, shown in the footer): Models is today's
   enumerated list; Agents lists every bio with description, preferred
   model and a tools summary (allow count, mcp count), with the same
   filter and autocomplete. Picking a bio records the agent on the slot;
   picking a model keeps today's behaviour; "New bio..." at the top of the
   Agents source opens the bio editor and returns with the new bio
   selected. In a legacy role table a bio pick stores the bio's resolved
   preference as the model and `agent: <name>` beside it.
3. **Lineup editor** (replaces the legacy-template editing in `RolesStep`;
   the step title becomes "Roles and lineup"): choose an installed team
   template to edit, or "New lineup"; the assignments grid (one row per
   role: role, agent-or-model via the two-source picker, alias `as`,
   `instances`, `use_for`), the other top sections from `TOP_SECTIONS` as
   collapsed optional groups each with a one-line meaning and its fields
   (`delegation`, `routing`, `budget`, `escalation`, `context`,
   `permissions`, `org`, `pipeline` with its stages and `GATE_KINDS`,
   `acceptance`), and at the bottom the optional multi-line field **"How
   the pieces work together"** saved as `about:` on the template.
   `teams_yaml` accepts `about` (string) as an identity field; when the
   team is the active `team:`, the text is appended to every member's
   system context under the heading "How this team works" (the same place
   the bio's `context.files` land); `halo teams show` prints it. Save
   validates through `teams_yaml`'s validator, writes `teams/<name>.yaml`
   in user scope (project on toggle), and asks whether to make it the
   active `team:`. A legacy role template still loads (through the 2.0.4
   round-4 migration) and saves as a lineup. Folded in (rolo 2026-10-06
   ~04:50):
   - **The grid shows the resolved truth per row**: agent, preferred
     model, fallback, price, context, gym score when present, tools count;
     inline warnings that need no Governor: bio not found, no reachable
     model for the slot, fallback on the same gateway host as the
     preference (a fallback that cannot help), duplicate alias, two rows
     with `role: main`.
   - **The about text is drafted, never blank**: a Draft chord generates
     one sentence per assignment plus the delegation and pipeline sections
     in the house voice; the user edits it; when the lineup changes after
     the draft, the field shows a "stale" marker until redrafted or edited.
   - **One source of truth**: the roles table is shown under the lineup as
     a read-only projection (`teams_yaml`'s role-table projection) and the
     wizard's roles save goes through the lineup; the legacy role-table
     editor remains only for a config with no lineup at all.
4. **The same forms outside the wizard**: `/agents` (list, new, edit,
   duplicate, delete) and `/teams` (list, show, new, edit, activate) open
   the same screens in a running session; `halo agents new|edit --form` and
   `halo teams new|edit --form` open them from the CLI instead of
   `$EDITOR`. One form module (`tui/dialogs/agent_bio_editor.py` and
   `tui/dialogs/lineup_editor.py`) serves the wizard, the slash dialogs and
   `--form`.
5. **Docs and CHANGELOG**: docs/AGENTS.md (the Agents step, the editor's
   sections, `about`), docs/ROLES.md (two sources for a slot), the wizard
   section of docs/HANDBOOK.md (the new step order), docs/COMMANDS.md and
   docs/SLASH-COMMANDS.md entries, CHANGELOG `[2.0.5]` "### Wizard: agent
   bios and lineups".

## Tests (hermetic; Textual pilots with a fixture catalog, no network, no real model)

The Agents step: create a bio picking its preference from the fixture
catalog, save, reload the step and see it, edit a limit, duplicate a
shipped bio into user scope, delete; a bad save (invalid name, unknown
kind) shows the lines and keeps the form. The roles editor: switch to the
Agents source, pick a bio, see the model and `agent:` recorded; "New
bio..." round trip. The lineup editor: new lineup with one role by model
and one by bio, the `about` text, one advanced section (`budget`), save,
`teams_yaml` loads it clean, `halo teams show` prints the about text, the
activation prompt sets `team:`; editing an installed template; a legacy
role template loads and saves as a lineup. The active team's about text
reaches a member's system context (unit test on the context builder).
`/agents`, `/teams`, `--form` open the screens. `halo init --step agents`.
Folded items: new-from a shipped bio writes only the override keys and the
inherited view shows them greyed; an inline problem appears beside the
field as it is typed; the picker filter hides a non-tool row for a bio with
tools and the toggle shows it again; Suggest fills both model fields; a
rule renders as a sentence and a bad rule shows its line; the budget hint;
Import converts a fixture `.claude/agents/*.md` into a bio; the grid
warnings for a missing bio, an unreachable model, a same-host fallback and a
duplicate alias; Draft produces the text and the stale marker appears after
an edit to the lineup; the projection under the lineup equals
`teams_yaml`'s role table.

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file; `halo audit privacy` exit 0; privacy scan and invariants
  green. Fixture bios use placeholder names.
- No network in tests; never read the owner's key files; the real `~/.halo`
  is never touched by tests (`BRIDGE_TEST_HOME`).
- No new hard dependency. House size conventions: `init_wizard.py` is
  already past them (1671 lines), so the new step and the two editors are
  NEW modules (`tui/dialogs/agents_step.py`, `agent_bio_editor.py`,
  `lineup_editor.py`); `init_wizard.py` gains only the registration lines.
- Never block the UI thread: the enumeration is reused, never re-run, when
  a pick list opens; a bio or lineup save is a short file write.
- Picker keys stay chords (Ctrl+letter) or function keys, never bare
  letters that the filter input would consume.

## Verification before hand-back

Touched and new test modules, `python test_bridge.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python tests/test_docs_commands.py`, `python tests/test_docs_slash_commands.py`,
`python -m halo_harness audit privacy`, all green. Record
`stat -c %s ~/.halo/history.jsonl` and `ls ~/.halo/sessions | wc -l` at the
start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-5: DONE / PARTIAL / ALREADY COVERED with
evidence and the pinning test names), FILES TOUCHED, WHAT YOU FOUND (what
the legacy role-template path still does, anything left open and why, the
manual check for the owner: `halo init`, Agents step, new bio with a model
from the list, then Roles and lineup, new lineup filling one role from
Agents, the about text, save and activate). No commit, no push.
