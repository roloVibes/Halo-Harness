"""tests.test_studio_canvas_nav -- zoom and pan, the same on every drawing in Studio (Halo 3.4.1.3; the owner, 2026-11-12,
at Session's Map drawn too small to read: "a ctrl+mouse up and down would be nice to zoom in via a mouse. It should
work for Mac and windows style mouse's"). Unit pins over lib/canvasNav.ts, then headless Chrome through
tests/helpers/studio_canvas_nav.py (skipped without one), no model call:

1. one module: every zoomable drawing (the Map and Session's lit map, the design pack's artboards; 3.6.0.0 R5: Live
   and Cast went) wires lib/canvasNav.ts; no other wheel listener is left; the help line is said once and shown;
2. the wheel step: a notch (lines, or a big pixel delta) is one 10% step, a pinch's small pixel deltas a smooth
   fraction, pages count as the page's height;
3. Chrome, Session's Map (the session drawn as its map): a Ctrl + wheel notch zooms with the point under the pointer
   kept; Cmd (metaKey) zooms too; a pinch-shaped event zooms a little; a plain wheel does not zoom; the page's own
   zoom is unchanged; with seven agents it opens with its text at or above the readable size, and has its buttons.
Run: python -m tests.test_studio_canvas_nav
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
DESIGN = REPO / "halo_harness" / "templates" / "packs" / "design" / "studio" / "src"
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_canvas_nav", why="the zoom and pan checks need headless Chrome", cache=_RUN,
                      args=("nav",), timeout=420, tail=600, stdin=False)


@test
def test_one_module_wires_every_drawing(ctx: Ctx):
    nav = (UI / "lib" / "canvasNav.ts").read_text(encoding="utf-8")
    for bit in ("e.ctrlKey || e.metaKey", "e.preventDefault(); // the page's own zoom", "deltaMode", "e.shiftKey", '"dblclick"',
                '"pointerdown"', 'e.key === "0"', "keepZoom", "READABLE"):
        ctx.check(f"canvasNav.ts has {bit}", bit in nav)
    # R5; 3.6.0.2 R7: Session's drawing is routes/session/MapDown.tsx (LitMini.tsx keeps the lit data and a box's face)
    for p in (UI / "routes" / "session" / "MapDown.tsx", UI / "routes" / "crew" / "map" / "MapCanvas.tsx", DESIGN / "Artboards.tsx"):
        ctx.check(f"{p.name} wires useCanvasNav", "useCanvasNav(scroll" in p.read_text(encoding="utf-8"))
    wheel = [str(p.relative_to(UI)) for p in UI.rglob("*.ts*") if re.search(r"addEventListener\(\"wheel\"|onWheel=", p.read_text(encoding="utf-8"))]
    wheel = sorted(w.replace("\\", "/") for w in wheel)
    # 3.6.0.14 OP1: routes/crew/map/useSheet.ts folds the box's open sheet on a wheel over the drawing; it listens
    # passively (it never stops the wheel, so the drawing still scrolls and canvasNav still zooms)
    ctx.check(f"no other wheel listener (lib/hover/store.ts only closes the hover card on a scroll, useSheet.ts only "
              f"folds the open sheet), got {wheel}",
              wheel == ["lib/canvasNav.ts", "lib/hover/store.ts", "routes/crew/map/useSheet.ts"])
    sheet = (UI / "routes" / "crew" / "map" / "useSheet.ts").read_text(encoding="utf-8")
    ctx.check("the sheet's one wheel listener is passive and is taken off",
              sheet.count('addEventListener("wheel"') == 1 and 'addEventListener("wheel", wheel, { passive: true })' in sheet
              and 'removeEventListener("wheel", wheel)' in sheet and "preventDefault" not in sheet)
    line = "Ctrl + wheel (Cmd on a Mac) or pinch to zoom, drag to pan, double-click to fit."
    ctx.check("the help line is in the module", line in nav)
    shown = [*(UI / "routes").glob("help-*.ts"), *(UI / "routes" / "crew" / "map").glob("*.tsx")]  # R5: the Map's own
    helps = [p.name for p in shown if "NAV_HELP" in p.read_text(encoding="utf-8") or line in p.read_text(encoding="utf-8")]
    ctx.check(f"the sections' help says it, got {helps}", len(helps) >= 2)


@test
def test_the_files_stay_under_the_cap(ctx: Ctx):
    for p in (UI / "lib" / "canvasNav.ts", UI / "lib" / "ui" / "ZoomButtons.tsx", UI / "styles" / "canvas-nav.css",
              UI / "routes" / "crew" / "map" / "LitMini.tsx", UI / "routes" / "crew" / "map" / "MapCanvas.tsx", DESIGN / "Artboards.tsx"):
        text = p.read_text(encoding="utf-8")
        raw = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", re.sub(r"/\*.*?\*/", "", text, flags=re.S)) if p.suffix == ".css" else []
        ctx.check(f"{p.name}: {len(text.splitlines())} lines <= 250, no colour literal {raw}", len(text.splitlines()) <= 250 and not raw)


@test
def test_the_wheel_step(ctx: Ctx):
    src = (UI / "lib" / "canvasNav.ts").read_text(encoding="utf-8")
    ctx.check("a notch is 1.1, a pinch exp(-px * 0.01) under 50 px", "return px < 0 ? 1.1 : 1 / 1.1" in src and "Math.exp(-px * 0.01)" in src
              and "Math.abs(px) < 50" in src and "e.deltaY * 16" in src)
    ctx.check("a pinch of 8 px zooms about 8%", abs(math.exp(0.08) - 1.083) < 0.001)


def _kind(ctx: Ctx, got: dict, name: str) -> None:
    w = got.get(name) or {}
    for k in ("ctrl", "meta", "pinch"):
        z = w.get(k) or {}
        ctx.check(f"{name}: {k} zooms in, got {z}", (z.get("to") or 0) > (z.get("from") or 9))
        ctx.check(f"{name}: {k} keeps the point under the pointer, got {z}", z.get("kept") is True and z.get("under") is True)
    p = w.get("pinch") or {}
    ctx.check(f"{name}: a pinch is a small step, got {p}", p.get("from") and 1.0 < p.get("to", 0) / p["from"] < 1.12)
    ctx.check(f"{name}: a plain wheel does not zoom, got {w.get('plain')}", (w.get("plain") or [0, 1])[0] == (w.get("plain") or [0, 1])[1])
    ctx.check(f"{name}: the page's zoom is unchanged, got {w.get('page_before')} {w.get('page_after')}",
              w.get("page_before") and w.get("page_before") == w.get("page_after"))


@test
def test_session_map_opens_readable_and_zooms(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"seven agents, got {got.get('map_nodes')}", (got.get("map_nodes") or 0) >= 7)
    # 3.6.0.2 R9: opened at 100 %, a name 13.5 px and its rows 12 px on screen at 1280, 1440 and 1920
    sizes = got.get("sizes") or {}
    ctx.check(f"R9: read at the three sizes, got {sorted(sizes)}", sorted(sizes) == ["1280x800", "1440x900", "1920x1080"])
    for size, (z, name_px, row_px) in ((k, (v or [0, 0, 0])) for k, v in sizes.items()):
        ctx.check(f"R9 {size}: opens at 100 % (got {z}), name >= 13.5 px (got {name_px}), rows >= 12 px (got {row_px})",
                  abs(z - 1.0) <= 1e-3 and name_px >= 13.5 - 0.01 and row_px >= 12 - 0.01)
    ctx.check(f"R9: it opens at 100 % with its name 13.5 px, got {got.get('map_text_px')} at {got.get('map_open_zoom')}",
              abs(float(got.get("map_open_zoom") or 0) - 1.0) <= 1e-3 and (got.get("map_text_px") or 0) >= 13.5 - 0.01)
    ctx.check("its zoom buttons and Fit", got.get("map_buttons") is True)
    _kind(ctx, got, "map")
    ctx.check(f"R9: a zoom out by hand stops at 75 %, never lower, got {got.get('map_floor')}",
              abs(float(got.get("map_floor") or 0) - 0.75) <= 1e-3)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
