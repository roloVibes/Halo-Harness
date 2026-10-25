"""tests.test_start_tui -- Halo 3.1.1.0 R1: `/start` and `/explain` in the TUI
(tui/dialogs/start_panel.py, explain_card.py, tui/slash.py), as Textual pilots.

1. `/start` pushes the start panel; the panel runs the guided start (here on
   the fake model calls in this module's home) and shows the seven steps
   done and the outcome; Esc closes it once it has ended
2. Esc on a running start stops it at its next check; Esc again closes
3. `/explain tiers` pushes a card with the tier paragraph; Esc closes it
4. (3.2.2.0 R2: the wizard Summary's five check rows are in tests/test_round2c_wizard_ux.py)
5. (3.2.2.0 R1) a raising step is `!!` in the panel; the Summary's checks ending after Finish print nothing
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
def test_a_raising_step_shows_failed_in_the_panel(ctx: Ctx):
    from halo_harness.start import steps_setup
    from halo_harness.tui.dialogs.start_panel import StartPanel

    def boom(_run):
        raise TypeError("boom")

    async def drive():
        app = _host(lambda: StartPanel(_factory()))
        async with app.run_test(size=(150, 46)) as pilot:
            panel = app.screen
            done = await _until(pilot, lambda: panel.summary is not None, 60)
            return done, str(panel.query_one("#start-body").render()), type(app.screen).__name__, panel.summary
    saved = steps_setup.repo
    steps_setup.repo = boom
    try:
        done, body, screen, summary = asyncio.run(drive())
    finally:
        steps_setup.repo = saved
    ctx.check(f"the start ended on the step, got {summary}", done and summary.get("ok") is False
              and summary.get("stopped_at") == "repo" and summary.get("reason") == "TypeError: boom")
    ctx.check(f"the panel: !! on step 2, the line and the log, got {body[-500:]!r}", "[!!] 2. The sample repo" in body
              and "TypeError: boom" in body and "the full error is in " in body and "Stopped at repo: TypeError: boom" in body)
    ctx.check(f"still the panel, no crash screen, got {screen}", screen == "StartPanel")


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
            app.screen.query_one("#wiz-summary-checks").select("start")  # tui/dialogs/check_rows.py
            app.screen.action_do_next()  # Finish: doctor, catalog and hello start; doctor waits on the gate
            await _until(pilot, lambda: "thread" in seen, 20)
        gate.set()  # the app has stopped; the doctor ends now (asyncio.run waits for the thread before it returns)
    saved = (doctor.run_checks, models_refresh.refresh, init_cli._run_live_pong)
    doctor.run_checks = slow_checks
    models_refresh.refresh = lambda *a, **k: later.append("catalog") or {"outcomes": []}
    init_cli._run_live_pong = lambda *a, **k: later.append("hello") or (True, "pong")
    err = io.StringIO()
    bridge.addHandler(tap)
    try:
        with redirect_stderr(err):
            asyncio.run(drive())
            if seen.get("thread") is not None:
                seen["thread"].join(20)
    finally:
        gate.set()
        doctor.run_checks, models_refresh.refresh, init_cli._run_live_pong = saved
        bridge.removeHandler(tap)
    ctx.check(f"setup closed while they ran: no hand-off to the start, got {state.run_start} {state.checks_cancel}",
              state.run_start is True and state.checks_cancel is True)
    ctx.check(f"the checks ended, got {seen}", seen.get("thread") is not None and not seen["thread"].is_alive())
    ctx.check(f"the ones after the doctor did not start, got {later}", later == [])
    raised = [r.getMessage() for r in records if "raised" in r.getMessage()]
    ctx.check(f"no worker error logged, got {raised}", raised == [])
    ctx.check(f"nothing on stderr, got {err.getvalue()[-400:]!r}", "Traceback" not in err.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
