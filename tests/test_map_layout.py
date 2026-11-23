"""tests.test_map_layout -- Halo 3.6.0.2 R6, R7, R8, R14 (the block's place), R45: the map's two layouts, run in node through
tests/helpers/node_ts.py (no browser, no clock).

1. the golden pin: Agents -> Map's `layout()` and `view()` (routes/crew/map/layout.ts, view.ts) give, for the starter map,
   the tiers map and the strip probe, exactly what they gave on the base of 3.6.0.2 (e8c2a3c1). Agents' drawing may not
   move by a pixel: this test is green on the base and stays green;
2. Session's drawing top to bottom (routes/crew/map/layoutDown.ts): main alone on row 0 over the spine, two 184 px boxes a
   row (one under 400 px), a new rank starts a row; lines leave a box's bottom centre, enter the target's top, turn only
   in the bands, run the spine (or the outer pad past a full-width row), never under a box; entries 14 px apart;
3. the boxes no line from main reaches (routes/crew/map/reach.ts) below the last rank, including one fed only by another
   unconnected box;
4. a saved workflow's block: as tall as all its steps; on a full-width row under its caller when it is on no box.
Run: python -m tests.test_map_layout   (HALO_NODE_TS_TRANSPILE=1 runs it the way a node without TypeScript does)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MAPDIR = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "crew" / "map"


def _url(name: str) -> str:
    return json.dumps((MAPDIR / name).resolve().as_uri())


STARTER = {"format": "map/1", "name": "starter", "main": {"agent": "main"},
           "boxes": [{"id": n, "agent": n} for n in ("planner", "researcher", "coder", "reviewer", "writer", "media-reader", "ops")],
           "lines": [{"from": "main", "to": n, "when": "main-decides"}
                     for n in ("planner", "researcher", "coder", "reviewer", "writer", "media-reader", "ops")]}
TIERS = {"format": "map/1", "name": "tiers", "main": {"agent": "main"},
         "boxes": [{"id": "plan", "agent": "planner"}, {"id": "research", "agent": "researcher"}, {"id": "code", "agent": "coder"},
                   {"id": "docs", "agent": "writer"}, {"id": "review", "agent": "reviewer"}, {"id": "check", "workflow": "review"}],
         "lines": [{"from": "main", "to": "plan", "when": "always"}, {"from": "main", "to": "research", "when": "main-decides"},
                   {"from": "plan", "to": "code", "when": "always"}, {"from": "plan", "to": "docs", "when": {"says": ["docs"]}},
                   {"from": "research", "to": "code", "when": "ask"}, {"from": "code", "to": "review", "when": "always"},
                   {"from": "code", "to": "check", "when": "main-decides"}]}
PROBE = {"format": "map/1", "name": "probe", "main": {"agent": "main"},
         "boxes": [{"id": n, "agent": n} for n in ("coder", "reviewer", "tester", "docs", "loose")],
         "lines": [{"from": a, "to": b} for a, b in (("main", "coder"), ("coder", "reviewer"), ("main", "reviewer"),
                                                       ("loose", "tester"), ("main", "docs"))]}
FIXTURES = {"starter": STARTER, "tiers": TIERS, "probe": PROBE}

GOLDEN_JS = """
const L = await import(%s); const V = await import(%s);
const F = %s; const out = {};
for (const [k, f] of Object.entries(F)) {
  const v = V.view(f, [], []);
  out[k] = { view: v, lit: L.layout(v.boxes, v.lines, (b) => L.estimate(b, false, 0) + 20),
             canvas: L.layout(v.boxes, v.lines, (b) => L.estimate(b, false, 0)) };
}
console.log(JSON.stringify(out));
"""

# Recorded on the base of 3.6.0.2 (e8c2a3c1) and never edited: `lit` = Session's height (LitMini.tsx), `canvas` = Agents ->
# Map's height before it measures (MapCanvas.tsx).
GOLDEN = json.loads(
    '{"starter":{"view":{"boxes":[{"id":"main","kind":"agent","name":"main","names":["main"],"main":true},{"id":"pl'
    'anner","kind":"agent","name":"planner","names":["planner"]},{"id":"researcher","kind":"agent","name":"research'
    'er","names":["researcher"]},{"id":"coder","kind":"agent","name":"coder","names":["coder"]},{"id":"reviewer","k'
    'ind":"agent","name":"reviewer","names":["reviewer"]},{"id":"writer","kind":"agent","name":"writer","names":["w'
    'riter"]},{"id":"media-reader","kind":"agent","name":"media-reader","names":["media-reader"]},{"id":"ops","kind'
    '":"agent","name":"ops","names":["ops"]}],"strip":[],"lines":[{"from":"main","to":"planner","when":"main-decide'
    's"},{"from":"main","to":"researcher","when":"main-decides"},{"from":"main","to":"coder","when":"main-decides"}'
    ',{"from":"main","to":"reviewer","when":"main-decides"},{"from":"main","to":"writer","when":"main-decides"},{"f'
    'rom":"main","to":"media-reader","when":"main-decides"},{"from":"main","to":"ops","when":"main-decides"}]},"lit'
    '":{"boxes":[{"id":"main","kind":"agent","name":"main","names":["main"],"main":true,"x":24,"y":24,"h":103,"col"'
    ':0},{"id":"planner","kind":"agent","name":"planner","names":["planner"],"x":484,"y":24,"h":103,"col":1},{"id":'
    '"researcher","kind":"agent","name":"researcher","names":["researcher"],"x":484,"y":155,"h":103,"col":1},{"id":'
    '"coder","kind":"agent","name":"coder","names":["coder"],"x":484,"y":286,"h":103,"col":1},{"id":"reviewer","kin'
    'd":"agent","name":"reviewer","names":["reviewer"],"x":484,"y":417,"h":103,"col":1},{"id":"writer","kind":"agen'
    't","name":"writer","names":["writer"],"x":484,"y":548,"h":103,"col":1},{"id":"media-reader","kind":"agent","na'
    'me":"media-reader","names":["media-reader"],"x":484,"y":679,"h":103,"col":1},{"id":"ops","kind":"agent","name"'
    ':"ops","names":["ops"],"x":484,"y":810,"h":103,"col":1}],"lines":[{"from":"main","to":"planner","when":"main-d'
    'ecides","key":"main>planner","d":"M272 54 H290 V54 H484","lx":298,"ly":24},{"from":"main","to":"researcher","w'
    'hen":"main-decides","key":"main>researcher","d":"M272 54 H290 V185 H484","lx":298,"ly":155},{"from":"main","to'
    '":"coder","when":"main-decides","key":"main>coder","d":"M272 54 H290 V316 H484","lx":298,"ly":286},{"from":"ma'
    'in","to":"reviewer","when":"main-decides","key":"main>reviewer","d":"M272 54 H290 V447 H484","lx":298,"ly":417'
    '},{"from":"main","to":"writer","when":"main-decides","key":"main>writer","d":"M272 54 H290 V578 H484","lx":298'
    ',"ly":548},{"from":"main","to":"media-reader","when":"main-decides","key":"main>media-reader","d":"M272 54 H29'
    '0 V709 H484","lx":298,"ly":679},{"from":"main","to":"ops","when":"main-decides","key":"main>ops","d":"M272 54 '
    'H290 V840 H484","lx":298,"ly":810}],"w":756,"h":937},"canvas":{"boxes":[{"id":"main","kind":"agent","name":"ma'
    'in","names":["main"],"main":true,"x":24,"y":24,"h":83,"col":0},{"id":"planner","kind":"agent","name":"planner"'
    ',"names":["planner"],"x":484,"y":24,"h":83,"col":1},{"id":"researcher","kind":"agent","name":"researcher","nam'
    'es":["researcher"],"x":484,"y":135,"h":83,"col":1},{"id":"coder","kind":"agent","name":"coder","names":["coder'
    '"],"x":484,"y":246,"h":83,"col":1},{"id":"reviewer","kind":"agent","name":"reviewer","names":["reviewer"],"x":'
    '484,"y":357,"h":83,"col":1},{"id":"writer","kind":"agent","name":"writer","names":["writer"],"x":484,"y":468,"'
    'h":83,"col":1},{"id":"media-reader","kind":"agent","name":"media-reader","names":["media-reader"],"x":484,"y":'
    '579,"h":83,"col":1},{"id":"ops","kind":"agent","name":"ops","names":["ops"],"x":484,"y":690,"h":83,"col":1}],"'
    'lines":[{"from":"main","to":"planner","when":"main-decides","key":"main>planner","d":"M272 54 H290 V54 H484","'
    'lx":298,"ly":24},{"from":"main","to":"researcher","when":"main-decides","key":"main>researcher","d":"M272 54 H'
    '290 V165 H484","lx":298,"ly":135},{"from":"main","to":"coder","when":"main-decides","key":"main>coder","d":"M2'
    '72 54 H290 V276 H484","lx":298,"ly":246},{"from":"main","to":"reviewer","when":"main-decides","key":"main>revi'
    'ewer","d":"M272 54 H290 V387 H484","lx":298,"ly":357},{"from":"main","to":"writer","when":"main-decides","key"'
    ':"main>writer","d":"M272 54 H290 V498 H484","lx":298,"ly":468},{"from":"main","to":"media-reader","when":"main'
    '-decides","key":"main>media-reader","d":"M272 54 H290 V609 H484","lx":298,"ly":579},{"from":"main","to":"ops",'
    '"when":"main-decides","key":"main>ops","d":"M272 54 H290 V720 H484","lx":298,"ly":690}],"w":756,"h":797}},"tie'
    'rs":{"view":{"boxes":[{"id":"main","kind":"agent","name":"main","names":["main"],"main":true},{"id":"plan","ki'
    'nd":"agent","name":"planner","names":["planner"]},{"id":"research","kind":"agent","name":"researcher","names":'
    '["researcher"]},{"id":"code","kind":"agent","name":"coder","names":["coder"]},{"id":"docs","kind":"agent","nam'
    'e":"writer","names":["writer"]},{"id":"review","kind":"agent","name":"reviewer","names":["reviewer"]},{"id":"c'
    'heck","kind":"workflow","name":"review","names":["review"]}],"strip":[],"lines":[{"from":"main","to":"plan","w'
    'hen":"always"},{"from":"main","to":"research","when":"main-decides"},{"from":"plan","to":"code","when":"always'
    '"},{"from":"plan","to":"docs","when":{"says":["docs"]}},{"from":"research","to":"code","when":"ask"},{"from":"'
    'code","to":"review","when":"always"},{"from":"code","to":"check","when":"main-decides"}]},"lit":{"boxes":[{"id'
    '":"main","kind":"agent","name":"main","names":["main"],"main":true,"x":24,"y":24,"h":103,"col":0},{"id":"plan"'
    ',"kind":"agent","name":"planner","names":["planner"],"x":484,"y":24,"h":103,"col":1},{"id":"research","kind":"'
    'agent","name":"researcher","names":["researcher"],"x":484,"y":155,"h":103,"col":1},{"id":"code","kind":"agent"'
    ',"name":"coder","names":["coder"],"x":944,"y":24,"h":103,"col":2},{"id":"docs","kind":"agent","name":"writer",'
    '"names":["writer"],"x":944,"y":155,"h":103,"col":2},{"id":"review","kind":"agent","name":"reviewer","names":["'
    'reviewer"],"x":1404,"y":24,"h":103,"col":3},{"id":"check","kind":"workflow","name":"review","names":["review"]'
    ',"x":1404,"y":155,"h":103,"col":3}],"lines":[{"from":"main","to":"plan","when":"always","key":"main>plan","d":'
    '"M272 54 H290 V54 H484","lx":298,"ly":24},{"from":"main","to":"research","when":"main-decides","key":"main>res'
    'earch","d":"M272 54 H290 V185 H484","lx":298,"ly":155},{"from":"plan","to":"code","when":"always","key":"plan>'
    'code","d":"M732 54 H750 V54 H944","lx":758,"ly":24},{"from":"research","to":"code","when":"ask","key":"researc'
    'h>code","d":"M732 185 H750 V88 H944","lx":758,"ly":58},{"from":"plan","to":"docs","when":{"says":["docs"]},"ke'
    'y":"plan>docs","d":"M732 54 H750 V185 H944","lx":758,"ly":155},{"from":"code","to":"review","when":"always","k'
    'ey":"code>review","d":"M1192 54 H1210 V54 H1404","lx":1218,"ly":24},{"from":"code","to":"check","when":"main-d'
    'ecides","key":"code>check","d":"M1192 54 H1210 V185 H1404","lx":1218,"ly":155}],"w":1676,"h":282},"canvas":{"b'
    'oxes":[{"id":"main","kind":"agent","name":"main","names":["main"],"main":true,"x":24,"y":24,"h":83,"col":0},{"'
    'id":"plan","kind":"agent","name":"planner","names":["planner"],"x":484,"y":24,"h":83,"col":1},{"id":"research"'
    ',"kind":"agent","name":"researcher","names":["researcher"],"x":484,"y":135,"h":83,"col":1},{"id":"code","kind"'
    ':"agent","name":"coder","names":["coder"],"x":944,"y":24,"h":88,"col":2},{"id":"docs","kind":"agent","name":"w'
    'riter","names":["writer"],"x":944,"y":140,"h":83,"col":2},{"id":"review","kind":"agent","name":"reviewer","nam'
    'es":["reviewer"],"x":1404,"y":24,"h":83,"col":3},{"id":"check","kind":"workflow","name":"review","names":["rev'
    'iew"],"x":1404,"y":135,"h":83,"col":3}],"lines":[{"from":"main","to":"plan","when":"always","key":"main>plan",'
    '"d":"M272 54 H290 V54 H484","lx":298,"ly":24},{"from":"main","to":"research","when":"main-decides","key":"main'
    '>research","d":"M272 54 H290 V165 H484","lx":298,"ly":135},{"from":"plan","to":"code","when":"always","key":"p'
    'lan>code","d":"M732 54 H750 V54 H944","lx":758,"ly":24},{"from":"research","to":"code","when":"ask","key":"res'
    'earch>code","d":"M732 165 H750 V88 H944","lx":758,"ly":58},{"from":"plan","to":"docs","when":{"says":["docs"]}'
    ',"key":"plan>docs","d":"M732 54 H750 V170 H944","lx":758,"ly":140},{"from":"code","to":"review","when":"always'
    '","key":"code>review","d":"M1192 54 H1210 V54 H1404","lx":1218,"ly":24},{"from":"code","to":"check","when":"ma'
    'in-decides","key":"code>check","d":"M1192 54 H1210 V165 H1404","lx":1218,"ly":135}],"w":1676,"h":247}},"probe"'
    ':{"view":{"boxes":[{"id":"main","kind":"agent","name":"main","names":["main"],"main":true},{"id":"coder","kind'
    '":"agent","name":"coder","names":["coder"]},{"id":"reviewer","kind":"agent","name":"reviewer","names":["review'
    'er"]},{"id":"tester","kind":"agent","name":"tester","names":["tester"]},{"id":"docs","kind":"agent","name":"do'
    'cs","names":["docs"]}],"strip":[{"id":"loose","kind":"agent","name":"loose","names":["loose"]}],"lines":[{"fro'
    'm":"main","to":"coder"},{"from":"coder","to":"reviewer"},{"from":"main","to":"reviewer"},{"from":"loose","to":'
    '"tester"},{"from":"main","to":"docs"}]},"lit":{"boxes":[{"id":"main","kind":"agent","name":"main","names":["ma'
    'in"],"main":true,"x":24,"y":24,"h":103,"col":0},{"id":"coder","kind":"agent","name":"coder","names":["coder"],'
    '"x":484,"y":24,"h":103,"col":1},{"id":"docs","kind":"agent","name":"docs","names":["docs"],"x":484,"y":155,"h"'
    ':103,"col":1},{"id":"reviewer","kind":"agent","name":"reviewer","names":["reviewer"],"x":944,"y":24,"h":103,"c'
    'ol":2}],"lines":[{"from":"main","to":"coder","key":"main>coder","d":"M272 54 H290 V54 H484","lx":298,"ly":24},'
    '{"from":"coder","to":"reviewer","key":"coder>reviewer","d":"M732 54 H750 V54 H944","lx":758,"ly":24},{"from":"'
    'main","to":"reviewer","key":"main>reviewer","d":"M272 54 H290 V88 H944","lx":758,"ly":58},{"from":"main","to":'
    '"docs","key":"main>docs","d":"M272 54 H290 V185 H484","lx":298,"ly":155}],"w":1216,"h":282},"canvas":{"boxes":'
    '[{"id":"main","kind":"agent","name":"main","names":["main"],"main":true,"x":24,"y":24,"h":83,"col":0},{"id":"c'
    'oder","kind":"agent","name":"coder","names":["coder"],"x":484,"y":24,"h":83,"col":1},{"id":"docs","kind":"agen'
    't","name":"docs","names":["docs"],"x":484,"y":135,"h":83,"col":1},{"id":"reviewer","kind":"agent","name":"revi'
    'ewer","names":["reviewer"],"x":944,"y":24,"h":88,"col":2}],"lines":[{"from":"main","to":"coder","key":"main>co'
    'der","d":"M272 54 H290 V54 H484","lx":298,"ly":24},{"from":"coder","to":"reviewer","key":"coder>reviewer","d":'
    '"M732 54 H750 V54 H944","lx":758,"ly":24},{"from":"main","to":"reviewer","key":"main>reviewer","d":"M272 54 H2'
    '90 V88 H944","lx":758,"ly":58},{"from":"main","to":"docs","key":"main>docs","d":"M272 54 H290 V165 H484","lx":'
    '298,"ly":135}],"w":1216,"h":242}}}')


def _first_diff(a, b, path="$"):
    if type(a) is not type(b):
        return f"{path}: {a!r} != {b!r}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}.{k}: only in {'the golden' if k in b else 'today'}"
            d = _first_diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return ""
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: {len(a)} items != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = _first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return ""
    return "" if a == b else f"{path}: {a!r} != {b!r}"


@test
def test_layout_and_view_pinned_starter_tiers(ctx: Ctx):
    from tests.helpers import node_ts
    got = node_ts.run(GOLDEN_JS % (_url("layout.ts"), _url("view.ts"), json.dumps(FIXTURES)))
    diff = _first_diff(got, GOLDEN)
    ctx.check(f"layout() and view() give exactly what they gave on the base (first difference: {diff})", not diff)


# ---- L9a: Auto's lane and group column in Agents -> Live (layout.ts options, autoWide) ----

LIVE_SRC = MAPDIR.parent.parent / "agents" / "LiveDraw.tsx"
AUTO_MAP = {"format": "map/1", "name": "auto", "main": {"agent": "main"}, "boxes": [{"id": "x", "agent": "coder"}],
            "lines": [{"from": "main", "to": "x"}]}


def _grp(n: int) -> dict:
    return {"n": n, "key": f"task:t{n}", "by": "task", "name": f"t{n}", "members": [{"aid": f"a{n}"}], "first": n}


def _lay(body: str, data) -> dict:
    """`body` runs with L = layout.ts, V = view.ts, A = litView.ts and D = `data`; it prints one JSON line."""
    from tests.helpers import node_ts
    return node_ts.run(f"const L = await import({_url('layout.ts')}); const V = await import({_url('view.ts')});\n"
                       f"const A = await import({_url('litView.ts')}); const D = {json.dumps(data)};\n{body}")


@test
def test_auto_lane_96_and_a_wide_group_column(ctx: Ctx):
    """L9a: with { lane: 96, wide: 760 } main stays at x 24, 248 wide; every group stands at 24 + 248 + 96 = 368, 760 wide,
    stacked 28 apart; main's line into each enters it 30 below its top; the drawing is 24 + 248 + 96 + 760 + 24 wide."""
    js = """const v = A.autoView(V.view(D.map, [], []), D.gs);
const p = L.layout(v.boxes, v.lines, () => 120, { lane: 96, wide: 760 });
const at = (id) => p.boxes.find((b) => b.id === id);
console.log(JSON.stringify({main: at("main").x, g: [1, 2].map((n) => [at(A.groupId(n)).x, at(A.groupId(n)).y, at(A.groupId(n)).h]),
  lines: p.lines.map((l) => [l.to, l.d]), w: p.w}));"""
    got = _lay(js, {"map": AUTO_MAP, "gs": [_grp(1), _grp(2)]})
    g = got.get("g") or []
    ctx.check(f"main in column 0 at x 24, got {got.get('main')}", got.get("main") == 24)
    ctx.check(f"each group at x 368, stacked 28 apart, got {g}",
              len(g) == 2 and all(x[0] == 368 for x in g) and g[1][1] == g[0][1] + g[0][2] + 28)
    ends = {to: d for to, d in got.get("lines") or []}
    ctx.check(f"main's line into each group: M272 54 H290 V(y + 30) H368, got {ends}",
              len(g) == 2 and all(ends.get(f"group:{n}") == f"M272 54 H290 V{y + 30} H368" for n, (_x, y, _h) in zip((1, 2), g)))
    ctx.check(f"the drawing is 24 + 248 + 96 + 760 + 24 = 1152 wide, got {got.get('w')}", got.get("w") == 1152)


