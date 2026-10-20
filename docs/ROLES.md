# Roles

Read this when you point different kinds of work at different models with roles.

Halo 2.0.2 ("roles v2", W7 round 1), carrying forward V2c (H15): a small
vocabulary that lets a team point different kinds of work at different
models -- cheap for exploration, strong for planning/review -- without
editing every agent file by hand, and (new this round) pin a specific
REASONING EFFORT per role too. Verified against `halo_harness/roles.py`,
`config/agents_md.py`, `agent/subagent.py`, `agent/loop.py`,
`tools/agent.py`, `cli.py`, `roles_cli.py`, `completion_cli.py`,
`commands/builtins.py`, `tui/slash.py`, `tui/completion.py`,
`tui/dialogs/roles_editor.py`, and `telemetry.py`. See
[MODELS.md](MODELS.md) for how a model reference itself resolves,
[DATABRICKS.md](DATABRICKS.md)'s work-matrix section for endpoint health (a
separate concern), and that same doc's **End-to-end team workflow** section
for how a shared `team.json`'s own `roles` table gets onto everyone's box
via `halo init --provider databricks`. Round 7 (the init wizard) is
verified against `halo_harness/tui/dialogs/init_wizard.py` and
`setup_cli.py` too.

**Teams (Halo 3.0.8.0):** a team file ([TEAM.md](TEAM.md)) names its members as instances of a lineup's aliases (`lineup` + `role`), can name a lineup tier as a stage's members, and runs the lineup preflight for every member before `halo team run`.

## The 90-second version

Four words, in this order: **bio -> lineup -> role -> session**.

- A **bio** says what an agent IS: its name, its model, its tools, its
  limits. `coder` is a bio; so is `local-small`. (`halo agents`.)
- A **lineup** hands bios to jobs: "planning goes to this bio, coding to that
  one". Six ship with Halo -- `standard`, `balanced`, `quality`,
  `local-first`, `code-review`, `halo-dev-cycle` -- and you can write your
  own. (`halo teams`.)
- A **role** is one job slot the session fills: main, planner, coder,
  reviewer, researcher and so on. A lineup gives every role an agent and a
  model. (`halo roles`.)
- Your **session** runs each job on the model its role names, and the
  sub-agents Halo spawns do the same. With roles off, nothing changes:
  **one model for everything**, the default model you picked.

![How bios, lineups and roles fit together](media/diagrams/agents-model.svg)

Three ways to pick a lineup, all writing the same two config keys (`team`
and `roles.enabled`):

1. **The wizard** -- `halo init` (Quick setup includes the Team step) or
   `halo init --step team`. The first row, "One model for everything", is
   the off state; every other row previews its `role -> agent -> model`
   tree with prices before you apply it.
2. **The command line** -- `halo teams use <name>` points the active
   lineup at one; `halo roles on|off` flips the switch.
