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

from tests.helpers.scratch_seven import NAME as SEVEN  # noqa: E402
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
              f.get("sid") == b and f.get("map") == "auto")
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


# -- 3.6.0.2 batch 7: the default pick selects an agent again; a stale pick is given up; the drawing's timer is cleared --
STALE_JS = """const m = await import(%s);
const T = {session_id: 'TERM', parent: null, turns: 4, started: 100};
m.noteRows([T], 1);
const gone = [m.staleRead([T], 'GONE'), m.staleRead([T], 'GONE')];
m.startedHere('NEW');
const mine = [1, 2, 3, 4].map(() => m.staleRead([T], 'NEW'));
m.noteRows([T, {session_id: 'END', turns: 1, started: 50}], 2); m.noteRows([T], 3);
const ended = [1, 2, 3].map(() => m.staleRead([T], 'END'));
const late = [m.staleRead([T], 'LATE'), m.staleRead([T, {session_id: 'LATE', turns: 1, started: 400}], 'LATE'), m.staleRead([T], 'LATE')];
console.log(JSON.stringify({gone, mine, ended, late, held: m.livePick([T], 'NEW')?.session_id ?? null, none: m.staleRead([T], '')}));"""
_STALE: dict = {}


def _stale_node(ctx: Ctx) -> "dict | None":
    """pick.ts `staleRead` / `startedHere` in node (None where node cannot run a .ts: the browser half still runs)."""
    from tests.helpers import node_ts
    if "p" not in _STALE:
        try:
            _STALE["p"] = node_ts.run(STALE_JS % json.dumps(PICK.resolve().as_uri()))
        except SkipTest as e:
            _STALE["p"], _STALE["skip"] = None, str(e)
    return _STALE["p"]


@test
def test_no_pick_selects_the_newest_working_agent(ctx: Ctx):
    # batch 7 (the repair of batch 1 took the default pick away): Session opened with no pick selects the newest working
    # agent of the session it shows (R1's newest open one), as 3.6.0.1 did; a pick this page started (New session) and
    # not listed yet is still never replaced by another session.
    p = _stale_node(ctx)
    if p is not None:
        ctx.check(f"R1: a New session's pick not listed yet is held through every read, got {p.get('mine')} {p.get('held')!r}",
                  p.get("mine") == [False] * 4 and p.get("held") is None)
    got = _driver()
    d = _ran(ctx, got, "default")
    a = got.get("rig_sid") or ""
    ctx.check(f"R1: with no pick the Agent panel shows an agent, not 'Pick an agent', got {d}", d.get("key") and not d.get("empty"))
    ctx.check(f"R1: the newest working agent of the session shown (the rig's, the newest open), got {d} (rig {a})",
              d.get("key", "").split("|")[1:2] == [a] and d.get("state") == "running")
    if p is None:
        raise SkipTest(f"browser half passed; node half: {_STALE.get('skip')}")


@test
def test_a_pick_never_listed_is_given_up_after_two_reads(ctx: Ctx):
    # batch 7: a `?session=` link (or 'Watch in Session') to a session that ended before the page loaded is given up once
    # two reads of the rows do not list it, and Session shows what it would with no pick; one seen and then gone keeps T8.
    p = _stale_node(ctx)
    if p is not None:
        ctx.check(f"R1: a pick never listed: kept at the first read, given up at the second, got {p.get('gone')}", p.get("gone") == [False, True])
        ctx.check(f"R4: a pick seen and then gone (T8) is never given up, got {p.get('ended')}", p.get("ended") == [False] * 3)
        ctx.check(f"R1: a pick listed late is not given up, got {p.get('late')}; no pick is no give-up, got {p.get('none')}",
                  p.get("late") == [False] * 3 and p.get("none") is False)
    got = _driver()
    s = _ran(ctx, got, "stale")
    a = got.get("rig_sid") or ""
    ctx.check(f"R1: after the reads Session draws and costs the newest open session, not 'No session is running here', got {s}",
              s.get("sid") == a and s.get("cost") == a and s.get("boxes"))
    if p is None:
        raise SkipTest(f"browser half passed; node half: {_STALE.get('skip')}")



LIST_JS = """const m = await import(%s);
const rows = (...ids) => ids.map((id) => ({session_id: id, parent: null, turns: 1, started: 100, map: 'auto'}));
const busy = (n) => rows('B').map((r) => ({...r, agents: Array.from({length: n}, (_, i) => ({agent_id: 'a' + i, state: 'running'}))}));
const held = [m.staleList(1, rows('B'), 'GONE1')];
for (let i = 1; i <= 6; i++) held.push(m.staleList(1, busy(i), 'GONE1'));  // agent frames of B: the same list read
const gone = [m.staleList(2, rows('B'), 'GONE1')];  // the second fresh read of the list without it
const later = [m.staleList(3, rows('B'), 'GONE2'), m.staleList(3, busy(2), 'GONE2'), m.staleList(4, rows('B'), 'GONE2')];
console.log(JSON.stringify({held, gone, later}));"""

NEWEST_JS = """const m = await import(%s);
const pend = [], kept = [], failed = [];
const read = m.newestOnly(() => new Promise((ok, no) => pend.push({ok, no})), (v) => kept.push(v), () => failed.push(1));
read(); read();
pend[1].ok('second'); await null; pend[0].ok('first'); await new Promise((r) => setTimeout(r, 0));
read(); read();
pend[2].ok('third-late'); pend[3].no(new Error('x')); await new Promise((r) => setTimeout(r, 0));
console.log(JSON.stringify({kept, failed: failed.length}));"""


@test
def test_stale_pick_counts_only_list_reads(ctx: Ctx):
    # P3 batch 8 (the checker of batch 7): a stale link's pick is given up after two fresh reads of the session LIST (GET
    # live, a sessions frame: the fleet's listReads), never after agent frames of a busy other session (pick.ts staleList,
    # which routes/session/store.ts calls with fleet.listReads).
    from tests.helpers import node_ts
    p = node_ts.run(LIST_JS % json.dumps(PICK.resolve().as_uri()))
    ctx.check(f"R1: six agent frames of another session after the first list read hold the pick, got {p.get('held')}",
              p.get("held") == [False] * 7)
    ctx.check(f"R1: the second fresh list read without it gives it up, got {p.get('gone')}", p.get("gone") == [True])
    ctx.check(f"R1: a frame between two list reads counts nothing, got {p.get('later')}", p.get("later") == [False, False, True])
    src = (PICK.parent / "store.ts").read_text(encoding="utf-8")
    ctx.check("store.ts gives up a pick by staleList(s.listReads, ...), not by a new harnesses array",
              "staleList(s.listReads," in src and "s.harnesses !== lastRead" not in src)


SYNC = PICK.parent.parent / "fleet" / "sync.ts"
# sync.ts's neighbours stood in for: the feed's handlers are kept in __on, the fleet is two harnesses (this one, gpu-box)
SYNC_STUB = r"""export const onEvent = (k, f) => { (globalThis.__on[k] ||= []).push(f); };
export const onFeedState = () => {}; export class ApiError extends Error {};
export const api = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) };
export const studio = { get: () => ({ feed: { status: 'open' } }) }; export const toast = () => {}; export const startPanels = () => {};
export const FIGURE_KINDS = [], agentWith = (a) => a, figuresOf = () => null, ownFrame = () => false, withFigures = (x) => x;
export const keepFresh = (x) => x, noteFigures = () => {}, noteFrame = () => {}, noteMode = () => {}, append = () => {}, rawEntry = () => null;
let s = { started: false, listReads: 0, streams: {}, doneAt: {},
  harnesses: [{ id: 'here', local: true, sessions: [] }, { id: 'gpu-box', local: false, sessions: [] }] };
export const fleet = { get: () => s, update: (fn) => { s = { ...s, ...fn(s) }; } };
export const keyOf = (h, sid) => `${h}/${sid}`, localId = (st = s) => st.harnesses.find((h) => h.local)?.id || '';"""
SYNC_HOOK = r"""const STUB = %s;
export async function resolve(spec, ctx, next) {
  // P8: on node_ts's transpile path (a node without TypeScript) the same neighbours are ./m<n>-<name>.mjs files
  if (/^\.\/m\d+-(api|events|store|pload|figures|fresh|streams)\.mjs$/.test(spec)) return { url: STUB, shortCircuit: true };
  const r = await next(spec, ctx);
  if (/\/(lib\/(api|events|store)|fleet\/(pload|figures|fresh|streams|store))\.(ts|mjs)$/.test(r.url)) return { url: STUB, shortCircuit: true };
  return r; }"""
SYNC_JS = """import { register } from 'node:module';
register('data:text/javascript,' + encodeURIComponent(%s));
globalThis.__on = {};
globalThis.window = { setInterval: () => 0, setTimeout: () => 0, clearTimeout: () => {}, clearInterval: () => {} };
globalThis.document = { hidden: false, addEventListener: () => {} };
const m = await import(%s), st = await import(%s);
m.startFleet();
const fire = (h) => (globalThis.__on.registry || []).forEach((f) => f({ harness: h, session_id: null, event: 'registry',
  data: { action: 'sessions', sessions: [] } }));
const r0 = st.fleet.get().listReads; fire('gpu-box'); const r1 = st.fleet.get().listReads; fire('here'); const r2 = st.fleet.get().listReads;
console.log(JSON.stringify({ r0, r1, r2, bound: (globalThis.__on.registry || []).length }));
process.exit(0);"""


