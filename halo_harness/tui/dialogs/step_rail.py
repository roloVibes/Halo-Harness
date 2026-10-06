"""halo_harness.tui.dialogs.step_rail -- Halo 2.0.5 round 2c, deliverable 4:
rule 4 of `docs/WIZARD.md` -- a step rail across the top of every wizard
step (Providers, Local models, Default model, Permissions, Theme, Team,
Orgs, Summary): the current step highlighted, done steps ticked, Ctrl+Left/
Ctrl+Right Back/Next from anywhere. A NEW module (hard constraint:
`init_wizard.py` grows by registration lines only) -- `render_rail` takes
the step keys/titles as plain arguments so this module never imports FROM
`init_wizard.py` (no circularity, same reasoning `agents_step.py`'s own
module docstring already explains for why that file never does either).

`StepRailMixin` adds ONLY the two chords (`Ctrl+Left`/`Ctrl+Right`) --
Textual gathers `BINDINGS` from every class in the MRO, so a plain mixin
with no `__init__` of its own is enough; the concrete screen must define
`action_do_back`/`action_do_next` (every step screen in this package
already does, StepScreen's own pair or a step's own lazy-import copy of
them)."""

from __future__ import annotations

from rich.text import Text
from textual.binding import Binding

CHECK = "✓ "  # "✓ "
RAIL_ID = "wizard-rail"


def render_rail(step_keys: "tuple", index: int, titles: "dict") -> Text:
    """One line, `" >  "`-separated: a done step gets a check mark and
    dims, the current step is bold+reverse, a step still ahead stays
    plain dim -- `str(Text(...))` (what every test's own `_static_text`
    helper reads) is the plain label text with no markup, so a test can
    still substring-match a step's own title without caring about style."""
    text = Text(no_wrap=True, overflow="ellipsis")
    for i, key in enumerate(step_keys):
        if i:
            text.append("  >  ", style="dim")
        label = titles.get(key, key)
        if i < index:
            text.append(f"{CHECK}{label}", style="dim")
        elif i == index:
            text.append(label, style="bold reverse")
        else:
            text.append(label, style="dim")
    return text


#: `Ctrl+Left`/`Ctrl+Right` act exactly like the footer's own Back/Next
#: buttons, from ANY focused widget on the screen (`priority=True`: an
#: `Input`/`TextArea` would otherwise swallow a bare arrow key first,
#: same reasoning every other wizard chord in this codebase already
#: documents) -- "chords ... only in any screen with a text input" (the
#: hard constraint) is satisfied here since every step screen that uses
#: this mixin already has one.
#:
#: A plain tuple, NOT a `BINDINGS` list on `StepRailMixin` itself: see
#: `agents_step.AGENTS_LIST_BINDINGS`'s own comment for why Textual's
#: `DOMNode._merge_bindings` silently ignores `BINDINGS` declared on a
#: mixin with no `DOMNode` ancestor -- every concrete host (`init_wizard.
#: StepScreen`, `team_step.TeamStep`) splices this tuple into its OWN
#: `BINDINGS` instead; the two `action_rail_*` methods below still
#: resolve normally either way (ordinary method lookup, unaffected).
STEP_RAIL_BINDINGS = (
    Binding("ctrl+left", "rail_back", "Back", show=False, priority=True),
    Binding("ctrl+right", "rail_next", "Next", show=False, priority=True),
)


class StepRailMixin:
    """See `STEP_RAIL_BINDINGS` above for why the chords themselves are
    spliced in by each concrete host rather than declared here."""

    def action_rail_back(self) -> None:
        self.action_do_back()

    def action_rail_next(self) -> None:
        self.action_do_next()

    def rail_text(self, step_keys: "tuple", index: int, titles: "dict") -> Text:
        return render_rail(step_keys, index, titles)
