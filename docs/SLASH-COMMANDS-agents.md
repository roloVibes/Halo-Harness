# Slash commands: agents, lineups, roles and review

Read this when you work with bios, lineups, roles or `/review` from the prompt.

Part of [Slash commands, keys, and prompt prefixes](SLASH-COMMANDS.md), which lists every part.

## Built-in commands: agents, lineups, roles and review

### `/agents [new <name>|edit <name>|view <name>|duplicate <name> [new-name]|delete <name>]`
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

**Halo 2.0.5 round 2, 3.1.1.0**: bare `/agents` instead opens an interactive
list-with-actions screen over the bios (New, New from..., View, Edit in
Studio, Duplicate, Delete, Import from `.claude/agents/*.md`, one result line
each). Studio is the one editor of bios: `/agents edit <name>` opens Studio's
bio form on it (the Studio page already open switches to it, else Studio
starts and opens your browser; the transcript line says which, with the
URL); `/agents new <name>` writes the starter bio, then opens it in Studio;
`/agents view <name>` shows the bio read-only in the terminal (every field
with its help line, the file as YAML; `e` opens Studio on it, `t` tries it,
cost first). `duplicate <name> [new-name]` copies a bio (a shipped one lands
in user scope, shadowing it); `delete <name>` removes a project/user-scope
bio. Every other subcommand (`show`/`validate`/`export`/`import`) stays the
plain-text form documented above. From the CLI: `halo agents edit <name>` --
see [COMMANDS-agents.md](COMMANDS-agents.md#halo-agents).

**Halo 2.0.5 round 5**: `/agents schedule` prints what schedule/trigger
set is armed right now (any owning session) and each schedule's next
fire time -- the same lines `halo agents schedule list` prints. A bio's
`schedule:`/`triggers:` arm while a session that loaded the agent's team
is alive and disarm when it closes; see [AGENTS.md](AGENTS.md)'s
`hooks`/`schedule`/`triggers` section.

### `/teams [apply <name>|preview <name>|diff <a> <b>|list|new <name>|edit <name>|view <name>|activate <name>]`
**Halo 2.1.0**: bare `/teams` prints the same overview as `halo teams` (the
active lineup, its tree, one line per other lineup); `/teams apply <name>`
(or `use`) applies a lineup exactly like `halo teams apply` (writes
`roles.*` and `team:`, turns roles on; `standard` turns them off);
`/teams preview <name>` prints the tree; `/teams diff <a> <b>` compares two
lineups. The interactive list screen moved to `/teams list`.

Bare `/teams` lists every installed **team template** ("lineup" --
`halo_harness/teams_yaml.py`, `~/.halo/teams/<name>.yaml`), marking the
active one (`team` in config.json, `halo teams use <name>`).

**Halo 2.0.5 round 2, 3.1.1.0**: `/teams list` opens an interactive list
screen (View, Edit in Studio, New, Activate). Studio is the one editor of
lineups: `/teams edit <name>` opens the lineup in Studio's inspector (Lineup
tab), `/teams new <name>` writes the starter lineup and opens it there, and
`/teams view <name>` shows it read-only in the terminal (the resolved
assignments, warnings, costs, every section's YAML, the `about:` text; `e`
opens Studio, `t` tests the highlighted row's model, Smoke run runs every
member's acceptance prompt, cost first). `activate <name>` validates and sets
the active `team:`. Every other subcommand (`show`/`validate`/`use`/`export`/
`import`) stays the plain-text form documented above -- `halo teams show
<name>` (CLI) prints the full resolved role table and the `about:` text when
the lineup has one. From the CLI: `halo teams edit <name>` -- see
[COMMANDS-agents.md](COMMANDS-agents.md#halo-teams).

### `/tools`
Halo 3.1.8.0 R5: the tools this session's agent sees, one line per
capability (read, edit, bash, web, agent, `mcp:<server>`, media, recall,
other) with the tool names in it, then what narrowed the list ("Narrowed to
tools: read, edit, bash (by lineup ci)", or "(by bio reviewer)") or that
nothing does, then an Orchestra worker's isolation and secrets lines. A
lineup or bio narrows it with `tools.capabilities`; see
[ISOLATION.md](ISOLATION.md#toolscapabilities).

### `/edit <bio:name|lineup:name|team>`
Halo 3.1.1.0: opens Studio on the thing to edit -- `bio:<name>` (the bio
form), `lineup:<name>` (the lineup's inspector), `team` (the Team section),
or a bare name (the bio of that name, else the lineup of that name) -- the
same as `halo studio --edit`. A Studio already running for this home switches
its open page to it; otherwise one starts in the background and opens your
browser. The transcript gets one line: what opened, and the URL (when no
browser can be opened, the URL is the way in). An unknown name says so and
opens nothing. In print mode `/edit` prints the `halo studio --edit` command
to run.

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

### `/setup [roles]`
Halo 2.0.2 round 7: opens the init wizard's own Roles setup
screen over the live session (a modal screen stack, not a separate
program) -- bare `/setup` chains Roles -> a short
summary; `/setup roles` opens just the one. Saving a role
template here updates the LIVE session's own role table immediately, no
restart needed. `halo setup [roles]` is the CLI equivalent (prints
the current roles table with no TTY instead of blocking). See
`docs/ROLES.md`.
