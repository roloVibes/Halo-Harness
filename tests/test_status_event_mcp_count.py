"""Halo 2.0.3 release fix: a status event without an MCP count must not reset
the status bar to "MCP 0/0". Before this fix `events.status()` filled a
missing count with {"connected": 0, "total": 0}, and the several idle status
events a turn emits without a count zeroed the bar mid-session (the owner
saw "0/6" become "0/0" every session). Now the key is absent when the
producer does not know the count, and the status bar keeps its last value.
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
