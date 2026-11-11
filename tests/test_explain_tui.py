"""tests.test_explain_tui -- Halo 3.1.1.0 R1: `/explain` in the TUI (tui/dialogs/explain_card.py), as Textual pilots
(tests/test_start_tui.py until 3.4.0.0 B, when the guided first run and its /start panel left for the first-run pack).

1. `/explain tiers` pushes a card with the tier paragraph; Esc closes it
2. (3.2.2.0 R1) the Summary's checks ending after Finish print nothing
Run: python -m tests.test_explain_tui
"""
from __future__ import annotations

TIER = "full"  # Textual pilots: the full tier

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _host(screen_factory):
    from textual.app import App

    class _Host(App):
        def on_mount(self):
            self.push_screen(screen_factory())
    return _Host()


async def _until(pilot, cond, timeout: float = 60.0) -> bool:
    import time
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        await pilot.pause(0.1)
    return cond()


@test
def test_explain_card_shows_the_paragraph(ctx: Ctx):
    from halo_harness import glossary as G
    from halo_harness.tui.dialogs.explain_card import ExplainCard

    async def drive():
        app = _host(lambda: ExplainCard("tiers"))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            title = str(app.screen.query_one("#explain-title").render())
            body = str(app.screen.query_one("#explain-body").render())
            await pilot.press("escape")
            await pilot.pause()
            return title, body, type(app.screen).__name__
    title, body, after = asyncio.run(drive())
    ctx.check(f"the card: tier and its paragraph, got {title!r}", title == "tier" and " ".join(body.split()) == G.load()["tier"])
    ctx.check(f"Esc closes it, got {after}", after != "ExplainCard")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
