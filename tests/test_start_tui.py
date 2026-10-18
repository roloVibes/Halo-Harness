"""tests.test_start_tui -- Halo 3.1.1.0 R1: `/start` and `/explain` in the TUI
(tui/dialogs/start_panel.py, explain_card.py, tui/slash.py), as Textual pilots.

1. `/start` pushes the start panel; the panel runs the guided start (here on
   the fake model calls in this module's home) and shows the seven steps
   done and the outcome; Esc closes it once it has ended
2. Esc on a running start stops it at its next check; Esc again closes
3. `/explain tiers` pushes a card with the tier paragraph; Esc closes it
4. the wizard's Summary offers "Run the ten-minute start now" (off by default)
Run: python -m tests.test_start_tui
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


def _factory(pause_after: str = ""):
    """A StartRun on the fake in this module's home; `pause_after`: the engine waits 2 s once that step is done
    (so a key press lands while the start still runs)."""
    import time
    from halo_harness.config.paths import bridge_home
    from halo_harness.start.engine import Options, StartRun

    def make(emit):
        def slow(frame):
            emit(frame)
            if frame["key"] == pause_after and frame["state"] == "done":
                time.sleep(2.0)
        return StartRun(Options(yes=True, fake=True, studio=False, state_dir=Path(bridge_home())), emit=slow)
    return make


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
def test_slash_start_and_explain_push_their_screens(ctx: Ctx):
    from halo_harness.tui.slash import handle_slash

    class _App:
        def __init__(self):
            self.pushed, self.notes = [], []

        def push_screen(self, screen, *a, **k):
            self.pushed.append(screen)

        def notify(self, *a, **k):
            self.notes.append(a)
    app = _App()
    asyncio.run(handle_slash(app, "start", ""))
    asyncio.run(handle_slash(app, "explain", "hand-offs"))
    names = [type(s).__name__ for s in app.pushed]
    ctx.check(f"/start -> StartPanel, /explain -> ExplainCard, got {names} {app.notes}", names == ["StartPanel", "ExplainCard"])
    ctx.check(f"the card found hand-off, got {app.pushed[1].title_text!r}", app.pushed[1].title_text == "hand-off")


@test
def test_start_panel_runs_the_seven_steps(ctx: Ctx):
    from halo_harness.tui.dialogs.start_panel import StartPanel

    async def drive():
        app = _host(lambda: StartPanel(_factory()))
        async with app.run_test(size=(150, 46)) as pilot:
            panel = app.screen
            done = await _until(pilot, lambda: panel.summary is not None, 90)
            body = str(panel.query_one("#start-body").render())
            states = {k: f["state"] for k, f in panel.frames.items()}
            await pilot.press("escape")
            await pilot.pause()
            return done, body, states, type(app.screen).__name__, panel.summary
    done, body, states, after, summary = asyncio.run(drive())
    ctx.check(f"the start ended ok, got {summary}", done and summary and summary.get("ok") is True)
    ctx.check(f"seven steps done, got {states}", list(states.values()) == ["done"] * 7 and len(states) == 7)
    ctx.check(f"the body lists them and the outcome, got {body[-400:]!r}", "[ok] 1. The lineup" in body and "[ok] 7. Where to go next" in body
              and "Done: lineup my-halo-dev-cycle" in body)
    ctx.check(f"Esc closes the ended panel, got {after}", after != "StartPanel")


@test
def test_esc_stops_a_running_start(ctx: Ctx):
    from halo_harness.tui.dialogs.start_panel import StartPanel

    async def drive():
        app = _host(lambda: StartPanel(_factory(pause_after="goal")))
        async with app.run_test(size=(150, 46)) as pilot:
            panel = app.screen
            await _until(pilot, lambda: (panel.frames.get("goal") or {}).get("state") == "done", 30)
            await pilot.press("escape")
            stopped = await _until(pilot, lambda: panel.summary is not None, 60)
            still = type(app.screen).__name__
            await pilot.press("escape")
            await pilot.pause()
            return stopped, still, type(app.screen).__name__, panel.summary
    stopped, still, after, summary = asyncio.run(drive())
    ctx.check(f"Esc stopped it, got {summary}", stopped and summary.get("ok") is False and summary.get("stopped_at"))
    ctx.check(f"the panel stays until a second Esc, got {still} then {after}", still == "StartPanel" and after != "StartPanel")


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
def test_wizard_summary_offers_the_start_default_off(ctx: Ctx):
    """The standalone `halo init` Summary (the wizard's last step) has "Run the ten-minute start now", off by
    default; Finish with it on sets `run_start` (init_cli then runs `halo start`); a /setup Summary has no box."""
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState

    async def drive(offer: bool, tick: bool):
        state = WizardState(cwd=Path.cwd(), step_keys=("summary",), no_live=True, offer_start=offer)
        app = InitWizardApp(state)
        async with app.run_test(size=(120, 44)) as pilot:
            await pilot.pause(0.3)
            boxes = list(app.screen.query("#wiz-summary-start"))
            value = boxes[0].value if boxes else None
            if tick and boxes:
                boxes[0].value = True
            await pilot.pause(0.1)
            app.screen.action_do_next()
            await pilot.pause(0.2)
        return len(boxes), value, state.run_start
    ctx.check("halo init's Summary: one box, off", asyncio.run(drive(True, False)) == (1, False, False))
    ctx.check("ticked and Finish: run_start", asyncio.run(drive(True, True)) == (1, False, True))
    ctx.check("a /setup Summary: no box", asyncio.run(drive(False, False)) == (0, None, False))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
