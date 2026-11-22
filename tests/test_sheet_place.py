"""tests.test_sheet_place -- Halo 3.6.0.14 OP1 ("the box opens in place"), rules O1-1 and O1-4, run in node through
tests/helpers/node_ts.py (no browser, no model; runs anywhere).

1. Where the sheet goes (routes/crew/map/sheetPlace.ts `agentsPlace`, `drawerPlace`, `anchorSel`): Agents -> Live puts
   it 440 wide at its box's top-left (top-right near the view's right), at most the view less 16 tall, lifted till its
   bottom is 8 inside; Session's drawer puts it the drawer less 16 wide at left 8, 6 px under its box when 240 fit below,
   else 6 px over it, else today's place; with no anchor, the view's top-right (Agents) or today's place (drawer); an
   anchor partly out of view is clamped 8 inside.
2. The head holds still (`sheetHead`): the state line holds the rows of its longest state and NOW two rows (the held
   form), over a tool change and an ask.
Every frame here is invented. Run: python -m tests.test_sheet_place
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SRC = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"
MODS = {"sp": "routes/crew/map/sheetPlace.ts", "room": "routes/crew/map/nowRoom.ts"}


def _run(mods: list, body: str, data) -> dict:
    """`body` runs with M.<name> = the imported modules and D = `data`; it prints one JSON line."""
    from tests.helpers import node_ts
    head = "".join(f"M.{m} = await import({json.dumps((SRC / MODS[m]).resolve().as_uri())});\n" for m in mods)
    return node_ts.run(f"const M = {{}};\n{head}const D = {json.dumps(data)};\n{body}")


def R(left: float, top: float, right: float, bottom: float) -> dict:
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def P(left: float, top: float, width: float, height: float, side: str) -> dict:
    return {"left": left, "top": top, "width": width, "height": height, "side": side}


def _places(fn: str, cases: dict) -> dict:
    js = f"const out = {{}};\nfor (const [k, a] of Object.entries(D)) out[k] = M.sp.{fn}(...a);\nconsole.log(JSON.stringify(out));"
    return _run(["sp"], js, cases)


VIEW = R(0, 0, 1356, 600)  # Agents' scroll box, in the px of its frame


@test
def test_agents_sheet_opens_at_its_boxs_top_left(ctx: Ctx):
    got = _places("agentsPlace", {"s4": [R(496, 77, 720, 160), VIEW, 430]})
    ctx.check(f"S4: top-left (496, 77), 440 wide, 430 tall, no lift, got {got.get('s4')}",
              got.get("s4") == P(496, 77, 440, 430, "corner"))


@test
def test_agents_sheet_turns_to_top_right_near_the_views_right(ctx: Ctx):
    got = _places("agentsPlace", {"near": [R(1000, 50, 1300, 150), VIEW, 300],
                                  "edge": [R(908, 50, 1100, 150), VIEW, 300]})
    ctx.check(f"440 would pass the view's right less 8: its right at the box's right, got {got.get('near')}",
              got.get("near") == P(860, 50, 440, 300, "right"))
    ctx.check(f"exactly to the view's right less 8: still the corner, got {got.get('edge')}",
              got.get("edge") == P(908, 50, 440, 300, "corner"))


@test
def test_agents_sheet_is_lifted_till_its_bottom_is_8_inside(ctx: Ctx):
    got = _places("agentsPlace", {"low": [R(100, 400, 300, 480), VIEW, 430]})
    p = got.get("low") or {}
    ctx.check(f"lifted: its bottom 8 inside the view (592), got {p}", p == P(100, 162, 440, 430, "corner"))


@test
def test_agents_sheet_is_at_most_the_view_less_16(ctx: Ctx):
    got = _places("agentsPlace", {"tall": [R(100, 77, 300, 160), VIEW, 2000]})
    ctx.check(f"h 2000 in a 600 tall view: 584 tall at top 8, got {got.get('tall')}",
              got.get("tall") == P(100, 8, 440, 584, "corner"))


DRAWER_VIEW = R(0, 0, 334, 690)
FRAME = {"width": 334, "height": 690}


@test
def test_drawer_sheet_6_under_its_box_when_240_fit_below(ctx: Ctx):
    s5 = R(24, 259, 200, 359)
    got = _places("drawerPlace", {"s5": [s5, DRAWER_VIEW, FRAME, 430], "short": [s5, DRAWER_VIEW, FRAME, 200]})
    ctx.check(f"S5: 318 wide at x 8, 6 under (y 365), 317 tall (690 - 8 - 365), got {got.get('s5')}",
              got.get("s5") == P(8, 365, 318, 317, "below"))
    ctx.check(f"words shorter than the room: as tall as its words, got {got.get('short')}",
              got.get("short") == P(8, 365, 318, 200, "below"))


@test
def test_drawer_sheet_6_over_its_box_when_only_above_fits(ctx: Ctx):
    a = R(24, 500, 200, 600)
    got = _places("drawerPlace", {"over": [a, DRAWER_VIEW, FRAME, 300], "big": [a, DRAWER_VIEW, FRAME, 900]})
    p = got.get("over") or {}
    ctx.check(f"76 below, 486 above: over it, its bottom 6 over the box (494), got {p}", p == P(8, 194, 318, 300, "above"))
    ctx.check(f"taller words: its top kept 8 inside the view, got {got.get('big')}", got.get("big") == P(8, 8, 318, 486, "above"))


@test
def test_drawer_sheet_takes_todays_place_when_neither_fits(ctx: Ctx):
    view, frame, a = R(0, 0, 334, 400), {"width": 334, "height": 400}, R(24, 150, 200, 250)
    got = _places("drawerPlace", {"tall": [a, view, frame, 430], "short": [a, view, frame, 100]})
    ctx.check(f"neither 240 below (136) nor above (136): today's place, at most the view less 56, 40 from the foot, "
              f"got {got.get('tall')}", got.get("tall") == P(8, 16, 318, 344, "fixed"))
    ctx.check(f"... as tall as its words when they are shorter, got {got.get('short')}",
              got.get("short") == P(8, 260, 318, 100, "fixed"))


@test
def test_anchor_of_each_target(ctx: Ctx):
    ids = ["member:a7", "box:code", "group:2", "step:review:3", "head:review", "line:main>group:2", "line:code>review",
           "line:main>workflow:ship", "calm", "line:nothing", "step:bare"]
    js = ("const out = {};\nfor (const k of D) out[k] = M.sp.anchorSel(k);\n"
          "out.esc = M.sp.anchorSel('member:a\"b', (s) => s.replace(/\"/g, '\\\\\"'));\nconsole.log(JSON.stringify(out));")
    got = _run(["sp"], js, ids)
    want = {"member:a7": '[data-member="a7"]', "box:code": '[data-box="code"]', "group:2": '[data-box="group:2"]',
            "step:review:3": '[data-box][data-workflow="review"]', "head:review": '[data-box][data-workflow="review"]',
            "line:main>group:2": '[data-box="group:2"]',
            "line:code>review": '.mp-label[data-from="code"][data-to="review"]',
            "line:main>workflow:ship": '.mp-label[data-from="main"][data-to="workflow:ship"]',
            "calm": None, "line:nothing": None, "step:bare": None}
    for k, v in want.items():
        ctx.check(f"{k} -> {v!r}, got {got.get(k)!r}", got.get(k) == v)
    ctx.check(f"each name goes through the escape it is given, got {got.get('esc')!r}", got.get("esc") == '[data-member="a\\"b"]')


@test
def test_no_anchor_and_a_narrow_view(ctx: Ctx):
    narrow = R(0, 0, 400, 600)
    got = _places("agentsPlace", {"none": [None, VIEW, 300], "narrow": [R(100, 50, 300, 150), narrow, 300],
                                  "above": [R(-30, -50, 200, 40), VIEW, 300]})
    ctx.check(f"no anchor in Agents: the view's top-right, 8 inside, got {got.get('none')}",
              got.get("none") == P(908, 8, 440, 300, "fixed"))
    ctx.check(f"a view under 456 px: the view less 16 wide, kept 8 inside, got {got.get('narrow')}",
              got.get("narrow") == P(8, 50, 384, 300, "right"))
    ctx.check(f"an anchor partly out of view: clamped 8 inside, got {got.get('above')}",
              got.get("above") == P(8, 8, 440, 300, "corner"))
    dr = _places("drawerPlace", {"none": [None, DRAWER_VIEW, FRAME, 430]})
    ctx.check(f"no anchor in the drawer: today's place, got {dr.get('none')}", dr.get("none") == P(8, 220, 318, 430, "fixed"))


@test
def test_the_sheets_head_holds_over_three_frames(ctx: Ctx):
    """O1-4: one head over three frames (working with a short tool, working with a tool name too long for two rows, then
    waiting after an ask) at the Agents width (440) and the drawer's (318). The description's length is computed from the
    width so the "working" line fills its rows exactly and "waiting on you" needs one more."""
    js = """const out = {};
