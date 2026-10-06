"""halo_harness.tui.dialogs.autocomplete -- Halo 2.0.5 round 2c, deliverable
3: rule 3 of `docs/WIZARD.md` -- a dropdown under a model field, filtered by
what is typed from the enumerated rows, Enter picks, Escape closes; Ctrl+P
(each host dialog's own existing binding, unchanged) still opens the full
`ModelPicker` with its price/context/speed columns. A NEW module (hard
constraint: `init_wizard.py` and the editors grow by registration/wiring
lines for this, never a re-implementation per field).

Builds on `tui/dialogs/listnav.py::NavInput`, which already forwards
Up/Down/PageUp/PageDown/Home/End and Enter-selects-the-highlighted-row to a
sibling `OptionList` -- this module adds only: `AutocompleteDropdown` (an
`OptionList` subclass that starts hidden via its own `DEFAULT_CSS`, so a
host screen just instantiates it beside its existing `Input`, no per-screen
CSS needed), `AutocompleteInput` (a `NavInput` that also closes an OPEN
dropdown on Escape rather than letting it bubble to the screen's own Back/
Cancel -- a CLOSED dropdown still lets Escape through unchanged, so rule 8
"Escape is always Back" holds one level up), and the two plain functions
every host's own `on_input_changed`/`on_option_list_option_selected` calls:
`refresh_dropdown` (fill it from what's typed) and `apply_pick`/
`hide_dropdown`.
"""

from __future__ import annotations

from typing import Optional

from textual import events
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from halo_harness.tui.dialogs.listnav import NavInput
from halo_harness.tui.dialogs.model_picker import autocomplete_suggestions

DROPDOWN_MAX = 8


class AutocompleteDropdown(OptionList):
    """Starts hidden (`display: none` in its own `DEFAULT_CSS`) -- a host
    screen composes one of these right after the `Input` it belongs to,
    with its OWN id (e.g. `f"{field_id}-ac"`), and never needs to style it
    itself."""
    DEFAULT_CSS = """
    AutocompleteDropdown { display: none; height: auto; max-height: 6; margin-top: 0;
                            border: round $primary-darken-2; background: $surface; }
    """


class AutocompleteInput(NavInput):
    """Same Up/Down/Enter forwarding as `NavInput` (unchanged); Escape
    closes the dropdown INSTEAD of leaving the screen, but only while the
    dropdown is actually showing suggestions -- an already-closed dropdown
    (nothing typed yet, or already picked) lets Escape fall through to
    `super()._on_key`, which for a plain `Input` means the screen's own
    `escape` binding (Back/Cancel) runs exactly as before this widget
    existed."""

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            dropdown = self._option_list()
            if dropdown is not None and dropdown.styles.display != "none" and dropdown.option_count:
                event.stop()
                event.prevent_default()
                hide_dropdown(dropdown)
                return
        await super()._on_key(event)


def refresh_dropdown(dropdown: OptionList, models: "list[dict]", query: str, *, limit: int = DROPDOWN_MAX) -> None:
    """Rule 3: "typing filters the enumerated list in a dropdown under the
    field" -- reuses `model_picker.autocomplete_suggestions` verbatim (the
    SAME prefix-then-substring-then-fuzzy ranking already used by the org
    editor's own suggestion line), so a row shown here is guaranteed
    pickable. An empty query, zero matches, OR a query that's already an
    EXACT match (`apply_pick` just wrote the full ref into the field,
    which re-fires `Input.Changed` -- without this check the dropdown
    would immediately reopen showing the very row just picked) hides the
    dropdown rather than showing a box with nothing left to narrow."""
    suggestions = autocomplete_suggestions(models, query, limit=limit)
    dropdown.clear_options()
    query_stripped = (query or "").strip()
    if not suggestions or query_stripped in suggestions:
        hide_dropdown(dropdown)
        return
    for ref in suggestions:
        dropdown.add_option(Option(ref, id=ref))
    dropdown.action_first()
    dropdown.styles.display = "block"


def hide_dropdown(dropdown: OptionList) -> None:
    dropdown.clear_options()
    dropdown.styles.display = "none"


def apply_pick(input_widget, dropdown: OptionList, ref: "Optional[str]") -> None:
    """The common "Enter picked a suggestion" tail every host site runs:
    writes `ref` into the field, moves the cursor to the end (so typing
    continues naturally rather than inserting mid-word), and closes the
    dropdown. A `None`/falsy `ref` just closes the dropdown with the
    field untouched (the host's own `OptionSelected` handler never fires
    this with one for a real row, but a defensive no-op costs nothing)."""
    hide_dropdown(dropdown)
    if not ref:
        return
    input_widget.value = ref
    input_widget.cursor_position = len(ref)