@test
def test_list_reads_count_only_this_harness_sessions_frames(ctx: Ctx):
    # P3 batch 8 repair (its checker): staleList judges THIS harness's rows (localSessions), so only a sessions frame of this
    # harness is a fresh read of that list; another harness's frame (through the hub) counts nothing. Driven through
    # sync.ts's own `registry` handler, its neighbours stood in for.
    from urllib.parse import quote
    from tests.helpers import node_ts
    stub = "data:text/javascript," + quote(SYNC_STUB)
    p = node_ts.run(SYNC_JS % (json.dumps(SYNC_HOOK % json.dumps(stub)), json.dumps(SYNC.resolve().as_uri()), json.dumps(stub)))
    ctx.check(f"R1: sync.ts listens for sessions frames, got {p}", (p or {}).get("bound") == 1)
    ctx.check(f"R1: another harness's sessions frame is no read of this harness's list; this harness's is one, got {p}",
              (p or {}).get("r0") == 0 and p.get("r1") == 0 and p.get("r2") == 1)


@test
def test_next_b_keeps_the_newest_read(ctx: Ctx):
    # P3 batch 8 (the checker of batch 3): the map new sessions use is read again on every maps/config change; reads may be
    # answered out of order, and only the newest read's answer is kept (pick.ts newestOnly, which nextB.ts reads through).
    from tests.helpers import node_ts
    p = node_ts.run(NEWEST_JS % json.dumps(PICK.resolve().as_uri()))
    ctx.check(f"two reads, the first answers last: the second's value is kept, the late first dropped; then a newer read's "
              f"failure drops an older answer, got {p}", p.get("kept") == ["second"] and p.get("failed") == 1)
    src = (PICK.parent / "nextB.ts").read_text(encoding="utf-8")
    ctx.check("nextB.ts reads through newestOnly", "newestOnly(" in src)

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
    ctx.check(f"R12: 3 s under the pointer with a new row in main's box and new words: nothing moved, nothing grew, got {moved[:6]}",
              len(under) == 12 and not moved)
    ctx.check(f"R12 R15: the pointer left: the new row drawn in main's box within 2 s, got {h.get('arrived_s')}", h.get("arrived_s") is not None)
    s, k = h.get("scrolled") or {}, h.get("kept") or {}
    ctx.check(f"R12: scrolled by hand so a row under main's is first, got {s}", s.get("first") not in (None, "main") and (s.get("st") or 0) > 0)
    ctx.check(f"R12: main's box growing above (a row arriving) keeps the first box seen in its place, got {s} -> {k}",
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
    # 3.6.0.2 batch 5 (R12 R18): the step-in card's buttons keep their rects over 20 frames of Pause <-> Resume
    d = _stepin(ctx, "card")
    cf = d.get("frames") or []
    c0 = cf[0] if cf else {}
    parts = ("rect", "pause", "stop", "steer", "live")
    moved = [(i, p) for i, f in enumerate(cf) for p in parts if not _same(f.get(p), c0.get(p))]
    ctx.check(f"R12: the card and its buttons keep their rects through Pause <-> Resume, got (frame, part) {moved[:6]}",
              len(cf) == 20 and all(c0.get(p) for p in parts) and not moved
              and {f.get("pauseText") for f in cf} == {"Pause", "Resume"})


@test
def test_live_drawing_clears_its_timer_when_it_goes(ctx: Ctx):
    # batch 7: a hand scroll arms the drawing's 200 ms settle timer (MapDown.tsx); the drawer closed at once unmounts it.
    # Its observers and listeners are lib/canvasNav.ts's and hold.ts's (each cleared on unmount); the timer was not.
    g = _drew(ctx, "gone")
    ctx.check(f"the scroll armed the drawing's timer and the drawer closed, got {g}", g.get("made", 0) >= 1 and g.get("closer") and g.get("drawn") is False)
    ctx.check(f"nothing of the drawing fires once it is gone, got {g}", g.get("firedGone") == 0 and g.get("fired") == 0)


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


# -- 3.6.0.2 batch 3: the truth block (R20 R22), the status line (R23), the Start view (R4) --------------------------
SESSION_DIR = REPO / "halo_harness" / "studio" / "ui" / "src" / "routes" / "session"
TRUTH_TS = REPO / "halo_harness" / "studio" / "ui" / "src" / "routes" / "crew" / "map" / "truth.ts"
TIME = r"\d{1,2}[:.]\d{2}(\s?[AaPp]\.?\s?[Mm]\.?)?"
_TRUTH: dict = {}


def _truth() -> dict:
    """tests/helpers/studio_session_truth.py, run once for the tests below."""
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Live drawer needs headless Chrome)")
    if not _TRUTH:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_session_truth"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _TRUTH.update(r=r, got=info)
    if _TRUTH["got"].get("skip"):
        raise SkipTest(_TRUTH["got"]["skip"])
    return _TRUTH["got"]


def _saw(ctx: Ctx, key: str):
    got = _truth()
    r = _TRUTH["r"]
    ctx.check(f"the driver reached {key}, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", key in got)
    return got.get(key)


def _untimed(s: str) -> str:
    import re
    return re.sub(TIME, "{t}", s or "")


TRUTH_JS = """const T = await import(%s);
const D = %s;
const base = { title: 's', a: 'shop', plain: false, b: 'shop', bSince: D.t0 - 3600, started: D.t0, turns: 1, studio: false,
  ended: null, machine: null, unreadable: null, changed: null, workflow: null, busy: false };
const t2 = { ...base, b: 'review-flow', bSince: D.t2 }, t5 = { ...t2, changed: { t: D.t2 + 30 } }, t7 = { ...t5, workflow: 'W' };
const L = (f) => T.truthLines(f).map((l) => l.text);
console.log(JSON.stringify({ T1: L(base), T2: L(t2), T5: L(t5), T7: L(t7), states: [base, t2, t5, t7].map((f) => T.truthState(f)) }));"""

PICK_TRUTH_JS = """const m = await import(%s);
const A = {session_id: 'A', parent: null, turns: 1, started: 100, map: 'shop', map_hash: 'h1', map_next: 'shop'};
m.noteRows([A], 10); const before = m.factsOf(A).changed;
m.noteRows([{...A, map_hash: 'h1'}], 20); const same = m.factsOf(A).changed;
m.noteRows([{...A, map_hash: 'h2'}], 30); const after = m.factsOf({...A, map_hash: 'h2'}).changed;
const next1 = m.knownNext();
m.noteBuild('A', {outcome: 'failed', wrote: [{kind: 'map', name: 'x'}]}, 40); const failed = m.lastBuild([]);
m.noteBuild('A', {outcome: 'applied', wrote: [{kind: 'workflow', name: 'review'}, {kind: 'map', name: 'review-flow', added: true}], next: 'review-flow', t: 50}, 41);
console.log(JSON.stringify({before, same, after, next1, failed, open: m.lastBuild([A]), ended: m.lastBuild([]), next2: m.knownNext()}));"""


BODY_JS = """const m = await import(%s);
const flow = {format: 'map/1', name: 'review-flow', boxes: [{id: 'check', workflow: 'W'}], lines: []};
m.noteBody('review-flow', {format: 'map/1', name: 'review-flow', boxes: [], lines: []}); const read = m.mapBody('review-flow');
m.noteBuild('A', {outcome: 'applied', wrote: [{kind: 'map', name: 'review-flow'}], maps: {'review-flow': flow}, next: 'review-flow', t: 5}, 6);
const built = m.mapBody('review-flow');
m.noteBuild('A', {outcome: 'failed', maps: {'review-flow': {boxes: []}}}, 7); const failed = m.mapBody('review-flow');
m.noteBody('x', false); m.noteBody('x', null);
console.log(JSON.stringify({read, built, failed, forgot: m.mapBody('x') === undefined}));"""


@test
def test_t7_reads_the_body_a_build_brought(ctx: Ctx):
    # R22 T7: {B}'s body comes from the builder_done frame's `maps` (a card that adds W's box to B shows T7 the next time
    # W runs, no reload), else the one read; a read that failed is not kept (pick.ts mapBody, TruthBlock's useBody).
    from tests.helpers import node_ts
    p = node_ts.run(BODY_JS % json.dumps(PICK.resolve().as_uri()))
    ctx.check(f"a read body, then the build's body replaces it, got {p}",
              p.get("read", {}).get("boxes") == [] and (p.get("built") or {}).get("boxes") == [{"id": "check", "workflow": "W"}])
    ctx.check(f"a failed card brings no body, got {p.get('failed')}", (p.get("failed") or {}).get("boxes") == [{"id": "check", "workflow": "W"}])
    ctx.check(f"a read that failed is forgotten (read again next time), got {p.get('forgot')}", p.get("forgot") is True)