@test
def test_auto_group_column_width(ctx: Ctx):
    """L9a: autoWide(view, zoom) = max(352, min(760, floor(view / zoom - 392))); 392 = PAD + BOX_W + 96 + PAD."""
    cases = [[1356, 1, 760], [1000, 1, 608], [700, 1, 352], [1356, 2, 352], [1000, 1.25, 408], [1356, 0.75, 760],
             [1000.6, 1, 608], [0, 1, 352]]
    got = _lay("console.log(JSON.stringify(D.map((c) => [c[0], c[1], typeof L.autoWide === 'function' ? L.autoWide(c[0], c[1]) : null])));",
               cases)
    ctx.check(f"autoWide gives {[c[2] for c in cases]} for {[c[:2] for c in cases]}, got {got}",
              got == [[a, b, w] for a, b, w in cases])


@test
def test_default_lane_and_width_unchanged_and_only_auto_passes_them(ctx: Ctx):
    """L9a: with no options layout() is exactly today's (Agents -> Map, a map of his), as with {} and with { lane: LANE,
    wide: BOX_W }; only Agents -> Live's Auto branch passes AUTO_LANE and autoWide; the drawing's hold is unchanged (a new
    column width waits for the hold, as every other re-flow)."""
    js = """const out = {};
for (const [k, f] of Object.entries(D)) {
  const v = V.view(f, [], []), h = (b) => L.estimate(b, false, 0);
  const none = JSON.stringify(L.layout(v.boxes, v.lines, h));
  out[k] = [none === JSON.stringify(L.layout(v.boxes, v.lines, h, {})),
            none === JSON.stringify(L.layout(v.boxes, v.lines, h, { lane: L.LANE, wide: L.BOX_W }))];
}
out.consts = [L.AUTO_LANE, L.AUTO_MIN, L.AUTO_MAX];
console.log(JSON.stringify(out));"""
    got = _lay(js, FIXTURES)
    for k in FIXTURES:
        ctx.check(f"{k}: layout() with no options equals it with {{}} and with {{lane: LANE, wide: BOX_W}}, got {got.get(k)}",
                  got.get(k) == [True, True])
    ctx.check(f"AUTO_LANE 96, AUTO_MIN 352, AUTO_MAX 760, got {got.get('consts')}", got.get("consts") == [96, 352, 760])
    live = LIVE_SRC.read_text(encoding="utf-8")
    uses = [ln for ln in live.splitlines() if ("AUTO_LANE" in ln or "autoWide(" in ln) and not ln.startswith("import ")]
    ctx.check(f"LiveDraw passes AUTO_LANE and autoWide( only on its s.auto branch, got {uses}",
              any("AUTO_LANE" in ln for ln in uses) and any("autoWide(" in ln for ln in uses)
              and all("s.auto ?" in ln for ln in uses))
    ctx.check("LiveDraw's hold keeps its key `map`: a new column width waits for the hold",
              "useHeld<G>(held, map, fresh, drawnAll(fresh.boxes, heights))" in live)