3. **Studio** -- `halo studio --mode roles` (or `/roles` in a session):
   the Roles section (3.0.7.0 R2) shows the lineup as cards in tier boxes;
   New, Duplicate, Delete and Apply a lineup, edit a card's slot and every
   section, drag a card into another tier, edit bios with the model picker
   table and **Test this model**, and read every problem with its fix as you
   edit. See [STUDIO-team-roles.md](STUDIO-team-roles.md#what-you-see-roles).
   **Where the model is chosen (3.1.4.0):** click a card (or its model pill)
   and the Inspector's **MODEL** strip says what it runs on and holds the
   model select for that card's own model, saved at once, with **change the
   bio's model** beside it for every card on that bio. The same select is the
   bio form's first field, and the catalog behind it resolves your providers
   the way a session does (the env file, the shell, the settings.json `env`
   chain), so a key a session uses lists its models there too.

**Editing a lineup or a bio happens in Studio (3.1.1.0).** The terminal shows
them read-only and opens Studio on the one you want to change: `halo teams
edit <lineup>` / `halo agents edit <bio>` (`--no-open` prints the URL,
`--yaml` opens `$EDITOR` on the file instead, for a box with no browser),
`halo studio --edit lineup:<name>` / `bio:<name>` / `team`, `/edit <thing>`
in the TUI, `e` in the terminal's lineup and bio views (`/teams view`,
`/agents view`, Enter in `/teams list` and `/agents`), and **Edit in Studio**
(Ctrl+E) in the wizard's Team step. A Studio already running for this home is
reused: its open page switches to the lineup or bio. The field-by-field
mapping (every field the terminal shows and its Studio control) is in
[AGENTS.md](AGENTS.md#editing-bios-and-lineups-studio-is-the-editor-halo-3110).

Everything below is the field-by-field reference.

## Roles on/off is one switch (Halo 2.0.5 round 2b)

`roles.enabled` (default **on**) is the ONE switch, everywhere: `halo
roles on`/`halo roles off` (CLI), `/roles on|off` (TUI/print mode), and a
**"One model for everything"** row at the TOP of the wizard's "Team"
step (Halo 2.1.0 B1 replaced the round-2c "Custom roles: off / on"
switch with it; picking a lineup is the on state) (Halo 2.0.5 round 2c retitled/merged what round 2b calls "Roles and
lineup" below into this one screen -- see "Setting up with the wizard"
further down) -- off hides BOTH panes and shows one sentence, "every
role uses the default model", rather than leaving one pane live while
only the other is hidden (the 2.0.5 round 2 version of this switch only
ever covered the legacy pane). `halo roles` always prints the state as
its own first line --
`roles: on (lineup <name>)`, `roles: on (legacy role table)`, or `roles:
off (standard: every role uses the default model)` -- before the
configured table below it; since 2.1.0 every role line also ends with its
source -- `[lineup <name>]`, `[legacy table]` or `[session default]`.
`halo roles template load <name>` now also
turns roles ON (previously it wrote the role mappings and left `roles.
enabled` exactly as it was, so a freshly loaded table sat inert until a
hand edit of config.json); `halo teams use <name>` ([AGENTS.md](AGENTS.
md)) is the non-overwriting way to just point the active lineup at an
already-matching table, never touching `roles.enabled` or re-applying
anything. See [AGENTS.md](AGENTS.md)'s own "The `default` model
reference and the `standard` lineup" section for what "off" is actually
equivalent to.

## Setting up with the wizard (`roles.enabled`, presets)

Halo 2.0.5 round 2c (`docs/WIZARD.md`, rule 11): the wizard's own step is
now called **Team** (`"team"` in `init_wizard.ALL_STEP_KEYS`; `--step
agents`/`--step roles`, `halo setup roles`, `/setup roles` all still land
there as aliases) and, since Halo 2.1.0 B1, carries a lineup list whose
first row, **"One model for everything"**, is the off state (the exact
same `roles.enabled` config key this whole section describes, always
written explicitly by the step), plus a live preview and an **Agents...**
button
`docs/AGENTS.md`'s own "Halo 2.0.5 round 2c: the Team step" section
covers -- the three-preset picker ("Use this template"/"Edit roles.../
"Skip for now") this section goes on to describe is NO LONGER shown
inside the wizard itself (rule 11's own screen has exactly two panes, no
third "Legacy roles" one); it lives on, unchanged, in the STANDALONE
round-1 form below (`/roles edit <name>`, `halo roles template load`) --
every behaviour described from here down still applies there verbatim.

**`roles.enabled`** (default **on**, the Team step's own switch -- the
round-1 form below has no switch of its own) means every role resolves
to the session model when off -- `resolve_role_table()` returns `{}`
outright, the same shape a session with no role table configured at all
already falls through to -- and `/roles`/`/role` are hidden from
`/help`/tab-completion/the rotating tips (never from `resolve()` itself:
typing either by hand still works, this is a discoverability default,
never a functional gate).

The round-1 form itself (`/roles edit <name>`, `tui/dialogs/roles_editor.
py`) shows three shipped **presets** -- written as
ordinary templates (below) into `~/.halo/roles/` the first time this
screen runs, computed from whatever is actually configured right then,
and never overwritten after that ("copy on first use"):

| Preset | What it sets |
|---|---|
| `balanced` | the cost-aware defaults: the session model for most roles; `researcher`/`small` drop to the cheapest configured model |
| `quality` | the session model everywhere; `judge`/`reviewer` pinned to the strongest configured model (the session's own default at setup time) |
| `local-first` | `small`/`researcher`/`judge` on a local `ol:` model when one is configured (forward-compatible with the 2.0.3 Ollama release -- nothing resolves one yet), else the cheapest configured model |

A preview of the highlighted template's own table is shown; picking one
REPLACES the form's own roles (never merges) through the SAME
`apply_role_template` a `/roles load`/`halo roles template load` would
use -- also pushed straight into a LIVE session's own role table when
this form runs via `/setup roles` inside one, no restart needed.
`ctrl+s` saves to the name this form was opened with; a separate `Save
as template...` action saves a COPY under a new name instead. `ctrl+s` with
the effort prompt still open commits the model just picked (with the effort
typed so far) first; an unrecognized effort is reported and nothing is saved.

## Enumeration after the keys step (2.0.4 round 4)

Owner report: "the available models are not listed when you select edit
a role... there aren't models to pick from and/or autocomplete." Leaving
the wizard's Providers step (Next) now runs ONE live, off-thread
enumeration of every provider `/model` knows (OpenRouter, Anthropic,
Databricks, Hugging Face, OpenAI, Experiential, every configured Ollama
host including a LAN one, and any
registered local server) -- with the credentials just typed into any tab
this run (saved or not) merged over the saved config, never written to
disk by the enumeration itself. A small screen shows one progress line
per provider as it answers ("`OpenRouter (or:): 42 model(s) cached`",
"`Databricks (dbx:): not reachable`", ...); a provider that never answers
is capped at a bounded wait and reported "not reachable" rather than
hanging the step. The merged, grouped list this produces
(`halo_harness.providers.model_enumeration.build_model_rows` -- the exact
same function `Controller.list_models()`/`/model` call, never a second
copy of it) is cached for the rest of this wizard run and reused by the
Team step and the Summary step; leaving the Providers
step again (Back, then Next) re-enumerates.

The round-1 form (`/roles edit <name>`) picks a model for a row through
that SAME merged, grouped list (`ModelPicker`, gym score shown beside a
model when one exists; Halo 2.0.5 round 2c also adds a quick inline
autocomplete filter above the role list itself -- see `docs/WIZARD.md`'s
own autocomplete field table); typing into its filter narrows the list
as you type (prefix and
substring, case-insensitive); typing something that matches nothing in
the list still works on Enter, with a one-line note ("`'foo' is not in
the enumerated list; kept as typed.`") rather than a refusal. Outside
the wizard, `/roles edit` already reads the live session's own
`Controller.list_models()` -- unaffected by any of this.

### The Auto tab

The round-1 form gained a second tab, **Auto**, alongside the roles
table itself: pick one of the three built-in presets above, or -- once
`halo gym` has saved at least one result on this machine -- **"From
`halo gym propose`"**, which uses that data's own per-role composite
score instead of the fixed preset rules. The preview shows one line per
role (the gym-proposed option's own lines are full sentences naming the
score and the raw measurements behind it, e.g. "`small -> ol:qwen3:8b:
composite 0.82 from tool call accuracy 0.90, ...`"). `ctrl+a` (or the
Apply button) fills the roles table from the highlighted option --
REPLACES it, never merges, same rule the template picker already
follows -- switches back to the Roles tab so the result is visible, and
lets you adjust any row by hand before `ctrl+s`. `roles.auto_fill_
options` (`halo_harness/roles.py`) is the one place both this tab and
`/roles` read the preset/gym-proposal list from.

See [AGENTS.md](AGENTS.md) for the separate, additive **team template**
layer (2.0.4 round 4): a team template is a named lineup that assigns an
*agent* (from the agent bio roster) to each role, resolved down through
that agent's own bio to a concrete model -- the Auto tab lists an
installed team template exactly like a built-in preset, resolving its
assignments to a role table the same way.

### Two sources for a role slot (Halo 2.0.5 round 2)

The SAME `ModelPicker` the round-1 form opens now
carries a source switch, `ctrl+a`, in its own
footer: **Models** (the enumerated list above, unchanged) or **Agents**
(every reachable agent bio, with its description, preferred model, and
a tools-count summary -- the same text filter and autocomplete). Picking
a model keeps every behaviour this page already documents, unchanged;
picking a bio records the agent ON the slot too -- the role-table entry
becomes `{"model": <the bio's own resolved preference>, "agent": <bio
name>}` instead of a bare model string (`roles._normalize_role_value`
carries the `agent` key through a save/reload round trip the same way
it already does `escalation`) -- `role_value_parts` still reads just
`model`/`effort` from it, so every EXISTING caller of that function is
completely unaffected. "New bio..." sits at the top of the Agents source:
it writes a starter bio on the role's model, picks it for the role, and
opens Studio's bio form on it (3.1.1.0: Studio is the editor of bios). See
[AGENTS.md](AGENTS.md) for the bio form's fields.

## The ten roles

| Role | Default meaning when unset |
|---|---|
| `orchestrator` | the session's own model (no entry needed to mean this) |
| `planner` | the session's own model, unless configured -- the `Plan` agent's role |
| `coder` | the session's own model, unless configured |
| `reviewer` | the session's own model, unless configured |
| `judge` | the session's own model, unless configured -- adjudicates candidate outputs/verifies a result against acceptance criteria |
| `researcher` | the session's own model, unless configured (see "cost-aware defaults" below) |
| `tester` | the session's own model, unless configured -- runs named suites/live checks and reports |
| `compaction` | the rung right after `compactionModel` (below `compactionModel`, above the session's main model) -- see "Resolution precedence" |
| `small` | the session's own small model, unless configured; used for summaries, titles, `/improve` drafts, and compaction when NEITHER `compactionModel` NOR the `compaction` role is set |
| `subagent_default` | the last rung before the session model, for a sub-agent with NO role at all (not a built-in, no `role:` frontmatter) |

`planner`/`judge`/`tester`/`compaction`/`subagent_default` are new in Halo
2.0.2; everything else carries forward unchanged from V2c. `Plan` moved from
`reviewer` to its own `planner` role this round (it no longer shares a rung
with `Reviewer`).

### Custom role names

Any OTHER name matching `[a-z][a-z0-9_]*` that a `team.json` or a loaded
role TEMPLATE (see below) actually defines a value for is an equally valid
role everywhere a built-in name is: `Agent(role=...)`, `--role`,
frontmatter `role:`, `/role`. `roles.known_role_names()` is the live
"what's valid right now" set (the ten built-ins plus whatever is currently
defined) every one of those validates a name against -- an unknown name
errors with that list.

## A role's VALUE: model, or model + effort

Every role table (config.json, team.json, a template, a `--role`/`/role`
override) holds either a bare model-reference string, or
`{"model": "...", "effort": "..."}`. The effort half is optional; when
present, a sub-agent that resolves its MODEL from that same role also
applies that EFFORT -- through the identical `agent/loop.py` `set_model`/
effort path a normal session uses, resolved via `providers/effort.py` so an
effort level the route doesn't support maps the same way `/effort` would
(shown as `requested (sent as X)`, never silently dropped). Precedence for
the effort half mirrors the model half: a CLI `--role`/`/role` override's
own effort beats the role table's, which beats inheriting the parent's.

## Where the table lives

`~/.halo/config.json`'s own `roles` key (`roles.<name>`, dotted-path, the
same convention `databricks.gateway.<endpoint>` uses) -- read/written with
`halo config get/set roles.<name> ...`, `/role`/`/roles set` (session-only,
see below), or hand-edited. A shared `team.json`'s own `roles` map (see
[DATABRICKS.md](DATABRICKS.md)'s team preset section) is seeded into
config.json exactly once, at `halo init --preset work` time, by the SAME
idempotent idiom `gateway_preference` already uses (`roles.py::
apply_role_preference`): a role the user already configured locally is
never overwritten by the team default. A loaded TEMPLATE instead
OVERWRITES (`roles.py::apply_role_template`) -- see "Role templates" below
for why that's the right behavior for an explicit, named load.

## How an agent gets a role

A built-in agent has a fixed default role:

| Agent | Role | Why |
|---|---|---|
| `general-purpose` | `orchestrator` | the default, heaviest-duty agent -- stays on the session model unless the team pins `roles.orchestrator` |
| `Explore` | `researcher` | fast, read-only, cheap |
| `Researcher` | `researcher` | Explore's tool set + WebSearch, for open-ended research |
| `Plan` | `planner` | strong-model planning (its own role as of 2.0.2) |
| `Reviewer` | `reviewer` | strong-model code review |
| `Coder` | `coder` | implementation work |
| `Judge` | `judge` | adjudication / acceptance-criteria verification |
| `Tester` | `tester` | runs suites/live checks, reports verbatim |

A custom `.claude/agents/*.md` file sets the same thing with a `role:`
frontmatter key (a built-in name above, or any OTHER currently-known custom
name); it needs no `role:` at all if it doesn't want to participate in the
table. `compaction` and `subagent_default` are never a sub-agent's own
`role:` -- they're consulted directly by `agent/loop.py` (see the table
above and "Resolution precedence" below), not through an `AgentSpec`.

## Resolution precedence

Full chain, per sub-agent call (`config/agents_md.py::resolve_agent_model`):

1. An explicit `model=` argument on the `Agent`/`Task` tool call, or `--agent
   NAME --model ...` -- always wins outright, exactly as before roles existed.
2. A `--role NAME=MODEL[:EFFORT]`/`/role`/`Agent(role=...)` override, for
   THIS agent's own role (an `Agent(role=...)` call-time override, else the
   agent's file/built-in default role) -- wins even over the agent's own
   file `model:`. This is deliberate: a freshly-typed, run-only flag is more
   explicit than a shared/managed agent file, so the user gets to trump it
   for one run.
3. The agent's own file `model:` frontmatter, when set.
4. The role table (config.json/team.json/a loaded template, or the
   cost-aware default below) for this agent's own role.
5. `CLAUDE_CODE_SUBAGENT_MODEL` (env) / `settings.subagentModel`.
6. `subagent_default` (new in 2.0.2) -- ONLY for a sub-agent with NO role
   name at all (steps 2 and 4 above never applied). A role-bearing agent
   with nothing configured for its OWN role does NOT fall through to this;
   that still means "the session model", unchanged.
7. The parent/session's own model (unchanged) -- `orchestrator`'s own
   documented default is exactly this outcome, reached by having no entry at
   all rather than a special case.

An agent with NO role at all is affected only by step 6 above (new this
round) and otherwise unchanged from the pre-V2c chain.

**Compaction** is a parallel, separate chain (`agent/loop.py::
_compaction_model_override`, `agent/compact.py::resolve_knobs`): a plain
`compactionModel` key in config.json wins first, then Claude Code's own
settings chain's `compactionModel`, THEN (new in 2.0.2) the `compaction`
role, then the session's own main model.

## `--role NAME=MODEL[:EFFORT]` (CLI)

Repeatable; a later repeat of the same role name wins. Validated once, right
after argument parsing, before either `-p` or the TUI starts building a
session -- a bad `NAME=MODEL` (no `=`, an unrecognized role name, an empty
model) is a clean exit-2 usage error, never a traceback. The `:EFFORT`
suffix is optional and must be one of the harness's own accepted effort
words (`low`/`medium`/`high`/`xhigh`/`max`, same set `--effort` itself
takes) -- anything else is read as part of the model id, so a model ref
that legitimately contains colons (`or:vendor/model`, `dbx:endpoint`,
`ant:fable[1m]`) is never mis-split.
```sh
halo -p --role researcher=or:deepseek/deepseek-v4.1-flash:low \
  "use the Researcher agent to summarize this repo"
```

## `Agent(role=...)` (the tool)

The `Agent`/`Task` tool itself accepts a `role` argument, alongside the
existing `model`: `Agent(subagent_type="general-purpose", role="researcher",
...)` makes THIS ONE call resolve against the `researcher` role's model
(and effort, if that role has one), overriding `general-purpose`'s own
default role (`orchestrator`) for just that call. It works identically for
a custom `.claude/agents/*.md` agent that sets its own `role:` frontmatter
-- the call-time `role=` still overrides it for that one call.

## `/role` and `/roles set` (session-only, TUI and print mode)

```
/role <name> <model> [effort]
/roles set <name> <model> [effort]
```
The same operation under two names -- sets ONE role for THIS session only
(mutates the live session's own role table directly; never persisted --
`/roles save <name>` below is the explicit "keep this" action). `<name>`
must already be a known role (see "Custom role names" above); an unknown
name errors with the list of known ones. In the TUI, both tab-complete:
the role-name argument first (`roles.known_role_names()`), then a model ref
(the same enumerated catalog `/model`'s own picker uses --
`controller.list_models()`), then the effort levels valid for whichever
model was just typed -- ranked prefix-matches-first-then-substring
(`tui/completion.py::filter_items`, reused for all three).

## Role templates: `~/.halo/roles/<name>.json`

```json
{"name": "release-flow", "description": "...", "roles": {"coder": "or:vendor/x", "judge": {"model": "or:vendor/j", "effort": "high"}}}
```
A named, reusable role table, independent of any one project's
config.json. TUI: `/roles templates` (list), `/roles save <name>` (the
CURRENT table), `/roles load <name>` (apply), `/roles new <name>` (empty),
`/roles show <name>`, `/roles edit <name>` (a form: one row per role, Enter
opens the same model picker `/model` uses, then an inline effort prompt;
`ctrl+s` saves, Esc cancels with nothing written -- `tui/dialogs/
roles_editor.py`). CLI: `halo roles template
list|save|load|new|edit|show|export|import` (`edit` opens `$EDITOR`/
`$VISUAL` on the raw file, no form; `export <name> [file]`/`import
<file>` move a template as plain JSON -- `export` writes to `file` or
stdout when omitted, `import` validates the same way any other template
write is, listing every problem, and falls back to the file's own
basename when the JSON has no `"name"` field). Setting
`roles.editor: "external"` in config.json makes the TUI's own `/roles edit`
use the SAME `$EDITOR` flow instead of opening the form.

**Precedence**: CLI `--role`/`/role` (session-only, always wins) > a loaded
template (explicit, overwrites config.json's `roles` key outright) >
team.json (idempotent seed, only fills a gap) > whatever was already in
config.json by hand > the cost-aware defaults below.

## Data-driven roles: `halo gym propose`

```sh
halo gym                 # measure local models on this machine first
halo gym propose
halo gym propose --apply
```

Halo 2.0.3 round 5d: once `halo gym` has measured at least one local model
on this machine (`docs/MODELS.md`'s "The model gym" section), `halo gym
propose` picks the best-scoring LOCAL model for each of `small`,
`researcher`, `judge`, `subagent_default` -- the SAME four roles
`VRAM_AWARE_ROLE_NAMES` already names -- weighting each role's own
measurements by what that role's job leans on most, and respecting the
round 5b VRAM-aware rule on the winner exactly as a live session would.
`main`/`orchestrator` is never touched: propose only ever fills the
supporting roles, same as every other automatic default this page
documents. One plain sentence per role says which model won and why, or
that no local model has a usable score for that role yet. `--apply` saves
the proposal as an ordinary role template -- `~/.halo/roles/gym-proposed.
json` by default, `--name` to choose another -- through the SAME `halo
roles template import` path just above; `halo roles template load
gym-proposed` is the separate, explicit step that makes it the live table
(this command never edits config.json directly). See
[COMMANDS.md](COMMANDS.md)'s `halo gym`/`halo gym propose` entries for
every flag.

## Shell completion

```sh
halo completion bash      # eval "$(halo completion bash)" in ~/.bashrc
halo completion zsh       # eval "$(halo completion zsh)" in ~/.zshrc, or save as `_halo` on $fpath
halo completion powershell  # dot-source from $PROFILE
```
Completes `halo`'s own subcommands, every known role name, and every model
ref already cached under `~/.halo` (`models.json`/`dbx-endpoints.json`,
plain file reads -- no network call of its own; an empty/missing cache just
means fewer model-ref completions offered).

## Cost-aware defaults (documented, never automatic beyond this)

When the role table (config.json's `roles` key, itself already including
anything a team.json/template seeded) is **completely empty** -- no team, no
local override, nothing -- and this session's own model is a Databricks one
(the practical signature of the `work` preset; presets themselves are an
init-time-only choice and are never persisted, so this is the same proxy
`model.py`/`providers.config` already use elsewhere for "acting like
work"), exactly two roles get a built-in default:

| Role | Default |
|---|---|
| `researcher` | `dbx:databricks-deepseek-v4-1-flash` (cheap, for exploration) |
| `small` | `dbx:databricks-deepseek-v4-1-flash` (cheap, for summaries/titles) |

Every other role is deliberately left out of this default -- "the session
model for the rest" is already what an absent entry means, so nothing needs
to be written for them. This is the ONLY place a model is ever picked for a
role without the user, a team.json, or a template asking for it by name --
any role table entry at all, even a single one, turns this off entirely
(`roles.py::resolve_role_table`), and no other code path in the harness ever
invents a role's model on its own.

## `/roles`

Shows the resolved table: model, effort (the plain sent value, or
`requested (sent as X)` when a role's own effort maps to a different one on
its route), endpoint/path type, and price per role, straight off the live
session's own `agent_runtime.role_table`/`.cli_role_overrides` -- the SAME
table a role-bearing `Agent` call actually resolves against, so this never
drifts from real behavior. Includes every built-in role PLUS any custom
name actually defined in the table.
```
Role table (model/effort/endpoint/path type/price per role):
  orchestrator  or:deepseek/deepseek-v4.1-flash  -     openrouter  $0.14/1M in, $0.28/1M out  (session model)
  coder         or:deepseek/deepseek-v4.1-flash  high  openrouter  $0.14/1M in, $0.28/1M out  (session model)
  researcher    dbx:databricks-deepseek-v4-1-flash  -  databricks  mlflow  ? DBU  (role table)
  small         dbx:databricks-deepseek-v4-1-flash  -  databricks  mlflow  ? DBU  (role table)
```

## `stats --roles`

Sub-agent spend (sessions/calls/tokens/cost) per role, summed from every
`Agent`/`Task` call's own rolled-up usage node -- see
[COMMANDS.md](COMMANDS.md)'s `stats` section for the full flag table and
`--json` shape. A rolled-up node with no `role` (every pre-V2c log, and any
role-less agent's own calls) simply doesn't contribute to this table; the
existing `--models`/`--tools` tables are completely unaffected. The row set
is whatever roles actually appear in the scanned logs -- built-in or
custom alike, never limited to a fixed list. Halo 2.0.2: each row also
carries that role's CURRENTLY CONFIGURED model/effort
(`roles.configured_role_table()`, no live session needed) -- `null`/`-`
when nothing is configured for it today, even if it had spend in the
window (it was reconfigured since, or it always meant the session model).
Price is not repeated here (that needs a parent model to fall back to,
which this standalone command has no live session to borrow -- see
`/roles` above for that).

## Tiers (Halo 3.0.7.0)

A lineup can stack its members in tiers: an ordered list under `tiers:`,
each entry a name, the aliases it holds and an optional `max_parallel`.

```yaml
agents:
  - {agent: orchestrator, role: main}
  - {agent: researcher, role: planner}
  - {agent: reviewer, role: reviewer}
  - {agent: implementer, role: subagent, as: worker, instances: 3}
tiers:
  - {name: lead, members: [main]}
  - {name: leads, members: [planner, reviewer], max_parallel: 2}
  - {name: workers, members: [worker], max_parallel: 3}
delegation:
  max_depth: 2      # a three-tier stack is two spawn levels deep
```

**The rule:** a member spawns only into the next tier down. `main` (tier 0)
spawns `planner` or `reviewer`; a lead spawns `worker`; a worker spawns no
lineup member (it does its work itself). A member is named by its alias:
the assignment's `as`, else its `role`.

**What the validator checks** (`halo teams validate`, Studio's Save and its
Problems panel): tier names are unique; every member is an alias in
the lineup; the main agent sits alone in tier 0; an alias sits in at most
one tier; `max_parallel` is a positive whole number.

**The implicit tiers.** An alias no tier names joins an implicit last tier
called `rest`, and a `warning:` line says so (it does not block a save). A
lineup with no `tiers:` has one implicit tier, `all`, holding everyone, and
spawning follows the other sections only: nothing changes for a lineup
written before 3.0.7.0. `extends` merges `tiers` like any other section: a
child that never mentions it inherits the parent's list; a child's own list
replaces it.

**At run time** the check sits right after routing, before the pipeline
gate, and comes back to the spawning model as one line:

```
`main` (tier 0 `lead`) may spawn only into the next tier down (tier 1 `leads`); `worker` is in tier 2
tier `leads` already runs 2 of 2: wait or raise max_parallel
```

`max_parallel` counts the tier's live members across the whole session
tree; a member's slot frees the moment its call ends. A sub-agent spawned
with no lineup alias (a plain `general-purpose` call the routing leaves
alone) is outside the tiers and is not counted. Studio's graph carries the
tiers (`graph.tiers`: name, members, max_parallel, index, implicit and the
card ids in each), and a lineup's saved layout keeps each tier's collapsed
state beside the card positions.

**In Studio** (3.0.7.0 R2): each tier is a labelled column box on the Roles
canvas (tier 0 on the left, the implicit last tier dashed); its strip
collapses or expands it. Drag a card into another box and the alias moves to
that tier's `members` and the lineup saves (`PUT /api/lineup/<name>`); the
main agent stays in tier 0 and nothing else may join it (the drop snaps back
with the rule). The Inspector's Lineup tab edits `tiers` as rows (name,
members, max at once) or as YAML, and the Problems panel lists the tier
lines above plus "three tiers need `delegation.max_depth: 2`".

## Lanes and fallbacks (Halo 2.0.5 round 4)

Roles interact with the Governor's routing layer in two ways:

- **Lanes**: models carry a tier (1 strongest .. 3 cheapest); `roles.lanes`
  maps a role to the weakest tier it may use. The standing rule -- reviewer,
  judge and tester must never resolve to a weaker tier than coder -- is
  enforced by the roles validator (one plain line naming the role to raise)
  and by the team-template loader over a lineup's resolved assignments.
- **Fallbacks**: `roles.<name>.fallbacks` (a list of model refs, in
  config.json) appends to a role's fallback chain after any
  `--fallback-model` entries. A fallback on the same gateway host as the
  primary cannot help -- the gateway throttles per machine -- and
  `halo roles` warns when one is configured.

See [GOVERNOR.md](GOVERNOR.md) for the whole mechanism.
