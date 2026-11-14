"""tests.test_bg_pickup_studio -- Halo 3.4.1.3: background work that finished while a session was idle reaches
Studio with no prompt sent (the control socket's `status` carries `bg_done`, the session row carries it, Attention
lists a `background_done` row: the glance, Agents -> Live's chip and the browser alert read that queue), the
setting is in the Settings catalog, and the TUI draws the line and puts it on the status bar.
The pump-level behaviour (the self-started turn, the window, typing, the cap, the three values): tests/test_bg_pickup.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.bg_pickup_rig import Rig

test, TESTS = new_registry()


@test
def test_studio_lists_it_without_a_prompt(ctx: Ctx):
    from halo_harness.live import attention
    from halo_harness.peers.local_view import session_row
    from halo_harness.remote.base import _BaseHandle
    from halo_harness.studio.live_answer import SET_ASIDE
    rig = Rig("bgp-studio", ["hi", "ok"], when_done="tell")
    try:
        rig.submit("hello")
        rig.turns_done(1)
        rig.finish_job("bash_10", "nightly report")
        status = _BaseHandle(rig.session, rig.session.cwd).status()
        row = session_row({"session_id": "s1", "title": "work", "kind": "tui"}, status, [])
        view = {"harnesses": [{"id": "h1", "name": "tower", "local": True, "sessions": [row]}]}
        rows = [r for r in attention.build(view) if r["kind"] == "background_done"]
        ctx.check("the session's row carries it", (row.get("bg_done") or {}).get("count") == 1)
        ctx.check(f"Attention lists it, got {rows}", len(rows) == 1 and "nightly report" in rows[0]["detail"]
                  and rows[0]["what"] == "Background work finished")
        ctx.check("it can be set aside", "background_done" in SET_ASIDE and rows[0]["keys"].get("a") == "set aside")
        rig.finish_job("bash_11", "second report")
        status = _BaseHandle(rig.session, rig.session.cwd).status()
        view["harnesses"][0]["sessions"] = [session_row({"session_id": "s1"}, status, [])]
        again = [r for r in attention.build(view) if r["kind"] == "background_done"]
        ctx.check("a second finish is the same row (one alert), counting two",
                  len(again) == 1 and again[0]["id"] == rows[0]["id"] and "(2 tasks)" in again[0]["what"])
        rig.submit("ok")
        rig.turns_done(2)
        status = _BaseHandle(rig.session, rig.session.cwd).status()
        view["harnesses"][0]["sessions"] = [session_row({"session_id": "s1"}, status, [])]
        ctx.check("gone with the person's next message",
                  not [r for r in attention.build(view) if r["kind"] == "background_done"])
    finally:
        rig.close()


@test
def test_the_setting_is_in_the_settings_catalog(ctx: Ctx):
    from halo_harness.settings_catalog import row
    when, cap = row("background.when_done"), row("background.self_turns")
    ctx.check("background.when_done: continue / tell / wait, continue the default",
              when is not None and tuple(when.choices) == ("continue", "tell", "wait") and when.default == "continue")
    ctx.check("background.self_turns: an int, 3", cap is not None and cap.kind == "int" and cap.default == 3)
    ctx.check("both on Settings -> Steer and turn", when.group == "steer" and cap.group == "steer")


@test
def test_the_tui_draws_the_line_and_the_status_bar(ctx: Ctx):
    import asyncio
    from halo_harness import events
    from halo_harness.tui.dispatch import _apply_event_inner
    seen: list = []

    class _Transcript:
        async def add_note(self, text, *, kind="note"):
            seen.append(("note", text, kind))

    class _Bar:
        def set_notice(self, text, seconds=30.0):
            seen.append(("bar", text))

    class _App:
        transcript = _Transcript()
        status_bar = _Bar()

    line = "◼ background work finished: job lint -- exit 0 -- Halo picks it up in a few seconds, no message needed"
    asyncio.run(_apply_event_inner(_App(), events.turn_marker("background", line)))
    ctx.check(f"a transcript line and the status bar, got {seen}",
              ("note", line, "marker") in seen and ("bar", line) in seen)
    seen.clear()
    asyncio.run(_apply_event_inner(_App(), events.turn_marker("background", "↻ Halo picks up", started=True)))
    ctx.check("the turn's own start is a line only", seen == [("note", "↻ Halo picks up", "marker")])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
