# The wizard interaction model

Read this when you change or add a wizard screen: the ten rules every screen follows.

Halo 2.0.5 round 2c (`plans/ROADMAP.md` "ADDED 2026-10-06 ~10:05": "the
wizard stops being clunky"). Ten rules, followed by every wizard screen --
`halo init`, `halo setup`, `/setup`, `/agents`, `/teams`, and every editor
(`AgentBioEditor`, `LineupEditor`, `OrgEditor`, `RolesEditor`) they open.
Verified against `halo_harness/tui/dialogs/init_wizard.py`, `wizard_ux.py`,
`step_rail.py`, `autocomplete.py`, `setup_mode.py`, and `team_step.py`.

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
3. **Studio** -- coming in 2.1.0.

Everything below is the field-by-field reference; nothing in it changed.

## The ten rules

1. **Highlight is selection** for a one-of choice (default model,
   permission mode, theme, a lineup): the highlighted row IS the chosen
   one, marked with a check (`✓`); Next moves on -- no confirm button.
2. **Enter does the obvious thing** on a highlighted row: open/edit a bio
   or a lineup, pick a picker row, use the highlighted lineup. Space
   toggles an on/off row. Buttons stay for the mouse, but are never the
   only path.
3. **Autocomplete inside a model field**: typing filters the enumerated
   rows in a dropdown under the field; Enter picks, Escape closes the
   dropdown (never the screen underneath it). Ctrl+P still opens the full
   picker, with its price/context/speed columns.
4. **A step rail** across the top of every step (Providers, Local models,
   Default model, Permissions, Theme, Team, Orgs, Summary): the current
   step highlighted, done steps ticked. Ctrl+Left/Ctrl+Right are Back/Next
   from anywhere.
5. **Quick setup by default**: the first screen offers "Quick setup" (a
   provider key, your default model, and which lineup of agents runs your
   work -- the Team step, with "One model for everything" preselected) and
   "Full setup" (every step). Quick is the highlighted default; the Summary
   names the lineup that was applied.
6. **One sentence at the top of each step**: what it decides and the
   current choice -- "Default model: `<ref>`. Enter to change."
7. **Focus lands on the content** (the list, or the first field) the
   instant a screen opens -- never on a button. The focused control and
   the highlighted row look different.
8. **At most two levels deep** (a list, then its editor). Save shows a
   one-line toast; a problem stays inline, next to the field it's about.
   Escape is always Back, and never destructive -- it never writes a
   partial/unsaved edit over a file that already had something in it.
9. **The footer reads the same everywhere**: Enter choose, Space toggle,
   Ctrl+N new, Ctrl+E edit, Del delete, Ctrl+S save, Esc back -- a screen
   that doesn't offer one of these simply doesn't show it.
10. **The Summary has "Change" jumps**: one row per step this run actually
    used, jumping straight back into it.

## The step rail

```
Providers  >  Local models  >  [Default model]  >  Permissions  >  Theme  >  Team  >  Organizations  >  Summary
```

Current step bold+reversed, done steps prefixed with `✓` and dimmed,
steps still ahead plain. `halo init --step <key-or-number>` jumps straight
to one step (`docs/COMMANDS.md`'s own `--step STEP` row); Ctrl+Left/
Ctrl+Right walk it one step at a time from inside any step, including one
with a text field focused (both chords are priority bindings for exactly
this reason).

## Quick setup vs. Full setup

The very first screen of a genuine `halo init` (never a `--step .../
/setup .../halo setup ...` entry, which already knows where it's going):

| Choice | What runs | What it leaves |
|---|---|---|
| **Quick setup** (default, highlighted) | Providers -> Default model -> Team -> Summary | Whatever the Team step applied: the preselected "One model for everything" row leaves the shipped `standard` lineup with roles off (every role, including a spawned sub-agent, resolves to the default model -- see `docs/AGENTS.md`'s "the `default` model reference and the `standard` lineup"); picking a lineup turns roles on. |
| **Full setup** | Every step: Providers, Local models, Default model, Permissions, Theme, Team, Organizations, Linux fixes (Linux only, only when needed), Summary | Whatever each step's own section of this doc/`docs/AGENTS.md`/`docs/ROLES.md`/`docs/ORGS.md` says it writes. |

Nothing is ever permanently closed off by picking Quick: `halo init --step
team` (or `halo setup`/`/setup`) reaches Full setup's own steps any time
afterward.

## The Team step (rule 11)

One screen, titled "Team" (Halo 2.1.0 round B1 rebuilt it; Quick setup now
includes it). Top to bottom:

- **A plain-words header**: "Halo runs one model for everything unless you
  pick a lineup. A lineup gives each job (planning, coding, reviewing,
  research) its own agent and model."
- **A Custom roles switch** (3.0.2.0): off is one model for everything,
  on is a lineup. The switch and the list below are one choice: switching
  on highlights the first lineup (or the active one), switching off
  highlights the first row, and highlighting a lineup turns the switch on.
- **The lineup list.** The FIRST row is always **"One model for
  everything"** -- applying it writes `team: standard` and `roles.enabled:
  false` (the same state Quick setup used to leave silently). Then every
  reachable lineup (shipped, user, project) with its role count, its
  one-line description and a scope badge. The active one carries the check
  mark; a fresh install highlights the first row.
- **A live preview** of the highlighted row (beside the list from 100
  columns up, below it otherwise): a tree `role -> agent -> model` with the
  model's price and context window when the catalog knows them, the
  lineup's `about:` text, any warnings, and one cost line -- "Roughly $X per
  turn at these prices", or "price unknown for `<model>`" when a model has
  no price (never a blank that reads as free). For the first row it is the
  sentence "Halo uses `<default model>` for everything, including the
  sub-agents it spawns on its own, and still asks you questions when it
  needs to." `tui/dialogs/team_preview.py` (`preview_lines`, `cost_hint`)
  builds the same text for the command line.
- **Buttons**: **Use this lineup** (apply now) and **Open Studio (Roles)**,
  which starts Halo Studio in the background, opens your browser on the
  Roles canvas and prints the URL; it keeps running after setup until
  `halo studio --stop`. Editing lineups and bios happens there (3.0.2.0:
  the terminal editors were "too bunched up" and overlapped their labels
  on some terminals; they stay reachable from the keyboard: Enter on a row
  or Ctrl+E customize, Ctrl+N new lineup, Ctrl+A agents).

A plain Next applies whichever row is highlighted (rule 1) and always
writes `roles.enabled` explicitly: off for the first row, on for any
lineup. With roles off the main agent still spawns sub-agents for big
jobs and hands surveys and mechanical steps to cheaper models (the system
prompt and the Agent tool both say so). Keys: Esc back, Ctrl+Left/Ctrl+Right
step. The body scrolls, so every control is reachable at 80x24. The Summary step then names what was
applied: the lineup with one line per resolved role, or "One model for
everything: `<model>`".

`halo init --step team` reaches it directly; `--step agents` and `--step
roles` are kept as plain aliases (so is the pre-existing `/setup roles`/
`halo setup roles`, and the new, equally-spelled `/setup team`/`halo setup
team`) -- all four land on the exact same screen.

## Autocomplete field sites (rule 3)

| Site | Field | Suggests |
|---|---|---|
| Agent bio editor | Preferred / fallback model | The SAME bio-aware, narrowed candidate list Ctrl+P's picker would open (`agent_bio_editor.filter_models_for_bio_with_reason`) |
| Organization editor | "Role or model" | Every enumerated model ref |
| Lineup editor | "Agent or model" | Every reachable agent BIO NAME (this field always names a bio; Ctrl+P's Models source still auto-creates one via `agents_yaml.ensure_bio_for_model`) |
| Role template editor (`/roles edit`) | A quick filter above the role list | Every enumerated model ref, assigned to the role currently highlighted below it |

Typing narrows the dropdown (prefix matches first, then substring, same
ranking `model_picker.autocomplete_suggestions` already used for the org
editor's own plain-text hint); Enter picks the highlighted suggestion;
Escape closes the dropdown without leaving the screen underneath it
unless the dropdown was already closed, in which case Escape does
whatever it always does there (rule 8).

## The chrome every step shares

`tui/dialogs/wizard_ux.py` (the mixin/helper deliverable 2 names):
`mark_checked` (rule 1's check mark), `focus_first` (rule 7), `one_sentence`
(rule 6), `toast` (rule 8's save confirmation), `footer_hint` (rule 9's
sentence, built only from the chords a screen actually offers).
`tui/dialogs/step_rail.py` carries the rail text and the Ctrl+Left/
Ctrl+Right chords; `tui/dialogs/autocomplete.py` carries the dropdown
widget pair. All three are plain, Textual-free-at-the-top-level helper
modules reused by every step and editor named above -- never re-
implemented per screen.

## See also

- `docs/HANDBOOK.md`'s 10-minute walkthrough for the step-by-step flow in
  prose.
- `docs/COMMANDS.md`'s `halo init`/`halo setup` sections for every flag.
- `docs/AGENTS.md`'s own wizard section for the bio form and the lineup
  editor's own fields.
- `docs/ROLES.md` for `roles.enabled`, the `standard` lineup, and the
  role-table resolution chain the Team step's "off" state relies on.
- `docs/ORGS.md` for the Organizations step itself (unchanged by this
  round beyond gaining the rail/one-sentence header).
