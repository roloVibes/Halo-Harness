"""tests.test_liveness_round -- Halo 2.0.6 round 1: TUI liveness.

The owner's own words (2026-10-07, mid-2.0.5-release): "the seconds keep
ticking and I see a steering message, tells me nothing what is going on;
need better clarity it's not frozen." The phase line now (1) shows
TENTHS of a second on every live line so a stalled render is instantly
distinguishable from a stalled turn, (2) names what the turn is waiting
on (tool / sub-agent, not just "the model"), (3) says `quiet N s` once a
stream that HAS delivered goes silent, and the status bar (4) breaks
"bg jobs N" down by kind and (5) surfaces the hang watchdog's own stall
clock. Unit-level throughout (no pilots needed -- every behavior is a
pure function of clocks the tests pin directly).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


@test
def test_live_elapsed_shows_tenths_and_summary_stays_whole(ctx: Ctx):
    from halo_harness.tui.widgets.transcript import ThinkingBlock
    w = ThinkingBlock(model_label="m", phase_state="headers")
    try:
        live = w._live_elapsed()
        ctx.check(f"a live line renders tenths ('0.0 s' style), got {live!r}",
                  live.endswith(" s") and "." in live)
        w.phase_state = "reasoning"
        w.enter_done() if False else None
        w.final_elapsed = 12.0
        w.phase_state = "done"
        w._refresh_display()
        ctx.check("the done summary keeps the whole-second form",
                  "Thought for 12 s" in (w._last_rendered or ""))
    finally:
        w._timer = None


@test
def test_quiet_suffix_appears_only_after_activity_and_threshold(ctx: Ctx):
    from halo_harness.tui.widgets.transcript import ThinkingBlock
    w = ThinkingBlock(phase_state="reasoning")
    try:
        # no activity yet -> never quiet (the no-data suffix family owns that)
        w.last_activity_at = time.monotonic() - 30
        ctx.check(f"no activity yet -> no quiet suffix, got {w._quiet_suffix()!r}",
                  w._quiet_suffix() == "")
        # activity, recent -> omitted (normal think-time between chunks)
        w.has_activity = True
        w.last_activity_at = time.monotonic() - 0.5
        ctx.check(f"recent activity -> omitted, got {w._quiet_suffix()!r}",
                  w._quiet_suffix() == "")
        # activity, then silence past the threshold -> visible
        w.last_activity_at = time.monotonic() - 3.2
        got = w._quiet_suffix()
        ctx.check(f"3.2s of silence after activity -> '· quiet 3 s', got {got!r}",
                  got == " · quiet 3 s")
        # a non-streaming state never says quiet
        w.phase_state = "waiting"
        ctx.check("the waiting state leaves quiet to the no-data suffix",
                  w._quiet_suffix() == "")
    finally:
        w._timer = None


@test
def test_wait_target_labels_every_state(ctx: Ctx):
    from halo_harness.tui.widgets.transcript import ThinkingBlock
    w = ThinkingBlock(phase_state="headers")
    try:
        w.set_wait_target("tool: Bash")
        ctx.check(f"the headers line names the tool, got {w._wait_label()!r}",
                  w._wait_label() == " (waiting on tool: Bash)")
        w.set_wait_target(None)
        ctx.check("clearing returns to the plain labels", w._wait_label() == "")
        w.set_wait_target("model")
        ctx.check("'model' IS the plain label (never 'waiting on model')",
                  w._wait_label() == "")
        w.set_wait_target("agent: implementer")
        ctx.check(f"an agent round is named, got {w._wait_label()!r}",
                  w._wait_label() == " (waiting on agent: implementer)")
    finally:
        w._timer = None


@test
def test_transcript_phase_wait_target_routes_to_the_live_line(ctx: Ctx):
    """Routing only (`_phase_lines` dict + set_wait_target -- no mount
    needed): the live line at (agent_id, turn) gets the target, a miss is
    a silent no-op. The full mount path is `begin_phase_line`'s own
    existing coverage."""
    from halo_harness.tui.widgets.transcript import Transcript, ThinkingBlock
    tr = Transcript.__new__(Transcript)  # never mounted; only the dict is touched
    tr._phase_lines = {}
    w = ThinkingBlock(phase_state="headers")
    tr._phase_lines[(None, 1)] = w
    tr.phase_wait_target(1, "tool: Bash")
    ctx.check("the live line carries the target", w.wait_target == "tool: Bash")
    tr.phase_wait_target(1, None)
    ctx.check("and clears it", w.wait_target is None)
    tr.phase_wait_target(99, "tool: X")
    ctx.check("an unknown turn key is a silent no-op (no raise, nothing set)",
              w.wait_target is None)


@test
def test_status_bar_kinds_and_hang_watch_segments(ctx: Ctx):
    import asyncio
    from textual.app import App
    from halo_harness.tui.widgets.statusbar import StatusBar

    async def body():
        class _Shell(App):
            pass

        app = _Shell()
        async with app.run_test(size=(120, 30)):
            sb = StatusBar()
            await app.mount(sb)
            sb.set_background_activity(bg_jobs=0, oldest_elapsed_s=None,
                                       bg_kinds="", hang_watch_s=None)
            ctx.check("no jobs, healthy pump -> neither segment",
                      not sb.bg_kinds and sb.hang_watch_s is None)
            sb.set_background_activity(bg_jobs=3, oldest_elapsed_s=42.0,
                                       bg_kinds="suites 2, build 1", hang_watch_s=None)
            ctx.check(f"bg kinds stored, got {sb.bg_kinds!r}", sb.bg_kinds == "suites 2, build 1")
            sb.set_background_activity(bg_jobs=0, oldest_elapsed_s=None,
                                       bg_kinds="", hang_watch_s=31.0)
            ctx.check(f"the hang-watch clock is stored, got {sb.hang_watch_s!r}",
                      sb.hang_watch_s == 31.0)
    asyncio.run(body())


@test
def test_bg_kinds_word_comes_from_the_description_first(ctx: Ctx):
    """The classifier lives in BridgeApp._tick_background_activity; the
    word-picking contract (description first, then the command, first
    word, lowercased) is pinned here against a fake registry so the
    status bar's vocabulary stays deterministic."""
    from halo_harness.tui.app import BridgeApp

    class _FakeReg:
        def __init__(self, jobs):
            self._jobs = jobs
        def list_jobs(self):
            return self._jobs

    class _FakeSession:
        def __init__(self, reg):
            self.job_registry = reg

    class _FakeController:
        def __init__(self, sess):
            self.session = sess

    jobs = [
        {"status": "running", "description": "run the release suites", "command": "python x", "started_at": 1.0},
        {"status": "running", "description": "", "command": "BUILD_ALL.ps1 -t", "started_at": 2.0},
        {"status": "completed", "description": "run the release suites", "command": "python x", "started_at": 3.0},
    ]
    app = BridgeApp.__new__(BridgeApp)  # never started; only the tick runs
    app._agents_started_at = {}
    app.controller = _FakeController(_FakeSession(_FakeReg(jobs)))

    class _Bar:
        def __init__(self):
            self.got = None
        def set_background_activity(self, **kw):
            self.got = kw
    app.status_bar = _Bar()
    app._tick_background_activity()
    got = app.status_bar.got or {}
    ctx.check(f"only RUNNING jobs count, got bg_jobs={got.get('bg_jobs')}", got.get("bg_jobs") == 2)
    ctx.check(f"description word first, command word (extension stripped) second, "
              f"got {got.get('bg_kinds')!r}",
              got.get("bg_kinds") == "build_all 1, run 1")
    ctx.check("no agents running -> no oldest agent time, oldest from jobs only",
              got.get("oldest_elapsed_s") is not None)
    ctx.check("healthy pump (no _watchdog_stall_since) -> no hang chip",
              got.get("hang_watch_s") is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