# ---- Session's drawing top to bottom (layoutDown.ts) ----

def _chain(name, pairs, boxes):
    return {"format": "map/1", "name": name, "main": {"agent": "main"}, "boxes": [{"id": b, "agent": b} for b in boxes],
            "lines": [{"from": a, "to": b} for a, b in pairs]}


FAN = _chain("fan", [("main", "a"), ("main", "b"), ("main", "c"), ("a", "d"), ("b", "d"), ("c", "d")], "abcd")
SOURCES = [f"s{i}" for i in range(1, 14)]
MANY = _chain("many", [("main", s) for s in SOURCES] + [(s, "t") for s in SOURCES], SOURCES + ["t"])
FIXTURES_DOWN = {**FIXTURES, "fan": FAN, "many": MANY}
SIX = [{"n": i + 1, "step": s, "agent": a, "model": "m", "state": st} for i, (s, a, st) in enumerate(
    [("plan", "planner", "done"), ("code", "coder", "done"), ("test", "tester", "working"), ("review", "reviewer", "next"),
     ("docs", "writer", "next"), ("ship", "ops", "next")])]


def _block_box(under):
    return {"id": "workflow:W", "kind": "workflow", "name": "W", "names": ["W"],
            "block": {"workflow": "W", "under": under, "running": 3, "steps": SIX}}


