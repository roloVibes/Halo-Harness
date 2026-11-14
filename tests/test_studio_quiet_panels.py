"""tests.test_studio_quiet_panels -- Halo 3.3.2.0 "Quiet Studio" round R3: quieter panels, one thing per section,
a density setting (rolo, 2026-10-27: "the visuals in studio are too cluttered"). Headless Chrome at 1280 x 800
through tests/helpers/studio_quiet_panels.py (skipped without one), over a seeded scratch home; no provider
request, no model call:

1. one thing per section: on a fresh browser each of Session, Agents (Cast) and Packs opens on its main panel (Live,
   Canvas, Installed), its box >= 60 % of the stage, every other panel closed: a button in the view bar (3.6.0.0 R0a;
   strips at the foot before);
2. the ornament on one panel at a time: one `.panel.focused` (the main one until a click), one set of HUD
   brackets, one mono data line, no about line in any panel; a click moves it; the panel's ? opens its help on
   the about line and toggles it shut;
3. (on Agents -> Live, the inspector's button) a drawer opens on the main panel's right (the main panel gives up that
   width, as tall as before, one 12 px gap between them) and gives it back when closed; the drawer is kept across a
   reload with no "custom layout" badge, Reset layout returns to the default;
4. density: the header toggle sets `data-density="compact"` and the measured tokens (`--pad`, the stage's gap, the
   title line, the body text), remembered across a reload; the palette's "Density: comfortable" switches it back.
Plus source pins: no about line in the panel frame, the compact token set changes no colour.
Run: python -m tests.test_studio_quiet_panels
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.driver_got import got as driver_got  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
_RUN: dict = {}
PRIMARY = {"session": "session-live", "roles": "roles-graph",  # 3.3.16.0 R1: roles, Agents' door; R2: no Fleet; 3.4.0.0 D: no Runs
           "packs": "pm-installed"}


def _got(ctx: Ctx) -> dict:
    info = driver_got(ctx, "tests.helpers.studio_quiet_panels", why="the quiet panel checks need headless Chrome",
                      cache=_RUN, key="run", timeout=480, tail=600)
    return info


@test
def test_the_source_is_quiet(ctx: Ctx):
    panel = (UI / "lib" / "workspace" / "Panel.tsx").read_text(encoding="utf-8")
    ctx.check("the panel frame draws no about line", "panel-about" not in panel and "{spec.about}</" not in panel)
    ctx.check("the brackets and the data line only on the focused panel",
              '{focused && <span className="hud-brackets"' in panel and "{focused && (" in panel and 'data-testid="panel-help-btn"' in panel)
    css = (UI / "styles" / "tokens.css").read_text(encoding="utf-8")
    m = re.search(r':root\[data-density="compact"\] \{(.*?)\}', css, re.S)
    ctx.check("tokens.css has the compact set", bool(m))
    body = m.group(1) if m else ""
    ctx.check("the compact set changes no colour", not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", body) and "--pad:" in body and "--fs:" in body)
    store = (UI / "lib" / "density.ts").read_text(encoding="utf-8")
    ctx.check("density is remembered per browser under halo.studio.density, every read and write in try/catch",
              'DENSITY_KEY = "halo.studio.density"' in store and store.count("try {") >= 3)
    specs = {sid: pid for sid, pid in PRIMARY.items()}
    src = "\n".join(p.read_text(encoding="utf-8") for p in (UI / "routes").rglob("*.tsx"))
    for sid, pid in specs.items():
        ctx.check(f"{sid}: {pid} is the primary", re.search(rf'panel\("{pid}", \{{ title: "[^"]+", primary: true,', src) is not None)


@test
def test_one_thing_per_section(ctx: Ctx):
    got = _got(ctx)
    for sid, pid in PRIMARY.items():
        cover = (got.get("cover") or {}).get(sid) or 0
        ctx.check(f"{sid}: {pid} covers >= 60 % of the stage at 1280 x 800, got {cover}", cover >= 0.6)
        state = dict((got.get("state") or {}).get(sid) or [])
        others = {k: v for k, v in state.items() if k != pid}
        ctx.check(f"{sid}: the main panel open, every other panel closed in the view bar, got {state}",
                  state.get(pid) == "open" and others and set(others.values()) == {"closed"})


@test
def test_the_ornament_on_one_panel(ctx: Ctx):
    got = _got(ctx)
    for sid, pid in PRIMARY.items():
        orn = (got.get("ornament") or {}).get(sid)
        ctx.check(f"{sid}: one focused panel (the main one), one set of brackets, one data line, no about line, got {orn}",
                  orn == [[pid], 1, 1, 1, 0])
    ctx.check(f"a click moves it, got {got.get('ornament_click')}", got.get("ornament_click") == [["roles-inspector"], 1, 1, 1, 0])
    ctx.check(f"the ? opens the help on the about line, got {got.get('help_first')!r} / {got.get('about_title')!r}",
              bool(got.get("help_first")) and got.get("help_first") == got.get("about_title"))
    ctx.check(f"the ? again closes it, got {got.get('help_toggled')}", got.get("help_toggled") == "closed")


@test
def test_a_drawer_opens_beside_the_main_panel_and_is_kept(ctx: Ctx):
    got = _got(ctx)
    mb, ao, mo, back = (got.get(k) or [0, 0, 0, 0] for k in ("map_before", "att_open", "map_open", "map_back"))
    ctx.check(f"the drawer sits right of the tree (one 12 px gap), as tall, the tree narrower by its width, got {mb} {ao} {mo}",
              mo[3] == mb[3] and ao[3] == mb[3] and mo[2] < mb[2] and abs((mo[0] + mo[2] + 12) - ao[0]) <= 2 and ao[1] == mb[1])
    ctx.check(f"closed again, the tree has its width back, no badge, got {back} {got.get('custom_after')}", back == mb and got.get("custom_after") is False)
    ctx.check(f"opened: saved, kept across a reload, no badge, got {got.get('map_mine')} {got.get('map_reload')} {got.get('badge')}",
              got.get("key") is True and got.get("map_mine") != got.get("map_default") and got.get("map_reload") == got.get("map_mine") and got.get("badge") is False)
    ctx.check(f"Reset layout: the default again, got {got.get('reset')} {got.get('map_reset')} {got.get('cover_reset')}",
              got.get("reset") is True and got.get("map_reset") == got.get("map_default") and (got.get("cover_reset") or 0) >= 0.6)


@test
def test_density(ctx: Ctx):
    got = _got(ctx)
    comf, comp = got.get("comfortable") or [], got.get("compact") or []
    ctx.check(f"comfortable by default (3.3.15.0 L1, the Instrument scale): --pad 12px, a 12 px stage gap, a 40 px title line, 13 px text, got {comf}", comf == ["comfortable", "12px", "12px", 40, "13px"])
    # 3.3.15.0 R3 (owner feedback 2026-11-09, panels breathe): a title line is 36 px at the least, compact's 32 grows
    ctx.check(f"the toggle: compact, --pad 9px, a 10 px stage gap, a 36 px title line, 12 px text, got {comp} {got.get('toggle_title')!r}",
              comp == ["compact", "9px", "10px", 36, "12px"] and got.get("toggle_title") == "Density: comfortable (press for compact)")
    ctx.check(f"remembered across a reload, got {got.get('saved')} {got.get('reload')}", got.get("saved") == "compact" and got.get("reload") == comp)
    ctx.check(f"the palette's Density: comfortable, got {got.get('palette')} {got.get('saved_after')}",
              got.get("palette") == comf and got.get("saved_after") == "comfortable")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
