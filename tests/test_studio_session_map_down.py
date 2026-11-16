"""tests.test_studio_session_map_down -- which session Session's Live drawer draws, and that it holds still (Halo
3.6.0.2 "Session map", R1 R2 R4 R5; headless Chrome through tests/helpers/studio_session_map_down.py, skipped without
one; the pure pick, routes/session/pick.ts, in node through tests/helpers/node_ts.py, anywhere).

1. the drawer draws the session chosen in Session (the one Cost speaks of), never "the first on a map";
2. once drawn, it stays drawn while another session gets a turn;
3. across three turns the map, its boxes, the head line and its place never change; main is lit only in a turn;
4. a terminal session that has had no turn yet is drawn;
5. a Studio-started session with no message yet is never picked while another is open and sorts last; when the
   session drawn ends it reads T8; alone, the Studio one reads T10 with no drawing and no map fetched.
Run: python -m tests.test_studio_session_map_down
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
PICK = REPO / "halo_harness" / "studio" / "ui" / "src" / "routes" / "session" / "pick.ts"
_RUN: dict = {}


def _driver() -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Live drawer needs headless Chrome)")
    if not _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_session_map_down"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN.update(r=r, got=info)
    if _RUN["got"].get("skip"):
        raise SkipTest(_RUN["got"]["skip"])
    return _RUN["got"]


def _ran(ctx: Ctx, got: dict, key: str) -> dict:
    r = _RUN["r"]
    ctx.check(f"the driver reached {key}, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", key in got)
    return got[key]


def _b() -> str:
    from tests.helpers.studio_session import FAKE_SID
    return FAKE_SID


@test
def test_the_map_follows_the_selected_session(ctx: Ctx):
    got = _driver()
    f = _ran(ctx, got, "follows")
    b = _b()
    ctx.check(f"R1: B chosen in Session is the session drawn (not the newest on a map), got {f}",
              f.get("sid") == b and f.get("map") == "starter")
    ctx.check(f"R1: the drawer and Cost speak of one session, got {f.get('sid')!r} and {f.get('cost')!r}", f.get("cost") == f.get("sid") == b)


@test
def test_pick_is_kept_when_another_gets_a_turn(ctx: Ctx):
    got = _driver()
    k = _ran(ctx, got, "kept")
    x = (k[0] if k else {}).get("sid")
    ctx.check(f"R1: with neither busy the newest open session is drawn, got {k[:1]}", bool(x) and (k[0].get("map") is not None))
    ctx.check(f"R1: the same session before, during and after the other's turn, Cost with it, got {[(s.get('sid'), s.get('cost')) for s in k]}",
              len(k) == 3 and all(s.get("sid") == x and s.get("cost") == x for s in k))


@test
def test_three_turns_the_map_and_its_line_never_change(ctx: Ctx):
    got = _driver()
    snaps = _ran(ctx, got, "turns")
    during = got.get("turns_during") or []
    keys = ("map", "boxes", "line", "top")
    first = {k: (snaps[0] if snaps else {}).get(k) for k in keys}
    ctx.check(f"R2: an open session between turns is drawn with its head line, got {snaps[:1]}",
              bool(first["map"]) and bool(first["boxes"]) and bool(first["line"]))
    ctx.check(f"R2: map, boxes, head line and its top equal across the 4 snapshots, got {[{k: s.get(k) for k in keys} for s in snaps]}",
              len(snaps) == 4 and all({k: s.get(k) for k in keys} == first for s in snaps))
    ctx.check(f"R2: main working in each turn, not between, got {[s.get('main') for s in during]} / {[s.get('main') for s in snaps]}",
              len(during) == 3 and all(s.get("main") == "working" for s in during) and all(s.get("main") != "working" for s in snaps))


@test
def test_terminal_session_with_no_turn_is_drawn(ctx: Ctx):
    got = _driver()
    n = _ran(ctx, got, "noturn")
    b = _b()
    ctx.check(f"R2: a terminal session with no turn, not busy, is drawn, got {n}",
              n.get("sid") == b and n.get("map") is not None and len(n.get("boxes") or []) >= 1)


PICK_JS = """const m = await import(%s);
const S = {session_id: 'S', parent: 'studio:123', turns: 0, started: 200};
const T = {session_id: 'T', parent: null, turns: 0, started: 100};
const U = {session_id: 'U', parent: null, turns: 3, started: 50};
console.log(JSON.stringify({
  two: m.livePick([S, T], '')?.session_id, order: m.openOrder([S, T, U]).map((r) => r.session_id),
  alone: m.livePick([S], '')?.session_id, asked: m.isStudioIdle({parent: 'studio:1', turns: 1}),
  cleared: m.isStudioIdle({parent: 'studio:1', turns: 0, asked: true}), idle: m.isStudioIdle(S), term: m.isStudioIdle(T),
  picked: m.livePick([S, T, U], 'U')?.session_id, none: m.livePick([], ''),
}));"""


@test
def test_studio_unasked_session_named_never_chosen(ctx: Ctx):
    from tests.helpers import node_ts
    ctx.check(f"routes/session/pick.ts exists, got {PICK.exists()}", PICK.exists())
    try:  # (a) runs wherever node can run a .ts; (b) still runs where it cannot (Debian's node, an exported tree)
        p = node_ts.run(PICK_JS % json.dumps(PICK.resolve().as_uri()))
    except SkipTest as e:
        p, node_skip = None, str(e)
    if p is not None:
        node_skip = ""
        ctx.check(f"R5 (a): a Studio session with no turn is not picked while a terminal one is open, got {p.get('two')!r}", p.get("two") == "T")
        ctx.check(f"R5 (a): it sorts last (else newest first), got {p.get('order')}", p.get("order") == ["T", "U", "S"])
        ctx.check(f"R1 (a): alone it is the pick, got {p.get('alone')!r}", p.get("alone") == "S")
        ctx.check(f"R5 (a): one with a turn (or a cleared one, asked) is not T10; a terminal one never is, got {p}",
                  p.get("asked") is False and p.get("cleared") is False and p.get("idle") is True and p.get("term") is False)
        ctx.check(f"R1 (a): the pick wins while it is open; nothing open is no pick, got {p.get('picked')!r} {p.get('none')!r}",
                  p.get("picked") == "U" and p.get("none") is None)
    try:
        got = _driver()
    except SkipTest as e:
        raise SkipTest(f"(a) {'passed' if not node_skip else node_skip}; (b) {e}")
    first, ended, alone = (_ran(ctx, got, k) for k in ("studio_first", "studio_ended", "studio_alone"))
    b = _b()
    ctx.check(f"R5 (b): with a terminal session open the Studio one is not drawn, got {first}", first.get("sid") and first.get("sid") != b)
    ctx.check(f"R4: the session drawn ended: T8 until another is picked, not a move to another, got {ended}",
              ended.get("state") == "T8" and ended.get("sid") == first.get("sid") and str(ended.get("line")).startswith("This session ended at ")
              and not ended.get("boxes"))
    from tests.helpers.studio_session_map_down import T10_SHOP
    ctx.check(f"R5 (b): alone, the Studio one reads T10 with {{B}} filled, no box, got {alone}",
              alone.get("sid") == b and alone.get("state") == "T10" and alone.get("line") == T10_SHOP and not alone.get("boxes"))
    ctx.check(f"R28: no GET crew/map for T10, got {got.get('studio_map_reads')}", got.get("studio_map_reads") == 0)
    if node_skip:
        raise SkipTest(f"(b) passed; (a) {node_skip}")


UNLISTED_JS = """const m = await import(%s);
const T = {session_id: 'TERM', parent: null, turns: 4, started: 100};
const N = {session_id: 'NEW', parent: 'studio:1', turns: 0, started: 300};
console.log(JSON.stringify({
  before: m.livePick([T], 'NEW')?.session_id ?? null, listed: m.livePick([T, N], 'NEW')?.session_id ?? null,
  stale: m.livePick([T], 'GONE-LONG-AGO')?.session_id ?? null, unpicked: m.livePick([T], '')?.session_id ?? null,
}));"""


@test
def test_a_pick_not_listed_yet_is_never_another_session(ctx: Ctx):
    # New session: openSession({session: id}) picks an id that registers a moment later. Until it is listed, Prompt, Cost
    # and the Live drawer (all chosenSession = livePick) must speak of no session, never send to the terminal one.
    from tests.helpers import node_ts
    p = node_ts.run(UNLISTED_JS % json.dumps(PICK.resolve().as_uri()))
    ctx.check(f"R1: a pick not listed yet is no session (not the open terminal one), got {p.get('before')!r}", p.get("before") is None)
    ctx.check(f"R1: once it registers it is the one, got {p.get('listed')!r}", p.get("listed") == "NEW")
    ctx.check(f"R1: a pick this page never saw is still never another session, got {p.get('stale')!r}", p.get("stale") is None)
    ctx.check(f"R1: with no pick the newest open one is the default, got {p.get('unpicked')!r}", p.get("unpicked") == "TERM")



# -- 3.6.0.2 batch 2: the drawing top to bottom, readable, never cut, held still (R7 R10 R11 R12) ------------------------
FIT = REPO / "halo_harness" / "studio" / "ui" / "src" / "routes" / "session" / "downFit.ts"
_DRAW: dict = {}


def _draw() -> dict:
    """tests/helpers/studio_session_map_down_draw.py, run once for the tests below."""
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Live drawer needs headless Chrome)")
    if not _DRAW:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_session_map_down_draw"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=560, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _DRAW.update(r=r, got=info)
    if _DRAW["got"].get("skip"):
        raise SkipTest(_DRAW["got"]["skip"])
    return _DRAW["got"]


def _drew(ctx: Ctx, key: str):
    got = _draw()
    r = _DRAW["r"]
    ctx.check(f"the driver reached {key}, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", got.get(key) is not None)
    return got.get(key) or {}


def _rows(boxes: list) -> list:
    """Boxes [id, x, y, w, h] grouped by top (within 2 px), top to bottom."""
    rows: list = []
    for b in sorted(boxes, key=lambda b: b[2]):
        if rows and abs(rows[-1][0][2] - b[2]) <= 2:
            rows[-1].append(b)
        else:
            rows.append([b])
    return rows


def _overlap(boxes: list) -> list:
    return [(p[0], q[0]) for i, p in enumerate(boxes) for q in boxes[i + 1:]
            if p[1] < q[1] + q[3] - 0.5 and q[1] < p[1] + p[3] - 0.5 and p[2] < q[2] + q[4] - 0.5 and q[2] < p[2] + p[4] - 0.5]


@test
def test_two_per_row_at_1280_with_gutter(ctx: Ctx):
    p = _drew(ctx, "pair")
    boxes, z = p.get("boxes") or [], p.get("zoom") or 0
    main = next((b for b in boxes if b[0] == "main"), None)
    ctx.check(f"R7: drawn down (data-dir), got {p.get('dir')!r} on {p.get('map')!r}", p.get("dir") == "down" and p.get("map") == "seven")
    ctx.check(f"R7: main + 7 drawn, got {[b[0] for b in boxes]}", len(boxes) == 8 and main is not None)
    if not main:
        return
    ctx.check(f"R7: main alone on row 0 and every other box below it, got {boxes}",
              all(b[2] >= main[2] + main[4] - 0.5 for b in boxes if b is not main))
    rows = _rows(boxes)
    cw = p.get("cw") or 0
    ctx.check(f"R7: at most two boxes a row, two when clientWidth {cw} >= 400, got {[[b[0] for b in r] for r in rows]}",
              max(len(r) for r in rows) <= 2 and (cw < 400 or any(len(r) == 2 for r in rows)))
    ctx.check(f"R7: every box 184 px wide x zoom {z}, got {[round(b[3], 1) for b in boxes]}", all(abs(b[3] - 184 * z) <= 0.5 for b in boxes))
    ctx.check(f"R7: scrollbar-gutter stable, got {p.get('gutter')!r}", p.get("gutter") == "stable")
    ctx.check(f"R7: the scroll box's clientWidth at 1280 x 800 is 400..429, got {cw}", 400 <= cw <= 429)
    ctx.check(f"R7: nothing sideways (scrollWidth {p.get('sw')} <= clientWidth {cw})", (p.get("sw") or 9999) <= cw)


@test
def test_long_name_wraps_never_ellipsis(ctx: Ctx):
    from tests.helpers.studio_session_map_down_draw import CMD, LONG
    d = _drew(ctx, "long")
    css = d.get("css") or []
    ctx.check(f"R10: the whole name, no '...', got {d.get('name')!r}", d.get("name") == LONG)
    ctx.check(f"R10: names and rows wrap anywhere, no ellipsis, no line clamp, got {css}",
              len(css) >= 2 and all(c[0] == "anywhere" and c[1] != "ellipsis" and c[2] in ("none", "") for c in css))
    ctx.check(f"R10: the name wraps, not clipped (scrollWidth {d.get('name_sw')} <= clientWidth {d.get('name_cw')} + 1)",
              d.get("name_sw") is not None and d["name_sw"] <= d["name_cw"] + 1)
    z = d.get("zoom") or 1
    ctx.check(f"R10: the box holds its words (rect {d.get('h')} >= content {d.get('sh')} x {z})", (d.get("h") or 0) >= (d.get("sh") or 9e9) * z - 0.5)
    ctx.check(f"R10: no two boxes overlap, got {_overlap(d.get('boxes') or [])}", not _overlap(d.get("boxes") or []) and len(d.get("boxes") or []) >= 2)
    ctx.check(f"R10: the whole 80-character command in the row, got {d.get('rows')}", any(CMD in r for r in d.get("rows") or []))


def _cut(d: dict) -> tuple:
    """(boxes crossing the scroll box's top or bottom edge, boxes wholly below it)."""
    x, y, w, h = d.get("sc") or [0, 0, 0, 0]
    crossed, below = [], []
    for b in d.get("boxes") or []:
        top, bottom = b[2], b[2] + b[4]
        if top >= y + h - 0.5:
            below.append(b[0])
        elif bottom > y + 0.5 and (top < y - 0.5 or bottom > y + h + 0.5):
            crossed.append(b[0])
    return crossed, below


@test
def test_no_box_cut_at_rest(ctx: Ctx):
    from tests.helpers.studio_session_map_down_draw import MORE
    seen = _drew(ctx, "cut")
    ctx.check(f"R11: seven drawings measured, got {len(seen) if isinstance(seen, list) else seen}", isinstance(seen, list) and len(seen) == 7)
    pressed = 0
    for one in seen if isinstance(seen, list) else []:
        where, d = f"{one['size']} {one['map']}", one.get("before") or {}
        crossed, below = _cut(d)
        ctx.check(f"R11 {where}: drawn, no box cut at rest, got crossed {crossed}, boxes {d.get('boxes')}, scroll {d.get('sc')}",
                  bool(d.get("boxes")) and not crossed)
        ctx.check(f"R11 {where}: the boxes below are counted, got {d.get('below')!r} for {below}",
                  d.get("below") == (MORE % len(below) if below else ""))
        a = one.get("after")
        if a:
            pressed += 1
            rows = _rows(d.get("boxes") or [])
            nxt = rows[1][0][0] if len(rows) > 1 else None
            top = next((b[2] for b in a.get("boxes") or [] if b[0] == nxt), None)
            ctx.check(f"R11 {where}: a press brings the next row ({nxt}) to the scroll box's top, got {top} vs {(a.get('sc') or [0, 0])[1]}",
                      top is not None and abs(top - a["sc"][1]) <= 1)
            ctx.check(f"R11 {where}: after the press no box is cut, got {_cut(a)[0]}", not _cut(a)[0])
            ctx.check(f"R11 {where}: the slot holds still, got {d.get('slot')} / {a.get('slot')}", _same(d.get("slot"), a.get("slot")))
    ctx.check(f"R11: at least one drawing had boxes below and was pressed, got {pressed}", pressed >= 1)


def _same(p, q, tol: float = 0.5) -> bool:
    return bool(p) and bool(q) and len(p) == len(q) and all(abs(a - b) <= tol for a, b in zip(p, q))


@test
def test_nothing_moves_under_the_pointer(ctx: Ctx):
    h = _drew(ctx, "hold")
    rest = {b[0]: b[1:] for b in (h.get("rest") or {}).get("boxes") or []}
    under = h.get("under") or []
    moved = [(i, k) for i, s in enumerate(under) for k in set(rest) | set(s) if not _same(rest.get(k), s.get(k))]
    ctx.check(f"R12: the drawing at rest before the pointer came, got {sorted(rest)}", len(rest) >= 7)
    ctx.check(f"R12: 3 s under the pointer with a new box and new words: nothing moved, nothing arrived, got {moved[:6]}",
              len(under) == 12 and not moved)
    ctx.check(f"R12: the pointer left: the new box drawn within 2 s, got {h.get('arrived_s')}", h.get("arrived_s") is not None)
    s, k = h.get("scrolled") or {}, h.get("kept") or {}
    ctx.check(f"R12: scrolled by hand so a row under main's is first, got {s}", s.get("first") not in (None, "main") and (s.get("st") or 0) > 0)
    ctx.check(f"R12: a box arriving above keeps the first box seen in its place, got {s} -> {k}",
              k.get("top") is not None and s.get("top") is not None and abs(k["top"] - s["top"]) <= 1)


@test
def test_button_and_card_hold_still(ctx: Ctx):
    s = _drew(ctx, "still")
    first, frames = s.get("first") or {}, s.get("frames") or []
    head = first.get("head") or []
    ctx.check(f"R42: Fit hidden while fitted, its slot kept, got {first.get('fit')!r} {head}",
              first.get("fit") == "hidden" and len(head) == 5 and bool(head[4]) and head[4][2] > 0)
    ctx.check(f"R12: zoom and new words over 20 frames, got zooms {[f.get('zoom') for f in frames]}",
              len(frames) == 20 and len({f.get("zoom") for f in frames}) >= 2)
    bad = [(i, j) for i, f in enumerate(frames) for j, r in enumerate(f.get("head") or []) if j >= len(head) or not _same(r, head[j])]
    ctx.check(f"R12: the link, -, %, + and Fit keep their rects, got (frame, button) {bad[:6]}", not bad and len(head) == 5 and all(head))
    ctx.check(f"R12: the slot keeps its rect, got {[f.get('slot') for f in frames if not _same(f.get('slot'), first.get('slot'))][:3]}",
              all(_same(f.get("slot"), first.get("slot")) for f in frames))


FIT_JS = """const m = await import(%s);
const rows = [{top: 12, bottom: 68}, {top: 96, bottom: 152}, {top: 168, bottom: 224}, {top: 252, bottom: 308}];
const boxes = [{id: 'main', y: 12, h: 56}, {id: 'a', y: 96, h: 56}, {id: 'b', y: 96, h: 56}, {id: 'c', y: 168, h: 56}, {id: 'd', y: 252, h: 56}];
console.log(JSON.stringify({
  rows: m.rowsOf(boxes), all: m.viewHeight(rows, 1, 0, 400), part: m.viewHeight(rows, 1, 0, 250), none: m.viewHeight(rows, 1, 0, 40),
  from96: m.viewHeight(rows, 1, 96, 250), below: m.belowCount(boxes, 1, 0, 236), next0: m.nextTop(rows, 1, 0), next96: m.nextTop(rows, 1, 96),
  last: m.nextTop(rows, 1, 252), seen: m.firstSeen(boxes, 1, 100), kept: m.keepSeen([{id: 'a', y: 168, h: 56}], 1, {id: 'a', off: -4}),
}));"""


@test
def test_rest_height_counts_whole_rows(ctx: Ctx):
    # R11's arithmetic (routes/session/downFit.ts) in node, anywhere: the scroll box ends under the last whole row + 12
    from tests.helpers import node_ts
    ctx.check(f"routes/session/downFit.ts exists, got {FIT.exists()}", FIT.exists())
    p = node_ts.run(FIT_JS % json.dumps(FIT.resolve().as_uri()))
    ctx.check(f"rows by top, got {p.get('rows')}", p.get("rows") == [{"top": 12, "bottom": 68}, {"top": 96, "bottom": 152},
                                                                      {"top": 168, "bottom": 224}, {"top": 252, "bottom": 308}])
    ctx.check(f"R11: all whole: 308 + 12, got {p.get('all')}", p.get("all") == 320)
    ctx.check(f"R11: room 250: the third row's bottom + 12, got {p.get('part')}", p.get("part") == 236)
    ctx.check(f"R11: no row fits: the whole room, got {p.get('none')}", p.get("none") == 40)
    ctx.check(f"R11: counted from the row at the top, got {p.get('from96')}", p.get("from96") == 224)
    ctx.check(f"R11: one box wholly below, got {p.get('below')}", p.get("below") == 1)
    ctx.check(f"R11: a press scrolls one row, got {p.get('next0')} {p.get('next96')} {p.get('last')}",
              p.get("next0") == 96 and p.get("next96") == 168 and p.get("last") is None)
    ctx.check(f"R12: the first box seen and its place kept, got {p.get('seen')} {p.get('kept')}",
              p.get("seen") == {"id": "a", "off": -4} and p.get("kept") == 172)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