MAIN_REVIEW = {"lines": [{"from": "main", "to": "review"}]}
BLOCK_A = {"boxes": [_block_box("main")], "lines": [{"from": "main", "to": "workflow:W"}], "est": True}
BLOCK_B = {"patch": {"check": {"block": {"workflow": "review", "steps": SIX}}}, "est": True}
BLOCK_C = {"boxes": [_block_box("plan")], "lines": [{"from": "plan", "to": "workflow:W"}], "est": True}

DOWN_JS = """
const D = await import(%s); const V = await import(%s); const R = await import(%s);
const F = %s; const cases = %s;
const out = cases.map((c) => {
  const v = V.view(F[c.map], [], []);
  if (c.long) for (const b of [...v.boxes, ...v.strip]) b.name = b.name.padEnd(60, "x");
  for (const b of v.boxes) if (c.patch && c.patch[b.id]) Object.assign(b, c.patch[b.id]);
  v.boxes.push(...(c.boxes || [])); v.lines.push(...(c.lines || []));
  const h = c.est ? (b) => D.estimateDown(b) : () => 56;
  if (c.twice) {
    const before = JSON.stringify(v);
    const a = JSON.stringify(D.layoutDown(v, h, c.width)), b = JSON.stringify(D.layoutDown(v, h, c.width));
    return { same: a === b, untouched: JSON.stringify(v) === before };
  }
  return D.layoutDown(v, h, c.width, c.opts);
});
const reach = Object.fromEntries(Object.entries(F).map(([k, f]) => [k, [...R.reach(f.lines)].sort()]));
const est = { long: D.estimateDown({ id: "x", kind: "agent", name: "x".repeat(60), names: [] }),
              six: D.estimateDown({ id: "w", kind: "workflow", name: "W", names: [], block: { workflow: "W", steps: %s } }) };
console.log(JSON.stringify({ out, reach, est }));
"""


