"""tests.test_steward_tui_notice -- Halo 3.3.4.0 R4: the steward's note in a
live TUI (halo_harness/tui/steward_notice.py, StatusBar.set_notice), one
pilot: a Textual app with the real StatusBar and Transcript, a fixture state
dir whose steward.jsonl gains a note after the watch started; the worker-thread
poll puts the note's first line in the status bar (for NOTICE_S, then gone)
and one system line in the transcript; a note written before the TUI started is
never shown; a member's hub note reads "steward on <hub>: ...". No model, no
server.
Run: python -m tests.test_steward_tui_notice
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402

test, TESTS = new_registry()


@test
def test_a_new_note_shows_in_the_status_bar_and_the_transcript(ctx: Ctx):
    from textual.app import App
    from halo_harness.ollama_steward import notes
    from halo_harness.tui import steward_notice
    from halo_harness.tui.widgets.statusbar import StatusBar
    from halo_harness.tui.widgets.transcript import Transcript

    class _Shell(App):
        def compose(self):
            yield Transcript()
            yield StatusBar()

        def on_mount(self):
            self.transcript = self.query_one(Transcript)
            self.status_bar = self.query_one(StatusBar)

    async def body(h):
        notes.append(h.state, "note", "an old note from before the TUI started")
        watch = steward_notice.NoticeWatch(h.state).start()
        app = _Shell()
        async with app.run_test(size=(140, 30)) as pilot:
            notes.append(h.state, "note", "the 27B on pc spilled 3 GiB to the CPU: the window went down to 49,152",
                         lines=["the 27B on pc spilled 3 GiB to the CPU: the window went down to 49,152", "line two"],
                         attention=True)
            got = await asyncio.to_thread(steward_notice.poll_once, app, watch)
            await pilot.pause()
            await pilot.pause()
            ctx.check(f"the poll found the one new note, got {got}", got == [
                "the 27B on pc spilled 3 GiB to the CPU: the window went down to 49,152"])
            shown = app.status_bar.notice_shown()
            ctx.check(f"its first line is in the status bar, got {shown!r}", shown and shown.startswith("the 27B on pc"))
            log = app.transcript.plain_log
            ctx.check(f"one system line in the transcript, got {log}",
                      [x for x in log if "the 27B on pc spilled" in x] == [got[0]] and not [x for x in log if "old note" in x])
            app.status_bar.set_notice("a short one", 0.2)
            await asyncio.sleep(0.5)
            await pilot.pause()
            ctx.check("a notice is gone after its time", app.status_bar.notice_shown() is None
                      and app.status_bar.notice_text is None)
            ctx.check("nothing new: the next poll finds nothing", await asyncio.to_thread(steward_notice.poll_once, app, watch) == [])
            notes.take_hub_note(h.state, {"hub": "pc-hub", "id": "n-1", "at": "2026-10-27T20:00:00Z",
                                          "line": "the 30B on pc reloads every call: two windows", "attention": False})
            hub = await asyncio.to_thread(steward_notice.poll_once, app, watch)
            await pilot.pause()
            ctx.check(f"a member's hub note, got {hub}", hub == ["steward on pc-hub: the 30B on pc reloads every call: "
                                                                  "two windows"])
            ctx.check("in the status bar too", (app.status_bar.notice_shown() or "").startswith("steward on pc-hub"))

    with Home() as h:
        asyncio.run(body(h))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
