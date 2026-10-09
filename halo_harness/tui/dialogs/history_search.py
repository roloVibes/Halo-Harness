"""halo_harness.tui.dialogs.history_search -- Ctrl+R (D-TUI: "HistorySearch
(Ctrl+R)"). `entries` is a plain list of display strings, newest first
(app.py builds it from `history.load_merged_history(cwd)`). Dismisses with
the chosen text, or `None` if cancelled.
"""

from __future__ import annotations

from rich.text import Text
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option


class HistorySearchDialog(ModalScreen):
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]
    DEFAULT_CSS = """
    HistorySearchDialog { align: center middle; }
    HistorySearchDialog > Vertical { width: 90%; height: 70%; border: round $primary;
        background: $surface; padding: 1 2; }
    HistorySearchDialog OptionList { height: 1fr; }
    """

    def __init__(self, entries: "list[str]") -> None:
        super().__init__()
        self.entries = entries

    def compose(self):
        with Vertical():
            yield Static("Search history (Esc to cancel)", classes="dialog-title")
            yield Input(placeholder="Type to filter...", id="history-filter")
            yield OptionList(id="history-list")

    def on_mount(self) -> None:
        self._refresh("")
        self.query_one("#history-filter", Input).focus()

    def _refresh(self, query: str) -> None:
        option_list = self.query_one("#history-list", OptionList)
        option_list.clear_options()
        query_low = query.strip().lower()
        matches = [e for e in self.entries if query_low in e.lower()] if query_low else self.entries
        # vibes/review.md findings 27+28: the option id used to be the
        # PROMPT TEXT itself, so a repeated prompt (the common case --
        # "continue", "go on") raised DuplicateID and crashed the TUI on
        # Ctrl+R; ids are now the filtered list index (kept in sync via
        # `_current_ids`). The label is wrapped in Text() so a prompt
        # containing markup-shaped text (`[/path]`, square brackets in a
        # filename) renders literally instead of raising MarkupError.
        self._current_ids = matches[:200]
        for i, e in enumerate(matches[:200]):
            option_list.add_option(Option(Text(e.replace("\n", " ⏎ ")[:200]), id=str(i)))

    def on_input_changed(self, event: Input.Changed) -> None:
        self._refresh(event.value)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        # finding 27: dismiss with the ENTRY TEXT (what the caller fills
        # the input with), resolved from the index id -- never the raw id.
        try:
            self.dismiss(self._current_ids[int(event.option_id)])
        except (ValueError, IndexError, AttributeError):
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
