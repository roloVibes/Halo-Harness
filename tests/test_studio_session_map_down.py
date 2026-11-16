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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
