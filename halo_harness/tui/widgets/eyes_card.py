"""halo_harness.tui.widgets.eyes_card -- Halo 3.3.6.0 R6: the offer before the eyes (agent/eyes_offer.py), queued
through the PendingDock like every other card. One line says the model cannot see the image (or that nothing
says it can); the three ways on are a menu, each with what it does, costs and writes:

    Enter / 1 / l   the first one that can run: this turn on the visual lane
    2 / d           a model that sees describes the image into the turn
    3 / s           send the text without it (the image as its path)
    Esc             the text without it

A choice that cannot run here (no visual lane set, no model that sees) shows why and takes no key.
`on_decide({"action": "lane" | "describe" | "send"})` fires once.
"""

from __future__ import annotations

from typing import Callable

from textual.binding import Binding

from halo_harness.tui.widgets.cards import _AnswerCard

KEYS = {"lane": "1", "describe": "2", "send": "3"}


class EyesCard(_AnswerCard, can_focus=True):
    BINDINGS = [
        Binding("enter", "choose_first", "The first", show=False),
        Binding("1,l", "choose('lane')", "Visual lane", show=False),
        Binding("2,d", "choose('describe')", "Describe it", show=False),
        Binding("3,s,escape", "choose('send')", "Text only", show=False),
    ]

    def __init__(self, *, request_id: str, text: str, choices: list, on_decide: Callable) -> None:
        super().__init__("", markup=False, classes="approval-card eyes-card")
        self.request_id = request_id
        self.text = text
        self.choices = [c for c in choices or [] if isinstance(c, dict) and c.get("id") in KEYS]
        self.summary = "Eyes: the model cannot see the image"
        self._on_decide = on_decide
        self.done = False
        self.decision_line = None
        self._refresh()

    def _open(self, cid: str) -> bool:
        return any(c["id"] == cid and not c.get("disabled") for c in self.choices) or cid == "send"

    def menu_lines(self) -> list:
        out = []
        for c in self.choices:
            mark = "  " if c.get("disabled") else f"[{KEYS[c['id']]}]"
            out.append(f"  {mark} {c.get('label')}: {c.get('what')}")
        return out

    def _refresh(self) -> None:
        lines = [f"◌ {self.text}"]
        if not self.done:
            lines += self.menu_lines() + ["  Enter: the first one that can run · Esc: the text without it"]
        self.update("\n".join(lines))

    def _finish(self, action: str) -> None:
        self.done = True
        label = next((c.get("label") for c in self.choices if c["id"] == action), action)
        self.decision_line = f"✓ eyes: {label}"
        self._refresh()
        self._on_decide({"action": action, "instruction": None})

    def action_choose_first(self) -> None:
        if not self.done:
            first = next((c["id"] for c in self.choices if not c.get("disabled")), "send")
            self._finish(first)

    def action_choose(self, action: str) -> None:
        if not self.done and self._open(action):
            self._finish(action)