def down(cases):
    from tests.helpers import node_ts
    return node_ts.run(DOWN_JS % (_url("layoutDown.ts"), _url("view.ts"), _url("reach.ts"), json.dumps(FIXTURES_DOWN),
                                  json.dumps(cases), json.dumps(SIX)))


def case(m, width, **kw):
    return {"map": m, "width": width, **kw}


def at(g, bid):
    return next(b for b in g["boxes"] if b["id"] == bid)


def line(g, key):
    return next(x for x in g["lines"] if x["key"] == key)


_D = re.compile(r"M(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)((?: [HV]-?\d+(?:\.\d+)?)*)")


def segments(d):
    """The axis-aligned segments of a path made of M, H and V only (None when it has any other command)."""
    m = _D.fullmatch(d)
    if not m:
        return None
    x, y, out = float(m.group(1)), float(m.group(2)), []
    for cmd, v in re.findall(r" ([HV])(-?\d+(?:\.\d+)?)", m.group(3)):
        nx, ny = (float(v), y) if cmd == "H" else (x, float(v))
        out.append(((x, y), (nx, ny)))
        x, y = nx, ny
    return out


def under_a_box(seg, b):
    (x1, y1), (x2, y2) = seg
    lo_x, hi_x, lo_y, hi_y = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
    return (hi_x > b["x"] + 1 and lo_x < b["x"] + b["w"] - 1 and hi_y > b["y"] + 1 and lo_y < b["y"] + b["h"] - 1)


