# Halo 2.0.4 round 4: the roles wizard shows every reachable model (and an Auto tab)

Repo: <repo> (branch master; start
from HEAD, after round 3's picker/balances/enumeration work: read its
`Controller.list_models()` and the shared enumeration cache before building
anything). Read `plans/WORKER-RULES.md` FIRST and follow every rule in it
(test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>` and
`BRIDGE_TEST_NO_BACKGROUND_NET=1` only).

The owner's report, verbatim (2026-10-05): "When you do halo init and set
roles, the available models are not listed when you select edit a role.
Maybe an enum of what models you can reach should occur after you set the
keys so when you get to the roles step, and I'm sure for the business roles
too, there aren't models to pick from and/or autocomplete when you are
setting the models to roles or company org roles."

The round is defined in `plans/ROADMAP.md`, sections "ADDED 2026-10-05
~11:15 (rolo): 2.0.4 provider-pack round 'roles wizard'" and "ADDED
2026-10-05 ~22:35 (rolo): the roles-wizard round, made precise". Read both.

## Where the code is

- `halo_harness/tui/dialogs/init_wizard.py` (`RolesStep`, the org step
  around `_open_editor_screen` / `_refresh_orgs`), `tui/dialogs/
  roles_editor.py`, `tui/dialogs/org_editor.py`, `tui/dialogs/init_tabs.py`
  (the keys tabs), `init_providers.py` (what the keys step saves),
  `roles.py` (the role table, presets if any, `vram_aware_override`),
  `gym_propose` (the gym's proposal), `controller.py::list_models()` and the
  enumeration cache round 3 built, `tui/dialogs/model_picker.py` (the
  grouped list and its fuzzy filter: reuse its data source, do not copy it).

## Deliverables

1. **Enumerate after the keys step, with this run's keys.** When the user
   leaves the keys tabs (Next), the wizard runs one off-thread enumeration
   using the credentials just entered (merge the in-progress values over
   the saved config; never write them yet) for every provider the
   `/model` picker knows, including every Ollama host and LAN host, local
   servers, the HF router and cache, OpenAI, Codex, Claude Code,
   Experiential, OpenRouter, Databricks and Anthropic. Show one progress
   line per provider as it answers; a provider that is not reachable gets
   a "not reachable" row and never blocks the step (bounded timeouts). The
   merged list is cached for the rest of the wizard run and reused by the
   roles step, the org step and the summary. Re-running the keys step
   re-enumerates.
2. **Pick list plus autocomplete in the role editor.** Editing a role shows
   the merged list grouped by provider (same groups and labels as `/model`),
   with the gym score beside a model when one exists; the ref field
   autocompletes from the list as the user types (prefix and fuzzy, like
   the picker's filter); a ref not in the list is still accepted with a
   one-line note ("not in the enumerated list; kept as typed").
3. **The same in the company/org roles editor** (`org_editor.py` and the
   wizard's org step): every position's model field uses the same pick list
   and autocomplete; and in the TUI `/roles` and `/org` editors outside the
   wizard (they read the live `Controller.list_models()`).
4. **The Auto tab** in the role editor (wizard and `/roles`): one key fills
   every role from a preset (local-first, balanced, quality) or from
   `halo gym propose` when gym data exists, shows the resulting table with
   one sentence per choice, lets the user adjust, then Save. Presets are
   defined once in `roles.py` (document them in docs/ROLES or the roles
   section of docs/CONFIG.md).
5. Docs: the init wizard section (docs/INSTALL or docs/QUICKSTART, wherever
   `halo init` is documented), docs/SLASH-COMMANDS.md for `/roles` and
   `/org` changes, CHANGELOG `[2.0.4]` "### Roles wizard" bullets.

## Tests (hermetic, no network, no real providers)

- A Textual pilot walk through `halo init` with fixture providers (mocks or
  fixture catalogs for at least three providers, one of them "not
  reachable"): the enumeration cache fills after the keys step, the roles
  step lists the models grouped by provider, autocomplete narrows on typing,
  a typed-only ref is accepted with the note, the org step shows the same
  list, Save round-trips into the real config files under the scratch home.
- The Auto fill from each preset and from a gym fixture; the proposal table
  text; adjusting one role before Save.
- `/roles` and `/org` outside the wizard with a fake controller.

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere. Describe behaviour.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file; `halo audit privacy` stays at exit 0; privacy scan and
  invariants green.
- Never block the UI thread: enumeration and gym proposals run in workers.
- No new hard dependency. Keep modules under the house size conventions.
- Do not duplicate the picker's data source; share it.

## Verification before hand-back

Every test module you touched or added (TUI pilots through a filtered
runner, not the whole test_tui.py), `python test_bridge.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python tests/test_docs_slash_commands.py`, `python -m halo_harness audit
privacy`, all green. Record `stat -c %s ~/.halo/history.jsonl` and
`ls ~/.halo/sessions | wc -l` at the start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-5: DONE / PARTIAL with evidence and the
pinning test names), FILES TOUCHED, WHAT YOU FOUND (anything in the roadmap
text that no longer matches the code, anything left open and why, and the
manual check for the owner: run `halo init`, enter keys, reach the roles
step, edit a role, see the list and the autocomplete). No commit, no push.

## Added 2026-10-05 ~22:45 (rolo, approved): agent declaration files are the storage

Read `plans/ROADMAP.md` section "ADDED 2026-10-05 ~22:45 (rolo): agent
declaration files (YAML) behind roles and orgs" and build it in this round:

6. `halo_harness/agents_yaml.py` (loader, validator, writer): the schema in
   that section, `extends`, the precedence chain, user and project
   locations, the shipped templates under `halo_harness/templates/agents/`
   (add the directory to pyproject's package-data the way
   providers/catalog/*.json is listed), import from and export to Claude
   Code's `.claude/agents/*.md` frontmatter. Add `pyyaml` to pyproject's
   dependencies (and the dev extra if separate). `halo agents list|show|
   validate|new <name> --from <template>|export|import` CLI, `/agents` in
   the TUI, `halo doctor --agents` running each file's `acceptance` block
   against a mock in tests and the real model live.
7. The roles editor, the org editor and the Auto tab READ and WRITE these
   files (the role table in config stays as the derived view for
   compatibility; a legacy table with no files is migrated into files on
   the first wizard save, announced in one line).
8. Tests: round-trip every section, `extends` precedence, validation
   errors (one plain line each), the frontmatter import/export, the
   migration, the CLI and `/agents`. Docs: docs/AGENTS.md (new) describing
   every field with one example file, linked from CONFIG.md and
   SLASH-COMMANDS.md; CHANGELOG bullets.

## Added 2026-10-06 ~00:25 (rolo): two layers, bios and team templates

Deliverables 6-8 follow ROADMAP section "ADDED 2026-10-06 ~00:25 (rolo):
agent BIOS and team TEMPLATES are two layers": agent bios (who an agent is)
and team templates (which agent fills which role or position), with the
CLIs `halo agents ...` and `halo teams ...`, `/agents` and `/teams`, the
active-team config key, the migration, and docs/AGENTS.md covering both.
