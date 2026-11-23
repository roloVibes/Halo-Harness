"""tests.test_studio_live_fold -- Halo 3.6.0.15 LW, rules L9a and L9b ("fold and lanes") as a person sees them, in headless
Chrome (tests/helpers/studio_live_fold_steps.py; on the Linux VM, never on the owner's PC). No model is called. The tests
assert the rules, never the scenes' pixel figures: the zoom and the view are read from the page.

L9a
1. Agents -> Live on Auto: each group stands 96 x zoom right of main and is max(352, min(760, floor(view / zoom - 392)))
   wide; when view / zoom >= 744 the drawing does not scroll sideways; with the pointer resting on the drawing the window
   narrows and no group moves; the pointer leaves and every group takes the new width.
L9b
2. A group of four lays three a row when (inner - 16) / 3 >= 200 (inner = its width / zoom - 24), each member
   floor((inner - 16) / 3) wide, the fourth on the next row; narrower, two a row; Session's drawer one or two a row.
Run: python -m tests.test_studio_live_fold
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUNS: dict = {}


def _ran(ctx: Ctx, key: str) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the drawings need headless Chrome)")
    if not _RUNS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_live_fold_steps"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=600, env=driver_env(REPO), cwd=str(REPO))
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {}
        _RUNS.update(r=r, got=got)
    if _RUNS["got"].get("skip"):
        raise SkipTest(_RUNS["got"]["skip"])
    r, got = _RUNS["r"], _RUNS["got"]
    ctx.check(f"the driver reached {key}, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", got.get(key) is not None)
    return got.get(key) or {}


def _want(geo: dict) -> int:
    """L9a's column width for the view and zoom the page shows."""
    z = geo.get("zoom") or 1
    return max(352, min(760, math.floor((geo.get("view") or 0) / z - 392)))


def _in_world(geo: dict) -> dict:
    """Each group's place and size inside the drawing (its rect against the world's), so a move of the frame is not one."""
    wx, wy = (geo.get("world") or [0, 0])[:2]
    return {n: [round(g["rect"][0] - wx, 1), round(g["rect"][1] - wy, 1), round(g["rect"][2], 1), round(g["rect"][3], 1)]
            for n, g in (geo.get("groups") or {}).items() if g.get("rect")}


def _lanes_ok(ctx: Ctx, geo: dict, label: str) -> None:
    z, gs, main = geo.get("zoom") or 1, geo.get("groups") or {}, geo.get("main") or [0, 0, 0, 0]
    want = _want(geo)
    ctx.check(f"{label}: three groups drawn, got {sorted(gs)}", len(gs) == 3)
    for n, g in gs.items():
        r = g.get("rect") or [0, 0, 0, 0]
        ctx.check(f"{label}: group {n} stands 96 x zoom ({96 * z}) right of main, got {r[0] - (main[0] + main[2])}",
                  abs(r[0] - (main[0] + main[2]) - 96 * z) <= 1)
        ctx.check(f"{label}: group {n} is max(352, min(760, floor(view / zoom - 392))) = {want} wide (view {geo.get('view')}, "
                  f"zoom {z}), got {r[2] / z}", abs(r[2] / z - want) <= 1)
    if (geo.get("view") or 0) / z >= 744:
        ctx.check(f"{label}: view / zoom >= 744: no sideways scroll, got scrollWidth {geo.get('sw')} clientWidth {geo.get('view')}",
                  (geo.get("sw") or 0) <= (geo.get("view") or 0) + 1)


@test
def test_auto_lane_96_and_the_group_column(ctx: Ctx):
    d = _ran(ctx, "lanes")
    ctx.check("the groups took L9a's width at 1440 x 900", d.get("settled") is True)
    _lanes_ok(ctx, d.get("wide") or {}, "1440 x 900")
    before, after = [x or {} for x in ((d.get("resting") or []) + [{}, {}])[:2]]
    ctx.check(f"the pointer rests on the drawing (held), got {before.get('held')!r} then {after.get('held')!r}",
              before.get("held") == "1" and after.get("held") == "1")
    ctx.check(f"the view narrowed while it rested, got {before.get('view')} -> {after.get('view')}",
              (after.get("view") or 1e9) < (before.get("view") or 0))
    ctx.check(f"no group moved or changed its size while the pointer rested, got {_in_world(before)} -> {_in_world(after)}",
              bool(_in_world(before)) and _in_world(before) == _in_world(after))
    narrow = d.get("narrow") or {}
    ctx.check("the pointer left: every group took the new width", d.get("settled_narrow") is True)
    ctx.check(f"the new width differs from the first (the window really narrowed), got {_want(d.get('wide') or {})} -> {_want(narrow)}",
              _want(narrow) != _want(d.get("wide") or {}))
    _lanes_ok(ctx, narrow, "1100 x 800, the pointer off")


def _rows_ok(ctx: Ctx, geo: dict, label: str) -> bool:
    """L9b on the page: the four-member group's per and its members' rects against its own measured width; returns
    whether it is three a row."""
    z = geo.get("zoom") or 1
    g = next((x for x in (geo.get("groups") or {}).values() if len(x.get("members") or []) == 4), None)
    ctx.check(f"{label}: a group of four members drawn, got {geo.get('groups')}", g is not None)
    if not g:
        return False
    inner = g["rect"][2] / z - 24
    third = (inner - 16) / 3
    per = 3 if third >= 200 else 2 if (inner - 8) / 2 >= 160 else 1
    ms = g["members"]
    ctx.check(f"{label}: data-per {per} for inner {inner}, got {g.get('per')!r}", g.get("per") == str(per))
    if per == 3:
        ctx.check(f"{label}: each member floor((inner - 16) / 3) = {math.floor(third)} wide, got {[m[2] / z for m in ms]}",
                  all(abs(m[2] / z - math.floor(third)) <= 1 for m in ms))
        ctx.check(f"{label}: the first three share one top, the fourth starts the next row, got {[m[1] for m in ms]}",
                  abs(ms[0][1] - ms[1][1]) <= 0.5 and abs(ms[0][1] - ms[2][1]) <= 0.5 and ms[3][1] > ms[0][1] + 1)
    elif per == 2:
        ctx.check(f"{label}: two a row: the first two share a top, the third is lower, got {[m[1] for m in ms]}",
                  abs(ms[0][1] - ms[1][1]) <= 0.5 and ms[2][1] > ms[0][1] + 1)
    return per == 3


@test
def test_a_group_lays_three_a_row(ctx: Ctx):
    d = _ran(ctx, "three")
    ctx.check("the groups took L9a's width at 1440 x 900", d.get("settled") is True)
    ctx.check("at 1440 x 900 the group of four lays three a row", _rows_ok(ctx, d.get("wide") or {}, "1440 x 900"))
    ctx.check("narrower (1000 x 800), the groups took the new width", d.get("settled_narrow") is True)
    ctx.check("at 1000 x 800 (inner - 16) / 3 < 200: not three a row", not _rows_ok(ctx, d.get("narrow") or {}, "1000 x 800"))
    per = d.get("session")
    ctx.check(f"Session's drawer at its default width: every group one or two a row, got {per}",
              bool(per) and all(p in ("1", "2") for p in per))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
