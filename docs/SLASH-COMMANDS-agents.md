# Slash commands: agents, lineups, roles and review

Read this when you work with bios, lineups, roles, organizations or `/review` from the prompt.

Part of [Slash commands, keys, and prompt prefixes](SLASH-COMMANDS.md), which lists every part.

## Built-in commands: agents, lineups, roles and review

### `/agents [new <name>|edit <name>|duplicate <name> [new-name]|delete <name>]`
Bare `/agents` (or `/agents list`) lists every discovered sub-agent
definition (built-ins plus `.claude/agents`/`~/.claude/agents`/
`--agents`/managed/plugin), pulled from the live session's own agent
runtime when one is attached, plus a second section listing every
**agent bio** (`halo_harness/agents_yaml.py`, `halo agents show <name>`
for the full YAML) -- a different, additive concept describing what an
agent IS (models/tools/context/limits), assigned to a role by a **team
template**.

**Halo 2.1.0**: in print mode, the bios section of `/agents` uses the same
grouped lines as `halo agents` (project / user / shipped, kind and model per
line, ending with the `halo agents show <name>` hint).

**Halo 3.0.5.0 (Fleet)**: `/agents live` lists THIS session's running
agents instead: the main agent and every sub-agent at every depth (and
background Bash jobs), indented under their parents, with state, cost so
far, model and what each one is doing (the tool in flight, or its task).
It is the same tree Studio and `halo remote agents <session>` show; see
[SUBAGENTS.md](SUBAGENTS.md).