@test
def test_truth_block_height_moves_only_with_a_name(ctx: Ctx):
    # R20 R22: the truth block's words are truth.ts's for the session's facts; never amber. (a) pick.ts's facts in node;
    # (b) the page. Rewritten to the truth by P4 batch 11 (was test_truth_block_height_fixed, which held the height across
    # T1 -> T2 -> T5 -> T7 by reserving room for names the session did not have): with the coordinator's ruling the block
    # holds only its real names, so T2 (new sessions switched to review-flow) and T7 (the workflow W starts) are names that
    # really change and the block is measured again then; T5 (its own map changed) is held from the state before it.
    from tests.helpers import node_ts
    try:
        p = node_ts.run(PICK_TRUTH_JS % json.dumps(PICK.resolve().as_uri()))
    except SkipTest as e:
        p, node_skip = None, str(e)
    if p is not None:
        node_skip = ""
        ctx.check(f"T5 (a): no change while the map's hash stays, then changed at the read that saw a new one, got {p}",
                  p.get("before") is None and p.get("same") is None and p.get("after") == {"t": 30})
        # P7: rewritten to the truth -- pick.ts's {B} carries `none` since P4 batch 10 (new sessions with no map are never
        # "the default"); this half had never run where node strips TypeScript, so its old shape was never seen red
        ctx.check(f"R4 (a): {{B}} heard from the newest row, then from an applied build, got {p.get('next1')} {p.get('next2')}",
                  p.get("next1") == {"b": "shop", "none": False} and p.get("next2") == {"b": "review-flow", "none": False})
        ctx.check(f"R4 (a): a failed card is no build; an applied one counts once its session is not open, got {p}",
                  p.get("failed") is None and p.get("open") is None and p.get("ended") == {"map": "review-flow", "t": 50})
    try:
        snaps = _saw(ctx, "truth") or []
    except SkipTest as e:
        raise SkipTest(f"(a) {'passed' if not node_skip else node_skip}; (b) {e}")
    facts = (_TRUTH["got"].get("truth_facts") or {})
    try:  # the words truth.ts gives for the same facts (in node; where node cannot run a .ts, the rest is still checked)
        want = node_ts.run(TRUTH_JS % (json.dumps(TRUTH_TS.resolve().as_uri()), json.dumps(facts))) if facts else {}
    except SkipTest as e:
        want, node_skip = None, node_skip or str(e)
    ctx.check(f"the page went through T1, T2, T2 (+T5), T2 (+T7), got {[s.get('state') for s in snaps]}",
              [s.get("state") for s in snaps] == ["T1", "T2", "T2", "T2"] and (want is None or want.get("states") == ["T1", "T2", "T2", "T2"]))
    for name, s in zip(("T1", "T2", "T5", "T7"), snaps):
        if want is not None:
            ctx.check(f"{name}: the lines are truth.ts's for the same facts (times by pattern), got {s.get('lines')} want {want.get(name)}",
                      [_untimed(x) for x in s.get("lines") or []] == [_untimed(x) for x in want.get(name) or []])
        import re
        ctx.check(f"{name}: every time reads as a time, got {s.get('lines')}",
                  all(re.search(TIME, x) for x in s.get("lines") or [] if " at " in x))
        ctx.check(f"{name}: never amber (block {s.get('color')!r}, line {s.get('lineColor')!r}, --warn {s.get('warn')!r})",
                  s.get("color") != s.get("warn") and s.get("lineColor") != s.get("warn") and not s.get("amber"))
    first = snaps[0] if snaps else {}
    ctx.check(f"T2 holds [New session] after S13, got {snaps[1].get('buttons') if len(snaps) > 1 else None}",
              len(snaps) > 1 and snaps[1].get("buttons") == ["New session"])
    ctx.check(f"T7 is the first line, got {snaps[-1].get('lines')[:1] if snaps else None}",
              len(snaps) == 4 and (snaps[3].get("lines") or [""])[0] == "This session is running the workflow W from review-flow.")
    ctx.check(f"R20: each state's block is as tall as its twin of the real words, got {[(s.get('h'), s.get('th')) for s in snaps]}",
              len(snaps) == 4 and all(s.get("h") and s.get("th") and abs(s["h"] - s["th"]) <= 0.5 for s in snaps))
    t2, t5 = (snaps + [{}, {}])[1:3]
    ctx.check(f"R20: T5 changes neither the block's height nor the drawing's top (held from T2), got {t2.get('h')} -> {t5.get('h')}, "
              f"{t2.get('top')} -> {t5.get('top')}", t2.get("h") is not None and t2.get("h") == t5.get("h")
              and t2.get("top") is not None and t2.get("top") == t5.get("top"))
    ctx.check(f"P4 batch 11: T1's twin holds no name the session does not have, got {first.get('ttext')!r}",
              "review-flow" not in (first.get("ttext") or "") and "name-" not in (first.get("ttext") or "")
              and "running the workflow" not in (first.get("ttext") or ""))
    if node_skip:
        raise SkipTest(f"(b) passed; (a) {node_skip}")


@test
def test_truth_block_measures_its_real_names_again_when_one_changes(ctx: Ctx):
    # R20 with the coordinator's ruling of P4 batch 11 (it replaces P3 batch 8's longest-name reserve; this test was
    # test_truth_block_reserve_holds_a_48_character_name, rewritten to the truth): the block reserves nothing for a name
    # it does not have. T1 holds only shop; new sessions switched to a 48-character map is a real change, measured again;
    # a 48-character workflow that starts is another. At every step the block is exactly its twin of the real words.
    # Red on a740c566: T1's twin held "name-name-..." and "flow-flow-..." stand-ins.
    from tests.helpers.studio_session_truth import LONG48
    snaps = _saw(ctx, "long") or []
    ctx.check(f"the page went T1, T2 (a 48-character B), T2 + T7 (a 48-character W), got {[s.get('state') for s in snaps]}",
              [s.get("state") for s in snaps] == ["T1", "T2", "T2"] and "running the workflow" in ((snaps[-1].get("lines") or [""])[0] if snaps else ""))
    first = snaps[0] if snaps else {}
    ctx.check(f"T1's twin holds only the names it has, got {first.get('ttext')!r}",
              "shop" in (first.get("ttext") or "") and not any(w in (first.get("ttext") or "") for w in ("name-", "flow-", LONG48)))
    ctx.check(f"each step's block is its twin's measured height, got {[(s.get('h'), s.get('th')) for s in snaps]}",
              len(snaps) == 3 and all(s.get("h") and s.get("th") and abs(s["h"] - s["th"]) <= 0.5 for s in snaps))
    ctx.check(f"the 48-character B is in the twin once it is the map new sessions use, got {(snaps[1:2] or [{}])[0].get('ttext')!r}",
              len(snaps) > 1 and LONG48 in (snaps[1].get("ttext") or ""))


@test
def test_truth_block_first_draw_holds_a_wide_48_character_name(ctx: Ctx):
    # P4 batch 11, the coordinator's ruling: the block's height comes from the twin of its REAL words, measured with real
    # letters, so a session whose map is a 48-character name of the widest letters (m, w) draws the block at its height
    # in the first frame: the block's height at its first animation frame equals its height five frames later.
    d = _saw(ctx, "wide") or {}
    snap, frames = d.get("snap") or {}, d.get("frames") or []
    ctx.check(f"the page drew T1 naming the wide map, got {snap.get('state')!r} {snap.get('lines')}",
              snap.get("state") == "T1" and any("mw" * 24 in x for x in snap.get("lines") or []))
    ctx.check(f"at least six frames were seen from the block's first draw, got {len(frames)}", len(frames) >= 6)
    ctx.check(f"the height at the first draw equals the height five frames later and after, got {frames[:8]}",
              len(frames) >= 6 and frames[0] > 0 and abs(frames[0] - frames[5]) <= 0.5 and all(abs(f - frames[0]) <= 0.5 for f in frames))


@test
def test_status_line_room_holds_a_40_character_workflow(ctx: Ctx):
    # R23 with the coordinator's ruling of P4 batch 11: the status line's room is its twin's tallest sentence with this
    # run's REAL names (the rows, the workflow it knows), never less than two lines, from its first draw. A session that
    # ran a workflow of a 40-character name is Done, then runs it again waiting for a model reply: that sentence takes three
    # lines, and the link-and-zoom row and the drawing do not move. Red on a740c566: both moved (P3 batch 8's notes: 17 px).
    from tests.helpers.studio_session_truth import W40
    first, run = ((_saw(ctx, "flow40") or []) + [{}, {}])[:2]
    ctx.check(f"first draw: Done, got {first.get('status')!r}", (first.get("status") or "").startswith("Done"))
    ctx.check(f"then the long sentence with the workflow's name, got {run.get('status')!r}",
              (run.get("status") or "").startswith(f"tester working on the workflow {W40}") and "waiting for a model reply" in (run.get("status") or ""))
    lh = first.get("slh") or 0
    ctx.check(f"the long sentence takes more than two lines (the case is real), got {run.get('sh')} at line-height {lh}",
              bool(lh) and (run.get("sh") or 0) > 2 * lh + 1)
    ctx.check(f"the zoom row did not move, got {first.get('ztop')} -> {run.get('ztop')}",
              first.get("ztop") is not None and first.get("ztop") == run.get("ztop"))
    ctx.check(f"the drawing did not move, got {first.get('top')} -> {run.get('top')}",
              first.get("top") is not None and first.get("top") == run.get("top"))


