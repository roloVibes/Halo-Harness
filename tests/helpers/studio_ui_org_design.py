"""tests.helpers.studio_ui_org_design -- the Org and Design checks of
tests/test_studio_ui.py (Halo 3.0.7.0 round R3: both are React sections of
the shell now), kept here so that file stays small. Two headless Chrome runs
(`python -m tests.helpers.studio_org_design org|design`), one at a time; the
runner caches each, so the tests read one run per section."""
from __future__ import annotations

from tests.helpers.runner import Ctx, SkipTest

ORG = ("-m", "tests.helpers.studio_org_design", "org")
DESIGN = ("-m", "tests.helpers.studio_org_design", "design")


def register(test, json_of, chrome) -> None:
    @test
    def test_org_start_view_without_paperclip_in_headless_chrome(ctx: Ctx):
        """R3: with no Paperclip answering, Org is one Start view (what Org mode
        is, Install Paperclip and Link a company), no empty panels."""
        if not chrome():
            raise SkipTest("no Chrome found (the Org test needs headless Chrome)")
        r, got = json_of(*ORG)
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0)
        ctx.check(f"the Start view with its two buttons and no panels, got {got}",
                  got.get("start") == 1 and got.get("start_buttons") == [1, 1] and got.get("start_panels") == 0)

    @test
    def test_org_chart_draws_boxes_and_a_drag_saves_and_reparents(ctx: Ctx):
        """R3: over FakePaperclip (halo-dev-cycle synced in) the chart draws the
        seven cards inside their group boxes (Leadership, CEO's team) with the
        reports-to edges; a move is saved to `layout/pc:<id>`; a card dropped
        onto another asks first, then PATCHes reportsTo; double-click opens the
        Inspector, Wake posts the action, an issue row opens the issue."""
        if not chrome():
            raise SkipTest("no Chrome found (the Org test needs headless Chrome)")
        r, got = json_of(*ORG)
        ctx.check(f"the run finished, got {r.stderr[-300:]!r}", r.returncode == 0)
        ctx.check(f"seven cards, each in a box, six edges, got {got}", got.get("cards") == 7 and got.get("cards_in_boxes") is True
                  and got.get("groups") == ["Leadership", "CEO's team"] and got.get("edges") == 6)
        ctx.check("a drag saves the place on the server", got.get("layout_saved") is True)
        ctx.check(f"a drop onto a card asks, then changes the manager, got {got.get('asked')!r}",
                  got.get("asked") == "verify reports to worker?" and got.get("reparented") is True and got.get("new_box") == "yes")
        ctx.check(f"the Inspector, Wake and an issue, got {got.get('inspector')} / {got.get('woke')} / {got.get('issue')}",
                  got.get("inspector") == "research" and got.get("woke") is True and got.get("issue") == "FAK-1")

    @test
    def test_design_thread_artboards_and_a_cancelled_turn_in_headless_chrome(ctx: Ctx):
        """R3: no project: the Design Start view; a seeded project: its two turns
        as a markdown thread (a heading, a code block, no raw HTML), its two
        artboards (the prototype in a scripts-only sandbox); a message sent with
        Enter streams in over the live feed with its tool chip, Cancel turn
        stops it (logged as cancelled); Rename renames an artboard."""
        if not chrome():
            raise SkipTest("no Chrome found (the Design test needs headless Chrome)")
        r, got = json_of(*DESIGN)
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0)
        ctx.check(f"the Start view first, then the thread, got {got}", got.get("start") == 1 and got.get("turns") == 2
                  and got.get("heading") == "Made two artboards" and got.get("code") == 1 and got.get("raw_html") == 0)
        ctx.check(f"the artboards, sandboxed, got {got.get('artboards')} {got.get('sandbox')}",
                  got.get("artboards") == ["hero", "logo-mark"] and got.get("sandbox") == ["allow-scripts"])
        ctx.check(f"a turn streams with its tool chip and Cancel turn stops it, got {got}", "Write" in str(got.get("live"))
                  and got.get("cancel_button") == 1 and got.get("after_cancel") == 3 and got.get("cancelled_logged") is True)
        ctx.check("Rename renames the artboard", got.get("renamed") == "Landing hero")
