"""halo_harness.tui.dialogs.wizard_ux -- Halo 2.0.5 round 2c (`plans/briefs/
2.0.5/round-2c-wizard-ux.md`), deliverable 2: the one shared mixin/helper
every wizard step screen and list screen uses for rules 1, 2 and 7 of
`docs/WIZARD.md` --

1. Highlight is selection for a one-of choice: the highlighted row IS the
   chosen one, marked with a check; Next moves on, no confirm button.
2. Enter does the obvious thing on a highlighted row (opening an editor is
   each screen's own job -- this module only carries the PICK/MARK half
   that is identical everywhere).
7. Focus lands on the content (the list or the first field) when a screen
   opens, never on a button.

Plain functions, not a deep class hierarchy -- every screen here already
has its own bespoke `compose()`/`on_mount()`, so a function each one calls
at the right point is less invasive than a mixin that assumes a fixed
widget tree (`init_wizard.py`'s own module docstring: these screens
duplicate chrome rather than share a base class across a package boundary
that would otherwise circular-import). Also carries rules 6/8/9's own small
reusable pieces (the one-sentence header, the save toast, the uniform
footer caption) so every screen phrases them identically.
"""

from __future__ import annotations

from typing import Optional

CHECK = "✓ "  # "✓ "


def mark_checked(option_list, selected_id) -> None:
    """Rule 1: puts the check mark on the option whose `id == selected_id`
    and strips it from every other option in `option_list` -- generalized
    from the round 2b `RolesStep._mark_selected` static method (now used
    by every single-choice list in the wizard, not just the lineup pane).
    Safe against a `Text`-renderable prompt (stringifies first) and
    against an empty/`None` `selected_id` (every row simply loses its
    mark)."""
    for i in range(option_list.option_count):
        opt = option_list.get_option_at_index(i)
        text = str(opt.prompt)
        bare = text[len(CHECK):] if text.startswith(CHECK) else text
        marked = f"{CHECK}{bare}" if (selected_id is not None and opt.id == selected_id) else bare
        if marked != text:
            option_list.replace_option_prompt(opt.id, marked)


def focus_first(screen, ids: "list[str]") -> bool:
    """Rule 7: focuses the first widget among `ids` (queried in order)
    that actually exists on `screen` right now -- returns whether
    anything was focused. Never a `Button`: a caller lists its OWN
    content widgets first (an `OptionList`, the first `Input`), so a
    button id accidentally included here would still only be reached if
    every earlier id was absent."""
    for wid in ids:
        try:
            widget = screen.query_one(wid)
        except Exception:
            continue
        widget.focus()
        return True
    return False


def one_sentence(label: str, current: "Optional[str]", *, hint: str = "Enter to change.") -> str:
    """Rule 6: "one sentence at the top of each step: what it decides and
    the current choice" -- the brief's own worked example is literally
    `one_sentence("Default model", ref)`."""
    shown = current if (current and str(current).strip()) else "(not set yet)"
    return f"{label}: {shown}. {hint}"


def toast(widget, text: str, *, clear_after: float = 2.5) -> None:
    """Rule 8: "Save shows a one-line toast" -- `widget` is whatever
    Static a screen already uses for its own hint/status line (never a
    new floating widget of its own, so this works identically wherever a
    screen already has one); clears itself after `clear_after` seconds so
    it never lingers and gets mistaken for a persistent error. A screen
    that unmounts before the timer fires just lets the exception from a
    dead widget pass (`set_timer`'s own callback already runs on the
    event loop, never raising INTO caller code either way)."""
    widget.update(text)
    try:
        widget.set_timer(clear_after, lambda: _clear(widget))
    except Exception:
        pass


def _clear(widget) -> None:
    try:
        widget.update("")
    except Exception:
        pass


# Rule 9: "the footer reads the same on every screen" -- the brief's own
# literal sentence, in order; a screen that doesn't offer one of these
# chords passes `False` for it so the sentence only names what actually
# works here (never a false promise).
def footer_hint(*, choose: bool = True, toggle: bool = False, new: bool = True, edit: bool = False,
                 delete: bool = False, save: bool = True, back: bool = True) -> str:
    parts = []
    if choose:
        parts.append("Enter choose")
    if toggle:
        parts.append("Space toggle")
    if new:
        parts.append("Ctrl+N new")
    if edit:
        parts.append("Ctrl+E edit")
    if delete:
        parts.append("Del delete")
    if save:
        parts.append("Ctrl+S save")
    if back:
        parts.append("Esc back")
    return "  |  ".join(parts)
