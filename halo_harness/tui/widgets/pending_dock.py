"""halo_harness.tui.widgets.pending_dock -- `PendingDock` (Halo 2.0.1 W3a,
"PendingDock (nothing that waits for the user may be off-screen)"):
a container between the `Transcript` and the input row, hidden when empty,
holding exactly the ACTIVE permission/question/plan card. It is a NORMAL
(non-docked) flow child placed right after `Transcript` in `BridgeApp.
compose()` -- `Transcript` itself is `height: 1fr` (grows to fill whatever
space is left), so this dock (height: auto, 0 when hidden) always ends up
sitting directly above the prompt row regardless of how tall the
transcript's own content is, with no absolute positioning of its own
needed. `BridgeApp._pending_queue` (finding 16's own queue, keyed by each
card's `request_id`) is what actually feeds it one card at a time, in
arrival order -- this widget itself knows nothing about the queue, only
how to show/hide exactly one card.
"""

from __future__ import annotations

from textual.binding import Binding
from textual.containers import VerticalScroll


DOCK_MIN_LINES = 12


def dock_room(screen_rows: int) -> int:
    """3.6.0.2 P8: the dock's cap, half the screen and never under DOCK_MIN_LINES. A fixed 12 scrolled a Builder card's
    seventh row (the use row) out of sight even at 200x50 (a text is never cut); half the screen still leaves the
    transcript, the box and the status line their rows, and a 24-row terminal keeps its 12."""
    return max(DOCK_MIN_LINES, int(screen_rows or 0) // 2)


class PendingDock(VerticalScroll):
    """Capped at 12 lines (half the screen on a tall terminal: dock_room) with its own internal scroll (a long diff/
    question list scrolls INSIDE the dock rather than pushing the prompt
    row off-screen); `o` opens the current card's full content in the same
    `PagerScreen` a `ToolCard`'s own `o` already uses -- reached via
    Textual's normal focus-chain binding fallback (the focused CARD's own
    bindings, e.g. PermissionCard's 1/2/3/4, are checked first and always
    win; `o` only ever reaches this dock because none of the three pending
    card types bind it themselves)."""

    BINDINGS = [Binding("o", "open_pager", "Pager", show=False)]

    DEFAULT_CSS = """
    PendingDock {
        height: auto;
        max-height: 12;
        width: 100%;
        background: $surface;
        border-top: solid $warning;
        display: none;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.card = None
        self.display = False
        self._refit = False

    def fit(self, screen_rows: int, *, resized: bool = False) -> None:
        """3.6.0.2 P8 batch 3: the dock's room (dock_room) from the screen's rows -- when a card is shown and again on
        every resize of the terminal (BridgeApp.on_resize), so a card shown on a tall terminal never keeps a room the
        screen no longer has (it overflowed under the box and the status line). After a resize, a card taller than the
        dock keeps its answers in sight (`_keep_answers`, once the dock has its new size)."""
        self.styles.max_height = dock_room(screen_rows)
        self._refit = resized and self.card is not None
        if self._refit:
            self.call_after_refresh(self._keep_answers)

    def on_resize(self, _event) -> None:
        if self._refit:
            self.call_after_refresh(self._keep_answers)

    def _keep_answers(self) -> None:
        """The card's answers in sight when it is taller than the dock: a question card's first unanswered list of
        options, else the card's last line (a permission card's keys line `[1] Yes ... [4] No`)."""
        card = self.card
        if not self._refit or card is None or self.max_scroll_y <= 0:
            return
        self._refit = False  # once per resize: the screen regions read below are stale until the next paint
        lists = getattr(card, "_lists", None) or []
        at = getattr(card, "active_index", 0)
        target = lists[at] if 0 <= at < len(lists) else None
        if target is None:
            self.scroll_end(animate=False, immediate=True)
            return
        # where the answers end, in the dock's own scrolled space (screen rows, read after the dock's new layout)
        view = self.scrollable_content_region
        end = target.region.y - view.y + int(self.scroll_y) + target.outer_size.height
        if end > int(self.scroll_y) + view.height:
            self.scroll_to(y=min(self.max_scroll_y, end - view.height), animate=False, immediate=True)

    async def show_card(self, card) -> None:
        """Mounts `card` as this dock's one and only child and makes the
        dock itself visible. Defensive `remove_children()` first -- the
        queue (`BridgeApp`) only ever calls this once the previous card
        has already been cleared, so there should never actually be one,
        but a stray leftover must never silently stack two cards in here."""
        await self.remove_children()
        self.fit(self.app.size.height)
        self.card = card
        await self.mount(card)
        self.display = True

    async def clear(self) -> None:
        await self.remove_children()
        self.card = None
        self._refit = False
        self.display = False

    def action_open_pager(self) -> None:
        """Parity gap: this used to show only the card's own `summary`/
        `reason` (a PermissionCard) or "(no further detail)" (a
        QuestionCard) -- the full tool input (every question and its
        options, for a QuestionCard) is now shown whenever the card
        carries one (`input_data`, PermissionCard/QuestionCard only; a
        PlanReviewCard has no tool call to show at all, so it keeps the
        old plan_text/reason/summary fallback chain unchanged)."""
        if self.card is None:
            return
        import json
        from halo_harness.tui.widgets.cards import PagerScreen
        title = getattr(self.card, "summary", None) or type(self.card).__name__
        input_data = getattr(self.card, "input_data", None)
        if input_data:
            body = json.dumps(input_data, indent=2, ensure_ascii=False, default=str)
        else:
            # Halo 2.0.2 round D (brief item 2): `ApprovalCard`'s own
            # `text` (the gated position's full result) joins the same
            # fallback chain -- it has no `input_data`/`plan_text`/
            # `reason` of its own (there is no tool call behind an
            # approval gate at all).
            body = (getattr(self.card, "plan_text", None) or getattr(self.card, "reason", None)
                    or getattr(self.card, "text", None) or getattr(self.card, "summary", None)
                    or "(no further detail)")
        self.app.push_screen(PagerScreen(str(title), str(body)))
