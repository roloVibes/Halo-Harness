"""tests.helpers.studio_ui_org_design -- the Org and Design checks of
tests/test_studio_ui.py (Halo 3.0.7.0 round R3: both are React sections of
the shell now), kept here so that file stays small. Two headless Chrome runs
(`python -m tests.helpers.studio_org_design org|design`), one at a time; the
runner caches each, so the tests read one run per section. 3.0.7.0 R3b: a
third run (`design-rest`, tests/helpers/studio_design_rest.py) drives the
classic page's last features in the React Design section, one check each."""
from __future__ import annotations

from tests.helpers.runner import Ctx, SkipTest

ORG = ("-m", "tests.helpers.studio_org_design", "org")
DESIGN = ("-m", "tests.helpers.studio_org_design", "design")
REST = ("-m", "tests.helpers.studio_org_design", "design-rest")


def register(test, json_of, chrome) -> None:
    register_rest(test, json_of, chrome)  # R3b, below
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


def _rest(ctx: Ctx, json_of, chrome) -> dict:
    if not chrome():
        raise SkipTest("no Chrome found (the Design test needs headless Chrome)")
    r, got = json_of(*REST)
    ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0 and got.get("artboards") == 2)
    return got


def register_rest(test, json_of, chrome) -> None:
    @test
    def test_design_knobs_in_the_artboards_settings_face(ctx: Ctx):
        """R3b: a card's Knobs opens the Artboards panel's settings on its knobs;
        a slider step posts the knob route, the css variable changes in the page
        and the chip and the card show the new version."""
        got = _rest(ctx, json_of, chrome)
        ctx.check(f"no step failed, got {got.get('errors')}", not got.get("errors"))
        ctx.check(f"the two knobs as rows, got {got.get('knobs')!r}", got.get("knobs") == "Spacing|Accent colour")
        ctx.check(f"a step saves v3 in place, got {got.get('knob_chip')!r} {got.get('knob_css')} {got.get('knob_card_version')!r}",
                  got.get("knob_chip") == "made v3" and got.get("knob_css") is True and got.get("knob_card_version") == "v3")

    @test
    def test_design_direct_text_edit_in_the_prototype(ctx: Ctx):
        """R3b: a double-click on a prototype's text opens Studio's inline editor
        with that text; Esc cancels (the page is unchanged); Enter saves the page
        through text-edit as a new version, the rest of the page kept."""
        got = _rest(ctx, json_of, chrome)
        ctx.check(f"the editor opens on the text, got {got.get('edit_text')!r}", got.get("edit_text") == "PULSE")
        ctx.check("Esc cancels", got.get("edit_cancelled") is True)
        ctx.check(f"Enter saves v4, got {got.get('edit_saved')} {got.get('edit_kept_rest')} {got.get('edit_version')!r}",
                  got.get("edit_saved") is True and got.get("edit_kept_rest") is True and got.get("edit_version") == "v4")

    @test
    def test_design_pin_a_comment_and_resolve_it(ctx: Ctx):
        """R3b: with the Comment tool a click on a frame opens the comment box
        there; Enter pins it (posted with the click's place); the pin opens its
        text and Resolve resolves it."""
        got = _rest(ctx, json_of, chrome)
        ctx.check(f"the box, then the comment at the click, got {got.get('comment_box')} {got.get('comment_saved')}",
                  got.get("comment_box") == 1 and got.get("comment_saved") == ["Make the pulse line thicker", True, True])
        ctx.check(f"one numbered pin that opens its text, got {got.get('comment_pins')} {got.get('pin_pop')!r}",
                  got.get("comment_pins") == 1 and got.get("pin_pop") == "Make the pulse line thicker")
        ctx.check("Resolve resolves it and the pin goes", got.get("resolved") is True and got.get("pins_after") == "none")

    @test
    def test_design_system_tokens_save_and_sync(ctx: Ctx):
        """R3b: the design-system panel lists the token sheet; an edited value is
        saved (PUT system); Sync from a folder answers in a dialog and the new
        tokens show."""
        got = _rest(ctx, json_of, chrome)
        ctx.check(f"the panel and its 8 tokens, got {got.get('system_panel')} {got.get('tokens')}", got.get("system_panel") == 1 and got.get("tokens") == 8)
        ctx.check("an edited token is saved", got.get("token_saved") is True)
        ctx.check(f"Sync answers in a dialog and adds the folder's tokens, got {got.get('sync_title')!r} {got.get('tokens_after')}",
                  got.get("sync_title") == "Design system: 10 tokens" and got.get("tokens_after") == 10 and got.get("synced_brand") is True)

    @test
    def test_design_three_directions_land_as_artboards_in_a_row(ctx: Ctx):
        """R3b: 3 directions runs the Send path with variants (the server writes
        the directions prompt); the three artboards land in one row under the
        others, the first selected, their places saved on the server."""
        got = _rest(ctx, json_of, chrome)
        ctx.check(f"five cards, got {got.get('directions_cards')!r}", got.get("directions_cards") == "hero|logo-mark|pricing-a|pricing-b|pricing-c")
        ctx.check(f"the variants prompt, got {got.get('directions_prompt')!r}", str(got.get("directions_prompt")).startswith("Make 3 directions of: a pricing section"))
        tops = got.get("directions_tops") or [0, 0, 0, 0]
        ctx.check(f"one row under the others, got {tops}", tops[1] == tops[2] == tops[3] and tops[1] > tops[0])
        ctx.check("the first is selected and the places are saved", got.get("directions_selected") == "pricing-a" and got.get("directions_saved") is True)

    @test
    def test_design_device_select_is_kept(ctx: Ctx):
        """R3b: the Artboards header's device select draws prototypes at phone
        size; the panel's settings face shows the same select; the choice is
        kept across a reload."""
        got = _rest(ctx, json_of, chrome)
        ctx.check(f"the settings face has the select, got {got.get('settings_device')!r}", got.get("settings_device") == "desktop")
        ctx.check(f"phone draws at 390 px, got {got.get('device_card')!r} {got.get('device_frame')!r}", got.get("device_card") == "phone" and got.get("device_frame") == "390px")
        ctx.check(f"kept as the panel's setting and after a reload, got {got.get('device_saved')!r} {got.get('device_reloaded')!r}",
                  got.get("device_saved") == '{"device":"phone"}' and got.get("device_reloaded") == "phone")