def v_at(g, key, x):
    return [s for s in segments(line(g, key)["d"]) if s[0][0] == s[1][0] == x and s[0][1] != s[1][1]]


@test
def test_down_two_per_row_at_408(ctx: Ctx):
    widths = (408, 412, 429)
    got = down([case("starter", w) for w in widths] + [case("tiers", w) for w in widths])["out"]
    for w, g in zip(widths * 2, got):
        ctx.check(f"at {w}: two a row, pad 12, world 408, got {g['per']} {g['pad']} {g['w']}", (g["per"], g["pad"], g["w"]) == (2, 12, 408))
        ctx.check(f"at {w}: main alone on row 0 over the spine (x 112, y 12), got {at(g, 'main')['x']} {at(g, 'main')['y']}",
                  (at(g, "main")["x"], at(g, "main")["y"]) == (112, 12))
    for w, g in zip(widths, got[:3]):
        xy = [(at(g, b["id"])["x"], at(g, b["id"])["y"]) for b in STARTER["boxes"]]
        ctx.check(f"at {w}: the starter's seven in file order two a row, ops alone at the left, got {xy}",
                  xy == [(12, 96), (212, 96), (12, 168), (212, 168), (12, 240), (212, 240), (12, 312)])
        ctx.check(f"at {w}: the starter is 380 high, got {g['h']}", g["h"] == 380)
    for w, g in zip(widths, got[3:]):
        xy = {k: (at(g, k)["x"], at(g, k)["y"]) for k in ("plan", "research", "code", "docs", "review", "check")}
        ctx.check(f"at {w}: tiers, a new rank starts a row, got {xy}",
                  xy == {"plan": (12, 96), "research": (212, 96), "code": (12, 180), "docs": (212, 180), "review": (12, 264),
                         "check": (212, 264)})
        ctx.check(f"at {w}: tiers is 332 high, got {g['h']}", g["h"] == 332)
        ctx.check(f"at {w}: Session's lines carry no When label, got {[k for k in g['lines'] if 'lx' in k]}",
                  all("lx" not in x and "ly" not in x for x in g["lines"]))


@test
def test_down_two_per_row_at_400_pad_8(ctx: Ctx):
    widths = (400, 407)
    got = down([case("starter", w) for w in widths] + [case("tiers", w) for w in widths])["out"]
    for w, g in zip(widths * 2, got):
        ctx.check(f"at {w}: pad 8, world 400, main at x 108, got {g['pad']} {g['w']} {at(g, 'main')['x']}",
                  (g["per"], g["pad"], g["w"], at(g, "main")["x"]) == (2, 8, 400, 108))
    for w, g in zip(widths, got[:2]):
        xy = [(at(g, b["id"])["x"], at(g, b["id"])["y"]) for b in STARTER["boxes"]]
        ctx.check(f"at {w}: left x 8, right x 208, the same rows, got {xy}",
                  xy == [(8, 96), (208, 96), (8, 168), (208, 168), (8, 240), (208, 240), (8, 312)])
        ctx.check(f"at {w}: still 380 high, got {g['h']}", g["h"] == 380)
    for w, g in zip(widths, got[2:]):
        ctx.check(f"at {w}: tiers code at (8, 180), check at (208, 264), 332 high",
                  (at(g, "code")["x"], at(g, "code")["y"], at(g, "check")["x"], at(g, "check")["y"], g["h"]) == (8, 180, 208, 264, 332))


