"""halo_harness.tui.dialogs.explain_card -- `/explain <thing>`: the word's
glossary paragraph in a card over the session (Halo 3.1.1.0 R1).

The text is docs/GLOSSARY.md's (halo_harness/glossary.py), the same
`halo explain` prints and Studio's Glossary lists. With no word, or one the
glossary does not have, the card lists the words (and the closest ones).
Esc or Enter closes it.
"""

from __future__ import annotations

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


def card_parts(thing: str) -> "tuple[str, str]":
    """`(title, body)` for `thing` ('' lists every word)."""
    from halo_harness import glossary as G
    words = G.load()
    if not (thing or "").strip():
        return "Glossary", "\n".join(f"{w}: {G.first_sentence(t)}" for w, t in words.items()) + \
            "\n\n/explain <word> shows one paragraph."
    word, close = G.find(thing, words)
    if word is None:
        hint = f"Closest: {', '.join(close)}.\n\n" if close else ""
        return f"No word {thing!r}", hint + "Words: " + ", ".join(words) + "."
    return word, words[word]


class ExplainCard(ModalScreen):
    BINDINGS = [Binding("escape", "close", "Close", show=False), Binding("enter", "close", "Close", show=False)]
    DEFAULT_CSS = """
    ExplainCard { align: center middle; }
    ExplainCard > Vertical { width: 84; max-width: 96%; height: auto; max-height: 90%; border: round $primary;
        background: $surface; padding: 1 2; }
    ExplainCard #explain-body { height: auto; margin-top: 1; }
    """

    def __init__(self, thing: str) -> None:
        super().__init__()
        self.title_text, self.body_text = card_parts(thing)

    def compose(self):
        from rich.text import Text
        with Vertical():
            yield Static(Text(self.title_text), classes="dialog-title", id="explain-title")
            yield Static(Text(self.body_text), id="explain-body")
            yield Static("Esc closes - docs/GLOSSARY.md", classes="dialog-subtitle")

    def action_close(self) -> None:
        self.dismiss(None)
