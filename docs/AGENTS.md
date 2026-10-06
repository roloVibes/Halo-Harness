# Agent bios and team templates

Halo 2.0.4 round 4 (owner: "each role should have a yaml file that can be
editable too"), two layers, approved 2026-10-05/06:

1. **Agent bios** (`halo_harness/agents_yaml.py`) -- one YAML file per
   agent NAME, describing what that agent IS: its models, tools, context,
   limits, output shape, environment, and an acceptance check. A bio
   never names a role or a position.
2. **Team templates** ("lineups", `halo_harness/teams_yaml.py`) -- one
   YAML file per template, ASSIGNING bios to roles/positions, with
   delegation/routing/budget/escalation/pipeline settings around them.
   The active one is `team` in `~/.halo/config.json` (`halo teams use
   <name>`).

A team template is what the Roles step's **Auto** tab, `/roles`, and
`/teams` show as a pickable, resolvable set of roles -- it never needs a
parallel runtime: applying one just fills the EXISTING role table
(`docs/ROLES.md`) or builds an EXISTING org dict (`docs/ORGS.md`) through
two resolution functions, so every other part of this harness keeps
working completely unchanged.

Verified against `halo_harness/agents_yaml.py`, `agents_md_bridge.py`,
`teams_yaml.py`, `agents_doctor.py`, `agents_cli.py`, `teams_cli.py`,
`commands/builtins.py`, `roles.py::auto_fill_options`, and the shipped
files under `halo_harness/templates/agents/` and `halo_harness/templates/
teams/`.

## Storage and precedence

Both layers use the SAME three-tier, nearest-wins search (`team_config.
py`'s own project/user split, `config/agents_md.py`'s `.claude/agents`
precedence):

| Tier | Agent bios | Team templates |
|---|---|---|
| Project (nearest) | `.halo/agents/<name>.yaml` | `.halo/teams/<name>.yaml` |
| User | `~/.halo/agents/<name>.yaml` | `~/.halo/teams/<name>.yaml` |
| Shipped (read-only) | `halo_harness/templates/agents/<name>.yaml` | `halo_harness/templates/teams/<name>.yaml` |

The shipped team templates (`local-first`/`balanced`/`quality`/
`halo-dev-cycle`) are copied into `~/.halo/teams/` the first time each is
missing there (never overwritten after -- the same "copy on first use"
rule `roles.py`'s own three presets and `orgs.py`'s own built-ins already
follow); the shipped bios are NOT auto-copied -- `extends:`/`--from`
reach them directly in the templates directory, and `halo agents new
<name> --from <bio>` makes an editable copy on request.

`extends: <name>` (both layers) follows the SAME search order. For a
bio, every section (`models`/`tools`/`context`/`limits`/`output`/
`environment`/`acceptance`) merges KEY BY KEY -- a child's own key wins,
a section the child never mentions is inherited whole; identity fields
(`description`/`version`/`tags`/`kind`) never inherit, only `extends`
itself chains. For a team template, every top section
(`delegation`/`routing`/`budget`/`escalation`/`context`/`permissions`/
`org`/`pipeline`/`acceptance`) merges the same way; `agents:` (the
lineup itself) does NOT merge -- a child that defines its own
`agents:`/`roles:` replaces the parent's lineup outright.

## Agent bio fields

```yaml
name: coder-local            # identity -- usually matches the filename
description: Implements a brief using a local model.
version: "1.0"
tags: [subagent, local]
kind: subagent                # main | subagent | researcher | judge | reviewer | custom
extends: coder                 # optional -- another bio to inherit from

models:
  preference: ol:qwen3-coder:30b
  fallback: or:deepseek/deepseek-v4.1-flash
  escalation: cc:claude-opus-5-5   # the roles.py-style escalation target
  effort: medium
  temperature: 0.2
  thinking: native               # native | off
  context_budget: 0.8             # fraction of the model's own context to budget for
  lean_prompt: false

tools:
  allow: [Read, Grep, Glob, Edit, Write, Bash]
  deny: [Agent, WebFetch, WebSearch]
  mcp_servers: []
  permission_mode: auto
  rules: ["deny Bash(git commit*)", "deny Bash(git push*)"]   # settings.json grammar
  limits: {Bash: {timeout: 20}}    # per-tool limits

context:
  files: [plans/WORKER-RULES.md]           # prepended
  obsidian: [{path: "vibes/*.md"}]          # Obsidian notes by path/glob/tag
  skills: []
  system_prompt: "You are careful and terse."   # inline, or system_prompt_file: <path>
  memory: {enabled: false}          # on/off (+ optionally `namespace`/a directory)

limits:
  max_iterations: 40
  timeout: 2h
  max_budget_usd: 6
  max_tokens_per_turn: 8000
  concurrency: 1

output:
  output_schema: review-findings
  report_to: boss
  handoff: structured           # summary | full | structured

environment:
  cwd: null
  worktree: false
  offline: false
  env: []                        # env-var NAMES by reference, never a literal secret

acceptance:
  prompt: "Reply with exactly one word: ok"
  expect: ok                     # a substring to match, or the sentinel "non-empty"
```

`halo doctor --agents` validates every bio's shape, then runs each one's
own `acceptance.prompt` through a real one-shot model call (`halo -p
<prompt> --model <ref>`) and checks the reply against `expect`.

Deferred to 2.0.5 with the Governor: `hooks` (pre/post tool commands) and
`schedule`/`triggers` -- not part of a bio's schema yet.

## Team template ("lineup") fields

The short form -- `roles:` is SUGAR, expanding to one `agents:` entry per
role on load (a minimal template stays five lines):

```yaml
name: balanced
description: The session model for most roles; researcher/small drop to a cheaper agent.
roles:
  main: general
  researcher: local-small
  small: local-small
```

The full form -- any number of assignments, several may share a role,
exactly one has `role: main`:

```yaml
agents:
  - {agent: orchestrator, role: main, as: boss}
  - {agent: implementer, role: subagent, as: worker, instances: 1, use_for: [implement, fix]}
  - {agent: reviewer, role: reviewer, as: review, instances: 3, use_for: [review]}
    # per-assignment override -- wins over the bio's own models/tools/limits:
  - {agent: coder, role: subagent, as: worker2, models: {preference: or:vendor/other-model}}
```

Every OTHER top section, also stored/validated/shown but not enforced by
the live agent loop this round (the Governor's own job, 2.0.5):

```yaml
delegation: {mode: by-skill, max_parallel: 2, max_depth: 1, handoff: structured, forward_text: false}
routing: {implement: worker, review: review, default: boss}     # task kind -> role or alias
budget: {max_budget_usd: 20, max_total_turns: 400, max_wall_time: 3h, agents_may_exceed: false}
escalation: {triggers: [tool_failures, context_overflow], to: cc:claude-opus-5-5, ask: false, allow_fallbacks: true}
context: {files: [CLAUDE.md], skills: [], memory: {namespace: my-team, writers: [boss]}}
permissions: {mode: auto, rules: [], offline: false}
org:
  positions:
    - {title: Boss, agent: orchestrator, delegates_to: [Worker]}
    - {title: Worker, agent: implementer, reports_to: Boss}
  reporting: {cadence: per-round, format: one-line}
pipeline:
  stages:    # order stored and SHOWN, gates not enforced yet
    - {name: implement, role: subagent, gate: required}
    - {name: review, role: reviewer, gate: optional}
acceptance: {prompt: "...", expect: non-empty}   # one smoke prompt through the lineup, halo doctor --teams
```

**Validation** (`halo teams validate [name]`, `halo doctor --agents`):
every `agent` names a bio that actually exists; exactly one `agents[]`
entry has `role: main`; every `as` alias is unique; every `routing`
value names a known role or alias.

## Resolution -- how a template becomes a real role table or org

`teams_yaml.resolve_role_table(template)` walks `agents:` and, for each
entry, resolves its bio and computes the effective model: **this
entry's own `models` override → the bio's own `models.preference` →
the bio's own `models.fallback`** (the roadmap's own precedence order,
minus a CLI-flag tier that belongs to the caller, same as every other
role source already works). The result key is the entry's `as` alias
when it has one, else its bare `role` -- `roles.py`'s own role table,
completely unchanged; `roles.auto_fill_options()` lists every installed
team template alongside the three built-in presets and `halo gym
propose`, so the Roles step's Auto tab and `/roles` show one.

`teams_yaml.resolve_org(template)` does the same for an `org:` section,
producing an `orgs.py`-shaped `{"positions": [{"title", "model",
"reports", "instructions"}]}` dict -- `delegates_to` becomes `orgs.py`'s
own `reports` field; the EXISTING `OrgEditor`/`OrgsStep` open and apply
it with no changes of their own.

An agent with no resolvable model anywhere is left OUT of the result
(never a crash, never a placeholder), reported as a plain-English note.

## The flagship example: `halo-dev-cycle`

`halo_harness/templates/teams/halo-dev-cycle.yaml` is this project's OWN
development cycle (`plans/CYCLE.md`), as a team template: seven
assignments (`orchestrator` as `boss`/main, `implementer` as `worker`,
`researcher` x2, `verifier`, `reviewer` x3, `release-manager`,
`watchdog`), full `delegation`/`routing`/`budget`/`escalation`/
`context`/`permissions`/`pipeline`/`acceptance` sections, with one
matching agent bio per name under `halo_harness/templates/agents/`. `halo
teams show halo-dev-cycle` prints the resolved role table; `halo doctor
--agents` runs every one of those seven bios' own acceptance checks.

## CLI

```
halo agents list                           every reachable bio name
halo agents show <name>                    resolved identity + every section
halo agents validate [name]                shape-check one bio, or every one (exit 1 on a problem)
halo agents new <name> [--from BIO] [--project]
halo agents edit <name>                     $VISUAL/$EDITOR on the raw YAML
halo agents export <name> [file] [--claude-md]     plain YAML, or .claude/agents/<name>.md frontmatter
halo agents import <file> | --claude-md <name>     a YAML file, or a discovered .claude/agents/*.md

halo teams list                            every reachable team template name
halo teams show <name>                      the lineup, the resolved role table, any org
halo teams validate [name]                  shape-and-reference-check (exit 1 on a problem)
halo teams new <name> [--from TEMPLATE] [--project]
halo teams use <name>                       sets the ACTIVE team (`team` in config.json); refuses an invalid one
halo teams export <name> [file]
halo teams import <file>
```

## TUI: `/agents`, `/teams`, the Auto tab, autocomplete

`/agents` lists the built-in/`.claude/agents` sub-agent DEFINITIONS (an
unrelated, pre-existing concept -- see `docs/SUBAGENTS.md`) in its first
section, then every agent BIO in a second section; `/teams` lists every
team template, marking the active one.

The Roles step's own **Auto** tab (`docs/ROLES.md`) and `/roles edit`
list each installed team template by name, with ONE line per resolved
role (`roles.auto_fill_options()`) -- picking one and applying it (`ctrl
+a`) fills the role table exactly like a built-in preset does, through
`resolve_role_table` above. The model pick list and autocomplete from
`docs/ROLES.md`'s "Enumeration after the keys step" section still apply
unchanged when hand-editing a BIO's own `models.preference` (`halo
agents edit <name>`, or a future dedicated bio-models picker).

**Known, deliberate scope limit this round**: the role/org editors
(`RolesEditor`/`OrgEditor`) still assign a bare MODEL ref per role/
position, same as before this round -- they do not yet have a
dedicated "assign an agent bio, with autocomplete over bio names, add/
remove/duplicate an `agents:` entry" grid of their own. Building and
editing a team template's own `agents:` list happens through the CLI
(`halo teams new/edit` -- hand-editing the YAML is the point) or the
Auto tab's whole-template apply; a richer in-editor assignment grid is
left as explicit follow-up work, not silently dropped.

## `halo doctor --agents`

Validates every agent bio's shape and the ACTIVE team template (`team`
in config.json -- every agent it references must exist), then runs each
bio's own `acceptance` block against a REAL one-shot model call (`halo
-p <prompt> --model <ref> --max-turns 1`, reusing the already-proven
print-mode path rather than a second direct-provider pipeline) and
checks the reply against `expect`. `--mock` (tests only) never calls a
real model.

## Migration from the legacy role table

The first time a wizard save sees a real, non-empty legacy role table
(`roles.py`'s own `config.json` `roles.*` entries -- no files behind
them) and no "migrated" team template exists yet, it builds one agent
bio per DISTINCT model the table names (`migrated-<model-slug>`, just
`models.preference` pinned) plus a bio for the session's own current
default model (there is no legacy "main" role -- `config.json`'s plain
`model` key always WAS that), and saves them all as one team template
named `migrated` -- a fully file-backed equivalent of the table that
existed before, announced in one line in the wizard's own Summary step.
Never runs again once `migrated` exists (`teams_yaml.migrate_legacy_
role_table`).

## The `.claude/agents/*.md` frontmatter bridge

`halo agents export <name> --claude-md` / `halo agents import <name>
--claude-md` convert between a bio and Claude Code's own `.claude/
agents/*.md` frontmatter (`config/agents_md.py::AgentSpec`) -- a LOSSY
bridge both ways; only these fields are mapped:

| Bio field | `.claude/agents/*.md` frontmatter field |
|---|---|
| `name`, `description` | `name`, `description` |
| `models.preference` | `model` |
| `models.effort` | `effort` |
| `tools.allow` | `tools` (comma-joined) |
| `tools.deny` | `disallowedTools` (comma-joined) |
| `tools.permission_mode` | `permission_mode` |
| `tools.mcp_servers` | `mcp_servers` |
| `context.skills` | `skills` (comma-joined) |
| `context.memory` | `memory` |
| `limits.max_iterations` | `max_turns` |
| `context.system_prompt` | the markdown BODY |
| `color` (a bare passthrough field, no section) | `color` |

Everything else a bio can carry (`models.fallback`/`escalation`/
`temperature`/`thinking`/`context_budget`/`lean_prompt`, `tools.rules`/
`limits` (per-tool), `context.files`/`obsidian`, every `limits.*` field
except `max_iterations`, all of `output`/`environment`/`acceptance`,
`kind`, `tags`, `version`, `extends`) has no frontmatter equivalent --
lost on export, absent on import. Import reuses `config/agents_md.
discover_agents` (the SAME precedence-aware loader the live agent
runtime calls), so an imported bio is guaranteed to match what a real
`Agent(subagent_type=name)` call would actually see.

## The wizard: the Agents step and the two editor forms (Halo 2.0.5 round 2)

Three NEW modules, never grown into `tui/dialogs/init_wizard.py` itself
(the house size convention; that file only gained the registration/pane
lines): `tui/dialogs/agent_bio_editor.py` (`AgentBioEditor`, the bio
form), `tui/dialogs/agents_step.py` (`AgentsStep` -- the wizard step --
and `AgentsListScreen`, the standalone counterpart `/agents`/`halo
agents --form` open), `tui/dialogs/lineup_editor.py` (`LineupEditor` and
`TeamsListScreen`, the same split for lineups). ONE form module each --
the wizard, `/agents`/`/teams`, and `halo agents|teams new|edit --form`
all push the SAME screen class, so a save behaves identically everywhere
it's reached from.

**The Agents step** (`"agents"` in `init_wizard.ALL_STEP_KEYS`, right
before "roles") lists every reachable bio (`agents_step.bio_rows`: name,
scope -- project/user/template --, description, preferred model) with
New, New from..., Edit, Duplicate (a shipped bio copied into user scope
under the SAME name, so it shadows the read-only original -- never
edited in place), Delete, and Import (every `.claude/agents/*.md`
`config/agents_md.discover_agents` finds that isn't already a bio name,
converted in one action, one result line each).

**The bio form** is ONE screen over `agents_yaml.BIO_SECTIONS` --
identity (name, description, tags, kind, extends -- never inherited, see
`resolve_agent_bio`'s own rule) plus a field per section: `models`
(preference/fallback open the SAME `ModelPicker` the roles/org/lineup
pickers use, narrowed by the bio's own needs -- tool-capable rows only
when `tools.allow` is non-empty, local rows only when `environment.
offline` is on, enough context for `models.context_budget`'s own share
-- `ctrl+e` shows every row regardless; `ctrl+g` **Suggest** fills both
from `roles.auto_fill_options()`, falling back to the cheapest row in
the picker's own catalog when every preset/gym/team option comes up
empty, e.g. a bare machine right after install), effort, thinking,
context_budget; `tools` (allow/deny against the harness's real tool
names, mcp_servers, permission_mode, and `rules` -- one settings.json-
grammar line each, rendered as a plain sentence beside it, e.g. "Bash
may not run git push", a parse error shown in place of a bad line);
`context` (files, skills, a memory namespace); `limits` (max_iterations,
`timeout` taking the house duration words -- `20m`/`2h`/`90s`/`1d` --
with the parsed figure shown beside it, `max_budget_usd` with "about N
turn(s) at this model's price" against the picked model's own enumerated
price, concurrency); `output` (handoff, report_to); `environment`
(worktree, offline); `acceptance` (prompt, expect). A right-hand pane
shows the YAML that would be written, live, as you type; every problem
`agents_yaml.validate_agent_bio` (plus the name check) finds appears
there AND beside the field it names, not only on Save -- a bad Save
keeps the form open. Save writes user scope by default, project scope on
a toggle.

**New from...** (and the picker's own "New bio..." -- any role-slot pick
can create a bio inline, see below) opens the form with `extends:` set:
every field whose key the raw file does NOT already define shows
INHERITED (greyed, disabled, the resolved parent value as its
placeholder) behind its own per-field override `Switch` -- flipping one
on makes that ONE key the child's own; only the fields actually flipped
on get written to the child's file ("an agent file carries only
overrides"), matching `resolve_agent_bio`'s own key-by-key merge
EXACTLY (never a coarser per-section toggle). A bio with no `extends` at
all shows no toggles -- every field is simply its own, same as before
this round.

## Two sources for a role slot (Halo 2.0.5 round 2)

Wherever a role is filled -- the roles table, an org position, a
lineup's own assignment -- the model picker (`tui/dialogs/model_picker.
py::ModelPicker`) now carries a source switch, `ctrl+a`, shown in its
own footer: **Models** (the enumerated list, exactly as before) or
**Agents** (every bio, with its description, preferred model, and a
tools-count summary; the same text filter and autocomplete). Picking a
model keeps today's behaviour exactly; picking a bio records the agent
on the slot -- a legacy role-table entry becomes `{"model": <the bio's
own resolved preference>, "agent": <bio name>}` (`roles._normalize_
role_value` now carries `agent` through a save/reload round trip the
same way it already does `escalation`), an org position gets a bare
`agent` key beside its `model`, and a lineup assignment's `agent` field
IS the bio name directly (`teams_yaml`'s own schema always names a bio,
never a bare model -- picking "Models" there auto-creates, or reuses, a
tiny bio pinning just that model via `agents_yaml.ensure_bio_for_model`,
the same `model-<slug>` shape `teams_yaml.migrate_legacy_role_table`'s
own per-model bios already use). "New bio..." sits at the top of the
Agents source and opens the SAME bio form; saving it is treated exactly
like picking that freshly-created bio, with no second pick step needed.
`allow_agent_source=False` (the bio form's own preference/fallback
fields) hides the source switch entirely -- a bio's own model must
resolve to a real model, never another bio.

## The lineup editor (Halo 2.0.5 round 2)

`LineupEditor` replaces the Roles step's legacy-template-only editing
with a Lineup pane shown first (the legacy role-table pane moves to its
own "Legacy roles" pane, reachable by its own toggle button -- never
removed, since a config with no lineup at all still needs it). The
assignments grid (`ctrl+n` add, `ctrl+d` delete, `ctrl+p` pick agent-or-
model for the highlighted row) shows the RESOLVED TRUTH per row
(`lineup_editor.resolved_assignment_line`: agent, preferred model,
fallback, price, context, tools count, a gym score when one exists) and
inline warnings needing no Governor (`lineup_editor.lineup_warnings`): a
bio that doesn't exist, no reachable model for the slot, a fallback on
the SAME gateway prefix as the preference (can't help if that gateway is
down), a duplicate `as` alias, or not-exactly-one `role: main`. Every
OTHER `teams_yaml.TOP_SECTIONS` -- `delegation`/`routing`/`budget`/
`escalation`/`context`/`permissions`/`org`/`pipeline`/`acceptance` -- is
a `Collapsible`, its own one-line meaning as the title, editing that
section as ONE YAML-mapping-body `TextArea` (never a bespoke widget per
field -- round-trips through the same `yaml.safe_load` every other
section of this codebase already uses). A read-only roles-table
projection (`teams_yaml.resolve_role_table`, the SAME function `/roles`'s
Auto tab already calls) sits under the grid -- the lineup is the one
place a role actually gets edited.

At the bottom, the free-text **"How the pieces work together"** field
saves as the template's own `about:` (an identity field like
`description` -- inherited whole by a child that never sets its own,
never merged key-by-key). `ctrl+g` **Draft** fills it from `lineup_
editor.draft_about_text` (one sentence per assignment plus the
delegation/pipeline sections, in the house's own plain voice) -- never
leaves it blank; a "stale" marker appears once the lineup's own
assignments/delegation/pipeline change after the last draft (or edit),
until redrafted or edited again. Save validates through `teams_yaml`'s
own validator, writes `teams/<name>.yaml` (user scope by default,
project on a toggle), and offers to make it the active `team:`
(`_ActivateLineupConfirm`) -- "Use this lineup" in the wizard's own
Lineup pane does both in one step via the new `teams_yaml.apply_team_
template` (writes `roles.*` AND `team:`, the lineup counterpart of
`roles.apply_role_template`). `halo teams show`/`/teams show` print the
`about:` text when the lineup has one.

**The active team's `about:` reaches a member's system context** through
`teams_yaml.member_system_context_addition(agent_name, team_name=None,
...)` -- a NEW, pure, local-file-only function this round builds and
unit-tests: the bio's own `context.files`/`context.system_prompt`, then
(only when `agent_name` is actually assigned inside the active, or
given, team) the team's `about:` text appended under the heading "How
this team works" (the SAME heading `halo teams show` prints above it).
Wiring this into the REAL `agent/subagent.py` child-session builder is
left to the Governor round (2.0.5 round 4) -- same "compose the piece,
enforce it later" boundary every other lineup section in this file
already draws; this round's own job was building and proving the
assembly itself.
