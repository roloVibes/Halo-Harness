"""tests.test_sheet_place -- Halo 3.6.0.14 OP1 ("the box opens in place"), rules O1-1 and O1-4, run in node through
tests/helpers/node_ts.py (no browser, no model; runs anywhere).

1. Where the sheet goes (routes/crew/map/sheetPlace.ts `agentsPlace`, `drawerPlace`, `anchorSel`): Agents -> Live puts
   it 440 wide at its box's top-left (top-right near the view's right), at most the view less 16 tall, lifted till its
   bottom is 8 inside; Session's drawer puts it the drawer less 16 wide at left 8, 6 px under its box when 240 fit below,
   else 6 px over it, else today's place; with no anchor, the view's top-right (Agents) or today's place (drawer); an
   anchor partly out of view is clamped 8 inside.
2. The head holds still (`sheetHead`): the state line holds the rows of its longest state and NOW two rows (the held
   form), over a tool change and an ask.
3. (O1-2) What folds the sheet (`sheetClose`) and where its unfold starts (`fromInset`, `insetOf`).
4. (O1-6) Last said: the sheet opens at the GET's answer or at 1 s (`saidOpen`); its words (truthBits.ts `saidLines`,
   `saidParts`, `secsClock`); the one request ends with the sheet (a source check of StepInSaid.tsx).
Every frame here is invented. Run: python -m tests.test_sheet_place
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SRC = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"
MODS = {"sp": "routes/crew/map/sheetPlace.ts", "room": "routes/crew/map/nowRoom.ts", "tb": "routes/crew/map/truthBits.ts"}


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
    ctx.check(f"neither 240 below (136) nor above (136): today's place, at most the drawer less 56, 40 from the foot, "
              f"got {got.get('tall')}", got.get("tall") == P(8, 16, 318, 344, "fixed"))
    ctx.check(f"... as tall as its words when they are shorter, got {got.get('short')}",
              got.get("short") == P(8, 260, 318, 100, "fixed"))
    # batch 2 (seen on the Linux VM at 1280 x 500): the drawing's scroll box is far lower than the drawer (48 of 400 px);
    # today's place is the drawer's (40 from its foot, at most the drawer less 56), never a sheet with no room at all
    low = _places("drawerPlace", {"low": [R(24, 4, 200, 122), R(0, 0, 334, 48), {"width": 334, "height": 400}, 336]})
    ctx.check(f"a 48 px scroll box in a 400 px drawer: today's place, as tall as its words (336), got {low.get('low')}",
              low.get("low") == P(8, 24, 318, 336, "fixed"))


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


# ------------------------------------------------------------------------------- batch 2: O1-2 what folds it, O1-6 Last said

@test
def test_what_folds_the_sheet(ctx: Ctx):
    """O1-2: `sheetClose(e)` over invented events. A pointer-down inside the sheet, on the drawing's slot (its own press
    folds the sheet first, R4) or inside the Stop confirm's scrim folds nothing; on a box or a line of this drawing it is
    the click's pick (that box's sheet opens, or this one closes); anywhere else it folds -- a box outside the drawing (the
    Feed's head) among them. Escape outside a text field folds; a wheel over the drawing folds, over the sheet it scrolls
    the body; a zoom since the open folds."""
    cases = {
        "inside": [{"kind": "pointer", "at": "sheet"}, "none"], "pick": [{"kind": "pointer", "at": "pick"}, "pick"],
        "slot": [{"kind": "pointer", "at": "slot"}, "none"], "scrim": [{"kind": "pointer", "at": "scrim"}, "none"],
        "pan": [{"kind": "pointer", "at": "pan"}, "fold"], "else": [{"kind": "pointer", "at": "else"}, "fold"],
        "esc": [{"kind": "key", "at": "else", "key": "Escape"}, "fold"],
        "escInSheet": [{"kind": "key", "at": "sheet", "key": "Escape"}, "fold"],
        "escField": [{"kind": "key", "at": "sheet", "key": "Escape", "field": True}, "none"],
        "otherKey": [{"kind": "key", "at": "else", "key": "a"}, "none"],
        "wheelPan": [{"kind": "wheel", "at": "pan"}, "fold"], "wheelBox": [{"kind": "wheel", "at": "pick"}, "fold"],
        "wheelSheet": [{"kind": "wheel", "at": "sheet"}, "none"], "zoom": [{"kind": "zoom", "at": "else"}, "fold"],
    }
    js = "const out = {};\nfor (const [k, [e]] of Object.entries(D)) out[k] = M.sp.sheetClose(e);\nconsole.log(JSON.stringify(out));"
    got = _run(["sp"], js, cases)
    for k, (e, want) in cases.items():
        ctx.check(f"{k}: {e} -> {want!r}, got {got.get(k)!r}", got.get(k) == want)


@test
def test_the_unfold_starts_at_the_boxs_rectangle(ctx: Ctx):
    """O1-2: `fromInset(sheet, anchor)` -- the four insets (top, right, bottom, left), each clamped to 0..the sheet's size,
    that cut the sheet down to its box's rectangle; `insetOf` writes them as the clip's start."""
    cases = {"s4": [P(496, 77, 440, 430, "corner"), R(496, 77, 720, 160)],
             "lifted": [P(100, 162, 440, 430, "corner"), R(100, 400, 300, 480)],
             "turned": [P(860, 50, 440, 300, "right"), R(1000, 50, 1300, 150)],
             "bigger": [P(100, 100, 440, 300, "corner"), R(0, 0, 2000, 2000)]}
    js = ("const out = {};\nfor (const [k, a] of Object.entries(D)) { const i = M.sp.fromInset(...a); out[k] = [i, M.sp.insetOf(i)]; }\n"
          "console.log(JSON.stringify(out));")
    got = _run(["sp"], js, cases)
    want = {"s4": ({"top": 0, "right": 216, "bottom": 347, "left": 0}, "inset(0px 216px 347px 0px)"),
            "lifted": ({"top": 238, "right": 240, "bottom": 112, "left": 0}, "inset(238px 240px 112px 0px)"),
            "turned": ({"top": 0, "right": 0, "bottom": 200, "left": 140}, "inset(0px 0px 200px 140px)"),
            "bigger": ({"top": 0, "right": 0, "bottom": 0, "left": 0}, "inset(0px 0px 0px 0px)")}
    for k, (ins, css) in want.items():
        g = got.get(k) or [None, None]
        ctx.check(f"{k}: {ins} written {css!r}, got {g}", g[0] == ins and g[1] == css)


@test
def test_the_sheet_opens_at_its_answer_or_at_one_second(ctx: Ctx):
    """O1-6: the sheet opens when the one GET answers or at 1 s, whichever is first (the times are given: no clock)."""
    js = ("console.log(JSON.stringify({wait: M.sp.SAID_WAIT_MS, no: [0, 500, 999, 1000, 4000].map((t) => M.sp.saidOpen(false, t)),"
          " yes: [0, 200].map((t) => M.sp.saidOpen(true, t))}));")
    got = _run(["sp"], js, None)
    ctx.check(f"it waits 1 s at the most, got {got.get('wait')}", got.get("wait") == 1000)
    ctx.check(f"not answered: closed till 1 s, open from 1 s, got {got.get('no')}", got.get("no") == [False, False, False, True, True])
    ctx.check(f"answered: open at once, got {got.get('yes')}", got.get("yes") == [True, True])


REST = "The rest is in the session export: Export on Session's Feed, or halo session export S-1."


@test
def test_last_said_words(ctx: Ctx):
    """O1-6: `saidLines(got, sid)` letter for letter, each `ts` in seconds and its hh:mm:ss two digits each, 24-hour, local
    (compared with this process's own Date parts, never a zone of this machine); `saidParts` puts a late answer at the
    body's end with "Reading what it said..." kept where it was."""
    js = r"""const T = 1700000000, hms = (t) => { const d = new Date(t * 1000);
  return [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, "0")).join(":"); };
const E = (kind, text, ts) => ts == null ? {kind, text} : {kind, text, ts};
const cut = "a".repeat(2000) + "... (1234 more characters)";
const G = {
  mixed: {events: [E("text", "old words", T), E("thinking", "a later thought", T + 5), E("text", "new words", T + 9), E("thinking", "last thought", T + 12)]},
  handback: {events: [E("thinking", "checking", T), E("handback", "done: 3 files changed", T + 30)]},
  thought: {events: [E("thinking", "which file first", T + 61)]},
  notime: {events: [E("text", "no clock here")]}, notimeThought: {events: [E("thinking", "a bare thought")]},
  none: {events: []}, empty: {}, reading: "reading", error: {error: "no answer"}, cut: {events: [E("text", cut, T)]}};
const out = {lines: {}, want: {mixed: hms(T + 9), handback: hms(T + 30), thought: hms(T + 61), cut: hms(T)}, cut};
for (const [k, g] of Object.entries(G)) out.lines[k] = M.tb.saidLines(g, "S-1");
out.clock = [M.tb.secsClock(T), hms(T)];
out.late = M.tb.saidParts("reading", G.thought, "S-1");
out.atOpen = M.tb.saidParts(G.thought, G.thought, "S-1");
out.still = M.tb.saidParts("reading", "reading", "S-1");
console.log(JSON.stringify(out));"""
    got = _run(["tb"], js, None)
    L, W = got.get("lines") or {}, got.get("want") or {}
    ctx.check(f"secsClock is hh:mm:ss from Date's own parts, got {got.get('clock')}",
              bool(got.get("clock")) and got["clock"][0] == got["clock"][1] and len(got["clock"][0]) == 8)
    ctx.check(f"the newest text, after a later thought, got {L.get('mixed')}", L.get("mixed") == [f"Last said at {W.get('mixed')}: new words"])
    ctx.check(f"a done helper's handback is what it said, got {L.get('handback')}",
              L.get("handback") == [f"Last said at {W.get('handback')}: done: 3 files changed"])
    ctx.check(f"a thought only, got {L.get('thought')}", L.get("thought") == [f"Last thought at {W.get('thought')}: which file first"])
    ctx.check(f"no time: 'Last said:' and 'Last thought:', got {L.get('notime')} {L.get('notimeThought')}",
              L.get("notime") == ["Last said: no clock here"] and L.get("notimeThought") == ["Last thought: a bare thought"])
    ctx.check(f"nothing said, got {L.get('none')} {L.get('empty')}", L.get("none") == ["Nothing said yet."] and L.get("empty") == ["Nothing said yet."])
    ctx.check(f"before the answer, got {L.get('reading')}", L.get("reading") == ["Reading what it said..."])
    ctx.check(f"an error, got {L.get('error')}", L.get("error") == ["Could not read what it said: no answer"])
    ctx.check(f"a cut text, then where the rest is, got {(L.get('cut') or [''])[-1]!r}",
              L.get("cut") == [f"Last said at {W.get('cut')}: {got.get('cut')}", REST])
    th = [f"Last thought at {W.get('thought')}: which file first"]
    ctx.check(f"a late answer: 'Reading...' stays, the answer at the body's end, got {got.get('late')}",
              got.get("late") == {"here": ["Reading what it said..."], "end": th})
    ctx.check(f"answered at open: in its place, got {got.get('atOpen')}", got.get("atOpen") == {"here": th, "end": []})
    ctx.check(f"still reading, got {got.get('still')}", got.get("still") == {"here": ["Reading what it said..."], "end": []})


@test
def test_the_said_request_ends_with_the_sheet(ctx: Ctx):
    """O1-6: ONE GET of the tail at the click, aborted and its answer dropped when the sheet goes; one timer, cleared; no
    interval. The request and its timer live in StepInSaid.tsx only."""
    p = SRC / "routes/crew/map/StepInSaid.tsx"
    src = p.read_text(encoding="utf-8") if p.is_file() else ""
    ctx.check("StepInSaid.tsx exists", bool(src))
    ctx.check("one api.get( of the agent's /tail, n 20, kinds text,thinking,handback",
              len(re.findall(r"\bapi\.get[<(]", src)) == 1 and "/tail" in src and "n: 20" in src and 'kinds: "text,thinking,handback"' in src)
    ctx.check("its cleanup clears the timer, aborts the request and drops the answer",
              "clearTimeout(" in src and ".abort(" in src and "dropped" in src)
    ctx.check("no setInterval(", "setInterval(" not in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