STATUS_JS = """const S = await import(%s); const T = await import(%s);
const kid = (id, name, state, step, cost, current) => ({agent_id: id, name, parent: 'main', state, current: current || '', cost_usd: cost,
  crew: {workflow: 'W', step}});
const main = (state, current) => ({agent_id: 'main', name: 'main', parent: null, state, current, cost_usd: 1.0});
const kids = [kid('w1', 'planner', 'done', 1, 0.5), kid('w2', 'coder', 'done', 2, 0.42), kid('w3', 'tester', 'running', 3, 0.3, 'thinking'),
  kid('w4', 'reviewer', 'queued', 4, 0.2)];
const start = [{event: 'map_step', data: {kind: 'start', workflow: 'W', box: 'workflow:W', steps: ['a', 'b', 'c', 'd', 'e', 'f']}}];
const line = (rows, ev, busy) => T.statusLine(S.statusOf(rows, ev, busy));
console.log(JSON.stringify({
  none: line([], [], false), busy: line([main('running', 'Workflow: W'), ...kids], start, true),
  nostart: line([main('running', 'Workflow: W'), ...kids], [], true),
  done: line([main('done', ''), ...kids.map((k) => ({...k, state: 'done'}))], start, false),
  tool: line([main('running', 'Bash: pytest -q')], [], true), you: line([main('waiting', '')], [], true),
  two: line([main('running', 'Read: a.py'), {...kids[2], current: 'Edit: b.py'}], [], true),
}));"""


@test
def test_status_line_reserved_two_lines(ctx: Ctx):
    # R23: one status line under the truth block: who works (running rows only; main waiting on its workflow is not),
    # on what, waiting for whom, the cost; two lines reserved from the first draw. (a) statusOf.ts in node; (b) the page.
    from tests.helpers import node_ts
    want = "tester working on the workflow W, step 3 of 6 · waiting for a model reply · $2.42"
    try:
        p = node_ts.run(STATUS_JS % (json.dumps((SESSION_DIR / "statusOf.ts").resolve().as_uri()), json.dumps(TRUTH_TS.resolve().as_uri())))
    except SkipTest as e:
        p, node_skip = None, str(e)
    if p is not None:
        node_skip = ""
        ctx.check(f"(a) no rows: 'Waiting for you · $0.00', got {p.get('none')!r}", p.get("none") == "Waiting for you · $0.00")
        ctx.check(f"(a) a workflow's step at work, got {p.get('busy')!r}", p.get("busy") == want)
        ctx.check(f"(a) with no start frame the step count is the highest step known, got {p.get('nostart')!r}",
                  p.get("nostart") == want.replace("of 6", "of 4"))
        ctx.check(f"(a) all done, got {p.get('done')!r}", p.get("done") == "Done · $2.42")
        ctx.check(f"(a) a tool's few words; two at work, got {p.get('tool')!r} {p.get('two')!r}",
                  p.get("tool") == "main working on Bash pytest -q · $1.00" and p.get("two") == "2 agents working on Read a.py · $1.30")
        ctx.check(f"(a) a row waiting on him: 'waiting for you', got {p.get('you')!r}", p.get("you") == "main working · waiting for you · $1.00")
    try:
        got = _saw(ctx, "status") or []
    except SkipTest as e:
        raise SkipTest(f"(a) {'passed' if not node_skip else node_skip}; (b) {e}")
    first, busy, done = (got + [{}, {}, {}])[:3]
    # batch 4 (R17): the session runs on shop, a map of his, and W is no box of it: its steps came by no line of the map,
    # so the status line counts that one block as a hand-off outside the map (rewritten to the truth: it ended at $2.42)
    off1 = " · 1 hand-off outside the map"
    ctx.check(f"first paint, no rows yet, got {first.get('status')!r}", first.get("status") == "Waiting for you · $0.00")
    ctx.check(f"the workflow's step at work, got {busy.get('status')!r}", busy.get("status") == want + off1)
    ctx.check(f"no 'delegating', 'helpers', 'models', got {busy.get('status')!r}",
              not any(w in (busy.get("status") or "") for w in ("delegating", "helpers", "models")))
    ctx.check(f"all done, got {done.get('status')!r}", done.get("status") == "Done · $2.42" + off1)
    # R23 under the block, R20 the block changes only with a fact (PA's check compares its innerText across a busy turn)
    ctx.check(f"the status line is under the truth block, not in it, got {[(s.get('inside'), s.get('below')) for s in (first, busy, done)]}",
              all(s.get("inside") is False and s.get("below") is True for s in (first, busy, done)))
    ctx.check(f"the truth block's text is the same idle, busy and done, got {[s.get('itext') for s in (first, busy, done)]}",
              bool(first.get("itext")) and busy.get("itext") == first.get("itext") == done.get("itext"))
    h = [s.get("sh") for s in (first, busy, done)]
    lh = first.get("slh") or 0
    ctx.check(f"two lines reserved from the first paint: heights {h}, line-height {lh}",
              bool(lh) and all(x is not None and abs(x - 2 * lh) <= 1 for x in h))
    if node_skip:
        raise SkipTest(f"(b) passed; (a) {node_skip}")


@test
def test_start_view_names_the_last_build(ctx: Ctx):
    # R4: the chosen session that ends reads T8; with no session the Start view says which map new sessions use and,
    # after a build this page saw from a since-ended session, that build; [New session] takes him to the form.
    import re
    ended = _saw(ctx, "start_ended") or {}
    view = _TRUTH["got"].get("start_view") or {}
    fresh = _TRUTH["got"].get("start_fresh") or {}
    ctx.check(f"(a) T8 while another session is open, got {ended.get('state')!r} {ended.get('lines')}",
              ended.get("state") == "T8" and len(ended.get("lines") or []) == 1
              and re.fullmatch(f"This session ended at {TIME}\\. It ran on Auto \\(the default\\)\\.", (ended.get("lines") or [""])[0]))
    ctx.check(f"(b) the Start view's first sentence, got {view.get('map')!r}",
              view.get("map") == "No session is open here. New sessions will run on review-flow.")
    ctx.check(f"(b) the last build, got {view.get('built')!r}",
              bool(re.fullmatch(f"Your last session built the map review-flow at {TIME}\\. New sessions run on it\\.", view.get("built") or "")))
    ctx.check(f"(b) [New session] on the last line, focusing the New session form, got {view.get('button')!r} {_TRUTH['got'].get('start_focus')!r}",
              view.get("button") == "New session" and _TRUTH["got"].get("start_focus") == "session-new-cwd")
    ctx.check(f"(c) a fresh page with no build seen: the first sentence only, got {fresh}",
              fresh.get("map") == "No session is open here. New sessions will run on review-flow." and fresh.get("built") is False
              and fresh.get("button") == "New session")
    got = _TRUTH["got"]
    ctx.check(f"(d) the map new sessions use, switched on the same page, shows at once, got {got.get('start_switched')!r}",
              got.get("start_switched") == "No session is open here. New sessions will run on shop.")
    ctx.check(f"(e) the drawer's Empty on a fresh page names the server's map, got {got.get('empty_fresh')!r}",
              got.get("empty_fresh") == "No session is open here. New sessions will run on review-flow.")
    ctx.check(f"(e) and the switch, got {got.get('empty_switched')!r}",
              got.get("empty_switched") == "No session is open here. New sessions will run on shop.")


# -- 3.6.0.2 batch 4 (P3d): the run drawn as it is (R14 R15 R16 R17) ----------------------------------------------------
_RUNS: dict = {}


def _runs() -> dict:
    """tests/helpers/studio_session_run.py, run once for the tests below."""
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Live drawer needs headless Chrome)")
    if not _RUNS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_session_run"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=400, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUNS.update(r=r, got=info)
    if _RUNS["got"].get("skip"):
        raise SkipTest(_RUNS["got"]["skip"])
    return _RUNS["got"]


def _ranrun(ctx: Ctx, key: str) -> dict:
    got = _runs()
    r = _RUNS["r"]
    ctx.check(f"the driver reached {key}, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", got.get(key) is not None)
    return got.get(key) or {}


