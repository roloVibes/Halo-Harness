# Agent bios and team templates

Read this when you write or edit an agent bio or a lineup, field by field.

Halo 2.0.4 round 4 (owner: "each role should have a yaml file that can be
editable too"), two layers, approved 2026-10-05/06:

1. **Agent bios** (`halo_harness/agents_yaml.py`) -- one YAML file per
   agent NAME, describing what that agent IS: its models, tools, context,
   limits, output shape, environment, and an acceptance check. A bio
   never names a role.
2. **Team templates** ("lineups", `halo_harness/teams_yaml.py`) -- one
   YAML file per template, ASSIGNING bios to roles, with
   delegation/routing/budget/escalation/pipeline settings around them.
   The active one is `team` in `~/.halo/config.json` (`halo teams use
   <name>`).

A team template is what the Roles step's **Auto** tab, `/roles`, and
`/teams` show as a pickable, resolvable set of roles -- applying one just
fills the EXISTING role table (`docs/ROLES.md`) through one resolution
function, so every other
part of this harness keeps working completely unchanged. When a session
actually RUNS under a team (`team:` in config.json or `--team <name>`),
its other sections are enforced by `teams_runtime.py` (Halo 2.0.5 round 5)
-- see "Team template (\"lineup\") fields" below for what each does.

Verified against `halo_harness/agents_yaml.py`, `agents_md_bridge.py`,
`teams_yaml.py`, `teams_runtime.py`, `agents_schedule.py`,
`agents_doctor.py`, `agents_cli.py`, `teams_cli.py`,
`commands/builtins.py`, `roles.py::auto_fill_options`, and the shipped
files under `halo_harness/templates/agents/` and `halo_harness/templates/
teams/`.

> **Every shipped bio and lineup names an API route** (`or:`, `ol:`,
> `default`). A `cc:`/`cx:` ref left in an older bio or lineup file (the
> routes were removed in 3.1.5.0) gets one line and falls through to the
> session model; Studio's card says the same.

> **Roles off still delegates.** With custom roles off (the default) the
> main agent runs your session model and still spawns sub-agents through
> the Agent tool when a job is big; the system prompt tells it to hand
> surveys, searches, test runs and mechanical edits to a cheaper model
> (`model:` on the call) and keep judgement and the final review for
> itself. A lineup (roles on) replaces that per-call pick with the role
> table. The wizard's Team step is the switch; Studio's Roles mode is
> where lineups and bios are edited.

## The 90-second version

Four words, in this order: **bio -> lineup -> role -> session**.

- A **bio** says what an agent IS: its name, its model, its tools, its
  limits. `coder` is a bio; so is `local-small`. (`halo agents`.)
- A **lineup** hands bios to jobs: "planning goes to this bio, coding to that
  one". Seven ship with Halo -- `auto` (the default), `standard`,
  `balanced`, `quality`, `local-first`, `code-review`, `halo-dev-cycle` --
  and you can write your own. (`halo teams`.)
- A **role** is one job slot the session fills: main, planner, coder,
  reviewer, researcher and so on. A lineup gives every role an agent and a
  model. (`halo roles`.)
- Your **session** runs each job on the model its role names, and the
  sub-agents Halo spawns do the same. Until you pick a lineup the **auto**
  lineup runs (3.1.9.0: a pool whose models are picked for each task,
  [ROLES.md](ROLES.md#the-auto-lineup-halo-3190)); with roles off, **one
  model for everything**, the default model you picked.

![How bios, lineups and roles fit together](media/diagrams/agents-model.svg)

Three ways to pick a lineup, all writing the same two config keys (`team`
and `roles.enabled`):

1. **The wizard** -- `halo init` (Quick setup includes the Team step) or
   `halo init --step team`. The Custom roles switch (3.0.2.0) and the first
   row, "One model for everything", are the off state; every other row
   previews its `role -> agent -> model` tree with prices before you apply
   it, and **Open Studio (Roles)** edits in the browser. With no `team:` set
   the `auto` row is the checked "(default)" one, and Next on it writes
   nothing (3.1.9.0).
2. **The command line** -- `halo teams` shows the active lineup, its tree
   and the others; `halo teams apply <name>` uses one (the same result as
   the wizard); `halo roles on|off` flips the switch.
3. **Studio** -- `halo studio`: the lineup as a graph in your browser; Apply
   there writes the same keys ([STUDIO.md](STUDIO.md)).

Everything below is the field-by-field reference; nothing in it changed.

## Storage and precedence

Both layers use the SAME nearest-wins search (`team_config.
py`'s own project/user split, `config/agents_md.py`'s `.claude/agents`
precedence):

| Tier | Agent bios | Team templates |
|---|---|---|
| Project (nearest) | `.halo/agents/<name>.yaml` | `.halo/teams/<name>.yaml` |
| User | `~/.halo/agents/<name>.yaml` | `~/.halo/teams/<name>.yaml` |
| Pack (read-only, 3.2.0.0) | `<pack>/agents/<name>.yaml`, listed as `<id>--<name>` | `<pack>/teams/<name>.yaml`, listed as `<id>--<name>` |
| Shipped (read-only) | `halo_harness/templates/agents/<name>.yaml` | `halo_harness/templates/teams/<name>.yaml` |

The pack tier (Halo 3.2.0.0, [PACKS.md](PACKS.md)) is one folder per
enabled pack, in run order, read in place: a pack's bio `reviewer` is the
bio `doc-review--reviewer` (`_pack: doc-review`, `_name: reviewer`), valid
under the name rule, so it works as a lineup's `agent:`, a route target, a
memory folder and in `tools.mcp_servers`. Inside the pack, a lineup's
`agent:` and an `extends:` may name the pack's own bios and lineups bare;
Halo qualifies them. A bio or lineup of yours with the same `<id>--<name>`
wins (Studio's Duplicate makes one) and `halo pack doctor` names it; a
disabled pack adds nothing to this search. `halo agents` groups the pack's
bios under "Pack <id> agents:", and `halo agents list` / `halo teams list`
under `pack <id>:` (3.2.0.0 R2), where a name a file of yours shadows says
"shadowed by" your file.

The seven shipped team templates (`auto`, `balanced`, `code-review`,
`halo-dev-cycle`, `local-first`, `quality`, `standard`) are copied into `~/.halo/teams/` the first time each is
missing there (never overwritten after -- the same "copy on first use"
rule `roles.py`'s own three presets already
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
`pipeline`/`acceptance`) merges the same way; `agents:` (the
lineup itself) does NOT merge -- a child that defines its own
`agents:`/`roles:` replaces the parent's lineup outright.

## Agent bio fields

```yaml
name: coder-local            # identity -- usually matches the filename
description: Implements a brief using a local model.
version: "1.0"
tags: [subagent, local]
kind: subagent                # main | subagent | researcher | judge | reviewer | custom | media | planner | coder | writer | ops
extends: coder                 # optional -- another bio to inherit from

models:
  preference: ol:qwen3-coder:30b  # a model ref, `default` (the session's model) or `auto` (picked at spawn)
  needs: []                       # with `auto`: what the pick must have -- vision | audio | video | pdf | reasoning | tools | long-context
  fallback: or:deepseek/deepseek-v4.1-flash
  escalation: or:anthropic/claude-opus-5.5   # the roles.py-style escalation target
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
  prompt_notes: "Run the tests before you release a unit."   # 3.0.9.0: added after the prompt (the coach's Apply fills it)
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
  secrets:                       # 3.1.8.0 R5: read at spawn by `secrets.broker` into the worker's env only
    - {env: OPENROUTER_API_KEY, ref: "op://Engineering/OpenRouter/credential"}
  pass_to_tools: []              # broker keys its tool children (Bash, MCP) may see too

acceptance:
  prompt: "Reply with exactly one word: ok"
  expect: ok                     # a substring to match, or the sentinel "non-empty"

isolation: container             # 3.1.8.0 R5: container | user, or {mode, image, network, mounts, env | user, group}
secrets: {broker: 1password}     # 3.1.8.0 R5: 1password | env, account?
```

Halo 3.1.8.0 R5 adds three opt-ins to a bio ([ISOLATION.md](ISOLATION.md)):
`tools.capabilities` (`[read, edit, bash, web, agent, mcp:<server>, media,
recall]`: the agent is built with only those tools; `tools.allow`/`deny`
still apply inside the list), `isolation` (its Orchestra workers run in a
container or as a scoped user; a bio's wins over its lineup's) and
`secrets` with `environment.secrets` (the refs its workers' environment is
fed from at spawn; `environment.pass_to_tools` names the keys its tool
children may see). `isolation` and `secrets` inherit through `extends:`
like a section.

`halo doctor --agents` validates every bio's shape, then runs each one's
own `acceptance.prompt` through a real one-shot model call (`halo -p
<prompt> --model <ref>`) and checks the reply against `expect`.

### `hooks`, `schedule`, `triggers` (Halo 2.0.5 round 5 -- no longer deferred)

```yaml
hooks:                          # Claude Code's own hook shape, run by the
  pre_tool:                     # existing hook runner with HALO_AGENT=<name>
    - {command: "./check.sh", match: Bash, timeout: 30}
  post_tool: [{command: "echo done"}]
  on_start: ["echo starting"]   # a bare string is a one-command shorthand
  on_finish: [{command: "./teardown.sh"}]
schedule:                       # exactly one of cron / every, plus a prompt
  every: 30m                    # ...or cron: "*/5 * * * *"
  prompt: "Check the build and report one line."
  model: or:vendor/cheap-model  # optional; the bio's preference otherwise
triggers:                       # one shot per session, fired on the event
  - {on: file_change, paths: [src/]}
  - {on: event, name: turn_done}
  - {on: message, from: worker}
```

A bio's `hooks` run wherever that bio runs: a member child maps `pre_tool`
/`post_tool` onto PreToolUse/PostToolUse and `on_start`/`on_finish` onto
SubagentStart/SubagentStop; the MAIN assignment's bio gets SessionStart/
SessionEnd instead. `HALO_AGENT` carries the agent's name into every hook
command's environment, and hook output reaches the transcript exactly the
way a settings hook's already does. A template assignment may override the
bio's hooks per key (`hooks:` inside an `agents:` entry).

`schedule`/`triggers` arm when a session that loaded the agent's team is
ALIVE (`team:` in config.json or `--team`), fire the agent as a background
job through the existing job surfaces, and disarm when that session closes
-- never a system service. `halo agents schedule list|run <name>` and
`/agents schedule` show what is armed and each schedule's next fire time.

Halo 3.1.8.0 R1: the supervisor (`halo supervise`, [SUPERVISE.md](SUPERVISE.md))
keeps every lineup's schedules and triggers armed while it runs, so they no
longer need a session open at all. Its store entries are marked `owner:
supervisor`; a session that loads a lineup the supervisor already owns does
not arm it a second time, so nothing double-fires.

## Asking for a model by capability (Halo 3.2.0.0 R2)

`models.capabilities: [long-context, tools]` asks for what the model must do
instead of naming one: each time the bio resolves it runs on the best
catalog model carrying every tag (a model of the family a bare
`models.preference` names first, e.g. `claude-sonnet`), and on your
`default` model when none does (`halo pack doctor`, `halo pack inspect` and
the card in Studio say so). A full model ref in `models.preference` (`or:`,
`ant:` ...) pins the bio instead. The tags: `long-context`, `vision`,
`audio`, `video`, `files`, `image-out`, `tools`, `local`, and since 3.2.1.0
`reasoning`, `open-weights`, `audio-out` (`halo_harness/packs/bio_models.py`;
[PACKS.md](PACKS.md) "A pack's bios" says what each one reads). A pack's bios ask this way and never
name a provider ([PACKS.md](PACKS.md) "A pack's bios", where `tools.needs`
and the pack bio's memory namespace are too). A bio Studio cloned from a
pack carries `from_pack: <id>@<version>`, which changes nothing at run time.

## The `default` model reference and the `standard` lineup (Halo 2.0.5 round 2b)

`models.preference`/`models.fallback` may hold the literal string
`default` instead of a real model ref -- `agents_yaml.resolve_agent_bio`
substitutes it, EVERY TIME it resolves that bio, with the session's own
current default model (`~/.halo/config.json`'s plain `model` key, the
one the init wizard's Default model step/`/model`/`halo config set
model ...` all write). Nothing is baked in at save time: change the
default model and the very next resolution of a bio that uses `default`
picks it up, with no file to edit.

Since Halo 3.1.4.0 EVERY shipped bio that names a model says `default`
(`orchestrator`, `reviewer`, `implementer`, `researcher`, `verifier`,
`release-manager`, `watchdog`, `media`) and carries no provider-pinned
fallback: nothing shipped sends a role to a provider you did not set up.
Before, the orchestrator pinned `or:anthropic/claude-fable-5.1`, so a
lineup that put it in the boss slot silently routed the boss through
OpenRouter on a Databricks or local session. Each of those bios keeps a
comment saying which class of model suits the role; pin one there, or per
slot in Studio's Roles Inspector, when you want it.

The shipped bio `default-model` (`halo_harness/templates/agents/
default-model.yaml`) pins `models.preference: default` and nothing else;
the shipped lineup `standard` (`halo_harness/templates/teams/
standard.yaml`) assigns every one of `roles.py`'s own role names to that
SAME bio. Resolving `standard` therefore always produces a role table
where every role equals the session's own default model -- the EXACT
observable behaviour "Roles: off" already has (`roles.resolve_role_
table()` returns `{}` outright, which means the same thing: every role
falls through to the session model). A config with no `team:` and
`roles.enabled: false` and a config with `team: standard` and `roles.
enabled: true` are therefore equivalent in what a session actually
does -- `standard` just makes that default EXPLICIT and inspectable
(`halo teams show standard` prints its own one-sentence description).
Since 3.1.9.0 a fresh install runs the `auto` lineup (no `team:` written;
below); "Roles: off" still runs no lineup, and nothing writes `team:
standard` to config.json on its own -- see [ROLES.md](ROLES.md)'s own
"Roles on/off is one switch" section.

## The `auto` model reference and `models.needs` (Halo 3.1.9.0)

`models.preference: auto` is the other reference literal: unlike `default` it
is NOT substituted when the bio resolves -- the model is picked when the
agent spawns (`halo_harness/models_auto.py`), from the catalog's best-at
index (`halo models analyze`) and what the task needs. `models.needs` lists
what the picked model must state it has: `vision`, `audio`, `video`, `pdf`
(the input modalities), `reasoning`, `tools` (stated tool calls) and
`long-context` (128k tokens or more); the task adds its own (an image, audio,
video or PDF path in it; "plan", "review" or "judge" in the member's name or
its bio's kind ask for reasoning; a task over 100,000 characters asks for
long-context). A lineup card may override `models.needs` like any other
`models` key, and the lineup's `budget.band` (`low`, `mid` the default,
`high`) is what the pick weighs cost against. In the one model order the
pick sits where the role table does: below a call's own `model`, a
`--role` override, an agent file's `model:` and a tier's model, above the
env / settings fallbacks; no candidate (or a pick whose provider has no
credentials here) runs on the spawning session's model, and the one-line
reason says so. `halo doctor --agents` runs an `auto` bio's acceptance on
your default model. The shipped `auto-*` bios are the `auto` lineup's pool;
[ROLES.md](ROLES.md#the-auto-lineup-halo-3190) has the lineup, the band rules
and two worked picks.

Halo 3.1.8.0 R3: `models.preference: measured` is picked at spawn the same
way, with one rule first: among the candidates that carry the needs, the
model with the best measured first-time success here for the bio's kind
(from 3 checked tasks, `halo models --measured`) wins; with nothing measured
for that kind it is the `auto` pick, and the reason says which
([ROLES.md](ROLES.md#measured-a-bio-that-routes-by-what-succeeded-halo-3180),
[OUTCOMES.md](OUTCOMES.md)). A bio's `kind` is also the task kind its
outcomes are recorded under (coder -> code, researcher -> research, ...).

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

Every OTHER top section -- ENFORCED by the live agent loop since Halo
2.0.5 round 5 (`halo_harness/teams_runtime.py`, the deferral's own
due date) whenever a session runs under the team (`team:` in config.json
or `--team <name>`):

```yaml
delegation: {mode: by-skill, max_parallel: 2, max_depth: 1, handoff: structured, forward_text: false}
routing: {implement: worker, review: review, default: boss}     # task kind -> role or alias
budget: {max_budget_usd: 20, max_total_turns: 400, max_wall_time: 3h, agents_may_exceed: false}
escalation: {triggers: [tool_failures, context_overflow], to: or:anthropic/claude-opus-5.5, ask: false, allow_fallbacks: true}
context: {files: [CLAUDE.md], skills: [], memory: {namespace: my-team, writers: [boss]}}
permissions: {mode: auto, rules: [], offline: false}
pipeline:
  stages:    # stages run in order; a required gate must pass first
    - {name: implement, role: subagent, gate: required, acceptance: {prompt: "...", expect: non-empty}}
    - {name: review, role: reviewer, gate: optional}
acceptance: {prompt: "...", expect: non-empty}   # one smoke prompt through the lineup, halo doctor --teams
tiers:       # docs/ROLES.md "Tiers": a member spawns only into the next tier down
  - {name: top, members: [boss]}
  - {name: media, members: [worker], max_parallel: 2, model: or:google/gemini-3-flash,
     trigger: {on: schedule, every: 30m, prompt: "Cut the new clips"}}
```

What each section DOES at runtime:

- **delegation** -- `max_depth` is the session's depth cap, `max_parallel`
  its in-flight spawn cap (the same gate `agents.max_concurrent` sizes,
  per team); `handoff` shapes what a member hands back (`summary` -- the
  final text, `full` -- plus the child's transcript path, `structured` --
  role/status/cost/result lines); `forward_text: true` prepends the
  parent's latest user text to the delegation prompt.
- **routing** -- at spawn time, the first routing key (or a member's
  `use_for` word) appearing in the call's description/prompt picks the
  role/alias; the template's `default` applies otherwise; an explicit
  `Agent(role=...)` always wins.
- **budget** -- `max_budget_usd`/`max_total_turns`/`max_wall_time` count
  the whole tree (root turns + every member's spend/turns); when one is
  exhausted the team STOPS DELEGATING and says so in one line (never a
  judgement of the request). `agents_may_exceed: true` keeps members
  running while still counting.
- **escalation** -- `triggers` (`tool_failures`, `context_overflow`,
  `budget_exhausted`) switch the session to `to`; `ask: true` shows the
  existing approval card first, `ask: false` switches and announces in
  one line.
- **context** -- `files`/`skills` load for every member on top of its
  bio's own context; `memory.namespace` is a shared memory directory
  under `<state>/teams/<name>/memory/` that only `writers` may write.
- **permissions** -- `mode` and `rules` (the settings.json grammar) apply
  to every member on top of the bio's own; `offline: true` keeps a member
  whose model lives on a network host from ever spawning. A member never
  runs in a more permissive mode than the session that spawned it (a
  `mode` above the parent's is lowered to the parent's, and a plan-mode
  parent always spawns plan-mode members). In a folder you have not
  trusted, a project-level template (`.halo/teams/`, including one reached
  through `extends:`) keeps its deny/ask rules but its `mode` and allow
  rules are ignored.
- **reporting** -- each member's completion is a one-line report to main
  (delivered as a user-role notice on the root session's next turn). A
  lineup that still has an `org:` section (removed in 3.1.4.0) loads with
  one warning line, `org: removed in 3.1.4.0, ignored`; the section does
  nothing.
- **pipeline** -- stages run in order; a `required` gate must pass its
  stage's acceptance (the stage's own `acceptance`, else its bio's) before
  the next stage's calls run, an `optional` gate records and continues.
- **tiers** -- `tiers[].name`, `tiers[].members` (aliases; main alone in
  tier 0) and `tiers[].max_parallel` stack the members: a member spawns
  only into the next tier down, `max_parallel` caps a tier's live members.
  3.1.6.0: `tiers[].model` (a model ref, or `default` for the session's) is
  what the tier's members run on unless the card names its own model or
  its bio pins a real one (a `default` bio takes the tier's model);
  `tiers[].trigger` (`{on: schedule|file_change|event|message, cron|every|
  paths|name|from, prompt, model?}`, the bio trigger shapes) starts the
  tier's lead (its first member) as a background job under the lineup with
  `HALO_TIER_FIRED=<tier>`, and that lead may spawn its own tier's other
  members and the next tier down. The full rule is in
  [ROLES.md](ROLES.md#tiers-halo-3070).
- **isolation, secrets, tools** (Halo 3.1.8.0 R5, [ISOLATION.md](ISOLATION.md))
  -- three opt-ins, none set by default: `isolation: container | user` (or
  its mapping) runs the lineup's Orchestra workers in a per-run container or
  as a scoped OS user; `secrets: {broker: 1password | env, account?}` is the
  broker that reads a bio's `environment.secrets` at spawn;
  `tools: {capabilities: [...]}` (also per tier, `tiers[i].tools`, and per
  card, `agents[i].tools`) builds every member with only the tools of those
  capabilities. A bio's own `isolation`/`secrets` win over the lineup's; a
  card's or a tier's list wins over the bio's, which wins over the lineup's.

`halo teams show <name>` prints the enforcement state per section
(enforced / not set / checked by doctor), so a reader never has to guess
which parts are real.

**Validation** (`halo teams validate [name]`, `halo doctor --agents`):
every `agent` names a bio that actually exists; exactly one `agents[]`
entry has `role: main`; every `as` alias is unique; every `routing`
value names a known role or alias.

## Resolution -- how a template becomes a real role table

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
halo agents                                bios grouped by project / user / shipped, with kind and model
halo agents list                           every reachable bio name
halo agents show <name>                    resolved identity + every section (`halo agents <name>` too)
halo agents validate [name]                shape-check one bio, or every one (exit 1 on a problem)
halo agents new <name> [--from BIO] [--project] [--studio]   a starter bio (--studio: then Studio on it)
halo agents edit <name> [--no-open] [--yaml]  Studio's bio form on it (--yaml: $VISUAL/$EDITOR on the file)
halo agents export <name> [file] [--claude-md]     plain YAML, or .claude/agents/<name>.md frontmatter
halo agents import <file> | --claude-md <name>     a YAML file, or a discovered .claude/agents/*.md

halo teams                                 the active lineup, its tree, one line per other lineup
halo teams list                            every reachable team template name
halo teams show <name>                      the lineup, the resolved role table, its enforcement
halo teams preview <name>                   the lineup as the wizard shows it: role -> agent -> model
halo teams apply <name> [--one-model]       use a lineup: writes roles.* and team, turns roles on
                                            (`standard` / --one-model turns roles off); `use` is the same
halo teams diff <a> <b>                     role-by-role comparison (-, +, ~; "No difference" when equal)
halo teams validate [name]                  shape-and-reference-check (exit 1 on a problem)
halo teams new <name> [--from TEMPLATE] [--project] [--studio]
halo teams edit <name> [--no-open] [--yaml]  Studio's lineup inspector on it (--yaml: $EDITOR)
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

A lineup's `agents:` list (add, remove, duplicate a card, pick its bio) is
edited on Studio's Roles canvas and in its Inspector (see "Editing bios and
lineups" below); the terminal shows it (`/teams list`, `/teams view`).

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

## Editing bios and lineups: Studio is the editor (Halo 3.1.1.0)

Studio is the one editor of bios and lineups. The terminal shows them and
opens Studio on the one you want to change; it never edits a field itself.

| From | What it opens |
|---|---|
| `halo studio --edit bio:<name>` | Roles, the Bios panel on that bio's form |
| `halo studio --edit lineup:<name>` | Roles, that lineup open, the Inspector on its Lineup tab |
| `halo studio --edit team` | the Team section |
| `halo agents edit <bio>`, `halo teams edit <lineup>` | the same, for that bio or lineup (a name that does not exist yet gets a starter file first) |
| `halo agents new <bio> --studio`, `halo teams new <lineup> --studio` | the starter file, then Studio on it |
| `/edit bio:<name>`, `/edit lineup:<name>`, `/edit team`, `/edit <name>` | the same from the TUI (a bare name: the bio of that name, else the lineup) |
| `/agents edit <bio>`, `/teams edit <lineup>`, `/agents new`, `/teams new` | the same from the TUI |
| `e` in the terminal's bio view, lineup view and lists | the bio or lineup on screen |
| the wizard's Team step: **Edit in Studio** (Ctrl+E) | the highlighted lineup |

When a Studio already runs for this home (`~/.halo/studio.json`), it is
reused: every Studio page that is open switches to the bio or lineup, and no
new tab opens. With no page open the browser opens the URL; when no browser
can be opened, or with `--no-open`, the URL is printed (and over SSH that is
the way in: forward the port as `halo studio` says). The URL carries the
target, `http://127.0.0.1:<port>/?mode=roles&edit=bio:coder#t=<token>`; see
[STUDIO-shell.md](STUDIO-shell.md#opening-studio-on-a-bio-a-lineup-or-the-team-halo-studio---edit).

On a box with no browser at all, `halo agents edit <bio> --yaml` and
`halo teams edit <lineup> --yaml` open `$VISUAL`/`$EDITOR` on the YAML file
and validate it when the editor exits.

### What the terminal shows

`/agents` (and the wizard's Team step, Ctrl+A) lists every bio with **New**,
**New from...**, **View**, **Edit in Studio** (`e`), **Duplicate**, **Delete**
and **Import**. Enter or View opens the read-only **bio view**
(`tui/dialogs/agent_bio_editor.py`, `AgentBioView`; `/agents view <name>`
too): the identity, then every field of every section with its one plain line
(`halo_harness/field_help.py`), a value the bio inherits through `extends`
marked `(inherited)`, the `tools.rules` lines as plain sentences, the timeout
in plain units, "about N turns" beside the budget, the triggers, and on the
right the whole file as YAML. `e` opens Studio on it; `t` (or **Try it**)
prints the cost line first, then runs the bio's smoke call (its acceptance
prompt) on a worker; Esc closes it. New writes a starter bio (`agent-<hex>`);
New from... writes a child that only `extends` the highlighted bio
(`<name>-child`); both then open Studio on it. Duplicate copies a shipped bio
into user scope under the same name; Import converts every
`.claude/agents/*.md` that is not a bio yet.

`/teams list` lists every lineup with **View**, **Edit in Studio** (`e`),
**New** and **Activate**. View (Enter; `/teams view <name>`; Enter on a
lineup in the wizard's Team step) opens the read-only **lineup view**
(`tui/dialogs/lineup_editor.py`, `LineupView`): one resolved line per
assignment (agent, preferred model, fallback, price, context, tools, a gym
score), the warnings that need no Governor (a missing bio, no model for a
slot, a fallback on the preference's own gateway, a duplicate alias, not
exactly one `role: main`), what each row costs, the role table the lineup
resolves to, the highlighted assignment's fields, every top section's YAML
under its one-line meaning, and the `about:` text (drafted from the lineup,
and marked so, when it has none). `e` opens Studio on it; `t` sends the
one-token probe (`halo models test`) to the highlighted row's model and shows
ok and the latency, or the error, under the costs; **Smoke run (cost first)**
prints every distinct model's cost line, then runs each member's acceptance
prompt.

"New bio..." in a model picker's Agents source (the roles editor) writes a starter bio on the slot's model, picks it for the slot and
opens Studio's bio form on it.

### Every terminal field has its Studio control

Studio's bio form (Roles -> Bios) and the lineup inspector (Roles ->
Inspector: Assignment and Lineup tabs) hold every field the terminal shows,
and each field carries the same help line: Studio reads them from
`GET /api/field-help`, served from `halo_harness/field_help.py`. Each form
keeps its YAML toggle (a lineup section's raw body; the whole bio, for
`hooks` and any key with no field); **Save to project scope** writes the
repo's `.halo/agents/` or `.halo/teams/` instead of `~/.halo`.

| Bio field | Studio's bio form |
|---|---|
| `description`, `kind`, `tags`, `extends` | Description, Kind (a choice), Tags (comma separated), Extends |
| `models.preference` | Preferred model: the model picker table and "Test this model" |
| `models.fallback`, `effort`, `thinking` | Fallback, Effort (low ... xhigh, max), Thinking (choices) |
| `models.context_budget` | Context budget (0-1) |
| `tools.allow`, `tools.deny` | Allow, Deny: chips from the real tool registry (`GET /api/tools`) |
| `tools.mcp_servers`, `permission_mode`, `rules` | MCP servers, Permission mode, Rules (one per line) |
| `context.files`, `skills`, `memory`, `prompt_notes` | Files, Skills, Memory namespace, Prompt notes |
| `limits.max_iterations`, `timeout`, `max_budget_usd`, `concurrency` | Max iterations, Timeout, Max budget (USD), Concurrency |
| `output.handoff`, `report_to` | Hand-back, Report to |
| `environment.worktree`, `offline` | Own git worktree, Offline (checks) |
| `acceptance.prompt`, `expect` | Prompt, Expect |
| `schedule.cron`, `every`, `prompt`, `model` | Cron, Every, Prompt, Model |
| `triggers` | one row per trigger: on (file_change, event, message), its paths / event / role, a prompt |
| `hooks`, any other key | the YAML toggle |

| Lineup field | Studio's lineup inspector |
|---|---|
| an assignment's `role`, `agent`, `as`, `instances`, `use_for`, `models.preference` | Assignment tab: Role, Agent bio, Alias, Instances, Use for, Model override |
| `description`, `about`, `extends` | the Lineup tab's header (also the Assignment tab with no card selected) |
| `delegation`, `routing`, `budget`, `escalation`, `context`, `permissions`, `pipeline`, `acceptance`, `tiers` | the Lineup tab: one block per section, its fields as a form, its YAML toggle |

## Halo 2.0.5 round 2c: the Team step (rebuilt in 2.1.0 round B1)

`plans/ROADMAP.md` "Added 2026-10-06 ~10:15" merged the Agents step and the
Roles-and-lineup step into ONE "Team" step (`tui/dialogs/team_step.py`,
`TeamStep`). Halo 2.1.0 round B1 rebuilt its screen (the "Custom roles: off /
on" switch and the two panes are gone) and put it back into Quick setup:

- a plain-words header, then the **lineup list** -- the first row is always
  **"One model for everything"** (turns roles off; since 3.1.9.0 it clears
  `team:` instead of applying the shipped `standard` lineup), then every reachable lineup from
  `teams_list.team_rows`, the active one marked with a check;
- a **live preview** of the highlighted row (`tui/dialogs/team_preview.py`:
  the `role -> agent -> model` tree with price and context, the lineup's
  `about:` text, `lineup_warnings`, one cost line), beside the list from 100
  columns up and below it otherwise;
- buttons **Use this lineup**, **Edit in Studio** (3.1.1.0: Studio's
  inspector on the highlighted lineup, also Ctrl+E) and **Open Studio
  (Roles)**; Ctrl+N writes a new lineup and opens it in Studio, Ctrl+A lists
  the bios. A **Custom roles** switch above the list mirrors the highlighted
  row: off is the first row, on is a lineup.

A plain Next applies whichever row is highlighted (`TeamStep.commit`) and
writes `roles.enabled` explicitly (off for the first row, on for a lineup);
Enter on a row shows it read-only (`LineupView`; `docs/WIZARD.md` rules 1 and 2).

`STEP_FACTORIES["team"]` is the real registration; `STEP_FACTORIES
["agents"]`/`["roles"]` are plain aliases of the SAME factory (never a
second class) -- `--step agents`/`--step roles`, the pre-existing
`/setup roles`/`halo setup roles`, and the round 2c-added `/setup team`/
`halo setup team` all land on this one screen. `AgentsStep` itself (the
class) no longer exists -- `tui/dialogs/agents_step.py` keeps
`_AgentsListMixin`/`AgentsListScreen`/`bio_rows` and friends, which the
standalone `/agents` dialog and the Team step's **Agents...** button build
on.

## Two sources for a role slot (Halo 2.0.5 round 2)

Wherever a role is filled -- the roles table or a
lineup's own assignment -- the model picker (`tui/dialogs/model_picker.
py::ModelPicker`) now carries a source switch, `ctrl+a`, shown in its
own footer: **Models** (the enumerated list, exactly as before) or
**Agents** (every bio, with its description, preferred model, and a
tools-count summary; the same text filter and autocomplete). Picking a
model keeps today's behaviour exactly; picking a bio records the agent
on the slot -- a legacy role-table entry becomes `{"model": <the bio's
own resolved preference>, "agent": <bio name>}` (`roles._normalize_
role_value` now carries `agent` through a save/reload round trip the
same way it already does `escalation`), and a lineup assignment's `agent` field
IS the bio name directly (`teams_yaml`'s own schema always names a bio,
never a bare model -- picking "Models" there auto-creates, or reuses, a
tiny bio pinning just that model via `agents_yaml.ensure_bio_for_model`,
the same `model-<slug>` shape `teams_yaml.migrate_legacy_role_table`'s
own per-model bios already use). "New bio..." sits at the top of the
Agents source: it writes a starter bio on the slot's model, picks it for
the slot (no second pick step) and opens Studio's bio form on it (3.1.1.0).
`allow_agent_source=False` hides the source switch entirely -- a bio's own
model must resolve to a real model, never another bio.

## The `about:` text and a member's context

The free-text **"How the pieces work together"** field (Studio's lineup
header) saves as the template's own `about:` (an identity field like
`description` -- inherited whole by a child that never sets its own, never
merged key-by-key). `halo teams show`/`/teams show` print the `about:` text
when the lineup has one; the terminal's lineup view drafts one from the
lineup (`lineup_view_text.draft_about_text`: one sentence per assignment plus
the delegation and pipeline sections) when it has none.

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

**Teams (Halo 3.0.8.0):** `halo team` (no s) reads a different file, a project's members, blocks and stages, each member an instance of one of these lineups' aliases; see [TEAM.md](TEAM.md).
