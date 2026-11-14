"""tests.test_packs_studio_ui -- what a pack adds to Studio, in the page
(Halo 3.2.0.0 R3). Headless Chrome through the driver base
(tests/helpers/studio_packs.py; skipped without one), over a fresh home with
the doc-review reference pack and studio-bundle enabled:

1. the pack's section comes after Packs behind a "packs" divider and
   opens by its rail row and by Alt+7 (3.3.16.0 R2: the first pack section's key): its markdown, table, links and Settings form render,
   each panel names its pack and has its help; the rail lists it;
2. Session holds the pack's Reviews panel, collapsed;
3. the palette's pack action runs (the checks panel, focused);
4. the form writes packs.settings.doc-review;
4b. (3.2.1.0 R1) after a reload the saved pack section is the first paint;
5. the bundle panel shows the grant line until studio-script is granted,
   then "hello from studio-bundle";
5b. (3.3.10.0 R3) the bundle panel's api: publish shows in the pack's events panel and on() hears it, an
   undeclared kind is refused with the server's line, getData and mode() read, attention raises a row and route
   lands on Fleet, where the row shows;
6. a review.done frame renders with the pack's line in Fleet's Activity,
   Session's Live column and the Reviews panel; an undeclared kind keeps the
   generic line;
7. the attention row shows the pack's label and keys, A answers it;
8. disabled: everything of the pack is gone without a reload (3.2.0.0 R5: and
   its events are refused with one line).
Run: python -m tests.test_packs_studio_ui
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.driver_got import got as driver_got  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}
CORE = ["Session", "Agents", "Local", "Packs", "Setup", "Settings"]  # 3.3.16.0 R1: Agents took in Team, Roles, Orchestra  # Local: 3.3.5.0 R1; 3.3.13.0 R2: Design is a pack's


def _got(ctx: Ctx) -> dict:
    info = driver_got(ctx, "tests.helpers.studio_packs", why="the Studio packs checks need headless Chrome",
                      cache=_RUN, timeout=400, tail=600, stdin=False)
    return info


@test
def test_the_packs_section_after_orchestra_with_its_panels(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the nine, then the packs' sections, got {got.get('tabs')}", got.get("tabs") == CORE + ["Docs review", "Hello"])
    ctx.check(f"Alt+1..6 the core's, Alt+7 and Alt+8 the pack sections' (3.3.16.0 R2), got {got.get('kbds')}",
              got.get("kbds") == [f"Alt+{n}" for n in range(1, 7)] + ["Alt+7", "Alt+8"])
    ctx.check(f"3.3.2.0 R1: no row prints its key, got {got.get('printed')}", got.get("printed") == 0)
    ctx.check(f"a thin packs divider before the first, got {got.get('divider')}", got.get("divider") == ["packs", "Docs review"])
    ctx.check(f"Alt+6 opens Settings, got {got.get('alt8')!r}", str(got.get("alt8")).startswith("Settings"))
    ctx.check(f"Alt+7 opens the first pack section (3.3.16.0 R2), got {got.get('alt0')!r}", str(got.get("alt0")).startswith("Docs review"))
    ctx.check("its rail row opens it", str(got.get("row")).startswith("Docs review"))
    ctx.check(f"the markdown panel, got {got.get('markdown')!r}", str(got.get("markdown")).startswith("Review notes"))
    ctx.check(f"the table: its columns and three rows, got {got.get('table_head')} {got.get('table_rows')}",
              got.get("table_head") == ["check", "state", "note"] and got.get("table_rows") == 3)
    ctx.check(f"the links, got {got.get('links')}", got.get("links") == ["Roles (the review lineup)", "The checks", "How packs work"])
    ctx.check(f"the Settings form's fields, got {got.get('form_fields')}", got.get("form_fields") == ["style", "max_findings"])
    ctx.check(f"each panel names its pack, got {got.get('about')!r}", got.get("about") == "from pack doc-review")
    ctx.check(f"its help is the pack's, got {got.get('help')!r}", "The reviewer's notes for this repo" in str(got.get("help")))
    ctx.check(f"the rail's pack rows, the diamond each, Alt+7 and Alt+8 (3.3.16.0 R2), got {got.get('rail')}",
              got.get("rail") == ["Docs review|Alt+7|true", "Hello|Alt+8|true"])  # 3.3.2.0 R1: the icon rail


@test
def test_the_session_panel_starts_collapsed(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Reviews in Session, a closed drawer (its view bar button), from the pack, got {got.get('session_panel')}",
              got.get("session_panel") == [True, "Reviews", "from pack doc-review"])


@test
def test_the_palette_action_runs(ctx: Ctx):
    got = _got(ctx)
    groups = got.get("palette_groups") or []
    ctx.check(f"the pack's group, after the sections', before Media, got {groups}", "pack doc-review" in groups
              and groups.index("pack doc-review") > groups.index("Go to"))
    ctx.check("Open the review checks: Docs review, the Checks panel focused", got.get("palette_ran") is True)


@test
def test_the_form_writes_the_packs_settings(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"packs.settings.doc-review.style = long, got {got.get('form_saved')}", (got.get("form_saved") or {}).get("style") == "long")


@test
def test_a_reload_paints_the_saved_pack_section_first(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Docs review was the saved section, got {got.get('saved_section')!r}", got.get("saved_section") == "doc-review--docs")
    ctx.check(f"the page names the pack sections, got {got.get('paint_boot_attr')}",
              got.get("paint_boot_attr") == ["doc-review--docs", "studio-bundle--hello"])
    ctx.check(f"the first visible section is the pack's, and no other came before, got {got.get('paint_sections')}",
              (got.get("paint_sections") or [None])[0] == "doc-review--docs" and set(got.get("paint_sections") or []) == {"doc-review--docs"})
    ctx.check("its frame said it was loading, then the panels came", got.get("paint_loading_seen") is True
              and got.get("paint_loading_after") is False)


@test
def test_the_bundle_waits_for_its_grant(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the grant line first, got {got.get('bundle_grant')!r}", "halo pack enable studio-bundle --grant studio-script" in str(got.get("bundle_grant"))
              and got.get("bundle_before") is False)
    ctx.check(f"granted: the pack's script draws it, got {got.get('bundle_hello')!r}", got.get("bundle_hello") == "hello from studio-bundle")


@test
def test_the_bundle_panels_api_acts(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"publish, then the line in the pack's events panel, got {got.get('bundle_publish')!r} {got.get('bundle_events_panel')}",
              got.get("bundle_publish") == "published" and (got.get("bundle_events_panel") or [None])[0] == ["HELLO", "hi from the bundle"])
    ctx.check(f"on() hears its own publish, got {got.get('bundle_on')!r}", got.get("bundle_on") == "heard hello.said: hi from the bundle")
    ctx.check(f"an undeclared kind: the server's line, got {got.get('bundle_publish_bad')!r}",
              got.get("bundle_publish_bad") == "error: studio-bundle declares no event hello.nope (contributes.events: hello.said): "
                                               "a bundle panel publishes its pack's own kinds")
    ctx.check(f"getData reads the data folder, got {got.get('bundle_getdata')!r}", got.get("bundle_getdata") == '{"note": "kept in the data folder"}')
    ctx.check(f"mode() reads the mode, got {got.get('bundle_mode')!r}", got.get("bundle_mode") == "mode loud (Loud)")
    ctx.check(f"attention raises a row, route lands on the fleet (Agents -> Live), got {got.get('bundle_attention')!r} {got.get('bundle_route')!r}",
              got.get("bundle_attention") == "row greet" and str(got.get("bundle_route")).startswith("Agents"))
    ctx.check(f"the row in the attention queue, the pack's label, got {got.get('bundle_attn_chip')!r} {got.get('bundle_attn_what')!r}",
              got.get("bundle_attn_chip") == "hello" and got.get("bundle_attn_what") == "the bundle asks you")
    said = str(got.get("bundle_grant_self"))  # 3.3.14.0 R1 (#4): a pack's page cannot change its own grant
    ctx.check(f"api.lib's client names its scope, got {said!r}",
              said.startswith("lib: POST pack/studio-bundle/grant: a pack's page reaches its own routes"))
    ctx.check(f"a plain fetch with the token: 403, this needs the owner's own page, got {said!r}",
              " | page: 403 this needs the owner's own page" in said)
    ctx.check(f"the grants are unchanged, got {got.get('bundle_grants_after')}", got.get("bundle_grants_after") == ["studio-script"])


@test
def test_the_event_line_everywhere(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Fleet's Activity: the pack's line, then the generic one, got {got.get('activity')}",
              got.get("activity", [""])[0] == "REVIEW README.md: 3 findings" and str(got.get("activity", ["", ""])[1]).startswith("PACK doc-review review.started"))
    ctx.check(f"Session's Live column, got {got.get('live')}", (got.get("live") or [None])[0] == ["REVIEW", "README.md: 3 findings"]
              and (got.get("live") or [None, ["", ""]])[1][0] == "PACK" and "review.started" in (got.get("live") or [None, ["", ""]])[1][1])
    ctx.check(f"the Reviews panel, got {got.get('panel_lines')}", (got.get("panel_lines") or [None])[0] == ["REVIEW", "README.md: 3 findings"])


@test
def test_the_attention_row_with_the_packs_keys(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the pack's label and what, got {got.get('attn_chip')!r} {got.get('attn_what')!r}",
              got.get("attn_chip") == "review" and got.get("attn_what") == "readme: 3 findings wait for you")
    ctx.check(f"its keys, got {got.get('attn_keys')}", got.get("attn_keys") == ["A accept", "R redo", "S skip", "O open"])
    ctx.check("A answers it: the answer file, the row gone", got.get("attn_answer") == "accept" and got.get("attn_row_gone") is True)


@test
def test_disabled_everything_goes_without_a_reload(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"its tab is gone, the other pack's stays, got {got.get('tabs_after')}", got.get("tabs_after") == CORE + ["Hello"])
    ctx.check("its Session panel is gone", got.get("session_panel_after") is False)
    ctx.check(f"its palette action is gone, got {got.get('palette_after')}", got.get("palette_after") == [])
    ctx.check("its attention row is gone", got.get("attn_after") is True)
    ctx.check(f"its event is refused with one line (3.2.0.0 R5), got {got.get('refused')!r}", got.get("refused") ==
              "pack doc-review is disabled here: its event review.done is not published (halo pack enable doc-review)")
    ctx.check(f"so no new line shows, got {got.get('live_after')}", (got.get("live_after") or [0, 1])[0] == (got.get("live_after") or [0, 1])[1])
    ctx.check("no reload happened", got.get("reloads") == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