@test
def test_down_one_per_row_under_400(ctx: Ctx):
    widths = (399, 360)
    got = down([case("starter", w) for w in widths])["out"]
    for w, g in zip(widths, got):
        ctx.check(f"at {w}: one a row, world 224, got {g['per']} {g['w']}", (g["per"], g["w"]) == (1, 224))
        ctx.check(f"at {w}: every box at x 12, got {sorted({b['x'] for b in g['boxes']})}", {b["x"] for b in g["boxes"]} == {12})
        ys = [at(g, b["id"])["y"] for b in STARTER["boxes"]]
        ctx.check(f"at {w}: one box a row, got {ys}", ys == [96 + 72 * i for i in range(7)])
        ctx.check(f"at {w}: the starter is 596 high, got {g['h']}", g["h"] == 596)


@test
def test_down_same_input_same_output(ctx: Ctx):
    got = down([case(m, 412, twice=True) for m in FIXTURES_DOWN])["out"]
    for m, g in zip(FIXTURES_DOWN, got):
        ctx.check(f"{m}: two calls give the same JSON", g["same"] is True)
        ctx.check(f"{m}: the input is left as it was", g["untouched"] is True)


@test
def test_down_no_segment_under_a_box(ctx: Ctx):
    shapes = [("starter", {}), ("tiers", {}), ("tiers", MAIN_REVIEW), ("probe", {}), ("fan", {}), ("many", {}), ("starter", BLOCK_A),
              ("tiers", BLOCK_B), ("tiers", BLOCK_C)]
    cases = [case(m, w, **{**extra, **more}) for m, extra in shapes for w in (412, 404, 360) for more in ({}, {"est": True, "long": True})]
    got = down(cases)["out"]
    bad, counted = [], 0
    for c, g in zip(cases, got):
        boxes = {b["id"]: b for b in g["boxes"]}
        for ln in g["lines"]:
            counted += 1
            segs = segments(ln["d"])
            where = f"{c['map']}@{c['width']}{' long' if c.get('long') else ''} {ln['key']}: {ln['d']}"
            if not segs:
                bad.append(f"{where} (not M/H/V only)")
                continue
            s, t = boxes[ln["from"]], boxes[ln["to"]]
            if segs[0][0] != (s["x"] + s["w"] / 2, s["y"] + s["h"]):
                bad.append(f"{where} (does not leave its source's bottom centre)")
            end = segs[-1][1]
            if not (end[1] == t["y"] and t["x"] <= end[0] <= t["x"] + t["w"] and segs[-1][0][1] < t["y"]):
                bad.append(f"{where} (does not enter its target's top from above)")
            for seg in segs:
                for b in g["boxes"]:
                    if under_a_box(seg, b):
                        bad.append(f"{where} (a segment under {b['id']})")
    ctx.check(f"lines were drawn ({counted})", counted > 200)
    ctx.check(f"every line leaves at the bottom centre, enters at the top, never runs under a box: {bad[:4]}", not bad)


@test
def test_down_skip_rank_on_the_spine(ctx: Ctx):
    g412, g404 = down([case("tiers", 412, **MAIN_REVIEW), case("tiers", 404, **MAIN_REVIEW)])["out"]
    for g, spine in ((g412, 204), (g404, 200)):
        rev, code = at(g, "review"), at(g, "code")
        runs = v_at(g, "main>review", spine)
        ctx.check(f"main -> review has one vertical on the spine's centre {spine}, got {line(g, 'main>review')['d']}", len(runs) == 1)
        if runs:
            (_, ya), (_, yb) = runs[0]
            ctx.check(f"it runs from the band under main to the band above review's row (past code's row), got {ya}..{yb}",
                      ya <= 68 + 28 and yb >= code["y"] + code["h"] and yb <= rev["y"])
        end = segments(line(g, "main>review")["d"])[-1][1]
        ctx.check(f"it enters review's top, got {end}", end[1] == rev["y"] and rev["x"] <= end[0] <= rev["x"] + rev["w"])


@test
def test_down_entries_staggered_14(ctx: Ctx):
    tiers, fan, many = down([case("tiers", 412), case("fan", 412), case("many", 412)])["out"]
    ctx.check(f"code is entered at 97 from plan and 111 from research, got {line(tiers, 'plan>code')['entry']} "
              f"{line(tiers, 'research>code')['entry']}", (line(tiers, "plan>code")["entry"], line(tiers, "research>code")["entry"]) == (97, 111))
    ctx.check(f"docs is entered once, at its centre 304, got {line(tiers, 'plan>docs')['entry']}", line(tiers, "plan>docs")["entry"] == 304)
    d = at(fan, "d")
    cx = d["x"] + d["w"] / 2
    got = [line(fan, k)["entry"] for k in ("a>d", "c>d", "b>d")]
    ctx.check(f"three into d: cx - 14, cx, cx + 14 by the sources' exit x (then id), got {got} about {cx}", got == [cx - 14, cx, cx + 14])
    t = at(many, "t")
    xs = [line(many, f"{s}>t")["entry"] for s in SOURCES]
    ctx.check(f"thirteen into one box: every entry on its top between x + 8 and x + w - 8, all distinct, got {xs}",
              all(t["x"] + 8 <= x <= t["x"] + t["w"] - 8 for x in xs) and len(set(xs)) == 13)


