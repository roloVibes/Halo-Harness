"""halo_harness.tui.dialogs.quit_confirm -- the "Quit Halo?" card a second
Ctrl+C press opens (2.0.7 round 7c). The first Ctrl+C copies; two presses
within the window usually mean "I want out", and this card asks before
anything closes. It never quits by itself: Enter reports True (the caller
runs the existing quit path), Esc reports False and the window resets.
"""

from __future__ import annotations

from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

QUIT_CARD_TITLE = "Quit Halo?"
QUIT_CARD_HINT = "Enter quits, Esc stays"


class QuitConfirmScreen(ModalScreen):
    """`dismiss(True)` on Enter, `dismiss(False)` on Esc."""

    BINDINGS = [
        Binding("enter", "confirm", "Quit", show=False, priority=True),
        Binding("escape", "stay", "Stay", show=False, priority=True),
    ]
    DEFAULT_CSS = """
    QuitConfirmScreen { align: center middle; }
    QuitConfirmScreen > Static#quit-confirm-card { width: 44; height: auto; border: round $primary;
        background: $surface; padding: 1 2; }
    """

    def compose(self):
        yield Static(f"{QUIT_CARD_TITLE}\n\n{QUIT_CARD_HINT}", id="quit-confirm-card", markup=False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_stay(self) -> None:
        self.dismiss(False)