@test
def test_workflow_block_names_steps_agents_models(ctx: Ctx):
    import re
    d = _ranrun(ctx, "block")
    blk, boxes = d.get("block") or [0, 0, 0, 0], d.get("boxes") or []
    side = [b for b in boxes if b[0] != "main"]
    left = min((b[1] for b in side), default=None)
    right = max((b[1] + b[3] for b in side), default=None)
    bottom = max((b[2] + b[4] for b in boxes), default=None)
    ctx.check(f"R14: the block W on a full-width row under the last rank, got block {blk} row {left}..{right} last bottom {bottom}",
              left is not None and abs(blk[0] - left) <= 1 and abs(blk[2] - (right - left)) <= 1 and blk[1] >= bottom - 0.5)
    ctx.check(f"R14: its head while it runs, got {d.get('head')!r}", d.get("head") == "workflow W · step 3 of 6")
    want = ["1 plan · planner · or:v/planner · done", "2 code · coder · or:v/coder · done", "3 test · tester · or:v/tester · working",
            "4 review · reviewer · or:v/reviewer · next", "5 fix · next", "6 ship · next"]
    ctx.check(f"R14: every step a row, in order, by agent and model, got {d.get('steps')}",
              [s[0] for s in d.get("steps") or []] == want and [s[1] for s in d.get("steps") or []] == ["done", "done", "working", "next", "next", "next"])
    rows = d.get("mainRows") or []
    ctx.check(f"R15: main's box holds the made-up row with Save as an agent, got {rows}",
              rows == [["made up: list the repo · working", True, "g1"]] and d.get("saves") == 1)
    text = d.get("text") or ""
    ctx.check(f"R15: no 'helper', no 'made up for this task' in the drawer, got {re.findall(r'(?i)helper|made up for this task', text)}",
              not re.search(r"(?i)helper|made up for this task", text))
    calm = {b[0]: (b[5], b[6]) for b in boxes if b[0] in ("planner", "coder", "reviewer")}
    ctx.check(f"R14: on his map seven-boxes the planner, coder, reviewer stay calm (not used yet), got {calm}",
              len(calm) == 3 and all(st == "idle" and "not used yet" in tx for st, tx in calm.values()))
    ln = d.get("line") or {}
    ctx.check(f"R16 R17: main -> W is a dashed line, lit, plain on his map seven-boxes (not off the map), got {ln}",
              ln.get("lit") == "live" and ln.get("dash") not in ("", "none") and "off-map" not in str(ln))


@test
def test_hops_light_their_line_and_leave_a_trace(ctx: Ctx):
    import re
    d = _ranrun(ctx, "hops")
    calm, docs0 = (d.get("calm") or [{}, {}])
    live, live8 = d.get("live") or {}, d.get("live8") or {}
    t1, t2, t3 = d.get("t1") or {}, d.get("t2") or {}, d.get("t3") or {}
    cw = calm.get("w") or 0
    ctx.check(f"R16: calm before any hand-off, got {calm}", calm.get("lit") == "" and cw > 0)
    ctx.check(f"R16: a hand-off lights its line, heavier than calm, got {live}", live.get("lit") == "live" and (live.get("w") or 0) > cw)
    ctx.check(f"R16: still live 8 s later with no end while a row carries it (no 4 s timeout), got {live8}", live8.get("lit") == "live")
    ctx.check(f"R16: its end leaves a trace of 1, marked last, lighter than live, heavier than calm, got {t1}",
              t1.get("lit") == "trace" and t1.get("hops") == "1" and t1.get("last") and cw < (t1.get("w") or 0) < (live.get("w") or 0))
    ctx.check(f"R16: the trace weighs more at 2 and 3 hand-offs, got {t1.get('w')} {t2.get('w')} {t3.get('w')}",
              t3.get("hops") == "3" and (t1.get("w") or 0) < (t2.get("w") or 0) < (t3.get("w") or 0))
    ctx.check(f"R16: only the newest hand-off's line is marked, got {d.get('lasts')}", d.get("lasts") == ["main>code"])
    ctx.check(f"R16: its hover, got {t3.get('hover')!r}",
              re.fullmatch(r"Carried 3 hand-offs; last at \d{1,2}:\d\d\D{0,4}: fix the retry in client\.py so it backs", t3.get("hover") or "") is not None)
    docs = d.get("docs") or {}
    ctx.check(f"R16: a line no hand-off took is never lit, got {docs}", docs.get("lit") == "" and abs((docs.get("w") or 0) - (docs0.get("w") or -1)) < 0.01)
    ctx.check(f"R16: a workflow's steps light in order, got {d.get('steps1')} -> {d.get('steps2')}",
              d.get("steps1") == ["working", "next"] and d.get("steps2") == ["done", "working"])


@test
def test_off_map_hand_off_stands_out(ctx: Ctx):
    d = _ranrun(ctx, "off")
    his, st = d.get("offmap") or {}, d.get("auto") or {}
    r = his.get("row") or {}
    ctx.check(f"R17: on a map of his the child no line brought is marked off the map, got {r}", r.get("off") == "1" and his.get("offs") == 1)
    ctx.check(f"R17: dashed in --off-map, not amber, not the accent, got {r.get('color')} {r.get('style')} off-map {his.get('offMap')} "
              f"warn {his.get('warn')}", r.get("style") == "dashed" and r.get("color") == his.get("offMap")
              and his.get("offMap") not in (his.get("warn"), his.get("accent")))
    ctx.check(f"R17: its hover, got {r.get('title')!r}", r.get("title") == "Not on the map: main started this itself")
    ctx.check(f"R17: the status line counts it, got {his.get('status')!r}", (his.get("status") or "").endswith("· 1 hand-off outside the map"))
    ctx.check(f"3.6.0.5 B11: on Auto it is main's pick, the one member of one group, got {st}",
              st.get("groups") == 1 and st.get("member") == ["agent: list the repo", "working"])
    ctx.check(f"R17 on Auto: nothing in the drawer is off the map, got {st.get('offs')}", st.get("offs") == 0)
    ctx.check(f"R17: and not counted, got {st.get('status')!r}", "outside the map" not in (st.get("status") or "x outside the map"))


@test
def test_off_map_row_is_drawn_from_its_senders_box(ctx: Ctx):
    s = _ranrun(ctx, "sender")
    ctx.check(f"R17: the reviewer coder started (no line) is a row in code's box, marked off, got {s}", s.get("in") == "code" and s.get("off") == "1")
    ctx.check(f"R17: its hover names the box that started it, got {s.get('title')!r}", s.get("title") == "Not on the map: code started this itself")
    ctx.check(f"R17: review, which started nothing, stays calm and holds no row, got {s}", s.get("review") == "idle" and s.get("reviewRows") == 0)


# -- 3.6.0.2 batch 5 (P3e): stepping in from a box, and its hover (R18 R43 R44) ---------------------------------------
_STEPS: dict = {}


def _stepin(ctx: Ctx, key: str) -> dict:
    """tests/helpers/studio_session_step_in.py, run once for the tests below."""
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Live drawer needs headless Chrome)")
    if not _STEPS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_session_step_in"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _STEPS.update(r=r, got=info)
    got, r = _STEPS["got"], _STEPS["r"]
    if got.get("skip"):
        raise SkipTest(got["skip"])
    ctx.check(f"the driver reached {key}, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", got.get(key) is not None)
    return got.get(key) or {}


_ENDED = r"ended at \d{1,2}:\d\d\D{0,4}"


@test
def test_step_in_card_pauses_and_steers_inline(ctx: Ctx):
    d = _stepin(ctx, "card")
    t, m, key = d.get("tester") or {}, d.get("main") or {}, d.get("key")
    ctx.check(f"R18: tester's step row opens the card inside the drawer, named tester, got {t.get('title')!r} {t.get('rows')}",
              t.get("inDrawer") is True and "tester" in (t.get("title") or "") and [r.get("key") for r in t.get("rows") or []] == [key])
    ctx.check(f"R18: Pause, Stop and the steer field there, aimed at tester ({key}), got {t.get('n')} steer at {t.get('steerKey')!r}",
              (t.get("n") or {}).get("pause") == 1 and (t.get("n") or {}).get("stop") == 1 and (t.get("n") or {}).get("steer") == 1
              and t.get("steerKey") == key and t.get("pauseText") == "Pause")
    ctx.check(f"R18: the card sits in the drawer's fixed corner, the same rect from main's box, got {t.get('rect')} {m.get('rect')}",
              _same(t.get("rect"), m.get("rect")) and m.get("inDrawer") is True)
    ctx.check(f"R18: Pause reached the session for tester, got {d.get('paused')}", len(d.get("paused") or []) == 1)
    ctx.check(f"R18: the button reads Resume once tester is paused, got {(d.get('resume') or {}).get('pauseText')!r}",
              (d.get("resume") or {}).get("pauseText") == "Resume")
    ctx.check(f"R18: a steer typed in the card reached the session for tester, got {d.get('steered')}",
              [x.get("text") for x in d.get("steered") or []] == ["use the fast suite"])
    b4, af = d.get("before") or {}, d.get("after") or {}
    ctx.check(f"R18: no section change and no panel opened, got {b4} -> {af}",
              af.get("tab") == b4.get("tab") and af.get("panels") == b4.get("panels") and af.get("card") is True)


