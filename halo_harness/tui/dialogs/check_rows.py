"""halo_harness.tui.dialogs.check_rows -- `CheckRows`, an on/off list whose rows
are two lines: a title, then a muted detail line (Halo 3.2.2.0 R2, the wizard
Summary's checks). Textual's SelectionList keeps only a prompt's first line,
so this is an OptionList with its own ticks.

Space or Enter toggles the highlighted row (docs/WIZARD.md rule 2). The same
small surface the Summary reads: `selected` (the ticked ids, in row order),
`select(id)`, `deselect(id)`, `toggle(id)`, `deselect_all()`.
"""

from __future__ import annotations

from textual.binding import Binding
from textual.widgets import OptionList
from textual.widgets.option_list import Option


class CheckRows(OptionList):
    BINDINGS = [Binding("space", "toggle_highlighted", "Toggle", show=False)]

    def __init__(self, rows: "list[tuple[str, str, str, bool]]", **kw) -> None:
        """`rows`: `(id, title, detail, on)` each."""
        self._rows = [(rid, title, detail) for rid, title, detail, _on in rows]
        self._on = {rid for rid, _t, _d, on in rows if on}
        super().__init__(*[Option(self._prompt(rid, t, d), id=rid) for rid, t, d in self._rows], **kw)

    def _prompt(self, rid: str, title: str, detail: str):
        from rich.text import Text
        mark = "[x] " if rid in self._on else "[ ] "
        return Text.assemble((mark, "bold"), (title, "bold"), "\n    ", (detail, "dim"))

    def _redraw(self, rid: str) -> None:
        for r, title, detail in self._rows:
            if r == rid:
                try:
                    self.replace_option_prompt(rid, self._prompt(rid, title, detail))
                except Exception:
                    pass

    @property
    def selected(self) -> "list[str]":
        return [rid for rid, _t, _d in self._rows if rid in self._on]

    def select(self, rid: str) -> None:
        self._on.add(rid)
        self._redraw(rid)

    def deselect(self, rid: str) -> None:
        self._on.discard(rid)
        self._redraw(rid)

    def toggle(self, rid: str) -> None:
        (self.deselect if rid in self._on else self.select)(rid)

    def deselect_all(self) -> None:
        for rid in list(self._on):
            self.deselect(rid)

    def action_toggle_highlighted(self) -> None:
        if self.disabled or self.highlighted is None:
            return
        option = self.get_option_at_index(self.highlighted)
        if option.id:
            self.toggle(option.id)

    def on_option_list_option_selected(self, event) -> None:
        if event.option_list is self:
            event.stop()
            if event.option_id and not self.disabled:
                self.toggle(event.option_id)
