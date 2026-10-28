"""halo_harness.tui.widgets.lane_offer -- Halo 3.3.5.0 R0b (d): the one-key
offer under the main-model line (agent/main_model_check.py): `y` or Enter
keeps the model as the coder lane under the orchestrator (the lineup written
and made active, the session moved to the orchestrator); any other key goes
ahead with the model as it is. `on_decide(accepted)` fires exactly once.
"""

from __future__ import annotations

from typing import Callable

from textual.binding import Binding

from halo_harness.tui.widgets.input_sanitize import SafeStatic


class LaneOfferCard(SafeStatic, can_focus=True):
    BINDINGS = [Binding("y,enter", "accept", "Keep it as the coder lane", show=False)]

    def __init__(self, *, line: str, offer: dict, on_decide: Callable) -> None:
        super().__init__("", markup=False, classes="effort-card")
        self.line = line
        self.offer = dict(offer or {})
        self._on_decide = on_decide
        self.done = False
        self.answer = ""
        self._refresh()

    def _refresh(self) -> None:
        o = self.offer
        lines = [self.line,
                 f"  y / Enter: keep it as the coder lane under {o.get('orchestrator')} (lineup '{o.get('lineup')}': "
                 "the coder role on this model, main on the orchestrator)",
                 "  any other key: go ahead anyway with it as the main model"]
        if self.done:
            lines = [self.line, f"  {self.answer}"]
        self.update("\n".join(lines))

    def _finish(self, accepted: bool) -> None:
        if self.done:
            return
        self.done = True
        self.answer = ("keeping it as the coder lane..." if accepted else "going ahead with it as the main model")
        self._refresh()
        self._on_decide(accepted)

    def action_accept(self) -> None:
        self._finish(True)

    def on_key(self, event) -> None:
        if self.done:
            return
        if event.key in ("y", "enter"):
            return  # the binding answers it
        self._finish(False)
        event.stop()
