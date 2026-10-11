"""tests.test_review_tui -- Halo 2.0.10 round 1: `/review` in the TUI (Textual
pilot) with a REAL Controller and Session against the mock upstream: the
reviewers show up as rows in `/tasks` while they run, the result lands as a
header line plus one ReviewCard per finding (file:line link, severity, verdict
badge, failure scenario folded), and the cards fold/unfold and copy.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_openai import MockUpstream
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.helpers import review_mock as rm

ensure_default_provider_credentials()
import halo_harness.tui.clipboard as clipboard_mod

test, TESTS = new_registry()


def _without_real_clipboard(fn):
    """Every test in this module runs with the external clipboard tools
    stubbed -- and RESTORED afterwards: a module-level override leaked
    into tests/run_all.py's single process and broke
    test_round_copy_out's own read_via_external_tool pin on CI."""
    def wrapped(ctx):
        saved = (clipboard_mod.copy_via_external_tool, clipboard_mod.read_via_external_tool)
        clipboard_mod.copy_via_external_tool = lambda *a, **kw: False     # never touch the real clipboard
        clipboard_mod.read_via_external_tool = lambda *a, **kw: None
        try:
            return fn(ctx)
        finally:
            clipboard_mod.copy_via_external_tool, clipboard_mod.read_via_external_tool = saved
    wrapped.__name__ = fn.__name__
    return wrapped
_ORIGINAL_HOME = os.environ.get("BRIDGE_TEST_HOME")


def _verdict(v: str, reason: str) -> str:
    return "```json\n" + json.dumps({"verdict": v, "reason": reason}) + "\n```"


def _dim(prompt: str) -> str:
    for line in prompt.splitlines():
        if line.startswith("Dimension: "):
            return line.split()[1]
    return ""


async def _type(pilot, text: str) -> None:
    for ch in text:
        await pilot.press(ch)


async def _wait(app, pilot, predicate, tries: int = 200, pause: float = 0.05) -> bool:
    for _ in range(tries):
        await app._drain()
        await pilot.pause(pause)
        if predicate():
            return True
    return False


def _tasks_texts(app) -> "list[str]":
    from textual.widgets import OptionList
    out = []
    for ol in app.screen.query(OptionList):
        for i in range(ol.option_count):
            out.append(str(ol.get_option_at_index(i).prompt))
    return out


