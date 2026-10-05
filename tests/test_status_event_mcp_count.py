"""Halo 2.0.3 release fix: a status event without an MCP count must not reset
the status bar to "MCP 0/0". Before this fix `events.status()` filled a
missing count with {"connected": 0, "total": 0}, and the several idle status
events a turn emits without a count zeroed the bar mid-session (the owner
saw "0/6" become "0/0" every session). Now the key is absent when the
producer does not know the count, and the status bar keeps its last value.

Fix pass C-2 extends the exact same "presence means a reading" pattern to
the three `ollama_*` throughput fields (finding 10) and pins `message_end`'s
`saved_usd` actually reaching the real `StatusBar` through `tui/dispatch.py`
(finding 9), not just `StatusBar.apply_status` called directly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


@test
def test_status_event_without_mcp_omits_the_key(ctx: Ctx):
    from halo_harness import events
    ev = events.status(phase="idle", model="or:x/y", turn=3)
    ctx.check("no mcp key when the producer passes none", "mcp" not in ev.data)
    ev2 = events.status(phase="idle", model="or:x/y", turn=3, mcp={"connected": 2, "total": 6})
    ctx.check("mcp key present when given", ev2.data.get("mcp") == {"connected": 2, "total": 6})


@test
def test_status_event_without_ollama_keys_omits_them(ctx: Ctx):
    """C-2 finding 10 pin: the same "presence means a reading" rule as the
    MCP count just above, now for the three `ollama_*` fields -- before
    this fix `events.status()` always defaulted and included them, so
    every PLAIN `events.status(phase=..., model=...)` call (every ordinary
    turn-start/turn-end status `agent/loop.py` emits outside `Session.
    status_event`) wiped the status bar's throughput segment back to
    blank, every single time."""
    from halo_harness import events
    ev = events.status(phase="idle", model="ol:x", turn=3)
    ctx.check("no ollama_tokens_per_second key when the producer never mentions it",
              "ollama_tokens_per_second" not in ev.data)
    ctx.check("no ollama_prefill_seconds key either", "ollama_prefill_seconds" not in ev.data)
    ctx.check("no ollama_offloaded key either", "ollama_offloaded" not in ev.data)
    # `Session.status_event`'s own deliberate case: the route switched AWAY
    # from ollama, so it explicitly passes None to CLEAR a stale reading --
    # that is a real, intentional clear, not "the producer never mentioned
    # it", so the key must still be present (as None).
    ev2 = events.status(phase="idle", model="or:x/y", turn=3, ollama_tokens_per_second=None)
    ctx.check("an explicit None is still PRESENT (a real clear)", "ollama_tokens_per_second" in ev2.data)
    ctx.check("value is None", ev2.data["ollama_tokens_per_second"] is None)
    ev3 = events.status(phase="idle", model="ol:x", turn=3, ollama_tokens_per_second=41.0,
                         ollama_prefill_seconds=1.2, ollama_offloaded=False)
    ctx.check("a real reading carries all three", ev3.data["ollama_tokens_per_second"] == 41.0
              and ev3.data["ollama_prefill_seconds"] == 1.2 and ev3.data["ollama_offloaded"] is False)


@test
def test_status_bar_keeps_last_ollama_reading_when_a_plain_status_omits_it(ctx: Ctx):
    """The real-widget half of the finding 10 pin -- an ordinary idle
    status with no ollama keys at all (what every plain `events.status(
    phase=..., model=...)` call site produces) must leave the throughput
    chip exactly as it was, never blank it."""
    from textual.widgets import Static
    from halo_harness.tui.widgets.statusbar import StatusBar
    captured = []
    original = Static.update
    Static.update = lambda self, content="": captured.append(content)
    try:
        bar = StatusBar(cwd="")
        bar.apply_status({"phase": "idle", "model": "ol:x",
                           "ollama_tokens_per_second": 41.0, "ollama_prefill_seconds": 1.2,
                           "ollama_offloaded": False})
        ctx.check("reading applied", bar.ollama_tokens_per_second == 41.0)
        ctx.check(f"chip shows the reading, got {captured[-1].plain!r}", "41" in captured[-1].plain)
        bar.apply_status({"phase": "idle", "model": "ol:x"})  # no ollama_* keys at all
        ctx.check("a plain status with no ollama keys leaves the reading untouched",
                  bar.ollama_tokens_per_second == 41.0)
        ctx.check(f"chip still shows it, got {captured[-1].plain!r}", "41" in captured[-1].plain)
        bar.apply_status({"phase": "idle", "model": "or:x/y", "ollama_tokens_per_second": None,
                           "ollama_prefill_seconds": None, "ollama_offloaded": None})
        ctx.check("an EXPLICIT None (switched away from ollama) does clear it",
                  bar.ollama_tokens_per_second is None)
    finally:
        Static.update = original


@test
def test_message_end_forwards_saved_usd_to_status_bar_through_real_dispatch(ctx: Ctx):
    """C-2 finding 9 pin: `tui/dispatch.py`'s own `message_end` handler
    (never just `StatusBar.apply_status` called directly, which the old
    `test_offline_mode.py::test_status_bar_offline_chip` check never
    actually exercised) must forward `saved_usd` -- same `Static.update`
    capture technique as the tests above, through the REAL `_apply_event_
    inner` dispatcher this time, with a minimal fake `app` (a real
    `StatusBar` plus a bare transcript double) standing in for the parts
    of `BridgeApp` the `message_end` branch touches."""
    import asyncio
    from textual.widgets import Static
    from halo_harness import events
    from halo_harness.tui.dispatch import _apply_event_inner
    from halo_harness.tui.widgets.statusbar import StatusBar

    class _FakeTranscript:
        async def finish_phase_line(self, turn, *, agent_id=None):
            pass

        async def finish_open_streams(self, *, agent_id=None):
            pass

    class _FakeApp:
        def __init__(self):
            self.status_bar = StatusBar(cwd="")
            self.transcript = _FakeTranscript()

    captured = []
    original = Static.update
    Static.update = lambda self, content="": captured.append(content)
    try:
        app = _FakeApp()
        ctx.check("saved_usd starts unset", app.status_bar.saved_usd is None)
        ev = events.message_end(turn=1, saved_usd=0.0123)
        asyncio.run(_apply_event_inner(app, ev))
        ctx.check(f"saved_usd forwarded to the real StatusBar, got {app.status_bar.saved_usd}",
                  app.status_bar.saved_usd == 0.0123)
        ctx.check(f"the chip renders the saved figure, got {captured[-1].plain!r}",
                  "saved $" in captured[-1].plain)
    finally:
        Static.update = original


@test
def test_session_status_event_with_no_mcp_status_fn_omits_the_key(ctx: Ctx):
    """C-2 EXTRA (owner report) pin: `Session.status_event` used to pass a
    FAKE {"connected": 0, "total": 0} whenever no `mcp_status_fn` was ever
    wired (print mode, a sub-agent's own Session) -- it now passes None,
    so `events.status()`'s own presence rule (above) correctly omits the
    key instead of claiming a real empty-registry reading nothing ever
    actually checked."""
    import os
    import tempfile
    from pathlib import Path
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    from tests.helpers.fake_home import build_fake_home
    fh = build_fake_home()
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    try:
        session_ctx = SessionContext(cwd=fh["proj"], model_label="ol:plain-text")
        session = Session(
            cwd=fh["proj"], model_ref=parse_model_ref("ol:plain-text"), model_profile=ModelProfile(),
            creds=ProviderCreds(base_url="http://127.0.0.1:1", api_key=""),
            state_dir=Path(tempfile.mkdtemp(prefix="mcp-status-")), model_label="ol:plain-text",
            session_context=session_ctx, max_turns=6,
        )
        ctx.check("no mcp_status_fn wired by default", session.mcp_status_fn is None)
        ev = session.status_event()
        ctx.check(f"no mcp key at all, got {ev.data}", "mcp" not in ev.data)
    finally:
        os.environ.pop("BRIDGE_TEST_HOME", None)


@test
def test_status_bar_keeps_last_count_when_an_event_carries_none(ctx: Ctx):
    # Same technique as tests/test_offline_mode.py: the real widget renders
    # through `Static.update`, which needs a live Textual app, so the paint
    # is captured instead and the bar's own state logic runs for real.
    from textual.widgets import Static
    from halo_harness.tui.widgets.statusbar import StatusBar
    captured = []
    original = Static.update
    Static.update = lambda self, content="": captured.append(content)
    try:
        bar = StatusBar(cwd="")
        bar.apply_status({"phase": "idle", "mcp": {"connected": 2, "total": 6}})
        ctx.check("count applied", (bar.mcp_connected, bar.mcp_total) == (2, 6))
        ctx.check(f"the bar paints MCP 2/6, got {captured[-1].plain!r}", "MCP 2/6" in captured[-1].plain)
        bar.apply_status({"phase": "idle", "model": "or:x/y"})
        ctx.check("a later event without a count keeps 2/6, never 0/0",
                  (bar.mcp_connected, bar.mcp_total) == (2, 6))
        ctx.check(f"still painted as MCP 2/6, got {captured[-1].plain!r}", "MCP 2/6" in captured[-1].plain)
        bar.apply_status({"phase": "idle", "mcp": {"connected": 0, "total": 0}})
        ctx.check("an explicit 0/0 still applies (a real empty registry)",
                  (bar.mcp_connected, bar.mcp_total) == (0, 0))
    finally:
        Static.update = original


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
