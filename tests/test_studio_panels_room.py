"""tests.test_studio_panels_room -- the workspace makes room, in a real browser
(Halo 3.2.2.0 R5; the owner, live in Studio: "When I move the parts in halo
studio over another block like in roles, they disappear. Moving one block
should shrink the ones next to them without things disappearing"). Headless
Chrome through tests/helpers/studio_ui_panels_room.py (skipped without one),
over Roles at its default layout:

1. the default layout: every panel inside the viewport, none over another;
2. the Canvas's east edge dragged three columns left is a splitter: the
   Inspector, Problems and Models column moves left and widens by the same
   three columns, nothing overlaps, nothing leaves the viewport;
3. Arrange (the rail) puts every panel back in its default rectangle;
4. the Inspector's title bar dragged over the Canvas: the Canvas gives up
   columns (it is narrower than before), every panel stays inside the
   viewport, no two overlap, the canvas still draws its cards;
5. Arrange again: the defaults.
Run: python -m tests.test_studio_panels_room
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
DEFAULT = {"roles-lineups": [0, 0, 5, 32], "roles-graph": [5, 0, 13], "roles-inspector": [18, 0, 6, 46], "roles-problems": [18, 46, 6, 20]}


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the workspace room checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_ui_panels_room", "room"], capture_output=True, encoding="utf-8",
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


def _defaults(grid: dict) -> bool:
    return all(grid.get(k, [])[:len(v)] == v for k, v in DEFAULT.items())


@test
def test_the_default_layout_fits_and_nothing_overlaps(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"six panels, got {sorted(got.get('default') or {})}", len(got.get("default") or {}) == 6)
    ctx.check(f"every panel inside the viewport, got {got.get('default_outside')}", got.get("default_outside") == [])
    ctx.check(f"no two overlap, got {got.get('default_overlaps')}", got.get("default_overlaps") == [])


@test
def test_an_edge_resize_moves_the_neighbour(ctx: Ctx):
    got = _got(ctx)
    g = got.get("resize_grid") or {}
    ctx.check(f"the Canvas is three columns narrower, got {g.get('roles-graph')} (by {got.get('resize_by')})", (g.get("roles-graph") or [])[:3] == [5, 0, 10])
    ctx.check(f"the right-hand column starts where the Canvas ends and is three columns wider, got {g}",
              all((g.get(k) or [])[0:1] == [15] and (g.get(k) or [0, 0, 0])[2] == 9 for k in ("roles-inspector", "roles-problems", "roles-models")))
    before, after = (got.get("default") or {}).get("roles-inspector") or {}, (got.get("resized") or {}).get("roles-inspector") or {}
    ctx.check(f"on screen the Inspector moved left and widened, got {before} -> {after}",
              after.get("x", 1e9) < before.get("x", 0) and after.get("w", 0) > before.get("w", 1e9))
    ctx.check(f"nothing overlaps, nothing leaves the viewport, got {got.get('resize_overlaps')} {got.get('resize_outside')}",
              got.get("resize_overlaps") == [] and got.get("resize_outside") == [])


@test
def test_arrange_puts_the_defaults_back(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Arrange: the default rectangles, got {got.get('arranged_grid')}", _defaults(got.get("arranged_grid") or {}))
    ctx.check("on screen too", got.get("arranged") == got.get("default"))
    ctx.check("and after the move, once more", got.get("arranged_again") == got.get("default"))


@test
def test_a_panel_dragged_over_the_canvas_makes_room(ctx: Ctx):
    got = _got(ctx)
    g, d = got.get("move_grid") or {}, got.get("default") or {}
    m = got.get("moved") or {}
    ctx.check(f"the Inspector moved over the Canvas's columns, got {g.get('roles-inspector')} (by {got.get('move_by')})",
              (g.get("roles-inspector") or [24])[0] < 18)
    ctx.check(f"the Canvas gave up columns: narrower than before, got {d.get('roles-graph')} -> {m.get('roles-graph')}",
              0 < (m.get("roles-graph") or {}).get("w", 0) < (d.get("roles-graph") or {}).get("w", 0))
    ctx.check(f"every panel inside the viewport, got {got.get('move_outside')}", got.get("move_outside") == [])
    ctx.check(f"no two overlap, got {got.get('move_overlaps')}", got.get("move_overlaps") == [])
    ctx.check(f"the canvas still draws its cards, got {got.get('canvas_cards')}", (got.get("canvas_cards") or 0) >= 7)


if __name__ == "__main__":
    results, passed, failed, skipped = run_all(TESTS, Ctx())
    sys.exit(print_results(results, passed, failed, skipped))