@test
def test_review_command_shows_tasks_rows_then_finding_cards(ctx: Ctx):
    from halo_harness.controller import Controller
    from halo_harness.tui.app import BridgeApp
    from halo_harness.tui.dialogs.tasks import TasksPanel
    from halo_harness.tui.widgets.review_cards import ReviewCard, ReviewHeader

    async def body():
        mock = MockUpstream().start()
        try:
            repo = rm.make_repo()
            session = rm.new_session(mock, repo)
            items = [rm.finding_json(severity="high", short="subtracts instead of adds", category="logic-error"),
                     rm.finding_json(file="util.py", line=2, severity="low", category="crash", short="empty list crash",
                                     summary="xs[0] on an empty list", scenario="first([]) raises IndexError")]
            rev = rm.Router(lambda p: rm.fenced(items) if _dim(p) == "correctness" else "```json\n[]\n```", delay=1.6)
            jud = rm.Router(lambda p: _verdict("CONFIRMED", "traced") if "subtracts" in p
                            else _verdict("PLAUSIBLE", "depends on callers"))
            rm.register(reviewer=rev, judge=jud)
            controller = Controller(session=session, cwd=repo)
            app = BridgeApp(controller, cwd=str(repo))
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.3)
                await pilot.click("#prompt-input")
                await _type(pilot, "/review --dimensions correctness,tests")
                await pilot.press("enter")
                await pilot.pause(0.3)

                # the reviewers appear live in /tasks while they work
                await _type(pilot, "/tasks")
                await pilot.press("enter")
                opened = await _wait(app, pilot, lambda: isinstance(app.screen, TasksPanel))
                ctx.check("/tasks panel opened mid-review", opened)
                rows = []
                seen = await _wait(app, pilot, lambda: bool(
                    [t for t in _tasks_texts(app) if "review-correctness" in t]) and bool(
                    [t for t in _tasks_texts(app) if "review-tests" in t]), tries=60)
                rows = _tasks_texts(app)
                ctx.check(f"both reviewer rows are listed, got {rows}", seen)
                ctx.check("a running row says so", any("running" in t or "thinking" in t or "waiting" in t
                                                       for t in rows if "review-" in t))
                await pilot.press("escape")
                await pilot.pause(0.2)

                # then the result: header + one card per finding
                done = await _wait(app, pilot, lambda: len(app.query(ReviewCard)) >= 2, tries=300)
                ctx.check("two finding cards were mounted", done)
                headers = [h.raw_text for h in app.query(ReviewHeader)]
                ctx.check(f"one header line with counts, got {headers}",
                          len(headers) == 1 and "2 findings (1 confirmed, 1 plausible) from 2 reviewers" in headers[0])
                cards = list(app.query(ReviewCard))
                first = cards[0]
                ctx.check("high-severity confirmed finding first",
                          first.finding["severity"] == "high" and first.finding["verdict"] == "CONFIRMED")
                head = first.header_markup()
                ctx.check(f"card header shows severity, link, verdict, category, got {head!r}",
                          "\\[HIGH]" in head and "[@click=copy_location]a.py:2[/]" in head and "CONFIRMED" in head
                          and "logic-error" in head)
                ctx.check(f"the rendered card shows the [HIGH] tag as text, got {str(first.render())[:80]!r}",
                          "1. [HIGH] a.py:2  CONFIRMED" in str(first.render()))
                ctx.check("failure scenario is folded by default", "add(1, 2) returns -1" not in str(first.render()))
                first.focus()
                await pilot.press("enter")
                await pilot.pause(0.1)
                ctx.check("enter unfolds the details", "add(1, 2) returns -1" in str(first.render())
                          and "Judge: traced" in str(first.render()))
                await pilot.press("enter")
                await pilot.pause(0.1)
                ctx.check("enter folds them again", "add(1, 2) returns -1" not in str(first.render()))
                app._clipboard = ""
                await pilot.click(ReviewCard, offset=(2 + len("1. [HIGH] ") + 2, 0))
                await pilot.pause(0.2)
                ctx.check(f"clicking the file:line link copies it, got {app.clipboard!r}", app.clipboard == "a.py:2")
                app._clipboard = ""
                first.action_copy_location()
                await pilot.pause(0.1)
                ctx.check(f"copying the location puts file:line on the clipboard, got {app.clipboard!r}",
                          app.clipboard == "a.py:2")
                first.action_copy_card()
                await pilot.pause(0.1)
                ctx.check("copying the card puts the whole finding on the clipboard",
                          "Failure scenario: add(1, 2) returns -1" in app.clipboard)
                ctx.check("the transcript log carries the result for later copy",
                          any("subtracts instead of adds" in line for line in app.transcript.plain_log))
                # /tasks afterwards: every reviewer and judge row is finished
                rows_now = controller.list_agent_tasks()
                titles = sorted({r["title"] for r in rows_now})
                ctx.check(f"reviewers and judges are in the task list, got {titles}",
                          titles == ["review-correctness", "review-judge", "review-tests"])
                ctx.check("all finished", all(r["status"] == "completed" for r in rows_now))
                ctx.check("no exit, app still running", app.return_code is None)
        finally:
            mock.stop()
    asyncio.run(body())


@test
def test_review_usage_error_is_shown_not_raised(ctx: Ctx):
    from halo_harness.controller import Controller
    from halo_harness.tui.app import BridgeApp
    from halo_harness.tui.widgets.review_cards import ReviewCard

    async def body():
        mock = MockUpstream().start()
        try:
            repo = rm.make_repo()
            session = rm.new_session(mock, repo)
            controller = Controller(session=session, cwd=repo)
            app = BridgeApp(controller, cwd=str(repo))
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.3)
                await pilot.click("#prompt-input")
                await _type(pilot, "/review --dimensions bogus")
                await pilot.press("enter")
                ok = await _wait(app, pilot, lambda: any("bogus" in line for line in app.transcript.plain_log), tries=60)
                ctx.check(f"the error names the bad dimension, got {app.transcript.plain_log[-3:]}", ok)
                ctx.check("no cards", len(app.query(ReviewCard)) == 0)
                ctx.check("no exit", app.return_code is None)
        finally:
            mock.stop()
    asyncio.run(body())


@test
def test_zzz_restore_env(ctx: Ctx):
    if _ORIGINAL_HOME is None:
        os.environ.pop("BRIDGE_TEST_HOME", None)
    else:
        os.environ["BRIDGE_TEST_HOME"] = _ORIGINAL_HOME
    ctx.check("env restored", True)


TESTS[:] = [(name, _without_real_clipboard(fn)) for name, fn in TESTS]


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