**Halo 2.0.5 round 2**: bare `/agents` instead opens an interactive
list-with-actions screen over the bios (New, New from..., Edit,
Duplicate, Delete, Import from `.claude/agents/*.md`, one result line
each); `new`/`edit <name>` open the bio form directly (identity, models
with the enumerated/Agents-source picker, tools, context, limits,
output, environment, acceptance -- see [AGENTS.md](AGENTS.md)'s wizard
section); `duplicate <name> [new-name]` copies a bio (a shipped one
lands in user scope, shadowing it); `delete <name>` removes a project/
user-scope bio. Every other subcommand (`show`/`validate`/`export`/
`import`) stays the plain-text form documented above. `halo agents
new|edit <name> --form` opens the SAME form from the CLI -- see
[COMMANDS.md](COMMANDS.md#halo-agents).

**Halo 2.0.5 round 5**: `/agents schedule` prints what schedule/trigger
set is armed right now (any owning session) and each schedule's next
fire time -- the same lines `halo agents schedule list` prints. A bio's
`schedule:`/`triggers:` arm while a session that loaded the agent's team
is alive and disarm when it closes; see [AGENTS.md](AGENTS.md)'s
`hooks`/`schedule`/`triggers` section.

### `/teams [apply <name>|preview <name>|diff <a> <b>|list|new <name>|edit <name>|activate <name>]`
**Halo 2.1.0**: bare `/teams` prints the same overview as `halo teams` (the
active lineup, its tree, one line per other lineup); `/teams apply <name>`
(or `use`) applies a lineup exactly like `halo teams apply` (writes
`roles.*` and `team:`, turns roles on; `standard` turns them off);
`/teams preview <name>` prints the tree; `/teams diff <a> <b>` compares two
lineups. The interactive list screen moved to `/teams list`.

Bare `/teams` lists every installed **team template** ("lineup" --
`halo_harness/teams_yaml.py`, `~/.halo/teams/<name>.yaml`), marking the
active one (`team` in config.json, `halo teams use <name>`).

**Halo 2.0.5 round 2**: bare `/teams` instead opens an interactive list
screen (list, New, Edit, Activate); `new`/`edit <name>` open the lineup
editor directly (the assignments grid, the collapsed advanced sections,
the `about:` "how the pieces work together" text -- see
[AGENTS.md](AGENTS.md)'s wizard section); `activate <name>` validates
and sets the active `team:` without opening the editor. Every other
subcommand (`show`/`validate`/`use`/`export`/`import`) stays the plain-
text form documented above -- `halo teams show <name>` (CLI) prints the
full resolved role table and the `about:` text when the lineup has one.
`halo teams new|edit <name> --form` opens the SAME editor from the CLI
-- see [COMMANDS.md](COMMANDS.md#halo-teams).

**Halo 2.0.5 round 5**: `/teams show <name>` prints the same resolved
view as the CLI, plus the per-section ENFORCEMENT state (enforced / not
set / checked by doctor, one behaviour line each) -- a session running
under the team (`team:` in config.json or `--team <name>`) executes
those sections through `teams_runtime.py`.

### `/roles [gui|table|on|off|templates|save <name>|load <name>|new <name>|edit <name>|show <name>|set <name> <model> [effort]]`
Halo 3.0.2.0: in the TUI, bare `/roles` opens **Halo Studio's Roles mode** in
the browser (lineups and agent bios as an editable graph, see
[STUDIO.md](STUDIO.md)); `/roles gui` says the same thing anywhere, `/roles
gui url` prints the URL without opening a browser, and `/roles table` is the
text table below. Outside the TUI (`halo -p`, Signal) bare `/roles` stays the
text table.

V2c (H15), extended Halo 2.0.2: the text table: the resolved role table
(model, effort, endpoint/path type, price per role), pulled from the live
session's own `agent_runtime.role_table`/`.cli_role_overrides` (the SAME
table a role-bearing `Agent`/`Task` call actually resolves against) so it
never drifts from real behavior. `templates`/`save`/`load`/`new`/`show`
manage `~/.halo/roles/<name>.json` templates; `edit` opens a form in the TUI
only (print mode names that instead); `set` is the long form of `/role`
below. Round 5b part 2: a VRAM-aware role redirected to the main model
(`docs/MODELS.md`'s "VRAM-aware role defaults") shows `(same as main:
fits beside it: no)` next to that role's own source. See `docs/ROLES.md`.

Halo 2.0.5 round 2b: `on`/`off` is the ONE switch for `roles.enabled` --
the SAME key `halo roles on|off` and the wizard's "Roles: on / off" toggle
write; `load <name>` now also turns it on (printed in the reply).

Halo 2.0.4 round 4: `edit <name>` (and the wizard's own "Edit roles...")
now picks a model from the SAME merged, enumerated, grouped list `/model`
shows (`docs/ROLES.md`'s own "Enumeration after the keys step" section),
with autocomplete and a one-line note on a typed-only ref, plus a second
**Auto** tab that fills every role from a preset, an installed team
template, or `halo gym propose` in one action (`ctrl+a`), adjustable
before `ctrl+s`.

### `/role <name> <model> [effort]`
Halo 2.0.2: sets ONE role for THIS session only -- mutates the live
session's own role table directly (never persisted; `/roles save <name>`
is the explicit "keep this" action), so the very next `Agent`/`Task` call
that resolves this role picks it up. `<name>` must already be a known role
(a built-in, or a custom name a team.json/loaded template actually defined)
-- an unknown name errors with the list of known ones. See `docs/ROLES.md`.

### `/org [gui|on|off|list|show <name>|new <name>|load <name>|install <name> [--force]|edit <name>|run [<name>] "<goal>"|export <name> [file]|import <file>|resume]`
Halo 3.0.2.0: in the TUI, bare `/org` opens **Halo Studio's Org mode** (your
company in Paperclip: titles, reporting lines, budgets, issues; see
[STUDIO.md](STUDIO.md) and [PAPERCLIP.md](PAPERCLIP.md)); `/org gui` does the
same anywhere, `/org gui url` prints the URL only. **`/org on|off` is the Org
mode switch** (off by default): on resumes the linked company's Halo agents so
Paperclip's heartbeats run them, off pauses them and every heartbeat answers
idle; the reply says who orchestrates what ([PAPERCLIP.md](PAPERCLIP.md)).
`/org list` is the text list
of Halo's own legacy organizations below, which bare `/org` still prints
outside the TUI.

Halo 2.0.2 round 2: `/org list` (bare `/org` outside the TUI) lists saved
organizations (`~/.halo/orgs/<name>.json`), each with its own one-line
README (its `description`); `show` prints the text tree; `new` creates a
one-position "Orchestrator" starter; `load` re-installs a built-in's
shipped definition over a local copy; `edit` opens a form in the TUI only
(print mode names that instead, like `/roles edit`); `run` executes the
org's root position on `"<goal>"` against the LIVE session, through the
exact same machinery an `Agent(org=...)` tool call uses -- the result
flows back like any other sub-agent's. Round 7: `<name>` is optional on
`run` -- `/org run "<goal>"` (just the goal, quoted) uses `orgs.default`
(set via `/setup orgs`); with none set, it names the fix instead of
guessing. Round D: `install <name> [--force]` copies a shipped or saved
template into `~/.halo/orgs/`, refusing to overwrite without `--force`;
`export <name> [file]`/`import <file>` move an org as plain JSON (import
validates role names, reports and budgets, listing every problem);
`resume` continues THIS session's own interrupted org run from its saved
run record and shared task board (open/claimed tasks become the work
list, done tasks are kept) -- `halo org resume <session-id>` is the CLI
form, for a past session with no "current" one to resume. A position with
`requires_approval: true` holds its result as a pending card in the dock
(accept, edit the instruction and re-run, or stop) before its own parent
continues; `dontAsk` mode (and `halo org run/resume --yes`) accepts every
gate automatically instead. See `docs/ORGS.md`.

Halo 2.0.4 round 4: `edit <name>`'s own "Role or model" field shows live
autocomplete suggestions from the same merged, enumerated list as it's
typed, and a one-line note if the committed value matches nothing in it
(still accepted either way).

### `/review [target] [--level low|medium|high] [--dimensions a,b] [--fix] [--no-verify]`
Halo 2.0.10: review a change with parallel dimension reviewers (correctness,
security, performance, tests, docs-consistency; one read-only sub-agent each,
on the `reviewer` role) and a judge that checks every finding (`judge` role).
`target` is nothing (this branch against its base, uncommitted changes
included), a range `a..b`, a branch, a PR number (`#123`, needs `gh`), or paths
and globs reviewed as they are. The reviewers appear live in `/tasks`; the
result lands in the transcript as a header line ("N findings (c confirmed, p
plausible) from d reviewers in t s, $cost") and one card per finding: severity,
`file:line` (click it, or press `c`, to copy), the verdict badge and the short
summary, with the failure scenario folded (Enter or a click unfolds it, `y`
copies the finding). `--fix` has a `coder` sub-agent apply a minimal fix per
CONFIRMED finding in the working tree (never committing) and re-verifies it;
`--no-verify` skips the judge. Esc aborts every reviewer. Runs on a worker
thread. In print mode (`-p "/review ..."`) it prints the text form; `halo
review` is the CLI form, with `--json`. See `docs/REVIEW.md`.

### `/setup [roles|orgs]`
Halo 2.0.2 round 7: opens the init wizard's own Roles/Organizations setup
screen(s) over the live session (a modal screen stack, not a separate
program) -- bare `/setup` chains Roles -> Organizations -> a short
summary; `/setup roles`/`/setup orgs` open just one. Saving a role
template here updates the LIVE session's own role table immediately, no
restart needed. `halo setup [roles|orgs]` is the CLI equivalent (prints
the current roles table/orgs list with no TTY instead of blocking). See
`docs/ROLES.md`/`docs/ORGS.md`.