@test
def test_step_in_target_from_rows_rechecked_at_confirm(ctx: Ctx):
    import re
    d = _stepin(ctx, "recheck")
    k = d.get("keys") or {}
    two = (d.get("two") or {}).get("rows") or []
    ctx.check(f"R18 (a): a box with two live children lists two rows, each its own Pause and Stop, got {two}",
              sorted(r.get("key") for r in two) == sorted([k.get("c1"), k.get("c2")]) and all(r.get("pause") and r.get("stop") for r in two))
    ctx.check(f"R18: a line's hit area is at least 10 px, got {d.get('hitWidth')}", (d.get("hitWidth") or 0) >= 10)
    ctx.check(f"R18 (b): the line main -> code opens c1's card, got {(d.get('line') or {}).get('rows')}",
              [r.get("key") for r in (d.get("line") or {}).get("rows") or []] == [k.get("c1")])
    ended = [r.get("ended") for r in (d.get("ended") or {}).get("rows") or []]
    ctx.check(f"R18 (b): ended before the confirm: nothing is sent, got {d.get('endedLog')}", d.get("endedLog") == [])
    ctx.check(f"R18 (b): the card reads 'ended at {{t}}', got {ended}", len(ended) == 1 and re.fullmatch(_ENDED, ended[0] or "") is not None)
    ctx.check(f"R18 (c): confirmed while it runs: one agent stop for c1, got {d.get('stops')}",
              [x.get("agent_id") for x in d.get("stops") or []] == ["c1"])
    ctx.check(f"R18 (c): never a session command (no shutdown), got {d.get('sessionCmds')}", d.get("sessionCmds") == 0)
    off = d.get("off") or {}
    ctx.check(f"R18 (d): an off-map line's card offers the map at its sender, got {off.get('map')!r} rows {off.get('rows')}",
              off.get("map") == "Open the map at main" and [r.get("key") for r in off.get("rows") or []] == [k.get("w1")])
    ctx.check(f"R18 (d): pressing it opens Agents on the map, got {d.get('offTab')!r}", "Agents" in (d.get("offTab") or ""))
    ctx.check(f"R18 (e): every card has 'Open in Agents -> Live', got {(d.get('line') or {}).get('liveText')!r} {off.get('liveText')!r}",
              (d.get("line") or {}).get("liveText") == "Open in Agents -> Live" and off.get("liveText") == "Open in Agents -> Live")
    ctx.check(f"R18 (e): it opens Agents and Session keeps this session, got {d.get('liveTab')!r} back {d.get('back')}",
              "Agents" in (d.get("liveTab") or "") and (d.get("back") or {}).get("sid") == k.get("c1", "||").split("|")[1])


@test
def test_done_step_card_has_no_stop(ctx: Ctx):
    d = _stepin(ctx, "done")
    want = {"step1": "1 plan · planner · or:v/planner · done", "step4": "4 review · reviewer · or:v/reviewer · next"}
    for name in ("step1", "step4", "calm"):
        s = d.get(name) or {}
        ctx.check(f"R18: {name}'s card shows the state only: no Stop, Pause or steer field, got {s.get('n')} rows {s.get('rows')}",
                  s.get("n") == {"pause": 0, "stop": 0, "steer": 0, "live": 1} and not s.get("rows") and s.get("inDrawer") is True)
        if name in want:
            ctx.check(f"R18: {name}'s card reads the row's own words, got {s.get('state')!r}", s.get("state") == want[name])
    calm = d.get("calm") or {}
    ctx.check(f"R18: a calm line's state, got {calm.get('state')!r}", calm.get("state") == "Starts when: main decides per task (from main)")


@test
def test_hover_card_rows(ctx: Ctx):
    d = _stepin(ctx, "hover")
    code = d.get("code") or {}
    ctx.check(f"R43: the hover card on code: name, agent, model, state, Starts when, its child, got {code}",
              code.get("kind") == "map" and code.get("lines") == ["coder", "agent", "or:v/coder", "working", "Starts when: always (from main)",
                                                                 "coder · or:v/coder · working"])
    blk = (d.get("block") or {}).get("lines") or []
    ctx.check(f"R43: on a workflow's block it says 'workflow W' and the workflow's state, got {blk}",
              blk[:5] == ["W", "workflow W", "working", "Starts when: main decides per task (from main)", "1 step 1 · coder · working"])
    ctx.check(f"R44: no When label and no connect dot on Session's drawing, got {d.get('labels')} labels {d.get('dots')} dots",
              d.get("labels") == 0 and d.get("dots") == 0)
    ctx.check(f"R43: a click opens the step-in card, not the hover, got {d.get('click')}", d.get("click") == {"card": True, "hover": False})


_BUILT: dict = {}
_T = r"\d{1,2}:\d\d\D{0,4}"


def _built(ctx: Ctx, key: str) -> dict:
    """tests/helpers/studio_session_just_built.py, run once for the tests below (P3 batch 6, R26-R32)."""
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Live drawer needs headless Chrome)")
    if not _BUILT:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_session_just_built"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=600, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _BUILT.update(r=r, got=info)
    got, r = _BUILT["got"], _BUILT["r"]
    if got.get("skip"):
        raise SkipTest(got["skip"])
    ctx.check(f"the driver reached {key}, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", got.get(key) is not None)
    return got.get(key) or {}


@test
def test_viewbar_word_reserved_nothing_moves(ctx: Ctx):
    d = _built(ctx, "word")
    b4, af, op = d.get("before") or {}, d.get("after") or {}, d.get("opened") or {}
    ctx.check(f"R29: the word slot is there and empty at first paint, got {b4.get('there')} {b4.get('text')!r}",
              b4.get("there") is True and b4.get("text") == "")
    ctx.check(f"R29: its min-width holds three digits, got {b4.get('minW')} for '0' = {b4.get('zero')}",
              (b4.get("minW") or 0) >= 3 * (b4.get("zero") or 99) - 0.5)
    ctx.check(f"R29: only Session's Live button has the word slot, got {b4.get('words')}", b4.get("words") == ["session-map"])
    ctx.check(f"R29: an applied build writes 'new' within 5 s, got {af.get('text')!r} after {d.get('took'):.1f} s",
              d.get("came") is True and af.get("text") == "new" and (d.get("took") or 99) <= 5)
    same = len(b4.get("rects") or []) == len(af.get("rects") or []) and all(
        p[0] == q[0] and all(abs(x - y) <= 0.5 for x, y in zip(p[1:], q[1:])) for p, q in zip(b4.get("rects") or [], af.get("rects") or []))
    ctx.check(f"R32: no view-bar button moved, got {b4.get('rects')} -> {af.get('rects')}", same)
    ctx.check(f"R32: nothing opened, the section is still Session, nothing popped up, got {af.get('pressed')} {af.get('section')!r} "
              f"drawer {af.get('drawer')} pops {af.get('pops')}",
              af.get("pressed") == b4.get("pressed") and af.get("section") == "session" and not af.get("drawer") and af.get("pops") == 0)
    ctx.check(f"R29: opening the drawer empties the word, in the same place, got {op.get('text')!r} {b4.get('rect')} -> {op.get('rect')}",
              op.get("text") == "" and _same(b4.get("rect"), op.get("rect")))


@test
def test_same_name_edit_redraws(ctx: Ctx):
    d = _built(ctx, "same")
    n, a, b, c = d.get("n") or 0, d.get("a") or {}, d.get("b") or {}, d.get("c") or {}
    ctx.check(f"R27 (a): a Builder card's edit of shop redraws it from the frame's body, no read before it, got {a}",
              a.get("ok") is True and a.get("reqs") == 0 and a.get("isNew") is True)
    ctx.check(f"R26 (b): a plain write redraws the open drawing, with no 'new' and no word, got {b} (first {n})",
              b.get("ok") is True and b.get("n") == n + 2 and b.get("isNew") is False and b.get("tag") is False and b.get("word") == "")
    ctx.check(f"R27 (c): closed and opened again it is the newest version, got {c}", c.get("ok") is True and c.get("n") == n + 2)


@test
def test_a_workflow_box_follows_its_files(ctx: Ctx):
    """3.6.0.9 V (the owner's point 34): Session's drawing (Agents -> 4 Live draws through the same code) shows a workflow
    box's steps as its file has them, whoever wrote it, and the model of its steps' agent as the agent's file has it."""
    d = _built(ctx, "follow")
    ctx.check(f"the drawing first shows the 2 steps, got {d.get('first')}", d.get("first") is True)
    ctx.check(f"(1) a plain write of the workflow: 3 step rows, got {d.get('plain')}", d.get("plain") == [True, 3])
    b = d.get("built") or []
    ctx.check(f"(2) a Builder card that wrote only the workflow: 4 step rows, 'new' on the new one, got {b}",
              len(b) == 3 and b[0] is True and b[1] == 4 and (b[2] or [False])[-1] is True)
    ctx.check(f"(3) the steps' agent file with another model: the rows say it, got {d.get('model')}", (d.get("model") or [False])[0] is True)


@test
def test_a_builders_own_write_is_read_once_never_twice(ctx: Ctx):
    """3.6.0.9 V: a card's map body, then the watcher's frame for that very write: the map is read zero times (the hashes
    match); a different plain write right after is read once and drawn. No time window."""
    r = (_built(ctx, "follow").get("reads") or {})
    ctx.check(f"drawn from the body, the watcher's frame heard, the next write drawn, got {r.get('drawn')}", r.get("drawn") == [True, True, True])
    urls = [u for u in r.get("urls") or [] if u.startswith("crew/map/review-flow")]
    ctx.check(f"one read in all (the different write), got {r.get('urls')}", len(urls) == 1)


