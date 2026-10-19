# Commands: roles, review, bios and lineups

Read this when you manage roles, reviews, bios and lineups from the command line.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo roles`

```sh
halo roles                           print the roles state, then the configured table
                                     (each role says where its value came from)
halo roles on
halo roles off
halo roles template list
halo roles template show <name>
halo roles template save <name> [--description TEXT]
halo roles template new <name> [--description TEXT]
halo roles template load <name>
halo roles template edit <name>
```

GUI: `halo studio --mode roles` shows the same roles as a graph in the browser (in the TUI, `/roles`).

Halo 2.0.5 round 2b: `on`/`off` is the ONE switch for `roles.enabled`,
from the CLI (`/roles on|off` in the TUI/print mode, and a "Roles: on /
off" toggle at the top of the init wizard's "Roles and lineup" step are
the other two surfaces that write the SAME key). Bare `halo roles` always
prints the state as its first line -- `roles: on (lineup <name>)` when a
lineup is active, `roles: on (legacy role table)` with roles on but no
lineup, or `roles: off (standard: every role uses the default model)` --
before the configured table below it. **Halo 2.1.0**: each role line ends
with its source in brackets -- `[lineup <name>]` (the active lineup defines
it), `[legacy table]` (set outside the lineup) or `[session default]`
(nothing set; it follows the session model). `halo roles template load <name>`
also turns roles ON (the fixed weak spot: loading used to leave the table
sitting inert until a hand edit of config.json); `halo teams use <name>`
([AGENTS.md](AGENTS.md)) is the non-overwriting way to just point the
active lineup at a different, already-matching table without reloading
one.

Halo 2.0.2: manages `~/.halo/roles/<name>.json` role templates (`{"name",
"description", "roles": {role: model_or_{"model","effort"}}}`). `save`
captures the CURRENT `~/.halo/config.json` role table under a name; `new`
starts an empty one; `load` writes every role the template defines back
into config.json, overwriting a stale local value for that role (the one
deliberately non-idempotent write in this whole table -- see
[ROLES.md](ROLES.md)'s own precedence section); `edit` opens `$EDITOR`/
`$VISUAL` on the raw JSON file (creating it first if it doesn't exist),
re-validating on save. The TUI's own `/roles edit <name>` opens a form
instead (`tui/dialogs/roles_editor.py`) unless `roles.editor: "external"`
is configured, in which case it uses the same `$EDITOR` flow as this CLI
command; that form, and the init wizard's own Roles step, both gain a
"start from" template picker in round 7 (three shipped presets --
`balanced`/`quality`/`local-first` -- written on first use, never
overwritten). See [ROLES.md](ROLES.md) for the full picture: the role
table itself, per-role effort, custom role names, `/role`/`/roles` in the
TUI and print mode, the presets, and the `roles.enabled` mode switch.

## `halo review`

```sh
halo review [target ...] [--level {low,medium,high}] [--dimensions LIST] [--fix] [--no-verify]
            [--json] [--model REF] [--role NAME=MODEL[:EFFORT]] [--cwd DIR]
```

Halo 2.0.10: review a change with parallel dimension reviewers and a judge,
and print the ranked findings (the same thing `/review` does in the TUI).
`target` is nothing (this branch against its merge base with the default
branch, uncommitted changes included), a range `a..b`, a branch, a pull
request (`#123` or `123`, through `gh`), or one or more paths/globs reviewed
as they are. Exit code 0 whenever the review ran (findings never change it),
1 if every reviewer failed, 2 for usage errors and targets that cannot be
resolved. Progress lines go to stderr; the result goes to stdout. See
[REVIEW.md](REVIEW.md) for the pipeline, the JSON shape and the cost.

#### `--level {low,medium,high}`

How many findings each reviewer may report (3, 8, 20) and how speculative
it may be. Default `medium`.

#### `--dimensions LIST`

A comma-separated subset of `correctness`, `security`, `performance`,
`tests`, `docs-consistency`. Default: all five.

#### `--fix`

After verification, a `coder` sub-agent applies a minimal fix in the working
tree for each CONFIRMED finding (never committing) and the judge re-checks
it; each finding gets an `outcome` of `fixed`, `skipped` or
`no_change_needed`. Runs the session in `acceptEdits` mode. Not combinable
with `--no-verify`.

