"""tests.test_studio_room -- Halo 3.6.0.0 R0a "room for everything in Studio" (the owner, 2026-11-12: "the panel is
cramped. We need to fix that for all of studio parts"): "cramped" as a test that fails. Unit pins over the source, then
headless Chrome through tests/helpers/studio_room.py (skipped without one) over the Session rig and the long-names seed,
every view at 1280 x 800, 1500 x 900 and 1920 x 1000, each drawer opened from the view bar in turn:

R1  the main thing keeps >= 60 % of the stage's width and height (Session, Agents, Packs), with any drawer open
R2  an open drawer is as wide as its content (contentW, or the drawers' room when that is less), 360-560 px
R3  no strip anywhere; the stage row is the window less the header, the view's bars and the status line
R4  no sideways scrollbar inside a panel or a page (the canvases, maps and code blocks pan by design)
R5  every text cut sideways has its whole text on hover (a title, a hover card or a label); 3.6.0.0: a name is never cut
    in a box at least 24 characters wide
R6  no text under 12 px
R7  controls >= 28 px tall, no two drawn on each other (3.6.0.0: Session too), 8 px between neighbours where it holds
R8  a drawer sits beside the main thing, never over it (at 1100 and up); 3.6.0.0: a drawing fits its new box when a
    drawer opens (or, past the 12 px floor, keeps its lead node whole in view), a zoom by hand survives it
R9  under 1440 one drawer at a time, wider one per side while the main thing keeps 60 % (2560: both; 1920: the
    older closes; 3.6.0.0: 2560 for both, the Map drawer is 560 px), under 1100 it floats, under 760 the rail is a menu
R10 a drawer opened is kept across a reload without a "custom layout"; an old grid layout is dropped and a newer
    layout version announced, each once
R4b the line between Session's Map and Live drags until the Map is bigger; Map only / Live only / both (studio_room_split)
Run: python -m tests.test_studio_room
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
WS = REPO / "halo_harness" / "studio" / "ui" / "src" / "lib" / "workspace"
UI = WS.parent.parent
_RUN: dict = {}
STAGED = ("session", "agents", "crew", "flows", "map", "packs")  # 3.6.0.0 R1: crew = Agents -> 1 · Agents; R2: flows = 2 · Workflows; R3: map


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_room", why="the room rules are measured in headless Chrome",
                      cache=_RUN, timeout=900, tail=800, what="the room driver")


def _room(got: dict) -> dict:
    return got.get("room") or {}


def _room_px(stage_w: int, n: int = 1) -> int:
    return max(360, int(stage_w * 0.4) - 24 - 12 * n)  # lib/workspace/rules.ts drawerRoom


@test
def test_the_stage_in_the_source(ctx: Ctx):
    ctx.check("the grid is gone: no grid.ts, quiet.ts or room.ts", not any((WS / f).exists() for f in ("grid.ts", "quiet.ts", "room.ts")))
    for f in ("Stage.tsx", "ViewBar.tsx", "breakpoint.ts", "rules.ts"):
        ctx.check(f"lib/workspace/{f} is there", (WS / f).is_file())
    types = (WS / "types.ts").read_text(encoding="utf-8")
    ctx.check("a panel declares role / side / contentW", all(k in types for k in ('role?: Role', 'side?: Side', 'contentW?: number')))
    ctx.check("persist keeps v3 with a layout version", "const VERSION = 3;" in (WS / "persist.ts").read_text(encoding="utf-8"))
    css = (UI / "styles" / "workspace.css").read_text(encoding="utf-8")
    ctx.check("no grid, no strip, no resize handles in the sheet", ".ws-grid" not in css and ".rz-" not in css and "data-dragging" not in css)
    for rel in ("routes/session/Session.tsx", "routes/crew/map/MapView.tsx", "routes/packs/manager/Manager.tsx"):  # R5: Roles went
        src = (UI / rel).read_text(encoding="utf-8")
        ctx.check(f"{rel}: no grid cells in a core spec", not re.search(r"\bx: \d+, y: \d+, w: \d+, h: -?\d+", src))
    ctx.check("the header's + menu went", not (UI / "shell" / "PanelsMenu.tsx").exists())


@test
def test_r7_the_goal_forms_run_row_is_the_drawers_foot(ctx: Ctx):
    # 3.6.0.3 B: the Map's drawer opens on Run a goal; its Run row was sticky over the scrolling form and sat 4 px under the
    # model picker at 1280 x 800 (R7: 8 px between neighbours). The fields scroll in their own box, the Run row under it.
    for rel in ("routes/orchestra/GoalForm.tsx", "routes/orchestra/WorkflowForm.tsx"):
        src = (UI / rel).read_text(encoding="utf-8")
        fields, actions = src.find('className="og-fields"'), src.find('className="og-actions fl-actions"')
        ctx.check(f"{rel}: the fields are in one box (og-fields) and the Run row comes after it", -1 < fields < actions)
        ctx.check(f"{rel}: the Run row is outside the fields' box", src.rfind("</div>", fields, actions) > fields)
    css = (UI / "styles" / "run.css").read_text(encoding="utf-8")
    rule = lambda sel: (re.search(re.escape(sel) + r"\s*\{([^}]*)\}", css) or [None, ""])[1]  # noqa: E731
    ctx.check("run.css: the drawer's body does not scroll (its form's fields do)", "overflow: hidden" in rule(".rg-body"))
    ctx.check("run.css: the fields' box scrolls", "overflow-y: auto" in rule(".rg-body .og-fields"))
    ctx.check("run.css: the Run row is not sticky in the drawer", "position: static" in rule(".rg-body .fl-actions"))


@test
def test_r1_r2_r8_the_main_thing_and_its_drawers(ctx: Ctx):
    room = _room(_got(ctx))
    ctx.check(f"every view measured at three sizes ({len(room)} records)", len(room) >= 21)
    ctx.check("3.6.0.0 R1: the Agents tab at 1280, 1500 and 1920", all(f"crew@{s}" in room for s in ("1280x800", "1500x900", "1920x1000")))
    ctx.check("3.6.0.0 R2: the Workflows tab at 1280, 1500 and 1920", all(f"flows@{s}" in room for s in ("1280x800", "1500x900", "1920x1000")))
    ctx.check("3.6.0.0 R3: the Map tab at 1280, 1500 and 1920", all(f"map@{s}" in room for s in ("1280x800", "1500x900", "1920x1000")))
    for key, m in room.items():
        if not m or key.split("@")[0] not in STAGED or not m.get("main"):
            continue
        st, main = m["stage"], m["main"]
        ctx.check(f"R1 {key}: the main thing's share >= 60 %, got {main[2]}/{st[2]} x {main[3]}/{st[3]}",
                  main[2] >= 0.6 * st[2] - 1 and main[3] >= 0.6 * st[3])
        for pid, side, w, floating in m.get("drawers") or []:
            cw = next((r["cw"] for r in m["regions"] if r["id"] == pid), 0)
            ctx.check(f"R2 {key}: {pid} is {w} px, its content {cw} px, the room {_room_px(st[2])} px",
                      360 <= w <= 560 and w >= min(cw, _room_px(st[2])) - 1 and not floating)
            reg = next((r["rect"] for r in m["regions"] if r["id"] == pid), None)
            beside = reg and (reg[0] >= main[0] + main[2] or reg[0] + reg[2] <= main[0])
            ctx.check(f"R8 {key}: {pid} beside the main thing, never over it, got {reg} / {main}", bool(beside))


@test
def test_r3_no_strips_and_the_stage_height(ctx: Ctx):
    for key, m in _room(_got(ctx)).items():
        if not m:
            continue
        ctx.check(f"R3 {key}: no strip, got {m.get('strips')}", m.get("strips") == 0)
        if m.get("main"):
            want = m["vh"] - m["header"] - m["status"] - m["bar"]
            ctx.check(f"R3 {key}: the stage row is the window less the header, the bars and the status line, got {m['stage'][3]} want {want}",
                      abs(m["stage"][3] - want) <= 2)
        ctx.check(f"{key}: the page never scrolls sideways", m.get("doc_hscroll") is False)


@test
def test_r4_r5_r6_text_and_scrollbars(ctx: Ctx):
    for key, m in _room(_got(ctx)).items():
        for r in (m or {}).get("regions") or []:
            where = f"{key} {r['id']}"
            ctx.check(f"R4 {where}: no sideways scrollbar, got {r['hscroll']}", not r["hscroll"])
            ctx.check(f"R5 {where}: every cut text has its whole text on hover, got {r['bare']}", not r["bare"])
            ctx.check(f"R5 {where}: no name cut in a box 24 characters wide or more, got {r.get('names')}", r.get("names") == [])
            ctx.check(f"R6 {where}: nothing under 12 px, got {r['small']} {r['small_ex']}", r["small"] == 0)


#: 3.6.0.0 R0a-finish: the views where "8 px between neighbours" holds everywhere measured (a segmented control's
#: parts are one control); the others are listed with their pairs in the round's hand-back
SPACED = ("session", "crew", "flows", "map", "packs", "local", "setup", "settings")  # 3.6.0.0 R1: the Agents tab from the start; R2: Workflows; R3: Map


@test
def test_r7_controls(ctx: Ctx):
    room = _room(_got(ctx))
    for key, m in room.items():
        for r in (m or {}).get("regions") or []:
            where = f"{key} {r['id']}"
            if key.startswith(("session", "packs", "agents", "crew", "flows", "map", "local")) and r["id"] not in ("roles-bios",):
                ctx.check(f"R7 {where}: no control under 28 px, got {r['low']} {r['low_ex']}", r["low"] == 0)
            ctx.check(f"R7 {where}: no two controls drawn on each other, got {r['overlap']} {r['over']}", r["overlap"] == 0)
            if key.startswith(SPACED):
                ctx.check(f"R7 {where}: 8 px between neighbours, got {r['close']} {r.get('near')}", r["close"] == 0)


def _fits(d: dict) -> bool:
    """3.6.0.0 R8: no node cut, or (past the 12 px floor) it says 'more' with the lead node whole. 3.6.0.2 R11: Session's
    Live drawer (`session-map`) never cuts a box at rest, with no 'more' exemption: a box wholly below it waits there, and
    then (batch 7: checked in full again) the lead, main, is whole and the slot says '↓ {n} more below' with n the boxes
    wholly below; a drawing that fits says nothing."""
    if d.get("id") == "session-map":
        n = d.get("below")
        said = d.get("below_text") == (f"↓ {n} more below" if n else "")
        return d.get("crossed") == 0 and bool(d.get("main")) and isinstance(n, int) and said
    return d["cut"] == 0 or (d["more"] and d["lead"])


@test
def test_r11_session_drawing_room_rule_in_full(ctx: Ctx):
    """batch 7: the room rule for Session's Live drawer (`_fits`, read by R8 and R4b below) fails a drawing whose boxes
    wait below unannounced, with a wrong count, with words when nothing is below, with main cut, or with a box cut;
    no browser: the measured dicts are fed to it."""
    ok = {"id": "session-map", "nodes": 8, "crossed": 0, "main": True, "below": 1, "below_text": "↓ 1 more below"}
    bad = {"unannounced": {"below_text": ""}, "wrong n": {"below": 2}, "words, none below": {"below": 0},
           "main cut": {"main": False}, "a box cut": {"crossed": 1}, "not measured": {"below": None}}
    ctx.check("R11: one box below, said with its number, fits", _fits(ok))
    ctx.check("R11: a drawing that fits says nothing", _fits({**ok, "below": 0, "below_text": ""}))
    wrong = [k for k, v in bad.items() if _fits({**ok, **v})]
    ctx.check(f"R11: each of these fails the rule, passed instead: {wrong}", not wrong)


@test
def test_r8_a_drawing_fits_its_box(ctx: Ctx):
    """3.6.0.0 R8: after a drawer opens (or closes) each drawing on Session and Agents fits its new box -- no node box
    cut by it -- or, past the 12 px floor (the Map in its drawer), says so and keeps the lead node whole in view; a zoom
    by hand survives a drawer opening, and Fit makes the drawing automatic again."""
    seen = 0
    for key, m in _room(_got(ctx)).items():
        if not key.startswith(("session", "agents", "flows", "map")):  # 3.6.0.0 R2: the steps drawn beside the workflow form; R3: the map
            continue
        for d in (m or {}).get("drawings") or []:
            seen += 1
            ctx.check(f"R8 {key} {d['id']}: every node whole in the drawing's box, or (12 px floor) the lead one, got {d}",
                      d["nodes"] > 0 and _fits(d))
    ctx.check(f"R8: the drawings measured (Cast with each Agents drawer, the Map drawer), got {seen}", seen >= 12)
    h = _got(ctx).get("hand") or {}
    ctx.check(f"R8 a zoom by hand survives a drawer opening, got {h}", h.get("hand") and h.get("after_drawer") == h.get("hand") != h.get("auto"))
    ctx.check(f"R8 Fit makes it automatic again: the drawer closing fits it anew, got {h}",
              h.get("fit") != h.get("hand") and h.get("fit_after_close") != h.get("fit"))


@test
def test_r9_breakpoints(ctx: Ctx):
    bp = _got(ctx).get("bp") or {}
    mid, hd, wide, narrow = (bp.get(k) or {} for k in ("mid", "full_hd", "wide", "narrow"))
    ctx.check(f"R9 1280: one drawer at a time (Map closed when Cost opened), got {mid.get('open')}", mid.get("open") == [["session-cost", False]])
    ctx.check(f"R9 1920: two 360 px drawers would leave the main thing under 60 %: the older closes, got {hd.get('open')}",
              hd.get("open") == [["session-cost", False]])
    ctx.check(f"R9 2560: a left and a right drawer together, got {wide.get('open')}",
              sorted(wide.get("open") or []) == [["session-cost", False], ["session-map", False]])
    room = wide.get("room") or {}
    if room.get("main"):
        ctx.check(f"R9 2560: the main thing keeps 60 % beside both, got {room['main'][2]}/{room['stage'][2]}", room["main"][2] >= 0.6 * room["stage"][2] - 1)
    ctx.check(f"R9 1024: the drawer floats over the main thing, got {narrow.get('open')}", narrow.get("open") == [["session-cost", True]])
    ctx.check(f"R9 390: the rail hidden, its menu button shown, no sideways scroll, got {bp.get('phone')} {bp.get('phone_wide')}", (bp.get("phone") or [""])[0] == "none" and (bp.get("phone") or ["", "none"])[1] != "none" and (bp.get("phone") or [0, 0, False])[2] is True)
    ctx.check(f"R9 390: the menu button opens the rail, got {bp.get('phone_menu')!r}", bp.get("phone_menu") == "flex")


@test
def test_r10_what_is_kept(ctx: Ctx):
    k = _got(ctx).get("kept") or {}
    saved = k.get("saved") or {}
    ctx.check(f"R10 the drawer opened is saved as v3, got {saved}", saved.get("v") == 3 and saved.get("open") == ["session-cost"] and saved.get("lv") == 1)
    ctx.check(f"R10 kept across a reload, no custom layout anywhere, got {k.get('after_reload')}", k.get("after_reload") == [["session-cost"], False, False])
    ctx.check(f"R10 an old grid layout is dropped with the note, got {k.get('dropped')}", k.get("dropped") == ["dropped", None])
    ctx.check(f"R10 the note once, got {k.get('dropped_again')}", k.get("dropped_again") is False)
    ctx.check(f"R10 an older layout version: kept (Cost open, its own width) and said once, got {k.get('changed')}",
              k.get("changed") == ["changed", ["session-cost"], 420])
    ctx.check(f"R10 Use the new one: the default, and no note again, got {k.get('changed_again')}", k.get("changed_again") == [False, False])


@test
def test_r4b_the_line_in_the_middle_moves(ctx: Ctx):
    """3.6.0.0 R4b, the owner's report (2026-11-14): Session's line between the Map and Live drags with real pointer
    events (CDP) at 1280 / 1500 / 1920 until the Map is the bigger view, stays under the pointer both ways, is kept
    across a reload, answers Alt+Right / Alt+Left; the drawing re-fits only when the drag ends (never under a hand zoom);
    the floating drawer under 1100 px drags too."""
    sp = _got(ctx).get("split") or {}
    for size in ("1280x800", "1500x900", "1920x1000"):
        s = sp.get(size) or {}
        d = s.get("drag") or {}
        ctx.check(f"{size}: the line under the pointer at every move, off by {d.get('off')}", len(d.get("off") or []) == 8 and all(abs(o) < 2 for o in d["off"]))
        ctx.check(f"{size}: the Map ends wider than Live, got {s.get('wider')} (from {s.get('start')}, max {s.get('max')})",
                  len(s.get("wider") or []) == 2 and s["wider"][0] > s["wider"][1] >= 360 and s["wider"][0] > 560)
        ctx.check(f"{size}: the width is kept, and after a reload still that width, got {s.get('saved')} / {s.get('reloaded')}",
                  s.get("saved") == (s.get("wider") or [0])[0] and s.get("reloaded") == s.get("wider"))
        ctx.check(f"{size}: dragged back, under the pointer, got {s.get('back')}", len(s.get("back") or []) == 4 and all(abs(o) < 2 for o in s["back"]))
        k = s.get("keys") or [0, 0, 0]
        ctx.check(f"{size}: Alt+Right widens by 40, Alt+Left narrows back, got {k}", k[1] == k[0] + 40 and k[2] == k[0])
        b, during, after, fit = d.get("before") or [], d.get("during") or [], d.get("after") or [], s.get("fit") or []
        ctx.check(f"{size}: no re-fit while the line moves, got {b} then {during}", bool(b) and all(x == b for x in during))
        ctx.check(f"{size}: one re-fit when the drag ends, to what Fit makes of the box, got {after} / Fit {fit}",
                  len(after) == 2 and after[1] == b[1] + 1 and after[0] == fit[0])
        h = s.get("hand") or {}
        z = h.get("zoom") or []
        ctx.check(f"{size}: a zoom by hand stays through the drag and after it, got {h}",
                  bool(z) and all(x == z for x in h.get("during") or [None]) and (h.get("after") or [None])[0] == z[0] and (h.get("after") or [0, -1])[1] == z[1])
    f = sp.get("float") or {}
    ctx.check(f"1024: the floating drawer's line drags too, got {f}", f.get("floating") and f.get("to", 0) >= f.get("from", 0) + 150 and all(abs(o) < 2 for o in f.get("off") or [9]))


@test
def test_r4b_either_view_alone(ctx: Ctx):
    """R4b: Only this / Show both on the Live drawer (the drawing) and on the Feed (3.6.0.2 R35's words), kept per section;
    the Feed stays mounted under Live only; the Live button brings both back; each arrangement keeps the room rules (no
    sideways scrollbar, nothing under 12 px, controls >= 28 px and 8 px apart, the drawing fits or pans from main).
    The arrangements keep their ids (map-only = Live only, live-only = Feed only)."""
    sp = _got(ctx).get("split") or {}
    for size in ("1280x800", "1500x900", "1920x1000"):
        s = sp.get(size) or {}
        ctx.check(f"{size}: Live only keeps the Feed mounted, hidden, the Live drawing with the whole stage, got {s.get('mounted')}",
                  (s.get("mounted") or [False])[0] is True and (s.get("mounted") or [0, 0])[1] > 1100)
        ctx.check(f"{size}: Live only is kept across a reload (the bar says 'Live only'), got {s.get('map_only_kept')}",
                  s.get("map_only_kept") == ["Live only", True])
        ctx.check(f"{size}: Feed only: no Live drawer, the Live button not pressed, got {s.get('live_only')}", s.get("live_only") == [False, "false"])
        ctx.check(f"{size}: Feed only kept, then the Live button shows both ('Live and Feed'), got {s.get('both_again')}",
                  s.get("both_again") == "Live and Feed")
        arr = s.get("arr") or {}
        # 3.6.0.2 R35: the drawer is titled Live and the main panel Feed, so the bar says Live and Feed / Live only / Feed only
        want = {"map-and-live": "Live and Feed", "map-only": "Live only", "live-only": "Feed only"}
        for name, words in want.items():
            m = arr.get(f"session@{size}={name}") or {}
            ctx.check(f"{size} {name}: measured, the view bar says {words!r}, got {m.get('words')!r}", m.get("words") == words and m.get("regions"))
            ctx.check(f"{size} {name}: the page never scrolls sideways", m.get("doc_hscroll") is False)
            for r in m.get("regions") or []:
                where = f"{size} {name} {r['id']}"
                ctx.check(f"{where}: no sideways scrollbar {r['hscroll']}, nothing under 12 px {r['small']}, controls >= 28 px {r['low_ex']}, "
                          f"none on another {r['over']}, 8 px apart {r.get('near')}",
                          not r["hscroll"] and r["small"] == 0 and r["low"] == 0 and r["overlap"] == 0 and r["close"] == 0)
            for d in m.get("drawings") or []:
                ctx.check(f"{size} {name} {d.get('id')}: the drawing fits or pans from main, got {d}", d["nodes"] > 0 and _fits(d))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