@test
def test_what_was_built_is_said_again_after_a_reload(ctx: Ctx):
    """3.6.0.9 V batch 2 (the owner's point 34; reader V1, WHAT HE MEETS TODAY 5): after F5 the head, the ready lines and
    the "new" tags are said again, per session (this tab's sessionStorage); a session's row gone takes them with it; a
    storage that refuses writes changes nothing (the page works as before, nothing is kept)."""
    import re
    d = _built(ctx, "kept")
    bb, ba = d.get("b_before") or {}, d.get("b_after") or {}
    ctx.check(f"(1) on Auto: a head and ready lines before F5, got {bb}", bool(bb.get("head")) and len(bb.get("lines") or []) >= 1)
    ctx.check(f"(3) after F5 on Auto: the same head and ready lines, got {ba} (before {bb})",
              ba.get("head") == bb.get("head") and ba.get("lines") == bb.get("lines") and bool(ba.get("head")))
    ctx.check(f"(2) another session's page shows none of them, got {d.get('a_none')}", d.get("a_none") == {"head": "", "lines": [], "tags": []})
    ab, aa = d.get("a_before") or {}, d.get("a_after") or {}
    ctx.check(f"(2) a box added to the running map: its head and its tag, got {ab}",
              re.fullmatch(f"Changed in this session at {_T}; this session takes it at its next hand-off.", ab.get("head") or "") is not None
              and len(ab.get("tags") or []) == 1 and re.fullmatch(f"tester new {_T}", (ab.get("tags") or [""])[0]) is not None)
    ctx.check(f"(3) after F5: the same head and tag, got {aa} (before {ab})", aa == ab and bool(aa.get("head")))
    ag = d.get("a_again") or {}
    ctx.check(f"(3) its address opened again in the same tab (not a reload): the same head and tag, got {ag}", ag == ab and bool(ag.get("head")))
    ctx.check(f"(4) its row gone: its entry left this tab's storage, b's stayed, got {d.get('dropped')}", d.get("dropped") is True)
    ctx.check(f"(4) back and F5: nothing of it is said, got {d.get('a_dropped')}", d.get("a_dropped") == {"head": "", "lines": [], "tags": []})
    rf, ra = d.get("refused") or {}, d.get("refused_after") or {}
    ctx.check(f"(5) storage refusing writes: the head and tag are drawn as today, no page error, nothing written, got {rf}",
              rf.get("refusing") is True and bool(rf.get("head")) and any(t.startswith("tester2 new ") for t in rf.get("tags") or [])
              and rf.get("errors") == [] and rf.get("same") is True)
    ctx.check(f"(5) then F5: nothing kept, the page as today, got {ra}", ra.get("head") == "" and ra.get("tags") == [] and ra.get("errors") == [])


@test
def test_a_plain_write_of_a_workflow_is_said_in_words(ctx: Ctx):
    """3.6.0.9 V batch 2 (the owner's point 34): a workflow on a box of the session's drawing written by a plain write (no
    Builder card named it) is said in the truth block's lines, the page's clock time; a Builder card's own write is said by
    its head alone; no line for an agent file; the line is kept over F5. tests.test_step_runner proves the two facts."""
    import re
    d = _built(ctx, "plain")
    line = f"The workflow review changed at {_T}. A run already going keeps its steps; the next run takes the change."
    one = lambda got: len(got or []) == 1 and re.fullmatch(line, (got or [""])[0]) is not None  # noqa: E731
    ctx.check(f"the drawing first: 2 steps, no such line, got {d.get('first')}", d.get("first") == [True, []])
    p = d.get("plain") or [False, []]
    ctx.check(f"(1) a plain write: 3 steps and the one line, got {p}", p[0] is True and one(p[1]))
    g0, g1 = [g or {} for g in ((d.get("still") or []) + [{}, {}])[:2]]
    ctx.check(f"(1) nothing moved when the line came (its room held from the first draw: top box, truth block, Open), "
              f"got {g0} -> {g1}", bool(g0) and all(g0.get(k) is not None and g1.get(k) is not None
                                                     and abs(g0[k] - g1[k]) <= 0.5 for k in ("box", "truth", "open")))
    g = d.get("again") or [False, []]
    ctx.check(f"(2) another plain write: still one line for it, got {g}", g[0] is True and one(g[1]))
    cd = d.get("card") or [False, "", None]
    ctx.check(f"(3) a Builder card that wrote it: its head, not this line as well (also after the watcher's frame for that "
              f"write), got {cd}", cd[0] is True and re.fullmatch(f"Changed in this session at {_T}; this session takes it at its next "
                                                                 f"hand-off.", cd[1] or "") is not None and cd[2] == [])
    af = d.get("after") or [False, []]
    ctx.check(f"(4) a different plain write right after: said again, got {af}", af[0] is True and one(af[1]))
    ag = d.get("agent") or [False, None, None]
    ctx.check(f"(5) an agent file: no line, got {ag}", ag[0] is True and ag[1] == ag[2] and bool(ag[1]))
    rl = d.get("reload") or [False, []]
    ctx.check(f"(6) after F5 the line is still there, got {rl}", rl[0] is True and one(rl[1]))
    au = (d.get("auto") or []) + [None] * 5
    ctx.check(f"(7) on Auto, a workflow it ran: no line first, the one line after a plain write, got {au[:5]}",
              au[0] is True and au[1] == [] and one(au[3]))
    ctx.check(f"(7) on Auto nothing moved when the line came, got {au[2]} -> {au[4]}",
              bool(au[2]) and bool(au[4]) and all(au[2].get(k) is not None and au[4].get(k) is not None
                                                 and abs(au[2][k] - au[4][k]) <= 0.5 for k in ("box", "truth", "open")))


@test
def test_just_built_selected_once_only_when_untouched(ctx: Ctx):
    d = _built(ctx, "once")
    p, f, bk, s = d.get("plain") or {}, d.get("first") or {}, d.get("back") or {}, d.get("second") or {}
    # P3 batch 8, the coordinator's ruling: with one map there is no such row (the truth block above names it), so the
    # drawing has that room; the pair shows once the session built another map
    ctx.check(f"R30: one map and nothing built: no pair row and no head, got {p.get('text')!r} buttons {p.get('buttons')} bar {p.get('bar')}",
              p.get("text") == "" and p.get("buttons") == 0 and p.get("bar") is False)
    ctx.check(f"R30 (a): two maps: the pair on one 24 px line, Just built chosen and unlit, got {f}",
              f"Running: {SEVEN}" in (f.get("text") or "") and "Just built: review-flow" in (f.get("text") or "")
              and f.get("h") == 24 and (f.get("built") or {}).get("pressed") == "true" and f.get("map") == "review-flow"
              and f.get("lit") == 0 and f.get("working") == 0)
    ctx.check(f"P8: both buttons of the pair say their words whole (no ellipsis, nothing overflows), got "
              f"{(f.get('running') or {}).get('whole')} {(f.get('built') or {}).get('whole')}",
              (f.get("running") or {}).get("whole") is True and (f.get("built") or {}).get("whole") is True)
    ctx.check(f"R30 (a): Running: {SEVEN} draws it again, lit, got {bk.get('map')!r} lit {bk.get('lit')}",
              bk.get("map") == SEVEN and (bk.get("lit") or 0) > 0)
    ctx.check(f"R30 (a): a second build in the session only marks the tab, got {s}",
              s.get("map") == SEVEN and (s.get("built") or {}).get("marked") is True and (s.get("built") or {}).get("pressed") == "false")
    h, ho, pr = d.get("held") or {}, d.get("held_out") or {}, d.get("pressed") or {}
    ctx.check(f"R30 (b): the pointer on the drawing: only marked, and no jump once it leaves, got {h.get('map')!r} -> {ho.get('map')!r}",
              h.get("map") == SEVEN and (h.get("built") or {}).get("marked") is True and ho.get("map") == SEVEN)
    ctx.check(f"R30 (c): the pair pressed before: a later build only marks its tab, got {pr}",
              pr.get("map") == SEVEN and (pr.get("built") or {}).get("marked") is True and "Just built: third" in (pr.get("text") or ""))


