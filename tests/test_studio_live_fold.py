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
L8
3. In Session's drawer and in Agents -> Live: a group whose members all ended before the page loaded is folded to its head
   at the first draw (its members hidden, its box its head + 24); a failed or a stopped member keeps a group open; with
   the pointer resting on the drawing nothing folds or moves; the pointer off, the group folds and the one under it
   moves up; an open sheet holds the fold until it closes; a member joining a folded group opens it, its earlier members
   at the heights they had, with one HAND ring; the slot never names a folded group.
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


def _folded(r: dict) -> list:
    return [n for n, g in (r.get("groups") or {}).items() if g.get("folded")]


def _places(r: dict, ns: list) -> dict:
    gs = r.get("groups") or {}
    return {"main": r.get("main"), **{n: [gs.get(n, {}).get(k) for k in ("top", "left", "h")] for n in ns}}


def _fold_ok(ctx: Ctx, d: dict, view: str) -> None:
    first, d_open, resting, left = (d.get(k) or {} for k in ("first", "d_open", "resting", "left"))
    g = lambda r, n: (r.get("groups") or {}).get(str(n)) or {}  # noqa: E731
    # (a) the first draw
    a = g(first, 1)
    ctx.check(f"{view} (a): A, all done before the page loaded, folded from the first draw; the others open, got {_folded(first)}",
              _folded(first) == ["1"])
    ctx.check(f"{view} (a): every member of A has a zero rect, got {a.get('members')}",
              bool(a.get("members")) and all(m["w"] == 0 and m["rh"] == 0 for m in a["members"].values()))
    ctx.check(f"{view} (a): A's head reads its all-done line, got {a.get('counts')!r}", "all done" in str(a.get("counts")))
    ctx.check(f"{view} (a): A's box is its head + 24 tall, got {a.get('h')} for a head of {a.get('head')}",
              abs((a.get("h") or 0) - (a.get("head") or 0) - 24) <= 1.5)
    ctx.check(f"{view} (a): every member of B, C, D, E, F drawn, got {[(n, x['members']) for n, x in (first.get('groups') or {}).items() if n != '1']}",
              all(m["w"] > 0 and m["rh"] > 0 for n, x in (first.get("groups") or {}).items() if n != "1" for m in x["members"].values()))
    # (b) the pointer rests on the drawing while D's last member ends and 11 s pass; then it leaves
    ctx.check(f"{view} (b): d2 ended (raw done) and D is still open while the pointer rests, got {g(resting, 2)}",
              (g(resting, 2).get("members") or {}).get("d2", {}).get("raw") == "done" and not g(resting, 2).get("folded"))
    ns = ["1", "2", "3", "4", "5", "6"]
    ctx.check(f"{view} (b): nothing moved while the pointer rested, got {_places(d_open, ns)} -> {_places(resting, ns)}",
              _places(d_open, ns) == _places(resting, ns))
    dl = g(left, 2)
    ctx.check(f"{view} (b): the pointer left: D folded, got {d.get('d_folded')} {_folded(left)}", d.get("d_folded") is True and dl.get("folded"))
    ctx.check(f"{view} (b): D's box is its head + 24 tall, its members hidden, got {dl.get('h')} {dl.get('head')} {dl.get('members')}",
              abs((dl.get("h") or 0) - (dl.get("head") or 0) - 24) <= 1.5 and all(m["rh"] == 0 for m in (dl.get("members") or {}).values()))
    ctx.check(f"{view} (b): F under D moved up, got {g(resting, 3).get('top')} -> {g(left, 3).get('top')}",
              (g(left, 3).get("top") or 0) < (g(resting, 3).get("top") or 0))
    ctx.check(f"{view} (b): nothing above D moved, got {_places(resting, ['1'])} -> {_places(left, ['1'])}",
              _places(resting, ["1"]) == _places(left, ["1"]))
    # (c) a sheet open: E's member ends, E stays open; the sheet closed: E folds
    sh = d.get("sheet") or {}
    ctx.check(f"{view} (c): the sheet opened on b1 and is open 11 s after e1 ended, got {d.get('sheet_opened')} {sh.get('sheet')}",
              d.get("sheet_opened") is True and sh.get("sheet") is True)
    ctx.check(f"{view} (c): E open while the sheet is open, got {g(sh, 6)}",
              (g(sh, 6).get("members") or {}).get("e1", {}).get("raw") == "done" and not g(sh, 6).get("folded"))
    ctx.check(f"{view} (c): the sheet closed by Escape: E folds, got {d.get('closed')} {d.get('e_folded')}",
              d.get("closed") is True and d.get("e_folded") is True)
    # (d) a member joins D (drawn open, then folded): back at the heights read before the fold, one HAND ring
    before, after = d.get("d_before") or {}, d.get("d_after") or {}
    hs = {k: m["h"] for k, m in (g(d_open, 2).get("members") or {}).items()}
    back = {k: m["h"] for k, m in (g(after, 2).get("members") or {}).items() if k in hs}
    ctx.check(f"{view} (d): D opened when d3 joined, got {d.get('d_opened')} {_folded(after)}", d.get("d_opened") is True and not g(after, 2).get("folded"))
    ctx.check(f"{view} (d): D's earlier members have the heights read before the fold, got {hs} -> {back}",
              bool(hs) and set(back) == set(hs) and all(abs(back[k] - hs[k]) <= 1 for k in hs))
    ctx.check(f"{view} (d): D rang HAND once, got {g(before, 2).get('rang')!r} -> {g(after, 2).get('rang')!r}",
              int(g(after, 2).get("rang") or 0) == int(g(before, 2).get("rang") or 0) + 1)
    rang = lambda r, n: {k: m["rang"] for k, m in (g(r, n).get("members") or {}).items()}  # noqa: E731
    ctx.check(f"{view} (d): no member hidden by the fold rang, got D {rang(before, 2)} -> {rang(after, 2)}, A {rang(after, 1)}",
              all(rang(after, 2).get(k) == v for k, v in rang(before, 2).items()) and not any(rang(d.get("a_after") or {}, 1).get(k) for k in ("a1", "a2")))
    aa = g(d.get("a_after") or {}, 1)
    ctx.check(f"{view} (d): a member joining A opens it and draws every member, got {d.get('a_opened')} {aa.get('members')}",
              d.get("a_opened") is True and not aa.get("folded") and len(aa.get("members") or {}) == 3
              and all(m["w"] > 0 and m["rh"] > 0 for m in aa["members"].values()))
    # (e) the slot never names a folded group
    reads = [d.get(k) or {} for k in ("first", "d_open", "resting", "left", "sheet", "after_sheet", "d_before", "d_after", "a_after")]
    ctx.check(f"{view} (e): the slot's group is never a folded one, got {[(r.get('slot'), _folded(r)) for r in reads]}",
              all(r.get("slot") is None or r.get("slot") not in _folded(r) for r in reads))


@test
def test_an_all_done_group_folds_after_the_hold(ctx: Ctx):
    """L8 (with R1 and the coordinator's rulings): Session's drawer, then Agents -> Live."""
    d = _ran(ctx, "groupfold")
    for view in ("session", "live"):
        ctx.check(f"the driver read {view}", bool(d.get(view)))
        _fold_ok(ctx, d.get(view) or {}, view)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
