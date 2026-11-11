"""halo_harness.tui.dialogs.wizard_ux -- the uniform footer caption the list screens print (Halo 2.0.5 round 2c, rule 9
of the old docs/WIZARD.md). 3.4.0.0 B2: the terminal wizard's step screens left, and with them the pick-and-mark,
focus, header and toast helpers they shared; `/agents`' list screen (agents_step.py) keeps the footer.
"""

from __future__ import annotations


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