@test
def test_just_built_workflow_on_no_map_and_box_on_the_running_map(ctx: Ctx):
    import re
    d = _built(ctx, "heads")
    w, o = d.get("workflow") or {}, d.get("opened") or {}
    ctx.check(f"R31 (a): a workflow on no map, got {w.get('head')!r} [{w.get('headButton')}]",
              w.get("head") == "Just built: the workflow solo. It is on no map, so no session runs it yet." and w.get("headButton") == "Open in Workflows")
    ctx.check(f"R32: the head changed no section, got {d.get('workflow_section')!r}", d.get("workflow_section") == "session")
    ctx.check(f"R31 (a): [Open in Workflows] opens Agents on Workflows with solo, got {o}",
              o.get("section") == "agents" and o.get("view") == "workflows" and o.get("text") is True)
    r = d.get("running") or {}
    ctx.check(f"R31 (b): a box added to the running map: one map, tagged 'new {{t}}' alone, got {r}",
              "Just built" not in (r.get("text") or "") and re.fullmatch(f"new {_T}", r.get("tag") or "") is not None and r.get("others") == ["tester"]
              and r.get("map") == "shop")
    ctx.check(f"R31 (b): its head, got {r.get('head')!r}",
              re.fullmatch(f"Changed in this session at {_T}; this session takes it at its next hand-off.", r.get("head") or "") is not None)
    ot = d.get("other") or {}
    ctx.check(f"R31 (c): another map, got {ot.get('head')!r}",
              re.fullmatch(f"Just built in this session at {_T}. This session does not run on it.", ot.get("head") or "") is not None)
    on = d.get("other_next") or {}
    ctx.check(f"R31 (c) + R36's row: another map new sessions now run on, got {on.get('head')!r}",
              re.fullmatch(f"Just built in this session at {_T}. This session does not run on it. New sessions run on fourth.",
                           on.get("head") or "") is not None)
    ctx.check(f"R31 (c): S13 is on screen once in the drawer (the truth block's T2), the head adds only 'New sessions run on "
              f"fourth.', got {on.get('s13')} in {on.get('truth')!r}", on.get("s13") == 1 and on.get("truth") == "T2")
    # P3 batch 8, the coordinator's ruling: the head's words are never cut (no clamp), they wrap whole across the drawer, its
    # buttons sit on their own row, and it takes room inside the drawing's box only once a build lands
    lg = d.get("long") or {}
    sentence = "Just built: the workflow code-review-and-tests-for-every-change-made-now. It is on no map, so no session runs it yet."

    def whole(w: dict) -> bool:
        return (w or {}).get("text") == sentence and w.get("scrollH") == w.get("clientH") and w.get("clamp") in ("none", "0", "")\
            and w.get("display") != "-webkit-box" and (w.get("last") or {}).get("inBox") is True and (w.get("last") or {}).get("inRoom") is True\
            and w.get("ownRow") is True
    for k, w in (("1280 x 800", (lg.get("still") or {}).get("whole")), ("a 412 px drawer", d.get("long412"))):
        ctx.check(f"R31 (e) at {k}: the long head shows its whole sentence, unclamped, its last word on screen, [Open in Workflows] "
                  f"on its own row under the words, got {w}", whole(w))
    ctx.check(f"R31 (e): the 412 px check ran at 412 px, got {(d.get('long412') or {}).get('width')}",
              abs(((d.get("long412") or {}).get("width") or 0) - 412) <= 1)
    css = "".join(p.read_text(encoding="utf-8") for p in (REPO / "halo_harness" / "studio" / "static" / "dist").rglob("*.css"))
    ctx.check("no rule of the built CSS clamps the head's words", not re.search(r"\.mp-built-text[^{}]*\{[^}]*line-clamp", css))
    for k in ("workflow", "running"):
        st = (d.get(k) or {}).get("still") or {}
        ctx.check(f"Controls hold still ({k}): a head landing moves no control; the drawing moves down once, inside its own "
                  f"box, got moved {st.get('moved')} top +{st.get('top')}", st.get("moved") == {} and (st.get("top") or 0) > 0)
    ctx.check(f"the switch of the map new sessions use reached the truth block before the heads after it were compared (P9 "
              f"batch 3: R20 measures the block again for a name it did not have), got {on.get('named')}", on.get("named") is True)
    for k in ("other", "other_next", "long"):
        st = (d.get(k) or {}).get("still") or {}
        ctx.check(f"Controls hold still ({k}): no control moved, got {st.get('moved')}", st.get("moved") == {})
    sf = d.get("same_frame") or {}
    ctx.check(f"a frame that changes nothing in the head's words moves nothing (the head, its words, its button, the drawing), "
              f"got {sf.get('moved')}", sf.get("moved") == {} and bool((sf.get("now") or {}).get("session-built-open")))
    ctx.check(f"R29 (d): the tag stays over turns and a fleet read, got {d.get('kept')}", d.get("kept") is True)
    ctx.check(f"R29 (d): once the session ended the tags are gone, got {d.get('ended')}", d.get("ended") is True)


@test
def test_no_fetch_before_the_first_draw(ctx: Ctx):
    d = _built(ctx, "fetch")
    p = d.get("painted") or {}
    ctx.check(f"R28: the truth block (naming shop) and the status line are painted with every crew/map answer held, and with one "
              f"map no pair row (P3 batch 8), got {p}",
              "shop" in (p.get("truth") or "") and bool(p.get("status")) and p.get("pair") == "" and p.get("done") == 0)
    # the driver opens the page only once Studio's watcher has told of its own write of shop's file: a files_changed naming
    # the running map while its read is held is a new version, and a second read of it is right (mapFiles.ts)
    ctx.check(f"R28: no map file changed while the first read was held (the step's own writes told before the page opened), "
              f"got {p.get('told')}", p.get("told") == [])
    asked = p.get("asked") or []
    ctx.check(f"R28 R50: then one read of the running map, by scope and path, soft, got {asked}",
              len(asked) == 1 and asked[0].startswith("crew/map/shop?") and all(k in asked[0] for k in ("scope=yours", "path=", "soft=1")))
    ctx.check(f"R28: a body the frame brought is drawn with no request, got {d.get('body')}", d.get("body") == [])
    lo = d.get("left_out") or []
    ctx.check(f"R28: a body left out (over 64 KB) is one soft read after the draw, got {lo}",
              len(lo) == 1 and lo[0].startswith("crew/map/big?") and "soft=1" in lo[0])
    ctx.check(f"R28: outcomes left and failed read nothing, got {d.get('left_failed')}", d.get("left_failed") == [])
    import re
    ctx.check(f"R28: a removed map says so, got {d.get('removed')!r}", re.fullmatch(f"This map was removed at {_T}.", d.get("removed") or "") is not None)
    q = d.get("quiet") or {}
    ctx.check(f"R28: T4, T10, T8 and Empty read no map, got {q}",
              q.get("seen") == ["T4", "T10", "T8", "Empty"] and q.get("reads") == [])
    ctx.check(f"R28: no request failed, got {d.get('failed')}", d.get("failed") == [])


# At 1280 x 800, one map and nothing built, on the tree before batch 8 (HEAD 9d8b6e20, the Linux VM): the drawing's box
# was 246 px (its scroll box 133, '↓ 7 more below'), the truth block and status line 192 px, and 114 px stood between
# them and the drawing's box (the pair row, the head's two reserved lines, the link and zoom row, their gaps).
ROOM_BEFORE_1280, TRUTH_BEFORE_1280, OVER_BEFORE_1280 = 246, 192, 114
ROOM_BAR_1280 = 306  # the coordinator's ruling of P4 batch 11


@test
def test_drawing_room_at_1280_one_map_no_build(ctx: Ctx):
    # P3 batch 8, the coordinator's ruling: the two-map row only when there are two maps, the head's room only once a build
    # lands and inside the drawing's box: with one map and no build the drawing has that room back, and "↓ n more below"
    # still counts the boxes wholly below.
    d = _built(ctx, "room")
    for size in ("1280x800", "1440x900", "1920x1080"):
        r = d.get(size) or {}
        ctx.check(f"{size}: no pair row and no head room with one map and no build, got {r}", r.get("pair") is False and r.get("bar") is False)
        n = r.get("below")
        ctx.check(f"{size}: '↓ n more below' says the boxes wholly below ({n}), got {r.get('text')!r}",
                  isinstance(n, int) and n >= 0 and r.get("text") == (f"↓ {n} more below" if n else ""))
    r = d.get("1280x800") or {}
    ctx.check(f"1280 x 800: what stands between the truth block and the drawing is at least 60 px less than before "
              f"({OVER_BEFORE_1280} px), got {r.get('over')}", r.get("over") is not None and r["over"] <= OVER_BEFORE_1280 - 60)
    # P4 batch 11, the coordinator's ruling (the truth block reserves nothing for names it does not have): THE BAR, literal
    sizes = {k: (d.get(k) or {}).get("room") for k in ("1280x800", "1440x900", "1920x1080")}
    ctx.check(f"1280 x 800: the drawing's box is at least {ROOM_BAR_1280} px tall (it was {ROOM_BEFORE_1280} before P3's batch 8, "
              f"278 after it), got {r.get('room')} (all sizes {sizes}, truth block {r.get('truth')})",
              (r.get("room") or 0) >= ROOM_BAR_1280)


@test
def test_stop_confirmed_after_it_ended_says_so_at_every_door(ctx: Ctx):
    # P3 batch 8 (the checker of batch 5): a control never has no visible effect. Stop asked in Agents' row, the Feed, the
    # command palette and the k key; the agent ends before Yes: the confirm goes, nothing is sent, and one line in the
    # step-in card's words (truth.ts endedAt) says so where Stop was pressed: the row's own line, or a toast.
    import re
    d = _stepin(ctx, "doors")
    for door in ("agents", "feed", "palette", "key"):
        g = d.get(door) or {}
        want = f"ended at {_T}" if door in ("agents", "feed") else f"\\S.* ended at {_T}"
        ctx.check(f"{door}: Yes after the agent ended: the confirm is gone, nothing sent, the line says so, got {g}",
                  re.fullmatch(want, g.get("line") or "") is not None and g.get("confirm") is False and g.get("stops") == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
