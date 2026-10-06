# The wizard interaction model

Halo 2.0.5 round 2c (`plans/ROADMAP.md` "ADDED 2026-10-06 ~10:05": "the
wizard stops being clunky"). Ten rules, followed by every wizard screen --
`halo init`, `halo setup`, `/setup`, `/agents`, `/teams`, and every editor
(`AgentBioEditor`, `LineupEditor`, `OrgEditor`, `RolesEditor`) they open.
Verified against `halo_harness/tui/dialogs/init_wizard.py`, `wizard_ux.py`,
`step_rail.py`, `autocomplete.py`, `setup_mode.py`, and `team_step.py`.

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
5. **Quick setup by default**: the first screen offers "Quick setup" (keys
   -> default model -> done -- every role, including the sub-agents halo
   spawns on its own, uses that model) and "Full setup" (every step).
   Quick is the highlighted default; the Summary says which one ran.
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
| **Quick setup** (default, highlighted) | Providers -> Default model -> Summary | Every role -- including a spawned sub-agent with none of its own -- resolves to that one model; the observable state is identical to the shipped `standard` lineup with custom roles off (see `docs/AGENTS.md`'s "the `default` model reference and the `standard` lineup"). |
| **Full setup** | Every step: Providers, Local models, Default model, Permissions, Theme, Team, Organizations, Linux fixes (Linux only, only when needed), Summary | Whatever each step's own section of this doc/`docs/AGENTS.md`/`docs/ROLES.md`/`docs/ORGS.md` says it writes. |

Nothing is ever permanently closed off by picking Quick: `halo init --step
team` (or `halo setup`/`/setup`) reaches Full setup's own steps any time
afterward.

## The Team step (rule 11)

One screen, titled "Team", replacing the round-2/2b "Agents" step and
"Roles and lineup" step. A single switch at the top, **"Custom roles: off
/ on"**:

- **Off**: one sentence -- "Halo uses `<default model>` for everything,
  including the sub-agents it spawns on its own, and still asks you
  questions when it needs to." -- and nothing else. Delegation and the
  question card both keep working exactly as described, through the
  shipped `standard` lineup (`docs/AGENTS.md`); this is the SAME
  observable state Quick setup leaves things in.
- **On**: two panes --
  - **Lineups** (left): every reachable team template, the ACTIVE one
    (`team:` in `config.json`) marked with a check -- not the arrow-key
    highlight, which is rule 1's OWN mark on the four pickers above; this
    pane is a management list, like Agents, so Enter edits a highlighted
    lineup (`LineupEditor`) rather than selecting it. Ctrl+N opens a new
    lineup; Ctrl+D duplicates the highlighted one into user scope under
    the SAME name (so it shadows a shipped one -- never a clone under a
    new name). A plain Next (footer) applies whichever lineup is
    highlighted -- writing `roles.*` and `team:` -- the one place this
    step still follows rule 1's "no confirm button needed".
  - **Agents** (right): every reachable agent bio (`agents_step.
    bio_rows`) -- Enter edits, Ctrl+N new, Ctrl+D duplicate (same
    shadow-under-the-same-name rule), Del deletes a project/user-scope
    one.

  Side by side at 120 columns or wider; below that, stacked behind a
  small pane switch ("Lineups" / "Agents" buttons) showing one at a time
  -- Ctrl+N/Ctrl+D/Del always act on whichever pane is actually focused.
  Editing a lineup's own assignment grid picks from those same bios, or
  from the plain model list (`ModelPicker`'s own Agents/Models source
  switch, Ctrl+A).

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
