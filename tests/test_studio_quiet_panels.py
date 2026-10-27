"""tests.test_studio_quiet_panels -- Halo 3.3.2.0 "Quiet Studio" round R3: quieter panels, one thing per section,
a density setting (rolo, 2026-10-27: "the visuals in studio are too cluttered"). Headless Chrome at 1280 x 800
through tests/helpers/studio_quiet_panels.py (skipped without one), over a seeded scratch home; no provider
request, no model call:

1. one thing per section: on a fresh browser each of Session, Team, Roles, Fleet, Design, Orchestra and Packs
   opens on its primary panel (Live, Board, Canvas, Map, Artboards, Workflow, Installed), its box >= 60 % of the
   stage, every other panel a strip at the foot;
2. the ornament on one panel at a time: one `.panel.focused` (the primary until a click), one set of HUD
   brackets, one mono data line, no about line in any panel; a click moves it; the panel's ? opens its help on
   the about line and toggles it shut;
3. a strip that opens joins the column on the primary's right (the primary gives up those columns, as tall as
   before, the strips stay below) and gives them back when collapsed again; a saved layout wins across a reload, Reset layout returns to the
   quiet default;
4. density: the header toggle sets `data-density="compact"` and the measured tokens (`--pad`, the gutter
   between panels, the title line, the body text), remembered across a reload; the palette's "Density: comfortable" switches it back.
Plus source pins: no about line in the panel frame, the compact token set changes no colour.
Run: python -m tests.test_studio_quiet_panels
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
_RUN: dict = {}
PRIMARY = {"session": "session-live", "team": "team-board", "roles": "roles-graph", "fleet": "fleet-map",
           "design": "design-artboards", "orchestra": "graph", "packs": "pm-installed"}


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the quiet panel checks need headless Chrome)")
    if "run" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_quiet_panels"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=480, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["run"] = (r, info)
    r, info = _RUN["run"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in info)
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
        ctx.check(f"{sid}: the primary open, every other panel a strip, got {state}", state.get(pid) == "open" and others and set(others.values()) == {"strip"})


@test
def test_the_ornament_on_one_panel(ctx: Ctx):
    got = _got(ctx)
    for sid, pid in PRIMARY.items():
        orn = (got.get("ornament") or {}).get(sid)
        ctx.check(f"{sid}: one focused panel (the primary), one set of brackets, one data line, no about line, got {orn}",
                  orn == [[pid], 1, 1, 1, 0])
    ctx.check(f"a click moves it, got {got.get('ornament_click')}", got.get("ornament_click") == [["fleet-attention"], 1, 1, 1, 0])
    ctx.check(f"the ? opens the help on the about line, got {got.get('help_first')!r} / {got.get('about_title')!r}",
              bool(got.get("help_first")) and got.get("help_first") == got.get("about_title"))
    ctx.check(f"the ? again closes it, got {got.get('help_toggled')}", got.get("help_toggled") == "closed")


@test
def test_strips_open_beside_the_primary_and_the_saved_layout_wins(ctx: Ctx):
    got = _got(ctx)
    mb, ao, mo, back = (got.get(k) or [0, 0, 0, 0] for k in ("map_before", "att_open", "map_open", "map_back"))
    ctx.check(f"the opened strip sits right of the map, as tall, the map narrower by its columns, got {mb} {ao} {mo}",
              mo[3] == mb[3] and ao[3] == mb[3] and mo[2] < mb[2] and abs((mo[0] + mo[2]) - ao[0]) <= 10 and ao[1] == mb[1]
              and got.get("strips_below") is True)
    ctx.check(f"collapsed again, the map has its rows back, got {back}", back == mb)
    ctx.check(f"a layout of your own: saved, kept across a reload, the badge, got {got.get('map_mine')} {got.get('map_reload')} {got.get('badge')}",
              got.get("key") is True and got.get("map_mine") != got.get("map_default") and got.get("map_reload") == got.get("map_mine") and got.get("badge") is True)
    ctx.check(f"Reset layout: the quiet default again, got {got.get('reset')} {got.get('map_reset')} {got.get('cover_reset')} {got.get('badge_reset')}",
              got.get("reset") is True and got.get("map_reset") == got.get("map_default") and (got.get("cover_reset") or 0) >= 0.6 and got.get("badge_reset") is False)


@test
def test_density(ctx: Ctx):
    got = _got(ctx)
    comf, comp = got.get("comfortable") or [], got.get("compact") or []
    ctx.check(f"comfortable by default: --pad 14px, a 4 px gutter, a 36 px title line, 14 px text, got {comf}", comf == ["comfortable", "14px", "4px", 36, "14px"])
    ctx.check(f"the toggle: compact, --pad 9px, a 2 px gutter, a 30 px title line, 13 px text, got {comp} {got.get('toggle_title')!r}",
              comp == ["compact", "9px", "2px", 30, "13px"] and got.get("toggle_title") == "Density: comfortable (press for compact)")
    ctx.check(f"remembered across a reload, got {got.get('saved')} {got.get('reload')}", got.get("saved") == "compact" and got.get("reload") == comp)
    ctx.check(f"the palette's Density: comfortable, got {got.get('palette')} {got.get('saved_after')}",
              got.get("palette") == comf and got.get("saved_after") == "comfortable")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
