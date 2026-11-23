"""tests.test_studio_sheet_acts -- Halo 3.6.0.15 OP2 rule O2-7: the box acts, as a person sees it, in headless Chrome
(tests/helpers/studio_sheet_acts_steps.py; on the Linux VM, never on the owner's PC). No model is called. The sheet that
opens at a helper's box has a MODEL block (O2-5) that reads GET crew/agent-model (O2-2) and writes through POST
crew/agent-model and its Undo (O2-3); every word is compared with the product's own constants (studio/crew_model_api.py,
studio/crew_live_api.py), every figure read from the page.

1. test_each_kind_reads_its_line (O2-2, O2-5): MAIN, MINE, SHIPPED, ROUTED, BUILT-IN, MADE-UP, PACK, CLAUDE, each from its
   member's sheet (main from main's): the line letter for letter in the now form (`use_now` true, reduced motion) and the
   later form (false, no preference); ROUTED's first line; PACK and CLAUDE with no picker; Edit for MINE, Make for the
   made kinds.
2. test_a_groups_sheet_has_the_chosen_rows_model_row (O2-9, rewritten from ruling F's "no block"): the chosen row's
   closed row "MODEL of {name}", no MODEL request.
3. test_a_pick_saves_and_undo_puts_back (O2-3, MINE): the picker folds open IN the body, a pick reads "Saved: ...", the
   file holds the pick; Undo reads "Put back: ...", the file byte-equal to before.
4. test_a_pick_makes_and_undo_takes_back (O2-3, BUILT-IN Judge): "Made judge, ..."; Undo: "Taken back: judge is gone.",
   the file gone.
5. test_edit_and_make_open_the_form (O2-5, O2-6): Edit in Agents opens his agent in the Agents form; Make it an agent fills
   it ("Built from {helper} on {model}, ..."), nothing written; from Agents -> Live and from Session's drawer.
6. test_mains_door (O2-3, ruling R7): a terminal, none, a refused ref ("Not switched: {first line}."), a busy session
   (refused before the door: nothing sent through it).
7. test_the_model_block_is_closed_until_asked (O2-8, rewritten from O2-5's late read): a member's sheet opens with ONE
   row, "MODEL" and [Change], and no request for the block; Change opens it under the row (the read held: "Reading this
   helper's agent..."), ONE request; Close folds it, nothing above it moved; Change again asks nothing; a pick's line and
   Undo are kept over a Close. Every leg above presses Change before it reads the block.
8. test_the_picker_never_folds_the_sheet (O2-5): a click in the folded picker and Escape in its search box leave the sheet
   open; Escape after the picker closed folds it.
9. test_a_folded_groups_helper_can_still_be_given_a_model (O2-9): a folded group's card; the chosen row's block, read
   once per helper, closed when another row is chosen; a pick gives its helper a model.
Run: python -m tests.test_studio_sheet_acts
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from halo_harness.studio import crew_model_api as K  # noqa: E402
from halo_harness.studio.crew_live_api import BUILT  # noqa: E402
from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUNS: dict = {}
RUN = "or:vendor/fast"  # the scene's model (tests/helpers/studio_sheet_acts_steps.py RUN)
MADE_UP = "count-lines-basket"  # crew_live_api.name_for("Count the lines in basket.py")


def _ran(ctx: Ctx, key: str) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the sheet needs headless Chrome)")
    if not _RUNS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_sheet_acts_steps"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=900, env=driver_env(REPO), cwd=str(REPO))
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {}
        _RUNS.update(r=r, got=got)
    if _RUNS["got"].get("skip"):
        raise SkipTest(_RUNS["got"]["skip"])
    r, got = _RUNS["r"], _RUNS["got"]
    step = got.get(key) or {}
    ctx.check(f"the driver ran {key}, got {r.returncode} {got.get('failed')!r} {step.get('error')!r} {r.stderr[-600:]!r}",
              bool(step) and not step.get("error"))
    return step


def want(aid: str, now: bool, maps: "dict | None" = None) -> dict:
    """What the block of helper `aid` reads, from the product's constants; `maps`: the rig's maps that name each name (the
    line then adds "Your map {M} names {name}: ..." for the first)."""
    keeps = K.KEEPS.format(model=RUN)
    made = {"edit": None, "make": "Make it an agent", "select": True, "first": None}
    lines = {
        "main": ("MAIN", [K.MAIN_LINE], {"edit": None, "make": None, "select": True, "first": None}),
        "a1": ("MINE", [K.LINES[(K.MINE, now)].format(name="sorter"), keeps], {**made, "edit": "Edit in Agents", "make": None}),
        "a2": ("SHIPPED", [K.LINES[(K.SHIPPED, now)].format(name="planner"), keeps], made),
        "a3": ("ROUTED", [K.LINES[(K.ROUTED, now)].format(name="media-reader", card="media"), keeps],
               {**made, "first": K.FIRST_ROUTED.format(card="media", word="transcribe")}),
        "a4": ("BUILT-IN", [K.LINES[(K.BUILTIN, now)].format(name="judge", X="Judge"), keeps], made),
        "a5": ("MADE-UP", [K.LINES[(K.MADE_UP, now)].format(name=MADE_UP), keeps], made),
        "a6": ("PACK", [K.PACK_LINE.format(name="doc-review--review-docs", P="doc-review")],
               {"edit": None, "make": None, "select": False, "first": None}),
        "a7": ("CLAUDE", [K.CLAUDE_LINE.format(name="helper-x")], {"edit": None, "make": None, "select": False, "first": None}),
    }
    kind, rows, more = lines[aid]
    names = {"a1": "sorter", "a2": "planner", "a3": "media-reader", "a4": "judge", "a5": MADE_UP}
    on = (maps or {}).get(names.get(aid, "")) or []
    if on:
        rows = [rows[0] + (K.MAP_MINE if kind == "MINE" else K.MAP_MADE).format(M=on[0], name=names[aid]), *rows[1:]]
    return {"kind": kind, "rows": rows, "head": "MODEL", **more}


@test
def test_each_kind_reads_its_line(ctx: Ctx):
    d = _ran(ctx, "kinds")
    for form, now in (("now", True), ("later", False)):
        got = d.get(form) or {}
        for aid in ("main", "a1", "a2", "a3", "a4", "a5", "a6", "a7"):
            w, g = want(aid, now, d.get("maps")), got.get(aid) or {}
            seen = {k: g.get(k) for k in w}
            ctx.check(f"{form} {w['kind']}: the block reads letter for letter, got {seen} want {w}", seen == w)


@test
def test_a_groups_sheet_has_the_chosen_rows_model_row(ctx: Ctx):
    """Rewritten to O2-9 (it was ruling F's test_a_groups_sheet_draws_no_model_block): a group's card has the CHOSEN
    row's MODEL row, "MODEL of {name}" and Change, closed, and no MODEL request."""
    g = _ran(ctx, "kinds").get("group") or {}
    r, who = g.get("row") or {}, g.get("who") or []
    chosen = next((w for w in who if w[2]), None)
    ctx.check(f"a group's sheet open, its first row chosen, got {g.get('target')} {who}",
              g.get("target") == "group:1" and len(who) == 7 and chosen == who[0])
    ctx.check(f"its MODEL row: 'MODEL of {{the chosen row's name}}', Change, closed, first in the body, got {r}",
              bool(chosen) and r.get("head") == f"MODEL of {chosen[1]}" and r.get("word") == "Change" and r.get("expanded") == "false"
              and r.get("first") is True and r.get("content") is False)
    ctx.check(f"no MODEL request, got {g.get('gets')}", g.get("gets") == 0)


@test
def test_a_pick_saves_and_undo_puts_back(ctx: Ctx):
    m = _ran(ctx, "picks").get("mine") or {}
    u, ref = m.get("unfolded") or {}, m.get("ref") or ""
    ctx.check(f"the picker folded open IN the sheet's body, no dialog, got {u}", u.get("fold") is True and u.get("inBody") is True and u.get("dialog") is False)
    ctx.check(f"the session took sorter exactly when it can take (UN's push), got took {m.get('took')} can {m.get('can')}",
              isinstance(m.get("took"), bool) and m.get("took") == m.get("can"))
    saved = (K.SAVED_NOW if m.get("took") else K.SAVED_LATER).format(name="sorter", model=ref)
    p = m.get("picked") or {}
    ctx.check(f"a pick of {ref!r}: {saved!r}, Undo offered, the sheet still open, got {p.get('rows')} {p.get('undo')!r} {m.get('sheet_open')}",
              bool(ref) and p.get("rows") == [saved] and p.get("undo") == "Undo" and m.get("sheet_open") is True)
    ctx.check(f"his file holds the pick, got {m.get('file_model')!r}", bool(ref) and m.get("file_model") == ref)
    un = m.get("undone") or {}
    ctx.check(f"Undo: {K.PUT_BACK.format(name='sorter', old='auto')!r}, Undo gone, got {un.get('rows')} {un.get('undo')!r}",
              un.get("rows") == [K.PUT_BACK.format(name="sorter", old="auto")] and un.get("undo") is None)
    ctx.check(f"his file byte-equal to before, got {m.get('bytes_back')}", m.get("bytes_back") is True)


@test
def test_a_pick_makes_and_undo_takes_back(ctx: Ctx):
    m = _ran(ctx, "picks").get("made") or {}
    ref = m.get("ref") or ""
    made = (K.MADE_NOW if m.get("took") else K.MADE_LATER).format(name="judge", model=ref)
    p = m.get("picked") or {}
    ctx.check(f"the session took judge exactly when it can take, got took {m.get('took')} can {m.get('can')}",
              isinstance(m.get("took"), bool) and m.get("took") == m.get("can"))
    ctx.check(f"a pick of {ref!r} on Judge: {made!r}, Undo offered, got {p.get('rows')} {p.get('undo')!r}",
              bool(ref) and p.get("rows") == [made] and p.get("undo") == "Undo")
    ctx.check(f"judge's file made on the pick, got {m.get('before')} -> {m.get('after_pick')} model {m.get('file_model')!r}",
              "judge.yaml" not in (m.get("before") or []) and "judge.yaml" in (m.get("after_pick") or []) and m.get("file_model") == ref)
    un = m.get("undone") or {}
    ctx.check(f"Undo: {K.TAKEN_BACK.format(name='judge')!r}, the file gone, got {un.get('rows')} {m.get('after_undo')}",
              un.get("rows") == [K.TAKEN_BACK.format(name="judge")] and m.get("after_undo") == m.get("before"))


@test
def test_edit_and_make_open_the_form(ctx: Ctx):
    d = _ran(ctx, "forms")
    note = BUILT.format(helper="general-purpose", model=RUN)
    for view in ("live", "session"):
        e, m = d.get(f"{view}_edit") or {}, d.get(f"{view}_make") or {}
        ef, mf = e.get("form") or {}, m.get("form") or {}
        ctx.check(f"{view}: Edit in Agents carried him to the Agents form on sorter, got {ef}",
                  ef.get("name") == "sorter" and ef.get("shown") is True and ef.get("view") == "crew")
        ctx.check(f"{view}: Make it an agent filled the form, got {mf}",
                  mf.get("name") == MADE_UP and mf.get("shown") is True and mf.get("view") == "crew" and mf.get("note") == note)
        ctx.check(f"{view}: nothing written by Edit or Make, got {e.get('before')} {e.get('after')} {m.get('before')} {m.get('after')}",
                  e.get("before") == e.get("after") and m.get("before") == m.get("after") and bool(m.get("before")))


@test
def test_mains_door(ctx: Ctx):
    d = _ran(ctx, "door")
    t, n, r, b = (d.get(k) or {} for k in ("terminal", "none", "refused", "busy"))
    for rec in (t, n, r, b):
        o = rec.get("open") or {}
        ctx.check(f"main's block: {K.MAIN_LINE!r}, its picker, got {o.get('kind')} {o.get('rows')} {o.get('select')}",
                  o.get("kind") == "MAIN" and o.get("rows") == [K.MAIN_LINE] and o.get("select") is True)
    rows = lambda rec: (rec.get("picked") or {}).get("rows")  # noqa: E731
    ctx.check(f"a terminal: {K.SWITCHED_TERMINAL!r}, got {rows(t)} {t.get('calls')}",
              rows(t) == [K.SWITCHED_TERMINAL.format(model=t.get("ref"))] and (t.get("calls") or [])[:2] == ["status", "slash"]
              and "model" not in (t.get("calls") or []))
    ctx.check(f"no terminal: {K.SWITCHED_SESSION!r}, got {rows(n)} {n.get('calls')}",
              rows(n) == [K.SWITCHED_SESSION.format(model=n.get("ref"))] and (n.get("calls") or [])[:3] == ["status", "slash", "model"])
    first = f"No model named {r.get('ref')} on this harness"
    ctx.check(f"a refused ref (R7): Not switched with the door's first line, got {rows(r)}",
              rows(r) == [K.NOT_SWITCHED.format(why=first)] and (r.get("picked") or {}).get("undo") is None)
    ctx.check(f"a busy session: {K.IN_A_TURN!r}, nothing sent through the door, got {rows(b)} {b.get('calls')}",
              rows(b) == [K.IN_A_TURN] and b.get("calls") == ["status"])


def _near(a, b) -> bool:
    return bool(a) and bool(b) and len(a) == len(b) and all(abs(x - y) <= 0.5 for x, y in zip(a, b))


@test
def test_the_model_block_is_closed_until_asked(ctx: Ctx):
    """O2-8 (the owner's rule: a section he uses rarely is closed by default, opened by its button, and has a close
    button). The sizes are read from the page at the rig's own size: no constant."""
    d = _ran(ctx, "closed")
    o = d.get("at_open") or {}
    ctx.check(f"the sheet opens with ONE row first in its body: MODEL and Change, aria-expanded false, got {o}",
              o.get("first") is True and o.get("head") == "MODEL" and o.get("word") == "Change" and o.get("expanded") == "false"
              and o.get("btns") == 1 and o.get("controls") is True)
    ctx.check(f"closed: no picker, no line, no model button, no content in the page, got {o}",
              o.get("content") is False and o.get("picker") is False and o.get("line") is False and o.get("buttons") is False)
    ctx.check(f"closed: NO request for the block, at open and a frame later, got {o.get('gets')} {d.get('frame_later')}",
              o.get("gets") == [0, 0] and d.get("frame_later") == [0, 0])
    # closed, the block costs the sheet ONE row (a button's height), not the drawing's whole height (OP2's open block
    # made it 482 of a 498-px drawing): the sheet holds its words unclamped, its body does not scroll. Whether another
    # member stays reachable beside it is test_studio_sheet's pick leg (its own scene); this scene's figures are recorded.
    z = d.get("sizes") or {}
    ctx.check(f"closed: the row is one button's height, the sheet holds its words (not clamped, the body not scrolled), got {z}",
              bool(z.get("row")) and abs((z.get("row") or 0) - (z.get("tog") or -9)) <= 0.5 and bool(z.get("sheet"))
              and z["sheet"] < (z.get("view") or 0) - 16 and (z.get("body") or [0, 1])[0] == (z.get("body") or [0, 1])[1])
    r = d.get("reading") or {}
    ctx.check(f"Change: open under the row, Close, aria-expanded true, the content it controls, got {r}",
              r.get("word") == "Close" and r.get("expanded") == "true" and r.get("controlled") is True and r.get("first") is True)
    ctx.check(f"while the read is held: ONE row \"Reading this helper's agent...\", no picker, no button, ONE request, got {r}",
              (r.get("block") or {}).get("rows") == ["Reading this helper's agent..."] and r.get("picker") is False
              and r.get("buttons") is False and (r.get("gets") or [0])[0] == 1 and d.get("released") == 1)
    op = d.get("opened") or {}
    blk = op.get("block") or {}
    ctx.check(f"answered: MINE's block, its picker, exactly ONE request, got {blk.get('kind')} {blk.get('select')} {op.get('gets')}",
              blk.get("kind") == "MINE" and blk.get("select") is True and blk.get("head") == "MODEL" and (op.get("gets") or [0])[0] == 1)
    f = d.get("folded") or {}
    ctx.check(f"Close: the content left the page, the row reads Change again, got {f}",
              f.get("content") is False and f.get("picker") is False and f.get("word") == "Change" and f.get("expanded") == "false")
    for k in ("rect", "headRect", "actions"):
        seen = [(x or {}).get(k) for x in (o, r, op, f)]
        ctx.check(f"{k}: the row and what is above it never moved (closed, reading, open, folded), got {seen}",
                  all(_near(seen[0], s) for s in seen[1:]))
    g = d.get("again") or {}
    ctx.check(f"Change again: the same block at once, no second request, got {(g.get('block') or {}).get('rows')} {g.get('gets')}",
              (g.get("block") or {}).get("rows") == blk.get("rows") and (g.get("gets") or [0])[0] == 1)
    p, k = d.get("picked") or {}, d.get("kept") or {}
    ctx.check(f"a pick's line and Undo kept over Close and Change, nothing asked, got {p.get('rows')} -> {(k.get('block') or {}).get('rows')}",
              bool(d.get("ref")) and p.get("undo") == "Undo" and (k.get("block") or {}).get("rows") == p.get("rows")
              and (k.get("block") or {}).get("undo") == "Undo" and (k.get("gets") or [0])[0] == 1 and k.get("open") is True)


@test
def test_the_picker_never_folds_the_sheet(ctx: Ctx):
    d = _ran(ctx, "picker")
    c, e = d.get("click") or {}, d.get("escape_in_search") or {}
    ctx.check(f"a click in the folded picker: the sheet open, the picker open, its search focused, got {c}",
              c.get("open") is True and c.get("fold") is True and c.get("focus") is True)
    ctx.check(f"Escape in its search box closed the picker, not the sheet, got {e}", e.get("open") is True and e.get("fold") is False)
    ctx.check(f"Escape after the picker closed folded the sheet, got {d.get('escape_after')}", (d.get("escape_after") or {}).get("gone") is True)


@test
def test_a_folded_groups_helper_can_still_be_given_a_model(ctx: Ctx):
    """O2-9 (the coordinator's ruling): a group of two finished helpers folds to its head (L8: their boxes hidden); its
    card is the door to them. The MODEL row is the CHOSEN row's, "MODEL of {name}"; Change reads THAT helper, once;
    choosing another row closes it and asks nothing; what each helper's block read, a pick's line and Undo are kept per
    helper while the card lives."""
    d = _ran(ctx, "grouprow")
    maps = d.get("maps")

    def line(aid: str) -> list:  # a finished helper: its kind's line, then "It ran on {model}."
        return [want(aid, True, maps)["rows"][0], K.RAN.format(model=RUN)]
    ctx.check(f"the group folded, its members' boxes hidden, got {d.get('folded')}", d.get("folded") == [True, 0])
    o = d.get("opened") or {}
    r, who = o.get("row") or {}, o.get("who") or []
    ctx.check(f"its head opened the group's card: a row per finished helper, the first chosen, got {o.get('target')} {who}",
              o.get("target") == "group:1" and [w[0] for w in who] == ["a1", "a4"] and [w[2] for w in who] == [True, False])
    ctx.check(f"the body's first row: 'MODEL of {{the first row's name}}' and Change, closed, got {r}",
              bool(who) and r.get("head") == f"MODEL of {who[0][1]}" and r.get("word") == "Change" and r.get("first") is True
              and r.get("content") is False)
    ctx.check(f"no request for crew/agent-model yet, got {o.get('gets')}", o.get("gets") == [0, 0])
    f = d.get("first") or {}
    fb = f.get("block") or {}
    ctx.check(f"Change: THAT helper's line (MINE sorter), one request for a1, got {fb.get('kind')} {fb.get('rows')} {f.get('gets')} {f.get('url')!r}",
              fb.get("kind") == "MINE" and fb.get("rows") == line("a1") and (f.get("gets") or [0])[0] == 1 and "agent=a1" in (f.get("url") or ""))
    s = d.get("second") or {}
    sr = s.get("row") or {}
    second = next((w[1] for w in s.get("who") or [] if w[0] == "a4"), None)
    ctx.check(f"the second row chosen: the block closed, the row names it, no request, got {sr} {s.get('gets')}",
              bool(second) and sr.get("head") == f"MODEL of {second}" and sr.get("word") == "Change" and sr.get("content") is False
              and (s.get("gets") or [0])[0] == 1)
    so = d.get("second_open") or {}
    sb = so.get("block") or {}
    ctx.check(f"Change: the second helper's line (BUILT-IN Judge), one request for a4, got {sb.get('kind')} {sb.get('rows')} {so.get('gets')} {so.get('url')!r}",
              sb.get("kind") == "BUILT-IN" and sb.get("rows") == line("a4") and (so.get("gets") or [0])[0] == 2 and "agent=a4" in (so.get("url") or ""))
    bk, bo = d.get("back") or {}, d.get("back_open") or {}
    ctx.check(f"back to the first row: closed, its heading, no request, got {bk.get('row')} {bk.get('gets')}",
              (bk.get("row") or {}).get("head") == f"MODEL of {who[0][1] if who else '?'}" and (bk.get("row") or {}).get("content") is False
              and (bk.get("gets") or [0])[0] == 2)
    ctx.check(f"Change: its line again at once, NO new request, got {(bo.get('block') or {}).get('rows')} {bo.get('gets')}",
              (bo.get("block") or {}).get("rows") == line("a1") and (bo.get("gets") or [0])[0] == 2)
    ref, p = d.get("ref") or "", d.get("picked") or {}
    saved = (K.SAVED_NOW if d.get("took") else K.SAVED_LATER).format(name="sorter", model=ref)
    ctx.check(f"a pick gives the folded group's helper sorter a model: {saved!r}, Undo, the file, got {p.get('rows')} {p.get('undo')!r} {d.get('file_model')!r}",
              bool(ref) and p.get("rows") == [saved] and p.get("undo") == "Undo" and d.get("file_model") == ref)
    k = d.get("kept") or {}
    ctx.check(f"another row chosen and back: the pick's line and Undo kept, nothing asked, got {(k.get('block') or {}).get('rows')} {k.get('gets')}",
              (k.get("block") or {}).get("rows") == p.get("rows") and (k.get("block") or {}).get("undo") == "Undo"
              and (k.get("gets") or [0])[0] == 2 and k.get("open") is True)


@test
def test_choosing_a_row_never_moves_the_rows_of_a_groups_card(ctx: Ctx):
    """3.6.0.16 U4 (the owner's rules: controls hold still; a text is never cut): on a group's card the MODEL row is as tall
    as its longest member's heading needs from the first draw, so choosing a short name, a 60-character one and the short
    one again moves neither [Change] nor any row, and the long heading is whole. Red on 602c5df6: the heading wrapped to
    a second line and every row under it moved by a line."""
    from tests.helpers.studio_sheet_acts_steps import LONG
    d = _ran(ctx, "grouplong")
    s, lg, ag = d.get("short") or {}, d.get("long") or {}, d.get("again") or {}
    ctx.check(f"the short name's heading, then the long one's, then the short one's, got {s.get('head')!r} {lg.get('head')!r} {ag.get('head')!r}",
              s.get("head") == "MODEL of sorter" and lg.get("head") == f"MODEL of {LONG}" and ag.get("head") == "MODEL of sorter")
    ctx.check(f"two rows and [Change] read, got {len(s.get('rows') or [])} {s.get('toggle')}", len(s.get("rows") or []) == 2 and bool(s.get("toggle")))
    for name, x in (("the long one", lg), ("the short one again", ag)):
        ctx.check(f"{name} chosen: [Change] and every row where they were, got {s.get('toggle')} {s.get('rows')} -> {x.get('toggle')} {x.get('rows')}",
                  _near(s.get("toggle"), x.get("toggle")) and len(x.get("rows") or []) == len(s.get("rows") or [])
                  and all(_near(p, q) for p, q in zip(s.get("rows") or [], x.get("rows") or [])))
    w = lg.get("whole") or []
    ctx.check(f"the long heading is whole: no ellipsis, its scroll size its box's, got {w} {lg.get('ellipsis')}",
              len(w) == 4 and w[0] <= w[1] and w[2] <= w[3] and lg.get("ellipsis") is False)


@test
def test_after_a_failed_read_the_rows_hold_the_answers_height(ctx: Ctx):
    """3.6.0.16 U5: the MODEL block's rows keep the height of the first draw of an ANSWER, never of the error row: after a
    failed read, Close, Change and an answer, the kept height is the answer's own. Red on 602c5df6: the error row's."""
    from tests.helpers.studio_sheet_acts_steps import FAIL_WHY
    d = _ran(ctx, "failread")
    e, a = d.get("refused") or {}, d.get("answer") or {}
    ctx.check(f"the failed read's row, holding nothing, got {e}",
              (e.get("text") or "").startswith("Could not read this helper's agent: ") and FAIL_WHY in (e.get("text") or "") and e.get("kept") == "")
    ctx.check(f"the answer's rows keep the answer's own height, got {a}",
              not (a.get("text") or "").startswith("Could not") and bool(a.get("own"))
              and (a.get("kept") == "" or abs(float(str(a.get("kept")).rstrip("px") or 0) - a["own"]) <= 0.5) and abs(a.get("h", 0) - a["own"]) <= 0.5)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