@test
def test_down_unreached_band_has_strip_fed_box(ctx: Ctx):
    res = down([case("probe", 412), case("probe", 360), case("starter", 412)])
    g, narrow, starter = res["out"]
    ctx.check(f"reach() of the probe's lines is main, coder, reviewer, docs, got {res['reach']['probe']}",
              res["reach"]["probe"] == ["coder", "docs", "main", "reviewer"])
    ctx.check(f"a map whose every box is reached has no band, got {starter['band']}", starter["band"] is None)
    band = g["band"] or {}
    ctx.check(f"the band names tester and loose, got {band}", band.get("ids") == ["tester", "loose"])
    ranked = [at(g, k) for k in ("main", "coder", "reviewer", "docs")]
    ctx.check("coder, reviewer, docs are ranked and not flagged", all(not b.get("unreached") for b in ranked))
    last = max(b["y"] + b["h"] for b in ranked)
    ctx.check(f"the band starts 28 under the last ranked row, got {band.get('y')} for a bottom at {last}", band.get("y", 0) >= last + 28)
    for gg, xs in ((g, {12, 212}), (narrow, {12})):
        un = [at(gg, k) for k in ("tester", "loose")]
        ctx.check(f"tester AND loose are placed and flagged, got {[(b['id'], b.get('unreached')) for b in un]}",
                  all(b.get("unreached") is True for b in un))
        ctx.check("they sit under the band's heading", all(b["y"] >= gg["band"]["y"] + gg["band"]["head"] for b in un))
        ctx.check(f"at {gg['w']}: at most {gg['per']} a row at x {xs}, got {[(b['x'], b['y']) for b in un]}",
                  {b["x"] for b in un} <= xs and len({b["y"] for b in un}) == (1 if gg["per"] == 2 else 2))
        ctx.check(f"no line has loose or tester at either end, got {[x['key'] for x in gg['lines']]}",
                  not any({x["from"], x["to"]} & {"loose", "tester"} for x in gg["lines"]))
    ctx.check(f"the band's height is in the drawing's, got {g['h']}", g["h"] >= max(b["y"] + b["h"] for b in g["boxes"]) + 12)


@test
def test_down_workflow_block_full_row_every_step(ctx: Ctx):
    res = down([case("starter", 412, **BLOCK_A), case("tiers", 412, **BLOCK_B), case("tiers", 412, **BLOCK_C),
                case("tiers", 360, **BLOCK_C)])
    a, b, c, d = res["out"]
    ctx.check(f"a six-step block is 146 high, a 60-character name 92, got {res['est']}", res["est"] == {"six": 146, "long": 92})
    w = at(a, "workflow:W")
    ctx.check(f"(a) the block under main: full width at (12, 384), 384 x 146, got {(w['x'], w['y'], w['w'], w['h'])}",
              (w["x"], w["y"], w["w"], w["h"]) == (12, 384, 384, 146))
    ctx.check("(a) every one of its six steps, in order", [s["n"] for s in w["block"]["steps"]] == [1, 2, 3, 4, 5, 6])
    end = segments(line(a, "main>workflow:W")["d"])[-1][1]
    ctx.check(f"(a) main -> W runs the spine and enters the block's top at 204, got {line(a, 'main>workflow:W')['d']}",
              v_at(a, "main>workflow:W", 204) and end == (204, 384))
    ctx.check(f"(a) the drawing holds it, got {a['h']}", a["h"] == 384 + 146 + 12)
    ck = at(b, "check")
    ctx.check(f"(b) a map box with a block keeps its place and width, as tall as its steps, got {(ck['x'], ck['w'], ck['h'])}",
              (ck["x"], ck["w"], ck["h"]) == (212, 184, 146))
    w, code = at(c, "workflow:W"), at(c, "code")
    ctx.check(f"(c) the block under plan is the last, full-width row of rank 2, got {(w['x'], w['y'], w['w'])}",
              (w["x"], w["w"]) == (12, 384) and w["y"] > code["y"] + code["h"] and w["y"] < at(c, "review")["y"])
    spine = v_at(c, "plan>workflow:W", 204)
    ctx.check(f"(c) plan -> W comes down the spine between code and docs, got {line(c, 'plan>workflow:W')['d']}",
              any(min(s[0][1], s[1][1]) <= code["y"] and max(s[0][1], s[1][1]) >= code["y"] + code["h"] for s in spine))
    ctx.check("(c) and enters the block's top at 204", segments(line(c, "plan>workflow:W")["d"])[-1][1] == (204, w["y"]))
    for k in ("code>review", "code>check"):
        ctx.check(f"(c) {k} passes the block in the left outer pad (x 6), got {line(c, k)['d']}",
                  any(min(s[0][1], s[1][1]) <= w["y"] and max(s[0][1], s[1][1]) >= w["y"] + w["h"] for s in v_at(c, k, 6)))
    ctx.check(f"(d) at 360 the full-width block is 200 wide, got {at(d, 'workflow:W')['w']}", at(d, "workflow:W")["w"] == 200)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