for (const W of [440, 318]) {
  const tw = M.sp.textWidth(W), per = M.room.perRow(tw);
  const head = "reviewer: ", tail = " · kimi-k3 · ";
  const desc = "c".repeat(2 * per - (head + tail + "working").length);
  const line = (st) => head + desc + tail + st;
  const tool = "mcp__deck__insert_chart_from_range_x_".repeat(8).slice(0, 2 * per);
  const frames = [[line("working"), {text: "Grep · ", secs: "4 s"}], [line("working"), {text: tool + " · ", secs: "9 s"}],
                  [line("waiting on you"), {text: "waiting for you · ", secs: "2 s"}]];
  out[W] = {heads: frames.map(([t, n]) => M.sp.sheetHead(W, t, n)),
            own: [M.room.rowsOf(line("working"), "", tw), M.room.rowsOf(line("waiting on you"), "", tw)],
            model: M.room.stateRows("kimi-k3", tw)};
}
console.log(JSON.stringify(out));"""
    got = _run(["sp", "room"], js, None)
    for w in ("440", "318"):
        g = got.get(w) or {}
        heads, own = g.get("heads") or [{}] * 3, g.get("own") or [0, 0]
        ctx.check(f"{w}: the working line fills 2 rows, the waiting line needs 3, got {own}", own == [2, 3])
        ctx.check(f"{w}: the state line holds 3 rows in all three frames, got {[h.get('stateRows') for h in heads]}",
                  [h.get("stateRows") for h in heads] == [3, 3, 3])
        ctx.check(f"{w}: NOW holds 2 rows in all three frames, got {[h.get('nowRows') for h in heads]}",
                  [h.get("nowRows") for h in heads] == [2, 2, 2])
        ctx.check(f"{w}: a tool too long for two rows reads the held form 'a tool · ', got {heads[1].get('text')!r}",
                  heads[1].get("text") == "a tool · " and heads[1].get("secs") == "9 s")
        ctx.check(f"{w}: the short words are read as they are, got {heads[0].get('text')!r} {heads[2].get('text')!r}",
                  heads[0].get("text") == "Grep · " and heads[2].get("text") == "waiting for you · ")
        ctx.check(f"{w}: nowRoom's stateRows alone ({g.get('model')}) would hold fewer rows than the ask needs",
                  (g.get("model") or 0) < 3)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
