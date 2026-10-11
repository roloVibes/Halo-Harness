# 2.1.0 round B2 -- the CLI: one obvious path to pick and inspect a lineup

Read `plans/WORKER-RULES.md` first. Work ONLY in this checkout
(`<home>\Halo-B`, branch `track-b`). Do not commit or push. Round B1
(the Team step, `tui/dialogs/team_preview.py`) and B3 (`halo studio`) are
already committed on this branch; build on them, never rewrite them.

## Why

The owner wants agents/roles to be "the clearest and smoothest part of this
set up ... easily change and apply templates for agent assignments thru wizard
or command line". The wizard side is B1. The CLI today has `halo teams use`,
`halo agents`, `halo roles` with inconsistencies the survey found:

- `halo teams use` writes only `team:` (`teams_cli.py:205`), while the wizard's
  `apply_team_template` (`teams_yaml.py:657`) writes `roles.*` AND `team:` and
  the Team step flips `roles.enabled` on. The CLI and the wizard must produce
  the same config.
- `agents_cli.py:279` advertises a bare `halo agents <name>` that the
  `_SUBCOMMANDS` dispatch rejects as "unknown subcommand".
- There is no `apply`, no `preview`, no `diff`, and no no-argument overview.

## Deliverables

1. **`halo teams` with no arguments** prints an overview: the active lineup (or
   "One model for everything: <model>"), then its tree exactly as the wizard
   previews it (`team_preview.preview_lines(name, ...)`, reuse it, do not
   re-implement), then one line per other reachable lineup (name, scope,
   description). **`halo agents` with no arguments** lists bios grouped by
   scope (project / user / shipped) with kind and preferred model, one per
   line, and ends with the one-line hint `halo agents show <name>`.
2. **`halo teams apply <name>`** (the plain verb) and `halo teams use <name>`
   both call `teams_yaml.apply_team_template` and then `roles.set_roles_enabled
   (True)`, printing the resolved roles afterwards (reuse
   `team_preview.applied_summary_lines`). `halo teams apply standard` (or
   `--one-model`) applies `standard` and sets roles OFF, like the wizard's
   first row. Refuse an unknown lineup with the validator's own lines.
3. **`halo teams preview <name>`** prints the tree (`preview_lines`); **`halo
   teams diff <a> <b>`** prints a role-by-role comparison (role, agent, model
   for each side; `-`/`+`/`~` markers; "no difference" when equal).
4. **Bare `halo roles`** (`roles_cli.py:300`) gains a first line naming the
   active lineup and whether custom roles are on, and, per role, where the value
   came from (lineup `<name>` / legacy table / session default).
5. **`halo agents <name>`** works as the usage line promises (an alias of
   `show`); fix the usage text if anything else it lists does not exist.
6. **TUI:** `/teams` (no args) prints the same overview as `halo teams`;
   `/teams apply <name>` and `/teams preview <name>` exist; `/agents` (no args)
   keeps its current two sections but the bios section uses the same grouped
   lines as `halo agents`. Register through `commands/builtins.py`
   `_BUILTIN_SPECS` (headless and TUI share it); the existing TUI overrides in
   `tui/slash.py` must keep working.
7. **Plain words:** read every error and notice string in `teams_cli.py`,
   `agents_cli.py`, `roles_cli.py` and the `_cmd_teams`/`_cmd_agents` builtins
   once; rewrite anything a first-time user would not understand (no round
   numbers, no internal jargon). Keep the sentences short.
8. **Tests:** extend `tests/test_agents_teams.py` (the `_Env` + `_run_cli`
   pattern): the overviews, apply/use writing `team`, `roles.*` and
   `roles.enabled`, `apply standard` turning roles off, preview, diff (equal
   and different), `halo agents <name>`, `halo roles` source lines. Extend
   `tests/test_agents_teams_forms.py` or the slash tests for `/teams apply` and
   `/teams preview`. Any test that pinned `use` writing only `team:` is updated.
9. **Docs:** `docs/COMMANDS.md` (`halo teams`, `halo agents`, `halo roles`
   sections), `docs/SLASH-COMMANDS.md` (`/teams`, `/agents`), `docs/AGENTS.md`
   "The 90-second version" bullet 2 (the CLI) and its CLI section, `docs/
   ROLES.md` where `halo roles` is described, CHANGELOG `## [2.1.0] -
   unreleased` gets a B2 entry under the B1 one.

## Constraints

- No new dependencies. No safety/refusal wording.
- Every file write <= 250 lines; split modules rather than grow them (a new
  `teams_cli_views.py` for the overview/preview/diff printing is fine).
- Tests: `python -m tests.<module>` with a scoped `BRIDGE_TEST_HOME`,
  `BRIDGE_TEST_NO_BACKGROUND_NET=1`, `PYTHONIOENCODING=utf-8`. Run the modules
  you touched plus `python test_bridge.py` and `python test_tui.py` (then `git
  checkout -- docs/harness/tui-snapshots`). The one pre-existing failure to
  ignore: `test_tui.py::test_bare_effort_card_selection_persists_like_the_plain_
  text_path`.
- On this host the Bash tool corrupts backslash escapes inside heredocs: write
  file contents with the Write/Edit tools.

## Hand-back

RESULT LINES per deliverable (DONE / PARTIAL with evidence and test names),
FILES TOUCHED, WHAT YOU FOUND, the final RESULT line of each suite. No
commit, no push.
