"""halo_harness.tui.dialogs.listnav -- 1.0.1 hotfix addendum 7: a shared
`Input` subclass for every dialog with an `Input` (filter box) + `OptionList`
(results) pair -- `ModelPicker`, `SessionPicker`, `CommandPalette`, and the
new `init`/`  /model` grouped picker (`halo_harness.tui.dialogs.init_picker`).

Textual's own `Input` binds no key at all for Up/Down/PageUp/PageDown (they
silently do nothing while the Input has focus -- verified: this is exactly
why Up/Down in `/model` did nothing), and binds Home/End to text-cursor
movement, which a one-line filter box has little use for compared to "jump
to the first/last result" here. `NavInput` forwards all six to the sibling
`OptionList` instead, and Enter selects the HIGHLIGHTED row (the same
`OptionSelected` event each dialog's own `on_option_list_option_selected`
already handles) rather than submitting -- falling back to the Input's
ordinary `Submitted` event only when the list has nothing selectable (e.g.
filtered down to zero rows, or a disabled placeholder-only list), so each
dialog's own `on_input_submitted` fallback (first match / raw text) still
runs exactly as before in that case.
"""

from __future__ import annotations

from typing import Optional

from textual import events
from textual.widgets import Input, OptionList

_NAV_ACTIONS = {
    "up": "cursor_up", "down": "cursor_down",
    "pageup": "page_up", "pagedown": "page_down",
    "home": "first", "end": "last",
}


class NavInput(Input):
    """`option_list_id`: the CSS id of the sibling `OptionList` this Input's
    navigation keys should drive (looked up lazily via `self.screen`, so
    construction order between the two widgets never matters).

    C-2 finding 12: `extra_keys` ({key: screen_action_name}, default none)
    is a SECOND, generic forwarding table, alongside the fixed nav-key one
    above, for a per-DIALOG shortcut (`ModelPicker`'s own `u` -> "set a
    role for the highlighted model") that must fire while this Input has
    focus -- which, for any PRINTABLE key, a plain `Binding(..., priority=
    True)` on the screen can never do on its own: `Input.check_consume_
    key` claims every printable character (`character.isprintable()`),
    and Textual's own `Screen._binding_chain` DELETES any key the
    currently-FOCUSED widget claims from every ancestor's bindings map --
    including the screen's and the App's -- before `priority` is even
    consulted (verified against Textual 8.2.8's own `app.py`/`screen.py`).
    Forwarding it here, through the widget's own public `run_action`
    (the same mechanism a real key dispatch would have used), is the only
    way a letter-key shortcut can ever reach the screen while an `Input`
    sibling holds focus; a key NOT in this table still falls through to
    ordinary text entry exactly as before."""

    def __init__(self, *args, option_list_id: str, extra_keys: "Optional[dict]" = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._option_list_id = option_list_id
        self._extra_keys = dict(extra_keys or {})

    def _option_list(self) -> "OptionList | None":
        try:
            return self.screen.query_one(f"#{self._option_list_id}", OptionList)
        except Exception:
            return None

    async def _on_key(self, event: events.Key) -> None:
        option_list = self._option_list()
        if option_list is not None:
            action = _NAV_ACTIONS.get(event.key)
            if action is not None:
                event.stop()
                event.prevent_default()
                getattr(option_list, f"action_{action}")()
                return
            if event.key == "enter" and option_list.option_count and option_list.highlighted is not None:
                highlighted = option_list.get_option_at_index(option_list.highlighted)
                if not highlighted.disabled:
                    event.stop()
                    event.prevent_default()
                    option_list.action_select()
                    return
        extra_action = self._extra_keys.get(event.key)
        if extra_action is not None:
            event.stop()
            event.prevent_default()
            await self.screen.run_action(extra_action)
            return
        await super()._on_key(event)