#### `--no-verify`

Skip the judge: findings stay PLAUSIBLE and none are dismissed.

#### `--json`

Print one JSON object `{target, findings, dismissed, reviewers, cost_usd,
elapsed_s}` with the ReportFindings field names instead of text.

#### `--model REF`, `--role NAME=MODEL[:EFFORT]`, `--cwd DIR`

`--model` is the model for roles with none of their own; `--role` (repeatable)
sets the `reviewer`, `judge` or `coder` role for this run; `--cwd` is the
repository or directory to review (default: the current directory).

## `halo agents`

```sh
halo agents
halo agents list
halo agents show <name>      (or just: halo agents <name>)
halo agents validate [name]
halo agents new <name> [--from BIO] [--project] [--studio]
halo agents edit <name> [--no-open] [--yaml]
halo agents export <name> [file] [--claude-md]
halo agents import <file> | --claude-md <name>
halo agents schedule list
halo agents schedule run <name>
halo agents schedule pause <name>
halo agents schedule resume <name>
halo agents schedule rm <name>
```

GUI: `halo studio --mode roles` edits bios and lineups as a graph in the browser (in the TUI, `/roles`).

**Halo 3.1.1.0: Studio is the editor.** `halo agents edit <name>` opens
Studio's bio form on the bio (Roles -> Bios), the same as `halo studio --edit
bio:<name>`: a Studio already running for this home switches its open page to
the bio, else one starts in the background and opens your browser; the line
it prints says which, with the URL. A name with no bio yet gets a starter
file first. `--no-open` prints the URL and opens nothing (over SSH: forward
the port and open it on your machine). `--yaml` is the terminal-only way:
`$VISUAL`/`$EDITOR` on the bio's YAML file, re-validated when the editor
exits. `new <name> --studio` writes the starter bio, then opens it in Studio.
Exit codes: 0 opened (or the URL printed), 1 Studio did not start or the
saved YAML has problems, 2 a name that is not a valid bio name.

**Halo 2.1.0**: bare `halo agents` lists the bios grouped by where they
live (project, user, shipped), one per line with its kind and preferred
model, and ends with `halo agents show <name>`; `halo agents <name>` is the
same as `show`.

Halo 2.0.4 round 4: manages agent BIOS (`~/.halo/agents/<name>.yaml`
user, `.halo/agents/<name>.yaml` project, shipped read-only starters
under the package's own `templates/agents/`) -- a bio describes what one
agent IS (models, tools, context, limits, output, environment,
acceptance; never a role or position). `new --from BIO` copies another
bio's file verbatim as a starting point; `export --claude-md`/`import --claude-md` bridge
to Claude Code's own `.claude/agents/*.md` frontmatter (lossy both ways --
see [AGENTS.md](AGENTS.md)'s own field table).

`/agents` in a running session opens the list-with-actions screen (new,
new from..., view, edit in Studio, duplicate, delete, import from
`.claude/agents/*.md`); view shows the bio read-only in the terminal and `e`
there opens Studio on it. Every other subcommand (`show`/`validate`/
`export`/`import`) stays plain text. See
[AGENTS.md](AGENTS.md#editing-bios-and-lineups-studio-is-the-editor-halo-3110)
for the bio form's fields and the terminal's bio view.

**Halo 2.0.5 round 5**: `schedule list` shows every armed schedule and
trigger (any owning session) with each schedule's next fire time, from
`<state>/agents-schedules.json`; `run <name>` fires one right now through
`halo bg`'s own detached background-run surface; `pause`/`resume`/`rm`
manage the armed entry. Schedules and triggers ARM when a session that
loaded the agent's team is alive and DISARM when it closes -- never a
system service; `/agents schedule` in a running session prints the same
list. See [AGENTS.md](AGENTS.md)'s `hooks`/`schedule`/`triggers` section
for the bio schema.

## `halo teams`

```sh
halo teams
halo teams list
halo teams show <name>
halo teams preview <name>
halo teams apply <name> [--one-model]
halo teams diff <a> <b>
halo teams validate [name]
halo teams new <name> [--from TEMPLATE] [--project] [--studio]
halo teams edit <name> [--no-open] [--yaml]
halo teams use <name>
halo teams export <name> [file]
halo teams import <file>
```

GUI: `halo studio --mode roles` edits lineups as a graph in the browser (in the TUI, `/roles`).

**Halo 3.1.1.0: Studio is the editor.** `halo teams edit <name>` opens the
lineup in Studio's Roles section with the Inspector on its Lineup tab (every
section as a form, each with its YAML toggle), the same as `halo studio
--edit lineup:<name>`; a running Studio's open page switches to it. A name
with no lineup yet gets a starter file first. `--no-open` prints the URL;
`--yaml` opens `$VISUAL`/`$EDITOR` on the lineup's YAML file instead and
re-validates it; `new <name> --studio` writes the starter lineup, then opens
it in Studio. Exit codes as for `halo agents edit`.

**Halo 2.1.0**: one obvious path. Bare `halo teams` prints the active
lineup (or "One model for everything: <model>"), its tree exactly as the
wizard previews it (`role -> agent -> model`, price, warnings, one cost
line), then one line per other lineup with its scope and description.
`apply <name>` (and `use <name>`, the same thing) writes the lineup's
`roles.*` and `team:` and turns custom roles on -- the same config the
wizard's Team step writes -- then prints the roles now in force;
`apply standard` or `apply --one-model` applies `standard` with roles off.
An unknown or invalid lineup changes nothing and prints the validator's
lines. `preview <name>` prints the tree; `diff <a> <b>` compares two
lineups role by role (`-` only on the left, `+` only on the right, `~`
differs, "No difference" when equal).

Halo 2.0.4 round 4: manages team templates ("lineups",
`~/.halo/teams/<name>.yaml` user, `.halo/teams/<name>.yaml` project,
shipped starters -- `local-first`/`balanced`/`quality`/`halo-dev-cycle`
-- copied in on first use) -- a lineup ASSIGNS agent bios to roles/
positions (`agents:`, or the `roles:` shorthand for one assignment per
role), plus `delegation`/`routing`/`budget`/`escalation`/`context`/
`permissions`/`pipeline`/`acceptance`. `show` prints the lineup,
its resolved role table, and -- since Halo 2.0.5 round 5 --
the per-section ENFORCEMENT state (enforced / not set / checked by
doctor, with the one behaviour line each: a session running under the
team executes these through `teams_runtime.py`, `--team <name>` for one
run); `use <name>` is `apply <name>` (see above).

**Halo 2.0.5 round 2**: `edit` (symmetrical with `agents edit`; Studio since
3.1.1.0). `show` also prints `about:` when the lineup has one. `/teams list`
in a running session opens the list screen (view, edit in Studio, new,
activate); `/teams view <name>` shows a lineup read-only in the terminal
(its `e` opens Studio, `t` tests a row's model); every other subcommand stays
plain text. See
[AGENTS.md](AGENTS.md#editing-bios-and-lineups-studio-is-the-editor-halo-3110)
for the lineup inspector's fields and the terminal's lineup view.


The export/import pair also ships lineups as one PORTABLE FOLDER:
`halo teams export <name> --bundle <dir>` writes the full template plus
every non-shipped bio it references (and a `bundle.json` manifest);
`halo teams import <dir> [--force]` applies it on any box -- every bio
is validated first (one invalid bio refuses the whole import, nothing
written), bios land in user scope, a bio colliding with one of your own
(user or project scope) is reported and skipped unless `--force`, a bio
named like a shipped one is installed and the import prints a
"shadows shipped bio(s)" line (every lineup on that machine that assigns
it then uses the bundle's copy), and the team goes through the same
validated save path.
## `halo subscriptions scrub`

3.0.2.0: rewrites every `cc:`/`cx:` model ref in your bios and lineups
(`~/.halo/agents`, `~/.halo/teams`, the project's `.halo/agents` and
`.halo/teams`) to its OpenRouter equivalent and prints what moved. Only
model-valued keys change (`models.preference`/`fallback`/`escalation`,
`escalation.to`, a position's `model`, an inline `models:`); descriptions,
prompts, comments and URLs stay as written, and a file keeps its own line
endings. It also runs on its own the first time lineups are listed in a
process (`halo teams list`, `/teams`), which then print one line per file
it rewrote, so pre-made copies from older versions stop naming
subscription models.
