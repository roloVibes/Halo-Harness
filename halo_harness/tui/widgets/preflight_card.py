"""halo_harness.tui.widgets.preflight_card -- Halo 3.3.5.0 R4: the preflight
card (agent/preflight.py), queued through the PendingDock like every other
card. One line says the prompt, the window, what Ollama keeps and that it
will be cut; three keys answer it:

    Enter / 1 / c   compact first (the default)
    2 / b           switch to the bigger-window model the card names (when one fits)
    3 / s           send anyway (the payload is ordered so the tail holds the task)
    Esc             compact (the default)

`on_decide({"action": "compact" | "switch" | "send"})` fires once.
"""

from __future__ import annotations

from typing import Callable, Optional

from textual.binding import Binding

from halo_harness.tui.widgets.cards import _AnswerCard


class PreflightCard(_AnswerCard, can_focus=True):
    BINDINGS = [
        Binding("enter,1,c,escape", "choose_compact", "Compact", show=False),
        Binding("2,b", "choose_switch", "Bigger-window model", show=False),
        Binding("3,s", "choose_send", "Send anyway", show=False),
    ]

    def __init__(self, *, request_id: str, text: str, switch_to: Optional[str], on_decide: Callable) -> None:
        super().__init__("", markup=False, classes="approval-card preflight-card")
        self.request_id = request_id
        self.text = text
        self.switch_to = switch_to
        self.summary = "Preflight: the prompt is larger than the window"
        self._on_decide = on_decide
        self.done = False
        self.decision_line: "Optional[str]" = None
        self._refresh()

    def keys_line(self) -> str:
        switch = f"[2] bigger-window model: {self.switch_to}" if self.switch_to else "[2] (no bigger-window model fits here)"
        return f"  [Enter/1] compact   {switch}   [3] send anyway"

    def _refresh(self) -> None:
        lines = [f"⚠ {self.text}"]
        if not self.done:
            lines.append(self.keys_line())
        self.update("\n".join(lines))

    def _finish(self, action: str) -> None:
        self.done = True
        self.decision_line = {"compact": "✓ preflight: compacting first",
                              "switch": f"✓ preflight: switching to {self.switch_to}",
                              "send": "✓ preflight: sent anyway"}[action]
        self._refresh()
        self._on_decide({"action": action, "instruction": None})

    def action_choose_compact(self) -> None:
        if not self.done:
            self._finish("compact")

    def action_choose_switch(self) -> None:
        if not self.done and self.switch_to:
            self._finish("switch")

    def action_choose_send(self) -> None:
        if not self.done:
            self._finish("send")
