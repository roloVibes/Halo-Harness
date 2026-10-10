"""halo_harness.tui.dialogs.subscription_notice -- the TUI form of the
cc:/cx: subscription-routes notice (Halo 2.0.7 round 7b). Same words as
the CLI form (`subscription_consent.notice_text`) -- title, the five facts,
both providers' terms, the responsibility sentence, and the acceptance
rule: typing the exact phrase and Enter accepts; Escape or anything else
leaves the routes off.
"""

from __future__ import annotations

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class SubscriptionNoticeScreen(ModalScreen):
    """`dismiss(True)` once the exact acceptance phrase was typed and
    submitted (the caller is responsible for actually calling
    `subscription_consent.record_acceptance()` -- this screen only reports
    what the user typed, it never writes config itself, so a test can
    drive it with no config.json on disk at all); `dismiss(False)` for
    Escape, a blank/empty submit, or any non-matching text."""

    BINDINGS = [Binding("escape", "decline", "Decline", show=False)]
    DEFAULT_CSS = """
    SubscriptionNoticeScreen { align: center middle; }
    SubscriptionNoticeScreen > VerticalScroll { width: 92; max-height: 30; border: round $primary;
        background: $surface; padding: 1 2; }
    SubscriptionNoticeScreen Input { margin-top: 1; }
    """

    def __init__(self, route: "str | None" = None) -> None:
        super().__init__()
        self.route = route

    def compose(self):
        from halo_harness.subscription_consent import (
            ACCEPT_PHRASE, ACCEPTANCE_SENTENCE, NOTICE_PARAGRAPHS, NOTICE_TITLE, PROVIDER_TERMS,
            RESPONSIBILITY_SENTENCE,
        )
        with VerticalScroll():
            yield Static(NOTICE_TITLE, classes="dialog-title")
            for para in NOTICE_PARAGRAPHS:
                yield Static("")
                yield Static(para, markup=False)
            yield Static("")
            for title, url in PROVIDER_TERMS:
                yield Static(f"{title}: {url}", markup=False)
            yield Static("")
            yield Static(RESPONSIBILITY_SENTENCE, markup=False)
            yield Static("")
            yield Static(ACCEPTANCE_SENTENCE, markup=False)
            yield Input(placeholder=ACCEPT_PHRASE, id="subscription-accept-input")

    def on_input_submitted(self, event) -> None:
        from halo_harness.subscription_consent import ACCEPT_PHRASE
        self.dismiss((event.value or "").strip() == ACCEPT_PHRASE)

    def action_decline(self) -> None:
        self.dismiss(False)
