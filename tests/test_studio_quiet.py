"""tests.test_studio_quiet -- Halo 3.3.2.0 "Quiet Studio" round R1 (rolo, 2026-10-27: "the visuals in studio
are too cluttered and the pop up is annoying when you open a tab and the left column takes up too much space").
Headless Chrome through tests/helpers/studio_quiet.py (skipped without one), over a seeded scratch home and a
fresh one; no provider request, no model call:

1. nothing opens on any tab: each of the eight core sections, loaded on its own (no `tour=off`) and reached
   by Alt+1..8, shows no section help, no dialog, no Start here after 2 s, on the seeded home and the fresh one;
2. Start here only on the fresh home's first section; "Set up this box" closes it for this browser (not on the
   next section, not on a reload); a browser without the key gets it once more, "Just look around" closes it;
3. the icon rail: 56 px of section icons by default (<= 64), 200 px expanded by its chevron (R2: <= 200), the
   choice remembered across a reload; a row per section with its title as tooltip and name, the current one
   lit, no printed shortcut; no tab strip in the header; R2: the section rows and the chevron only, in both
   widths (no panel row, no layout block, no Fleet tree, no runs); Alt+4 and a click still switch;
4. the inspector closed on load; a Roles card click selects in Roles' own Inspector panel and leaves the column
   closed; a panel's Settings opens it (340 px, the stage gives the width), it is remembered across a reload,
   its close button gives the width back and a reload keeps it closed;
5. Focus: F hides the rail, the inspector and the status bar (`0 1fr 0`, the status row 0), remembered across
   a reload; F again brings back the rail and the inspector as they were; the header button; Shift+F in
   Session, where F follows an agent.
Run: python -m tests.test_studio_quiet
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
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
_RUN: dict = {}
SECTIONS = ["session", "team", "roles", "fleet", "design", "orchestra", "packs", "setup"]
NOTHING = [0, 0, 0]  # section help, dialogs, Start here


def _got(ctx: Ctx, which: str) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the quiet Studio checks need headless Chrome)")
    if which not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_quiet", which], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=420, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN[which] = (r, info)
    r, info = _RUN[which]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the {which} driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_the_source_has_no_welcome_left(ctx: Ctx):
    store = (UI / "lib" / "store.ts").read_text(encoding="utf-8")
    ctx.check("welcomeIfNew, SEEN_PREFIX and NO_WELCOME are gone", not any(w in store for w in ("welcomeIfNew", "SEEN_PREFIX", "NO_WELCOME")))
    src = "\n".join(p.read_text(encoding="utf-8") for p in UI.rglob("*.ts*"))
    ctx.check("nothing in ui/src calls it or reads halo.studio.seen", "welcomeIfNew" not in src and "halo.studio.seen" not in src)
    css = (UI / "styles" / "shell.css").read_text(encoding="utf-8")
    for rule in ("grid-template-columns: 56px minmax(0, 1fr) 0;", '.app[data-rail="open"] { grid-template-columns: 200px minmax(0, 1fr) 0; }',
                 '.app[data-focus="on"][data-rail][data-inspector] { grid-template-columns: 0 minmax(0, 1fr) 0;'):
        ctx.check(f"shell.css has {rule}", rule in css)


@test
def test_nothing_opens_on_any_tab(ctx: Ctx):
    for which in ("seeded", "fresh"):
        got = _got(ctx, which)
        for how in ("loads", "keys"):
            seen = got.get(f"{which}_{how}") or {}
            ctx.check(f"{which} home, every section by {how}: nothing open after 2 s, got {seen}",
                      list(seen) == SECTIONS and all(v == NOTHING for v in seen.values()))


@test
def test_start_here_once_on_the_first_section(ctx: Ctx):
    got = _got(ctx, "fresh")
    ctx.check(f"the fresh home's first section shows Start here (and only it), got {got.get('offer_open')}",
              got.get("offer_first") is True and got.get("offer_open") == [0, 1, 1])
    ctx.check(f"Set up this box: Setup, the overlay gone, the browser's key written, got {got.get('setup_went')!r} {got.get('start_key')!r}",
              got.get("setup_went") == "setup" and got.get("start_key") == "answered")
    for k in ("after_setup", "next_section", "after_reload"):
        ctx.check(f"not back ({k}), got {got.get(k)}", got.get(k) == NOTHING)
    ctx.check(f"a browser without the key: once more, and Just look around closes it, got {got.get('offer_again')} {got.get('dismissed')}",
              got.get("offer_again") is True and got.get("dismissed") == "gone")


@test
def test_the_icon_rail(ctx: Ctx):
    got = _got(ctx, "seeded")
    ctx.check(f"icons by default, <= 64 px, got {got.get('rail_default')} {got.get('rail_icons_w')}",
              got.get("rail_default") == "icons" and 0 < (got.get("rail_icons_w") or 0) <= 64)
    titles = ["Session", "Team", "Roles", "Fleet", "Design", "Orchestra", "Packs", "Setup"]
    ctx.check(f"one rail-item per core section, title and name the section's, got {got.get('rail_items')}",
              got.get("rail_items") == [[s, t, t, True] for s, t in zip(SECTIONS, titles)])
    ctx.check(f"the current one lit, got {got.get('rail_on')}", got.get("rail_on") == ["roles"])
    ctx.check(f"no label while icons, all eight expanded, got {got.get('rail_labels_shown_icons')} / {got.get('rail_labels_shown_open')}",
              got.get("rail_labels_shown_icons") == 0 and got.get("rail_labels_shown_open") == 8)
    ctx.check(f"no printed shortcut in the rail, got {got.get('rail_kbd')} / {got.get('rail_kbd_open')}",
              got.get("rail_kbd") == [0, False] and got.get("rail_kbd_open") == [0, False])
    ctx.check(f"no tab strip in the header, the section's title there, got {got.get('header_tabs')} {got.get('header_title')!r}",
              got.get("header_tabs") == 0 and str(got.get("header_title")).startswith("Roles"))
    ctx.check(f"the chevron expands to <= 200 px, got {got.get('rail_open')} {got.get('rail_open_w')}",
              got.get("rail_open") == "open" and 64 < (got.get("rail_open_w") or 0) <= 200)
    sections_only = ["rail-sections,rail-toggle", 0, 0]
    ctx.check(f"R2: the section rows and the chevron only, in both widths, got {got.get('panels_icons')} / {got.get('panels_open')}",
              got.get("panels_icons") == sections_only and got.get("panels_open") == sections_only)
    ctx.check(f"remembered across a reload both ways, got {got.get('rail_after_reload')} / {got.get('rail_back')}",
              got.get("rail_after_reload") == ["open", 200] and got.get("rail_back") == ["icons", 56, "icons"])
    ctx.check(f"Alt+4 and a click still switch, got {got.get('alt4')} {got.get('click_team')}", got.get("alt4") == "fleet" and got.get("click_team") == "team")


@test
def test_the_inspector_asks_first(ctx: Ctx):
    got = _got(ctx, "seeded")
    ctx.check(f"closed on load, got {got.get('insp_load')} {got.get('insp_aside')}", got.get("insp_load") == "closed" and got.get("insp_aside") is False)
    ctx.check(f"a card click selects in Roles' own panel, the column stays closed, got {got.get('card_selected')} {got.get('insp_after_card')}",
              got.get("card_selected") is True and got.get("insp_after_card") == "closed")
    ctx.check(f"a panel's Settings opens it at 340 px, the stage gives the width, got {got.get('insp_open')} {got.get('insp_w')} {got.get('stage_w')} -> {got.get('stage_w_open')}",
              got.get("insp_open") == "Canvas" and got.get("insp_w") == 340 and (got.get("stage_w") or 0) - (got.get("stage_w_open") or 0) == 340)
    ctx.check(f"remembered per browser, open across a reload, got {got.get('insp_saved')} {got.get('insp_reload_open')}",
              json.loads(got.get("insp_saved") or "{}") == {"section": "roles", "panel": "roles-graph"} and got.get("insp_reload_open") == "Canvas")
    ctx.check(f"its close button gives the width back, closed across a reload, got {got.get('insp_closed')} {got.get('stage_w_closed')} {got.get('insp_reload_closed')}",
              got.get("insp_closed") == "closed" and got.get("stage_w_closed") == got.get("stage_w") and got.get("insp_reload_closed") == ["closed", None])
    ctx.check(f"the next selection opens it again, got {got.get('insp_reopen')}", got.get("insp_reopen") == "Lineups")


@test
def test_focus(ctx: Ctx):
    got = _got(ctx, "seeded")
    ctx.check(f"F: focus on, the rail and the inspector choices kept, got {got.get('before')} -> {got.get('f_on')}",
              got.get("before") == ["open", "open", "off"] and got.get("f_on") == ["open", "open", "on"])
    ctx.check(f"the rail, the inspector and the status bar hidden, got {got.get('f_hidden')}", got.get("f_hidden") == [False, False, False])
    grid, rows = str(got.get("f_grid")), str(got.get("f_rows"))
    ctx.check(f"the grid is 0 1fr 0 and the status row 0, got {grid!r} {rows!r}", grid.startswith("0px ") and grid.endswith(" 0px") and rows.endswith(" 0px"))
    ctx.check(f"remembered across a reload, got {got.get('f_saved')} {got.get('f_reload')}",
              got.get("f_saved") == "on" and got.get("f_reload") == ["open", "open", "on"])
    ctx.check(f"F again restores them, got {got.get('f_off')} {got.get('f_back')}", got.get("f_off") == ["open", "open", "off"] and got.get("f_back") == [True, True])
    ctx.check(f"the header button, got {got.get('btn_on')} {got.get('btn_off')} {got.get('btn_title')!r}",
              got.get("btn_on") == "true" and got.get("btn_off") == "off" and got.get("btn_title") == "Focus: hide the rail, the inspector and the status bar (F)")
    ctx.check(f"Shift+F in Session (F follows an agent there), got {got.get('shift_f')} {got.get('shift_f_off')}",
              got.get("shift_f") == "on" and got.get("shift_f_off") == "off")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
