"""tests.test_packs_studio_ui -- what a pack adds to Studio, in the page
(Halo 3.2.0.0 R3). Headless Chrome through the driver base
(tests/helpers/studio_packs.py; skipped without one), over a fresh home with
the doc-review reference pack and studio-bundle enabled:

1. the pack's section comes after Packs behind a "packs" divider and
   opens with Alt+8 (3.2.0.0 R6): its markdown, table, links and Settings form render,
   each panel names its pack and has its help; the rail lists it;
2. Session holds the pack's Reviews panel, collapsed;
3. the palette's pack action runs (the checks panel, focused);
4. the form writes packs.settings.doc-review;
4b. (3.2.1.0 R1) after a reload the saved pack section is the first paint;
5. the bundle panel shows the grant line until studio-script is granted,
   then "hello from studio-bundle";
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

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}
CORE = ["Session", "Team", "Roles", "Fleet", "Design", "Orchestra", "Packs"]  # Packs: 3.2.0.0 R6


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Studio packs checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_packs"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=400, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_the_packs_section_after_orchestra_with_its_panels(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the six, then the packs' sections, got {got.get('tabs')}", got.get("tabs") == CORE + ["Docs review", "Hello"])
    ctx.check(f"Alt+1..6 kept, Alt+7 Packs, Alt+8 and Alt+9 for the packs (3.2.0.0 R6), got {got.get('kbds')}",
              got.get("kbds") == [f"Alt{n}" for n in range(1, 10)])
    ctx.check(f"a thin packs divider before the first, got {got.get('divider')}", got.get("divider") == ["packs", "Docs review"])
    ctx.check("Alt+8 opens it", str(got.get("alt7")).startswith("Docs review"))
    ctx.check(f"the markdown panel, got {got.get('markdown')!r}", str(got.get("markdown")).startswith("Review notes"))
    ctx.check(f"the table: its columns and three rows, got {got.get('table_head')} {got.get('table_rows')}",
              got.get("table_head") == ["check", "state", "note"] and got.get("table_rows") == 3)
    ctx.check(f"the links, got {got.get('links')}", got.get("links") == ["Roles (the review lineup)", "The checks", "How packs work"])
    ctx.check(f"the Settings form's fields, got {got.get('form_fields')}", got.get("form_fields") == ["style", "max_findings"])
    ctx.check(f"each panel names its pack, got {got.get('about')!r}", got.get("about") == "from pack doc-review")
    ctx.check(f"its help is the pack's, got {got.get('help')!r}", "The reviewer's notes for this repo" in str(got.get("help")))
    ctx.check(f"the rail's PACKS group, with their keys, got {got.get('rail')}", got.get("rail") == ["Docs reviewAlt8", "HelloAlt9"])


@test
def test_the_session_panel_starts_collapsed(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Reviews in Session, a strip, from the pack, got {got.get('session_panel')}",
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
