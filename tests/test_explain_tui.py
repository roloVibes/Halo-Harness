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


@test
def test_summary_checks_ending_after_finish_print_no_traceback(ctx: Ctx):
    """Setup closes while the Summary's checks run: they end with the app gone (was a NoActiveAppError traceback),
    and the ticked checks still to come do not start (3.2.2.0 R2)."""
    import io
    import logging
    import threading
    from contextlib import redirect_stderr
    from halo_harness import doctor, init_cli
    from halo_harness.studio import models_refresh
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    gate, seen, later = threading.Event(), {}, []

    def slow_checks(*_a, **_k):
        seen["thread"] = threading.current_thread()
        gate.wait(20)
        return ["doctor: ok"], True
    records: list = []
    tap = logging.Handler()
    tap.emit = records.append
    bridge = logging.getLogger("bridge")
    state = WizardState(cwd=Path.cwd(), step_keys=("summary",), no_live=False, offer_start=True, final_model="or:v/m")

    async def drive():
        app = InitWizardApp(state)
        async with app.run_test(size=(120, 44)) as pilot:
            await pilot.pause(0.3)
            app.screen.query_one("#wiz-summary-checks").select("gym")  # tui/dialogs/check_rows.py
            app.screen.action_do_next()  # Finish: doctor, catalog and hello start; doctor waits on the gate
            await _until(pilot, lambda: "thread" in seen, 20)
        gate.set()  # the app has stopped; the doctor ends now (asyncio.run waits for the thread before it returns)
    saved = (doctor.run_checks, models_refresh.refresh, init_cli._run_live_pong)
    doctor.run_checks = slow_checks
    models_refresh.refresh = lambda *a, **k: later.append("catalog") or {"outcomes": []}
    init_cli._run_live_pong = lambda *a, **k: later.append("hello") or (True, "pong")
    err = io.StringIO()
    bridge.addHandler(tap)
    from tests.helpers.custom_lineup import custom_lineup
    try:
        with redirect_stderr(err), custom_lineup():
            asyncio.run(drive())
            if seen.get("thread") is not None:
                seen["thread"].join(20)
    finally:
        gate.set()
        doctor.run_checks, models_refresh.refresh, init_cli._run_live_pong = saved
        bridge.removeHandler(tap)
    ctx.check(f"setup closed while they ran: the checks cancelled (3.4.0.0 B: no start hand-off), got {state.checks_cancel}",
              state.checks_cancel is True)
    ctx.check(f"the checks ended, got {seen}", seen.get("thread") is not None and not seen["thread"].is_alive())
    ctx.check(f"the ones after the doctor did not start, got {later}", later == [])
    raised = [r.getMessage() for r in records if "raised" in r.getMessage()]
    ctx.check(f"no worker error logged, got {raised}", raised == [])
    ctx.check(f"nothing on stderr, got {err.getvalue()[-400:]!r}", "Traceback" not in err.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
